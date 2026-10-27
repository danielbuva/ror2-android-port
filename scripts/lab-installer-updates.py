#!/usr/bin/env python3
"""Run synthetic update acceptance through the real Android installer UI.

Run only through /lab with device=nova-b. No game, existing alpha installation,
production key, arbitrary private directory, or remote release is used. The
runner toolhost job builds the exact-ref public tool APK; this script validates
that receipt and uses a fresh independent test publisher key.
All generated binaries/keys stay on the lab host/device, never in GitHub output.
"""

import argparse
from contextlib import contextmanager
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dev.ror2lab.installertest"
GAME = "dev.ror2lab.alpha"
ACTIVITY = PACKAGE + "/dev.ror2lab.phonebuildhostfixture.ToolHostActivity"
CASES = ("check-for-updates", "update-N-to-N+1", "same-key-rollback", "tampered-manifest-refused", "wrong-key-release-refused")
PRODUCER = "tools/phone-build/accepted-output/record_produce.py"
JOB = "recipe/synthetic-installer-update-job.json"
INPUTS = "recipe/synthetic-installer-update-inputs.json"
KEY_ID = "dots-synthetic-extra-test"
DIAGNOSTICS = None
CURRENT_PHASE = "setup"


class Failure(Exception):
    """Only fixed, authored reason codes may leave the lab host."""


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def sha(value):
    return hashlib.sha256(value).hexdigest()


class PrivateDiagnostics:
    """Persist raw child output locally, never command arguments or stdin."""

    def __init__(self, parent):
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
        self.sequence = 0

    def write(self, name, data):
        descriptor = os.open(self.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)

    def record(self, category, *, stdout=b"", stderr=b"", returncode=None, outcome="returned"):
        self.sequence += 1
        prefix = f"{self.sequence:05d}-{category}"
        self.write(prefix + ".stdout.log", stdout or b"")
        self.write(prefix + ".stderr.log", stderr or b"")
        self.write(prefix + ".json", encoded({"phase": CURRENT_PHASE, "category": category, "returncode": returncode, "outcome": outcome}))


def set_phase(phase):
    global CURRENT_PHASE
    CURRENT_PHASE = phase


