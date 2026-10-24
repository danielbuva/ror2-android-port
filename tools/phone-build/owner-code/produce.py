"""Build player code from owner game/SDK inputs, or explicit managed providers.

Current experimental source_inputs mode composes the existing managed producers
with fixed roots, SDK stripping/conversion and native ARM64 construction. The
managed mode accepts an explicit prepared cohort for bounded backend work.
No project, captured DAG/response, Editor or device is read or executed.
"""

import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import phone_linker_roots  # noqa: E402
import phone_registry  # noqa: E402

SPEC = importlib.util.spec_from_file_location("owner_code_native_stage", HERE / "native.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
PROFILE = ROOT / "recipe/owner-player-code.json"
PROFILE_SHA = "50b445d8ae972880b3f5177bb9e5bcd6726acde344208fc039b2398ff19b8b98"
XML_ORDER = ("TypesInScenes.xml", "SerializedTypes.xml", "empty.xml", "burst.xml", "whole-preservation.xml", "item-behaviors.xml")


def target_inputs(selection):
    if set(selection) != {"profile", "source"}:
        raise ValueError("target requires explicit profile and authored source root")
    path, source = [native.canonical(selection[n]) for n in ("profile", "source")]
    target = json.loads(path.read_text())
    for name, expected in target["source_files"].items():
        file = native.canonical(source / native.relative(name))
        if not file.is_relative_to(source) or native.sha(file) != expected:
            raise ValueError("target authored source drift: " + name)
    return target, source, native.sha(path)


def tools(sdk, profile):
    actual = {}
    for folder in (sdk / "Unity.app/Contents/il2cpp/build/deploy", sdk / "Unity.app/Contents/il2cpp/LinkerDescriptors"):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                if not path.resolve().is_relative_to(sdk):
                    raise ValueError("converter tool escapes SDK")
                actual[path.relative_to(sdk).as_posix()] = native.sha(path)
    for name in (
        "PlaybackEngines/AndroidPlayer/modules.asset",
        "PlaybackEngines/AndroidPlayer/Tools/AndroidNativeLink.xml",
        "Unity.app/Contents/il2cpp/il2cpp_root",
    ):
        path = sdk / name
        if not path.resolve(strict=True).is_relative_to(sdk):
            raise ValueError("linker configuration escapes SDK")
        actual[name] = native.sha(path)
    if actual != profile["tools"]:
        raise ValueError("qualified SDK linker/converter tool or configuration drift")
    return actual


def providers(request, profile):
    if set(request) != set(profile["managed_assemblies"]):
        raise ValueError("complete managed provider membership differs")
    result = {}
    for name, row in request.items():
        if native.relative(name).name != name or not name.endswith(".dll") or set(row) != {"path", "sha256"}:
            raise ValueError("invalid managed provider record")
        source = native.canonical(row["path"])
        if not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) or native.sha(source) != row["sha256"]:
            raise ValueError("managed provider drift: " + name)
        result[name] = {"path": str(source), "sha256": row["sha256"], "bytes": source.stat().st_size}
    # Fixed-target Unity stripping preserves symbols. Omitting them changes PE
    # sizes, which changes the SDK converter's size-based assembly ordering.
    for name in profile.get("symbol_assemblies", []):
        source = Path(result[name]["path"]).with_suffix(".pdb")
        if not source.is_file() or source != source.resolve(strict=True):
            raise ValueError("required managed symbol companion missing or redirected: " + name)
        result[source.name] = {"path": str(source), "sha256": native.sha(source), "bytes": source.stat().st_size}
    return result


def configuration(profile, sdk, output):
    config = output / "configuration"
    config.mkdir()
    for name in XML_ORDER:
        (config / name).write_text(profile["xml"][name])
    registry = phone_registry.inspect(sdk / "Unity.app/Contents/MacOS/Unity", config / "sdk-native-registry.json")
    data = phone_linker_roots.compose(profile["project"], registry)
    native.write(config / "EditorToUnityLinkerData.json", data)
    return {p.name: native.sha(p) for p in config.iterdir() if p.is_file()}


def tool_command(sdk, output, name, android_tools=None):
    folder = sdk / "Unity.app/Contents/il2cpp/build/deploy"
    if android_tools:
        return [android_tools["dotnet"], "exec", "--runtimeconfig", str(output / "configuration/android.runtimeconfig.json"), str(folder / (name + ".dll"))]
    return [str(folder / name)]


