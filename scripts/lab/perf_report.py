"""Host-only analysis of session_sustained_check receipts; never accesses a device.

Periodic frame_ms is reciprocal averaged FPS, not an individual frame duration.
Raw frame quantiles require a complete, counter-reconciled optional sidecar.
Causal throttling onset remains unavailable.
"""

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct

RAW_HEADER = struct.Struct("<8siiii")
RAW_CAPACITY = 262144
HITCH33_MS = struct.unpack("<f", struct.pack("<f", 33.334))[0]


def read_raw_frames(data):
    if len(data) < RAW_HEADER.size:
        raise ValueError("Truncated raw frame header")
    magic, first, count, last, dropped = RAW_HEADER.unpack_from(data)
    if (
        magic != b"ROR2FRAM"
        or first < 1
        or not 0 <= count <= RAW_CAPACITY
        or dropped < 0
        or last != first + count + dropped - 1
        or len(data) != RAW_HEADER.size + count * 4
    ):
        raise ValueError("Invalid raw frame coverage/header")
    durations = [row[0] for row in struct.iter_unpack("<f", data[RAW_HEADER.size :])]
    if any(not math.isfinite(ms) or ms < 0 for ms in durations):
        raise ValueError("Invalid raw frame duration")
    return dict(first_frame=first, last_frame=last, retained_frames=count, dropped_frames=dropped, durations_ms=durations)


def raw_frame_window(first, last, trace):
    begin = first["pacing_frames"] + 1 - trace["first_frame"]
    end = last["pacing_frames"] + 1 - trace["first_frame"]
    result = dict(
        first_frame=first["pacing_frames"] + 1,
        last_frame=last["pacing_frames"],
        complete=False,
        percentiles_ms=None,
    )
    if begin < 0 or end > trace["retained_frames"]:
        result["reason"] = "Raw capture does not cover every frame in this counter window"
        return result
    if first.get("pacing_total_ms_exact") is not True or last.get("pacing_total_ms_exact") is not True:
        raise ValueError("Raw reconciliation requires exact cumulative duration counters")
    durations = trace["durations_ms"][begin:end]
    window = frame_window(first, last)
    if (
        len(durations) != window["frames"]
        or sum(ms > HITCH33_MS for ms in durations) != window["over33ms"]
        or sum(ms > 50 for ms in durations) != window["over50ms"]
        or not math.isclose(sum(durations), last["pacing_total_ms"] - first["pacing_total_ms"], rel_tol=1e-12, abs_tol=1e-5)
    ):
        raise ValueError("Raw durations do not reconcile with frame/duration/hitch counters")
    result.update(
        complete=True,
        frames=len(durations),
        total_ms=sum(durations),
        over33ms=window["over33ms"],
        over50ms=window["over50ms"],
        percentiles_ms=dict(samples=len(durations), **{f"p{p}": percentile(durations, p) for p in (50, 95, 99)}),
    )
    return result


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def percentile(values, percent):
    """Linear interpolation at (n - 1) * p; never weight periodic rows as frames."""
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * percent / 100
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def distribution(values):
    values = [v for v in values if type(v) in (int, float) and math.isfinite(v) and v > 0]
    return dict(samples=len(values), **{f"p{p}": percentile(values, p) for p in (50, 95, 99)})


def thermal_samples(rows):
    result = []
    for row in rows:
        if row.get("admission") is not False:
            continue
        groups = {"cpu_c": [], "gpu_c": []}
        for line in row.get("all_zones_raw", "").splitlines():
            fields = line.split("\t")
            if len(fields) < 2:
                continue
            key = "cpu_c" if fields[0].startswith("cpu") else "gpu_c" if fields[0].startswith("gpu") else None
            if key and fields[1] != "UNREADABLE":
                value = float(fields[1]) / 1000
                if math.isfinite(value):
                    groups[key].append(value)
        result.append(
            dict(
                utc_seconds=stamp(row["utc"]),
                **{key: max(values) if values else None for key, values in groups.items()},
                battery_c=row.get("battery", {}).get("celsius"),
            )
        )
    return sorted(result, key=lambda r: r["utc_seconds"])


