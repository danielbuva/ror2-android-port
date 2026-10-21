"""New authored-compiler handoff, separate from the qualified linker replay.

Copies only a pinned SDK/fixture template into a fresh stage and supplies actual
qualified Android compiler outputs. Captured desktop scene roots remain inputs.
"""

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import uuid

PROFILE = "authored-android-compiler-linker-v1"
SOURCE = "scripts/lab/phone_compiled_linker.py"
TEMPLATE_SHA = "dff90a8ab8062a134c09f012aaf321d65fbeac6ff8616f46cfd1da0a5aee9322"
COMPILER_SOURCE = "e9eae1da652221709db7d224397c4757f5d190d3"
COMPILER_PROFILE = "authored-unity-builtin-references-v1"
# Canonical JSON fingerprints omit only source_commit. Identical source/tool
# bytes remain eligible after unrelated Git commits; actual commits and raw
# receipt hashes are always preserved in the handoff.
COMPILER_INPUTS_SHA = "aacffb6221361bfcb3be88c741b4fb81d17fd8d03fb55bb0a45f0cd66d992de7"
REFERENCE_REPORT_SHA = "8b6c4c948f3cb39bc1613ed884a57574de16a1e595535fec97c4f2ce6e7d13ff"
# Acceptance pins for the qualified fixed public source/profile, never compiled
# file inputs or generators. A different source/tool profile needs qualification.
OUTPUTS = {
    "Assembly-CSharp.dll": "d34d7a7341d8cbf8a1a0f29f452bafe1839d400cfd5c8351e9a9378fe68693dd",
    "Assembly-CSharp.ref.dll": "d912f592d09ad4e47f64c85310dd2d3db90db31586f93ea298d3e62a64220e66",
    "Assembly-CSharp.pdb": "a62e6c053cc38b692d6a3ed153b4ae2673c4f9992df7763fd51c6e92aff6d130",
}
GUARD_SHA = "ab8693a0a8854c315cd745c6552b77714ecbbd5b31705b06e902560111784efb"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or not re.fullmatch("[0-9a-f]{40}", value.get("source_commit", "")):
        raise ValueError("Expected a recorded compiler source commit")
    body = {key: item for key, item in value.items() if key != "source_commit"}
    return value, hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bounded(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != name:
        raise ValueError("Expected a canonical relative handoff path")
    result = Path(root) / name
    if result != result.resolve() or not result.is_file():
        raise ValueError("Handoff input links or missing files")
    return result


def guard():
    path = Path(__file__).with_name("phone_managed_compile.py")
    if path.is_symlink() or sha(path) != GUARD_SHA:
        raise ValueError("Compiler handoff guard drift")
    spec = importlib.util.spec_from_file_location("_compiled_linker_guard", path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def checked_manifest(root, name, *, digest=None):
    root = Path(root).absolute()
    if root != root.resolve():
        raise ValueError("Handoff root links are unsupported")
    file = bounded(root, name)
    if digest is not None and sha(file) != digest:
        raise ValueError("Unknown handoff template manifest")
    manifest = json.loads(file.read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Empty handoff input manifest")
    for path, expected in manifest.items():
        if sha(bounded(root, path)) != expected:
            raise ValueError("Handoff input drift")
    return manifest


def compiler_input(stage_root, output):
    stage_root, output = Path(stage_root).absolute(), Path(output).absolute()
    input_file = bounded(stage_root, "inputs.json")
    receipt, input_identity = identity(input_file)
    if input_identity != COMPILER_INPUTS_SHA:
        raise ValueError("Unqualified compiler supplier manifest")
    if receipt.get("schema") != 1 or receipt.get("profile") != COMPILER_PROFILE or receipt.get("game_inputs") is not False:
        raise ValueError("Unqualified compiler input profile")
    for name, digest in receipt["inputs"].items():
        if sha(bounded(stage_root, name)) != digest:
            raise ValueError("Compiler supplier input drift")
    result_path = bounded(output, "result.json")
    result = json.loads(result_path.read_text())
    if (
        result.get("schema") != 1
        or result.get("success") is not True
        or result.get("exit_code") != 0
        or result.get("source_commit") != receipt["source_commit"]
        or result.get("host") != "android"
        or result.get("runtime") != "8.0.32"
        or result.get("inputs_sha256") != sha(stage_root / "inputs.json")
        or result.get("outputs") != OUTPUTS
        or result.get("reference_count") != 157
        or result.get("reference_report_sha256") != sha(bounded(output, "references.json"))
    ):
        raise ValueError("Unqualified Android compiler result")
    if any(result.get(key) is not False for key in ("game_inputs", "player_built", "unity_player_compilation_qualified", "managed_game_compilation_qualified")):
        raise ValueError("Compiler result scope differs")
    for name, digest in OUTPUTS.items():
        if sha(bounded(output, name)) != digest:
            raise ValueError("Compiler output drift")
    report, reference_identity = identity(bounded(output, "references.json"))
    if reference_identity != REFERENCE_REPORT_SHA or report["source_commit"] != receipt["source_commit"]:
        raise ValueError("Compiler reference report drift")
    return receipt, result


def stage(root, template, compiler_stage, compiler_output, work):
    root, template, compiler_stage, compiler_output, work = (Path(p).absolute() for p in (root, template, compiler_stage, compiler_output, work))
    if subprocess.check_output(["git", "status", "--porcelain", "--", SOURCE, "scripts/lab/phone_managed_compile.py"], cwd=root):
        raise ValueError("Commit handoff sources before staging")
    if sha(root / SOURCE) != sha(__file__):
        raise ValueError("Handoff implementation differs from checkout")
    original = checked_manifest(template, "input-manifest.json", digest=TEMPLATE_SHA)
    plan = json.loads(bounded(template, "plan.json").read_text())
    if plan.get("game_inputs") is not False or plan.get("desktop_editor_roots") is not True or "native_registry" not in plan:
        raise ValueError("Expected the qualified authored SDK-root template")
    receipt, result = compiler_input(compiler_stage, compiler_output)
    provenance = dict(
        schema=1,
        profile=PROFILE,
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        template_manifest_sha256=TEMPLATE_SHA,
        compiler_source_commit=receipt["source_commit"],
        compiler_inputs_sha256=sha(compiler_stage / "inputs.json"),
        compiler_result_sha256=sha(compiler_output / "result.json"),
        compiler_outputs=result["outputs"],
        compiler_reference_report_sha256=result["reference_report_sha256"],
        game_inputs=False,
        desktop_editor_roots=True,
        desktop_compiled_fixture_input=False,
        managed_game_compilation_qualified=False,
    )
    destination = work / "rebuild/phone-managed-compile" / ("linker-" + uuid.uuid4().hex)
    writer = guard()
    with writer.directory(destination, work, new=True):
        pass
    replacements = {
        "inputs/Assembly-CSharp.dll": compiler_output / "Assembly-CSharp.dll",
        "inputs/Assembly-CSharp.pdb": compiler_output / "Assembly-CSharp.pdb",
    }
    for name in original:
        writer.write_input(destination / name, (replacements.get(name) or bounded(template, name)).read_bytes(), work)
    extras = {
        "compiler-provenance.json": (json.dumps(provenance, indent=2) + "\n").encode(),
        "template-manifest.json": (template / "input-manifest.json").read_bytes(),
        "compiler-inputs.json": (compiler_stage / "inputs.json").read_bytes(),
        "compiler-result.json": (compiler_output / "result.json").read_bytes(),
        "compiler-references.json": (compiler_output / "references.json").read_bytes(),
        "compiler-reference.dll": (compiler_output / "Assembly-CSharp.ref.dll").read_bytes(),
        "phone_compiled_linker.py": Path(__file__).read_bytes(),
    }
    for name, data in extras.items():
        writer.write_input(destination / name, data, work)
    manifest = {name: sha(destination / name) for name in [*original, *extras]}
    writer.write_input(destination / "input-manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), work)
    validate(destination)
    checked_manifest(template, "input-manifest.json", digest=TEMPLATE_SHA)
    compiler_input(compiler_stage, compiler_output)
    if receipt["inputs"] != json.loads((compiler_stage / "inputs.json").read_text())["inputs"]:
        raise ValueError("Compiler supplier manifest changed during staging")
    return destination, provenance


def validate(stage_root):
    stage_root = Path(stage_root).absolute()
    manifest = checked_manifest(stage_root, "input-manifest.json")
    original_file = bounded(stage_root, "template-manifest.json")
    if sha(original_file) != TEMPLATE_SHA:
        raise ValueError("Historical template manifest differs")
    original = json.loads(original_file.read_text())
    replacements = {"inputs/Assembly-CSharp.dll": OUTPUTS["Assembly-CSharp.dll"], "inputs/Assembly-CSharp.pdb": OUTPUTS["Assembly-CSharp.pdb"]}
    extras = {
        "compiler-provenance.json",
        "template-manifest.json",
        "compiler-inputs.json",
        "compiler-result.json",
        "compiler-references.json",
        "compiler-reference.dll",
        "phone_compiled_linker.py",
    }
    if set(manifest) != set(original) | extras or not set(replacements) <= set(original):
        raise ValueError("Compiled handoff membership differs")
    if any(manifest[name] != replacements.get(name, digest) for name, digest in original.items()):
        raise ValueError("Compiled handoff changed a retained template input")
    compiler, input_identity = identity(stage_root / "compiler-inputs.json")
    references, reference_identity = identity(stage_root / "compiler-references.json")
    if (
        input_identity != COMPILER_INPUTS_SHA
        or reference_identity != REFERENCE_REPORT_SHA
        or compiler["source_commit"] != references["source_commit"]
        or sha(stage_root / "compiler-reference.dll") != OUTPUTS["Assembly-CSharp.ref.dll"]
        or sha(stage_root / "phone_compiled_linker.py") != sha(__file__)
    ):
        raise ValueError("Compiled handoff producer evidence drift")
    provenance = json.loads((stage_root / "compiler-provenance.json").read_text())
    result = json.loads((stage_root / "compiler-result.json").read_text())
    if (
        provenance.get("schema") != 1
        or provenance.get("profile") != PROFILE
        or provenance.get("template_manifest_sha256") != TEMPLATE_SHA
        or provenance.get("compiler_source_commit") != compiler["source_commit"]
        or provenance.get("compiler_inputs_sha256") != sha(stage_root / "compiler-inputs.json")
        or provenance.get("compiler_result_sha256") != sha(stage_root / "compiler-result.json")
        or provenance.get("compiler_outputs") != OUTPUTS
        or provenance.get("compiler_reference_report_sha256") != sha(stage_root / "compiler-references.json")
    ):
        raise ValueError("Compiled handoff provenance differs")
    if (
        result.get("source_commit") != compiler["source_commit"]
        or result.get("success") is not True
        or result.get("exit_code") != 0
        or result.get("host") != "android"
        or result.get("runtime") != "8.0.32"
        or result.get("inputs_sha256") != sha(stage_root / "compiler-inputs.json")
        or result.get("outputs") != OUTPUTS
        or result.get("reference_report_sha256") != sha(stage_root / "compiler-references.json")
        or result.get("reference_count") != 157
    ):
        raise ValueError("Compiled handoff compiler receipt differs")
    if any(
        provenance.get(key) is not value
        for key, value in {
            "game_inputs": False,
            "desktop_editor_roots": True,
            "desktop_compiled_fixture_input": False,
            "managed_game_compilation_qualified": False,
        }.items()
    ):
        raise ValueError("Compiled handoff scope differs")
    if any(result.get(key) is not False for key in ("game_inputs", "player_built", "unity_player_compilation_qualified", "managed_game_compilation_qualified")):
        raise ValueError("Compiled handoff compiler scope differs")
    actual = {p.relative_to(stage_root).as_posix() for p in stage_root.rglob("*") if p.is_file()}
    if any(p.is_symlink() for p in stage_root.rglob("*")) or actual != set(manifest) | {"input-manifest.json"}:
        raise ValueError("Foreign compiled handoff files or links")
    return manifest, provenance


def strip(stage_root, tool_root, output):
    stage_root, tool_root, output = (Path(p).absolute() for p in (stage_root, tool_root, output))
    manifest, provenance = validate(stage_root)
    if output != output.resolve() or output.exists() or output.parent != stage_root.parent or not output.name.startswith(stage_root.name + "-output-"):
        raise ValueError("Select a fresh owned sibling output for the compiled handoff")
    started = time.monotonic()
    command = [sys.executable, "-I", "-S", "-B", str(stage_root / "phone_linker.py"), str(stage_root), str(tool_root), str(output)]
    child = subprocess.run(command, capture_output=True, text=True, timeout=660)
    if not output.exists():
        output.mkdir(exist_ok=False)
    with (output / "driver.log").open("x") as log:
        log.write(child.stdout + child.stderr)
    result = dict(
        schema=1,
        profile=PROFILE,
        success=False,
        source_commit=provenance["source_commit"],
        compiler_source_commit=provenance["compiler_source_commit"],
        compiler_result_sha256=provenance["compiler_result_sha256"],
        input_manifest_sha256=sha(stage_root / "input-manifest.json"),
        game_inputs=False,
        desktop_editor_roots=True,
        desktop_compiled_fixture_input=False,
        managed_game_compilation_qualified=False,
        player_built=False,
        exit_code=child.returncode,
        elapsed_seconds=time.monotonic() - started,
    )
    try:
        after, _ = validate(stage_root)
        if after != manifest or child.returncode:
            raise ValueError("Compiled handoff child or input preservation failed")
        original = json.loads((output / "result.json").read_text())
        if original.get("success") is not True or original.get("exit_code") != 0 or original.get("input_manifest_sha256") != result["input_manifest_sha256"]:
            raise ValueError("Compiled handoff linker result differs")
        outputs = {p.relative_to(output / "stripped").as_posix(): sha(p) for p in (output / "stripped").rglob("*") if p.is_file()}
        if original.get("outputs") != outputs or "Assembly-CSharp.dll" not in outputs:
            raise ValueError("Compiled handoff stripped output drift")
        result.update(success=True, linker_result_sha256=sha(output / "result.json"), outputs=outputs)
    except (OSError, ValueError) as error:
        result["failure"] = str(error)
    with (output / "handoff-result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "stage":
        destination, receipt = stage(*sys.argv[2:])
        print(json.dumps(dict(stage=str(destination), **receipt)))
    elif len(sys.argv) == 5 and sys.argv[1] == "run":
        result = strip(*sys.argv[2:])
        print(json.dumps({key: value for key, value in result.items() if key != "outputs"}))
        raise SystemExit(0 if result["success"] else 1)
    else:
        raise SystemExit(
            "Usage: phone_compiled_linker.py stage ROOT TEMPLATE COMPILER_STAGE COMPILER_OUTPUT WORK | run STAGE OWNED_TOOL_ROOT NEW_SIBLING_OUTPUT (authored fixture only; desktop scene roots retained)"
        )
