#!/usr/bin/env python3
"""Current: exact-source, synthetic-only picker UI smoke through the serialized /lab runner.

No game install/update, real driver, download, native load, Settings navigation or
permission grant. Reuses the installer owner's APK binding, storage and cleanup.
Only fixed results leave the lab; raw UI evidence stays in the owned private run.
"""

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("graphics_installer_owner", ROOT / "scripts/lab-installer-updates.py")
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)
CASES = (
    "system-default",
    "active-driver-unavailable",
    "adreno-unavailable",
    "source-license-visible",
    "synthetic-package-verified",
    "invalid-hash-refused",
    "mali-unavailable",
    "system-reset-cold-start",
    "close-reopen",
)


def fixture_bytes():
    library = bytearray(64)
    library[:7] = b"\x7fELF\x02\x01\x01"
    library[16:20] = b"\x03\x00\xb7\x00"
    metadata = {"schemaVersion": 1, "name": "Authored graphics fixture", "driverVersion": "synthetic-only", "minApi": 28, "libraryName": "libvulkan_fixture.so"}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in (("meta.json", json.dumps(metadata).encode()), ("libvulkan_fixture.so", library)):
            row = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            row.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(row, data)
    return output.getvalue()


def owned_focus(activity, user, displays):
    """Join the exact owned ToolHostActivity record to display-0 focus; no Settings parser."""
    if not isinstance(activity, bytes) or len(activity) > 65536 or not isinstance(user, bytes) or len(user) > 64:
        raise LAB.Failure("picker-activity-unverified")
    try:
        lines, current = activity.decode("utf-8").splitlines(), user.decode("ascii").strip()
    except UnicodeError:
        raise LAB.Failure("picker-activity-unverified") from None
    header = "ACTIVITY MANAGER TOP-RESUMED (dumpsys activity top-resumed)"
    fields = ("packageName=", "launchedFromUid=", "mActivityComponent=", "state=", "occludesParent=", "mVisibleRequested=")
    rows = {field: [line for line in lines if line.startswith(field)] for field in fields}
    if not lines or lines[0] != header or lines.count(header) != 1 or any(len(values) != 1 for values in rows.values()):
        raise LAB.Failure("picker-activity-unverified")
    if (
        len(lines) < 5
        or lines[1] != rows["packageName="][0]
        or lines[2] != rows["launchedFromUid="][0]
        or not lines[3].startswith("app=")
        or not lines[4].startswith("Intent { ")
    ):
        raise LAB.Failure("picker-activity-unverified")
    caller = re.fullmatch(
        r"launchedFromUid=[0-9]+ launchedFromPackage=com\.android\.shell launchedFromFeature=null userId=([0-9]+)", rows["launchedFromUid="][0]
    )
    if (
        rows["packageName="][0] != f"packageName={LAB.PACKAGE} processName={LAB.PACKAGE}"
        or rows["mActivityComponent="][0] != "mActivityComponent=" + LAB.ACTIVITY
        or caller is None
        or not re.fullmatch(r"[0-9]+", current)
        or caller.group(1) != current
        or rows["state="][0] != "state=RESUMED stopped=false delayedResume=false finishing=false"
        or not re.fullmatch(r"occludesParent=(?:true|false) noDisplay=false immersive=(?:true|false) launchMode=[0-9]+", rows["occludesParent="][0])
        or rows["mVisibleRequested="][0] != "mVisibleRequested=true mVisible=true mClientVisible=true reportedDrawn=true reportedVisible=true"
    ):
        raise LAB.Failure("picker-activity-unverified")
    matched, fingerprint = LAB.settings_window_identity(activity, displays)  # Generic ActivityRecord.windows/display join only.
    if not matched:
        raise LAB.Failure("picker-focus-unverified")
    return fingerprint


def bounds(node):
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if match:
        box = tuple(map(int, match.groups()))
        if box[0] < box[2] and box[1] < box[3]:
            return box
    return None


def unique_node(tree, *, label=None, description=None):
    roots = tree.findall("node")
    if len(roots) != 1 or roots[0].get("package") != LAB.PACKAGE or any(n.get("package") not in (None, "", LAB.PACKAGE) for n in tree.iter("node")):
        raise LAB.Failure("picker-ui-owner-unverified")
    nodes = [
        n
        for n in tree.iter("node")
        if (n.get("content-desc") == description if description else n.get("text", "").casefold() == label.casefold()) and bounds(n)
    ]
    if len(nodes) > 1:
        raise LAB.Failure("picker-ui-control-ambiguous")
    return nodes[0] if nodes else None


