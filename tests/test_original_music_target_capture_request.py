from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid


def find_repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


REPOSITORY_ROOT = find_repository_root()
SOURCE_ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "tools/unity/support/audio/generators/generate_accepted_request_pin.py").is_file()),
    REPOSITORY_ROOT,
)
GENERATOR = SOURCE_ROOT / "tools/unity/support/audio/generators/generate_accepted_request_pin.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("target_capture_request_generator", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load request pin generator")
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


class AcceptedRequestTargetCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="target-capture-request-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        self.work = self.project / "work"
        self.work.mkdir()
        self.module = load_generator()
        self.module.ROOT = self.project
        self.module.WORK = self.work.resolve()
        self.module.EXPECTED = {key: hashlib.sha256(("pin:" + key).encode()).hexdigest() for key in self.module.CONTRACT_ROLES | {"accepted_input_id"}}
        self.expected = self.module.EXPECTED
        self.contract_path = self.work / "contract.json"
        self.stage_path = self.work / "stage.json"
        self.request_path = self.work / "request.json"
        self.output_path = self.work / "generated/RequestPin.cs"
        self._write_inputs()

    def _write_inputs(self) -> None:
        rows = []
        for role in sorted(self.module.CONTRACT_ROLES):
            file_path = self.work / "inputs" / (role + ".bin")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(("input:" + role).encode())
            self.expected[role] = hashlib.sha256(file_path.read_bytes()).hexdigest()
            rows.append(
                {
                    "role": role,
                    "path": str(file_path.relative_to(self.work)),
                    "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
                }
            )
        self.contract_path.write_text(
            json.dumps(
                {
                    "schema": self.module.CONTRACT_SCHEMA,
                    "accepted_input_id": self.expected["accepted_input_id"],
                    "inputs": rows,
                }
            ),
            encoding="utf-8",
        )

        inventory_path = self.work / "inventory/files.json"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(
            json.dumps(
                {
                    "input_id": self.expected["accepted_input_id"],
                    "hash_mode": "full",
                }
            ),
            encoding="utf-8",
        )
        stage = {
            "schema": "original-game-wwise-bank-cohort-r1",
            "accepted_input_id": self.expected["accepted_input_id"],
            "requested_banks": 153,
            "runtime_private_copy_required": True,
            "output_relative_directory": "Audio/GeneratedSoundBanks/Android",
            "runtime_copy_complete": False,
            "runtime_bank_ready": False,
            "accepted_inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            "current_bank_index_sha256": self.expected["current_bank_index_sha256"],
            "wwise_global_prefab_sha256": self.expected["wwise_global_prefab_sha256"],
            "init_adaptation_receipt_sha256": self.expected["init_adaptation_receipt_sha256"],
            "init_adaptation_candidate_sha256": self.expected["adapted_init_sha256"],
            "global_accepted_original_sha256": self.expected["global_accepted_original_sha256"],
            "outputs": [
                {"filename": f"Bank{i:03}.bnk", "requested_name": f"Bank{i:03}", "sha256": hashlib.sha256(f"bank:{i}".encode()).hexdigest(), "size_bytes": 1}
                for i in range(153)
            ]
            + [{"filename": "Init.bnk", "sha256": self.expected["adapted_init_sha256"], "size_bytes": 1}],
        }
        self.stage_path.write_text(json.dumps(stage), encoding="utf-8")
        self.base_request = {
            "schema": self.module.REQUEST_SCHEMA,
            "requested": True,
            "passive_pcm_capture_requested": True,
            "accepted_input_id": self.expected["accepted_input_id"],
            "request_id": uuid.uuid4().hex,
            "stage_receipt_sha256": hashlib.sha256(self.stage_path.read_bytes()).hexdigest(),
            "build_input_contract_sha256": hashlib.sha256(self.contract_path.read_bytes()).hexdigest(),
            "adapted_init_sha256": self.expected["adapted_init_sha256"],
            **{key: self.expected[key] for key in self.expected if key not in {"accepted_input_id", "init_adaptation_candidate_sha256"}},
        }

    def _emit(self, request: dict) -> str:
        self.request_path.write_text(json.dumps(request), encoding="utf-8")
        self.output_path.unlink(missing_ok=True)
        self.module.emit(self.request_path, self.contract_path, self.stage_path, self.output_path)
        return self.output_path.read_text(encoding="utf-8")

    def test_absent_and_explicit_false_default_to_main_output_capture(self) -> None:
        for request in (dict(self.base_request), {**self.base_request, "passive_pcm_capture_music_output_requested": False}):
            source = self._emit(request)
            self.assertIn("PassivePcmCaptureMusicOutputRequested = false;", source)

    def test_true_requires_existing_passive_capture_opt_in(self) -> None:
        request = {**self.base_request, "passive_pcm_capture_music_output_requested": True}
        source = self._emit(request)
        self.assertIn("PassivePcmCaptureMusicOutputRequested = true;", source)
        self.assertIn("PassivePcmCaptureRequested = true;", source)

        request["passive_pcm_capture_requested"] = False
        self.request_path.write_text(json.dumps(request), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "requires passive PCM capture"):
            self.module.validate(self.request_path, self.contract_path, self.stage_path)

    def test_new_flag_rejects_non_boolean_values(self) -> None:
        for invalid in (1, "true", None, []):
            with self.subTest(invalid=invalid):
                request = {**self.base_request, "passive_pcm_capture_music_output_requested": invalid}
                self.request_path.write_text(json.dumps(request), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "explicit opted-in runtime request"):
                    self.module.validate(self.request_path, self.contract_path, self.stage_path)


if __name__ == "__main__":
    unittest.main()
