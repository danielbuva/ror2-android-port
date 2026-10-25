# Owner alpha packaging and acquisition policy

Engineering decisions for the owner-built alpha; no release is published or
approved by this document. Architecture C, IL2CPP ARM64 and the accepted-input
boundary in [ADR-002](ADR-002-public-alpha-distribution.md) remain fixed.
[public-alpha.md](public-alpha.md) owns the remaining acceptance work.

## Package and updates

Reserve `dev.ror2lab.alpha` for the first owner alpha. Keep the disposable
`dev.ror2lab.arm64` laboratory package and separate tool fixtures unchanged.
The new identity is not active in the current player or accepted-output replay.
It requires its own package, storage, execution and update evidence before use.
Do not adopt an existing installation without a local ownership receipt and
matching package/signing identity. Do not remove a conflicting package to make
an installation succeed. Migration of laboratory data is a separate reviewed
operation; the first alpha starts with its own Android-local profile.

Each owner keeps the signing key private and uses that same key for subsequent
updates. The project does not hold a shared signing key or accept uploaded keys,
passwords or owner-generated game packages. Key creation, durable custody and
private recovery backup must be qualified before the first alpha installation.
Losing the key blocks in-place updates; silent key replacement is not recovery.
The final phone key-storage implementation belongs to owner-build research.

Every installed alpha update must use a strictly greater positive `versionCode`
than its predecessor. Keep an owner-local issued-version receipt; rebuilding the
same source for rollback still allocates a new code. Bind that code to source,
accepted input, toolchain, APK hash, payload manifest and signing certificate.
Do not derive ordering from a Git hash or a wall clock alone. Refuse exhaustion
rather than wrapping or reusing a code. Use the conservative upper bound
2,100,000,000 documented by Android; this does not select Google Play delivery.
Android documents [version ordering](https://developer.android.com/studio/publish/versioning)
and [signing continuity](https://developer.android.com/studio/publish/app-signing).

Rollback means rebuilding a retained compatible source/payload set with the
same owner key and a higher version code. Preserve the last known-good receipt,
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
phone import and the final player UI remain unqualified. Cancellation must leave
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

These are concrete acceptance cases for the eventual alpha flow, not claims
that it exists. Extend the existing [owner APK producer](../tools/phone-build/owner-apk/README.md),
input admission and device ownership owners; do not introduce a second signing,
installer or input-acceptance pipeline. Keep detailed receipts private and publish
only reviewed summaries. The prepared-lab [playtest checklist](PLAYTESTING.md)
remains the desktop fallback.

| Boundary | Required case and evidence | Existing coverage and remaining gate |
| --- | --- | --- |
| Final package identity | Independently inspect the assembled and installed package as `dev.ror2lab.alpha`. On an occupied identity, require its local ownership receipt and matching signing certificate before updating; refuse an unowned or conflicting signer without uninstalling. Record actual installed APK hash, version, placement and runtime backing. | `binary_manifest.py` preserves the supplied package identity; its authored fixture proves that preservation. It does not select the alpha identity. The current laboratory/device ownership contract and J1065 are reusable, but neither qualifies an alpha installation. |
| Issued versions | Allocate positive codes through 2,100,000,000 from durable owner-local state. Build two updates from the same frozen source manifest and prove the second code exceeds the first issued code. Refuse reuse, lower codes and exhaustion before dispatching installation. A failed or cancelled attempt must not allow a previously issued code to be reused. Bind every issue to the source/input/toolchain/APK/payload/certificate receipt required above. | `binary_manifest.py` checks only that an explicit code exceeds the supplied manifest version, accepts through the policy maximum of 2,100,000,000 and permits omission. Request admission refuses a larger explicit code before creating output. Durable issued-version allocation and mandatory final-flow codes are additional integration gates; passing the manifest tests does not establish monotonic owner updates. |
| Signing and recovery | Sign separate builds with the same owner certificate, then independently verify signatures, alignment and unchanged nonsignature content. Refuse redirected, exposed or incomplete existing key state without replacing a retained key. Qualify a private recovery backup and restoration with that same certificate before the first alpha installation. | `build_owner_apk.py` owns durable key reuse and signing verification; `test_owner_signing.py` covers authored key reuse, tool failure and unsafe existing custody. J1095 qualifies authored phone signing, not final game packaging, certificate-bound install admission or backup recovery. |
| Legitimate local input | Admit the complete reviewed inventory, then repeat with an unknown version, missing file and changed bytes under otherwise identical filenames. Each refused attempt leaves the legitimate installation unchanged and creates no accepted build/current pointer. Recheck admitted input after processing so a mid-operation change cannot become accepted output. | The desktop inventory/acceptance preflight and source producers supply admission contracts. The private replay APK builder accepts a target profile, not arbitrary original PC files. Final phone import/UI and honest unknown-version refusal remain unqualified. |
| Cancellation and updates | Cancel local acquisition before copying and during processing, then restart. Source bytes stay unchanged; incomplete output is never Ready, launchable or selected as accepted. Separately prove a normal installer update and a compatible higher-code rollback retain real game profile/settings across cold starts. Refuse incompatible schemas. | `PayloadStore.java` and its actual Java harness cover per-file packaged-payload pause/restart, exact drift consent, retained backups and failed-stage refusal. They do not implement local PC import cancellation. J1065 qualifies retained data under the lab identity and ADB installation; final alpha identity, ordinary installer and rollback cases remain open. |

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