def linker_command(sdk, output, profile, android_tools=None):
    inputs = output / "managed"
    config = output / "configuration"
    android = sdk / "PlaybackEngines/AndroidPlayer"
    command = tool_command(sdk, output, "UnityLinker", android_tools) + ["--search-directory=" + str(inputs), "--out=" + str(output / "stripped")]
    command += ["--include-link-xml=" + str(config / name) for name in XML_ORDER]
    command += [
        "--include-link-xml=" + str(android / "Tools/AndroidNativeLink.xml"),
        "--include-directory=" + str(inputs),
        "--rule-set=Conservative",
        "--profiler-report",
        "--profiler-output-file=" + str(output / "linker.traceevents"),
        "--dotnetprofile=unityaot-linux",
        "--dotnetruntime=Il2Cpp",
        "--platform=Android",
        "--use-editor-options",
        "--editor-settings-flag=None,Development",
        "--engine-modules-asset-file=" + str(android / "modules.asset"),
        "--editor-data-file=" + str(config / "EditorToUnityLinkerData.json"),
    ]
    command += ["--include-unity-root-assembly=" + str(inputs / n) for n in profile["root_assemblies"]]
    return command + ["--print-command-line"]


def converter_command(sdk, output, profile, android_tools=None):
    converter = output / "converter"
    command = tool_command(sdk, output, "il2cpp", android_tools) + ["--convert-to-cpp"]
    command += ["--assembly=" + str(output / "stripped" / n) for n in profile["converter_assemblies"]]
    command += [
        "--emit-null-checks",
        "--enable-array-bounds-check",
        "--dotnetprofile=unityaot-linux",
        "--data-folder=" + str(converter / "data"),
        "--generatedcppdir=" + str(converter / "cpp"),
        "--symbols-folder=" + str(converter / "cpp/Symbols"),
        "--profiler-report",
        "--profiler-output-file=" + str(converter / "converter.traceevents"),
        "--print-command-line",
    ]
    return command


def file_map(folder):
    return {p.relative_to(folder).as_posix(): {"bytes": p.stat().st_size, "sha256": native.sha(p)} for p in sorted(folder.rglob("*")) if p.is_file()}


def burst(tools, policy, managed, output):
    """Run the unchanged acquired Burst compiler over freshly produced DLLs."""
    if set(tools) != {"command", "runtime", "ndk"} or not isinstance(tools["command"], list) or not tools["command"]:
        raise ValueError("explicit Burst host command, runtime and NDK required")
    if any(not isinstance(arg, str) or any(c in arg for c in ("\n", "\r", "\0")) for arg in tools["command"]):
        raise ValueError("invalid Burst host argument")
    executable, runtime, ndk, managed = [native.canonical(p) for p in (tools["command"][0], tools["runtime"], tools["ndk"], managed)]
    output = Path(output)
    native.disjoint(output, [executable, runtime, ndk, managed])
    for name, expected in policy["runtime_files"].items():
        if native.sha(runtime / native.relative(name)) != expected:
            raise ValueError("pinned Burst compiler drift: " + name)
    backends = [name for name, expected in policy["backends"].items() if (runtime / name).is_file() and native.sha(runtime / name) == expected]
    if len(backends) != 1:
        raise ValueError("one pinned Burst LLVM backend required")
    providers, compiler = file_map(managed), file_map(runtime)
    runner = native.sha(executable)
    roots = [native.relative(name) for name in policy["roots"]]
    if any(len(name.parts) != 1 or name.suffix != ".dll" or name.as_posix() not in providers for name in roots):
        raise ValueError("complete produced Burst root cohort required")
    output.mkdir(mode=0o700)
    result = {"success": False, "runtime_qualified": False}
    try:
        for name in ("logs", "tmp"):
            (output / name).mkdir()
        options = [
            *policy["options"],
            "--temp-folder=" + str(output / "tmp"),
            "--assembly-folder=" + str(managed),
            "--output=" + str(output / "lib_burst_generated"),
            "--generate-link-xml=" + str(output / "burst.xml"),
        ]
        for name, defines in policy["assembly_defines"].items():
            options.append("--assembly-defines=" + name + ";" + ";".join(defines))
        options += ["--root-assembly=" + str(managed / name) for name in roots]
        response = output / "options.rsp"
        response.write_text("\n".join(options) + "\n")
        native.write(output / "inputs.json", {"managed": providers, "runtime": compiler, "runner_sha256": runner, "backend": backends[0]})
        environment = dict(os.environ, ANDROID_NDK_ROOT=str(ndk), BURST_ANDROID_MIN_API_LEVEL=str(policy["api_level"]), TMPDIR=str(output / "tmp"))
        native.invoke([*tools["command"], str(runtime / "bcl.exe"), "+burstc", "@" + str(response)], output, "burst", env=environment)
        library = output / "lib_burst_generated.so"
        with library.open("rb") as stream:
            header = stream.read(64)
        if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<HH", header, 16) != (3, 183):
            raise ValueError("Burst did not produce an AArch64 shared ELF")
        if not (output / "burst.xml").is_file():
            raise ValueError("Burst linker preservation output missing")
        if file_map(managed) != providers or file_map(runtime) != compiler or native.sha(executable) != runner:
            raise ValueError("Burst input or tool provider changed")
        result.update(
            success=True, library_sha256=native.sha(library), library_bytes=library.stat().st_size, linker_xml_sha256=native.sha(output / "burst.xml")
        )
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        native.write(output / "result.json", result)
    return result


