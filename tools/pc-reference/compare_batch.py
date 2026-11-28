"""Offline comparison of explicitly paired PC and Android capture steps."""

import argparse
from collections import defaultdict
import io
import json
import math
from pathlib import Path
import statistics
import sys

from compare import artifact, pair, read, select, timeline_frame

DEFAULTS = {
    "effect_delta": 18,
    "missing_ratio": 0.40,
    "opaque_fill": 0.85,
    "opaque_range": 22,
    "blend_change": 18,
    "audio_tolerance_ms": 100,
}


def number(value, label, low=0, high=math.inf):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {label}")
    return value


def relative(root, name):
    path = Path(name)
    target = (root / path).resolve()
    if path.is_absolute() or ".." in path.parts or not target.is_relative_to(root) or not target.is_file():
        raise ValueError("Android capture path must name a file inside the pairing directory")
    return target


def load_png(path):
    from PIL import Image

    with Image.open(path, formats=["PNG"]) as image:
        return image.convert("RGB")


def align(pc, android, offset):
    x, y = offset
    w, h = pc.size
    aw, ah = android.size
    if w * ah != h * aw:
        raise ValueError("Frame aspect ratios differ; crop to the same view before comparing")
    if abs(x) >= w or abs(y) >= h:
        raise ValueError("Offset leaves no overlapping pixels")
    # Offset is where Android's resized top-left lands in PC coordinates.
    l, t, r, b = max(x, 0), max(y, 0), min(w + x, w), min(h + y, h)
    if android.size != pc.size:
        from PIL import Image

        android = android.resize(pc.size, Image.Resampling.BILINEAR)
    return pc.crop((l, t, r, b)), android.crop((l - x, t - y, r - x, b - y))


def similarity(pc, android):
    # Average local luminance SSIM over nonoverlapping 8x8 tiles (population
    # moments). Keeping local contrast avoids a large uniform background
    # dominating the structural score as strongly as a global statistic.
    p, a = (im.convert("L").load() for im in (pc, android))
    w, h = pc.size
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    result = 0.0
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            sp = sa = spp = saa = spa = n = 0
            for yy in range(y, min(y + 8, h)):
                for xx in range(x, min(x + 8, w)):
                    u, v = p[xx, yy], a[xx, yy]
                    sp, sa, spp, saa, spa = sp + u, sa + v, spp + u * u, saa + v * v, spa + u * v
                    n += 1
            mp, ma = sp / n, sa / n
            vp, va, cov = spp / n - mp * mp, saa / n - ma * ma, spa / n - mp * ma
            result += n * (2 * mp * ma + c1) * (2 * cov + c2) / ((mp * mp + ma * ma + c1) * (vp + va + c2))
    return result / (w * h)


def effect_stats(image, background, delta):
    from PIL import ImageChops, ImageStat

    difference = ImageChops.difference(image, background)
    r, g, b = difference.split()
    max_channel = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = max_channel.point([0 if i < delta else 255 for i in range(256)])
    count = mask.histogram()[255]
    rect = mask.getbbox()
    if not rect:
        return {"pixels": 0, "box_fill": None, "box_aspect": None, "color_range": None, "mean_delta": None}
    l, t, r, b = rect
    return {
        "pixels": count,
        "box_fill": count / ((r - l) * (b - t)),
        "box_aspect": min(r - l, b - t) / max(r - l, b - t),
        "color_range": max(hi - lo for lo, hi in image.crop(rect).getextrema()),
        "mean_delta": ImageStat.Stat(max_channel, mask=mask).mean[0],
    }


