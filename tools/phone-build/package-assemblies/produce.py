"""Produce the retained SDK package cohort without the Unity Editor.

Experimental host support only. Explicit owner SDK/packages, no game/project or
captured inputs, no downloads or terms acceptance, no current game-build consumer.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROWS = (
    ("com.unity.ugui", "Runtime/UnityEngine.UI.asmdef"),
    ("com.unity.burst", "Runtime/Unity.Burst.asmdef"),
    ("com.unity.mathematics", "Unity.Mathematics/Unity.Mathematics.asmdef"),
    ("com.unity.collections", "Unity.Collections/Unity.Collections.asmdef"),
    ("com.unity.burst", "Unity.Burst.CodeGen/Unity.Burst.CodeGen.asmdef"),
)
PROFILE_SHA = "cc113c8d707f43d12d4afff574eebc5dab625c430612bd5bcb175e99fb9fadd3"
RESERVE = 1024**3


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def aggregate(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def canonical(value):
    path = Path(value)
    if any(c in str(path) for c in ('"', "\\", "\r", "\n", "\0")) or ".." in path.parts or not path.is_absolute() or path != path.resolve(strict=True):
        raise ValueError("explicit canonical input path required")
    return path


def profile():
    path = HERE / "profile.json"
    if sha(path) != PROFILE_SHA:
        raise ValueError("package compilation profile drift")
    return json.loads(path.read_text())


def sources(asmdef):
    """Honor nested assembly boundaries and same-assembly asmrefs; ignore ~/dot folders."""
    spec = json.loads(asmdef.read_text())
    guid = re.search(r"^guid: ([0-9a-f]{32})$", Path(str(asmdef) + ".meta").read_text(), re.M)
    if not guid:
        raise ValueError("assembly definition GUID missing")
    identities = {spec["name"], "GUID:" + guid[1]}
    selected = []
    for path in sorted(asmdef.parent.rglob("*.cs"), key=lambda p: p.as_posix().casefold()):
        relative = path.relative_to(asmdef.parent)
        if any(p.startswith(".") or p.endswith("~") for p in relative.parts[:-1]):
            continue
        if path.is_symlink() or path.resolve() != path:
            raise ValueError("redirected package source")
        redirected = False
        for folder in path.parents:
            if folder == asmdef.parent:
                break
            if list(folder.glob("*.asmdef")) or any(json.loads(p.read_text())["reference"] not in identities for p in folder.glob("*.asmref")):
                redirected = True
                break
        if not redirected:
            selected.append(path)
    return selected


def symbols(version, spec, versions):
    if version != "2021.3.45f2":
        raise ValueError("unqualified compiler version")
    values = set(
        "UNITY_2021_3_45 UNITY_2021_3 UNITY_2021 UNITY_ANDROID UNITY_ANDROID_API PLATFORM_ANDROID ENABLE_IL2CPP NET_STANDARD NET_STANDARD_2_0 NET_STANDARD_2_1 NETSTANDARD NETSTANDARD2_1 DEVELOPMENT_BUILD ENABLE_PROFILER DEBUG TRACE UNITY_ASSERTIONS CSHARP_7_OR_LATER CSHARP_7_3_OR_NEWER".split()
    )
    values.update("UNITY_5_" + str(n) + "_OR_NEWER" for n in range(3, 7))
    for year in range(2017, 2022):
        values.update("UNITY_" + str(year) + "_" + str(n) + "_OR_NEWER" for n in range(1, (4 if year < 2020 else 3) + 1))
    for row in spec.get("versionDefines", []):
        actual = versions.get(row["name"])
        if actual is None:
            continue
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", row["expression"]) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", actual):
            raise ValueError("unqualified package version expression")
        if tuple(map(int, actual.split("."))) >= tuple(map(int, row["expression"].split("."))):
            values.add(row["define"])
    return sorted(values)


def invoke(args, name, out):
    started = time.monotonic()
    result = {"name": name, "argv": [str(p) for p in args], "exit_code": None}
    with (out / (name + ".log")).open("xb") as log:
        process = subprocess.Popen(
            result["argv"],
            cwd=out,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=os.environ
            | {
                "TMPDIR": str(out / "tmp"),
                "DOTNET_CLI_HOME": str(out / "dotnet-home"),
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
            },
        )
        try:
            result["exit_code"] = process.wait(timeout=120)
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        finally:
            result["seconds"] = time.monotonic() - started
            (out / (name + ".process.json")).write_text(json.dumps(result, indent=2) + "\n")
    if result["exit_code"]:
        raise RuntimeError(name + " failed; see retained log")
    return result


def run(request):
    if set(request) != {"sdk_install", "packages", "output"}:
        raise ValueError("explicit SDK/package/output request required")
    install = canonical(request["sdk_install"])
    sdk = install / "Unity.app/Contents"
    packages = canonical(request["packages"])
    out = Path(request["output"])
    parent = canonical(str(out.parent))
    if not out.is_absolute() or out.name in ("", ".", "..") or out != parent / out.name or out.exists() or out.is_symlink():
        raise ValueError("new canonical output root required")
    if out.is_relative_to(install) or out.is_relative_to(packages) or install.is_relative_to(out) or packages.is_relative_to(out):
        raise ValueError("output and owner inputs overlap")
    if shutil.disk_usage(parent).free < RESERVE + 128 * 1024**2:
        raise ValueError("package output reserve unavailable")
    settings = profile()
    out.mkdir()
    for name in ("compiled", "postprocessed", "tmp"):
        (out / name).mkdir()
    terminal = {"schema": 1, "profile": settings["profile"], "success": False, "game_inputs": False, "editor_executed": False, "phone_qualified": False}
    try:
        inputs = {}

        def bind(path):
            path = canonical(str(path))
            if not path.is_file():
                raise ValueError("non-file package input")
            inputs[str(path)] = sha(path)
            return path

        reference_module = ROOT / "scripts/lab/phone_unity_compile.py"
        loader = importlib.util.spec_from_file_location("package_sdk_refs", reference_module)
        helper = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(helper)
        sdk_hashes = helper.references(install)
        refs = [install / p for p in sorted(sdk_hashes, key=str.casefold)]
        for path in refs:
            bind(path)
        bind(reference_module)
        bind(HERE / "produce.py")
        bind(HERE / "profile.json")
        versions = dict(settings["packages"])
        for path in (sdk / "Resources/PackageManager/BuiltInPackages").glob("*/package.json"):
            value = json.loads(path.read_text())
            versions[value["name"]] = value["version"]
            bind(path)
        for folder in (sdk / "NetCoreRuntime", sdk / "DotNetSdkRoslyn", sdk / "Tools/netcorerun", sdk / "Tools/ILPostProcessorRunner"):
            for path in folder.rglob("*"):
                if path.is_file():
                    bind(path)
        bind(sdk / "Managed/Unity.CompilationPipeline.Common.dll")
        tool_hashes = {
            Path(path).relative_to(sdk).as_posix(): digest
            for path, digest in inputs.items()
            if Path(path).is_relative_to(sdk)
            and (
                Path(path).relative_to(sdk).parts[0] in ("NetCoreRuntime", "DotNetSdkRoslyn", "Tools")
                or Path(path).relative_to(sdk).as_posix() == "Managed/Unity.CompilationPipeline.Common.dll"
            )
        }
        if len(tool_hashes) != settings["toolchain"]["input_count"] or aggregate(tool_hashes) != settings["toolchain"]["aggregate_sha256"]:
            raise ValueError("SDK compiler/post-processor toolchain drift")
        requests, built, results = [], {}, []
        for package, relative in ROWS:
            package_root = packages / (package + "@" + settings["packages"][package])
            asmdef = canonical(str(package_root / relative))
            spec = json.loads(asmdef.read_text())
            name, folder = spec["name"], asmdef.parent
            selected = sources(asmdef)
            extra = []
            if name == "Unity.Burst":
                extra = [package_root / "Unity.Burst.Unsafe.dll"]
            if name == "Unity.Collections":
                extra = [packages / "com.unity.collections@1.2.4/Unity.Collections.LowLevel.ILSupport/Unity.Collections.LowLevel.ILSupport.dll"]
            if name == "Unity.Burst.CodeGen":
                extra = [folder / p for p in spec["precompiledReferences"]]
            group = [asmdef, Path(str(asmdef) + ".meta"), *selected, *folder.rglob("*.asmref"), *extra]
            hashes = {p.relative_to(packages).as_posix(): sha(bind(p)) for p in group}
            expected = settings["groups"][name]
            if len(selected) != expected["source_count"] or len(hashes) != expected["input_count"] or aggregate(hashes) != expected["aggregate_sha256"]:
                raise ValueError("retained package source/precompiled input drift: " + name)
            references = list(refs) + extra
            if name == "Unity.Collections":
                references += [built["Unity.Burst"], built["Unity.Mathematics"]]
            if name == "Unity.Burst.CodeGen":
                references += [built["Unity.Burst"], sdk / "Managed/Unity.CompilationPipeline.Common.dll"]
            defines = symbols(settings["unity_version"], spec, versions)
            output = out / "compiled" / (name + ".dll")
            response = out / (name + ".generated.rsp")
            args = [
                "-target:library",
                "-out:" + json.dumps(str(output)),
                "-refout:" + json.dumps(str(out / "compiled" / (name + ".ref.dll"))),
                "-langversion:9.0",
                "/deterministic",
                "/optimize-",
                "/debug:portable",
                "/nologo",
                "/RuntimeMetadataVersion:v4.0.30319",
                "/nowarn:0169,0649,1701,1702",
                "/utf8output",
                "/preferreduilang:en-US",
                "-warn:0",
                "/pathmap:" + str(packages) + "=/owner/packages",
            ]
            if spec.get("allowUnsafeCode"):
                args.append("/unsafe+")
            args += ["-define:" + p for p in defines] + ["-r:" + json.dumps(str(p)) for p in references] + [json.dumps(str(p)) for p in selected]
            response.write_text("\n".join(args) + "\n")
            requests.append({"name": name, "source_count": len(selected), "inputs": hashes, "defines": defines, "references": [str(p) for p in references]})
            (out / "inputs.json").write_text(json.dumps({"packages": requests, "inputs": inputs}, indent=2) + "\n")
            invoke(
                [sdk / "NetCoreRuntime/dotnet", "exec", sdk / "DotNetSdkRoslyn/csc.dll", "/nostdlib", "/noconfig", "@" + str(response)], name + ".compile", out
            )
            built[name] = output
        for row in requests[:4]:
            name = row["name"]
            references = (
                refs
                + [p for n, p in built.items() if n != name]
                + [
                    packages / "com.unity.collections@1.2.4/Unity.Collections.LowLevel.ILSupport/Unity.Collections.LowLevel.ILSupport.dll",
                    packages / "com.unity.burst@1.8.11/Unity.Burst.Unsafe.dll",
                ]
            )
            args = ["-assembly", str(built[name]), "-outputDir", str(out / "postprocessed"), "-processors", str(built["Unity.Burst.CodeGen"])]
            for path in references:
                args += ["-assemblyReferences", str(path)]
            for define in row["defines"]:
                args += ["-defines", define]
            folders = {p.parent for p in references} | {
                sdk / "Managed",
                sdk / "Tools/ILPostProcessorRunner",
                packages / "com.unity.burst@1.8.11/Unity.Burst.CodeGen",
            }
            for path in sorted(folders):
                args += ["-assemblyFolders", str(path)]
            response = out / (name + ".generated-ilpp.rsp")
            response.write_text(" ".join(json.dumps(p) for p in args) + "\n")
            invoke(
                [sdk / "Tools/netcorerun/netcorerun", sdk / "Tools/ILPostProcessorRunner/ILPostProcessorRunner.exe", "@" + str(response)],
                name + ".postprocess",
                out,
            )
            output = out / "postprocessed" / (name + ".dll")
            results.append({"name": name, "bytes": output.stat().st_size, "sha256": sha(output), "compiled_sha256": sha(built[name])})
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError("owner input changed during production")
        terminal.update(success=True, packages=results)
    except Exception as error:
        terminal["error"] = str(error)
        raise
    finally:
        (out / "result.json").write_text(json.dumps(terminal, indent=2) + "\n")
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="private JSON with canonical sdk_install, packages and new output")
    args = parser.parse_args()
    result = run(json.loads(args.request.read_text()))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