def preserve_sources(converter, files, output):
    """Keep bounded exact frames; remove owned expansions only after verification."""
    frames = output / "sources"
    frames.mkdir()
    rows = {}
    for name, row in files.items():
        if not name.startswith("cpp/") or not name.endswith((".cpp", ".c")):
            continue
        relative = native.relative(name)
        if len(relative.parts) != 2:
            raise ValueError("unqualified nested generated translation unit")
        source = converter / relative
        if native.sha(source) != row["sha256"] or source.stat().st_size != row["bytes"]:
            raise ValueError("converter source changed before preservation")
        # Each task restores one source; cross-translation-unit includes are unsupported.
        with source.open("rb") as stream:
            for line in stream:
                if re.match(rb'\s*#\s*include\s*[<"][^>"\r\n]*\.(?:cpp|c)[>"]', line):
                    raise ValueError("generated source-to-source include requires qualification")
        target = frames / (source.name + ".gz")
        with source.open("rb") as incoming, target.open("xb") as packed:
            with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0) as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        # Verify the entire decompressed frame through the same native source contract.
        restore = converter / (source.name + ".verification")
        binding = {"path": str(target), "provider_sha256": native.sha(target), "compressed": True, **row}
        native.expand(binding, restore)
        restore.unlink()
        rows[source.name] = binding
    if not rows:
        raise ValueError("converter emitted no source translation units")
    native.write(output / "source-frames.json", rows)
    for name in rows:
        (converter / "cpp" / name).unlink()
    return frames


def verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs):
    if tools(sdk, profile) != sdk_state or providers(request["managed"], profile) != before or native.input_state(work) != state:
        raise ValueError("owner backend input drift")
    if {p.name: native.sha(p) for p in (output / "configuration").iterdir() if p.is_file()} != configs:
        raise ValueError("generated root configuration changed")
    if {n: native.sha(output / "managed" / n) for n in before} != {n: r["sha256"] for n, r in before.items()}:
        raise ValueError("managed inputs changed during owner backend")


def source_run(request, *, stop_after_conversion=False, burst_only=False):
    """Join original-input managed production to this same backend."""
    if set(request) - {"target", "android_tools", "linux_tools", "burst_tools"} != {"owner_work", "sdk_install", "source_inputs", "output"}:
        raise ValueError("explicit original-input owner request required")
    if burst_only and (stop_after_conversion or "burst_tools" not in request):
        raise ValueError("Burst-only qualification requires its tools and no conversion stop")
    specification = importlib.util.spec_from_file_location("owner_code_managed_producer", HERE / "managed.py")
    managed_owner = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = managed_owner
    specification.loader.exec_module(managed_owner)
    work, sdk = native.canonical(request["owner_work"]), native.canonical(request["sdk_install"])
    target, source_root, target_sha = target_inputs(request["target"]) if "target" in request else (None, None, None)
    if target is None and work != ROOT / "work":
        raise ValueError("source owner currently requires this checkout's work root")
    state = native.input_state(work)
    inputs = {k: native.canonical(v) for k, v in request["source_inputs"].items()} if target else managed_owner.bind_paths(request["source_inputs"])
    output = Path(request["output"])
    if not output.is_relative_to(work) or output == work:
        raise ValueError("new source owner output must be inside owner work")
    native.disjoint(output, [sdk, state[1], work / "config", work / "inventory", *inputs.values()])
    if native.sha(PROFILE) != PROFILE_SHA or native.sha(managed_owner.PROFILE) != managed_owner.PROFILE_SHA:
        raise ValueError("audited owner code profile drift")
    tools(sdk, target["player"] if target else json.loads(PROFILE.read_text()))
    if "linux_tools" in request:
        native.linux_tool_state(request["linux_tools"])
    native.sdk_files(sdk, json.loads(native.PROFILE.read_text()))
    output.mkdir(mode=0o700)
    result = {
        "schema": 1,
        "success": False,
        "phase": "managed-production",
        "source_sha256": native.sha(Path(__file__)),
        "phone_qualified": False,
        "runtime_qualified": False,
    }
    try:
        if target:
            providers = managed_owner.target_run(
                work, sdk, request["source_inputs"], target, source_root, output / "managed-production", android_tools=request.get("android_tools")
            )
        else:
            providers = managed_owner.run(work, sdk, request["source_inputs"], output / "managed-production")
        backend_request = {"owner_work": str(work), "sdk_install": str(sdk), "managed": providers, "output": str(output / "backend")}
        for name in ("target", "android_tools", "linux_tools", "burst_tools"):
            if name in request:
                backend_request[name] = request[name]
        native.write(output / "backend-request.json", backend_request)
        result["phase"] = "whole-player-backend"
        backend = run(backend_request, stop_after_conversion=stop_after_conversion, burst_only=burst_only)
        if native.input_state(work) != state:
            raise ValueError("owner input state changed across source production")
        if target and target_inputs(request["target"])[2] != target_sha:
            raise ValueError("target profile changed during source production")
        result.update(success=True, phase=backend["phase"], upstream_managed_generation_qualified=True, managed_providers=len(providers), backend=backend)
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        native.write(output / "result.json", result)
    return result


