from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/lab/original_game_audio_produce.py"
SPEC = importlib.util.spec_from_file_location("audio_producer", SCRIPT)
assert SPEC and SPEC.loader
producer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer)


def fixture_manifest(root: Path) -> tuple[dict, dict[str, Path]]:
    names = {
        "raw_game": "accepted-game.dll",
        "raw_api": "accepted-api.dll",
        "adapted_api": "api-adapted.dll",
        "observed_api": "api-observed.dll",
        "composed_api": "api-instrumented-composed.dll",
        "guarded_game": "game-optional-presentation-guarded.dll",
        "composed_game": "game-original-owner-composed.dll",
    }
    hashes: dict[str, str] = {}
    outputs: dict[str, Path] = {}
    sources = {}
    for role, filename in names.items():
        path = root / "synthetic-chain" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic authored chain output: {role}".encode())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[role] = digest
        outputs[f"synthetic-chain/{filename}"] = path
        sources[role] = digest
    manifest = {
        "schema": "game-audio-original-public-producer-r1",
        "accepted_input_id": producer.LINEAGE["accepted_input_id"],
        "source_input_hashes": sources,
        "android_abi_input_hashes": {
            "arm64_release_native_plugin": producer.ABI_NATIVE_PLUGIN_SHA256,
            "generated_android_source": producer.ABI_GENERATED_SOURCE_SHA256,
            "handwritten_android_source": producer.ABI_HANDWRITTEN_SOURCE_SHA256,
            "llvm_nm": producer.ABI_LLVM_NM_SHA256,
        },
        "request": {"requested": False, "stage_to_apk_binding": False, "dispatch_ready": False},
        "outputs_relative_to_work": {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in outputs.items()},
    }
    return manifest, outputs


class ProducerManifestTests(unittest.TestCase):
    def temporary_directory(self):
        return tempfile.TemporaryDirectory()

    def test_all_managed_outputs_join_to_the_accepted_chain(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, outputs = fixture_manifest(root)
            lineage = {
                "accepted_game_sha256": manifest["source_input_hashes"]["raw_game"],
                "raw_api_sha256": manifest["source_input_hashes"]["raw_api"],
                "adapted_api_sha256": manifest["source_input_hashes"]["adapted_api"],
                "observed_api_sha256": manifest["source_input_hashes"]["observed_api"],
                "composed_api_sha256": manifest["source_input_hashes"]["composed_api"],
                "guarded_game_input_sha256": manifest["source_input_hashes"]["guarded_game"],
                "composed_game_sha256": manifest["source_input_hashes"]["composed_game"],
            }
            with mock.patch.dict(producer.LINEAGE, lineage):
                joined = producer.verify_managed_output_manifest(manifest, root)
            self.assertEqual(set(outputs), set(joined))
            self.assertEqual("api-instrumented-composed.dll", next(p.name for p in joined.values() if p.name == "api-instrumented-composed.dll"))

    def test_managed_output_bytes_must_match_the_manifest(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, outputs = fixture_manifest(root)
            lineage = {
                "accepted_game_sha256": manifest["source_input_hashes"]["raw_game"],
                "raw_api_sha256": manifest["source_input_hashes"]["raw_api"],
                "adapted_api_sha256": manifest["source_input_hashes"]["adapted_api"],
                "observed_api_sha256": manifest["source_input_hashes"]["observed_api"],
                "composed_api_sha256": manifest["source_input_hashes"]["composed_api"],
                "guarded_game_input_sha256": manifest["source_input_hashes"]["guarded_game"],
                "composed_game_sha256": manifest["source_input_hashes"]["composed_game"],
            }
            outputs["synthetic-chain/api-adapted.dll"].write_bytes(b"changed after producer receipt")
            with mock.patch.dict(producer.LINEAGE, lineage), self.assertRaisesRegex(ValueError, "manifest hash"):
                producer.verify_managed_output_manifest(manifest, root)

    def test_request_mode_and_path_escape_are_refused(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _ = fixture_manifest(root)
            lineage = {
                "accepted_game_sha256": manifest["source_input_hashes"]["raw_game"],
                "raw_api_sha256": manifest["source_input_hashes"]["raw_api"],
                "adapted_api_sha256": manifest["source_input_hashes"]["adapted_api"],
                "observed_api_sha256": manifest["source_input_hashes"]["observed_api"],
                "composed_api_sha256": manifest["source_input_hashes"]["composed_api"],
                "guarded_game_input_sha256": manifest["source_input_hashes"]["guarded_game"],
                "composed_game_sha256": manifest["source_input_hashes"]["composed_game"],
            }
            with mock.patch.dict(producer.LINEAGE, lineage):
                enabled = {**manifest, "request": {"requested": True}}
                with self.assertRaisesRegex(ValueError, "non-default request state"):
                    producer.verify_managed_output_manifest(enabled, root)
                escaped = dict(manifest)
                escaped["outputs_relative_to_work"] = {"../outside.dll": "0" * 64}
                with self.assertRaisesRegex(ValueError, "unsafe output path"):
                    producer.verify_managed_output_manifest(escaped, root)


if __name__ == "__main__":
    unittest.main()
