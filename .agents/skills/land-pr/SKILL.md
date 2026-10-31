---
name: land-pr
description: Use when updating, verifying and merging a branch or draft PR of the RoR2 Android lab into main, or when deciding whether an existing PR/branch's work can be reused. Covers branch update (merge, not rebase), CI-local, privacy audit, journal-number collisions and merge.
---

# Land a branch

1. `git fetch origin && git merge origin/main` in the branch's own worktree (a not-yet-pushed branch may
   rebase instead; never rebase or force-push a pushed branch). For journal conflicts, preserve main's
   entries unchanged and keep each branch addition as a separate `## J<n>` heading (temporary duplicate
   numbers are fine); remove conflict markers, never discard another branch's entry. Then run `python3
   scripts/journal-renumber.py --dry-run` and `python3 scripts/journal-renumber.py`. This host-only tool
   compares complete entries against the fetched `origin/main`, renumbers only branch additions above
   main's highest ID in source order, and regenerates the index. It works during conflict resolution or
   after the merge completes; it never fetches, stages or commits. Stage the resolved journal/index
   before completing an in-progress merge. If it refuses missing, edited or duplicate entries, reconcile
   those explicitly rather than guessing ownership from J numbers. Review branch-owned references/links
   manually: collided numbers are ambiguous, so only headings and generated index links are rewritten.
   Never renumber someone else's entry.
2. `.local/lab-venv/bin/ruff format` + `ruff check` on changed Python; `python3 -m unittest discover -s tests` for affected tests.
3. `python3 scripts/audit-public.py` on staged content; manually confirm no game-derived bytes, device serials, private paths or credentials.
4. Push; the pre-push hook runs `scripts/ci-local.sh` in a fresh clone (rerun once if a capture-transfer step flakes).
5. If the PR claims device behaviour, its journal entry must cite the device run. Host-only PRs may merge with the device gate stated as open.
6. Merge with `gh pr merge <n> --squash --delete-branch --author-email "$(git config user.email)"` (the repo's configured GitHub noreply address) once CI is green (without `--author-email` GitHub uses the account's private address). Never force-push or rewrite `main`, including to fix commit metadata; report such issues instead. then remove the local worktree (`git worktree remove`) and prune its `work/` outputs.

Prefer landing finished draft PRs over starting parallel re-implementations; stale PRs that no longer apply are closed with a one-line reason.
