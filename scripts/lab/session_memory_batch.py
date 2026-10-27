"""Current: runner-leased, thermally supervised session-memory diagnostics.

Use through /lab script with device=<alias>. The bridge owns the sole lease;
this synchronous adapter neither acquires another lease nor changes policy.
Private evidence stays under work/. Stdout is an explicit numeric/hash summary.
Capture is attribution only; measure omits snapshots and the static-root walk.
"""

import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

import common
from device_context import command_selectors, set_command_selector, validate_serial
from installed_attempt import attempt_from_installed, validate_expected_apk_sha256


def _runner_context(environ):
    serial = validate_serial(environ.get("LAB_DEVICE_SERIAL"))
    run_id = environ.get("LAB_RUN_ID", "")
    if not re.fullmatch(r"[0-9]+", run_id):
        raise ValueError("Run through the lab runner")
    root = common.WORK.resolve().parent
    lease = root / ".local/orchestrator/leases" / serial
    if lease.resolve() != lease or not lease.is_dir():
        raise RuntimeError("Runner device lease is absent or unsafe")
    marker = lease / "lab-runner.json"
    if marker.is_symlink():
        raise RuntimeError("Runner lease marker is unsafe")
    owner = common.read(marker)
    if owner.get("workstream") != "lab-runner" or owner.get("pid") != os.getppid() or str(owner.get("run")) != run_id:
        raise RuntimeError("This process does not belong to the runner lease")
    return serial, root, run_id


def _thermal_reason(error):
    """Classify known owner messages without publishing raw errors or zone names."""
    if not error:
        return None
    for prefix, reason in (
        ("CPU/GPU thermal zone stayed above 95 C", "cpu-gpu-sustained-limit"),
        ("Battery at or above 43 C", "battery-limit"),
        ("Battery thermal zone at or above 43 C", "battery-limit"),
        ("Thermal sample gap exceeded", "sampling-gap"),
        ("Battery charge separation/limit admission refused", "battery-admission"),
        ("Readable thermal zone exceeded 80 C hard abort", "admission-hard-limit"),
        ("Three-hour alpha driver deadline reached", "deadline"),
    ):
        if str(error).startswith(prefix):
            return reason
    return "supervision-failed"


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _stage_result(stage):
    evidence = stage.get("evidence")
    if not isinstance(evidence, str):
        raise RuntimeError("Session owner did not return evidence")
    path = common.WORK.parent / evidence / "result.json"
    if not path.resolve().is_relative_to(common.WORK.resolve()):
        raise RuntimeError("Session evidence escaped local work")
    return common.read(path)


def _receipt_path(value):
    relative = Path(value)
    if relative.is_absolute() or relative.parts[:2] != ("work", "coordination") or ".." in relative.parts or relative.suffix != ".json":
        raise ValueError("Use a new repository-relative JSON receipt under work/coordination")
    # Runner worktrees intentionally link work/ to the canonical private tree.
    # Resolve that authorized boundary once; reject additional nested links.
    work = common.WORK.resolve()
    path = work.joinpath(*relative.parts[1:])
    if path != path.resolve() or path.exists():
        raise ValueError("Receipt must be new and have no symlink components")
    return path


