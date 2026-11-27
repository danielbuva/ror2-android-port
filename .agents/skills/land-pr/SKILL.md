---
name: land-pr
description: Use when updating, verifying and merging a branch or draft PR of the RoR2 Android lab into main, or when deciding whether an existing PR/branch's work can be reused. Covers branch update (merge, not rebase), CI-local, privacy audit, journal-number collisions and merge.
---

# Land a branch

1. `git fetch origin && git merge origin/main` in the branch's own worktree. Never rebase or force-push
   a pushed branch. For journal conflicts, preserve main's
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
4. Push. The pre-push hook runs `scripts/ci-local.sh` with affected test selection in a fresh clone. GitHub runs the full suite.
5. Journal shipped device-verified behaviour and closed readiness or alpha gates. Cite the device run for device claims. Record routine host-only fixes in their PR.
6. After opening the PR, append `AUTOMERGE <n>` to the workstream status file. The orchestrator's
   merge bot waits for the required `host-tests` check and squash-merges with the GitHub noreply
   author address. GitHub deletes the remote head branch. Start the next item from `origin/main`
   while CI runs. Use `WAITING ci-pr <n>` only when the next step requires the merge.
7. After the merge, fetch updates and switch off the topic branch before deleting it locally with
   `git branch -D <branch>` (squash merges create a new commit). Keep the assigned worktree and its
   symlinks. Remove any extra worktree you created and run `python3 scripts/prune-generated.py --apply --aggressive`
   from an up-to-date main checkout. Never force-push or rewrite `main`, including to fix commit metadata.

Prefer landing finished draft PRs over starting parallel re-implementations; stale PRs that no longer apply are closed with a one-line reason.
