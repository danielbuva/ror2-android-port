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

## Current local emission request

After obtaining the orchestrator's device grant, use the same runner locally:

```
source scripts/env.sh
.local/lab-venv/bin/python scripts/lab/lab_runner.py --emission-request <config.json> --dry-run
.local/lab-venv/bin/python scripts/lab/lab_runner.py --emission-request <config.json>
```

The ignored JSON config has exactly these fields:

| Field | Value |
| --- | --- |
| `runner` | `repo` canonical checkout path, `ref` fetchable branch/commit, `device` configured alias |
| `tool_apk`, `manifest` | Each has an absolute `path` and `sha256` |
| `request` | Relative staged request path for `bundle_preload.py --inputs` |
| `done_file` | New absolute terminal JSON path under canonical `work/` |
| `expected_records` | Positive expected native record count |
| `estimated_output_bytes` | Positive output-space budget, in addition to inputs and 20 GiB reserve |
| `profile` | `thor` or `nova` thermal profile |
| `timeout_seconds` | Positive producer time budget |

The manifest's `files` maps relative staged paths to `source`, `bytes` and
`sha256`. Include the public producer closure beneath `repo/`; this operation
executes the tracked `phone_runner.py` and `bundle_preload.py` there. It streams
the pinned APK's Python runtime and pinned inputs without host archive copies.
Dry-run validates pins without device access. Live execution uses the standard
fresh checkout, lease, cooldown, package-identity, storage and display owners.
The current runtime staging supports configured internal-only devices; adopted
storage is refused without an internal-storage fallback.

Before a new producer qualification, repin the existing manifest explicitly:

```
.local/lab-venv/bin/python scripts/lab/lab_runner.py --emission-request <config.json> --refresh-emission-manifest <clean-checkout>
```

This host-only action validates the existing pins, replaces only `repo/` entries
with tracked files from a clean committed checkout, updates the manifest's total
bytes/source diagnostics and outer hash, and sets `runner.ref` to that commit.
Publish that commit before live execution. Every non-repo input pin is preserved.
A changed manifest needs fresh device staging; it cannot resume an old identity.

`device-state.json` beside the terminal path records the owned toolhost,
staging root and detached handle before launch. The on-phone thermal supervisor
owns producer duty cycling. Receipts and logs return to the host; output bundles
and the emission cache stay in the owned app for the next pipeline stage.
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
