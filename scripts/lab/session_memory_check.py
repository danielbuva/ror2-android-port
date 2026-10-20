"""Observe resource samples across repeated same-process UI-abandon sessions.

Each session is an ordinary Commando menu start, at least 60 s of ready Lakes
play with diagnostic automatic input (all gameplay debug assists off), then the
existing offline settings end-run control. Every completed session must pass the
session-cleanup runner's abandon contract before the next menu start. The
runtime's existing SessionResourceBoundary samples and the host's per-menu PSS
are collected; growth is reported as an observation, never as a leak fix or
normal-game acceptance.
"""

import re
import time

from common import WORK, now, write
from device import PACKAGE
from installed_attempt import attempt_from_installed, bind_installed_apk, validate_expected_apk_sha256
from nova_bridge import current_errors
import session_cleanup_check as cleanup
from session_cleanup_check import (
    ABANDON_STARTUP_TIMEOUT_SECONDS,
    DEFAULT_SURVIVOR,
    LOG_POLL_SECONDS,
    POLL_SECONDS,
    SPINE_ID,
    SessionCleanupDevice,
    abandon_contract,
    abandon_control_coordinates,
    abandon_observation_failures,
    matches_run,
    menu_start_coordinates,
    report_errors,
    runtime_stop,
    selection,
    selector_action,
    survivor_identity_failures,
)

DEFAULT_SESSIONS = 5
MIN_SESSIONS = 3
MAX_SESSIONS = 8
SESSION_BUDGET_SECONDS = 300
SAMPLE_FIELDS = (
    "phase",
    "seconds",
    "allocated",
    "reserved",
    "managed",
    "managedTotal",
    "collections",
    "trackedCompletedSessions",
    "liveCompletedProbes",
    "liveCompletedReports",
    "materials",
    "textures",
    "shaders",
    "gameObjects",
    "bundles",
    "catalogGenerations",
    "catalogLocatorsAlive",
    "catalogManifestsAlive",
    "activeLocators",
    "detachedCatalogOperations",
    "rootWalkRan",
    "rootWalkTruncated",
    "rootWalkNodes",
    "rootWalkRoots",
    "rootWalkReadFailures",
    "rootWalkSeconds",
    "rootWalkPaths",
    "rootWalkFailureSamples",
    "rootWalkCensus",
    "rootWalkRootAttribution",
    "staticCallbackCounts",
    "prunedDestroyedDepossessionSubscribers",
    "prunedDestroyedRegistryEntries",
)
WAITING = (
    "live world report is shorter than the 60 second observation interval",
    "host did not observe a full 60 second live interval",
    "waiting for a ready integrated world",
    "waiting for diagnostic input in the live world",
    "waiting for positive player health/maxHealth",
)


def as_session_one(report, session):
    """Reuse the session-1 abandon contracts only after checking the real index."""
    if not isinstance(report, dict) or report.get("session") != session:
        return None
    return dict(report, session=1)


def completed_name(session):
    return "movement-completed-session-%d.json" % session


def resource_samples(report):
    samples = []
    for sample in (report or {}).get("sessionResources") or []:
        if isinstance(sample, dict):
            samples.append({key: sample.get(key) for key in SAMPLE_FIELDS})
    return samples


def parse_total_pss_kib(text):
    """Return dumpsys meminfo TOTAL PSS in KiB, or None when absent."""
    match = re.search(r"TOTAL PSS:\s+(\d+)", text or "")
    if match:
        return int(match.group(1))
    match = re.search(r"^\s*TOTAL\s+(\d+)", text or "", re.MULTILINE)
    return int(match.group(1)) if match else None


def _phase_value(samples, phase, key):
    for sample in samples:
        if sample.get("phase") == phase:
            return sample.get(key)
    return None


