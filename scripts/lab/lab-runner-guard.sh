#!/bin/bash
# Job-started hook for the owner's self-hosted lab runner (docs/LAB_RUNNER.md).
# Install a COPY outside the repository and point ACTIONS_RUNNER_HOOK_JOB_STARTED at it, so no branch can
# change it. It refuses every job except main's lab-runner workflow triggered by an owner issue comment:
# a branch that adds its own self-hosted workflow (push, pull_request, ...) never runs here.
set -u
expected_repo="danielbuva/ror2-android-port"
fail() { echo "lab-runner guard: refused ($1)" >&2; exit 1; }
[ "${GITHUB_REPOSITORY:-}" = "$expected_repo" ] || fail "repository ${GITHUB_REPOSITORY:-unset}"
[ "${GITHUB_EVENT_NAME:-}" = "issue_comment" ] || fail "event ${GITHUB_EVENT_NAME:-unset}"
[ "${GITHUB_WORKFLOW_REF:-}" = "$expected_repo/.github/workflows/lab-runner.yml@refs/heads/main" ] ||
  fail "workflow ${GITHUB_WORKFLOW_REF:-unset}"
[ "${GITHUB_ACTOR:-}" = "${expected_repo%%/*}" ] || fail "actor ${GITHUB_ACTOR:-unset}"
echo "lab-runner guard: admitted main lab-runner workflow for ${GITHUB_ACTOR}"
