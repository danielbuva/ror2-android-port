"""Produce qualified animation and generic object records from original PC bundles.

Source schemas identify floats and clip arrays. No curve coefficient, pose,
event string or target body is supplied by the public recipe.
"""

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import shutil
import struct
import time
import zlib


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
    if not nd and policy != "preserve":
        rate = number(integer(("m_SampleRate",)))
        stop = number(integer(("m_MuscleClip", "m_StopTime")))
        if not math.isfinite(rate) or rate <= 0 or not math.isfinite(stop) or stop < 0:
            raise ValueError("invalid empty dense timing")
        new_frames = max(int(f32(f32(stop * rate) + number(0x3F7FFFFF))), 1) + 1
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
    if not nd and policy != "preserve":
        changes.extend([(spans[dp + ("m_SampleRate",)], struct.pack("<f", rate)), (spans[dp + ("m_BeginTime",)], bytes(4))])
    size = integer(("m_MuscleClipSize",)) + 4 * (len(frames) - len(words) + len(new_constants) - len(constants) + len(new_samples) - len(samples))
    changes.append((spans[("m_MuscleClipSize",)], struct.pack("<I", size)))
    result = bytearray(body)
    for (start, end), data in sorted(changes, reverse=True):
        result[start:end] = data
    return bytes(result)


def normalize_quaternion(values):
    """Normalize source quaternions with the admitted ARM float32 operations."""

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

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
    return [f32(value * inverse) for value in values]


