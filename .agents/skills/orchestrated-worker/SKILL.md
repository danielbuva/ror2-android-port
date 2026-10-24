---
name: orchestrated-worker
description: Use when running as a Codex/Claude worker launched by the orchestrator for this repo (a brief naming a workstream, worktree and device). Defines autonomy, scope, coordination files and the final report format.
---

# Working under the orchestrator

- You own exactly the workstream, worktree and device serial in your brief. Shared resources: the Unity editor (`work/coordination/unity-build.lock`, acquired only through `./dev`), journal numbers, `main`.
- Work autonomously toward a **complete implementation** of the workstream goal. Prefer finishing a whole vertical slice (code + host tests + build + device check + docs) over a chain of tiny probes. Do not stop to ask; record blockers and continue with the next highest-value piece.
- Reuse existing branches/PRs listed in your brief before writing new machinery (`gh pr list`, `git worktree list`).
- Commit logical checkpoints with Conventional Commits; push your branch; open/update a PR. Merge to main only when the brief allows it and `land-pr` passes.
- Append a status line to `.local/orchestrator/status/<workstream>.md` (timestamp, what changed, next step, blockers) after each milestone so the orchestrator can track you without reading your transcript.
- Before finishing: `python3 scripts/prune-generated.py --apply`, leave the device idle (app stopped, screen asleep), and release any lease you recorded.
- Final reply: outcome (done / partial / blocked), commits + PR, device evidence (journal number, APK hash), what remains, and the single most valuable next step.
