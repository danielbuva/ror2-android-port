# Architecture

What runs today, how it is built, and who owns what. The ADRs explain *why*
([ADR-001](ADR-001-port-architecture.md)); this page is the current map. Update it when a
file, owner or pipeline step is added, moved or retired. Results and evidence live in the
[journal](PORTING_JOURNAL.md); the files the build expects under `work/` are listed in
[LOCAL_STATE.md](LOCAL_STATE.md).

[Alpha policy](ALPHA_POLICY.md) owns packaging/acquisition decisions;
[screen inventory](SCREEN_COVERAGE.md) maps the current Android surfaces and their
remaining interaction gates.

Documentation entry points: [project home](../README.md) and
[player guide](PLAYER_GUIDE.md) explain availability for players.
[DEVELOPING.md](DEVELOPING.md) owns contributor setup, the repository map and
command reference, including the generated prototype-action table.
[PLAYTESTING.md](PLAYTESTING.md) owns the prepared-lab desktop fallback checklist:
matching build receipts, selected-device installation, assisted checks, manual
playtest limits and reviewed feedback. It introduces no installer or runtime step.
[Branding notes](assets/branding/README.md) record the two repository-only
promotional graphics and their sources; they are not part of the runtime pipeline.

Launcher presentation: [`launcher/`](../launcher/README.md) owns the approved
original background and dependency-free frontend. `controller.js` owns the
versioned host state/action adapter, subscription teardown and pending-action
guard; `app.js` owns views and navigation. No backend is connected by default.
The separate `demo/` is simulated and is never loaded by the frontend. This
package's `feedback.js` owns page-memory notes, explicit consumption of schema 1
sanitized baseline previews, an exact plain-text preview, review consent and
clipboard copy with manual fallback. Setup is the Diagnostics feedback route;
navigation removes listeners and retains notes in page memory, reload clears
them, and background host updates preserve the form. It projects typed,
bounded public facts into a new object and ignores unknown keys and draft URLs.
No raw receipt, log, device, storage, network or attachment access is added.
The notes are user-authored and require manual privacy review. The launcher
package is a public-alpha integration boundary, not an Android shell, new
build pipeline or runtime owner. Setup, lifecycle and acceptance gates are in
its README; the existing owner-built delivery route remains unchanged.

Public alpha delivery: [ADR-002](ADR-002-public-alpha-distribution.md) accepts
owner-built APKs and locally reconstructed content; [public-alpha.md](public-alpha.md)
holds open release work. ADR-001's architecture C and the runtime pipeline below
remain current. [phone-owner-build.md](phone-owner-build.md) assesses build stages
for phone-only delivery while retaining the desktop workflow as fallback; no
replacement game runtime or working build pipeline is selected. Public-input bootstrap,
performance equivalence and device acceptance remain open.

[Accepted-build reconstruction](accepted-build-reconstruction.md) compares a
fixed-target owner converter, private delta/frame replay and general Unity-project
reconstruction. `tools/phone-build/accepted-output/package.py` owns explicit private-packet
reproduction and framed emission. It verifies supplied target/profile/PC/SDK
inputs without generating independent Android target information. `assemble.py`
owns hash-bound unsigned APK assembly and required uncompressed/aligned resource
storage; canonical alignment and owner signing follow separately.
`unity_write.py` owns current experimental bounded UnityFS 7/8 and
serialized-v22 construction from explicit type metadata, object bodies and
resource streams. Object table order and physical body order remain independent.
It owns one temporary compressed stream, a bounded pinned codec child, block
deadlines and child teardown; callers own input provenance and retained outputs.
`build_bundle_lz4.py` builds the HC12/fast block helper `bundle_lz4.c` from a
separately acquired pinned public LZ4 archive, retaining its license, build logs
and terminal receipt. These structural writers generate no game content or
target relationships and have no game-build/runtime consumer. J1116 qualifies
all 133 accepted bundles as a structural control using accepted records; PC-only
object/layout derivation and phone qualification remain separate.
`object_produce.py` owns the current source-only pickup, player-death-effect
and teleport-material content slices. Audited profiles
`recipe/owner-pickup-objects.json`, `recipe/owner-death-effect-objects.json` and
`recipe/owner-teleport-material-objects.json` select original bodies/type
metadata and checked pointer relationships. It generates container/preload
metadata with explicit local/external order, packs, layout and canonical
bundles through those writers. New disjoint output, pinned PC files/recipe/
codec and capacity checks set up the process; persisted output and unchanged
inputs precede a complete/failed receipt. The qualified dummy material moves
its original valid keywords into the invalid list without introducing strings
or material values. Failure retains outputs and the codec context reaps its
child; exit ends the producer.

`player_data.py` owns the separate current 75-file player cohort: SDK/converter
resources, PC-derived script JSON, the three-object font file, original
line-breaking TextAssets, authored runtime JSON, 64 standalone Sprites and one
original TimerStringFormatter object. Its audited `recipe/owner-player-data.json`,
