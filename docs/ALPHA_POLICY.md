# Owner alpha packaging and acquisition policy

Engineering decisions for the owner-built alpha; no release is published or
approved by this document. Architecture C, IL2CPP ARM64 and the accepted-input
boundary in [ADR-002](ADR-002-public-alpha-distribution.md) remain fixed.
[public-alpha.md](public-alpha.md) owns the remaining acceptance work.

## Package and updates

Reserve `dev.ror2lab.alpha` for the first owner alpha. Keep the disposable
`dev.ror2lab.arm64` laboratory package and separate tool fixtures unchanged.
The final owner installer enforces this identity; the laboratory and private replay
identities are not migrated. Actual alpha package, storage, execution and update
evidence is still required before release.
Do not adopt an existing installation without a local ownership receipt and
matching package/signing identity. Do not remove a conflicting package to make
an installation succeed. Migration of laboratory data is a separate reviewed
operation; the first alpha starts with its own Android-local profile.

Each owner keeps the signing key private and uses that same key for subsequent
updates. The project does not hold a shared signing key or accept uploaded keys,
passwords or owner-generated game packages. Key creation, durable custody and
private recovery backup must be qualified before the first alpha installation.
Losing the key blocks in-place updates; silent key replacement is not recovery.
The existing owner signer retains custody; the installer independently checks the
installed certificate, signed output and local ownership/issued-version receipts.

