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
## J1182 — Source-only J850 catalog identity projection

2026-10-26. Existing integration metadata owner accepts an explicit camera-root extension; current defaults stay intact.
J850 selects no extension and only closure/mesh sources, following receipted public source commit `1780ea9545`.
Fresh PC-source catalog analysis plus public importer declarations reproduces all 30,322 locations,
84,016 keys and 7,458 roots in order against the receipt-linked final catalog's metadata projection.
Only attempt is normalized; final bundle fields are excluded from this metadata comparison.
Evidence: `work/coordination/p1-payload-catalog-fresh-v1/metadata-done.json`; generated metadata SHA-256
`ea85d7903fb23fa103d36c9b877966cdc65506a75f8468d862724d8361718a30`.
Pinned ThunderKit copies desktop catalogs only; existing J714/J725 host reconstruction remains authoritative.
33 focused tests, Ruff and host preflight pass. Host-only; readiness stays 598/705, final catalog/manifests,
remaining payload bundles and phone qualification stay open. No new APK or device claim.
## J1183 — Eight complete source-derived scene bundles

2026-10-26. Eight object and eleven Shader profiles complete Lakes/Lakesnight/Sulfurpools spine,
Satellitescene, Limbo, IronAlluvium, IronAlluvium2 and Lobby: 135,541 records, including 80 Shaders.
All 16 serialized members and eight compressed bundles are raw-exact against J850 on the host.
Existing owners and source-selected variants are retained; Director exposed-reference naming gains
an original-identity derivation and host contract, without a complete Conduit qualification claim.
Evidence and per-output SHA-256: `work/coordination/p1-anim/six-scenes-final-host-v1/` and
`work/coordination/p1-anim/two-scenes-final-host-v1/` in the animation worktree; readiness union:
`work/coordination/p1-anim/eight-scene-publication-v1/readiness-union/` (606/705 available,
601 raw-exact, two code comparisons, three drift-explained; 99 missing: 7 APK, 92 payload).
Prior art: pinned AssetRipper property/fallback relationships; existing J1157/J1163 Shader contracts.
Host-only; phone production, installation and runtime remain open. APK unchanged: J850
`f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`.

## J1185 — Integrated preparation timing and cleanup race repair

2026-10-26. Existing IntegratedWorldSession emits bounded monotonic-time/frame markers around preparation
and its existing resource waits; report writes, scheduling and ownership remain unchanged.
Prior art: pinned R2API AddressReferencedAsset distinguishes request, handle and completion; no code copied.
Normal IL2CPP code-build source `3749f5d8`, APK `9dd424f4a183d299b0ee03cd325a0cae7c9f863edb8e0b6332c81cd43c3a4dc1`.
Evidence: `work/coordination/main-port-preparation-trace/` build receipt, focused checks and preflight logs.
Ten focused trace checks, 45 camera checks (three skips), host preflight and public audit pass.
Cleanup now tolerates a concurrently removed payload and continues the plan; other errors propagate.
Nine cleanup regressions and Ruff pass; cleanup receipts are in the same evidence directory.
Device qualification, hotspot attribution and measured thermal improvement remain open; no gameplay claim.
## J1184 — Isolated ambient observation fixture

2026-10-26. Existing phone-content owner gains authored ambient staging and graphical capture actions.
The exact-editor session waits for controller arming, saves the scene, and exits on completion or timeout.
Host validation requires six ordered finite 64 by 64 float images, uncached SH and a nonempty GPU trace;
native job association remains the external controller's contract. No captured bytes are producer inputs.
Seven focused host checks and the pinned editor API compile pass; generated action documentation is current.
Evidence: `work/coordination/accepted-build-reconstruction/media-source-v1/default-sky-source-v1/ambient-fixture-checkpoint-done.json`;
fixture implementation commit `6a73e581e53a127c15b34c94e5cf261f46d4b286`. No APK generated or changed.
Prior art: pinned AssetRipper copies baked lighting values; independent sky generation remains unsolved.
Actual SaveScene bake, GPU execution, target equality and phone production remain unqualified.

## J1185 — Complete Conduit Canyon and source fog Shader retention

