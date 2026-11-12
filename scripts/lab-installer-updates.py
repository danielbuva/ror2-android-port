#!/usr/bin/env python3
"""Run synthetic update acceptance through the real Android installer UI.

Run only through /lab with an explicitly authorized device alias.
No game, existing alpha installation,
production key, arbitrary private directory, or remote release is used. The
runner toolhost job builds the exact-ref public tool APK; this script validates
that receipt and uses a fresh independent test publisher key.
All generated binaries/keys stay on the lab host/device, never in GitHub output.
"""

import argparse
import ast
from contextlib import contextmanager, nullcontext
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
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
PROMPT_CASES = ("install-unknown-apps-visible", "pending-user-action-visible")
PRODUCER = "tools/phone-build/accepted-output/record_produce.py"
JOB = "recipe/synthetic-installer-update-job.json"
INPUTS = "recipe/synthetic-installer-update-inputs.json"
KEY_ID = "dots-synthetic-extra-test"
DIAGNOSTICS = None
CURRENT_PHASE = "setup"


class Failure(Exception):
    """Only fixed, authored reason codes may leave the lab host."""


def process_pss(data):
    """A single app-process sample, not child-tool memory or a true peak."""
    if not isinstance(data, bytes) or len(data) > 65536:
        return None
    values = re.findall(rb"\bTOTAL PSS:\s*(\d+)\b", data)
    return int(values[0]) * 1024 if len(values) == 1 else None


class FlowMetrics:
    """Optional, synchronous observations; never own a device or alter acceptance."""

    STAGES = (
        "fresh-installer",
        "synthetic-provision-and-check",
        "baseline-reconstruction",
        "visible-install-permission",
        "baseline-install",
        "seed-retention-witness",
        "check-for-updates",
        "in-place-update",
        "verify-profile-settings",
    )

    def __init__(self, phone):
        self.phone, self.current, self.rows = phone, None, []

    def sample(self, force=False):
        row = self.current
        now = time.monotonic()
        if row is None or not force and row["times"] and now - row["times"][-1] < 10:
            return
        row["times"].append(now)
        try:
            observed = self.phone.flow_observation()
        except Exception:
            observed = {}
        if not isinstance(observed, dict):
            observed = {}
        safe = {}
        for package in ("installer", "alpha"):
            value = observed.get(package, {})
            if not isinstance(value, dict):
                value = {}
            safe[package] = {
                key: value.get(key) if type(value.get(key)) is int and value[key] >= 0 else None for key in ("pss_bytes", "code_free_bytes", "data_free_bytes")
            }
        temperature = observed.get("battery_temp_tenths_c")
        safe["battery_temp_tenths_c"] = temperature if type(temperature) is int and temperature >= 0 else None
        row["samples"].append(safe)

    @contextmanager
    def stage(self, name):
        if name not in self.STAGES or self.current is not None:
            raise Failure("phone-flow-stage-contract")
        row = {"stage": name, "started": time.monotonic(), "times": [], "samples": [], "completed": False}
        self.current = row
        self.sample(force=True)
        try:
            yield
            row["completed"] = True
        finally:
            self.sample(force=True)
            row["elapsed_seconds"] = round(time.monotonic() - row["started"], 3)
            self.current = None
            self.rows.append(row)

    def report(self):
        rows = []
        for row in self.rows:
            samples = row["samples"]
            packages = {}
            for package in ("installer", "alpha"):
                memory = [sample[package]["pss_bytes"] for sample in samples if sample[package]["pss_bytes"] is not None]
                packages[package] = {
                    "memory_samples": len(memory),
                    "sampled_max_pss_bytes": max(memory) if memory else None,
                    "storage_start": {key: samples[0][package][key] for key in ("code_free_bytes", "data_free_bytes")},
                    "storage_end": {key: samples[-1][package][key] for key in ("code_free_bytes", "data_free_bytes")},
                }
            rows.append(
                {
                    "stage": row["stage"],
                    "completed": row["completed"],
                    "elapsed_seconds": row["elapsed_seconds"],
                    "samples": len(samples),
                    "largest_sample_gap_seconds": round(max((b - a for a, b in zip(row["times"], row["times"][1:])), default=0), 3),
                    "packages": packages,
                    "sampled_max_battery_temp_c": max(
                        (s["battery_temp_tenths_c"] / 10 for s in samples if s["battery_temp_tenths_c"] is not None), default=None
                    ),
                }
            )
        return {"mode": "synthetic-phone-flow-metrics", "memory_scope": "sampled-app-process-pss-not-true-peak", "stages": rows}


def install_diagnostic_summary(data):
    """Only the agreed fixed A diagnostic schema may leave the private host."""
    unavailable = {"status": "unavailable", "reason": "invalid-schema"}
    if not isinstance(data, bytes) or len(data) > 4096:
        return {"status": "unavailable", "reason": "size-limit"}
    try:
        row = json.loads(data)
    except (ValueError, UnicodeError):
        return unavailable
    if row is None:
        return {"status": "unavailable", "reason": "missing"}
    stages = {
        "prepare",
        "session-create",
        "unknown",
        "session-open",
        "write-start",
        "write-complete",
        "fsync-start",
        "fsync-complete",
        "commit-start",
        "commit-returned",
    }
    callbacks = {"none", "pending-user-action", "success", "failure", "unknown"}
    if not isinstance(row, dict) or type(row.get("schema")) is not int or row["schema"] not in (1, 2):
        return unavailable
    keys = {"schema", "stage", "callback", "session_match"}
    if row["schema"] == 2:
        keys |= {"receiver_registration", "callback_entry"}
    if set(row) != keys or not isinstance(row["stage"], str) or row["stage"] not in stages:
        return unavailable
    if not isinstance(row["callback"], str) or row["callback"] not in callbacks:
        return unavailable
    if (row["callback"] == "none" and row["session_match"] is not None) or (row["callback"] != "none" and type(row["session_match"]) is not bool):
        return unavailable
    result = {"status": "observed", "stage": row["stage"], "callback": row["callback"], "session_match": row["session_match"]}
    if row["schema"] == 2:
        if not isinstance(row["receiver_registration"], str) or row["receiver_registration"] not in {
            "private",
            "exported",
            "disabled",
            "missing",
            "unavailable",
        }:
            return unavailable
        if not isinstance(row["callback_entry"], str) or row["callback_entry"] not in {"none", "entered", "unknown"}:
            return unavailable
        result.update(receiver_registration=row["receiver_registration"], callback_entry=row["callback_entry"])
    return result


def settings_window_identity(activity, displays):
    """Private join: ActivityRecord-owned window to display 0 current focus.

    WindowToken.dump supplies windows; DisplayContent.dump supplies current
    focus. AccessibilityWindowInfo.isFocused uses that same WMS focus predicate.
    The private fingerprint is compared in memory only, never reported.
    """
    if not isinstance(activity, bytes) or len(activity) > 65536 or not isinstance(displays, bytes) or len(displays) > 131072:
        return False, None
    try:
        rows = activity.decode("utf-8").splitlines()
        text = displays.decode("utf-8")
    except UnicodeError:
        return False, None
    owned = [row for row in rows if row.startswith("windows=")]
    if len(owned) != 1 or not owned[0].startswith("windows=[") or not owned[0].endswith("]"):
        return False, None
    window_pattern = r"Window\{[0-9a-fA-F]+ u[0-9]+ [^{}\n]+\}"
    content = owned[0][len("windows=[") : -1]
    windows = re.findall(window_pattern, content)
    if not windows or len(set(windows)) != len(windows) or ", ".join(windows) != content:
        return False, None
    header = "WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)"
    lines = text.splitlines()
    if not lines or lines[0] != header or lines.count(header) != 1:
        return False, None
    starts = [(index, match.group(1)) for index, line in enumerate(lines) if (match := re.match(r"^\s*Display: mDisplayId=([0-9]+)(?:\s|$)", line))]
    if len([item for item in starts if item[1] == "0"]) != 1 or len({item[1] for item in starts}) != len(starts):
        return False, None
    position = next(index for index, item in enumerate(starts) if item[1] == "0")
    start = starts[position][0]
    end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
    focused = [line.strip()[len("mCurrentFocus=") :] for line in lines[start:end] if line.strip().startswith("mCurrentFocus=")]
    if len(focused) != 1 or re.fullmatch(window_pattern, focused[0]) is None or focused[0].endswith(" EXITING}") or focused[0] not in windows:
        return False, None
    return True, sha(focused[0].encode())


def prompt_activity_summary(data, current_user, displays=None, *, install=False):
    """Fixed booleans from one Android 13 server-side top-resumed record.

    This relies on the hash-owned app's fixed, no-extra Settings deep link:
    dumpsys Intent text is not an adversarially unambiguous serialization.
    A resumed record is not a visible click target; the UI gate remains required.
    AOSP android-13.0.0_r1: ActivityTaskManagerService.dumpTopResumedActivityLocked
    and ActivityRecord.dump. No record identities or raw fields leave this helper.
    """
    result = dict.fromkeys(
        (
            "record_verified",
            "component_verified",
            "target_verified",
            "caller_verified",
            "user_verified",
            "resumed_verified",
            "visible_verified",
            "focused_window_verified",
        ),
        False,
    )
    if not isinstance(data, bytes) or len(data) > 65536 or not isinstance(current_user, bytes) or len(current_user) > 64:
        return result
    try:
        lines = data.decode("utf-8").splitlines()
        user = current_user.decode("ascii").strip()
    except UnicodeError:
        return result
    header = "ACTIVITY MANAGER TOP-RESUMED (dumpsys activity top-resumed)"
    prefixes = ("packageName=", "launchedFromUid=", "Intent { ", "mActivityComponent=", "state=", "occludesParent=", "mVisibleRequested=")
    records = {prefix: [line for line in lines if line.startswith(prefix)] for prefix in prefixes}
    if (
        not lines
        or lines[0] != header
        or lines.count(header) != 1
        or not all(len(rows) == 1 for rows in records.values())
        or sum("Intent {" in line for line in lines) != 1
    ):
        return result
    # Primary record starts immediately after the header; reject another record
    # or nested/indented stand-ins rather than matching independent substrings.
    if (
        len(lines) < 5
        or lines[1] != records["packageName="][0]
        or lines[2] != records["launchedFromUid="][0]
        or not lines[3].startswith("app=")
        or lines[4] != records["Intent { "][0]
    ):
        return result
    result["record_verified"] = True
    result["focused_window_verified"] = settings_window_identity(data, displays)[0]
    if install:
        # AOSP android-13.0.0_r1 InstallStart forwards CONFIRM_INSTALL to
        # PackageInstallerActivity with the sealed session in extras. That
        # forward makes the system installer, not the test app, the caller.
        # PackageInstallerSession sets the package; InstallStart retains it
        # while adding the component. Both identities must name the same owner.
        component = records["mActivityComponent="][0].removeprefix("mActivityComponent=")
        components = {
            package + "/" + activity: package
            for package in ("com.android.packageinstaller", "com.google.android.packageinstaller")
            for activity in (".PackageInstallerActivity", "com.android.packageinstaller.PackageInstallerActivity")
        }
        package = components.get(component)
        result["component_verified"] = package is not None and records["packageName="][0] == f"packageName={package} processName={package}"
        caller_package = re.escape(package or "invalid")
        intent = (
            r"Intent \{ act=android\.content\.pm\.action\.CONFIRM_INSTALL (?:flg=0x[0-9a-fA-F]+ )?"
            + r"(?:pkg="
            + re.escape(package or "invalid")
            + r" )?cmp="
            + re.escape(component)
            + r" \(has extras\) \}"
        )
    else:
        component = "com.android.settings/.Settings$ManageAppExternalSourcesActivity"
        result["component_verified"] = (
            records["packageName="][0] == "packageName=com.android.settings processName=com.android.settings"
            and records["mActivityComponent="][0] == "mActivityComponent=" + component
        )
        caller_package = re.escape(PACKAGE)
        # The hash-owned app supplies this fixed no-extra Settings deep link.
        intent = (
            r"Intent \{ act=android\.settings\.MANAGE_UNKNOWN_APP_SOURCES dat=package:"
            + re.escape(PACKAGE)
            + r" (?:flg=0x[0-9a-fA-F]+ )?cmp="
            + re.escape(component)
            + r" \}"
        )
    caller = re.fullmatch(
        r"launchedFromUid=[0-9]+ launchedFromPackage=" + caller_package + r" launchedFromFeature=null userId=([0-9]+)", records["launchedFromUid="][0]
    )
    result["caller_verified"] = caller is not None
    result["user_verified"] = caller is not None and re.fullmatch(r"[0-9]+", user) is not None and caller.group(1) == user
    result["target_verified"] = re.fullmatch(intent, records["Intent { "][0]) is not None
    result["resumed_verified"] = records["state="][0] == "state=RESUMED stopped=false delayedResume=false finishing=false"
    result["visible_verified"] = (
        re.fullmatch(r"occludesParent=(?:true|false) noDisplay=false immersive=(?:true|false) launchMode=[0-9]+", records["occludesParent="][0]) is not None
        and records["mVisibleRequested="][0] == "mVisibleRequested=true mVisible=true mClientVisible=true reportedDrawn=true reportedVisible=true"
    )
    return result


