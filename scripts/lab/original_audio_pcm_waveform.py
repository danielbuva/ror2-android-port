#!/usr/bin/env python3
"""Validate a private bounded F32 capture and export a local IEEE-float WAV.

This helper consumes only explicitly supplied app-private capture files and
writes only under an explicit ignored evidence directory. It never decodes or
plays audio. Real device transport/ownership remains an external gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

MAX_SAMPLES = 262_144
MAX_METADATA_BYTES = 16 * 1024
EXPECTED_ABI = "WwiseDiag_CaptureReadbackV1"


class Refusal(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise Refusal(f"{field}_invalid")
    if isinstance(value, str) and not value.isdecimal():
        raise Refusal(f"{field}_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise Refusal(f"{field}_invalid") from error
    if parsed <= 0:
        raise Refusal(f"{field}_invalid")
    return parsed


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise Refusal(f"{field}_invalid")
    if isinstance(value, str) and not value.isdecimal():
        raise Refusal(f"{field}_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise Refusal(f"{field}_invalid") from error
    if parsed < 0:
        raise Refusal(f"{field}_invalid")
    return parsed


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise Refusal(f"{field}_invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise Refusal(f"{field}_invalid") from error
    if not math.isfinite(parsed):
        raise Refusal(f"{field}_nonfinite")
    return parsed


def inspect_capture(raw_path: Path, metadata_path: Path, expected_output_id: str) -> tuple[dict, bytes, float, float]:
    if raw_path.is_symlink() or metadata_path.is_symlink():
        raise Refusal("symlink_input_refused")
    try:
        if metadata_path.stat().st_size > MAX_METADATA_BYTES:
            raise Refusal("metadata_too_large")
        with metadata_path.open("rb") as stream:
            metadata_bytes = stream.read(MAX_METADATA_BYTES + 1)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Refusal("metadata_unreadable") from error
    if len(metadata_bytes) > MAX_METADATA_BYTES:
        raise Refusal("metadata_too_large")
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Refusal("metadata_unreadable") from error
    if not isinstance(metadata, dict) or metadata.get("schema") != 1 or metadata.get("abi") != EXPECTED_ABI:
        raise Refusal("metadata_schema_or_abi_mismatch")
    if (
        metadata.get("original_engine_term_returned") is not True
        or metadata.get("original_callback_manager_term_returned") is not True
        or metadata.get("post_term_disarm_verified") is not True
        or metadata.get("raw_pcm_persisted") is not True
    ):
        raise Refusal("term_disarm_or_raw_persistence_witness_missing")
    if not expected_output_id.isdecimal() or int(expected_output_id) == 0 or int(expected_output_id) > 0xFFFFFFFFFFFFFFFF:
        raise Refusal("expected_output_id_invalid")
    if str(metadata.get("output_id")) != expected_output_id:
        raise Refusal("output_identity_mismatch")
    if metadata.get("sample_format") != "ieee-float32-le":
        raise Refusal("sample_format_unsupported")
    channels = _positive_int(metadata.get("channels"), "channels")
    mask = _positive_int(metadata.get("channel_mask"), "channel_mask")
    if (channels, mask) not in {(1, 4), (2, 3)}:
        raise Refusal("channel_layout_not_supported_for_wav")
    sample_rate = _positive_int(metadata.get("sample_rate_hz"), "sample_rate_hz")
    if sample_rate > 0xFFFFFFFF // (channels * 4):
        raise Refusal("sample_rate_hz_overflow")
    total_samples = _positive_int(metadata.get("total_samples"), "total_samples")
    stored_samples = _positive_int(metadata.get("stored_samples"), "stored_samples")
    finite_samples = _positive_int(metadata.get("finite_samples"), "finite_samples")
    nonfinite_samples = _nonnegative_int(metadata.get("nonfinite_samples"), "nonfinite_samples")
    nonzero_samples = _nonnegative_int(metadata.get("nonzero_finite_samples"), "nonzero_finite_samples")
    if stored_samples > MAX_SAMPLES or stored_samples > total_samples:
        raise Refusal("sample_bound_or_total_invalid")
    if stored_samples % channels or total_samples < finite_samples:
        raise Refusal("sample_frame_or_count_invalid")
    if nonfinite_samples != 0 or finite_samples != total_samples or not 0 <= nonzero_samples <= finite_samples:
        raise Refusal("finite_sample_contract_failed")
    if bool(metadata.get("truncated")) != (stored_samples < total_samples):
        raise Refusal("truncation_flag_mismatch")
    generation = str(metadata.get("generation", ""))
    if not generation.isdecimal() or int(generation) == 0:
        raise Refusal("capture_generation_invalid")
    capture_id = metadata.get("capture_id")
    if not isinstance(capture_id, str) or re.fullmatch(r"[0-9a-f]{32}", capture_id) is None:
        raise Refusal("capture_id_invalid")
    pair_stem = f"capture-v1-{capture_id}-{int(generation):016x}"
    if raw_path.name != pair_stem + ".f32le" or metadata_path.name != pair_stem + ".json":
        raise Refusal("capture_pair_filename_mismatch")

    try:
        if raw_path.stat().st_size != stored_samples * 4:
            raise Refusal("raw_sample_byte_count_mismatch")
        with raw_path.open("rb") as stream:
            raw = stream.read(stored_samples * 4 + 1)
    except OSError as error:
        raise Refusal("raw_samples_unreadable") from error
    if len(raw) != stored_samples * 4:
        raise Refusal("raw_sample_byte_count_mismatch")
    raw_hash = hashlib.sha256(raw).hexdigest()
    if metadata.get("raw_sha256") != raw_hash:
        raise Refusal("raw_sample_hash_mismatch")
    values = [item[0] for item in struct.iter_unpack("<f", raw)]
    if len(values) != stored_samples or any(not math.isfinite(value) for value in values):
        raise Refusal("raw_samples_invalid")
    prefix_peak = max(abs(value) for value in values)
    prefix_rms = math.sqrt(sum(value * value for value in values) / len(values))
    expected_peak = _finite_float(metadata.get("stored_prefix_peak_abs"), "stored_prefix_peak_abs")
    expected_rms = _finite_float(metadata.get("stored_prefix_rms"), "stored_prefix_rms")
    window_peak = _finite_float(metadata.get("window_peak_abs"), "window_peak_abs")
    window_rms = _finite_float(metadata.get("window_rms"), "window_rms")
    if not math.isclose(prefix_peak, expected_peak, rel_tol=1e-5, abs_tol=1e-6):
        raise Refusal("prefix_peak_mismatch")
    if not math.isclose(prefix_rms, expected_rms, rel_tol=1e-5, abs_tol=1e-6):
        raise Refusal("prefix_rms_mismatch")
    if stored_samples == total_samples and (
        not math.isclose(prefix_peak, window_peak, rel_tol=1e-5, abs_tol=1e-6) or not math.isclose(prefix_rms, window_rms, rel_tol=1e-5, abs_tol=1e-6)
    ):
        raise Refusal("complete_window_meter_mismatch")
    prefix_nonzero = sum(value != 0.0 for value in values)
    if (stored_samples < total_samples and prefix_nonzero > nonzero_samples) or (stored_samples == total_samples and prefix_nonzero != nonzero_samples):
        raise Refusal("prefix_nonzero_count_mismatch")
    if not raw:
        raise Refusal("empty_waveform_refused")
    return metadata, raw, prefix_peak, prefix_rms


def _wave_bytes(raw: bytes, channels: int, sample_rate: int) -> bytes:
    block_align = channels * 4
    byte_rate = sample_rate * block_align
    fmt = struct.pack("<HHIIHH", 3, channels, sample_rate, byte_rate, block_align, 32)
    data_chunk = b"data" + struct.pack("<I", len(raw)) + raw
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body = fmt_chunk + data_chunk
    if len(body) > 0xFFFFFFFF - 4:
        raise Refusal("riff_size_overflow")
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body


def export_capture(
    raw_path: Path,
    metadata_path: Path,
    output_dir: Path,
    expected_output_id: str,
    expected_apk_sha256: str,
) -> tuple[Path, Path]:
    if not (len(expected_apk_sha256) == 64 and all(c in "0123456789abcdef" for c in expected_apk_sha256)):
        raise Refusal("expected_apk_hash_invalid")
    metadata, raw, peak, rms = inspect_capture(raw_path, metadata_path, expected_output_id)
    if output_dir.is_symlink():
        raise Refusal("output_directory_symlink_refused")
    output_dir.mkdir(parents=True, exist_ok=True)
    root = output_dir.resolve()
    stem = f"pcm-capture-{metadata['capture_id']}-{metadata['generation']}"
    wav_path = root / f"{stem}.wav"
    receipt_path = root / f"{stem}.receipt.json"
    if wav_path.exists() or receipt_path.exists() or wav_path.is_symlink() or receipt_path.is_symlink():
        raise Refusal("output_path_preexisting")
    wav = _wave_bytes(raw, int(metadata["channels"]), int(metadata["sample_rate_hz"]))
    receipt = {
        "schema": "ror2lab-passive-pcm-wave-export-r1",
        "apk_sha256": expected_apk_sha256,
        "readback_abi": EXPECTED_ABI,
        "generation": str(metadata["generation"]),
        "capture_id": metadata["capture_id"],
        "output_id": expected_output_id,
        "sample_rate_hz": int(metadata["sample_rate_hz"]),
        "channels": int(metadata["channels"]),
        "channel_mask": int(metadata["channel_mask"]),
        "total_samples": str(metadata["total_samples"]),
        "stored_samples": int(metadata["stored_samples"]),
        "waveform_truncated": bool(metadata["truncated"]),
        "original_engine_term_returned": True,
        "original_callback_manager_term_returned": True,
        "post_term_disarm_verified": True,
        "prefix_peak_abs": peak,
        "prefix_rms": rms,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "wav_sha256": hashlib.sha256(wav).hexdigest(),
        "event_attributed": False,
        "physical_audibility_claim": False,
    }
    # Create-new semantics prevent replacement of any evidence artifact.
    created_wav = False
    try:
        with wav_path.open("xb") as stream:
            created_wav = True
            stream.write(wav)
        with receipt_path.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except Exception as error:
        if created_wav:
            try:
                wav_path.unlink()
            except OSError:
                pass
        raise Refusal("output_creation_failed") from error
    return wav_path, receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-output-id", required=True)
    parser.add_argument("--expected-apk-sha256", required=True)
    args = parser.parse_args()
    try:
        # Generated game audio and its receipts stay in the ignored workspace.
        # Library callers may supply authored synthetic fixtures elsewhere.
        work = (Path(__file__).resolve().parents[2] / "work").resolve()
        if any(not path.resolve().is_relative_to(work) for path in (args.raw, args.metadata, args.output_dir)):
            raise Refusal("capture_paths_must_be_under_ignored_work")
        wav, receipt = export_capture(
            args.raw,
            args.metadata,
            args.output_dir,
            args.expected_output_id,
            args.expected_apk_sha256,
        )
    except Refusal as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "wav": str(wav),
                "receipt": str(receipt),
                "physical_audibility_claim": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
