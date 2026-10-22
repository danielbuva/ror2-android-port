from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/lab/original_game_audio_stage.py"
SPEC = importlib.util.spec_from_file_location("audio_stage", SCRIPT)
assert SPEC and SPEC.loader
stage_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_module)
TEST_CURRENT_API_SHA256 = "c" * 64
stage_module.LINEAGE["composed_api_sha256"] = TEST_CURRENT_API_SHA256
stage_module.ALLOWED_RESTORE_PREIMAGES["restore_api"] = frozenset(
    {stage_module.LEGACY_RESTORE_API_SHA256, stage_module.PREVIOUS_COMPOSED_API_SHA256, TEST_CURRENT_API_SHA256}
)

ACCEPTED = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
DEFAULT_ROLES = list(stage_module.DEFAULT_ROLES)


def write_set(root: Path, requested: bool, roles: list[str] | None = None, *, music_output_requested: bool = False) -> tuple[Path, Path | None, Path | None]:
    if roles is None:
        roles = DEFAULT_ROLES + (["api", "game", "native"] + ["banks"] * 154 + ["streamed_media"] * stage_module.STREAMED_MEDIA_COUNT if requested else [])
    rows_to_write = [(role, index) for index, role in enumerate(roles)]
    rows_to_write.extend(("metadata", index) for index in range(3 + int(requested)))
    outputs = []
    native_hash = None
    bank_outputs = []
    media_outputs = []
    for role, index in rows_to_write:
        relative = f"out/{role}-{index}.bin"
        data = f"synthetic authored test fixture {role} {index}".encode()
        bank_filename = "Init.bnk" if not bank_outputs else f"Bank-{len(bank_outputs):03}.bnk"
        media_id = 700000 + len(media_outputs) if role == "streamed_media" else None
        media_relative = f"Media/{media_id}.wem" if media_id is not None else None
        metadata_target = sorted(stage_module.NEW_ASSEMBLY_META | ({stage_module.NATIVE_META} if requested else set()))[index] if role == "metadata" else None
        if metadata_target:
            guid = hashlib.sha256(metadata_target.encode()).hexdigest()[:32]
            data = f"fileFormatVersion: 2\nguid: {guid}\nPluginImporter:\n  serializedVersion: 2\n".encode()
        elif role == "streamed_media":
            data = f"synthetic streamed media fixture {media_id}".encode()
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        output = {
            "role": role,
            "source": relative,
            "target": (
                f"Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android/{bank_filename}"
                if role == "banks"
                else f"{stage_module.ANDROID_BANK_ROOT}/{media_relative}"
                if role == "streamed_media"
                else "Assets/Plugins/Android/arm64-v8a/libAkSoundEngine.so"
                if role == "native"
                else metadata_target
                if role == "metadata"
                else stage_module.DEFAULT_TARGETS[role]
                if role in stage_module.DEFAULT_TARGETS
                else f"Assets/Plugins/OriginalAudio/{role}.bin"
            ),
            "sha256": hashlib.sha256(data).hexdigest(),
            "requires_request": role in {"native", "banks", "streamed_media"},
        }
        if role == "banks":
            output["filename"] = bank_filename
            output["size_bytes"] = len(data)
            if bank_filename != "Init.bnk":
                output["requested_name"] = Path(bank_filename).stem
            bank_outputs.append(
                {key: output[key] for key in ("filename", "sha256", "size_bytes", *(("requested_name",) if bank_filename != "Init.bnk" else ()))}
            )
        if role == "streamed_media":
            output.update({"media_id": media_id, "relative_path": media_relative, "referenced_by": ["Bank-001"]})
            output["size_bytes"] = len(data)
            media_outputs.append({key: output[key] for key in ("media_id", "relative_path", "sha256", "size_bytes", "referenced_by")})
        outputs.append(output)
        if role == "native":
            native_hash = outputs[-1]["sha256"]
    request = {
        "schema": "game-audio-original-runtime-request-r3",
        "requested": requested,
        "passive_pcm_capture_requested": bool(requested and music_output_requested),
        "passive_pcm_capture_music_output_requested": music_output_requested,
        "request_id": "0123456789abcdef0123456789abcdef" if requested else "",
        "build_input_contract_sha256": "a" * 64 if requested else "",
    }
    lineage = dict(stage_module.LINEAGE)
    receipt_path = None
    if requested:
        receipt_path = root / "stage-receipt.json"
        receipt_pins = dict(stage_module.R2_RECEIPT_PINS)
        receipt_path.write_text(
            json.dumps(
                {
                    "schema": "original-game-wwise-bank-cohort-r2",
                    "accepted_input_id": ACCEPTED,
                    "requested_banks": 153,
                    **receipt_pins,
                    "outputs": bank_outputs,
                    "streamed_media": media_outputs,
                }
            ),
            encoding="utf-8",
        )
        receipt_bytes = receipt_path.read_bytes()
        receipt_source = root / "out/bank-receipt.json"
        receipt_source.parent.mkdir(parents=True, exist_ok=True)
        receipt_source.write_bytes(receipt_bytes)
        outputs.append(
            {
                "role": "bank_receipt",
                "source": "out/bank-receipt.json",
                "target": stage_module.BANK_RECEIPT_TARGET,
                "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                "requires_request": True,
            }
        )
        lineage["stage_receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        stage_module.R2_BANK_RECEIPT_SHA256 = lineage["stage_receipt_sha256"]
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

    def write_previous_default_off_receipt(self, project: Path, *, lineage: dict | None = None, ordinary_pair: bool = False) -> Path:
        outputs = []
        plugin_guids = {}
        targets = sorted({target for role, target in stage_module.DEFAULT_TARGETS.items() if role in stage_module.DEFAULT_ROLES})
        targets += sorted(target + ".meta" for target in targets)
        for index, target in enumerate(targets):
            path = project / target
            path.parent.mkdir(parents=True, exist_ok=True)
            if target.endswith(".meta"):
                guid = f"{index + 1:032x}"
                path.write_text(f"fileFormatVersion: 2\nguid: {guid}\nPluginImporter:\n", encoding="utf-8")
                plugin_guids[guid] = target
            else:
                path.write_bytes(f"old owned support output {index}".encode())
            outputs.append({"target": target, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "status": "staged"})
        if ordinary_pair:
            for role in ("api", "game"):
                target = stage_module.DEFAULT_TARGETS[role]
                path = project / target
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"synthetic ordinary {role}".encode())
                output_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                outputs.append({"target": target, "sha256": output_hash, "status": "staged"})
        receipt_path = project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(
                {
                    "schema": stage_module.RECEIPT_SCHEMA,
                    "accepted_input_id": stage_module.LINEAGE["accepted_input_id"],
                    "lineage": lineage or stage_module.PREVIOUS_LINEAGE,
                    "requested": False,
                    "request_id": None,
                    "request_sha256": None,
                    "artifact_manifest_sha256": "a" * 64,
                    "stage_receipt_sha256": None,
                    "plugin_guids": plugin_guids,
                    "outputs": outputs,
                }
            ),
            encoding="utf-8",
        )
        return receipt_path

    def test_known_old_lineage_owned_support_receipt_upgrades_to_current_generation(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            previous_path = self.write_previous_default_off_receipt(project)
            previous_hash = hashlib.sha256(previous_path.read_bytes()).hexdigest()
            manifest, _, _ = write_set(root, False)
            result = stage_module.stage(project, manifest, None, None)
            self.assertFalse(result["requested"])
            self.assertEqual(stage_module.LINEAGE, result["lineage"])
            self.assertNotEqual(previous_hash, hashlib.sha256(previous_path.read_bytes()).hexdigest())

    def test_r6_immediate_predecessor_lineage_is_exact_and_older_pairs_do_not_cross(self):
        self.assertEqual("d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23", stage_module.PREVIOUS_LINEAGE["composed_api_sha256"])
        self.assertEqual("6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc", stage_module.PREVIOUS_LINEAGE["composed_game_sha256"])
        self.assertEqual("1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c", stage_module.OLDER_PREVIOUS_LINEAGE["composed_game_sha256"])
        self.assertNotIn((stage_module.OLDER_RESTORE_API_SHA256, stage_module.PREVIOUS_COMPOSED_GAME_SHA256), stage_module.ALLOWED_RESTORE_PREIMAGE_PAIRS)
        self.assertNotIn((stage_module.LEGACY_RESTORE_API_SHA256, stage_module.PREVIOUS_COMPOSED_GAME_SHA256), stage_module.ALLOWED_RESTORE_PREIMAGE_PAIRS)

    def test_predecessor_lineage_differs_only_at_declared_composed_game_pin(self):
        differences = {key for key in stage_module.LINEAGE if stage_module.LINEAGE[key] != stage_module.PREVIOUS_LINEAGE.get(key)}
        self.assertEqual({"observed_api_sha256", "composed_api_sha256", "native_library_sha256"}, differences)
        self.assertEqual(
            "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
            stage_module.PREVIOUS_LINEAGE["composed_api_sha256"],
        )

    def test_five_previous_lineages_keep_bb_native_pin_while_current_uses_new_output(self):
        old_lineages = (
            stage_module.OLD_CURRENT_LINEAGE,
            stage_module.PREVIOUS_LINEAGE,
            stage_module.OLDER_PREVIOUS_LINEAGE,
            stage_module.OLDER_RESTORE_LINEAGE,
            stage_module.LEGACY_RESTORE_LINEAGE,
        )
        self.assertEqual(5, len(old_lineages))
        self.assertEqual(
            {"bb5879b4eb38b81dc3830a1662ba467b60b595e7fedb88a1301d3161f8ab9304"},
            {item["native_library_sha256"] for item in old_lineages},
        )
        self.assertEqual(
            "4f309b9df05392b7b78ea51c53955225f27400a83810e260441f65dfdc335498",
            stage_module.LINEAGE["native_library_sha256"],
        )

    def test_old_current_requested_receipt_upgrades_directly_to_new_native(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            old_manifest, old_request, old_receipt = write_set(root / "old", True)
            new_manifest, new_request, new_receipt = write_set(root / "new", True)
            self.assertIsNotNone(old_request)
            self.assertIsNotNone(old_receipt)
            self.assertIsNotNone(new_request)
            self.assertIsNotNone(new_receipt)
            old = json.loads(old_manifest.read_text())
            new = json.loads(new_manifest.read_text())
            for document in (old, new):
                api_hash = next(row["sha256"] for row in document["outputs"] if row["role"] == "api")
                game_hash = next(row["sha256"] for row in document["outputs"] if row["role"] == "game")
                document["lineage"]["composed_api_sha256"] = api_hash
                document["lineage"]["composed_game_sha256"] = game_hash
            old_native = next(row for row in old["outputs"] if row["role"] == "native")
            old_lineage = {
                **stage_module.OLD_CURRENT_LINEAGE,
                "composed_api_sha256": old["lineage"]["composed_api_sha256"],
                "composed_game_sha256": old["lineage"]["composed_game_sha256"],
                "native_library_sha256": old_native["sha256"],
                "stage_receipt_sha256": old["lineage"]["stage_receipt_sha256"],
            }
            old["lineage"] = old_lineage
            new_native = next(row for row in new["outputs"] if row["role"] == "native")
            new_native_path = new_manifest.parent / new_native["source"]
            new_native_path.write_bytes(b"new native selector output fixture")
            new_native["sha256"] = hashlib.sha256(new_native_path.read_bytes()).hexdigest()
            new_lineage = {
                **old_lineage,
                "native_library_sha256": new_native["sha256"],
                "stage_receipt_sha256": new["lineage"]["stage_receipt_sha256"],
            }
            new["lineage"] = new_lineage
            old_manifest.write_text(json.dumps(old))
            new_manifest.write_text(json.dumps(new))
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(stage_module.LINEAGE, old_lineage, clear=True):
                stage_module.stage(project, old_manifest, old_request, old_receipt)
            prior_receipt_path = project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
            with mock.patch.dict(stage_module.LINEAGE, new_lineage, clear=True), mock.patch.object(stage_module, "OLD_CURRENT_LINEAGE", old_lineage):
                result = stage_module.stage(project, new_manifest, new_request, new_receipt)
            self.assertTrue(result["requested"])
            self.assertEqual(new_lineage, result["lineage"])
            self.assertEqual(
                new_native_path.read_bytes(),
                (project / stage_module.NATIVE_TARGET).read_bytes(),
            )
            self.assertEqual(
                new_native["sha256"],
                next(row["sha256"] for row in result["outputs"] if row["target"] == stage_module.NATIVE_TARGET),
            )
            self.assertNotEqual(
                old_native["sha256"],
                new_native["sha256"],
            )
            self.assertTrue(prior_receipt_path.is_file())

    def test_9a_lineage_is_restore_only_and_migrates_to_current_default_off(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            self.write_previous_default_off_receipt(project, lineage=stage_module.OLDER_RESTORE_LINEAGE)
            manifest, _, _ = write_set(root, False)
            result = stage_module.stage(project, manifest, None, None)
            self.assertEqual(stage_module.LINEAGE, result["lineage"])
            self.assertFalse(result["requested"])

    def test_legacy_793_is_restore_only_and_cannot_start_new_optin(self):
        self.assertIn(stage_module.LEGACY_RESTORE_API_SHA256, stage_module.ALLOWED_RESTORE_PREIMAGES["restore_api"])
        self.assertNotIn("e" * 64, stage_module.ALLOWED_RESTORE_PREIMAGES["restore_api"])
        with self.temporary_directory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            previous = {"lineage": stage_module.LEGACY_RESTORE_LINEAGE}
            with (
                mock.patch.object(stage_module, "read_artifacts", return_value=({}, [], {"requested": True})),
                mock.patch.object(stage_module, "inspect_previous_stage", return_value=(previous, [])),
            ):
                with self.assertRaisesRegex(ValueError, "legacy 793 API lineage must be restored"):
                    stage_module.stage(project, root / "unused-manifest.json", None, None)

    def test_owned_requested_predecessor_upgrades_to_current_requested_bytes(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            old_manifest, old_request, old_banks = write_set(root / "old", True)
            new_manifest, new_request, new_banks = write_set(root / "new", True)
            old = json.loads(old_manifest.read_text())
            new = json.loads(new_manifest.read_text())
            old_api = next(row for row in old["outputs"] if row["role"] == "api")
            new_api = next(row for row in new["outputs"] if row["role"] == "api")
            new_bytes = b"authored current API fixture with repaired observer"
            (new_manifest.parent / new_api["source"]).write_bytes(new_bytes)
            new_api["sha256"] = hashlib.sha256(new_bytes).hexdigest()
            game = next(row["sha256"] for row in old["outputs"] if row["role"] == "game")
            prior_policy = {**old["lineage"], "composed_api_sha256": old_api["sha256"], "composed_game_sha256": game}
            current_policy = {**prior_policy, "composed_api_sha256": new_api["sha256"]}
            old["lineage"] = prior_policy
            new["lineage"] = current_policy
            old_manifest.write_text(json.dumps(old))
            new_manifest.write_text(json.dumps(new))
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(stage_module.LINEAGE, prior_policy, clear=True):
                stage_module.stage(project, old_manifest, old_request, old_banks)
            with mock.patch.dict(stage_module.LINEAGE, current_policy, clear=True), mock.patch.dict(stage_module.PREVIOUS_LINEAGE, prior_policy, clear=True):
                result = stage_module.stage(project, new_manifest, new_request, new_banks)
            self.assertTrue(result["requested"])
            self.assertEqual(current_policy, result["lineage"])
            self.assertEqual(new_bytes, (project / stage_module.DEFAULT_TARGETS["api"]).read_bytes())
            self.assertEqual(285, len(result["outputs"]))

    def test_old_lineage_default_off_receipt_may_own_only_exact_ordinary_pair(self):
        with self.temporary_directory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            # Synthetic fixture bytes stand in for the declared ordinary pair;
            # production pins remain the existing exact default API/game hashes.
            receipt_path = self.write_previous_default_off_receipt(project, ordinary_pair=True)
            receipt = json.loads(receipt_path.read_text())
            ordinary_hashes = {
                f"restore_{role}": next(row["sha256"] for row in receipt["outputs"] if row["target"] == stage_module.DEFAULT_TARGETS[role])
                for role in ("api", "game")
            }
            with mock.patch.dict(stage_module.RESTORE_HASHES, ordinary_hashes):
                previous, removal = stage_module.inspect_previous_stage(project, receipt_path)
            self.assertEqual(stage_module.PREVIOUS_LINEAGE, previous["lineage"])
            self.assertFalse(previous["requested"])
            self.assertEqual([], removal)

    def test_unknown_predecessor_lineage_and_output_drift_refuse_before_upgrade(self):
        for mutate in ("lineage", "output"):
            with self.subTest(mutate=mutate), self.temporary_directory() as temp:
                root = Path(temp)
                project = root / "project"
                project.mkdir()
                receipt_path = self.write_previous_default_off_receipt(project)
                receipt = json.loads(receipt_path.read_text())
                if mutate == "lineage":
                    receipt["lineage"]["observed_api_sha256"] = "f" * 64
                    receipt_path.write_text(json.dumps(receipt))
                else:
                    target = project / receipt["outputs"][0]["target"]
                    target.write_bytes(b"drift")
                with self.assertRaises(ValueError):
                    stage_module.inspect_previous_stage(project, receipt_path)

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
            manifest_document = json.loads(manifest.read_text())
            api_hash = next(row["sha256"] for row in manifest_document["outputs"] if row["role"] == "api")
            game_hash = next(row["sha256"] for row in manifest_document["outputs"] if row["role"] == "game")
            manifest_document["lineage"]["composed_api_sha256"] = api_hash
            manifest_document["lineage"]["composed_game_sha256"] = game_hash
            manifest.write_text(json.dumps(manifest_document))
            lineage = manifest_document["lineage"]
            with mock.patch.dict(
                stage_module.LINEAGE,
                {
                    "native_library_sha256": lineage["native_library_sha256"],
                    "stage_receipt_sha256": lineage["stage_receipt_sha256"],
                    "composed_api_sha256": api_hash,
                    "composed_game_sha256": game_hash,
                },
            ):
                receipt = stage_module.stage(project, manifest, request, stage_receipt)
            self.assertTrue(receipt["requested"])
            self.assertEqual("0123456789abcdef0123456789abcdef", receipt["request_id"])
            self.assertEqual(285, len(receipt["outputs"]))

    def test_stage_binds_music_output_selector_and_refuses_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            request = {
                "schema": "game-audio-original-runtime-request-r3",
                "requested": True,
                "request_id": "0123456789abcdef0123456789abcdef",
                "passive_pcm_capture_requested": True,
                "passive_pcm_capture_music_output_requested": True,
                "build_input_contract_sha256": "a" * 64,
            }
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            manifest = {
                "request": {
                    "requested": True,
                    "request_id": request["request_id"],
                    "passive_pcm_capture_requested": True,
                    "passive_pcm_capture_music_output_requested": True,
                    "build_input_contract_sha256": "a" * 64,
                }
            }
            pins = stage_module.verify_request(manifest, request_path)
            self.assertIs(pins["passive_pcm_capture_music_output_requested"], True)
            mismatched_manifest = {"request": {**manifest["request"], "passive_pcm_capture_music_output_requested": False}}
            with self.assertRaisesRegex(ValueError, "specific-output PCM selection differs"):
                stage_module.verify_request(mismatched_manifest, request_path)
            request["passive_pcm_capture_requested"] = False
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires passive PCM capture"):
                stage_module.verify_request(manifest, request_path)

    def test_requested_receipt_is_staged_and_present_at_payload_copy_url(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, bank_receipt = write_set(root, True, music_output_requested=True)
            assert request is not None and bank_receipt is not None
            manifest_doc = json.loads(manifest.read_text())
            lineage = manifest_doc["lineage"]
            for key in ("composed_api_sha256", "composed_game_sha256", "native_library_sha256", "stage_receipt_sha256"):
                if key in {"composed_api_sha256", "composed_game_sha256"}:
                    lineage[key] = next(row["sha256"] for row in manifest_doc["outputs"] if row["role"] == key.removesuffix("_sha256").replace("composed_", ""))
            manifest.write_text(json.dumps(manifest_doc))
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(
                stage_module.LINEAGE,
                {key: lineage[key] for key in ("composed_api_sha256", "composed_game_sha256", "native_library_sha256", "stage_receipt_sha256")},
            ):
                result = stage_module.stage(project, manifest, request, bank_receipt)
            self.assertTrue(result["passive_pcm_capture_music_output_requested"])
            expected = bank_receipt.read_bytes()
            packaged = project / stage_module.BANK_RECEIPT_TARGET
            self.assertEqual(expected, packaged.read_bytes())
            self.assertEqual(
                hashlib.sha256(expected).hexdigest(), next(row["sha256"] for row in result["outputs"] if row["target"] == stage_module.BANK_RECEIPT_TARGET)
            )
            archive = root / "streaming-assets.zip"
            with zipfile.ZipFile(archive, "w") as output:
                for path in (project / "Assets/StreamingAssets").rglob("*"):
                    if path.is_file():
                        output.write(path, path.relative_to(project / "Assets/StreamingAssets").as_posix())
            with zipfile.ZipFile(archive) as packaged_assets:
                self.assertEqual(expected, packaged_assets.read("stage-receipt.json"))

    def test_requested_set_cannot_omit_or_retarget_the_copy_receipt(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, receipt_path = write_set(root, True)
            assert request is not None and receipt_path is not None
            original = json.loads(manifest.read_text())
            for mutation in ("missing", "retargeted"):
                document = json.loads(json.dumps(original))
                row = next(row for row in document["outputs"] if row["role"] == "bank_receipt")
                if mutation == "missing":
                    document["outputs"].remove(row)
                else:
                    row["target"] = "Assets/StreamingAssets/Lab/stage-receipt.json"
                manifest.write_text(json.dumps(document))
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    stage_module.read_artifacts(manifest, request, receipt_path)

    def test_r2_requested_receipt_requires_packaged_exact_bank_media_receipt(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, bank_receipt = write_set(root, True)
            assert request is not None and bank_receipt is not None
            document = json.loads(manifest.read_text())
            for key in ("composed_api_sha256", "composed_game_sha256"):
                role = key.removesuffix("_sha256").removeprefix("composed_")
                document["lineage"][key] = next(row["sha256"] for row in document["outputs"] if row["role"] == role)
            manifest.write_text(json.dumps(document))
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(
                stage_module.LINEAGE,
                {
                    "composed_api_sha256": document["lineage"]["composed_api_sha256"],
                    "composed_game_sha256": document["lineage"]["composed_game_sha256"],
                    "native_library_sha256": document["lineage"]["native_library_sha256"],
                },
            ):
                stage_module.stage(project, manifest, request, bank_receipt)
                receipt_path = project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
                receipt = json.loads(receipt_path.read_text())
                packaged_receipt = project / stage_module.BANK_RECEIPT_TARGET
                packaged_receipt.unlink()
                receipt["outputs"] = [row for row in receipt["outputs"] if row["target"] != stage_module.BANK_RECEIPT_TARGET]
                receipt_path.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, "receipt package is missing or has drifted"):
                    stage_module.inspect_previous_stage(project, receipt_path)

    def test_default_off_rejects_opt_in_native_or_bank_bytes(self) -> None:
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False, [*DEFAULT_ROLES, "native"])
            with self.assertRaisesRegex(ValueError, "opt-in output"):
                stage_module.read_artifacts(manifest, None, None)

    def test_unfilled_current_api_pin_fails_closed(self) -> None:
        with self.temporary_directory() as temp:
            manifest, _, _ = write_set(Path(temp), False)
            with mock.patch.dict(stage_module.LINEAGE, {"composed_api_sha256": "ROOT_MUST_FILL_CURRENT_COMPOSED_API_SHA256"}):
                with self.assertRaisesRegex(ValueError, "pin is not finalized"):
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
            fixture_preimages = {
                "restore_api": frozenset({hashlib.sha256((project / stage_module.DEFAULT_TARGETS["api"]).read_bytes()).hexdigest()}),
                "restore_game": frozenset({hashlib.sha256((project / stage_module.DEFAULT_TARGETS["game"]).read_bytes()).hexdigest()}),
            }
            with (
                mock.patch.dict(stage_module.RESTORE_HASHES, restore_hashes),
                mock.patch.dict(stage_module.ALLOWED_RESTORE_PREIMAGES, fixture_preimages),
                mock.patch.object(
                    stage_module,
                    "ALLOWED_RESTORE_PREIMAGE_PAIRS",
                    frozenset({(next(iter(fixture_preimages["restore_api"])), next(iter(fixture_preimages["restore_game"])))}),
                ),
            ):
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
            with (
                mock.patch.dict(
                    stage_module.LINEAGE,
                    {
                        "native_library_sha256": native_hash,
                        "stage_receipt_sha256": hashlib.sha256(bank_receipt.read_bytes()).hexdigest(),
                        "composed_api_sha256": api_hash,
                        "composed_game_sha256": game_hash,
                    },
                ),
                mock.patch.dict(
                    stage_module.ALLOWED_RESTORE_PREIMAGES,
                    {
                        "restore_api": frozenset({api_hash}),
                        "restore_game": frozenset({game_hash}),
                    },
                ),
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
                with (
                    mock.patch.dict(stage_module.RESTORE_HASHES, restore_hashes),
                    mock.patch.object(stage_module, "ALLOWED_RESTORE_PREIMAGE_PAIRS", frozenset({(api_hash, game_hash)})),
                ):
                    receipt = stage_module.stage(project, default_off, None, None)

            self.assertFalse(receipt["requested"])
            self.assertFalse((project / stage_module.NATIVE_TARGET).exists())
            self.assertFalse((project / stage_module.NATIVE_META).exists())
            self.assertFalse((project / stage_module.BANK_RECEIPT_TARGET).exists())
            bank_root = project / "Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android"
            self.assertEqual({sidecar, project / stage_module.STREAMED_MEDIA_ROOT}, set(bank_root.iterdir()))
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


class StageTests(StageTests):
    def test_historical_r23_stage_receipt_pin_is_preserved_separately_from_unbound_r2_pin(self):
        self.assertEqual("8fe02400a7ab0905ae21b728e702d7ef2c4dcf8646f77f631682a81bda0ab88c", stage_module.LINEAGE["stage_receipt_sha256"])
        with self.temporary_directory() as temp:
            manifest, request, receipt = write_set(Path(temp), True)
            native_hash = next(row["sha256"] for row in json.loads(manifest.read_text())["outputs"] if row["role"] == "native")
            with (
                mock.patch.dict(stage_module.LINEAGE, {"native_library_sha256": native_hash}),
                mock.patch.object(stage_module, "R2_BANK_RECEIPT_SHA256", "ROOT_MUST_FILL_CURRENT_R2_BANK_STAGE_RECEIPT_SHA256"),
            ):
                with self.assertRaisesRegex(ValueError, "pin is not finalized"):
                    stage_module.read_artifacts(manifest, request, receipt)

    def test_streamed_media_receipt_join_rejects_mutated_contract_shapes(self):
        with self.temporary_directory() as temp:
            manifest, request, receipt_path = write_set(Path(temp), True)
            self.assertIsNotNone(request)
            self.assertIsNotNone(receipt_path)
            original = json.loads(receipt_path.read_text())
            mutations = ("duplicate_id", "bad_path", "bad_hash", "bad_size", "bad_reference", "extra_row", "missing_row")
            for mutation in mutations:
                receipt = json.loads(json.dumps(original))
                if mutation == "duplicate_id":
                    receipt["streamed_media"][1]["media_id"] = receipt["streamed_media"][0]["media_id"]
                    receipt["streamed_media"][1]["relative_path"] = receipt["streamed_media"][0]["relative_path"]
                elif mutation == "bad_path":
                    receipt["streamed_media"][0]["relative_path"] = "Media/../outside.wem"
                elif mutation == "bad_hash":
                    receipt["streamed_media"][0]["sha256"] = "z" * 64
                elif mutation == "bad_size":
                    receipt["streamed_media"][0]["size_bytes"] = True
                elif mutation == "bad_reference":
                    receipt["streamed_media"][0]["referenced_by"] = ["NotARequestedBank"]
                elif mutation == "extra_row":
                    receipt["streamed_media"].append(receipt["streamed_media"][-1])
                elif mutation == "missing_row":
                    receipt["streamed_media"].pop()
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    stage_module.validate_streamed_media_rows(receipt)

    def test_manifest_media_artifact_rejects_source_hash_size_or_target_drift(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, receipt_path = write_set(root, True)
            document = json.loads(manifest.read_text())
            media_row = next(row for row in document["outputs"] if row["role"] == "streamed_media")
            native_hash = next(row["sha256"] for row in document["outputs"] if row["role"] == "native")
            with mock.patch.dict(stage_module.LINEAGE, {"native_library_sha256": native_hash}):
                for mutation in ("target", "size", "reference"):
                    changed = json.loads(json.dumps(document))
                    row = next(row for row in changed["outputs"] if row["role"] == "streamed_media")
                    if mutation == "target":
                        row["target"] = "Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android/Media/999999.wem"
                    elif mutation == "size":
                        row["size_bytes"] += 1
                    else:
                        row["referenced_by"] = ["OtherBank"]
                    manifest.write_text(json.dumps(changed))
                    with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                        stage_module.read_artifacts(manifest, request, receipt_path)
                manifest.write_text(json.dumps(document))
                source = root / media_row["source"]
                source.write_bytes(b"drifted media")
                with self.assertRaisesRegex(ValueError, "artifact bytes differ"):
                    stage_module.read_artifacts(manifest, request, receipt_path)

    def test_requested_stages_exact_120_media_files_and_default_off_removes_owned_media_only(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, bank_receipt = write_set(root, True)
            project = root / "project"
            project.mkdir()
            doc = json.loads(manifest.read_text())
            lineage = doc["lineage"]
            for key in ("composed_api_sha256", "composed_game_sha256"):
                role = key.removesuffix("_sha256").removeprefix("composed_")
                lineage[key] = next(row["sha256"] for row in doc["outputs"] if row["role"] == role)
            manifest.write_text(json.dumps(doc))
            with mock.patch.dict(
                stage_module.LINEAGE,
                {
                    "composed_api_sha256": lineage["composed_api_sha256"],
                    "composed_game_sha256": lineage["composed_game_sha256"],
                    "native_library_sha256": lineage["native_library_sha256"],
                },
            ):
                receipt = stage_module.stage(project, manifest, request, bank_receipt)
                media_targets = [row["target"] for row in receipt["outputs"] if row["target"].startswith(stage_module.STREAMED_MEDIA_ROOT + "/")]
                self.assertEqual(stage_module.STREAMED_MEDIA_COUNT, len(media_targets))
                self.assertTrue(all((project / target).is_file() for target in media_targets))
                (project / stage_module.STREAMED_MEDIA_ROOT / "700000.wem.meta").write_text("Unity editor sidecar")
                sidecar_bytes = (project / stage_module.STREAMED_MEDIA_ROOT / "700000.wem.meta").read_bytes()
                default_manifest, _, _ = write_set(root / "default", False)
                default_doc = json.loads(default_manifest.read_text())
                default_doc["lineage"].update(
                    {
                        "stage_receipt_sha256": stage_module.LINEAGE["stage_receipt_sha256"],
                        "composed_api_sha256": lineage["composed_api_sha256"],
                        "composed_game_sha256": lineage["composed_game_sha256"],
                        "native_library_sha256": lineage["native_library_sha256"],
                    }
                )
                default_manifest.write_text(json.dumps(default_doc))
                stage_module.stage(project, default_manifest, None, None)
            self.assertFalse(any((project / target).exists() for target in media_targets))
            self.assertTrue((project / stage_module.STREAMED_MEDIA_ROOT / "700000.wem.meta").is_file())
            self.assertEqual(sidecar_bytes, (project / stage_module.STREAMED_MEDIA_ROOT / "700000.wem.meta").read_bytes())

    def test_r23_no_wem_predecessor_is_recognized_without_rewriting_its_historical_lineage(self):
        with self.temporary_directory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            receipt_path = project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            outputs = []
            plugin_guids = {}
            lineage = {
                **stage_module.LINEAGE,
                "composed_api_sha256": hashlib.sha256(b"synthetic-api").hexdigest(),
                "composed_game_sha256": hashlib.sha256(b"synthetic-game").hexdigest(),
                "native_library_sha256": hashlib.sha256(b"synthetic-native").hexdigest(),
            }
            targets = [stage_module.DEFAULT_TARGETS[role] for role in DEFAULT_ROLES]
            targets += sorted(stage_module.NEW_ASSEMBLY_META)
            targets += [stage_module.DEFAULT_TARGETS["api"], stage_module.DEFAULT_TARGETS["game"], stage_module.NATIVE_TARGET, stage_module.NATIVE_META]
            targets += [f"{stage_module.ANDROID_BANK_ROOT}/Init.bnk"] + [f"{stage_module.ANDROID_BANK_ROOT}/Bank-{i:03}.bnk" for i in range(1, 154)]
            for index, target in enumerate(targets):
                path = project / target
                path.parent.mkdir(parents=True, exist_ok=True)
                if target.endswith(".meta"):
                    guid = f"{index + 1:032x}"
                    path.write_text(f"fileFormatVersion: 2\nguid: {guid}\nPluginImporter:\n", encoding="utf-8")
                    plugin_guids[guid] = target
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                elif target == stage_module.DEFAULT_TARGETS["api"]:
                    path.write_bytes(b"synthetic-api")
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                elif target == stage_module.DEFAULT_TARGETS["game"]:
                    path.write_bytes(b"synthetic-game")
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                elif target == stage_module.NATIVE_TARGET:
                    path.write_bytes(b"synthetic-native")
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                else:
                    path.write_bytes(f"old R23 fixture output {index}".encode())
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                outputs.append({"target": target, "sha256": digest, "status": "staged"})
            old_receipt = {
                "schema": stage_module.RECEIPT_SCHEMA,
                "accepted_input_id": ACCEPTED,
                "lineage": lineage,
                "requested": True,
                "request_id": "0123456789abcdef0123456789abcdef",
                "request_sha256": "d" * 64,
                "artifact_manifest_sha256": "e" * 64,
                "stage_receipt_sha256": stage_module.LINEAGE["stage_receipt_sha256"],
                "plugin_guids": plugin_guids,
                "outputs": outputs,
            }
            receipt_path.write_text(json.dumps(old_receipt), encoding="utf-8")
            original_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            with mock.patch.object(stage_module, "LINEAGE", lineage):
                previous, remove = stage_module.inspect_previous_stage(project, receipt_path)
                self.assertEqual(lineage, previous["lineage"])
                self.assertEqual("8fe02400a7ab0905ae21b728e702d7ef2c4dcf8646f77f631682a81bda0ab88c", previous["lineage"]["stage_receipt_sha256"])
                self.assertFalse(any("/Media/" in path.as_posix() for path in remove))
                default_manifest, _, _ = write_set(Path(temp), False)
                document = json.loads(default_manifest.read_text())
                prior_hashes = {row["target"]: row["sha256"] for row in old_receipt["outputs"]}
                for item in document["outputs"]:
                    old_hash = prior_hashes.get(item["target"])
                    if old_hash is not None:
                        item["preimage_sha256"] = old_hash
                default_manifest.write_text(json.dumps(document))
                updated = stage_module.stage(project, default_manifest, None, None)
            self.assertNotEqual(original_hash, hashlib.sha256(receipt_path.read_bytes()).hexdigest())
            self.assertFalse(updated["requested"])
            self.assertEqual("8fe02400a7ab0905ae21b728e702d7ef2c4dcf8646f77f631682a81bda0ab88c", updated["lineage"]["stage_receipt_sha256"])
            self.assertFalse((project / stage_module.NATIVE_TARGET).exists())
            self.assertFalse(any((project / stage_module.ANDROID_BANK_ROOT).glob("*.bnk")))
            self.assertFalse((project / stage_module.STREAMED_MEDIA_ROOT).exists())

    def test_unowned_media_extra_or_symlink_refuses(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, _, _ = write_set(root, False)
            project = root / "project"
            project.mkdir()
            media_dir = project / stage_module.STREAMED_MEDIA_ROOT
            media_dir.mkdir(parents=True)
            extra = media_dir / "999999.wem"
            extra.write_bytes(b"unowned")
            with self.assertRaisesRegex(ValueError, "unreceipted"):
                stage_module.stage(project, manifest, None, None)
            extra.unlink()
            (media_dir / "700000.wem").symlink_to(root / "does-not-exist")
            with self.assertRaisesRegex(ValueError, "symlink"):
                stage_module.stage(project, manifest, None, None)


class StageTests(StageTests):
    def test_default_off_to_requested_restores_owned_media_with_preserved_editor_sidecar(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            requested, request, bank_receipt = write_set(root, True)
            assert request is not None and bank_receipt is not None
            doc = json.loads(requested.read_text())
            for key in ("composed_api_sha256", "composed_game_sha256"):
                role = key.removesuffix("_sha256").removeprefix("composed_")
                doc["lineage"][key] = next(row["sha256"] for row in doc["outputs"] if row["role"] == role)
            requested.write_text(json.dumps(doc))
            pins = {key: doc["lineage"][key] for key in ("composed_api_sha256", "composed_game_sha256", "native_library_sha256")}
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(stage_module.LINEAGE, pins):
                stage_module.stage(project, requested, request, bank_receipt)
                sidecar = project / stage_module.STREAMED_MEDIA_ROOT / "700000.wem.meta"
                sidecar.write_text("Unity-generated sidecar")
                default_manifest, _, _ = write_set(root / "default", False)
                default_doc = json.loads(default_manifest.read_text())
                default_doc["lineage"].update({"stage_receipt_sha256": stage_module.LINEAGE["stage_receipt_sha256"], **pins})
                default_manifest.write_text(json.dumps(default_doc))
                stage_module.stage(project, default_manifest, None, None)
                self.assertFalse((project / f"{stage_module.STREAMED_MEDIA_ROOT}/700000.wem").exists())
                self.assertTrue(sidecar.is_file())
                result = stage_module.stage(project, requested, request, bank_receipt)
            self.assertTrue(result["requested"])
            targets = {row["target"] for row in result["outputs"] if row["target"].startswith(stage_module.STREAMED_MEDIA_ROOT + "/")}
            self.assertEqual(stage_module.STREAMED_MEDIA_COUNT, len(targets))
            self.assertTrue(all((project / target).is_file() for target in targets))
            self.assertEqual("Unity-generated sidecar", sidecar.read_text())

    def test_receipt_bound_project_refuses_extra_media_and_unmatched_sidecars(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            requested, request, bank_receipt = write_set(root, True)
            assert request is not None and bank_receipt is not None
            doc = json.loads(requested.read_text())
            for key in ("composed_api_sha256", "composed_game_sha256"):
                role = key.removesuffix("_sha256").removeprefix("composed_")
                doc["lineage"][key] = next(row["sha256"] for row in doc["outputs"] if row["role"] == role)
            requested.write_text(json.dumps(doc))
            pins = {key: doc["lineage"][key] for key in ("composed_api_sha256", "composed_game_sha256", "native_library_sha256")}
            project = root / "project"
            project.mkdir()
            with mock.patch.dict(stage_module.LINEAGE, pins):
                stage_module.stage(project, requested, request, bank_receipt)
                (project / stage_module.STREAMED_MEDIA_ROOT / "999999999.wem").write_bytes(b"extra")
                with self.assertRaisesRegex(ValueError, "outside the previous receipt|exact owned payload"):
                    stage_module.inspect_previous_stage(project, project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json")
                (project / stage_module.STREAMED_MEDIA_ROOT / "999999999.wem").unlink()
                (project / stage_module.STREAMED_MEDIA_ROOT / "999999999.wem.meta").write_text("unmatched")
                with self.assertRaisesRegex(ValueError, "outside the exact receipt-owned bank/media cohort"):
                    stage_module.inspect_previous_stage(project, project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json")

    def test_media_source_alias_and_unfinalized_receipt_hash_are_refused(self):
        with self.temporary_directory() as temp:
            root = Path(temp)
            manifest, request, receipt = write_set(root, True)
            document = json.loads(manifest.read_text())
            media_rows = [row for row in document["outputs"] if row["role"] == "streamed_media"]
            media_rows[1]["source"] = media_rows[0]["source"]
            media_rows[1]["sha256"] = media_rows[0]["sha256"]
            media_rows[1]["size_bytes"] = media_rows[0]["size_bytes"]
            manifest.write_text(json.dumps(document))
            pins = {
                "composed_api_sha256": next(row["sha256"] for row in document["outputs"] if row["role"] == "api"),
                "composed_game_sha256": next(row["sha256"] for row in document["outputs"] if row["role"] == "game"),
                "native_library_sha256": next(row["sha256"] for row in document["outputs"] if row["role"] == "native"),
            }
            document["lineage"].update(pins)
            manifest.write_text(json.dumps(document))
            with mock.patch.dict(stage_module.LINEAGE, pins):
                with self.assertRaisesRegex(ValueError, "must not alias one source artifact"):
                    stage_module.read_artifacts(manifest, request, receipt)
            with mock.patch.object(stage_module, "R2_BANK_RECEIPT_SHA256", "ROOT_MUST_FILL_CURRENT_R2_BANK_STAGE_RECEIPT_SHA256"):
                with self.assertRaisesRegex(ValueError, "pin is not finalized"):
                    stage_module.verify_bank_receipt(receipt, [])


if __name__ == "__main__":
    unittest.main()
