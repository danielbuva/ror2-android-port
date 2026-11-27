"""Scoreboard coverage for standalone files, bundle members and attempt evidence."""

import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"))
S = importlib.import_module("whole_game_scoreboard")


def pin(path):
    return dict(path=str(path), sha256=S.W.B.sha(path))


def serialized(rows):
    types = [dict(class_id=class_id, stripped=0, script_type=-1, hash=bytes(16)) for class_id in (28, 43)]
    objects = [dict(path_id=pid, type_id=type_id, offset=offset, bytes=1) for offset, (pid, type_id, _) in enumerate(rows)]
    layout = dict(engine="2021.3.45f2", platform=13, trees=False, types=types, objects=objects, scripts=[], externals=[], ref_types=[], user="")
    stream = io.BytesIO()
    S.W.write_serialized(stream, layout, lambda row: io.BytesIO(rows[row["offset"]][2]))
    return stream.getvalue()


def bundle(path, raw):
    with path.open("wb") as stream:
        S.W.write_bundle(stream, [("CAB-pack", 4, len(raw), lambda: io.BytesIO(raw))], lambda body, _: body, flags=0x240)


class WholeGameScoreboardTests(unittest.TestCase):
    def test_full_inventory_and_apk_bound_device_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, reference = root / "candidate.apk", root / "reference.apk"
            bundle_path, old_bundle = root / "stage", root / "prior-stage"
            bundle(bundle_path, serialized([(1, 0, b"x"), (2, 1, b"a"), (4, 1, b"q")]))
            bundle(old_bundle, serialized([(1, 0, b"x"), (2, 1, b"b"), (3, 0, b"y")]))
            level = serialized([(1, 0, b"s")])
            with ZipFile(candidate, "w") as apk:
                apk.writestr(S.PLAYER + "level0", level)
                apk.write(bundle_path, S.EMBEDDED + "stage")
                apk.writestr(S.INDEX, json.dumps(dict(files=[dict(name="stage", bytes=bundle_path.stat().st_size, sha256=pin(bundle_path)["sha256"])])))
            with ZipFile(reference, "w") as apk:
                apk.writestr(S.PLAYER + "level0", level)
            payload = root / "receipt.json"
            payload.write_text(json.dumps(dict(apk_sha256=pin(reference)["sha256"], payload={"prior-stage": pin(old_bundle)["sha256"]})))
            request = dict(
                schema="whole-game-scoreboard-request-v1",
                candidate={"apk": pin(candidate)},
                reference={"apk": pin(reference), "external_payload": {"receipt": pin(payload), "directory": str(root)}},
            )
            # The member IDs cannot match across differently named runtime bundles.
            self.assertEqual(S.build(request)["totals"], dict(exact=1, approximate=0, missing=3, unverified=3))
            old_root = root / "prior"
            old_root.mkdir()
            old_bundle.rename(old_root / "stage")
            payload.write_text(json.dumps(dict(apk_sha256=pin(reference)["sha256"], payload={"stage": pin(old_root / "stage")["sha256"]})))
            request["reference"]["external_payload"] = dict(receipt=pin(payload), directory=str(old_root))
            terminal = root / "terminal.done.json"
            terminal.write_text(json.dumps(dict(apk_sha256=pin(candidate)["sha256"], process_checkpoints=[dict(phase="launch", verified_launch_pid="123")])))
            (root / "world-start.json").write_text(
                json.dumps(dict(pid=123, phase="integrated-world-playing", world={"ready": True}, stage={"scene": "fixture"}))
            )
            request["device_receipts"] = [pin(terminal)]
            result = S.build(request)
            self.assertEqual(result["totals"], dict(exact=2, approximate=1, missing=1, unverified=1))
            self.assertEqual(result["files"]["candidate"], dict(bundles=1, bundle_members=1, player_members=1))
            self.assertEqual(
                result["device"], dict(launch="passed", menu="unobserved", first_stage="passed", stage_transition="unobserved", stages=["fixture"])
            )
            self.assertEqual([row["owner"] for row in result["classes"]], ["p1-textures", "p1-scenes-w"])
            terminal.write_text(json.dumps(dict(apk_sha256=pin(reference)["sha256"])))
            request["device_receipts"] = [pin(terminal)]
            with self.assertRaisesRegex(ValueError, "different build"):
                S.build(request)