def execute(argv, *, label, stdin=None, timeout=300):
    try:
        result = subprocess.run(list(map(str, argv)), input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        if DIAGNOSTICS is not None:
            DIAGNOSTICS.record(label, stdout=getattr(error, "stdout", b""), stderr=getattr(error, "stderr", b""), outcome=type(error).__name__)
        raise Failure(label) from error
    if DIAGNOSTICS is not None:
        DIAGNOSTICS.record(label, stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
    return result


def run(argv, *, label, stdin=None, timeout=300):
    result = execute(argv, label=label, stdin=stdin, timeout=timeout)
    if result.returncode:
        raise Failure(label)
    return result.stdout


def read_context():
    root = os.environ.get("LAB_TOOLHOST_ROOT")
    if not root:
        raise Failure("LAB_TOOLHOST_ROOT-required-run-lab-toolhost-first")
    commit = run(["git", "-C", ROOT, "rev-parse", "HEAD"], label="resolve-source-commit").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise Failure("source-commit-unavailable")
    cached = Path(root).resolve(strict=True) / commit
    apk, receipt_path = cached / "signed.apk", cached / "result.json"
    if not apk.is_file() or not receipt_path.is_file():
        raise Failure("toolhost-cache-missing-run-lab-toolhost-for-this-ref")
    receipt = json.loads(receipt_path.read_text())
    if (
        receipt.get("success") is not True
        or receipt.get("package") != PACKAGE
        or receipt.get("source_commit") != commit
        or receipt.get("apk_sha256") != sha(apk.read_bytes())
    ):
        raise Failure("toolhost-cache-receipt-mismatch")
    # The builder's publisher key is deliberately not opened or copied. A new
    # independent key exercises the explicit debug-only additive trust seam.
    # Only the public repository's deterministic environment selector runs;
    # no private directories/configuration are searched for tool paths.
    values = run(
        ["/bin/bash", "-c", 'set -eu; . "$1"; printf "%s\\0" "$ANDROID_HOME" "$JAVA_HOME" "$ANDROID_NDK_ROOT"', "lab-env", ROOT / "scripts/env.sh"],
        label="load-public-toolchain-environment",
    ).split(b"\0")
    if len(values) != 4 or values[-1]:
        raise Failure("public-toolchain-environment-invalid")
    return {
        "installer_apk": apk,
        "installer_version": receipt.get("version_code"),
        **{key: Path(value.decode()).resolve(strict=True) for key, value in zip(("android_sdk", "java_home", "ndk"), values[:3])},
    }


class HostTools:
    def __init__(self, config):
        self.java = config["java_home"] / "bin/java"
        self.javac = config["java_home"] / "bin/javac"
        self.build = config["android_sdk"] / "build-tools/34.0.0"
        self.android = config["android_sdk"] / "platforms/android-33/android.jar"
        candidates = list((config["ndk"] / "toolchains/llvm/prebuilt").glob("*/bin/aarch64-linux-android24-clang"))
        if len(candidates) != 1:
            raise Failure("configured-ndk-compiler-unavailable")
        self.clang = candidates[0]
        for path in (self.java, self.javac, self.android, self.build / "aapt", self.build / "lib/d8.jar", self.clang):
            if not path.is_file():
                raise Failure("configured-host-tool-unavailable")

    def dex(self, sources, output):
        output.mkdir()
        classes = output / "classes"
        classes.mkdir()
        run([self.javac, "-source", "8", "-target", "8", "-bootclasspath", self.android, "-d", classes, *sources], label="compile-authored-java")
        jar = output / "classes.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            for path in classes.rglob("*.class"):
                archive.write(path, path.relative_to(classes).as_posix())
        run(
            [self.java, "-cp", self.build / "lib/d8.jar", "com.android.tools.r8.D8", "--min-api", "24", "--lib", self.android, "--output", output, jar],
            label="compile-authored-dex",
        )
        return (output / "classes.dex").read_bytes()

    def resource_apk(self, manifest, output, resources=None):
        argv = [self.build / "aapt", "package", "-f", "-M", manifest, "-I", self.android, "-F", output]
        if resources:
            argv += ["-S", resources]
        run(argv, label="compile-authored-resources")


def synthetic_manifest(temporary):
    """AAPT1 indexes -M by basename and requires AndroidManifest.xml."""
    manifest = temporary / "AndroidManifest.xml"
    manifest.write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.ror2lab.alpha" android:versionCode="1"><uses-sdk android:minSdkVersion="24" android:targetSdkVersion="30"/><application android:label="@string/app_name" android:debuggable="true" android:extractNativeLibs="true"><activity android:name="com.unity3d.player.UnityPlayerActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>'
    )
    return manifest


def synthetic_inputs(tools, temporary):
    """Compile tiny ORIGINAL fixtures, not Unity/game/SDK runtime implementations.

    The alpha is never launched. Only the real authored retention provider runs.
    These objects exercise packaging/update mechanics, not game readiness.
    """
    sdk = module("synthetic_sdk_names", ROOT / "tools/phone-build/accepted-output/sdk_package.py")
    owner = module("synthetic_owner_names", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")
    result = {"apk/" + name: b"synthetic fixture\n" for name in sdk.SDK_ENTRIES | owner.CODE_ENTRIES}
    source = temporary / "stub.c"
    source.write_text("int synthetic_update_marker(void) { return 1; }\n")
    library = temporary / "synthetic.so"
    run([tools.clang, "-shared", "-fPIC", "-nostdlib", source, "-o", library], label="compile-authored-native")
    for name in result:
        if name.endswith(".so"):
            result[name] = library.read_bytes()
    for number in range(1, 5):
        name = "UnityPlayerActivity" if number == 1 else "SyntheticMarker" + str(number)
        java = temporary / (name + ".java")
        java.write_text("package com.unity3d.player; public class " + name + (" extends android.app.Activity" if number == 1 else "") + " {}\n")
        result["apk/classes" + (str(number) if number > 1 else "") + ".dex"] = tools.dex([java], temporary / ("synthetic-dex-" + str(number)))
    resources = temporary / "res"
    (resources / "values").mkdir(parents=True)
    (resources / "values/strings.xml").write_text('<resources><string name="app_name">Synthetic update fixture</string></resources>')
    manifest = synthetic_manifest(temporary)
    packaged = temporary / "synthetic-resources.apk"
    tools.resource_apk(manifest, packaged, resources)
    with zipfile.ZipFile(packaged) as archive:
        for name in ("AndroidManifest.xml", "resources.arsc"):
            result["apk/" + name] = archive.read(name)
    # Unreferenced icon entries need no game image or external bitmap.
    for name in result:
        if name.startswith("apk/res/"):
            result[name] = b"synthetic unreferenced resource\n"
    result["payload/synthetic-update.txt"] = b"synthetic payload N\n"
    return result


def release_fixture(public, inputs, version, directory, private_key, public_key):
    contents = {name: (ROOT / name).read_bytes() for name in public.PUBLISHING_SOURCE_FILES}
    required = {
        "schema": 1,
        "game_version": "synthetic-installer-only",
        "files": [{"path": name, "bytes": len(data), "sha256": sha(data)} for name, data in sorted(inputs.items())],
    }
    contents[INPUTS] = encoded(required)
    # The fixture producer replaces only the signed TEST bundle's producer source,
    # never repository or production assets. It uses admitted synthetic inputs.
    contents[PRODUCER] = (
        "from pathlib import Path\nimport shutil,sys\nsource,out=map(Path,sys.argv[1:3]);out.mkdir()\nfor path in source.rglob('*'):\n if path.is_file():\n  target=out/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)\n(out/'payload/synthetic-update.txt').write_text("
        + repr("synthetic payload N" + ("+1" if version == 2 else "") + "\n")
        + ")\n"
    ).encode()
    contents[JOB] = encoded({"schema": 1, "script": PRODUCER, "arguments": ["${input:synthetic}", "${output}"], "outputs": {name: name for name in inputs}})
    plan = {
        "schema": 1,
        "required_inputs": INPUTS,
        "workspace_bytes": 64 * 1024**2,
        "configuration": {"bindings": {"synthetic": "."}},
        "stages": [
            {"id": stage, "title": "Synthetic " + stage, "jobs": [JOB] if stage == "assembly" else []}
            for stage in ("admission", "staging", "assembly", "textures", "native", "apk", "signing", "install")
        ],
    }
    index = {
        "schema": 1,
        "files": {name: sha(data) for name, data in contents.items()},
        "entries": {name: {"recipe_files": [JOB, INPUTS], "producer_files": [PRODUCER], "job": JOB} for name in inputs},
        "install_plan": plan,
    }
    directory.mkdir()
    bundle = directory / "public-tools.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            public.public_source_path(name, sha(data))
            archive.writestr(name, data)
        archive.writestr("bundle-index.json", encoded(index))
    body = {
        "version": "synthetic-N" + ("+1" if version == 2 else ""),
        "version_code": version,
        "application_id": GAME,
        "minimum_installer_version": 3,
        "bundle_sha256": sha(bundle.read_bytes()),
        "data_schema": {"writes": 1, "reads": [1]},
        "entries": {name: public.entry_dependencies(index, name) for name in inputs},
    }
    public.validate_publication(bundle, body)
    envelope = public.sign_envelope(body, KEY_ID, private_key, public_key)
    return {"release.json": encoded(envelope["release"]), "release.sig": encoded(envelope["signature"]), "public-tools.zip": bundle.read_bytes()}


@contextmanager
def server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            with self.server.lock:
                self.server.requests.append(self.path)
                data = self.server.paths.get(self.path)
            self.send_response(200 if data is not None else 404)
            self.send_header("Content-Length", str(len(data) if data is not None else 0))
            self.end_headers()
            if data is not None:
                self.wfile.write(data)

        def log_message(self, *args):
            pass

    service = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    service.paths, service.requests, service.lock = {}, [], threading.Lock()
    service.handle_error = lambda request, address: None  # no client addresses/raw tracebacks in public output
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        yield service
    finally:
        service.shutdown()
        service.server_close()
        thread.join()


def publish(service, files, version):
    base = "http://127.0.0.1:" + str(service.server_port) + "/"
    metadata = {
        "draft": False,
        "prerelease": False,
        "tag_name": "owner-v" + str(version),
        "assets": [{"name": name, "size": len(data), "browser_download_url": base + name} for name, data in files.items()],
    }
    with service.lock:
        service.paths = {"/" + name: data for name, data in files.items()}
        service.paths["/latest.json"] = encoded(metadata)
        service.requests.clear()
    return base


class Phone:
    def __init__(self, serial, timeout, allow_test_installs=False):
        self.serial, self.timeout = serial, timeout
        self.allow_test_installs = allow_test_installs
        self.adb = Path("/opt/homebrew/bin/adb")
        self.owned_installer = False
        self.install_attempted = False
        self.installer_hash = None
        self.alpha_hash = None
        self.reverse_port = None
        self.install_volume = None
        self.ui_path = "/data/local/tmp/ror2-installer-ui-" + secrets.token_hex(8) + ".xml"

    def command(self, *args, stdin=None, label, timeout=60):
        return run([self.adb, "-s", self.serial, *args], label=label, stdin=stdin, timeout=timeout)

    def shell(self, *args, **kwargs):
        return self.command("shell", *args, **kwargs)

    def package_paths(self, package):
        # Android pm path reports an absent package with either exit 0 or 1.
        # This exception belongs only to this read-only query, not generic ADB.
        result = execute([self.adb, "-s", self.serial, "shell", "pm", "path", package], label="device-package-path-query", timeout=60)
        if result.returncode in (0, 1) and result.stdout == b"" and result.stderr == b"":
            return []
        if result.returncode or result.stderr:
            raise Failure("device-package-path-query")
        paths = result.stdout.decode().strip().splitlines()
        if not paths or any(not path.startswith("package:/") for path in paths):
            raise Failure("device-package-path-shape")
        return paths

    def occupied(self, package):
        return bool(self.package_paths(package))

    def package_hash(self, package):
        paths = self.package_paths(package)
        if len(paths) != 1 or not paths[0].startswith("package:"):
            raise Failure("installed-package-shape")
        # Hash only; APK bytes never leave the lab device for readback.
        value = self.shell("sha256sum", paths[0][8:], label="device-package-hash").decode().split()[0]
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise Failure("installed-package-hash")
        return value

    @staticmethod
    def available(data):
        rows = data.decode().splitlines()
        if len(rows) < 2:
            raise Failure("device-storage-backing-unavailable")
        fields = rows[-1].split()
        if len(fields) < 6 or not fields[-3].isdigit():
            raise Failure("device-storage-backing-unavailable")
        return int(fields[-3]) * 1024

    def storage(self):
        # Discover today's mounted adopted volumes; do not remember, print,
        # reconfigure, or move anything between their private identifiers.
        volumes = self.shell("sm", "list-volumes", "private", label="device-storage-volumes").decode().splitlines()
        choices = [("internal", "/data")]
        for row in volumes:
            fields = row.split()
            if len(fields) == 3 and fields[1] == "mounted" and fields[2] != "null":
                if not re.fullmatch(r"[A-Za-z0-9-]+", fields[2]):
                    raise Failure("device-storage-volume-shape")
                choices.append((fields[2], "/mnt/expand/" + fields[2]))
        observed = [(self.available(self.shell("df", "-k", path, label="device-storage-volume-free")), volume) for volume, path in choices]
        if not self.owned_installer:
            available, self.install_volume = max(observed)
            if available < 15 * 1024**3:
                raise Failure("device-storage-reserve")
            return
        # Verify both installed code placement and actual app-private backing,
        # not /sdcard aliases. All outputs stay inside this lab process.
        for package in (PACKAGE, GAME) if self.alpha_hash else (PACKAGE,):
            paths = self.package_paths(package)
            if len(paths) != 1 or not paths[0].startswith("package:"):
                raise Failure("device-package-placement-unavailable")
            code = self.available(self.shell("df", "-k", paths[0][8:], label="device-storage-code-free"))
            data = self.available(self.shell("run-as", package, "df", "-k", ".", label="device-storage-data-free"))
            if min(code, data) < 15 * 1024**3:
                raise Failure("device-storage-reserve")

    def put(self, name, data):
        if not self.owned_installer:
            raise Failure("test-installer-not-owned")
        path = "files/owner-input/" + name
        if not re.fullmatch(r"[A-Za-z0-9_./+-]+", path) or ".." in path.split("/"):
            raise Failure("test-input-path")
        self.shell("run-as", PACKAGE, "mkdir", "-p", str(Path(path).parent), label="device-input-directory")
        self.command("shell", "run-as", PACKAGE, "sh", "-c", "'cat > " + path + "'", stdin=data, label="device-input-write")

    def read(self, name):
        path = "files/owner-input/" + name
        result = self.command(
            "shell", "run-as", PACKAGE, "sh", "-c", "'if [ -f " + path + " ]; then cat " + path + "; else printf null; fi'", label="device-state-read"
        )
        return json.loads(result)

    def ui(self):
        # A newly launched Activity can report a null accessibility root while
        # uiautomator still exits 0 and creates no file. Retry only that observed
        # result, never cat a missing dump or retry unrelated command failures.
        for attempt in range(3):
            result = execute([self.adb, "-s", self.serial, "shell", "uiautomator", "dump", self.ui_path], label="device-ui-dump", timeout=30)
            if result.returncode:
                raise Failure("device-ui-dump")
            if "null-root" not in (ui_output_classification(result.stdout), ui_output_classification(result.stderr)):
                break
            if attempt == 2:
                raise Failure("device-ui-null-root-retry-exhausted")
            time.sleep(1)
        try:
            value = self.shell("cat", self.ui_path, label="device-ui-read")
        finally:
            self.shell("rm", "-f", self.ui_path, label="device-ui-remove")
        start, end = value.find(b"<?xml"), value.rfind(b"</hierarchy>")
        if start < 0 or end < 0:
            raise Failure("ui-hierarchy-unavailable")
        return ET.fromstring(value[start : end + len(b"</hierarchy>")])

    def tap_visible(self, label):
        tree = self.ui()
        for node in tree.iter("node"):
            if node.get("text", "").casefold() == label.casefold() and node.get("enabled") == "true":
                bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
                if not bounds:
                    raise Failure("ui-button-bounds")
                x1, y1, x2, y2 = map(int, bounds.groups())
                self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2), label="device-ui-tap")
                return True
        return False

    def tap(self, label, *, required=True):
        if self.tap_visible(label):
            return True
        if not required:
            return False
        # This Activity is a real ScrollView: lengthy live status can push the
        # buttons off-screen. Search visible accessibility text, never pixels.
        tree = self.ui()
        scroll = next((node for node in tree.iter("node") if node.get("scrollable") == "true"), None)
        if scroll is None:
            raise Failure("ui-button-unavailable")
        coordinates = list(map(int, re.findall(r"\d+", scroll.get("bounds", ""))))
        if len(coordinates) != 4:
            raise Failure("ui-scroll-bounds")
        x1, y1, x2, y2 = coordinates
        x, top, bottom = (x1 + x2) // 2, y1 + (y2 - y1) // 5, y2 - (y2 - y1) // 5
        for direction in ((top, bottom), (bottom, top)):
            previous = None
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                current = tuple((node.get("text"), node.get("bounds")) for node in self.ui().iter("node") if node.get("class") == "android.widget.Button")
                if current and current == previous:
                    break
                previous = current
                self.shell("input", "swipe", str(x), str(direction[0]), str(x), str(direction[1]), "250", label="device-ui-scroll")
                if self.tap_visible(label):
                    return True
        raise Failure("ui-button-unavailable")

    def start(self):
        self.shell("input", "keyevent", "KEYCODE_WAKEUP", label="device-display-wake")
        self.shell("wm", "dismiss-keyguard", label="device-keyguard-dismiss")
        self.shell("am", "start", "-W", "-n", ACTIVITY, label="device-installer-launch")
        time.sleep(1)
        self.dismiss_notification_permission()

    def dismiss_notification_permission(self):
        # ToolHostActivity.onCreate requests only POST_NOTIFICATIONS. This is
        # not the separately authorized unknown-source install permission.
        # Decline only this owned test app's notification prompt, never grant
        # an unidentified permission or rely on localized button text.
        if not self.owned_installer:
            raise Failure("notification-dialog-installer-not-owned")
        controller = "com.android.permissioncontroller"
        nodes = [node for node in self.ui().iter("node") if node.get("package") == controller]
        if not nodes:
            return False
        messages = [node.get("text", "").casefold() for node in nodes if node.get("resource-id") == controller + ":id/permission_message"]
        if len(messages) != 1 or "owner game installer" not in messages[0] or not re.search(r"\bnotifications\b", messages[0]):
            raise Failure("notification-dialog-not-identified")
        buttons = [node for node in nodes if node.get("resource-id") == controller + ":id/permission_deny_button" and node.get("enabled") == "true"]
        if len(buttons) != 1:
            raise Failure("notification-denial-unavailable")
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", buttons[0].get("bounds", ""))
        if not bounds:
            raise Failure("ui-button-bounds")
        x1, y1, x2, y2 = map(int, bounds.groups())
        self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2), label="device-notification-deny")
        if any(node.get("package") == controller for node in self.ui().iter("node")):
            raise Failure("notification-dialog-not-dismissed")
        return True

    def wait_state(self, expected):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            row = self.read("update-state.json")
            if row and row.get("state") in expected:
                return row
            if row and row.get("state") == "ERROR":
                raise Failure("installer-update-error")
            time.sleep(1)
        raise Failure("installer-update-timeout")

    def check(self, version):
        self.put("update-state.json", encoded({"state": "TEST_WAIT"}))
        self.tap("Check for updates")
        row = self.wait_state({"UPDATE_AVAILABLE"})
        if row.get("release", {}).get("version_code") != version:
            raise Failure("release-version-not-observed")

    def installed(self, publisher, previous=None):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            receipt = self.read("installed-release.json")
            if receipt and receipt.get("release", {}).get("version_code") == publisher and receipt.get("installed_readback_verified") is True:
                if self.package_hash(GAME) != receipt.get("sha256"):
                    raise Failure("installed-receipt-readback-mismatch")
                if previous is not None:
                    if receipt["signer_sha256"] != previous["signer_sha256"] or receipt["version_code"] <= previous["version_code"]:
                        raise Failure("same-key-forward-version-mismatch")
                    old = self.read("previous-installed-release.json")
                    if old["sha256"] != previous["sha256"]:
                        raise Failure("previous-release-not-retained")
                self.alpha_hash = receipt["sha256"]
                self.storage()
                self.start()
                return receipt
            row = self.read("update-state.json")
            if row and row.get("state") == "ERROR":
                raise Failure("installer-build-error")
            # Consent is always the real Android PackageInstaller UI. Never forge
            # success receipts or use adb install to replace the alpha package.
            self.tap("Install", required=False)
            time.sleep(1)
        raise Failure("install-readback-timeout")

    def await_install_permission(self):
        value = self.shell("appops", "get", PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query").decode()
        if re.search(r"REQUEST_INSTALL_PACKAGES: allow\b", value):
            return
        if not self.allow_test_installs or not self.owned_installer:
            raise Failure("install-permission-owner-authorization-required")
        # The root lab invocation may pass this flag ONLY after explicit owner
        # authorization for this fresh disposable test package on the leased phone.
        self.shell("appops", "set", PACKAGE, "REQUEST_INSTALL_PACKAGES", "allow", label="device-install-permission-enable")

    def cleanup(self):
        # Only delete exact packages installed by this fresh run. Unknown or
        # changed packages, including a failed in-flight alpha, are retained.
        packages_absent = False
        try:
            if self.reverse_port is not None:
                self.command("reverse", "--remove", "tcp:" + str(self.reverse_port), label="device-reverse-remove")
            if self.owned_installer:
                self.shell("am", "force-stop", PACKAGE, label="device-installer-stop")
                if self.occupied(GAME):
                    ready = self.read("owner-apk-ready.json")
                    owned = self.read("installed-release.json")
                    actual = self.package_hash(GAME)
                    # The test refused an existing alpha before installation.
                    # A signed ready receipt also covers interrupted readback.
                    matches = [row for row in (ready, owned) if row and row.get("application_id") == GAME and row.get("sha256") == actual]
                    if not matches:
                        raise Failure("cleanup-alpha-ownership-not-established")
                    self.command("uninstall", GAME, label="cleanup-alpha-uninstall")
                    if self.occupied(GAME):
                        raise Failure("cleanup-alpha-still-installed")
                if self.package_hash(PACKAGE) != self.installer_hash:
                    raise Failure("cleanup-installer-ownership-changed")
                self.command("uninstall", PACKAGE, label="cleanup-installer-uninstall")
                if self.occupied(PACKAGE):
                    raise Failure("cleanup-installer-still-installed")
                packages_absent = True
            elif self.install_attempted:
                # Installation may have completed before an ADB/readback error.
                # Unknown ownership permits observation, never deletion.
                if self.occupied(PACKAGE) or self.occupied(GAME):
                    raise Failure("cleanup-package-ownership-unverified")
                packages_absent = True
        finally:
            self.shell("input", "keyevent", "KEYCODE_SLEEP", label="device-display-sleep")
        return "verified-absent" if packages_absent else "not-checked"


def publisher_keys(temporary, name):
    private = temporary / (name + "-private.pem")
    public = temporary / (name + "-public.pem")
    run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", private], label="create-throwaway-publisher-key")
    private.chmod(0o600)
    run(["openssl", "pkey", "-in", private, "-pubout", "-out", public], label="derive-throwaway-publisher-public-key")
    return private, public.read_bytes()


def prepare_artifacts(config, temporary):
    tools = HostTools(config)
    apk = config["installer_apk"]
    with zipfile.ZipFile(apk) as archive:
        trust = json.loads(archive.read("assets/release-trust.json"))
    if KEY_ID in trust["keys"]:
        raise Failure("synthetic-extra-key-id-collides-with-packaged-trust")
    manifest = run([tools.build / "aapt", "dump", "badging", apk], label="inspect-cached-installer-manifest").decode()
    identity = re.search(r"^package: name='([^']+)' versionCode='(\d+)'", manifest, re.MULTILINE)
    if (
        not identity
        or identity.group(1) != PACKAGE
        or int(identity.group(2)) != config["installer_version"]
        or int(identity.group(2)) < 3
        or "application-debuggable" not in manifest
    ):
        raise Failure("cached-installer-manifest-not-debug-test-package")
    inputs = synthetic_inputs(tools, temporary)
    public = module("synthetic_release_public", ROOT / "tools/phone-build/owner-apk/public_release.py")
    private, key = publisher_keys(temporary, "trusted")
    wrong_private, wrong_key = publisher_keys(temporary, "wrong")
    releases = {version: release_fixture(public, inputs, version, temporary / ("release-" + str(version)), private, key) for version in (1, 2)}
    wrong = release_fixture(public, inputs, 2, temporary / "wrong-release", wrong_private, wrong_key)
    return apk, inputs, key, releases, wrong


def acceptance(phone, config, temporary, passed):
    set_phase("pre-install-checks")
    if phone.occupied(GAME) or phone.occupied(PACKAGE):
        raise Failure("occupied-package-no-fresh-run-ownership")
    phone.storage()
    set_phase("host-fixture-build")
    apk, inputs, key, releases, wrong = prepare_artifacts(config, temporary)
    set_phase("pre-install-storage")
    phone.storage()
    set_phase("installer-install")
    phone.install_attempted = True
    phone.command("install", "--force-uuid", phone.install_volume, str(apk), timeout=600, label="install-fresh-test-installer")
    phone.installer_hash = sha(apk.read_bytes())
    if phone.package_hash(PACKAGE) != phone.installer_hash:
        raise Failure("test-installer-readback")
    phone.owned_installer = True
    set_phase("installer-storage")
    phone.storage()
    set_phase("installer-permission")
    phone.await_install_permission()
    set_phase("fixture-provision")
    with server() as service:
        base = publish(service, releases[1], 1)
        phone.command("reverse", "--no-rebind", "tcp:" + str(service.server_port), "tcp:" + str(service.server_port), label="device-reverse-create")
        phone.reverse_port = service.server_port
        phone.put("debug-release-source.json", encoded({"enabled": True, "base_url": base, "key_id": KEY_ID, "public_key": key.decode()}))
        for name, data in inputs.items():
            phone.put("import/files/" + name, data)
        # Input bytes are generated above, not copied from any owner directory.
        # The production Python admission rehashes the signed manifest itself.
        phone.put("import-state.json", encoded({"state": "IMPORTED", "message": "Synthetic test inputs only"}))
        set_phase("baseline-N-check")
        phone.start()
        phone.check(1)
        if not any("TEST RELEASE SOURCE" in node.get("text", "") for node in phone.ui().iter("node")):
            raise Failure("debug-source-warning-not-visible")
        set_phase("baseline-N-install")
        phone.storage()
        phone.tap("Reconstruct and install verified game")
        first = phone.installed(1)
        set_phase("check-for-updates")
        publish(service, releases[2], 2)
        phone.check(2)
        if "/public-tools.zip" in service.requests:
            raise Failure("check-downloaded-bundle-before-consent")
        passed("check-for-updates")
        set_phase("update-N-to-N+1")
        phone.storage()
        phone.tap("Reconstruct and install verified game")
        second = phone.installed(2, first)
        passed("update-N-to-N+1")
        set_phase("same-key-rollback")
        phone.storage()
        phone.tap("Rebuild and install previous release (same key)")
        rolled = phone.installed(1, second)
        passed("same-key-rollback")
        tampered = dict(releases[2])
        body = json.loads(tampered["release.json"])
        body["version"] = "synthetic-tampered"
        tampered["release.json"] = encoded(body)
        for case, files in (("tampered-manifest-refused", tampered), ("wrong-key-release-refused", wrong)):
            set_phase(case)
            publish(service, files, 2)
            before = phone.read("installed-release.json")
            phone.put("update-state.json", encoded({"state": "TEST_WAIT"}))
            phone.tap("Check for updates")
            state = phone.wait_state({"ERROR"})
            if "signature" not in state.get("message", "").lower():
                raise Failure("refusal-was-not-signature-validation")
            if "/public-tools.zip" in service.requests or phone.read("installed-release.json") != before or phone.package_hash(GAME) != rolled["sha256"]:
                raise Failure("refused-release-mutated-installed-state")
            passed(case)


def ui_output_classification(data):
    """Only authored classifications, never excerpts of private child output."""
    value = data.lower()
    for marker, label in (
        (b"could not get idle state", "idle-timeout"),
        (b"null root node", "null-root"),
        (b"error while dumping window hierarchy", "hierarchy-write-error"),
        (b"no such file or directory", "missing-file"),
        (b"permission denied", "permission-denied"),
        (b"ui hierchary dumped to", "dump-reported-written"),
        (b"ui hierarchy dumped to", "dump-reported-written"),
    ):
        if marker in value:
            return label
    if b"<?xml" in value and b"</hierarchy>" in value:
        return "hierarchy-present"
    return "other-output" if value.strip() else "empty"


def inspect_ui_failure(selection, *, conflicting_mode=False):
    result = {"mode": "inspect-ui-failure", "status": "observed", "selection": "newest" if selection == "newest" else "explicit", "records": [], "errors": []}
    try:
        if conflicting_mode:
            raise Failure("log-inspection-cannot-run-other-modes")
        if selection != "newest" and (not selection or not re.fullmatch(r"run-[a-z0-9_]{8}", selection)):
            raise Failure("log-inspection-requires-constrained-run-selection")
        parent = ROOT / "work/coordination/installer-update-acceptance"
        if selection == "newest":
            # Only this driver's immediate per-run directories; no recursive
            # search, other lab namespaces, artifacts, or arbitrary paths.
            candidates = [path for path in parent.iterdir() if re.fullmatch(r"run-[a-z0-9_]{8}", path.name) and not path.is_symlink() and path.is_dir()]
            if not candidates:
                raise Failure("log-inspection-run-not-found")
            directory = max(candidates, key=lambda path: path.stat().st_mtime_ns)
        else:
            directory = parent / selection
        if directory.is_symlink() or not directory.is_dir():
            raise Failure("log-inspection-run-not-found")

        def read(name):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise Failure("log-inspection-record-unavailable")
            return path.read_bytes()

        failure_sequence = None
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-ui-read.json")):
            metadata = json.loads(read(path.name))
            if metadata.get("phase") == "baseline-N-check" and metadata.get("category") == "device-ui-read":
                if metadata.get("returncode") != 0 or metadata.get("outcome") != "returned":
                    failure_sequence = int(path.name[:5])
                    break
        if failure_sequence is None or failure_sequence < 2:
            raise Failure("log-inspection-ui-read-failure-not-found")
        for sequence, category in ((failure_sequence - 1, "device-ui-dump"), (failure_sequence, "device-ui-read")):
            prefix = f"{sequence:05d}-{category}"
            metadata = json.loads(read(prefix + ".json"))
            if metadata.get("phase") != "baseline-N-check" or metadata.get("category") != category:
                raise Failure("log-inspection-record-mismatch")
            outcome = metadata.get("outcome")
            result["records"].append(
                {
                    "phase": "baseline-N-check",
                    "category": category,
                    "returncode": "zero" if metadata.get("returncode") == 0 else "nonzero" if type(metadata.get("returncode")) is int else "unavailable",
                    "outcome": outcome if outcome in ("returned", "OSError", "TimeoutExpired") else "unknown",
                    "stdout": ui_output_classification(read(prefix + ".stdout.log")),
                    "stderr": ui_output_classification(read(prefix + ".stderr.log")),
                }
            )
    except Exception as error:
        result["status"] = "error"
        result["errors"].append(str(error) if isinstance(error, Failure) else "log-inspection-local-read-error")
    print(encoded(result).decode(), end="", flush=True)
    return 1 if result["errors"] else 0


def inspect_state(expected_installer_hash, timeout, *, conflicting_mode=False):
    """Observe only the two fixed packages; never adopt ownership or clean up."""
    result = {
        "mode": "inspect-state",
        "status": "observed",
        "installer": {"presence": "unknown", "hash": "not-read", "install_permission": "unknown"},
        "alpha": {"presence": "unknown", "hash": "not-read"},
        "errors": [],
    }

    def failed(error):
        result["status"] = "error"
        result["errors"].append(str(error) if isinstance(error, Failure) else "unexpected-inspection-error")

    try:
        if conflicting_mode:
            raise Failure("inspection-cannot-build-or-enable-installs")
        if not expected_installer_hash or not re.fullmatch(r"[0-9a-f]{64}", expected_installer_hash):
            raise Failure("inspection-requires-expected-installer-sha256")
        serial = os.environ.get("LAB_DEVICE_SERIAL")
        if not serial:
            raise Failure("LAB_DEVICE_SERIAL-required-use-authorized-lab-runner")
        phone = Phone(serial, timeout)
        for name, package in (("installer", PACKAGE), ("alpha", GAME)):
            row = result[name]
            try:
                present = phone.occupied(package)
                row["presence"] = "present" if present else "absent"
                if present:
                    digest = phone.package_hash(package)
                    row["hash"] = ("match" if digest == expected_installer_hash else "mismatch") if name == "installer" else "read"
                else:
                    row["hash"] = "absent"
            except Exception as error:
                failed(error)
        if result["installer"]["presence"] == "present":
            try:
                value = phone.shell("appops", "get", PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query").decode()
                mode = re.search(r"\bREQUEST_INSTALL_PACKAGES: (allow|ignore|deny|default|foreground)\b", value)
                if mode:
                    result["installer"]["install_permission"] = mode.group(1)
                elif value.strip() == "No operations.":
                    result["installer"]["install_permission"] = "unset"
                else:
                    raise Failure("device-install-permission-shape")
            except Exception as error:
                failed(error)
        elif result["installer"]["presence"] == "absent":
            result["installer"]["install_permission"] = "not-installed"
    except Exception as error:
        failed(error)
    # Hashes, APK paths, identifiers and raw ADB output never leave this process.
    # A successful observation (even a mismatch) is not an acceptance PASS.
    print(encoded(result).decode(), end="", flush=True)
    return 1 if result["errors"] else 0


def main(argv=None):
    global DIAGNOSTICS
    set_phase("setup")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host-only", action="store_true", help="Build/sign synthetic fixtures on the lab host, without any phone operation or phone PASS claim"
    )
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument(
        "--allow-test-installs", action="store_true", help="Only after explicit owner authorization: allow installs for this fresh disposable test package"
    )
    parser.add_argument("--inspect-state", action="store_true", help="Read-only fixed-package presence/hash and installer permission; no build, UI or cleanup")
    parser.add_argument(
        "--expected-installer-sha256", help="Required for --inspect-state: last known installer hash, used only for comparison, never ownership"
    )
    parser.add_argument("--inspect-ui-failure", action="store_true", help="Read-only fixed classification of this driver's retained UI dump/read failure logs")
    parser.add_argument(
        "--diagnostic-run", help="Required for --inspect-ui-failure: newest or one private run-directory basename; never prints paths or raw logs"
    )
    args = parser.parse_args(argv)
    if args.inspect_ui_failure:
        DIAGNOSTICS = None
        return inspect_ui_failure(args.diagnostic_run, conflicting_mode=args.inspect_state or args.host_only or args.allow_test_installs)
    if args.inspect_state:
        # This driver-only observation makes no claim about APK source identity.
        # Bypass cache/toolchain setup, private log writes and all cleanup paths.
        DIAGNOSTICS = None
        return inspect_state(args.expected_installer_sha256, args.timeout, conflicting_mode=args.host_only or args.allow_test_installs)
    completed = set()
    phone = None
    reason = None
    failure_phase = "setup"
    cleanup_reason = None
    cleanup_verified = False

    def passed(case):
        completed.add(case)
        print("PASS " + case, flush=True)

    try:
        serial = os.environ.get("LAB_DEVICE_SERIAL")
        if not serial and not args.host_only:
            raise Failure("LAB_DEVICE_SERIAL-required-use-authorized-lab-runner")
        DIAGNOSTICS = PrivateDiagnostics(ROOT / "work/coordination/installer-update-acceptance")
        config = read_context()
        if not args.host_only:
            phone = Phone(serial, args.timeout, args.allow_test_installs)
        # Explicit /tmp, never TMPDIR (which might point inside a checkout).
        with tempfile.TemporaryDirectory(prefix="ror2-synthetic-updates-", dir="/tmp") as name:
            temporary = Path(name).resolve()
            if temporary.is_relative_to(ROOT.resolve()):
                raise Failure("throwaway-root-must-be-outside-repository")
            if args.host_only:
                set_phase("host-fixture-build")
                prepare_artifacts(config, temporary)
                print("PASS host-fixture-build (phone acceptance NOT RUN)", flush=True)
            else:
                acceptance(phone, config, temporary, passed)
    except Failure as error:
        reason = str(error)
        failure_phase = CURRENT_PHASE
    except Exception:
        reason = "unexpected-local-error-see-private-lab-environment"
        failure_phase = CURRENT_PHASE
    finally:
        if phone is not None:
            set_phase("cleanup")
            try:
                cleanup_verified = phone.cleanup() == "verified-absent"
            except Failure as error:
                cleanup_reason = str(error)
            except Exception:
                cleanup_reason = "unexpected-cleanup-error-see-private-lab-environment"
        DIAGNOSTICS = None
    if reason:
        if args.host_only:
            print("FAIL host-fixture-build phase=" + failure_phase + " reason=" + reason, flush=True)
        else:
            for case in CASES:
                if case not in completed:
                    print("FAIL " + case + " phase=" + failure_phase + " reason=" + reason, flush=True)
    if phone is not None:
        if cleanup_reason:
            print("FAIL cleanup phase=cleanup reason=" + cleanup_reason, flush=True)
        else:
            if cleanup_verified:
                print("PASS cleanup packages=verified-absent", flush=True)
            else:
                print("SKIP cleanup packages=not-checked reason=no-owned-package-mutation", flush=True)
    return 1 if reason or cleanup_reason else 0


if __name__ == "__main__":
    sys.exit(main())
