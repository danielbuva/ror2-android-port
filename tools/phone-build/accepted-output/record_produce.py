"""Produce qualified animation and generic object records from original PC bundles.

Source schemas identify floats and clip arrays. No curve coefficient, pose,
event string or target body is supplied by the public recipe.
"""

import argparse
import hashlib
import importlib.util
import io
import json
import math
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
            element = node.children[1]
            if not element.children and element.size >= 0 and (not canonical or element.kind not in ("float", "#161")):
                cursor += count * element.size
            else:
                for index in range(count):
                    walk(element, path + (str(index),))
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


def native_stream(data):
    """Reconstruct source tangents, then pack native Hermite coefficients.

    AssetRipper's pinned exporter documents tangent reconstruction. Native
    SDK curve observations establish float32 rounding and operation order.
    Every input value/coefficient remains original; no target floats are read.
    """
    if len(data) < 4:
        raise ValueError("truncated streamed word extent")
    (length,) = struct.unpack_from("<I", data)
    if len(data) != 4 + length * 4:
        raise ValueError("invalid streamed word extent")
    words = list(struct.unpack_from("<" + "I" * length, data, 4))
    result, frames, cursor = list(words), [], 0

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    def number(value):
        return struct.unpack("<f", struct.pack("<I", value))[0]

    def word(value):
        return 0x7FC00000 if math.isnan(value) else struct.unpack("<I", struct.pack("<f", value))[0]

    while cursor < length:
        if cursor + 2 > length:
            raise ValueError("truncated streamed frame")
        time_word, count = words[cursor : cursor + 2]
        cursor += 2
        if count > (length - cursor) // 5:
            raise ValueError("truncated streamed key")
        keys = []
        for _ in range(count):
            keys.append((words[cursor], cursor))
            cursor += 5
        frames.append((number(time_word), keys))
    following = {}
    # The first frame holds reference curves; the final frame is a dummy.
    for frame_index in range(len(frames) - 2, 0, -1):
        time_value, keys = frames[frame_index]
        for index, position in keys:
            if index in following:
                next_time, next_position = following[index]
                delta_time = next_time - time_value
                if delta_time > 0 and math.isfinite(delta_time):
                    a, b, c, value = map(number, words[position + 1 : position + 5])
                    next_value = number(words[next_position + 4])
                    regular = a != 0 or b != 0 or c != 0
                    if not regular and value != next_value:
                        result[position + 1 : position + 4] = [0, 0, 0]
                    else:
                        out_slope = c if regular else 0.0
                        in_slope = f32(3 * ((a * delta_time) * delta_time) + 2 * (b * delta_time) + c) if regular else 0.0
                        dx = max(f32(delta_time), f32(0.0001))
                        inverse = f32(1 / dx)
                        square = f32(inverse * inverse)
                        difference = f32(next_value - value)
                        d0, d1 = f32(out_slope * dx), f32(in_slope * dx)
                        an = f32(f32(f32(d0 + d1) - difference) - difference)
                        bn = f32(f32(f32(f32(difference + f32(difference + difference)) - d0) - d0) - d1)
                        result[position + 1 : position + 4] = [word(f32(f32(an * square) * inverse)), word(f32(bn * square)), word(out_slope)]
            following[index] = (time_value, position)
    return struct.pack("<I" + "I" * length, length, *result)


