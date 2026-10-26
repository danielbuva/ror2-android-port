#!/usr/bin/env python3
"""Time the entire unittest host suite, serially or in an isolated process pool.

Discovery is exactly ``unittest discover -s tests``: no path/change filters.
Workers inherit that discovery using POSIX fork (Linux CI and macOS ci-local),
so import-time skips, custom load_tests suites and their IDs are not recreated.
Each discovery module stays intact, including its class/module fixtures. The
serial control uses one process for the entire suite in discovery order.

JSON keeps every native unittest outcome, including fixture errors/skips and
successful/failed/skipped subtests, plus the full discovered test inventory.
Subtest IDs can contain random temporary paths/object addresses; comparison
therefore keys subtests by exact parent ID and invocation ordinal, retaining
their original unittest IDs in the report for diagnosis.
"""

from __future__ import annotations

import argparse
from collections import Counter
import contextlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import traceback
import unittest


# These existing optional-toolchain tests build csproj files in shared source
# directories (tests/observer-fixtures and tools/assembly-transforms), including
# their shared obj/ outputs. Keep them together even when the toolchain is absent:
# the runner never substitutes its own skip policy for the tests' own checks.
SHARED_BUILD_MODULES = {
    "test_assembly_slice",
    "test_music_output_observer",
    "test_observer_stage_hook",
    "test_original_music_native_result_observer",
}
BAD_OUTCOMES = {"failure", "error", "unexpectedSuccess"}


