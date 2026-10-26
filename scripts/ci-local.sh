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
preserve_scratch=0
cleanup_dir=$(git -C "$root" rev-parse --path-format=absolute --git-path ci-cleanup)
cleanup_log="$cleanup_dir/$(basename "$scratch").log"
mkdir -p "$cleanup_dir"
cleanup() {
  local status=$?
  trap - EXIT
  (
    echo "cleanup: started"
    if [ "${preserve_scratch:-0}" -eq 1 ]; then
      echo "cleanup: attach timed out with uncertain mount state; preserving $scratch"
      exit 0
    fi
    if [ -d "$volume" ] && ! hdiutil detach "$volume" -quiet; then
      echo "cleanup: detach failed; preserving $scratch"
      exit 0
    fi
    if rm -rf "$scratch"; then
      echo "cleanup: scratch removed"
    else
      echo "cleanup: scratch removal failed"
    fi
  ) </dev/null >>"$cleanup_log" 2>&1 &
  exit "$status"
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
setup_status=0
if [ "$(uname -s)" = Darwin ]; then
  "$python" "$root/scripts/ci-hdiutil-volume.py" 30 "$scratch/volume.sparseimage" "$volume" || setup_status=$?
else
  # Linux CI/VMs already use case-sensitive storage and have no Unity installation.
  setup_status=1
fi
if [ "$setup_status" -eq 0 ]; then
  tmp="$volume/tmp"
elif [ "$setup_status" -eq 2 ]; then
  # hdiutil may have mounted before its CLI timed out. Do not detach or remove the
  # image/volume on this ambiguous outcome; the cleanup trap preserves the scratch.
  preserve_scratch=1
else
  echo "ci-local: using the host temporary filesystem" >&2
fi
mkdir -p "$tmp"
if [ "$(uname -s)" = Darwin ]; then
  TMPDIR="$tmp" sandbox-exec -p '(version 1)(allow default)(deny file-read* (subpath "/Applications/Unity"))' \
    "$python" -m unittest discover -s tests
else
  TMPDIR="$tmp" "$python" -m unittest discover -s tests
fi
echo "ci-local: all CI steps pass for $target"
