"""Read-only SDK metadata coverage, never a substitute linker-root generator."""

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def coverage(inventory, oracle):
    """Keep explicit attribute evidence separate from unauthoritative name guesses."""
    groups = defaultdict(list)
    for assembly in inventory["assemblies"]:
        for item in assembly["types"]:
            groups[assembly["group"]].append(item | {"assembly": assembly["assembly"]})
    reports = {}
    for group, types in groups.items():
        explicit, short = defaultdict(list), defaultdict(list)
        for item in types:
            short[item["name"].rsplit("/", 1)[-1].rsplit(".", 1)[-1]].append(item)
            for attribute in item["native_attributes"]:
                # A header/property does not establish a native type name.
                if attribute["name"].endswith(".NativeClassAttribute") and attribute["arguments"] and attribute["arguments"][0]["type"] == "System.String":
                    explicit[attribute["arguments"][0]["value"]].append(item)
        rows = []
        for native in oracle["allNativeTypes"]:
            exact = explicit.get(native["qualifiedName"], [])
            explicit_short = explicit.get(native["name"], []) if native["qualifiedName"] != native["name"] else []
            inferred = short.get(native["name"], [])
            rows.append(
                {
                    "native": native,
                    "explicit_qualified_candidates": [{"name": x["name"], "assembly": x["assembly"], "base_type": x["base_type"]} for x in exact],
                    "explicit_short_candidates": [{"name": x["name"], "assembly": x["assembly"]} for x in explicit_short],
                    "managed_short_name_candidates": [{"name": x["name"], "assembly": x["assembly"], "base_type": x["base_type"]} for x in inferred],
                    "native_module_and_base_proven": False,
                }
            )
        reports[group] = {
            "managed_types": len(types),
            "types_with_native_attributes": sum(bool(x["native_attributes"]) for x in types),
            "native_types": len(rows),
            "unique_explicit_qualified_matches": sum(len(x["explicit_qualified_candidates"]) == 1 for x in rows),
            "unique_explicit_short_matches": sum(len(x["explicit_short_candidates"]) == 1 for x in rows),
            "unique_managed_short_name_matches": sum(len(x["managed_short_name_candidates"]) == 1 for x in rows),
            "ambiguous_managed_short_names": sum(len(x["managed_short_name_candidates"]) > 1 for x in rows),
            "missing_managed_short_names": sum(not x["managed_short_name_candidates"] for x in rows),
            "root_generation_qualified": False,
            "rows": rows,
        }
    return reports


def inspect_action(request):
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
    capture = Path(validate_linker_capture(attempt, build["source_commit"])["capture"])
    editor = Path(os.environ["UNITY_EDITOR"]).parent.parent
    inputs = []
    for group, directory in (("editor-sdk", editor / "Managed/UnityEngine"), ("player-sdk", capture / "inputs")):
        paths = sorted(directory.glob("UnityEngine*.dll"))
        if not paths:
            raise ValueError("No SDK assemblies in " + group)
        inputs += [{"group": group, "path": str(path)} for path in paths]
    destination = WORK / "experiments/phone-roots" / now()
    destination.mkdir(parents=True, exist_ok=False)
    result = {
        "success": False,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "request": value,
        "executes_inputs": False,
    }
    try:
        source = ROOT / "tools/phone-build/metadata"
        shutil.copytree(source, destination / "source")
        result["tool_sources"] = {path.name: sha(path) for path in sorted(source.iterdir()) if path.is_file()}
        (destination / "inputs.json").write_text(json.dumps({"assemblies": inputs}, indent=2) + "\n")
        (destination / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>\n")
        cecil = editor / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
        expected = json.loads((ROOT / "recipe/assembly-transforms.json").read_text())["cecil_sha256"]
        if sha(cecil) != expected:
            raise ValueError("Supplied Cecil differs from the exact SDK pin")
        result["cecil_sha256"] = expected
        dotnet = Path.home() / ".local/share/dotnet/dotnet"
        env = dict(os.environ)
        env.update(
            DOTNET_CLI_HOME=str(destination / "dotnet-home"),
            NUGET_PACKAGES=str(destination / "nuget"),
            DOTNET_CLI_TELEMETRY_OPTOUT="1",
            DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
            MSBUILDDISABLENODEREUSE="1",
            DOTNET_CLI_USE_MSBUILD_SERVER="0",
        )
        commands = [
            [
                str(dotnet),
                "build",
                str(destination / "source/MetadataInventory.csproj"),
                "-o",
                str(destination / "tool"),
                "-p:CecilPath=" + str(cecil),
                "-p:RestoreConfigFile=" + str(destination / "NuGet.Config"),
                "-p:UseSharedCompilation=false",
                "--nologo",
            ],
            [str(dotnet), str(destination / "tool/MetadataInventory.dll"), str(destination / "inputs.json"), str(destination / "metadata.json")],
        ]
        for index, command in enumerate(commands):
            with (destination / f"command-{index}.log").open("w") as log:
                completed = subprocess.run(command, cwd=destination, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
            if completed.returncode:
                raise RuntimeError(f"SDK metadata command {index} exit {completed.returncode}")
        inventory = json.loads((destination / "metadata.json").read_text())
        oracle_path = capture / "inputs/EditorToUnityLinkerData.json"
        reports = coverage(inventory, json.loads(oracle_path.read_text()))
        (destination / "coverage.json").write_text(json.dumps(reports, indent=2) + "\n")
        result.update(
            success=True,
            input_assemblies=len(inputs),
            metadata_sha256=sha(destination / "metadata.json"),
            oracle_sha256=sha(oracle_path),
            coverage_sha256=sha(destination / "coverage.json"),
            groups={group: {k: v for k, v in report.items() if k != "rows"} for group, report in reports.items()},
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result["failure"] = str(error)
    (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result | {"evidence": str(destination)}, indent=2))
    if not result["success"]:
        raise RuntimeError("SDK metadata contract inspection failed; retain the original evidence")
