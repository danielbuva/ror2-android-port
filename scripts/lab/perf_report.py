"""Host-only analysis of session_sustained_check receipts; never accesses a device.

Periodic frame_ms is reciprocal averaged FPS, not an individual frame duration.
Raw frame quantiles require a complete, counter-reconciled optional sidecar.
Causal throttling onset remains unavailable.
"""

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct

from evidence_files import open_evidence

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
        hitch_bursts=None,
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
    bursts = longest = current = 0
    for ms in durations:
        if ms > 50:
            bursts += current == 0
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    worst_index = max(range(len(durations)), key=durations.__getitem__)
    result.update(
        complete=True,
        hitch_bursts=dict(
            threshold_ms=50,
            count=bursts,
            longest_frames=longest,
            worst_frame=result["first_frame"] + worst_index,
            worst_frame_ms=durations[worst_index],
            limitation="Strictly >50 ms consecutive frames within this reconciled window only; boundary bursts may extend outside it. Worst-frame ties use the earliest frame. No causal attribution.",
        ),
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
            name = fields[0].lower()
            key = "cpu_c" if name.startswith("cpu") else "gpu_c" if name.startswith("gpu") else None
            if key:
                try:
                    value = float(fields[1]) / 1000
                except ValueError:
                    continue
                # Match the sampler's unavailable low-reading cutoff.
                if math.isfinite(value) and value > -30:
                    groups[key].append(value)
        result.append(
            dict(
                utc_seconds=stamp(row["utc"]),
                **{key: max(values) if values else None for key, values in groups.items()},
                battery_c=row.get("battery", {}).get("celsius"),
            )
        )
    return sorted(result, key=lambda r: r["utc_seconds"])


def median(rows, key, *, allow_zero=False):
    values = [r[key] for r in rows if type(r.get(key)) in (int, float) and math.isfinite(r[key]) and (r[key] > 0 or (allow_zero and r[key] == 0))]
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


def proposed_pacing_comparison(window, quantiles, observed_seconds, required_seconds):
    """Compare retained observations with public-alpha's proposed targets only."""
    values = dict(
        average_fps=window["average_fps"] if window else None,
        **{f"p{p}_ms": quantiles[f"p{p}"] if quantiles else None for p in (50, 95, 99)},
        over50ms_percent=100 * window["over50ms"] / window["frames"] if window else None,
    )
    targets = dict(average_fps=60, p50_ms=16.67, p95_ms=33.334, p99_ms=50, over50ms_percent=1)
    metrics = {}
    for name, target in targets.items():
        value = values[name]
        minimum = name == "average_fps"
        metrics[name] = dict(
            observed=value,
            target=target,
            comparison=">=" if minimum else "<=",
            meets_target=None if value is None else value >= target if minimum else value <= target,
        )
    return dict(
        observed_seconds=observed_seconds,
        required_seconds=required_seconds,
        complete_duration=observed_seconds >= required_seconds,
        metrics=metrics,
    )


def camera_profile(session, completed):
    """Summarize retained recorder windows, without inventing per-frame attribution."""
    camera = completed["framePacing"]
    if completed["attempt"] != session["attempt"] or (camera.get("rawFrameTrace") or None) != (session.get("raw_frame_trace") or {}).get("file"):
        raise ValueError("Completed camera report belongs to a different sustained session")
    first, last = session["samples"][0], session["samples"][-1]
    # Each camera row contains means since the preceding row. Do not admit a
    # partial boundary window, weight every row equally, or count repeated copies.
    windows = [(a, b) for a, b in zip(camera["samples"], camera["samples"][1:]) if first["pacing_frames"] <= a["frames"] < b["frames"] <= last["pacing_frames"]]
    metrics = {}
    for name, value, count in (
        ("cpu_frame_ms", "sampledCpuMs", "frameTimingSamples"),
        ("gpu_frame_ms", "sampledGpuMs", "gpuTimingSamples"),
        ("main_thread_ms", "sampledMainActiveMs", "mainTimingSamples"),
        ("render_thread_ms", "sampledRenderActiveMs", "renderTimingSamples"),
        ("gc_allocated_bytes", "sampledGcAllocBytes", "gcAllocSamples"),
        ("draw_calls", "sampledDrawCalls", "renderCounterSamples"),
        ("setpass_calls", "sampledSetPassCalls", "renderCounterSamples"),
        ("vertices", "sampledVertices", "renderCounterSamples"),
    ):
        rows = [b for _, b in windows if b.get(count, 0) > 0]
        total = sum(row[count] for row in rows)
        metrics[name] = dict(
            samples=total,
            windows=len(rows),
            positive_windows=sum(row[value] > 0 for row in rows),
            weighted_mean=sum(row[value] * row[count] for row in rows) / total if total else None,
        )
    start, end = (windows[0][0], windows[-1][1]) if windows else (None, None)
    return dict(
        windows=len(windows),
        first_frame=start["frames"] + 1 if start else None,
        last_frame=end["frames"] if end else None,
        observed_seconds=end["seconds"] - start["seconds"] if start else 0,
        gc_collections=sum(b["gcCollections"] - a["gcCollections"] for a, b in windows),
        metrics=metrics,
        limitations=[
            "Only complete retained camera windows inside the sustained frame endpoints are included; boundary windows are excluded.",
            "Means are weighted by recorder sample counts, not frames; CPU/GPU, thread and allocation recorders sample at different cadences.",
            "Main/Render Thread recorder durations do not separate work from waits or name simulation/render-submission costs.",
            "All-zero render timings cannot distinguish an idle thread from an unavailable duration; they do not establish zero rendering cost.",
            "Allocation bytes and collection counts are not GC duration; no per-hitch or causal GC attribution is available.",
        ],
    )


def clock_cooling_summary(samples):
    """Describe retained sensor readings without inferring thermal causation."""
    times = [row["host_seconds"] for row in samples]

    def summarize(values, unit, cooling=False):
        values = [value if type(value) is int and (value >= 0 if cooling else value > 0) else None for value in values]
        observed = [(time, value) for time, value in zip(times, values) if value is not None]
        return dict(
            unit=unit,
            valid_samples=len(observed),
            missing_samples=len(values) - len(observed),
            minimum=min((value for _, value in observed), default=None),
            maximum=max((value for _, value in observed), default=None),
            first_host_seconds=observed[0][0] if observed else None,
            last_host_seconds=observed[-1][0] if observed else None,
            largest_unobserved_gap_seconds=max(b - a for a, b in zip([times[0], *[t for t, _ in observed]], [*[t for t, _ in observed], times[-1]])),
            adjacent_observed_changes=sum(a is not None and b is not None and a != b for a, b in zip(values, values[1:])),
        )

    channels = {}
    for field, unit in (("cpu_frequency_khz", "kHz"), ("cpu_limit_khz", "kHz"), ("cooling_states", "state index")):
        mappings = [row.get(field) if isinstance(row.get(field), dict) else {} for row in samples]
        names = sorted({name for mapping in mappings for name in mapping if isinstance(name, str)})
        channels[field] = {name: summarize([mapping.get(name) for mapping in mappings], unit, field == "cooling_states") for name in names}
    for field in ("gpu_frequency_hz", "gpu_limit_hz"):
        channels[field] = summarize([row.get(field) for row in samples], "Hz")
    return dict(
        channels=channels,
        limitations=[
            "These are sampled sensor observations, not time-weighted clocks or residency. Missing readings are not zero; changes across missing samples are not counted.",
            "CPU policies and cooling devices are reported separately. Cooling state indices are device-specific, not temperatures or comparable severity levels.",
            "Clock/limit drops or cooling changes do not establish thermal causation or throttling onset; workload, power policy and external power can confound them.",
        ],
    )


def energy_summary(samples):
    """Summarize sampled battery-terminal observations, never device energy use."""

    def numeric(value):
        return type(value) in (int, float) and math.isfinite(value)

    times = [row["host_seconds"] for row in samples]
    sources = [row.get("battery_external_power") if type(row.get("battery_external_power")) is bool else None for row in samples]
    metrics = {key: [] for key in ("power_mw", "charge_uah", "level_percent")}
    for row in samples:
        current, voltage = row.get("battery_current_ua"), row.get("battery_voltage_uv")
        power = current * voltage / 1_000_000_000 if numeric(current) and numeric(voltage) and voltage > 0 else None
        metrics["power_mw"].append(power if numeric(power) else None)
        charge, level = row.get("battery_charge_uah"), row.get("battery_level_percent")
        metrics["charge_uah"].append(charge if numeric(charge) and charge >= 0 else None)
        metrics["level_percent"].append(level if numeric(level) and 0 <= level <= 100 else None)

    def coverage(values):
        observed = [time for time, value in zip(times, values) if value is not None]
        return dict(
            valid_samples=len(observed),
            missing_samples=len(values) - len(observed),
            first_host_seconds=observed[0] if observed else None,
            last_host_seconds=observed[-1] if observed else None,
            largest_unobserved_gap_seconds=max(b - a for a, b in zip([times[0], *observed], [*observed, times[-1]])),
        )

    def delta(values):
        return values[-1] - values[0] if values[0] is not None and values[-1] is not None else None

    plugged = sum(value is True for value in sources)
    unplugged = sum(value is False for value in sources)
    source = (
        "mixed"
        if plugged and unplugged
        else "externally-powered"
        if plugged == len(sources)
        else "observed-unplugged"
        if unplugged == len(sources)
        else "incomplete"
    )
    power = [value for value in metrics["power_mw"] if value is not None]
    return dict(
        power_source=source,
        externally_powered_samples=plugged,
        unplugged_samples=unplugged,
        unknown_power_source_samples=len(sources) - plugged - unplugged,
        observed_power_source_transitions=sum(a is not None and b is not None and a != b for a, b in zip(sources, sources[1:])),
        power_source_coverage=coverage(sources),
        coverage={key: coverage(values) for key, values in metrics.items()},
        signed_battery_terminal_power_mw=dict(
            sample_mean=statistics.fmean(power) if power else None, minimum=min(power) if power else None, maximum=max(power) if power else None
        ),
        charge_change_uah=delta(metrics["charge_uah"]),
        level_change_percentage_points=delta(metrics["level_percent"]),
        unplugged_energy_qualified=False,
        limitations=[
            "Power is sampled current times voltage at the battery terminals, retaining the source sign convention; it is not total device or wall power.",
            "Power mean uses equal observation weights, not time weights or integrated energy. Gaps and power-source transitions are not interpolated.",
            "Charge/level changes are last minus first retained session endpoints only; missing endpoints remain unavailable. Gauge resets or recalibration are not distinguished from charge changes.",
            "Observed-unplugged means every retained power-source sample was false, not proof of uninterrupted unplugged operation between samples. External power may coexist with battery discharge.",
            "These observations do not qualify an unplugged energy budget or establish causal thermal throttling.",
        ],
    )


def analyze(session, thermal, raw_trace=None, completed=None):
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
    above80 = classified = 0
    for row, gap in zip(heat, gaps):
        if not 0 < gap <= 1:
            continue
        channels = (row["cpu_c"], row["gpu_c"])
        # One hot group establishes an exceedance; ruling one out requires
        # readings from both groups. A retained row alone is not coverage.
        hot = any(value is not None and value > 80 for value in channels)
        if hot or all(value is not None for value in channels):
            classified += gap
            if hot:
                above80 += gap
    # Host elapsed time is recorded before reading the runtime snapshot. Use
    # snapshot UTC, not host elapsed, to pair FPS observations with thermal UTC.
    runtime_bins = defaultdict(list)
    thermal_bins = defaultdict(list)
    for row in samples:
        runtime_bins[math.floor((stamp(row["snapshot_utc"]) - start) / 300) * 300].append(row)
    for row in heat:
        thermal_bins[math.floor((row["utc_seconds"] - start) / 300) * 300].append(row)
    bins = [
        dict(
            start_seconds=begin,
            samples=len(rows),
            live_enemies=median(rows, "live_enemies", allow_zero=True),
            **{key: median(rows, key) for key in ("fps", "cpu_frame_ms", "gpu_frame_ms")},
            **{key: median(thermal_bins.get(begin, ()), key) for key in ("cpu_c", "gpu_c", "battery_c")},
        )
        for begin, rows in sorted(runtime_bins.items())
    ]
    statuses = [r for r in samples if type(r.get("thermal_status")) is int and r["thermal_status"] > 0]
    report = dict(
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
        camera_profile=camera_profile(session, completed) if completed is not None else None,
        energy=energy_summary(samples),
        clock_cooling=clock_cooling_summary(samples),
        thermal=dict(
            samples=len(heat),
            max_gap_seconds=max(gaps) if gaps else None,
            gaps_over_one_second=sum(gap > 1 for gap in gaps),
            boundary_uncovered_seconds=(heat[0]["utc_seconds"] - start + end - heat[-1]["utc_seconds"]) if heat else end - start,
            threshold_observed_seconds=classified,
            threshold_unobserved_seconds=max(0, end - start - classified),
            time_above80_observed_seconds=above80 if classified else None,
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
            "Five-minute bins use elapsed UTC from the first runtime snapshot for both runtime and thermal rows; counter windows still use host observations.",
            "Final ten-minute counters use the first retained observation inside the last 600 host seconds; uncovered boundary time is reported, never interpolated.",
            "Thermal exposure uses the left sample across gaps <=1 s. One hot CPU/GPU group counts above 80 C; a non-hot interval needs both groups. Other time is unclassified.",
            "This report does not attribute clock changes to thermal limits. Battery-terminal observations do not qualify an unplugged energy budget.",
        ],
    )
    report["proposed_pacing_budget"] = dict(
        qualification="Observation comparison only; proposed targets do not establish release readiness.",
        whole_session=proposed_pacing_comparison(window, report["true_frame_time_percentiles_ms"], report["observed_seconds"], 1800),
        covered_tail=proposed_pacing_comparison(tail["frame_window"], tail["true_frame_time_percentiles_ms"], tail["observed_seconds"], 600),
        evidence_not_established=[
            "Representative ordinary play on every supported stage, with assistance state recorded.",
            "Visual fidelity against the original.",
            "Unplugged battery drain and an accepted energy budget.",
            "Clock/limit evidence for causal throttling attribution.",
            "Causal raw-capture overhead qualification.",
        ],
    )
    return report


def markdown(report):
    window = report["frame_window"]
    proxy = report["periodic_frame_mean_ms"]

    def fmt(value):
        return "unavailable" if value is None else f"{value:.2f}"

    tail = report["final_ten_minutes"]
    thermal = report["thermal"]
    above80 = thermal["time_above80_observed_seconds"]
    unclassified = thermal["threshold_unobserved_seconds"]
    exposure = (
        f"time above 80 C unavailable; {unclassified:.3f} s unclassified"
        if above80 is None
        else f"{above80:.3f} s above 80 C; {thermal['threshold_observed_seconds']:.3f} s classified; {unclassified:.3f} s unclassified"
    )

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
    budget = report["proposed_pacing_budget"]
    budget_lines = [budget["qualification"], "", "| Observation | Metric | Measured | Proposed target | Comparison |", "| --- | --- | --- | --- | --- |"]
    for label, key in (("Whole session", "whole_session"), ("Covered tail", "covered_tail")):
        comparison = budget[key]
        for name, metric in comparison["metrics"].items():
            status = "unavailable" if metric["meets_target"] is None else "within target" if metric["meets_target"] else "outside target"
            budget_lines.append(f"| {label} | {name} | {fmt(metric['observed'])} | {metric['comparison']} {metric['target']} | {status} |")
    budget_lines += [
        "",
        "A partial covered tail retains measured FPS/hitches; full-tail quantile comparisons remain unavailable.",
        "This report does not establish: " + " ".join(budget["evidence_not_established"]),
    ]
    camera = report["camera_profile"]
    camera_lines = ["Camera recorder attribution: unavailable (completed native report not supplied)."]
    if camera is not None:
        camera_lines = [
            f"Camera recorder coverage: {camera['windows']} complete windows, {camera['observed_seconds']:.3f} s; "
            f"frames {camera['first_frame']}–{camera['last_frame']}; {camera['gc_collections']} GC collections.",
            "",
            "| Recorder | Sample-weighted mean | Samples | Positive windows / measured windows |",
            "| --- | --- | --- | --- |",
        ]
        for name, metric in camera["metrics"].items():
            camera_lines.append(f"| {name} | {fmt(metric['weighted_mean'])} | {metric['samples']} | {metric['positive_windows']} / {metric['windows']} |")
        camera_lines += ["", *camera["limitations"]]
    energy = report["energy"]
    energy_lines = [
        "## Battery observations (not energy qualification)",
        f"Power source: {energy['power_source']}; external power observed in {energy['externally_powered_samples']} samples, "
        f"unplugged in {energy['unplugged_samples']}, unknown in {energy['unknown_power_source_samples']}; "
        f"adjacent observed transitions: {energy['observed_power_source_transitions']}.",
        f"Signed battery-terminal power sample mean: {fmt(energy['signed_battery_terminal_power_mw']['sample_mean'])} mW (equal observation weights).",
        f"Endpoint charge change: {fmt(energy['charge_change_uah'])} uAh; level change: {fmt(energy['level_change_percentage_points'])} percentage points (last minus first).",
    ]
    for name, measured in {"power_source": energy["power_source_coverage"], **energy["coverage"]}.items():
        energy_lines.append(
            f"{name}: {measured['valid_samples']} valid / {measured['missing_samples']} missing samples; largest unobserved gap {fmt(measured['largest_unobserved_gap_seconds'])} s."
        )
    energy_lines.extend(energy["limitations"])
    sensors = report["clock_cooling"]
    sensor_lines = ["## Clock and cooling observations (not throttling attribution)"]
    for field, channels in sensors["channels"].items():
        rows = {field: channels} if field.startswith("gpu_") else {f"{field}/{name}": value for name, value in channels.items()}
        if not rows:
            sensor_lines.append(f"{field}: unavailable (no retained channels).")
        for name, measured in rows.items():
            sensor_lines.append(
                f"{name}: min/max {fmt(measured['minimum'])}/{fmt(measured['maximum'])} {measured['unit']}; "
                f"{measured['valid_samples']} valid / {measured['missing_samples']} missing; "
                f"largest gap {fmt(measured['largest_unobserved_gap_seconds'])} s; adjacent changes {measured['adjacent_observed_changes']}."
            )
    sensor_lines.extend(sensors["limitations"])
    hitch_lines = []
    for label, raw in (("Whole counter window", report.get("raw_frame_window")), ("Covered tail", tail.get("raw_frame_window"))):
        bursts = (raw or {}).get("hitch_bursts")
        if bursts is None:
            hitch_lines.append(f"{label} hitch bursts: unavailable (no complete reconciled raw window).")
        else:
            hitch_lines.append(
                f"{label} >50 ms hitch bursts: {bursts['count']}; longest {bursts['longest_frames']} frames; "
                f"worst frame {bursts['worst_frame']} at {fmt(bursts['worst_frame_ms'])} ms."
            )
            hitch_lines.append(bursts["limitation"])
    lines = [
        "# Sustained game performance report",
        "",
        f"Scope: {report['scope'] or 'unspecified; workload qualification unavailable'}",
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
        *hitch_lines,
        f"CPU/GPU thermal exposure: {exposure}.",
        "Throttling onset: unestablished by this report.",
        "",
        *budget_lines,
        "",
        *camera_lines,
        "",
        *energy_lines,
        "",
        *sensor_lines,
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
    parser.add_argument("--completed-session", type=Path, help="Optional completed native report containing retained camera recorder windows")
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
    completed = json.loads(args.completed_session.read_text()) if args.completed_session else None
    thermal_hash = hashlib.sha256()
    thermal = []
    with open_evidence(args.thermal) as stream:
        for line in stream:
            thermal_hash.update(line)
            if line.strip():
                thermal.append(json.loads(line))
    report = analyze(session, thermal, raw_trace, completed)
    report["input_sha256"] = {"session": hashlib.sha256(args.session.read_bytes()).hexdigest(), "thermal": thermal_hash.hexdigest()}
    if raw_hash:
        report["input_sha256"]["raw_frames"] = raw_hash
    if args.completed_session:
        report["input_sha256"]["completed_session"] = hashlib.sha256(args.completed_session.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    args.output.with_suffix(".md").write_text(markdown(report))


if __name__ == "__main__":
    main()
