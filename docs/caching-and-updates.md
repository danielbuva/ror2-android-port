# Cache and update rules

| Stage | Invalidation input | Output |
| --- | --- | --- |
| File inventory | Full content SHA-256; fast mode reuses only same size/mtime | inventory/files.json + prior input snapshots |
| Managed metadata | Managed file hashes + scanner source | managed.json, seams.json, surface-diff.json |
| Decompilation | Individual assembly hash + ilspycmd version + language/options | per-assembly content-addressed folder and success receipt |
| Content metadata | Individual file SHA + UnityPy version + scanner schema | per-file JSON caches; aggregated graphics/shader manifest |
| AssetRipper export | Entire input identity + AssetRipper pin + export settings identity | content-addressed local export and receipt |
| Lab APK | Harness/imported inputs + API/editor/backend/build recipe | immutable build-cache APK and hash receipt |
| Android bundles | Unity dependency cache / source asset changes | generated Android payload; cache snapshot accompanies APK |
| Device sync | SHA-256 of each payload file compared with device | only changed files transferred and verified |

A C# edit never invokes acquisition, full decompilation or AssetRipper export. Shader/content inspection does not invalidate managed recovery. Unity's incremental asset build handles unchanged bundles when an APK rebuild is necessary. Do not delete Library or all work/ to fix an isolated issue. Failed stages never write a success stamp.

`./dev inspect --full` identifies changed input hashes and records added/removed/changed files. `input-diff.json` reports assembly/native/bundle groups; `surface-diff.json` compares type/method/field signature surfaces when managed metadata changes. Signature blobs include metadata tokens, so a changed surface hash is a review trigger, not a semantic equivalence theorem. Shader changes are detected through changed bundles and a subsequent graphics scan; compare per-file shader manifests for details.

Preflight rejects filesystem drift and refuses an unaccepted input ID. To adopt an update, inspect the diff, rerun affected stages, review patch match counts, then explicitly record the reviewed ID in `work/config/accepted-input.json`. There is no silent autoaccept. A size/mtime comparison is a quick drift guard; full content validation belongs at reviewed checkpoints.

The initial bounded reconstruction patch qualifies ambiguous type names, checks expected match counts and records before/after hashes. It does not patch game binary offsets. Unknown builds are blocked by preflight. Revisit source-aware matching if future changes need method-body transformations; textual anchors are insufficient for broad semantic patching.
