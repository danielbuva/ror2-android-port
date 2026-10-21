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
observer = support("phone_wrapper_reverse")
SOURCES = tuple(
    dict.fromkeys(
        (
            "scripts/lab/phone_wrapper_population_oracle.py",
            "tools/phone-build/WrapperPopulationOracle.cs",
            *base.SOURCES,
            "scripts/lab/build_lock.py",
            "tools/phone-build/WrapperReverseOracle.cs",
            *observer.SOURCES,
        )
    )
)
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


def run(root, work, editor, *, reverse=False):
    root, work, editor = Path(root).absolute(), Path(work).absolute(), Path(editor).absolute()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit oracle sources before staging")
    if base.sha(editor) != base.BINARY_SHA256:
        raise ValueError("Unknown owner SDK")
    sources = {name: base.sha(root / name) for name in SOURCES}
    mono = editor.parent.parent / "Frameworks/MonoBleedingEdge/MonoEmbedRuntime/osx/libmonobdwgc-2.0.dylib"
    layout_bytes = None
    if reverse:
        if base.sha(mono) != observer.MONO_SHA256:
            raise ValueError("Unknown existing SDK Mono library")
        layout_bytes = (json.dumps(observer.layout(observer.registry.MachO(editor.read_bytes())), indent=2) + "\n").encode()
    destination = work / "rebuild/phone-wrapper-oracle" / ("population-" + uuid.uuid4().hex)
    project = destination / "project"
    base.owned_destination(project, work)
    with base.owned_directory(project, work, create=True, new=True):
        pass
    for name in ("Assets/Editor", "Packages", "ProjectSettings"):
        with base.owned_directory(project / name, work, create=True):
            pass
    assets = (*ASSETS, "WrapperReverseOracle.cs") if reverse else ASSETS
    authored = {"Assets/Editor/" + name: (root / "tools/phone-build" / name).read_bytes() for name in assets}
    authored.update({"Packages/manifest.json": base.MANIFEST.encode(), "ProjectSettings/ProjectVersion.txt": base.PROJECT_VERSION.encode()})
    for name, data in authored.items():
        base.write_owned(project / name, data, work)
    inputs = {"schema": 1, "generator": SOURCES[0], "source_commit": commit, "sources": sources, "editor_sha256": base.BINARY_SHA256, "game_inputs": False}
    if reverse:
        base.write_owned(destination / "layout.json", layout_bytes, work)
        inputs.update(reverse_observer=True, layout_sha256=base.sha(destination / "layout.json"), mono_sha256=observer.MONO_SHA256)
    base.write_owned(destination / "inputs.json", (json.dumps(inputs, indent=2) + "\n").encode(), work)

    def validate():
        base.owned_destination(project, work)
        if any(path.is_symlink() for path in project.rglob("*")):
            raise ValueError("Population project links are unsupported")
        for name, data in authored.items():
            if (project / name).read_bytes() != data:
                raise ValueError("Population project input drift")
        allowed = {"Editor.meta", *("Editor/" + name for name in assets), *("Editor/" + name + ".meta" for name in assets)}
        if not {p.relative_to(project / "Assets").as_posix() for p in (project / "Assets").rglob("*") if p.is_file()} <= allowed:
            raise ValueError("Foreign population oracle asset")
        if any(base.sha(root / name) != value for name, value in sources.items()) or base.sha(editor) != base.BINARY_SHA256:
            raise ValueError("Population source or SDK drift")
        if reverse and ((destination / "layout.json").read_bytes() != layout_bytes or base.sha(mono) != observer.MONO_SHA256):
            raise ValueError("Reverse layout or existing runtime drift")

    validate()
    output, log = destination / "oracle.json", destination / "editor.log"
    env = dict(os.environ, ROR2_POPULATION_ORACLE_REPORT=str(output), ROR2_PHONE_BUILD_SOURCE=commit)
    if reverse:
        env.update(ROR2_REVERSE_ORACLE_LAYOUT=str(destination / "layout.json"), ROR2_REVERSE_ORACLE_EDITOR=str(editor), ROR2_REVERSE_ORACLE_MONO=str(mono))
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
        "WrapperReverseOracle.Check" if reverse else "WrapperPopulationOracle.Check",
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
        if reverse:
            validate_reverse(report, inputs, editor)
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


def validate_reverse(report, inputs, editor):
    if any(report.get(name) is not True for name in ("self_process_only", "existing_runtime_only", "stable_snapshot")):
        raise ValueError("Reverse observation scope or stability differs")
    if report.get("layout_sha256") != inputs["layout_sha256"] or report.get("mono_sha256") != observer.MONO_SHA256:
        raise ValueError("Reverse layout/runtime identity differs")
    contents = Path(editor).resolve().parent.parent
    mono = Path(report["mono_path"])
    if not mono.resolve().is_relative_to(contents) or base.sha(mono) != observer.MONO_SHA256:
        raise ValueError("Observed runtime identity differs")
    rows = report["reverse"]
    native_ids = {row["persistentTypeID"] for row in report["records"]}
    keys = {(row["managed"]["assembly_identity"], row["managed"]["name"]) for row in rows}
    if not rows or len(keys) != len(rows) or any(row["persistentTypeID"] not in native_ids for row in rows):
        raise ValueError("Incomplete or ambiguous reverse identity")
    for row in rows:
        path = Path(row["managed"]["image_path"])
        if not path.resolve().is_relative_to(contents) or base.sha(path) != row["managed"]["image_sha256"]:
            raise ValueError("Observed reverse SDK assembly drift")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5) or (len(sys.argv) == 5 and sys.argv[4] != "--reverse"):
        raise SystemExit("Usage: phone_wrapper_population_oracle.py ROOT WORK EXACT_EDITOR [--reverse]")
    destination, receipt = run(*sys.argv[1:4], reverse=len(sys.argv) == 5)
    print(json.dumps({"evidence": str(destination), **receipt}))
    raise SystemExit(not receipt["success"])