def root_average(body, root):
    """Integrate original generic root curves over twenty native sample intervals."""

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    def dot(value):
        square = [f32(v * v) for v in value]
        return f32(f32(square[0] + square[1]) + f32(square[2] + square[3]))

    normalize = normalize_quaternion

    def conjugate(q):
        return [-q[0], -q[1], -q[2], q[3]]

    def multiply(left, right):
        ax, ay, az, aw = left
        bx, by, bz, bw = right
        x = -f32(f32(f32(f32(az * by) - f32(ay * bz)) - f32(aw * bx)) - f32(ax * bw))
        y = -f32(f32(f32(f32(ax * bz) - f32(az * bx)) - f32(aw * by)) - f32(ay * bw))
        z = -f32(f32(f32(f32(ay * bx) - f32(aw * bz)) - f32(az * bw)) - f32(ax * by))
        w = f32(f32(f32(f32(aw * bw) - f32(ax * bx)) - f32(az * bz)) - f32(ay * by))
        return [x, y, z, w]

    def heading(q):
        # Rotate world up, remove tilt, then project to the yaw quaternion.
        value = [f32(v * q[3]) for v in q]
        value[3] = f32(value[3] - 0.5)
        rotated = [-value[2], value[3], value[0], -value[1]]
        up = [f32(2 * f32(f32(q[i] * q[1]) + rotated[i])) for i in range(4)]
        swing = normalize([-up[2], 0.0, up[0], f32(up[1] + f32(math.sqrt(dot(up))))])
        value = multiply(swing, q)
        value = [f32(value[0] * 0.0), value[1], f32(value[2] * 0.0), value[3]]
        length = f32(math.sqrt(dot(value)))
        if not length:
            raise ValueError("invalid projected heading")
        return [f32(v / length) for v in value]

    def rotate(q, delta):
        x, y, z, w = q
        column_x = [
            f32(f32(y * f32(-2 * y)) - f32(z * f32(2 * z))),
            f32(f32(x * f32(2 * y)) - f32(w * f32(-2 * z))),
            f32(f32(w * f32(-2 * y)) - f32(x * f32(-2 * z))),
        ]
        column_y = [
            f32(f32(w * f32(-2 * z)) - f32(y * f32(-2 * x))),
            f32(f32(z * f32(-2 * z)) - f32(x * f32(2 * x))),
            f32(f32(y * f32(2 * z)) - f32(w * f32(-2 * x))),
        ]
        column_z = [
            f32(f32(z * f32(2 * x)) - f32(w * f32(-2 * y))),
            f32(f32(w * f32(-2 * x)) - f32(z * f32(-2 * y))),
            f32(f32(x * f32(-2 * x)) - f32(y * f32(2 * y))),
        ]
        return [f32(f32(delta[i] + f32(column_x[i] * delta[0])) + f32(f32(column_y[i] * delta[1]) + f32(column_z[i] * delta[2]))) for i in range(3)]

    _, spans = fields(body, root)
    muscle = ("m_MuscleClip",)
    clip = muscle + ("m_Clip", "data")

    def integer(path):
        return struct.unpack_from("<I", body, spans[path][0])[0]

    def number(path):
        return struct.unpack_from("<f", body, spans[path][0])[0]

    def array(path, kind):
        start, end = spans[path]
        count = struct.unpack_from("<I", body, start)[0]
        if end - start != 4 + 4 * count:
            raise ValueError("invalid root curve array")
        return struct.unpack_from("<" + kind * count, body, start + 4)

    stream = clip + ("m_StreamedClip",)
    dense = clip + ("m_DenseClip",)
    ns, nd = integer(stream + ("curveCount",)), integer(dense + ("m_CurveCount",))
    frame_count = integer(dense + ("m_FrameCount",))
    rate, begin = number(dense + ("m_SampleRate",)), number(dense + ("m_BeginTime",))
    words = array(stream + ("data",), "I")
    samples = array(dense + ("m_SampleArray",), "f")
    constants = array(clip + ("m_ConstantClip", "data"), "f")
    indices = array(muscle + ("m_IndexArray",), "i")
    if len(indices) < 14 or any(i >= 0 for i in indices[:7]) or number(muscle + ("m_OrientationOffsetY",)) != 0:
        raise ValueError("unqualified root average layout")
    if any(i < -1 or i >= ns + nd + len(constants) for i in indices[7:14]) or len(samples) != frame_count * nd:
        raise ValueError("invalid root average source index")
    keys, cursor = {}, 0
    while cursor < len(words):
        if cursor + 2 > len(words):
            raise ValueError("truncated root streamed frame")
        time_word, count = words[cursor : cursor + 2]
        time_value = struct.unpack("<f", struct.pack("<I", time_word))[0]
        cursor += 2
        if count > (len(words) - cursor) // 5:
            raise ValueError("truncated root streamed keys")
        for _ in range(count):
            index, *coefficients = words[cursor : cursor + 5]
            coefficients = struct.unpack("<4f", struct.pack("<4I", *coefficients))
            keys.setdefault(index, []).append((time_value, coefficients))
            cursor += 5

    def sample(time_value, index):
        if index >= ns + nd:
            return constants[index - ns - nd]
        if index >= ns:
            if not frame_count or not math.isfinite(rate) or rate <= 0:
                raise ValueError("invalid root dense timing")
            value = f32(f32(time_value - begin) * rate)
            whole = math.trunc(value)
            alpha = f32(value - whole)
            low, high = min(max(whole, 0), frame_count - 1), min(max(whole + 1, 0), frame_count - 1)
            first = samples[low * nd + index - ns]
            return f32(first + f32(alpha * f32(samples[high * nd + index - ns] - first)))
        if index not in keys:
            raise ValueError("missing root source curve")
        eligible = [key for key in keys[index] if key[0] <= time_value]
        if not eligible:
            raise ValueError("root curve starts after sample")
        key_time, (a, b, c, value) = eligible[-1]
        delta = f32(time_value - key_time)
        return f32(value + f32(delta * f32(c + f32(delta * f32(b + f32(delta * a))))))

    start, stop = number(muscle + ("m_StartTime",)), number(muscle + ("m_StopTime",))
    step = f32(f32(stop - start) / 20)
    if not math.isfinite(step) or step <= 0:
        raise ValueError("invalid root sample interval")
    initial = list(struct.unpack_from("<4f", body, spans[muscle + ("m_StartX", "q")][0]))
    flag = lambda name: bool(body[spans[muscle + (name,)][0]])
    offset = normalize(conjugate(initial)) if flag("m_KeepOriginalOrientation") else [0.0, 0.0, 0.0, 1.0]
    blend, mirror = flag("m_LoopBlendOrientation"), flag("m_Mirror")
    previous, previous_position = None, None
    linear, angular, time_value = [0.0, 0.0, 0.0], 0.0, start
    for _ in range(21):
        position = [sample(time_value, indices[7 + i]) if indices[7 + i] >= 0 else 0.0 for i in range(3)]
        rotation = normalize([sample(time_value, indices[10 + i]) if indices[10 + i] >= 0 else (1.0 if i == 3 else 0.0) for i in range(4)])
        if blend:
            rotation = initial
        rotation = normalize(multiply(offset, heading(rotation)))
        if previous is not None:
            inverse = conjugate(previous)
            delta_rotation = multiply(inverse, rotation)
            ratio = f32(delta_rotation[1] / delta_rotation[3])
            angle = f32(f32(2 * f32(math.atan(ratio))) / step)
            delta = rotate(inverse, [f32(a - b) for a, b in zip(position, previous_position)])
            if mirror:
                angle, delta[0] = -angle, -delta[0]
            linear = [f32(a + f32(b / step)) for a, b in zip(linear, delta)]
            angular = f32(angular + angle)
        previous, previous_position = rotation, position
        time_value = f32(time_value + step)
    linear = [f32(value / 20) for value in linear]
    if flag("m_LoopBlendPositionXZ"):
        linear[0] = linear[2] = 0.0
    if flag("m_LoopBlendPositionY"):
        linear[1] = 0.0
    result = bytearray(body)
    struct.pack_into("<3f", result, spans[muscle + ("m_AverageSpeed",)][0], *linear)
    struct.pack_into("<f", result, spans[muscle + ("m_AverageAngularSpeed",)][0], f32(angular / 20))
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
        "root_average",
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
            struct.pack_into("<4f", result, start, *normalize_quaternion(values))
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
    result = layout_clip(bytes(result), root, selected["layout"]) if "layout" in selected else bytes(result)
    return root_average(result, root) if selected.get("root_average") else result


