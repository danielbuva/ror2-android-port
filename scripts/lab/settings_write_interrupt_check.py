"""Current: observe a genuine pending-file transaction, terminate its owned writer, cold-recover.

No injected store bytes, player hooks, power-cut or ENOSPC claim. Refuse a missed
pre-commit window. The native store performs both ordinary saves and recovery.
"""

import json
import re
import time
import uuid

from common import ROOT, WORK, now, sha, write
from device import Device, PACKAGE
from nova_bridge import current_errors
from installed_attempt import attempt_from_installed, bind_installed_apk, validate_expected_apk_sha256
from session_cleanup_check import SPINE_ID, _read_json, _read_raw, _remote_path_state, matches_run, selection, selector_action
from touch_gesture import run as gesture


def interrupted_transaction(before, after, pending, observed):
    """Accept an actual create/stop witness only while the old primary survives."""
    if (
        not isinstance(observed, dict)
        or observed.get("success") is not True
        or observed.get("createObserved") is not True
        or observed.get("writerExited") is not True
        or observed.get("pendingPresentBeforeStop") is not True
        or observed.get("pendingPresentAfterStop") is not True
    ):
        raise RuntimeError("No successful native pending-create/stop witness")
    if not before or after != before or not pending or pending.get("state") != "file":
        raise RuntimeError("Missed pre-commit window; do not claim interrupted-write recovery")


def validate_observer_binding(observed, nonce, pid, uid):
    if (
        not isinstance(observed, dict)
        or observed.get("nonce") != nonce
        or observed.get("pid") != int(pid)
        or observed.get("uid") != uid
        or type(observed.get("observerPid")) is not int
        or observed["observerPid"] <= 0
        or observed["observerPid"] == int(pid)
    ):
        raise RuntimeError("Separate-process observer binding differs")


def stop_after_observed_exit(device, observed, expected):
    """Keep the witnessed writer distinct from an Android activity restart."""
    if observed.get("success") is not True or observed.get("writerExited") is not True:
        raise RuntimeError("No successful native writer-exit witness")
    if _remote_path_state(device, "/proc/" + str(observed["pid"])) != "absent":
        raise RuntimeError("Witnessed writer PID remains present")
    processes = device.sh("pidof", PACKAGE, check=False).strip()
    bind_installed_apk(device.owned(), expected_sha256=expected)
    device.sh("am", "force-stop", PACKAGE)
    deadline = time.monotonic() + 10
    while device.sh("pidof", PACKAGE, check=False).strip():
        if time.monotonic() >= deadline:
            raise RuntimeError("Owned package remained after force-stop")
        time.sleep(0.1)
    return dict(writer_pid=observed["pid"], writer_absent=True, package_pids_before_stop=processes)


