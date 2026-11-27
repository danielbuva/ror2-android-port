---
name: orchestrated-worker
description: Use when running as a Codex/Claude worker launched by the orchestrator for this repo (a brief naming a workstream, worktree and device). Defines autonomy, scope, coordination files and the final report format.
---

# Working under the orchestrator

- You own exactly the workstream, worktree and device serial in your brief. Shared resources: the Unity editor (`work/coordination/unity-build.lock`, acquired only through `./dev`), journal numbers, `main`.
- Work autonomously toward a **complete implementation** of the workstream goal. Prefer finishing a whole vertical slice (code + host tests + build + device check + docs) over a chain of tiny probes. Do not stop to ask; record blockers and continue with the next highest-value piece.
- Simplest design that fully meets the goal: no speculative abstractions, option matrices, schema versions or guards for impossible cases; extend existing owners/scripts instead of adding new frameworks. Every new file, flag or receipt field must be required by the goal or an AGENTS.md rule.
- Reuse existing branches/PRs listed in your brief before writing new machinery (`gh pr list`, `git worktree list`).
- Commit logical checkpoints with Conventional Commits. Follow `land-pr` to merge `origin/main` into the branch, run focused checks, push and open the PR. When the brief authorizes merging, immediately arm `gh pr merge --auto --squash --delete-branch` as shown in `land-pr`. GitHub merges after the required `host-tests` check passes and deletes the remote head branch.
- Start the next item from `origin/main` while CI runs. Use `WAITING ci-pr <n>` only when the next step requires the merge. After squash merge, delete the local topic branch and keep the assigned worktree and its symlinks.
- Journal shipped device-verified behaviour and closed readiness or alpha gates. Record routine host-only fixes in their PR.
- Append a status line to `.local/orchestrator/status/<workstream>.md` (timestamp, what changed, next step, blockers) after each milestone so the orchestrator can track you without reading your transcript.
- Before finishing, run `python3 scripts/prune-generated.py --apply --aggressive` from an up-to-date main checkout, leave the device idle (app stopped, screen asleep), and release any lease you recorded.
- Final reply: outcome (done / partial / blocked), commits + PR, applicable journal number and APK hash, what remains, and the single most valuable next step.
