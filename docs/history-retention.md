# Historical storage retention

J427 follows the user's explicit storage-cleanup request: keep two ready-to-use
rollbacks and retire superseded full snapshots and build outputs. Earlier journal
statements that every archived APK/full snapshot remained present describe the
state at those historical exits; this retention policy supersedes them.

The expanded rollbacks are:

| Role | Retained composition | Source/evidence directory |
| --- | --- | --- |
| Current integrated game | J425, APK `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0` | `work/experiments/scene-runtime/20261008T163328.528634Z` |
| Paused Moon candidate | J323, APK `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9` | `work/experiments/scene-runtime/20261006T034153.546343Z` |

Both retain their exact APK, matching complete payload, source archive, settings,
recipes and evidence. The active lab project, current generated payload, legitimate
PC input, AssetRipper export, decompiled input, recovery tools, shader/IR records,
whole-catalog investigation, profiles and Git history are outside the cleanup.
No installation, package update or device storage operation is required.

Superseded source trees are compressed and deduplicated by SHA-256 under ignored
`work/retired-storage`. Every distinct source file is retained, together with its
path, mode and modification time. A tree is removed only after every stored file
and its complete manifest verify, and the source tree is checked for concurrent
changes. Findings, logs, captures, provenance, failed-attempt classifications and
build receipts outside the retired trees remain at their existing locations.

Superseded APKs and Android payload outputs are disposable generated artifacts.
Their hashes/recipes and historical results remain; only the two selected builds
are guaranteed ready for reinstall. Old checkpoint JSON remains historical
evidence, not a promise that its executable is still available. Rebuild an obsolete
candidate from its archived source if it becomes necessary.

## Restoring an old source tree

Read the adjacent `<tree>.retired.json` marker before using an old checkpoint.
Restore only the specific source tree needed by the next experiment:

```sh
python3 scripts/compact-history.py restore work/experiments/scene-runtime/ATTEMPT/stage
```

An explicit `--destination work/restore-review` restores an independent review
copy. Restoration validates the manifest and every file hash, restores modes and
times, and publishes the destination only after verification. It refuses existing
destinations, symlink paths and paths outside ignored `work/`. It never hard-links
restored working files to the archive. Markers for deliberately discarded generated
outputs reject restoration and direct the caller to rebuild.

The content store and manifests are development inputs after retirement; do not
delete them as cache, publish them, or recursively rehydrate all historical trees.
Raw selection, deletion, integrity and free-space ledgers stay local under
`work/cleanup-analysis`. Public documentation contains authored summaries only.

The command defaults to plan validation. Applying retirement requires an explicit
list of eligible snapshot trees and protected rollback roots; overlapping protected
paths, arbitrary workspace paths and build APK/receipt paths are rejected. CLI
operations hold a single storage lock. Separate tests cover independent restoration,
deduplication, corruption, changing sources, symlinks and protected paths.

## J427 completed cleanup

| Area | Before, reported usage | After, reported usage |
| --- | --- | --- |
| Historical scene experiments | 247.7 GB | 12.6 GB |
| Build cache | 76.1 GB | 0.75 GB |
| Deduplicated source history | — | 0.88 GB |

Actual host free space increased by **218.8 GB**, from **100.7 GB to 319.4 GB**.
Reported directory usage counts APFS-shared extents more than once, so its reduction
is larger than the actual space reclaimed. These are completion-time measurements,
not future capacity constants.

Retired 387 superseded expanded source trees into 21,061 distinct compressed source
blobs; removed 437 obsolete APK copies and all 351 obsolete cache payload trees,
plus the retired historical payload copies. Only the two selected APK identities
remain in these areas. The remaining scene data is the two source rollbacks and
useful runtime findings/captures/receipts.

An actual 18,581-file archived-source restoration passed content, mode and timestamp
checks and independently matched 18,580 entries in its original archive receipt.
The temporary restoration was removed after verification. Both retained rollbacks'
34,000-plus source files, APKs and complete payloads verify unchanged; current build
selection and recipe hashes remain exact. All 110 host tests pass. No device run,
installation, original-input change or gameplay capability advancement occurred.

Source retirement intentionally stopped after all 460 selected history trees were
preserved, before unnecessary compression of the remaining obsolete cache outputs.
Those outputs were pruned directly with separate hash/deletion receipts. The raw
interrupted compression result is retained alongside the successful source-phase,
generated-output, restoration and final-integrity receipts; it is not an unknown
source-preservation failure.