def run(request, *, stop_after_conversion=False, burst_only=False):
    if "source_inputs" in request:
        return source_run(request, stop_after_conversion=stop_after_conversion, burst_only=burst_only)
    if set(request) - {"android_tools", "target", "linux_tools", "burst_tools"} != {"owner_work", "sdk_install", "managed", "output"}:
        raise ValueError("explicit owner backend request required")
    if burst_only and (stop_after_conversion or "burst_tools" not in request):
        raise ValueError("Burst-only qualification requires its tools and no conversion stop")
    work, sdk = [native.canonical(request[k]) for k in ("owner_work", "sdk_install")]
    output = Path(request["output"])
    state = native.input_state(work)
    if native.sha(PROFILE) != PROFILE_SHA or native.sha(native.PROFILE) != native.PROFILE_SHA:
        raise ValueError("audited owner code profile drift")
    target, _, target_sha = target_inputs(request["target"]) if "target" in request else (None, None, None)
    profile = target["player"] if target else json.loads(PROFILE.read_text())
    if state[0] != profile["input_id"]:
        raise ValueError("unsupported legitimate game input")
    before = providers(request["managed"], profile)
    if "linux_tools" in request:
        native.linux_tool_state(request["linux_tools"])
    android_tools = request.get("android_tools")
    android_state = native.android_tool_state(android_tools) if android_tools else None
    if not output.is_relative_to(work) or output == work:
        raise ValueError("owner backend output must be inside owner work")
    native.disjoint(output, [sdk, state[1], work / "config", work / "inventory", *[Path(r["path"]) for r in before.values()]])
    sdk_state = tools(sdk, profile)
    # Qualify native compiler and all implicit NDK inputs before spending conversion work.
    native.sdk_files(sdk, json.loads(native.PROFILE.read_text()))
    output.mkdir(mode=0o700)
    result = {
        "schema": 1,
        "success": False,
        "phase": "configuration",
        "profile_sha256": PROFILE_SHA,
        "source_sha256": native.sha(Path(__file__)),
        "input_id": state[0],
        "phone_qualified": False,
        "runtime_qualified": False,
        "managed_providers_supplied": True,
    }
    try:
        for name in ("managed", "logs", "tmp", "converter"):
            (output / name).mkdir()
        native.write(output / "inputs.json", {"providers": before, "sdk_tools": sdk_state, "owner_state": state[2]})
        configs = configuration(profile, sdk, output)
        if android_tools:
            native.write(
                output / "configuration/android.runtimeconfig.json",
                {
                    "runtimeOptions": {
                        "tfm": "net8.0",
                        "framework": {"name": "Microsoft.NETCore.App", "version": "8.0.32"},
                        "configProperties": {"System.GC.Server": True},
                    }
                },
            )
            configs["android.runtimeconfig.json"] = native.sha(output / "configuration/android.runtimeconfig.json")
            native.write(output / "android-tools.json", android_state)
        for name, row in before.items():
            destination = output / "managed" / name
            with Path(row["path"]).open("rb") as incoming, destination.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            if native.sha(destination) != row["sha256"]:
                raise ValueError("managed input copy changed")
        if "burst_tools" in request:
            if target is None or "burst" not in target:
                raise ValueError("fixed target Burst policy required")
            if set(request["burst_tools"]) != {"command", "runtime"}:
                raise ValueError("explicit Burst host command and runtime required")
            result["phase"] = "burst-production"
            ndk = native.burst_ndk(sdk, request["linux_tools"], output / "burst-ndk") if "linux_tools" in request else sdk / "PlaybackEngines/AndroidPlayer/NDK"
            result["burst"] = burst({**request["burst_tools"], "ndk": str(ndk)}, target["burst"], output / "managed", output / "burst")
            if (output / "burst/burst.xml").read_text() != profile["xml"]["burst.xml"]:
                raise ValueError("fresh Burst preservation differs from qualified target roots")
            if burst_only:
                verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs)
                if target_inputs(request["target"])[2] != target_sha:
                    raise ValueError("target changed during Burst production")
                result.update(success=True, phase="burst-built")
                return result
        environment = dict(os.environ, TMPDIR=str(output / "tmp")) if android_tools else None
        native.write(
            output / "commands.json",
            {"linker": linker_command(sdk, output, profile, android_tools), "converter": converter_command(sdk, output, profile, android_tools)},
        )
        result["phase"] = "stripping"
        native.invoke(linker_command(sdk, output, profile, android_tools), output, "linker", env=environment)
        verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs)
        stripped = file_map(output / "stripped")
        if {n for n in stripped if n.endswith(".dll")} != set(profile["converter_assemblies"]):
            raise ValueError("complete stripped assembly closure differs")
        native.write(output / "stripping-result.json", {"exit_code": 0, "inputs_unchanged": True, "files": stripped})
        result["phase"] = "conversion"
        if shutil.disk_usage(output).free < 2 * 1024**3:
            raise RuntimeError("converter output reserve unavailable; prior outputs retained")
        native.invoke(converter_command(sdk, output, profile, android_tools), output, "converter", env=environment)
        converter = output / "converter"
        files = {folder + "/" + n: row for folder in ("cpp", "data") for n, row in file_map(converter / folder).items()}
        native_profile = json.loads(native.PROFILE.read_text())
        if target:
            native_profile = native.generated_profile(native_profile, files)
        if {"cpp/" + j["generated"] for j in native_profile["jobs"] if "generated" in j} != {n for n in files if n.endswith((".cpp", ".c"))}:
            raise ValueError("new code generation changes native membership; inspect profile drift")
        if "data/Metadata/global-metadata.dat" not in files:
            raise ValueError("converter metadata missing")
        if file_map(output / "stripped") != stripped:
            raise ValueError("stripped inputs changed during conversion")
        verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs)
        receipt = converter / "result.json"
        native.write(receipt, {"exit_code": 0, "inputs_unchanged": True, "input_assemblies": len(profile["converter_assemblies"]), "files": files})
        result["phase"] = "source-preservation"
        sources = preserve_sources(converter, files, output)
        native_request = {
            "owner_work": str(work),
            "sdk_install": str(sdk),
            "converter_receipt": str(receipt),
            "converter_receipt_sha256": native.sha(receipt),
            "sources": str(sources),
            "sources_compressed": True,
            "metadata": str(converter / "data/Metadata/global-metadata.dat"),
            "output": str(output / "native"),
        }
        if android_tools:
            native_request["android_tools"] = android_tools
        if "linux_tools" in request:
            native_request["linux_tools"] = request["linux_tools"]
        native.write(output / "native-request.json", native_request)
        result["phase"] = "native-planning" if stop_after_conversion else "native-production"
        native_result = native.run(native_request, plan_only=stop_after_conversion, **({"profile": native_profile} if target else {}))
        verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs)
        if android_tools and native.android_tool_state(android_tools) != android_state:
            raise ValueError("Android backend tools changed")
        if target and target_inputs(request["target"])[2] != target_sha:
            raise ValueError("target profile changed during backend")
        result.update(
            success=True,
            phase="converted-native-planned" if stop_after_conversion else "native-built",
            stripped_assemblies=len(profile["converter_assemblies"]),
            generated_files=len(files),
            source_frames=len(json.loads((output / "source-frames.json").read_text())),
            native=native_result,
        )
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        native.write(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--stop-after-conversion", action="store_true", help="run complete stripping/conversion/preservation and only plan native compilation")
    parser.add_argument("--burst-only", action="store_true", help="current fixed-target Burst qualification; stop before stripping/conversion/native work")
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.request.read_text()), stop_after_conversion=args.stop_after_conversion, burst_only=args.burst_only), indent=2))


if __name__ == "__main__":
    main()
