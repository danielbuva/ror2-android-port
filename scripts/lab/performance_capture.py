"""Capture a bounded CPU call graph from an already-running owned lab process.

This module never launches, installs, or synchronizes the application. It is
intended for a selected Device whose user has already started representative
gameplay and whose foreground package is the owned lab application.
"""

import json
import re
import shlex
import subprocess
import traceback
import uuid

from common import now, write
from device import Device, PACKAGE


_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,47}\Z")
_SAFE_SELECTION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
_RUNTIME_PATH = re.compile(
    r"/(?:storage/(?:emulated/[0-9]+|[A-Za-z0-9-]+)|sdcard)/Android/data/"
    + re.escape(PACKAGE)
    + r"/files\Z"
)


class CaptureError(RuntimeError):
    """Capture refusal or failure with its persisted receipt attached."""

    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt


def _pid(device):
    values = device.sh("pidof", PACKAGE, check=False).split()
    if len(values) != 1 or not values[0].isdigit():
        raise RuntimeError("Owned lab package must have exactly one running PID")
    return values[0]


def _require_foreground(device):
    listing = device.sh("dumpsys", "activity", "activities")
    foreground = [
        line
        for line in listing.splitlines()
        if "mResumedActivity" in line or "topResumedActivity" in line
    ]
    if not foreground or not any(
        re.search(r"(?:^|\s)" + re.escape(PACKAGE) + r"(?:/|\s)", line)
        for line in foreground
    ):
        raise RuntimeError("Owned lab package is not confirmed as the resumed foreground activity")


def _runtime_path(device):
    # Device.read_receipt performs selected-serial and live storage-backing
    # validation; bypassing it could direct report reads at another volume.
    runtime = device.read_receipt("runtime.json")
    if runtime.get("serial") not in (None, device.serial):
        raise RuntimeError("Runtime receipt belongs to another selected device")
    path = runtime.get("persistentDataPath")
    if not isinstance(path, str) or not _RUNTIME_PATH.fullmatch(path):
        raise RuntimeError("Runtime receipt does not identify the owned lab package path")
    return path


def _session_context(device, runtime_path, pid):
    """Return only identity and performance metadata from the live runtime report."""
    context = {"available": False}
    selector_path = runtime_path + "/movement-batch-selection.json"
    try:
        selector = json.loads(device.sh("cat", selector_path, check=False))
    except (ValueError, TypeError):
        context["reason"] = "No readable active movement-batch selection"
        return context
    selection_id = selector.get("id") if isinstance(selector, dict) else None
    attempt = selector.get("attempt") if isinstance(selector, dict) else None
    if not isinstance(selection_id, str) or not _SAFE_SELECTION_ID.fullmatch(selection_id):
        context["reason"] = "Active selection has no safe report identifier"
        return context
    report_name = "movement-batch-" + selection_id + ".json"
    try:
        report = json.loads(device.sh("cat", runtime_path + "/" + report_name, check=False))
    except (ValueError, TypeError):
        context["reason"] = "No readable live movement-batch report"
        return context
    if not isinstance(report, dict) or str(report.get("pid")) != pid:
        context["reason"] = "Live report PID does not match the owned process"
        return context
    if attempt is not None and report.get("attempt") != attempt:
        context["reason"] = "Live report attempt does not match the active selection"
        return context

    stage = report.get("stage") if isinstance(report.get("stage"), dict) else {}
    world = report.get("world") if isinstance(report.get("world"), dict) else {}
    progress = report.get("stageProgress") if isinstance(report.get("stageProgress"), dict) else {}
    performance = report.get("performance") if isinstance(report.get("performance"), dict) else {}
    pacing = report.get("framePacing") if isinstance(report.get("framePacing"), dict) else {}
    samples = pacing.get("samples") if isinstance(pacing.get("samples"), list) else []
    latest = samples[-1] if samples and isinstance(samples[-1], dict) else {}
    report_id = report.get("id")
    report_attempt = report.get("attempt")
    session = report.get("session")
    if not isinstance(report_id, str) or not isinstance(report_attempt, str) or type(session) is not int:
        context["reason"] = "Live runtime report lacks attempt, id, or session identity"
        return context
    if attempt is not None and report_attempt != attempt:
        context["reason"] = "Live runtime report attempt does not match the active selection"
        return context
    if report_id != selection_id:
        context["reason"] = "Live runtime report id does not match the active selection"
        return context
    context.update(
        {
            "available": True,
            "selection_id": selection_id,
            "id": report_id,
            "attempt": report.get("attempt"),
            "pid": pid,
            "session": session,
            "phase": report.get("phase"),
            "stage": stage.get("scene"),
            "transitions": progress.get("transitions"),
            "world_seconds": world.get("seconds"),
            "framePacing": {
                key: pacing.get(key)
                for key in (
                    "frames", "meanMs", "maxMs", "over33ms", "over50ms",
                    "pauses", "resumeFramesSkipped", "backgroundSeconds",
                )
                if key in pacing
            },
            "latestSample": {
                key: latest.get(key)
                for key in (
                    "activeSeconds", "seconds", "frames", "scene", "meanMs", "maxMs",
                    "over33ms", "over50ms", "managedBytes", "allocatedBytes", "reservedBytes",
                    "gcCollections", "frameTimingSamples", "gpuTimingSamples", "mainTimingSamples",
                    "renderTimingSamples", "renderCounterSamples",
                    "sampledCpuMs", "sampledMainActiveMs", "sampledGpuMs", "sampledRenderActiveMs",
                    "sampledDrawCalls", "sampledSetPassCalls", "sampledVertices",
                    "sampledGcAllocBytes", "gcAllocSamples",
                )
                if key in latest
            },
            "performance": {
                key: performance.get(key)
                for key in (
                    "displayRefreshRate",
                    "requestedFrameRate",
                    "targetFrameRate",
                    "frames",
                    "observersMs",
                    "worldMs",
                    "saveMs",
                    "sampledAllocationFrames",
                )
                if key in performance
            },
        }
    )
    return context


