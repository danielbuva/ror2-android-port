"""Separate authored compiled-input consumer for native IL2CPP construction.

Supplied SDK/player files stay private. This fixed fixture still depends on
captured desktop scene/editor roots; it is not a general phone game builder.
"""

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import time
import uuid
import zipfile


PROFILE = "authored-android-compiled-native-v1"
SOURCE = "scripts/lab/phone_compiled_native.py"
CONVERTER_SHA = "13116d60baae05732b711e019963c48613e07f3a7516dfc13223d172bcf551c4"
NATIVE_SHA = "b924cb84bc923f8422aff0afcb3ee8289e7f4a86b96e87a6bc12d56849f7fefa"
GUARD_SHA = "ab8693a0a8854c315cd745c6552b77714ecbbd5b31705b06e902560111784efb"
TEMPLATE_SHA = "fc304d7799bb2c703f82c5676856d231ea8c8c0dd8ac9d0065831c940008149f"
APK_SHA = "90e8f9f8fa5028716cf9f1c8de8afb6d297f048c8c0bb486a987a594e3ab5a61"
FIXTURE_SHA = "957217bd379a3e0a747ce0b5d7aef9420fff449432b07775d8a320f908a0a22f"
SDK_SHA = "906123118e45d56c6bcf20f3776ed2373417553042500714023daeb9e53058e8"
CPP = "project/Library/Bee/artifacts/Android/il2cppOutput/cpp/"
FIXTURE_SOURCES = ("ContentFixture.cs", "NativeScriptSchemaFixture.cs", "ContentFixtureBuilder.cs", "ContentFixtureLinkerCapture.cs")
FIXTURE_FILES = {"tools/phone-build/" + name: "sources/" + name for name in FIXTURE_SOURCES} | {
    "scripts/lab/phone_content.py": "generators/phone_content.py",
    "scripts/lab/phone_bundle.py": "generators/phone_bundle.py",
}
DATA = {
    "data/Metadata/global-metadata.dat": "assets/bin/Data/Managed/Metadata/global-metadata.dat",
    "data/Resources/mscorlib.dll-resources.dat": "assets/bin/Data/Managed/Resources/mscorlib.dll-resources.dat",
}
SCOPE = dict(game_inputs=False, desktop_editor_roots=True, desktop_compiled_fixture_input=False, managed_game_compilation_qualified=False, player_built=False)
CHILD_TIMEOUT_SECONDS = 1800
CHILD_OUTPUT_LIMIT_BYTES = 64 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounded(root, name):
    path = PurePosixPath(name)
    root = Path(root).absolute()
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != name:
        raise ValueError("Expected a canonical compiled-native relative path")
    result = root / name
    if root != root.resolve() or result != result.resolve() or not result.is_file():
        raise ValueError("Compiled-native links or missing files")
    return result


