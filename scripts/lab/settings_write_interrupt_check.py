"""Current: observe a genuine pending-file transaction, stop its owned writer, cold-recover.

No injected store bytes, player hooks, power-cut or ENOSPC claim. Refuse a missed
pre-commit window. The native store performs both ordinary saves and recovery.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import re
import shlex
import time
import uuid

from common import ROOT, WORK, now, sha, write
from device import Device, PACKAGE
from nova_bridge import current_errors
from installed_attempt import attempt_from_installed, bind_installed_apk, validate_expected_apk_sha256
from session_cleanup_check import SPINE_ID, _read_json, _read_raw, _remote_path_state, matches_run, selection, selector_action
from touch_gesture import compile_tool, run as gesture


def interrupted_transaction(before, after, pending, observed):
    """Accept an actual create/stop witness only while the old primary survives."""
    if (
        not isinstance(observed, dict)
        or observed.get("success") is not True
        or observed.get("createObserved") is not True
        or observed.get("pendingPresentAfterStop") is not True
    ):
        raise RuntimeError("No successful native pending-create/stop witness")
    if not before or after != before or not pending or pending.get("state") != "file":
        raise RuntimeError("Missed pre-commit window; do not claim interrupted-write recovery")


def pending_observer(device, command):
    """Run the 30-second observer through the timeout-capable device transport."""
    return device.cmd("shell", command, timeout=40)


def check_settings_write_interrupt(expected_apk_sha256=None):
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
        scope="Observed native pending transaction interrupted by owned-package force-stop; no power-cut/ENOSPC claim",
    )
    pid = None
    remote = []

    def wait(check, timeout=100):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            report = _read_json(device, runtime + "/movement-batch-" + SPINE_ID + ".json")
            if matches_run(report, pid, attempt):
                if report.get("firstFailure"):
                    raise RuntimeError("Native first failure: " + str(report["firstFailure"]))
                if check(report):
                    return report
            if device.sh("pidof", PACKAGE, check=False).strip() != pid:
                raise RuntimeError("Owned process exited before expected transition")
            time.sleep(0.5)
        raise RuntimeError("Current native report deadline")

    def menu():
        nonlocal pid
        pid = device.launch()["pid"]
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
        if errors:
            raise RuntimeError("Actual-PID runtime error during native persistence case")

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
        report = menu()
        tap("settings-open", report, report["settings"]["buttonX"], report["settings"]["buttonY"])
        report = wait(lambda r: r["settings"]["visible"] is True)
        width, height = report["settings"]["screenWidth"], report["settings"]["screenHeight"]
        original_invert = report["settings"]["invertY"]
        # Saving unchanged values still performs the real pending/replace transaction.
        # A retained newly-created pending file distinguishes interruption from commit.
        write(out / "native-settings-before-save.json", report)
        dex = compile_tool(ROOT / "tools/android-write-interruption/LabPendingWriteStop.java")
        prefix = "/data/local/tmp/ror2lab-write-" + uuid.uuid4().hex
        targets = [prefix + ".dex", prefix + ".ready"]
        if any(_remote_path_state(device, path) != "absent" for path in targets):
            raise RuntimeError("Temporary observer target exists; preserve it")
        remote = targets
        packages = device.sh("cmd", "package", "list", "packages", "-U", PACKAGE)
        matches = re.findall(r"^package:" + re.escape(PACKAGE) + r" uid:([0-9]+)$", packages, re.M)
        if len(matches) != 1 or int(matches[0]) < 10000:
            raise RuntimeError("Owned package UID is ambiguous")
        write(
            out / "observer-binding.json",
            dict(
                apk_sha256=expected,
                pid=pid,
                uid=int(matches[0]),
                dex_sha256=sha(dex),
                source_sha256=sha(ROOT / "tools/android-write-interruption/LabPendingWriteStop.java"),
            ),
        )
        device.cmd("push", str(dex), remote[0])
        if device.sh("sha256sum", remote[0]).split()[0] != sha(dex):
            raise RuntimeError("Observer DEX transfer hash differs")
        command = shlex.join(["env", "CLASSPATH=" + remote[0], "app_process", "/system/bin", "LabPendingWriteStop", directory, remote[1], pid, matches[0]])
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(pending_observer, device, command)
            deadline = time.monotonic() + 10
            while _remote_path_state(device, remote[1]) != "file":
                if future.done():
                    future.result()
                    raise RuntimeError("Observer exited before arming")
                if time.monotonic() >= deadline:
                    raise RuntimeError("Observer did not arm")
                time.sleep(0.1)
            try:
                result["save_gesture"] = tap("native-save-and-interrupt", report, width * 0.5 - 110, height * 0.5 + 48)
            except Exception as error:
                # The observed stop can invalidate the scoped gesture actor before
                # its final UP/wait completes. Only the independent CREATE/stop
                # witness and retained pending file below can qualify this case.
                result["save_gesture"] = dict(success=False, error=str(error))
            raw = future.result(timeout=40)
            (out / "observer.stdout").write_text(raw)
            observed = json.loads(raw)
        stopped_pid = pid
        capture_owned_errors("interrupted-process")
        deadline = time.monotonic() + 10
        while device.sh("pidof", PACKAGE, check=False).strip() and time.monotonic() < deadline:
            time.sleep(0.1)
        if device.sh("pidof", PACKAGE, check=False).strip():
            raise RuntimeError("Owned writer remained after force-stop")
        after_raw = _read_raw(device, primary)
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
        capture_owned_errors("recovered-process")
        result.update(success=True, protected_files=len(before_profile), recovered_pid=pid, interrupted_pid=stopped_pid)
        write(out / "native-resave.json", report)
    except Exception as error:
        result["error"] = str(error)
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
        for path in remote:
            try:
                device.sh("rm", "-f", path)
                if _remote_path_state(device, path) != "absent":
                    errors.append("Observer temporary target remains")
            except Exception as error:
                errors.append(str(error))
        try:
            if pid and device.sh("pidof", PACKAGE, check=False).strip() == pid:
                bind_installed_apk(device.owned(), expected_sha256=expected)
                device.sh("am", "force-stop", PACKAGE)
            if device.sh("pidof", PACKAGE, check=False).strip():
                errors.append("Owned package still running")
            if not device.display(False):
                errors.append("OLED sleep not verified")
        except Exception as error:
            errors.append(str(error))
        result["cleanup_errors"] = errors
        result["success"] = result["success"] and not errors
        write(out / "result.json", result)
        if errors:
            raise RuntimeError("Interruption-case teardown failed; inspect private evidence")
    return dict(result, evidence=str(out.relative_to(WORK.parent)))
