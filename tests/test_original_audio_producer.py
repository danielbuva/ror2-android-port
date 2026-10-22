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
        "point_sound_composed_game": "game-original-owner-point-sound-composed.dll",
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

    def test_new_native_output_pin_replaces_old_pin_for_producer_artifacts(self):
        self.assertEqual(
            "9075b5a4d3718a209eb244760d2b251a59ef2f5c486a2d2fc0e83b90240cbba3",
            producer.LINEAGE["native_library_sha256"],
        )
        self.assertNotEqual(
            "bb5879b4eb38b81dc3830a1662ba467b60b595e7fedb88a1301d3161f8ab9304",
            producer.LINEAGE["native_library_sha256"],
        )

    def test_actual_current_pair_accepts_game_only_transform_with_same_api(self):
        current_api = producer.LINEAGE["composed_api_sha256"]
        current_game = producer.LINEAGE["composed_game_sha256"]
        predecessor_api = producer.PREVIOUS_COMPOSED_API_SHA256
        predecessor_game = producer.PREVIOUS_COMPOSED_GAME_SHA256
        self.assertNotEqual(predecessor_api, current_api)
        self.assertNotEqual(predecessor_game, current_game)
        self.assertEqual("current-audio", producer.classify_project_pair(current_api, current_game))
        self.assertEqual(
            "previous-audio-restore-only",
            producer.classify_project_pair(current_api, producer.PREVIOUS_R10_GAME_SHA256),
        )
        self.assertEqual("previous-audio-restore-only", producer.classify_project_pair(current_api, producer.PREVIOUS_R10_GAME_SHA256))
        self.assertEqual("previous-audio", producer.classify_project_pair(predecessor_api, predecessor_game))
        self.assertEqual("older-previous-audio", producer.classify_project_pair(predecessor_api, producer.OLDER_PREVIOUS_GAME_SHA256))
        with self.assertRaisesRegex(ValueError, "neither ordinary guarded"):
            producer.classify_project_pair(producer.OLDER_RESTORE_API_SHA256, predecessor_game)

    def test_only_declared_ordinary_previous_and_current_pairs_are_accepted(self):
        current_api = "c" * 64
        old_api = producer.OLDER_RESTORE_API_SHA256
        predecessor_api = producer.PREVIOUS_COMPOSED_API_SHA256
        game = producer.LINEAGE["composed_game_sha256"]
        old_game = producer.OLDER_PREVIOUS_GAME_SHA256
        with mock.patch.dict(producer.LINEAGE, {"composed_api_sha256": current_api}):
            self.assertEqual("ordinary", producer.classify_project_pair(producer.DEFAULT_API_SHA256, producer.DEFAULT_GAME_SHA256))
            self.assertEqual("older-restore-only", producer.classify_project_pair(old_api, old_game))
            self.assertEqual("older-previous-audio", producer.classify_project_pair(predecessor_api, producer.OLDER_PREVIOUS_GAME_SHA256))
            self.assertEqual("older-previous-audio", producer.classify_project_pair(predecessor_api, old_game))
            self.assertEqual("current-audio", producer.classify_project_pair(current_api, game))
            self.assertEqual(
                "previous-audio-restore-only",
                producer.classify_project_pair(current_api, producer.PREVIOUS_R10_GAME_SHA256),
            )
            self.assertEqual("legacy-restore-only", producer.classify_project_pair(producer.LEGACY_RESTORE_API_SHA256, old_game))
            with self.assertRaisesRegex(ValueError, "neither ordinary guarded"):
                producer.classify_project_pair("d" * 64, game)
            with self.assertRaisesRegex(ValueError, "neither ordinary guarded"):
                producer.classify_project_pair(old_api, "e" * 64)
        with mock.patch.dict(producer.LINEAGE, {"composed_api_sha256": "ROOT_MUST_FILL_CURRENT_COMPOSED_API_SHA256"}):
            with self.assertRaisesRegex(ValueError, "pin is unfilled"):
                producer.classify_project_pair(producer.DEFAULT_API_SHA256, producer.DEFAULT_GAME_SHA256)

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
                "composed_game_sha256": manifest["source_input_hashes"]["point_sound_composed_game"],
            }
            with (
                mock.patch.dict(producer.LINEAGE, lineage),
                mock.patch.object(producer, "CURRENT_COMPOSED_GAME_SHA256", manifest["source_input_hashes"]["composed_game"]),
            ):
                joined = producer.verify_managed_output_manifest(manifest, root)
            self.assertEqual(set(outputs), set(joined))
            self.assertEqual("api-instrumented-composed.dll", next(p.name for p in joined.values() if p.name == "api-instrumented-composed.dll"))
            self.assertIn("game-original-owner-point-sound-composed.dll", {p.name for p in joined.values()})

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
                "composed_game_sha256": manifest["source_input_hashes"]["point_sound_composed_game"],
            }
            outputs["synthetic-chain/api-adapted.dll"].write_bytes(b"changed after producer receipt")
            with (
                mock.patch.dict(producer.LINEAGE, lineage),
                mock.patch.object(producer, "CURRENT_COMPOSED_GAME_SHA256", manifest["source_input_hashes"]["composed_game"]),
                self.assertRaisesRegex(ValueError, "manifest hash"),
            ):
                producer.verify_managed_output_manifest(manifest, root)

    def test_frozen_pipeline_sources_match_the_exact_manifest_pins(self) -> None:
        for relative, expected in producer.OWNER_SOURCE_HASHES.items():
            path = producer.SOURCE / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(expected, hashlib.sha256(path.read_bytes()).hexdigest(), relative)
        generator_path = producer.TOOLS / "generate_accepted_request_pin.py"
        self.assertEqual(producer.REQUEST_PIN_TOOL_SHA256, hashlib.sha256(generator_path.read_bytes()).hexdigest())
        managed = producer.SOURCE / "managed-producer/produce.py"
        self.assertEqual(producer.MANAGED_PRODUCER_SHA256, hashlib.sha256(managed.read_bytes()).hexdigest())

    def test_owner_recipe_matches_both_producer_and_camera_pins(self) -> None:
        recipe = ROOT / "recipe/original-audio-owner-sources.json"
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        camera_spec = importlib.util.spec_from_file_location("camera_owner_recipe_contract", ROOT / "scripts/lab/native_view_camera_build_hook.py")
        assert camera_spec and camera_spec.loader
        camera = importlib.util.module_from_spec(camera_spec)
        camera_spec.loader.exec_module(camera)
        self.assertEqual(digest, producer.OWNER_ANCESTOR_MANIFEST_SHA256)
        self.assertEqual(digest, camera.HASHES["r4_manifest_sha256"])
        self.assertEqual(json.loads(recipe.read_text())["owner_source_hashes"], producer.OWNER_SOURCE_HASHES)
        producer.validate_owner_source_manifest()

    def test_owner_recipe_refuses_changed_bytes_or_mismatched_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            recipe = root / "recipe/original-audio-owner-sources.json"
            recipe.parent.mkdir()
            recipe.write_text(json.dumps({"owner_source_hashes": {"changed.cs": "wrong"}}))
            with mock.patch.object(producer, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "pinned manifest"):
                    producer.validate_owner_source_manifest()
                with mock.patch.object(producer, "OWNER_ANCESTOR_MANIFEST_SHA256", producer.sha256(recipe)):
                    with self.assertRaisesRegex(ValueError, "producer cohort"):
                        producer.validate_owner_source_manifest()

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
                "composed_game_sha256": manifest["source_input_hashes"]["point_sound_composed_game"],
            }
            with (
                mock.patch.dict(producer.LINEAGE, lineage),
                mock.patch.object(producer, "CURRENT_COMPOSED_GAME_SHA256", manifest["source_input_hashes"]["composed_game"]),
            ):
                enabled = {**manifest, "request": {"requested": True}}
                with self.assertRaisesRegex(ValueError, "non-default request state"):
                    producer.verify_managed_output_manifest(enabled, root)
                escaped = dict(manifest)
                escaped["outputs_relative_to_work"] = {"../outside.dll": "0" * 64}
                with self.assertRaisesRegex(ValueError, "unsafe output path"):
                    producer.verify_managed_output_manifest(escaped, root)


if __name__ == "__main__":
    unittest.main()
