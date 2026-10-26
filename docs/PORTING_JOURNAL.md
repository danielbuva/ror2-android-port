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

## J1179 — Four recursive-source Standard Shader packs

Hypothesis: original scene PPtr closure supplies missing material feature and instancing seeds.
Existing Shader owner accepts the observed four-seed context and exposes its validated original VertexLit → SDK6 dependency relocation.
Four public selector profiles retain first-seen distinct original keyword/instancing pairs, without a target retention table.
Guarded actual CLI persists all production before independent comparison; all four complete Shader records match J850.
Blackbeach2, Shipgraveyard and TestOtherBrother each reproduce 261,528 B; Repurposed Crater reproduces 301,384 B.
Evidence: `work/coordination/p1-payload-scene-shaders-v1/recursive-standard-qualify-v1/qualify-done.json`; original pointer chains: `recursive-standard-v1/`.
Prior art: pinned AssetRipper DummyShaderTextExporter property/fallback relationships; SDK/native contracts remain J1157/J1163.
The direct-only seed failure in J1172 is resolved; full scene/preload closure and readiness union remain consumer-owned.
Host-only; phone Shader production/runtime remain open. APK unchanged: J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`.
