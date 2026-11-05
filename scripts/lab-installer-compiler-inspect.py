#!/usr/bin/env python3
"""Host-only, fixed-vocabulary inspection of retained synthetic installer logs.

Historical captures contain a source commit, not a lab run ID. Require a unique
source-matching capture and corroborate the requested run's public command and
failure. Report that weaker binding explicitly; never select by newest/mtime.
No device commands, artifacts, raw excerpts or inferred class names are emitted.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import stat

LIMIT = 512 * 1024
PHASE = "baseline-N-install"
PREFIX = "ROR2_APK_LOG_BEGIN\n"


class Refused(Exception):
    pass


def read(path, limit=LIMIT):
    """Bounded regular-file read; refuse symlinks including immediate parent."""
    if path.parent.is_symlink():
        raise Refused("record-unavailable")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise Refused("record-unavailable")
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise Refused("record-unavailable")
            return data.decode("utf-8", errors="replace")
    except OSError:
        raise Refused("record-unavailable") from None


def metadata(path, category, phase=None):
    value = json.loads(read(path, 4096))
    if not isinstance(value, dict) or value.get("category") != category or (phase and value.get("phase") != phase):
        raise Refused("record-mismatch")
    if type(value.get("returncode")) is not int or value["returncode"] != 0 or value.get("outcome") != "returned":
        raise Refused("record-command-not-successful")
    return value


def classify(text):
    """Only literal labels leave this function, never regex capture groups."""
    markers = {
        "null-pointer": "java.lang.NullPointerException",
        "d8-compilation-failed": "CompilationFailedException",
        "null-string-length": 'Cannot invoke "String.length()"',
        "out-of-memory": "java.lang.OutOfMemoryError",
        "unsupported-class-version": "UnsupportedClassVersionError",
        "class-format-error": "ClassFormatError",
        "verify-error": "java.lang.VerifyError",
        "java-symbol-not-found": "cannot find symbol",
        "java-incompatible-types": "incompatible types",
        "java-duplicate-definition": "already defined",
        "java-override-error": "does not override",
        "java-package-missing": "package does not exist",
        "invalid-class-file": "Invalid class file",
        "duplicate-program-type": "defined multiple times",
        "missing-stack-map": "Expected stack map table",
        "storage-exhausted": "No space left on device",
        "permission-denied": "Permission denied",
        "file-missing": "No such file or directory",
    }
    categories = [label for label, marker in markers.items() if marker in text]
    known = (
        "PayloadBootstrapActivity",
        "PayloadBootstrapActivity$1",
        "PayloadBootstrapActivity$2",
        "PayloadBootstrapActivity$LocalAssetClient",
        "PayloadBootstrapActivity$AssetPayloadSource",
        "PayloadBootstrapActivity$Bridge",
        "PayloadBootstrapActivity$Backend",
        "PayloadStore",
        "PayloadStore$Source",
        "PayloadStore$Progress",
        "PayloadStore$Row",
        "PayloadStore$Paused",
        "PayloadStore$Drift",
        "ProfileStore",
        "ProfileStore$Environment",
        "ProfileStore$Snapshot",
        "ProfileStore$Row",
        "ProfileStore$Manifest",
        "ProfileStore$Status",
        "ProfileRetentionProvider",
        "ProfileRetentionProvider$1",
        "ProfileRetentionProvider$2",
    )
    classes = [name for name in known if re.search(r"(?:^|[/.:\s])" + re.escape(name) + r"\.class(?:$|[:\s])", text, re.MULTILINE)]
    return {"categories": categories or ["unclassified"], "authored_classes": classes, "empty": not text.strip()}


def corroborate(log, source, run_id):
    commands = []
    for line in log.splitlines():
        if line.startswith("$ "):
            commands.append(shlex.split(line[2:]))
    fetches = [cmd[-1] for cmd in commands if len(cmd) >= 6 and cmd[0] == "git" and cmd[-3:-1] == ["-q", "origin"] and "fetch" in cmd]
    accepts = [cmd for cmd in commands if "scripts/lab-installer-updates.py" in cmd]
    suffix = "/.local/worktrees/lab-run-" + run_id + "/.local/lab-venv/bin/python"
    if fetches != [source] or len(accepts) != 1 or not accepts[0][0].endswith(suffix):
        raise Refused("run-source-command-mismatch")
    if accepts[0][1:] != ["scripts/lab-installer-updates.py", "--allow-test-installs", "--allow-test-notifications"]:
        raise Refused("run-source-command-mismatch")
    if "FAIL check-for-updates phase=baseline-N-install reason=installer-build-error" not in log.splitlines():
        raise Refused("run-failure-mismatch")


def inspect(toolhost_root, source, run_id):
    if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise Refused("invalid-source-or-run")
    root = Path(toolhost_root).resolve(strict=True)
    if root.name != "toolhost" or root.parent.name != "lab-runner":
        raise Refused("unexpected-lab-root")
    log = read(root.parent / run_id / "output.log", 4 * 1024 * 1024)
    corroborate(log, source, run_id)
    parent = root.parent.parent / "installer-update-acceptance"
    if parent.is_symlink():
        raise Refused("record-unavailable")
    candidates = list(parent.iterdir())
    if len(candidates) > 2048:
        raise Refused("too-many-captures")
    matches = []
    for directory in candidates:
        if not re.fullmatch(r"run-[a-z0-9_]{8}", directory.name) or directory.is_symlink() or not directory.is_dir():
            continue
        records = list(directory.glob("[0-9][0-9][0-9][0-9][0-9]-resolve-source-commit.json"))
        if len(records) != 1:
            continue
        record = records[0]
        metadata(record, "resolve-source-commit")
        if read(record.with_suffix(".stdout.log"), 128).strip() == source:
            matches.append(directory)
    if len(matches) != 1:
        raise Refused("source-capture-missing-or-ambiguous")
    directory = matches[0]
    errors = []
    for record in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-state-read.json")):
        value = json.loads(read(record, 4096))
        if value.get("phase") != PHASE:
            continue
        metadata(record, "device-state-read", PHASE)
        state = json.loads(read(record.with_suffix(".stdout.log")))
        if isinstance(state, dict) and state.get("state") == "ERROR":
            errors.append(record)
    if len(errors) != 1:
        raise Refused("failure-record-missing-or-ambiguous")
    sequence = int(errors[0].name[:5])
    logs = []
    for tool in ("javac", "dex"):
        records = [p for p in directory.glob("[0-9][0-9][0-9][0-9][0-9]-device-apk-" + tool + "-log.json") if sequence < int(p.name[:5]) <= sequence + 4]
        if len(records) != 1:
            raise Refused("compiler-record-missing-or-ambiguous")
        record = records[0]
        metadata(record, "device-apk-" + tool + "-log", PHASE)
        output = read(record.with_suffix(".stdout.log"))
        if not output.startswith(PREFIX):
            raise Refused("compiler-capture-missing")
        logs.append({"tool": tool, **classify(output[len(PREFIX) :])})
    return {"status": "observed", "binding": "unique-source-plus-run-log", "direct_run_id_binding": False, "logs": logs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        configured = os.environ.get("LAB_TOOLHOST_ROOT")
        if not configured:
            raise Refused("lab-root-required")
        result = inspect(configured, args.source, args.run)
    except Refused as error:
        result = {"status": "refused", "reason": str(error)}
    except Exception:
        result = {"status": "refused", "reason": "malformed-or-unavailable-record"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
