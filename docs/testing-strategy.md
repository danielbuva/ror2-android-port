# Testing and observability

Run `./dev preflight` before expensive builds. `./dev smoke --target gles` (or `vulkan`) builds/reuses the harness, installs onto the live adopted volume, launches to discover content paths, syncs changed payloads, relaunches, waits for LAB_READY, collects evidence and removes only the disposable package first installed by this smoke transaction. A pre-existing unreceipted package is never replaced or removed.

Each `work/runs/<UTC>-<APK hash>/` contains a result, Unity log, crash log, exit-info, screenshot, memory/gfxinfo/thermal/CPU captures and runtime snapshot when readable. `work/runs/latest.json` points to the latest attempt, including failure. Never replace failed evidence with a success under the same run ID. A fresh PID/checkpoint and visible screenshot are required; compilation alone is not success.

First-failure classification starts at preflight/input drift → host/toolchain → install/storage → process/native crash → managed exception → missing content → shader/material → gameplay. Current automatic classification is coarse; preserve raw evidence and refine it instead of claiming detailed diagnosis from an exit code.

## Current instrumentation

`android/Assets/LabDiagnostics.cs` writes machine-readable snapshot.json and exceptions.jsonl under persistentDataPath. It reports scene, hierarchy, components, optional public fields, camera, renderer/shader names, loaded managed assemblies, controller names, content/save paths, player-name heuristic, sampled FPS/frame time, managed/allocated memory, CPU/GPU frame timings when Unity exposes them. Native mappings are collected through run-as when allowed; tombstones may be inaccessible on the non-root device and that limitation is recorded.

`./dev diagnostics --subtree NAME --fields` updates development-only `diagnostics.json`; `--disable` stops periodic snapshots. The configuration can enable/disable periodic snapshots, select a subtree string and enable public-field collection without rebuilding. The hierarchy is bounded to 1,000 objects and field output is bounded; it is not a complete game-state serializer. Runtime game/audio/network states are explicitly reported as uninitialized in this isolated harness. Future RoR2 adapters must supply actual run/player/audio/network checkpoints; a GameObject named Player is only a diagnostic heuristic.

Long logcat messages were truncated in the first run. The collector now reads the full app snapshot file using the path reported in the log; do not parse a truncated JSON message as a complete snapshot. Runtime diagnostics and game-derived screenshots stay ignored. Review for account/device information before any external sharing.

## Measurements and limits

The initial GLES lab sampled about 30 FPS / 33 ms CPU frame pacing with a tiny mesh. This is not a RoR2 performance estimate. Capture idle/stage/combat/transition scenarios later, control refresh rate and frame cap, warm up, then measure sustained thermals and percentiles. Unity GPU timing values need validation against device profiling; zeros/unavailable values are not zero GPU cost. Android gfxinfo may not describe Unity's native rendering fully. Package size, sync bytes and install duration are recorded; large payload load/transfer/thermal tests remain open.

Host tests cover safety guards, unknown-input rejection and failure receipt behavior. They do not simulate real-device authority or certify graphics. The real device is the acceptance environment.