def images(pc, android, offset, thresholds, backgrounds=None, diff_output=None):
    from PIL import ImageChops, ImageStat

    pc_image, android_image = load_png(pc), load_png(android)
    p, a = align(pc_image, android_image, offset)
    diff = ImageChops.difference(p, a)
    if diff_output is not None:
        diff.save(diff_output, format="PNG")
    result = {
        "overlap": list(p.size),
        "android_offset_pc_pixels": offset,
        "mean_absolute_rgb_delta": statistics.mean(ImageStat.Stat(diff).mean),
        "luminance_ssim_8x8": similarity(p, a),
        "color_is_advisory": True,
        "effect_flags": None,
    }
    if backgrounds:
        pb, ab = (load_png(path) for path in backgrounds)
        if pb.size != pc_image.size or ab.size != android_image.size:
            raise ValueError("Background sizes do not match their capture frames")
        pb, ab = align(pb, ab, offset)
        pfx, afx = [effect_stats(im, bg, thresholds["effect_delta"]) for im, bg in ((p, pb), (a, ab))]

        def square(row):
            return (
                row["pixels"] >= 16
                and row["box_aspect"] >= 0.85
                and row["box_fill"] >= thresholds["opaque_fill"]
                and row["color_range"] <= thresholds["opaque_range"]
            )

        result["effect_measurements"] = {"pc": pfx, "android": afx}
        result["effect_flags"] = {
            "missing_effect": afx["pixels"] < pfx["pixels"] * thresholds["missing_ratio"] if pfx["pixels"] else None,
            "opaque_square_candidate": square(afx) and not square(pfx) if pfx["pixels"] else None,
            "blend_difference_candidate": (
                abs(afx["mean_delta"] - pfx["mean_delta"]) >= thresholds["blend_change"] if pfx["pixels"] and afx["pixels"] else None
            ),
        }
    return result


def event_id(value):
    if type(value) in (str, int) and str(value).isascii() and str(value).isdigit():
        return str(int(value))
    return None


def events(path, step, aliases, start=None, end=None):
    groups = defaultdict(list)
    skipped = 0
    posts = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("step") != step:
                continue
            seconds = number(row["seconds"], "event time")
            if (start is not None and seconds < start) or (end is not None and seconds >= end):
                continue
            numeric, name = event_id(row.get("event_id")), row.get("event_name")
            if not isinstance(name, str) or not name.strip():
                name = aliases.get(numeric)
            identity = ("name:" + name) if name else ("id:" + numeric) if numeric else None
            if not identity:
                skipped += 1
                continue
            playing = event_id(row.get("playing_id"))
            if playing not in {None, "0"}:
                # Wrapped Wwise overloads can both observe one post. IDs are
                # local to this trace, not cross-platform event identities.
                key = playing, row.get("frame") if type(row.get("frame")) is int else seconds
                old = posts.get(key)
                if old is None or (identity.startswith("name:") and old[0].startswith("id:")):
                    posts[key] = identity, seconds
            else:
                groups[identity].append(seconds)
    for identity, seconds in posts.values():
        groups[identity].append(seconds)
    return {key: sorted(values) for key, values in groups.items()}, skipped


def audio(pc, android, step, marks, tolerance, aliases):
    markers = None
    duration = None
    if marks is not None:
        if not isinstance(marks, dict) or marks.keys() - {"pc_seconds", "android_seconds", "window_seconds"}:
            raise ValueError("Invalid audio marker fields")
        markers = [number(marks[key], key) for key in ("pc_seconds", "android_seconds")]
        if "window_seconds" in marks:
            duration = number(marks["window_seconds"], "audio window", 0.001, 86400)

    def load_events(path, marker):
        if duration is None:
            return events(path, step, aliases)
        return events(path, step, aliases, marker, marker + duration)

    (p, dropped_pc), (a, dropped_android) = [load_events(path, marker) for path, marker in zip((pc, android), markers or (None, None))]
    rows = []
    for key in sorted(p.keys() | a.keys()):
        pc_times, android_times = p.get(key, []), a.get(key, [])
        deltas = None if markers is None else [round(1000 * ((v - markers[1]) - (u - markers[0])), 3) for u, v in zip(pc_times, android_times)]
        rows.append(
            {
                "event": key,
                "pc_count": len(pc_times),
                "android_count": len(android_times),
                "android_minus_pc_ms": deltas,
                "out_of_tolerance": None if deltas is None else sum(abs(value) > tolerance for value in deltas),
            }
        )
    return {
        "timing_aligned": markers is not None,
        "pc_unidentified": dropped_pc,
        "android_unidentified": dropped_android,
        "audio_tolerance_ms": tolerance,
        "window_seconds": duration,
        "events": rows,
    }


