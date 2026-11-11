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


def notification_xml(button="permission_deny_and_dont_ask_again_button"):
    controller = "com.android.permissioncontroller"
    tree = ET.Element("hierarchy")
    root = ET.SubElement(tree, "node", {"package": controller})
    ET.SubElement(
        root, "node", {"package": controller, "resource-id": controller + ":id/permission_message", "text": "Allow Owner game installer to send notifications?"}
    )
    ET.SubElement(
        root,
        "node",
        {
            "package": controller,
            "resource-id": controller + ":id/" + button,
            "class": "android.widget.Button",
            "enabled": "true",
            "clickable": "true",
            "bounds": "[1,2][3,4]",
            "text": "PRIVATE SENTINEL",
        },
    )
    return ET.tostring(tree, encoding="utf-8", xml_declaration=True)


def retained_notification(root, *, run_id="43117215117", bound=False):
    source = "3aeb5702381a4db584323674239af674161633a1"
    runner = root / "work/coordination/lab-runner" / run_id
    runner.mkdir(parents=True)
    row = {"mode": "graphics-picker-smoke", "success": False, "synthetic_only": True, "reason": "notification-denial-unavailable"}
    (runner / "output.log").write_text("$ git -C private fetch -q origin " + source + "\n" + json.dumps(row) + "\n")
    directory = root / "work/coordination/graphics-picker-smoke/run-authored"
    directory.mkdir(parents=True)
    for name, phase in (("00001-resolve-source-commit", "admission"), ("00123-device-ui-read", "picker-ui")):
        (directory / (name + ".json")).write_text(json.dumps({"category": name[6:], "phase": phase, "returncode": 0, "outcome": "returned"}))
        stamp = G.datetime.fromisoformat("2026-11-11T23:07:00+00:00").timestamp()
        os.utime(directory / (name + ".json"), (stamp, stamp))
    (directory / "00001-resolve-source-commit.stdout.log").write_text(source + "\n")
    (directory / "00123-device-ui-read.stdout.log").write_bytes(notification_xml())
    if bound:
        (directory / "runner-binding.json").write_text(json.dumps({"lab_run_id": run_id}))
    return directory