def _cohort(installed, serial):
    if not isinstance(installed, dict):
        raise RuntimeError("Installed ownership receipt is invalid")
    if installed.get("serial") != serial or installed.get("package") != PACKAGE:
        raise RuntimeError("Installed ownership receipt does not match the selected lab package")
    apk_hash = installed.get("apk_sha256")
    if not isinstance(apk_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", apk_hash):
        raise RuntimeError("Installed ownership receipt lacks a valid APK hash")
    return {
        "serial": serial,
        "package": PACKAGE,
        "apk_sha256": apk_hash,
        "package_path": installed.get("package_path"),
        "build_key": installed.get("build_key"),
        "storage_mode": (installed.get("storage") or {}).get("mode"),
    }


def _identity(device):
    installed = device.owned()
    cohort = _cohort(installed, device.serial)
    return cohort, _pid(device)


def capture_cpu(device=None, *, duration_seconds=15, label="sample"):
    """Capture an existing foreground lab process and return its JSON receipt.

    The selected ``Device`` is frozen before any command. A successful raw
    profile is retained even when simpleperf cannot resolve symbols. Failures
    after the evidence directory is allocated produce ``failure.txt`` and a
    JSON receipt before ``CaptureError`` is raised.
    """
    if type(duration_seconds) is not int or not 1 <= duration_seconds <= 60:
        raise ValueError("CPU capture duration must be an integer from 1 through 60 seconds")
    if not isinstance(label, str) or not _LABEL.fullmatch(label) or ".." in label:
        raise ValueError("Capture label must be a short safe filename component")

    selected = device if device is not None else Device()
    serial = selected.serial
    attempt = "cpu-" + now() + "-" + uuid.uuid4().hex[:10] + "-" + label
    evidence_root = selected.evidence_directory("performance", attempt)
    evidence_root.mkdir(parents=True, exist_ok=False)
    profile_path = evidence_root / "simpleperf.data"
    record_output_path = evidence_root / "record-output.txt"
    report_path = evidence_root / "simpleperf-report.txt"
    receipt_path = evidence_root / "receipt.json"
    failure_path = evidence_root / "failure.txt"
    remote_profile = "/data/local/tmp/lab-performance-capture-" + uuid.uuid4().hex + ".data"
    profile_pulled = False
    record_started = False
    first_failure = None
    receipt = {
        "schema": 1,
        "success": False,
        "success_scope": "Nonempty raw profile from the stable owned process; report and runtime context are separately qualified",
        "selected_serial": serial,
        "package": PACKAGE,
        "label": label,
        "duration_seconds": duration_seconds,
        "attempt": attempt,
        "profile_path": str(profile_path.relative_to(selected.work_root)),
        "record_output_path": str(record_output_path.relative_to(selected.work_root)),
        "report_path": str(report_path.relative_to(selected.work_root)),
        "runtime_context_before": {"available": False},
        "runtime_context_after": {"available": False},
        "runtime_transition": {},
        "capture_mechanism": "adb shell system simpleperf record -g -p <PID>; report -g --sort comm,dso,symbol",
        "permission_note": (
            "The existing runner uses adb shell simpleperf with -p <PID>. Whether the selected Android build "
            "permits shell profiling of this app is device/build dependent; failures are preserved without "
            "falling back to --app, run-as, or another guessed privilege path."
        ),
    }
    operation = "ownership-check"

    try:
        cohort_before, pid_before = _identity(selected)
        receipt["cohort"] = cohort_before
        receipt["pid"] = pid_before
        operation = "foreground-check"
        _require_foreground(selected)
        operation = "runtime-context-before"
        runtime_path = _runtime_path(selected)
        context_before = _session_context(selected, runtime_path, pid_before)
        receipt["runtime_context_before"] = context_before

        operation = "simpleperf-availability"
        try:
            selected.cmd("shell", "command", "-v", "simpleperf", timeout=10)
        except Exception as exc:
            raise RuntimeError("Android system simpleperf is unavailable; no profiler was installed or guessed") from exc

        receipt["record_command"] = [
            "simpleperf", "record", "-g", "-p", pid_before,
            "--duration", str(duration_seconds), "-o", remote_profile,
        ]
        receipt["record_remote_profile"] = remote_profile
        record_script = shlex.join(receipt["record_command"]) + " 2>&1"
        receipt["record_command_script"] = record_script
        operation = "raw-profile-record"
        record_started = True
        record_output = selected.cmd("shell", record_script, timeout=duration_seconds + 30)
        record_output_path.write_text(record_output + ("\n" if record_output and not record_output.endswith("\n") else ""))
        operation = "raw-profile-pull"
        selected.cmd("pull", remote_profile, str(profile_path), timeout=60)
        if not profile_path.is_file() or profile_path.stat().st_size <= 0:
            raise RuntimeError("simpleperf pull completed without a non-empty local profile")
        profile_pulled = True

        operation = "symbol-report"
        try:
            rendered = selected.cmd(
                "shell", "simpleperf", "report", "-g", "-i", remote_profile,
                "--sort", "comm,dso,symbol", timeout=30,
            )
            report_path.write_text(rendered + ("\n" if rendered and not rendered.endswith("\n") else ""))
            receipt["report_generated"] = True
        except Exception as exc:
            receipt["report_generated"] = False
            receipt["report_error"] = str(exc)
            receipt["first_failure"] = {"phase": operation, "message": str(exc)}
            report_path.write_text("simpleperf report failed: " + str(exc) + "\n")

        operation = "identity-check-after"
        cohort_after, pid_after = _identity(selected)
        if pid_after != pid_before:
            receipt["post_capture_pid"] = pid_after
            receipt["identity_stable"] = False
            raise RuntimeError("Owned process PID changed during CPU capture")
        if cohort_after != cohort_before:
            receipt["identity_stable"] = False
            raise RuntimeError("Installed APK ownership/cohort changed during CPU capture")
        context_after = _session_context(selected, runtime_path, pid_after)
        receipt["runtime_context_after"] = context_after
        if context_before.get("available"):
            identity_keys = ("selection_id", "attempt", "id", "session", "pid")
            before_identity = tuple(context_before.get(key) for key in identity_keys)
            after_identity = tuple(context_after.get(key) for key in identity_keys)
            if not context_after.get("available") or before_identity != after_identity:
                receipt["identity_stable"] = False
                receipt["runtime_identity_error"] = "Runtime selection/session changed during CPU capture"
                raise RuntimeError(receipt["runtime_identity_error"])
        receipt["runtime_transition"] = {
            "phase_before": context_before.get("phase"),
            "phase_after": context_after.get("phase"),
            "stage_before": context_before.get("stage"),
            "stage_after": context_after.get("stage"),
            "session_before": context_before.get("session"),
            "session_after": context_after.get("session"),
            "world_seconds_before": context_before.get("world_seconds"),
            "world_seconds_after": context_after.get("world_seconds"),
            "transitions_before": context_before.get("transitions"),
            "transitions_after": context_after.get("transitions"),
        }
        operation = "foreground-check-after"
        _require_foreground(selected)
        receipt["pid"] = pid_before
        receipt["success"] = True
        receipt["identity_stable"] = True
    except Exception as exc:
        first_failure = exc
        receipt["error"] = str(exc)
        receipt.setdefault("first_failure", {"phase": operation, "message": str(exc)})
        if operation in ("raw-profile-record", "raw-profile-pull"):
            receipt["raw_profile_error"] = str(exc)
        if receipt.get("identity_stable") is not False:
            try:
                cohort_after, pid_after = _identity(selected)
                receipt["post_capture_pid"] = pid_after
                receipt["identity_stable"] = (
                    receipt.get("cohort") == cohort_after
                    and receipt.get("pid", pid_after) == pid_after
                )
                if receipt.get("pid") is None:
                    receipt["pid"] = pid_after
                if not receipt["identity_stable"]:
                    receipt["identity_error"] = "Owned package or PID changed during capture"
            except Exception as identity_error:
                receipt["identity_stable"] = False
                receipt["identity_error"] = str(identity_error)
        failure_path.write_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    finally:
        # Only remove the uniquely named remote output after it was pulled
        # completely. On a timeout or failed pull, preserve the remote first
        # failure material and never kill an in-flight profiler by guessing.
        if profile_pulled:
            try:
                selected.sh("rm", "-f", remote_profile)
                receipt["remote_profile_removed"] = True
            except Exception as cleanup_error:
                receipt["remote_profile_removed"] = False
                receipt["cleanup_error"] = str(cleanup_error)
        elif record_started:
            receipt["remote_profile_preserved"] = remote_profile
        write(receipt_path, receipt)

    if first_failure is not None:
        raise CaptureError(str(first_failure), receipt) from first_failure
    return receipt
