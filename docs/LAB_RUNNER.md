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
| `toolhost` | builds the phone toolhost (the #163 installer host) from `ref` with the owner's local builder on the build phone, cached by commit; never installs |

With `device=<alias>` (aliases come from ignored `work/config/lab-runner.json`) the job takes the
orchestrator's atomic device lease, refuses a battery above 85 %, actually charging at 80 % or more, or
at 35 C or warmer, receives `--device` (for `dev`) or `LAB_DEVICE_SERIAL` (for `script`), and always
puts the display to sleep and releases the lease. Every job ends with `prune-generated.py --apply`.
The reply shows PASS/FAIL, the command, duration and the last 150 output lines with home paths,
serials, storage UUIDs, emails, IPs and tokens removed. Full output: `work/coordination/lab-runner/<run>/`.
Jobs run one at a time in comment order. Every job also gets `LAB_TOOLHOST_ROOT`: `toolhost` writes
`<commit>/signed.apk`, `result.json` and `test-publisher.json` (the local path of the test publisher key the
build trusts) there, so a later `script` job can install that build and sign synthetic test releases.

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