class GraphicsPickerTests(unittest.TestCase):
    def test_notification_classifier_emits_fixed_classes_counts_and_no_raw_values(self):
        tree = ET.fromstring(notification_xml())
        node = tree.find("node/node[@class='android.widget.Button']")
        node.set("resource-id", "com.android.permissioncontroller:id/permission_deny_button")
        node.set("enabled", "false")
        node.set("bounds", "[1,1][1,1]")
        tree.find("node").append(ET.fromstring(ET.tostring(node)))
        unknown = ET.SubElement(
            tree.find("node"), "node", {"package": "com.android.permissioncontroller", "class": "android.widget.Button", "resource-id": "PRIVATE SENTINEL"}
        )
        unknown.set("text", "PRIVATE SENTINEL")
        result = G.notification_summary(ET.tostring(tree, encoding="utf-8", xml_declaration=True))
        deny = next(row for row in result["actions"] if row["class"] == "permission_deny_button")
        self.assertEqual(deny, {"class": "permission_deny_button", "count": 2, "enabled": 0, "clickable": 2, "bounds_valid": 0})
        self.assertEqual(result["actions"][-1]["count"], 1)
        self.assertNotIn("PRIVATE SENTINEL", json.dumps(result))

    def test_notification_classifier_rejects_foreign_purpose_packages_and_entities(self):
        data = notification_xml()
        for value in (
            data.replace(b"notifications", b"camera"),
            data.replace(b"Owner game installer", b"Another app"),
            data.replace(b"com.android.permissioncontroller", b"foreign"),
            data + b"<!ENTITY authored>",
            b"x" * (1024 * 1024 + 1),
        ):
            with self.subTest(value=value[:50]), self.assertRaises(G.LAB.Failure):
                G.notification_summary(value)

    def test_notification_classifier_uses_only_focused_display_zero_window(self):
        document = ET.Element("displays")
        display = ET.SubElement(document, "display", {"id": "0"})
        window = ET.SubElement(
            display,
            "window",
            {
                "index": "0",
                "title": "PRIVATE SENTINEL",
                "type": "TYPE_APPLICATION",
                "layer": "1",
                "active": "true",
                "focused": "true",
                "accessibility-focused": "false",
                "bounds": "[0,0][500,500]",
            },
        )
        window.append(ET.fromstring(notification_xml()))
        with patch.object(G.LAB, "focused_ui_hierarchy", return_value=ET.fromstring(notification_xml())) as focus:
            result = G.notification_summary(ET.tostring(document, encoding="utf-8", xml_declaration=True))
        self.assertTrue(result["owned_notification_message"])
        self.assertEqual(focus.call_args.args[1], ("com.android.permissioncontroller",))

    def test_notification_inspector_distinguishes_legacy_candidate_from_runner_id_binding(self):
        for bound in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                retained_notification(root, bound=bound)
                output = io.StringIO()
                with patch.object(G, "ROOT", root), patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
                    self.assertEqual(G.inspect_notification("43117215117"), 0)
                result = json.loads(output.getvalue())
                self.assertEqual(result["binding"], "runner-id" if bound else "legacy-unique-source-time-candidate")
                self.assertEqual(result["actions"][2]["count"], 1)
                self.assertNotIn(temporary, output.getvalue())
                self.assertNotIn("PRIVATE SENTINEL", output.getvalue())

    def test_notification_inspector_refuses_ambiguous_missing_changed_or_unbound_evidence(self):
        for mode in (
            "ambiguous",
            "source",
            "wrong-result",
            "outside-window",
            "wrong-phase",
            "missing",
            "symlink",
            "metadata-symlink",
            "oversize",
            "malformed",
            "wrong-run",
        ):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = retained_notification(root)
                if mode == "ambiguous":
                    duplicate = directory.with_name("run-copyhere")
                    duplicate.mkdir()
                    marker = duplicate / "00001-resolve-source-commit.json"
                    marker.write_text("{}")
                    stamp = (directory / marker.name).stat().st_mtime
                    os.utime(marker, (stamp, stamp))
                elif mode == "source":
                    (directory / "00001-resolve-source-commit.stdout.log").write_text("a" * 40)
                elif mode == "wrong-result":
                    (root / "work/coordination/lab-runner/43117215117/output.log").write_text("{}")
                elif mode == "outside-window":
                    os.utime(directory / "00123-device-ui-read.json", (1, 1))
                elif mode == "wrong-phase":
                    path = directory / "00123-device-ui-read.json"
                    path.write_text(path.read_text().replace("picker-ui", "picker-cleanup"))
                elif mode == "metadata-symlink":
                    path = directory / "00123-device-ui-read.json"
                    outside = root / "not-owned"
                    path.rename(outside)
                    path.symlink_to(outside)
                elif mode in ("missing", "symlink", "oversize", "malformed"):
                    path = directory / "00123-device-ui-read.stdout.log"
                    path.unlink()
                    if mode == "symlink":
                        path.symlink_to(root / "not-owned")
                    elif mode == "oversize":
                        path.write_bytes(b"x" * (1024 * 1024 + 1))
                    elif mode == "malformed":
                        path.write_bytes(b"<?xml version='1.0'?><hierarchy>PRIVATE SENTINEL</hierarchy>")
                output = io.StringIO()
                with self.subTest(mode=mode), patch.object(G, "ROOT", root), patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
                    self.assertEqual(G.inspect_notification("999" if mode == "wrong-run" else "43117215117"), 1)
                self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")
                self.assertNotIn("PRIVATE SENTINEL", output.getvalue())
                self.assertNotIn(temporary, output.getvalue())

    def test_notification_inspection_cli_never_constructs_phone_or_discovers_toolchain(self):
        for argv, env in (
            (["--inspect-notification-run", "../bad"], {}),
            (["--inspect-notification-run", "43117215117", "--timeout", "30"], {}),
            (["--inspect-notification-run", "43117215117"], {"LAB_DEVICE_SERIAL": "authored-selector"}),
        ):
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(G.LAB, "Phone") as phone,
                patch.object(G.LAB, "read_context") as context,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(G.main(argv), 1)
                phone.assert_not_called()
                context.assert_not_called()

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

    def test_smoke_records_only_a_valid_runner_id_without_changing_diagnostic_sequence(self):
        for run_id in ("43117215117", "PRIVATE SENTINEL"):
            diagnostics = Mock()
            with (
                patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "authored-selector", "LAB_RUN_ID": run_id}),
                patch.object(G.LAB, "PrivateDiagnostics", return_value=diagnostics),
                patch.object(G.LAB, "read_context", side_effect=G.LAB.Failure("authored-stop-before-device")),
                patch.object(G.LAB, "Phone") as phone,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(G.main([]), 1)
            name, data = diagnostics.write.call_args.args
            self.assertEqual(name, "runner-binding.json")
            self.assertEqual(json.loads(data), {"lab_run_id": run_id if run_id.isdigit() else None})
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
