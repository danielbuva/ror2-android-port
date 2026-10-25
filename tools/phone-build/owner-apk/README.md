# Owner APK payload bootstrap candidate

Current experimental installation support after accepted-output reconstruction.
The private candidate's preparation, increasing-version upgrade, Unity lifecycle
and assisted standard controls are device-qualified in
[J1065](../../../docs/PORTING_JOURNAL.md#j1065--qualify-private-owner-apk-preparation-upgrade-and-unity-lifecycle).
[J1095](../../../docs/PORTING_JOURNAL.md#j1095--retain-one-on-device-owner-key-across-separate-apk-signing-builds)
qualifies durable phone signing on authored APKs. Ordinary app packaging-tool
hosting, installer UI and independent PC-input production remain open; this is not an adopted final distribution architecture.
Game-bearing packets, APKs, metadata and outputs remain private under
ignored `work/`; no key or game content belongs in Git.

Android 11 [restricts other apps' external app-specific directories](https://developer.android.com/about/versions/11/privacy/storage).
A separate launcher cannot simply reproduce the lab's ADB payload sync. This
candidate instead includes the owner's verified runtime payload in the owner's
APK. An authored Android entry activity prepares its own
`getExternalFilesDir(null)/payload`, matching the existing `Device.sync` and
`WholeCatalogComposed` contract, then starts the original Unity activity.
Android [provides this app-specific location without storage permission](https://developer.android.com/training/data-storage/app-specific).

The replay control preserves native IL2CPP libraries, original DEX files, game
resources and payload hashes. Explicit produced-code selection replaces the
selected cohort with the producer's actual bytes. Binary manifest structure editing moves only the
original MAIN/LAUNCHER filter into the new authored activity and makes the
original Unity entry private to prevent bypassing preparation. Resource indices
and all other original activity/application attributes remain intact. No Unity
project, source text replacement, stripping, game compilation, runtime backend,
shader mechanism or replacement content loader is introduced.

## Owners and lifecycle

- `PayloadStore.java` owns bounded streaming, exact hashes, fresh storage
  admission, per-file staging/rename and retained backups. Unknown existing
  contents require an exact observed-hash review before replacement. It writes
  only named prepared files and its own stage/backup directories; saves and
  settings are outside its target set. Pause takes effect between files.
- `PayloadBootstrapActivity.java` owns the app entry, worker, private completion
  receipt, native update consent, launch verification and WebView lifecycle.
  A process restart rechecks actual files; a receipt alone never makes it ready.
  Completed files survive pause/restart, and failed stages/backups are retained.
  After Unity is requested, this process cannot prepare replacement data. The
  WebView is released before handing off to Unity. A same-process launcher
  re-entry resumes the already prepared Unity activity directly. The lab's old direct exported-Unity
  launch helper is not the candidate's public entry; exercise its bootstrap/Play
  path rather than changing the shared helper for this experiment.
- `owner-host.js` connects the approved frontend's adapter v1 to fixed native
  actions. It exposes no paths, account state, arbitrary JavaScript/shell or file
  access. Polling/subscription teardown does not cancel preparation. Only bundled
  allowlisted HTTPS-origin resources are served; navigation/network are blocked.
- `index.html` provides accurate owner-APK preparation copy while reusing the
  unchanged approved `launcher/{app.js,controller.js,style.css,background.png}`.
  The simulated demo is never included. There is no new tracked PNG exception.
- `binary_manifest.py` edits binary XML using the existing public `phone_apk.py`
  chunk/string reader. `build_owner_apk.py` compiles only the authored Java to a
  separate DEX, assembles the owner APK and independently hashes every entry.
  No current `./dev` game build consumes this path.

Preparation reserves 2 GiB plus all required new data and metadata margin.
Source and output stream in 64 KiB blocks; the largest bundle is not read into
one Java array. Backups and failed stages count against fresh capacity. This
approach stores payload in both the installed APK and prepared app files: its
size/space cost and actual installer behavior must be measured before adoption.
It never formats storage, relocates another app or clears user data to fit.

## Build the complete private candidate

Use the exact accepted file layout/profile supported by `accepted-output/`. An explicit
ignored request JSON contains these paths and the manifest SHA:

```json
{
  "manifest": "PRIVATE_PACKET_MANIFEST",
  "manifest_sha256": "93789f88d8fff178e31e1a4b78bc5cf735bb63f6e17d8bfd4518474dbff99d4a",
  "targets": "VERIFIED_RECONSTRUCTED_OUTPUT_ROOT",
  "frontend": "PUBLIC_REPOSITORY_LAUNCHER_DIRECTORY",
  "java": "SUPPLIED_JDK_BIN_JAVA",
  "android_jar": "SUPPLIED_ANDROID_API_30_JAR",
  "d8_jar": "SUPPLIED_BUILD_TOOLS_34_D8_JAR",
  "wire_helper": "PUBLIC_REPOSITORY_SCRIPTS_LAB_PHONE_APK_PY",
  "version_code": 2
}
```

```sh
python3 -I -S tools/phone-build/owner-apk/build_owner_apk.py \
  --request PRIVATE_REQUEST.json --output NEW_PRIVATE_OUTPUT_DIRECTORY
```

`version_code` is optional. Omission retains the frozen manifest version. An
explicit value must be a positive Android integer greater than the frozen
input version; select a value greater than every previously installed owner
version for an update. Only that typed manifest attribute changes in addition
to the launcher routing. Retain the same private signing key across updates.

For independently produced code, add one `code` dictionary mapping these three
APK entry names to canonical absolute output files:

- `lib/arm64-v8a/libil2cpp.so`
- `assets/bin/Data/Managed/Metadata/global-metadata.dat`
- `lib/arm64-v8a/lib_burst_generated.so`

All three are required together: a source-code build never silently falls back
to replayed Burst or metadata. To consume the independent Android SDK producer,
include its complete 15-entry cohort in the same dictionary: `AndroidManifest.xml`,
the four original DEX files, `libmain.so`, `libunity.so`, `resources.arsc` and all
five compiled `res/` files and both generic Android `META-INF` build metadata files.
`accepted-output/sdk_package.py` owns the exact
`SDK_ENTRIES` membership. The selection accepts exactly three or 18 entries;
partial SDK cohorts and unknown names refuse. Each value is an explicit
canonical absolute file path. The produced manifest feeds the existing launcher
and version patch; produced DEX/resource/native bytes stream unchanged into the
APK, including independently explained compiler checksum differences.
Their comparison-target files need not exist.
The builder records actual hashes/sizes, rechecks every source and verifies ZIP
readback; every other content/payload path retains its existing target hash.
Host assembly fixtures cover all 18 selected outputs with no corresponding
replay files, produced-manifest consumption and input-drift refusal. Complete
phone composition, installation, controls and matched performance remain open.
The `targets` root is the content producer's existing `apk/` plus `payload/`
file tree, not a record pack. Omitting `code` retains the existing private replay
control. This input selection does not establish source provenance or runtime
compatibility: retain the producer evidence, complete Burst ABI and full-player
phone/install/performance qualification. The synthetic assembly contract passes
with all comparison-target code files absent (J1102).

Before assembling, inventory the same request without invoking Java or writing
an APK:

```sh
python3 -I -S tools/phone-build/owner-apk/build_owner_apk.py \
  --check-request PRIVATE_REQUEST.json --output NEW_PRIVATE_READINESS.json
```

This current host/Android action needs only `manifest`, `manifest_sha256`,
`targets`, optional existing `code` mapping and optional `drift` evidence from
that request. The target
root and selected produced files may be absent: the report lists every required
final entry as ready, missing, mismatched or invalid. An absent produced code
file remains missing even if its comparison file exists under `targets`.
Obsolete signatures and payload `.manifest` sidecars are omitted, matching the
assembler. Exit 0 means all assembly inputs are available; exit 1 means entries
are blocked. A report must be a new file.

Each available entry records actual size/hash and raw target equality.
`code_comparison_required` lists produced code/SDK entries whose raw bytes differ;
the assembler preserves these actual bytes, allowing independently documented
compiler and ELF metadata differences. Content matches its existing target
hash unless explicitly admitted as `drift-explained` below. The selection distinguishes complete produced code/SDK, produced game
code alone and the replay control. Neither a hash match nor a supplied tree
proves source provenance or phone/runtime qualification; both qualification
fields stay false. Keep the producer journals with the report. Mesh/avatar/
texture object/resource packs are intermediate records and cannot fill a final
bundle/player-data target entry.

### Current-input drift evidence

J1153 implements the current-install input policy without changing exact hash
admission. An optional `drift` dictionary maps a changed **content** target path
(including `apk/` or `payload/`) to three pinned private JSON documents:

```json
{
  "drift": {
    "payload/example.bundle": {
      "historical_exact": {"path": "/PRIVATE/historical.json", "sha256": "SHA256"},
      "current_deterministic": {"path": "/PRIVATE/current.json", "sha256": "SHA256"},
      "difference_map": {"path": "/PRIVATE/map.json", "sha256": "SHA256"}
    }
  }
}
```

All three documents require `success: true`, `path` equal to the dictionary's
target, and nonempty `evidence` containing pinned `{path, sha256}` references to
the retained raw producer/comparison receipts. Every receipt path is canonical
and absolute. Pins are rechecked through assembly; explicit failed raw evidence
refuses. The documents contain these additional fields:

- `historical_exact`: `producer_sha256`, `bytes`, `sha256`. The complete output
  must match the existing target pin. Historical originals qualify the producer
  only; neither the checker nor assembler reads them or their generated outputs.
- `current_deterministic`: the **same** `producer_sha256` and at least two `runs`,
  each with a distinct `id` identifying its actual invocation, `bytes`, `sha256`.
  Retained raw evidence must identify both executions. Every run must match the
  actual current supplier. Changing producer source requires requalification.
- `difference_map`: `inputs` and `operations`. Each input pairs `historical` and
  `current` relative original-game `{path, bytes, sha256}` identities; one may be
  `null` for additions/removals. The identities must differ. Each operation has
  half-open `historical_range` and `current_range`, `historical_sha256` and
  `current_sha256`. Operations partition both complete files in order, including
  equal extents and zero-length insert/delete sides. Changed extents additionally
  require nonempty `inputs` indexes into the input list and a nonempty `reason`.
  Every current extent is hashed directly from the assembly supplier.

The documents are reviewed qualification summaries of the pinned raw evidence,
not independent proof of semantic causation. The checker verifies their explicit
contract and current bytes; human review establishes the public producer,
independent executions and original-input lineage. It cannot establish these
facts from hashes alone. `source_provenance_verified` and `device_qualified`
remain false. Do not normalize a receipt from an earlier producer as though it
came from a later one or use target bytes to fill missing production.

`exact_count` counts raw-exact available entries. `drift_explained_count` counts
only admitted changed content, whose status is `drift-explained` and whose
`target_equal` remains false. Produced code with raw ELF/compiler differences
remains in `code_comparison_required`, separate from both counts. Missing,
unexplained, malformed or stale evidence stays blocked. The assembler preserves
admitted current bytes and hashes, including the embedded Android payload index;
it never substitutes historical bytes. Keep these required private evidence
inputs with their producer receipts as described in
[LOCAL_STATE](../../../docs/LOCAL_STATE.md).

The normal build writes the same `readiness.json` and refuses all blocked inputs
before launcher compilation or ZIP creation. Once the content owner materializes
its final tree, use that unchanged request with `--request`, then pass the new
`owner-unsigned.apk` to the existing `--sign-request` mode below. No replay bytes
are selected automatically. A separately labelled replay-content validation run
can exercise assembly/signing while final content production and corrected
phone-native output remain open; it is not a source-input production result.

Keep the public source tree's relative `owner-apk/` and `accepted-output/`
directories together when staging on Android. Supply the wire helper explicitly;
the builder never finds a timestamped analysis directory. SDK/tool acquisition
remains owner supplied; no redistribution permission is inferred by compilation.

The new unsigned ZIP uses deterministic entry metadata and aligned, uncompressed
`resources.arsc`. It uses ZIP32 and refuses unsupported archive size rather than
silently producing a ZIP64 APK. Canonically check alignment, owner-sign with a
persistent private key and verify signatures/alignment/content before installing.
Installation requires the explicit authorized device, fresh placement/capacity
and ownership receipts. Do not replace the working lab game while another chat
owns its device. Preserve the original input/accepted APK, failed runs and receipts.

## Prior art and acceptance boundaries

The pinned BepInEx.Android.Launcher `fd1a4023` README and Fusion exports were
inspected. They explicitly provide injection/runtime-container hooks; that
mechanism is excluded here. Existing source `WholeCatalogComposed` and the
accepted `payload/whole-catalog.json` supply the measured content contract.
No community implementation is copied. The existing framework, original loader,
serialization identities and gameplay remain authoritative.

J1065 qualifies the complete private candidate through authorized ADB installs,
fresh preparation/readback, pause/interruption/restart, update consent/backup,
unknown-file refusal, retained user data, live placement/backing, public
bootstrap/Play, warm re-entry and both assisted standard controls. Ordinary
Android installer UX, full-player app signing, independent input-only production
and matched performance remain open.
Neither the frontend nor successful extraction claims account ownership,
authentication, DLC access or original-game readiness.


## Durable owner signing

The same owner accepts `--sign-request PRIVATE_SIGN_REQUEST.json --output
NEW_PRIVATE_OUTPUT` after unsigned APK assembly. The request fields are exactly
`unsigned`, `java`, `zipalign`, `apksigner_jar` and `key_directory`, all explicitly
supplied local paths. Tool acquisition remains owner supplied. Keep the durable
key directory separate from build outputs and preserve it across upgrades.

On first use the owner creates `owner.p12` (alias `owner`) and a random private
`password` file in that private directory. Later processes validate/reuse them;
missing or mismatched existing state fails without replacing a key. Back up that
owner key through an authorized private mechanism before removing its host data;
never include it in an APK, recipe, public report or Git. The laboratory fixture's
disposable signing identity is a separate mechanism.

The owner writes new aligned/signed APKs and command/result logs, verifies the
signature and 16 KiB alignment, and checks that every nonsignature APK content
entry and original input/key remain unchanged. It reserves room for two output
APKs plus 2 GiB. It never installs an APK. Failures and private keys remain; only
the explicit disposable output may be removed after retaining needed evidence.
J1095 qualifies two separate phone processes reusing a key for authored APKs;
J1103 qualifies that operation inside the ordinary Android app host. The complete
independent game APK, installer and matched runtime acceptance remain open.

The optional explicit `keytool` signing path and `javac` assembly path support
read-only Android app tool entry names; desktop callers retain their adjacent
JDK executable defaults. The managed-host owner provides those JNI entry points
and the user-triggered Android installer handoff. Signing success alone does
not establish installer, update-signature compatibility or gameplay acceptance.

A fresh owner key supports that owner's first install and subsequent updates.
The existing shared lab package requires explicit provisioning of its matching
signer before a retained-data update; a new key does not inherit that identity.
No existing lab key is shipped or silently selected by this producer.

## Public release updates

`release.py` owns the current host-qualified release contract and incremental
cache. The installer owns download, trust-key provisioning, signature verification,
producer dispatch and PackageInstaller; complete phone updates remain open.
Release assets are `release.json` and `public-tools.zip`, containing only public
recipes, producers, installer and permitted toolchain material. Neither asset
contains an APK, original inputs or game-derived outputs.

`release.json` contains a `release` object and a `signature` object. The release
fields are `version` (display text), `version_code` (positive Android integer),
`application_id`, `minimum_installer_version`, `bundle_sha256` (public-tools.zip),
and `entries`. Each entry key is its relative `apk/` or `payload/` output path;
its value has `recipe_sha256` and `producer_sha256`. Each hash binds the complete
transitive recipe or producer dependency closure, including configuration and
shared tools; dependency changes must change every affected entry fingerprint.
These hashes identify transformations, never downloadable game data.

Signature fields are `algorithm: "SHA256withRSA"`, `key_id`, and base64 `value`.
Sign the bytes from `signed_bytes(release)`: ASCII JSON with sorted keys, compact
separators, ASCII escapes and no trailing newline. Use RSA PKCS1 v1.5 SHA-256.
The installer must verify against its embedded trusted X509 SubjectPublicKeyInfo
key selected by key_id, then hash the downloaded bundle before executing tools.
A downloaded key never establishes trust. Publisher key provisioning and actual
release publication remain separate gates; no private key is tracked.

After verification, call `rebuild` with the release body, actual installed
applicationId/versionCode, installer version, accepted original-input inventory
SHA-256, private persistent cache root and `produce(name, hashes, destination)`.
The callback dispatches existing source-only producers after checking their
recipe/tool hashes; it writes one complete output. The owner checks cached output
hashes and reuses unchanged entries; changed dependencies, missing outputs or a
changed original-input inventory trigger production. Failed production retains
the previous completed output. A successful result returns `rebuilt`, `reused`
and `outputs` (entry-to-path map). Removed entries are absent from that map and
must not be included by a directory scan. Cache files remain owner-private;
no output receipt alone establishes installation or game readiness.

Assemble the selected outputs using the release versionCode, then call
`sign_release` with the existing signing request and durable key directory.
It validates package/version selection and delegates unchanged signing to the
existing owner; updates refuse missing key material before invoking signing.
The installer must independently verify the assembled APK's actual package,
version and signing certificate, then install over the matching installed app.
Losing the key requires exporting saves and an explicit reinstall/reimport path;
a replacement key cannot update an existing installation. Never clear game data
as part of an update. The final alpha identity remains `dev.ror2lab.alpha`;
current disposable lab packaging retains its separately qualified identity.