def load(path, digest, name):
    path = Path(path)
    if path.is_symlink() or sha(path) != digest:
        raise ValueError("Compiled-native helper drift")
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
        raise ValueError("Unqualified native SDK template")
    manifest = json.loads(file.read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Empty compiled-native manifest")
    for name, expected in manifest.items():
        if sha(bounded(root, name)) != expected:
            raise ValueError("Compiled-native input drift: " + name)
    return manifest


def converter_result(stage_root, output, provenance):
    raw = json.loads(bounded(output, "result.json").read_text())
    result = json.loads(bounded(output, "handoff-result.json").read_text())
    files = {
        path.relative_to(output).as_posix(): sha(bounded(output, path.relative_to(output).as_posix()))
        for folder in ("cpp", "data")
        for path in (Path(output) / folder).rglob("*")
        if path.is_file()
    }
    if (
        result.get("schema") != 1
        or result.get("profile") != "authored-android-compiler-converter-v1"
        or result.get("source_commit") != provenance["source_commit"]
        or result.get("supplier_source_commit") != provenance["supplier_source_commit"]
        or result.get("compiler_source_commit") != provenance["compiler_source_commit"]
        or result.get("input_manifest_sha256") != sha(stage_root / "input-manifest.json")
        or result.get("converter_result_sha256") != sha(output / "result.json")
        or raw.get("input_manifest_sha256") != sha(stage_root / "converter/input-manifest.json")
        or any(result.get(key) is not value for key, value in SCOPE.items())
        or any(value.get("success") is not True or value.get("exit_code") != 0 or value.get("outputs") != files for value in (raw, result))
        or {name for name in files if name.startswith("data/")} != set(DATA)
        or not any(name.endswith(".cpp") for name in files)
    ):
        raise ValueError("Compiled converter result/output provenance differs")
    return files, result


def fixture(root, outputs):
    apk = bounded(root, "base.apk")
    receipt_path = bounded(root, "fixture-inputs.json")
    if sha(apk) != APK_SHA or sha(receipt_path) != FIXTURE_SHA:
        raise ValueError("Unqualified compiled-native fixture")
    receipt = json.loads(receipt_path.read_text())
    request = json.loads(bounded(root, "request.json").read_text())
    if set(request) != {"project", "apk", "sha256"} or request["sha256"] != APK_SHA:
        raise ValueError("Authored fixture request differs")
    sources = {name: sha(bounded(root, target)) for name, target in FIXTURE_FILES.items()}
    if receipt.get("game_inputs") is not False or receipt.get("unity") != "2021.3.45f2" or receipt.get("sources") != sources:
        raise ValueError("Authored native fixture source/scope differs")
    with zipfile.ZipFile(apk) as archive:
        if hashlib.sha256(archive.read("assets/phone-fixture.bundle")).hexdigest() != receipt["bundle_sha256"]:
            raise ValueError("Authored fixture bundle differs")
        if any(hashlib.sha256(archive.read(member)).hexdigest() != outputs[name] for name, member in DATA.items()):
            raise ValueError("Converted data/metadata differs from the exact player APK")


def sdk_members(manifest):
    return {name: digest for name, digest in manifest.items() if name.startswith(("unity/", "android/", "ndk/"))}


def native_plan(base, handoff_sha):
    return dict(
        base,
        desktop_stripping_and_codegen_inputs=False,
        desktop_stripping_inputs=False,
        codegen_origin="phone-compiled-converter",
        compiled_converter_profile="authored-android-compiler-converter-v1",
        converter_handoff_sha256=handoff_sha,
        **SCOPE,
    )


def validate(stage_root):
    stage_root = Path(stage_root).absolute()
    manifest = checked(stage_root)
    producer = load(bounded(stage_root, "converter/phone_compiled_converter.py"), CONVERTER_SHA, "_compiled_native_converter")
    upstream_manifest, upstream = producer.validate(stage_root / "converter")
    outputs, result = converter_result(stage_root / "converter", stage_root / "converter-output", upstream)
    fixture(stage_root / "fixture", outputs)
    qualified_file = bounded(stage_root, "native-template-manifest.json")
    if sha(qualified_file) != TEMPLATE_SHA:
        raise ValueError("Qualified native SDK template changed")
    qualified = json.loads(qualified_file.read_text())
    base_manifest = json.loads(bounded(stage_root, "native-base-manifest.json").read_text())
    base_plan = json.loads(bounded(stage_root, "native-base-plan.json").read_text())
    if base_manifest.get("plan.json") != sha(stage_root / "native-base-plan.json"):
        raise ValueError("Native captured plan identity differs")
    current_native = checked(stage_root / "native")
    if not sdk_members(qualified) or sdk_members(qualified) != sdk_members(base_manifest):
        raise ValueError("Native SDK/target input set differs from qualification")
    expected_native = dict(base_manifest, **{"plan.json": sha(stage_root / "native/plan.json")})
    if current_native != expected_native or sha(bounded(stage_root, "native/phone_native.py")) != NATIVE_SHA:
        raise ValueError("Native capture changed an input or driver")
    cpp = {name.removeprefix(CPP): digest for name, digest in current_native.items() if name.startswith(CPP)}
    if {"cpp/" + name: digest for name, digest in cpp.items()} != {name: digest for name, digest in outputs.items() if name.startswith("cpp/")}:
        raise ValueError("Native capture substituted generated C++")
    converter_plan = json.loads(bounded(stage_root, "converter/converter/plan.json").read_text())
    if base_plan["graph_sha256"] != converter_plan["graph_sha256"]:
        raise ValueError("Native graph belongs to another fixture generation")
    plan = json.loads(bounded(stage_root, "native/plan.json").read_text())
    handoff_sha = sha(stage_root / "converter-output/handoff-result.json")
    if plan != native_plan(base_plan, handoff_sha):
        raise ValueError("Native compilation/link options changed")
    extras = {
        "phone_compiled_native.py",
        "phone_managed_compile.py",
        "provenance.json",
        "native-template-manifest.json",
        "native-base-manifest.json",
        "native-base-plan.json",
        "fixture/base.apk",
        "fixture/fixture-inputs.json",
        "fixture/request.json",
    } | {"fixture/" + name for name in FIXTURE_FILES.values()}
    expected = (
        extras
        | {"converter/" + name for name in [*upstream_manifest, "input-manifest.json"]}
        | {"converter-output/" + name for name in [*outputs, "result.json", "handoff-result.json"]}
        | {"native/" + name for name in [*current_native, "input-manifest.json"]}
    )
    actual = {path.relative_to(stage_root).as_posix() for path in stage_root.rglob("*") if path.is_file()}
    if set(manifest) != expected or actual != expected | {"input-manifest.json"} or any(path.is_symlink() for path in stage_root.rglob("*")):
        raise ValueError("Foreign compiled-native files or links")
    provenance = json.loads((stage_root / "provenance.json").read_text())
    if (
        provenance.get("schema") != 1
        or provenance.get("profile") != PROFILE
        or not re.fullmatch("[0-9a-f]{40}", provenance.get("source_commit", ""))
        or provenance.get("converter_source_commit") != upstream["source_commit"]
        or provenance.get("compiler_source_commit") != upstream["compiler_source_commit"]
        or provenance.get("converter_manifest_sha256") != sha(stage_root / "converter/input-manifest.json")
        or provenance.get("converter_handoff_sha256") != handoff_sha
        or provenance.get("fixture_apk_sha256") != APK_SHA
        or provenance.get("native_base_manifest_sha256") != sha(stage_root / "native-base-manifest.json")
        or any(provenance.get(key) is not value for key, value in SCOPE.items())
        or sha(bounded(stage_root, "phone_compiled_native.py")) != sha(__file__)
        or sha(bounded(stage_root, "phone_managed_compile.py")) != GUARD_SHA
    ):
        raise ValueError("Compiled-native provenance differs")
    return manifest, provenance


def stage(root, template, request, converter_stage, converter_output, editor, android, work):
    root, template, request, converter_stage, converter_output, editor, android, work = (
        Path(path).absolute() for path in (root, template, request, converter_stage, converter_output, editor, android, work)
    )
    sources = [SOURCE, "scripts/lab/phone_native.py", "scripts/lab/phone_compiled_converter.py", "scripts/lab/phone_managed_compile.py", *FIXTURE_FILES]
    if subprocess.check_output(["git", "status", "--porcelain", "--", *sources], cwd=root) or sha(root / SOURCE) != sha(__file__):
        raise ValueError("Commit compiled-native sources before staging")
    if sha(editor / "MacOS/Unity") != SDK_SHA:
        raise ValueError("Expected the pinned owner SDK")
    writer = load(root / sources[3], GUARD_SHA, "_compiled_native_writer")
    builder = load(root / sources[1], NATIVE_SHA, "_compiled_native_builder")
    producer = load(root / sources[2], CONVERTER_SHA, "_compiled_native_stage_converter")
    original = checked(template, TEMPLATE_SHA)
    # The legacy guard uses module context. Scope it to these explicit roots
    # for this one synchronous staging call, then restore the caller's context.
    import common

    prior_root, prior_work = common.ROOT, common.WORK
    try:
        common.ROOT, common.WORK = root, work
        value, project = builder.fixture_request(request)
    finally:
        common.ROOT, common.WORK = prior_root, prior_work
    if sha(Path(value["apk"])) != APK_SHA or sha(project / "fixture-inputs.json") != FIXTURE_SHA:
        raise ValueError("Unqualified compiled-native fixture")
    receipt = json.loads((project / "fixture-inputs.json").read_text())
    if receipt["sources"] != {name: sha(root / name) for name in FIXTURE_FILES}:
        raise ValueError("Authored fixture generator/source drift")
    upstream_manifest, upstream = producer.validate(converter_stage)
    outputs, result = converter_result(converter_stage, converter_output, upstream)
    destination = work / "rebuild/phone-managed-compile" / ("native-" + uuid.uuid4().hex)
    with writer.directory(destination, work, new=True):
        for name in [*upstream_manifest, "input-manifest.json"]:
            writer.write_input(destination / "converter" / name, bounded(converter_stage, name).read_bytes(), work)
        for name in [*outputs, "result.json", "handoff-result.json"]:
            writer.write_input(destination / "converter-output" / name, bounded(converter_output, name).read_bytes(), work)
        for name in ("phone_compiled_native.py", "phone_managed_compile.py"):
            writer.write_input(destination / name, (root / "scripts/lab" / name).read_bytes(), work)
        writer.write_input(destination / "fixture/base.apk", Path(value["apk"]).read_bytes(), work)
        writer.write_input(destination / "fixture/fixture-inputs.json", (project / "fixture-inputs.json").read_bytes(), work)
        writer.write_input(destination / "fixture/request.json", request.read_bytes(), work)
        for name, target in FIXTURE_FILES.items():
            writer.write_input(destination / "fixture" / target, (root / name).read_bytes(), work)
        fixture(destination / "fixture", outputs)
        builder.stage(project, destination / "native", editor, android, generated_cpp=converter_output / "cpp")
        base_manifest = (destination / "native/input-manifest.json").read_bytes()
        base_plan = (destination / "native/plan.json").read_bytes()
        handoff_sha = sha(converter_output / "handoff-result.json")
        plan = native_plan(json.loads(base_plan), handoff_sha)
        (destination / "native/plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        inner = json.loads(base_manifest)
        inner["plan.json"] = sha(destination / "native/plan.json")
        (destination / "native/input-manifest.json").write_text(json.dumps(inner, indent=2) + "\n")
        writer.write_input(destination / "native-template-manifest.json", (template / "input-manifest.json").read_bytes(), work)
        writer.write_input(destination / "native-base-manifest.json", base_manifest, work)
        writer.write_input(destination / "native-base-plan.json", base_plan, work)
        provenance = dict(
            schema=1,
            profile=PROFILE,
            source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            converter_source_commit=upstream["source_commit"],
            compiler_source_commit=upstream["compiler_source_commit"],
            converter_manifest_sha256=sha(converter_stage / "input-manifest.json"),
            converter_handoff_sha256=handoff_sha,
            fixture_apk_sha256=APK_SHA,
            native_base_manifest_sha256=sha(destination / "native-base-manifest.json"),
            **SCOPE,
        )
        writer.write_input(destination / "provenance.json", (json.dumps(provenance, indent=2) + "\n").encode(), work)
        manifest = {path.relative_to(destination).as_posix(): sha(path) for path in sorted(destination.rglob("*")) if path.is_file()}
        writer.write_input(destination / "input-manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), work)
    validate(destination)
    if checked(template, TEMPLATE_SHA) != original or producer.validate(converter_stage)[0] != upstream_manifest:
        raise ValueError("Compiled-native suppliers changed during staging")
    return destination, provenance


def native_result(stage_root, output, provenance):
    result = json.loads(bounded(output, "result.json").read_text())
    plan = json.loads(bounded(stage_root, "native/plan.json").read_text())
    library = bounded(output, plan["library"])
    with library.open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:7] != b"\x7fELF\x02\x01\x01" or struct.unpack_from("<HHI", header, 16) != (3, 183, 1):
        raise ValueError("Expected an ELF64 little-endian AArch64 shared library")
    if (
        result.get("success") is not True
        or result.get("input_manifest_sha256") != sha(stage_root / "native/input-manifest.json")
        or result.get("completed") != len(plan["compile"])
        or result.get("library_sha256") != sha(library)
    ):
        raise ValueError("Native result/library differs")
    return plan, result


def captured_output(value):
    # TimeoutExpired can retain bytes even when run(text=True) was requested.
    raw = value if isinstance(value, bytes) else (value or "").encode("utf-8", errors="replace")
    encoded = raw[:CHILD_OUTPUT_LIMIT_BYTES].decode("utf-8", errors="replace").encode("utf-8")
    return encoded[:CHILD_OUTPUT_LIMIT_BYTES].decode("utf-8", errors="ignore"), len(raw) > CHILD_OUTPUT_LIMIT_BYTES or len(encoded) > CHILD_OUTPUT_LIMIT_BYTES


def build(stage_root, tool_root, output, reuse_request=None):
    stage_root, tool_root, output = (Path(path).absolute() for path in (stage_root, tool_root, output))
    manifest, provenance = validate(stage_root)
    if output != output.resolve() or output.exists() or output.parent != stage_root.parent or not output.name.startswith(stage_root.name + "-output-"):
        raise ValueError("Select a fresh owned sibling native output")
    command = [sys.executable, "-I", "-S", "-B", str(stage_root / "native/phone_native.py"), str(stage_root / "native"), str(tool_root), str(output)]
    if reuse_request is not None:
        command.append(str(Path(reuse_request).absolute()))
    started = time.monotonic()
    timed_out = False
    try:
        child = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_SECONDS)
        stdout, stderr, exit_code = child.stdout, child.stderr, child.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stdout_truncated = captured_output(error.stdout)
        stderr, stderr_truncated = captured_output(error.stderr)
        exit_code = None
        timed_out = True
    output.mkdir(exist_ok=True)
    (output / "driver.log").write_text(stdout + stderr)
    if timed_out:
        (output / "stdout.log").write_text(stdout)
        (output / "stderr.log").write_text(stderr)
    result = dict(
        schema=1,
        profile=PROFILE,
        success=False,
        source_commit=provenance["source_commit"],
        converter_handoff_sha256=provenance["converter_handoff_sha256"],
        input_manifest_sha256=sha(stage_root / "input-manifest.json"),
        exit_code=exit_code,
        elapsed_seconds=time.monotonic() - started,
        **SCOPE,
    )
    if timed_out:
        result.update(
            timed_out=True,
            timeout_seconds=CHILD_TIMEOUT_SECONDS,
            child_output_limit_bytes=CHILD_OUTPUT_LIMIT_BYTES,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )
    try:
        if validate(stage_root)[0] != manifest:
            raise ValueError("Native input preservation failed")
        if timed_out:
            raise ValueError("Native child timed out after " + str(CHILD_TIMEOUT_SECONDS) + " seconds")
        if exit_code:
            raise ValueError("Native execution or input preservation failed")
        plan, original = native_result(stage_root, output, provenance)
        result.update(
            success=True,
            native_built=True,
            native_result_sha256=sha(output / "result.json"),
            library=plan["library"],
            library_sha256=original["library_sha256"],
            completed=original["completed"],
            reused_objects=len(original.get("reused_objects", {})),
        )
    except (OSError, ValueError) as error:
        result["failure"] = str(error)
    with (output / "handoff-result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def library_input(request):
    if set(request) != {"stage", "output", "result_sha256"}:
        raise ValueError("Select an explicit compiled-native stage/output/result hash")
    stage_root, output = (Path(request[key]).absolute() for key in ("stage", "output"))
    _, provenance = validate(stage_root)
    file = bounded(output, "handoff-result.json")
    if sha(file) != request["result_sha256"]:
        raise ValueError("Compiled-native result drift")
    result = json.loads(file.read_text())
    plan, original = native_result(stage_root, output, provenance)
    if (
        result.get("profile") != PROFILE
        or result.get("success") is not True
        or result.get("exit_code") != 0
        or result.get("native_built") is not True
        or result.get("source_commit") != provenance["source_commit"]
        or result.get("input_manifest_sha256") != sha(stage_root / "input-manifest.json")
        or result.get("converter_handoff_sha256") != provenance["converter_handoff_sha256"]
        or result.get("native_result_sha256") != sha(output / "result.json")
        or result.get("library") != plan["library"]
        or result.get("library_sha256") != original["library_sha256"]
        or any(result.get(key) is not value for key, value in SCOPE.items())
    ):
        raise ValueError("Compiled-native handoff/scope differs")
    return bounded(stage_root, "fixture/base.apk"), bounded(output, plan["library"])


if __name__ == "__main__":
    if len(sys.argv) == 10 and sys.argv[1] == "stage":
        destination, receipt = stage(*sys.argv[2:])
        print(json.dumps(dict(stage=str(destination), **receipt)))
    elif len(sys.argv) in (5, 6) and sys.argv[1] == "run":
        result = build(*sys.argv[2:])
        print(json.dumps(result))
        raise SystemExit(0 if result["success"] else 1)
    else:
        raise SystemExit(
            "Usage: phone_compiled_native.py stage ROOT QUALIFIED_NATIVE_TEMPLATE FIXTURE_REQUEST CONVERTER_STAGE CONVERTER_OUTPUT EDITOR ANDROID WORK | run STAGE OWNED_TOOL_ROOT NEW_SIBLING_OUTPUT [REUSE_REQUEST] (current authored fixture; desktop scene/editor roots retained)"
        )
