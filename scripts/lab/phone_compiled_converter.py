"""Separate authored Android compiler/stripper to IL2CPP converter handoff.

The qualified replay consumers are unchanged. All supplied SDK/generated files
remain private. Captured desktop scene roots are still required inputs.
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


PROFILE = "authored-android-compiler-converter-v1"
SOURCE = "scripts/lab/phone_compiled_converter.py"
TEMPLATE_SHA = "91ee2763aa34866fb4c710ca9cf89bff412184f5c53dd3ab770ea0c375fc79dc"
SUPPLIER_SHA = "c3b5c8f584f5e7059ea5db46c433ae65d0dd533ede1acf8da76e6c518753ce94"
CONVERTER_SHA = "7260877e118448f47a9c277343484e7f20a9901bb650b6b0a04824e31d0447d7"
GUARD_SHA = "ab8693a0a8854c315cd745c6552b77714ecbbd5b31705b06e902560111784efb"
# Fixed authored profile acceptance pin, never a generator or file supplier.
STRIPPED_SHA = "dcff93f933539800a967ee0b581abef8805ed69a9a14cb3b250e203dbb69c153"
STRIPPED = "project/Library/Bee/artifacts/Android/ManagedStripped/"
SCOPE = dict(game_inputs=False, desktop_editor_roots=True, desktop_compiled_fixture_input=False, managed_game_compilation_qualified=False, player_built=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bounded(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != name:
        raise ValueError("Expected a canonical relative compiled-converter path")
    root = Path(root).absolute()
    result = root / name
    if root != root.resolve() or result != result.resolve() or not result.is_file():
        raise ValueError("Compiled-converter links or missing files")
    return result


def load(path, digest, name):
    path = Path(path)
    if path.is_symlink() or sha(path) != digest:
        raise ValueError("Compiled-converter helper drift")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def checked(root, digest=None):
    file = bounded(root, "input-manifest.json")
    if digest is not None and sha(file) != digest:
        raise ValueError("Unqualified compiled-converter template")
    manifest = json.loads(file.read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Empty compiled-converter manifest")
    for name, expected in manifest.items():
        if sha(bounded(root, name)) != expected:
            raise ValueError("Compiled-converter input drift: " + name)
    return manifest


def supplier_result(stage_root, output, provenance, stripped):
    """Bind actual stripping results, including their complete upstream inputs."""
    handoff_path = bounded(output, "handoff-result.json")
    result_path = bounded(output, "result.json")
    handoff, result = (json.loads(path.read_text()) for path in (handoff_path, result_path))
    manifest_sha = sha(bounded(stage_root, "input-manifest.json"))
    actual = {path.relative_to(stripped).as_posix(): sha(path) for path in Path(stripped).rglob("*") if path.is_file()}
    if fingerprint(actual) != STRIPPED_SHA or any(path.is_symlink() for path in Path(stripped).rglob("*")):
        raise ValueError("Unqualified compiled stripping closure")
    if (
        handoff.get("schema") != 1
        or handoff.get("profile") != "authored-android-compiler-linker-v1"
        or handoff.get("source_commit") != provenance["source_commit"]
        or handoff.get("compiler_source_commit") != provenance["compiler_source_commit"]
        or handoff.get("compiler_result_sha256") != provenance["compiler_result_sha256"]
        or handoff.get("linker_result_sha256") != sha(result_path)
        or any(handoff.get(key) is not value for key, value in SCOPE.items())
        or any(
            value.get("success") is not True
            or value.get("exit_code") != 0
            or value.get("input_manifest_sha256") != manifest_sha
            or value.get("outputs") != actual
            for value in (handoff, result)
        )
    ):
        raise ValueError("Compiled stripping supplier result/provenance differs")
    return actual, handoff


def validate(stage_root):
    stage_root = Path(stage_root).absolute()
    manifest = checked(stage_root)
    supplier = load(bounded(stage_root, "supplier/phone_compiled_linker.py"), SUPPLIER_SHA, "_compiled_converter_supplier")
    supplier_manifest, upstream = supplier.validate(stage_root / "supplier")
    outputs, handoff = supplier_result(stage_root / "supplier", stage_root / "supplier-output", upstream, stage_root / "converter" / STRIPPED)
    original_file = bounded(stage_root, "converter-template-manifest.json")
    if sha(original_file) != TEMPLATE_SHA:
        raise ValueError("Historical converter template differs")
    original = json.loads(original_file.read_text())
    converter = stage_root / "converter"
    inner = checked(converter)
    replacement = {STRIPPED + name: digest for name, digest in outputs.items()}
    if set(inner) != set(original) or set(replacement) != {name for name in original if name.startswith(STRIPPED)}:
        raise ValueError("Compiled converter input membership differs")
    if any(inner[name] != replacement.get(name, digest) for name, digest in original.items()):
        raise ValueError("Compiled converter changed a retained SDK/plan input")
    if sha(bounded(converter, "phone_converter.py")) != CONVERTER_SHA:
        raise ValueError("Qualified converter driver changed")
    extras = {
        "converter-template-manifest.json",
        "compiled-provenance.json",
        "phone_compiled_converter.py",
        "phone_managed_compile.py",
        "supplier-output/result.json",
        "supplier-output/handoff-result.json",
    }
    expected = (
        extras
        | {"supplier/" + name for name in [*supplier_manifest, "input-manifest.json"]}
        | {"converter/" + name for name in [*inner, "input-manifest.json"]}
    )
    actual = {path.relative_to(stage_root).as_posix() for path in stage_root.rglob("*") if path.is_file()}
    if set(manifest) != expected or actual != expected | {"input-manifest.json"} or any(path.is_symlink() for path in stage_root.rglob("*")):
        raise ValueError("Foreign compiled-converter files or links")
    provenance = json.loads(bounded(stage_root, "compiled-provenance.json").read_text())
    if (
        provenance.get("schema") != 1
        or provenance.get("profile") != PROFILE
        or not re.fullmatch("[0-9a-f]{40}", provenance.get("source_commit", ""))
        or provenance.get("supplier_source_commit") != upstream["source_commit"]
        or provenance.get("compiler_source_commit") != upstream["compiler_source_commit"]
        or provenance.get("supplier_handoff_sha256") != sha(stage_root / "supplier-output/handoff-result.json")
        or provenance.get("supplier_manifest_sha256") != sha(stage_root / "supplier/input-manifest.json")
        or provenance.get("stripped_outputs") != outputs
        or any(provenance.get(key) is not value for key, value in SCOPE.items())
        or sha(bounded(stage_root, "phone_compiled_converter.py")) != sha(__file__)
        or sha(bounded(stage_root, "phone_managed_compile.py")) != GUARD_SHA
    ):
        raise ValueError("Compiled converter provenance differs")
    return manifest, provenance


def stage(root, template, supplier_stage, supplier_output, work):
    root, template, supplier_stage, supplier_output, work = (Path(path).absolute() for path in (root, template, supplier_stage, supplier_output, work))
    sources = [SOURCE, "scripts/lab/phone_converter.py", "scripts/lab/phone_compiled_linker.py", "scripts/lab/phone_managed_compile.py"]
    if subprocess.check_output(["git", "status", "--porcelain", "--", *sources], cwd=root) or sha(root / SOURCE) != sha(__file__):
        raise ValueError("Commit compiled-converter sources before staging")
    writer = load(root / sources[3], GUARD_SHA, "_compiled_converter_writer")
    supplier = load(root / sources[2], SUPPLIER_SHA, "_compiled_converter_stage_supplier")
    original = checked(template, TEMPLATE_SHA)
    upstream_manifest, upstream = supplier.validate(supplier_stage)
    outputs, handoff = supplier_result(supplier_stage, supplier_output, upstream, supplier_output / "stripped")
    destination = work / "rebuild/phone-managed-compile" / ("converter-" + uuid.uuid4().hex)
    provenance = dict(
        schema=1,
        profile=PROFILE,
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        supplier_source_commit=upstream["source_commit"],
        compiler_source_commit=upstream["compiler_source_commit"],
        supplier_handoff_sha256=sha(supplier_output / "handoff-result.json"),
        supplier_manifest_sha256=sha(supplier_stage / "input-manifest.json"),
        stripped_outputs=outputs,
        **SCOPE,
    )
    with writer.directory(destination, work, new=True):
        for name in [*upstream_manifest, "input-manifest.json"]:
            writer.write_input(destination / "supplier" / name, bounded(supplier_stage, name).read_bytes(), work)
        inner = {}
        for name in original:
            source = bounded(supplier_output / "stripped", name.removeprefix(STRIPPED)) if name.startswith(STRIPPED) else bounded(template, name)
            writer.write_input(destination / "converter" / name, source.read_bytes(), work)
            inner[name] = sha(source)
        for name in ("result.json", "handoff-result.json"):
            writer.write_input(destination / "supplier-output" / name, bounded(supplier_output, name).read_bytes(), work)
        for name in ("phone_compiled_converter.py", "phone_managed_compile.py"):
            writer.write_input(destination / name, (root / "scripts/lab" / name).read_bytes(), work)
        writer.write_input(destination / "converter-template-manifest.json", (template / "input-manifest.json").read_bytes(), work)
        for path, value in ((destination / "converter/input-manifest.json", inner), (destination / "compiled-provenance.json", provenance)):
            writer.write_input(path, (json.dumps(value, indent=2) + "\n").encode(), work)
        manifest = {path.relative_to(destination).as_posix(): sha(path) for path in sorted(destination.rglob("*")) if path.is_file()}
        writer.write_input(destination / "input-manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), work)
    validate(destination)
    if supplier.validate(supplier_stage)[0] != upstream_manifest or checked(template, TEMPLATE_SHA) != original:
        raise ValueError("Compiled-converter suppliers changed during staging")
    return destination, provenance


def convert(stage_root, tool_root, output):
    stage_root, tool_root, output = (Path(path).absolute() for path in (stage_root, tool_root, output))
    manifest, provenance = validate(stage_root)
    if output != output.resolve() or output.exists() or output.parent != stage_root.parent or not output.name.startswith(stage_root.name + "-output-"):
        raise ValueError("Select a fresh owned sibling output for the compiled converter")
    started = time.monotonic()
    child = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(stage_root / "converter/phone_converter.py"), str(stage_root / "converter"), str(tool_root), str(output)],
        capture_output=True,
        text=True,
        timeout=660,
    )
    output.mkdir(exist_ok=True)
    with (output / "driver.log").open("x") as stream:
        stream.write(child.stdout + child.stderr)
    result = dict(
        schema=1,
        profile=PROFILE,
        success=False,
        source_commit=provenance["source_commit"],
        supplier_source_commit=provenance["supplier_source_commit"],
        compiler_source_commit=provenance["compiler_source_commit"],
        input_manifest_sha256=sha(stage_root / "input-manifest.json"),
        exit_code=child.returncode,
        elapsed_seconds=time.monotonic() - started,
        **SCOPE,
    )
    try:
        if validate(stage_root)[0] != manifest or child.returncode:
            raise ValueError("Compiled converter execution or input preservation failed")
        original = json.loads((output / "result.json").read_text())
        outputs = {path.relative_to(output).as_posix(): sha(path) for folder in ("cpp", "data") for path in (output / folder).rglob("*") if path.is_file()}
        if (
            original.get("success") is not True
            or original.get("exit_code") != 0
            or original.get("input_manifest_sha256") != sha(stage_root / "converter/input-manifest.json")
            or not outputs
            or outputs != original.get("outputs")
        ):
            raise ValueError("Compiled converter result/output drift")
        result.update(success=True, converter_result_sha256=sha(output / "result.json"), outputs=outputs)
    except (OSError, ValueError) as error:
        result["failure"] = str(error)
    with (output / "handoff-result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "stage":
        destination, receipt = stage(*sys.argv[2:])
        print(json.dumps(dict(stage=str(destination), **receipt)))
    elif len(sys.argv) == 5 and sys.argv[1] == "run":
        result = convert(*sys.argv[2:])
        print(json.dumps({key: value for key, value in result.items() if key != "outputs"}))
        raise SystemExit(0 if result["success"] else 1)
    else:
        raise SystemExit(
            "Usage: phone_compiled_converter.py stage ROOT CONVERTER_TEMPLATE LINKER_STAGE LINKER_OUTPUT WORK | run STAGE OWNED_TOOL_ROOT NEW_SIBLING_OUTPUT (authored fixture; captured desktop roots retained)"
        )
