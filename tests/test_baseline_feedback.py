"""Authored data only; no device, account or captured game report."""

import copy
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import baseline_feedback as f


def result(stage=False):
    value = {
        "success": True,
        "failures": [],
        "apk_sha256": "a" * 64,
        "is_current_build": False,
        "world_seconds": 35.2,
        "applied_runs": 0,
        "cleanup": {"selector_absent": True, "process_absent": True, "sleep_requested": True, "display_asleep": True},
    }
    if stage:
        value.update(mode="stage-exit", transitions=1, stage_world_seconds=10.25)
    return value


class FeedbackTests(unittest.TestCase):
    def test_both_modes_report_assistance_and_limits_without_changing_input(self):
        for stage in (False, True):
            source = result(stage)
            before = copy.deepcopy(source)
            value = f.preview(source)
            self.assertEqual(source, before)
            self.assertEqual(value["check"], "stage-exit" if stage else "baseline")
            self.assertFalse(value["matches_local_current_build"])
            self.assertTrue(value["assisted"])
            self.assertTrue(all(value[key] is False for key in ("ordinary_controls_qualified", "full_run_qualified", "visual_audio_parity_qualified")))

    def test_private_strings_nested_data_and_failure_text_never_export(self):
        secret = "AUTHORED_PRIVATE_SENTINEL"
        source = result()
        source.update(
            success=False,
            failures=[secret],
            pid=secret,
            evidence=secret,
            stop=secret,
            scene=secret,
            issue_draft_url=secret,
            ordinary_controls_qualified=True,
            extra={"account": secret, "token": secret},
        )
        source["cleanup"]["device"] = secret
        value = f.preview(source)
        self.assertEqual(value["failed_criteria_count"], 1)
        self.assertFalse(value["reported_success"])
        self.assertFalse(value["ordinary_controls_qualified"])
        self.assertNotIn(secret, json.dumps(value))
        self.assertNotIn(secret, parse_qs(urlparse(f.issue_url(source)).query)["body"][0])

    def test_draft_has_fixed_destination_and_no_extra_query_parameters(self):
        url = urlparse(f.issue_url(result(True)))
        self.assertEqual((url.scheme, url.netloc, url.path), ("https", "github.com", "/danielbuva/ror2-android-port/issues/new"))
        query = parse_qs(url.query)
        self.assertEqual(set(query), {"title", "body"})
        self.assertIn('"assisted":true', query["body"][0])
        self.assertLess(len(url.geturl()), 2048)

    def test_largest_allowed_counters_keep_the_draft_url_bounded(self):
        source = result(True)
        source.update(success=False, failures=["omitted"] * 10000)
        for key in ("world_seconds", "stage_world_seconds", "applied_runs", "transitions"):
            source[key] = 604800
        self.assertLess(len(f.issue_url(source)), 2048)

    def test_malformed_identity_booleans_mode_and_failures_refuse(self):
        cases = [
            {"apk_sha256": "not-a-hash"},
            {"apk_sha256": "A" * 64},
            {"mode": "custom"},
            {"success": 1},
            {"is_current_build": "true"},
            {"failures": "raw log"},
            {"failures": [None]},
            {"failures": ["failure"]},
            {"success": False},
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                f.preview(dict(result(), **change))

    def test_quantity_types_bounds_and_nonfinite_values_refuse(self):
        for field in ("world_seconds", "stage_world_seconds", "applied_runs", "transitions"):
            invalid = [True, -1, float("nan"), float("inf"), "35", 604801]
            if field in ("applied_runs", "transitions"):
                invalid.append(1.5)
            for item in invalid:
                with self.subTest(field=field, item=item), self.assertRaises(ValueError):
                    f.preview(dict(result(True), **{field: item}))

    def test_missing_observations_are_null_not_invented(self):
        source = result(True)
        for key in ("world_seconds", "stage_world_seconds", "applied_runs", "transitions"):
            del source[key]
        value = f.preview(source)
        for key in ("world_seconds", "stage_world_seconds", "applied_profile_runs", "transitions"):
            self.assertIsNone(value[key])

    def test_incomplete_teardown_refuses_and_optional_sleep_is_explicit(self):
        for key, item in (("selector_absent", False), ("process_absent", False), ("sleep_requested", None), ("display_asleep", None), ("display_asleep", 1)):
            source = result()
            source["cleanup"][key] = item
            with self.subTest(key=key, item=item), self.assertRaises(ValueError):
                f.preview(source)
        source = result()
        source["cleanup"].update(sleep_requested=False, display_asleep=None)
        self.assertIsNone(f.preview(source)["cleanup"]["display_asleep"])

    def test_file_input_duplicate_keys_nonfinite_and_oversized_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "preview.json"
            for raw in ('{"success": true, "success": false}', '{"value":NaN}', '{"value":Infinity}', " " * (f.MAX_INPUT_BYTES + 1)):
                source.write_text(raw)
                with self.assertRaises(ValueError):
                    f.write_preview(source, output)
                self.assertFalse(output.exists())

    def test_new_file_only_and_existing_output_or_symlink_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.json", root / "preview.json"
            source.write_text(json.dumps(result()))
            f.write_preview(source, output)
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                f.write_preview(source, output)
            self.assertEqual(output.read_bytes(), before)
            link = root / "link.json"
            link.symlink_to(output)
            with self.assertRaises(FileExistsError):
                f.write_preview(source, link)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(json.loads(before)["schema"], 1)
            if sys.platform != "win32":
                self.assertEqual(stat.S_IMODE(output.stat().st_mode) & 0o077, 0)

    def test_cli_writes_optional_draft_only_locally_and_errors_omit_input_values(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "preview.json"
            source.write_text(json.dumps(result(True)))
            command = [sys.executable, str(ROOT / "scripts/lab/baseline_feedback.py"), "--input", str(source), "--output", str(output), "--draft-url"]
            run = subprocess.run(command, capture_output=True, text=True, check=True)
            value = json.loads(output.read_text())
            self.assertEqual(value["issue_draft_url"], f.issue_url(result(True)))
            self.assertNotIn("https://", run.stdout)
            before = output.read_bytes()
            refused = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            secret = "AUTHORED_PRIVATE_SENTINEL"
            source.write_text(json.dumps(dict(result(), success=secret)))
            output.unlink()
            refused = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertNotIn(secret, refused.stdout + refused.stderr)
            self.assertFalse(output.exists())

    def test_optimized_cli_keeps_validation_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "preview.json"
            source.write_text(json.dumps(dict(result(), apk_sha256="AUTHORED_PRIVATE_SENTINEL")))
            for optimization in ("-O", "-OO"):
                command = [sys.executable, optimization, str(ROOT / "scripts/lab/baseline_feedback.py"), "--input", str(source), "--output", str(output)]
                refused = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(refused.returncode, 2)
                self.assertFalse(output.exists())
                self.assertNotIn("AUTHORED_PRIVATE_SENTINEL", refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main()
