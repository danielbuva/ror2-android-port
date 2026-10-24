"""Compose the existing fixed-root, linker, converter and native owner stages.

Experimental whole-player backend: upstream managed assembly production remains
an explicit supplied provider cohort. No project, captured DAG, response file,
Editor or device is read. The default runs through the ARM64 native library.
"""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import re
import shutil
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
PROFILE_SHA = "11780f8849add2425e53d25dd9dc045c7062c1405fd651e8e7f89f1ea89b155a"
XML_ORDER = ("TypesInScenes.xml", "SerializedTypes.xml", "empty.xml", "burst.xml", "whole-preservation.xml", "item-behaviors.xml")


def tools(sdk, profile):
    actual = {}
    folder = sdk / "Unity.app/Contents/il2cpp/build/deploy"
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            if not path.resolve().is_relative_to(sdk):
                raise ValueError("converter tool escapes SDK")
            actual[path.relative_to(sdk).as_posix()] = native.sha(path)
    for name in ("PlaybackEngines/AndroidPlayer/modules.asset", "PlaybackEngines/AndroidPlayer/Tools/AndroidNativeLink.xml"):
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


def linker_command(sdk, output, profile):
    inputs = output / "managed"
    config = output / "configuration"
    android = sdk / "PlaybackEngines/AndroidPlayer"
    command = [str(sdk / "Unity.app/Contents/il2cpp/build/deploy/UnityLinker"), "--search-directory=" + str(inputs), "--out=" + str(output / "stripped")]
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


def converter_command(sdk, output, profile):
    converter = output / "converter"
    command = [str(sdk / "Unity.app/Contents/il2cpp/build/deploy/il2cpp"), "--convert-to-cpp"]
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


def run(request, *, stop_after_conversion=False):
    if set(request) != {"owner_work", "sdk_install", "managed", "output"}:
        raise ValueError("explicit owner backend request required")
    work, sdk = [native.canonical(request[k]) for k in ("owner_work", "sdk_install")]
    output = Path(request["output"])
    state = native.input_state(work)
    if native.sha(PROFILE) != PROFILE_SHA or native.sha(native.PROFILE) != native.PROFILE_SHA:
        raise ValueError("audited owner code profile drift")
    profile = json.loads(PROFILE.read_text())
    if state[0] != profile["input_id"]:
        raise ValueError("unsupported legitimate game input")
    before = providers(request["managed"], profile)
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
        "upstream_managed_generation_qualified": False,
    }
    try:
        for name in ("managed", "logs", "tmp", "converter"):
            (output / name).mkdir()
        native.write(output / "inputs.json", {"providers": before, "sdk_tools": sdk_state, "owner_state": state[2]})
        configs = configuration(profile, sdk, output)
        for name, row in before.items():
            target = output / "managed" / name
            with Path(row["path"]).open("rb") as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            if native.sha(target) != row["sha256"]:
                raise ValueError("managed input copy changed")
        native.write(output / "commands.json", {"linker": linker_command(sdk, output, profile), "converter": converter_command(sdk, output, profile)})
        result["phase"] = "stripping"
        native.invoke(linker_command(sdk, output, profile), output, "linker")
        verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs)
        stripped = file_map(output / "stripped")
        if {n for n in stripped if n.endswith(".dll")} != set(profile["converter_assemblies"]):
            raise ValueError("complete stripped assembly closure differs")
        native.write(output / "stripping-result.json", {"exit_code": 0, "inputs_unchanged": True, "files": stripped})
        result["phase"] = "conversion"
        if shutil.disk_usage(output).free < 2 * 1024**3:
            raise RuntimeError("converter output reserve unavailable; prior outputs retained")
        native.invoke(converter_command(sdk, output, profile), output, "converter")
        converter = output / "converter"
        files = {folder + "/" + n: row for folder in ("cpp", "data") for n, row in file_map(converter / folder).items()}
        if {"cpp/" + j["generated"] for j in json.loads(native.PROFILE.read_text())["jobs"] if "generated" in j} != {
            n for n in files if n.endswith((".cpp", ".c"))
        }:
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
        native.write(output / "native-request.json", native_request)
        result["phase"] = "native-planning" if stop_after_conversion else "native-production"
        native_result = native.run(native_request, plan_only=stop_after_conversion)
        verify_inputs(request, profile, sdk, sdk_state, before, work, state, output, configs)
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
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.request.read_text()), stop_after_conversion=args.stop_after_conversion), indent=2))


if __name__ == "__main__":
    main()
