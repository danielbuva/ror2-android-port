from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

PATCH = Path(__file__).resolve().parents[1]
PRODUCER_PATH = PATCH / "scripts/lab/original_game_audio_produce.py"
GENERATOR_PATH = PATCH / "tools/unity/support/audio/generators/generate_accepted_request_pin.py"
MANAGED_PRODUCER_PATH = PATCH / "tools/unity/support/audio/managed-producer/produce.py"
COMPOSED_TRANSFORM_PATH = PATCH / "tools/unity/support/audio/managed-producer/tools/composed/ComposedGameCecilTransform.cs"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


class RequestPipelineTests(unittest.TestCase):
    def test_point_sound_transform_resolves_dependencies_from_accepted_managed_input(self) -> None:
        transform = COMPOSED_TRANSFORM_PATH.read_text(encoding="utf-8")
        producer = MANAGED_PRODUCER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'args.Length == 5 && args[0] == "point-sound") return TransformPointSound(args[1], args[2], args[3], args[4])',
            transform,
        )
        self.assertIn(
            "TransformPointSound(string input, string observerPath, string output, string referenceDirectory)",
            transform,
        )
        self.assertIn("Resolver(input, observerPath, referenceDirectory)", transform)
        self.assertIn("resolver.AddSearchDirectory(full);", transform)
        command_start = producer.index('"point-sound",')
        command_end = producer.index("],", command_start)
        command = producer[command_start:command_end]
        self.assertIn("str(managed)", command)
        managed_producer = load(MANAGED_PRODUCER_PATH, "private_managed_audio_producer")
        self.assertEqual(
            hashlib.sha256(COMPOSED_TRANSFORM_PATH.read_bytes()).hexdigest(),
            managed_producer.EXPECTED["composed_transform_source"],
        )
        self.assertEqual(
            "53e732cbdf507e79bb0c9581acdf138c8e3b028efac20d8adcfd8a73dc5e5aba",
            managed_producer.EXPECTED["composed_transform_source"],
        )

    def test_composed_game_is_generated_into_request_and_runtime_pin(self) -> None:
        producer = load(PRODUCER_PATH, "private_audio_producer")
        generator = load(GENERATOR_PATH, "private_request_generator")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            work = root / "work"
            (work / "config").mkdir(parents=True)
            game_root = root / "legitimate-game"
            managed = game_root / "Risk of Rain 2_Data/Managed"
            raw_game = managed / "RoR2.dll"
            raw_api = managed / "AK.Wwise.Unity.API.dll"
            raw_game_sha = write(raw_game, b"synthetic accepted raw game")
            raw_api_sha = write(raw_api, b"synthetic accepted raw API")
            (work / "config/local.json").write_text(json.dumps({"game_path": str(game_root)}))
            stage_root = work / "stage"
            bank_dir = stage_root / "Audio/GeneratedSoundBanks/Android"
            init_sha = write(bank_dir / "Init.bnk", b"synthetic adapted Init")
            global_sha = write(bank_dir / "Global.bnk", b"synthetic accepted Global")
            inventory_path = work / "inventory/files.json"
            inventory_sha = write(inventory_path, json.dumps({"input_id": "accepted", "hash_mode": "full"}).encode())
            stage_outputs = []
            for index in range(153):
                filename = "Global.bnk" if index == 0 else f"Bank{index:03}.bnk"
                digest = global_sha if filename == "Global.bnk" else init_sha if filename == "Init.bnk" else hashlib.sha256(filename.encode()).hexdigest()
                stage_outputs.append({"filename": filename, "requested_name": filename[:-4], "sha256": digest, "size_bytes": 32})
            stage_outputs.append({"filename": "Init.bnk", "requested_name": "Init", "sha256": init_sha, "size_bytes": 32})
            # The accepted receipt carries 153 banks plus the separate Init file.
            names = {row["filename"] for row in stage_outputs}
            self.assertEqual(154, len(names))
            stage_doc = {
                "schema": "original-game-wwise-bank-cohort-r1",
                "accepted_input_id": "accepted",
                "requested_banks": 153,
                "runtime_private_copy_required": True,
                "output_relative_directory": "Audio/GeneratedSoundBanks/Android",
                "runtime_copy_complete": False,
                "runtime_bank_ready": False,
                "accepted_inventory_sha256": inventory_sha,
                "current_bank_index_sha256": "",
                "wwise_global_prefab_sha256": "",
                "init_adaptation_receipt_sha256": "",
                "init_adaptation_candidate_sha256": init_sha,
                "global_accepted_original_sha256": global_sha,
                "outputs": stage_outputs,
            }
            values = {}
            roles = generator.CONTRACT_ROLES
            for role in roles:
                if role == "game_assembly_sha256":
                    values[role] = raw_game_sha
                elif role == "composed_game_sha256":
                    values[role] = "1" * 64
                elif role == "adapted_init_sha256":
                    values[role] = init_sha
                elif role == "global_accepted_original_sha256":
                    values[role] = global_sha
                elif role == "current_bank_index_sha256":
                    values[role] = "2" * 64
                elif role == "wwise_global_prefab_sha256":
                    values[role] = "3" * 64
                elif role == "init_adaptation_receipt_sha256":
                    values[role] = "4" * 64
                elif role == "raw_api_sha256":
                    values[role] = raw_api_sha
                else:
                    values[role] = hashlib.sha256(role.encode()).hexdigest()
            stage_path = work / "stage-receipt.json"
            stage_path.write_text(json.dumps(stage_doc, sort_keys=True))
            managed_paths = {}
            for filename, digest in (
                ("api-adapted.dll", values["adapted_api_sha256"]),
                ("api-observed.dll", values["observed_api_sha256"]),
                ("api-instrumented-composed.dll", values["instrumented_api_sha256"]),
                ("game-original-owner-point-sound-composed.dll", values["composed_game_sha256"]),
            ):
                path = work / "managed" / filename
                write(path, filename.encode())
                managed_paths[filename] = path
                values["adapted_api_sha256"] = (
                    hashlib.sha256(b"api-adapted.dll").hexdigest() if filename == "api-adapted.dll" else values.get("adapted_api_sha256")
                )
                values["observed_api_sha256"] = (
                    hashlib.sha256(b"api-observed.dll").hexdigest() if filename == "api-observed.dll" else values.get("observed_api_sha256")
                )
                values["instrumented_api_sha256"] = (
                    hashlib.sha256(b"api-instrumented-composed.dll").hexdigest()
                    if filename == "api-instrumented-composed.dll"
                    else values.get("instrumented_api_sha256")
                )
                values["composed_game_sha256"] = (
                    hashlib.sha256(b"game-original-owner-point-sound-composed.dll").hexdigest()
                    if filename == "game-original-owner-point-sound-composed.dll"
                    else values.get("composed_game_sha256")
                )
            native = work / "native.so"
            write(native, b"synthetic accepted native")
            bank_index = work / "bank-index.json"
            write(bank_index, b"synthetic bank index")
            prefab = work / "global.prefab"
            write(prefab, b"synthetic global prefab")
            init_receipt = work / "init-receipt.json"
            write(init_receipt, b"synthetic init receipt")
            # Make the generator's immutable accepted pins match only this isolated fixture.
            values.update(
                {
                    "accepted_input_id": "accepted",
                    "adapted_init_sha256": init_sha,
                    "native_library_sha256": hashlib.sha256(b"synthetic accepted native").hexdigest(),
                    "current_bank_index_sha256": hashlib.sha256(b"synthetic bank index").hexdigest(),
                    "wwise_global_prefab_sha256": hashlib.sha256(b"synthetic global prefab").hexdigest(),
                    "init_adaptation_receipt_sha256": hashlib.sha256(b"synthetic init receipt").hexdigest(),
                    "global_accepted_original_sha256": global_sha,
                }
            )
            expected = {
                key: values[key]
                for key in (
                    "accepted_input_id",
                    "adapted_init_sha256",
                    "game_assembly_sha256",
                    "composed_game_sha256",
                    "raw_api_sha256",
                    "adapted_api_sha256",
                    "observed_api_sha256",
                    "instrumented_api_sha256",
                    "native_library_sha256",
                    "current_bank_index_sha256",
                    "wwise_global_prefab_sha256",
                    "init_adaptation_receipt_sha256",
                    "global_accepted_original_sha256",
                )
            }
            stage_doc["current_bank_index_sha256"] = values["current_bank_index_sha256"]
            stage_doc["wwise_global_prefab_sha256"] = values["wwise_global_prefab_sha256"]
            stage_doc["init_adaptation_receipt_sha256"] = values["init_adaptation_receipt_sha256"]
            stage_path.write_text(json.dumps(stage_doc, sort_keys=True))
            fake_generator = SimpleNamespace(EXPECTED=expected, CONTRACT_SCHEMA=generator.CONTRACT_SCHEMA)
            (work / "out").mkdir()
            (work / "generated").mkdir()
            producer.ROOT = root
            producer.TOOLS = PATCH / "tools/unity/support/audio/generators"
            producer.LINEAGE.update({"accepted_game_sha256": raw_game_sha, "raw_api_sha256": raw_api_sha, "accepted_input_id": "accepted"})
            with mock.patch.object(producer, "load_module", return_value=fake_generator):
                request_path, contract_path = producer.generate_request_contract(
                    work / "out",
                    work / "generated",
                    "0123456789abcdef0123456789abcdef",
                    {},
                    managed_paths,
                    native,
                    stage_path,
                    stage_root,
                    prefab,
                    bank_index,
                    bank_dir / "Init.bnk",
                    init_receipt,
                )
            contract = json.loads(contract_path.read_text())
            request = json.loads(request_path.read_text())
            self.assertIn("composed_game_sha256", {row["role"] for row in contract["inputs"]})
            composed_row = next(row for row in contract["inputs"] if row["role"] == "composed_game_sha256")
            self.assertEqual(expected["composed_game_sha256"], composed_row["sha256"])
            self.assertEqual(expected["composed_game_sha256"], request["composed_game_sha256"])
            generator.ROOT = root
            generator.WORK = work
            generator.EXPECTED = expected
            generator.CONTRACT_ROLES = roles
            validated = generator.validate(request_path, contract_path, stage_path)
            self.assertEqual(request["request_id"], validated["request"]["request_id"])
            generated_pin = work / "generated-pin.cs"
            generator.emit(request_path, contract_path, stage_path, generated_pin)
            self.assertIn(expected["composed_game_sha256"], generated_pin.read_text())
            tampered = json.loads(request_path.read_text())
            tampered["composed_game_sha256"] = "f" * 64
            request_path.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "accepted source pin mismatch: composed_game_sha256"):
                generator.validate(request_path, contract_path, stage_path)


if __name__ == "__main__":
    unittest.main()