def layout_clip(body, root, selected):
    """Reorder source binding groups and import selected constant/dense curves."""
    _, spans = fields(body, root)

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    def number(value):
        return struct.unpack("<f", struct.pack("<I", value))[0]

    def integer(path):
        start, end = spans[path]
        if end - start != 4:
            raise ValueError("invalid clip scalar extent")
        return struct.unpack_from("<I", body, start)[0]

    def array(path):
        start, end = spans[path]
        (count,) = struct.unpack_from("<I", body, start)
        if end - start != 4 + 4 * count:
            raise ValueError("invalid clip word array")
        return list(struct.unpack_from("<" + "I" * count, body, start + 4))

    def pack(values):
        return struct.pack("<I" + "I" * len(values), len(values), *values)

    bp = ("m_ClipBindingConstant", "genericBindings")
    bstart, bend = spans[bp]
    (count,) = struct.unpack_from("<I", body, bstart)
    order, folds = selected["binding_order"], selected["fold_bindings"]
    if (
        any(type(i) is not int for i in order + folds)
        or sorted(order) != list(range(count))
        or len(set(folds)) != len(folds)
        or any(not 0 <= i < count for i in folds)
    ):
        raise ValueError("invalid source binding selection")
    entries, groups, cursor = [], [], 0
    for index in range(count):
        path = bp + ("Array", str(index))
        start, end = spans[path]
        entries.append(body[start:end])
        typ, attribute = integer(path + ("typeID",)), integer(path + ("attribute",))
        dimension = {1: 3, 2: 4, 3: 3, 4: 3}.get(attribute, 1) if typ == 4 else 1
        groups.append(list(range(cursor, cursor + dimension)))
        cursor += dimension
    flat = [i for binding in order for i in groups[binding]]
    inverse = {i: j for j, i in enumerate(flat)}
    cp = ("m_MuscleClip", "m_Clip", "data")
    sp, dp, kp = cp + ("m_StreamedClip",), cp + ("m_DenseClip",), cp + ("m_ConstantClip", "data")
    ns, nd = integer(sp + ("curveCount",)), integer(dp + ("m_CurveCount",))
    cs = ns + nd
    folded = {i for binding in folds for i in groups[binding]}
    if any(i >= cs for i in folded):
        raise ValueError("cannot refold existing constants")
    new_ns = ns - sum(i < ns for i in folded)
    new_nd = nd - sum(ns <= i < cs for i in folded)
    new_cs = new_ns + new_nd
    if (
        any(i >= ns or i in folded for i in flat[:new_ns])
        or any(not ns <= i < cs or i in folded for i in flat[new_ns:new_cs])
        or any(i < cs and i not in folded for i in flat[new_cs:])
    ):
        raise ValueError("unqualified clip bucket movement")
    words = array(sp + ("data",))
    first, frames, position = {}, [], 0
    while position < len(words):
        if position + 2 > len(words):
            raise ValueError("truncated clip frame")
        time_word, n = words[position : position + 2]
        position += 2
        if n > (len(words) - position) // 5:
            raise ValueError("truncated clip keys")
        keys = []
        for _ in range(n):
            i = words[position]
            if i >= ns:
                raise ValueError("source curve outside stream")
            first.setdefault(i, words[position + 4])
            if i not in folded:
                keys.append((inverse[i], *words[position + 1 : position + 5]))
            position += 5
        if keys or not math.isfinite(number(time_word)):
            frames.extend((time_word, len(keys), *(word for key in sorted(keys, key=lambda key: key[0]) for word in key)))
    samples = array(dp + ("m_SampleArray",))
    old_frames = integer(dp + ("m_FrameCount",))
    if len(samples) != old_frames * nd or (nd and not old_frames):
        raise ValueError("dense sample extent differs")
    for i in folded:
        if i >= ns:
            first[i] = samples[i - ns]
    constants = array(kp)
    if len(flat) != cs + len(constants):
        raise ValueError("binding dimensions differ")
    new_constants = [constants[i - cs] if i >= cs else first[i] for i in flat[new_cs:]]
    policy = selected["dense_policy"]
    if policy not in ("preserve", "append", "interior-zero"):
        raise ValueError("unknown dense import policy")
    new_frames = old_frames
    if nd and policy != "preserve":
        rate, begin = number(integer(dp + ("m_SampleRate",))), number(integer(dp + ("m_BeginTime",)))
        if not math.isfinite(rate) or rate <= 0 or not math.isfinite(begin):
            raise ValueError("invalid dense sample timing")
        last = f32(f32((old_frames - 1) / rate) + begin)
        q = f32(f32(last - begin) * rate)
        new_frames = max(int(f32(q + number(0x3F7FFFFF))), 1) + 1
    if new_frames * new_nd > B.LIMIT // 4:
        raise ValueError("dense clip exceeds bounded output")
    new_samples = []
    for frame in range(new_frames):
        for i in flat[new_ns:new_cs]:
            value = samples[min(frame, old_frames - 1) * nd + i - ns]
            if policy == "interior-zero" and frame < old_frames - 1 and value == 0x80000000:
                value = 0
            new_samples.append(value)
    vp = ("m_MuscleClip", "m_ValueArrayDelta")
    vstart, vend = spans[vp]
    if struct.unpack_from("<I", body, vstart)[0] != len(flat) or vend - vstart != 4 + len(flat) * 8:
        raise ValueError("value-delta extent differs")
    delta_rows = []
    for i in flat:
        if i in folded:
            row = struct.pack("<II", first[i], first[i])
        else:
            row = body[vstart + 4 + i * 8 : vstart + 12 + i * 8]
            if policy == "interior-zero" and ns <= i < cs:
                row = struct.pack("<II", *(0 if value == 0x80000000 else value for value in struct.unpack("<II", row)))
        delta_rows.append(row)
    delta = struct.pack("<I", len(flat)) + b"".join(delta_rows)
    index_path = ("m_MuscleClip", "m_IndexArray")
    indices = array(index_path)
    if any(i != 0xFFFFFFFF and i not in inverse for i in indices):
        raise ValueError("root index outside source curves")
    indices = [inverse[i] if i != 0xFFFFFFFF else i for i in indices]
    changes = [
        (spans[index_path], pack(indices)),
        (spans[sp + ("data",)], pack(frames)),
        (spans[kp], pack(new_constants)),
        (spans[dp + ("m_SampleArray",)], pack(new_samples)),
        ((bstart, bend), struct.pack("<I", count) + b"".join(entries[i] for i in order)),
        ((vstart, vend), delta),
        (spans[sp + ("curveCount",)], struct.pack("<I", new_ns)),
        (spans[dp + ("m_CurveCount",)], struct.pack("<I", new_nd)),
        (spans[dp + ("m_FrameCount",)], struct.pack("<I", new_frames)),
    ]
    size = integer(("m_MuscleClipSize",)) + 4 * (len(frames) - len(words) + len(new_constants) - len(constants) + len(new_samples) - len(samples))
    changes.append((spans[("m_MuscleClipSize",)], struct.pack("<I", size)))
    result = bytearray(body)
    for (start, end), data in sorted(changes, reverse=True):
        result[start:end] = data
    return bytes(result)


