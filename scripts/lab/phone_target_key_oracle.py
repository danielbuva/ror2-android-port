"""Current experimental SDK name-API observations; never phone-generation input."""

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from build_lock import host_build_lock
import phone_target_keys as keys
import phone_wrapper_oracle as guard

COLLECTOR = "tools/phone-build/TargetKeyOracle.cs"
SOURCES = tuple(
    sorted(
        {
            "scripts/lab/phone_target_key_oracle.py",
            "scripts/lab/phone_wrapper_oracle.py",
            "scripts/lab/build_lock.py",
            COLLECTOR,
            *("scripts/lab/" + name for name in keys.SOURCES),
        }
    )
)
MANIFEST = '{"dependencies":{"com.unity.modules.jsonserialize":"1.0.0"}}\n'


def queries(report):
    if (
        report.get("profile") != "native-target-key-inputs-v1"
        or report.get("source_argument_slots_complete") is not True
        or report.get("root_generation_qualified") is not False
    ):
        raise ValueError("Unknown target-key input profile")
    values = report["rows"]
    if not values or any(type(row.get("key")) is not int or not isinstance(row.get("label"), str) for row in values):
        raise ValueError("Unknown target-key input row")
    return dict(schema=1, keys=sorted({row["key"] for row in values}), names=sorted({keys.label_token(row["label"]) for row in values}))


def stage(root, work, editor):
    root, work, editor = (Path(value).absolute() for value in (root, work, editor))
    if guard.sha(editor) != guard.BINARY_SHA256:
        raise ValueError("Exact owner SDK required")
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit reader/oracle sources before staging")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    destination = work / "rebuild/phone-wrapper-oracle" / ("target-" + uuid.uuid4().hex)
    project = destination / "project"
    with guard.owned_directory(project, work, create=True, new=True):
        pass
    for name in ("Assets/Editor", "Packages", "ProjectSettings"):
        with guard.owned_directory(project / name, work, create=True):
            pass
    report = keys.inspect(editor, destination / "inputs-metadata.json")
    request = queries(report)
    guard.write_owned(destination / "queries.json", (json.dumps(request, indent=2) + "\n").encode(), work)
    authored = {
        "Assets/Editor/TargetKeyOracle.cs": (root / COLLECTOR).read_bytes(),
        "Packages/manifest.json": MANIFEST.encode(),
        "ProjectSettings/ProjectVersion.txt": guard.PROJECT_VERSION.encode(),
    }
    for name, data in authored.items():
        guard.write_owned(project / name, data, work)
    inputs = dict(
        schema=1,
        source_commit=commit,
        sources={name: guard.sha(root / name) for name in SOURCES},
        authored={name: guard.sha(project / name) for name in authored},
        editor_sha256=guard.BINARY_SHA256,
        metadata_sha256=guard.sha(destination / "inputs-metadata.json"),
        request_sha256=guard.sha(destination / "queries.json"),
        game_inputs=False,
        player_built=False,
        phone_generation_input=False,
        root_generation_qualified=False,
    )
    guard.write_owned(destination / "inputs.json", (json.dumps(inputs, indent=2) + "\n").encode(), work)
    return destination, inputs


def validate_project(root, work, editor, destination, inputs):
    guard.owned_destination(destination / "project", work)
    if any(path.is_symlink() for path in destination.rglob("*")):
        raise ValueError("Oracle links are unsupported")
    for name, digest in inputs["sources"].items():
        if guard.sha(root / name) != digest:
            raise ValueError("Target-key oracle source changed")
    for name, digest in inputs["authored"].items():
        if guard.sha(destination / "project" / name) != digest:
            raise ValueError("Target-key oracle authored input changed")
    for name, key in (("inputs-metadata.json", "metadata_sha256"), ("queries.json", "request_sha256")):
        if guard.sha(destination / name) != inputs[key]:
            raise ValueError("Target-key oracle request/data changed")
    allowed = {"Editor.meta", "Editor/TargetKeyOracle.cs", "Editor/TargetKeyOracle.cs.meta"}
    if not {str(path.relative_to(destination / "project/Assets")) for path in (destination / "project/Assets").rglob("*") if path.is_file()} <= allowed:
        raise ValueError("Foreign target-key oracle asset")
    if not {path.name for path in (destination / "project/Packages").iterdir()} <= {"manifest.json", "packages-lock.json"}:
        raise ValueError("Foreign target-key oracle package")
    if guard.sha(editor) != inputs["editor_sha256"]:
        raise ValueError("Target-key oracle SDK changed")


