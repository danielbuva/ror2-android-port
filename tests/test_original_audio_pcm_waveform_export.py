from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))

from original_audio_pcm_waveform import Refusal, export_capture, inspect_capture
from original_audio_pcm_waveform import MAX_METADATA_BYTES

OUTPUT_ID = "17375808098319191535"
APK_SHA = "a" * 64
CAPTURE_ID = "c" * 32
PRIVATE_TEST_ROOT = Path(__file__).resolve().parents[1]


def write_capture(root: Path, values: list[float], **overrides: object) -> tuple[Path, Path]:
    generation = int(overrides.get("generation", 19))
    capture_id = str(overrides.get("capture_id", CAPTURE_ID))
    stem = f"capture-v1-{capture_id}-{generation:016x}"
    raw = root / f"{stem}.f32le"
    metadata_path = root / f"{stem}.json"
    payload = b"".join(struct.pack("<f", value) for value in values)
    raw.write_bytes(payload)
    metadata = {
        "schema": 1,
        "abi": "WwiseDiag_CaptureReadbackV1",
        "generation": str(generation),
        "capture_id": capture_id,
        "output_id": OUTPUT_ID,
        "sample_format": "ieee-float32-le",
        "sample_rate_hz": 48000,
        "channels": 2,
        "channel_mask": 3,
        "total_samples": str(len(values)),
        "stored_samples": len(values),
        "finite_samples": str(len(values)),
        "nonzero_finite_samples": str(sum(value != 0 for value in values)),
        "nonfinite_samples": "0",
        "callbacks": "1",
        "window_peak_abs": max(abs(value) for value in values),
        "window_rms": math.sqrt(sum(value * value for value in values) / len(values)),
        "stored_prefix_peak_abs": max(abs(value) for value in values),
        "stored_prefix_rms": math.sqrt(sum(value * value for value in values) / len(values)),
        "truncated": False,
        "original_engine_term_returned": True,
        "original_callback_manager_term_returned": True,
        "post_term_disarm_verified": True,
        "raw_pcm_persisted": True,
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "source_event_attributed": False,
        "physical_audibility_claim": False,
    }
    metadata.update({key: value for key, value in overrides.items() if key not in {"generation", "capture_id"}})
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return raw, metadata_path