def median(rows, key):
    values = [r[key] for r in rows if type(r.get(key)) in (int, float) and math.isfinite(r[key]) and r[key] > 0]
    return statistics.median(values) if values else None


def frame_window(first, last):
    frames = last["pacing_frames"] - first["pacing_frames"]
    total_ms = last["pacing_total_ms"] - first["pacing_total_ms"]
    if frames <= 0 or total_ms <= 0:
        raise ValueError("No advancing frame window")
    over33 = last["pacing_over33"] - first["pacing_over33"]
    over50 = last["pacing_over50"] - first["pacing_over50"]
    if not 0 <= over50 <= over33 <= frames:
        raise ValueError("Inconsistent hitch counters")
    return dict(frames=frames, mean_ms=total_ms / frames, average_fps=frames * 1000 / total_ms, over33ms=over33, over50ms=over50)


def final_ten_minutes(samples):
    last = samples[-1]
    requested_start = last["host_seconds"] - 600
    # Use only retained endpoints inside the requested window; never invent counters.
    rows = [row for row in samples if row["host_seconds"] >= requested_start]
    first = rows[0]
    observed = last["host_seconds"] - first["host_seconds"]
    window = frame_window(first, last) if len(rows) >= 2 else None
    return dict(
        requested_seconds=600,
        start_host_seconds=first["host_seconds"],
        end_host_seconds=last["host_seconds"],
        observed_seconds=observed,
        boundary_uncovered_seconds=600 - observed,
        observations=len(rows),
        frame_window=window,
        over33ms_percent=100 * window["over33ms"] / window["frames"] if window else None,
        over50ms_percent=100 * window["over50ms"] / window["frames"] if window else None,
    )


