"""Host-only full-scene qualification; no producer reads comparison artifacts.

Lighting recipes select native sample fields, never arbitrary byte masks. Every
other serialized byte and bundle member remains exact. Unsupported schemas or
encodings remain mismatches. See ADR-003 for measurement and visual review.
"""

import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct


def module(name):
    spec = importlib.util.spec_from_file_location("_lighting_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


W = module("unity_write")
M = module("unity_mesh")
B = W.B


def digest(data):
    return hashlib.sha256(data).hexdigest()


def member(data):
    stream = io.BytesIO(data)
    stream.size = len(data)
    return stream


def pointers(body, root):
    """Read actual native PPtr leaves, including LightmapSettings arrays."""
    cursor = 0
    found = []

    def walk(node, path):
        nonlocal cursor
        start = cursor
        if node.kind.startswith("PPtr<"):
            if node.size != 12:
                raise ValueError("unsupported lighting pointer schema")
            found.append((path, struct.unpack_from("<iq", body, cursor)))
            cursor += 12
        elif node.flags & 1:
            count = struct.unpack_from("<I", body, cursor)[0]
            cursor += 4
            if len(node.children) != 2 or count > len(body):
                raise ValueError("invalid lighting array")
            for _ in range(count):
                walk(node.children[1], path)
        elif node.children:
            for child in node.children:
                walk(child, path + (child.name,))
        elif node.size >= 0:
            cursor += node.size
        else:
            raise ValueError("unsupported lighting schema")
        if node.meta & 0x4000:
            cursor = (cursor + 3) // 4 * 4
        if not start <= cursor <= len(body):
            raise ValueError("lighting schema exceeds body")

    walk(root, ())
    if cursor != len(body):
        raise ValueError("unparsed lighting bytes")
    return found


def compare_member(reference, candidate, rules):
    """Compare one v22 member; rules are reviewed, per-record measured recipes.

    Require identical physical layout, native identities and embedded schemas.
    Returning tolerance-accepted never changes the raw-exact classification.
    """
    old, new = W.read_serialized(reference), W.read_serialized(candidate)
    if old != new:
        raise ValueError("serialized metadata/layout differs")
    objects = {row["path_id"]: row for row in old["objects"]}
    selected = set()
    accepted = []
    extents = []
    for rule in rules:
        pid = rule["path_id"]
        if pid in selected:
            raise ValueError("duplicate lighting record")
        selected.add(pid)
        row = objects[pid]
        native = old["types"][row["type_id"]]
        cid = native["class_id"]
        if cid != rule["class_id"] or cid not in (28, 89, 104, 258):
            raise ValueError("record class outside lighting sample scope")
        if not old["trees"]:
            raise ValueError("embedded native sample schema required")
        start = old["data_offset"] + row["offset"]
        reference.seek(start)
        before = B.exact(reference, row["bytes"])
        candidate.seek(start)
        after = B.exact(candidate, row["bytes"])
        tree = M.type_tree(io.BytesIO(native["tree"]))
        fields = M.spans(before, tree)
        if fields != M.spans(after, tree):
            raise ValueError("lighting field layout differs")
        if cid == 89:
            owner = objects[rule["reflection_owner"]]
            owner_type = old["types"][owner["type_id"]]
            if owner_type["class_id"] not in (104, 215):
                raise ValueError("Cubemap requires reflection binding")
            reference.seek(old["data_offset"] + owner["offset"])
            body = B.exact(reference, owner["bytes"])
            links = pointers(body, M.type_tree(io.BytesIO(owner_type["tree"])))
            if not any(
                path and path[-1] in ("m_GeneratedSkyboxReflection", "m_CustomReflection", "m_BakedTexture", "m_CustomBakedTexture") and pointer == (0, pid)
                for path, pointer in links
            ):
                raise ValueError("Cubemap is not a bound reflection")
        if cid == 28:
            owner = objects[rule["lightmap_owner"]]
            owner_type = old["types"][owner["type_id"]]
            if owner_type["class_id"] != 157:
                raise ValueError("Texture2D requires LightmapSettings binding")
            reference.seek(old["data_offset"] + owner["offset"])
            body = B.exact(reference, owner["bytes"])
            links = pointers(body, M.type_tree(io.BytesIO(owner_type["tree"])))
            if not any(path and path[0] == "m_Lightmaps" and pointer == (0, pid) for path, pointer in links):
                raise ValueError("Texture2D is not a bound lightmap")
        covered = []
        measured = []
        for sample in rule["samples"]:
            path = tuple(sample["field"])
            if cid in (104, 258):
                allowed = ("m_AmbientProbe",) if cid == 104 else ("m_BakedCoefficients", "Array", "payload")
                if path != allowed:
                    raise ValueError("field outside ambient coefficient scope")
                code, width = "f", 4
            else:
                if path != ("image data", "Array", "payload"):
                    raise ValueError("field outside lighting texel scope")
                a, b = fields[("m_TextureFormat",)]
                if b - a != 4:
                    raise ValueError("invalid texture format field")
                fmt = struct.unpack("<i", before[a:b])[0]
                formats = {3: ("B", 1, 3), 4: ("B", 1, 4), 17: ("e", 2, 4), 20: ("f", 4, 4)}
                if fmt not in formats:
                    raise ValueError("unsupported lighting texel encoding")
                code, width, channels = formats[fmt]
                if sample["channels"] != channels:
                    raise ValueError("lighting texture channel count differs")
            a, b = fields[path]
            channels = sample["channels"]
            if cid in (104, 258) and channels != 27:
                raise ValueError("ambient bounds must identify all 27 native coefficients")
            bounds = sample["max_abs"]
            if (
                type(channels) is not int
                or not 1 <= channels <= 27
                or len(bounds) != channels
                or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in bounds)
            ):
                raise ValueError("finite measured per-channel bounds required")
            if not sample["measurement"].strip() or b <= a or (b - a) % (width * channels):
                raise ValueError("complete measured lighting samples required")
            if cid in (104, 258) and (b - a) % (27 * 4):
                raise ValueError("complete 27-coefficient ambient probes required")
            maxima = [0.0] * channels
            for index, (x, y) in enumerate(zip(struct.iter_unpack("<" + code, before[a:b]), struct.iter_unpack("<" + code, after[a:b]))):
                if not math.isfinite(x[0]) or not math.isfinite(y[0]):
                    raise ValueError("nonfinite lighting sample")
                channel = index % channels
                maxima[channel] = max(maxima[channel], abs(x[0] - y[0]))
            if any(actual > limit for actual, limit in zip(maxima, bounds)):
                raise ValueError("lighting sample exceeds measured bound")
            covered.append((a, b))
            measured.append(dict(field=list(path), max_abs=maxima))
        if not covered:
            raise ValueError("lighting sample selection required")
        at = 0
        for a, b in sorted(covered):
            if a < at:
                raise ValueError("overlapping lighting fields")
            if before[at:a] != after[at:a]:
                raise ValueError("non-lighting record bytes differ")
            at = b
            extents.append((start + a, start + b))
        if before[at:] != after[at:]:
            raise ValueError("non-lighting record bytes differ")
        if before != after:
            accepted.append(dict(path_id=pid, class_id=cid, measured=measured))
    # Includes metadata, PPtrs, unselected records, padding and trailing bytes.
    at = 0
    for a, b in sorted(extents) + [(old["bytes"], old["bytes"])]:
        if a < at:
            raise ValueError("overlapping serialized sample extents")
        reference.seek(at)
        candidate.seek(at)
        remaining = a - at
        while remaining:
            count = min(65536, remaining)
            if B.exact(reference, count) != B.exact(candidate, count):
                raise ValueError("non-lighting member bytes differ")
            remaining -= count
        at = b
    return dict(status="tolerance-accepted" if accepted else "raw-exact", records=accepted)


