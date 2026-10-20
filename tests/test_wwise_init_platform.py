from __future__ import annotations

import hashlib
from dataclasses import replace
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ANCESTORS = Path(__file__).resolve().parents
SCRIPT_ROOT = next(parent for parent in ANCESTORS if (parent / "scripts/lab/wwise_init_platform.py").is_file())
COMMON_ROOT = next(parent for parent in ANCESTORS if (parent / "scripts/lab/common.py").is_file())
sys.path.insert(0, str(COMMON_ROOT / "scripts/lab"))
sys.path.insert(0, str(SCRIPT_ROOT / "scripts/lab"))
import wwise_init_platform as transform


TEST_CONTRACT = transform.Contract(
    format_version=150,
    bank_id=7,
    bank_size_bytes=0,
    plugin_entries=((100, "EffectA"), (200, ""), (300, "")),
    device_effects={10: 300, 11: 200},
    root_bus_map={20: 11, 21: 10},
    controller_bus_map={20: 11},
    system_device=10,
    remove_plugin=200,
    remove_devices=(11,),
    expected_tags=(b"BKHD", b"INIT", b"STMG", b"HIRC", b"ENVS", b"PLAT"),
)


def chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload


def hirc_record(kind: int, body: bytes) -> bytes:
    return bytes([kind]) + struct.pack("<I", len(body)) + body


def audio_device(object_id: int, plugin_id: int, body_size: int = 20, params: bytes | None = None) -> bytes:
    if params is None:
        params = bytes(body_size - 8)
    body = struct.pack("<II", object_id, plugin_id) + params
    return hirc_record(21, body)


def bus(object_id: int, device_id: int, override: int = 0, tail: bytes = b"\xaa\xbb") -> bytes:
    return hirc_record(8, struct.pack("<III", object_id, override, device_id) + tail)


def build_bank(*, plugins=None, devices=None, buses=None, malformed=False) -> bytes:
    plugins = plugins if plugins is not None else list(TEST_CONTRACT.plugin_entries)
    plugin_payload = struct.pack("<I", len(plugins)) + b"".join(struct.pack("<I", plugin_id) + name.encode("ascii") + b"\0" for plugin_id, name in plugins)
    devices = devices if devices is not None else [audio_device(11, 200), audio_device(10, 300, 20, b"\x01" * 12)]
    buses = buses if buses is not None else [bus(20, 11), bus(21, 10)]
    records = devices + buses
    hirc_payload = struct.pack("<I", len(records)) + b"".join(records)
    if malformed:
        hirc_payload += b"x"
    header = bytearray(48)
    struct.pack_into("<I", header, 0, 150)
    struct.pack_into("<I", header, 4, TEST_CONTRACT.bank_id)
    return b"".join(
        (
            chunk(b"BKHD", bytes(header)),
            chunk(b"INIT", plugin_payload),
            chunk(b"STMG", b"opaque-preserved"),
            chunk(b"HIRC", hirc_payload),
            chunk(b"ENVS", b"env-preserved"),
            chunk(b"PLAT", b"plat-preserved"),
        )
    )


def parsed_records(data: bytes):
    chunks = dict(transform._chunks(data, TEST_CONTRACT.expected_tags))
    return chunks, transform._parse_hirc(chunks[b"HIRC"])


