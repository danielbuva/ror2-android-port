"""Generate ignored ShaderLab candidates from accepted native translucent shaders."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import UnityPy

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "scripts/lab/shader_segments.py").is_file())
PACKET = Path(__file__).resolve().parent
RECIPE_PATH = ROOT / "recipe/shader-translucent-candidate.json"
if not RECIPE_PATH.is_file():
    raise RuntimeError("Missing public translucent candidate recipe")
RECIPE = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
SOURCE = RECIPE["source"]
D3DASM_REVISION = RECIPE["tools"]["d3dasm"]["revision"]
D3DASM_SHA256 = RECIPE["tools"]["d3dasm"]["binary_sha256"]
DXBC_DISASM_SHA256 = RECIPE["tools"]["dxbc_spirv"]["disassembler_sha256"]
OBJECTS = {row["name"]: row["path_id"] for row in RECIPE["shaders"]}
EXPECTED_IDENTITIES = {
    "DownTent": (8446615176080386013, "Hidden/DownTent", 2537, "e4abd95960ed75f4a9f59cac7c40bd9d"),
    "EfficientBlur": (6370232586618374777, "Hidden/EfficientBlur", 2538, "12e87e7c7fde8e74db9f75172456c5c3"),
    "FillCrop": (5721449320467667425, "Hidden/FillCrop", 2539, "d996ab4381100014d99e25e68e9aac84"),
    "QuickDumbBlur": (-5627814109785558414, "UI/QuickDumbBlur", 2540, "b12e02e9a9b684543a286089a03cb04b"),
}
EXPECTED_SHADER_ROWS = [
    {
        "catalog_key": "e4abd95960ed75f4a9f59cac7c40bd9d",
        "catalog_location": 2537,
        "guid": "b950b7b50f8e9734e8b26f23f8409418",
        "manifest": "manifests/DownTent.json",
        "name": "DownTent",
        "output": "sources/DownTent.shader",
        "pass_count": 1,
        "path_id": 8446615176080386013,
        "primary_key": "TranslucentImage/DownTent.shader",
        "serialized_name": "Hidden/DownTent",
        "source_asset_path": "Assets/Le Tai's Asset/TranslucentImage/FormerResources/DownTent.shader",
    },
    {
        "catalog_key": "12e87e7c7fde8e74db9f75172456c5c3",
        "catalog_location": 2538,
        "guid": "f7022f9f8b1c05f45b0e69d890d31534",
        "manifest": "manifests/EfficientBlur.json",
        "name": "EfficientBlur",
        "output": "sources/EfficientBlur.shader",
        "pass_count": 2,
        "path_id": 6370232586618374777,
        "primary_key": "TranslucentImage/EfficientBlur.shader",
        "serialized_name": "Hidden/EfficientBlur",
        "source_asset_path": "Assets/Le Tai's Asset/TranslucentImage/FormerResources/EfficientBlur.shader",
    },
    {
        "catalog_key": "d996ab4381100014d99e25e68e9aac84",
        "catalog_location": 2539,
        "guid": "89c413d50c7159d42a05c19230c43769",
        "manifest": "manifests/FillCrop.json",
        "name": "FillCrop",
        "output": "sources/FillCrop.shader",
        "pass_count": 1,
        "path_id": 5721449320467667425,
        "primary_key": "TranslucentImage/FillCrop.shader",
        "serialized_name": "Hidden/FillCrop",
        "source_asset_path": "Assets/Le Tai's Asset/TranslucentImage/FormerResources/FillCrop.shader",
    },
    {
        "catalog_key": "b12e02e9a9b684543a286089a03cb04b",
        "catalog_location": 2540,
        "guid": "e5c4572c0a575514bb041a5a82e33cea",
        "keyword_axes": ["FLIP_V"],
        "manifest": "manifests/QuickDumbBlur.json",
        "name": "QuickDumbBlur",
        "output": "sources/QuickDumbBlur.shader",
        "pass_count": 1,
        "path_id": -5627814109785558414,
        "primary_key": "TranslucentImage/QuickDumbBlur.shader",
        "serialized_name": "UI/QuickDumbBlur",
        "source_asset_path": "Assets/Le Tai's Asset/TranslucentImage/FormerResources/QuickDumbBlur.shader",
    },
]
EXPECTED_HELPERS = {
    "shader_deferred.py": "9fa121e6b5f3e769c365eb3b4092c2a460c7a05bbe5617f3ccba01958acaef39",
    "shader_metadata.py": "1701b9a0f621cd29c4f16fbb594676401d4a81cf2d02b5ab10664ce8aa629318",
    "shader_ramp_fog.py": "7e7fe1089b5a64f80e30151948072e9becd658569e8fd277dc02a4335af9e865",
    "shader_segments.py": "2cba875459a7ea35f9f0279696569fd05a6429c9f4b206ad331d5b723dca4872",
    "shader_source.py": "d712407d715c37e79806207bd763bf2dc7d502a861366af2784ae8e63e3c026c",
}

sys.path.insert(0, str(ROOT / "scripts/lab"))
from shader_deferred import render_state  # noqa: E402
from shader_ramp_fog import _assembly_signature_rows, _signature_rows  # noqa: E402
from shader_segments import read_segments, selected_layout  # noqa: E402
import shader_source  # noqa: E402
from common import WORK, game, read


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_tool_pins() -> None:
    d3dasm_repo = ROOT / "work" / RECIPE["tools"]["d3dasm"]["path"]
    D3DASM = d3dasm_repo / "target/release/d3dasm"
    DXBC_DISASM = ROOT / "work" / RECIPE["tools"]["dxbc_spirv"]["path"]
    revision = subprocess.run(
        ["git", "-C", str(d3dasm_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != D3DASM_REVISION or sha(D3DASM) != D3DASM_SHA256:
        raise RuntimeError("Pinned d3dasm source or binary drift")
    if sha(DXBC_DISASM) != DXBC_DISASM_SHA256:
        raise RuntimeError("Pinned independent DXBC disassembler drift")


def output_path(work: Path, input_id: str) -> Path:
    if input_id != SOURCE["input_id"]:
        raise RuntimeError("Accepted input does not match translucent recipe")
    relative = Path(RECIPE["stable_output"].format(input_id=input_id))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Translucent output recipe escapes work/")
    work = _absolute_without_symlink_components(Path(work))
    if not work.is_dir():
        raise RuntimeError("Translucent work root must be an existing directory")
    output = work / relative
    if work not in output.parents:
        raise RuntimeError("Translucent output resolves outside work/")
    _absolute_without_symlink_components(output)
    return output


def _absolute_without_symlink_components(path: Path) -> Path:
    """Normalize lexically while checking each supplied component before resolution."""
    expanded = Path(os.path.expanduser(os.fspath(path)))
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    cursor = Path(expanded.anchor)
    for part in expanded.parts[1:]:
        if part in ("", "."):
            continue
        if part == "..":
            cursor = cursor.parent
            continue
        cursor = cursor / part
        if cursor.is_symlink():
            raise RuntimeError("Translucent path may not contain a symlink component")
    return Path(os.path.abspath(os.fspath(expanded)))


def accepted_bundle(work: Path) -> Path:
    accepted = read(work / "config/accepted-input.json")
    inventory = read(work / "inventory/files.json")
    if accepted.get("input_id") != SOURCE["input_id"] or str(accepted.get("steam_buildid")) != SOURCE["build_id"]:
        raise RuntimeError("Accepted input/build differs from translucent recipe")
    if inventory.get("input_id") != SOURCE["input_id"]:
        raise RuntimeError("Inventory belongs to a different accepted input")
    rows = [r for r in inventory.get("files", []) if r.get("path") == SOURCE["bundle_path"]]
    if len(rows) != 1 or rows[0].get("sha256") != SOURCE["bundle_sha256"]:
        raise RuntimeError("Translucent source bundle inventory row is missing/ambiguous/drifted")
    path = game(work) / SOURCE["bundle_path"]
    if not path.is_file() or sha(path) != SOURCE["bundle_sha256"]:
        raise RuntimeError("Accepted installation source bundle is missing or changed")
    return path


def verify_authored_helpers() -> None:
    pins = RECIPE["tools"]["authored_helpers"]
    if pins != EXPECTED_HELPERS:
        raise RuntimeError("Authored helper set or digest differs from the reviewed pins")
    for name, expected in pins.items():
        path = ROOT / "scripts/lab" / name
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"Authored helper pin drift: {name}")


def validate_recipe() -> None:
    if RECIPE.get("schema") != 1 or RECIPE.get("target") != "translucent-image-camera-shaders":
        raise RuntimeError("Unknown translucent candidate recipe")
    if RECIPE.get("candidate_schema") != "local-source-bound-translucent-wrapper-candidate-r1":
        raise RuntimeError("Translucent candidate manifest schema differs from reviewed value")
    if SOURCE != {
        "input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
        "build_id": "25475991",
        "bundle_path": "Risk of Rain 2_Data/StreamingAssets/aa/StandaloneWindows64/translucentimage_shader_assets_all_e047e7a8b87bfe680ee207a3f02be2ce.bundle",
        "bundle_sha256": "e10aaf15affd3058e0f3da79e49ec52bd22ddabd460cbf507a34107e73f87861",
    }:
        raise RuntimeError("Accepted source identity differs from the reviewed translucent recipe")
    if set(OBJECTS) != set(EXPECTED_IDENTITIES) or RECIPE.get("shaders") != EXPECTED_SHADER_ROWS:
        raise RuntimeError("Translucent recipe metadata differs from the exact reviewed identities")
    if RECIPE.get("stable_output") != "generated-shader-candidates/translucent-camera-r2/{input_id}":
        raise RuntimeError("Translucent stable output root differs from the reviewed path")
    expected_tools = {
        "authored_helpers": EXPECTED_HELPERS,
        "d3dasm": {
            "binary_sha256": D3DASM_SHA256,
            "path": "reference-repos/coconutbird__d3dasm",
            "revision": D3DASM_REVISION,
        },
        "dxbc_spirv": {
            "disassembler_sha256": DXBC_DISASM_SHA256,
            "path": "reference-repos/doitsujin__dxbc-spirv/builddir/tools/dxbc_disasm",
        },
    }
    if RECIPE.get("tools") != expected_tools:
        raise RuntimeError("Translucent tool/helper pin metadata differs from reviewed values")
    if RECIPE.get("acceptance") != {
        "unity_compiled": False,
        "android_accepted": False,
        "semantic_equivalence_proven": False,
        "visual_parity_proven": False,
    }:
        raise RuntimeError("Translucent candidate recipe may not claim acceptance")


def validate_output_layout(shader_specs: list[dict], program_indices: dict[str, list[int]]) -> list[str]:
    """Preflight every output path, including intermediates and reserved reports."""
    outputs = ["manifest.json"]
    for spec in shader_specs:
        outputs.extend((spec["output"], spec["manifest"]))
        for index in program_indices[spec["name"]]:
            stem = f"{spec['name']}-{index}"
            outputs.extend(f"{stem}{suffix}" for suffix in (".dxbc", ".d3dasm", ".hlsl", ".roundtrip.dxbc"))
    normalized = []
    for value in outputs:
        if not isinstance(value, str) or "\\" in value:
            raise RuntimeError("Translucent artifact path is not a safe relative POSIX path")
        relative = Path(value)
        if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
            raise RuntimeError("Translucent artifact path escapes the output directory")
        normalized.append(relative.as_posix().casefold())
    if len(normalized) != len(set(normalized)):
        raise RuntimeError("Translucent shader, manifest, intermediate, or report paths collide")
    sorted_paths = sorted(normalized)
    for index, current in enumerate(sorted_paths):
        prefix = current + "/"
        if any(other.startswith(prefix) for other in sorted_paths[index + 1 :]):
            raise RuntimeError("Translucent artifact file path collides with an output directory")
    return outputs


def preflight_output(work: Path, input_id: str, shader_specs: list[dict], program_indices: dict[str, list[int]]) -> Path:
    """Resolve the stable root and all artifact names before the first output write."""
    destination = output_path(work, input_id)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("Refusing to overwrite existing stable candidate output")
    validate_output_layout(shader_specs, program_indices)
    return destination


def semantic_name(semantic: str, register: int) -> str:
    if semantic in ("SV_POSITION", "SV_POSITION0"):
        return "SV_POSITION0"
    return semantic if re.search(r"\d$", semantic) else semantic + "0"


def interface_rows(rows: list[tuple[str, int, str]]) -> list[dict]:
    return [
        {
            "semantic": semantic_name(semantic, register),
            "register": register,
            "mask": mask,
            "columns": len(mask),
            "type": "float",
        }
        for semantic, register, mask in rows
    ]


def struct(name: str, rows: list[dict]) -> str:
    fields = []
    for item in rows:
        width = item["columns"]
        if item["type"] != "float" or not 1 <= width <= 4:
            raise RuntimeError("Unsupported measured signature type/width")
        ty = "float" if width == 1 else f"float{width}"
        fields.append(f"    {ty} {item['semantic']} : {item['semantic']};")
    return f"struct {name} {{\n" + "\n".join(fields) + "\n};"


def format_constant_declaration(declaration: str, name: str) -> str:
    """Place a measured HLSL array suffix after the identifier, as required by HLSL."""
    match = re.fullmatch(r"(.+)\[(\d+)\]", declaration)
    if match:
        return f"{match.group(1)} {name}[{match.group(2)}];"
    return f"{declaration} {name};"


def native_args(params: list[dict], rows: list[dict], *, outputs: bool, prefix: str) -> tuple[list[str], list[str], list[str]]:
    args: list[str] = []
    prelude: list[str] = []
    postlude: list[str] = []
    local_for_register: dict[int, str] = {}
    for param in params:
        # Match by semantic string; register-indexed HLSL semantics are explicit.
        match = next(
            (row for row in rows if row["semantic"] == semantic_name(param["semantic"], row["register"])),
            None,
        )
        if match is None:
            raise RuntimeError("Recovered entry parameter is absent from native DXBC signature")
        register = match["register"]
        group = [row for row in rows if row["register"] == register]
        direct = len(group) == 1 and match["mask"] == "xyzw" and param["columns"] == 4
        if direct:
            args.append(("o." if outputs else "i.") + match["semantic"])
            continue
        local = local_for_register.setdefault(register, f"{prefix}{register}")
        if not any(line.startswith("float4 " + local + " =") for line in prelude):
            prelude.append(f"float4 {local} = float4(0,0,0,0);")
        args.append(local)
        for row in group:
            statement = f"o.{row['semantic']} = {local}.{row['mask']};" if outputs else f"{local}.{row['mask']} = i.{row['semantic']};"
            target = postlude if outputs else prelude
            if statement not in target:
                target.append(statement)
    return args, prelude, postlude


def conditional_call(
    variants: dict[tuple[str, ...], str],
    args_by_variant: dict[tuple[str, ...], list[str]],
) -> str:
    keys = sorted(variants)
    union = sorted({keyword for key in keys for keyword in key})
    if not union:
        if len(keys) != 1 or keys[0] != ():
            raise RuntimeError("Unmeasured unconditional variant table")
        return variants[()]
    if len(union) > 1:
        raise RuntimeError("Only the measured single-keyword variant axis is supported")
    expected = {tuple(k for i, k in enumerate(union) if bits & (1 << i)) for bits in range(1 << len(union))}
    if set(keys) != expected:
        raise RuntimeError("Serialized variants do not form complete independent keyword axes")
    lines = []
    for i, key in enumerate(k for k in keys if k):
        condition = " && ".join(f"defined({keyword})" for keyword in key)
        lines.append(("#if " if i == 0 else "#elif ") + condition)
        lines.append(variants[key] + ";")
    lines.extend(["#else", variants[()] + ";", "#endif"])
    return "\n".join(lines)


def selected_pass_records(native_pass: dict, record_by_index: dict[int, dict]) -> dict[str, dict[tuple[str, ...], dict]]:
    """Join the D3D11 per-pass program table, preserving serialized blob reuse."""
    selected: dict[str, dict[tuple[str, ...], dict]] = {
        "progVertex": {},
        "progFragment": {},
    }
    for stage in selected:
        entries = native_pass[stage]["m_PlayerSubPrograms"][3]
        if not entries:
            raise RuntimeError(f"Pass has no native {stage}; refuse to substitute")
        for entry in entries:
            index = entry["m_BlobIndex"]
            record = record_by_index.get(index)
            if record is None or record["stage"] != stage:
                raise RuntimeError("Pass blob/stage join failed")
            keywords = tuple(record["keywords"])
            if len(keywords) != len(entry["m_KeywordIndices"]):
                raise RuntimeError("Serialized keyword count disagrees with program record")
            if keywords in selected[stage]:
                raise RuntimeError("Duplicate keyword variant in one stage/pass")
            selected[stage][keywords] = record
    if set(selected["progVertex"]) != set(selected["progFragment"]):
        raise RuntimeError("Vertex and fragment keyword variants do not pair exactly")
    return selected


def validate_wrapper_metadata(shader_name: str, subshader: dict) -> None:
    """Fail closed on serialized pass fields this wrapper does not reproduce."""
    if subshader.get("m_LOD") != 0 or subshader.get("m_Tags", {}).get("tags") != []:
        raise RuntimeError("Unmeasured translucent subshader LOD/tags")
    passes = subshader.get("m_Passes")
    if not isinstance(passes, list) or not passes:
        raise RuntimeError("Native translucent shader has no measured passes")
    for index, native_pass in enumerate(passes):
        expected = {
            "m_Type": 0,
            "m_ProgramMask": 6,
            "m_UseName": "",
            "m_Name": "",
            "m_TextureName": "",
            "m_Tags": {"tags": []},
            "m_HasInstancingVariant": False,
            "m_HasProceduralInstancingVariant": False,
        }
        for field, value in expected.items():
            if native_pass.get(field) != value:
                raise RuntimeError(f"Pass {index}: unsupported serialized {field} contract")
        state = native_pass.get("m_State")
        if not isinstance(state, dict):
            raise RuntimeError(f"Pass {index}: missing serialized render state")
        if state.get("m_Name") != "":
            raise RuntimeError(f"Pass {index}: unsupported named render state")
        if state.get("m_LOD") != 0 or state.get("lighting") is not False:
            raise RuntimeError(f"Pass {index}: unsupported pass LOD/lighting contract")
        # The existing ShaderLab mapper consumes target 0; verify every other
        # target is identical before relying on Unity's single-target default.
        blend0 = state.get("rtBlend0")
        if not isinstance(blend0, dict) or any(state.get(f"rtBlend{target}") != blend0 for target in range(1, 8)):
            raise RuntimeError(f"Pass {index}: independent MRT blend state is unsupported")
        if state.get("conservative", {}).get("val") != 0:
            raise RuntimeError(f"Pass {index}: conservative rasterization is unsupported")
        if state.get("offsetFactor", {}).get("val") != 0 or state.get("offsetUnits", {}).get("val") != 0:
            raise RuntimeError(f"Pass {index}: polygon offset is unsupported")
        if state.get("fogMode") not in (-1, 0):
            raise RuntimeError(f"Pass {index}: active/unknown fog mode is unsupported")


def emit_pass(
    tree: dict,
    pass_index: int,
    stage_records: dict[str, dict[tuple[str, ...], dict]],
    hlsl_by_index: dict[int, str],
    layouts: dict[int, dict],
    signatures: dict[int, dict],
    bind_hlsl,
) -> tuple[str, dict]:
    native: dict[int, tuple[str, list[dict], list[dict], list[str], list[dict]]] = {}
    declarations: dict[str, str] = {}
    textures: dict[str, dict] = {}
    evidence: dict[str, dict] = {}
    for stage in ("progVertex", "progFragment"):
        for keywords, record in stage_records[stage].items():
            index = record["index"]
            function, params, decls, texture_names, used = bind_hlsl(hlsl_by_index[index], layouts[index], f"native_{index}")
            native[index] = (function, params, decls, texture_names, used)
            for name, declaration in decls.items():
                if name in declarations and declarations[name] != declaration:
                    raise RuntimeError("Conflicting measured constant declarations across variants/stages")
                declarations[name] = declaration
            for texture in layouts[index]["textures"]:
                if texture["name"] not in texture_names:
                    raise RuntimeError("Measured native texture was not consumed by its program")
                if texture["name"] in textures and textures[texture["name"]] != texture:
                    raise RuntimeError("Conflicting measured texture contract")
                textures[texture["name"]] = texture
            evidence[str(index)] = {
                "stage": stage,
                "keywords": list(keywords),
                "native_record_index": index,
                "layout_sha256": hashlib.sha256(json.dumps(layouts[index], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            }

    vertex_records = stage_records["progVertex"]
    fragment_records = stage_records["progFragment"]
    if set(vertex_records) != set(fragment_records):
        raise RuntimeError("Vertex and fragment keyword variants do not pair exactly")
    v_input_rows = interface_rows(signatures[next(iter(vertex_records.values()))["index"]]["ISGN"])
    v_output_rows = interface_rows(signatures[next(iter(vertex_records.values()))["index"]]["OSGN"])
    f_input_rows = interface_rows(signatures[next(iter(fragment_records.values()))["index"]]["ISGN"])
    f_output_rows = interface_rows(signatures[next(iter(fragment_records.values()))["index"]]["OSGN"])
    if f_output_rows != [
        {
            "semantic": "SV_Target0",
            "register": 0,
            "mask": "xyzw",
            "columns": 4,
            "type": "float",
        }
    ]:
        raise RuntimeError("Unmeasured native fragment target contract")
    produced = {row["semantic"]: row for row in v_output_rows}
    for row in f_input_rows:
        if produced.get(row["semantic"], {}).get("columns") != row["columns"]:
            raise RuntimeError("Vertex/fragment signature mismatch")
    for stage, mapping, rows in (
        ("progVertex", vertex_records, v_input_rows),
        ("progFragment", fragment_records, f_input_rows),
    ):
        for keywords, record in mapping.items():
            index = record["index"]
            current = interface_rows(signatures[index]["ISGN"])
            if current != rows:
                raise RuntimeError(f"{stage} keyword variants have differing input signatures")
    for keywords, record in vertex_records.items():
        if interface_rows(signatures[record["index"]]["OSGN"]) != v_output_rows:
            raise RuntimeError("Vertex keyword variants have differing output signatures")
    for keywords, record in fragment_records.items():
        if interface_rows(signatures[record["index"]]["OSGN"]) != f_output_rows:
            raise RuntimeError("Fragment keyword variants have differing output signatures")

    functions = []
    vertex_calls: dict[tuple[str, ...], str] = {}
    fragment_calls: dict[tuple[str, ...], str] = {}
    vertex_args: dict[tuple[str, ...], list[str]] = {}
    fragment_args: dict[tuple[str, ...], list[str]] = {}
    for keywords, record in vertex_records.items():
        idx = record["index"]
        function, params = native[idx][0], native[idx][1]
        function = re.sub(r"\bvoid main\(", f"void native_{idx}(", function, count=1)
        functions.append(function)
        inputs = [p for p in params if not p["out"]]
        outputs = [p for p in params if p["out"]]
        in_args, in_setup, _ = native_args(inputs, v_input_rows, outputs=False, prefix=f"vin{idx}_")
        out_args, out_setup, out_finish = native_args(outputs, v_output_rows, outputs=True, prefix=f"vout{idx}_")
        body = [
            "{ Varyings o=(Varyings)0;",
            *in_setup,
            *out_setup,
            f"native_{idx}(" + ", ".join(in_args + out_args) + ");",
            *out_finish,
            "return o; }",
        ]
        vertex_calls[keywords] = " ".join(body)
    for keywords, record in fragment_records.items():
        idx = record["index"]
        function, params = native[idx][0], native[idx][1]
        function = re.sub(r"\bvoid main\(", f"void native_{idx}(", function, count=1)
        functions.append(function)
        inputs = [p for p in params if not p["out"]]
        in_args, in_setup, _ = native_args(inputs, f_input_rows, outputs=False, prefix=f"fin{idx}_")
        fragment_calls[keywords] = (
            "{ float4 color=float4(0,0,0,0); " + " ".join(in_setup) + f" native_{idx}(" + ", ".join(in_args + ["color"]) + "); return color; }"
        )

    keywords = sorted({keyword for variant in vertex_records for keyword in variant})
    variant_directives = "\n".join(f"#pragma multi_compile __ {keyword}" for keyword in keywords)
    vert = "Varyings vert(AppData i) {\n" + conditional_call(vertex_calls, vertex_args) + "\n}"
    frag_calls = conditional_call(fragment_calls, fragment_args)
    frag = "float4 frag(Varyings i) : SV_Target0 {\n" + frag_calls + "\n}"
    constant_text = "\n".join(format_constant_declaration(declaration, name) for name, declaration in sorted(declarations.items()))
    texture_text = "\n".join(
        f"{'Texture2D' if item['dimension'] == 2 else 'TextureCube'}<float4> {name}; {item['sampler_type']} sampler{name};"
        for name, item in sorted(textures.items())
    )
    state = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][pass_index]["m_State"]
    state_text = (
        render_state(state)
        + "\nZClip "
        + ("On" if int(state["zClip"]["val"]) else "Off")
        + "\nAlphaToMask "
        + ("On" if int(state["alphaToMask"]["val"]) else "Off")
        + "\nLighting Off\n"
    )
    if int(state["fogMode"]) == 0:
        state_text += "Fog { Mode Off }\n"
    code = (
        f'Pass {{\n{state_text}HLSLPROGRAM\n#pragma target 4.0\n#pragma vertex vert\n#pragma fragment frag\n{variant_directives}\n#include "UnityCG.cginc"\n'
        + constant_text
        + "\n"
        + texture_text
        + "\n"
        + struct("AppData", v_input_rows)
        + "\n"
        + struct("Varyings", v_output_rows)
        + "\n"
        + "\n".join(functions)
        + "\n"
        + vert
        + "\n"
        + frag
        + "\nENDHLSL\n}"
    )
    return code, {
        "pass_index": pass_index,
        "keyword_variants": [list(k) for k in sorted(vertex_records)],
        "programs": evidence,
    }


def main(work: Path | None = None) -> dict:
    global OUT, D3DASM, DXBC_DISASM
    work = _absolute_without_symlink_components(Path(work or WORK))
    validate_recipe()
    accepted = read(work / "config/accepted-input.json")
    input_id = accepted.get("input_id")
    OUT = output_path(work, input_id)
    BUNDLE = accepted_bundle(work)
    D3DASM = ROOT / "work" / RECIPE["tools"]["d3dasm"]["path"] / "target/release/d3dasm"
    DXBC_DISASM = ROOT / "work" / RECIPE["tools"]["dxbc_spirv"]["path"]
    if OUT.exists():
        raise RuntimeError("Refusing to overwrite existing stable candidate output")
    verify_authored_helpers()
    checked_tool_pins()
    env = UnityPy.load(str(BUNDLE))
    prepared: dict[str, tuple[dict, bytes, list[dict], dict[int, bytes]]] = {}
    program_indices: dict[str, list[int]] = {}
    resolved_path_ids: set[int] = set()
    for shader_spec in RECIPE["shaders"]:
        shader_name = shader_spec["name"]
        path_id = OBJECTS[shader_name]
        objects = [obj for obj in env.objects if obj.type.name == "Shader" and obj.path_id == path_id]
        if len(objects) != 1 or path_id in resolved_path_ids:
            raise RuntimeError(f"{shader_name}: exact Shader identity is missing or ambiguous")
        resolved_path_ids.add(path_id)
        tree = objects[0].read_typetree()
        if tree["m_ParsedForm"]["m_Name"] != shader_spec["serialized_name"]:
            raise RuntimeError(f"{shader_name}: serialized shader name drift")
        raw, records, programs = read_segments(tree, bytes(tree["compressedBlob"]))
        subshader = tree["m_ParsedForm"]["m_SubShaders"][0]
        validate_wrapper_metadata(shader_name, subshader)
        if len({row["index"] for row in records}) != len(records):
            raise RuntimeError(f"{shader_name}: native record indexes are not unique")
        record_by_index = {row["index"]: row for row in records if row["kind"] == "program"}
        if set(programs) != set(record_by_index):
            raise RuntimeError(f"{shader_name}: native program bytes and record indexes disagree")
        for index, record in record_by_index.items():
            if record["gpu_type"] not in (15, 17) or record["stage"] not in ("progVertex", "progFragment"):
                raise RuntimeError(f"{shader_name}: unexpected native program type/stage")
        if len(tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"]) != shader_spec["pass_count"]:
            raise RuntimeError(f"{shader_name}: source pass count differs from the reviewed recipe")
        prepared[shader_name] = (tree, raw, records, programs)
        program_indices[shader_name] = sorted(record_by_index)
    OUT = preflight_output(work, input_id, RECIPE["shaders"], program_indices)
    OUT.mkdir(parents=True)
    bind_hlsl = shader_source.bind_hlsl
    result = {
        "schema": RECIPE["candidate_schema"],
        "input_id": input_id,
        "source_bundle_sha256": SOURCE["bundle_sha256"],
        "generator_sha256": sha(Path(__file__).resolve()),
        "recipe_sha256": sha(RECIPE_PATH),
        "d3dasm_sha256": D3DASM_SHA256,
        "dxbc_disasm_sha256": DXBC_DISASM_SHA256,
        "candidates": {},
        "unity_compiled": False,
        "android_accepted": False,
        "visual_parity_proven": False,
    }
    for shader_spec in RECIPE["shaders"]:
        shader_name = shader_spec["name"]
        path_id = OBJECTS[shader_name]
        tree, raw, records, programs = prepared[shader_name]
        parsed = tree["m_ParsedForm"]
        subshader = parsed["m_SubShaders"][0]
        record_by_index = {r["index"]: r for r in records if r["kind"] == "program"}
        hlsl_by_index: dict[int, str] = {}
        layouts: dict[int, dict] = {}
        signatures: dict[int, dict] = {}
        for index, record in record_by_index.items():
            stem = f"{shader_name}-{index}"
            dxbc = OUT / f"{stem}.dxbc"
            assembly = OUT / f"{stem}.d3dasm"
            hlsl = OUT / f"{stem}.hlsl"
            rebuilt = OUT / f"{stem}.roundtrip.dxbc"
            dxbc.write_bytes(programs[index])
            layouts[index] = selected_layout(tree, raw, record)
            for fmt, target in (("d3dasm", assembly), ("hlsl", hlsl)):
                run = subprocess.run(
                    [str(D3DASM), str(dxbc), "--emit", fmt, "--output", str(target)],
                    capture_output=True,
                    timeout=90,
                    check=False,
                )
                if run.returncode:
                    raise RuntimeError(f"{stem}: d3dasm {fmt} emission failed")
            reassemble = subprocess.run(
                [str(D3DASM), str(assembly), "--assemble", "--output", str(rebuilt)],
                capture_output=True,
                timeout=90,
                check=False,
            )
            if reassemble.returncode or sha(dxbc) != sha(rebuilt):
                raise RuntimeError(f"{stem}: native roundtrip mismatch")
            disasm = subprocess.run(
                [str(DXBC_DISASM), str(dxbc)],
                capture_output=True,
                timeout=90,
                check=False,
            )
            if disasm.returncode:
                raise RuntimeError(f"{stem}: independent signature disassembly failed")
            signatures[index] = _signature_rows(disasm.stdout.decode("utf-8", errors="strict"))
            if signatures[index] != _assembly_signature_rows(assembly.read_text()):
                raise RuntimeError(f"{stem}: signature readers disagree")
            hlsl_by_index[index] = hlsl.read_text()

        pass_candidates = []
        pass_mapping = []
        for pass_index, native_pass in enumerate(parsed["m_SubShaders"][0]["m_Passes"]):
            selected = selected_pass_records(native_pass, record_by_index)
            candidate, pass_evidence = emit_pass(
                tree,
                pass_index,
                selected,
                hlsl_by_index,
                layouts,
                signatures,
                bind_hlsl,
            )
            pass_candidates.append(candidate)
            pass_mapping.append(pass_evidence)
        if len(pass_candidates) != shader_spec["pass_count"]:
            raise RuntimeError(f"{shader_name}: source pass count differs from recipe")
        props = shader_source.properties(tree)
        tags = dict(subshader.get("m_Tags", {}).get("tags", []))
        tag_text = "Tags { " + " ".join(f"{json.dumps(k)}={json.dumps(v)}" for k, v in sorted(tags.items())) + " }\n" if tags else ""
        shaderlab = (
            f"Shader {json.dumps(parsed['m_Name'])} {{\nProperties {{\n{props}\n}}\nSubShader {{\n{tag_text}LOD {subshader['m_LOD']}\n"
            + "\n".join(pass_candidates)
            + "\n}\n}\n"
        )
        dest = OUT / shader_spec["output"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(shaderlab)
        candidate_manifest = {
            "schema": RECIPE["candidate_schema"],
            "success": True,
            "generator_sha256": sha(Path(__file__).resolve()),
            "recipe_sha256": sha(RECIPE_PATH),
            "source": {
                "input_id": input_id,
                "bundle_sha256": SOURCE["bundle_sha256"],
                "asset_path": shader_spec["source_asset_path"],
                "catalog_key": shader_spec["catalog_key"],
                "catalog_location": shader_spec["catalog_location"],
                "shader_path_id": path_id,
                "shader_name": shader_spec["serialized_name"],
            },
            "generated_shader_path": shader_spec["output"],
            "generated_shader_sha256": sha(dest),
            "semantic_equivalence_proven": False,
            "android_compile_or_render_tested": False,
            "appearance_parity_proven": False,
            "unity_compiled": False,
            "android_accepted": False,
            "visual_parity_proven": False,
            "pass_mapping": pass_mapping,
        }
        manifest_path = OUT / shader_spec["manifest"]
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(candidate_manifest, indent=2, sort_keys=True) + "\n")
        result["candidates"][shader_name] = {
            "path_id": path_id,
            "serialized_name": parsed["m_Name"],
            "catalog_location": shader_spec["catalog_location"],
            "catalog_key": shader_spec["catalog_key"],
            "source_asset_path": shader_spec["source_asset_path"],
            "pass_count": len(pass_candidates),
            "pass_mapping": pass_mapping,
            "shaderlab_sha256": sha(dest),
            "manifest": shader_spec["manifest"],
            "manifest_sha256": sha(manifest_path),
            "source_properties": [p["m_Name"] for p in parsed["m_PropInfo"]["m_Props"]],
        }
    if sha(BUNDLE) != SOURCE["bundle_sha256"]:
        raise RuntimeError("Accepted source bundle changed during candidate generation")
    (OUT / "manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