class PcmWaveExportTests(unittest.TestCase):
    def test_cli_refuses_capture_paths_outside_ignored_work(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-cli-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.5, -0.5])
            output = root / "output"
            command = [
                sys.executable,
                str(PRIVATE_TEST_ROOT / "scripts/lab/original_audio_pcm_waveform.py"),
                "--raw",
                str(raw),
                "--metadata",
                str(metadata),
                "--output-dir",
                str(output),
                "--expected-output-id",
                OUTPUT_ID,
                "--expected-apk-sha256",
                APK_SHA,
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("capture_paths_must_be_under_ignored_work", result.stderr)
            self.assertFalse(output.exists())

    def test_oversized_raw_is_refused_before_sample_file_is_opened(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-bound-", dir=PRIVATE_TEST_ROOT) as temp:
            raw, metadata = write_capture(Path(temp), [0.5, -0.5])
            with raw.open("r+b") as stream:
                stream.truncate(262144 * 4 + 1)
            original_open = Path.open

            def guarded_open(path, *args, **kwargs):
                if path == raw:
                    raise AssertionError("oversized sample file was opened")
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", guarded_open):
                with self.assertRaisesRegex(Refusal, "raw_sample_byte_count_mismatch"):
                    inspect_capture(raw, metadata, OUTPUT_ID)

    def test_oversized_metadata_is_refused_before_metadata_file_is_opened(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-metadata-bound-", dir=PRIVATE_TEST_ROOT) as temp:
            raw, metadata = write_capture(Path(temp), [0.5, -0.5])
            metadata.write_bytes(b" " * (MAX_METADATA_BYTES + 1))
            original_open = Path.open

            def guarded_open(path, *args, **kwargs):
                if path == metadata:
                    raise AssertionError("oversized metadata file was opened")
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", guarded_open):
                with self.assertRaisesRegex(Refusal, "metadata_too_large"):
                    inspect_capture(raw, metadata, OUTPUT_ID)

    def test_sample_rate_byte_rate_overflow_refuses_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-rate-overflow-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.5, -0.5], sample_rate_hz=(0xFFFFFFFF // 8) + 1)
            output = root / "out"
            with self.assertRaisesRegex(Refusal, "sample_rate_hz_overflow"):
                export_capture(raw, metadata, output, OUTPUT_ID, APK_SHA)
            self.assertFalse(output.exists())

    def test_term_and_disarm_witnesses_are_mandatory(self) -> None:
        for field in (
            "original_engine_term_returned",
            "original_callback_manager_term_returned",
            "post_term_disarm_verified",
            "raw_pcm_persisted",
        ):
            with (
                self.subTest(field=field),
                tempfile.TemporaryDirectory(prefix="pcm-wave-witness-", dir=PRIVATE_TEST_ROOT) as temp,
            ):
                root = Path(temp)
                raw, metadata = write_capture(root, [0.5, -0.5], **{field: False})
                with self.assertRaisesRegex(Refusal, "term_disarm_or_raw_persistence_witness_missing"):
                    inspect_capture(raw, metadata, OUTPUT_ID)

    def test_valid_float32_stereo_wav_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-export-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            values = [0.5, -0.5, 1.0, -1.0]
            raw, metadata = write_capture(root, values)
            wav_path, receipt_path = export_capture(raw, metadata, root / "out", OUTPUT_ID, APK_SHA)
            self.assertTrue(wav_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertFalse(receipt["event_attributed"])
            self.assertFalse(receipt["physical_audibility_claim"])
            self.assertTrue(receipt["original_engine_term_returned"])
            self.assertTrue(receipt["original_callback_manager_term_returned"])
            self.assertTrue(receipt["post_term_disarm_verified"])
            self.assertEqual(receipt["prefix_peak_abs"], 1.0)
            self.assertAlmostEqual(receipt["prefix_rms"], math.sqrt(0.625))
            blob = wav_path.read_bytes()
            self.assertEqual(blob[:4], b"RIFF")
            self.assertEqual(blob[8:12], b"WAVE")
            self.assertEqual(blob[12:16], b"fmt ")
            fmt = struct.unpack("<HHIIHH", blob[20:36])
            self.assertEqual(fmt, (3, 2, 48000, 384000, 8, 32))
            self.assertEqual(blob[36:40], b"data")
            self.assertEqual(blob[40:44], struct.pack("<I", 16))
            self.assertEqual(blob[44:], raw.read_bytes())
            self.assertEqual(hashlib.sha256(blob).hexdigest(), receipt["wav_sha256"])

    def test_truncated_prefix_is_exported_and_labeled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-truncated-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            values = [0.25, -0.25]
            raw, metadata = write_capture(
                root,
                values,
                total_samples="8",
                finite_samples="8",
                nonzero_finite_samples="8",
                truncated=True,
            )
            wav_path, receipt_path = export_capture(raw, metadata, root / "out", OUTPUT_ID, APK_SHA)
            self.assertTrue(wav_path.is_file())
            self.assertTrue(json.loads(receipt_path.read_text())["waveform_truncated"])

    def test_mismatched_identity_hash_and_format_refuse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-refusal-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.5, -0.5])
            with self.assertRaisesRegex(Refusal, "output_identity_mismatch"):
                inspect_capture(raw, metadata, "1")
            data = json.loads(metadata.read_text())
            data["raw_sha256"] = "0" * 64
            metadata.write_text(json.dumps(data))
            with self.assertRaisesRegex(Refusal, "raw_sample_hash_mismatch"):
                inspect_capture(raw, metadata, OUTPUT_ID)
            data["raw_sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
            data["sample_format"] = "pcm16"
            metadata.write_text(json.dumps(data))
            with self.assertRaisesRegex(Refusal, "sample_format_unsupported"):
                inspect_capture(raw, metadata, OUTPUT_ID)

    def test_nonfinite_count_bad_layout_and_rms_drift_refuse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-invalid-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.5, -0.5], nonfinite_samples="1")
            with self.assertRaisesRegex(Refusal, "finite_sample_contract_failed"):
                inspect_capture(raw, metadata, OUTPUT_ID)
            raw, metadata = write_capture(root, [0.5, -0.5], channel_mask=4)
            with self.assertRaisesRegex(Refusal, "channel_layout_not_supported_for_wav"):
                inspect_capture(raw, metadata, OUTPUT_ID)
            raw, metadata = write_capture(root, [0.5, -0.5], stored_prefix_rms=0.0)
            with self.assertRaisesRegex(Refusal, "prefix_rms_mismatch"):
                inspect_capture(raw, metadata, OUTPUT_ID)

    def test_fractional_metadata_counts_are_not_truncated_to_integers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-counts-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.5, -0.5], sample_rate_hz=48000.5)
            with self.assertRaisesRegex(Refusal, "sample_rate_hz_invalid"):
                inspect_capture(raw, metadata, OUTPUT_ID)

    def test_capture_nonce_binds_pair_and_separates_same_generation_outputs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-capture-id-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw1, metadata1 = write_capture(root, [0.5, -0.5], generation=1, capture_id="1" * 32)
            raw2, metadata2 = write_capture(root, [0.25, -0.25], generation=1, capture_id="2" * 32)
            out = root / "out"
            wav1, receipt1 = export_capture(raw1, metadata1, out, OUTPUT_ID, APK_SHA)
            wav2, receipt2 = export_capture(raw2, metadata2, out, OUTPUT_ID, APK_SHA)
            self.assertNotEqual(wav1, wav2)
            self.assertNotEqual(receipt1, receipt2)
            self.assertEqual(json.loads(receipt1.read_text())["capture_id"], "1" * 32)
            self.assertEqual(json.loads(receipt2.read_text())["capture_id"], "2" * 32)
            with self.assertRaisesRegex(Refusal, "capture_pair_filename_mismatch"):
                inspect_capture(raw1, metadata2, OUTPUT_ID)
            data = json.loads(metadata1.read_text())
            data["capture_id"] = "not-a-canonical-id"
            metadata1.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(Refusal, "capture_id_invalid"):
                inspect_capture(raw1, metadata1, OUTPUT_ID)

    def test_symlinks_short_files_and_output_reuse_refuse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-path-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.5, -0.5])
            symlink = root / "linked.f32le"
            symlink.symlink_to(raw)
            with self.assertRaisesRegex(Refusal, "symlink_input_refused"):
                inspect_capture(symlink, metadata, OUTPUT_ID)
            raw.write_bytes(raw.read_bytes()[:-1])
            with self.assertRaisesRegex(Refusal, "raw_sample_byte_count_mismatch"):
                inspect_capture(raw, metadata, OUTPUT_ID)
            raw, metadata = write_capture(root, [0.5, -0.5])
            out = root / "out"
            wav_path, _ = export_capture(raw, metadata, out, OUTPUT_ID, APK_SHA)
            with self.assertRaisesRegex(Refusal, "output_path_preexisting"):
                export_capture(raw, metadata, out, OUTPUT_ID, APK_SHA)

    def test_mono_uses_standard_float_wave_container(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pcm-wave-mono-", dir=PRIVATE_TEST_ROOT) as temp:
            root = Path(temp)
            raw, metadata = write_capture(root, [0.25], channels=1, channel_mask=4)
            wav_path, _ = export_capture(raw, metadata, root / "out", OUTPUT_ID, APK_SHA)
            blob = wav_path.read_bytes()
            self.assertEqual(struct.unpack("<HHIIHH", blob[20:36]), (3, 1, 48000, 192000, 4, 32))
            self.assertEqual(blob[44:], raw.read_bytes())


if __name__ == "__main__":
    unittest.main()
