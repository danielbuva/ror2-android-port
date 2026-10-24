"""Stage/check the authored native content probe without touching the game."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from phone_bundle import VERSION, make_bundle

SOURCES = {
    "ContentFixture.cs": "Assets",
    "ContentFixtureBuilder.cs": "Assets/Editor",
    "TextureMipFixture.cs": "Assets/Editor",
    "ContentFixtureLinkerCapture.cs": "Assets/Editor",
}


def stage(destination):
    """Stage a new isolated project; refuse to overwrite any earlier attempt."""
    from common import ROOT

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    assets = destination / "Assets"
    (assets / "Editor").mkdir(parents=True)
    (assets / "StreamingAssets").mkdir()
    for name, relative in SOURCES.items():
        folder = destination / relative
        source = ROOT / "tools/phone-build" / name
        (folder / name).write_bytes(source.read_bytes())
    (destination / "Packages").mkdir()
    (destination / "Packages/manifest.json").write_text(
        '{"dependencies":{"com.unity.modules.androidjni":"1.0.0","com.unity.modules.assetbundle":"1.0.0","com.unity.modules.imageconversion":"1.0.0","com.unity.modules.jsonserialize":"1.0.0","com.unity.modules.unitywebrequest":"1.0.0"}}\n'
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
                "tools/phone-build/TextureMipFixture.cs",
                "tools/phone-build/ContentFixtureLinkerCapture.cs",
            )
        },
    }
    (destination / "fixture-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def stage_action():
    from common import WORK, now

    destination = WORK / "rebuild/phone-content" / now() / "project"
    print(json.dumps({"project": str(destination), **stage(destination)}, indent=2))


def validate_oracle(report):
    if report.get("unity") != VERSION or not all(report.get(key) is True for key in ("bundleLoaded", "textMatched", "unloaded")) or report.get("failure"):
        raise RuntimeError("Exact-editor oracle version/content contract failed")


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


def validate_mips(attempt, commit):
    """Verify the authored oracle's complete imported-image/level file cohort."""
    root = Path(attempt) / "texture-mips"
    report = json.loads((root / "result.json").read_text())
    if report["unity"] != VERSION or report["source_commit"] != commit:
        raise ValueError("Texture mip oracle identity differs")
    identities = {(r["pattern"], r["mode"]) for r in report["images"]}
    if len(report["images"]) != 9 or identities != {(p, m) for p in ("ramp", "noise", "normal") for m in ("linear", "srgb", "normal")}:
        raise ValueError("Texture mip oracle import cohort differs")
    outputs = {}
    for row in report["images"]:
        width, height = (256, 4) if row["pattern"] == "ramp" else (32, 32)
        source = root / (row["pattern"] + ".input.rgba")
        if row["input"] != source.name or source.stat().st_size != width * height * 4:
            raise ValueError("Texture mip oracle authored input differs")
        expected_levels = max(width, height).bit_length()
        if len(row["levels"]) != expected_levels:
            raise ValueError("Texture mip oracle level count differs")
        for mip, level in enumerate(row["levels"]):
            name = row["pattern"] + "-" + row["mode"] + ".mip" + str(mip) + ".rgba"
            w, h = max(1, width >> mip), max(1, height >> mip)
            if level != {"width": w, "height": h, "mip": mip, "file": name}:
                raise ValueError("Texture mip oracle level identity differs")
            path = root / name
            if path.stat().st_size != w * h * 4:
                raise ValueError("Texture mip oracle pixel extent differs")
            if mip == 0 and row["mode"] != "normal" and path.read_bytes() != source.read_bytes():
                raise ValueError("Texture mip oracle base pixels differ")
            outputs[name] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"report": str(root / "result.json"), "images": 9, "outputs": outputs}


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
    for name, folder in SOURCES.items():
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
    operation = "build" if build else "check"
    attempt = project.parent / ("editor-" + operation + "-" + uuid.uuid4().hex)
    attempt.mkdir(exist_ok=False)
    log = attempt / "editor.log"
    method = "ContentFixtureBuilder.Build" if build else "ContentFixtureBuilder.Check"
    env = dict(os.environ)
    env["ROR2_PHONE_ORACLE_REPORT"] = str(attempt / "oracle.json")
    env["ROR2_PHONE_BUILD_SOURCE"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
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
    (attempt / "launch.txt").write_bytes(result.stdout + result.stderr)
    oracle = None
    oracle_error = None
    linker_capture = None
    mips = None
    try:
        oracle = json.loads((attempt / "oracle.json").read_text())
        validate_oracle(oracle)
        mips = validate_mips(attempt, env["ROR2_PHONE_BUILD_SOURCE"])
        if build and result.returncode == 0:
            linker_capture = validate_linker_capture(attempt, env["ROR2_PHONE_BUILD_SOURCE"])
    except (OSError, ValueError, RuntimeError) as error:
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
        "texture_mips": mips,
    }
    (attempt / "receipt.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome, indent=2))
    if result.returncode or oracle_error:
        raise RuntimeError("Exact-editor fixture failed; inspect its retained log")
