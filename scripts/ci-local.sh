#!/bin/bash
# Run .github/workflows/host-tests.yml's steps on committed content, the way GitHub's Linux runner
# sees it: a fresh checkout without work/ or local config, the Unity editor install hidden (macOS
# sandbox), and temporary files on a case-sensitive volume. Uncommitted work never affects it.
# Usage: scripts/ci-local.sh [TARGET [BASE]]   (defaults: HEAD, merge-base with origin/main)
# Reuses only locked source objects and pinned dependencies under the Git common directory.
# Used by the pre-push hook (scripts/git-hooks/pre-push); exits nonzero if CI would fail.
set -euo pipefail
# Hooks export repository-local variables. Clear them before addressing the fresh clone;
# otherwise `git -C` still operates on the pushing worktree instead of the clone.
for git_env in $(git rev-parse --local-env-vars); do unset "$git_env"; done
root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
target=$(git -C "$root" rev-parse --verify "${1:-HEAD}^{commit}")
base=${2:-$(git -C "$root" merge-base origin/main "$target" 2>/dev/null || git -C "$root" hash-object -t tree /dev/null)}
base=$(git -C "$root" rev-parse "$base")
# Do not import caller-local modules or write into the shared dependency environment.
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE VIRTUAL_ENV
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
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
  if [ "$(uname -s)" = Linux ]; then
    # There is no mounted image to detach on Linux. Finish removal before exiting:
    # VM/job supervisors can terminate background children as soon as the hook ends.
    {
      echo "cleanup: started"
      if rm -rf "$scratch"; then
        echo "cleanup: scratch removed"
      else
        echo "cleanup: scratch removal failed"
      fi
    } </dev/null >>"$cleanup_log" 2>&1
    exit "$status"
  fi
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

"$python" "$root/scripts/ci-local-cache.py" checkout "$root" "$scratch/repo" "$target" "$base"
python=$("$python" "$root/scripts/ci-local-cache.py" environment "$root" "$scratch/repo")
export PATH="$(dirname "$python"):$PATH"

echo "ci-local: $target (Ruff base $base)"
cd "$scratch/repo"
"$python" scripts/ruff-committed.py "$base" "$target"
"$python" scripts/audit-public.py
"$python" scripts/journal-index.py --check
"$python" scripts/readme-actions.py --check

tmp="$scratch/tmp"
setup_status=0
if [ "$(uname -s)" = Darwin ]; then
  "$python" scripts/ci-hdiutil-volume.py 30 "$scratch/volume.sparseimage" "$volume" || setup_status=$?
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
# Historical commits without the parallel runner still execute full unittest discovery.
# A runner failure is fatal, never hidden by a fallback or a saved test result.
if [ -f scripts/host-tests.py ]; then
  tests=(scripts/host-tests.py --workers "${HOST_TEST_WORKERS:-2}" --report "$scratch/host-tests.json")
else
  tests=(-m unittest discover -s tests)
fi
if [ "$(uname -s)" = Darwin ]; then
  TMPDIR="$tmp" sandbox-exec -p '(version 1)(allow default)(deny file-read* (subpath "/Applications/Unity"))' \
    "$python" "${tests[@]}"
else
  TMPDIR="$tmp" "$python" "${tests[@]}"
fi
echo "ci-local: all CI steps pass for $target"