def analyze(session, thermal, raw_trace=None):
    samples = session["samples"]
    if len(samples) < 2:
        raise ValueError("At least two periodic observations are required")
    for previous, current in zip(samples, samples[1:]):
        if current["host_seconds"] <= previous["host_seconds"] or stamp(current["snapshot_utc"]) <= stamp(previous["snapshot_utc"]):
            raise ValueError("Observations must advance in host and snapshot time")
        if any(current[key] < previous[key] for key in ("pacing_frames", "pacing_total_ms", "pacing_over33", "pacing_over50")):
            raise ValueError("Pacing counters reset; split sessions before analysis")
    first, last = samples[0], samples[-1]
    window = frame_window(first, last)
    tail = final_ten_minutes(samples)
    raw_window = None
    raw_coverage = None
    tail["true_frame_time_percentiles_ms"] = None
    if raw_trace is not None:
        binding = session.get("raw_frame_trace") or {}
        if not binding.get("file") or any(row.get("pacing_trace") != binding["file"] for row in samples):
            raise ValueError("Raw trace identity differs from observation counters")
        raw_coverage = {key: value for key, value in raw_trace.items() if key != "durations_ms"}
        # Reconcile each retained interval, not just a coincidentally matching total.
        for a, b in zip(samples, samples[1:]):
            raw_frame_window(a, b, raw_trace)
        raw_window = raw_frame_window(first, last, raw_trace)
        if tail["frame_window"]:
            tail_first = next(row for row in samples if row["host_seconds"] == tail["start_host_seconds"])
            tail["raw_frame_window"] = raw_frame_window(tail_first, last, raw_trace)
            if tail["boundary_uncovered_seconds"] == 0:
                tail["true_frame_time_percentiles_ms"] = tail["raw_frame_window"]["percentiles_ms"]
    start, end = stamp(first["snapshot_utc"]), stamp(last["snapshot_utc"])
    heat = [r for r in thermal_samples(thermal) if start <= r["utc_seconds"] <= end]
    gaps = [b["utc_seconds"] - a["utc_seconds"] for a, b in zip(heat, heat[1:])]
    above80 = 0
    for a, b in zip(heat, heat[1:]):
        gap = b["utc_seconds"] - a["utc_seconds"]
        if gap <= 1 and max(a["cpu_c"] or 0, a["gpu_c"] or 0) > 80:
            above80 += gap
    bins = []
    for begin in range(0, math.floor(last["host_seconds"] / 300) * 300 + 1, 300):
        rows = [r for r in samples if begin <= r["host_seconds"] < begin + 300]
        temperatures = [r for r in heat if begin <= r["utc_seconds"] - start < begin + 300]
        if rows:
            bins.append(
                dict(
                    start_seconds=begin,
                    samples=len(rows),
                    **{key: median(rows, key) for key in ("fps", "cpu_frame_ms", "gpu_frame_ms", "live_enemies")},
                    **{key: median(temperatures, key) for key in ("cpu_c", "gpu_c", "battery_c")},
                )
            )
    statuses = [r for r in samples if type(r.get("thermal_status")) is int and r["thermal_status"] > 0]
    return dict(
        scope=session.get("scope"),
        apk_sha256=session.get("apk_sha256"),
        observations=len(samples),
        observed_seconds=last["host_seconds"] - first["host_seconds"],
        frame_window=window,
        final_ten_minutes=tail,
        raw_frame_coverage=raw_coverage,
        raw_frame_window=raw_window,
        true_frame_time_percentiles_ms=raw_window["percentiles_ms"] if raw_window else None,
        periodic_frame_mean_ms=distribution([r.get("frame_ms") for r in samples]),
        periodic_fps=distribution([r.get("fps") for r in samples]),
        cpu_frame_ms=distribution([r.get("cpu_frame_ms") for r in samples]),
        gpu_frame_ms=distribution([r.get("gpu_frame_ms") for r in samples]),
        thermal=dict(
            samples=len(heat),
            max_gap_seconds=max(gaps) if gaps else None,
            gaps_over_one_second=sum(gap > 1 for gap in gaps),
            boundary_uncovered_seconds=(heat[0]["utc_seconds"] - start + end - heat[-1]["utc_seconds"]) if heat else end - start,
            time_above80_observed_seconds=above80,
            **{f"peak_{key}": max((r[key] for r in heat if r[key] is not None), default=None) for key in ("cpu_c", "gpu_c", "battery_c")},
        ),
        first_nonzero_hal_status_seconds=statuses[0]["host_seconds"] if statuses else None,
        hal_status_samples=sum(type(r.get("thermal_status")) is int for r in samples),
        throttling_onset_seconds=None,
        bins=bins,
        limitations=[
            "Periodic frame_ms is reciprocal averaged FPS; its quantiles are not individual-frame quantiles.",
            "Raw quantiles require complete frame coverage and reconciled counters; final-ten-minute quantiles also require all 600 host seconds.",
            "Raw durations are Unity unscaled active-frame intervals, not compositor presentation or synchronized CPU/GPU samples.",
            "Hitches are frame counts, not distinct hitch episodes; >50 ms is a subset of >33.334 ms. Startup counters are subtracted.",
            "CPU/GPU timings are latest FrameTimingManager observations, not a synchronized per-frame critical-path trace.",
            "Five-minute thermal bins align snapshot UTC with thermal UTC; runtime counter window uses first/last host observations.",
            "Final ten-minute counters use the first retained observation inside the last 600 host seconds; uncovered boundary time is reported, never interpolated.",
            "Thermal exposure uses left-sample hold only across gaps <=1 s; uncovered boundaries and longer gaps are unmeasured.",
            "No clocks or scheduler trace: HAL status alone cannot establish or exclude throttling. Battery drain is unmeasured while plugged in.",
        ],
    )