def growth_summary(sessions):
    """Summarize post-collection levels per completed session; no leak verdict."""
    rows = []
    for entry in sessions:
        samples = entry.get("samples") or []
        rows.append(
            {
                "session": entry["session"],
                "managed_after_collection": _phase_value(samples, "completed-after-managed-collection", "managed"),
                "reserved_after_collection": _phase_value(samples, "completed-after-managed-collection", "reserved"),
                "game_objects_after_reclaim": _phase_value(samples, "completed-after-reclaim", "gameObjects"),
                "textures_after_reclaim": _phase_value(samples, "completed-after-reclaim", "textures"),
                "bundles_after_reclaim": _phase_value(samples, "completed-after-reclaim", "bundles"),
                "live_completed_probes_at_start": _phase_value(samples, "before-presentation", "liveCompletedProbes"),
                "managed_at_start": _phase_value(samples, "before-presentation", "managed"),
                "menu_pss_kib": entry.get("menu_pss_kib"),
                "root_walk_paths_at_start": _phase_value(samples, "before-presentation", "rootWalkPaths"),
                "static_callback_counts_at_start": _phase_value(samples, "before-presentation", "staticCallbackCounts"),
                "pruned_destroyed_depossession": _phase_value(samples, "completed-before-reclaim", "prunedDestroyedDepossessionSubscribers"),
                "pruned_destroyed_registries": _phase_value(samples, "completed-before-reclaim", "prunedDestroyedRegistryEntries"),
            }
        )

    def slope(key):
        # Exclude session 1, whose first collection includes one-time warmup.
        points = [(row["session"], row[key]) for row in rows[1:] if type(row[key]) is int]
        if len(points) < 2:
            return None
        n = len(points)
        mean_x = sum(x for x, _ in points) / n
        mean_y = sum(y for _, y in points) / n
        den = sum((x - mean_x) ** 2 for x, _ in points)
        return round(sum((x - mean_x) * (y - mean_y) for x, y in points) / den) if den else None

    return {
        "rows": rows,
        "per_session_slope_from_session_2": {
            "managed_after_collection_bytes": slope("managed_after_collection"),
            "reserved_after_collection_bytes": slope("reserved_after_collection"),
            "menu_pss_kib": slope("menu_pss_kib"),
        },
        "limits": "Observation only: Boehm/IL2CPP heap usage, PSS and object counts; no retaining root is attributed here.",
    }


