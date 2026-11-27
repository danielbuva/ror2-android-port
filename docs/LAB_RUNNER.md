# Lab runner bridge

The lab runner lets a remote agent (for example ChatGPT Dots, which works only from GitHub) build, test
and run on the owner's Mac and phones without receiving any game files. The agent writes code on a
branch and posts a `/lab ...` comment as the repository owner; the owner's self-hosted runner runs the
job locally and replies with a sanitized summary. Game files, device data and raw logs stay on the Mac.

## Commands

Post on any issue or pull request (first line only):

```
/lab <job> [ref=<branch|sha>] [device=<alias>] [-- args...]
```

| Job | Runs (in a fresh worktree of `ref`, default `main`) |
| --- | --- |
| `status` | host free space, held device leases, each device's battery state and admission |
| `host-tests` | `scripts/host-tests.py [args]` |
| `preflight`, `doctor` | `./dev preflight` / `./dev doctor` |
| `dev <action> ...` | `./dev <action> ...` for build, install, run, logs, screenshot, crash, storage, inspect, test, check-baseline, sync-data, perf, graphics, diagnostics, lane |
| `script <path.py> ...` | a Python file under `tools/`, `scripts/`, `recipe/` or `tests/` with the lab venv |
| `toolhost` | builds the phone toolhost (the #163 installer host) from `ref` as the disposable package `dev.ror2lab.installertest` with the owner's local builder on the build phone, cached by commit; never installs |

With `device=<alias>` (aliases come from ignored `work/config/lab-runner.json`) the job takes the
orchestrator's atomic device lease, refuses a battery above 85 %, actually charging at 80 % or more, or
above 35 C, receives `--device` (for `dev`) or `LAB_DEVICE_SERIAL` (for `script`), and always
puts the display to sleep. Charging admission requires three positive-current samples 10 s apart.
The lease is released unless an emission job's remote outcome is unknown. Every job ends with
`prune-generated.py --apply`.
The reply shows PASS/FAIL, the command, duration and the last 150 output lines with home paths,
serials, storage UUIDs, emails, IPs and tokens removed. Full output: `work/coordination/lab-runner/<run>/`.
Jobs run one at a time in comment order. Every job also gets `LAB_TOOLHOST_ROOT`: `toolhost` writes
`<commit>/signed.apk`, `result.json` and `test-publisher.json` (the local path of the test publisher key the
build trusts) there, so a later `script` job can install that build and sign synthetic test releases.

## Tour an already-installed alpha release

Run the current `./dev device-session --request <private JSON> --dry-run` with
`serial` in the request. After the device grant, run the same action with
`--device SERIAL --detach` in place of `--dry-run`. Choose
`mode: "installed-alpha"` and `package: "dev.ror2lab.alpha"`. Supply
`canonical_root` for the main checkout, private `output` under its `work/`,
`workstream` and `duration_seconds`. Use `installer_apk`, `installer_package`
and `installer_sha256` to select the authorized, debuggable production installer with
provisioned publisher keys. Use the selected publisher release's fingerprint
as `source_sha256` and its published `public-tools.zip` as `public_tools`.
The signed recipe supplies the runtime attempt. The installer receipt and
on-device readback supply the installed APK hash. Use a device with working
controls for that release. Nova requires the game's matching Nova input map.

The runner records bootstrap Play, Unity activity focus, character select,
one ordinary first stage, and return to character select via End Run. It
writes JSON receipts and the first failure, then stops the game and sleeps
the display. A separate native title screen is currently unobserved.

## Current local packaging request

Use the installer APK and receipt cached for the checkout's commit. A packaging
request can set `toolhost_source_commit` to reuse a verified earlier fixture when
the embedded installer inputs match. Keep the cache pinned with `.prune-keep`
until qualification finishes. An ignored JSON request names the canonical
`repo`, linked `checkout`, configured `device` alias, granted `workstream` and
new absolute `done_file` under canonical `work/`.

```
source scripts/env.sh
.local/lab-venv/bin/python scripts/lab/lab_runner.py --packaging-request <config.json> --dry-run
.local/lab-venv/bin/python scripts/lab/lab_runner.py --packaging-request <config.json> --detach
```

Dry-run verifies the cached installer and prepares the synthetic fixtures without
accessing the device. The detached runner checks the grant before taking the
lease, then invokes the existing package and signing acceptance. The shared
thermal monitor verifies cool-start admission and records the run's thermal
trace. The shared display owner wakes only the authorized display at the first
installer launch and verifies sleep and mode restoration after the UI flow.
The runner retains installed receipts, versions and hashes before disposing of
the owned fixtures.
The terminal receipt links the private log after cleanup and pruning.
To prepare the APK, use a separate request with `"operation": "toolhost"`,
`"device": "thor"` and a Thor grant. This calls the configured toolhost builder,
which owns the build lease, and pins the output recorded by the terminal receipt.
Set `backup_installer_key` to `true` on that request to also retain the
test signer locally. The backup reads its two files under the granted Thor
lease, checks the fixture certificate, and stores them under ignored `work/`
with mode 0600. An existing matching backup is reused.
Set `toolhost_source_commit` to a successful retained Thor build's full source
commit on the same request to back up its signer without starting a new build.

With the backup and a retained fixture build, the Mac can rebuild the disposable
installer on a clean checkout without a device grant. Supply an Android Build
Tools `zipalign` with `-P 16` support alongside the SDK selected by `scripts/env.sh`.

```sh
source scripts/env.sh
.local/lab-venv/bin/python scripts/lab/installer_toolhost.py --base <retained-cache-entry> --zipalign <zipalign>
```

This compiles the current Java and manifest, packages the tracked installer
sources and verifies every retained runtime asset and Android library.
The build refuses changed native/runtime inputs and records the base commit
and hash next to the new APK. The repack verifies current authored source pins
against the tracked files it embeds and caches the APK by checkout commit.
For a local staged-release check, pass `--release-trust <public-key-config.json>`.
Use the retained repository and application ID with the publisher RSA public
keys in `keys`. The repack records the trust hash and prints a separate cache
key. Use `signed.apk` from that entry and its receipt hash as `installer_apk`
and `installer_sha256` in the staged-update request.
An explicitly staged Android build can also seed this rebuild. Use its
request-keyed cache directory. For an older receipt without source and signer
fields, replay its original packaging request against the original checkout with
a fresh terminal path. A cache hit rechecks the signed APK against the original
stage and writes those fields without a device lease.

For Android input qualification, set `operation` to `acquisition` and add
`current_inventory`, `current_source`, `older_inventory` and `older_source`.
The inventories are local lab inventory JSON files. Each source path points to
its complete legitimate game folder. The first test catalog supports the
current inventory. The second also recognizes the older inventory for refusal.
An optional `toolhost_source_commit` selects a previously built cache entry.
The acquisition runner checks its stage/build receipts and requires matching
installer runtime sources and the disposable APK's document fixture. The dry-run
checks the catalogs and source shape. The detached run stages the cohorts and
invalid controls in a scoped Downloads directory. A private one-use command
invokes the normal buttons in the debuggable installer-test package. Android's
system picker grants read access through the external storage provider. The
shared display owner verifies top-panel-only use on Thor and restores its prior
mode when the picker tests end. The run restarts the installer before importing
the supported selections, verifies a mid-copy cancellation and resumed import,
and hashes staged files before and after acquisition. It then removes its owned
files and installer.

For a signed source-release update, set `operation` to `staged-update` and add
`installer_apk`, `installer_sha256`, `installer_version`, `game_label`,
`current_inventory`, `current_source`, `baseline_release` and `update_release`.
Each release directory supplies its signed manifest, signature and public tools
ZIP. Use a disposable installer with the publisher key in its packaged trust.
The dry-run verifies both signed source graphs and checks that both support the
current inventory. The detached run serves the releases over local ADB reverse,
imports the staged originals through Android's picker, and checks native save
retention across a same-key update. Each play phase writes a
`terminal.done.json` bound to the live APK hash and signed runtime attempt.
The whole-game scoreboard can join those receipts to a census of the same APK.
Cleanup removes the scoped stage and the packages the run installed. Import
and each reconstruction have a four-hour limit to accommodate the measured
signed native build.

To build a specific managed installer stage, add a `toolhost_inputs` object.
Set `stage_receipt` to its local `{path, sha256}` pin and `tool_root` to the
existing Android tool workspace containing `material/`, `archives/` and the
retained signing key. Set `signer_sha256` to the expected certificate digest.
Optional `native_sources` maps planned native filenames to local provider files
when those providers need transfer. Host files must match the existing
`backend-tools.json` and Python provider pins. This request uses the
retained signer. Use a commit-keyed toolhost request to back up the signer.

Run `--dry-run` to check the staged files, checkout and host providers. The
shared lease covers transfer, supervised Android build and scratch cleanup.
The terminal receipt identifies a verified APK cached by commit and request
pins. A missing terminal device status retains the lease and the private
detached handle for reconciliation.

## Run a converter stage on the phone

`./dev converter-stage <producer> --request <config.json> --workstream <name>`
runs a registered content producer against pinned inputs. Use the producer's
filename stem with hyphens, for example
`bundle-preload`, `mesh-produce`, or `texture-produce`. Run with `--dry-run`
before queuing the phone. Run the live command detached once the dispatcher
grants the phone. The shared runner checks the toolhost identity, grant, battery
and storage, and owns thermal supervision and cleanup.

Use the emission config below with `"operation": "converter-stage"` and
`"request": "stage.json"`. Omit `expected_records`. Set
`retained_tool_sha256` to reuse the exact installed toolhost. For a fresh
disposable install, omit that pin and supply every descriptor input in the
manifest as `inputs/<input_root>/<relative path>`. The manifest maps
`stage.json` to the host descriptor pin and lists any additional producer
dependencies as `repo/<tracked path>`
keys. The action pins all producer paths to the calling checkout's clean
commit, adds the selected script and the runner's support files, and writes a
new manifest beside the terminal receipt. The toolhost supplies the
Python runtime. The current runner accepts internal-only toolhost staging.

An example descriptor for a prepared bundle request is:

```json
{
  "producer": "tools/phone-build/accepted-output/bundle_preload.py",
  "input_root": "prepared-input",
  "input_pins": {"inputs.json": "<sha256 of the staged request>"},
  "arguments": ["--inputs", {"inputs": "inputs.json"}, "--output", {"output": "."}],
  "artifacts": {"bundle": "<produced bundle name>"}
}
```

`input_root` is relative to the retained toolhost's `files/owner-input` or
the fresh scratch input directory.
Pass the stage's read-only input files under `inputs` and its generated files
under `output`. Path arguments also accept `repo`, `native`, and `runtime`.
Use `.` for the root itself. Artifact paths and the optional `scoreboard`
path are relative to the output root. A producer's own structural checks still
run. Bundle preload runs with one record worker on Android.

The terminal directory receives JSON receipts, artifact hashes, and the
optional scoreboard. Every attempt gets fresh device scratch, which is removed
after the terminal result. The runner removes a toolhost installed for the
attempt and preserves an explicitly retained toolhost and its existing inputs.
If the device disconnects during production, use the generated
`*.request.json` with a fresh terminal filename in the same directory and
resume its retained handle through `--emission-request ... --resume-emission`.

Use `whole-game-scoreboard` to census APKs already readable by the retained
toolhost. Its descriptor selects
`tools/phone-build/accepted-output/whole_game_scoreboard.py` and uses arguments
`[{"inputs":"scoreboard-request.json"}, "--output", {"output":"scoreboard.json"}]`.
Pin the request under `input_pins` and set
`"artifacts": {"scoreboard": "scoreboard.json"}` and
`"scoreboard": "scoreboard.json"`. Paths inside the scoreboard request resolve
from the descriptor's retained input root. The request pins the candidate,
optional reference, and any external payload receipts with the same format as
the [host census](../tools/phone-build/accepted-output/README.md#whole-game-scoreboard).
The lab runner stages its two Unity readers automatically.

## Current local emission request

After obtaining the orchestrator's device grant, use the same runner locally:

```
source scripts/env.sh
.local/lab-venv/bin/python scripts/lab/lab_runner.py --emission-request <config.json> --dry-run
.local/lab-venv/bin/python scripts/lab/lab_runner.py --emission-request <config.json> --workstream <name>
```

The ignored JSON config has exactly these fields:

| Field | Value |
| --- | --- |
| `runner` | `repo` canonical checkout path, `ref` fetchable branch/commit, `device` configured alias |
| `tool_apk`, `manifest` | Each has an absolute `path` and `sha256` |
| `retained_tool_sha256` | Optional exact hash of the already-installed bundle toolhost, matching `tool_apk.sha256` |
| `request` | Relative staged request path for `bundle_preload.py --inputs` |
| `done_file` | New absolute terminal JSON path under canonical `work/` |
| `expected_records` | Positive expected native record count |
| `estimated_output_bytes` | Positive output-space budget, in addition to inputs and 20 GiB reserve |
| `profile` | `thor` or `nova` thermal profile |
| `timeout_seconds` | Positive producer time budget |

The manifest's `files` maps relative staged paths to `source`, `bytes` and
`sha256`. Include the public producer closure beneath `repo/`; this operation
executes the tracked `phone_runner.py` and `bundle_preload.py` there.

Android record emission explicitly uses `--workers 1`: the packaged Python has
no `_multiprocessing` extension. The operation's `record_workers` records this
selection; the thermal receipt's `workers` remains the native-library limit.
Host emission still defaults to two record workers. Structural checks and cache
checkpoints are the same in both modes.

The operation streams the pinned APK's Python runtime and pinned inputs without
host archive copies.
With the retained toolhost pin, each fresh request discovers the installed
runtime path and creates a fresh staging root and cache. After collecting
terminal evidence it removes that root and preserves the installed toolhost.
Use a separate terminal directory for each cold run. Resume applies only to an
unconfirmed handle in this mode.
Dry-run validates pins without device access. Live execution with `--workstream`
verifies the named grant and takes the lease before device admission. Use the
same workstream to reattach to a retained lease. Pass `--strict-battery` when
seeding inputs for a converter stage to apply the same charge limits as replay.
Execution uses the standard fresh checkout, cooldown, package-identity,
storage and display owners.
The current runtime staging supports configured internal-only devices; adopted
storage is refused without an internal-storage fallback.

For a paired UnityFS decoder benchmark, set `operation` to `bundle-decode`
and replace `expected_records` with `expected_blocks` and
`expected_decoded_sha256`. The latter pins the SHA-256 of the concatenated
decoded blocks in bundle order. Both pins include raw blocks. Set `request`
to the staged bundle path and provide the exact
`retained_tool_sha256`. The manifest includes `baseline-unity_bundle.py` from
the baseline revision and the candidate's tracked `bundle_decode_benchmark.py`,
`unity_bundle.py` and `phone_runner.py` under
`repo/tools/phone-build/accepted-output/`. The supervised child decodes each
block with both versions in alternating order and requires equal bytes. Only
the receipt is written. It records per-decoder CPU time, elapsed time and peak
RSS. The runner retains the thermal trace and removes the staged inputs.

Before a new producer qualification, repin the existing manifest explicitly:

```
.local/lab-venv/bin/python scripts/lab/lab_runner.py --emission-request <config.json> --refresh-emission-manifest <clean-checkout>
```

This host-only action validates the existing pins, replaces only `repo/` entries
with tracked files from a clean committed checkout, updates the manifest's total
bytes/source diagnostics and outer hash, and sets `runner.ref` to that commit.
Publish that commit before live execution. Every non-repo input pin is preserved.
A changed manifest needs fresh device staging; it cannot resume an old identity.
Use `--restage-emission` with a new terminal path in the same directory to replace
the owned staging after a confirmed terminal outcome. This explicitly discards
that attempt's inputs/cache and streams the new pins; the installed toolhost must
still match its ownership hash. Unknown outcomes refuse restaging.

`device-state.json` beside the terminal path records the owned toolhost,
staging root and detached handle before launch. The on-phone thermal supervisor
owns producer duty cycling. Receipts and logs return to the host; output bundles
and the emission cache stay in the owned app for the next pipeline stage.
The supervisor waits through valid warm admission samples before launching a
producer, reporting `cooling`; cancellation, sensor validation and the wall
deadline remain active. CPU/GPU/skin must be at most 50 C and battery at most 35 C.
Receipts include admission duration and the peak's phase.
Neither a producer failure nor a lost host connection uninstalls that app.

To retry, use a new `done_file` **in the same directory** and add
`--resume-emission`. An uncertain job is observed through its original handle;
a confirmed terminal job starts a fresh output attempt with the same cache.
A retained lease can be reclaimed only for that exact state/handle after its
previous runner exits. Reattachment does not start another producer or require
the active producer to cool down. The final done-file is written after runner
cleanup and pruning, including on failure. Retention is temporary: after downstream
consumers finish, dispose of the owned toolhost with its exact identity receipt.
Host tests cover this contract; on-device qualification remains separate.

### Signed source code qualification

For current signed code conversion, add `"operation": "signed-code"` and use
`expected_managed_providers` in place of `expected_records`. The pinned private
request selects `source_inputs`, the signed `audio_members` roster and an
`output` relative to its private `work/` directory. Stage the accepted input
inventory, `input-hashes.json`, original game and compiler inputs beside that
request. Include the matching public producer closure under `repo/`.

The same runner stages Python, both .NET frameworks and Clang resources from
the pinned toolhost APK. Its existing Android code adapter runs fresh managed
compilation, audio roster verification, UnityLinker, IL2CPP conversion and native
planning. The terminal receipt records the provider count, converter file
hashes, wall time, peak memory, storage and thermal sampling. This gate ends at
the native plan. Before removing its owned scratch, the runner streams child
logs and app-owned crash files to the private run directory. Failed runs also
capture Android's crash buffer and package exit history. If transfer fails,
the runner retains its exact handle and scratch for `--resume-emission`.
After a confirmed result, use a fresh request directory for another attempt.

### Signed native qualification

Use `"operation": "signed-native"` with `expected_managed_providers`. The pinned
private request selects `bundle`, `envelope`, `public_key`, `key_id` and an
`output` relative to its private `work/` directory. The public source bundle
must select the Burst library, IL2CPP library and matching metadata. Generate
its jobs with the owner code, Burst and native token requests and the staged
audio roster. Stage the SDK, original, package and GNU tool inputs beside the
request. Pin the accepted inventory in the transfer manifest and keep mutable
inventory and configuration files out of `input-hashes.json`.

The runner verifies the envelope and source bundle, then dispatches the
conversion and native jobs under the same thermal supervisor. The terminal
receipt records managed provider and compile counts, readback hashes for all
three native outputs, and resource measurements. The runner captures the
receipts and cleans the attempt's scratch after a confirmed result.

## Safety model

- The workflow (`.github/workflows/lab-runner.yml`) triggers only on `issue_comment`, so GitHub always
  runs main's copy, and only when the comment author is the repository owner with `OWNER` association.
- It runs main's `scripts/lab/lab_runner.py` (fetched from `origin/main`), so a branch can change what a
  job builds but not which jobs exist or how leases, battery checks and sanitizing work.
- The runner's job-started hook (`scripts/lab/lab-runner-guard.sh`, installed outside the repository)
  refuses every job that is not main's `lab-runner` workflow on an owner comment. A branch that adds its
  own `runs-on: self-hosted` workflow for `push` or `pull_request` therefore never runs on the Mac.
- Code on the requested branch does run on the Mac with the runner user's permissions: trust a remote
  agent the way you trust a local Codex worker. The AGENTS.md boundaries apply to it in full.

## One-time setup (owner)

1. GitHub: repository **Settings → Actions → Runners → New self-hosted runner**, macOS, ARM64. Run the
   shown download commands in a folder outside the repository (for example `~/actions-runner`), then
   configure with the shown token plus the lab label:
   `./config.sh --url https://github.com/danielbuva/ror2-android-port --token <TOKEN> --name ror2-lab-mac --labels ror2-lab`
2. Install the guard where no branch can change it:
   `mkdir -p ~/actions-runner-hooks && cp scripts/lab/lab-runner-guard.sh ~/actions-runner-hooks/ && chmod 555 ~/actions-runner-hooks/lab-runner-guard.sh`
3. Add to `~/actions-runner/.env` (absolute paths):
   ```
   ACTIONS_RUNNER_HOOK_JOB_STARTED=<home>/actions-runner-hooks/lab-runner-guard.sh
   LAB_REPO=<absolute path of this repository checkout>
   PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
   ```
4. Start it as a service: `./svc.sh install && ./svc.sh start` (or `./run.sh` in a terminal).
5. GitHub: **Settings → Actions → General → Fork pull request workflows from outside collaborators**:
   require approval for all outside collaborators.
6. Check: comment `/lab status` on the work-queue issue; the runner replies within a minute.

To pause the bridge, stop the service (`./svc.sh stop`); to remove it, `./svc.sh uninstall` and delete
the runner under Settings → Actions → Runners.
