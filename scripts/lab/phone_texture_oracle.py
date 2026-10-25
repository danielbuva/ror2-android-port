"""Isolated exact-editor raw mip oracle; never a phone/game build input."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

VERSION = "2021.3.45f2"
SOURCES = ("scripts/lab/phone_texture_oracle.py", "tools/phone-build/TextureMipFixture.cs")
MANIFEST = '{"dependencies":{"com.unity.modules.imageconversion":"1.0.0","com.unity.modules.jsonserialize":"1.0.0"}}\n'
PROJECT_VERSION = "m_EditorVersion: " + VERSION + "\nm_EditorVersionWithRevision: " + VERSION + " (88f88f591b2e)\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_action():
    from common import ROOT, WORK, now

    project = WORK / "rebuild/phone-texture-oracle" / now() / "project"
    (project / "Assets/Editor").mkdir(parents=True)
    (project / "Packages").mkdir()
    (project / "ProjectSettings").mkdir()
    (project / "Assets/Editor/TextureMipFixture.cs").write_bytes((ROOT / SOURCES[1]).read_bytes())
    (project / "Packages/manifest.json").write_text(MANIFEST)
    (project / "ProjectSettings/ProjectVersion.txt").write_text(PROJECT_VERSION)
    receipt = {
        "unity": VERSION,
        "game_inputs": False,
        "sources": {name: sha(ROOT / name) for name in SOURCES},
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    (project / "oracle-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"project": str(project), **receipt}, indent=2))


def run_editor(project):
    from build_lock import host_build_lock
    from common import ROOT, WORK
    from phone_registry import BINARY_SHA256

    project = Path(project).absolute()
    base = (WORK / "rebuild/phone-texture-oracle").resolve()
    if project != project.resolve(strict=True) or not project.is_relative_to(base) or project == base:
        raise ValueError("Select an isolated authored texture-oracle project")
    receipt = json.loads((project / "oracle-inputs.json").read_text())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if receipt != {"unity": VERSION, "game_inputs": False, "sources": {name: sha(ROOT / name) for name in SOURCES}, "source_commit": commit}:
        raise ValueError("Texture oracle source identity differs; stage current committed sources")
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=ROOT):
        raise ValueError("Commit texture oracle sources before checking")
    if (project / "Assets/Editor/TextureMipFixture.cs").read_bytes() != (ROOT / SOURCES[1]).read_bytes():
        raise ValueError("Staged texture oracle source drift")
    if (project / "Packages/manifest.json").read_text() != MANIFEST or (project / "ProjectSettings/ProjectVersion.txt").read_text() != PROJECT_VERSION:
        raise ValueError("Texture oracle project configuration differs")
    if {p.relative_to(project / "Assets").as_posix() for p in (project / "Assets").rglob("*") if p.is_file()} != {"Editor/TextureMipFixture.cs"}:
        raise ValueError("Fresh texture oracle project required")
    editor = Path(os.environ["UNITY_EDITOR"])
    if sha(editor) != BINARY_SHA256:
        raise ValueError("Exact owner SDK required")
    common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, text=True).strip())
    if common.name != ".git":
        raise ValueError("Primary checkout mutex is unavailable")
    attempt = project.parent / ("editor-check-" + uuid.uuid4().hex)
    attempt.mkdir()
    output, log = attempt / "texture-mips", attempt / "editor.log"
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
        "TextureMipFixture.Run",
        "-logFile",
        str(log),
    ]
    env = dict(os.environ, ROR2_TEXTURE_MIP_REPORT=str(output), ROR2_PHONE_BUILD_SOURCE=commit)
    result = {"success": False, "source_commit": commit, "command": args, "inputs": receipt}
    try:
        with host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="owner authored texture mip oracle", timeout=1):
            child = subprocess.run(args, env=env, capture_output=True, timeout=600)
        (attempt / "launch.txt").write_bytes(child.stdout + child.stderr)
        result["returncode"] = child.returncode
        if child.returncode:
            raise ValueError("Exact-editor texture oracle failed; inspect retained log")
        result["mips"] = validate_mips(attempt, commit)
        result["success"] = True
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        (attempt / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"receipt": str(attempt / "receipt.json"), **result}, indent=2))


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
        width = 1024 if row["pattern"] == "noise" else 256
        height = 4 if row["pattern"] == "ramp" else width
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
    mirror = report["floatMirror"]
    if {k: mirror[k] for k in ("pattern", "mode", "format", "input")} != {
        "pattern": "noise",
        "mode": "linear-float",
        "format": "RGBAFloat",
        "input": "noise.input.rgba",
    } or len(mirror["levels"]) != 11:
        raise ValueError("Texture oracle float mirror identity differs")
    for mip, level in enumerate(mirror["levels"]):
        size = max(1, 1024 >> mip)
        name = "noise-linear-float.mip" + str(mip) + ".rgba32f"
        if level != {"width": size, "height": size, "mip": mip, "file": name} or (root / name).stat().st_size != size * size * 16:
            raise ValueError("Texture oracle float mirror extent differs")
        outputs[name] = {"bytes": (root / name).stat().st_size, "sha256": sha(root / name)}
    quantized = report["floatQuantized"]
    if {k: quantized[k] for k in ("pattern", "mode", "format", "input")} != {
        "pattern": "noise",
        "mode": "linear-float-quantized",
        "format": "RGBAFloat",
        "input": "noise.input.rgba",
    } or len(quantized["levels"]) != 11:
        raise ValueError("Texture oracle float quantization identity differs")
    for mip, level in enumerate(quantized["levels"]):
        size = max(1, 1024 >> mip)
        name = "noise-linear-float-quantized.mip" + str(mip) + ".rgba"
        if level != {"width": size, "height": size, "mip": mip, "file": name} or (root / name).stat().st_size != size * size * 4:
            raise ValueError("Texture oracle float quantization extent differs")
        outputs[name] = {"bytes": (root / name).stat().st_size, "sha256": sha(root / name)}
    if report["transfer"] != "runtime-transfer.f32" or (root / report["transfer"]).stat().st_size != 256 * 8:
        raise ValueError("Texture oracle native transfer extent differs")
    outputs[report["transfer"]] = {"bytes": 256 * 8, "sha256": sha(root / report["transfer"])}
    return {"report": str(root / "result.json"), "images": 9, "float_mirror": True, "outputs": outputs}
