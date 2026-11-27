"""Census a built game's Unity objects and compare a pinned reference payload."""

from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager, nullcontext
from hashlib import file_digest
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import unity_write as W


PLAYER = "assets/bin/Data/"
EMBEDDED = "assets/owner-bootstrap/data/"
INDEX = "assets/owner-bootstrap/payload-index.json"
STATUSES = ("exact", "approximate", "missing", "unverified")
CLASS_OWNERS = {
    "p1-scenes-w": {43, 74, 90, 91},
    "p1-textures": {28, 89},
    "p1-shaderx": {48, 72},
    "p1-selectors": {21, 29, 41, 104, 108, 157, 192, 197, 215, 216, 220, 258, 259, 363, 1120, 850595691},
}


def owner(class_id):
    return next((name for name, classes in CLASS_OWNERS.items() if class_id in classes), "p1-payload")


def pinned(pin):
    path = Path(pin["path"])
    if W.B.sha(path) != pin["sha256"]:
        raise ValueError(f"Scoreboard input hash differs: {path}")
    return path


class ArchiveFile:
    """Expose a seekable APK entry to the existing Unity readers without staging it."""

    def __init__(self, archive, entry):
        self.archive = archive
        self.entry = entry

    def stat(self):
        return SimpleNamespace(st_size=self.archive.getinfo(self.entry).file_size)

    @contextmanager
    def open(self, mode):
        with self.archive.open(self.entry) as stream:
            yield stream


