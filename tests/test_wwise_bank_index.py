import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import wwise_bank_index as BANKS
from wwise_bank_index import bank_version, embedded_media, parse_source_banks


def chunk(tag, body):
    return tag + struct.pack("<I", len(body)) + body


class WwiseBankIndexTests(unittest.TestCase):
    def source_fixture(self, root):
        bank = root / "fixture.bnk"
        bank.write_bytes(chunk(b"BKHD", struct.pack("<II", 150, 17)) + chunk(b"DIDX", struct.pack("<III", 17, 0, 3)) + chunk(b"DATA", b"abc"))
        xml = '<SoundBanksInfo SoundBankVersion="150" SchemaVersion="16" Platform="Windows"><SoundBanks><SoundBank><Path>fixture.bnk</Path><Media><File Id="17" Location="Memory" Streaming="false"/></Media><Events><Event Id="42" Name="authored_event" DurationType="OneShot"><MediaRefs><MediaRef Id="17"/></MediaRefs></Event></Events></SoundBank></SoundBanks></SoundBanksInfo>'
        (root / "SoundbanksInfo.xml").write_text(xml)
        return xml

    def test_source_only_parser_never_reads_lab_state_writes_or_runs_decoder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source_fixture(root)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with (
                patch.object(BANKS, "read", side_effect=AssertionError("lab read")),
                patch.object(BANKS, "write", side_effect=AssertionError("write")),
                patch.object(BANKS, "run", side_effect=AssertionError("decoder")),
                patch.object(BANKS, "game", side_effect=AssertionError("config")),
            ):
                report = parse_source_banks(root, "authored-input")
            self.assertEqual(
                report["summary"],
                {"banks": 1, "bank_versions": [150], "events": 1, "embedded_media": 1, "single_media_events": 1, "multi_media_events": 0, "no_media_events": 0},
            )
            self.assertIsNone(report["decoder_sample"])
            self.assertEqual(report["events"][0]["id"], 42)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_source_parser_keeps_traversal_version_and_media_refusals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            xml = self.source_fixture(root)
            for content, error in [
                (xml.replace("fixture.bnk", "../outside.bnk"), "escapes"),
                (xml.replace('SoundBankVersion="150"', 'SoundBankVersion="149"'), "generator version"),
                (xml.replace('Location="Memory"', 'Location="Streamed"'), "metadata/DIDX"),
                (xml.replace('<MediaRef Id="17"', '<MediaRef Id="999"'), "absent media"),
            ]:
                with self.subTest(error=error):
                    (root / "SoundbanksInfo.xml").write_text(content)
                    with self.assertRaisesRegex(ValueError, error):
                        parse_source_banks(root, "authored-input")

    def test_lab_index_still_refuses_a_foreign_generation_before_parsing(self):
        with (
            patch.object(BANKS, "read", side_effect=[{"input_id": "accepted"}, {"input_id": "foreign"}]),
            patch.object(BANKS, "parse_source_banks", side_effect=AssertionError("parser must not run")),
            patch.object(BANKS, "write", side_effect=AssertionError("write")),
        ):
            with self.assertRaisesRegex(RuntimeError, "accepted lab generation"):
                BANKS.index()

    def test_decoder_qualifies_only_a_temporary_copy_and_checks_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source_fixture(root)
            report = parse_source_banks(root, "authored-input")
            original = (root / "fixture.bnk").read_bytes()

            def metadata(command):
                local = Path(command[-1])
                self.assertNotEqual(local, root / "fixture.bnk")
                self.assertEqual(local.read_bytes(), original)
                self.assertEqual(command[:3], ["vgmstream-cli", "-m", "-I"])
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"streamInfo": {"name": "17"}, "numberOfSamples": 10}).encode())

            with patch.object(BANKS, "run", side_effect=metadata):
                result = BANKS.decoder_metadata(root, report["banks"], root / "scratch")
            self.assertEqual(result["numberOfSamples"], 10)
            self.assertEqual((root / "fixture.bnk").read_bytes(), original)
            with patch.object(BANKS, "run", return_value=subprocess.CompletedProcess([], 0, stdout=b'{"streamInfo":{"name":"18"},"numberOfSamples":10}')):
                with self.assertRaisesRegex(ValueError, "media identity"):
                    BANKS.decoder_metadata(root, report["banks"], root / "scratch")

    def test_owner_entry_uses_inventory_without_project_and_refuses_hash_drift(self):
        from common import digest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            game = root / "game"
            audio = game / "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows"
            audio.mkdir(parents=True)
            self.source_fixture(audio)
            assembly = game / "Risk of Rain 2_Data/Managed/RoR2.dll"
            assembly.parent.mkdir()
            assembly.write_bytes(b"independently authored inventory marker")
            files = [
                {
                    "path": p.relative_to(game).as_posix(),
                    "size": p.stat().st_size,
                    "mtime_ns": p.stat().st_mtime_ns,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
                for p in sorted(game.rglob("*"))
                if p.is_file()
            ]
            identity = digest([(r["path"], r["sha256"]) for r in files])
            work = root / "work"
            (work / "config").mkdir(parents=True)
            (work / "inventory").mkdir()
            (work / "config/local.json").write_text(json.dumps({"game_path": str(game)}))
            (work / "config/accepted-input.json").write_text(json.dumps({"input_id": identity}))
            (work / "inventory/files.json").write_text(json.dumps({"input_id": identity, "files": files}))
            with patch.object(BANKS, "run", side_effect=AssertionError("default owner mode must not decode")):
                result = BANKS.owner_index(work, work / "new-output")
            self.assertTrue(result["success"])
            self.assertFalse(result["decoder_executed"])
            self.assertFalse((work / "lab-project").exists())
            self.assertFalse((work / "experiments").exists())
            bank = audio / "fixture.bnk"
            previous = bank.stat()
            bank.write_bytes(bank.read_bytes()[:-1] + b"x")
            os.utime(bank, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "accepted inventory"):
                BANKS.owner_index(work, work / "drift-output")
            self.assertFalse(json.loads((work / "drift-output/result.json").read_text())["success"])
            self.assertFalse((work / "drift-output/bank-index.json").exists())

    def test_bank_generator_version_is_read_from_bkhd_not_the_first_chunk(self):
        with tempfile.TemporaryDirectory() as temporary:
            bank = Path(temporary) / "fixture.bnk"
            bank.write_bytes(chunk(b"JUNK", b"fixture") + chunk(b"BKHD", struct.pack("<II", 150, 17)))
            self.assertEqual(bank_version(bank), 150)

    def test_missing_truncated_or_duplicate_bkhd_cannot_select_a_runtime_abi(self):
        with tempfile.TemporaryDirectory() as temporary:
            bank = Path(temporary) / "fixture.bnk"
            for data in (chunk(b"JUNK", b""), chunk(b"BKHD", b"abc"), chunk(b"BKHD", b"abcd") * 2):
                with self.subTest(data=data):
                    bank.write_bytes(data)
                    with self.assertRaisesRegex(ValueError, "one complete BKHD"):
                        bank_version(bank)

    def test_didx_identifies_embedded_media_and_subsong_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            bank = Path(temporary) / "fixture.bnk"
            didx = struct.pack("<III", 17, 0, 3) + struct.pack("<III", 29, 3, 2)
            bank.write_bytes(chunk(b"BKHD", b"\0" * 4) + chunk(b"DIDX", didx) + chunk(b"DATA", b"abcde"))
            self.assertEqual(embedded_media(bank), [{"id": 17, "subsong": 1, "bytes": 3}, {"id": 29, "subsong": 2, "bytes": 2}])
            bank.write_bytes(chunk(b"BKHD", b"\0" * 4) + chunk(b"DIDX", didx) + chunk(b"DATA", b"abcd"))
            with self.assertRaisesRegex(ValueError, "exceeds DATA"):
                embedded_media(bank)


if __name__ == "__main__":
    unittest.main()
