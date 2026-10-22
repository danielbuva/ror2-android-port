"""Current host tool: make a local, allowlisted baseline feedback preview.

Only a user-selected baseline result is read. No device, browser, network,
credential store or attachment collector is used. Review the output before sharing.
"""

import argparse
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlencode

ISSUES_URL = "https://github.com/danielbuva/ror2-android-port/issues/new"
MAX_INPUT_BYTES = 1024 * 1024


def boolean(value):
    if type(value) is not bool:
        raise ValueError("Expected a reported boolean")
    return value


def quantity(value, *, integer=False):
    if value is None:
        return None
    if type(value) not in ((int,) if integer else (int, float)):
        raise ValueError("Expected a reported quantity")
    if not 0 <= value <= 604800 or not math.isfinite(value):
        raise ValueError("Reported quantity is out of bounds")
    return value


def preview(result):
    """Project a runner summary into fixed keys; never stringify unselected data."""
    if type(result) is not dict:
        raise ValueError("Expected a baseline result object")
    apk = result.get("apk_sha256")
    if type(apk) is not str or re.fullmatch(r"[0-9a-f]{64}", apk) is None:
        raise ValueError("Expected an APK SHA-256")
    mode = result.get("mode", "baseline")
    if mode not in ("baseline", "stage-exit"):
        raise ValueError("Unknown baseline mode")
    success = boolean(result.get("success"))
    failures = result.get("failures")
    if type(failures) is not list or len(failures) > 10000 or any(type(x) is not str for x in failures):
        raise ValueError("Expected the runner's failed-criteria list")
    if success != (not failures):
        raise ValueError("Contradictory reported result")
    cleanup = result.get("cleanup")
    if type(cleanup) is not dict:
        raise ValueError("Missing verified teardown")
    selector = boolean(cleanup.get("selector_absent"))
    process = boolean(cleanup.get("process_absent"))
    sleeping = boolean(cleanup.get("sleep_requested"))
    asleep = cleanup.get("display_asleep")
    if asleep is not None:
        asleep = boolean(asleep)
    if not selector or not process or (sleeping and asleep is not True):
        raise ValueError("Unverified baseline teardown")
    value = {
        "schema": 1,
        "check": mode,
        "apk_sha256": apk,
        "reported_success": success,
        "matches_local_current_build": boolean(result.get("is_current_build")),
        "failed_criteria_count": len(failures),
        "assisted": True,
        "world_seconds": quantity(result.get("world_seconds")),
        "applied_profile_runs": quantity(result.get("applied_runs"), integer=True),
        "cleanup": {
            "selector_absent": selector,
            "process_absent": process,
            "sleep_requested": sleeping,
            "display_asleep": asleep,
        },
        "ordinary_controls_qualified": False,
        "full_run_qualified": False,
        "visual_audio_parity_qualified": False,
    }
    if mode == "stage-exit":
        value["transitions"] = quantity(result.get("transitions"), integer=True)
        value["stage_world_seconds"] = quantity(result.get("stage_world_seconds"))
    return value


def issue_url(result):
    """Return a draft URL only. Caller must preview it before any browser action."""
    value = preview(result)
    body = (
        "Assisted laboratory check; ordinary controls/full run/parity remain unqualified.\n\n"
        "Selected check facts (review before submitting):\n```json\n"
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n```\n\nReproduction steps:\n\nExpected behavior:\n\nActual behavior:\n\n"
        "No logs or attachments included. Review any attachment separately before uploading."
    )
    return ISSUES_URL + "?" + urlencode({"title": "Assisted playtest: APK " + value["apk_sha256"][:12], "body": body})


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def invalid_constant(_):
    raise ValueError("Non-finite JSON constant")


def read_result(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Baseline result exceeds the input bound")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def write_preview(source, destination, *, draft_url=False):
    result = read_result(source)
    value = preview(result)
    if draft_url:
        value["issue_draft_url"] = issue_url(result)
    output = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    # Exclusive creation preserves existing evidence and refuses symlinks.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(output)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Private result.json from an existing check-baseline run")
    parser.add_argument("--output", required=True, help="New local preview JSON; existing files are refused")
    parser.add_argument("--draft-url", action="store_true", help="Include a fixed tokenless GitHub issue-draft URL for manual review; never opens it")
    args = parser.parse_args(argv)
    try:
        write_preview(args.input, args.output, draft_url=args.draft_url)
    except (ValueError, RecursionError):
        parser.exit(2, "Feedback preview refused malformed or unsupported baseline data.\n")
    except OSError:
        parser.exit(2, "Feedback preview refused a local file operation; check paths, permissions and existing output.\n")
    print("Preview written locally. Review every field before sharing or opening its optional draft URL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
