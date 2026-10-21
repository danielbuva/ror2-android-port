from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/lab/original_game_audio_stage.py"
SPEC = importlib.util.spec_from_file_location("audio_stage", SCRIPT)
assert SPEC and SPEC.loader
stage_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_module)

ACCEPTED = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
DEFAULT_ROLES = list(stage_module.DEFAULT_ROLES)


def write_set(root: Path, requested: bool, roles: list[str] | None = None) -> tuple[Path, Path | None, Path | None]:
    if roles is None:
        roles = DEFAULT_ROLES + (["api", "game", "native"] + ["banks"] * 154 if requested else [])
    rows_to_write = [(role, index) for index, role in enumerate(roles)]
    rows_to_write.extend(("metadata", index) for index in range(3 + int(requested)))
    outputs = []
    native_hash = None
    bank_outputs = []
    for role, index in rows_to_write:
        relative = f"out/{role}-{index}.bin"
        data = f"synthetic authored test fixture {role} {index}".encode()
        bank_filename = "Init.bnk" if not bank_outputs else f"Bank-{len(bank_outputs):03}.bnk"
        metadata_target = sorted(stage_module.NEW_ASSEMBLY_META | ({stage_module.NATIVE_META} if requested else set()))[index] if role == "metadata" else None
        if metadata_target:
            guid = hashlib.sha256(metadata_target.encode()).hexdigest()[:32]
            data = f"fileFormatVersion: 2\nguid: {guid}\nPluginImporter:\n  serializedVersion: 2\n".encode()
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        output = {
            "role": role,
            "source": relative,
            "target": (
                f"Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android/{bank_filename}"
                if role == "banks"
                else "Assets/Plugins/Android/arm64-v8a/libAkSoundEngine.so"
                if role == "native"
                else metadata_target
                if role == "metadata"
                else stage_module.DEFAULT_TARGETS[role]
                if role in stage_module.DEFAULT_TARGETS
                else f"Assets/Plugins/OriginalAudio/{role}.bin"
            ),
            "sha256": hashlib.sha256(data).hexdigest(),
            "requires_request": role in {"native", "banks"},
        }
        if role == "banks":
            output["filename"] = bank_filename
            output["size_bytes"] = len(data)
            bank_outputs.append({key: output[key] for key in ("filename", "sha256", "size_bytes")})
        outputs.append(output)
        if role == "native":
            native_hash = outputs[-1]["sha256"]
    request = {
        "schema": "game-audio-original-runtime-request-r2",
        "requested": requested,
        "request_id": "0123456789abcdef0123456789abcdef" if requested else "",
        "build_input_contract_sha256": "a" * 64 if requested else "",
    }
    lineage = dict(stage_module.LINEAGE)
    receipt_path = None
    if requested:
        receipt_path = root / "stage-receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "schema": "original-game-wwise-bank-cohort-r1",
                    "accepted_input_id": ACCEPTED,
                    "requested_banks": 153,
                    "outputs": bank_outputs,
                }
            ),
            encoding="utf-8",
        )
        lineage["stage_receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    if requested and native_hash:
        lineage["native_library_sha256"] = native_hash
    manifest = {
        "schema": stage_module.SCHEMA,
        "artifact_set_id": "synthetic-fixture",
        "accepted_input_id": ACCEPTED,
        "lineage": lineage,
        "request": request,
        "outputs": outputs,
        "runtime_accepted": False,
        "audible": False,
    }
    manifest_path = root / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    request_path = None
    if requested:
        request_path = root / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
    return manifest_path, request_path, receipt_path


class StageTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repository = Path(scratch.name).resolve()
        self.work = self.repository / "work"
        self.work.mkdir()
        patcher = mock.patch.object(stage_module, "ROOT", self.repository)
        patcher.start()
        self.addCleanup(patcher.stop)

    def temporary_directory(self):
        return tempfile.TemporaryDirectory(dir=self.work)

    def test_default_off_stages_compile_owners_without_audio_payload(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False)
            project = root / "project"
            project.mkdir()
            receipt = stage_module.stage(project, manifest, None, None)
            self.assertFalse(receipt["requested"])
            expected_owner_targets = {stage_module.DEFAULT_TARGETS[role] for role in stage_module.DEFAULT_ROLES}
            self.assertTrue(expected_owner_targets.issubset({row["target"] for row in receipt["outputs"]}))
            self.assertFalse((project / "Assets/Plugins/OriginalAudio/native.bin").exists())
            self.assertFalse((project / "Assets/Plugins/OriginalAudio/banks.bin").exists())
            self.assertFalse(receipt["runtime_accepted"])
            self.assertFalse(receipt["audible"])

    def test_requested_variant_requires_matching_request_and_payload_roles(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, stage_receipt = write_set(root, True)
            project = root / "project"
            project.mkdir()
            lineage = json.loads(manifest.read_text())["lineage"]
            with mock.patch.dict(
                stage_module.LINEAGE, {"native_library_sha256": lineage["native_library_sha256"], "stage_receipt_sha256": lineage["stage_receipt_sha256"]}
            ):
                receipt = stage_module.stage(project, manifest, request, stage_receipt)
            self.assertTrue(receipt["requested"])
            self.assertEqual("0123456789abcdef0123456789abcdef", receipt["request_id"])
            self.assertEqual(164, len(receipt["outputs"]))

    def test_default_off_rejects_opt_in_native_or_bank_bytes(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False, [*DEFAULT_ROLES, "native"])
            with self.assertRaisesRegex(ValueError, "opt-in output"):
                stage_module.read_artifacts(manifest, None, None)

    def test_default_off_can_restore_only_the_exact_prior_audio_pair(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest_path, _, _ = write_set(root, False)
            manifest = json.loads(manifest_path.read_text())
            for role, target, preimage in (
                ("restore_api", stage_module.DEFAULT_TARGETS["api"], stage_module.LINEAGE["composed_api_sha256"]),
                ("restore_game", stage_module.DEFAULT_TARGETS["game"], stage_module.LINEAGE["composed_game_sha256"]),
            ):
                relative = f"out/{role}.dll"
                source = root / relative
                source.write_bytes(("ordinary migration output " + role).encode())
                manifest["outputs"].append(
                    {
                        "role": role,
                        "source": relative,
                        "target": target,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "preimage_sha256": preimage,
                        "requires_request": False,
                    }
                )
            manifest_path.write_text(json.dumps(manifest))
            project = root / "project"
            for role in ("api", "game"):
                target = project / stage_module.DEFAULT_TARGETS[role]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(("prior audio " + role).encode())
                restore_role = f"restore_{role}"
                next(row for row in manifest["outputs"] if row["role"] == restore_role)["preimage_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            restore_hashes = {
                "restore_api": hashlib.sha256((root / "out/restore_api.dll").read_bytes()).hexdigest(),
                "restore_game": hashlib.sha256((root / "out/restore_game.dll").read_bytes()).hexdigest(),
            }
            with mock.patch.dict(stage_module.RESTORE_HASHES, restore_hashes):
                receipt = stage_module.stage(project, manifest_path, None, None)
            self.assertFalse(receipt["requested"])
            for role in ("api", "game"):
                target = project / stage_module.DEFAULT_TARGETS[role]
                expected = next(row["sha256"] for row in manifest["outputs"] if row["role"] == f"restore_{role}")
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)

    def test_owned_requested_generation_can_return_to_default_off(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            requested, request, bank_receipt = write_set(root, True)
            assert request is not None and bank_receipt is not None
            requested_doc = json.loads(requested.read_text())
            requested_outputs = requested_doc["outputs"]
            native_hash = next(row["sha256"] for row in requested_outputs if row["role"] == "native")
            api_hash = next(row["sha256"] for row in requested_outputs if row["role"] == "api")
            game_hash = next(row["sha256"] for row in requested_outputs if row["role"] == "game")
            requested_doc["lineage"]["native_library_sha256"] = native_hash
            requested_doc["lineage"]["stage_receipt_sha256"] = hashlib.sha256(bank_receipt.read_bytes()).hexdigest()
            requested_doc["lineage"]["composed_api_sha256"] = api_hash
            requested_doc["lineage"]["composed_game_sha256"] = game_hash
            requested.write_text(json.dumps(requested_doc))
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(
                stage_module.LINEAGE,
                {
                    "native_library_sha256": native_hash,
                    "stage_receipt_sha256": hashlib.sha256(bank_receipt.read_bytes()).hexdigest(),
                    "composed_api_sha256": api_hash,
                    "composed_game_sha256": game_hash,
                },
            ):
                stage_module.stage(project, requested, request, bank_receipt)
                sidecar = project / "Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android/Init.bnk.meta"
                sidecar.write_text("fileFormatVersion: 2\nguid: 1234567890abcdef1234567890abcdef\nDefaultImporter: {}\n")
                sidecar_before = sidecar.read_bytes()

                default_off, _, _ = write_set(root / "next", False)
                default_doc = json.loads(default_off.read_text())
                default_doc["lineage"].update(
                    {
                        "native_library_sha256": native_hash,
                        "stage_receipt_sha256": hashlib.sha256(bank_receipt.read_bytes()).hexdigest(),
                        "composed_api_sha256": api_hash,
                        "composed_game_sha256": game_hash,
                    }
                )
                for role, target, preimage in (
                    ("restore_api", stage_module.DEFAULT_TARGETS["api"], api_hash),
                    ("restore_game", stage_module.DEFAULT_TARGETS["game"], game_hash),
                ):
                    relative = f"out/{role}.dll"
                    source = default_off.parent / relative
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_bytes(("ordinary migration output " + role).encode())
                    default_doc["outputs"].append(
                        {
                            "role": role,
                            "source": relative,
                            "target": target,
                            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                            "preimage_sha256": preimage,
                            "requires_request": False,
                        }
                    )
                default_off.write_text(json.dumps(default_doc))
                restore_hashes = {
                    f"restore_{role}": next(row["sha256"] for row in default_doc["outputs"] if row["role"] == f"restore_{role}") for role in ("api", "game")
                }
                with mock.patch.dict(stage_module.RESTORE_HASHES, restore_hashes):
                    receipt = stage_module.stage(project, default_off, None, None)

            self.assertFalse(receipt["requested"])
            self.assertFalse((project / stage_module.NATIVE_TARGET).exists())
            self.assertFalse((project / stage_module.NATIVE_META).exists())
            bank_root = project / "Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android"
            self.assertEqual([sidecar], list(bank_root.iterdir()))
            self.assertEqual(sidecar_before, sidecar.read_bytes())
            for role in ("api", "game"):
                target = project / stage_module.DEFAULT_TARGETS[role]
                expected = next(row["sha256"] for row in default_doc["outputs"] if row["role"] == f"restore_{role}")
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)

    def test_unreceipted_native_payload_is_never_removed(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False)
            project = root / "project"
            native = project / stage_module.NATIVE_TARGET
            native.parent.mkdir(parents=True)
            native.write_bytes(b"unowned native")
            with self.assertRaisesRegex(ValueError, "unreceipted"):
                stage_module.stage(project, manifest, None, None)
            self.assertEqual(native.read_bytes(), b"unowned native")

    def test_true_request_refuses_contract_or_identity_drift(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, _ = write_set(root, True)
            assert request is not None
            document = json.loads(request.read_text())
            document["request_id"] = "f" * 32
            request.write_text(json.dumps(document))
            native_hash = json.loads(manifest.read_text())["lineage"]["native_library_sha256"]
            stage_hash = json.loads(manifest.read_text())["lineage"]["stage_receipt_sha256"]
            with mock.patch.dict(stage_module.LINEAGE, {"native_library_sha256": native_hash, "stage_receipt_sha256": stage_hash}):
                with self.assertRaisesRegex(ValueError, "identity"):
                    stage_module.read_artifacts(manifest, request, Path(temp) / "stage-receipt.json")

    def test_changed_artifact_bytes_are_refused_before_project_write(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False)
            rows = json.loads(manifest.read_text())["outputs"]
            core_source = next(row["source"] for row in rows if row["role"] == "core")
            (root / core_source).write_bytes(b"changed")
            project = root / "project"
            project.mkdir()
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                stage_module.stage(project, manifest, None, None)
            self.assertFalse((project / "Assets/Plugins/OriginalAudio/core.bin").exists())

    def test_unexpected_project_preimage_is_refused_before_any_write(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False)
            rows = json.loads(manifest.read_text())["outputs"]
            core_row = next(row for row in rows if row["role"] == "core")
            project = root / "project"
            target = project / core_row["target"]
            target.parent.mkdir(parents=True)
            target.write_bytes(b"unowned target")
            with self.assertRaisesRegex(ValueError, "target drift"):
                stage_module.stage(project, manifest, None, None)
            self.assertFalse((project / "Assets/Plugins/OriginalAudio/core.bin").exists())


if __name__ == "__main__":
    unittest.main()