def run(mode, expected_apk_sha256, sessions=6, *, receipt, environ=None):
    """Reuse installed identity, capacity, cleanup and thermal owners unchanged."""
    import alpha_stability_batch as owner
    from session_memory_check import check_session_memory

    environ = os.environ if environ is None else environ
    public = dict(success=False, mode=mode, sessions_requested=sessions, thermal_stop_reason=None)
    private = dict(success=False, mode=mode)
    previous = command_selectors()
    out = None
    receipt_path = None
    admitted = False
    thermal = None
    phase = "runner-context"
    try:
        if mode not in {"preflight", "capture", "measure"} or type(sessions) is not int or not 6 <= sessions <= 32:
            raise ValueError("Use preflight, capture or measure and 6 to 32 sessions")
        expected = validate_expected_apk_sha256(expected_apk_sha256)
        if expected is None:
            raise ValueError("An explicit installed APK hash is required")
        public["expected_apk_sha256"] = expected
        receipt_path = _receipt_path(receipt)
        serial, root, run_id = _runner_context(environ)
        candidate = common.WORK / "coordination/session-memory-batch" / run_id
        candidate.mkdir(parents=True, exist_ok=False)
        out = candidate
        # Any owner diagnostic (including exceptions) is local, not a public tail.
        with (out / "owner-output.log").open("w") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                set_command_selector(serial, previous[1])
                phase = "installed-identity"
                device = owner._device(serial)
                private["initial_readback"] = owner._idle_readback(device, expected)
                public["apk_sha256"] = expected
                attempt = attempt_from_installed(device.owned())
                private["attempt_sha256"] = hashlib.sha256(attempt.encode()).hexdigest()
                public["attempt_sha256"] = private["attempt_sha256"]
                admitted = True
                phase = "capacity"
                if mode != "measure":
                    budget = owner._host_capture_budget(root)
                    private["host_capture_budget"] = budget
                    if budget["free_bytes"] < budget["required_free_bytes"]:
                        raise RuntimeError("Host capture budget refused")
                    owner._require_capture_capacity(device)
                else:
                    storage = device.storage()
                    if storage[storage["mode"]]["free_bytes"] < owner.DEVICE_FREE_RESERVE_BYTES:
                        raise RuntimeError("Selected device is below the retained free-space reserve")
                phase = "thermal-admission"
                thermal = owner._GameThermalOwner(device, expected, out / "thermal.jsonl", time.monotonic() + owner.BATCH_DEADLINE_SECONDS)
                thermal.phase = "session-memory-" + mode
                thermal.cool()
                if mode != "preflight":
                    phase = "session-series"
                    stage_error = None
                    try:
                        thermal.start()
                        stage = check_session_memory(
                            sessions=sessions, expected_apk_sha256=expected, memory_snapshots=mode == "capture", _launch=thermal.launch
                        )
                    except BaseException as error:
                        stage_error = error
                    finally:
                        try:
                            thermal.finish()
                        except BaseException as error:
                            private["thermal_error"] = str(error)
                            public["thermal_stop_reason"] = _thermal_reason(thermal.error or error)
                            if stage_error:
                                private["stage_error"] = str(stage_error)
                            raise
                    if stage_error:
                        raise stage_error
                    phase = "session-result"
                    private["stage"] = stage
                    raw = _stage_result(stage)
                    if stage.get("success") is not True or raw.get("success") is not True or raw.get("apk_sha256") != expected:
                        raise RuntimeError("Session result is not a successful matched APK case")
                    private["stage_evidence"] = stage["evidence"]
                    private["memory_snapshots"] = raw.get("memory_snapshots", {})
                    public["sessions_observed"] = raw["sessions_observed"]
                    public["runtime_error_count"] = len(raw.get("runtime_errors", []))
                    public["failure_count"] = len(raw.get("failures", []))
                    public["snapshot_count"] = len(private["memory_snapshots"])
                    growth = raw.get("growth", {})
                    slope = growth.get("per_session_slope_from_session_2", {}).get("managed_before_presentation_bytes")
                    public["managed_menu_slope_bytes_per_session"] = _number(slope)
                    # Keep all matched menus, including the final menu. No spike filtering.
                    rows = growth.get("rows", [])
                    final = [x for x in growth.get("final_menu_samples", []) if x.get("phase") == "before-presentation"]
                    complete = len(rows) == sessions and all(type(x.get("managed_at_start")) is int for x in rows[1:])
                    complete = complete and len(final) == 1 and type(final[0].get("managed")) is int
                    public["memory_bound_pass"] = bool(
                        mode == "measure"
                        and complete
                        and public["sessions_observed"] == sessions
                        and not public["runtime_error_count"]
                        and not public["failure_count"]
                        and _number(slope) is not None
                        and slope <= 0.1 * 1024**2
                    )
                public["success"] = True
            except BaseException as error:
                private["error"] = str(error)
                public["failure_phase"] = phase
                if phase == "thermal-admission" or (thermal and thermal.error):
                    public["thermal_stop_reason"] = _thermal_reason(thermal.error or error)
            finally:
                if admitted:
                    try:
                        private["terminal_readback"] = owner._terminal_readback(serial, expected)
                        public["terminal_idle_verified"] = True
                    except BaseException as error:
                        private["terminal_error"] = str(error)
                        public["terminal_idle_verified"] = False
                        public["success"] = False
                        public["failure_phase"] = "terminal-readback"
                if thermal:
                    public["peak_cpu_gpu_celsius"] = _number(thermal.peak_cpu_gpu_celsius)
                    public["time_above_80_seconds"] = _number(thermal.time_above_80_seconds)
                    if thermal.error:
                        public["thermal_stop_reason"] = _thermal_reason(thermal.error)
                        public["success"] = False
    except BaseException as error:
        private["error"] = str(error)
        public["failure_phase"] = phase
    finally:
        set_command_selector(*previous)
        if not public["success"] and "memory_bound_pass" in public:
            public["memory_bound_pass"] = False
        if out is not None:
            private.update(public)
            common.write(out / "result.json", private)
            common.write(receipt_path, private)
            public["report_sha256"] = common.sha(receipt_path)
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "capture", "measure"))
    parser.add_argument("--expected-apk-sha256", required=True)
    parser.add_argument("--sessions", type=int, default=6)
    parser.add_argument("--receipt", required=True, help="New repository-relative ignored JSON receipt under work/coordination; remains local")
    args = parser.parse_args(argv)
    try:
        summary = run(args.mode, args.expected_apk_sha256, args.sessions, receipt=args.receipt)
    except BaseException:
        # A local receipt/output failure must not leak a traceback into the public tail.
        summary = dict(success=False, failure_phase="local-evidence-write")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
