"""Read-only integrity check for the J558 inherited local-state ledger."""

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from common import RECIPE, WORK, read, sha


HASH = re.compile(r"[a-f0-9]{64}\Z")
GUID = re.compile(r"[a-f0-9]{32}\Z")


def relative_path(value, prefix):
    if not isinstance(value, str) or not value.startswith(prefix) or ".." in PurePosixPath(value).parts or PurePosixPath(value).as_posix() != value:
        raise RuntimeError("Invalid inherited-state path")
    return value


def load_ledger(path=None):
    ledger = read(path or RECIPE / "inherited-state.json")
    if (
        set(ledger) != {"schema_version", "input_id", "source", "assets"}
        or ledger["schema_version"] != 1
        or not isinstance(ledger["input_id"], str)
        or not HASH.fullmatch(ledger["input_id"])
        or ledger["source"] != {"selection": "work/config/composition-migration.json", "field": "previous_project"}
        or not isinstance(ledger["assets"], list)
        or not ledger["assets"]
    ):
        raise RuntimeError("Invalid inherited-state ledger")
    paths, guids = set(), set()
    for asset in ledger["assets"]:
        relative_path(asset["path"], "Assets/LabLoadingScene/")
        relative_path(asset["project_path"], "Assets/")
        if (
            asset["status"] not in ("inherited", "reproducible", "retired")
            or asset["usage"] not in ("used", "unused", "unclear")
            or not GUID.fullmatch(asset["guid"])
            or any(not HASH.fullmatch(asset[key]) for key in ("sha256", "meta_sha256"))
            or any(asset[key] is not None and not HASH.fullmatch(asset[key]) for key in ("current_sha256", "current_meta_sha256"))
            or not isinstance(asset["usage_evidence"], list)
            or not asset["usage_evidence"]
            or asset["path"] in paths
            or asset["guid"] in guids
        ):
            raise RuntimeError("Invalid or duplicate inherited-state identity/status/evidence")
        paths.add(asset["path"])
        guids.add(asset["guid"])
    return ledger


def check(work=None, ledger=None):
    """Check inherited hashes and regenerate byte-proven pairs in scratch; never write to work."""
    work = Path(work or WORK).resolve()
    ledger = load_ledger() if ledger is None else ledger
    selection = read(work / "config/composition-migration.json")
    accepted = read(work / "config/accepted-input.json")
    if selection["input_id"] != ledger["input_id"] or accepted["input_id"] != ledger["input_id"]:
        raise RuntimeError("Inherited state belongs to a different accepted input")
    relative = relative_path(selection["previous_project"], "work/")
    previous = (work / PurePosixPath(relative).relative_to("work")).resolve()
    if work not in previous.parents or previous == (work / "lab-project").resolve():
        raise RuntimeError("Inherited source must be a separate previous project under work")
    differences = []
    checked = 0
    for asset in ledger["assets"]:
        if asset["status"] != "inherited":
            continue
        checked += 1
        for suffix, key in (("", "sha256"), (".meta", "meta_sha256")):
            path = previous / (asset["path"] + suffix)
            if previous not in path.resolve().parents:
                raise RuntimeError("Inherited file escapes previous project")
            if not path.is_file():
                differences.append({"path": asset["path"] + suffix, "reason": "missing"})
            elif sha(path) != asset[key]:
                differences.append({"path": asset["path"] + suffix, "reason": "sha256"})
            elif suffix and re.findall(r"^guid:\s*([a-f0-9]{32})\s*$", path.read_text(), re.M) != [asset["guid"]]:
                differences.append({"path": asset["path"] + suffix, "reason": "guid"})
    from shader_additions import cohort, generate_pairs

    reproducible = cohort(ledger)
    pairs = generate_pairs(reproducible, work, verify=False) if reproducible else {}
    for asset in reproducible:
        for (suffix, key), data in zip((("", "sha256"), (".meta", "meta_sha256")), pairs[asset["path"]]):
            path = previous / (asset["path"] + suffix)
            if previous not in path.resolve().parents:
                raise RuntimeError("Inherited file escapes previous project")
            if not path.is_file():
                differences.append({"path": asset["path"] + suffix, "reason": "missing"})
            elif data != path.read_bytes() or hashlib.sha256(data).hexdigest() != asset[key]:
                differences.append({"path": asset["path"] + suffix, "reason": "generated_pair"})
    return {
        "checked_generated_pairs": len(reproducible),
        "total": len(ledger["assets"]),
        "by_status": {key: sum(a["status"] == key for a in ledger["assets"]) for key in ("inherited", "reproducible", "retired")},
        "by_usage": {key: sum(a["usage"] == key for a in ledger["assets"]) for key in ("used", "unused", "unclear")},
        "by_status_and_usage": {
            status: dict(Counter(a["usage"] for a in ledger["assets"] if a["status"] == status)) for status in ("inherited", "reproducible", "retired")
        },
        "checked_inherited_pairs": checked,
        "differences": differences,
    }


def check_action(work=None):
    result = check(work)
    print(json.dumps(result, indent=2))
    if result["differences"]:
        raise SystemExit(1)
