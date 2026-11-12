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
The report also separates final-ten-minute FPS and hitch counts/percentages from
whole-session totals. It uses the first retained observation inside the last
600 host seconds and reports actual endpoint coverage; missing boundary counters
are never interpolated. Short sessions report partial coverage, and fewer than
two retained endpoints leaves tail frame statistics unavailable.

```sh
python3 scripts/lab/perf_report.py RESULT_JSON THERMAL_JSONL --output work/perf/report.json
```

New sustained captures opt in to `rawFrameTimesRequested` on the existing camera
observer. A bounded 1 MiB buffer retains up to 262,144 active-frame durations,
excluding suspension and the first resumed interval as before. Native teardown
writes a private sidecar once; the sustained owner retains it with a SHA-256,
checks interval counters and removes the device scratch. Supply this sidecar with
`--raw-frames FILE` to compute true interval p50/p95/p99. Every frame, duration
total and strict hitch count must reconcile; overflow or absent coverage leaves
quantiles unavailable. Final-ten-minute quantiles also require a full 600-second
endpoint window. These measure Unity active-frame intervals, not compositor
presentation timing. Capture overhead and sustained device qualification remain
open; historical aggregate evidence below cannot acquire raw quantiles.

### Bounded raw-capture qualification

The 2026-11-12 Main Nova assisted capture retained 8,354 active intervals without
overflow. All ten observed counter intervals reconciled; the 80.049 host-second
window contains 4,693 frames and 80,709.293 ms of active-frame duration. True
p50/p95/p99 are 16.667/16.917/49.939 ms, with 59 frames above 33.334 ms and 41
above 50 ms. The incomplete ten-minute window correctly has no tail quantiles.
Native End Run closed the sidecar; retention, scratch removal and cleanup passed.
This qualifies capture and reconciliation only: invincibility, neutral movement
and small camera drags do not establish representative ordinary play or overhead.
Evidence: `work/coordination/alpha-raw-frames-device-20261112T070204Z/`
(`performance.json`, `terminal.done.json`). APK SHA-256:
`b9217c23f81cea18cf570bfa309bffda235db6276a9cca898b92a0fbd731a3eb`.

### Bounded capture on/off comparison

The sustained owner's `raw_frame_times` boolean defaults to true; false retains
aggregate frame/duration/hitch counters and refuses unexpected trace metadata
without transferring a sidecar. The mode is recorded in the selector and result.

Four 75-second assisted windows used the same APK above, seed 2, Commando,
Lakes, neutral movement and small camera drags, in off/on/on/off order. Actual
host endpoint spans were 79.686–80.315 s. Native End Run and cleanup passed each
time; both on-windows reconciled raw intervals without drops, and both off-windows
retained aggregates with no trace. The device scratch inventory was unchanged.

| Window | Capture | Active-frame FPS | Mean ms | Frames >33.334 ms |
| --- | --- | --- | --- | --- |
| 1 | Off | 58.189 | 17.185 | 55 / 4,692 |
| 2 | On | 58.077 | 17.218 | 53 / 4,392 |
| 3 | On | 58.207 | 17.180 | 58 / 4,693 |
| 4 | Off | 58.133 | 17.202 | 56 / 4,689 |

Equal-weight per-window means are 58.161 FPS off and 58.142 FPS on. On minus off
is −0.019 FPS, +0.0056 ms mean duration and +0.038 percentage points above
33.334 ms. Within-mode FPS ranges are 0.057 off and 0.129 on. Two windows per
mode, changing workload timing/population and thermal conditions do not establish
causal capture overhead. Sustained performance, ordinary play and energy remain
open.

Observed-window thermal traces have no gaps above one second (maximum 0.467 s),
with 0.189–0.624 s uncovered at their boundaries. Their peaks are CPU 84.4 C,
GPU 64.6 C and battery 31 C; covered time above 80 C is 0.401 s. Across the wider
startup/teardown phases, CPU/GPU peaks reach 90.7 C and time above 80 C ranges
2.480–15.816 s per run. Battery admission was 27–30 C at the charge limit;
unchanged charge level does not measure energy use. Shared adopted storage grew
2,011,136 bytes across the wider diagnostic, including its evidence.

Evidence: `work/coordination/alpha-capture-overhead-20261112T073826Z/`
(`terminal.done.json`, four `*-performance.json` reports and thermal traces).
The terminal receipt binds result/report hashes, idle process/selector/pending
readback, OLED sleep and lease release. No install or package change occurred.

### Historical aggregate inputs

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

The final-ten-minute counter window covers host seconds 1,203.251–1,803.151:
599.900 s of the requested 600 s, leaving 0.100 s unmeasured at its boundary.
Its 30,053 active frames average 19.987 ms (50.032 FPS), with 771 frames above
33.334 ms (2.565%) and 383 above 50 ms (1.274%). These are retained endpoint
deltas, without interpolation. Host-only analysis:
`work/coordination/alpha-tail-performance-20261105/report.json`.

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
