"""Current: runner-leased, thermally supervised session-memory diagnostics.

Use through /lab script with device=<alias>. The bridge owns the sole lease;
this synchronous adapter neither acquires another lease nor changes policy.
Private evidence stays under work/. Stdout is an explicit numeric/hash summary.
Capture is attribution only; measure omits snapshots and the static-root walk.
The inspect mode reads existing failed evidence without a device alias or access.
The identity mode verifies the selected idle installation read-only and emits its hash.
"""

import argparse
import contextlib
import hashlib
import io
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


def _receipt_path(value, *, existing=False):
    relative = Path(value)
    if relative.is_absolute() or relative.parts[:2] != ("work", "coordination") or ".." in relative.parts or relative.suffix != ".json":
        raise ValueError("Use a new repository-relative JSON receipt under work/coordination")
    # Runner worktrees intentionally link work/ to the canonical private tree.
    # Resolve that authorized boundary once; reject additional nested links.
    work = common.WORK.resolve()
    path = work.joinpath(*relative.parts[1:])
    if path != path.resolve() or (not path.is_file() if existing else path.exists()):
        raise ValueError("Receipt must have the requested existence and no nested symlinks")
    return path


SERIES_STOPS = frozenset(
    "deadline process-exited unexpected-session-index survivor-selection-mismatch first-failure outside-first-stage-contract "
    "completed-session-report-unavailable completed-session-cleanup-failed offline-menu-start-control-unavailable "
    "ordinary-menu-start-not-observed first-live-profile-baseline-unavailable abandon-observation-contract-failed "
    "abandon-world-startup-timeout unexpected-or-unowned-end-run-confirmation abandon-control-geometry-unavailable "
    "original-loss-occurred-before-abandon first-runtime-log-error runner-error repeated-sessions-observed".split()
)
# Exact public literals in session_cleanup_check's observation/cleanup contracts.
# Runtime messages and dynamically interpolated values are deliberately excluded.
AUTHORED_FAILURES = frozenset(
    (
        "abandon observation is not live session 1",
        "world stopped being ready during observed interval",
        "ready world does not report a living player with positive maxHealth",
        "diagnostic input was not observed throughout the live interval",
        "player death event occurred before abandon",
        "player death lifecycle occurred before abandon",
        "run ending or result occurred before abandon",
        "profile result was applied before abandon",
        "abandoned-session report identity differs",
        "abandoned session did not finish successful owned cleanup",
        "integrated world/template cleanup was not observed",
        "source abandon action was not recorded",
        "abandon path lacks explicit no-ending/no-result evidence",
        "abandon path lacks explicit no-native-death evidence",
        "abandon path lacks explicit no-profile-result evidence",
        "abandon path changed/missed applied-run or earned-unlock counts",
        "diagnostic assistance evidence or all-off debug options differ",
    )
)


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _failure_summary(value):
    result = dict(first_authored_reason=None, failed_session=None, first_failure_sha256=None)
    if not isinstance(value, str):
        return result
    result["first_failure_sha256"] = hashlib.sha256(value.encode()).hexdigest()
    match = re.fullmatch(r"session (\d+)(?:: (.*)| (button|endRunButton|confirmEndRunButton))?", value, re.DOTALL)
    if match:
        result["failed_session"] = int(match[1])
        value = match[2] or ("abandon-control-geometry-unavailable" if match[3] else "session-index")
    if value in AUTHORED_FAILURES or value in SERIES_STOPS or value == "session-index":
        result["first_authored_reason"] = value
    return result


def _recorded_series_file(receipt):
    """Use exact recorded references only; never enumerate run directories."""
    references = []
    if isinstance(receipt.get("stage_evidence"), str):
        references.append(receipt["stage_evidence"])
    stage = receipt.get("stage")
    if isinstance(stage, dict) and isinstance(stage.get("evidence"), str):
        references.append(stage["evidence"])
    for key in ("error", "stage_error"):
        error = receipt.get(key)
        if isinstance(error, str) and error.startswith("Session memory check failed (") and "); see " in error:
            references.append(error.rsplit("); see ", 1)[1])
    if len(set(references)) != 1:
        raise ValueError("One unambiguous recorded session result is required")
    relative = Path(references[0])
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) not in (5, 6)
        or relative.parts[:2] != ("work", "device")
        or relative.parts[-3:-1] != ("experiments", "session-memory")
    ):
        raise ValueError("Recorded result is outside session-memory evidence")
    work = common.WORK.resolve()
    path = work.joinpath(*relative.parts[1:], "result.json")
    if path != path.resolve() or not path.is_relative_to(work) or not path.is_file():
        raise ValueError("Recorded result is missing or has nested symlinks")
    return path


