"""Observe authored scene/manager dependencies in a fresh desktop SDK process.

Reports are verification evidence, never phone-build or linker inputs.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import phone_wrapper_oracle as guard
from build_lock import host_build_lock

SOURCES = (
    "scripts/lab/phone_scene_usage_oracle.py",
    "scripts/lab/phone_wrapper_oracle.py",
    "scripts/lab/phone_registry.py",
    "scripts/lab/build_lock.py",
    "tools/phone-build/SceneUsageOracle.cs",
    "tools/phone-build/ContentFixture.cs",
)
MANIFEST = (
    json.dumps(
        {"dependencies": {"com.unity.modules." + name: "1.0.0" for name in ("androidjni", "assetbundle", "jsonserialize", "unitywebrequest")}},
        separators=(",", ":"),
    )
    + "\n"
)
GROUPS = {"scene_references", "scene_usage", "manager_objects", "manager_references", "manager_usage"}


def stage(root, work, editor):
    root, work, editor = (Path(p).absolute() for p in (root, work, editor))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit scene usage oracle sources before staging")
    if guard.sha(editor) != guard.BINARY_SHA256:
        raise ValueError("Exact owner SDK binary required")
    destination = work / "rebuild/phone-wrapper-oracle" / ("scene-" + uuid.uuid4().hex)
    project = destination / "project"
    with guard.owned_directory(project, work, create=True, new=True):
        pass
    for name in ("Assets/Editor", "Packages", "ProjectSettings"):
        with guard.owned_directory(project / name, work, create=True):
            pass
    authored = {
        "Assets/Editor/SceneUsageOracle.cs": (root / "tools/phone-build/SceneUsageOracle.cs").read_bytes(),
        "Assets/ContentFixture.cs": (root / "tools/phone-build/ContentFixture.cs").read_bytes(),
        "Packages/manifest.json": MANIFEST.encode(),
        "ProjectSettings/ProjectVersion.txt": guard.PROJECT_VERSION.encode(),
    }
    for name, data in authored.items():
        guard.write_owned(project / name, data, work)
    inputs = {
        "schema": 1,
        "generator": SOURCES[0],
        "source_commit": commit,
        "sources": {name: guard.sha(root / name) for name in SOURCES},
        "authored": {name: guard.sha(project / name) for name in authored},
        "editor_sha256": guard.BINARY_SHA256,
        "game_inputs": False,
        "root_generation_qualified": False,
    }
    guard.write_owned(destination / "inputs.json", (json.dumps(inputs, indent=2) + "\n").encode(), work)
    return destination, inputs


def validate_project(destination, root, work, inputs, editor):
    project = destination / "project"
    guard.owned_destination(project, work)
    if any(p.is_symlink() for p in destination.rglob("*")):
        raise ValueError("Scene oracle links are unsupported")
    for name, digest in inputs["sources"].items():
        if guard.sha(root / name) != digest:
            raise ValueError("Scene oracle source drift")
    for name, digest in inputs["authored"].items():
        if guard.sha(project / name) != digest:
            raise ValueError("Scene oracle project input drift")
    allowed = {
        "Editor.meta",
        "Fixture.unity",
        "Fixture.unity.meta",
        "ContentFixture.cs",
        "ContentFixture.cs.meta",
        "Editor/SceneUsageOracle.cs",
        "Editor/SceneUsageOracle.cs.meta",
    }
    if not {p.relative_to(project / "Assets").as_posix() for p in (project / "Assets").rglob("*") if p.is_file()} <= allowed:
        raise ValueError("Foreign scene oracle asset")
    if guard.sha(editor) != inputs["editor_sha256"]:
        raise ValueError("Scene oracle SDK drift")


def type_rows(rows):
    if not isinstance(rows, list):
        raise ValueError("Missing observed type list")
    keys = []
    for row in rows:
        if set(row) != {"assembly", "name"} or not all(isinstance(row[k], str) and row[k] for k in row):
            raise ValueError("Incomplete observed type identity")
        keys.append((row["assembly"], row["name"]))
    if len(set(keys)) != len(keys):
        raise ValueError("Repeated observed type identity")
    return keys


def validate_report(report, inputs, destination, editor):
    if (
        report.get("schema") != 1
        or report.get("unity") != guard.VERSION
        or report.get("source_commit") != inputs["source_commit"]
        or report.get("profile") != "authored-default-scene-dependencies-v1"
        or report.get("phase") != "complete"
        or report.get("failure")
        or any(report.get(key) is not False for key in ("game_inputs", "player_built", "root_generation_qualified"))
    ):
        raise ValueError("Scene usage oracle identity/completion/scope differs")
    settings = report["settings"]
    expected = dict(
        target="Android",
        group="Android",
        backend="IL2CPP",
        architecture="ARM64",
        stripping="Low",
        graphics=["Vulkan"],
        strip_engine=False,
        script_options=3,
        content_flags=4,
    )
    if any(settings.get(k) != v for k, v in expected.items()) or not settings.get("api"):
        raise ValueError("Scene usage oracle build settings differ")
    project = destination / "project"
    if report.get("scene") != "Assets/Fixture.unity" or guard.sha(project / "Assets/Fixture.unity") != report.get("scene_sha256"):
        raise ValueError("Authored oracle scene identity differs")
    if not re.fullmatch("[0-9a-f]{32}", report.get("type_db_hash", "")):
        raise ValueError("Missing compiled type database identity")
    for name, bounds in (
        ("compiled_assemblies", [destination / "player-scripts"]),
        ("loaded_assemblies", [editor.resolve().parent.parent, project / "Library/ScriptAssemblies"]),
    ):
        rows = report.get(name)
        if not isinstance(rows, list) or not rows or len({r["path"] for r in rows}) != len(rows):
            raise ValueError("Missing or repeated oracle assembly evidence")
        for row in rows:
            path = Path(row["path"])
            if not path.is_absolute() or path != path.resolve() or not any(path.is_relative_to(b) for b in bounds) or guard.sha(path) != row["sha256"]:
                raise ValueError("Observed oracle assembly drift or scope differs")
    type_rows(report["scene_types"])
    type_rows(report["manager_types"])
    groups = report["groups"]
    if len(groups) != len(GROUPS) or {row["name"] for row in groups} != GROUPS:
        raise ValueError("Missing or repeated scene/manager observation group")
    live = report["loaded_scene"]
    if not live or len({row["instance_id"] for row in live}) != len(live):
        raise ValueError("Missing or repeated live scene object")
    for row in live:
        if type(row["instance_id"]) is not int or not row["instance_id"] or not isinstance(row["name"], str):
            raise ValueError("Incomplete live scene identity")
        if type(row["supported"]) is not bool or type(row["identifier_available"]) is not bool:
            raise ValueError("Unknown live scene observation state")
        if len(type_rows(row["types"])) != 1 or len(row["identifiers"]) != int(row["identifier_available"]):
            raise ValueError("Invented live scene type or asset identifier")
    for group in [*groups, *(dict(objects=row["identifiers"]) for row in live)]:
        keys = []
        for row in group["objects"]:
            if (
                not re.fullmatch("[0-9a-f]{32}", row["guid"])
                or type(row["local_id"]) is not int
                or type(row["file_type"]) is not int
                or row["file_type"] not in range(4)
                or not isinstance(row["file_path"], str)
            ):
                raise ValueError("Incomplete object identifier")
            keys.append((row["guid"], row["local_id"], row["file_type"], row["file_path"]))
            if any(type(row[key]) is not bool for key in ("resolved", "support_queried", "supported", "types_returned_null")):
                raise ValueError("Unknown object observation state")
            if row["support_queried"] != row["resolved"] or (not row["support_queried"] and row["supported"]):
                raise ValueError("Invented object support result")
            loaded = type_rows(row["loaded_types"])
            types = type_rows(row["types"])
            if len(loaded) != int(row["resolved"]) or (row["types_returned_null"] and types):
                raise ValueError("Invented object type result")
        if len(set(keys)) != len(keys):
            raise ValueError("Repeated object identifier in an observation group")
    usage = report["global_usage"]
    if len(usage) != 3 or {row["name"] for row in usage} != {"scene", "graphics", "managers"}:
        raise ValueError("Missing global usage observation")
    layouts = []
    for row in usage:
        fields = row["fields"]
        if not fields or len({v["name"] for v in fields}) != len(fields) or any(not isinstance(v["value"], str) for v in fields):
            raise ValueError("Incomplete global usage fields")
        layouts.append({v["name"] for v in fields})
    if any(value != layouts[0] for value in layouts):
        raise ValueError("Global usage layouts differ")


def run(root, work, editor):
    root, work, editor = (Path(p).absolute() for p in (root, work, editor))
    destination, inputs = stage(root, work, editor)
    project = destination / "project"
    validate_project(destination, root, work, inputs, editor)
    common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, text=True).strip())
    if common.name != ".git":
        raise ValueError("Cannot locate primary Unity build mutex")
    output, log = destination / "oracle.json", destination / "editor.log"
    env = dict(os.environ, ROR2_SCENE_USAGE_REPORT=str(output), ROR2_PHONE_BUILD_SOURCE=inputs["source_commit"])
    args = [
        str(editor),
        "-batchmode",
        "-nographics",
        "-quit",
        "-projectPath",
        str(project),
        "-buildTarget",
        "Android",
        "-executeMethod",
        "SceneUsageOracle.Check",
        "-logFile",
        str(log),
    ]
    result, error = None, None
    try:
        with host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="Alpha SDK scene/manager usage oracle", timeout=1):
            validate_project(destination, root, work, inputs, editor)
            result = subprocess.run(args, env=env, capture_output=True, timeout=600)
        guard.write_owned(destination / "launch.txt", result.stdout + result.stderr, work)
        validate_project(destination, root, work, inputs, editor)
        if result.returncode:
            raise ValueError("Scene usage SDK batch failed; inspect retained report/log")
        validate_report(json.loads(output.read_text()), inputs, destination, editor)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as failure:
        error = str(failure)
    receipt = {
        **inputs,
        "success": error is None,
        "error": error,
        "exit_code": None if result is None else result.returncode,
        "oracle_sha256": guard.sha(output) if output.is_file() else None,
        "scene_sha256": guard.sha(project / "Assets/Fixture.unity") if (project / "Assets/Fixture.unity").is_file() else None,
    }
    guard.write_owned(destination / "receipt.json", (json.dumps(receipt, indent=2) + "\n").encode(), work)
    return destination, receipt


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: phone_scene_usage_oracle.py ROOT WORK EXACT_EDITOR (desktop verification only)")
    destination, receipt = run(*sys.argv[1:])
    print(json.dumps({"evidence": str(destination), **receipt}))
    raise SystemExit(0 if receipt["success"] else 1)
