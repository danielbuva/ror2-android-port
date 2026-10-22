"""Generate a source-bound ignored ShaderLab RampFog candidate.

The action is host-only support. Its candidate is not Android accepted or
semantically equivalent until separately checked in Unity and on device.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = next((p for p in SCRIPT.parents if (p / "scripts/lab/common.py").is_file()), None)
if ROOT is None:
    raise RuntimeError("Cannot find repository root")
sys.path.insert(0, str(ROOT / "scripts/lab"))
from common import WORK, game, read
from shader_segments import read_segments, selected_layout

RECIPE_PATH = ROOT / "recipe/shader-ramp-fog-candidate.json"
if not RECIPE_PATH.is_file():
    raise RuntimeError("Missing installed public RampFog candidate recipe")
RECIPE = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
SOURCE = RECIPE["source"]


def output_path(work: Path, input_id: str) -> Path:
    """Resolve the one recipe-declared stable output beneath work/ only."""
    if input_id != SOURCE["input_id"]:
        raise RuntimeError("Accepted input does not match the fixed RampFog recipe")
    relative = Path(RECIPE["stable_output"].format(input_id=input_id))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("RampFog output recipe escapes work/")
    work = Path(work).resolve()
    output = work / relative
    if work not in output.resolve(strict=False).parents:
        raise RuntimeError("RampFog output is outside work/")
    cursor = work
    for part in relative.parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise RuntimeError("RampFog output parent contains a symlink")
    return output


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_tree(tree: dict, blob: bytes, records: list[dict], programs: dict[int, bytes]) -> None:
    if sha_bytes(blob) != SOURCE["serialized_blob_sha256"]:
        raise RuntimeError("Serialized shader blob drift")
    if tree.get("platforms") != SOURCE["platform_codes"]:
        raise RuntimeError("Serialized platform drift")
    parsed = tree["m_ParsedForm"]
    if parsed["m_Name"] != SOURCE["shader_name"]:
        raise RuntimeError("Shader name drift")
    if len(parsed["m_SubShaders"]) != SOURCE["subshader_count"]:
        raise RuntimeError("Subshader count drift")
    actual_passes = [len(s["m_Passes"]) for s in parsed["m_SubShaders"]]
    if actual_passes != SOURCE["passes_per_subshader"]:
        raise RuntimeError("Pass topology drift")
    if len(records) != len(SOURCE["records"]) or len(programs) != 2:
        raise RuntimeError("Native record or executable count drift")
    for expected in SOURCE["records"]:
        actual = records[expected["index"]]
        for key, value in expected.items():
            if actual.get(key) != value:
                raise RuntimeError(f"Native record {expected['index']} {key} drift")
    if set(programs) != {1, 2}:
        raise RuntimeError("Expected the exact vertex/fragment program indices")


def _verify_tools(input_work: Path, root: Path) -> tuple[Path, Path]:
    from common import sha

    helper_pins = {
        "shader_segments.py": RECIPE["tools"]["shader_segments_sha256"],
        "shader_source.py": RECIPE["tools"]["shader_source_sha256"],
        "shader_deferred.py": RECIPE["tools"]["shader_deferred_sha256"],
    }
    for helper, digest in helper_pins.items():
        if sha(root / "scripts/lab" / helper) != digest:
            raise RuntimeError(f"Pinned authored shader helper drift: {helper}")
    d3d = input_work / RECIPE["tools"]["d3dasm"]["path"]
    spirv = input_work / RECIPE["tools"]["dxbc_spirv"]["path"]
    for name, spec, path in (("d3dasm", RECIPE["tools"]["d3dasm"], d3d), ("dxbc_spirv", RECIPE["tools"]["dxbc_spirv"], spirv)):
        rev = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        if rev != spec["revision"]:
            raise RuntimeError(f"Pinned {name} revision drift")
        dirty = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, timeout=10, check=True
        ).stdout
        if dirty:
            raise RuntimeError(f"Pinned {name} tracked source is modified")
    binary = d3d / "target/release/d3dasm"
    if sha_file(binary) != RECIPE["tools"]["d3dasm"]["binary_sha256"]:
        raise RuntimeError("Pinned d3dasm binary drift")
    disassembler = spirv / "builddir/tools/dxbc_disasm"
    if sha_file(disassembler) != RECIPE["tools"]["dxbc_spirv"]["disassembler_sha256"]:
        raise RuntimeError("Pinned DXBC disassembler binary drift")
    return binary, disassembler


def _source_bundle(input_work: Path) -> Path:
    accepted = read(input_work / "config/accepted-input.json")
    inventory = read(input_work / "inventory/files.json")
    if accepted.get("input_id") != SOURCE["input_id"] or str(accepted.get("steam_buildid")) != SOURCE["build_id"]:
        raise RuntimeError("Accepted game input/build changed")
    if inventory.get("input_id") != SOURCE["input_id"]:
        raise RuntimeError("Inventory belongs to another input")
    rows = [row for row in inventory["files"] if row["path"] == SOURCE["bundle_path"]]
    if len(rows) != 1 or rows[0]["sha256"] != SOURCE["bundle_sha256"]:
        raise RuntimeError("Accepted inventory bundle row drift/ambiguity")
    bundle = game(input_work) / SOURCE["bundle_path"]
    if not bundle.is_file() or sha_file(bundle) != SOURCE["bundle_sha256"]:
        raise RuntimeError("Accepted source bundle missing or changed")
    return bundle


def _extract(bundle: Path) -> tuple[dict, bytes, list[dict], dict[int, bytes]]:
    import UnityPy

    env = UnityPy.load(str(bundle))
    matches = [obj for obj in env.objects if obj.type.name == "Shader" and obj.path_id == SOURCE["shader_path_id"]]
    if len(matches) != 1:
        raise RuntimeError("Accepted shader path ID absent or ambiguous")
    tree = matches[0].read_typetree()
    if tree["m_ParsedForm"]["m_Name"] != SOURCE["shader_name"]:
        raise RuntimeError("Shader path ID resolves to a different name")
    blob = bytes(tree["compressedBlob"])
    raw, records, programs = read_segments(tree, blob)
    validate_tree(tree, blob, records, programs)
    return tree, raw, records, programs


def _layout_hash(tree: dict, raw: bytes, rec: dict) -> str:
    return sha_bytes(json.dumps(selected_layout(tree, raw, rec), sort_keys=True, separators=(",", ":")).encode())


def _signature_rows(text: str) -> dict[str, list[tuple[str, int, str]]]:
    result: dict[str, list[tuple[str, int, str]]] = {"ISGN": [], "OSGN": []}
    active = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("ISGN:", "OSGN:"):
            active = stripped[:-1]
            continue
        if active is None:
            continue
        if not stripped.startswith("|"):
            if stripped and not set(stripped) <= {"-", " "}:
                active = None
            continue
        cols = [part.strip() for part in stripped.split("|")[1:-1]]
        if len(cols) >= 7 and cols[0].isdigit() and cols[1] not in {"Semantic", ""}:
            result[active].append((cols[1], int(cols[2]), cols[3]))
    return result


def _assembly_signature_rows(text: str) -> dict[str, list[tuple[str, int, str]]]:
    result: dict[str, list[tuple[str, int, str]]] = {"ISGN": [], "OSGN": []}
    active = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "// Input Signature:":
            active = "ISGN"
            continue
        if stripped == "// Output Signature:":
            active = "OSGN"
            continue
        if active is None:
            continue
        if stripped.startswith("// ==="):
            active = None
            continue
        if stripped.startswith("//"):
            import re

            match = re.match(r"//\s+([A-Za-z0-9_]+)\s+float v(\d+)\.([xyzw]+)$", stripped)
            if match:
                result[active].append((match.group(1), int(match.group(2)), match.group(3)))
    return result


def _shaderlab_candidate(tree: dict, sources: dict[int, str], layouts: dict[int, dict], signatures: dict[int, dict[str, list[tuple[str, int, str]]]]) -> str:
    from shader_deferred import render_state
    from shader_source import bind_hlsl, properties

    native = {}
    declarations: dict[str, str] = {}
    textures: dict[str, dict] = {}
    bound_layouts = {}
    for index in (1, 2):
        function, params, decls, texture_names, used = bind_hlsl(sources[index], layouts[index], f"native_{index}")
        native[index] = (function, params, used)
        bound_layouts[index] = layouts[index]
        for name, declaration in decls.items():
            if name in declarations and declarations[name] != declaration:
                raise RuntimeError("Cross-stage constant declaration disagreement")
            declarations[name] = declaration
        for texture in bound_layouts[index]["textures"]:
            if texture["name"] not in texture_names:
                raise RuntimeError("Measured texture layout was not consumed by the d3dasm program")
            previous = textures.get(texture["name"])
            if previous is not None and previous != texture:
                raise RuntimeError("Cross-stage texture/sampler contract disagreement")
            textures[texture["name"]] = texture

    vertex_params = native[1][1]
    fragment_params = native[2][1]

    def semantic_name(raw: str) -> str:
        import re

        return raw if re.search(r"\d$", raw) else raw + "0"

    def interface_rows(index: int, direction: str) -> list[dict]:
        return [
            {"semantic": semantic_name(semantic), "register": register, "mask": mask, "columns": len(mask), "type": "float"}
            for semantic, register, mask in signatures[index][direction]
        ]

    vertex_inputs = interface_rows(1, "ISGN")
    vertex_outputs = interface_rows(1, "OSGN")
    fragment_inputs = interface_rows(2, "ISGN")
    fragment_outputs = interface_rows(2, "OSGN")
    for rows in (vertex_inputs, vertex_outputs, fragment_inputs, fragment_outputs):
        if len({row["semantic"] for row in rows}) != len(rows):
            raise RuntimeError("Duplicate native DXBC signature semantic")
    if len(fragment_outputs) != 1 or fragment_outputs[0]["semantic"] != "SV_Target0" or fragment_outputs[0]["columns"] != 4:
        raise RuntimeError("Unmeasured fragment output contract")
    vertex_output_by_semantic = {row["semantic"]: row for row in vertex_outputs}
    for item in fragment_inputs:
        produced = vertex_output_by_semantic.get(item["semantic"])
        if produced is None or produced["columns"] != item["columns"] or produced["type"] != item["type"]:
            raise RuntimeError("Native vertex/fragment DXBC interface mismatch")

    def struct(name: str, rows: list[dict]) -> str:
        fields = []
        for item in rows:
            semantic = item["semantic"]
            kind = item["type"]
            width = item["columns"]
            if kind not in ("float", "uint") or width < 1 or width > 4:
                raise RuntimeError("Unsupported native signature field")
            ty = kind if width == 1 else kind + str(width)
            fields.append(f"    {ty} {semantic} : {semantic};")
        return f"struct {name} {{\n" + "\n".join(fields) + "\n};"

    def native_args(params: list[dict], rows: list[dict], *, outputs: bool, prefix: str) -> tuple[list[str], list[str], list[str]]:
        args = []
        prelude = []
        postlude = []
        locals_by_register: dict[int, str] = {}
        for param in params:
            raw_semantic = semantic_name(param["semantic"])
            row = next((item for item in rows if item["semantic"] == raw_semantic), None)
            if row is None:
                raise RuntimeError(f"Native HLSL parameter lacks a DXBC signature: {raw_semantic}")
            group = [item for item in rows if item["register"] == row["register"]]
            direct = len(group) == 1 and row["mask"] == "xyzw" and param["columns"] == 4
            if direct:
                args.append(("o." if outputs else "i.") + raw_semantic)
                continue
            register = row["register"]
            local = locals_by_register.setdefault(register, f"{prefix}{register}")
            if register not in locals_by_register or not any(line.startswith("float4 " + local + " =") for line in prelude):
                prelude.append(f"float4 {local} = float4(0,0,0,0);")
            args.append(local)
            for item in group:
                statement = f"o.{item['semantic']} = {local}.{item['mask']};" if outputs else f"{local}.{item['mask']} = i.{item['semantic']};"
                target = postlude if outputs else prelude
                if statement not in target:
                    target.append(statement)
        return args, prelude, postlude

    vertex_in = [param for param in vertex_params if not param["out"]]
    vertex_out = [param for param in vertex_params if param["out"]]
    fragment_in = [param for param in fragment_params if not param["out"]]
    fragment_out = [param for param in fragment_params if param["out"]]
    v_in_args, v_in_setup, _ = native_args(vertex_in, vertex_inputs, outputs=False, prefix="nativeIn")
    v_out_args, v_out_setup, v_out_finish = native_args(vertex_out, vertex_outputs, outputs=True, prefix="nativeOut")
    if len(fragment_out) != 1 or fragment_out[0]["semantic"] != "SV_Target0":
        raise RuntimeError("Unexpected fragment native output binding")
    f_in_args, f_in_setup, _ = native_args(fragment_in, fragment_inputs, outputs=False, prefix="nativeIn")
    vertex_entry = (
        "Varyings vert(AppData i) {\n    Varyings o = (Varyings)0;\n"
        + "\n".join("    " + line for line in v_in_setup)
        + ("\n" if v_in_setup and v_out_setup else "")
        + "\n".join("    " + line for line in v_out_setup)
        + "\n    native_1("
        + ", ".join(v_in_args + v_out_args)
        + ");\n"
        + "\n".join("    " + line for line in v_out_finish)
        + "\n    return o;\n}"
    )
    fragment_call_out = ["color"]
    fragment_entry = (
        "float4 frag(Varyings i) : SV_Target0 {\n    float4 color = float4(0,0,0,0);\n"
        + "\n".join("    " + line for line in f_in_setup)
        + "\n    native_2("
        + ", ".join(f_in_args + fragment_call_out)
        + ");\n    return color;\n}"
    )
    constant_text = "\n".join(f"{declaration} {name};" for name, declaration in sorted(declarations.items()))
    texture_text = "\n".join(
        f"{'Texture2D' if item['dimension'] == 2 else 'TextureCube'}<float4> {name}; {item['sampler_type']} sampler{name};"
        for name, item in sorted(textures.items())
    )
    state = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["m_State"]
    if state["lighting"] is not False or int(state["fogMode"]) not in (-1, 0):
        raise RuntimeError("Unmeasured pass lighting/fog contract")
    if int(state["zClip"]["val"]) not in (0, 1) or int(state["alphaToMask"]["val"]) not in (0, 1):
        raise RuntimeError("Unmeasured pass fixed-function state")
    state_text = render_state(state) + "\n"
    state_text += "ZClip " + ("On" if int(state["zClip"]["val"]) else "Off") + "\n"
    state_text += "AlphaToMask " + ("On" if int(state["alphaToMask"]["val"]) else "Off") + "\n"
    state_text += "Lighting Off\n"
    # The accepted source serializes fogMode=-1 (unset), not an explicit mode.
    # Preserve that sentinel by omitting a ShaderLab Fog block. Explicit zero is
    # the measured Off value and can be represented directly.
    if int(state["fogMode"]) == 0:
        state_text += "Fog { Mode Off }\n"
    parsed = tree["m_ParsedForm"]
    subshader = parsed["m_SubShaders"][0]
    tags = subshader.get("m_Tags", {}).get("tags", [])
    tag_map = dict(tags) if isinstance(tags, list) else dict(tags)
    tag_line = " ".join(f"{json.dumps(k)}={json.dumps(v)}" for k, v in sorted(tag_map.items()))
    property_text = properties(tree)
    return (
        f"Shader {json.dumps(SOURCE['shader_name'])} {{\n"
        + ("Properties {\n" + property_text + "\n}\n" if property_text else "")
        + "SubShader {\n"
        + (f"Tags {{ {tag_line} }}\n" if tag_line else "")
        + f"LOD {subshader['m_LOD']}\n"
        + "Pass {\n"
        + state_text
        + 'HLSLPROGRAM\n#pragma target 4.0\n#pragma vertex vert\n#pragma fragment frag\n#include "UnityCG.cginc"\n'
        + constant_text
        + "\n"
        + texture_text
        + "\n"
        + struct("AppData", vertex_inputs)
        + "\n"
        + struct("Varyings", vertex_outputs)
        + "\n"
        # Emit the recovered function definitions before wrappers that call
        # them. Some Unity shader backends reject a call to a later undeclared
        # function even though the HLSL bodies and arguments are otherwise valid.
        + native[1][0]
        + "\n"
        + native[2][0]
        + "\n"
        + vertex_entry
        + "\n"
        + fragment_entry
        + "\nENDHLSL\n}\n}\n}\n"
    )


def _assert_source_unchanged(bundle: Path, initial_hash: str) -> None:
    if not bundle.is_file() or sha_file(bundle) != initial_hash:
        raise RuntimeError("Accepted source bundle changed during RampFog generation")


def _publish_staging(staging: Path, destination: Path, bundle: Path, initial_hash: str) -> None:
    """Publish only after final source verification; never replace an existing result."""
    _assert_source_unchanged(bundle, initial_hash)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"Stable candidate already exists; refusing overwrite: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # mkdir is the exclusive no-overwrite claim. Only after it succeeds do
    # staged children move into the stable input-keyed directory.
    try:
        destination.mkdir()
    except FileExistsError as exc:
        raise RuntimeError(f"Stable candidate already exists; refusing overwrite: {destination}") from exc
    try:
        for child in sorted(staging.iterdir()):
            child.replace(destination / child.name)
        staging.rmdir()
        _assert_source_unchanged(bundle, initial_hash)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def generate(work: Path = WORK, root: Path = ROOT) -> dict:
    work = Path(work).resolve()
    root = Path(root).resolve()
    destination = output_path(work, SOURCE["input_id"])
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"Stable candidate already exists; refusing overwrite: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".ramp-fog-", dir=destination.parent))
    bundle = None
    start_hash = None
    receipt = {
        "success": False,
        "unity_compiled": False,
        "android_shader_acceptance": False,
        "semantic_equivalence_proven": False,
        "visual_parity_proven": False,
    }
    try:
        bundle = _source_bundle(work)
        start_hash = sha_file(bundle)
        d3dasm, dxbc_disasm = _verify_tools(work, root)
        tree, raw, records, programs = _extract(bundle)
        selected = []
        recovered_sources: dict[int, str] = {}
        layouts: dict[int, dict] = {}
        signature_tables: dict[int, dict[str, list[tuple[str, int, str]]]] = {}
        for index in (1, 2):
            rec = records[index]
            program = programs[index]
            dxbc = staging / f"program-{index}.dxbc"
            dxbc.write_bytes(program)
            layout = selected_layout(tree, raw, rec)
            layouts[index] = layout
            (staging / f"program-{index}.layout.json").write_text(json.dumps(layout, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            for fmt in ("d3dasm", "hlsl"):
                argv = [d3dasm, dxbc, "--emit", fmt, "--output", staging / f"program-{index}.{fmt}"]
                result = subprocess.run([str(x) for x in argv], capture_output=True, timeout=180, check=False)
                (staging / f"d3dasm-{index}-{fmt}.stdout").write_bytes(result.stdout)
                (staging / f"d3dasm-{index}-{fmt}.stderr").write_bytes(result.stderr)
                if result.returncode:
                    raise RuntimeError(f"d3dasm {fmt} emission failed for record {index}")
            rebuilt = staging / f"program-{index}.roundtrip.dxbc"
            result = subprocess.run(
                [str(d3dasm), str(staging / f"program-{index}.d3dasm"), "--assemble", "--output", str(rebuilt)], capture_output=True, timeout=180, check=False
            )
            (staging / f"d3dasm-{index}-assemble.stdout").write_bytes(result.stdout)
            (staging / f"d3dasm-{index}-assemble.stderr").write_bytes(result.stderr)
            if result.returncode or sha_file(rebuilt) != sha_file(dxbc):
                raise RuntimeError(f"d3dasm byte roundtrip mismatch for record {index}")
            recovered_sources[index] = (staging / f"program-{index}.hlsl").read_text(encoding="utf-8")
            disassembly = subprocess.run([str(dxbc_disasm), str(dxbc)], capture_output=True, timeout=30, check=False)
            (staging / f"dxbc-disasm-{index}.stdout").write_bytes(disassembly.stdout)
            (staging / f"dxbc-disasm-{index}.stderr").write_bytes(disassembly.stderr)
            if disassembly.returncode:
                raise RuntimeError(f"Independent DXBC signature disassembly failed for record {index}")
            disasm_text = disassembly.stdout.decode("utf-8", errors="strict")
            assembly_text = (staging / f"program-{index}.d3dasm").read_text(encoding="utf-8")
            signature = _signature_rows(disasm_text)
            assembly_signature = _assembly_signature_rows(assembly_text)
            if signature != assembly_signature:
                raise RuntimeError(f"Independent signature readers disagree for record {index}")
            signature_tables[index] = signature
            selected.append(
                {
                    "index": index,
                    "gpu_type": rec["gpu_type"],
                    "stage": rec["stage"],
                    "keywords": rec["keywords"],
                    "program_sha256": sha_file(dxbc),
                    "record_sha256": rec["sha256"],
                    "parameter_index": rec["parameter_index"],
                    "layout_sha256": _layout_hash(tree, raw, rec),
                    "signature": signature,
                    "roundtrip_identical": True,
                    "independent_signature_readers_agree": True,
                }
            )
        (staging / "native-records.json").write_text(json.dumps(records, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        parsed = tree["m_ParsedForm"]
        state = parsed["m_SubShaders"][0]["m_Passes"][0]["m_State"]
        (staging / "serialized-pass-state.json").write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        shader_source = _shaderlab_candidate(tree, recovered_sources, layouts, signature_tables)
        sources_dir = staging / "sources"
        sources_dir.mkdir()
        shader_path = sources_dir / "RampFogCandidate.shader"
        shader_path.write_text(shader_source, encoding="utf-8")
        candidate = {
            "schema": 1,
            "kind": "local-source-bound-ramp-fog-candidate",
            "generator_sha256": sha_file(SCRIPT),
            "recipe_sha256": sha_file(RECIPE_PATH),
            "helper_sha256": {
                name: recipe_hash
                for name, recipe_hash in {
                    "shader_segments.py": RECIPE["tools"]["shader_segments_sha256"],
                    "shader_source.py": RECIPE["tools"]["shader_source_sha256"],
                    "shader_deferred.py": RECIPE["tools"]["shader_deferred_sha256"],
                }.items()
            },
            "tool_pins": RECIPE["tools"],
            "source": {key: SOURCE[key] for key in ["input_id", "build_id", "bundle_path", "bundle_sha256", "shader_path_id", "shader_name"]},
            "programs": selected,
            "pass_state_file": "serialized-pass-state.json",
            "fog_mode_mapping": "source sentinel -1 preserved by omitting a Fog block" if int(state["fogMode"]) == -1 else "explicit native Fog Off",
            "record_table_file": "native-records.json",
            "generated_shader": "sources/RampFogCandidate.shader",
            "generated_shader_sha256": sha_file(shader_path),
            "generated_shader_bytes": shader_path.stat().st_size,
            "unity_shaderlab_emitted": True,
            "semantic_equivalence_proven": False,
            "android_shader_acceptance": False,
        }
        (staging / "candidate.json").write_text(json.dumps(candidate, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        receipt.update(
            {
                "success": True,
                "input_id": SOURCE["input_id"],
                "bundle_path": SOURCE["bundle_path"],
                "bundle_sha256": SOURCE["bundle_sha256"],
                "shader_path_id": SOURCE["shader_path_id"],
                "shader_name": SOURCE["shader_name"],
                "record_count": len(records),
                "executable_program_count": len(programs),
                "selected_programs": selected,
                "serialized_state_retained": True,
                "generated_shader": "sources/RampFogCandidate.shader",
                "generated_shader_sha256": candidate["generated_shader_sha256"],
                "source_program_math_public": False,
                "unity_compiled": False,
                "android_shader_acceptance": False,
                "semantic_equivalence_proven": False,
                "visual_parity_proven": False,
                "scope": "Accepted-input-scoped local ShaderLab candidate using existing native HLSL/resource/state helpers; no Unity compile, Android backend, runtime binding, rendering, or semantic-equivalence claim.",
            }
        )
        if bundle is None or start_hash is None:
            raise RuntimeError("No accepted source bundle was bound")
        _assert_source_unchanged(bundle, start_hash)
        receipt["source_bundle_unchanged"] = True
        receipt["output"] = str(destination.relative_to(work))
        (staging / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        _publish_staging(staging, destination, bundle, start_hash)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return receipt


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True, indent=2))