class Picker:
    def __init__(self, phone, timeout):
        self.phone, self.deadline = phone, time.monotonic() + timeout

    def identity(self):
        self.phone.require_owned_installer()
        outputs = []
        for command in ("dumpsys activity top-resumed | head -c 65537", "am get-current-user | head -c 65", "dumpsys window displays | head -c 131073"):
            result = LAB.execute(
                [self.phone.adb, "-s", self.phone.serial, "shell", "sh", "-c", "'" + command + "'"],
                label="picker-identity-query",
                timeout=15,
                record_output=False,
            )
            if result.returncode or result.stderr:
                raise LAB.Failure("picker-identity-query")
            outputs.append(result.stdout)
        return owned_focus(*outputs)

    def snapshot(self):
        if time.monotonic() > self.deadline:
            raise LAB.Failure("picker-time-limit")
        self.phone.require_owned_installer()
        self.phone.shell("input", "keyevent", "KEYCODE_WAKEUP", label="picker-display-wake")
        fingerprint = self.identity()
        tree = self.phone.ui_windows((LAB.PACKAGE,), recovery=False)
        if self.identity() != fingerprint:
            raise LAB.Failure("picker-focus-changed")
        return tree, fingerprint

    def find(self, **selector):
        # Bounded accessibility-driven search in one focused owned ScrollView.
        for direction in (1, -1):
            previous = None
            for _ in range(7):
                tree, fingerprint = self.snapshot()
                node = unique_node(tree, **selector)
                if node is not None:
                    return node, fingerprint
                view = tuple((n.get("text"), n.get("bounds")) for n in tree.iter("node"))
                if view == previous:
                    break
                previous = view
                scrolls = [n for n in tree.iter("node") if n.get("scrollable") == "true" and bounds(n)]
                if len(scrolls) != 1:
                    raise LAB.Failure("picker-ui-scroll-unverified")
                x1, y1, x2, y2 = bounds(scrolls[0])
                top, bottom = y1 + (y2 - y1) // 5, y2 - (y2 - y1) // 5
                if self.identity() != fingerprint:
                    raise LAB.Failure("picker-focus-changed")
                start, end = (bottom, top) if direction == 1 else (top, bottom)
                self.phone.shell("input", "swipe", str((x1 + x2) // 2), str(start), str((x1 + x2) // 2), str(end), "250", label="picker-ui-scroll")
        raise LAB.Failure("picker-ui-control-missing")

    def tap(self, label):
        node, fingerprint = self.find(label=label)
        if node.get("enabled") != "true" or node.get("clickable") != "true" or node.get("class") != "android.widget.Button":
            raise LAB.Failure("picker-ui-control-disabled")
        if self.identity() != fingerprint:
            raise LAB.Failure("picker-focus-changed")
        self.phone.tap_prompt_node(node, "picker-ui-tap")

    def text(self, description, *expected):
        node, _ = self.find(description=description)
        if any(value not in node.get("text", "") for value in expected):
            raise LAB.Failure("picker-ui-text-mismatch")


def start(phone):
    phone.require_owned_installer()
    phone.shell("input", "keyevent", "KEYCODE_WAKEUP", label="picker-display-wake")
    phone.shell("wm", "dismiss-keyguard", label="picker-keyguard-dismiss")
    phone.shell("am", "start", "-W", "-n", LAB.ACTIVITY, "--ez", "graphics_fixture", "true", label="picker-launch")
    time.sleep(1)
    phone.dismiss_notification_permission()  # Existing owner declines by default, never grants.


def put(phone, name, data):
    if name not in ("package.zip", "sha256"):
        raise LAB.Failure("picker-fixture-name-refused")
    phone.require_owned_installer()
    path = "files/graphics-fixture/" + name
    script = "for p in files files/graphics-fixture " + path + '; do [ ! -L "$p" ] || exit 1; done; mkdir -p files/graphics-fixture && cat > ' + path
    phone.command("shell", "run-as", LAB.PACKAGE, "sh", "-c", "'" + script + "'", stdin=data, label="picker-fixture-write")


def acceptance(phone, config, passed, timeout):
    LAB.set_phase("picker-pre-install")
    if phone.occupied(LAB.PACKAGE) or phone.occupied(LAB.GAME):
        raise LAB.Failure("occupied-package-no-fresh-run-ownership")
    apk = config["installer_apk"]
    aapt = config["android_sdk"] / "build-tools/34.0.0/aapt"
    manifest = LAB.run([aapt, "dump", "badging", apk], label="inspect-cached-installer-manifest").decode()
    LAB.require_installer_manifest(manifest, config["installer_version"])
    if LAB.sha(apk.read_bytes()) != config["installer_sha256"]:
        raise LAB.Failure("picker-apk-hash-changed")
    phone.storage()
    phone.install(apk)
    phone.storage()
    if phone.package_hash(LAB.PACKAGE) != config["installer_sha256"]:
        raise LAB.Failure("picker-installed-apk-hash-changed")
    payload = fixture_bytes()
    put(phone, "package.zip", payload)
    put(phone, "sha256", hashlib.sha256(payload).hexdigest().encode())
    start(phone)
    LAB.set_phase("picker-ui")
    picker = Picker(phone, timeout)
    picker.tap("Graphics drivers")
    picker.text("graphics-selection", "Selected for next launch: System")
    passed("system-default")
    # Text is a dedicated content description, so no raw UI leaves the lab.
    picker.text("graphics-active", "Active driver details unavailable")
    passed("active-driver-unavailable")
    picker.text("graphics-choices", "Adreno / Mesa Turnip", "not connected to Unity", "No curated Turnip drivers")
    passed("adreno-unavailable")
    picker.tap("View driver source and licenses")
    source, _ = picker.find(description="graphics-license")
    if any(part not in source.get("text", "") for part in ("BSD-2-Clause", "8fae8ce254dfc1344527e05301e43f37dea2df80", "No proprietary Qualcomm")):
        raise LAB.Failure("picker-license-source-missing")
    picker.tap("Back to graphics drivers")
    passed("source-license-visible")
    picker.tap("Verify synthetic driver file")
    picker.text("graphics-result", "Synthetic package verified; custom activation unavailable.")
    passed("synthetic-package-verified")
    put(phone, "sha256", b"0" * 64)
    picker.tap("Verify synthetic driver file")
    picker.text("graphics-result", "Synthetic package rejected.")
    passed("invalid-hash-refused")
    picker.tap("Show Mali fixture")
    picker.text("graphics-choices", "requires an Adreno GPU", "Mali / Mesa PanVK", "no Android PanVK provider")
    passed("mali-unavailable")
    picker.tap("Use System driver")
    picker.text("graphics-result", "System selected for next launch. No live driver was changed.")
    phone.require_owned_installer()
    state = phone.shell("run-as", LAB.PACKAGE, "cat", "files/graphics-driver/launch-state", label="picker-selection-read")
    if state != b"system\nsystem\n":
        raise LAB.Failure("picker-system-receipt-mismatch")
    phone.shell("am", "force-stop", LAB.PACKAGE, label="picker-cold-stop")
    start(phone)
    picker.tap("Graphics drivers")
    picker.text("graphics-selection", "Selected for next launch: System")
    passed("system-reset-cold-start")
    picker.tap("Close graphics drivers")
    picker.tap("Graphics drivers")
    picker.text("graphics-selection", "Selected for next launch: System")
    picker.tap("Close graphics drivers")
    passed("close-reopen")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    phone, failure, cleanup = None, None, False
    completed = set()

    def passed(case):
        if case not in CASES or case in completed:
            raise LAB.Failure("picker-case-contract")
        completed.add(case)
        print("PASS " + case, flush=True)

    try:
        if not os.environ.get("LAB_DEVICE_SERIAL") or not 30 <= args.timeout <= 1800:
            raise LAB.Failure("picker-requires-authorized-device-and-bounded-timeout")
        LAB.DIAGNOSTICS = LAB.PrivateDiagnostics(ROOT / "work/coordination/graphics-picker-smoke")
        config = LAB.read_context()
        phone = LAB.Phone(os.environ["LAB_DEVICE_SERIAL"], args.timeout)
        acceptance(phone, config, passed, args.timeout)
    except LAB.Failure as error:
        failure = str(error)
    except Exception:
        failure = "unexpected-picker-error-see-private-evidence"
    finally:
        if phone is not None:
            LAB.set_phase("picker-cleanup")
            try:
                cleanup = phone.cleanup() == "verified-absent"
            except Exception:
                failure = failure or "picker-cleanup-unverified"
        LAB.DIAGNOSTICS = None
    success = not failure and cleanup and completed == set(CASES)
    print(
        json.dumps(
            {
                "mode": "graphics-picker-smoke",
                "success": success,
                "synthetic_only": True,
                "cases": sorted(completed),
                "cleanup_verified": cleanup,
                "reason": failure,
            }
        ),
        flush=True,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
