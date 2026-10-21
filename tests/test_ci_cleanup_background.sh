#!/bin/bash
set -euo pipefail

script=${1:?pass the ci-local.sh source to inspect}
test_root=$(mktemp -d "${TMPDIR:-/tmp}/ci-cleanup-test.XXXXXX")
trap 'rm -rf "$test_root"' EXIT
awk '/^cleanup\(\) \{/ { copy=1 } copy { print } copy && /^\}$/ { exit }' "$script" > "$test_root/cleanup-function.sh"
grep -q '^cleanup() {' "$test_root/cleanup-function.sh"
mkdir -p "$test_root/bin" "$test_root/scratch/case-sensitive" "$test_root/.local/ci-cleanup"
printf 'keep\n' > "$test_root/scratch/case-sensitive/mounted-sentinel"
cat > "$test_root/bin/hdiutil" <<'FAKE'
#!/bin/bash
set -eu
: > "$FAKE_STARTED"
while [ ! -e "$FAKE_RELEASE" ]; do sleep 0.05; done
: > "$FAKE_FINISHED"
exit 23
FAKE
chmod +x "$test_root/bin/hdiutil"
cat > "$test_root/runner.sh" <<'RUNNER'
#!/bin/bash
set -euo pipefail
scratch=$FIXTURE_SCRATCH
volume=$FIXTURE_VOLUME
cleanup_log=$FIXTURE_LOG
source "$FIXTURE_FUNCTION"
trap cleanup EXIT
exit 37
RUNNER
chmod +x "$test_root/runner.sh"
export FIXTURE_SCRATCH="$test_root/scratch"
export FIXTURE_VOLUME="$test_root/scratch/case-sensitive"
export FIXTURE_LOG="$test_root/.local/ci-cleanup/scratch.log"
export FIXTURE_FUNCTION="$test_root/cleanup-function.sh"
export FAKE_STARTED="$test_root/hdiutil-started"
export FAKE_RELEASE="$test_root/hdiutil-release"
export FAKE_FINISHED="$test_root/hdiutil-finished"
export PATH="$test_root/bin:$PATH"
"$test_root/runner.sh" &
runner_pid=$!
(
  sleep 3
  : > "$test_root/watchdog-fired"
  : > "$FAKE_RELEASE"
) &
watchdog_pid=$!
set +e
wait "$runner_pid"
status=$?
set -e
kill "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true
if [ -e "$test_root/watchdog-fired" ]; then
  echo "cleanup waited for the blocked hdiutil child" >&2
  exit 1
fi
if [ "$status" -ne 37 ]; then
  echo "cleanup changed the original exit status: $status" >&2
  exit 1
fi
for attempt in $(seq 1 100); do
  [ -e "$FAKE_STARTED" ] && break
  sleep 0.02
done
[ -e "$FAKE_STARTED" ] || { echo "fake hdiutil was not started" >&2; exit 1; }
[ -f "$FIXTURE_VOLUME/mounted-sentinel" ] || { echo "mounted scratch was removed before detach" >&2; exit 1; }
: > "$FAKE_RELEASE"
for attempt in $(seq 1 100); do
  grep -q 'detach failed; preserving' "$FIXTURE_LOG" 2>/dev/null && break
  sleep 0.02
done
[ -e "$FAKE_FINISHED" ] || { echo "fake hdiutil did not finish" >&2; exit 1; }
[ -d "$FIXTURE_SCRATCH" ] || { echo "scratch was removed after detach failed" >&2; exit 1; }
[ -f "$FIXTURE_VOLUME/mounted-sentinel" ] || { echo "mounted scratch was not preserved" >&2; exit 1; }
grep -q 'cleanup: started' "$FIXTURE_LOG"
grep -q 'detach failed; preserving' "$FIXTURE_LOG"
echo "cleanup background handoff, exit status, phase log, and mounted scratch preservation passed"
