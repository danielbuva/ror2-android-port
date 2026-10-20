"""Stage/check the authored native content probe without touching the game."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

from phone_bundle import VERSION, make_bundle


def stage(destination):
    """Stage a new isolated project; refuse to overwrite any earlier attempt."""
    from common import ROOT

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    assets = destination / "Assets"
    (assets / "Editor").mkdir(parents=True)
    (assets / "StreamingAssets").mkdir()
    for name, folder in (("ContentFixture.cs", assets), ("ContentFixtureBuilder.cs", assets / "Editor")):
        source = ROOT / "tools/phone-build" / name
        (folder / name).write_bytes(source.read_bytes())
    (destination / "Packages").mkdir()
    (destination / "Packages/manifest.json").write_text(
        '{"dependencies":{"com.unity.modules.assetbundle":"1.0.0","com.unity.modules.jsonserialize":"1.0.0","com.unity.modules.unitywebrequest":"1.0.0"}}\n'
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
        "sources": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "scripts/lab/phone_content.py",
                "scripts/lab/phone_bundle.py",
                "tools/phone-build/ContentFixture.cs",
                "tools/phone-build/ContentFixtureBuilder.cs",
            )
        },
    }
    (destination / "fixture-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def stage_action():
    from common import WORK, now

    destination = WORK / "rebuild/phone-content" / now() / "project"
    print(json.dumps({"project": str(destination), **stage(destination)}, indent=2))


def run_editor(project, *, build=False):
    """Use only the generated fixture and the primary checkout's build mutex."""
    from build_lock import host_build_lock
    from common import ROOT, WORK

    project = Path(project).resolve()
    if not project.is_relative_to((WORK / "rebuild/phone-content").resolve()):
        raise RuntimeError("Select an isolated phone-content project with --target")
    receipt = json.loads((project / "fixture-inputs.json").read_text())
    for name, expected in receipt["sources"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Source changed; generate a new attempt: " + name)
    for name, relative in (("ContentFixture.cs", "Assets/ContentFixture.cs"), ("ContentFixtureBuilder.cs", "Assets/Editor/ContentFixtureBuilder.cs")):
        if (project / relative).read_bytes() != (ROOT / "tools/phone-build" / name).read_bytes():
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
    operation = "build" if build else "check"
    log = project.parent / ("editor-" + operation + ".log")
    method = "ContentFixtureBuilder.Build" if build else "ContentFixtureBuilder.Check"
    env = dict(os.environ)
    env["ANDROID_SDK_HOME"] = str(ROOT / ".local/phone-build-android")
    env["ANDROID_USER_HOME"] = str(ROOT / ".local/phone-build-android/.android")
    env["GRADLE_USER_HOME"] = str(ROOT / ".local/phone-build-gradle")
    Path(env["ANDROID_USER_HOME"]).mkdir(parents=True, exist_ok=True)
    args = [
        env["UNITY_EDITOR"],
        "-batchmode",
        "-nographics",
        "-quit",
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
    (project.parent / ("editor-" + operation + "-launch.txt")).write_bytes(result.stdout + result.stderr)
    outcome = {
        "exit_code": result.returncode,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "log": str(log),
        "fixture_inputs": receipt,
    }
    (project.parent / ("editor-" + operation + "-receipt.json")).write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome, indent=2))
    if result.returncode:
        raise RuntimeError("Exact-editor fixture failed; inspect its retained log")
