"""Stage/replay only the authored fixture's native compilation graph.

Android: python3 -I -S phone_native.py STAGE OWNED_TOOL_ROOT NEW_OUTPUT [REUSE.json]
This copies supplied inputs, never edits Unity/game source, and is not a player builder.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import time


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Expected a bounded relative native path")
    return path.as_posix()


def lump_includes(node):
    includes = []
    for line in node["WriteTextFilePayload"].splitlines():
        if not line or line.startswith("//"):
            continue
        match = re.fullmatch(r'#include "([^"\n]+)"', line)
        if not match:
            raise ValueError("Unrecognized lump directive; refusing to rewrite it")
        includes.append(match[1])
    if not includes or set(includes) != set(node["FilesThatMightBeIncluded"]):
        raise ValueError("Lump dependency/payload mismatch")
    return includes


def path_argument(value, roots, *, prefix=""):
    value = Path(value)
    if not value.is_absolute():
        return {"path": "project" + ("/" + relative(value.as_posix()) if value.as_posix() != "." else ""), "prefix": prefix}
    for source, destination in roots:
        if value.is_relative_to(source):
            return {"path": relative(destination + "/" + value.relative_to(source).as_posix()), "prefix": prefix}
    raise ValueError("Native graph references an unrecognized input root")


def command_arguments(command, compiler, roots, outputs):
    tokens = shlex.split(command)
    if tokens.pop(0) != str(compiler) or any(token in {";", "&&", "||", "|"} for token in tokens):
        raise ValueError("Expected one pinned compiler invocation")
    result = []
    output_next = False
    for token in tokens:
        if output_next:
            result.append({"output": relative(token)})
            output_next = False
        elif token == "-o":
            result.append(token)
            output_next = True
        elif token in outputs:
            result.append({"output": relative(token)})
        elif token.startswith("-I"):
            result.append(path_argument(token[2:], roots, prefix="-I"))
        elif token.startswith("/") or token.endswith((".cpp", ".c", ".a")):
            result.append(path_argument(token, roots))
        elif token.startswith("@"):
            raise ValueError("Expand response files explicitly before staging")
        else:
            result.append(token)
    if output_next:
        raise ValueError("Compiler output argument is missing")
    return result


def stage(project, destination, editor, android, *, generated_cpp=None):
    project, destination, editor, android = map(Path, (project, destination, editor, android))
    destination.mkdir(parents=True, exist_ok=False)
    roots = [(project, "project"), (editor, "unity"), (android, "android")]
    compiler = android / "NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/clang++"
    graphs = []
    for path in (project / "Library/Bee").glob("Player*.dag.json"):
        data = json.loads(path.read_text())
        if any(node.get("Annotation", "").startswith("Link_Android_arm64 ") for node in data["Nodes"]):
            graphs.append((path, data))
    if len(graphs) != 1:
        raise ValueError("Select a fixture with exactly one ARM64 native graph")
    graph, data = graphs[0]
    compiles = [node for node in data["Nodes"] if node.get("Annotation", "").startswith("C_Android_arm64 ")]
    links = [node for node in data["Nodes"] if node.get("Annotation", "").startswith("Link_Android_arm64 ")]
    if not compiles or len(links) != 1:
        raise ValueError("Native graph compile/link contract differs")
    outputs = {node["Outputs"][0] for node in compiles}
    for output in outputs:
        relative(output)
    for source, target in (
        (editor / "il2cpp/libil2cpp", "unity/il2cpp/libil2cpp"),
        (editor / "il2cpp/external", "unity/il2cpp/external"),
        (
            Path(generated_cpp) if generated_cpp else project / "Library/Bee/artifacts/Android/il2cppOutput/cpp",
            "project/Library/Bee/artifacts/Android/il2cppOutput/cpp",
        ),
    ):
        shutil.copytree(source, destination / target)
    sysroot = android / "NDK/toolchains/llvm/prebuilt/darwin-x86_64/sysroot"
    shutil.copytree(sysroot / "usr/include", destination / "ndk/sysroot/usr/include")
    arch = "usr/lib/aarch64-linux-android"
    shutil.copytree(sysroot / arch / "22", destination / "ndk/sysroot" / arch / "22")
    for source in (sysroot / arch).iterdir():
        if source.is_file():
            shutil.copy2(source, destination / "ndk/sysroot" / arch / source.name)
    shutil.copy2(android / "NDK/toolchains/llvm/prebuilt/darwin-x86_64/lib/gcc/aarch64-linux-android/4.9.x/libgcc.a", destination / "ndk/libgcc.a")
    shutil.copy2(android / "NDK/toolchains/llvm/prebuilt/darwin-x86_64/lib/gcc/aarch64-linux-android/4.9.x/libgcc_real.a", destination / "ndk/libgcc_real.a")
    baseline = android / "Variations/il2cpp/Development/StaticLibs/arm64-v8a/baselib.a"
    target = destination / path_argument(str(baseline), roots)["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(baseline, target)
    for node in data["Nodes"]:
        if not node.get("Annotation", "").startswith("MakeLump "):
            continue
        wrapper = destination / "project" / relative(node["Outputs"][0])
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        includes = [destination / path_argument(name, roots)["path"] for name in lump_includes(node)]
        if not all(path.is_file() for path in includes):
            raise ValueError("Lump input was not staged")
        wrapper.write_text(
            "// Authored relocation wrapper; included source bytes are unchanged.\n"
            + "".join('#include "' + os.path.relpath(path, wrapper.parent) + '"\n' for path in includes)
        )
    link = links[0]
    tokens = shlex.split(link["Action"])
    if len(tokens) != 2 or tokens[0] != str(compiler) or not tokens[1].startswith("@"):
        raise ValueError("Expected an explicit native link response file")
    response = project / relative(tokens[1][1:])
    link_command = shlex.join([str(compiler), *shlex.split(response.read_text())])
    plan = {
        "schema": 1,
        "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "compile": [{"arguments": command_arguments(node["Action"], compiler, roots, outputs), "output": relative(node["Outputs"][0])} for node in compiles],
        "link": command_arguments(link_command, compiler, roots, outputs),
        "library": relative(link["Outputs"][0]),
        "changes": [
            "Android-host Clang 21 replaces desktop Clang 9",
            "LLD replaces the recorded BFD linker",
            "Explicit original NDK target sysroot and C++ headers/libraries",
            "Fresh relative include wrappers preserve original lump input order",
            "Explicit original static C++/ABI/GCC archives replace compiler implicit C++/unwind selection",
        ],
        "game_inputs": False,
        "desktop_stripping_and_codegen_inputs": generated_cpp is None,
        "desktop_stripping_inputs": True,
        "codegen_origin": "phone-converter" if generated_cpp else "desktop",
    }
    (destination / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    shutil.copy2(Path(__file__), destination / "phone_native.py")
    manifest = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(destination.rglob("*")) if path.is_file()
    }
    (destination / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "compile_tasks": len(compiles),
        "files": len(manifest),
        "bytes": sum(path.stat().st_size for path in destination.rglob("*") if path.is_file()),
        "manifest_sha256": hashlib.sha256((destination / "input-manifest.json").read_bytes()).hexdigest(),
    }


def fixture_request(request, *, optional_fields=()):
    """Bind the shared authored fixture before staging any private build inputs."""
    from common import ROOT, WORK
    from phone_apk import update_manifest

    import zipfile

    request = Path(request).resolve()
    if not request.is_relative_to(WORK.resolve()):
        raise ValueError("Native fixture request must be ignored local state")
    value = json.loads(request.read_text())
    if set(value) - set(optional_fields) != {"project", "apk", "sha256"}:
        raise ValueError("Expected explicit fixture project, APK and hash")
    project, apk = Path(value["project"]).resolve(), Path(value["apk"]).resolve()
    if (
        not project.is_relative_to((WORK / "rebuild/phone-content").resolve())
        or not apk.is_relative_to(WORK.resolve())
        or hashlib.sha256(apk.read_bytes()).hexdigest() != value["sha256"]
    ):
        raise ValueError("Authored fixture path/hash mismatch")
    receipt = json.loads((project / "fixture-inputs.json").read_text())
    if receipt.get("game_inputs") is not False or receipt.get("unity") != "2021.3.45f2":
        raise ValueError("Expected the pinned authored fixture")
    for name in ("ContentFixture.cs", "ContentFixtureBuilder.cs"):
        source = ROOT / "tools/phone-build" / name
        if receipt["sources"]["tools/phone-build/" + name] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError("Fixture source drift")
        staged = project / ("Assets/Editor" if name.endswith("Builder.cs") else "Assets") / name
        if staged.read_bytes() != source.read_bytes():
            raise ValueError("Staged fixture source drift")
    with zipfile.ZipFile(apk) as archive:
        if (
            update_manifest(archive.read("AndroidManifest.xml"), 3)[1] != 2
            or hashlib.sha256(archive.read("assets/phone-fixture.bundle")).hexdigest() != receipt["bundle_sha256"]
        ):
            raise ValueError("Expected the fixture base APK/content")
    return value, project


def stage_action(request):
    from common import ROOT, WORK, now

    value, project = fixture_request(request, optional_fields=("converter",))
    generated_cpp = None
    if "converter" in value:
        from phone_converter import cpp_input

        if any(not Path(value["converter"][key]).resolve().is_relative_to(WORK.resolve()) for key in ("stage", "output")):
            raise ValueError("Converter inputs must remain ignored local state")
        generated_cpp = cpp_input(value["converter"], value)
    destination = WORK / "rebuild/phone-native" / now()
    result = stage(project, destination, Path(os.environ["UNITY_EDITOR"]).parent.parent, Path(os.environ["UNITY_ANDROID_ROOT"]), generated_cpp=generated_cpp)
    result.update(stage=str(destination), request=value, source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
    (destination / "stage-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def compiler_arguments(stage_root, tool_root, output_root, arguments, *, link=False):
    def render(item):
        if isinstance(item, str):
            return item
        if set(item) == {"output"}:
            return str(output_root / relative(item["output"]))
        if set(item) == {"path", "prefix"}:
            return item["prefix"] + str(stage_root / relative(item["path"]))
        raise ValueError("Unrecognized native argument record")

    argv = [
        str(tool_root / "usr/bin/clang-21"),
        "--driver-mode=g++",
        "--sysroot=" + str(stage_root / "ndk/sysroot"),
        "-resource-dir=" + str(tool_root / "usr/lib/clang/21"),
    ]
    if link or "-std=c++11" in arguments:
        argv += ["-nostdinc++", "-isystem", str(stage_root / "ndk/sysroot/usr/include/c++/v1")]
    argv += [render(item) for item in arguments if item != "-fuse-ld=bfd" and not (link and item == "-static-libstdc++")]
    if link:
        arch = stage_root / "ndk/sysroot/usr/lib/aarch64-linux-android"
        argv += [
            "--ld-path=" + str(tool_root / "usr/bin/ld.lld"),
            "-B" + str(arch / "22"),
            "-L" + str(arch / "22"),
            "-L" + str(arch),
            "-L" + str(stage_root / "ndk"),
            "-nostdlib++",
            "--unwindlib=none",
            str(arch / "libc++_static.a"),
            str(arch / "libc++abi.a"),
            str(stage_root / "ndk/libgcc.a"),
        ]
    return argv


def reuse_objects(stage_root, tool_root, output_root, request):
    prior, old_stage = Path(request["output"]).resolve(), Path(request["stage"]).resolve()
    raw = (prior / "result.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != request["result_sha256"]:
        raise ValueError("Prior native result drift")
    result = json.loads(raw)
    old_manifest = json.loads((old_stage / "input-manifest.json").read_text())
    new_manifest = json.loads((stage_root / "input-manifest.json").read_text())
    if result["input_manifest_sha256"] != hashlib.sha256((old_stage / "input-manifest.json").read_bytes()).hexdigest():
        raise ValueError("Prior native manifest drift")
    metadata = {"plan.json", "phone_native.py", "ndk/libgcc.a", "ndk/libgcc_real.a"}
    if {k: v for k, v in old_manifest.items() if k not in metadata} != {k: v for k, v in new_manifest.items() if k not in metadata}:
        raise ValueError("Native source/target inputs differ; recompile")
    plan = json.loads((stage_root / "plan.json").read_text())
    if json.loads((old_stage / "plan.json").read_text())["compile"] != plan["compile"]:
        raise ValueError("Native compile plan differs; recompile")
    commands = [item for item in result["commands"] if item["label"].startswith("compile-")]
    outputs = {task["output"] for task in plan["compile"]}
    if result["completed"] != len(outputs) or set(request["objects"]) != outputs or len(commands) != len(outputs):
        raise ValueError("Prior native object set is incomplete")
    for index, task in enumerate(plan["compile"]):
        command = commands[index]
        if (
            command["exit"] != 0
            or command["label"] != f"compile-{index:03}"
            or command["args"] != compiler_arguments(old_stage, tool_root, prior, task["arguments"])
        ):
            raise ValueError("Native compiler arguments differ; recompile")
        source = prior / relative(task["output"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != request["objects"][task["output"]]:
            raise ValueError("Prior native object drift")
    for name in sorted(outputs):
        target = output_root / relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prior / name, target)
    return request["objects"]


def build(stage_root, tool_root, output_root, reuse_request=None):
    stage_root, tool_root, output_root = (Path(value).resolve() for value in (stage_root, tool_root, output_root))
    output_root.mkdir(mode=0o700, exist_ok=False)
    result = {"schema": 1, "success": False, "completed": 0, "commands": []}
    started = time.monotonic()

    def save():
        result["elapsed_seconds"] = time.monotonic() - started
        (output_root / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    def run(arguments, label, *, link=False):
        argv = compiler_arguments(stage_root, tool_root, output_root, arguments, link=link)
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(tool_root / "usr/lib") + ":" + str(tool_root / "python/usr/lib")
        process = subprocess.run(argv, cwd=stage_root / "project", env=env, capture_output=True, text=True, timeout=180)
        (output_root / (label + ".log")).write_text(process.stdout + process.stderr)
        result["commands"].append({"label": label, "args": argv, "exit": process.returncode})
        save()
        if process.returncode:
            raise RuntimeError(label + " exit " + str(process.returncode))

    try:
        manifest = (stage_root / "input-manifest.json").read_bytes()
        result["input_manifest_sha256"] = hashlib.sha256(manifest).hexdigest()
        for name, digest in json.loads(manifest).items():
            if hashlib.sha256((stage_root / relative(name)).read_bytes()).hexdigest() != digest:
                raise ValueError("Native staged input drift: " + name)
        plan = json.loads((stage_root / "plan.json").read_text())
        result["changes"] = plan["changes"]
        if reuse_request:
            reuse = json.loads(Path(reuse_request).read_text())
            result["reused_objects"] = reuse_objects(stage_root, tool_root, output_root, reuse)
            result["completed"] = len(result["reused_objects"])
            result["reuse_request_sha256"] = hashlib.sha256(Path(reuse_request).read_bytes()).hexdigest()
        else:
            for index, task in enumerate(plan["compile"]):
                (output_root / relative(task["output"])).parent.mkdir(parents=True, exist_ok=True)
                result["active"] = index
                save()
                run(task["arguments"], f"compile-{index:03}")
                result["completed"] += 1
        run(plan["link"], "link", link=True)
        library = output_root / relative(plan["library"])
        result.update(success=True, library=str(library), library_sha256=hashlib.sha256(library.read_bytes()).hexdigest())
    except Exception as error:
        result["failure"] = str(error)
    finally:
        save()
    print(json.dumps({key: value for key, value in result.items() if key not in {"commands", "reused_objects"}}))
    return result["success"]


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        raise SystemExit(__doc__)
    raise SystemExit(0 if build(*sys.argv[1:]) else 1)