@contextmanager
def inventory(spec):
    apk = pinned(spec["apk"])
    with ZipFile(apk) as archive:
        names = [row.filename for row in archive.infolist() if not row.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate entries in scoreboard APK")
        artifacts = {name: (ArchiveFile(archive, name), None) for name in names if name.startswith(PLAYER)}
        payload = spec.get("external_payload")
        if payload:
            receipt = json.loads(pinned(payload["receipt"]).read_bytes())
            if receipt["apk_sha256"] != spec["apk"]["sha256"] or INDEX in names:
                raise ValueError("External payload receipt belongs to a different build")
            root = Path(payload["directory"]).resolve()
            for name, digest in receipt["payload"].items():
                path = root / name
                if not path.resolve().is_relative_to(root):
                    raise ValueError("External payload path escapes its directory")
                artifacts[EMBEDDED + name] = (path, digest)
        elif INDEX in names:
            index = json.loads(archive.read(INDEX))
            rows = {EMBEDDED + row["name"]: row for row in index["files"]}
            if len(rows) != len(index["files"]) or set(rows) != {name for name in names if name.startswith(EMBEDDED)}:
                raise ValueError("Embedded payload index differs from APK membership")
            for name, row in rows.items():
                path = ArchiveFile(archive, name)
                if path.stat().st_size != row["bytes"]:
                    raise ValueError("Embedded payload entry size differs")
                artifacts[name] = (path, row["sha256"])
        yield artifacts


@contextmanager
def serialized_members(artifact):
    if artifact is None:
        yield None, {}, None
        return
    path, expected = artifact
    with path.open("rb") as stream:
        if expected is not None:
            digest = file_digest(stream, "sha256").hexdigest()
            if digest != expected:
                raise ValueError("Payload object census encountered a hash mismatch")
            stream.seek(0)
        else:
            digest = None
        signature = stream.read(20)
        stream.size = path.stat().st_size
        if signature.startswith(b"UnityFS\0"):
            # Reuse one ZIP reader for forward seeks across serialized members.
            reader = SimpleNamespace(open=lambda mode: nullcontext(stream), stat=path.stat)
            stream.seek(0)
            bundle = W.B.Bundle(reader)
            members = {name: bundle.member(name) for name, (_, _, flags) in bundle.members.items() if flags & 4}
            yield "bundle", members, digest
        elif len(signature) == 20 and signature[8:12] == b"\0\0\0\x16":
            yield "player", {"": stream}, digest
        else:
            yield None, {}, digest


def count_file(candidate, reference, counts):
    with serialized_members(candidate) as (kind, current, current_hash), serialized_members(reference) as (prior_kind, prior, prior_hash):
        if kind is None and prior_kind is None:
            return None, 0, 0
        whole_equal = current_hash is not None and current_hash == prior_hash
        if kind is not None and prior_kind is not None and kind != prior_kind:
            raise ValueError("Candidate and reference content kinds differ")
        for member in sorted(current.keys() | prior.keys()):
            current_stream, prior_stream = current.get(member), prior.get(member)
            after = W.read_serialized(current_stream) if current_stream is not None else None
            before = (after if whole_equal else W.read_serialized(prior_stream)) if prior_stream is not None else None
            compare_member(current_stream, after, prior_stream, before, counts, whole_equal)
        return kind or prior_kind, len(current), len(prior)


def same_body(left, left_offset, right, right_offset, size):
    left.seek(left_offset)
    right.seek(right_offset)
    while size:
        length = min(size, 1024 * 1024)
        if W.B.exact(left, length) != W.B.exact(right, length):
            return False
        size -= length
    return True


def compare_member(current, after, prior, before, counts, whole_equal):
    if whole_equal:
        for row in after["objects"]:
            counts[after["types"][row["type_id"]]["class_id"]]["exact"] += 1
        return
    expected = {row["path_id"]: row for row in before["objects"]} if before else {}
    shared_tables = (
        after is not None and before is not None and all(after[key] == before[key] for key in ("engine", "platform", "externals", "scripts", "ref_types"))
    )
    rows = after["objects"] if after else ()
    if expected:
        rows = sorted(rows, key=lambda row: row["offset"])
    for row in rows:
        typ = after["types"][row["type_id"]]
        class_id = typ["class_id"]
        old = expected.get(row["path_id"])
        old_type = before["types"][old["type_id"]] if old is not None else None
        if old_type is None or class_id != old_type["class_id"]:
            counts[class_id]["unverified"] += 1
            continue
        del expected[row["path_id"]]
        exact = (
            shared_tables
            and typ == old_type
            and row["bytes"] == old["bytes"]
            and same_body(current, after["data_offset"] + row["offset"], prior, before["data_offset"] + old["offset"], row["bytes"])
        )
        counts[class_id]["exact" if exact else "approximate"] += 1
    for old in expected.values():
        counts[before["types"][old["type_id"]]["class_id"]]["missing"] += 1


def original_audit(pin):
    data = json.loads(pinned(pin).read_bytes())
    if data["schema"] != "read-only-passthrough-audit-v1":
        raise ValueError("Unknown original-source audit schema")
    classes = []
    for name, row in sorted(data["classes"].items(), key=lambda pair: pair[1]["class_id"]):
        classes.append(dict(class_id=row["class_id"], name=name, owner=owner(row["class_id"]), **{key: row["categories"].get(key, 0) for key in "CRDU"}))
    totals = {key: sum(row[key] for row in classes) for key in "CRDU"}
    if totals != data["categories"] or sum(totals.values()) != data["objects"]:
        raise ValueError("Original-source audit totals differ")
    unknown_by_owner = Counter()
    for row in classes:
        unknown_by_owner[row["owner"]] += row["U"]
    return dict(sha256=pin["sha256"], scope=data["scope"], objects=data["objects"], totals=totals, classes=classes, unknown_by_owner=dict(unknown_by_owner))


def device_observations(receipts, apk_sha256):
    results = {name: "unobserved" for name in ("launch", "menu", "first_stage", "stage_transition")}
    stages = set()
    for pin in receipts:
        path = pinned(pin)
        row = json.loads(path.read_bytes())
        if path.name != "terminal.done.json" or row.get("apk_sha256") != apk_sha256:
            raise ValueError("Device observation belongs to a different build")
        checks = row.get("process_checkpoints", [])
        pids = {str(check["verified_launch_pid"]) for check in checks if check.get("phase") == "launch" and "verified_launch_pid" in check}
        if pids:
            results["launch"] = "passed"
        for key, name, phase in (
            ("menu", "start-menu.json", "offline-start-menu"),
            ("first_stage", "world-start.json", "integrated-world-playing"),
        ):
            marker = path.with_name(name)
            if pids and marker.is_file():
                value = json.loads(marker.read_bytes())
                if str(value.get("pid")) in pids and value.get("phase") == phase and (key == "menu" or value.get("world", {}).get("ready") is True):
                    results[key] = "passed"
                    if key == "first_stage" and value.get("stage", {}).get("scene"):
                        stages.add(value["stage"]["scene"])
        transition = row.get("stage_transition")
        marker = path.with_name("stage-transition.json")
        if pids and transition and marker.is_file():
            value = json.loads(marker.read_bytes())
            if str(value.get("pid")) in pids:
                results["stage_transition"] = "passed"
                stages.add(transition["to"])
    return dict(results, stages=sorted(stages))


def build(spec):
    if spec["schema"] != "whole-game-scoreboard-request-v1":
        raise ValueError("Unknown whole-game scoreboard request schema")
    if "census" in spec:
        if spec.keys() & {"candidate", "reference", "original_audit"} or not spec.get("device_receipts"):
            raise ValueError("A saved census requires device receipts as its only additional input")
        report = json.loads(pinned(spec["census"]).read_bytes())
        if report["schema"] != "whole-game-scoreboard-v1":
            raise ValueError("Unknown saved whole-game scoreboard schema")
        report["device"] = device_observations(spec["device_receipts"], report["apk_sha256"])
        return report
    reference = spec.get("reference")
    counts = defaultdict(Counter)
    files = Counter()
    with ExitStack() as stack:
        current = stack.enter_context(inventory(spec["candidate"]))
        prior = stack.enter_context(inventory(reference)) if reference else {}
        for name in sorted(current.keys() | prior.keys()):
            kind, present, expected = count_file(current.get(name), prior.get(name), counts)
            if kind:
                files[("candidate", kind)] += present
                files[("reference", kind)] += expected
                if kind == "bundle":
                    files[("candidate", "containers")] += bool(present)
                    files[("reference", "containers")] += bool(expected)
    audit = original_audit(spec["original_audit"]) if "original_audit" in spec else None
    names = {row["class_id"]: row["name"] for row in audit["classes"]} if audit else {}
    classes = [dict(class_id=cid, name=names.get(cid), owner=owner(cid), **{key: values[key] for key in STATUSES}) for cid, values in sorted(counts.items())]
    apk = spec["candidate"]["apk"]["sha256"]
    return dict(
        schema="whole-game-scoreboard-v1",
        apk_sha256=apk,
        reference_apk_sha256=reference["apk"]["sha256"] if reference else None,
        files={
            side: dict(bundles=files[side, "containers"], bundle_members=files[side, "bundle"], player_members=files[side, "player"])
            for side in ("candidate", "reference")
        },
        totals={key: sum(row[key] for row in classes) for key in STATUSES},
        classes=classes,
        device=device_observations(spec.get("device_receipts", []), apk),
        original_audit=audit,
    )


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    temp.replace(path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, help="Override the request's report path")
    args = parser.parse_args()
    request = json.loads(args.request.read_bytes())
    output = args.output if args.output is not None else Path(request["output"])
    scoreboard = build(request)
    write(output, scoreboard)
    print(json.dumps(dict(output=str(output), totals=scoreboard["totals"], files=scoreboard["files"])))
