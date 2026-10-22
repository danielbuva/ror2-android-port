# Local baseline feedback preview

Current host tool: `scripts/lab/baseline_feedback.py` projects an existing
`check-baseline` summary into a small local JSON preview. It reads one selected
file and creates one new file. It performs no device action, browser launch,
network request or issue submission. Settings integration and attachment export
remain open in the [alpha checklist](public-alpha.md).

## Create and review

Choose the `result.json` from your owned run described in [BASELINE.md](BASELINE.md).
Set `BASELINE_RESULT` to that private file and `FEEDBACK_PREVIEW` to a new path
beneath your ignored `work/`. Run from the repository root:

```sh
: "${BASELINE_RESULT:?Set your private baseline result path}"
: "${FEEDBACK_PREVIEW:?Set a new local preview path}"
python3 scripts/lab/baseline_feedback.py \
  --input "$BASELINE_RESULT" --output "$FEEDBACK_PREVIEW"
```

Add `--draft-url` to include a tokenless draft URL for this repository's existing
GitHub Issues page inside the preview. Review the full preview before opening
that URL. Opening it sends the selected facts to GitHub; submitting the issue
is a separate manual action. Enter reproduction steps and expected/actual
behavior deliberately. Preview and consent to each attachment separately;
the tool collects and attaches none.

## Exported facts and limits

The fixed fields contain the APK SHA-256, check mode, reported result, failed
criteria count, current-build comparison, optional timing/profile counters and
reported teardown states. Missing counters stay `null`. Assistance and ordinary
control/full-run/visual-audio limitations are explicit. These are selected runner
claims; the tool does not authenticate evidence, query the installed APK or
reassess gameplay acceptance.

Failure messages, process IDs, evidence paths, scene names and unknown fields
are omitted, including nested data. No arbitrary log text or user-written report
text enters the output. Keep the original reports, captures and game-derived
outputs private. The preview still requires human review before sharing.

Malformed identity/types, contradictory result/failure counts, incomplete
teardown, non-finite or out-of-bound counters, duplicate JSON keys and inputs
over 1 MiB refuse. The current counter bound is 604,800 (seven days for timing).
Outputs use exclusive creation with owner-only permissions on POSIX; an existing
file or symlink refuses. A failed write may leave a partial new file: preserve
it and choose a different output path after inspection. No state persists after
the process exits.

Run `python3 -m unittest discover -s tests -p test_baseline_feedback.py` for
authored projection, privacy, refusal, draft URL and file/CLI contracts.
