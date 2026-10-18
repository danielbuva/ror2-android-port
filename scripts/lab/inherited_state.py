"""Capture and verify the explicitly retained inherited asset/importer pairs."""

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile

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


def store_root(work, ledger):
    work = Path(work).resolve()
    if not HASH.fullmatch(ledger["input_id"]):
        raise RuntimeError("Invalid inherited store input identity")
    store = work / "inherited-store" / ledger["input_id"]
    if store.resolve() != store or work not in store.parents:
        raise RuntimeError("Inherited store escapes work or uses a symlink")
    return store


def validate_input(work, ledger):
    if read(work / "config/accepted-input.json")["input_id"] != ledger["input_id"]:
        raise RuntimeError("Inherited state belongs to a different accepted input")


def pair_path(base, relative):
    relative_path(relative, "Assets/LabLoadingScene/")
    path = base / relative
    if base.resolve() not in path.resolve().parents:
        raise RuntimeError("Inherited file escapes its store/source")
    return path


def read_pair(base, asset):
    pair = []
    for suffix, key in (("", "sha256"), (".meta", "meta_sha256")):
        data = pair_path(base, asset["path"] + suffix).read_bytes()
        if hashlib.sha256(data).hexdigest() != asset[key]:
            raise RuntimeError("Inherited pair hash mismatch: " + asset["path"] + suffix)
        if suffix and re.findall(rb"^guid:\s*([a-f0-9]{32})\s*$", data, re.M) != [asset["guid"].encode()]:
            raise RuntimeError("Inherited pair GUID mismatch: " + asset["path"])
        pair.append(data)
    return tuple(pair)


def capture(work=None, ledger=None):
    """Copy only inherited pairs from the selected rollback; publish only after verification."""
    work = Path(work or WORK).resolve()
    ledger = load_ledger() if ledger is None else ledger
    validate_input(work, ledger)
    selection = read(work / "config/composition-migration.json")
    if selection["input_id"] != ledger["input_id"]:
        raise RuntimeError("Inherited capture selection belongs to another input")
    relative = relative_path(selection["previous_project"], "work/")
    previous = (work / PurePosixPath(relative).relative_to("work")).resolve()
    if work not in previous.parents or previous == (work / "lab-project").resolve():
        raise RuntimeError("Inherited source must be a separate previous project under work")
    store = store_root(work, ledger)
    assets = [a for a in ledger["assets"] if a["status"] == "inherited"]
    pairs = {a["path"]: read_pair(previous, a) for a in assets}
    expected = {a["path"] + suffix for a in assets for suffix in ("", ".meta")}
    if store.exists():
        actual = {p.relative_to(store).as_posix() for p in store.rglob("*") if not p.is_dir()}
        if actual != expected:
            raise RuntimeError("Existing inherited store membership differs from ledger")
        for asset in assets:
            read_pair(store, asset)
    else:
        store.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".capture-", dir=store.parent) as temporary:
            scratch = Path(temporary) / "store"
            scratch.mkdir()
            for asset in assets:
                for suffix, data in zip(("", ".meta"), pairs[asset["path"]]):
                    target = pair_path(scratch, asset["path"] + suffix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                read_pair(scratch, asset)
            scratch.rename(store)
    return {"input_id": ledger["input_id"], "captured_pairs": len(assets), "store": "work/inherited-store/" + ledger["input_id"]}


def capture_action():
    print(json.dumps(capture(), indent=2))


def prepare(rows, work=None, ledger=None):
    """Validate the complete inherited selection and store before staging any project bytes."""
    work = Path(work or WORK).resolve()
    ledger = load_ledger() if ledger is None else ledger
    validate_input(work, ledger)
    assets = {a["path"]: a for a in ledger["assets"] if a["status"] == "inherited"}
    pairs = {}
    store = store_root(work, ledger)
    for row in rows:
        asset = assets.get(row["old"])
        if asset is None:
            continue
        if row["old"] in pairs or row["guid"] != asset["guid"] or row["target"] != asset["project_path"]:
            raise RuntimeError("Inherited addition disagrees with ledger identity")
        pairs[row["old"]] = read_pair(store, asset)
    if pairs.keys() != assets.keys():
        raise RuntimeError("Composition omits inherited additions")
    return pairs


def check(work=None, ledger=None):
    """Check the named store and regenerated pairs; never read the previous project."""
    work = Path(work or WORK).resolve()
    ledger = load_ledger() if ledger is None else ledger
    validate_input(work, ledger)
    store = store_root(work, ledger)
    differences = []
    checked = 0
    for asset in ledger["assets"]:
        if asset["status"] != "inherited":
            continue
        checked += 1
        for suffix, key in (("", "sha256"), (".meta", "meta_sha256")):
            path = pair_path(store, asset["path"] + suffix)
            if not path.is_file():
                differences.append({"path": asset["path"] + suffix, "reason": "missing"})
            elif sha(path) != asset[key]:
                differences.append({"path": asset["path"] + suffix, "reason": "sha256"})
            elif suffix and re.findall(r"^guid:\s*([a-f0-9]{32})\s*$", path.read_text(), re.M) != [asset["guid"]]:
                differences.append({"path": asset["path"] + suffix, "reason": "guid"})
    from shader_additions import cohort, generate_pairs

    reproducible = cohort(ledger)
    pairs = generate_pairs(reproducible, work, verify=False) if reproducible else {}
    from export_additions import cohort as export_cohort, generate_pairs as export_pairs

    exports = export_cohort(ledger)
    if exports:
        pairs.update(export_pairs(exports, work, verify=False))
        reproducible += exports
    from unity_package_additions import cohort as package_cohort, generate_pairs as package_pairs

    packages = package_cohort(ledger)
    if packages:
        pairs.update(package_pairs(packages, verify=False))
        reproducible += packages
    for asset in reproducible:
        for (suffix, key), data in zip((("", "sha256"), (".meta", "meta_sha256")), pairs[asset["path"]]):
            if hashlib.sha256(data).hexdigest() != asset[key]:
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