def leaves(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from leaves(test)
        else:
            yield test


class TimedResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.events = []
        self.tests = []
        self.started = {}
        self.subtest_counts = Counter()
        self.identities = {}

    def startTest(self, test):
        super().startTest(test)
        # Existing media-plan fixtures assign self.id = an integer in setUp.
        # Capture the unittest identity before fixture code shadows id().
        # Retain the object as well: suites release completed tests, and a later
        # fixture-error holder can otherwise reuse the same Python object ID.
        self.identities[id(test)] = (test, test.id())
        self.started[id(test)] = (time.perf_counter(), len(self.events))

    def identity(self, test):
        if id(test) in self.identities:
            return self.identities[id(test)][1]
        parent = getattr(test, "test_case", None)
        if parent is not None:
            return self.identity(parent) + " " + test._subDescription()
        return test.id()

    def stopTest(self, test):
        started, first = self.started.pop(id(test))
        events = self.events[first:]
        outcomes = [row["outcome"] for row in events if "subtest_index" not in row] or [row["outcome"] for row in events]
        outcome = next((name for name in ("error", "failure", "unexpectedSuccess", "expectedFailure", "skip") if name in outcomes), "pass")
        self.tests.append({"id": self.identity(test), "seconds": time.perf_counter() - started, "outcome": outcome})
        super().stopTest(test)

    def event(self, test, outcome, *, err=None, reason=None, parent=None):
        row = {"id": self.identity(test), "test_id": self.identity(parent or test), "outcome": outcome}
        if parent is not None:
            self.subtest_counts[self.identity(parent)] += 1
            row["subtest_index"] = self.subtest_counts[self.identity(parent)]
        if reason is not None:
            row["reason"] = str(reason)
        if err is not None:
            row["traceback"] = self._exc_info_to_string(err, test)
        self.events.append(row)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.event(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.event(test, "failure", err=err)

    def addError(self, test, err):
        super().addError(test, err)
        self.event(test, "error", err=err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.event(test, "skip", reason=reason, parent=getattr(test, "test_case", None))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.event(test, "expectedFailure", err=err)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.event(test, "unexpectedSuccess")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        outcome = "pass" if err is None else "failure" if issubclass(err[0], test.failureException) else "error"
        self.event(subtest, outcome, err=err, parent=test)


def module_name(suite, index):
    tests = list(leaves(suite))
    if not tests:
        return f"empty-discovery-suite-{index}"
    module = type(tests[0]).__module__
    if module == "unittest.loader":
        return tests[0].id().rsplit(".", 1)[-1]
    return module


def worker(modules, connection, directory):
    # A new process/session per pool job prevents cross-job globals and gives the
    # parent ownership of descendant compilers on timeout or abrupt worker exit.
    os.setsid()
    directory = Path(directory)
    directory.mkdir()
    os.environ.update(TMPDIR=str(directory), TEMP=str(directory), TMP=str(directory), PYTHONDONTWRITEBYTECODE="1")
    tempfile.tempdir = str(directory)
    try:
        for index, name, suite in modules:
            connection.send(("start", index, name))
            started = time.perf_counter()
            result = TimedResult()
            output = directory / f"{index}.log"
            # Redirect OS descriptors too: native subprocess output must not
            # interleave with another worker's diagnostics.
            with output.open("w+") as stream:
                sys.stdout.flush()
                sys.stderr.flush()
                saved = (os.dup(1), os.dup(2))
                try:
                    os.dup2(stream.fileno(), 1)
                    os.dup2(stream.fileno(), 2)
                    result.startTestRun()
                    suite.run(result)
                    result.stopTestRun()
                    sys.stdout.flush()
                    sys.stderr.flush()
                finally:
                    os.dup2(saved[0], 1)
                    os.dup2(saved[1], 2)
                    os.close(saved[0])
                    os.close(saved[1])
                stream.seek(0)
                diagnostic = stream.read() if not result.wasSuccessful() else ""
            connection.send(
                (
                    "result",
                    index,
                    {
                        "module": name,
                        "seconds": time.perf_counter() - started,
                        "tests_run": result.testsRun,
                        "successful": result.wasSuccessful(),
                        "tests": result.tests,
                        "events": result.events,
                        "diagnostic": diagnostic,
                    },
                )
            )
    except BaseException:
        connection.send(("crash", traceback.format_exc()))
    finally:
        connection.close()


def terminate(process):
    # The worker calls setsid before executing tests. If it failed before then,
    # killpg safely fails instead of signalling the runner's own process group.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    if process.is_alive():
        process.kill()
    process.join()


def run_pool(modules, workers, timeout, scratch):
    if not modules:
        return [], []
    context = multiprocessing.get_context("fork")
    if workers == 1:
        jobs = [modules]
    else:
        shared = [row for row in modules if row[1].split(".")[-1] in SHARED_BUILD_MODULES]
        jobs = [[row] for row in modules if row not in shared]
        if shared:
            jobs.insert(0, shared)
    active = []
    results = {}
    infrastructure_errors = []
    next_job = 0
    try:
        while next_job < len(jobs) or active:
            while next_job < len(jobs) and len(active) < workers:
                receive, send = context.Pipe(duplex=False)
                job = jobs[next_job]
                process = context.Process(target=worker, args=(job, send, str(scratch / f"worker-{next_job}")))
                process.start()
                send.close()
                active.append({"process": process, "pipe": receive, "job": job, "started": time.monotonic(), "module": job[0][1]})
                next_job += 1
            for state in active[:]:
                pipe, process = state["pipe"], state["process"]
                # Observe exit before draining: a worker can finish between a
                # poll and is_alive(), leaving its final result unread.
                exited = not process.is_alive()
                while pipe.poll():
                    try:
                        message = pipe.recv()
                    except EOFError:
                        break
                    if message[0] == "start":
                        state.update(started=time.monotonic(), module=message[2])
                    elif message[0] == "result":
                        results[message[1]] = message[2]
                    else:
                        infrastructure_errors.append({"module": state["module"], "error": message[1]})
                timed_out = time.monotonic() - state["started"] > timeout
                if timed_out or exited:
                    if timed_out:
                        infrastructure_errors.append({"module": state["module"], "error": f"worker exceeded {timeout:g} seconds"})
                    terminate(process)
                    if process.exitcode and not timed_out:
                        infrastructure_errors.append({"module": state["module"], "error": f"worker exited {process.exitcode}"})
                    missing = [name for index, name, _ in state["job"] if index not in results]
                    if missing:
                        infrastructure_errors.append({"module": state["module"], "error": "missing module results: " + ", ".join(missing)})
                    pipe.close()
                    active.remove(state)
            if active:
                time.sleep(0.01)
    finally:
        for state in active:
            terminate(state["process"])
            state["pipe"].close()
    return [results[index] for index in sorted(results)], infrastructure_errors


def outcome_signature(report):
    # Preserve multiplicity (including repeated IDs from custom load_tests).
    return Counter(
        (row["test_id"], row.get("subtest_index"), row["outcome"], row.get("reason", "")) for module in report["modules"] for row in module["events"]
    )


def compare_reports(baseline, current):
    differences = []
    if Counter(baseline["discovered_ids"]) != Counter(current["discovered_ids"]):
        differences.append("discovered test IDs differ")
    before, after = outcome_signature(baseline), outcome_signature(current)
    if before != after:
        differences.append(f"outcomes differ: {sum((before - after).values())} missing, {sum((after - before).values())} added")
    if baseline["infrastructure_errors"] or current["infrastructure_errors"]:
        differences.append("a run has infrastructure errors")
    return differences


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="checkout to test (default: current directory)")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="process limit; 1 is the serial baseline")
    parser.add_argument("--timeout", type=float, default=900, help="per-module deadline in seconds, including fixtures")
    parser.add_argument("--report", type=Path, help="write full machine-readable results (local diagnostics; review before publishing)")
    parser.add_argument("--compare", type=Path, help="fail unless discovered IDs and all unittest outcomes equal this prior report")
    parser.add_argument("--slowest", type=int, default=15, help="number of slowest tests and modules to print")
    args = parser.parse_args(argv)
    if args.workers < 1 or not math.isfinite(args.timeout) or args.timeout <= 0 or args.slowest < 0:
        parser.error("workers and timeout must be positive and finite; slowest must be nonnegative")
    if "fork" not in multiprocessing.get_all_start_methods():
        parser.error("host tests require the Linux/macOS fork start method")
    baseline = json.loads(args.compare.read_text()) if args.compare else None
    report_path = args.report.resolve() if args.report else None
    os.chdir(args.root.resolve())
    sys.path.insert(0, str(Path.cwd()))
    sys.dont_write_bytecode = True
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="host-tests-") as temporary:
        scratch = Path(temporary)
        # Imports may allocate temporary fixtures too; keep them on the same
        # case-sensitive scratch volume as all worker allocations.
        os.environ.update(TMPDIR=temporary, TEMP=temporary, TMP=temporary)
        tempfile.tempdir = temporary
        discovery_started = time.perf_counter()
        suite = unittest.TestLoader().discover("tests")
        discovered = [test.id() for test in leaves(suite)]
        modules = [(index, module_name(part, index), part) for index, part in enumerate(suite)]
        discovery_seconds = time.perf_counter() - discovery_started
        results, errors = run_pool(modules, args.workers, args.timeout, scratch)
    report = {
        "schema": 1,
        "workers": args.workers,
        "wall_seconds": time.perf_counter() - started,
        "discovery_seconds": discovery_seconds,
        "discovered_ids": discovered,
        "modules": results,
        "infrastructure_errors": errors,
    }
    differences = compare_reports(baseline, report) if baseline else []
    report["comparison_errors"] = differences
    report["successful"] = bool(discovered) and all(row["successful"] for row in results) and not errors and not differences
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    tests = [test for module in results for test in module["tests"]]
    outcomes = Counter(event["outcome"] for module in results for event in module["events"] if "subtest_index" not in event)
    print(f"Ran {sum(row['tests_run'] for row in results)} tests; {len(discovered)} discovered IDs; {len(results)} modules; {args.workers} worker(s)")
    print(f"Wall: {report['wall_seconds']:.3f}s (discovery {discovery_seconds:.3f}s); outcomes: {dict(sorted(outcomes.items()))}")
    for label, rows, key in (("tests", tests, "id"), ("modules (including fixtures)", results, "module")):
        print(f"Slowest {label}:")
        for row in sorted(rows, key=lambda row: row["seconds"], reverse=True)[: args.slowest]:
            print(f"  {row['seconds']:9.3f}s  {row[key]}")
    for module in results:
        if module["diagnostic"]:
            print(module["diagnostic"], file=sys.stderr)
        for event in module["events"]:
            if event["outcome"] in BAD_OUTCOMES:
                print(f"{event['outcome']}: {event['id']}\n{event.get('traceback', '')}", file=sys.stderr)
    for error in errors:
        print(f"Runner error: {error['module']}: {error['error']}", file=sys.stderr)
    for difference in differences:
        print(f"Comparison failed: {difference}", file=sys.stderr)
    if baseline is not None and not differences:
        print("Comparison passed: identical discovered IDs and unittest outcomes (including subtests).")
    print("OK" if report["successful"] else "FAILED")
    return 0 if report["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
