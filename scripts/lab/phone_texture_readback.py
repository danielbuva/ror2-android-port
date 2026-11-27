"""Run the exact-editor GPU readback in a separate, disposable fixture."""

import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from phone_content import VERSION, native_content_request, stage, validate_native_content


SOURCES = {
    "ContentFixtureTextureMip.cs": "Assets/Editor",
    "TextureMipFixture.shader": "Assets",
}


def readback_request(path):
    request = native_content_request(path)
    if "scene" in request:
        raise RuntimeError("Texture mip readback requires typed texture assets")
    for asset in request["assets"]:
        sample = asset.get("texture_mip")
        face_count = {"Texture2D": 1, "Cubemap": 6}.get(asset["type"], 0)
        if (
            not isinstance(sample, dict)
            or type(sample.get("mip")) is not int
            or sample["mip"] < 0
            or type(sample.get("face")) is not int
            or not 0 <= sample["face"] < face_count
        ):
            raise RuntimeError("Texture mip selection requires a nonnegative mip and a valid face for its type")
    return request


def validate_texture_mip(path, selection, report):
    if (
        not isinstance(report, dict)
        or any(report.get(key) != selection[key] for key in ("mip", "face"))
        or any(type(report.get(key)) is not int or report[key] <= 0 for key in ("width", "height"))
        or not report.get("graphics")
        or report["graphics"] == "Null"
        or report.get("color_space") not in ("Gamma", "Linear")
        or not report.get("format")
        or path.stat().st_size != report["width"] * report["height"] * 4
    ):
        raise RuntimeError("Exact-editor texture mip readback contract failed")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != report.get("sha256"):
            raise RuntimeError("Exact-editor texture mip readback hash mismatch")


def run_editor(path):
    from build_lock import host_build_lock, unity_editor_env
    from common import ROOT, WORK
    from phone_registry import BINARY_SHA256

    path = Path(path).resolve(strict=True)
    if not path.is_relative_to(WORK.resolve()):
        raise RuntimeError("Texture readback request must be ignored local state")
    request = readback_request(path)
    editor_env = unity_editor_env()
    editor = Path(editor_env["UNITY_EDITOR"])
    with editor.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != BINARY_SHA256:
            raise RuntimeError("Texture mip readback requires the pinned Unity editor")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    common_dir = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, text=True).strip())
    if common_dir.name != ".git":
        raise RuntimeError("Cannot locate the primary checkout build mutex")

    attempt = WORK / "rebuild/phone-texture-readback" / uuid.uuid4().hex
    project = attempt / "project"
    fixture = stage(project)
    for name, folder in SOURCES.items():
        relative = "tools/phone-build/" + name
        data = (ROOT / relative).read_bytes()
        (project / folder / name).write_bytes(data)
        fixture["sources"][relative] = hashlib.sha256(data).hexdigest()
    runner = "scripts/lab/phone_texture_readback.py"
    fixture["sources"][runner] = hashlib.sha256((ROOT / runner).read_bytes()).hexdigest()
    snapshot = attempt / "native-content-request.json"
    snapshot.write_text(json.dumps(request, indent=2) + "\n")
    editor_env.update(ROR2_PHONE_BUILD_SOURCE=commit, ROR2_PHONE_TEXTURE_READBACK=str(snapshot))
    log = attempt / "editor.log"
    args = [
        str(editor),
        "-batchmode",
        "-quit",
        "-projectPath",
        str(project),
        "-buildTarget",
        "Android",
        "-executeMethod",
        "ContentFixtureBuilder.CheckTextureReadback",
        "-logFile",
        str(log),
    ]
    result = {"success": False, "source_commit": commit, "unity": VERSION, "log": str(log), "inputs": fixture}
    try:
        with host_build_lock(common_dir.parent / "work/coordination/unity-build.lock", operation="exact-editor texture mip readback", timeout=1):
            child = subprocess.run(args, env=editor_env, capture_output=True, timeout=600)
        (attempt / "launch.txt").write_bytes(child.stdout + child.stderr)
        result["exit_code"] = child.returncode
        if child.returncode:
            raise RuntimeError("Exact-editor texture readback failed: " + str(log))
        report = validate_native_content(attempt, commit)
        samples = json.loads((attempt / "texture-readback.json").read_text())
        for index, (asset, sample) in enumerate(zip(request["assets"], samples["samples"], strict=True)):
            validate_texture_mip(attempt / f"texture-{index}.rgba", asset["texture_mip"], sample)
        result.update(success=True, native_content=report, samples=samples["samples"])
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        receipt = attempt / "receipt.json"
        receipt.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"receipt": str(receipt), **result}, indent=2))