def object_fields(value, allowed, label):
    if not isinstance(value, dict) or value.keys() - allowed:
        raise ValueError(f"Invalid {label} fields")
    return value


def capture_label(value):
    if not isinstance(value, str) or not value or not value.isascii() or not all(c.isalnum() or c in "-_." for c in value) or value in {".", ".."}:
        raise ValueError("Invalid capture step or scenario ID")
    return value


def compare(manifest_path, pairs_path, diff_images=None):
    spec = object_fields(read(pairs_path), {"schema_version", "pairs", "thresholds", "event_aliases"}, "pairing")
    if spec["schema_version"] != 1 or not isinstance(spec["pairs"], list) or not spec["pairs"]:
        raise ValueError("Expected a version 1 pairing file with at least one pair")
    manifest = read(manifest_path)
    limits = {**DEFAULTS, **object_fields(spec.get("thresholds", {}), DEFAULTS.keys(), "threshold")}
    for name, value in limits.items():
        lo, hi = (0, 1) if name in {"missing_ratio", "opaque_fill"} else (0, 60_000) if name == "audio_tolerance_ms" else (1, 255)
        number(value, name, lo, hi)
    aliases = spec.get("event_aliases", {})
    if not isinstance(aliases, dict) or any(event_id(key) != key or not isinstance(name, str) or not name.strip() for key, name in aliases.items()):
        raise ValueError("Event aliases require decimal Wwise ID strings mapped to names")
    root = pairs_path.resolve().parent
    rows = []
    seen = set()
    for item in spec["pairs"]:
        item = object_fields(
            item, {"scenario", "step", "pc_frame", "android_frame", "android_state", "offset", "background", "android_audio", "audio_markers"}, "step pair"
        )
        scenario_id, step_id = (capture_label(item[key]) for key in ("scenario", "step"))
        if (scenario_id, step_id) in seen:
            raise ValueError("Duplicate scenario/step pairing")
        seen.add((scenario_id, step_id))
        scenario, step = select(manifest, scenario_id, step_id)
        android_frame = relative(root, item["android_frame"])
        android_state = relative(root, item["android_state"]) if "android_state" in item else None
        frame = item.get("pc_frame", step["timeline"][0]["frame"])
        metadata, pc_frame = pair(manifest_path, scenario_id, step_id, android_frame, android_state, frame)
        metadata["pc"]["frame"] = frame
        metadata["pc"]["frame_seconds"] = number(next(entry["seconds"] for entry in step["timeline"] if entry["frame"] == frame), "PC frame time")
        offset = item.get("offset", [0, 0])
        if not isinstance(offset, list) or len(offset) != 2 or not all(type(x) is int for x in offset):
            raise ValueError("Offset must be two integer PC pixel coordinates")
        backgrounds = None
        if "background" in item:
            bg = object_fields(item["background"], {"pc_step", "pc_frame", "android_frame"}, "background")
            _, bg_step = select(manifest, scenario_id, capture_label(bg["pc_step"]))
            backgrounds = (
                timeline_frame(manifest_path, scenario, bg_step, bg.get("pc_frame", bg_step["timeline"][0]["frame"])),
                relative(root, bg["android_frame"]),
            )
        comparable = metadata["scene_matches"] is not False and metadata["requested_seed_matches"] is not False
        metadata["comparison_status"] = "measured" if comparable else "scene_or_seed_mismatch"
        buffer = io.BytesIO() if comparable and diff_images is not None else None
        metadata["images"] = images(pc_frame, android_frame, offset, limits, backgrounds, buffer) if comparable else None
        if buffer is not None:
            name = f"diff-{len(rows) + 1:04d}.png"
            diff_images[name] = buffer.getvalue()
            metadata["images"]["aligned_diff"] = name
        metadata["audio"] = None
        if "audio_markers" in item and "android_audio" not in item:
            raise ValueError("Audio markers require an Android event log")
        if comparable and "android_audio" in item:
            pc_audio = artifact(manifest_path, scenario, scenario.get("audio_events", "audio-events.jsonl"))
            metadata["audio"] = audio(
                pc_audio, relative(root, item["android_audio"]), step_id, item.get("audio_markers"), limits["audio_tolerance_ms"], aliases
            )
        rows.append(metadata)
    return {
        "schema_version": 1,
        "pc_capture_identity": {k: manifest[k] for k in ("build", "managed_sha256", "plan_sha256", "resolution") if k in manifest},
        "thresholds": limits,
        "steps": rows,
    }


