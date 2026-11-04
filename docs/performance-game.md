# Sustained game performance baseline

Host analysis, 2026-11-04 UTC, of retained 2026-10-31 Main Nova evidence.
This is an assisted first-stage observation: invincibility, neutral movement and
small camera drags; composed renderer, 120 Hz display. It does not qualify normal
play, visual parity, battery efficiency or the performance release gate.

## Reproduction and measurement limits

`scripts/lab/perf_report.py` consumes the existing sustained owner's `result.json`
and the supervisor's `session-sustained-thermal.jsonl`. It writes local JSON and
Markdown, including input SHA-256 values, counter deltas, periodic percentiles,
five-minute FPS/temperature tables and thermal coverage. No device access occurs.

```sh
python3 scripts/lab/perf_report.py RESULT_JSON THERMAL_JSONL --output work/perf/report.json
```

Local source: `work/coordination/alpha-sustained-current-device-20261031T214907Z/`;
`terminal.done.json` names the sustained result. `metrics.private.json` corroborates
the counter deltas. Analysis: `work/coordination/perf-game-1104/report.json`.
Input result SHA-256: `da410b8fa3e5e0786b3823d031647a2909605bfc6d78a0c1f994acb6900521a9`;
thermal SHA-256: `5710ec0d7a0f2c0cfbe71fb763273ba08602a7d5534009893fabb66587ad6a31`.
APK: `d9009691ddccbefb3bdca3aad45bf5120dd011ccb2de66056c9a591a636b038a`.

`LabDiagnostics` averages FPS over at least two seconds and sets `frameMs` to
its reciprocal. CPU/GPU timings are the latest `FrameTimingManager` observation,
sampled separately. The sustained owner observes roughly every seven seconds;
report counters and snapshots are not atomic. `AndroidPresentationCamera` counts
actual active frames above 33.334 and 50 ms, excluding suspension/resume frames.
Its retained 30-second windows contain aggregates, not raw frame durations.

Consequently **individual-frame p50/p95/p99 are unavailable**. Percentiles below
describe 261 periodic interval means with equal observation weights and linear
interpolation at `(n - 1) * p`. They cannot qualify a frame-pacing budget. The
startup-inclusive lifetime maximum is deliberately excluded.

## Measured baseline

Observation spans 1,803.151 s. First/last cumulative counter subtraction gives
88,421 frames, 20.383 ms mean and 49.061 average FPS. Periodic FPS ranges from
27.19 to 100.22, with median 49.86.

| Measurement | p50 | p95 | p99 |
| --- | --- | --- | --- |
| Periodic interval-mean frame time (ms) | 20.06 | 33.57 | 35.54 |
| Latest sampled CPU frame time (ms) | 19.61 | 36.36 | 42.72 |
| Latest sampled GPU frame time (ms) | 9.86 | 12.00 | 12.06 |

Hitch counters: **4,142 frames >33.334 ms (4.684%)**, including **1,359 frames
>50 ms (1.537%)**. These count frames, not separate hitch episodes. Their timing
and longest active-frame duration cannot be recovered from cumulative counters.

Five-minute medians, aligned by snapshot and thermal UTC; temperatures are maxima
across the readable CPU or GPU zones at each thermal sample:

| Minutes | Observations | FPS | CPU ms | GPU ms | CPU C | GPU C | Battery C |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0–5 | 44 | 60.20 | 17.65 | 11.80 | 74.1 | 67.7 | 36 |
| 5–10 | 43 | 31.41 | 33.25 | 11.93 | 67.4 | 60.3 | 38 |
| 10–15 | 42 | 52.35 | 18.94 | 9.51 | 71.3 | 63.9 | 39 |
| 15–20 | 43 | 52.35 | 18.75 | 9.57 | 72.1 | 65.0 | 40 |
| 20–25 | 45 | 50.15 | 18.99 | 9.85 | 72.5 | 65.2 | 41 |
| 25–30 | 43 | 48.26 | 20.32 | 9.95 | 72.5 | 65.4 | 41 |

The final observation at 1,803 s is a separate partial bin (51.15 FPS).
The slowest block has lower CPU/GPU temperatures than the first block; this
correlation does not establish a thermal cause or exclude clock limiting.

The UTC observation window contains 4,709 thermal samples, maximum gap 0.634 s,
no gaps above one second and 0.464 s total uncovered at its boundaries. Peaks:
CPU 82.0 C, GPU 76.3 C, battery 42.0 C. Left-sample hold across covered intervals
records 1.168 s above 80 C. The supervisor's wider startup/teardown interval
instead reports 84.0 C and 5.753 s above 80 C; these are different windows.
**Throttling onset is unestablished**: all 261 sampled HAL statuses are zero,
and no frequency, scheduler or limit-state trace was retained. Zero HAL status
does not exclude throttling. Heat is an improvement metric; the safety policy
remains CPU/GPU >95 C for at least three seconds or battery >=43 C, with runtime
sample gaps >1 s invalidating the trace.

Battery was plugged in at the 80% charge limit: unchanged level cannot measure
drain or energy efficiency. Adopted storage grew 12,341,248 bytes during the
wider diagnostic run; this includes evidence and is not a gameplay storage budget.
Other retained sessions have median FPS 50.54, 39.23 and 65.05 on different APKs;
the 39.23 FPS run also failed a runtime-error check. They are separate cohorts,
not causal regression comparisons.

## Three measured bottleneck hypotheses

1. **CPU work limits steady FPS.** Median sampled CPU time is approximately twice
   GPU time; the slow block records 33.25 versus 11.93 ms. Confirm with synchronized
   named main-thread markers separating original simulation/AI, render submission,
   diagnostic overhead and waits. Latest-frame CPU duration alone does not identify
   the critical thread or distinguish work from waiting.
2. **Visible workload/render submission explains the transient slow block.**
   Retained 30-second pacing windows around active seconds 445–745 show median
   draw calls/SetPass/vertices about 749/302/596,000, versus 552/252/460,000 in
   seconds 745–1,045 after recovery. Enemies remain at 40 and camera drags occur
   each minute. Confirm camera/visibility and draw-call timestamps against render
   submission and AI markers; this association does not isolate rendering cost.
3. **Allocation/GC contributes to the hitch tail.** Retained pacing windows span
   207 collections and median sampled allocation about 108 KB per sampled frame;
   1,359 active frames exceed 50 ms. Confirm per-frame durations synchronized with
   GC start/end and allocation markers. Aggregate collection counts do not show
   which, if any, hitch was caused by GC.

These are analysis hypotheses, not optimization changes. The next useful capture
combines actual frame durations, CPU/main/render/GPU markers, GC events and clock
or limit states on the same representative workload. Preserve original behaviour
and visual fidelity; assess diagnostics overhead before attributing it to the game.
