"""Replay only the authored fixture's captured UnityLinker inputs on Android.

Standalone: python3 -I -S phone_linker.py STAGE OWNED_TOOL_ROOT NEW_OUTPUT
Desktop scene/editor root production and supplied tools remain dependencies.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import time


LITERALS = {
    "--rule-set=Conservative",
    "--profiler-report",
    "--dotnetprofile=unityaot-linux",
    "--dotnetruntime=Il2Cpp",
    "--platform=Android",
    "--use-editor-options",
    "--editor-settings-flag=None,Development",
    "--print-command-line",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounded(root, value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Expected a bounded relative linker path")
    result = Path(root) / path.as_posix()
    if not result.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Linker path escapes its owned root")
    return result


def arguments(command, launcher, project, input_directory, capture, android):
    tokens = shlex.split(command)
    if not tokens or tokens.pop(0) != str(launcher):
        raise ValueError("Expected the exact supplied linker launcher")
    plan, literals, paths = [], [], []
    sdk = {android / "modules.asset": "sdk/modules.asset", android / "Tools/AndroidNativeLink.xml": "sdk/AndroidNativeLink.xml"}
    for token in tokens:
        if token == "--enable-analytics":
            continue
        if token in LITERALS:
            literals.append(token)
            plan.append(token)
            continue
        key, separator, value = token.partition("=")
        if not separator:
            raise ValueError("Unknown linker flag")
        if key == "--out" and value == "Library/Bee/artifacts/Android/ManagedStripped":
            plan.append({"output": "stripped", "prefix": key + "="})
        elif key == "--profiler-output-file" and Path(value).is_absolute() and Path(value).is_relative_to(project):
            plan.append({"output": "linker.traceevents", "prefix": key + "="})
        elif key in {
            "--search-directory",
            "--include-directory",
            "--include-link-xml",
            "--editor-data-file",
            "--engine-modules-asset-file",
            "--include-unity-root-assembly",
        }:
            source = Path(value)
            if source == input_directory:
                relative = "inputs"
            elif source.is_relative_to(input_directory):
                relative = "inputs/" + source.relative_to(input_directory).as_posix()
            elif source in sdk:
                relative = sdk[source]
            elif source == capture / "empty-linker.xml":
                relative = "empty-linker.xml"
            else:
                raise ValueError("Linker graph references a foreign input")
            bounded(Path("/stage"), relative)
            plan.append({"path": relative, "prefix": key + "="})
        else:
            raise ValueError("Unqualified linker option or output")
        paths.append(key)
    if len(literals) != len(LITERALS) or set(literals) != LITERALS:
        raise ValueError("Linker settings differ from the authored contract")
    required = {
        "--out": 1,
        "--profiler-output-file": 1,
        "--search-directory": 1,
        "--include-directory": 1,
        "--include-link-xml": 3,
        "--editor-data-file": 1,
        "--engine-modules-asset-file": 1,
        "--include-unity-root-assembly": 1,
    }
    if {key: paths.count(key) for key in paths} != required:
        raise ValueError("Linker descriptor/root closure differs")
    return plan


def stage_action(request):
    from common import ROOT, WORK, now
    from phone_content import validate_linker_capture
    from phone_native import fixture_request

    value, project = fixture_request(request, optional_fields=("capture",))
    attempt = Path(value["capture"]).resolve()
    if attempt.parent != project.parent or not attempt.name.startswith("editor-build-"):
        raise ValueError("Select the same fixture's owned editor attempt")
    build = json.loads((attempt / "receipt.json").read_text())
    if build["exit_code"] != 0 or build.get("oracle_error") is not None:
        raise ValueError("Fixture editor build did not pass")
    identity = validate_linker_capture(attempt, build["source_commit"])
    capture = Path(identity["capture"])
    receipt = json.loads((capture / "receipt.json").read_text())
    input_directory = bounded(project, receipt["input_directory"])
    editor = Path(os.environ["UNITY_EDITOR"]).parent.parent
    android = Path(os.environ["UNITY_ANDROID_ROOT"])
    nodes = []
    for graph in (project / "Library/Bee").glob("Player*.dag.json"):
        for node in json.loads(graph.read_text())["Nodes"]:
            if node.get("Annotation", "").startswith("UnityLinker "):
                nodes.append((graph, node))
    if len(nodes) != 1:
        raise ValueError("Expected exactly one fresh authored linker graph")
    graph, node = nodes[0]
    plan = arguments(node["Action"], editor / "il2cpp/build/deploy/UnityLinker", project, input_directory, capture, android)
    destination = WORK / "rebuild/phone-linker" / now()
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(capture / "inputs", destination / "inputs")
    shutil.copy2(capture / "empty-linker.xml", destination / "empty-linker.xml")
    if (destination / "empty-linker.xml").read_text() != '<?xml version="1.0" encoding="utf-8"?>\n<linker />\n':
        raise ValueError("Fixture callback descriptor is not inert")
    (destination / "sdk").mkdir()
    for source in (android / "modules.asset", android / "Tools/AndroidNativeLink.xml"):
        shutil.copy2(source, destination / "sdk" / source.name)
    (destination / "managed").mkdir()
    for source in (editor / "il2cpp/build/deploy").iterdir():
        if source.suffix in {".dll", ".json"}:
            shutil.copy2(source, destination / "managed" / source.name)
    (destination / "managed/probe.runtimeconfig.json").write_text(
        json.dumps(
            {
                "runtimeOptions": {
                    "tfm": "net8.0",
                    "framework": {"name": "Microsoft.NETCore.App", "version": "8.0.32"},
                    "configProperties": {"System.GC.Server": True},
                }
            }
        )
        + "\n"
    )
    support = destination / "support/libil2cpp"
    support.mkdir(parents=True)
    shutil.copy2(editor / "il2cpp/libil2cpp/libil2cpp.icalls", support / "libil2cpp.icalls")
    (destination / "plan.json").write_text(
        json.dumps(
            {
                "arguments": plan,
                "graph_sha256": sha(graph),
                "callback": identity,
                "game_inputs": False,
                "desktop_editor_roots": True,
                "changes": ["Android .NET 8.0.32 build-tool host", "Relocated input/output paths; unnecessary tool analytics disabled"],
            },
            indent=2,
        )
        + "\n"
    )
    shutil.copy2(__file__, destination / "phone_linker.py")
    manifest = {p.relative_to(destination).as_posix(): sha(p) for p in sorted(destination.rglob("*")) if p.is_file()}
    (destination / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = {
        "stage": str(destination),
        "files": len(manifest),
        "bytes": sum(p.stat().st_size for p in destination.rglob("*") if p.is_file()),
        "manifest_sha256": sha(destination / "input-manifest.json"),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "request": value,
        "capture_build_commit": build["source_commit"],
    }
    (destination / "stage-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def strip(stage_root, tool_root, output):
    stage_root, tool_root, output = (Path(p).resolve() for p in (stage_root, tool_root, output))
    output.mkdir(parents=True, exist_ok=False)
    result = {"schema": 1, "success": False}
    started = time.monotonic()
    try:
        result["input_manifest_sha256"] = sha(stage_root / "input-manifest.json")
        for name, digest in json.loads((stage_root / "input-manifest.json").read_text()).items():
            if sha(bounded(stage_root, name)) != digest:
                raise ValueError("Linker staged input drift")
        plan = json.loads((stage_root / "plan.json").read_text())
        if plan["game_inputs"] is not False or plan["desktop_editor_roots"] is not True:
            raise ValueError("Expected isolated authored linker inputs")
        argv = [
            str(tool_root / "usr/lib/dotnet/dotnet"),
            "exec",
            "--runtimeconfig",
            str(stage_root / "managed/probe.runtimeconfig.json"),
            str(stage_root / "managed/UnityLinker.dll"),
        ]
        for item in plan["arguments"]:
            if isinstance(item, str) and item in LITERALS:
                argv.append(item)
            elif isinstance(item, dict) and set(item) == {"path", "prefix"}:
                argv.append(item["prefix"] + str(bounded(stage_root, item["path"])))
            elif isinstance(item, dict) and set(item) == {"output", "prefix"} and item["output"] in {"stripped", "linker.traceevents"}:
                argv.append(item["prefix"] + str(bounded(output, item["output"])))
            else:
                raise ValueError("Unknown staged linker argument")
        env = dict(os.environ)
        env.update(
            DOTNET_ROOT=str(tool_root / "usr/lib/dotnet"),
            DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1",
            DOTNET_CLI_TELEMETRY_OPTOUT="1",
            IL2CPP_TESTHARNESS_SOLUTION_DIRECTORY=str(stage_root / "support"),
            TMPDIR=str(output / "tmp"),
        )
        (output / "tmp").mkdir()
        result["arguments"] = argv
        with (output / "linker.log").open("w") as log:
            completed = subprocess.run(argv, cwd=stage_root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        result["exit_code"] = completed.returncode
        if completed.returncode:
            raise RuntimeError("UnityLinker exit " + str(completed.returncode))
        result["outputs"] = {p.relative_to(output / "stripped").as_posix(): sha(p) for p in sorted((output / "stripped").rglob("*")) if p.is_file()}
        if "Assembly-CSharp.dll" not in result["outputs"]:
            raise ValueError("UnityLinker emitted no fixture assembly")
        result["success"] = True
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result["failure"] = str(error)
    result["elapsed_seconds"] = time.monotonic() - started
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"arguments", "outputs"}}))
    return result["success"]


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Expected STAGE OWNED_TOOL_ROOT NEW_OUTPUT")
    raise SystemExit(0 if strip(*sys.argv[1:]) else 1)