def settings_activity_summary(data, current_user, displays=None):
    return prompt_activity_summary(data, current_user, displays)


def install_activity_summary(data, current_user, displays=None):
    # Session-match diagnostics and the synthetic label are required separately;
    # dumpsys does not expose the sealed session ID inside Intent extras.
    return prompt_activity_summary(data, current_user, displays, install=True)


def install_consent_summary(nodes):
    """Fixed classifications only; observation never authorizes a consent tap."""
    expected = "Synthetic update fixture"
    text_found = any(node.get("text") == expected for node in nodes)
    description_found = any(node.get("content-desc") == expected for node in nodes)
    labels = {expected: "synthetic-fixture", GAME: "fixture-package", "Owner game installer": "installer-host"}
    titles = [node for node in nodes if node.get("resource-id") == "android:id/alertTitle"]
    buttons = [node for node in nodes if node.get("resource-id") == "android:id/button1"]
    title_class = "missing" if not titles else "multiple" if len(titles) > 1 else labels.get(titles[0].get("text"), "other")
    captions = {"install", "update", "ok", "settings", "cancel"}
    caption = buttons[0].get("text", "").casefold() if len(buttons) == 1 else ""
    button_class = "missing" if not buttons else "multiple" if len(buttons) > 1 else caption if caption in captions else "other"
    confirmation_ids = {
        package + ":id/" + name
        for package in ("com.android.packageinstaller", "com.google.android.packageinstaller")
        for name in ("install_confirm_question", "install_confirm_question_update")
    }
    confirmation = any(node.get("resource-id") in confirmation_ids for node in nodes)
    message = any(node.get("resource-id") == "android:id/message" for node in nodes)
    return {
        "expected_label_location": "both" if text_found and description_found else "text" if text_found else "content-desc" if description_found else "neither",
        "title_class": title_class,
        "button1_count": len(buttons),
        "button1_enabled_count": sum(node.get("enabled") == "true" for node in buttons),
        "button1_caption_class": button_class,
        "layout_class": "confirmation-control" if confirmation else "message-dialog" if message else "unclassified",
    }


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def check_diagnostic_summary(raw):
    """Allowlist one fixed test-only preference row; never echo arbitrary XML."""
    if not raw:
        return {"status": "unavailable", "reason": "not-recorded"}
    allowed = {
        "stage": {
            "entered",
            "blocked-busy",
            "request-written",
            "launch-returned",
            "failed-clear-status",
            "failed-request-build",
            "failed-request-write",
            "failed-service-launch",
        },
        "error": {"none", "security", "io", "json", "reflected", "other"},
        "files_root": {"canonical", "alias", "unavailable"},
    }
    try:
        if len(raw) > 4096 or b"<!" in raw:
            raise ValueError("bounded XML only")
        tree = ET.fromstring(raw)
        if tree.tag != "map" or tree.attrib or len(tree) != len(allowed):
            raise ValueError("fixed map required")
        result = {}
        for node in tree:
            name = node.get("name")
            if node.tag != "string" or set(node.attrib) != {"name"} or len(node) or name in result or name not in allowed or node.text not in allowed[name]:
                raise ValueError("fixed class required")
            result[name] = node.text
        if set(result) != set(allowed):
            raise ValueError("complete row required")
        return {"status": "observed", **result}
    except (ValueError, ET.ParseError):
        return {"status": "unavailable", "reason": "invalid-record"}


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


def execute(argv, *, label, stdin=None, timeout=300, record_output=True):
    try:
        result = subprocess.run(list(map(str, argv)), input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        if DIAGNOSTICS is not None and record_output:
            DIAGNOSTICS.record(label, stdout=getattr(error, "stdout", b""), stderr=getattr(error, "stderr", b""), outcome=type(error).__name__)
        raise Failure(label) from error
    if DIAGNOSTICS is not None and record_output:
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
        "installer_sha256": receipt["apk_sha256"],
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


WITNESS_FILES = {
    "android-profile-v1/profile.json": b'{"synthetic_profile":"retain-N"}\n',
    "offline-settings-v1/preferences.json": b'{"synthetic_settings":"retain-N"}\n',
}
WITNESS_CLASS = "dev.ror2lab.synthetic.RetentionWitness"


def witness_source():
    # Fixture-only Activity; never packaged into production inputs. It uses the
    # same Android root as ProfileRetentionProvider and exports only booleans.
    paths = ",".join(json.dumps(path) for path in WITNESS_FILES)
    values = ",".join(json.dumps(value.decode()) for value in WITNESS_FILES.values())
    return r"""package dev.ror2lab.synthetic;
import android.app.Activity;
import android.os.Bundle;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.JSONObject;
public final class RetentionWitness extends Activity {
  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    String nonce = getIntent().getStringExtra("nonce"), mode = getIntent().getStringExtra("mode");
    if (nonce == null || !nonce.matches("[0-9a-f]{32}") || !("seed".equals(mode) || "verify".equals(mode))) { finish(); return; }
    boolean ok = false;
    try {
      File raw = getExternalFilesDir(null);
      if (raw == null) throw new IOException();
      File root = raw.getCanonicalFile();
      String[] paths = new String[]{PATHS};
      String[] values = new String[]{VALUES};
      File[] files = new File[paths.length];
      for (int i=0; i<paths.length; i++) {
        files[i] = new File(root, paths[i]);
        if (!files[i].getCanonicalFile().equals(files[i])) throw new IOException();
        if ("seed".equals(mode) && files[i].exists()) throw new IOException();
      }
      for (int i=0; i<files.length; i++) {
        byte[] expected = values[i].getBytes(StandardCharsets.UTF_8);
        if ("seed".equals(mode)) {
          File parent = files[i].getParentFile();
          if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException();
          if (!files[i].createNewFile()) throw new IOException();
          try (FileOutputStream out = new FileOutputStream(files[i])) { out.write(expected); out.getFD().sync(); }
        }
        if (!files[i].isFile() || files[i].length() != expected.length) throw new IOException();
        byte[] actual = new byte[expected.length];
        try (DataInputStream in = new DataInputStream(new FileInputStream(files[i]))) { in.readFully(actual); if (in.read() != -1) throw new IOException(); }
        if (!Arrays.equals(actual, expected)) throw new IOException();
      }
      ok = true;
    } catch (Exception failure) { ok = false; }
    try {
      JSONObject row = new JSONObject().put("nonce", nonce).put("mode", mode).put("verified", ok).put("files", ok ? 2 : 0);
      File target = new File(getFilesDir(), "synthetic-retention-witness.json"), temp = new File(getFilesDir(), "synthetic-retention-witness.tmp");
      try (FileOutputStream out = new FileOutputStream(temp)) { out.write(row.toString().getBytes(StandardCharsets.UTF_8)); out.getFD().sync(); }
      if (!temp.renameTo(target)) throw new IOException();
    } catch (Exception failure) { /* Missing receipt fails the host check. */ }
    finish();
  }
}
""".replace("PATHS", paths).replace("VALUES", values)


def synthetic_manifest(temporary):
    """AAPT1 indexes -M by basename and requires AndroidManifest.xml."""
    manifest = temporary / "AndroidManifest.xml"
    manifest.write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.ror2lab.alpha" android:versionCode="1"><uses-sdk android:minSdkVersion="24" android:targetSdkVersion="30"/><application android:label="@string/app_name" android:debuggable="true" android:extractNativeLibs="true"><activity android:name="com.unity3d.player.UnityPlayerActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity><activity android:name="dev.ror2lab.synthetic.RetentionWitness" android:exported="true"/></application></manifest>'
    )
    return manifest


