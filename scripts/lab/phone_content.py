"""Stage/check the authored native content probe without touching the game."""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import struct
import uuid

from phone_bundle import VERSION, make_bundle

SOURCES = {
    "ContentFixture.cs": "Assets",
    "NativeScriptSchemaFixture.cs": "Assets",
    "ContentFixtureBuilder.cs": "Assets/Editor",
    "ContentFixtureLinkerCapture.cs": "Assets/Editor",
}


def fixture_sources(ambient=False):
    return {"AmbientSkyFixture.cs": "Assets/Editor"} if ambient else SOURCES


def stage(destination, *, ambient=False):
    """Stage a new isolated project; refuse to overwrite any earlier attempt."""
    from common import ROOT

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    assets = destination / "Assets"
    (assets / "Editor").mkdir(parents=True)
    (assets / "StreamingAssets").mkdir()
    sources = fixture_sources(ambient)
    for name, relative in sources.items():
        folder = destination / relative
        source = ROOT / "tools/phone-build" / name
        (folder / name).write_bytes(source.read_bytes())
    (destination / "Packages").mkdir()
    (destination / "Packages/manifest.json").write_text(
        '{"dependencies":{"com.unity.modules.androidjni":"1.0.0","com.unity.modules.assetbundle":"1.0.0","com.unity.modules.jsonserialize":"1.0.0","com.unity.modules.unitywebrequest":"1.0.0"}}\n'
    )
    (destination / "ProjectSettings").mkdir()
    (destination / "ProjectSettings/ProjectVersion.txt").write_text(
        "m_EditorVersion: " + VERSION + "\nm_EditorVersionWithRevision: " + VERSION + " (88f88f591b2e)\n"
    )
    data = make_bundle()
    (assets / "StreamingAssets/phone-fixture.bundle").write_bytes(data)
    receipt = {
        "schema": 1,
        "generator": "scripts/lab/phone_content.py",
        "unity": VERSION,
        "bundle_sha256": hashlib.sha256(data).hexdigest(),
        "game_inputs": False,
        "device_accepted": False,
        "ambient_capture": ambient,
        "sources": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "scripts/lab/phone_content.py",
                "scripts/lab/phone_bundle.py",
                *("tools/phone-build/" + name for name in sources),
            )
        },
    }
    (destination / "fixture-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def stage_action():
    from common import WORK, now

    destination = WORK / "rebuild/phone-content" / now() / "project"
    print(json.dumps({"project": str(destination), **stage(destination)}, indent=2))


def stage_ambient_action():
    from common import WORK, now

    destination = WORK / "rebuild/phone-content" / now() / "project"
    print(json.dumps({"project": str(destination), **stage(destination, ambient=True)}, indent=2))


def validate_oracle(report):
    if report.get("unity") != VERSION or not all(report.get(key) is True for key in ("bundleLoaded", "textMatched", "unloaded")) or report.get("failure"):
        raise RuntimeError("Exact-editor oracle version/content contract failed")


def validate_ambient_oracle(report):
    if report.get("unity") != VERSION or report.get("gpu") != "Metal" or report.get("captureCompleted") is not True or report.get("failure"):
        raise RuntimeError("Exact-editor ambient capture did not complete")


def validate_ambient_capture(attempt):
    """Check the external observer's evidence, never a marker alone."""
    from phone_converter import bounded, sha

    attempt = Path(attempt)
    receipt = json.loads((attempt / "capture-complete.json").read_text())
    faces = receipt["faces"]
    sh = receipt["sh"]
    if len(faces) != 6 or [row["face"] for row in faces] != list(range(6)) or sh["cached"] is not False:
        raise RuntimeError("Ambient capture needs six ordered faces and uncached SH")
    for row in [*faces, sh]:
        path = bounded(attempt, row["file"])
        expected_bytes = 108 if row is sh else 64 * 64 * 16
        if row is not sh and (row["width"], row["height"], row["format"]) != (64, 64, 89):
            raise RuntimeError("Unexpected ambient image layout")
        if path.stat().st_size != expected_bytes or sha(path) != row["sha256"]:
            raise RuntimeError("Ambient observation bytes changed")
        data = path.read_bytes()
        if not all(math.isfinite(value[0]) for value in struct.iter_unpack("<f", data)):
            raise RuntimeError("Nonfinite ambient observation")
    trace = attempt / "ambient.gputrace"
    if not trace.exists() or not (any(path.is_file() and path.stat().st_size for path in trace.rglob("*")) if trace.is_dir() else trace.stat().st_size):
        raise RuntimeError("Ambient GPU trace is absent or empty")
    return receipt


def validate_linker_capture(attempt, commit):
    from phone_converter import bounded, sha

    attempt = Path(attempt)
    build = json.loads((attempt / "player-build.json").read_text())
    capture = attempt / "linker-capture"
    receipt = json.loads((capture / "receipt.json").read_text())
    for value in (build, receipt):
        if value.get("unity") != VERSION or value.get("source_commit") != commit or not value.get("build_report_guid"):
            raise RuntimeError("Fixture linker build identity mismatch")
    if receipt["build_report_guid"] != build["build_report_guid"]:
        raise RuntimeError("Fixture linker capture belongs to another build")
    files = receipt["files"]
    names = [row["name"] for row in files]
    if len(set(names)) != len(names) or not {"Assembly-CSharp.dll", "TypesInScenes.xml", "EditorToUnityLinkerData.json"} <= set(names):
        raise RuntimeError("Fixture linker input closure is incomplete or duplicated")
    actual = {p.relative_to(capture / "inputs").as_posix() for p in (capture / "inputs").rglob("*") if p.is_file()}
    if actual != set(names):
        raise RuntimeError("Fixture linker input file set drift")
    for row in files:
        path = bounded(capture / "inputs", row["name"])
        if path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise RuntimeError("Fixture linker captured input drift")
    return {"capture": str(capture), "files": len(files), "receipt_sha256": sha(capture / "receipt.json"), "build_report_guid": build["build_report_guid"]}


def run_editor(project, *, build=False, ambient=False):
    """Use only the generated fixture and the primary checkout's build mutex."""
    from build_lock import host_build_lock
    from common import ROOT, WORK

    project = Path(project).resolve()
    if not project.is_relative_to((WORK / "rebuild/phone-content").resolve()):
        raise RuntimeError("Select an isolated phone-content project with --target")
    receipt = json.loads((project / "fixture-inputs.json").read_text())
    if ambient != receipt.get("ambient_capture", False) or (ambient and build):
        raise RuntimeError("Select the matching isolated fixture mode")
    for name, expected in receipt["sources"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Source changed; generate a new attempt: " + name)
    for name, folder in fixture_sources(ambient).items():
        if (project / folder / name).read_bytes() != (ROOT / "tools/phone-build" / name).read_bytes():
            raise RuntimeError("Staged fixture source changed: " + name)
    if hashlib.sha256((project / "Assets/StreamingAssets/phone-fixture.bundle").read_bytes()).hexdigest() != receipt["bundle_sha256"]:
        raise RuntimeError("Generated fixture bundle changed")
    if build and subprocess.check_output(
        ["git", "status", "--porcelain", "--", "tools/phone-build", "scripts/lab/phone_content.py", "scripts/lab/phone_bundle.py"], cwd=ROOT
    ):
        raise RuntimeError("Commit the fixture sources before building")
    common_dir = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, text=True).strip())
    if common_dir.name != ".git":
        raise RuntimeError("Cannot locate the primary checkout build mutex")
    lock = common_dir.parent / "work/coordination/unity-build.lock"
    operation = "ambient-capture" if ambient else "build" if build else "check"
    attempt = project.parent / ("editor-" + operation + "-" + uuid.uuid4().hex)
    attempt.mkdir(exist_ok=False)
    log = attempt / "editor.log"
    method = "AmbientSkyFixture.Begin" if ambient else "ContentFixtureBuilder.Build" if build else "ContentFixtureBuilder.Check"
    env = dict(os.environ)
    env["ROR2_PHONE_ORACLE_REPORT"] = str(attempt / "oracle.json")
    if ambient:
        env["ROR2_AMBIENT_CAPTURE"] = str(attempt)
    env["ROR2_PHONE_BUILD_SOURCE"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    env["ANDROID_SDK_HOME"] = str(ROOT / ".local/phone-build-android")
    env["ANDROID_USER_HOME"] = str(ROOT / ".local/phone-build-android/.android")
    env["GRADLE_USER_HOME"] = str(ROOT / ".local/phone-build-gradle")
    Path(env["ANDROID_USER_HOME"]).mkdir(parents=True, exist_ok=True)
    args = [
        env["UNITY_EDITOR"],
        "-batchmode",
        *([] if ambient else ["-nographics", "-quit"]),
        "-projectPath",
        str(project),
        "-buildTarget",
        "Android",
        "-executeMethod",
        method,
        "-logFile",
        str(log),
    ]
    with host_build_lock(lock, operation="Alpha phone content fixture " + operation, timeout=1):
        result = subprocess.run(args, env=env, capture_output=True, timeout=600)
    (attempt / "launch.txt").write_bytes(result.stdout + result.stderr)
    oracle = None
    oracle_error = None
    linker_capture = None
    ambient_capture = None
    try:
        oracle = json.loads((attempt / "oracle.json").read_text())
        (validate_ambient_oracle if ambient else validate_oracle)(oracle)
        if ambient and result.returncode == 0:
            ambient_capture = validate_ambient_capture(attempt)
        if build and result.returncode == 0:
            linker_capture = validate_linker_capture(attempt, env["ROR2_PHONE_BUILD_SOURCE"])
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        oracle_error = str(error)
    outcome = {
        "exit_code": result.returncode,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "log": str(log),
        "fixture_inputs": receipt,
        "editor": env["UNITY_EDITOR"],
        "oracle": oracle,
        "oracle_error": oracle_error,
        "linker_capture": linker_capture,
        "ambient_capture": ambient_capture,
    }
    (attempt / "receipt.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome, indent=2))
    if result.returncode or oracle_error:
        raise RuntimeError("Exact-editor fixture failed; inspect its retained log")
