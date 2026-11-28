"""Synthetic capture pairs through both public comparison entry points."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools/pc-reference/compare.py"


class ReferenceComparisonTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.pc = self.root / "pc"
        self.android = self.root / "phone"
        self.android.mkdir()
        self.scene = self.pc / "synthetic"
        self.steps = []
        for name in ("before", "cast"):
            folder = self.scene / name
            folder.mkdir(parents=True)
            self.steps.append({"id": name, "frame": f"{name}/frame.png", "state": f"{name}/state.json", "timeline": [{"frame": "frame.png", "seconds": 10}]})
            self.write(folder / "state.json", {"scene": "example", "field_of_view": 60})
        self.image(self.scene / "before/frame.png")
        self.image(self.scene / "cast/frame.png", "cross")
        self.image(self.android / "before.png")
        self.image(self.android / "frame.png", "square")
        self.write(self.android / "state.json", {"stage": {"scene": "example"}, "runSeedOverride": "4"})
        self.write_events(
            self.scene / "audio-events.jsonl",
            [
                (9.9, "cast", "lead_in"),
                (10.1, "cast", "launch"),
                (10.2, "cast", "launch"),
                (10.4, "cast", "vanished"),
                (11, "cast", "at_window_end"),
                (2, "before", "ignore"),
            ],
        )
        self.write_events(
            self.android / "events.jsonl",
            [(19.92, "cast", "lead_in"), (20.5, "cast", "launch"), (20.14, "cast", "launch"), (20.6, "cast", "added"), (21, "cast", "at_window_end")],
        )
        self.manifest = self.pc / "manifest.json"
        self.write(
            self.manifest,
            {
                "schema_version": 1,
                "platform": "crossover-d3d11",
                "build": "57",
                "scenarios": [
                    {
                        "id": "synthetic",
                        "status": "passed",
                        "seed": "4",
                        "route": "assisted-direct-entry",
                        "steps": self.steps,
                        "sha256": {
                            p.relative_to(self.scene).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.scene.rglob("*") if p.is_file()
                        },
                    }
                ],
            },
        )
        self.spec = self.android / "pairs.json"
        self.pair = {
            "scenario": "synthetic",
            "step": "cast",
            "android_frame": "frame.png",
            "android_state": "state.json",
            "background": {"pc_step": "before", "android_frame": "before.png"},
            "android_audio": "events.jsonl",
            "audio_markers": {"pc_seconds": 10, "android_seconds": 20, "window_seconds": 1},
        }
        self.output = self.root / "report"

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def write_events(self, path, events):
        path.write_text(
            "".join(json.dumps({"seconds": time, "step": step, "event_name": name, "playing_id": "fixture"}) + "\n" for time, step, name in events),
            encoding="utf-8",
        )

    def image(self, path, effect=None, dx=0):
        im = Image.new("RGB", (32, 32), (4, 4, 4))
        pen = ImageDraw.Draw(im)
        if effect == "square":
            pen.rectangle((10, 10, 20, 20), fill=(250, 240, 220))
        if effect == "cross":
            pen.line((10 + dx, 15, 20 + dx, 15), fill=(110, 52, 45), width=3)
            pen.line((15 + dx, 10, 15 + dx, 20), fill=(120, 75, 58), width=3)
        im.save(path)

    def batch(self, *pairs, thresholds=None, aliases=None, success=True):
        self.write(self.spec, {"schema_version": 1, "pairs": list(pairs), "thresholds": thresholds or {}, "event_aliases": aliases or {}})
        proc = subprocess.run(
            [sys.executable, str(CLI), "batch", str(self.manifest), str(self.spec), "--output", str(self.output), "--diff-images"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0 if success else 1, proc.stdout + proc.stderr)
        return json.loads((self.output / "comparison.json").read_text()) if success else proc.stderr

    def test_batch_effect_flags_audio_counts_and_aligned_timing(self):
        report = self.batch(self.pair, {"scenario": "synthetic", "step": "before", "android_frame": "before.png"})
        step, baseline = report["steps"]
        self.assertEqual(report["pc_capture_identity"]["build"], "57")
        self.assertEqual(baseline["images"]["luminance_ssim_8x8"], 1)
        self.assertEqual(baseline["images"]["mean_absolute_rgb_delta"], 0)
        flags = step["images"]["effect_flags"]
        self.assertEqual(flags, {"missing_effect": False, "opaque_square_candidate": True, "blend_difference_candidate": True})
        audio = {row["event"]: row for row in step["audio"]["events"]}
        self.assertEqual(audio["name:launch"]["android_minus_pc_ms"], [40, 300])
        self.assertEqual(audio["name:launch"]["out_of_tolerance"], 1)
        self.assertEqual(audio["name:added"]["pc_count"], 0)
        self.assertEqual(audio["name:vanished"]["android_count"], 0)
        self.assertNotIn("name:ignore", audio)
        self.assertNotIn("name:lead_in", audio)
        self.assertNotIn("name:at_window_end", audio)
        self.assertIn("name:launch", (self.output / "comparison.md").read_text())

    def test_audio_alignment_alone_preserves_events_across_the_step(self):
        self.pair["audio_markers"].pop("window_seconds")
        audio = self.batch(self.pair)["steps"][0]["audio"]
        self.assertTrue(audio["timing_aligned"])
        self.assertIsNone(audio["window_seconds"])
        events = {row["event"]: row for row in audio["events"]}
        for name, count, deltas in (("lead_in", 1, [20]), ("launch", 2, [40, 300]), ("at_window_end", 1, [0])):
            row = events[f"name:{name}"]
            self.assertEqual((row["pc_count"], row["android_count"], row["android_minus_pc_ms"]), (count, count, deltas))
        self.assertNotIn("name:ignore", events)

    def test_missing_effect_and_unaligned_audio_are_distinct(self):
        self.image(self.android / "frame.png")
        self.pair.pop("audio_markers")
        step = self.batch(self.pair)["steps"][0]
        self.assertTrue(step["images"]["effect_flags"]["missing_effect"])
        self.assertIsNone(step["images"]["effect_flags"]["blend_difference_candidate"])
        self.assertFalse(step["audio"]["timing_aligned"])
        self.assertIsNone(step["audio"]["events"][0]["android_minus_pc_ms"])

    def test_explicit_offset_and_existing_pair_cli(self):
        self.image(self.android / "frame.png", "cross", dx=3)
        self.pair.update(offset=[-3, 0])
        proc = subprocess.run(
            [sys.executable, str(CLI), str(self.manifest), "synthetic", "cast", str(self.android / "frame.png")],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(json.loads(proc.stdout)["pc"]["width"], 32)
        image = self.batch(self.pair)["steps"][0]["images"]
        self.assertEqual(image["overlap"], [29, 32])
        self.assertEqual(image["mean_absolute_rgb_delta"], 0)
        self.assertEqual(image["luminance_ssim_8x8"], 1)

    def test_refuses_modified_pc_artifact_and_path_escape(self):
        self.assertIn("inside the pairing directory", self.batch(dict(self.pair, android_frame="../pc/synthetic/cast/frame.png"), success=False))
        with (self.scene / "audio-events.jsonl").open("a") as stream:
            stream.write("\n")
        self.assertIn("PC artifact changed", self.batch(self.pair, success=False))
        self.assertFalse(self.output.exists())

    def test_distinct_seed_does_not_produce_parity_metrics(self):
        self.write(self.android / "state.json", {"stage": {"scene": "example"}, "runSeedOverride": "9"})
        step = self.batch(self.pair)["steps"][0]
        self.assertEqual(step["comparison_status"], "scene_or_seed_mismatch")
        self.assertIsNone(step["images"])

    def test_aliases_join_named_and_numeric_posts_and_diff_is_aligned(self):
        rows = [
            {"seconds": 20.1, "step": "cast", "event_id": "27", "playing_id": "321", "frame": 14},
            {"seconds": 20.1, "step": "cast", "event_name": "launch", "playing_id": "321", "frame": 14},
        ]
        (self.android / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        step = self.batch(self.pair, aliases={"27": "launch"})["steps"][0]
        launch = next(row for row in step["audio"]["events"] if row["event"] == "name:launch")
        self.assertEqual((launch["pc_count"], launch["android_count"], launch["android_minus_pc_ms"]), (2, 1, [0]))
        with Image.open(self.output / step["images"]["aligned_diff"]) as diff:
            self.assertEqual(diff.size, (32, 32))
            self.assertNotEqual(diff.getpixel((10, 10)), (0, 0, 0))