def inspect_receipt(receipt, expected_receipt_sha256, expected_apk_sha256):
    """Read an exact retained receipt/result; no device imports, calls or writes."""
    public = dict(success=False, mode="inspect", diagnostic_only=True, acceptance_available=False, memory_bound_pass=False)
    phase = "receipt-read"
    try:
        expected = validate_expected_apk_sha256(expected_apk_sha256)
        if expected is None or not isinstance(expected_receipt_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_receipt_sha256):
            raise ValueError("Explicit receipt and APK hashes are required")
        payload = _receipt_path(receipt, existing=True).read_bytes()
        phase = "receipt-hash"
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected_receipt_sha256:
            raise ValueError("Receipt bytes differ")
        private = json.loads(payload)
        phase = "receipt-provenance"
        if not isinstance(private, dict) or private.get("apk_sha256") != expected or private.get("mode") not in {"capture", "measure"}:
            raise ValueError("Receipt APK or mode differs")
        phase = "owner-evidence-reference"
        path = _recorded_series_file(private)
        phase = "owner-result-read"
        raw = path.read_bytes()
        series = json.loads(raw)
        phase = "owner-provenance"
        if not isinstance(series, dict) or series.get("apk_sha256") != expected or not isinstance(series.get("attempt"), str):
            raise ValueError("Owner result identity differs")
        if hashlib.sha256(series["attempt"].encode()).hexdigest() != private.get("attempt_sha256"):
            raise ValueError("Owner attempt differs")
        if series.get("sessions_requested") != private.get("sessions_requested"):
            raise ValueError("Owner requested-session count differs")
        phase = "owner-summary"
        growth = series.get("growth") or {}
        points = []
        for row in growth.get("rows") or []:
            points.append(
                {
                    "session": _count(row.get("session")),
                    "managed_at_start_bytes": _count(row.get("managed_at_start")),
                    "managed_after_collection_bytes": _count(row.get("managed_after_collection")),
                    "menu_pss_kib": _count(row.get("menu_pss_kib")),
                }
            )
        final = [sample for sample in growth.get("final_menu_samples") or [] if sample.get("phase") == "before-presentation"]
        public.update(
            success=True,
            original_report_sha256=digest,
            owner_result_sha256=hashlib.sha256(raw).hexdigest(),
            apk_sha256=expected,
            original_series_success=series.get("success") is True,
            original_receipt_success=private.get("success") is True,
            capture_instrumented=private["mode"] == "capture",
            sessions_requested=_count(series.get("sessions_requested")),
            sessions_observed=_count(series.get("sessions_observed")),
            runtime_error_count=len(series["runtime_errors"]) if isinstance(series.get("runtime_errors"), list) else None,
            failure_count=len(series["failures"]) if isinstance(series.get("failures"), list) else None,
            stop=series.get("stop") if series.get("stop") in SERIES_STOPS else "unclassified",
            stop_sha256=hashlib.sha256(series["stop"].encode()).hexdigest() if isinstance(series.get("stop"), str) else None,
            session_samples=points,
            final_menu_managed_bytes=_count(final[0].get("managed")) if len(final) == 1 else None,
            recorded_menu_slope_bytes_per_session=_number(growth.get("per_session_slope_from_session_2", {}).get("managed_before_presentation_bytes")),
            **_failure_summary(series.get("first_failure")),
        )
    except Exception:
        public["failure_phase"] = phase
    return public


def installed_identity(*, environ=None):
    """Discover an owned idle APK hash; no APK transfer, local APK read or writes."""
    public = dict(success=False, mode="identity", read_only=True)
    phase = "runner-context"
    try:
        # Device helpers capture adb output; suppress any Python owner diagnostics.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            serial, _, _ = _runner_context(os.environ if environ is None else environ)
            import alpha_stability_batch as owner

            phase = "installed-ownership"
            device = owner._device(serial)
            expected = validate_expected_apk_sha256(device.owned().get("apk_sha256"))
            if expected is None:
                raise ValueError("Owned receipt lacks an APK hash")
            phase = "installed-readback"
            # Independently hashes actual package bytes on-device and verifies
            # receipt placement, runtime backing and absent process/selector/pending.
            owner._idle_readback(device, expected)
            public.update(success=True, apk_sha256=expected, installed_bytes_verified=True, idle_verified=True)
    except BaseException:
        public["failure_phase"] = phase
    return public


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
    parser.add_argument("mode", choices=("preflight", "capture", "measure", "inspect", "identity"))
    parser.add_argument("--expected-apk-sha256")
    parser.add_argument("--sessions", type=int, default=6)
    parser.add_argument(
        "--receipt", help="Repository-relative ignored JSON receipt under work/coordination; new for runs, existing for inspect; omitted for identity"
    )
    parser.add_argument("--expected-receipt-sha256", help="Required for read-only inspect; bind the existing private receipt's exact bytes")
    args = parser.parse_args(argv)
    if args.mode == "identity":
        if any(value is not None for value in (args.receipt, args.expected_apk_sha256, args.expected_receipt_sha256)):
            parser.error("identity discovers the installed hash read-only; omit receipt and expected hashes")
    elif args.expected_apk_sha256 is None or args.receipt is None:
        parser.error("this mode requires --expected-apk-sha256 and --receipt")
    try:
        if args.mode == "identity":
            summary = installed_identity()
        elif args.mode == "inspect":
            summary = inspect_receipt(args.receipt, args.expected_receipt_sha256, args.expected_apk_sha256)
        else:
            if args.expected_receipt_sha256 is not None:
                parser.error("--expected-receipt-sha256 requires inspect")
            summary = run(args.mode, args.expected_apk_sha256, args.sessions, receipt=args.receipt)
    except BaseException:
        # A local receipt/output failure must not leak a traceback into the public tail.
        summary = dict(success=False, failure_phase="local-evidence-write")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