def markdown(report):
    window = report["frame_window"]
    proxy = report["periodic_frame_mean_ms"]

    def fmt(value):
        return "unavailable" if value is None else f"{value:.2f}"

    tail = report["final_ten_minutes"]

    def quantile_line(label, values):
        if values is None:
            return label + ": unavailable (raw capture or complete window coverage absent)."
        return label + f": {fmt(values['p50'])}/{fmt(values['p95'])}/{fmt(values['p99'])} ms ({values['samples']} frames)."

    tail_window = tail["frame_window"]
    tail_lines = [
        f"Final ten-minute coverage: {tail['observed_seconds']:.3f}/600 s; {tail['boundary_uncovered_seconds']:.3f} s uncovered; "
        f"retained endpoints {tail['start_host_seconds']:.3f}–{tail['end_host_seconds']:.3f} host s.",
    ]
    if tail_window:
        tail_lines.append(
            f"Covered tail: {tail_window['frames']} frames, {tail_window['mean_ms']:.3f} ms ({tail_window['average_fps']:.3f} FPS); "
            f">33.334 ms: {tail_window['over33ms']} ({tail['over33ms_percent']:.3f}%); "
            f">50 ms: {tail_window['over50ms']} ({tail['over50ms_percent']:.3f}%)."
        )
    else:
        tail_lines.append("Final ten-minute frame statistics: unavailable (fewer than two retained observations inside the window).")
    lines = [
        "# Sustained game performance report",
        "",
        f"{report['observations']} observations over {report['observed_seconds']:.1f} s; {window['frames']} counter-window frames.",
        f"Mean {window['mean_ms']:.3f} ms ({window['average_fps']:.3f} FPS).",
        f"Hitch frames >33.334 ms: {window['over33ms']} ({100 * window['over33ms'] / window['frames']:.3f}%); "
        f">50 ms: {window['over50ms']} ({100 * window['over50ms'] / window['frames']:.3f}%).",
        "",
        *tail_lines,
        "",
        quantile_line("Covered-tail individual-frame p50/p95/p99", (tail.get("raw_frame_window") or {}).get("percentiles_ms")),
        quantile_line("Individual-frame p50/p95/p99", report["true_frame_time_percentiles_ms"]),
        quantile_line("Final ten-minute individual-frame p50/p95/p99", tail["true_frame_time_percentiles_ms"]),
        f"Periodic frame-mean p50/p95/p99: {fmt(proxy['p50'])}/{fmt(proxy['p95'])}/{fmt(proxy['p99'])} ms (equal observation weights).",
        "Throttling onset: unestablished; no clocks/scheduler trace retained.",
        "",
        "| Start (min) | Samples | Median FPS | CPU ms | GPU ms | CPU C | GPU C | Battery C | Enemies |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["bins"]:
        lines.append(
            "| "
            + " | ".join(
                [fmt(row["start_seconds"] / 60), str(row["samples"])]
                + [fmt(row[key]) for key in ("fps", "cpu_frame_ms", "gpu_frame_ms", "cpu_c", "gpu_c", "battery_c", "live_enemies")]
            )
            + " |"
        )
    lines += ["", *[f"- {item}" for item in report["limitations"]], ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="session_sustained_check result.json")
    parser.add_argument("thermal", type=Path, help="session-sustained-thermal.jsonl")
    parser.add_argument("--output", type=Path, required=True, help="Local JSON output; adjacent Markdown is also written")
    parser.add_argument("--raw-frames", type=Path, help="Optional session-bound frame-times sidecar")
    args = parser.parse_args()
    session = json.loads(args.session.read_text())
    raw_trace = None
    raw_hash = None
    if args.raw_frames:
        data = args.raw_frames.read_bytes()
        raw_hash = hashlib.sha256(data).hexdigest()
        if raw_hash != (session.get("raw_frame_trace") or {}).get("sha256"):
            raise ValueError("Raw frame sidecar hash differs from retained session")
        raw_trace = read_raw_frames(data)
    report = analyze(session, [json.loads(line) for line in args.thermal.read_text().splitlines() if line.strip()], raw_trace)
    report["input_sha256"] = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in (("session", args.session), ("thermal", args.thermal))}
    if raw_hash:
        report["input_sha256"]["raw_frames"] = raw_hash
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    args.output.with_suffix(".md").write_text(markdown(report))


if __name__ == "__main__":
    main()
