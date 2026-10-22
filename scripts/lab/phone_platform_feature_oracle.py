"""Current experimental desktop SDK verification; never a phone-generation input."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import phone_platform_features as features
import phone_wrapper_oracle as guard
from build_lock import host_build_lock

SOURCES = tuple(
    sorted(
        {
            "scripts/lab/phone_platform_feature_oracle.py",
            "scripts/lab/phone_wrapper_oracle.py",
            "scripts/lab/build_lock.py",
            "tools/phone-build/PlatformFeatureOracle.cs",
            *("scripts/lab/" + name for name in features.SOURCES),
        }
    )
)
MANIFEST = json.dumps({"dependencies": {"com.unity.modules.jsonserialize": "1.0.0"}}, separators=(",", ":")) + "\n"
PROBES = ("ENABLE_MOVIES", "ENABLE_CLOTH", "ENABLE_AUDIO", "ENABLE_PHYSICS", "ENABLE_CLUSTERINPUT", "AUTHORED_UNKNOWN_FEATURE")


def query_features(report):
    if (
        report.get("profile") != "android-platform-feature-declarations-v1"
        or report.get("platform_define") != "PLATFORM_ANDROID"
        or report.get("root_generation_qualified") is not False
    ):
        raise ValueError("Unknown Android declaration profile")
    values = [row["feature"] for row in report["declarations"]]
    if not values or any(not isinstance(value, str) or len(value) > 128 or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value) for value in values):
        raise ValueError("Unknown feature query token")
    return sorted(set(values) | set(PROBES))


def stage(root, work, editor):
    root, work, editor = (Path(value).absolute() for value in (root, work, editor))
    if guard.sha(editor) != guard.BINARY_SHA256:
        raise ValueError("Exact owner SDK binary required")
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit feature reader/oracle sources before staging")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    destination = work / "rebuild/phone-platform-feature-oracle" / uuid.uuid4().hex
    project = destination / "project"
    with guard.owned_directory(project, work, create=True, new=True):
        pass
    for name in ("Assets/Editor", "Packages", "ProjectSettings"):
        with guard.owned_directory(project / name, work, create=True):
            pass
    declaration = features.inspect(editor, destination / "declarations.json")
    queries = {"schema": 1, "features": query_features(declaration)}
    guard.write_owned(destination / "queries.json", (json.dumps(queries, indent=2) + "\n").encode(), work)
    authored = {
        "Assets/Editor/PlatformFeatureOracle.cs": (root / "tools/phone-build/PlatformFeatureOracle.cs").read_bytes(),
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
        declaration_sha256=guard.sha(destination / "declarations.json"),
        query_sha256=guard.sha(destination / "queries.json"),
        phone_generation_input=False,
        game_inputs=False,
        player_built=False,
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
            raise ValueError("Feature oracle source drift")
    for name, digest in inputs["authored"].items():
        if guard.sha(destination / "project" / name) != digest:
            raise ValueError("Feature oracle authored input drift")
    for name, key in (("queries.json", "query_sha256"), ("declarations.json", "declaration_sha256")):
        if guard.sha(destination / name) != inputs[key]:
            raise ValueError("Feature oracle data drift")
    allowed = {"Editor.meta", "Editor/PlatformFeatureOracle.cs", "Editor/PlatformFeatureOracle.cs.meta"}
    if not {str(path.relative_to(destination / "project/Assets")) for path in (destination / "project/Assets").rglob("*") if path.is_file()} <= allowed:
        raise ValueError("Foreign oracle asset")
    if not {path.name for path in (destination / "project/Packages").iterdir()} <= {"manifest.json", "packages-lock.json"}:
        raise ValueError("Foreign oracle package input")
    if guard.sha(editor) != inputs["editor_sha256"]:
        raise ValueError("Feature oracle SDK drift")


def validate_report(report, inputs, declaration, queries):
    if (
        report.get("schema") != 1
        or report.get("profile") != "android-feature-api-oracle-v1"
        or report.get("unity") != guard.VERSION
        or report.get("source_commit") != inputs["source_commit"]
        or report.get("success") is not True
        or report.get("phase") != "complete"
        or report.get("failure")
    ):
        raise ValueError("Feature API oracle identity or completion differs")
    if any(report.get(key) is not False for key in ("game_inputs", "player_built", "phone_generation_input", "root_generation_qualified")):
        raise ValueError("Feature oracle scope differs")
    if (report.get("target"), report.get("target_value"), report.get("platform_define")) != ("Android", 19, "PLATFORM_ANDROID") or report.get(
        "query_sha256"
    ) != inputs["query_sha256"]:
        raise ValueError("Android API/query identity differs")
    names = [row.get("feature") for row in report["rows"]]
    if names != queries["features"] or any(type(row.get("supported")) is not bool for row in report["rows"]):
        raise ValueError("Missing, reordered or nonboolean API observations")
    expected = {row["feature"] for row in declaration["declarations"]}
    if any(row["supported"] != (row["feature"] in expected) for row in report["rows"]):
        raise ValueError("SDK API and independently decoded declarations disagree")


def run(root, work, editor):
    root, work, editor = (Path(value).absolute() for value in (root, work, editor))
    destination, inputs = stage(root, work, editor)
    common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, text=True).strip())
    if common.name != ".git":
        raise ValueError("Cannot locate the primary Unity mutex")
    output, log = destination / "oracle.json", destination / "editor.log"
    env = dict(
        os.environ,
        ROR2_FEATURE_ORACLE_REPORT=str(output),
        ROR2_FEATURE_ORACLE_QUERIES=str(destination / "queries.json"),
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
        "PlatformFeatureOracle.Check",
        "-logFile",
        str(log),
    ]
    process, error = None, None
    try:
        with host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="Alpha SDK Android feature API oracle", timeout=1):
            validate_project(root, work, editor, destination, inputs)
            process = subprocess.run(args, env=env, capture_output=True, timeout=360)
        guard.write_owned(destination / "launch.txt", process.stdout + process.stderr, work)
        validate_project(root, work, editor, destination, inputs)
        if process.returncode:
            raise ValueError("Feature API SDK process failed")
        report = json.loads(output.read_text())
        validate_report(report, inputs, json.loads((destination / "declarations.json").read_text()), json.loads((destination / "queries.json").read_text()))
        sdk_root = editor.resolve().parent.parent
        for name, owner in (("api_assembly", sdk_root), ("collector_assembly", destination / "project")):
            row = report[name]
            path = Path(row["path"]).resolve()
            if not path.is_relative_to(owner.resolve()) or guard.sha(path) != row["sha256"]:
                raise ValueError("Observed SDK/collector assembly provenance differs")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as failure:
        error = str(failure)
    result = dict(
        **inputs,
        success=error is None,
        error=error,
        exit_code=None if process is None else process.returncode,
        oracle_sha256=guard.sha(output) if output.is_file() else None,
    )
    guard.write_owned(destination / "receipt.json", (json.dumps(result, indent=2) + "\n").encode(), work)
    return destination, result


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: phone_platform_feature_oracle.py ROOT WORK EXACT_EDITOR (desktop verification only)")
    destination, result = run(*sys.argv[1:])
    print(json.dumps({"evidence": str(destination), **result}))
    raise SystemExit(0 if result["success"] else 1)
