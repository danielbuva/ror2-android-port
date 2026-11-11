"""Authored host-only picker smoke contracts; never calls ADB, a compiler or a driver."""

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lab_graphics_picker", ROOT / "scripts/lab-graphics-picker.py")
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)
MANIFEST = "package: name='dev.ror2lab.installertest' versionCode='3'\napplication-debuggable\n"
WINDOW = "Window{abc u0 dev.ror2lab.installertest/dev.ror2lab.phonebuildhostfixture.ToolHostActivity}"
ACTIVITY = (
    "ACTIVITY MANAGER TOP-RESUMED (dumpsys activity top-resumed)\n"
    f"packageName={G.LAB.PACKAGE} processName={G.LAB.PACKAGE}\n"
    "launchedFromUid=2000 launchedFromPackage=com.android.shell launchedFromFeature=null userId=0\n"
    "app=ProcessRecord{authored}\n"
    f"Intent {{ cmp={G.LAB.ACTIVITY} (has extras) }}\n"
    f"mActivityComponent={G.LAB.ACTIVITY}\n"
    "state=RESUMED stopped=false delayedResume=false finishing=false\n"
    "occludesParent=true noDisplay=false immersive=false launchMode=0\n"
    "mVisibleRequested=true mVisible=true mClientVisible=true reportedDrawn=true reportedVisible=true\n"
    f"windows=[{WINDOW}]\n"
).encode()
DISPLAYS = ("WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n  Display: mDisplayId=0\n    mCurrentFocus=" + WINDOW + "\n").encode()


def hierarchy():
    tree = ET.Element("hierarchy")
    root = ET.SubElement(tree, "node", {"package": G.LAB.PACKAGE, "bounds": "[0,0][500,500]"})
    ET.SubElement(
        root,
        "node",
        {
            "package": G.LAB.PACKAGE,
            "text": "Use System driver",
            "class": "android.widget.Button",
            "enabled": "true",
            "clickable": "true",
            "bounds": "[10,20][100,80]",
        },
    )
    return tree


