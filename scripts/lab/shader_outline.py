"""Private, fail-closed two-pass source generator for the accepted Outline shader.

This is a draft recipe, not a shipped shader. All generated files and provenance
stay under ignored work/. It proves exact-source reconstruction and binding
coverage only; Unity compilation, Android backend execution, and appearance are
separate gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_source = Path(__file__).resolve()
ROOT = next((parent for parent in _source.parents if (parent / "scripts/lab/common.py").is_file()), None)
if ROOT is None:
    raise RuntimeError("Cannot locate repository root from the authored action source")
sys.path.insert(0, str(ROOT / "scripts/lab"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import WORK


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


RECIPE_PATH = ROOT / "recipe/shader-outline-candidate.json"
if not RECIPE_PATH.is_file():
    raise RuntimeError("Missing installed public Outline candidate recipe")
RECIPE = read_json(RECIPE_PATH)
EXPECTED = RECIPE["source"]
PROGRAMS = {row["index"]: {"pass": row["pass"], "stage": row["stage"], "sha256": row["sha256"]} for row in RECIPE["programs"]}
EXPECTED_LAYOUTS = {row["index"]: row["layout_sha256"] for row in RECIPE["programs"]}
MODULE_PINS = RECIPE["helpers"]
D3DASM_REVISION = RECIPE["d3dasm"]["revision"]
D3DASM_BINARY_SHA256 = RECIPE["d3dasm"]["binary_sha256"]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_authored_helpers() -> None:
    for name, digest in MODULE_PINS.items():
        candidate = Path(__file__).resolve().parent / name
        path = candidate if candidate.is_file() else ROOT / "scripts/lab" / name
        if sha_file(path) != digest:
            raise RuntimeError(f"Authored shader helper drift: {name}")


def _accepted_bundle() -> tuple[Path, dict]:
    accepted = read_json(WORK / "config/accepted-input.json")
    inventory = read_json(WORK / "inventory/files.json")
    if accepted.get("input_id") != EXPECTED["input_id"] or accepted.get("steam_buildid") != EXPECTED["build_id"]:
        raise RuntimeError("Accepted game input/build changed")
    if inventory.get("input_id") != EXPECTED["input_id"]:
        raise RuntimeError("File inventory belongs to another accepted input")
    config = read_json(WORK / "config/local.json")
    game_path = Path(config["game_path"]).expanduser().resolve()
    data_path = game_path / "Risk of Rain 2_Data" if (game_path / "Risk of Rain 2_Data").is_dir() else game_path
    aa = data_path / "StreamingAssets/aa"
    catalog = aa / "catalog.json"
    if sha_file(catalog) != EXPECTED["catalog_sha256"]:
        raise RuntimeError("Accepted source catalog changed")

    if str(ROOT / "scripts/lab") not in sys.path:
        sys.path.append(str(ROOT / "scripts/lab"))
    from catalog_reader import read_shipped

    record = read_shipped(catalog, "unused", {"labels": [], "providers": []})
    bundle_location = select_bundle_location(
        record, EXPECTED["asset_key"], EXPECTED["asset_location"], EXPECTED["asset_path"], EXPECTED["bundle_hash_in_catalog"]
    )
    bundle_name = bundle_location["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
    bundle_path = aa / "StandaloneWindows64" / bundle_name
    if not bundle_path.is_file() or sha_file(bundle_path) != EXPECTED["bundle_sha256"]:
        raise RuntimeError("Accepted source bundle missing or changed")
    return bundle_path, {
        "input_id": accepted["input_id"],
        "steam_build_id": accepted["steam_buildid"],
        "catalog_sha256": sha_file(catalog),
        "bundle_sha256": sha_file(bundle_path),
        "bundle_relative_path": str(bundle_path.relative_to(aa)),
        "catalog_key": EXPECTED["asset_key"],
        "catalog_location": EXPECTED["asset_location"],
        "asset_path": EXPECTED["asset_path"],
    }


def _shader_object(bundle_path: Path):
    import UnityPy

    env = UnityPy.load(str(bundle_path))
    objects = {obj.path_id: obj for obj in env.objects}
    matches = []
    for obj in env.objects:
        if obj.type.name != "AssetBundle":
            continue
        for asset_path, info in obj.read().m_Container:
            if asset_path == EXPECTED["asset_path"]:
                if info.asset.m_PathID != EXPECTED["asset_path_id"]:
                    raise RuntimeError("Accepted shader path ID changed")
                matches.append(objects.get(info.asset.m_PathID))
    if len(matches) != 1 or matches[0] is None:
        raise RuntimeError("Accepted shader object is absent or ambiguous")
    shader_obj = matches[0]
    raw_data = shader_obj.get_raw_data()
    if sha_bytes(raw_data) != EXPECTED["object_sha256"]:
        raise RuntimeError("Accepted serialized shader object changed")
    tree = shader_obj.read_typetree()
    if tree["m_ParsedForm"]["m_Name"] != EXPECTED["shader_name"]:
        raise RuntimeError("Accepted shader name changed")
    return tree


def validate_program_records(records: list[dict], program_bytes: dict[int, bytes], expected: dict[int, dict]) -> dict[int, bytes]:
    """Join each required record by index, pass, stage, and exact byte digest."""
    selected = [row for row in records if row.get("kind") == "program" and row.get("index") in expected]
    if len(selected) != len(expected):
        raise RuntimeError("Native program record set is missing, duplicate, or extra")
    by_index: dict[int, bytes] = {}
    for rec in selected:
        index = rec["index"]
        spec = expected[index]
        if rec.get("pass_index") != spec["pass"] or rec.get("stage") != spec["stage"]:
            raise RuntimeError("Native program pass/stage identity drift")
        payload = program_bytes.get(index)
        if payload is None or sha_bytes(payload) != spec["sha256"]:
            raise RuntimeError("Native program bytes missing or changed")
        if index in by_index:
            raise RuntimeError("Duplicate native program record index")
        by_index[index] = payload
    if set(by_index) != set(expected):
        raise RuntimeError("One or more required pass programs are missing")
    return by_index


def select_bundle_location(record: dict, key_text: str, location_id: int, asset_path: str, bundle_hash: str) -> dict:
    """Resolve one catalog location through one exact dependency bundle hash."""
    matches = []
    for key in record["keys"]:
        if key["key"] != key_text:
            continue
        for location_index in key["locations"]:
            location = record["locations"][location_index]
            if location["id"] != location_id or location["internalId"] != asset_path:
                raise RuntimeError("Catalog asset location identity drift")
            for dep_id in record["dependencySets"][location["dependencySet"]]:
                dep = record["locations"][dep_id]
                if dep.get("bundle", {}).get("Hash") == bundle_hash:
                    matches.append(dep)
    if len(matches) != 1:
        raise RuntimeError("Shader-to-bundle dependency join is missing or ambiguous")
    return matches[0]


def _program_records(tree: dict) -> tuple[list[dict], dict[int, bytes], bytes]:
    from shader_segments import read_segments

    blob = bytes(tree["compressedBlob"])
    raw, records, programs = read_segments(tree, blob)
    subshaders = tree["m_ParsedForm"]["m_SubShaders"]
    pass_counts = [len(item["m_Passes"]) for item in subshaders]
    pass_platforms = [[int(value) for value in p["m_Platforms"]] for shader in subshaders for p in shader["m_Passes"]]
    if tree.get("platforms") != RECIPE["serialized_platform_codes"] or pass_platforms != RECIPE["pass_platform_codes"]:
        raise RuntimeError("Serialized platform identity drift")
    if pass_counts != [2] or len(records) != 8 or len(programs) != 4:
        raise RuntimeError("Outline shader pass/record topology changed")
    by_index = validate_program_records(records, programs, PROGRAMS)
    selected = [r for r in records if r.get("kind") == "program" and r.get("index") in PROGRAMS]
    return selected, by_index, raw


def _validate_state(state: dict, pass_index: int) -> str:
    from shader_deferred import render_state

    expected = RECIPE["pass_state"][pass_index]
    scalar_state = {name: value for name, value in expected.items() if name not in {"blend", "stencil"}}
    if any(state[name]["val"] != value for name, value in scalar_state.items()):
        raise RuntimeError("Native render-state value drift")
    if state["lighting"] is not False or state["fogMode"] != 0 or state["rtSeparateBlend"]:
        raise RuntimeError("Native fixed-function pass state drift")
    blend = state["rtBlend0"]
    for name, value in expected["blend"].items():
        if blend[name]["val"] != value:
            raise RuntimeError("Native blend state drift")
    for face in ("stencilOpFront", "stencilOpBack"):
        stencil = state[face]
        if any(stencil[name]["val"] != value for name, value in expected["stencil"].items()):
            raise RuntimeError("Native stencil state drift")
    return render_state(state, ui=True, color_mask_names={15: "RGBA"}) + "BlendOp Add\n"


def _field(params: list[dict], *, output: bool) -> dict[str, dict]:
    rows = [item for item in params if item["out"] is output]
    out = {}
    for row in rows:
        semantic = row["semantic"]
        if semantic in out:
            raise RuntimeError("Duplicate native shader I/O semantic")
        if row.get("type", "float") != "float":
            raise RuntimeError("Unmeasured shader interface scalar type")
        out[semantic] = row
    return out


def _struct(name: str, fields: dict[str, dict], *, qualifier_semantics: set[str] | None = None) -> str:
    qualifier_semantics = qualifier_semantics or set()
    lines = [f"struct {name} {{"]
    for semantic, item in fields.items():
        qualifier = "noperspective " if semantic in qualifier_semantics else ""
        lines.append(f"    {qualifier}float{item['columns']} {semantic} : {semantic};")
    lines.append("};")
    return "\n".join(lines)


def _wrapper(pass_index: int, vert_params: list[dict], frag_params: list[dict]) -> str:
    vert_in = _field(vert_params, output=False)
    vert_out = _field(vert_params, output=True)
    frag_in = _field(frag_params, output=False)
    frag_out = _field(frag_params, output=True)
    if set(vert_in) != {"POSITION0", "TEXCOORD0"}:
        raise RuntimeError("Vertex input layout changed")
    if not set(frag_in).issubset(vert_out) or "SV_POSITION0" not in vert_out:
        raise RuntimeError("Vertex/fragment interface no longer joins")
    if set(frag_out) != {"SV_Target0"}:
        raise RuntimeError("Fragment output layout changed")
    if any(row.get("interpolation") for row in vert_out.values()):
        raise RuntimeError("Unmeasured vertex-output interpolation qualifier")
    if any(row.get("interpolation") not in (None, "noperspective") for row in frag_in.values()):
        raise RuntimeError("Unmeasured fragment-input interpolation qualifier")
    for semantic in frag_in:
        if semantic not in vert_out or frag_in[semantic]["columns"] != vert_out[semantic]["columns"]:
            raise RuntimeError("Vertex output/fragment input width mismatch")
    for semantic in vert_out:
        if semantic == "SV_POSITION0" and vert_out[semantic]["columns"] != 4:
            raise RuntimeError("Position output width changed")
    app_fields = {key: vert_in[key] for key in ["POSITION0", "TEXCOORD0"]}
    # Keep the vertex output and pixel input declarations separate. Interpolation
    # modifiers are meaningful on the latter entry interface and must not leak
    # onto a vertex-stage output struct.
    struct = _struct("AppData", app_fields)
    struct += "\n" + _struct(f"Pass{pass_index}VertexOutput", vert_out)
    interpolation = {semantic for semantic, row in frag_in.items() if row.get("interpolation") == "noperspective"}
    struct += "\n" + _struct(f"Pass{pass_index}FragmentInput", frag_in, qualifier_semantics=interpolation)
    call = ["    Pass" + str(pass_index) + "VertexOutput o = (Pass" + str(pass_index) + "VertexOutput)0;"]
    args = ["i." + name for name in vert_in]
    args.extend("o." + name for name in vert_out)
    call.append(f"    native_{1 if pass_index == 0 else 5}(" + ", ".join(args) + ");")
    vertex = f"Pass{pass_index}VertexOutput vert(AppData i) {{\n" + "\n".join(call) + "\n    return o;\n}"
    fragment_args = ["i." + name for name in frag_in]
    fragment_args.append("color")
    frag_index = 3 if pass_index == 0 else 7
    fragment = (
        f"float4 frag(Pass{pass_index}FragmentInput i) : SV_Target0 {{\n"
        "    float4 color = float4(0,0,0,0);\n"
        f"    native_{frag_index}(" + ", ".join(fragment_args) + ");\n"
        "    return color;\n}"
    )
    return struct + "\n" + vertex + "\n" + fragment


def _shaderlab(tree: dict, native: dict[int, tuple[str, list[dict], dict, list[str]]]) -> str:
    parsed = tree["m_ParsedForm"]
    subshader = parsed["m_SubShaders"][0]
    passes = subshader["m_Passes"]
    if len(passes) != 2:
        raise RuntimeError("Expected two source passes")
    sections = []
    for pass_index, (v_index, f_index) in enumerate(((1, 3), (5, 7))):
        vert, vp, vd, vt = native[v_index]
        frag, fp, fd, ft = native[f_index]
        code = "\n".join([vert, frag])
        declarations = {}
        for source in (vd, fd):
            for name, declaration in source.items():
                if name in declarations and declarations[name] != declaration:
                    raise RuntimeError("Conflicting native constant declaration")
                declarations[name] = declaration
        texture_names = list(dict.fromkeys(vt + ft))
        texture_decls = "\n".join(f"Texture2D<float4> {name}; SamplerState sampler{name};" for name in texture_names)
        constant_decls = "\n".join(f"{declaration} {name};" for name, declaration in sorted(declarations.items()))
        wrapper = _wrapper(pass_index, vp, fp)
        state = _validate_state(passes[pass_index]["m_State"], pass_index)
        extra_state = "ZClip On\nAlphaToMask Off\nLighting Off\nFog { Mode Off }"
        sub_tags = subshader.get("m_Tags", {}).get("tags", {})
        tag_lines = " ".join(f'"{k}"="{v}"' for k, v in sorted(sub_tags.items()))
        sections.append(
            "Pass {\n"
            f"{state}"
            f"{extra_state}\n"
            'HLSLPROGRAM\n#pragma target 4.0\n#pragma vertex vert\n#pragma fragment frag\n#include "UnityCG.cginc"\n'
            # The recovered functions are called by the wrappers below. Keep
            # those definitions first for backends that reject later declarations.
            f"{constant_decls}\n{texture_decls}\n{code}\n{wrapper}\nENDHLSL\n}}"
        )
    return (
        f"Shader {json.dumps(EXPECTED['shader_name'])} {{\n"
        "Properties {\n" + properties_text(tree) + "\n}\n"
        "SubShader {\n"
        f"Tags {{{tag_lines}}}\nLOD {subshader['m_LOD']}\n" + "\n".join(sections) + "\n}\n}\n"
    )


def properties_text(tree: dict) -> str:
    from shader_source import properties

    return properties(tree)


def _verify_tool() -> Path:
    source = WORK / "reference-repos/coconutbird__d3dasm"
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    changed = subprocess.run(["git", "-C", str(source), "diff", "--no-ext-diff", "HEAD", "--"], capture_output=True, check=True).stdout
    if head != D3DASM_REVISION or changed:
        raise RuntimeError("Pinned d3dasm source is changed")
    exe = source / "target/release/d3dasm"
    if not exe.is_file() or sha_file(exe) != D3DASM_BINARY_SHA256:
        raise RuntimeError("Pinned d3dasm binary is unavailable or changed")
    return exe


def generate_candidate(output: Path) -> dict:
    output = output.resolve()
    if WORK.resolve() not in output.parents:
        raise RuntimeError("Generated shader output must remain under ignored work/")
    if output.exists():
        raise RuntimeError("Refusing to overwrite existing output")
    verify_authored_helpers()
    tool = _verify_tool()
    bundle, provenance = _accepted_bundle()
    tree = _shader_object(bundle)
    from shader_recovery import normalize
    from shader_segments import selected_layout

    records, program_bytes, raw_segments = _program_records(tree)
    parsed = normalize(tree)
    output.mkdir(parents=True, exist_ok=False)
    intermediates = output / "private-programs"
    intermediates.mkdir()
    native = {}
    rows = []
    for index in sorted(PROGRAMS):
        rec = next(row for row in records if row["index"] == index)
        layout = selected_layout(tree, raw_segments, rec)
        layout_bytes = json.dumps(layout, indent=2).encode()
        if sha_bytes(layout_bytes) != EXPECTED_LAYOUTS[index]:
            raise RuntimeError(f"Native parameter layout changed at record {index}")
        dxbc = program_bytes[index]
        dxbc_path = intermediates / f"program-{index}.dxbc"
        dxbc_path.write_bytes(dxbc)
        asm_path = intermediates / f"program-{index}.d3dasm"
        result = subprocess.run([str(tool), str(dxbc_path), "--emit", "d3dasm"], capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError(f"Pinned d3dasm assembly failed at record {index}")
        asm_path.write_bytes(result.stdout)
        roundtrip = intermediates / f"program-{index}-roundtrip.dxbc"
        result = subprocess.run([str(tool), str(asm_path), "--assemble", "--output", str(roundtrip)], capture_output=True, check=False)
        if result.returncode or sha_file(roundtrip) != PROGRAMS[index]["sha256"]:
            raise RuntimeError(f"DXBC roundtrip failed at record {index}")
        hlsl_path = intermediates / f"program-{index}.d3dasm.hlsl"
        result = subprocess.run([str(tool), str(dxbc_path), "--emit", "hlsl", "--output", str(hlsl_path)], capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError(f"Pinned d3dasm HLSL conversion failed at record {index}")
        hlsl = hlsl_path.read_text(encoding="utf-8")
        from shader_source import bind_hlsl

        function, params, declarations, textures, used = bind_hlsl(hlsl, layout, f"native_{index}")
        native[index] = (function, params, declarations, textures)
        rows.append(
            {
                "record_index": index,
                "pass_index": PROGRAMS[index]["pass"],
                "stage": PROGRAMS[index]["stage"],
                "parameter_layout_sha256": sha_bytes(layout_bytes),
                "program_sha256": sha_bytes(dxbc),
                "roundtrip_identical": True,
                "bound_native_constant_registers": len(used),
                "bound_texture_names": textures,
            }
        )
    shader = _shaderlab(parsed, native)
    source_output = output / "sources"
    source_output.mkdir()
    shader_path = source_output / "OutlineHighlightCandidate.shader"
    shader_path.write_text(shader, encoding="utf-8")
    manifest = {
        "schema": "private-outline-highlight-generated-candidate-r1",
        "success": True,
        "generator_sha256": sha_file(Path(__file__).resolve()),
        "recipe_sha256": sha_file(RECIPE_PATH),
        "helper_sha256": MODULE_PINS,
        "tool": {"name": "d3dasm", "revision": D3DASM_REVISION, "binary_sha256": D3DASM_BINARY_SHA256},
        "source": provenance,
        "object_path_id": EXPECTED["asset_path_id"],
        "serialized_platform_codes": tree.get("platforms"),
        "subshader_pass_counts": [len(s["m_Passes"]) for s in tree["m_ParsedForm"]["m_SubShaders"]],
        "programs": rows,
        "generated_shader_path": "sources/OutlineHighlightCandidate.shader",
        "generated_shader_sha256": sha_file(shader_path),
        "generated_shader_bytes": shader_path.stat().st_size,
        "semantic_equivalence_proven": False,
        "android_compile_or_render_tested": False,
        "appearance_parity_proven": False,
        "scope": "Source-bound two-pass ShaderLab candidate; no Unity compile, Android backend, runtime binding, or rendered appearance claim.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def generate(target: str = "lab") -> dict:
    """Current prototype action with one stable, input-scoped ignored output."""
    if target != "outline-highlight":
        raise RuntimeError("This action only supports --target outline-highlight")
    accepted = read_json(WORK / "config/accepted-input.json")
    if accepted.get("input_id") != EXPECTED["input_id"]:
        raise RuntimeError("Outline target is bound to another accepted input")
    output_template = RECIPE["stable_output"].format(input_id=EXPECTED["input_id"])
    final = WORK / output_template
    if WORK.resolve() not in final.resolve().parents:
        raise RuntimeError("Stable shader candidate path escapes ignored work/")
    final.parent.mkdir(parents=True, exist_ok=True)
    scratch_root = Path(tempfile.mkdtemp(prefix=".outline-highlight-", dir=final.parent))
    scratch = scratch_root / "candidate"
    result = generate_candidate(scratch)
    if final.exists():
        try:
            existing = read_json(final / "manifest.json")
            actual = final / "sources/OutlineHighlightCandidate.shader"
            if existing == result and actual.is_file() and sha_file(actual) == existing["generated_shader_sha256"]:
                shutil.rmtree(scratch_root)
                return existing
        except (OSError, KeyError, json.JSONDecodeError):
            pass
        raise RuntimeError("Stable candidate already exists with different or invalid contents; preserved both outputs")
    os.replace(scratch, final)
    scratch_root.rmdir()
    return read_json(final / "manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the source-bound Outline Highlight candidate into ignored work/.")
    parser.add_argument("--target", default="lab")
    args = parser.parse_args()
    result = generate(args.target)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("success", "generated_shader_sha256", "generated_shader_bytes", "semantic_equivalence_proven", "android_compile_or_render_tested")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