def reorder_controller_clips(body, root, order):
    """Move complete source clip entries and remap leaf indices inversely."""
    _, spans = fields(body, root)
    start, end = spans[("m_AnimationClips",)]
    count = struct.unpack_from("<I", body, start)[0]
    if end - start != 4 + 12 * count or any(type(i) is not int for i in order) or sorted(order) != list(range(count)):
        raise ValueError("controller clip order is not a complete permutation")
    inverse = {old: new for new, old in enumerate(order)}
    result = bytearray(body)
    for path, (offset, stop) in spans.items():
        if path[0] != "m_Controller" or path[-1] != "m_ClipID":
            continue
        child_start, _ = spans[path[:-1] + ("m_ChildIndices",)]
        if stop - offset != 4:
            raise ValueError("invalid controller clip index extent")
        if struct.unpack_from("<I", body, child_start)[0]:
            continue  # Blend-tree parent ClipID does not refer to a clip.
        old = struct.unpack_from("<I", body, offset)[0]
        if old != 0xFFFFFFFF:
            if old not in inverse:
                raise ValueError("controller leaf outside source clips")
            struct.pack_into("<I", result, offset, inverse[old])
    result[start + 4 : end] = b"".join(body[start + 4 + i * 12 : start + 16 + i * 12] for i in order)
    return bytes(result)


def exported_clip_tos(value):
    """Rebuild the qualified export path from an original clip-path TOS entry."""
    if not value.startswith("Assets/"):
        raise ValueError("not an original clip asset path")
    match = re.search(r"\.(fbx|anim)", value, re.I)
    if not match or not (clip_name := value[match.end() :]):
        raise ValueError("missing original clip name")
    name = clip_name.replace("(Clone)", "").replace("(Instance)", "").strip()
    name = re.sub(r"[/:,\[\]\x00-\x1f]", "_", name)
    if not name or len((name + ".anim").encode()) > 240:
        raise ValueError("unqualified export filename")
    directory = value[: match.start()].rsplit("/", 1)[0]
    return directory.replace("Assets/", "Assets/WholeGame/", 1) + "/" + name + ".anim" + clip_name


def controller_tos(body, root, selection):
    _, spans = fields(body, root)
    start, end = spans[("m_TOS",)]
    count = struct.unpack_from("<I", body, start)[0]
    if len({row[0] for row in selection}) != len(selection) or any(
        type(i) is not int or not 0 <= i < count or type(rebuild) is not bool for i, rebuild in selection
    ):
        raise ValueError("invalid original controller TOS selection")
    rows = []
    for index, rebuild in selection:
        a, b = spans[("m_TOS", "Array", str(index))]
        raw = body[a:b]
        key, size = struct.unpack_from("<II", raw)
        value = raw[8 : 8 + size].decode("utf-8")
        if zlib.crc32(value.encode()) != key:
            raise ValueError("original TOS CRC drift")
        if rebuild:
            encoded = exported_clip_tos(value).encode("utf-8")
            raw = struct.pack("<II", zlib.crc32(encoded), len(encoded)) + encoded
            raw += bytes(-len(raw) % 4)
        rows.append(raw)
    return body[:start] + struct.pack("<I", len(rows)) + b"".join(rows) + body[end:]


