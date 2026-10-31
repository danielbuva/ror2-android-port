"""Standalone source-registry emission uses the existing owner and pins inputs."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


S = load("registry_phase", ROOT / "tools/phone-build/accepted-output/script_registry.py")
F = load("registry_fixture", ROOT / "tests/test_phone_record_producer.py")


class ScriptRegistryTests(unittest.TestCase):
    def test_serialized_phase_and_source_drift_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            pc = root / "pc"
            pc.mkdir()
            source = root / "authored-source"
            source.write_bytes(b"original authored input")
            profile = root / "profile.json"
            profile.write_text(json.dumps({"input_id": S.P.INPUT_ID}))
            body = b"authored script fixture"
            stream = io.BytesIO(F.serialized(body, F.F.node("Base", len(body), kind="UInt8"), class_id=115))
            stream.size = len(stream.getvalue())
            value = {
                "layout": S.P.W.read_serialized(stream),
                "bodies": {77: body},
                "script_ids": {("Authored.dll", "", "Demo"): 77},
                "provider_pins": {str(source): {"bytes": source.stat().st_size, "sha256": S.P.sha(source)}},
            }
            with patch.object(S.P, "registry_records", return_value=value) as owner:
                result = S.produce(profile, S.P.sha(profile), pc, root, root / "request.json", root, root / "output")
            owner.assert_called_once()
            self.assertTrue(result["success"])
            self.assertEqual(result["scripts"], 1)
            path = root / "output" / S.NAME
            self.assertEqual(result["files"][S.NAME]["sha256"], S.P.sha(path))
            with path.open("rb") as f:
                f.size = path.stat().st_size
                metadata = S.P.W.read_serialized(f)
                row = metadata["objects"][0]
                f.seek(metadata["data_offset"] + row["offset"])
                self.assertEqual(S.P.OBJECTS.B.exact(f, row["bytes"]), body)
            source.write_bytes(b"changed source")
            with patch.object(S.P, "registry_records", return_value=value), self.assertRaisesRegex(ValueError, "bytes differ"):
                S.produce(profile, S.P.sha(profile), pc, root, root / "request.json", root, root / "failed")
            self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