class TransformInitTests(unittest.TestCase):
    def test_checked_in_recipe_loads_without_pinning_a_private_input_hash(self):
        recipe_path = Path(transform.__file__).resolve().parents[2] / "recipe/wwise-init-android.json"
        recipe = json.loads(recipe_path.read_text())
        contract = transform.load_contract(recipe_path)
        self.assertEqual(contract.format_version, 150)
        self.assertEqual(contract.bank_id, recipe["bank_id"])
        self.assertEqual(len(contract.plugin_entries), len(recipe["plugin_entries"]))
        self.assertNotIn("input_sha256", recipe)
        self.assertNotIn("accepted_input_id", recipe)

    def test_rewrites_only_target_metadata_and_preserves_other_objects(self):
        source = build_bank()
        chunks_before, records_before = parsed_records(source)
        system = next(record for kind, record in records_before if kind == 21 and transform._record_id(kind, record) == 10)
        nested = bus(22, 1234, override=20)
        source = build_bank(buses=[bus(20, 11), bus(21, 10), nested])
        chunks_before, records_before = parsed_records(source)
        system = next(record for kind, record in records_before if kind == 21 and transform._record_id(kind, record) == 10)
        out = transform.rewrite_bank(source, TEST_CONTRACT)
        chunks_after, records_after = parsed_records(out)
        plugins, _ = transform._parse_plugin_chunk(chunks_after[b"INIT"])
        self.assertEqual([(pid, name) for pid, name, _ in plugins], [(100, "EffectA"), (300, "")])
        self.assertFalse(any(kind == 21 and transform._record_id(kind, record) == 11 for kind, record in records_after))
        self.assertTrue(any(kind == 21 and transform._record_id(kind, record) == 10 and record == system for kind, record in records_after))
        out_buses = {
            transform._record_id(kind, record): transform._u32(record[5:], 8)
            for kind, record in records_after
            if kind == 8 and transform._u32(record[5:], 4) == 0
        }
        self.assertEqual(out_buses, {20: 10, 21: 10})
        self.assertIn(nested, [record for _, record in records_after])
        for tag in (b"BKHD", b"STMG", b"ENVS", b"PLAT"):
            self.assertEqual(chunks_after[tag], chunks_before[tag])
        self.assertEqual(len(out), len(source) - 30)

    def test_missing_or_ambiguous_plugin_registration_refuses(self):
        cases = [
            [(100, "EffectA"), (300, "")],
            [(100, "EffectA"), (200, "wrong-library"), (300, "")],
            [(100, "EffectA"), (200, ""), (200, ""), (300, "")],
        ]
        for plugins in cases:
            with self.subTest(plugins=plugins), self.assertRaises(transform.Refusal):
                transform.rewrite_bank(build_bank(plugins=plugins), TEST_CONTRACT)

    def test_audio_device_identity_plugin_and_parameter_contract_refuses(self):
        good_system = audio_device(10, 300, 20, b"\x01" * 12)
        cases = [
            [good_system],
            [audio_device(11, 100), good_system],
            [audio_device(11, 200, 20, b"\x00" * 11 + b"\x01"), good_system],
            [audio_device(11, 200), audio_device(11, 200), good_system],
        ]
        for devices in cases:
            with self.subTest(devices=[r[5:9].hex() for r in devices]), self.assertRaises(transform.Refusal):
                transform.rewrite_bank(build_bank(devices=devices), TEST_CONTRACT)

    def test_bus_topology_and_old_shareset_relationships_are_required(self):
        cases = [
            [bus(21, 10)],
            [bus(20, 99), bus(21, 10)],
            [bus(20, 11, override=21), bus(21, 10)],
            [bus(20, 11), bus(21, 10), bus(23, 11)],
        ]
        for buses in cases:
            with self.subTest(buses=len(buses)), self.assertRaises(transform.Refusal):
                transform.rewrite_bank(build_bank(buses=buses), TEST_CONTRACT)

    def test_chunk_count_length_and_order_refuse_corruption(self):
        good = build_bank()
        cases = [good[:-1], good[:4] + struct.pack("<I", 9999) + good[8:], good.replace(b"HIRC", b"HIRC", 1)[:-5]]
        malformed_hirc = build_bank(malformed=True)
        cases.append(malformed_hirc)
        for value in cases:
            with self.subTest(size=len(value)), self.assertRaises(transform.Refusal):
                transform.rewrite_bank(value, TEST_CONTRACT)

    def test_accepted_source_check_binds_explicit_path_hash_and_full_input_id(self):
        work = transform._repository_root() / "work"
        work.mkdir(exist_ok=True)  # ignored; absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=work) as temp:
            root = Path(temp)
            relative = "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/Init.bnk"
            configured = root / "accepted-game"
            source = configured / relative
            source.parent.mkdir(parents=True)
            data = build_bank()
            source.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            accepted = {"input_id": "fixture-input"}
            inventory = {"input_id": "fixture-input", "hash_mode": "full", "files": [{"path": relative, "sha256": digest, "size": len(data)}]}
            contract = replace(TEST_CONTRACT, bank_size_bytes=len(data))
            self.assertEqual(transform.verify_accepted_source(source, digest, configured, accepted, inventory, contract, relative), (digest, len(data), data))
            cases = [
                (source, "0" * 64, accepted, inventory),
                (source, digest, {"input_id": "other"}, inventory),
                (source, digest, accepted, {**inventory, "hash_mode": "cached"}),
                (root / "elsewhere.bnk", digest, accepted, inventory),
            ]
            for selected, expected, accepted_row, inventory_row in cases:
                with self.subTest(selected=selected, expected=expected), self.assertRaises(transform.Refusal):
                    transform.verify_accepted_source(selected, expected, configured, accepted_row, inventory_row, contract, relative)

    def test_transform_creates_new_output_and_receipt_without_changing_source(self):
        work = transform._repository_root() / "work"
        work.mkdir(exist_ok=True)  # ignored; absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=work) as temp:
            root = Path(temp)
            relative = "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/Init.bnk"
            configured = root / "accepted-game"
            source = configured / relative
            source.parent.mkdir(parents=True)
            data = build_bank()
            source.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            accepted = {"input_id": "fixture-input"}
            inventory = {"input_id": "fixture-input", "hash_mode": "full", "files": [{"path": relative, "sha256": digest, "size": len(data)}]}
            contract = replace(TEST_CONTRACT, bank_size_bytes=len(data))
            output_dir = root / "output"
            output_dir.mkdir()
            destination, receipt_path = output_dir / "Init.android.bnk", output_dir / "receipt.json"
            receipt = transform.transform_file(source, destination, receipt_path, digest, contract, configured, accepted, inventory, relative)
            self.assertEqual(source.read_bytes(), data)
            self.assertEqual(destination.read_bytes(), transform.rewrite_bank(data, contract))
            self.assertEqual(receipt["input_sha256"], digest)
            self.assertEqual(receipt["input_relative_path"], relative)
            self.assertEqual(receipt["output_sha256"], hashlib.sha256(destination.read_bytes()).hexdigest())
            self.assertEqual(json.loads(receipt_path.read_text()), receipt)

    def test_transform_uses_the_verified_snapshot_if_source_changes_after_read(self):
        work = transform._repository_root() / "work"
        work.mkdir(exist_ok=True)  # ignored; absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=work) as temp:
            root = Path(temp)
            relative = "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/Init.bnk"
            configured = root / "accepted-game"
            source = configured / relative
            source.parent.mkdir(parents=True)
            verified = build_bank()
            replacement = verified.replace(b"\xaa\xbb", b"\xcc\xdd")
            self.assertNotEqual(verified, replacement)
            source.write_bytes(verified)
            digest = hashlib.sha256(verified).hexdigest()
            accepted = {"input_id": "fixture-input"}
            inventory = {"input_id": "fixture-input", "hash_mode": "full", "files": [{"path": relative, "sha256": digest, "size": len(verified)}]}
            contract = replace(TEST_CONTRACT, bank_size_bytes=len(verified))
            output_dir = root / "output"
            output_dir.mkdir()
            destination, receipt_path = output_dir / "Init.android.bnk", output_dir / "receipt.json"

            original_read_bytes = Path.read_bytes
            source_reads = 0

            def read_then_replace(path):
                nonlocal source_reads
                data = original_read_bytes(path)
                if path == source:
                    source_reads += 1
                    source.write_bytes(replacement)
                return data

            with mock.patch.object(Path, "read_bytes", read_then_replace):
                receipt = transform.transform_file(source, destination, receipt_path, digest, contract, configured, accepted, inventory, relative)

            self.assertEqual(source_reads, 1)
            self.assertEqual(source.read_bytes(), replacement)
            self.assertEqual(destination.read_bytes(), transform.rewrite_bank(verified, contract))
            self.assertNotEqual(destination.read_bytes(), transform.rewrite_bank(replacement, contract))
            self.assertEqual(receipt["input_sha256"], digest)
            self.assertEqual(receipt["input_size_bytes"], len(verified))

    def test_wrong_accepted_hash_refuses_before_creating_either_output(self):
        work = transform._repository_root() / "work"
        work.mkdir(exist_ok=True)  # ignored; absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=work) as temp:
            root = Path(temp)
            relative = "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/Init.bnk"
            configured = root / "accepted-game"
            source = configured / relative
            source.parent.mkdir(parents=True)
            data = build_bank()
            source.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            accepted = {"input_id": "fixture-input"}
            inventory = {"input_id": "fixture-input", "hash_mode": "full", "files": [{"path": relative, "sha256": digest, "size": len(data)}]}
            contract = replace(TEST_CONTRACT, bank_size_bytes=len(data))
            output_dir = root / "output"
            output_dir.mkdir()
            destination, receipt = output_dir / "Init.android.bnk", output_dir / "receipt.json"
            with self.assertRaises(transform.Refusal):
                transform.transform_file(source, destination, receipt, "0" * 64, contract, configured, accepted, inventory, relative)
            self.assertFalse(destination.exists())
            self.assertFalse(receipt.exists())

    def test_output_paths_must_be_new_distinct_and_inside_ignored_work(self):
        repo = transform._repository_root()
        work = repo / "work"
        work.mkdir(exist_ok=True)  # ignored; absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=work) as temp:
            root = Path(temp)
            source = root / "source.bnk"
            source.write_bytes(b"synthetic source")
            destination, receipt = root / "out.bnk", root / "receipt.json"

            resolved = transform.validate_output_paths(source, destination, receipt)
            self.assertEqual(resolved, (destination.resolve(), receipt.resolve()))
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, source)
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, destination, destination)

            destination.write_bytes(b"preserve destination")
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, destination, receipt)
            self.assertEqual(destination.read_bytes(), b"preserve destination")
            destination.unlink()

            receipt.write_bytes(b"preserve receipt")
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, destination, receipt)
            self.assertEqual(receipt.read_bytes(), b"preserve receipt")

            outside = repo / "untrusted-output.bnk"
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, outside)
            self.assertFalse(outside.exists())
            with self.assertRaises(transform.Refusal):
                transform.transform_file(source, outside, root / "unused-receipt", "0" * 64, TEST_CONTRACT, root, {}, {}, "input.bnk")
            self.assertFalse(outside.exists())

    def test_output_paths_refuse_symlink_and_symlink_escape_without_writes(self):
        repo = transform._repository_root()
        work = repo / "work"
        work.mkdir(exist_ok=True)  # ignored; absent in a fresh clone
        with tempfile.TemporaryDirectory(dir=work) as temp:
            root = Path(temp)
            source = root / "source.bnk"
            source.write_bytes(b"synthetic source")

            outside_target = root / "outside-target"
            outside_target.mkdir()
            external_file = outside_target / "kept.bin"
            external_file.write_bytes(b"unchanged")
            symlink_file = root / "linked-output"
            symlink_file.symlink_to(external_file)
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, symlink_file)
            self.assertEqual(external_file.read_bytes(), b"unchanged")

            escape = root / "escape"
            escape.symlink_to(repo, target_is_directory=True)
            escaped_destination = escape / "should-not-exist.bin"
            with self.assertRaises(transform.Refusal):
                transform.validate_output_paths(source, escaped_destination)
            self.assertFalse((repo / "should-not-exist.bin").exists())


if __name__ == "__main__":
    unittest.main()