def transform(body, root, selected):
    if set(selected) - {
        "canonical",
        "clear_reference_pose",
        "canonical_stream",
        "fold_constants",
        "references",
        "binding_attributes",
        "native_stream",
        "layout",
        "normalize_root_quaternions",
    }:
        raise ValueError("unknown AnimationClip operation")
    canonical = selected.get("canonical")
    if canonical not in (None, "zero-and-nan", "nan"):
        raise ValueError("unknown AnimationClip canonical policy")
    if not selected:
        return body
    result, spans = fields(body, root, canonical)
    result = O.remap(result, selected.get("references", []))
    result = bytearray(result)
    if selected.get("normalize_root_quaternions"):

        def f32(value):
            return struct.unpack("<f", struct.pack("<f", value))[0]

        index_start, index_end = spans[("m_MuscleClip", "m_IndexArray")]
        delta_start, delta_end = spans[("m_MuscleClip", "m_ValueArrayDelta")]
        index_count = struct.unpack_from("<I", body, index_start)[0]
        delta_count = struct.unpack_from("<I", body, delta_start)[0]
        if index_count < 14 or index_end - index_start != 4 + 4 * index_count or delta_end - delta_start != 4 + 8 * delta_count:
            raise ValueError("invalid root quaternion source arrays")
        indices = struct.unpack_from("<4i", body, index_start + 4 + 10 * 4)
        if any(index < -1 or index >= delta_count for index in indices):
            raise ValueError("invalid root quaternion source index")
        for side, name in enumerate(("m_StartX", "m_StopX")):
            start, end = spans[("m_MuscleClip", name, "q")]
            if end - start != 16:
                raise ValueError("invalid root quaternion extent")
            values = [
                struct.unpack_from("<f", body, delta_start + 4 + 8 * index + 4 * side)[0] if index >= 0 else float(i == 3) for i, index in enumerate(indices)
            ]
            squares = [f32(value * value) for value in values]
            norm = f32(f32(squares[0] + squares[1]) + f32(squares[2] + squares[3]))
            bits = struct.unpack("<I", struct.pack("<f", norm))[0]
            exponent, fraction = bits >> 23, bits & 0x7FFFFF
            if not 0 < exponent < 255:
                raise ValueError("invalid root quaternion magnitude")
            # ARM FRSQRTE seed followed by two FRSQRTS refinements. The step
            # fuses product, subtraction and halve before float32 rounding.
            scaled = 128 + (fraction >> 16) if exponent & 1 else 256 + (fraction >> 15)
            midpoint = (scaled + 0.5) / 512 if scaled < 256 else ((scaled & ~1) + 1) / 512
            estimate = math.floor(256 / math.sqrt(midpoint) + 0.5)
            inverse = math.ldexp(estimate / 256, (126 - exponent) // 2)
            for _ in range(2):
                product = f32(norm * inverse)
                correction = f32((3 - product * inverse) / 2)
                inverse = f32(inverse * correction)
            struct.pack_into("<4f", result, start, *(f32(value * inverse) for value in values))
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
    if selected.get("canonical_stream") or selected.get("fold_constants") or selected.get("native_stream"):
        clip = muscle + ("m_Clip", "data")
        stream = clip + ("m_StreamedClip",)
        start, end = spans[stream + ("data",)]
        data = native_stream(result[start:end]) if selected.get("native_stream") else result[start:end]
        data, values = streamed(data, canonical if selected.get("canonical_stream") else None, selected.get("fold_constants", False))
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
    return layout_clip(bytes(result), root, selected["layout"]) if "layout" in selected else bytes(result)


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
                        if typ["class_id"] != selected["class_id"] or selected["class_id"] not in (
                            1,
                            4,
                            21,
                            23,
                            65,
                            74,
                            91,
                            104,
                            114,
                            135,
                            136,
                            198,
                            199,
                            205,
                            215,
                            224,
                        ):
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
