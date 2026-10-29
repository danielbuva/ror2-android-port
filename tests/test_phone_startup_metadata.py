"""Public startup production and narrow APK admission, using invented inputs."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


P = load("startup_under_test", "tools/phone-build/accepted-output/startup_metadata.py")
OWNER = load("startup_apk_under_test", "tools/phone-build/owner-apk/build_owner_apk.py")


class StartupTests(unittest.TestCase):
    def produce(self, root, name="output"):
        paths = [root / name for name in ("inventory.json", "settings.asset", "toolchain.json")]
        paths[0].write_text('{"files":["invented original input"]}')
        paths[1].write_text("PlayerSettings:\n  useHDRDisplay: 0\n  gcIncremental: 1\n  androidStartInFullscreen: 1\n  androidRenderOutsideSafeArea: 1\n")
        paths[2].write_text(json.dumps({"unity_version": "2021.3.45f2", "unity_revision": "88f88f591b2e", "architecture": "arm64"}))
        receipt = P.produce(*paths, root / name)
        return receipt, root / name / "result.json"

    def test_complete_boot_policy_and_repeatable_relocated_build_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, path = self.produce(root)
            boot = Path(first["outputs"][P.PREFIX + "boot.config"]["path"]).read_bytes()
            self.assertEqual(
                boot, b"wait-for-native-debugger=0\nhdr-display-enabled=0\ngc-max-time-slice=3\nandroidStartInFullscreen=1\nandroidRenderOutsideSafeArea=1\n"
            )
            app = Path(first["outputs"][P.PREFIX + "unity_app_guid"]["path"]).read_text()
            self.assertEqual(str(uuid.UUID(app)), app)
            self.assertEqual(len(app), 36)
            self.assertNotEqual(uuid.UUID(app).hex, first["build_guid"])
            other = root / "relocated"
            other.mkdir()
            second, _ = self.produce(other)
            self.assertEqual(first["build_guid"], second["build_guid"])
            self.assertEqual({k: v["sha256"] for k, v in first["outputs"].items()}, {k: v["sha256"] for k, v in second["outputs"].items()})
            self.assertEqual(P.verify(path, P.digest(path)), first["outputs"])
            changed = copy.deepcopy(first["inputs"])
            inventory = root / "different.json"
            inventory.write_text('{"files":["updated original input"]}')
            changed["inventory"] = P.pin(inventory)
            self.assertNotEqual(P.render(changed)[1], first["build_guid"])

    def test_receipt_cannot_admit_arbitrary_or_modified_startup_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt, path = self.produce(root)
            boot = Path(receipt["outputs"][P.PREFIX + "boot.config"]["path"])
            boot.write_bytes(boot.read_bytes() + b"player-connection-ip=private\n")
            receipt["outputs"][P.PREFIX + "boot.config"] = P.pin(boot)
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "public inputs"):
                P.verify(path, P.digest(path))

    def test_admission_is_separate_from_exact_and_does_not_cover_game_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, path = self.produce(root)
            targets = root / "output/targets"
            unknown = targets / (P.PREFIX + "globalgamemanagers")
            unknown.write_bytes(b"incorrect invented manager")
            rows = [{"path": name, "bytes": 1, "sha256": "0" * 64} for name in sorted(P.NAMES | {P.PREFIX + "globalgamemanagers"})]
            request = {"manifest": "unused", "manifest_sha256": OWNER.PROFILE, "targets": str(targets)}
            with patch.object(OWNER.PACKET, "profile", return_value=(b"", {"targets": rows})):
                before = OWNER.check(request)
                self.assertEqual(len(before["blocked_entries"]), 3)
                request["startup_metadata"] = {"path": str(path), "sha256": P.digest(path)}
                after = OWNER.check(request)
            self.assertEqual(after["generated_metadata_count"], 2)
            self.assertEqual(after["exact_count"], 0)
            self.assertEqual(after["blocked_entries"], [P.PREFIX + "globalgamemanagers"])
            self.assertFalse(after["assembly_ready"])
            self.assertFalse(after["device_qualified"])

    def test_changed_inputs_and_unknown_settings_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt, path = self.produce(root)
            settings = root / "settings.asset"
            settings.write_text(settings.read_text().replace("gcIncremental: 1", "gcIncremental: 0"))
            with self.assertRaisesRegex(ValueError, "input changed"):
                P.verify(path, P.digest(path))
            receipt["inputs"]["settings"] = P.pin(settings)
            with self.assertRaisesRegex(ValueError, "incremental GC"):
                P.render(receipt["inputs"])


if __name__ == "__main__":
    unittest.main()
