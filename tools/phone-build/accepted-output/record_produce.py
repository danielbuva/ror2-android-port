"""Produce qualified animation and generic object records from original PC bundles.

Source schemas identify floats and clip arrays. No curve coefficient, pose,
event string or target body is supplied by the public recipe.
"""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import time


def module(name):
    spec = importlib.util.spec_from_file_location("_animation_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


W, O = module("unity_write"), module("object_produce")
B, M = W.B, O.M
SCHEMA = module("unity_mesh")


def fields(body, root, canonical=None):
    """Locate source fields and normalize only schema-declared float32 values."""
    result, revised = {}, bytearray(body)
    cursor = 0

    def word(offset):
        if offset + 4 > len(body):
            raise ValueError("truncated AnimationClip field")
        return struct.unpack_from("<I", body, offset)[0]

    def walk(node, path):
        nonlocal cursor
        start = cursor
        if node.flags & 1:
            if len(node.children) != 2:
                raise ValueError("invalid AnimationClip array schema")
            count = word(cursor)
            cursor += 4
            if count > len(body):
                raise ValueError("excessive AnimationClip array")
            for index in range(count):
                walk(node.children[1], path + (str(index),))
        elif node.children:
            for child in node.children:
                walk(child, path + ("data" if child.name == "#106" else child.name,))
        elif node.size >= 0:
            if node.kind in ("float", "#161") and canonical:
                value = word(cursor)
                if value & 0x7FFFFFFF > 0x7F800000:
                    struct.pack_into("<I", revised, cursor, 0x7FC00000)
                elif canonical == "zero-and-nan" and value == 0x80000000:
                    struct.pack_into("<I", revised, cursor, 0)
            cursor += node.size
        else:
            raise ValueError("unqualified AnimationClip field")
        if node.meta & 0x4000:
            cursor = (cursor + 3) // 4 * 4
        if cursor > len(body):
            raise ValueError("AnimationClip field outside original body")
        if path:
            result[path] = (start, cursor)

    for child in root.children:
        walk(child, (child.name,))
    if cursor != len(body):
        raise ValueError("unparsed AnimationClip bytes")
    return bytes(revised), result


def streamed(data, canonical=None, fold=False):
    """Normalize packed float words; fold only proven constant source curves."""
    if len(data) < 8 or len(data) % 4:
        raise ValueError("invalid streamed clip extent")
    (length,) = struct.unpack_from("<I", data)
    if len(data) != 4 + length * 4:
        raise ValueError("streamed clip word count differs")
    words = list(struct.unpack_from("<" + "I" * length, data, 4))
    cursor, values = 0, {}
    constant = True
    while cursor < length:
        if cursor + 2 > length:
            raise ValueError("truncated streamed frame")
        count = words[cursor + 1]
        if canonical == "zero-and-nan" and words[cursor] == 0x80000000:
            words[cursor] = 0
        cursor += 2
        if count > (length - cursor) // 5:
            raise ValueError("truncated streamed key")
        for _ in range(count):
            index = words[cursor]
            for offset in range(cursor + 1, cursor + 5):
                value = words[offset]
                if canonical and value & 0x7FFFFFFF > 0x7F800000:
                    words[offset] = 0x7FC00000
                elif canonical == "zero-and-nan" and value == 0x80000000:
                    words[offset] = 0
            a, b, c, value = words[cursor + 1 : cursor + 5]
            constant &= not any(word & 0x7FFFFFFF for word in (a, b, c)) and (index not in values or values[index] == value)
            values[index] = value
            cursor += 5
    if fold and not constant:
        raise ValueError("nonconstant streamed curve cannot fold")
    return struct.pack("<I" + "I" * length, length, *words), values


def transform(body, root, selected):
    if set(selected) - {"canonical", "clear_reference_pose", "canonical_stream", "fold_constants", "references", "binding_attributes"}:
        raise ValueError("unknown AnimationClip operation")
    canonical = selected.get("canonical")
    if canonical not in (None, "zero-and-nan", "nan"):
        raise ValueError("unknown AnimationClip canonical policy")
    if not selected:
        return body
    result, spans = fields(body, root, canonical)
    result = O.remap(result, selected.get("references", []))
    result = bytearray(result)
    attributes = {start for path, (start, end) in spans.items() if "genericBindings" in path and path[-1] == "attribute" and end - start == 4}
    for offset in selected.get("binding_attributes", []):
        if type(offset) is not int or offset not in attributes:
            raise ValueError("invalid AnimationClip binding attribute")
        (value,) = struct.unpack_from("<I", result, offset)
        struct.pack_into("<I", result, offset, (value & 0x0FFFFFFF) | 0x80000000)
    changes = []
    muscle = ("m_MuscleClip",)
    if selected.get("clear_reference_pose"):
        start, end = spans[muscle + ("m_ValueArrayReferencePose",)]
        (count,) = struct.unpack_from("<I", result, start)
        if end - start != 4 + count * 4:
            raise ValueError("invalid reference-pose extent")
        changes.append((start, end, bytes(4)))
        # m_MuscleClipSize is the source import value, not the new byte count.
    if selected.get("canonical_stream") or selected.get("fold_constants"):
        clip = muscle + ("m_Clip", "data")
        stream = clip + ("m_StreamedClip",)
        start, end = spans[stream + ("data",)]
        data, values = streamed(result[start:end], canonical if selected.get("canonical_stream") else None, selected.get("fold_constants", False))
        if selected.get("fold_constants"):
            count_start, _ = spans[stream + ("curveCount",)]
            (count,) = struct.unpack_from("<I", result, count_start)
            dense_start, _ = spans[clip + ("m_DenseClip", "m_CurveCount")]
            constant_start, constant_end = spans[clip + ("m_ConstantClip", "data")]
            if set(values) != set(range(count)) or struct.unpack_from("<I", result, dense_start)[0] or constant_end - constant_start != 4:
                raise ValueError("constant fold requires complete exclusive source curves")
            data = struct.pack("<III", 2, 0x7F800000, 0)
            struct.pack_into("<I", result, count_start, 0)
            constant = struct.pack("<I" + "I" * count, count, *(values[i] for i in range(count)))
            changes.append((constant_start, constant_end, constant))
            size_start, _ = spans[("m_MuscleClipSize",)]
            (size,) = struct.unpack_from("<I", result, size_start)
            struct.pack_into("<I", result, size_start, size + len(data) - (end - start) + len(constant) - 4)
        changes.append((start, end, data))
    for start, end, data in sorted(changes, reverse=True):
        result[start:end] = data
    return bytes(result)


def transform_generic(body, class_id, selected):
    if set(selected) - {"references", "demote_keywords"} or (selected.get("demote_keywords") and class_id != 21):
        raise ValueError("unknown generic object operation")
    result = O.remap(body, selected.get("references", []))
    return O.demote_material_keywords(result) if selected.get("demote_keywords") else result


def produce(profile_path, profile_sha256, pc, output):
    if B.sha(profile_path) != profile_sha256:
        raise ValueError("object-record profile drift")
    profile = json.loads(profile_path.read_text())
    if set(profile) != {"input_id", "bundles"} or profile["input_id"] != M.INPUT_ID:
        raise ValueError("unknown object-record input")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("object-record output must be new and outside original input")
    expected = sum(target["bytes"] for bundle in profile["bundles"] for member in bundle["members"] for clip in member["objects"] for target in clip["outputs"])
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient object-record output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": M.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0}
    try:
        with (output / "objects.bin").open("xb") as data, (output / "index.jsonl").open("x") as index:
            for source in profile["bundles"]:
                path = M.safe_input(pc, source["path"])
                before = path.stat()
                if B.sha(path) != source["sha256"]:
                    raise ValueError("original object-record bundle drift")
                bundle = B.Bundle(path)
                for selected_member in source["members"]:
                    member = bundle.member(selected_member["name"])
                    metadata = W.read_serialized(member)
                    objects = {row["path_id"]: row for row in metadata["objects"]}
                    for selected in selected_member["objects"]:
                        obj = objects[selected["path_id"]]
                        typ = metadata["types"][obj["type_id"]]
                        if typ["class_id"] != selected["class_id"] or selected["class_id"] not in (74, 91, 21):
                            raise ValueError("unqualified original object class")
                        member.seek(metadata["data_offset"] + obj["offset"])
                        body = B.exact(member, obj["bytes"])
                        if hashlib.sha256(body).hexdigest() != selected["sha256"]:
                            raise ValueError("original object-record body drift")
                        root = SCHEMA.type_tree(io.BytesIO(typ["tree"]))
                        for target in selected["outputs"]:
                            operations = target.get("transform", {})
                            if typ["class_id"] == 74:
                                result = transform(body, root, operations)
                            else:
                                result = transform_generic(body, typ["class_id"], operations)
                            digest = hashlib.sha256(result).hexdigest()
                            if digest != target["sha256"] or len(result) != target["bytes"]:
                                raise ValueError("produced object record differs from accepted hash")
                            row = {key: target[key] for key in ("bundle", "member", "path_id", "bytes", "sha256")}
                            row["offset"] = data.tell()
                            data.write(result)
                            index.write(json.dumps(row, sort_keys=True) + "\n")
                            receipt["objects"] += 1
                            receipt["object_bytes"] += len(result)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or B.sha(path) != source["sha256"]:
                    raise ValueError("original object-record input changed during production")
        with (output / "objects.bin").open("rb") as data, (output / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                data.seek(row["offset"])
                if hashlib.sha256(B.exact(data, row["bytes"])).hexdigest() != row["sha256"]:
                    raise ValueError("persisted object-record extent drift")
        receipt["outputs"] = {name: {"bytes": (output / name).stat().st_size, "sha256": B.sha(output / name)} for name in ("objects.bin", "index.jsonl")}
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output)


if __name__ == "__main__":
    main()