def observations(report, inputs, request):
    if (
        report.get("schema") != 1
        or report.get("profile") != "target-key-api-observations-v1"
        or report.get("unity") != guard.VERSION
        or report.get("source_commit") != inputs["source_commit"]
        or report.get("success") is not True
        or report.get("phase") != "complete"
        or report.get("failure")
    ):
        raise ValueError("Target-key SDK observations did not complete with exact identity")
    if (
        any(report.get(key) is not False for key in ("game_inputs", "player_built", "phone_generation_input", "root_generation_qualified"))
        or report.get("request_sha256") != inputs["request_sha256"]
    ):
        raise ValueError("Target-key oracle scope/request differs")
    if [row.get("key") for row in report["keys"]] != request["keys"] or [row.get("name") for row in report["names"]] != request["names"]:
        raise ValueError("Missing or reordered SDK query observations")
    if any(type(row.get("key")) is not int or row.get("value") is not None and not isinstance(row.get("value"), str) for row in report["keys"]):
        raise ValueError("Unknown key observation type")
    if any(type(row.get("value")) is not int or type(row.get("returned")) is not bool for row in report["names"]):
        raise ValueError("Unknown name observation type")


def compare(report, metadata):
    """Record mismatches without converting SDK display names into input keys."""
    key_rows = {row["key"]: row for row in report["keys"]}
    name_rows = {row["name"]: row for row in report["names"]}
    results = []
    for row in metadata["rows"]:
        key, name = row["key"], row["label"]
        forward, reverse = key_rows[key], name_rows[name]
        forward_ok = not forward.get("error") and forward.get("value") == name
        reverse_ok = not reverse.get("error") and reverse.get("returned") is True and reverse["value"] == key
        results.append(
            dict(
                key=key,
                label=name,
                key_name_exact=bool(forward_ok),
                name_key_exact=bool(reverse_ok),
                observed_name=forward.get("value"),
                key_error=forward.get("error"),
                observed_key=reverse.get("value"),
                name_error=reverse.get("error"),
            )
        )
    return dict(
        rows=results,
        key_name_exact_count=sum(row["key_name_exact"] for row in results),
        name_key_exact_count=sum(row["name_key_exact"] for row in results),
        all_exact=all(row["key_name_exact"] and row["name_key_exact"] for row in results),
        root_generation_qualified=False,
    )


def run(root, work, editor):
    root, work, editor = (Path(value).absolute() for value in (root, work, editor))
    destination, inputs = stage(root, work, editor)
    common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, text=True).strip())
    if common.name != ".git":
        raise ValueError("Cannot locate primary Unity mutex")
    output = destination / "oracle.json"
    env = dict(
        os.environ,
        ROR2_TARGET_KEY_REPORT=str(output),
        ROR2_TARGET_KEY_REQUEST=str(destination / "queries.json"),
        ROR2_PHONE_BUILD_SOURCE=inputs["source_commit"],
    )
    args = [
        str(editor),
        "-batchmode",
        "-nographics",
        "-quit",
        "-projectPath",
        str(destination / "project"),
        "-buildTarget",
        "Android",
        "-executeMethod",
        "TargetKeyOracle.Check",
        "-logFile",
        str(destination / "editor.log"),
    ]
    process, error, comparison = None, None, None
    try:
        with host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="Alpha SDK target-key API observations", timeout=1):
            validate_project(root, work, editor, destination, inputs)
            process = subprocess.run(args, env=env, capture_output=True, timeout=360)
        guard.write_owned(destination / "launch.txt", process.stdout + process.stderr, work)
        validate_project(root, work, editor, destination, inputs)
        if process.returncode:
            raise ValueError("Target-key SDK process failed")
        report = json.loads(output.read_text())
        observations(report, inputs, json.loads((destination / "queries.json").read_text()))
        for name, owner in (("api_assembly", editor.resolve().parent.parent), ("collector_assembly", destination / "project")):
            row = report[name]
            path = Path(row["path"]).resolve()
            if not path.is_relative_to(owner.resolve()) or guard.sha(path) != row["sha256"]:
                raise ValueError("Observed target-key SDK/collector assembly differs")
        comparison = compare(report, json.loads((destination / "inputs-metadata.json").read_text()))
        guard.write_owned(destination / "comparison.json", (json.dumps(comparison, indent=2) + "\n").encode(), work)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as failure:
        error = str(failure)
    result = dict(
        **inputs,
        observation_success=error is None,
        error=error,
        exit_code=None if process is None else process.returncode,
        oracle_sha256=guard.sha(output) if output.is_file() else None,
        comparison_all_exact=None if comparison is None else comparison["all_exact"],
    )
    guard.write_owned(destination / "receipt.json", (json.dumps(result, indent=2) + "\n").encode(), work)
    return destination, result


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: phone_target_key_oracle.py ROOT WORK EXACT_EDITOR (desktop observations only; inspect comparison separately)")
    destination, result = run(*sys.argv[1:])
    print(json.dumps({"evidence": str(destination), **result}))
    raise SystemExit(0 if result["observation_success"] else 1)
