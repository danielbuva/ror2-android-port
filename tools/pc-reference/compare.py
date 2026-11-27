"""Pair a PC recorder frame with an explicitly chosen Android lab capture."""

import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def png_info(path):
    with path.open("rb") as image:
        header = image.read(24)
        if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise ValueError(f"Expected a PNG image: {path.name}")
        width, height = struct.unpack(">II", header[16:24])
        image.seek(0)
        return {"width": width, "height": height, "sha256": hashlib.file_digest(image, "sha256").hexdigest()}


def pair(manifest_path, scenario_id, step_id, android_frame, android_state_path, frame):
    manifest = read(manifest_path)
    if manifest.get("schema_version", 1) != 1:
        raise ValueError("Unsupported PC capture manifest version")
    scenario = next((entry for entry in manifest["scenarios"] if entry["id"] == scenario_id), None)
    if not scenario or scenario["status"] != "passed" or "sha256" not in scenario:
        raise ValueError("PC scenario has no completed capture")
    step = next((entry for entry in scenario["steps"] if entry["id"] == step_id), None)
    if not step or frame not in [entry["frame"] for entry in step["timeline"]]:
        raise ValueError("Frame is not present in the selected PC step")
    root = manifest_path.resolve().parent

    def artifact(name):
        path = (root / scenario_id / name).resolve()
        if not path.is_relative_to(root) or name not in scenario["sha256"]:
            raise ValueError("Artifact is absent from the PC manifest")
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != scenario["sha256"][name]:
                raise ValueError(f"PC artifact changed since capture: {path.name}")
        return path

    pc_frame = artifact(f"{step_id}/{frame}")
    pc_state = read(artifact(step["state"]))
    phone = read(android_state_path) if android_state_path else {}
    android_camera = phone.get("world", {}).get("camera", {})
    android_scene = phone.get("stage", {}).get("scene") or None
    android_seed = phone.get("runSeedOverride") or None
    camera_delta = None
    if "position" in android_camera and android_camera.get("frames", 0) > 0:
        camera_delta = math.dist(
            [pc_state["camera_position"][axis] for axis in "xyz"],
            [android_camera["position"][axis] for axis in "xyz"],
        )
    report = {
        "scenario": scenario_id,
        "step": step_id,
        "pc": {
            **png_info(pc_frame),
            "platform": manifest["platform"],
            "scene": pc_state["scene"],
            "seed": scenario["seed"],
            "route": scenario["route"],
            "field_of_view": pc_state["field_of_view"],
        },
        "android": {**png_info(android_frame), "scene": android_scene, "requested_seed": android_seed, "field_of_view": android_camera.get("fov")},
        "scene_matches": pc_state["scene"] == android_scene if android_scene else None,
        "requested_seed_matches": scenario["seed"] == str(android_seed) if android_seed else None,
        "camera_position_delta_m": camera_delta,
    }
    return report, pc_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("scenario")
    parser.add_argument("step")
    parser.add_argument("android_frame", type=Path)
    parser.add_argument("--android-state", type=Path, help="Optional Android gameplay state JSON")
    parser.add_argument("--pc-frame", default="frame.png", help="Select a named PNG from the PC step timeline")
    parser.add_argument("--side-by-side", type=Path, help="Write a PNG with PC left and Android right (requires ffmpeg)")
    args = parser.parse_args()
    try:
        report, pc_frame = pair(args.manifest, args.scenario, args.step, args.android_frame, args.android_state, args.pc_frame)
        if args.side_by_side:
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg is None:
                raise RuntimeError("Side-by-side images require ffmpeg")
            subprocess.run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-n",
                    "-v",
                    "error",
                    "-i",
                    pc_frame,
                    "-i",
                    args.android_frame,
                    "-filter_complex",
                    "[0:v]scale=-2:720,setsar=1[pc];[1:v]scale=-2:720,setsar=1[android];[pc][android]hstack",
                    "-frames:v",
                    "1",
                    "-update",
                    "1",
                    args.side_by_side,
                ],
                check=True,
                timeout=60,
            )
        print(json.dumps(report, indent=2))
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
