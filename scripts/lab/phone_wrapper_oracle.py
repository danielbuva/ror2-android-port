"""Isolated desktop verification oracle; never a phone/game build input."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from phone_registry import BINARY_SHA256

VERSION = "2021.3.45f2"
READER = "tools/phone-build/WrapperMetadataOracle.cs"
SOURCES = ("scripts/lab/phone_wrapper_oracle.py", READER)
MANIFEST = '{"dependencies":{"com.unity.modules.jsonserialize":"1.0.0"}}\n'
PROJECT_VERSION = "m_EditorVersion: " + VERSION + "\nm_EditorVersionWithRevision: " + VERSION + " (88f88f591b2e)\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(destination, root):
    """Generate a fresh SDK-only project. Earlier projects are never overwritten."""
    destination, root = Path(destination), Path(root)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "Assets/Editor").mkdir(parents=True)
    (destination / "Assets/Editor/WrapperMetadataOracle.cs").write_bytes((root / READER).read_bytes())
    (destination / "Packages").mkdir()
    (destination / "Packages/manifest.json").write_text(MANIFEST)
    (destination / "ProjectSettings").mkdir()
    (destination / "ProjectSettings/ProjectVersion.txt").write_text(PROJECT_VERSION)
    receipt = {
        "schema": 1,
        "unity": VERSION,
        "generator": SOURCES[0],
        "game_inputs": False,
        "root_generation_qualified": False,
        "sources": {name: sha(root / name) for name in SOURCES},
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    }
    (destination / "oracle-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def validate_project(project, root, work):
    project, root = Path(project).absolute(), Path(root)
    if project != project.resolve() or not project.is_relative_to((Path(work) / "rebuild/phone-wrapper-oracle").resolve()):
        raise ValueError("Select an owned isolated wrapper-oracle project")
    if project.is_symlink() or any(p.is_symlink() for p in project.rglob("*")):
        raise ValueError("Oracle project links are unsupported")
    receipt = json.loads((project / "oracle-inputs.json").read_text())
    if receipt.get("schema") != 1 or receipt.get("unity") != VERSION or set(receipt.get("sources", {})) != set(SOURCES):
        raise ValueError("Oracle input schema/source set differs")
    for name in SOURCES:
        if sha(root / name) != receipt["sources"][name]:
            raise ValueError("Oracle source drift: " + name)
    if (project / "Assets/Editor/WrapperMetadataOracle.cs").read_bytes() != (root / READER).read_bytes():
        raise ValueError("Staged oracle source drift")
    assets = {p.relative_to(project / "Assets").as_posix() for p in (project / "Assets").rglob("*") if p.is_file()}
    if not assets <= {"Editor.meta", "Editor/WrapperMetadataOracle.cs", "Editor/WrapperMetadataOracle.cs.meta"}:
        raise ValueError("Foreign oracle asset")
    if (project / "Packages/manifest.json").read_text() != MANIFEST or (project / "ProjectSettings/ProjectVersion.txt").read_text() != PROJECT_VERSION:
        raise ValueError("Oracle project configuration drift")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if commit != receipt.get("source_commit") or subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit current oracle sources and stage a new project")
    return receipt


def validate_report(report, commit):
    if (
        report.get("schema") != 1
        or report.get("unity") != VERSION
        or report.get("source_commit") != commit
        or report.get("queryProfile") != "concrete-object-descendants-v1"
        or report.get("root_generation_qualified") is not False
        or report.get("game_inputs") is not False
    ):
        raise ValueError("Exact-editor oracle identity/scope differs")
    rows = report["records"]
    by_id = {row["persistentTypeID"]: row for row in rows}
    if not rows or len(by_id) != len(rows) or len({row["qualifiedName"] for row in rows}) != len(rows):
        raise ValueError("Oracle has duplicate/incomplete identities")
    roots = [row for row in rows if row["name"] == "Object" and row["nativeNamespace"] == "" and row["hasParent"] is False]
    if len(roots) != 1:
        raise ValueError("Oracle native Object root differs")
    root = roots[0]
    for row in rows:
        ancestor, seen, descends = row, set(), False
        while ancestor["hasParent"]:
            identity = ancestor["persistentTypeID"]
            if identity in seen or ancestor["parentID"] not in by_id:
                raise ValueError("Oracle parent cycle or missing parent")
            seen.add(identity)
            ancestor = by_id[ancestor["parentID"]]
            descends |= ancestor is root
        reason = "native-object-root" if row is root else "outside-object-hierarchy" if not descends else "abstract" if row["flags"] & 1 else ""
        if row["skipReason"] != reason or row["wrapperQueried"] is not (not reason) or not isinstance(row["wrapperName"], str):
            raise ValueError("Oracle query coverage differs")
        if reason and (row["wrapperName"] or row["wrapperReturnedNull"]):
            raise ValueError("Unqueried wrapper has invented output")
    if not any(row["wrapperQueried"] for row in rows):
        raise ValueError("Oracle performed no supported query")


def run_editor(project, root, work):
    from build_lock import host_build_lock

    root, work, project = Path(root), Path(work), Path(project).absolute()
    receipt = validate_project(project, root, work)
    editor = Path(os.environ["UNITY_EDITOR"])
    if sha(editor) != BINARY_SHA256:
        raise ValueError("Exact owner SDK binary required")
    common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, text=True).strip())
    if common.name != ".git":
        raise ValueError("Cannot locate the primary checkout mutex")
    attempt = project.parent / ("editor-check-" + uuid.uuid4().hex)
    attempt.mkdir(exist_ok=False)
    output, log = attempt / "oracle.json", attempt / "editor.log"
    env = dict(os.environ, ROR2_WRAPPER_ORACLE_REPORT=str(output), ROR2_PHONE_BUILD_SOURCE=receipt["source_commit"])
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
        "WrapperMetadataOracle.Check",
        "-logFile",
        str(log),
    ]
    result, error, report = None, None, None
    try:
        with host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="Alpha SDK wrapper metadata oracle", timeout=1):
            result = subprocess.run(args, env=env, capture_output=True, timeout=300)
        (attempt / "launch.txt").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError("Exact-editor process failed")
        validate_project(project, root, work)
        if sha(editor) != BINARY_SHA256:
            raise ValueError("Owner SDK changed during oracle")
        report = json.loads(output.read_text())
        validate_report(report, receipt["source_commit"])
        contents = editor.resolve().parent.parent
        if not report.get("assemblies"):
            raise ValueError("Missing loaded SDK assembly evidence")
        for item in report["assemblies"]:
            path = Path(item["path"])
            if not path.resolve().is_relative_to(contents) or sha(path) != item["sha256"]:
                raise ValueError("Loaded SDK assembly identity drift")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
        error = str(failure)
    outcome = {
        "schema": 1,
        "success": error is None,
        "error": error,
        "exit_code": None if result is None else result.returncode,
        "source_commit": receipt["source_commit"],
        "inputs": receipt,
        "editor_sha256": BINARY_SHA256,
        "oracle_sha256": sha(output) if output.is_file() else None,
        "log": str(log),
        "root_generation_qualified": False,
    }
    (attempt / "receipt.json").write_text(json.dumps(outcome, indent=2) + "\n")
    if error:
        raise RuntimeError("Oracle refused; inspect retained attempt: " + str(attempt))
    return {
        "attempt": str(attempt),
        "receipt_sha256": sha(attempt / "receipt.json"),
        "records": len(report["records"]),
        "queried": sum(r["wrapperQueried"] for r in report["records"]),
        **outcome,
    }


def stage_action(request_path):
    from common import ROOT, WORK

    request = json.loads(Path(request_path).read_text())
    if request == {"operation": "stage"}:
        project = WORK / "rebuild/phone-wrapper-oracle" / uuid.uuid4().hex / "project"
        result = {"project": str(project), **stage(project, ROOT)}
    elif set(request) == {"operation", "project"} and request["operation"] == "check":
        result = run_editor(request["project"], ROOT, WORK)
    else:
        raise ValueError("Select stage or check with an explicit isolated project")
    print(json.dumps(result, indent=2))