def check_settings_write_interrupt(expected_apk_sha256=None, _launch=None):
    expected = validate_expected_apk_sha256(expected_apk_sha256)
    if expected is None:
        raise ValueError("settings-write-interrupt-check requires --expected-apk-sha256")
    device = Device()
    installed = device.owned()
    bind_installed_apk(installed, expected_sha256=expected)
    attempt = attempt_from_installed(installed)
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    directory = runtime + "/offline-settings-v1"
    primary, pending = directory + "/preferences.json", directory + "/preferences.json.pending"
    selector = runtime + "/movement-batch-selection.json"
    if _remote_path_state(device, selector) != "absent" or device.sh("pidof", PACKAGE, check=False).strip():
        raise RuntimeError("Requires idle owned package and no diagnostic selector")
    if _remote_path_state(device, primary) != "file" or _remote_path_state(device, pending) != "absent":
        raise RuntimeError("Preserve existing missing-primary or pending store state")
    out = device.evidence_directory("experiments", "settings-write-interruption", now())
    out.mkdir(parents=True, exist_ok=False)
    result = dict(
        success=False,
        apk_sha256=expected,
        attempt=attempt,
        scope="Observed native pending transaction interrupted by same-UID writer termination; no power-cut/ENOSPC claim",
    )
    pid = None
    last_report = None
    remote = []

    def wait(check, timeout=100):
        nonlocal last_report
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            report = _read_json(device, runtime + "/movement-batch-" + SPINE_ID + ".json")
            if matches_run(report, pid, attempt):
                last_report = report
                if report.get("firstFailure"):
                    raise RuntimeError("Native first failure: " + str(report["firstFailure"]))
                if check(report):
                    return report
            if device.sh("pidof", PACKAGE, check=False).strip() != pid:
                raise RuntimeError("Owned process exited before expected transition")
            time.sleep(0.5)
        raise RuntimeError("Current native report deadline")

    def menu():
        nonlocal pid, last_report
        last_report = None
        pid = (_launch(device) if _launch else device.launch())["pid"]
        return wait(lambda r: r.get("phase") == "offline-start-menu" and r.get("settings", {}).get("ready") is True)

    def tap(name, report, x, y):
        request = out / (name + ".json")
        write(
            request,
            dict(
                pid=pid,
                width=report["settings"]["screenWidth"],
                height=report["settings"]["screenHeight"],
                steps=[dict(action="down", id=0, x=x, y=y), dict(action="wait", ms=100), dict(action="up", id=0, x=x, y=y), dict(action="wait", ms=400)],
            ),
        )
        return gesture(request, expected)

    def capture_owned_errors(name):
        logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "epoch", "Unity:I", "AndroidRuntime:E", "*:S")
        (out / (name + ".log")).write_text(logs)
        errors = current_errors(logs, pid)
        result.setdefault("runtime_errors", []).extend(errors)
        return errors

    def protected_hashes():
        roots = [runtime + "/" + name for name in ("android-profile-v1", "offline-run-results-v1")]
        value = device.sh("find", *roots, "-type", "f", "-exec", "sha256sum", "{}", "+", check=False)
        return {line[66:]: line[:64] for line in value.splitlines() if re.fullmatch(r"[0-9a-f]{64}  .+", line)}

    try:
        selected = selection(attempt)
        selected["debugOptions"]["purpose"] = result["scope"]
        write(out / "selection.json", selected)
        device.cmd("push", str(out / "selection.json"), selector)
        before_profile = protected_hashes()
        before_raw = _read_raw(device, primary)
        before = json.loads(before_raw.lstrip("\ufeff"))
        before_file = out / "before-primary.private"
        device.cmd("pull", primary, str(before_file))
        before_hash = device.sh("sha256sum", primary).split()[0]
        if sha(before_file) != before_hash:
            raise RuntimeError("Initial primary evidence transfer hash differs")
        result["primary_before"] = dict(sha256=before_hash, bytes=before_file.stat().st_size)
        nonce = uuid.uuid4().hex
        prefix = runtime + "/ror2lab-write-" + nonce
        request = runtime + "/settings-write-observer.request"
        remote = [request, prefix + ".ready", prefix + ".result", prefix + ".ready.tmp", prefix + ".result.tmp"]
        if any(_remote_path_state(device, path) != "absent" for path in remote):
            remote = []
            raise RuntimeError("Observer request/evidence already exists; preserve it")
        write(out / "observer-request.json", dict(nonce=nonce))
        (out / "observer.request").write_text(nonce)
        device.cmd("push", str(out / "observer.request"), request)
        report = menu()
        tap("settings-open", report, report["settings"]["buttonX"], report["settings"]["buttonY"])
        report = wait(lambda r: r["settings"]["visible"] is True)
        width, height = report["settings"]["screenWidth"], report["settings"]["screenHeight"]
        original_invert = report["settings"]["invertY"]
        # Saving unchanged values still performs the real pending/replace transaction.
        # A retained newly-created pending file distinguishes interruption from commit.
        write(out / "native-settings-before-save.json", report)
        packages = device.sh("cmd", "package", "list", "packages", "-U", PACKAGE)
        matches = re.findall(r"^package:" + re.escape(PACKAGE) + r" uid:([0-9]+)$", packages, re.M)
        if len(matches) != 1 or int(matches[0]) < 10000:
            raise RuntimeError("Owned package UID is ambiguous")
        uid = int(matches[0])
        deadline = time.monotonic() + 10
        while _remote_path_state(device, prefix + ".ready") != "file":
            if time.monotonic() >= deadline:
                raise RuntimeError("Separate-process observer did not arm")
            time.sleep(0.1)
        ready = _read_json(device, prefix + ".ready")
        validate_observer_binding(ready, nonce, pid, uid)
        service_pid = device.sh("pidof", PACKAGE + ":settings_write_observer", check=False).strip()
        if service_pid != str(ready["observerPid"]):
            raise RuntimeError("Ready witness does not match the separate service PID")
        write(out / "observer-binding.json", dict(apk_sha256=expected, **ready))
        # Consume request before cold launch so recovery cannot re-arm it.
        device.sh("rm", request)
        try:
            result["save_gesture"] = tap("native-save-and-interrupt", report, width * 0.5 - 110, height * 0.5 + 48)
        except Exception as error:
            result["save_gesture"] = dict(success=False, error=str(error))
        deadline = time.monotonic() + 40
        while _remote_path_state(device, prefix + ".result") != "file":
            if time.monotonic() >= deadline:
                raise RuntimeError("Separate-process observer result deadline")
            time.sleep(0.1)
        observed = _read_json(device, prefix + ".result")
        validate_observer_binding(observed, nonce, pid, uid)
        if observed["observerPid"] != ready["observerPid"]:
            raise RuntimeError("Observer process changed after arming")
        write(out / "observer-result.json", observed)
        result["interruption_observer"] = observed
        stopped_pid = pid
        if capture_owned_errors("interrupted-process"):
            raise RuntimeError("Actual-PID runtime error during native persistence case")
        result["writer_exit"] = stop_after_observed_exit(device, observed, expected)
        write(out / "writer-exit.json", result["writer_exit"])
        after_raw = _read_raw(device, primary)
        if device.sh("sha256sum", primary).split()[0] != before_hash:
            raise RuntimeError("Interrupted transaction changed the original primary bytes")
        state = _remote_path_state(device, pending)
        interrupted_transaction(before_raw, after_raw, dict(state=state), observed)
        result["interruption"] = observed
        result["persistence_captures"] = {}
        for source, name in ((pending, "interrupted-pending.private"), (primary, "unchanged-primary.private")):
            device.cmd("pull", source, str(out / name))
            actual = device.sh("sha256sum", source).split()[0]
            if sha(out / name) != actual:
                raise RuntimeError("Persistence evidence transfer hash differs")
            result["persistence_captures"][name] = dict(sha256=actual, bytes=(out / name).stat().st_size)
        report = menu()
        if pid == stopped_pid or report["settings"]["recovery"] != "validated-primary" or report["settings"]["invertY"] != original_invert:
            raise RuntimeError("Cold recovery did not retain validated primary settings")
        if _read_raw(device, primary) != before_raw or json.loads(_read_raw(device, primary).lstrip("\ufeff")) != before:
            raise RuntimeError("Cold recovery changed the prior primary")
        write(out / "cold-recovery.json", report)
        # Let the original store supersede its own stale pending transaction.
        tap("recovered-settings-open", report, report["settings"]["buttonX"], report["settings"]["buttonY"])
        report = wait(lambda r: r["settings"]["visible"] is True)
        tap("native-resave", report, width * 0.5 - 110, height * 0.5 + 48)
        report = wait(lambda r: r["settings"]["persisted"] is True and r["settings"]["visible"] is False)
        if _remote_path_state(device, pending) != "absent" or json.loads(_read_raw(device, primary).lstrip("\ufeff")) != before:
            raise RuntimeError("Native resave failed to supersede the interrupted pending transaction")
        after_profile = protected_hashes()
        if not before_profile or after_profile != before_profile:
            raise RuntimeError("Existing native profile/results changed")
        if capture_owned_errors("recovered-process"):
            raise RuntimeError("Actual-PID runtime error during native persistence case")
        result.update(success=True, protected_files=len(before_profile), recovered_pid=pid, interrupted_pid=stopped_pid)
        write(out / "native-resave.json", report)
    except Exception as error:
        result["error"] = str(error)
        if pid:
            # Capture before teardown even if the first menu transition failed.
            # A transport failure must not hide either the original exception or
            # runtime evidence collected through the other channel.
            try:
                report = _read_json(device, runtime + "/movement-batch-" + SPINE_ID + ".json")
                if matches_run(report, pid, attempt):
                    last_report = report
            except Exception as capture_error:
                result.setdefault("capture_errors", []).append(str(capture_error))
            try:
                if last_report is not None:
                    write(out / "failure-current-report.json", last_report)
            except Exception as capture_error:
                result.setdefault("capture_errors", []).append(str(capture_error))
            try:
                capture_owned_errors("failure-process")
            except Exception as capture_error:
                result.setdefault("capture_errors", []).append(str(capture_error))
            failure = last_report.get("firstFailure") if last_report is not None else None
            if failure or result.get("runtime_errors"):
                message = "Native first failure: " + str(failure) if failure else "Actual-PID runtime error during native persistence case"
                result["original_error"] = str(error)
                result["error"] = message
                raise RuntimeError(message) from error
        raise
    finally:
        errors = []
        try:
            state = _remote_path_state(device, selector)
            action = selector_action(state, _read_raw(device, selector) if state == "file" else "", attempt)
            if action == "remove-owned":
                device.sh("rm", selector)
                if _remote_path_state(device, selector) != "absent":
                    errors.append("Owned selector remains")
            elif action != "none":
                errors.append("Selector ownership changed; preserved it")
        except Exception as error:
            errors.append(str(error))
        try:
            if pid:
                bind_installed_apk(device.owned(), expected_sha256=expected)
                device.sh("am", "force-stop", PACKAGE)
            if device.sh("pidof", PACKAGE, check=False).strip() or device.sh("pidof", PACKAGE + ":settings_write_observer", check=False).strip():
                errors.append("Owned package still running")
            if not device.display(False):
                errors.append("OLED sleep not verified")
        except Exception as error:
            errors.append(str(error))
        for path in remote:
            try:
                device.sh("rm", "-f", path)
                if _remote_path_state(device, path) != "absent":
                    errors.append("Observer temporary target remains")
            except Exception as error:
                errors.append(str(error))
        result["cleanup_errors"] = errors
        result["success"] = result["success"] and not errors
        write(out / "result.json", result)
        if errors:
            raise RuntimeError("Interruption-case teardown failed; inspect private evidence")
    return dict(result, evidence=str(out.relative_to(WORK.parent)))
