"""Wall phases and request-bounded Bee observations; overlapping work stays explicit."""

from collections import defaultdict
from contextlib import contextmanager
import json
from pathlib import Path
import time
import re


class PhaseTiming:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.phases = {}

    @contextmanager
    def phase(self, name):
        start = self.clock()
        try:
            yield
        finally:
            self.phases[name] = self.phases.get(name, 0.0) + self.clock() - start

    def report(self):
        return {"wall_seconds": self.clock() - self.started, "phases_seconds": dict(self.phases)}


def trace_events(path):
    # Bee writes a comma-separated stream, including a trailing comma, rather
    # than an enclosing array. Other versions emit normal Chrome trace JSON.
    raw = Path(path).read_text().strip().rstrip(",")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = json.loads("[" + raw + "]")
    return value.get("traceEvents", []) if isinstance(value, dict) else value


def bee_timing(project, start_epoch, end_epoch):
    groups = defaultdict(list)
    sources = []
    # backend_profiler and buildreport duplicate some events. Use the backend
    # only; parallel compiler time is reported as work and interval union.
    for path in sorted((Path(project) / "Library/Bee").glob("backend_profiler*.traceevents")):
        if path.stat().st_mtime < start_epoch:
            continue
        try:
            events = trace_events(path)
        except (ValueError, OSError):
            continue
        used = False
        for event in events:
            ts, duration = event.get("ts", 0) / 1e6, event.get("dur", 0) / 1e6
            if event.get("ph") != "X" or not start_epoch <= ts <= end_epoch or duration <= 0:
                continue
            name = event.get("name", "")
            group = next(
                (
                    label
                    for prefix, label in (
                        ("UnityLinker", "unity_linker"),
                        ("Il2Cpp", "il2cpp_codegen"),
                        ("IL2CPP", "il2cpp_codegen"),
                        ("C_Android", "cpp_compile"),
                        ("Link_Android", "native_link"),
                        ("Csc", "csharp_compile"),
                    )
                    if name.startswith(prefix)
                ),
                None,
            )
            if group:
                groups[group].append((ts, min(ts + duration, end_epoch)))
                used = True
        if used:
            sources.append(str(path))
    report = {}
    for group, intervals in groups.items():
        merged = []
        for begin, end in sorted(intervals):
            if merged and begin <= merged[-1][1]:
                merged[-1][1] = max(end, merged[-1][1])
            else:
                merged.append([begin, end])
        report[group] = {"jobs": len(intervals), "work_seconds": sum(b - a for a, b in intervals), "active_wall_seconds": sum(b - a for a, b in merged)}
    return {"sources": sources, "phases": report, "scope": "same-request backend events; parallel work overlaps; absent phases were not observed"}


def editor_log_cursor(work):
    try:
        path = Path(json.loads((Path(work) / "editor/lab-process.json").read_text())["log"])
        return path, path.stat().st_size
    except (OSError, ValueError, KeyError):
        return None


def editor_log_timing(cursor):
    if cursor is None:
        return {"observed": False}
    path, offset = cursor
    with path.open("rb") as stream:
        if stream.seek(0, 2) < offset:
            return {"observed": False, "reason": "editor log rotated"}
        stream.seek(offset)
        raw = stream.read()
    text = raw.decode(errors="replace")
    gradle = []
    for duration in re.findall(r"BUILD SUCCESSFUL in ([^\r\n]+)", text):
        terms = re.findall(r"([0-9.]+)(ms|h|m|s)", duration)
        if terms:
            gradle.append(sum(float(value) * {"ms": 0.001, "h": 3600, "m": 60, "s": 1}[unit] for value, unit in terms))
    return {
        "observed": True,
        "path": str(path),
        "byte_start": offset,
        "byte_end": offset + len(raw),
        "gradle_invocations_seconds": gradle,
        "scope": "request-bounded editor log; Gradle reports rounded elapsed seconds",
    }