def synthetic_inputs(tools, temporary):
    """Compile tiny ORIGINAL fixtures, not Unity/game/SDK runtime implementations.

    Only the fixture witness Activity and real authored retention provider run
    in the alpha package; the synthetic Unity Activity is never launched. These
    objects exercise packaging/update mechanics, not game readiness.
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
    witness = temporary / "RetentionWitness.java"
    witness.write_text(witness_source())
    for number in range(1, 5):
        name = "UnityPlayerActivity" if number == 1 else "SyntheticMarker" + str(number)
        java = temporary / (name + ".java")
        java.write_text("package com.unity3d.player; public class " + name + (" extends android.app.Activity" if number == 1 else "") + " {}\n")
        result["apk/classes" + (str(number) if number > 1 else "") + ".dex"] = tools.dex(
            [java, witness] if number == 1 else [java], temporary / ("synthetic-dex-" + str(number))
        )
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


TRANSPORT = module("lab_adb_transport", ROOT / "scripts/lab/adb_transport.py")


def adb_diagnostic(label, **record):
    if DIAGNOSTICS is not None:
        DIAGNOSTICS.record(label, **record)


class Phone:
    def __init__(self, serial, timeout, allow_test_installs=False, allow_test_notifications=False):
        self.serial, self.timeout = serial, timeout
        self.allow_test_installs = allow_test_installs
        self.allow_test_notifications = allow_test_notifications
        self.notification_denied = False
        self.flow_metrics = None
        self.adb = Path("/opt/homebrew/bin/adb")
        self.transport = TRANSPORT.AdbTransport(self.adb, serial, observer=adb_diagnostic)
        self.owned_installer = False
        self.install_attempted = False
        self.installer_hash = None
        self.alpha_hash = None
        self.reverse_port = None
        self.install_volume = None
        self.settings_focus_key = None
        self.install_focus_key = None
        self.ui_path = "/data/local/tmp/ror2-installer-ui-" + secrets.token_hex(8) + ".xml"

    def flow_observation(self):
        """Read only the freshly owned fixed packages; raw responses stay private."""
        result = {}
        for name, package, expected in (("installer", PACKAGE, self.installer_hash if self.owned_installer else None), ("alpha", GAME, self.alpha_hash)):
            row = result[name] = {}
            if not expected:
                continue
            try:
                if self.package_hash(package) != expected:
                    continue
                memory = self.shell("dumpsys", "meminfo", "-s", package, label="phone-flow-memory", timeout=10)
                row["pss_bytes"] = process_pss(memory)
            except Exception:
                pass
            try:
                # Recheck ownership if memory sampling failed. Never derive a
                # report from a replaced package or a remembered volume path.
                if self.package_hash(package) != expected:
                    continue
                paths = self.package_paths(package)
                if len(paths) != 1 or not paths[0].startswith("package:"):
                    continue
                row["code_free_bytes"] = self.available(self.shell("df", "-k", paths[0][8:], label="phone-flow-code-free", timeout=10))
                row["data_free_bytes"] = self.available(self.shell("run-as", package, "df", "-k", ".", label="phone-flow-data-free", timeout=10))
                if name == "installer":
                    battery = self.shell("dumpsys", "battery", label="phone-flow-temperature", timeout=10)
                    values = re.findall(rb"^\s*temperature:\s*(\d+)\s*$", battery, re.M)
                    if len(values) == 1:
                        result["battery_temp_tenths_c"] = int(values[0])
            except Exception:
                pass
        return result

    def execute(self, *args, stdin=None, label, timeout=60, idempotent=False):
        try:
            return self.transport.execute(*args, label=label, stdin=stdin, timeout=timeout, idempotent=idempotent)
        except TRANSPORT.AdbError:
            raise Failure(label) from None

    def command(self, *args, stdin=None, label, timeout=60, idempotent=False):
        result = self.execute(*args, label=label, stdin=stdin, timeout=timeout, idempotent=idempotent)
        if result.returncode:
            raise Failure(label)
        return result.stdout

    def detached(self, command, *, label, timeout=30):
        # Long accessibility commands survive a killed host adb client. Polling
        # never relaunches the job; final logical records preserve the existing
        # private UI diagnostic inspector's dump/read adjacency contract.
        with tempfile.TemporaryDirectory(prefix="ror2-adb-logs-") as temporary:
            logs = Path(temporary)
            try:
                job = self.transport.start_detached(command, label=label, timeout=min(10, timeout))
                if DIAGNOSTICS is not None:
                    # Retain the exact private handle and partial logs if waiting
                    # times out. No device identifiers or paths are published.
                    name = Path(job.directory).name
                    DIAGNOSTICS.write(name + ".json", encoded({"directory": job.directory, "phase": CURRENT_PHASE, "category": label}))
                    logs = DIAGNOSTICS.directory / name
                    logs.mkdir(mode=0o700)
                result = self.transport.wait_detached(job, logs, label=label, timeout=timeout)
                try:
                    self.transport.cleanup_detached(job)
                except TRANSPORT.AdbError:
                    pass  # Terminal evidence exists; retain the exact directory.
            except TRANSPORT.AdbError as error:
                adb_diagnostic(
                    label,
                    stdout=(logs / "stdout.log").read_bytes() if (logs / "stdout.log").is_file() else b"",
                    stderr=(logs / "stderr.log").read_bytes() if (logs / "stderr.log").is_file() else b"",
                    outcome="TimeoutExpired" if isinstance(error, TRANSPORT.DetachedUncertain) else "transport-error",
                )
                raise Failure(label) from None
        adb_diagnostic(label, stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
        return result

    def install(self, apk):
        self.install_attempted = True
        self.installer_hash = sha(apk.read_bytes())
        try:
            self.transport.install(
                apk,
                self.install_volume,
                label="install-fresh-test-installer",
                timeout=600,
                reconcile=lambda: self.package_hash(PACKAGE) == self.installer_hash,
            )
        except TRANSPORT.AdbError:
            raise Failure("test-installer-install-unverified") from None
        self.owned_installer = True

    def shell(self, *args, **kwargs):
        # Exact read-only command shapes; mutations (taps, appops set, launches,
        # writes, uninstalls) are not silently replayed after an uncertain result.
        readonly = (
            args[:1] in (("cat",), ("sha256sum",), ("df",))
            or args[:2]
            in (
                ("sm", "list-volumes"),
                ("appops", "get"),
                ("am", "get-current-user"),
            )
            or args
            in (
                ("dumpsys", "power"),
                ("dumpsys", "window"),
                ("dumpsys", "activity", "activities"),
                ("dumpsys", "accessibility"),
                ("dumpsys", "activity", "processes"),
            )
            or (len(args) >= 3 and args[:1] == ("run-as",) and args[2] == "df")
        )
        return self.command("shell", *args, idempotent=readonly, **kwargs)

    def package_paths(self, package):
        # Android pm path reports an absent package with either exit 0 or 1.
        # This exception belongs only to this read-only query, not generic ADB.
        result = self.execute("shell", "pm", "path", package, label="device-package-path-query", timeout=60, idempotent=True)
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
        if not re.fullmatch(r"[A-Za-z0-9_./+ -]+", path) or ".." in path.split("/"):
            raise Failure("test-input-path")
        self.shell("run-as", PACKAGE, "mkdir", "-p", shlex.quote(str(Path(path).parent)), label="device-input-directory")
        self.command("shell", shlex.join(["run-as", PACKAGE, "sh", "-c", "cat > " + shlex.quote(path)]), stdin=data, label="device-input-write")

    def read(self, name, *, timeout=60):
        path = "files/owner-input/" + name
        result = self.command(
            "shell",
            "run-as",
            PACKAGE,
            "sh",
            "-c",
            "'if [ -f " + path + " ]; then cat " + path + "; else printf null; fi'",
            label="device-state-read",
            timeout=timeout,
        )
        return json.loads(result)

    def retain_build_artifact(self, receipt, name, destination, *, timeout=300):
        """Retain one receipt-pinned result before owned-installer cleanup.

        Stream directly to ignored host storage; never copy a device checkpoint,
        traverse undeclared results, or buffer a bundle in the diagnostics log.
        """
        if not self.owned_installer or not self.installer_hash or self.package_hash(PACKAGE) != self.installer_hash:
            raise Failure("artifact-installer-not-owned")
        directory = receipt.get("directory", "")
        digest = receipt.get("files", {}).get(name, "")
        if not isinstance(directory, str) or not re.fullmatch(r"[0-9a-f]{16}-[A-Za-z0-9_-]+/output", directory):
            raise Failure("artifact-receipt-directory")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_./+ -]+", name) or any(part in ("", ".", "..") for part in name.split("/")):
            raise Failure("artifact-receipt-path")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Failure("artifact-receipt-hash")
        destination = Path(destination)
        if not destination.resolve().is_relative_to((ROOT / "work").resolve()):
            raise Failure("artifact-host-output-not-private")
        if destination.exists() or destination.is_symlink():
            raise Failure("artifact-host-output-exists")
        path = "files/owner-input/work/releases/jobs/" + directory + "/" + name
        parents = [str(parent) for parent in reversed(Path(path).parents) if str(parent) != "."]
        checks = "; ".join("[ ! -L " + shlex.quote(part) + " ] || exit 1" for part in [*parents, path])
        command = checks + "; [ -f " + shlex.quote(path) + " ] && cat " + shlex.quote(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".retained-", dir=destination.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                try:
                    result = subprocess.run(
                        [str(self.adb), "-s", self.serial, "exec-out", shlex.join(["run-as", PACKAGE, "sh", "-c", command])],
                        stdout=stream,
                        stderr=subprocess.PIPE,
                        timeout=timeout,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    raise Failure("artifact-transfer-unavailable") from None
            with temporary.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if result.returncode or actual != digest:
                raise Failure("artifact-transfer-hash-mismatch")
            # An exclusive link publishes only the verified file, never a partial
            # result or a replacement for an existing retained witness.
            os.link(temporary, destination)
            return {"bytes": destination.stat().st_size, "sha256": actual}
        finally:
            temporary.unlink(missing_ok=True)

    def ui(self):
        return self.ui_for((PACKAGE,))

    def ui_for(self, allowed_packages):
        # A newly launched Activity can report a null accessibility root while
        # uiautomator still exits 0 and creates no file. Retry only that observed
        # result, never cat a missing dump or retry unrelated command failures.
        for attempt in range(3):
            result = self.detached(["uiautomator", "dump", self.ui_path], label="device-ui-dump", timeout=30)
            if result.returncode:
                raise Failure("device-ui-dump")
            # Both AOSP dump modes wait for idle before acquiring any root.
            # Timeout exits 0 without writing XML; never read a stale/missing file.
            if "idle-timeout" in (ui_output_classification(result.stdout), ui_output_classification(result.stderr)):
                raise Failure("device-ui-idle-timeout")
            if "null-root" not in (ui_output_classification(result.stdout), ui_output_classification(result.stderr)):
                break
            if attempt == 2:
                return self.ui_windows(allowed_packages)
            time.sleep(1)
        return self.read_ui_dump("hierarchy")

    def read_ui_dump(self, root):
        try:
            value = self.shell("cat", self.ui_path, label="device-ui-read")
        finally:
            self.shell("rm", "-f", self.ui_path, label="device-ui-remove")
        closing = ("</" + root + ">").encode()
        start, end = value.find(b"<?xml"), value.rfind(closing)
        if start < 0 or end < 0:
            raise Failure("ui-hierarchy-unavailable")
        return ET.fromstring(value[start : end + len(closing)])

    def ui_windows(self, allowed_packages, *, recovery=True):
        # Android 13 DumpCommand's --windows uses getWindowsOnAllDisplays,
        # unlike the failed single active-root query. Older binaries may ignore
        # the option, so neither exit 0 nor a success message proves a hierarchy.
        reason = "ui-window-fallback-unavailable"
        try:
            if not self.owned_installer:
                raise Failure("ui-window-installer-not-owned")
            result = self.detached(["uiautomator", "dump", "--windows", self.ui_path], label="device-ui-windows-dump", timeout=30)
            if result.returncode or ui_output_classification(result.stdout) != "dump-reported-written":
                raise Failure("ui-window-dump-unavailable")
            hierarchy = focused_ui_hierarchy(self.read_ui_dump("displays"), allowed_packages)
            print("INFO ui-null-root-recovered source=focused-window" if recovery else "INFO prompt-ui source=focused-default-window", flush=True)
            return hierarchy
        except Failure as error:
            reason = str(error)
        except Exception:
            reason = "ui-window-fallback-invalid"
        self.ui_diagnostics(reason)
        raise Failure("device-ui-null-root-retry-exhausted" if recovery else "settings-ui-focused-window-unavailable")

    def ui_diagnostics(self, fallback_reason):
        # Observation only: never start instrumentation, unlock, grant a
        # permission, change accessibility settings, or export dumpsys text.
        outputs = {}
        for name, args in (
            ("power", ("dumpsys", "power")),
            ("window", ("dumpsys", "window")),
            ("activity", ("dumpsys", "activity", "activities")),
            ("accessibility", ("dumpsys", "accessibility")),
            ("instrumentation", ("dumpsys", "activity", "processes")),
            ("user", ("am", "get-current-user")),
        ):
            try:
                outputs[name] = self.shell(*args, label="device-ui-diagnostic-" + name).decode(errors="replace")
            except Exception:
                outputs[name] = None
        summary = ui_environment_summary(outputs)
        print(encoded({"mode": "ui-null-root-diagnostics", "fallback_reason": fallback_reason, "observed": summary}).decode(), end="", flush=True)

    def tap_visible(self, label):
        # Building can outlast the display timeout after start(). Refresh wake
        # before each UI interaction without relaunching the Activity: Android's
        # PackageInstaller consent window must keep its existing focus. WAKEUP
        # never toggles an already-awake display off; cleanup still sleeps it.
        self.shell("input", "keyevent", "KEYCODE_WAKEUP", label="device-display-wake")
        tree = self.ui_for((PACKAGE, "com.android.packageinstaller", "com.google.android.packageinstaller")) if label == "Install" else self.ui()
        for node in tree.iter("node"):
            if node.get("text", "").casefold() == label.casefold() and node.get("enabled") == "true":
                bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
                if not bounds:
                    raise Failure("ui-button-bounds")
                x1, y1, x2, y2 = map(int, bounds.groups())
                self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2), label="device-ui-tap")
                if label == "Install":
                    print("INFO android-install-consent actor=harness", flush=True)
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
        # The qualified synthetic flow restarts this same freshly owned app.
        # Reuse the device-proven explicit second-denial policy, never grant.
        if self.flow_metrics is not None and self.notification_denied:
            self.dismiss_notification_permission(repeat_denial=True)
        else:
            self.dismiss_notification_permission()

    def dismiss_notification_permission(self, *, repeat_denial=False):
        # ToolHostActivity.onCreate requests only POST_NOTIFICATIONS. This is
        # not the separately authorized unknown-source install permission.
        # Decline by default; allow only with explicit owner authorization for
        # this owned test app. Never act on an unidentified permission or rely
        # on localized button text.
        if not self.owned_installer:
            raise Failure("notification-dialog-installer-not-owned")
        if repeat_denial and self.allow_test_notifications:
            raise Failure("notification-repeat-denial-conflicting-policy")
        controller = "com.android.permissioncontroller"
        if repeat_denial:
            self.require_owned_installer()
            tree = self.ui_windows((PACKAGE, controller), recovery=False)
            self.prompt_nodes(tree, (PACKAGE, controller))
        else:
            tree = self.ui_for((PACKAGE, controller))
        nodes = [node for node in tree.iter("node") if node.get("package") == controller]
        if not nodes:
            return False
        messages = [node.get("text", "").casefold() for node in nodes if node.get("resource-id") == controller + ":id/permission_message"]
        if len(messages) != 1 or "owner game installer" not in messages[0] or not re.search(r"\bnotifications\b", messages[0]):
            raise Failure("notification-dialog-not-identified")
        action = "allow" if self.allow_test_notifications else "deny"
        buttons = [node for node in nodes if node.get("resource-id") == controller + ":id/permission_" + action + "_button" and node.get("enabled") == "true"]
        if repeat_denial:
            # AOSP's second denial is user-fixed, not an ordinary denial alias.
            # Only the picker cold-restart flow opts in, after this run denied
            # the fresh hash-owned disposable app's first notification prompt.
            ordinary = controller + ":id/permission_deny_button"
            fixed = controller + ":id/permission_deny_and_dont_ask_again_button"
            buttons = [node for node in nodes if node.get("resource-id") in (ordinary, fixed)]
            if len(buttons) != 1 or buttons[0].get("enabled") != "true" or buttons[0].get("clickable") != "true":
                raise Failure("notification-denial-unavailable")
            if buttons[0].get("resource-id") == fixed:
                if not self.notification_denied:
                    raise Failure("notification-repeat-denial-without-prior-denial")
                action = "deny-and-dont-ask-again"
            self.require_owned_installer()
            confirmed = self.ui_windows((controller,), recovery=False)
            self.prompt_nodes(confirmed, (controller,))
            if ET.tostring(tree) != ET.tostring(confirmed):
                raise Failure("notification-dialog-focus-changed")
        if len(buttons) != 1:
            raise Failure("notification-allow-unavailable" if self.allow_test_notifications else "notification-denial-unavailable")
        self.tap_prompt_node(buttons[0], "device-notification-" + action)
        observed = self.ui_windows((PACKAGE, controller), recovery=False) if repeat_denial else self.ui_for((PACKAGE, controller))
        if any(node.get("package") == controller for node in observed.iter("node")):
            raise Failure("notification-dialog-not-dismissed")
        if not self.allow_test_notifications:
            self.notification_denied = True
        if action == "deny-and-dont-ask-again":
            print("INFO android-notification-denial effect=user-fixed scope=owned-disposable-installer", flush=True)
        return True

    def wait_state(self, expected):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.flow_metrics is not None:
                self.flow_metrics.sample()
            row = self.read("update-state.json")
            if row and row.get("state") in expected:
                return row
            if row and row.get("state") == "ERROR":
                raise Failure("installer-update-error")
            time.sleep(1)
        raise Failure("installer-update-timeout")

    def read_check_progress(self, timeout):
        row = self.read("update-state.json", timeout=timeout)
        state = row.get("state") if isinstance(row, dict) else None
        if state == "ERROR":
            raise Failure("installer-update-error")
        if state not in ("TEST_WAIT", "CHECKING", "UPDATE_AVAILABLE"):
            raise Failure("release-check-state-unavailable")
        return row

    def check_acknowledgement(self):
        # A returned input command is not proof that the Activity handled it.
        # Observe only: no expensive APK rehash/telemetry inside this short wait.
        deadline = time.monotonic() + min(15, self.timeout)
        while (remaining := deadline - time.monotonic()) > 0:
            row = self.read_check_progress(min(5, remaining))
            if row["state"] != "TEST_WAIT":
                return row
            time.sleep(0.25)
        return None

    def retry_unacknowledged_check(self):
        self.require_owned_installer()
        row = self.read_check_progress(5)
        if row["state"] != "TEST_WAIT":
            return row
        self.shell("input", "keyevent", "KEYCODE_WAKEUP", label="device-display-wake")

        def control():
            tree = self.ui_windows((PACKAGE,), recovery=False)
            self.prompt_nodes(tree, (PACKAGE,))
            nodes = [node for node in tree.iter("node") if node.get("text", "").casefold() == "check for updates"]
            if len(nodes) != 1 or nodes[0].get("class") != "android.widget.Button" or nodes[0].get("enabled") != "true" or nodes[0].get("clickable") != "true":
                raise Failure("release-check-control-unavailable")
            return nodes[0]

        first, second = control(), control()
        if first.attrib != second.attrib:
            raise Failure("release-check-control-changed")
        # A late acknowledgment prohibits another tap. Never reset TEST_WAIT:
        # the handler persists CHECKING before launching any release worker.
        row = self.read_check_progress(5)
        if row["state"] != "TEST_WAIT":
            return row
        self.tap_prompt_node(second, "device-release-check-retry")
        print("INFO release-check-retry actor=harness reason=unacknowledged-visible-action", flush=True)
        return self.check_acknowledgement()

    def check(self, version):
        self.put("update-state.json", encoded({"state": "TEST_WAIT"}))
        self.tap("Check for updates")
        row = self.check_acknowledgement()
        if row is None:
            row = self.retry_unacknowledged_check()
        if row is None:
            raise Failure("check-action-not-acknowledged")
        if row["state"] == "CHECKING":
            row = self.wait_state({"UPDATE_AVAILABLE"})
        if row.get("release", {}).get("version_code") != version:
            raise Failure("release-version-not-observed")

    def installed(self, publisher, previous=None, *, require_pending_prompt=False):
        deadline = time.monotonic() + self.timeout
        callback_absent_since = None
        callback_observed = False
        pending_observed = False
        consent_observed = False
        while time.monotonic() < deadline:
            if self.flow_metrics is not None:
                self.flow_metrics.sample()
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
                if require_pending_prompt and not (pending_observed and consent_observed):
                    raise Failure("install-pending-prompt-not-observed")
                self.storage()
                self.start()
                return receipt
            row = self.read("update-state.json")
            if row and row.get("state") == "ERROR":
                try:
                    if CURRENT_PHASE == "baseline-N-install" and row.get("pipeline", {}).get("first_failure", {}).get("stage") == "apk":
                        self.capture_apk_logs()
                except Exception:
                    # Diagnostic loss must not replace the first failure or
                    # prevent normal owned-package cleanup.
                    pass
                raise Failure("installer-build-error")
            if (
                row
                and row.get("state") in ("INSTALLING", "AWAITING_CONFIRMATION")
                and (not callback_observed or (require_pending_prompt and not consent_observed))
            ):
                try:
                    diagnostic = self.capture_install_diagnostic()
                except Exception:
                    # Optional evidence loss must not replace the install result
                    # or manufacture proof that a callback remained absent.
                    diagnostic = {"status": "unavailable"}
                if (
                    require_pending_prompt
                    and row.get("state") == "AWAITING_CONFIRMATION"
                    and diagnostic.get("status") == "observed"
                    and diagnostic.get("callback") == "pending-user-action"
                    and diagnostic.get("session_match") is True
                ):
                    pending_observed = True
                    consent_observed = self.confirm_synthetic_install() or consent_observed
                if diagnostic.get("status") == "observed" and (diagnostic.get("callback") != "none" or diagnostic.get("callback_entry") == "entered"):
                    callback_observed = True
                    callback_absent_since = None
                elif (
                    not callback_observed
                    and row.get("state") == "INSTALLING"
                    and diagnostic.get("status") == "observed"
                    and diagnostic.get("stage") == "commit-returned"
                    and diagnostic.get("callback") == "none"
                    and diagnostic.get("session_match") is None
                    and diagnostic.get("callback_entry", "none") == "none"
                ):
                    now = time.monotonic()
                    if callback_absent_since is None:
                        callback_absent_since = now
                    elif now - callback_absent_since >= 60:
                        # Diagnostic harness bound only: never mark the runtime
                        # failed or initiate another sealed install session.
                        raise Failure("install-first-callback-timeout")
                else:
                    callback_absent_since = None
            else:
                callback_absent_since = None
            # Consent is always the real Android PackageInstaller UI. Never forge
            # success receipts or use adb install to replace the alpha package.
            if not require_pending_prompt:
                self.tap("Install", required=False)
            time.sleep(1)
        raise Failure("install-readback-timeout")

    def retention_witness(self, mode, receipt=None):
        if mode not in ("seed", "verify") or not self.owned_installer or not self.alpha_hash or self.package_hash(GAME) != self.alpha_hash:
            raise Failure("retention-witness-ownership")
        if receipt is not None:
            backup = receipt.get("retention_backup", {})
            if (
                receipt.get("profile_retention_verified") is not True
                or backup.get("data_schema") != 1
                or backup.get("bytes") != sum(map(len, WITNESS_FILES.values()))
                or not re.fullmatch(r"[0-9a-f]{64}", backup.get("snapshot", ""))
            ):
                raise Failure("retention-witness-provider-unverified")
        nonce = secrets.token_hex(16)
        try:
            self.shell("am", "force-stop", GAME, label="retention-witness-stop")
            self.shell("am", "start", "-W", "-n", GAME + "/" + WITNESS_CLASS, "--es", "mode", mode, "--es", "nonce", nonce, label="retention-witness-launch")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                raw = self.shell(
                    "run-as",
                    GAME,
                    "sh",
                    "-c",
                    "'if [ -f files/synthetic-retention-witness.json ]; then cat files/synthetic-retention-witness.json; else printf null; fi'",
                    label="retention-witness-result",
                )
                row = json.loads(raw)
                if row and row.get("nonce") == nonce:
                    if row.get("mode") != mode or row.get("verified") is not True or row.get("files") != 2:
                        raise Failure("retention-witness-mismatch")
                    break
                time.sleep(0.2)
            else:
                raise Failure("retention-witness-timeout")
        finally:
            self.shell("am", "force-stop", GAME, label="retention-witness-stop")
        self.start()

    def require_owned_installer(self):
        if not self.owned_installer or not self.installer_hash or self.package_hash(PACKAGE) != self.installer_hash:
            raise Failure("install-prompt-installer-not-owned")

    def install_permission_mode(self):
        value = self.shell("appops", "get", PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query").decode()
        # Android 13 reports an unset operation with its default on a second
        # line. This exact default is ungranted, not evidence of permission.
        if value.strip() == "No operations.":
            return "unset"
        if value.strip() == "No operations.\nDefault mode: default":
            return "default"
        if "No operations." in value:
            raise Failure("device-install-permission-shape")
        modes = re.findall(r"\bREQUEST_INSTALL_PACKAGES: (allow|ignore|deny|default|foreground)\b", value)
        if len(modes) == 1:
            return modes[0]
        raise Failure("device-install-permission-shape")

    def require_ungranted_install_permission(self):
        self.require_owned_installer()
        # Never revoke a pre-existing grant to manufacture a fresh-run result.
        if self.allow_test_installs or self.install_permission_mode() not in ("ignore", "deny", "default", "unset"):
            raise Failure("install-prompt-permission-already-granted")

    @staticmethod
    def prompt_nodes(tree, packages):
        roots = tree.findall("node")
        if len(roots) != 1 or roots[0].get("package") not in packages:
            raise Failure("install-prompt-foreground-not-identified")
        nodes = list(tree.iter("node"))
        package = roots[0].get("package")
        if any(node.get("package") not in (None, "", package) for node in nodes):
            raise Failure("install-prompt-foreground-not-identified")
        return package, nodes

    def tap_prompt_node(self, node, label):
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if not bounds:
            raise Failure("ui-button-bounds")
        x1, y1, x2, y2 = map(int, bounds.groups())
        if x2 <= x1 or y2 <= y1:
            raise Failure("ui-button-bounds")
        self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2), label=label)

    def prompt_identity(self, *, install=False):
        self.require_owned_installer()
        summarize = install_activity_summary if install else settings_activity_summary
        focus_attribute = "install_focus_key" if install else "settings_focus_key"
        label = "device-install-identity" if install else "device-settings-identity"
        summary = summarize(None, None)
        setattr(self, focus_attribute, None)
        try:
            outputs = []
            for command in ("dumpsys activity top-resumed | head -c 65537", "am get-current-user | head -c 65", "dumpsys window displays | head -c 131073"):
                result = execute(
                    [self.adb, "-s", self.serial, "shell", "sh", "-c", "'" + command + "'"],
                    label=label + "-query",
                    timeout=15,
                    record_output=False,
                )
                if result.returncode or result.stderr:
                    break
                outputs.append(result.stdout)
            if len(outputs) == 3:
                summary = summarize(*outputs)
                if all(summary.values()):
                    setattr(self, focus_attribute, settings_window_identity(outputs[0], outputs[2])[1])
        except Failure:
            pass
        # Raw top-activity text/user IDs are neither retained nor exported.
        if DIAGNOSTICS is not None:
            DIAGNOSTICS.record(label, stdout=encoded(summary), returncode=0)
        return summary

    def settings_identity(self):
        return self.prompt_identity()

    def install_identity(self):
        return self.prompt_identity(install=True)

    def allow_visible_install_permission(self):
        self.require_ungranted_install_permission()
        # The app, not an adb deep link, must open its own per-app Settings page.
        self.tap("Install verified owner build")
        settings = "com.android.settings"
        deadline = time.monotonic() + 30
        identity = settings_activity_summary(None, None)
        while time.monotonic() < deadline:
            identity = self.settings_identity()
            package, nodes = self.prompt_nodes(self.ui_windows((PACKAGE, settings), recovery=False), (PACKAGE, settings))
            if package == settings and all(identity.values()):
                focus_key = self.settings_focus_key
                break
            time.sleep(1)
        else:
            print(encoded({"mode": "settings-prompt-identity", "observed": identity}).decode(), end="", flush=True)
            raise Failure("install-settings-identity-not-verified")
        switches = [
            node
            for node in nodes
            if node.get("resource-id") in ("android:id/switch_widget", settings + ":id/switch_widget")
            and node.get("checkable") == "true"
            and node.get("enabled") == "true"
        ]
        if len(switches) != 1 or switches[0].get("checked") != "false":
            raise Failure("install-settings-ungranted-switch-not-visible")
        # Recheck the same target after reading the UI, before using its bounds.
        identity = self.settings_identity()
        unchanged = bool(focus_key) and self.settings_focus_key == focus_key
        print(encoded({"mode": "settings-prompt-identity", "observed": identity, "focus_unchanged": unchanged}).decode(), end="", flush=True)
        if not all(identity.values()) or not unchanged:
            raise Failure("install-settings-identity-changed")
        self.tap_prompt_node(switches[0], "device-install-permission-visible-enable")
        print("INFO install-permission-switch actor=harness", flush=True)
        # Require both visible checked state and read-only effective app-op.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            _, nodes = self.prompt_nodes(self.ui_windows((settings,), recovery=False), (settings,))
            observed = [node for node in nodes if node.get("resource-id") == switches[0].get("resource-id")]
            if len(observed) == 1 and observed[0].get("checked") == "true" and self.install_permission_mode() == "allow":
                break
            time.sleep(1)
        else:
            raise Failure("install-settings-grant-not-observed")
        self.shell("input", "keyevent", "KEYCODE_BACK", label="device-install-settings-return")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            package, _ = self.prompt_nodes(self.ui_for((PACKAGE, settings)), (PACKAGE, settings))
            if package == PACKAGE:
                return
            time.sleep(1)
        raise Failure("install-settings-return-not-observed")

    def confirm_synthetic_install(self):
        self.require_owned_installer()
        self.shell("input", "keyevent", "KEYCODE_WAKEUP", label="device-display-wake")
        identity = self.install_identity()
        if not all(identity.values()):
            print(encoded({"mode": "install-prompt-identity", "observed": identity}).decode(), end="", flush=True)
            if identity.get("target_verified") is False and all(value for key, value in identity.items() if key != "target_verified"):
                # A verified, focused confirmation with the wrong Intent is a
                # fixed harness gate, not a launch transition to poll for 20 min.
                raise Failure("install-consent-target-not-verified")
            return False
        focus_key = self.install_focus_key
        installers = ("com.android.packageinstaller", "com.google.android.packageinstaller")
        # The active accessibility root can still be the covered test app. Use
        # the focused display-0 window, as for the already qualified Settings UI.
        _, nodes = self.prompt_nodes(self.ui_windows(installers, recovery=False), installers)
        print(encoded({"mode": "install-consent-fixture", "identity_verified": True, "observed": install_consent_summary(nodes)}).decode(), end="", flush=True)
        if not any(node.get("text") == "Synthetic update fixture" for node in nodes):
            raise Failure("install-consent-fixture-not-identified")
        buttons = [
            node
            for node in nodes
            if node.get("resource-id") == "android:id/button1" and node.get("text", "").casefold() in ("install", "update") and node.get("enabled") == "true"
        ]
        if len(buttons) != 1:
            raise Failure("install-consent-button-not-identified")
        identity = self.install_identity()
        unchanged = bool(focus_key) and self.install_focus_key == focus_key
        print(encoded({"mode": "install-prompt-identity", "observed": identity, "focus_unchanged": unchanged}).decode(), end="", flush=True)
        if not all(identity.values()) or not unchanged:
            raise Failure("install-consent-identity-changed")
        self.tap_prompt_node(buttons[0], "device-synthetic-install-consent")
        print("INFO android-install-consent actor=harness", flush=True)
        return True

    def await_install_permission(self):
        value = self.shell("appops", "get", PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query").decode()
        if re.search(r"REQUEST_INSTALL_PACKAGES: allow\b", value):
            return
        if not self.allow_test_installs or not self.owned_installer:
            raise Failure("install-permission-owner-authorization-required")
        # The root lab invocation may pass this flag ONLY after explicit owner
        # authorization for this fresh disposable test package on the leased phone.
        self.shell("appops", "set", PACKAGE, "REQUEST_INSTALL_PACKAGES", "allow", label="device-install-permission-enable")

    def capture_check_diagnostic(self):
        # The fresh hash-owned test app stores only its last Check stage. Read
        # this independent Android preference before uninstall, not arbitrary
        # app files, raw logs or the release request (which contains metadata).
        self.require_owned_installer()
        command = (
            'for p in shared_prefs shared_prefs/owner-check-diagnostic.xml; do [ ! -L "$p" ] || exit 1; done; '
            "if [ -f shared_prefs/owner-check-diagnostic.xml ]; then head -c 4097 shared_prefs/owner-check-diagnostic.xml; fi"
        )
        raw = self.shell("run-as", PACKAGE, "sh", "-c", "'" + command + "'", label="device-check-diagnostic-read", timeout=15)
        return check_diagnostic_summary(raw)

    def capture_install_diagnostic(self):
        # Fresh-run ownership and exact installed test APK identity are mandatory.
        # No alpha/game namespace, broad traversal, or mutation is involved.
        if not self.owned_installer or not self.installer_hash or self.package_hash(PACKAGE) != self.installer_hash:
            return {"status": "unavailable", "reason": "ownership-unverified"}
        command = (
            'for p in files files/owner-input files/owner-input/install-diagnostic.json; do [ ! -L "$p" ] || exit 1; done; '
            "if [ -f files/owner-input/install-diagnostic.json ]; then head -c 4097 files/owner-input/install-diagnostic.json; else printf null; fi"
        )
        data = self.shell("run-as", PACKAGE, "sh", "-c", "'" + command + "'", label="device-install-diagnostic-read", timeout=15)
        return install_diagnostic_summary(data)

    def capture_apk_logs(self):
        # APK-stage subprocesses in build_owner_apk.build write only these two
        # logs. Never traverse producer artifacts, keys, or other app namespaces.
        if not self.owned_installer or self.package_hash(PACKAGE) != self.installer_hash:
            raise Failure("apk-log-installer-not-owned")
        for tool in ("javac", "dex"):
            script = (
                'for p in files files/owner-input files/owner-input/work files/owner-input/work/releases; do [ ! -L "$p" ] || exit 1; done; '
                "n=0; for d in files/owner-input/work/releases/build-*; do "
                '[ ! -L "$d" ] && [ ! -L "$d/assembly" ] || continue; '
                'p="$d/assembly/' + tool + '.log"; [ ! -L "$p" ] && [ -f "$p" ] || continue; '
                'n=$((n+1)); [ "$n" -le 4 ] || break; printf "ROR2_APK_LOG_BEGIN\\n"; head -c 65536 "$p" || exit 1; printf "\\n"; done'
            )
            self.shell("run-as", PACKAGE, "sh", "-c", "'" + script + "'", label="device-apk-" + tool + "-log", timeout=15)

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


def require_installer_manifest(manifest, expected_version):
    """Shared admission for synthetic installer/picker tests, without building fixtures."""
    identity = re.search(r"^package: name='([^']+)' versionCode='(\d+)'", manifest, re.MULTILINE)
    if (
        not identity
        or type(expected_version) is not int
        or identity.group(1) != PACKAGE
        or int(identity.group(2)) != expected_version
        or int(identity.group(2)) < 3
        or not re.search(r"^application-debuggable\s*$", manifest, re.MULTILINE)
    ):
        raise Failure("cached-installer-manifest-not-debug-test-package")


def prepare_artifacts(config, temporary):
    tools = HostTools(config)
    apk = config["installer_apk"]
    with zipfile.ZipFile(apk) as archive:
        trust = json.loads(archive.read("assets/release-trust.json"))
    if KEY_ID in trust["keys"]:
        raise Failure("synthetic-extra-key-id-collides-with-packaged-trust")
    manifest = run([tools.build / "aapt", "dump", "badging", apk], label="inspect-cached-installer-manifest").decode()
    require_installer_manifest(manifest, config["installer_version"])
    inputs = synthetic_inputs(tools, temporary)
    public = module("synthetic_release_public", ROOT / "tools/phone-build/owner-apk/public_release.py")
    private, key = publisher_keys(temporary, "trusted")
    wrong_private, wrong_key = publisher_keys(temporary, "wrong")
    releases = {version: release_fixture(public, inputs, version, temporary / ("release-" + str(version)), private, key) for version in (1, 2)}
    wrong = release_fixture(public, inputs, 2, temporary / "wrong-release", wrong_private, wrong_key)
    return apk, inputs, key, releases, wrong


def acceptance(phone, config, temporary, passed, *, qualify_install_prompts=False, phone_flow=False):
    metrics = phone.flow_metrics = FlowMetrics(phone) if phone_flow else None

    def stage(name):
        return metrics.stage(name) if metrics is not None else nullcontext()

    set_phase("pre-install-checks")
    if phone.occupied(GAME) or phone.occupied(PACKAGE):
        raise Failure("occupied-package-no-fresh-run-ownership")
    phone.storage()
    set_phase("host-fixture-build")
    apk, inputs, key, releases, wrong = prepare_artifacts(config, temporary)
    set_phase("pre-install-storage")
    phone.storage()
    set_phase("installer-install")
    with stage("fresh-installer"):
        phone.install(apk)
        set_phase("installer-storage")
        phone.storage()
    set_phase("installer-permission")
    if qualify_install_prompts:
        phone.require_ungranted_install_permission()
    else:
        phone.await_install_permission()
    set_phase("fixture-provision")
    with server() as service:
        with stage("synthetic-provision-and-check"):
            base = publish(service, releases[1], 1)
            phone.command("reverse", "--no-rebind", "tcp:" + str(service.server_port), "tcp:" + str(service.server_port), label="device-reverse-create")
            phone.reverse_port = service.server_port
            phone.put("debug-release-source.json", encoded({"enabled": True, "base_url": base, "key_id": KEY_ID, "public_key": key.decode()}))
            for name, data in inputs.items():
                phone.put("import/files/" + name, data)
            # Synthetic bytes and publisher are host-authored. Actual APK
            # reconstruction below runs on the phone, not the host.
            phone.put("import-state.json", encoded({"state": "IMPORTED", "message": "Synthetic test inputs only"}))
            set_phase("baseline-N-check")
            phone.start()
            phone.check(1)
            if not any("TEST RELEASE SOURCE" in node.get("text", "") for node in phone.ui().iter("node")):
                raise Failure("debug-source-warning-not-visible")
        set_phase("baseline-N-install")
        phone.storage()
        if qualify_install_prompts:
            with stage("baseline-reconstruction"):
                phone.tap("Reconstruct and install verified game")
                phone.wait_state({"READY"})
            with stage("visible-install-permission"):
                phone.allow_visible_install_permission()
                passed("install-unknown-apps-visible")
            with stage("baseline-install"):
                phone.tap("Install verified owner build")
                first = phone.installed(1, require_pending_prompt=True)
                passed("pending-user-action-visible")
        else:
            phone.tap("Reconstruct and install verified game")
            first = phone.installed(1)
        with stage("seed-retention-witness"):
            phone.retention_witness("seed")
        set_phase("check-for-updates")
        with stage("check-for-updates"):
            publish(service, releases[2], 2)
            phone.check(2)
            if "/public-tools.zip" in service.requests:
                raise Failure("check-downloaded-bundle-before-consent")
            passed("check-for-updates")
        set_phase("update-N-to-N+1")
        phone.storage()
        phone.retention_witness("verify")
        with stage("in-place-update"):
            phone.tap("Reconstruct and install verified game")
            second = phone.installed(2, first)
        with stage("verify-profile-settings"):
            phone.retention_witness("verify", second)
        passed("update-N-to-N+1")
        if phone_flow:
            passed("synthetic-phone-flow")
            return
        set_phase("same-key-rollback")
        phone.storage()
        phone.tap("Rebuild and install previous release (same key)")
        rolled = phone.installed(1, second)
        phone.retention_witness("verify", rolled)
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


def focused_window_hierarchy(document):
    # AOSP Android 13 AccessibilityNodeInfoDumper.dumpWindowsToFile schema:
    # displays/display/window/(child windows...)/DIRECT hierarchy/node.
    # Never flatten background, child, accessibility-focused or other-display
    # hierarchies into tap targets. DEFAULT_DISPLAY is 0.
    if document.tag != "displays":
        raise Failure("ui-window-schema")
    displays = [display for display in document.findall("display") if display.get("id") == "0"]
    if len(displays) != 1:
        raise Failure("ui-window-default-display-unavailable")
    windows = [window for window in displays[0].iter("window") if window.get("active") == "true" or window.get("focused") == "true"]
    if len(windows) != 1 or windows[0].get("active") != "true" or windows[0].get("focused") != "true":
        raise Failure("ui-window-focus-ambiguous")
    hierarchies = windows[0].findall("hierarchy")
    if len(hierarchies) != 1 or len(hierarchies[0].findall("node")) != 1:
        raise Failure("ui-window-root-unavailable")
    return hierarchies[0]


def focused_ui_hierarchy(document, allowed_packages):
    hierarchy = focused_window_hierarchy(document)
    package = hierarchy.find("node").get("package")
    if package not in allowed_packages or any(node.get("package") not in (None, "", package) for node in hierarchy.iter("node")):
        raise Failure("ui-window-package-not-allowed")
    return hierarchy


def ui_window_summary(data):
    """Read-only fixed foreground categories; never export window/node values."""
    try:
        start, end = data.find(b"<?xml"), data.rfind(b"</displays>")
        if start < 0 or end < 0:
            raise Failure("ui-window-schema")
        hierarchy = focused_window_hierarchy(ET.fromstring(data[start : end + len(b"</displays>")]))
        package = hierarchy.find("node").get("package")
        category = {
            PACKAGE: "test-installer",
            "com.android.permissioncontroller": "permission-controller",
            "com.android.systemui": "system-ui",
            "android": "android-system",
            "com.android.packageinstaller": "package-installer",
            "com.google.android.packageinstaller": "package-installer",
        }.get(package, "other" if package else "unknown")
        return {
            "status": "observed",
            "package_category": category,
            "mixed_node_packages": any(node.get("package") not in (None, "", package) for node in hierarchy.iter("node")),
        }
    except Failure as error:
        return {"status": "unknown", "reason": str(error)}
    except (ET.ParseError, ValueError):
        return {"status": "unknown", "reason": "ui-window-schema"}


def ui_environment_summary(outputs):
    """Fixed boolean/null facts; unknown fields never become negative proof."""
    power, window, activity, accessibility, instrumentation, user = (
        outputs.get(name) for name in ("power", "window", "activity", "accessibility", "instrumentation", "user")
    )

    def truth(text, field):
        values = set(re.findall(r"(?<![A-Za-z])" + re.escape(field) + r"=(true|false)\b", text or ""))
        return values == {"true"} if len(values) == 1 else None

    def lines_contain(text, marker, target):
        lines = [line for line in (text or "").splitlines() if re.search(marker, line)]
        return any(target in line for line in lines) if lines else None

    wake = re.findall(r"\bmWakefulness=(Awake|Asleep|Dozing|Dreaming)\b", power or "")
    current_user = user.strip() if user is not None and user.strip().isdigit() else None
    activity_users = re.findall(r"\bu(\d+)\s+" + re.escape(ACTIVITY) + r"(?=\s|\})", activity or "")
    accessibility_user = re.search(r"\bcurrentUserId=(\d+)\b", accessibility or "")
    activity_known = activity is not None and "ACTIVITY MANAGER ACTIVITIES" in activity
    accessibility_known = accessibility is not None and "ACCESSIBILITY MANAGER" in accessibility
    instrumentation_known = instrumentation is not None and "ACTIVITY MANAGER RUNNING PROCESSES" in instrumentation
    visible = []
    for block in re.split(r"(?m)(?=^\s*Window #\d+ )", window or ""):
        lines = block.splitlines()
        if lines and re.match(r"\s*Window #\d+ ", lines[0]) and PACKAGE + "/" in lines[0]:
            visible.append(truth(block, "isOnScreen"))
    return {
        **{name + "_query_ok": outputs.get(name) is not None for name in ("power", "window", "activity", "accessibility", "instrumentation", "user")},
        "display_awake": wake[0] == "Awake" if wake and len(set(wake)) == 1 else None,
        "keyguard_showing": truth(window, "showing"),
        "keyguard_showing_not_occluded": truth(window, "showingAndNotOccluded"),
        "keyguard_input_restricted": truth(window, "inputRestricted"),
        "test_activity_present": ACTIVITY in activity if activity_known else None,
        "test_activity_resumed": lines_contain(activity, r"\b(?:mResumedActivity|ResumedActivity|topResumedActivity)\s*[:=]", ACTIVITY),
        "test_window_focused": lines_contain(window, r"\bmCurrentFocus=", PACKAGE + "/"),
        "test_window_on_screen": any(visible) if visible and all(value is not None for value in visible) else None,
        "permission_window_focused": lines_contain(window, r"\bmCurrentFocus=", "com.android.permissioncontroller/"),
        "test_activity_current_user": current_user in activity_users if current_user is not None and activity_users else None,
        "accessibility_current_user": accessibility_user.group(1) == current_user if accessibility_user and current_user is not None else None,
        # Snapshot is AFTER the failing dump disconnected, not a claim that its
        # transient UiAutomation connection was absent during root acquisition.
        "ui_automation_registered_after_dump": "Ui Automation[" in accessibility if accessibility_known else None,
        "instrumentation_running_after_dump": "Active instrumentation:" in instrumentation if instrumentation_known else None,
    }


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


def backend_error_summary(message):
    """Match public source literals/locations, never print private message text."""
    sources = tuple(
        "tools/phone-build/owner-apk/" + name
        for name in ("updates.py", "release_source.py", "release.py", "public_release.py", "alpha_policy.py", "install_flow.py", "build_owner_apk.py")
    ) + (
        "tools/phone-build/accepted-output/sdk_package.py",
        "tools/phone-build/owner-code/native.py",
        "tools/phone-build/managed-host/ToolHostActivity.java",
        "tools/phone-build/managed-host/OwnerBuildService.java",
    )
    classes = (
        "ValueError",
        "TypeError",
        "KeyError",
        "ImportError",
        "ModuleNotFoundError",
        "OSError",
        "FileNotFoundError",
        "PermissionError",
        "TimeoutError",
        "ConnectionRefusedError",
        "HTTPError",
        "URLError",
        "RuntimeError",
        "java.io.IOException",
        "java.io.FileNotFoundException",
        "java.lang.IllegalStateException",
        "java.lang.IllegalArgumentException",
        "java.lang.SecurityException",
        "android.system.ErrnoException",
        "org.json.JSONException",
    )
    lines = message.splitlines()
    exceptions = sorted({name for name in classes if re.search(r"(?:^|\n)\s*" + re.escape(name) + r":", message)})
    normalized = [re.sub(r"^(?:" + "|".join(map(re.escape, classes)) + r"):\s*", "", line.strip()) for line in lines]
    matches, frames = [], []
    for source in sources:
        path = ROOT / source
        if not path.is_file():
            continue
        code = path.read_text()
        templates = []
        if source.endswith(".py"):
            for node in ast.walk(ast.parse(code)):
                if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call) or not node.exc.args:
                    continue
                value = node.exc.args[0]
                suffix = isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add)
                while isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
                    value = value.left
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    templates.append((node.lineno, value.value, suffix))
        else:
            for found in re.finditer(r'throw new [A-Za-z.]+\("((?:[^"\\]|\\.)*)"\s*(\+|\))', code):
                templates.append((code.count("\n", 0, found.start()) + 1, json.loads('"' + found.group(1) + '"'), found.group(2) == "+"))
        for line, literal, suffix in templates:
            if len(literal) >= 8 and any(value.startswith(literal) if suffix else value == literal for value in normalized):
                matches.append({"source": source, "line": line, "public_message": literal, "dynamic_suffix_omitted": suffix})
        for found in re.finditer(r'File "[^"\n]*' + re.escape(source) + r'", line ([0-9]+)', message):
            frames.append({"source": source, "line": int(found.group(1))})
    result = {"exception_classes": exceptions, "public_templates": matches[:8], "public_traceback_frames": frames[-8:]}
    # Python's OSError string contains private filenames after the standard
    # errno/strerror prefix. Classify only exact known prefixes, never the suffix.
    for prefix, label in (
        ("[Errno 2] No such file or directory", "missing-file"),
        ("[Errno 5] Input/output error", "io-error"),
        ("[Errno 8] Exec format error", "exec-format"),
        ("[Errno 12] Cannot allocate memory", "out-of-memory"),
        ("[Errno 13] Permission denied", "permission-denied"),
        ("[Errno 17] File exists", "file-exists"),
        ("[Errno 20] Not a directory", "not-directory"),
        ("[Errno 21] Is a directory", "is-directory"),
        ("[Errno 28] No space left on device", "no-space"),
        ("[Errno 30] Read-only file system", "read-only-filesystem"),
    ):
        if any(value == prefix or value.startswith(prefix + ":") for value in normalized):
            result["os_error"] = label
            break
    producer = re.fullmatch(r"Source producer exited with code (-?[0-9]{1,3}); private producer log retained\.", message)
    if producer:
        result["producer_exit"] = int(producer.group(1))
    child = re.match(r"(?:java\.io\.IOException: )?owner-backend exit (-?[0-9]+) ", message)
    if child:
        result["owner_backend_exit"] = int(child.group(1))
    return result


def inspect_check_timeout(source, *, conflicting_mode=False):
    """Read only one source-matching retained run, not a live device or app."""
    result = {"mode": "inspect-check-timeout", "status": "observed", "binding": "unique-retained-source-not-run-id", "errors": []}
    try:
        if conflicting_mode:
            raise Failure("log-inspection-cannot-run-other-modes")
        if not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{40}", source):
            raise Failure("log-inspection-source-required")
        parent = ROOT / "work/coordination/installer-update-acceptance"

        def read(path, limit=4 * 1024**2):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
                raise Failure("log-inspection-record-unavailable")
            return path.read_bytes()

        candidates = []
        for directory in sorted(parent.iterdir()):
            if not re.fullmatch(r"run-[a-z0-9_]{8}", directory.name) or directory.is_symlink() or not directory.is_dir():
                continue
            records = list(directory.glob("[0-9][0-9][0-9][0-9][0-9]-resolve-source-commit.json"))
            if len(records) != 1:
                continue
            metadata = json.loads(read(records[0], 16384))
            if metadata != {"phase": "setup", "category": "resolve-source-commit", "returncode": 0, "outcome": "returned"}:
                continue
            if read(records[0].with_suffix(".stdout.log"), 128).strip() == source.encode():
                candidates.append(directory)
        result["source_candidates"] = len(candidates)
        if len(candidates) != 1:
            raise Failure("log-inspection-source-candidate-not-unique")
        directory = candidates[0]
        states = {name: 0 for name in ("TEST_WAIT", "CHECKING", "UPDATE_AVAILABLE", "UP_TO_DATE", "ERROR", "CANCELLED", "null", "unknown", "read-unavailable")}
        transitions, previous, reads = [], None, 0
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-state-read.json")):
            metadata = json.loads(read(path, 16384))
            if metadata.get("phase") != "baseline-N-check":
                continue
            if metadata.get("category") != "device-state-read":
                raise Failure("log-inspection-record-mismatch")
            reads += 1
            if metadata.get("returncode") != 0 or metadata.get("outcome") != "returned":
                state = "read-unavailable"
            else:
                value = json.loads(read(path.with_suffix(".stdout.log")))
                state = "null" if value is None else value.get("state") if isinstance(value, dict) else None
                if not isinstance(state, str) or state not in states or state in ("unknown", "read-unavailable"):
                    state = "unknown"
            states[state] += 1
            if state != previous and len(transitions) < 16:
                transitions.append(state)
            previous = state
        if not reads:
            raise Failure("log-inspection-check-state-not-found")
        result.update(
            state_reads=reads, state_counts={name: count for name, count in states.items() if count}, first_transitions=transitions, last_state=previous
        )
        # The last retained successful UI read is not a new screenshot, proof of
        # tap delivery, or proof that the Activity entered its check handler.
        control = {"status": "unavailable"}
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-ui-read.json"), reverse=True):
            metadata = json.loads(read(path, 16384))
            if metadata.get("phase") != "baseline-N-check":
                continue
            if metadata.get("category") != "device-ui-read":
                raise Failure("log-inspection-record-mismatch")
            if metadata.get("returncode") != 0 or metadata.get("outcome") != "returned":
                continue
            raw = read(path.with_suffix(".stdout.log"))
            try:
                tree = ET.fromstring(raw)
                kind = "focused-window" if tree.tag == "displays" else "hierarchy"
                tree = focused_ui_hierarchy(tree, (PACKAGE,)) if tree.tag == "displays" else tree
                if tree.tag != "hierarchy":
                    raise Failure("ui-window-schema")
                Phone.prompt_nodes(tree, (PACKAGE,))
                nodes = [node for node in tree.iter("node") if node.get("text", "").casefold() == "check for updates"]

                def valid_bounds(node):
                    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
                    return bool(match and int(match[3]) > int(match[1]) and int(match[4]) > int(match[2]))

                control = {
                    "status": "owned-root",
                    "kind": kind,
                    "count": len(nodes),
                    "enabled_count": sum(node.get("enabled") == "true" for node in nodes),
                    "clickable_count": sum(node.get("clickable") == "true" for node in nodes),
                    "bounds_valid_count": sum(valid_bounds(node) for node in nodes),
                }
            except (Failure, ET.ParseError):
                control = {"status": "unclassified"}
            break
        result["last_retained_check_control"] = control
    except Exception as error:
        result["status"] = "error"
        result["errors"].append(str(error) if isinstance(error, Failure) else "log-inspection-local-read-error")
    print(encoded(result).decode(), end="", flush=True)
    return 1 if result["errors"] else 0


def inspect_ui_failure(selection, *, conflicting_mode=False, update_failure=False):
    result = {
        "mode": "inspect-update-failure" if update_failure else "inspect-ui-failure",
        "status": "observed",
        "selection": "newest" if selection == "newest" else "explicit",
        "records": [],
        "errors": [],
    }
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

        if update_failure:
            for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-state-read.json")):
                metadata = json.loads(read(path.name))
                if metadata.get("phase") not in ("baseline-N-check", "baseline-N-install") or metadata.get("category") != "device-state-read":
                    continue
                if metadata.get("returncode") != 0 or metadata.get("outcome") != "returned":
                    continue
                state = json.loads(read(path.stem + ".stdout.log"))
                if isinstance(state, dict) and state.get("state") == "ERROR":
                    message = state.get("message")
                    if not isinstance(message, str):
                        raise Failure("log-inspection-update-error-shape")
                    result["phase"] = metadata["phase"]
                    result["backend_error"] = backend_error_summary(message)
                    pipeline = state.get("pipeline")
                    first = pipeline.get("first_failure") if isinstance(pipeline, dict) else None
                    if isinstance(first, dict):
                        stage, reason = first.get("stage"), first.get("reason")
                        result["pipeline_first_failure"] = {
                            "stage": stage if stage in ("admission", "staging", "assembly", "textures", "native", "apk", "signing", "install") else "unknown",
                            "reason": backend_error_summary(reason) if isinstance(reason, str) else {"status": "unavailable"},
                        }
                    result["apk_logs"] = []
                    for log_path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-apk-*-log.json")):
                        match = re.fullmatch(r"([0-9]{5})-device-apk-(javac|dex)-log\.json", log_path.name)
                        if not match or not int(path.name[:5]) < int(match.group(1)) <= int(path.name[:5]) + 4:
                            continue
                        log_meta = json.loads(read(log_path.name))
                        if log_meta.get("phase") != metadata["phase"] or log_meta.get("category") != "device-apk-" + match.group(2) + "-log":
                            raise Failure("log-inspection-record-mismatch")
                        entry = {"tool": match.group(2), "status": "unavailable"}
                        if log_meta.get("returncode") == 0 and log_meta.get("outcome") == "returned":
                            output = read(log_path.stem + ".stdout.log").decode(errors="replace")
                            entry["status"] = "captured" if output.startswith("ROR2_APK_LOG_BEGIN\n") else "not-found"
                            if entry["status"] == "captured":
                                entry["error"] = toolhost_error_summary(output)
                                entry["backend_error"] = backend_error_summary(output)
                        result["apk_logs"].append(entry)
                    break
            else:
                raise Failure("log-inspection-update-error-not-found")
            print(encoded(result).decode(), end="", flush=True)
            return 0

        failure_sequence = None
        dump_category = "device-ui-dump"
        selected_records = None
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-ui-*.json")):
            match = re.fullmatch(r"([0-9]{5})-(device-ui-(?:dump|windows-dump|read))\.json", path.name)
            if not match:
                continue
            metadata = json.loads(read(path.name))
            if metadata.get("phase") != "baseline-N-check":
                continue
            sequence, category = int(match.group(1)), match.group(2)
            if metadata.get("category") != category:
                raise Failure("log-inspection-record-mismatch")
            if metadata.get("returncode") != 0 or metadata.get("outcome") != "returned":
                selected_records = [(sequence, category)]
                if category == "device-ui-read":
                    for previous in ("device-ui-dump", "device-ui-windows-dump"):
                        if (directory / f"{sequence - 1:05d}-{previous}.json").is_file():
                            dump_category = previous
                            selected_records.insert(0, (sequence - 1, previous))
                            break
                break
        if selected_records is None:
            # A windows dump may read successfully yet be rejected by the
            # focused-root/package guard. Inspect its retained XML, never retry
            # the phone or relax the tap-target whitelist to diagnose it.
            for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-ui-windows-dump.json")):
                metadata = json.loads(read(path.name))
                if metadata.get("phase") == "baseline-N-check" and metadata.get("category") == "device-ui-windows-dump":
                    sequence = int(path.name[:5])
                    # Successful fallbacks can precede the failure. Require the
                    # rejection-only diagnostic after this read and dump removal.
                    marker = f"{sequence + 3:05d}-device-ui-diagnostic-power.json"
                    if not (directory / marker).is_file():
                        continue
                    diagnostic = json.loads(read(marker))
                    if diagnostic.get("phase") != "baseline-N-check" or diagnostic.get("category") != "device-ui-diagnostic-power":
                        raise Failure("log-inspection-record-mismatch")
                    failure_sequence = sequence + 1
                    dump_category = "device-ui-windows-dump"
                    break
            if failure_sequence is not None:
                selected_records = [(failure_sequence - 1, dump_category), (failure_sequence, "device-ui-read")]
        if selected_records is None:
            raise Failure("log-inspection-ui-read-failure-not-found")
        for sequence, category in selected_records:
            prefix = f"{sequence:05d}-{category}"
            metadata = json.loads(read(prefix + ".json"))
            if metadata.get("phase") != "baseline-N-check" or metadata.get("category") != category:
                raise Failure("log-inspection-record-mismatch")
            outcome = metadata.get("outcome")
            returncode = metadata.get("returncode")
            termination = "unavailable"
            if type(returncode) is int:
                # subprocess uses negative POSIX signal numbers for the local
                # child. Do not infer a signal from a remote shell exit (128+N).
                termination = "exit-zero" if returncode == 0 else "exit-nonzero"
                if returncode < 0:
                    termination = {
                        -1: "signal-SIGHUP",
                        -2: "signal-SIGINT",
                        -6: "signal-SIGABRT",
                        -9: "signal-SIGKILL",
                        -11: "signal-SIGSEGV",
                        -15: "signal-SIGTERM",
                    }.get(returncode, "signal-other")
            result["records"].append(
                {
                    "phase": "baseline-N-check",
                    "category": category,
                    "returncode": "zero" if metadata.get("returncode") == 0 else "nonzero" if type(metadata.get("returncode")) is int else "unavailable",
                    "termination": termination,
                    "outcome": outcome if outcome in ("returned", "OSError", "TimeoutExpired") else "unknown",
                    "stdout": ui_output_classification(read(prefix + ".stdout.log")),
                    "stderr": ui_output_classification(read(prefix + ".stderr.log")),
                }
            )
            if dump_category == "device-ui-windows-dump" and category == "device-ui-read":
                result["foreground"] = (
                    ui_window_summary(read(prefix + ".stdout.log"))
                    if metadata.get("returncode") == 0 and outcome == "returned"
                    else {"status": "unknown", "reason": "ui-window-read-unavailable"}
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


def toolhost_error_summary(text):
    """First recognized error only; never return a log excerpt or unknown name."""
    java_files = (
        "PayloadStore.java",
        "PayloadBootstrapActivity.java",
        "ProfileStore.java",
        "ProfileRetentionProvider.java",
        "ToolHostActivity.java",
        "OwnerUpdateState.java",
        "OwnerInstaller.java",
        "OwnerAlphaInstall.java",
        "OwnerBuildService.java",
        "OwnerInputImport.java",
        "OwnerInputSource.java",
    )
    fallback = {"category": "unclassified"}
    for line in text.splitlines():
        java = re.search(r"(?:^|[/\\])(" + "|".join(map(re.escape, java_files)) + r"):(\d+): error: (.*)$", line)
        value = (java.group(3) if java else line).lower()
        for marker, category in (
            ("cannot find symbol", "java-symbol-not-found"),
            ("incompatible types", "java-incompatible-types"),
            ("already defined", "java-duplicate-definition"),
            ("does not override", "java-override-error"),
            ("does not exist", "dependency-missing"),
            ("no space left on device", "storage-exhausted"),
            ("permission denied", "permission-denied"),
            ("no such file or directory", "file-missing"),
            ("build input changed", "input-drift"),
            ("timed out", "timeout"),
            ("timeout after", "timeout"),
            ("fatal error:", "native-compiler-error"),
        ):
            if marker in value:
                return {"category": category, **({"source": java.group(1), "line": int(java.group(2))} if java else {})}
        if java:
            return {"category": "java-compiler-error", "source": java.group(1), "line": int(java.group(2))}
        if "traceback (most recent call last)" in value:
            fallback = {"category": "python-error"}
        stage = re.search(r"\b(native-build|javac|dex|aapt|owner-sign) exit -?[0-9]+\b", value)
        if stage:
            return {"category": "build-command-failed", "stage": stage.group(1)}
    return fallback


def inspect_toolhost_failure(source, run_id, *, conflicting_mode=False):
    result = {"mode": "inspect-toolhost-failure", "status": "observed", "errors": []}
    try:
        if conflicting_mode:
            raise Failure("toolhost-inspection-cannot-run-other-modes")
        if not re.fullmatch(r"[0-9a-f]{40}", source or "") or not re.fullmatch(r"[0-9]{1,20}", run_id or ""):
            raise Failure("toolhost-inspection-requires-source-and-run")
        configured = os.environ.get("LAB_TOOLHOST_ROOT")
        if not configured:
            raise Failure("LAB_TOOLHOST_ROOT-required")
        root = Path(configured).resolve(strict=True)
        build, run_directory = root / source, root.parent / run_id
        if build.is_symlink() or run_directory.is_symlink():
            raise Failure("toolhost-inspection-record-unavailable")

        def read(path):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024**2:
                raise Failure("toolhost-inspection-record-unavailable")
            return path.read_text(errors="replace")

        receipt = json.loads(read(build / "result.json"))
        if not isinstance(receipt, dict):
            raise Failure("toolhost-inspection-receipt-shape")
        if receipt.get("source_commit", source) != source or receipt.get("package", PACKAGE) != PACKAGE:
            raise Failure("toolhost-inspection-receipt-mismatch")
        result["build_success"] = receipt.get("success") if type(receipt.get("success")) is bool else None
        result["receipt_source_present"] = "source_commit" in receipt
        result["receipt_failure_present"] = any(isinstance(receipt.get(key), str) and receipt[key] for key in ("failure", "error"))
        result["receipt_failure"] = toolhost_error_summary("\n".join(receipt[key] for key in ("failure", "error") if isinstance(receipt.get(key), str)))
        # Public lab_runner.py writes this exact job log. It records --source
        # on the local builder command; no arbitrary receipt paths are followed.
        log = read(run_directory / "output.log")
        sources = re.findall(r"(?:^|\s)--source\s+([0-9a-f]{40})(?=\s|$)", log)
        if not sources or set(sources) != {source}:
            raise Failure("toolhost-inspection-log-source-mismatch")
        result["log_error"] = toolhost_error_summary(log)
    except Exception as error:
        result["status"] = "error"
        result["errors"].append(str(error) if isinstance(error, Failure) else "toolhost-inspection-local-read-error")
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
        "--qualify-phone-flow",
        action="store_true",
        help="Synthetic visible-permission phone reconstruction/install/update with sampled stage metrics; stops after profile/settings verification",
    )
    parser.add_argument(
        "--qualify-install-prompts",
        action="store_true",
        help="Authorized synthetic workflow only: require ungranted Settings permission and matching pending-user-action consent; never pregrant",
    )
    parser.add_argument(
        "--allow-test-installs", action="store_true", help="Only after explicit owner authorization: allow installs for this fresh disposable test package"
    )
    parser.add_argument(
        "--allow-test-notifications", action="store_true", help="Only after explicit owner authorization: allow this owned test app's POST_NOTIFICATIONS prompt"
    )
    parser.add_argument("--inspect-state", action="store_true", help="Read-only fixed-package presence/hash and installer permission; no build, UI or cleanup")
    parser.add_argument(
        "--expected-installer-sha256", help="Required for --inspect-state: last known installer hash, used only for comparison, never ownership"
    )
    parser.add_argument(
        "--inspect-check-timeout",
        metavar="SOURCE_COMMIT",
        help="Read-only retained baseline-check state counts and fixed Check control flags; no device actions",
    )
    parser.add_argument("--inspect-ui-failure", action="store_true", help="Read-only fixed classification of this driver's retained UI dump/read failure logs")
    parser.add_argument(
        "--inspect-update-failure", action="store_true", help="Read-only public-source error matches from the retained first baseline check/install ERROR"
    )
    parser.add_argument(
        "--inspect-toolhost-failure", metavar="SOURCE_COMMIT", help="Read-only fixed build-error classification for one exact toolhost source commit"
    )
    parser.add_argument(
        "--diagnostic-run", help="Inspection selection: UI newest/private run basename, or toolhost numeric lab run ID; never prints paths or raw logs"
    )
    args = parser.parse_args(argv)
    qualify_prompts = args.qualify_install_prompts or args.qualify_phone_flow
    if qualify_prompts and (
        args.allow_test_installs
        or args.host_only
        or args.inspect_state
        or args.inspect_ui_failure
        or args.inspect_update_failure
        or args.inspect_toolhost_failure is not None
        or args.inspect_check_timeout is not None
        or args.qualify_phone_flow
        and args.allow_test_notifications
    ):
        print("FAIL install-prompt-mode-conflict", flush=True)
        return 1
    if args.inspect_check_timeout is not None:
        DIAGNOSTICS = None
        return inspect_check_timeout(
            args.inspect_check_timeout,
            conflicting_mode=args.inspect_ui_failure
            or args.inspect_update_failure
            or args.inspect_toolhost_failure is not None
            or args.inspect_state
            or args.host_only
            or args.allow_test_installs
            or args.allow_test_notifications
            or args.diagnostic_run is not None
            or args.expected_installer_sha256 is not None,
        )
    if args.inspect_toolhost_failure is not None:
        DIAGNOSTICS = None
        return inspect_toolhost_failure(
            args.inspect_toolhost_failure,
            args.diagnostic_run,
            conflicting_mode=args.inspect_ui_failure
            or args.inspect_update_failure
            or args.inspect_state
            or args.host_only
            or args.allow_test_installs
            or args.allow_test_notifications,
        )
    if args.inspect_update_failure:
        DIAGNOSTICS = None
        return inspect_ui_failure(
            args.diagnostic_run,
            conflicting_mode=args.inspect_ui_failure or args.inspect_state or args.host_only or args.allow_test_installs or args.allow_test_notifications,
            update_failure=True,
        )
    if args.inspect_ui_failure:
        DIAGNOSTICS = None
        return inspect_ui_failure(
            args.diagnostic_run, conflicting_mode=args.inspect_state or args.host_only or args.allow_test_installs or args.allow_test_notifications
        )
    if args.inspect_state:
        # This driver-only observation makes no claim about APK source identity.
        # Bypass cache/toolchain setup, private log writes and all cleanup paths.
        DIAGNOSTICS = None
        return inspect_state(
            args.expected_installer_sha256, args.timeout, conflicting_mode=args.host_only or args.allow_test_installs or args.allow_test_notifications
        )
    completed = set()
    phone = None
    reason = None
    failure_phase = "setup"
    cleanup_reason = None
    cleanup_verified = False
    metrics = None

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
            phone = Phone(serial, args.timeout, args.allow_test_installs, args.allow_test_notifications)
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
                if args.qualify_phone_flow:
                    acceptance(phone, config, temporary, passed, qualify_install_prompts=True, phone_flow=True)
                elif qualify_prompts:
                    acceptance(phone, config, temporary, passed, qualify_install_prompts=True)
                else:
                    acceptance(phone, config, temporary, passed)
    except Failure as error:
        reason = str(error)
        failure_phase = CURRENT_PHASE
    except Exception:
        reason = "unexpected-local-error-see-private-lab-environment"
        failure_phase = CURRENT_PHASE
    finally:
        try:
            if phone is not None and reason and failure_phase in ("baseline-N-check", "check-for-updates"):
                try:
                    observed = phone.capture_check_diagnostic()
                except Exception:
                    observed = {"status": "unavailable", "reason": "capture-failed"}
                print(encoded({"mode": "release-check-diagnostic", "observed": observed}).decode(), end="", flush=True)
            if phone is not None and reason and failure_phase in ("baseline-N-install", "update-N-to-N+1", "same-key-rollback"):
                try:
                    observed = phone.capture_install_diagnostic()
                except Exception:
                    observed = {"status": "unavailable", "reason": "capture-failed"}
                print(encoded({"mode": "install-diagnostic", "observed": observed}).decode(), end="", flush=True)
        except Exception:
            # Optional diagnostics, including output, cannot replace the install failure.
            pass
        finally:
            if phone is not None:
                if args.qualify_phone_flow:
                    metrics, phone.flow_metrics = phone.flow_metrics, None
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
            cases = (*PROMPT_CASES, *CASES[:2], "synthetic-phone-flow") if args.qualify_phone_flow else (*PROMPT_CASES, *CASES) if qualify_prompts else CASES
            for case in cases:
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
    if metrics is not None:
        try:
            print(encoded(metrics.report()).decode(), end="", flush=True)
        except Exception:
            print('{"mode":"synthetic-phone-flow-metrics","status":"unavailable"}', flush=True)
    return 1 if reason or cleanup_reason else 0


if __name__ == "__main__":
    sys.exit(main())