def check_session_memory(sessions=DEFAULT_SESSIONS, expected_apk_sha256=None, root_walk=False):
    if type(sessions) is not int or not MIN_SESSIONS <= sessions <= MAX_SESSIONS:
        raise ValueError("Use %d to %d sessions" % (MIN_SESSIONS, MAX_SESSIONS))
    survivor = DEFAULT_SURVIVOR
    expected_apk_sha256 = validate_expected_apk_sha256(expected_apk_sha256)
    if expected_apk_sha256 is None:
        raise ValueError("session-memory-check requires --expected-apk-sha256 for the installed APK")
    device = SessionCleanupDevice()
    installed = device.owned()
    storage = device.storage()
    mode = device.settings["storage_mode"]
    if installed.get("storage", {}).get("mode") != mode or storage.get("mode") != mode:
        raise RuntimeError("Owned APK storage differs from selected-device policy")
    expected_prefix = "/data/app/" if mode == "internal" else "/mnt/expand/" + str(storage.get("uuid")) + "/"
    if expected_prefix not in installed.get("package_path", ""):
        raise RuntimeError("Owned APK placement differs from selected live storage")
    artifact_hash, apk_binding_mode = bind_installed_apk(installed, expected_sha256=expected_apk_sha256)
    attempt = attempt_from_installed(installed)
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    if not runtime.endswith("/Android/data/" + PACKAGE + "/files"):
        raise RuntimeError("Selected package runtime path is outside its app-private directory")
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + SPINE_ID + ".json"
    if cleanup._remote_path_state(device, selector) != "absent":
        raise RuntimeError("Existing diagnostic selector; preserve it")

    out = device.evidence_directory("experiments", "session-memory", now())
    out.mkdir(parents=True, exist_ok=False)
    value = selection(attempt, survivor)
    value["debugOptions"]["purpose"] = "Repeated UI-abandon sessions for resource observation; automatic input is diagnostic and assisted"
    if root_walk:
        # Opt-in reachability walk in SessionResourceBoundary, only at the final menu: it may run
        # unrelated static constructors, so it must follow every measured session (J773).
        value["diagnosticCompletedRootWalkSession"] = sessions + 1
    write(out / "selection.json", value)
    frozen = {
        "sessions": sessions,
        "root_walk": bool(root_walk),
        "package": PACKAGE,
        "apk_sha256": artifact_hash,
        "apk_binding_mode": apk_binding_mode,
        "attempt": attempt,
        "storage_mode": mode,
        "selected_survivor": survivor,
        "scope": "diagnostic automatic input; no gameplay debug assists; source UI abandon, no original ending/result",
    }
    write(out / "frozen.json", frozen)

    pid = None
    stop = "deadline"
    first_failure = None
    profile_baseline = None
    observed = []  # one entry per completed session
    menu_pss = {}
    menu_started = set()
    live_at = startup_at = None
    settings_sent = end_sent = False
    final_menu = None
    runtime_errors = []
    cleanup_errors = []
    started = time.monotonic()
    deadline = SESSION_BUDGET_SECONDS * sessions + 120
    next_log = 0.0

    def fail(reason, detail=None):
        nonlocal stop, first_failure
        stop = reason
        if first_failure is None:
            first_failure = detail or reason

    try:
        for index in range(1, sessions + 1):
            path = runtime + "/" + completed_name(index)
            for target, label in ((report_path, "prior-current-report.json"), (path, "prior-" + completed_name(index))):
                state = cleanup._remote_path_state(device, target)
                if state == "absent":
                    continue
                if state != "file":
                    raise RuntimeError("Refusing non-file app-private report path: " + target.rsplit("/", 1)[-1])
                (out / label).write_text(cleanup._read_raw(device, target))
                device.sh("rm", "-f", target)
                if cleanup._remote_path_state(device, target) != "absent":
                    raise RuntimeError("Could not clear the exact stale report target")
        device.cmd("push", str(out / "selection.json"), selector)
        launch = device.launch()
        pid = str(launch["pid"])
        write(out / "launch.json", {"pid": pid, **frozen})
        if not device.display(True):
            raise RuntimeError("Selected device display cannot be awakened for the existing on-screen controls")

        while time.monotonic() - started < deadline:
            if not cleanup._same_process(device, pid):
                fail("process-exited")
                break
            current = cleanup._read_json(device, report_path)
            if current and matches_run(current, pid, attempt):
                session = current.get("session")
                if type(session) is not int or not 1 <= session <= sessions + 1:
                    fail("unexpected-session-index")
                    break
                identity = survivor_identity_failures(current, survivor)
                if identity:
                    fail("survivor-selection-mismatch", identity[0])
                    break
                reason = runtime_stop(current, pid, attempt, survivor)
                if reason:
                    details = report_errors(current)
                    fail(reason, details[0] if details else None)
                    break
                phase = current.get("phase")
                if phase == "offline-start-menu" and session not in menu_started:
                    if session > 1:
                        completed = cleanup._read_json(device, runtime + "/" + completed_name(session - 1))
                        view = as_session_one(completed, session - 1)
                        if view is None:
                            fail("completed-session-report-unavailable", "session %d" % (session - 1))
                            break
                        failures = abandon_contract(view, pid, attempt, profile_baseline, survivor)
                        if failures:
                            fail("completed-session-cleanup-failed", "session %d: %s" % (session - 1, failures[0]))
                            break
                        write(out / ("completed-session-%d.json" % (session - 1)), completed)
                        observed.append({"session": session - 1, "samples": resource_samples(completed)})
                    pss = parse_total_pss_kib(device.sh("dumpsys", "meminfo", PACKAGE, check=False))
                    menu_pss[session] = pss
                    if observed:
                        observed[-1]["menu_pss_kib"] = pss
                    if session == sessions + 1:
                        final_menu = current
                        write(out / "final-menu.json", current)
                        stop = "repeated-sessions-observed"
                        break
                    coords = menu_start_coordinates(current)
                    if coords is None:
                        fail("offline-menu-start-control-unavailable", "session %d" % session)
                        break
                    device.sh("input", "tap", str(coords[0]), str(coords[1]))
                    menu_started.add(session)
                    live_at = startup_at = None
                    settings_sent = end_sent = False
                if phase == "integrated-world-playing" and not end_sent:
                    if session not in menu_started:
                        fail("ordinary-menu-start-not-observed", "session %d" % session)
                        break
                    if profile_baseline is None:
                        profile_baseline = cleanup._profile_counts(current)
                        if profile_baseline is None:
                            fail("first-live-profile-baseline-unavailable")
                            break
                    world = current.get("world") or {}
                    if startup_at is None:
                        startup_at = time.monotonic()
                    if (
                        live_at is None
                        and world.get("ready") is True
                        and cleanup._finite_number(world.get("health"))
                        and world["health"] > 0
                        and cleanup._finite_number(world.get("maxHealth"))
                        and world["maxHealth"] > 0
                        and world.get("diagnosticInputEver") is True
                    ):
                        live_at = time.monotonic()
                    view = as_session_one(current, session)
                    failures = abandon_observation_failures(view, survivor, time.monotonic() - live_at if live_at is not None else 0.0, live_at)
                    blocking = [failure for failure in failures if failure not in WAITING]
                    if blocking:
                        fail("abandon-observation-contract-failed", "session %d: %s" % (session, blocking[0]))
                        break
                    if live_at is None and time.monotonic() - startup_at >= ABANDON_STARTUP_TIMEOUT_SECONDS:
                        fail("abandon-world-startup-timeout", "session %d" % session)
                        break
                    if not any(failure in WAITING for failure in failures):
                        settings = current.get("settings") or {}
                        key = None
                        if not settings_sent:
                            key = "button"
                        elif settings.get("visible") is True and settings.get("canEndRun") is True:
                            key = "endRunButton"
                        if key:
                            coords = abandon_control_coordinates(current, key, device.sh("wm", "size"), device.sh("dumpsys", "window", "displays"))
                            if coords is None:
                                fail("abandon-control-geometry-unavailable", "session %d %s" % (session, key))
                                break
                            device.sh("input", "tap", str(coords[0]), str(coords[1]))
                            if key == "button":
                                settings_sent = True
                            else:
                                end_sent = True
                if phase == "commando-defeated":
                    fail("original-loss-occurred-before-abandon", "session %d" % session)
                    break
            if time.monotonic() >= next_log:
                logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S", check=False)
                runtime_errors = current_errors(logs, pid)
                if runtime_errors:
                    fail("first-runtime-log-error", runtime_errors[0])
                    break
                next_log = time.monotonic() + LOG_POLL_SECONDS
            time.sleep(POLL_SECONDS)
    except Exception as error:
        fail("runner-error", str(error))
    finally:
        try:
            if pid:
                logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S", check=False)
                (out / "current-process.log").write_text(logs)
                runtime_errors = current_errors(logs, pid) or runtime_errors
                if runtime_errors and stop == "repeated-sessions-observed":
                    fail("first-runtime-log-error", runtime_errors[0])
        except Exception as error:
            cleanup_errors.append("log capture: " + str(error))
        try:
            state = cleanup._remote_path_state(device, selector)
            raw = cleanup._read_raw(device, selector) if state == "file" else ""
            action = selector_action(state, raw, attempt)
            if action == "remove-owned":
                device.sh("rm", "-f", selector)
                if cleanup._remote_path_state(device, selector) != "absent":
                    cleanup_errors.append("owned selector remains after removal")
            elif action != "none":
                cleanup_errors.append("selector " + action + "; preserved it")
        except Exception as error:
            cleanup_errors.append("selector cleanup: " + str(error))
        try:
            if not cleanup._stop_process(device, pid):
                cleanup_errors.append("selected process remained after force-stop")
        except Exception as error:
            cleanup_errors.append("process cleanup: " + str(error))
        try:
            if not device.display(False):
                cleanup_errors.append("display did not confirm sleep")
        except Exception as error:
            cleanup_errors.append("display sleep: " + str(error))

    failures = []
    if stop != "repeated-sessions-observed":
        failures.append("stopped: " + stop)
    if len(observed) != sessions:
        failures.append("observed %d of %d completed sessions" % (len(observed), sessions))
    # Every completed session already passed abandon_contract's frozen profile counts; the final
    # menu's profile is not loaded yet, so it carries no further count evidence.
    failures.extend(cleanup_errors)
    summary = growth_summary(observed)
    summary["final_menu_samples"] = resource_samples(final_menu)
    result = {
        "success": not failures,
        "stop": stop,
        "first_failure": first_failure,
        "failures": failures,
        "sessions_requested": sessions,
        "sessions_observed": len(observed),
        "pid": pid,
        "attempt": attempt,
        "apk_sha256": artifact_hash,
        "apk_binding_mode": apk_binding_mode,
        "profile_baseline": profile_baseline,
        "menu_pss_kib": menu_pss,
        "growth": summary,
        "runtime_errors": runtime_errors,
        "evidence": str(out.relative_to(WORK.parent)),
    }
    write(out / "result.json", result)
    if failures:
        raise RuntimeError("Session memory check failed (" + str(first_failure or stop) + "); see " + result["evidence"])
    return {key: result[key] for key in ("success", "stop", "sessions_observed", "apk_sha256", "growth", "evidence")}