2026-10-26. Existing object/Shader owners complete Conduit Canyon: 49,573 records,
all serialized members and the compressed bundle raw-exact against J850 on the host.
Source-qualified preload relationships retain imported-model Mesh-only exclusion.
Standard source fog validation now retains original linear/exponential/exponential-squared modes;
Fungal Standard (642,752 B) and 25 postprocess records (87,712 B) are independently raw-exact,
with complete Fungal scene assembly still open. Prior art: pinned AssetRipper FogMode/ParsedForm
and SDK UnityCG fog defines; existing J1157/J1163 Shader/compiler contracts remain unchanged.
Evidence/output hashes: animation worktree `work/coordination/p1-anim/conduit-final-host-v2/`;
`work/coordination/p1-fungal-standard-v2/done.json` and `work/coordination/p1-fungal-shaders-v1/`.
Readiness: Conduit union 607/705 available, 602 exact, two code and three drift-explained;
98 missing (7 APK, 91 payload). Host-only; phone production/install/runtime remain open.
APK unchanged: J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`.

## J1186 — Apply the user-selected gameplay thermal safety limits

2026-10-26. Existing gameplay and producer thermal owners abort CPU/GPU only
above 95 C continuously for at least 3 s, or battery above 46 C; sample gaps
above 1 s still invalidate supervision. Admission and producer duty cycles stay.
Skin/HAL heat is recorded; receipts retain sampled time above 80 C, peak and phase.
The sustained-session battery check uses the same limit. No runtime pause/replay added.
57 focused host tests pass; retained J1152/J1164/J1177 traces all pass new limits,
with CPU/GPU peaks 81.6/84.8/83.6 C and sampled hot times 0.30/5.23/2.47 s.
Evidence: alpha worktree `work/coordination/alpha-thermal-policy/replay-results.json`.
No APK/output generated or installed. Fresh heap/sustained device qualification remains open;
preflight is blocked by this checkout's missing ignored local configuration.

## J1187 — Exact ordinary-app Android SDK cohort and producer battery cutoff

2026-10-26. Existing SDK producer emits all 15 persisted package entries raw-exact to J850
inside the ordinary Android app host; the prior 13 are unchanged, including all four DEX files.
Both generic META-INF metadata outputs now have phone equality evidence; no game input or Editor used.
Producer 44.279 s; supervised process 48.614 s; peak UID RSS 358,784 KiB; output 60,271 KiB.
Observed CPU/GPU peak 54.5 C, zero duty pauses or time above 80 C; both OLEDs asleep afterwards.
Evidence/per-entry SHA-256: `work/coordination/phone-code/android-sdk-phone-v6-proof.json`,
`android-sdk-phone-v6-result.json`, resources and terminal receipts in the same directory.
Tool APK SHA-256: `988b8850dffc134c02e7a86cf8bce73b724284c75ff87c4541faaa11bfea87b9`.
Owned-job cleanup, lease release and mandatory prune passed; game APK unchanged, no game launched.
Shared producer cutoff corrected to battery >= 43 C; eight focused host tests and Ruff pass.
Run predates correction and lacks battery/charge admission evidence: current thermal policy unqualified.
Complete source composition, installation, controls and matched performance remain open.

## J1188 — Battery health admission and gameplay safety cutoff

2026-10-26. Existing alpha thermal owner now admits each stage only with battery <= 35 C,
including cooldown between stages; CPU/GPU/skin admission remains <= 50 C.
Charging status 2 at level >= 80%, or level > 85%, refuses without retry.
Runtime battery >= 43 C aborts in the zone observer and sustained-session check.
Bounded battery reads retain temperature/level/status in trace and stage receipts;
charging settings remain untouched. CPU/GPU > 95 C for >= 3 s and gap > 1 s rules remain.
52 focused host tests and Ruff pass; preflight lacks ignored local configuration.
Evidence: alpha worktree `work/coordination/alpha-battery-health/validation.json`.
No APK/output generated or installed. Fresh stability/device qualification remains open.

## J1189 — Reconstruct eight further complete scene payloads

2026-10-26. Existing source-only owners reproduce Splash, Habitat, Helminthroost,
Itgolemplains, Artifactworld03, Itgoolake, Itmoon and Loadingbasic.
All 60,573 persisted objects, serialized members and compressed bundles are raw-exact
to J850 after guarded production. Title separately has 26 source-qualified Shader records,
including SDK terrain base-generation passes; complete Title assembly remains open.
Evidence/output hashes: `work/coordination/p1-shaders-publication-v2/`,
`work/coordination/p1-scenes-w/publication-batch-v1/` and Loadingbasic qualifier receipts.
The readiness union includes Fungal, independently shipped in J1190.
Readiness: 616/705 available, 611 exact, two code and three drift-explained;
89 missing (7 APK, 82 payload). Host-only; phone production/install/runtime remain open.
APK unchanged: J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`.

## J1190 — Complete source-derived Fungal scene

2026-10-26. Audited Fungal selectors extend the existing object producer:
123,671 records (36,645,626 B), both serialized members and the complete compressed
bundle are host raw-exact against J850. Output: 14,723,479 B, SHA-256
`e2addd8bbd3cbb1f30971a114b312ae434b8673905c2cc6fc34e3a6fd4f3edc2`.
Evidence: `work/coordination/p1-anim/fungal-final-host-v2/qualification-done.json`
and `work/coordination/p1-anim/fungal-publication-v1/checks-done.json` in the animation worktree.
Existing target-tree interface exposes `payload/whole-scene-fungal`; no union recount claimed.
Prior art: retained J1070/J1075 producer and original typed preload policies;
R2API addressed/direct distinction from the pinned community source index.
Focused host checks, source-only qualification and provenance review pass.
Host-only; phone production, installation and original scene behavior remain open.