class GraphicsPickerTests(unittest.TestCase):
    def test_fixture_is_deterministic_bounded_and_non_executable(self):
        data = G.fixture_bytes()
        self.assertEqual(data, G.fixture_bytes())
        self.assertLessEqual(len(data), 4096)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()), {"meta.json", "libvulkan_fixture.so"})
            library = archive.read("libvulkan_fixture.so")
            self.assertEqual(len(library), 64)
            self.assertEqual(library[:7], b"\x7fELF\x02\x01\x01")
            self.assertEqual(library[16:20], b"\x03\x00\xb7\x00")
            self.assertEqual(library[20:], bytes(44))
            self.assertEqual(json.loads(archive.read("meta.json"))["driverVersion"], "synthetic-only")

    def test_actual_manifest_admission_requires_owned_debug_apk_and_receipt_version(self):
        G.LAB.require_installer_manifest(MANIFEST, 3)
        for value, version in (
            (MANIFEST, 4),
            (MANIFEST, True),
            (MANIFEST, "3"),
            (MANIFEST.replace("installertest", "alpha"), 3),
            (MANIFEST.replace("application-debuggable", ""), 3),
            (MANIFEST.replace("'3'", "'2'"), 2),
            (MANIFEST.replace("application-debuggable", "label: application-debuggable"), 3),
        ):
            with self.subTest(value=value, version=version), self.assertRaises(G.LAB.Failure):
                G.LAB.require_installer_manifest(value, version)

    def test_toolhost_receipt_binds_exact_commit_and_apk_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commit = "a" * 40
            cached = root / commit
            cached.mkdir()
            apk = cached / "signed.apk"
            apk.write_bytes(b"authored apk fixture; not executable")
            expected = hashlib.sha256(apk.read_bytes()).hexdigest()
            receipt = {"success": True, "package": G.LAB.PACKAGE, "source_commit": commit, "apk_sha256": expected, "version_code": 3}
            value = cached / "result.json"
            paths = [root / name for name in ("sdk", "jdk", "ndk")]
            for path in paths:
                path.mkdir()
            env = b"\0".join(str(path).encode() for path in paths) + b"\0"
            for change, accepted in (
                ({}, True),
                ({"source_commit": "b" * 40}, False),
                ({"apk_sha256": "c" * 64}, False),
                ({"package": "dev.ror2lab.alpha"}, False),
                ({"success": False}, False),
            ):
                value.write_text(json.dumps(receipt | change))
                with patch.dict(os.environ, {"LAB_TOOLHOST_ROOT": str(root)}), patch.object(G.LAB, "run", side_effect=[commit.encode(), env]):
                    if accepted:
                        self.assertEqual(G.LAB.read_context()["installer_sha256"], expected)
                    else:
                        with self.assertRaises(G.LAB.Failure):
                            G.LAB.read_context()

    def test_focus_requires_exact_resumed_visible_owned_component_on_display_zero(self):
        self.assertEqual(G.owned_focus(ACTIVITY, b"0\n", DISPLAYS), G.LAB.sha(WINDOW.encode()))
        for activity, user, displays in (
            (ACTIVITY.replace(b"state=RESUMED", b"state=PAUSED"), b"0", DISPLAYS),
            (ACTIVITY.replace(b"mVisible=true", b"mVisible=false"), b"0", DISPLAYS),
            (ACTIVITY + b"state=RESUMED stopped=false delayedResume=false finishing=false\n", b"0", DISPLAYS),
            (ACTIVITY.replace(b"mActivityComponent=" + G.LAB.ACTIVITY.encode(), b"mActivityComponent=foreign/.Activity"), b"0", DISPLAYS),
            (ACTIVITY, b"10", DISPLAYS),
            (ACTIVITY, b"0", DISPLAYS.replace(b"mDisplayId=0", b"mDisplayId=1")),
            (ACTIVITY, b"0", DISPLAYS.replace(b"Window{abc", b"Window{def")),
        ):
            with self.subTest(activity=activity, user=user, displays=displays), self.assertRaises(G.LAB.Failure):
                G.owned_focus(activity, user, displays)

    def test_control_selection_refuses_foreign_duplicate_and_invalid_bounds(self):
        tree = hierarchy()
        self.assertIsNotNone(G.unique_node(tree, label="Use System driver"))
        tree.find("node/node").set("package", "foreign")
        with self.assertRaises(G.LAB.Failure):
            G.unique_node(tree, label="Use System driver")
        tree = hierarchy()
        tree.find("node").append(ET.fromstring(ET.tostring(tree.find("node/node"))))
        with self.assertRaises(G.LAB.Failure):
            G.unique_node(tree, label="Use System driver")
        tree = hierarchy()
        tree.find("node/node").set("bounds", "[10,10][10,10]")
        self.assertIsNone(G.unique_node(tree, label="Use System driver"))

    def test_no_tap_when_focus_changes_or_control_disabled(self):
        for disabled, focus in ((True, "before"), (False, "after")):
            phone = Mock()
            picker = G.Picker(phone, 30)
            node = hierarchy().find("node/node")
            if disabled:
                node.set("enabled", "false")
            with patch.object(picker, "find", return_value=(node, "before")), patch.object(picker, "identity", return_value=focus):
                with self.assertRaises(G.LAB.Failure):
                    picker.tap("Use System driver")
            phone.tap_prompt_node.assert_not_called()

    def test_snapshot_rejects_changed_focus_before_any_control_is_used(self):
        picker = G.Picker(Mock(), 30)
        with patch.object(picker, "identity", side_effect=["before", "after"]), self.assertRaises(G.LAB.Failure):
            picker.snapshot()
        picker.phone.tap_prompt_node.assert_not_called()

    def test_preexisting_package_and_changed_apk_refuse_before_install(self):
        phone = Mock()
        phone.occupied.return_value = True
        with self.assertRaises(G.LAB.Failure):
            G.acceptance(phone, {}, Mock(), 30)
        phone.install.assert_not_called()
        phone.occupied.return_value = False
        apk = Mock()
        apk.read_bytes.return_value = b"authored changed bytes"
        with patch.object(G.LAB, "run", return_value=MANIFEST.encode()), self.assertRaises(G.LAB.Failure):
            G.acceptance(phone, {"installer_apk": apk, "installer_version": 3, "installer_sha256": "0" * 64, "android_sdk": Path("/authored")}, Mock(), 30)
        phone.install.assert_not_called()

    def test_only_fixed_fixture_names_can_be_written(self):
        phone = Mock()
        with self.assertRaises(G.LAB.Failure):
            G.put(phone, "../foreign", b"authored")
        phone.command.assert_not_called()

    def test_acceptance_uses_only_picker_cases_not_installer_acceptance_or_keys(self):
        phone, apk, picker = Mock(), Mock(), Mock()
        phone.occupied.return_value = False
        apk.read_bytes.return_value = b"authored apk"
        digest = G.LAB.sha(apk.read_bytes())
        phone.package_hash.return_value = digest
        phone.shell.return_value = b"system\nsystem\n"
        picker.find.return_value = (ET.Element("node", {"text": "BSD-2-Clause 8fae8ce254dfc1344527e05301e43f37dea2df80 No proprietary Qualcomm"}), "focus")
        cases = []
        with (
            patch.object(G.LAB, "run", return_value=MANIFEST.encode()),
            patch.object(G, "start") as start,
            patch.object(G, "Picker", return_value=picker),
            patch.object(G.LAB, "prepare_artifacts") as artifacts,
            patch.object(G.LAB, "acceptance") as installer,
        ):
            G.acceptance(phone, {"installer_apk": apk, "installer_version": 3, "installer_sha256": digest, "android_sdk": Path("/authored")}, cases.append, 30)
        self.assertEqual(cases, list(G.CASES))
        self.assertEqual(start.call_count, 2)
        self.assertEqual(phone.storage.call_count, 2)
        artifacts.assert_not_called()
        installer.assert_not_called()
        self.assertNotIn("Open Android Developer options", [call.args[0] for call in picker.tap.call_args_list])

    def test_main_missing_device_has_no_side_effects(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(G.LAB, "read_context") as context,
            patch.object(G.LAB, "Phone") as phone,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(G.main([]), 1)
        context.assert_not_called()
        phone.assert_not_called()

    def test_main_requires_all_declared_cases_and_verified_cleanup_and_sanitizes_errors(self):
        for mode in ("pass", "cleanup-failed", "missing-case", "unknown-case", "private-error"):
            phone = Mock()
            phone.cleanup.return_value = "verified-absent"
            if mode == "cleanup-failed":
                phone.cleanup.side_effect = RuntimeError("private cleanup detail")

            def accept(_phone, _config, passed, _timeout):
                if mode == "private-error":
                    raise RuntimeError("private source path")
                for case in G.CASES[:-1] if mode == "missing-case" else G.CASES:
                    passed(case)
                if mode == "unknown-case":
                    passed("not-an-authorized-case")

            output = io.StringIO()
            with (
                patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "authored-selector"}),
                patch.object(G.LAB, "PrivateDiagnostics"),
                patch.object(G.LAB, "read_context", return_value={}),
                patch.object(G.LAB, "Phone", return_value=phone),
                patch.object(G, "acceptance", side_effect=accept),
                redirect_stdout(output),
            ):
                self.assertEqual(G.main([]), 0 if mode == "pass" else 1)
            phone.cleanup.assert_called_once()
            self.assertNotIn("private source path", output.getvalue())
            self.assertNotIn("private cleanup detail", output.getvalue())
            result = json.loads(output.getvalue().splitlines()[-1])
            self.assertEqual(result["success"], mode == "pass")


if __name__ == "__main__":
    unittest.main()