def qualify(reference, candidate, recipe):
    """Compare final standalone serialized data or every UnityFS member."""
    if B.sha(reference) != recipe["reference_sha256"]:
        raise ValueError("lighting reference pin differs")
    with reference.open("rb") as stream:
        bundled = stream.read(8) == b"UnityFS\0"
    if not bundled:
        if set(recipe["members"]) != {""}:
            raise ValueError("standalone lighting member must be named empty string")
        with reference.open("rb") as old, candidate.open("rb") as new:
            old.size, new.size = reference.stat().st_size, candidate.stat().st_size
            return compare_member(old, new, recipe["members"][""])
    old, new = B.Bundle(reference), B.Bundle(candidate)
    if (
        old.members != new.members
        or old.identity != new.identity
        or old.framing != new.framing
        or [(n, f) for _, n, _, f in old.blocks] != [(n, f) for _, n, _, f in new.blocks]
    ):
        raise ValueError("bundle identities/layout differs")
    if set(recipe["members"]) - old.members.keys():
        raise ValueError("lighting recipe names unknown member")
    reports = {}
    for name, (_, size, flags) in old.members.items():
        if name in recipe["members"]:
            if not flags & 4:
                raise ValueError("lighting rules require a serialized member")
            reports[name] = compare_member(old.member(name), new.member(name), recipe["members"][name])
        else:
            a, b = old.member(name), new.member(name)
            for _ in range(0, size, 65536):
                if a.read(65536) != b.read(65536):
                    raise ValueError("unselected bundle member differs")
    at = 0
    total = sum(size for _, size, _, _ in old.blocks)
    for offset, size, _ in sorted(old.members.values()) + [(total, 0, 0)]:
        if offset < at:
            raise ValueError("overlapping bundle members")
        while at < offset:
            count = min(65536, offset - at)
            if old.read(at, count) != new.read(at, count):
                raise ValueError("non-lighting bundle padding differs")
            at += count
        at = offset + size
    accepted = any(row["status"] == "tolerance-accepted" for row in reports.values())
    if not accepted and B.sha(reference) != B.sha(candidate):
        raise ValueError("bundle framing differs without lighting differences")
    return dict(status="tolerance-accepted" if accepted else "raw-exact", members=reports)


def verify(selection, row):
    """Readiness admission with pinned recipe, J850 reference and visual review."""
    evidence = []

    def document(pin):
        path = Path(pin["path"])
        if B.sha(path) != pin["sha256"]:
            raise ValueError("lighting evidence pin differs")
        evidence.append(dict(path=str(path), sha256=pin["sha256"]))
        return json.loads(path.read_text())

    recipe = document(selection["recipe"])
    visual = document(selection["visual"])
    reference = Path(selection["reference"])
    if recipe["reference_sha256"] != row["target_sha256"] or B.sha(reference) != row["target_sha256"]:
        raise ValueError("lighting reference is not the selected target")
    if B.sha(Path(row["source"])) != row["sha256"]:
        raise ValueError("lighting candidate changed")
    if (
        visual["reference_sha256"] != row["target_sha256"]
        or visual["candidate_sha256"] != row["sha256"]
        or visual["parity"] is not True
        or not visual["review"].strip()
    ):
        raise ValueError("matched visual parity review required")
    report = qualify(reference, Path(row["source"]), recipe)
    if report["status"] != "tolerance-accepted":
        raise ValueError("changed lighting samples required for tolerance admission")
    evidence.append(dict(path=str(reference), sha256=row["target_sha256"]))
    return report, evidence