Every installed alpha update must use a strictly greater positive `versionCode`
than its predecessor. Keep an owner-local issued-version receipt; rebuilding the
same source for rollback still allocates a new code. Bind that code to source,
accepted input, toolchain, APK hash, payload manifest and signing certificate.
Do not derive ordering from a Git hash or a wall clock alone. Refuse exhaustion
rather than wrapping or reusing a code. Use the conservative upper bound
2,100,000,000 documented by Android; this does not select Google Play delivery.
Android documents [version ordering](https://developer.android.com/studio/publish/versioning)
and [signing continuity](https://developer.android.com/studio/publish/app-signing).

Rollback reconstructs the previous verified signed APK's nonsignature entries,
changes only its binary manifest version, and signs with the same owner key and a
new higher issued code. This retains the previous reconstructed source/payload
set without a separate game-data backup or Android downgrade. Preserve the last known-good receipt,
profile/settings backup and data-schema compatibility declaration. Refuse a
schema-incompatible rollback. Never use uninstall, forced downgrade, data clear
or storage reconfiguration as an update/rollback step. Profile/settings retention
must be checked across the actual install and cold start; fixture retention is
not game-profile acceptance.

## Acquisition and capabilities

Select **local legitimate PC files only** for the first alpha. The owner supplies
a read-only copy or grants read access to the original installation. Inventory
and hash the complete accepted input before transformation. Unknown, incomplete
or changed input is refused until explicitly reviewed and accepted; filenames,
a Steam manifest label or a successful file picker alone do not prove identity.
The prepared desktop path already enforces its inventory/acceptance preflight;
the phone importer now checks reviewed complete fingerprints, with actual picker
and native-player behavior still requiring phone qualification. A signed catalog
can declare multiple supported inventories and recognition-only older versions.
An exact unsupported match is named but refused; otherwise the result is honestly
"unknown" (or ambiguous), with the supported list and a complete-installation/
maintainer-review action. Filenames, labels and partial matches never authorize
conversion. Cancellation must leave
the source untouched and retain no partial output as an accepted build.

Defer account downloads, Steam Guard flows and Steam Cloud synchronization.
The alpha needs no account password, embedded token or automatic login. Local
files do not establish Steam ownership authentication or an authenticated
in-game session. Preserve the existing unavailable Steam/EOS identity, lobby,
remote-peer and online-service capabilities. Keep expansion admission and earned
survivor/loadout filtering authoritative; catalog presence and developer
selection never grant entitlement or unlocks. Android-local progress stays
separate from PC/cloud saves. No cloud import/export or resumable-run promise is
made.

The pinned ProperSave filesystem boundary, reviewed in
[community prior art](community-prior-art.md#startupplatform-graph-and-profile-boundary),
informs that separation; its mod save format is not an Android profile protocol.
No community or game implementation is copied into this policy.

## Final-flow acceptance contract

These distinguish host-qualified code contracts from the remaining actual-phone
evidence. No host test establishes a released or game-qualified alpha. Extend the existing [owner APK producer](../tools/phone-build/owner-apk/README.md),
input admission and device ownership owners; do not introduce a second signing,
installer or input-acceptance pipeline. Keep detailed receipts private and publish
only reviewed summaries. The prepared-lab [playtest checklist](PLAYTESTING.md)
remains the desktop fallback.

| Boundary | Required case and evidence | Existing coverage and remaining gate |
| --- | --- | --- |
| Final package identity | Inspect assembled/installed `dev.ror2lab.alpha`; require an occupied installation's ownership receipt, actual APK hash/version and same signer. No adoption/uninstall fallback. | Host-qualified: alpha publisher, manifest, issued-receipt and session guards. Phone gate: actual alpha package, placement and cold start. |
| Issued versions | Durable codes 1–2,100,000,000 bind source/input/toolchain/APK/payload/certificate. Failed/cancelled attempts burn codes; reject reuse, downgrade, missing ledger and exhaustion. | Host-qualified: locked issuance and independent publisher/install ordering, including repeated source and rollback. Phone gate: durable recovery across real power/process interruption. |
| Signing and recovery | Keep one private owner certificate; verify signatures/alignment and reject lost, redirected or exposed custody. | Existing signer plus new ledger/certificate checks pass synthetic contracts. J1095 remains authored-phone signing only. Real alpha key backup/recovery and signature continuity still need phone evidence. |
| Legitimate local input | Hash complete supported inventories; clearly name known-unsupported/unknown/ambiguous inputs, supported versions and next action. No output admission from labels or partial copies. | Host-qualified: existing folder/ZIP import extended with shared version fingerprints, bounded reads, refusal and post-import verification. Phone gate: actual SAF providers and legitimate version cohorts. |
| Retained rollback | Retain current/previous manifests and signed-APK references; require compatible schema, same key and a newly issued higher code. Never uninstall or force downgrade. | Host-qualified: real binary-manifest forward reversion, unchanged retained content, signing/refusal boundaries and safe reference pruning. Phone gate: actual session rollback and cold-start compatibility. |
| Profile/settings retention | Preserve the bounded local file set below; snapshot before mutation, verify/restore before releasing the launch gate. | Host-qualified: executing Java store/installer tests, corruption/interruption/space refusal and released-token crash recovery without overwriting newer play. Phone gate: Binder caller checks, filesystem durability and real native profile/settings across update/rollback. |
| Cancellation and updates | Cancel acquisition/build/install without modifying originals, accepting partial output or losing current/previous recovery references. | Host-qualified: importer/checkpoint/session/backup recovery contracts. Phone gate: ordinary Android consent, cancellation and retained game progress across cold starts. |

Run the existing host contracts without private input or an editor:

```sh
python3 -m unittest discover -s tests -p 'test_owner_binary_manifest.py'
python3 -m unittest discover -s tests -p 'test_owner_signing.py'
python3 -m unittest discover -s tests -p 'test_owner_payload_store.py'
```

The payload fixture compiles and executes the actual Java owner when a JDK is
available; a skipped Java test is not a passing preparation result. Signing
tests use authored APK/tool doubles and establish orchestration/refusal contracts,
not cryptographic, Android installer or game-runtime acceptance. Keep J1065 and
J1095's separate device scopes when evaluating the final-flow evidence.


## Local retention and rollback storage

The retained native set is deliberately narrow: `android-profile-v1/profile.json`
plus `.backup`, `.pending`, `.backup.pending`, `.recovering`;
`offline-settings-v1/preferences.json` plus `.backup`, `.pending`; and
`offline-run-results-v1/profile.json` plus `.backup`, `.pending`, `run-<32 hex>.xml`
and its matching `.debug.json`. Suffixes extend the primary filename. Results
history preserves profile baseline reconciliation, not resumable runs. Exclude
payloads, diagnostics, rejected generations and arbitrary files. Native owners
still validate their own formats; this transport does not invent a save schema.

A certificate-bound, control-only provider keeps backup bytes inside the game
UID's `getNoBackupFilesDir()/owner-profile-retention`; nothing is uploaded or
passed to the installer. Each snapshot is bounded to 512 files, 16 MiB/file and
64 MiB total, with a further 16 MiB free reserve. Keep the newest and one previous
verified archive (at most 128 MiB plus bounded metadata); snapshot/restore also
needs up to one 64 MiB staging copy. Older app-owned archives are pruned only
after a new snapshot verifies. Current production reads/writes contract 1 only;
any other schema is refused until a real native migration is implemented.

A durable launch lease requires a fully stopped game, not merely a paused
activity. The installer cannot force-stop another UID; Android app settings may
be needed before retry. Verification/restore precedes release. One atomic
active/released journal lets interrupted installer finalization recognize an
already completed release without restoring a stale backup over newer gameplay.

The release store retains only current and previous signed APKs by canonical
reference/hash plus their manifests/receipts, and at most one active candidate.
The UI reports their actual combined bytes. No separate payload/game tree is
copied for rollback. Rollback requires space for three new APK-sized work files
plus 2 GiB reserve; unsigned/aligned and older unreferenced artifacts are pruned
at the next release operation and after Ready, never while referenced by current,
previous or pending recovery. Missing artifacts/key/receipts refuse safely.
Pre-v3 alpha fixtures lacking issued-version/retention state are not silently
adopted; recovery/migration needs a separate reviewed path, never automatic data
clear or uninstall.

## Distribution and feedback

Only audited authored tooling, recipes and original bootstrap material are
eligible for publication. Game-derived APKs, bundles, shaders, middleware, raw
logs, screenshots and signing material remain private owner outputs. Dependency
license/provenance review and a clean public-input bootstrap are release gates.
There is no project-hosted conversion service or prebuilt game download.

Feedback uses a local reviewed report and a tokenless browser issue draft.
Opening a draft may transfer its text to GitHub; submitting remains a separate
player action. No background upload, raw-log collection or automatic attachment
is authorized. Manually added notes and attachments require separate privacy
review and explicit sharing action. Public issue-template/tracker changes,
releases and outward announcements still require explicit user approval.