def bounded_f32_pi():
    rounded = struct.unpack("<f", struct.pack("<f", math.pi))[0]
    bits = struct.unpack("<I", struct.pack("<f", rounded))[0]
    return struct.unpack("<f", struct.pack("<I", bits - (rounded > math.pi)))[0]


def controller_opposed_angles(body, root):
    """Honor the bounded acos endpoint for source-derived opposing vectors."""

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    _, spans = fields(body, root)
    result = bytearray(body)
    for path, (start, _) in spans.items():
        if path[-1] != "m_BlendType" or struct.unpack_from("<I", body, start)[0] != 2:
            continue
        prefix = path[:-1] + ("m_Blend2dData", "data")
        positions = prefix + ("m_ChildPositionArray",)
        count = struct.unpack_from("<I", body, spans[positions][0])[0]
        points = [struct.unpack_from("<ff", body, spans[positions + ("Array", str(i))][0]) for i in range(count)]
        for j, (bx, by) in enumerate(points):
            for i, (ax, ay) in enumerate(points):
                aa = f32(f32(ax * ax) + f32(ay * ay))
                bb = f32(f32(bx * bx) + f32(by * by))
                if not aa or not bb:
                    continue
                dot = f32(f32(ax * bx) + f32(ay * by))
                denominator = f32(f32(math.sqrt(aa)) * f32(math.sqrt(bb)))
                cosine = f32(dot / denominator)
                cross = f32(f32(ax * by) - f32(bx * ay))
                if cosine <= -1 and cross == 0:
                    offset, end = spans[prefix + ("m_ChildPairVectorArray", "Array", str(i + j * count), "x")]
                    angle = struct.unpack_from("<f", body, offset)[0]
                    if end - offset != 4 or angle not in (f32(math.pi), bounded_f32_pi()):
                        raise ValueError("original opposed angle drift")
                    struct.pack_into("<f", result, offset, bounded_f32_pi())
    return bytes(result)


def controller_singleton_behaviours(body, root, order):
    _, spans = fields(body, root)
    inverse = {old: new for new, old in enumerate(order)}
    start, end = spans[("m_StateMachineBehaviours",)]
    count = struct.unpack_from("<I", body, start)[0]
    if any(type(i) is not int for i in order) or sorted(order) != list(range(count)) or end - start != 4 + 12 * count:
        raise ValueError("invalid behaviour permutation")
    prefix = ("m_StateMachineBehaviourVectorDescription",)
    a, b = spans[prefix + ("m_StateMachineBehaviourIndices",)]
    n = struct.unpack_from("<I", body, a)[0]
    if b - a != 4 + 4 * n or n != count or list(struct.unpack_from("<" + "I" * n, body, a + 4)) != list(range(n)):
        raise ValueError("nonidentity source behaviour indices")
    out = bytearray(body)
    out[start + 4 : end] = b"".join(body[start + 4 + i * 12 : start + 16 + i * 12] for i in order)
    seen = []
    for path, (a, b) in spans.items():
        if path[:2] != prefix + ("m_StateMachineBehaviourRanges",) or path[-1] != "m_StartIndex":
            continue
        c, d = spans[path[:-1] + ("m_Count",)]
        if b - a != 4 or d - c != 4 or struct.unpack_from("<I", body, c)[0] != 1:
            raise ValueError("nonsingleton behaviour range")
        old = struct.unpack_from("<I", body, a)[0]
        seen.append(old)
        struct.pack_into("<I", out, a, inverse[old])
    if sorted(seen) != list(range(n)):
        raise ValueError("incomplete source behaviour ranges")
    return bytes(out)


