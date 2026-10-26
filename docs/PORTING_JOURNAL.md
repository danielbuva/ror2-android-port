# Porting journal

Shipped results only, one short entry each (at most 15 lines): what changed, the evidence path, the
APK or output hash where relevant, and what remains. Exploratory and negative results go to dated notes
under ignored `work/coordination/`, not here. Entries J01–J1177 (2026-09-12 to 2026-10-25) are frozen in
[history/journal-J1-J1177/PORTING_JOURNAL.md](history/journal-J1-J1177/PORTING_JOURNAL.md) with its
[index](history/journal-J1-J1177/JOURNAL_INDEX.md); numbering continues here.

## J1178 — Journal archived and documentation slimmed

2026-10-26. The 3.8 MB, 1,132-entry journal and its index moved unchanged to `docs/history/journal-J1-J1177/`;
206 anchor links in docs and tool READMEs now point there. AGENTS.md documentation rules now record only
shipped results here, keep exploratory notes in ignored scratch, refresh `PORTING_STATE.md` once a day,
and add the speed, token-efficiency and branch-update rules the parallel workers follow.
Evidence: this commit. Remaining: none for this change.

## J1179 — Recursive Standard Shaders and five complete scene bundles

2026-10-26. Existing Shader owner derives material/instancing seeds from original scene PPtr closure;
four source-selected Standard packs reproduce complete J850 Shader records (261,528 B each for
Blackbeach2, Shipgraveyard and TestOtherBrother; 301,384 B for Repurposed Crater).
Existing object producer adds original preload and SDK DefaultMaterial dispatch; six audited source
profiles complete Logbook and those four scenes: five compressed bundles, 94,099 objects, all members raw-exact.
Evidence: `work/coordination/p1-payload-scene-shaders-v1/recursive-standard-qualify-v1/qualify-done.json`
and `work/coordination/p1-payload-preload-five-v3/done.json` (per-bundle output SHA-256 receipts).
Readiness: `work/coordination/p1-anim/five-scene-publication-v1/readiness-union/`; 598/705 available,
593 raw-exact, two code comparisons and three drift-explained; 107 missing (7 APK, 100 payload).
Prior art: pinned AssetRipper property/fallback relationships; SDK/native contracts remain J1157/J1163.
Host-only; phone production/runtime remain open. APK unchanged: J850
`f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`.

## J1181 — Loading presentation pacing

2026-10-26. Shipped loading-only presentation pacing; measured thermal improvement remains unqualified.
Existing NovaInputSession sets interval 3 after landing, restores before gameplay and first in finally before recovery.
Prior art: pinned UnityExplorer ReflectionInspector paced observations; Unity OnDemandRendering preserves simulation; no TimeScaleWidget clock change.
Normal code build source `b12e81ea0ff9968d20a6df8bdd5ebfd19e3b98e9`, APK `4666a1107e812d19b3186aa6f528adb745f6b3bb256fbe37f87472cc85b247ac`.
Player succeeds in 28.912 s, zero errors; pipeline 115.870 s; existing frozen payload reused.
Evidence: `work/coordination/main-port-loading-pacing/` build receipts, retry terminal and logs.
First attempt refused artifact snapshot identity after successful Unity build; normal retry passes unchanged checks; cause unproven.
Two focused lifecycle/presence checks, Ruff and host preflight pass; doctor retains historical bootstrap failure.
No device install/run: R58 remains last verified installed; strict three controls and measured loading heat remain open.
Mandatory prune passes; revisit after authorized device admission under unchanged J1156 limits.

## J1182 — Android producer affinity mask compatibility

2026-10-26. Shared phone runner passes selected CPUs as a hexadecimal mask;
Android Toybox on the assigned phone rejects the previous `-c` option before input admission.
The existing tool-host mask contract supplies the compatible command form; worker and thermal policies stay fixed.
Seven focused host tests, Ruff and host preflight pass; complete phone replay remains open.
Evidence: `work/coordination/p1-player-phone-assembly-v1/android-taskset-mask-host.json`
and `phone177-parent-terminal-v4.json` in that directory; independent device cleanup passed.
Runner SHA-256: `15fdc82f66808db46cf9b25ba17251af12237a32728cc12aecf1391f2e2eb649`.
No installation or game launch; accepted J850 APK and content readiness are unchanged.
