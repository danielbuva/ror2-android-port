"""Replay the authored player's converter, not a game runtime or full builder.

Android: python3 -I -S phone_converter.py STAGE OWNED_TOOL_ROOT NEW_OUTPUT
Supplied stripped assemblies/converter remain private; no redistribution grant.
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


FLAGS = {
    "--convert-to-cpp",
    "--emit-null-checks",
    "--enable-array-bounds-check",
    "--dotnetprofile=unityaot-linux",
    "--profiler-report",
    "--print-command-line",
}
OUTPUTS = {
    "--data-folder": "data",
    "--generatedcppdir": "cpp",
    "--symbols-folder": "cpp/Symbols",
    "--profiler-output-file": "converter.traceevents",
}
STRIPPED = "Library/Bee/artifacts/Android/ManagedStripped"


def bounded(root, value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Expected a bounded relative converter path")
    result = Path(root) / path.as_posix()
    if not result.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Converter path escapes its owned root")
    return result


def arguments(command, project, launcher):
    tokens = shlex.split(command)
    if not tokens or tokens.pop(0) != str(launcher):
        raise ValueError("Expected the exact supplied converter launcher")
    plan, assemblies, seen = [], [], set()
    for token in tokens:
        key, separator, value = token.partition("=")
        if key == "--assembly" and separator:
            path = PurePosixPath(value)
            if path.parent.as_posix() != STRIPPED or path.suffix != ".dll" or value in assemblies:
                raise ValueError("Expected unique fixture stripped assemblies")
            bounded(project, value)
            assemblies.append(value)
            plan.append({"input": value, "prefix": "--assembly="})
            continue
        if key in seen:
            raise ValueError("Duplicate converter option")
        seen.add(key)
        if token in FLAGS:
            plan.append(token)
        elif token == "--enable-analytics":
            # Tool telemetry is unnecessary for this local code-generation probe.
            continue
        elif key in OUTPUTS and separator and Path(value).is_absolute() and Path(value).resolve().is_relative_to(Path(project).resolve()):
            plan.append({"output": OUTPUTS[key], "prefix": key + "="})
        else:
            raise ValueError("Unknown converter option or foreign output")
    if not assemblies or seen != {flag.partition("=")[0] for flag in FLAGS} | set(OUTPUTS) | {"--enable-analytics"}:
        raise ValueError("Fixture converter flags differ from the qualified contract")
    return plan, assemblies


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(project, editor, destination, *, managed_stripped=None):
    project, editor, destination = map(Path, (project, editor, destination))
    launcher = editor / "il2cpp/build/deploy/il2cpp"
    nodes = []
    for graph in (project / "Library/Bee").glob("Player*.dag.json"):
        for node in json.loads(graph.read_text())["Nodes"]:
            if node.get("Annotation", "").startswith("IL2CPP_CodeGen "):
                nodes.append((graph, node))
    if len(nodes) != 1:
        raise ValueError("Expected exactly one fixture code-generation graph")
    graph, node = nodes[0]
    argv, assemblies = arguments(node["Action"], project, launcher)
    actual = {p.relative_to(project).as_posix() for p in (project / STRIPPED).glob("*.dll")}
    if set(assemblies) != actual:
        raise ValueError("Converter graph/stripped assembly closure differs")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(Path(managed_stripped) if managed_stripped else project / STRIPPED, destination / "project" / STRIPPED)
    managed = destination / "managed"
    managed.mkdir()
    for source in launcher.parent.iterdir():
        if source.suffix in {".dll", ".json"}:
            shutil.copy2(source, managed / source.name)
    (managed / "probe.runtimeconfig.json").write_text(
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
    plan = {
        "schema": 1,
        "arguments": argv,
        "assemblies": assemblies,
        "graph_sha256": sha(graph),
        "game_inputs": False,
        "desktop_stripping_inputs": managed_stripped is None,
        "desktop_editor_roots": True,
        "stripping_origin": "phone-unitylinker" if managed_stripped else "desktop",
        "changes": ["Android .NET 8.0.32 build-tool host replaces the desktop launcher", "Output paths relocated; unnecessary tool analytics disabled"],
    }
    (destination / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    shutil.copy2(__file__, destination / "phone_converter.py")
    manifest = {p.relative_to(destination).as_posix(): sha(p) for p in sorted(destination.rglob("*")) if p.is_file()}
    (destination / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "assemblies": len(assemblies),
        "files": len(manifest),
        "bytes": sum(p.stat().st_size for p in destination.rglob("*") if p.is_file()),
        "manifest_sha256": sha(destination / "input-manifest.json"),
    }


def stage_action(request):
    from common import ROOT, WORK, now
    from phone_native import fixture_request

    value, project = fixture_request(request, optional_fields=("linker",))
    managed_stripped = None
    if "linker" in value:
        from phone_linker import stripped_input

        if any(not Path(value["linker"][key]).resolve().is_relative_to(WORK.resolve()) for key in ("stage", "output")):
            raise ValueError("Linker inputs must remain ignored local state")
        managed_stripped = stripped_input(value["linker"], value)
    destination = WORK / "rebuild/phone-converter" / now()
    result = stage(project, Path(os.environ["UNITY_EDITOR"]).parent.parent, destination, managed_stripped=managed_stripped)
    result.update(stage=str(destination), request=value, source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
    (destination / "stage-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def cpp_input(request, fixture):
    """Bind actual converter outputs before selecting them for native compilation."""
    if set(request) != {"stage", "output", "result_sha256"}:
        raise ValueError("Expected explicit converter stage/output/result hash")
    stage_root, output = (Path(request[key]).resolve() for key in ("stage", "output"))
    receipt = json.loads((stage_root / "stage-receipt.json").read_text())
    if set(receipt["request"]) - {"linker"} != {"project", "apk", "sha256"} or {key: receipt["request"][key] for key in ("project", "apk", "sha256")} != {
        key: fixture[key] for key in ("project", "apk", "sha256")
    }:
        raise ValueError("Converter belongs to another fixture")
    result_file = output / "result.json"
    if sha(result_file) != request["result_sha256"]:
        raise ValueError("Converter result drift")
    result = json.loads(result_file.read_text())
    if result.get("success") is not True or result.get("exit_code") != 0 or result.get("input_manifest_sha256") != sha(stage_root / "input-manifest.json"):
        raise ValueError("Converter result/manifest failed")
    manifest = json.loads((stage_root / "input-manifest.json").read_text())
    for path, digest in manifest.items():
        if sha(bounded(stage_root, path)) != digest:
            raise ValueError("Converter input drift")
    project = Path(fixture["project"])
    selected = project / STRIPPED
    if "linker" in receipt["request"]:
        from phone_linker import stripped_input

        selected = stripped_input(receipt["request"]["linker"], fixture)
    original = {STRIPPED + "/" + p.relative_to(selected).as_posix(): sha(p) for p in selected.rglob("*") if p.is_file()}
    staged = {path.removeprefix("project/"): digest for path, digest in manifest.items() if path.startswith("project/" + STRIPPED + "/")}
    if original != staged:
        raise ValueError("Converter stripped input closure differs")
    actual = {p.relative_to(output).as_posix(): sha(p) for folder in (output / "cpp", output / "data") for p in folder.rglob("*") if p.is_file()}
    if not actual or actual != result["outputs"]:
        raise ValueError("Converter output drift")
    data = project / "Library/Bee/artifacts/Android/il2cppOutput/data"
    oracle = {"data/" + p.relative_to(data).as_posix(): sha(p) for p in data.rglob("*") if p.is_file()}
    if not oracle or oracle != {path: digest for path, digest in actual.items() if path.startswith("data/")}:
        raise ValueError("Converter data/metadata differs from the fixture")
    return output / "cpp"


def convert(stage_root, tool_root, output):
    stage_root, tool_root, output = (Path(p).resolve() for p in (stage_root, tool_root, output))
    output.mkdir(parents=True, exist_ok=False)
    result = {"schema": 1, "success": False}
    started = time.monotonic()
    try:
        manifest = stage_root / "input-manifest.json"
        result["input_manifest_sha256"] = sha(manifest)
        for relative, expected in json.loads(manifest.read_text()).items():
            if sha(bounded(stage_root, relative)) != expected:
                raise ValueError("Converter staged input drift: " + relative)
        plan = json.loads((stage_root / "plan.json").read_text())
        origin = plan.get("stripping_origin", "desktop")
        if (
            plan["game_inputs"] is not False
            or (origin, plan["desktop_stripping_inputs"]) not in {("desktop", True), ("phone-unitylinker", False)}
            or (origin == "phone-unitylinker" and plan.get("desktop_editor_roots") is not True)
        ):
            raise ValueError("Expected isolated authored converter inputs")
        argv = [
            str(tool_root / "usr/lib/dotnet/dotnet"),
            "exec",
            "--runtimeconfig",
            str(stage_root / "managed/probe.runtimeconfig.json"),
            str(stage_root / "managed/il2cpp.dll"),
        ]
        for item in plan["arguments"]:
            if isinstance(item, str) and item in FLAGS:
                argv.append(item)
            elif isinstance(item, dict) and set(item) == {"input", "prefix"} and item["prefix"] == "--assembly=":
                bounded(stage_root / "project", item["input"])
                argv.append(item["prefix"] + item["input"])
            elif (
                isinstance(item, dict)
                and set(item) == {"output", "prefix"}
                and item["prefix"][:-1] in OUTPUTS
                and item["output"] == OUTPUTS[item["prefix"][:-1]]
            ):
                argv.append(item["prefix"] + str(bounded(output, item["output"])))
            else:
                raise ValueError("Unknown staged converter argument")
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
        with (output / "converter.log").open("w") as log:
            completed = subprocess.run(argv, cwd=stage_root / "project", env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        result["exit_code"] = completed.returncode
        if completed.returncode:
            raise RuntimeError("IL2CPP converter exit " + str(completed.returncode))
        result["outputs"] = {
            p.relative_to(output).as_posix(): sha(p) for folder in (output / "cpp", output / "data") for p in sorted(folder.rglob("*")) if p.is_file()
        }
        if not any(p.endswith("global-metadata.dat") for p in result["outputs"]) or not any(p.endswith(".cpp") for p in result["outputs"]):
            raise ValueError("Converter emitted no complete C++/metadata output")
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
    raise SystemExit(0 if convert(*sys.argv[1:]) else 1)
