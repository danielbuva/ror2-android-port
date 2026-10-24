---
name: lab-device-cycle
description: Use when building, installing or running the RoR2 Android lab on a device (whole-catalog code/full build, install, sync, baseline/diagnostic checks). Covers choosing the cheapest build, device ownership, the editor mutex, evidence capture and mandatory cleanup. Not for host-only edits or docs.
---

# Build → device → evidence → cleanup

1. **Pick the cheapest build that tests the change.**
   - Authored C# only (`tools/unity`, `tools/catalog`): `./dev prototype --action whole-catalog-code-build` (reuses the frozen payload; Bee keeps IL2CPP incremental).
   - Content, scene, catalog or package change: `whole-catalog-build`.
   - Add `--debug-symbols` only when a native crash needs symbolication; it costs time and ~2 GB.
   - Batch several independent changes into one build when they touch separate selectors; a full build is ~20 min, an install ~1 min.
2. **Before building:** commit (builds refuse dirty `tools/unity`, `tools/catalog`, `android/Assets/Editor`), run `./dev preflight --host-only`, check `df -h /System/Volumes/Data` (≥100 GB free, else `python3 scripts/prune-generated.py --apply`), and honor `work/coordination/unity-build.lock` — one editor mutation at a time.
3. **Device ownership:** always pass `--device <serial>` and `--apk <path>`. Use only the serial your brief assigns (see `work/coordination/codex-runtime.lock` `device_mapping`). Never install over another worker's device. Query storage/placement each install (the tooling does this).
4. **Run and collect:** `./dev check-baseline` for the two standard controls, or the specific `./dev prototype --action …-check`. Capture logs/crash/screenshot with `./dev logs|crash|screenshot --device <serial>`. Classify the first failure before changing scope.
5. **Record once:** journal entry `## J<n> — <title>` (take the next free number at append time; check the lock's `journal_reservations`), `python3 scripts/journal-index.py`, replace `PORTING_STATE.md` facts you changed.
6. **Clean up (mandatory):** `python3 scripts/prune-generated.py --apply`. Do not copy APKs/payloads into run folders; reference them by path + SHA-256. Pin an APK you still need by naming its hash in `PORTING_STATE.md` or the lock.

Device evidence is the authority: never claim success from a build, an editor screenshot or a host test alone.
