"""SDK-only population verification; isolated project, existing shared mutex."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def support(name):
    spec = importlib.util.spec_from_file_location("_population_oracle_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = support("phone_wrapper_oracle")
SOURCES = ("scripts/lab/phone_wrapper_population_oracle.py", "tools/phone-build/WrapperPopulationOracle.cs", *base.SOURCES)
ASSETS = ("WrapperPopulationOracle.cs", "WrapperMetadataOracle.cs")


def validate_report(report, commit):
    if report.get("queryProfile") != "all-object-descendants-v1" or report.get("cache_population_qualified") is not False:
        raise ValueError("Population oracle scope differs")
    # Reuse the established complete graph/coverage validation after restoring
    # the old profile's abstract exclusions in a separate copy.
    copied = json.loads(json.dumps(report))
    copied["queryProfile"] = "concrete-object-descendants-v1"
    count = 0
    for row in copied["records"]:
        if row["wrapperQueried"] and row["flags"] & 1:
            count += 1
            if row["skipReason"] or row["wrapperReturnedNull"] or not row["wrapperName"]:
                raise ValueError("Abstract native query has no observed wrapper")
            row.update(wrapperQueried=False, wrapperReturnedNull=False, wrapperName="", skipReason="abstract")
    base.validate_report(copied, commit)
    if count != 27 or sum(row["wrapperQueried"] for row in report["records"]) != 305:
        raise ValueError("Pinned population oracle query coverage differs")


def run(root, work, editor):
    root, work, editor = Path(root).absolute(), Path(work).absolute(), Path(editor).absolute()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit oracle sources before staging")
    if base.sha(editor) != base.BINARY_SHA256:
        raise ValueError("Unknown owner SDK")
    sources = {name: base.sha(root / name) for name in SOURCES}
    destination = work / "rebuild/phone-wrapper-population" / uuid.uuid4().hex
    project = destination / "project"
    base.owned_destination(project, work)
    with base.owned_directory(project, work, create=True, new=True):
        pass
    for name in ("Assets/Editor", "Packages", "ProjectSettings"):
        with base.owned_directory(project / name, work, create=True):
            pass
    authored = {"Assets/Editor/" + name: (root / "tools/phone-build" / name).read_bytes() for name in ASSETS}
    authored.update({"Packages/manifest.json": base.MANIFEST.encode(), "ProjectSettings/ProjectVersion.txt": base.PROJECT_VERSION.encode()})
    for name, data in authored.items():
        base.write_owned(project / name, data, work)
    inputs = {"source_commit": commit, "sources": sources, "editor_sha256": base.BINARY_SHA256, "game_inputs": False}
    base.write_owned(destination / "inputs.json", (json.dumps(inputs, indent=2) + "\n").encode(), work)

    def validate():
        base.owned_destination(project, work)
        if any(path.is_symlink() for path in project.rglob("*")):
            raise ValueError("Population project links are unsupported")
        for name, data in authored.items():
            if (project / name).read_bytes() != data:
                raise ValueError("Population project input drift")
        allowed = {"Editor.meta", *("Editor/" + name for name in ASSETS), *("Editor/" + name + ".meta" for name in ASSETS)}
        if not {p.relative_to(project / "Assets").as_posix() for p in (project / "Assets").rglob("*") if p.is_file()} <= allowed:
            raise ValueError("Foreign population oracle asset")
        if any(base.sha(root / name) != value for name, value in sources.items()) or base.sha(editor) != base.BINARY_SHA256:
            raise ValueError("Population source or SDK drift")

    validate()
    output, log = destination / "oracle.json", destination / "editor.log"
    env = dict(os.environ, ROR2_POPULATION_ORACLE_REPORT=str(output), ROR2_PHONE_BUILD_SOURCE=commit)
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
        "WrapperPopulationOracle.Check",
        "-logFile",
        str(log),
    ]
    common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, text=True).strip())
    if common.name != ".git":
        raise ValueError("Cannot locate primary build mutex")
    lock = support("build_lock")
    result, error, report = None, None, None
    try:
        with lock.host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="Alpha SDK population oracle", timeout=1):
            result = subprocess.run(args, env=env, capture_output=True, timeout=300)
        base.write_owned(destination / "launch.txt", result.stdout + result.stderr, work)
        validate()
        if result.returncode:
            raise ValueError("Population SDK batch failed")
        report = json.loads(output.read_text())
        validate_report(report, commit)
        if not report.get("assemblies"):
            raise ValueError("Missing population SDK assembly evidence")
        for assembly in report["assemblies"]:
            path = Path(assembly["path"])
            if not path.resolve().is_relative_to(editor.resolve().parent.parent) or base.sha(path) != assembly["sha256"]:
                raise ValueError("Loaded population SDK assembly drift")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
        error = str(failure)
    receipt = {
        **inputs,
        "success": error is None,
        "error": error,
        "exit_code": None if result is None else result.returncode,
        "oracle_sha256": base.sha(output) if output.is_file() else None,
        "cache_population_qualified": False,
        "root_generation_qualified": False,
    }
    base.write_owned(destination / "receipt.json", (json.dumps(receipt, indent=2) + "\n").encode(), work)
    return destination, receipt


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: phone_wrapper_population_oracle.py ROOT WORK EXACT_EDITOR")
    destination, receipt = run(*sys.argv[1:])
    print(json.dumps({"evidence": str(destination), **receipt}))
    raise SystemExit(not receipt["success"])
