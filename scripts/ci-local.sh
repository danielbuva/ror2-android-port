#!/bin/bash
# Run .github/workflows/host-tests.yml's steps on committed content, the way GitHub's Linux runner
# sees it: a fresh clone without work/ or local config, the Unity editor install hidden (macOS
# sandbox), and temporary files on a case-sensitive volume. Uncommitted work never affects it.
# Usage: scripts/ci-local.sh [TARGET [BASE]]   (defaults: HEAD, merge-base with origin/main)
# Used by the pre-push hook (scripts/git-hooks/pre-push); exits nonzero if CI would fail.
set -euo pipefail
# Hooks export repository-local variables. Clear them before addressing the fresh clone;
# otherwise `git -C` still operates on the pushing worktree instead of the clone.
for git_env in $(git rev-parse --local-env-vars); do unset "$git_env"; done
root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
target=$(git -C "$root" rev-parse "${1:-HEAD}")
base=${2:-$(git -C "$root" merge-base origin/main "$target" 2>/dev/null || git -C "$root" hash-object -t tree /dev/null)}
python="$root/.local/lab-venv/bin/python"
[ -x "$python" ] || python=python3
scratch=$(mktemp -d "${TMPDIR:-/tmp}/ci-local.XXXXXX")
volume="$scratch/case-sensitive"
cleanup() {
  if [ -d "$volume" ]; then hdiutil detach "$volume" -quiet 2>/dev/null || true; fi
  rm -rf "$scratch"
}
trap cleanup EXIT

git clone -q --no-hardlinks --no-checkout "$root" "$scratch/repo"
git -C "$scratch/repo" checkout -q "$target"
# The clone's origin/main is this checkout's main; keep the real upstream for the Ruff test.
git -C "$scratch/repo" update-ref refs/remotes/origin/main "$(git -C "$root" rev-parse origin/main)"

echo "ci-local: $target (Ruff base $base)"
"$python" "$root/scripts/ruff-committed.py" "$base" "$target"
cd "$scratch/repo"
"$python" scripts/audit-public.py
"$python" scripts/journal-index.py --check
"$python" scripts/readme-actions.py --check

tmp="$scratch/tmp"
if hdiutil create -size 2g -fs "Case-sensitive APFS" -volname ci-local -type SPARSE "$scratch/volume.sparseimage" -quiet \
  && hdiutil attach "$scratch/volume.sparseimage" -mountpoint "$volume" -nobrowse -quiet; then
  tmp="$volume/tmp"
else
  echo "ci-local: no case-sensitive volume; temporary files stay case-insensitive" >&2
fi
mkdir -p "$tmp"
TMPDIR="$tmp" sandbox-exec -p '(version 1)(allow default)(deny file-read* (subpath "/Applications/Unity"))' \
  "$python" -m unittest discover -s tests
echo "ci-local: all CI steps pass for $target"
