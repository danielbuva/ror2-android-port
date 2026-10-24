---
name: land-pr
description: Use when rebasing, verifying and merging a branch or draft PR of the RoR2 Android lab into main, or when deciding whether an existing PR/branch's work can be reused. Covers rebase, CI-local, privacy audit, journal-number collisions and merge.
---

# Land a branch

1. `git fetch origin && git rebase origin/main` in the branch's own worktree. Resolve journal conflicts by renumbering your entry to the next free `J<n>` and rerunning `python3 scripts/journal-index.py`; never renumber someone else's entry.
2. `.local/lab-venv/bin/ruff format` + `ruff check` on changed Python; `python3 -m unittest discover -s tests` for affected tests.
3. `python3 scripts/audit-public.py` on staged content; manually confirm no game-derived bytes, device serials, private paths or credentials.
4. Push; the pre-push hook runs `scripts/ci-local.sh` in a fresh clone (rerun once if a capture-transfer step flakes).
5. If the PR claims device behaviour, its journal entry must cite the device run. Host-only PRs may merge with the device gate stated as open.
6. Merge with `gh pr merge <n> --squash --delete-branch` once CI is green, then remove the local worktree (`git worktree remove`) and prune its `work/` outputs.

Prefer landing finished draft PRs over starting parallel re-implementations; stale PRs that no longer apply are closed with a one-line reason.