def markdown(report):
    def plain(value):
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\n", " ").replace("\r", " ")

    lines = [
        "# PC to Android capture comparison",
        "",
        "CrossOver color and lighting differences are advisory. Effect flags are heuristics, not visual parity gates.",
        "Match the camera, scene and timing before interpreting scores. JSON retains measurements and thresholds.",
        "",
    ]
    for step in report["steps"]:
        lines += [f"## {step['scenario']} / {step['step']}", ""]
        if step["comparison_status"] != "measured":
            lines += ["Not compared: scene or requested seed differs.", ""]
            continue
        image = step["images"]
        w, h = image["overlap"]
        lines += [
            f"- Aligned overlap: {w} × {h}; luminance SSIM-style score: {image['luminance_ssim_8x8']:.4f}.",
            f"- Mean absolute RGB delta: {image['mean_absolute_rgb_delta']:.3f} (0–255, advisory).",
        ]
        flags = image["effect_flags"]
        lines.append(
            "- Effect candidates: "
            + (
                ", ".join(f"{key.replace('_', ' ')}: {'unavailable' if value is None else 'yes' if value else 'no'}" for key, value in flags.items())
                if flags is not None
                else "unavailable (needs paired background frames)."
            )
        )
        sound = step["audio"]
        if sound is None:
            lines += ["- Audio comparison: unavailable (no paired event log).", ""]
            continue
        lines += [
            f"- Audio timing: {'step-aligned' if sound['timing_aligned'] else 'unavailable without step markers'}. "
            f"Unidentified posts: PC {sound['pc_unidentified']}, Android {sound['android_unidentified']}.",
            "",
            "| Event | PC posts | Android posts | Android minus PC (ms) | Outside tolerance |",
            "|---|---:|---:|---|---:|",
        ]
        for row in sound["events"]:
            deltas = row["android_minus_pc_ms"]
            delta_cell = "unavailable" if deltas is None else ", ".join(map(str, deltas)) or "unmatched"
            lines.append(
                f"| {plain(row['event'])} | {row['pc_count']} | {row['android_count']} | {delta_cell} | "
                f"{row['out_of_tolerance'] if deltas is not None else 'unavailable'} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Existing PC capture manifest")
    parser.add_argument("pairs", type=Path, help="JSON mapping capture steps to Android evidence")
    parser.add_argument("--output", type=Path, required=True, help="New private directory for comparison.json and comparison.md")
    parser.add_argument("--diff-images", action="store_true", help="Write private aligned absolute RGB difference PNGs")
    args = parser.parse_args(argv)
    try:
        diff_images = {} if args.diff_images else None
        report = compare(args.manifest, args.pairs, diff_images)
        as_json = json.dumps(report, indent=2, allow_nan=False) + "\n"
        as_markdown = markdown(report)
        args.output.mkdir()
        (args.output / "comparison.json").write_text(as_json, encoding="utf-8")
        (args.output / "comparison.md").write_text(as_markdown, encoding="utf-8")
        for name, data in (diff_images or {}).items():
            (args.output / name).write_bytes(data)
    except (AttributeError, ImportError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"pc-reference comparison: {error}", file=sys.stderr)
        return 1
    return 0
