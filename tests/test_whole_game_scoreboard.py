"""Scoreboard coverage for standalone files, bundle members and attempt evidence."""

import importlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/phone-build/accepted-output"))
S = importlib.import_module("whole_game_scoreboard")
STAGE_SPEC = importlib.util.spec_from_file_location("scoreboard_lab_stage", ROOT / "tools/phone-build/owner-apk/lab_stage.py")
STAGE = importlib.util.module_from_spec(STAGE_SPEC)
STAGE_SPEC.loader.exec_module(STAGE)


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
    def test_lab_stage_returns_scoreboard_for_pinned_phone_local_apks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner_input = root / "owner-input"
            inputs = owner_input / "staged"
            inputs.mkdir(parents=True)
            pins = {}
            for name, body in (("candidate", b"a"), ("reference", b"b")):
                apk = inputs / (name + ".apk")
                with ZipFile(apk, "w") as archive:
                    archive.writestr(S.PLAYER + "level0", serialized([(1, 0, b"x"), (2, 1, body)]))
                pins[name] = {"apk": dict(path=apk.name, sha256=pin(apk)["sha256"])}
            request = inputs / "request.json"
            request.write_text(json.dumps(dict(schema="whole-game-scoreboard-request-v1", **pins)))
            descriptor = root / "stage.json"
            descriptor.write_text(
                json.dumps(
                    dict(
                        producer=STAGE.SCOREBOARD,
                        input_root="staged",
                        input_pins={"request.json": pin(request)["sha256"]},
                        arguments=[{"inputs": "request.json"}, "--output", {"output": "scoreboard.json"}],
                        artifacts={"scoreboard": "scoreboard.json"},
                        scoreboard="scoreboard.json",
                    )
                )
            )
            output = root / "output"
            receipt = root / "result.json"
            self.assertEqual(STAGE.run(STAGE.load_stage(descriptor), ROOT, owner_input, output, ROOT, ROOT, [sys.executable], receipt), 0)
            result = json.loads(receipt.read_bytes())
            scoreboard = json.loads((root / "scoreboard.json").read_bytes())
            self.assertTrue(result["success"])
            self.assertEqual(result["artifacts"]["scoreboard"]["sha256"], pin(output / "scoreboard.json")["sha256"])
            self.assertEqual(scoreboard["apk_sha256"], pins["candidate"]["apk"]["sha256"])
            self.assertEqual(scoreboard["reference_apk_sha256"], pins["reference"]["apk"]["sha256"])
            self.assertEqual(scoreboard["totals"], dict(exact=1, approximate=1, missing=0, unverified=0))
            self.assertEqual(scoreboard["device"]["launch"], "unobserved")

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
            census = root / "census.json"
            S.write(census, dict(result, device=S.device_observations([], result["apk_sha256"])))
            candidate.unlink()
            reference.unlink()
            request = dict(schema=request["schema"], census=pin(census), device_receipts=request["device_receipts"])
            self.assertEqual(S.build(request), result)
            terminal.write_text(json.dumps(dict(apk_sha256=result["reference_apk_sha256"])))
            request["device_receipts"] = [pin(terminal)]
            with self.assertRaisesRegex(ValueError, "different build"):
                S.build(request)