def transform_generic(body, class_id, selected, root=None):
    if set(selected) - {
        "references",
        "demote_keywords",
        "controller_clip_order",
        "controller_tos",
        "controller_opposed_angles",
        "controller_behaviour_order",
        "canonical",
    } or (selected.get("demote_keywords") and class_id != 21):
        raise ValueError("unknown generic object operation")
    if any(key.startswith("controller_") or key == "canonical" for key in selected) and (class_id != 91 or root is None):
        raise ValueError("controller operations require original controller schema")
    if "controller_clip_order" in selected:
        if class_id != 91 or root is None:
            raise ValueError("controller clip order requires original controller schema")
        body = reorder_controller_clips(body, root, selected["controller_clip_order"])
    if selected.get("controller_opposed_angles"):
        body = controller_opposed_angles(body, root)
    if "canonical" in selected:
        if selected["canonical"] != "nan":
            raise ValueError("unqualified controller float policy")
        body = fields(body, root, "nan")[0]
    if "controller_tos" in selected:
        body = controller_tos(body, root, selected["controller_tos"])
    if "controller_behaviour_order" in selected:
        body = controller_singleton_behaviours(body, root, selected["controller_behaviour_order"])
    result = O.remap(body, selected.get("references", []))
    return O.demote_material_keywords(result) if selected.get("demote_keywords") else result


def profile_bundles(path):
    """Stream bounded source-bundle groups from large compressed recipes."""
    if str(path).endswith(".jsonl.gz"):
        with gzip.open(path, "rb") as stream:
            header = json.loads(stream.readline(8 * 1024**2 + 1))
            if set(header) != {"input_id"} or header["input_id"] != M.INPUT_ID:
                raise ValueError("unknown object-record input")
            while line := stream.readline(8 * 1024**2 + 1):
                if len(line) > 8 * 1024**2 or not line.endswith(b"\n"):
                    raise ValueError("object-record source group exceeds bounded recipe line")
                source = json.loads(line)
                if set(source) != {"path", "sha256", "members"}:
                    raise ValueError("unknown object-record source group")
                yield source
    else:
        profile = json.loads(path.read_text())
        if set(profile) != {"input_id", "bundles"} or profile["input_id"] != M.INPUT_ID:
            raise ValueError("unknown object-record input")
        yield from profile["bundles"]


def produce(profile_path, profile_sha256, pc, output):
    if B.sha(profile_path) != profile_sha256:
        raise ValueError("object-record profile drift")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("object-record output must be new and outside original input")
    expected = sum(
        target["bytes"] for bundle in profile_bundles(profile_path) for member in bundle["members"] for clip in member["objects"] for target in clip["outputs"]
    )
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient object-record output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": M.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0}
    try:
        with (output / "objects.bin").open("xb") as data, (output / "index.jsonl").open("x") as index:
            for source in profile_bundles(profile_path):
                path = M.safe_input(pc, source["path"])
                before = path.stat()
                if B.sha(path) != source["sha256"]:
                    raise ValueError("original object-record bundle drift")
                bundle = B.Bundle(path)
                for selected_member in source["members"]:
                    member = bundle.member(selected_member["name"])
                    metadata = W.read_serialized(member)
                    objects = {row["path_id"]: row for row in metadata["objects"]}
                    trees = {}
                    for selected in selected_member["objects"]:
                        obj = objects[selected["path_id"]]
                        typ = metadata["types"][obj["type_id"]]
                        if typ["class_id"] != selected["class_id"] or selected["class_id"] not in (
                            1,
                            4,
                            21,
                            23,
                            33,
                            64,
                            65,
                            74,
                            91,
                            104,
                            108,
                            114,
                            135,
                            136,
                            137,
                            198,
                            199,
                            205,
                            215,
                            222,
                            223,
                            224,
                            225,
                        ):
                            raise ValueError("unqualified original object class")
                        member.seek(metadata["data_offset"] + obj["offset"])
                        body = B.exact(member, obj["bytes"])
                        if hashlib.sha256(body).hexdigest() != selected["sha256"]:
                            raise ValueError("original object-record body drift")
                        root = None
                        if typ["class_id"] in (74, 91):
                            if obj["type_id"] not in trees:
                                trees[obj["type_id"]] = SCHEMA.type_tree(io.BytesIO(typ["tree"]))
                            root = trees[obj["type_id"]]
                        for target in selected["outputs"]:
                            operations = target.get("transform", {})
                            if typ["class_id"] == 74:
                                result = transform(body, root, operations)
                            else:
                                result = transform_generic(body, typ["class_id"], operations, root)
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
        if B.sha(profile_path) != profile_sha256:
            raise ValueError("object-record profile changed during production")
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
