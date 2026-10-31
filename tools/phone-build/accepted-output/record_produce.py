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


def merged_stream(data, aliases):
    """Recover original tangents, then pack the merged source key sequence.

    The caller admits aliases only after comparing complete original binding,
    channel and delta data. Finite keys remain present, including tied times.
    """
    length = struct.unpack_from("<I", data)[0]
    if len(data) != 4 + length * 4:
        raise ValueError("invalid merged stream extent")
    words = list(struct.unpack_from("<" + "I" * length, data, 4))
    result, frames, cursor = list(words), [], 0

    def number(word):
        return struct.unpack("<f", struct.pack("<I", word))[0]

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    def word(value):
        return 0x7FC00000 if math.isnan(value) else struct.unpack("<I", struct.pack("<f", value))[0]

    while cursor < length:
        if cursor + 2 > length:
            raise ValueError("truncated merged frame")
        time_word, count = words[cursor : cursor + 2]
        cursor += 2
        if count > (length - cursor) // 5:
            raise ValueError("truncated merged keys")
        keys = []
        for _ in range(count):
            keys.append((words[cursor], cursor))
            cursor += 5
        frames.append((number(time_word), keys))
    incoming, outgoing, following = {}, {}, {}
    for frame in range(len(frames) - 2, 0, -1):
        time_value, keys = frames[frame]
        for index, position in keys:
            outgoing[position] = 0.0
            if index in following:
                next_time, next_position = following[index]
                dt = next_time - time_value
                a, b, c, value = map(number, words[position + 1 : position + 5])
                next_value = number(words[next_position + 4])
                if a != 0 or b != 0 or c != 0:
                    outgoing[position] = c
                    incoming[next_position] = f32(3 * ((a * dt) * dt) + 2 * (b * dt) + c)
                elif value != next_value:
                    outgoing[position] = incoming[next_position] = float("inf")
                else:
                    outgoing[position] = incoming[next_position] = 0.0
            following[index] = (time_value, position)
    curves = {}
    for frame in range(1, len(frames) - 1):
        time_value, keys = frames[frame]
        for index, position in keys:
            curves.setdefault(aliases.get(index, index), []).append((time_value, position))
    for keys in curves.values():
        for (time_value, position), (next_time, next_position) in zip(keys, keys[1:]):
            out_slope, in_slope = outgoing.get(position, 0.0), incoming.get(next_position, 0.0)
            if math.isinf(out_slope) or math.isinf(in_slope):
                result[position + 1 : position + 4] = [0, 0, 0]
                continue
            dx = max(f32(next_time - time_value), f32(0.0001))
            inverse = f32(1 / dx)
            square = f32(inverse * inverse)
            difference = f32(number(words[next_position + 4]) - number(words[position + 4]))
            d0, d1 = f32(out_slope * dx), f32(in_slope * dx)
            an = f32(f32(f32(d0 + d1) - difference) - difference)
            bn = f32(f32(f32(f32(difference + f32(difference + difference)) - d0) - d0) - d1)
            result[position + 1 : position + 4] = [word(f32(f32(an * square) * inverse)), word(f32(bn * square)), word(out_slope)]
    return struct.pack("<I" + "I" * length, length, *result)


def layout_clip(body, root, selected):
    """Import source groups, retaining one binding for identical channels."""
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
        or len(set(order)) != len(order)
        or any(not 0 <= i < count for i in order)
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
    aliases = {}
    for index in set(range(count)) - set(order):
        retained = next((i for i in order if entries[i] == entries[index]), None)
        if retained is None:
            raise ValueError("omitted binding has no identical original binding")
        for old, representative in zip(groups[index], groups[retained], strict=True):
            aliases[old] = representative
            inverse[old] = inverse[representative]
    cp = ("m_MuscleClip", "m_Clip", "data")
    sp, dp, kp = cp + ("m_StreamedClip",), cp + ("m_DenseClip",), cp + ("m_ConstantClip", "data")
    ns, nd = integer(sp + ("curveCount",)), integer(dp + ("m_CurveCount",))
    cs = ns + nd
    folded = {i for binding in folds for i in groups[binding]}
    if any(i >= cs for i in folded):
        raise ValueError("cannot refold existing constants")
    new_ns = ns - sum(i < ns for i in folded) - sum(i < ns for i in aliases)
    new_nd = nd - sum(ns <= i < cs for i in folded) - sum(ns <= i < cs for i in aliases)
    new_cs = new_ns + new_nd
    if (
        any(i >= ns or i in folded for i in flat[:new_ns])
        or any(not ns <= i < cs or i in folded for i in flat[new_ns:new_cs])
        or any(i < cs and i not in folded for i in flat[new_cs:])
    ):
        raise ValueError("unqualified clip bucket movement")
    words = array(sp + ("data",))
    original_words = words
    constants = array(kp)
    samples = array(dp + ("m_SampleArray",))
    vp = ("m_MuscleClip", "m_ValueArrayDelta")
    vstart, vend = spans[vp]
    if struct.unpack_from("<I", body, vstart)[0] != cursor or vend - vstart != 4 + cursor * 8:
        raise ValueError("value-delta extent differs")
    if aliases:
        signatures = {}
        position = 0
        while position < len(words):
            time_word, n = words[position : position + 2]
            position += 2
            if n > (len(words) - position) // 5:
                raise ValueError("truncated duplicate source stream")
            for _ in range(n):
                index = words[position]
                signatures.setdefault(index, []).append((time_word, *words[position + 1 : position + 5]))
                position += 5
        for old, representative in aliases.items():
            if (old < ns) != (representative < ns) or (old < cs) != (representative < cs):
                raise ValueError("duplicate binding crosses clip buckets")
            if old < ns:
                equal = signatures.get(old) == signatures.get(representative)
            elif old < cs:
                equal = samples[old - ns :: nd] == samples[representative - ns :: nd]
            else:
                equal = constants[old - cs] == constants[representative - cs]
            equal = equal and body[vstart + 4 + old * 8 : vstart + 12 + old * 8] == body[vstart + 4 + representative * 8 : vstart + 12 + representative * 8]
            if not equal:
                raise ValueError("duplicate binding has different original values")
        data = merged_stream(pack(words), aliases)
        words = list(struct.unpack_from("<" + "I" * (len(data) // 4 - 1), data, 4))
    first, frames, position = {}, [], 0
    stream_order = dict(selected.get("stream_order", []))
    frame_index = 0
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
            if i not in folded and not (frame_index == 0 and i in aliases):
                keys.append((inverse[i], *words[position + 1 : position + 5]))
            position += 5
        if keys or not math.isfinite(number(time_word)):
            keys.sort(key=lambda key: key[0])
            if frame_index in stream_order:
                permutation = stream_order.pop(frame_index)
                if sorted(permutation) != list(range(len(keys))) or any(keys[i][0] != keys[j][0] for i, j in enumerate(permutation)):
                    raise ValueError("invalid equal-curve source row permutation")
                keys = [keys[i] for i in permutation]
            frames.extend((time_word, len(keys), *(word for key in keys for word in key)))
        frame_index += 1
    if stream_order:
        raise ValueError("source frame permutation outside clip")
    old_frames = integer(dp + ("m_FrameCount",))
    if len(samples) != old_frames * nd or (nd and not old_frames):
        raise ValueError("dense sample extent differs")
    for i in folded:
        if i >= ns:
            first[i] = samples[i - ns]
    if cursor != cs + len(constants):
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
    delta_rows = []
    endpoints = None
    if selected.get("resample_stream_delta"):
        if not aliases:
            raise ValueError("stream delta resampling requires duplicate curves")
        endpoints = [number(integer(("m_MuscleClip", name))) for name in ("m_StartTime", "m_StopTime")]

    def sample_stream(index, time_value):
        latest = None
        position = 0
        while position < len(frames):
            time_word, n = frames[position : position + 2]
            position += 2
            key_time = number(time_word)
            for _ in range(n):
                key = frames[position : position + 5]
                if key[0] == index and math.isfinite(key_time) and key_time <= time_value:
                    latest = key_time, key
                position += 5
        if latest is None:
            raise ValueError("no original streamed endpoint")
        key_time, key = latest
        dx = f32(time_value - key_time)
        a, b, c, value = map(number, key[1:])
        value = f32(f32(f32(f32(f32(f32(a * dx) + b) * dx) + c) * dx) + value)
        return struct.pack("<f", value)

    for i in flat:
        if i in folded:
            row = struct.pack("<II", first[i], first[i])
        else:
            row = body[vstart + 4 + i * 8 : vstart + 12 + i * 8]
            if endpoints is not None and i < ns:
                row = b"".join(sample_stream(inverse[i], time_value) for time_value in endpoints)
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
        ((bstart, bend), struct.pack("<I", len(order)) + b"".join(entries[i] for i in order)),
        ((vstart, vend), delta),
        (spans[sp + ("curveCount",)], struct.pack("<I", new_ns)),
        (spans[dp + ("m_CurveCount",)], struct.pack("<I", new_nd)),
        (spans[dp + ("m_FrameCount",)], struct.pack("<I", new_frames)),
    ]
    if not nd and policy != "preserve":
        changes.extend([(spans[dp + ("m_SampleRate",)], struct.pack("<f", rate)), (spans[dp + ("m_BeginTime",)], bytes(4))])
    size = (
        integer(("m_MuscleClipSize",))
        + 4 * (len(frames) - len(original_words) + len(new_constants) - len(constants) + len(new_samples) - len(samples))
        + 8 * (len(flat) - cursor)
    )
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


# Adapted from FreeBSD msun s_atanf.c / e_atan2f.c, Sun's fdlibm.
# Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
# Developed at SunPro, a Sun Microsystems, Inc. business.
# Permission to use, copy, modify, and distribute this software is freely
# granted, provided that this notice is preserved.
def small_atan2f(y, x):
    """Portable fdlibm float arithmetic for the admitted positive-x yaw interval."""

    def f32(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    if not math.isfinite(x) or not math.isfinite(y) or x <= 0:
        raise ValueError("root yaw is outside the positive-x atan2f domain")
    value = f32(y / x)
    if abs(value) >= 0.4375:
        raise ValueError("root yaw is outside the small atan2f interval")
    if abs(value) < 2**-12:
        return value
    coefficients = [f32(v) for v in (3.3333328366e-01, -1.9999158382e-01, 1.4253635705e-01, -1.0648017377e-01, 6.1687607318e-02)]
    z = f32(value * value)
    w = f32(z * z)
    odd = f32(z * f32(coefficients[0] + f32(w * f32(coefficients[2] + f32(w * coefficients[4])))))
    even = f32(w * f32(coefficients[1] + f32(w * coefficients[3])))
    return f32(value - f32(value * f32(odd + even)))


def root_average(body, root, use_atan2=False, use_small_atan2f=False):
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
            if use_small_atan2f:
                phase = small_atan2f(delta_rotation[1], delta_rotation[3])
            elif use_atan2:
                phase = f32(math.atan2(delta_rotation[1], delta_rotation[3]))
            else:
                phase = f32(math.atan(f32(delta_rotation[1] / delta_rotation[3])))
            angle = f32(f32(2 * phase) / step)
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
        "material_path_bindings",
        "native_stream",
        "layout",
        "normalize_root_quaternions",
        "root_average",
        "root_average_atan2",
        "root_average_small_atan2f",
    }:
        raise ValueError("unknown AnimationClip operation")
    canonical = selected.get("canonical")
    if canonical not in (None, "zero-and-nan", "nan"):
        raise ValueError("unknown AnimationClip canonical policy")
    if "root_average_atan2" in selected and (selected["root_average_atan2"] is not True or selected.get("root_average") is not True):
        raise ValueError("atan2 projection requires source root-average integration")
    if "root_average_small_atan2f" in selected and (
        selected["root_average_small_atan2f"] is not True or selected.get("root_average") is not True or selected.get("root_average_atan2")
    ):
        raise ValueError("small atan2f requires its own source root-average projection")
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
    for index in selected.get("material_path_bindings", []):
        path = ("m_ClipBindingConstant", "genericBindings", "Array", str(index))
        if type(index) is not int or index < 0 or path + ("attribute",) not in spans:
            raise ValueError("invalid material path binding")
        # AssetRipper's unknown-path RendererMaterial fallback exports
        # material.PATH. Its imported property ID therefore comes from the
        # original path CRC rather than the original material property CRC.
        offset = spans[path + ("attribute",)][0]
        source_path = struct.unpack_from("<I", result, spans[path + ("path",)][0])[0]
        struct.pack_into("<I", result, offset, (source_path & 0x0FFFFFFF) | 0x80000000)
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
    return (
        root_average(result, root, use_atan2=selected.get("root_average_atan2", False), use_small_atan2f=selected.get("root_average_small_atan2f", False))
        if selected.get("root_average")
        else result
    )


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


def exported_clip_tos(value, collision_index=None):
    """Rebuild the qualified export path from an original clip-path TOS entry."""
    if not value.startswith("Assets/"):
        raise ValueError("not an original clip asset path")
    match = re.search(r"\.(fbx|anim)", value, re.I)
    if not match or not (clip_name := value[match.end() :]):
        raise ValueError("missing original clip name")
    name = clip_name.replace("(Clone)", "").replace("(Instance)", "").strip()
    name = re.sub(r"[/:,\[\]\x00-\x1f]", "_", name)
    if collision_index is not None:
        if type(collision_index) is not int or not 0 <= collision_index < 2**31 - 1:
            raise ValueError("invalid original export filename collision index")
        name += f"_{collision_index}"
    if not name or len((name + ".anim").encode()) > 240:
        raise ValueError("unqualified export filename")
    directory = value[: match.start()].rsplit("/", 1)[0]
    return "Assets/WholeGame" + directory[len("Assets") :] + "/" + name + ".anim" + clip_name


def controller_tos(body, root, selection):
    _, spans = fields(body, root)
    start, end = spans[("m_TOS",)]
    count = struct.unpack_from("<I", body, start)[0]
    if any(len(row) not in (2, 3) for row in selection):
        raise ValueError("invalid original controller TOS selection")
    if len({row[0] for row in selection}) != len(selection) or any(
        type(row[0]) is not int
        or not 0 <= row[0] < count
        or type(row[1]) is not bool
        or len(row) == 3
        and (not row[1] or type(row[2]) is not int or not 0 <= row[2] < 2**31 - 1)
        for row in selection
    ):
        raise ValueError("invalid original controller TOS selection")
    rows = []
    for selected in selection:
        index, rebuild = selected[:2]
        collision_index = selected[2] if len(selected) == 3 else None
        a, b = spans[("m_TOS", "Array", str(index))]
        raw = body[a:b]
        key, size = struct.unpack_from("<II", raw)
        value = raw[8 : 8 + size].decode("utf-8")
        if zlib.crc32(value.encode()) != key:
            raise ValueError("original TOS CRC drift")
        if rebuild:
            encoded = exported_clip_tos(value, collision_index).encode("utf-8")
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


def controller_behaviour_ranges(body, root, order):
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
        if b - a != 4 or d - c != 4:
            raise ValueError("invalid behaviour range extent")
        old = struct.unpack_from("<I", body, a)[0]
        size = struct.unpack_from("<I", body, c)[0]
        if old + size > n:
            raise ValueError("behaviour range outside source indices")
        mapped = [inverse[i] for i in range(old, old + size)]
        if mapped and mapped != list(range(mapped[0], mapped[0] + size)):
            raise ValueError("noncontiguous behaviour range")
        seen.extend(range(old, old + size))
        if mapped:
            struct.pack_into("<I", out, a, mapped[0])
    if sorted(seen) != list(range(n)):
        raise ValueError("incomplete source behaviour ranges")
    return bytes(out)


def controller_loop_states(body, root, states, read_clip):
    """Compile selected original states' loop flag from their original clip leaves."""
    if read_clip is None:
        raise ValueError("controller loop policy requires original clip reader")
    _, spans = fields(body, root)
    result = bytearray(body)
    clip_start = spans[("m_AnimationClips",)][0] + 4
    clip_count = struct.unpack_from("<I", body, clip_start - 4)[0]
    seen = set()
    for selected in states:
        machine, state = selected["state"]
        if type(machine) is not int or type(state) is not int or min(machine, state) < 0 or (machine, state) in seen:
            raise ValueError("invalid controller loop state selection")
        seen.add((machine, state))
        prefix = ("m_Controller", "m_StateMachineArray", "Array", str(machine), "data", "m_StateConstantArray", "Array", str(state), "data")
        leaves = set()
        for path, (offset, _) in spans.items():
            if path[: len(prefix)] != prefix or path[-1] != "m_ClipID":
                continue
            children = spans[path[:-1] + ("m_ChildIndices",)][0]
            if struct.unpack_from("<I", body, children)[0]:
                continue
            index = struct.unpack_from("<I", body, offset)[0]
            if index == 0xFFFFFFFF:
                continue
            if index >= clip_count:
                raise ValueError("controller loop leaf outside original clips")
            leaves.add(index)
        clips = selected["clips"]
        if not leaves or any(type(row["index"]) is not int for row in clips) or sorted(row["index"] for row in clips) != sorted(leaves):
            raise ValueError("controller loop dependency does not match original leaves")
        flags = [read_clip(row, struct.unpack_from("<iq", body, clip_start + row["index"] * 12)) for row in clips]
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("invalid original clip loop flag")
        offset, end = spans[prefix + ("m_Loop",)]
        if end - offset != 1 or body[offset] not in (0, 1):
            raise ValueError("invalid original state loop extent")
        result[offset] = all(flags)
    return bytes(result)


def controller_state_order(body, root, selections):
    """Relocate original state records and their checked local index references."""
    _, spans = fields(body, root)
    result, changes = bytearray(body), []
    machines = ("m_Controller", "m_StateMachineArray", "Array")
    count = struct.unpack_from("<I", body, spans[machines][0])[0]
    for machine, order in selections.items():
        if not isinstance(machine, str) or not machine.isdecimal() or str(int(machine)) != machine or not 0 <= int(machine) < count:
            raise ValueError("invalid original controller state machine")
        prefix = machines + (machine, "data")
        array = prefix + ("m_StateConstantArray", "Array")
        start, end = spans[array]
        states = struct.unpack_from("<I", body, start)[0]
        if not isinstance(order, list) or any(type(index) is not int for index in order) or sorted(order) != list(range(states)):
            raise ValueError("controller state order must be an original-state bijection")
        inverse = {old: new for new, old in enumerate(order)}
        for path, (offset, finish) in spans.items():
            if path[: len(prefix)] != prefix or path[-1] not in ("m_DefaultState", "m_DestinationState", "m_Destination"):
                continue
            if finish - offset != 4:
                raise ValueError("original controller state index extent drift")
            value = struct.unpack_from("<I", result, offset)[0]
            # High values select entry/exit state machines or unavailable states;
            # only local state indices move with the original state array.
            if value in inverse:
                struct.pack_into("<I", result, offset, inverse[value])
        ranges = [spans[array + (str(index),)] for index in range(states)]
        chunks = b"".join(result[ranges[index][0] : ranges[index][1]] for index in order)
        changes.append((start, end, struct.pack("<I", states) + chunks))
    for start, end, replacement in sorted(changes, reverse=True):
        result[start:end] = replacement
    return bytes(result)


def controller_clear_null_motion(body, root):
    """Import a single original unavailable clip leaf as a null state motion."""
    _, spans = fields(body, root)
    result, removals, memory = bytearray(body), [], 0
    for path, (start, end) in spans.items():
        if len(path) != 11 or path[:3] != ("m_Controller", "m_StateMachineArray", "Array") or path[-2:] != ("m_BlendTreeConstantArray", "Array"):
            continue
        if struct.unpack_from("<I", body, start)[0] != 1:
            continue
        nodes = path + ("0", "data", "m_NodeArray", "Array")
        if struct.unpack_from("<I", body, spans[nodes][0])[0] != 1:
            continue
        leaf = nodes + ("0", "data")
        clip, children = spans[leaf + ("m_ClipID",)][0], spans[leaf + ("m_ChildIndices",)][0]
        if struct.unpack_from("<I", body, clip)[0] != 0xFFFFFFFF or struct.unpack_from("<I", body, children)[0]:
            continue
        arrays = [p for p in spans if p[: len(path)] == path and p != path and p[-1] == "Array"]
        if any(struct.unpack_from("<I", body, spans[p][0])[0] for p in arrays if p != nodes):
            raise ValueError("original null-motion leaf contains unsupported array data")
        # Native inline arrays use 16-byte headers; the release serialization
        # stores their 4-byte counts. The outer state array header is retained.
        memory += end - start - 4 + 12 * len(arrays)
        removals.append((start, end))
        left, right = spans[path[:-2] + ("m_BlendTreeConstantIndexArray",)]
        count = struct.unpack_from("<I", body, left)[0]
        if right - left != 4 + count * 4:
            raise ValueError("original null-motion index extent drift")
        for index in range(count):
            offset = left + 4 + index * 4
            if struct.unpack_from("<I", body, offset)[0] not in (0, 0xFFFFFFFF):
                raise ValueError("original null-motion index does not select its sole tree")
            struct.pack_into("<I", result, offset, 0xFFFFFFFF)
    offset = spans[("m_ControllerSize",)][0]
    size = struct.unpack_from("<I", body, offset)[0]
    if size < memory:
        raise ValueError("original null-motion allocation size drift")
    struct.pack_into("<I", result, offset, size - memory)
    for start, end in sorted(removals, reverse=True):
        result[start:end] = bytes(4)
    return bytes(result)


def controller_omit_synced_behaviours(body, root):
    """The exporter leaves synced layers' behaviour overrides uninitialized."""
    _, spans = fields(body, root)
    layers = ("m_Controller", "m_LayerArray", "Array")
    synced = {
        int(path[3])
        for path, (offset, _) in spans.items()
        if path[:3] == layers and path[-1] == "m_StateMachineSynchronizedLayerIndex" and struct.unpack_from("<I", body, offset)[0]
    }
    if not synced:
        return body
    prefix = ("m_StateMachineBehaviourVectorDescription",)
    ranges = prefix + ("m_StateMachineBehaviourRanges", "Array")
    start, end = spans[ranges]
    count = struct.unpack_from("<I", body, start)[0]
    kept, indices = [], []
    for index in range(count):
        entry = ranges + (str(index),)
        values = {path[-1]: (path, struct.unpack_from("<I", body, a)[0]) for path, (a, b) in spans.items() if path[:4] == entry and b - a == 4}
        if values["m_LayerIndex"][1] in synced:
            continue
        a, b = spans[entry]
        raw = bytearray(body[a:b])
        path, old = values["m_StartIndex"]
        size = values["m_Count"][1]
        indices.extend(range(old, old + size))
        kept.append((raw, spans[path][0] - a, old))
    indices.sort()
    positions = {old: new for new, old in enumerate(indices)}
    for raw, offset, old in kept:
        struct.pack_into("<I", raw, offset, positions[old])
    ia, ib = spans[prefix + ("m_StateMachineBehaviourIndices",)]
    n = struct.unpack_from("<I", body, ia)[0]
    source_indices = struct.unpack_from("<" + "I" * n, body, ia + 4)
    selected = sorted({source_indices[i] for i in indices})
    inverse = {old: new for new, old in enumerate(selected)}
    pa, pb = spans[("m_StateMachineBehaviours",)]
    pointers = [body[pa + 4 + i * 12 : pa + 16 + i * 12] for i in selected]
    changes = [
        (start, end, struct.pack("<I", len(kept)) + b"".join(raw for raw, _, _ in kept)),
        (ia, ib, struct.pack("<I", len(indices)) + b"".join(struct.pack("<I", inverse[source_indices[i]]) for i in indices)),
        (pa, pb, struct.pack("<I", len(pointers)) + b"".join(pointers)),
    ]
    result = bytearray(body)
    for a, b, replacement in sorted(changes, reverse=True):
        result[a:b] = replacement
    return bytes(result)


def controller_tree_allocation(body, spans, tree):
    """Count the editor's 64-bit debug-pointer controller blob allocations."""
    cursor = 0

    def allocate(size, alignment=8):
        nonlocal cursor
        cursor = (cursor + alignment - 1) & -alignment
        cursor += size

    def count(path):
        return struct.unpack_from("<I", body, spans[path][0])[0]

    def payload(path, stride=4, alignment=4):
        size = count(path)
        if size:
            allocate(size * stride, alignment)
        return size

    nodes = tree + ("data", "m_NodeArray", "Array")
    # OffsetPtr tree slot, tree header and the array of node pointer slots.
    allocate(16)
    allocate(24)
    allocate(16 * count(nodes))
    for index in range(count(nodes)):
        node = nodes + (str(index), "data")
        allocate(96)
        payload(node + ("m_ChildIndices", "Array"))
        thresholds = node + ("m_Blend1dData", "data", "m_ChildThresholdArray", "Array")
        if count(thresholds):
            allocate(24)
            payload(thresholds)
        blend = node + ("m_Blend2dData", "data")
        arrays = [
            blend + (name, "Array")
            for name in (
                "m_ChildPositionArray",
                "m_ChildMagnitudeArray",
                "m_ChildPairVectorArray",
                "m_ChildPairAvgMagInvArray",
                "m_ChildNeighborListArray",
            )
        ]
        if any(count(path) for path in arrays):
            allocate(120)
            for path, stride in zip(arrays[:4], (8, 4, 8, 4)):
                payload(path, stride)
            neighbors = payload(arrays[4], 24, 8)
            for neighbor in range(neighbors):
                payload(arrays[4] + (str(neighbor), "m_NeighborArray", "Array"))
        direct = node + ("m_BlendDirectData", "data", "m_ChildBlendEventIDArray", "Array")
        if count(direct):
            raise ValueError("unsupported synced override direct blend data")
    return cursor


def controller_omit_synced_overrides(body, root):
    """Retain the pinned exporter's first motion tree and its clip occurrences."""
    _, spans = fields(body, root)
    result, changes, removed_clips, memory = bytearray(body), [], [], 0
    for path, (start, end) in spans.items():
        if len(path) != 11 or path[:3] != ("m_Controller", "m_StateMachineArray", "Array") or path[-2:] != ("m_BlendTreeConstantArray", "Array"):
            continue
        count = struct.unpack_from("<I", body, start)[0]
        # StateConstantExtensions.GetBlendTree exports tree zero regardless of
        # its original synchronized slot. Reimport makes it the base motion.
        left, right = spans[path[:-2] + ("m_BlendTreeConstantIndexArray",)]
        for offset in range(left + 4, right, 4):
            struct.pack_into("<I", result, offset, 0 if count and offset == left + 4 else 0xFFFFFFFF)
        if count <= 1:
            continue
        first_end = spans[path + ("0",)][1]
        for index in range(1, count):
            tree = path + (str(index),)
            left, right = spans[tree]
            memory += controller_tree_allocation(body, spans, tree)
            for p, (offset, _) in spans.items():
                if p[: len(tree)] != tree or p[-1] != "m_ClipID":
                    continue
                children = spans[p[:-1] + ("m_ChildIndices",)][0]
                clip = struct.unpack_from("<I", body, offset)[0]
                if not struct.unpack_from("<I", body, children)[0] and clip != 0xFFFFFFFF:
                    removed_clips.append(clip)
        changes.append((start, end, struct.pack("<I", 1) + body[start + 4 : first_end]))
    start, end = spans[("m_AnimationClips",)]
    count = struct.unpack_from("<I", body, start)[0]
    clips = [body[start + 4 + i * 12 : start + 16 + i * 12] for i in range(count)]
    retained = list(range(count))
    # Exported clips contain one occurrence per motion. A synced override may
    # share a clip with a retained motion; remove the final matching occurrence.
    for clip in removed_clips:
        match = next(i for i in reversed(retained) if clips[i] == clips[clip])
        retained.remove(match)
    inverse = {old: new for new, old in enumerate(retained)}
    removed_ranges = [(a + len(replacement), b) for a, b, replacement in changes]
    for path, (offset, _) in spans.items():
        if path[0] != "m_Controller" or path[-1] != "m_ClipID" or any(a <= offset < b for a, b in removed_ranges):
            continue
        if struct.unpack_from("<I", body, spans[path[:-1] + ("m_ChildIndices",)][0])[0]:
            continue
        old = struct.unpack_from("<I", body, offset)[0]
        if old != 0xFFFFFFFF:
            representative = next(i for i in retained if clips[i] == clips[old])
            struct.pack_into("<I", result, offset, inverse[representative])
    # Copy retained trees after updating their leaf indices.
    changes = [(a, b, replacement[:4] + result[a + 4 : a + len(replacement)]) for a, b, replacement in changes]
    changes.append((start, end, struct.pack("<I", len(retained)) + b"".join(clips[i] for i in retained)))
    offset = spans[("m_ControllerSize",)][0]
    size = struct.unpack_from("<I", body, offset)[0]
    struct.pack_into("<I", result, offset, size - memory)
    for start, end, replacement in sorted(changes, reverse=True):
        result[start:end] = replacement
    return controller_omit_synced_behaviours(bytes(result), root)


def controller_resolve_synced_layers(body, root):
    """Resolve the exporter's machine-index-as-layer-index synchronized links."""
    _, spans = fields(body, root)
    result, changes, allocation = bytearray(body), [], 0
    layers = ("m_Controller", "m_LayerArray", "Array")
    machines = ("m_Controller", "m_StateMachineArray", "Array")

    def read(path):
        return struct.unpack_from("<I", body, spans[path][0])[0]

    def write(path, value):
        struct.pack_into("<I", result, spans[path][0], value)

    count = read(layers)
    links = [read(layers + (str(i), "data", "m_StateMachineIndex")) for i in range(count)]
    synced = [read(layers + (str(i), "data", "m_StateMachineSynchronizedLayerIndex")) != 0 for i in range(count)]
    groups = {}
    for layer in range(count):
        base, seen = layer, set()
        while synced[base]:
            if base in seen or links[base] >= count:
                raise ValueError("invalid exported synchronized layer chain")
            seen.add(base)
            base = links[base]
        machine = links[base]
        group = groups.setdefault(machine, [])
        write(layers + (str(layer), "data", "m_StateMachineIndex"), machine)
        write(layers + (str(layer), "data", "m_StateMachineSynchronizedLayerIndex"), len(group))
        group.append(layer)
    for machine, group in groups.items():
        prefix = machines + (str(machine), "data")
        slots = len(group)
        write(prefix + ("m_SynchronizedLayerCount",), slots)
        states = prefix + ("m_StateConstantArray", "Array")
        for state in range(read(states)):
            path = states + (str(state), "data", "m_BlendTreeConstantIndexArray")
            left, right = spans[path]
            old = read(path)
            indices = list(struct.unpack_from("<" + "I" * old, body, left + 4))
            # Run after synced override omission: only the base motion remains.
            if not indices or any(index != 0xFFFFFFFF for index in indices[1:]):
                raise ValueError("synchronized layer resolution requires omitted motion overrides")
            replacement = struct.pack("<I", slots) + struct.pack("<I", indices[0]) + struct.pack("<I", 0xFFFFFFFF) * (slots - 1)
            changes.append((left, right, replacement))
            # Exact editor BlobWrite starts this payload at an 8-byte boundary.
            # Transition pointer blocks/bodies round to 8; condition bodies are
            # 16 bytes. uint slots use 4 bytes; the next allocation aligns to 8.
            allocation += ((4 * slots + 7) & ~7) - ((4 * old + 7) & ~7)
    size = ("m_ControllerSize",)
    write(size, read(size) + allocation)
    for left, right, replacement in sorted(changes, reverse=True):
        result[left:right] = replacement
    return bytes(result)


def controller_clear_skeleton_masks(body, root):
    """Apply the pinned exporter's omitted layer masks and native allocation size."""
    _, spans = fields(body, root)
    removals, memory = [], 0
    for path, (start, end) in spans.items():
        if len(path) != 9 or path[:3] != ("m_Controller", "m_LayerArray", "Array") or path[4:] != ("data", "m_SkeletonMask", "data", "m_Data", "Array"):
            continue
        count = struct.unpack_from("<I", body, start)[0]
        if end - start != 4 + count * 8:
            raise ValueError("original controller skeleton mask extent drift")
        if count:
            removals.append((start, end))
            # Each native mask entry occupies 8 bytes, with a 24-byte allocation
            # header for a nonempty array on the admitted 64-bit platforms.
            memory += count * 8 + 24
    offset, end = spans[("m_ControllerSize",)]
    size = struct.unpack_from("<I", body, offset)[0]
    if end - offset != 4 or size < memory:
        raise ValueError("original controller allocation size drift")
    result = bytearray(body)
    struct.pack_into("<I", result, offset, size - memory)
    for start, end in sorted(removals, reverse=True):
        result[start:end] = bytes(4)
    return bytes(result)


def director_exposed_names(body, root):
    """Reimport AssetRipper decimal PropertyName strings and retain their PPtrs."""
    _, located = fields(body, root)
    prefix = ("m_ExposedReferences", "m_References", "Array")
    start, end = located[prefix]
    count = struct.unpack_from("<I", body, start)[0]
    entries = []
    for index in range(count):
        left, right = located[prefix + (str(index),)]
        length = struct.unpack_from("<I", body, left)[0]
        text = body[left + 4 : left + 4 + length].decode("utf-8")
        value = int(text)
        if str(value) != text or not -(2**31) <= value < 2**31:
            raise ValueError("original PropertyName is not an exported signed integer")
        pointer = (left + 4 + length + 3) // 4 * 4
        if pointer + 12 != right:
            raise ValueError("invalid original exposed-reference entry")
        hashed = zlib.crc32(text.encode("utf-8"))
        signed = hashed if hashed < 2**31 else hashed - 2**32
        encoded = str(signed).encode("utf-8")
        key = struct.pack("<I", len(encoded)) + encoded
        entries.append((signed, key + bytes(-len(key) % 4) + body[pointer:right]))
    return body[:start] + struct.pack("<I", count) + b"".join(row for _, row in sorted(entries, key=lambda row: row[0])) + body[end:]


def control_exposed_name_default(body, root):
    """Import the managed YAML PropertyName mapping as the native default.

    The exact-editor authored scalar/mapping fixture establishes this import
    behavior independently of accepted game records. Other fields stay original.
    """
    _, located = fields(body, root)
    start, end = located[("sourceGameObject", "exposedName")]
    length = struct.unpack_from("<I", body, start)[0]
    text = body[start + 4 : start + 4 + length].decode("utf-8")
    value = int(text)
    if str(value) != text or not -(2**31) <= value < 2**31 or end != (start + 4 + length + 3) // 4 * 4:
        raise ValueError("original PropertyName is not an exported signed integer")
    result = body[:start] + struct.pack("<I", 1) + b"0\0\0\0" + body[end:]
    fields(result, root)
    return result


def director_unbound_tracks(body, root, selected):
    """Add explicit imported track relationships with native null bindings.

    The profile supplies only destination PPtrs and their binding positions.
    Original bindings and all other Director state remain source-owned.
    """
    _, located = fields(body, root)
    prefix = ("m_SceneBindings", "Array")
    start, end = located[prefix]
    count = struct.unpack_from("<I", body, start)[0]
    entries = []
    keys = set()
    for index in range(count):
        left, right = located[prefix + (str(index),)]
        if right - left != 24 or located[prefix + (str(index), "key")] != (left, left + 12) or located[prefix + (str(index), "value")] != (left + 12, right):
            raise ValueError("original Director binding schema differs")
        entries.append(body[left:right])
        keys.add(struct.unpack_from("<iq", body, left))
    previous = -1
    for row in selected:
        if set(row) != {"index", "key"}:
            raise ValueError("unbound track requires only position and PPtr")
        index, key = row["index"], tuple(row["key"])
        if type(index) is not int or not previous < index <= len(entries) or len(key) != 2 or any(type(value) is not int for value in key):
            raise ValueError("invalid imported Director track relationship")
        if key[0] < 0 or not key[1] or key in keys:
            raise ValueError("imported Director track must be distinct and nonnull")
        entries.insert(index, struct.pack("<iqiq", *key, 0, 0))
        keys.add(key)
        previous = index
    result = body[:start] + struct.pack("<I", len(entries)) + b"".join(entries) + body[end:]
    fields(result, root)
    return result


def expanding_wave_scale(body, root, selected, read_record):
    """Project the source callback's endpoint distance, retaining other native fields."""

    def record(name, class_id):
        selector, raw, typ = read_record(selected[name])
        if typ["class_id"] != class_id:
            raise ValueError("expanding wave source class differs")
        schema = SCHEMA.type_tree(io.BytesIO(typ["tree"]))
        spans = fields(raw, schema)[1]
        spans = {
            tuple({"#299": "m_Curve", "#374": "m_GameObject", "#490": "m_Script"}.get(part, part) for part in path): extent for path, extent in spans.items()
        }
        return selector, raw, spans

    def value(raw, locations, path, fmt):
        start, end = locations[tuple(path.split("/"))]
        if end - start != struct.calcsize(fmt):
            raise ValueError("expanding wave field extent differs")
        values = struct.unpack_from(fmt, raw, start)
        return values[0] if len(values) == 1 else values

    def ptr(raw, locations, path):
        return value(raw, locations, path, "<iq")

    def pointers(raw, locations, name):
        start, end = locations[(name, "Array")]
        count = struct.unpack_from("<I", raw, start)[0]
        if end - start != 4 + 12 * count:
            raise ValueError("expanding wave pointer array extent differs")
        return [struct.unpack_from("<iq", raw, start + 4 + 12 * index) for index in range(count)]

    own = {tuple("m_GameObject" if part == "#374" else part for part in path): extent for path, extent in fields(body, root)[1].items()}
    callback, cb, cf = record("callback", 114)
    script, sb, _ = record("script", 115)
    base, bb, bf = record("base", 4)
    parent, pb, pf = record("parent", 4)
    names = O.script_fields(sb)[1]
    if names[:2] not in (("ExpandingWaveProjectile", "RoR2.Projectile"), ("ExpandingWaveProjectileGhostController", "RoR2.Projectile")):
        raise ValueError("expanding wave callback script differs")
    if ptr(cb, cf, "m_Script") != (1, script["path_id"]) or ptr(cb, cf, "m_GameObject") != ptr(bb, bf, "m_GameObject"):
        raise ValueError("expanding wave callback ownership differs")
    ghost = names[0].endswith("GhostController")
    if ptr(cb, cf, "root" if ghost else "hitBoxParent") != (0, parent["path_id"]):
        raise ValueError("expanding wave parent relationship differs")
    if ptr(pb, pf, "m_Father") != (0, base["path_id"]) or ptr(body, own, "m_Father") != (0, parent["path_id"]):
        raise ValueError("expanding wave hierarchy differs")
    if (0, selected["source_transform"]) not in pointers(pb, pf, "m_Children"):
        raise ValueError("expanding wave reciprocal child missing")
    owner = ptr(body, own, "m_GameObject")
    if ghost:
        admitted = owner in pointers(cb, cf, "ghostSegments")
    else:
        group, gb, gf = record("group", 114)
        hitbox, hb, hf = record("hitbox", 114)
        admitted = (
            ptr(gb, gf, "m_GameObject") == ptr(cb, cf, "m_GameObject")
            and (0, hitbox["path_id"]) in pointers(gb, gf, "hitBoxes")
            and ptr(hb, hf, "m_GameObject") == owner
        )
    if not admitted:
        raise ValueError("expanding wave segment membership differs")
    if ptr(bb, bf, "m_Father") != (0, 0):
        raise ValueError("expanding wave base must be a prefab root")
    for axis, expected in zip("xyzw", (0, 0, 0, 1)):
        if value(bb, bf, "m_LocalRotation/" + axis, "<f") != expected:
            raise ValueError("expanding wave base rotation differs")
    for axis in "xyz":
        if value(bb, bf, "m_LocalScale/" + axis, "<f") != 1:
            raise ValueError("expanding wave base scale differs")
    keys = sorted(int(path[3]) for path in cf if path[:3] == ("sizeCurve", "m_Curve", "Array") and len(path) == 4 and path[3].isdigit())
    endpoint = "sizeCurve/m_Curve/Array/" + str(keys[-1])
    if value(cb, cf, endpoint + "/time", "<f") != 1:
        raise ValueError("expanding wave curve endpoint differs")
    f32 = lambda number: struct.unpack("<f", struct.pack("<f", number))[0]
    radius = f32(value(cb, cf, "radius", "<f") * value(cb, cf, endpoint + "/value", "<f"))
    segments = value(cb, cf, "segments", "<i")
    angle = f32(f32(f32(math.pi) * 2) * f32(1 / segments))
    position = [value(bb, bf, "m_LocalPosition/" + axis, "<f") for axis in "xyz"]
    first = [f32(position[0] + radius), position[1], position[2]]
    second = [f32(position[0] + f32(f32(math.cos(angle)) * radius)), position[1], f32(position[2] + f32(f32(math.sin(angle)) * radius))]
    delta = [f32(a - b) for a, b in zip(first, second)]
    distance = f32(math.sqrt(f32(f32(f32(delta[0] * delta[0]) + f32(delta[1] * delta[1])) + f32(delta[2] * delta[2]))))
    for axis, source_axis in (("y", "y"), ("z", "x")):
        if value(body, own, "m_LocalScale/" + axis, "<f") != value(cb, cf, "hurtboxSize/" + source_axis, "<f"):
            raise ValueError("expanding wave retained scale differs")
    result = bytearray(body)
    struct.pack_into("<f", result, own[("m_LocalScale", "x")][0], distance)
    return bytes(result)


def transform_generic(body, class_id, selected, root=None, read_clip=None, source_type=None, material_keywords=None, read_record=None):
    if set(selected) - {
        "references",
        "demote_keywords",
        "keyword_policy",
        "strip_compute_programs",
        "director_exposed_names",
        "control_exposed_name_default",
        "director_unbound_tracks",
        "controller_clip_order",
        "controller_loop_states",
        "controller_tos",
        "controller_opposed_angles",
        "controller_behaviour_order",
        "controller_clear_skeleton_masks",
        "controller_state_order",
        "controller_clear_null_motion",
        "controller_omit_synced_overrides",
        "controller_resolve_synced_layers",
        "canonical",
        "importer_guid",
        "crop_rectangle_offset",
        "normalize_exported_prefab_name",
        "append_components",
        "remove_components",
        "inactive_scene_object",
        "empty_mesh_renderer",
        "expanding_wave_scale",
    } or (selected.get("demote_keywords") and class_id != 21):
        raise ValueError("unknown generic object operation")
    if "expanding_wave_scale" in selected:
        if class_id != 4 or root is None or read_record is None:
            raise ValueError("expanding wave projection requires original Transform and callback reader")
        body = expanding_wave_scale(body, root, selected["expanding_wave_scale"], read_record)
    if "remove_components" in selected:
        if class_id != 1:
            raise ValueError("component omissions require original GameObject")
        body = O.remove_components(body, selected["remove_components"])
    if "normalize_exported_prefab_name" in selected:
        if class_id != 1 or selected["normalize_exported_prefab_name"] is not True:
            raise ValueError("prefab filename projection requires original GameObject")
        body = O.normalize_exported_prefab_name(body)
    if "append_components" in selected:
        if class_id != 1:
            raise ValueError("component append requires original GameObject")
        body = O.append_components(body, selected["append_components"])
    if "inactive_scene_object" in selected:
        if class_id != 1:
            raise ValueError("activation policy requires original GameObject")
        body = O.deactivate_named_gameobject(body, selected["inactive_scene_object"])
    if "empty_mesh_renderer" in selected:
        if class_id != 23 or selected["empty_mesh_renderer"] is not True or source_type is None:
            raise ValueError("empty renderer projection requires original MeshRenderer schema")
        body = O.empty_mesh_renderer(body, source_type["tree"])
    if "keyword_policy" in selected:
        if class_id != 21 or selected["keyword_policy"] not in ("dummy-shader-demote-valid", "dummy-shader-sort-invalid", "sdk-fallback-sort-invalid"):
            raise ValueError("keyword policy requires original Material and named shader import")
        if selected["keyword_policy"] == "sdk-fallback-sort-invalid" and material_keywords is None:
            raise ValueError("fallback keyword policy requires checked SDK declarations")
    if "strip_compute_programs" in selected:
        if selected["strip_compute_programs"] is not True or class_id != 72 or source_type is None:
            raise ValueError("compute projection requires original ComputeShader schema")
        body = O.strip_compute_programs(body, source_type)
    if any(key.startswith("controller_") or key == "canonical" for key in selected) and (class_id != 91 or root is None):
        raise ValueError("controller operations require original controller schema")
    if "director_exposed_names" in selected:
        if selected["director_exposed_names"] is not True or class_id != 320 or root is None:
            raise ValueError("exposed-name import requires original PlayableDirector schema")
        body = director_exposed_names(body, root)
    if "control_exposed_name_default" in selected:
        if selected["control_exposed_name_default"] is not True or class_id != 114 or root is None:
            raise ValueError("control exposed-name import requires original MonoBehaviour schema")
        body = control_exposed_name_default(body, root)
    if "controller_clear_skeleton_masks" in selected:
        if selected["controller_clear_skeleton_masks"] is not True:
            raise ValueError("unqualified controller skeleton mask policy")
        body = controller_clear_skeleton_masks(body, root)
    if "controller_state_order" in selected:
        body = controller_state_order(body, root, selected["controller_state_order"])
    if "controller_clear_null_motion" in selected:
        if selected["controller_clear_null_motion"] is not True:
            raise ValueError("unqualified controller null-motion policy")
        body = controller_clear_null_motion(body, root)
    if "controller_omit_synced_overrides" in selected:
        if selected["controller_omit_synced_overrides"] is not True:
            raise ValueError("unqualified controller synced-motion policy")
        body = controller_omit_synced_overrides(body, root)
    if "controller_resolve_synced_layers" in selected:
        if selected["controller_resolve_synced_layers"] is not True:
            raise ValueError("unqualified controller synchronized layer policy")
        body = controller_resolve_synced_layers(body, root)
    if "controller_loop_states" in selected:
        body = controller_loop_states(body, root, selected["controller_loop_states"], read_clip)
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
        body = controller_behaviour_ranges(body, root, selected["controller_behaviour_order"])
    if "importer_guid" in selected or "crop_rectangle_offset" in selected:
        if class_id != 213 or "importer_guid" not in selected:
            raise ValueError("Sprite import operations require an original Sprite and importer GUID")
        sprites = O.module("player_data")
        if "crop_rectangle_offset" in selected:
            body = sprites.sprite_crop(body, selected["crop_rectangle_offset"])
        body = sprites.sprite_key(body, selected["importer_guid"])
    result = O.remap(body, selected.get("references", []))
    if "director_unbound_tracks" in selected:
        if class_id != 320 or root is None:
            raise ValueError("unbound tracks require original PlayableDirector schema")
        result = director_unbound_tracks(result, root, selected["director_unbound_tracks"])
    if selected.get("demote_keywords") or "keyword_policy" in selected:
        return O.demote_material_keywords(
            result,
            sort_invalid=selected.get("keyword_policy") in ("dummy-shader-sort-invalid", "sdk-fallback-sort-invalid"),
            valid_keywords=material_keywords if selected.get("keyword_policy") == "sdk-fallback-sort-invalid" else (),
        )
    return result


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
        if set(profile) - {"sdk", "managed", "material_keyword_sdk"} != {"input_id", "bundles"} or profile["input_id"] != M.INPUT_ID:
            raise ValueError("unknown object-record input")
        yield from profile["bundles"]


def managed_record_hash(body, typ, metadata, member, script, sdk_tree, identity_owner, *, preserve_original=False):
    """Derive an unchanged managed record's native hash from original schema."""
    if typ["class_id"] != 114 or sdk_tree is None:
        raise ValueError("managed record properties require MonoBehaviour and pinned SDK")
    root = SCHEMA.type_tree(io.BytesIO(typ["tree"]))
    _, spans = fields(body, root)
    script_spans = [extent for path, extent in spans.items() if path in (("m_Script",), ("#490",))]
    if len(script_spans) != 1:
        raise ValueError("original managed script field is absent or ambiguous")
    start, end = script_spans[0]
    if end - start != 12:
        raise ValueError("original managed script field differs")
    file_id, path_id = struct.unpack_from("<iq", body, start)
    source_member = metadata["externals"][file_id - 1]["path"].split("/")[-1] if file_id else member
    selected, script_body, script_type = script
    if path_id == 0 or selected["path_id"] != path_id or selected["member"] != source_member or script_type["class_id"] != 115:
        raise ValueError("managed record script source differs from original PPtr")
    _, names = O.script_fields(script_body)
    if typ["script_id"] != identity_owner.md4("".join(names).encode()):
        raise ValueError("managed record script identity differs from original schema")
    if preserve_original:
        return O.original_script_properties(script_body, script_type, typ, typ, identity_owner)
    return identity_owner.properties_hash(*names, typ["tree"], sdk_tree)


def check_native_type(typ, target):
    if "native_type_hash" in target and target["native_type_hash"] != typ["hash"].hex():
        raise ValueError("produced record native type identity differs")


def produce(profile_path, profile_sha256, pc, output, sdk=None):
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
    runtime_fields = None
    try:
        sdk_path, sdk_tree = None, None
        if not str(profile_path).endswith(".jsonl.gz") and "sdk" in (profile := json.loads(profile_path.read_text())):
            if sdk is None:
                raise ValueError("managed record properties require pinned owner SDK")
            sdk_path = M.safe_input(sdk.resolve(strict=True), profile["sdk"]["path"])
            if B.sha(sdk_path) != profile["sdk"]["sha256"] or output.is_relative_to(sdk.resolve()):
                raise ValueError("SDK script metadata drift or output overlap")
            with sdk_path.open("rb") as stream:
                stream.size = sdk_path.stat().st_size
                metadata = W.read_serialized(stream)
            obj = next(row for row in metadata["objects"] if row["path_id"] == profile["sdk"]["path_id"])
            typ = metadata["types"][obj["type_id"]]
            if typ["class_id"] != 114:
                raise ValueError("SDK script base is not MonoBehaviour")
            sdk_tree = typ["tree"]
        material_keywords, keyword_sdk_path = None, None
        if not str(profile_path).endswith(".jsonl.gz") and "material_keyword_sdk" in profile:
            selected_sdk = profile["material_keyword_sdk"]
            if sdk is None:
                raise ValueError("fallback material keywords require pinned owner SDK")
            keyword_sdk_path = M.safe_input(sdk.resolve(strict=True), "Resources/unity_builtin_extra")
            if output.is_relative_to(sdk.resolve()):
                raise ValueError("SDK material keyword output overlap")
            shader = module("shader_sdk").sdk_source(sdk, selected_sdk["path_id"], selected_sdk["sha256"])
            if shader["m_ParsedForm"]["m_Name"] != selected_sdk["name"]:
                raise ValueError("SDK material keyword shader identity differs")
            material_keywords = set(module("shader_prefab").keyword_registry(shader, ([], []))[0])
        identity_owner = None
        scripts, script_inputs = {}, {}

        def original_record(selected):
            key = selected["bundle"], selected["member"], selected["path_id"], selected["sha256"]
            if key not in scripts:
                path = M.safe_input(pc, selected["bundle"])
                if path not in script_inputs:
                    before = path.stat()
                    if B.sha(path) != selected["bundle_sha256"]:
                        raise ValueError("original record bundle drift")
                    script_inputs[path] = before.st_size, before.st_mtime_ns, selected["bundle_sha256"]
                if script_inputs[path][2] != selected["bundle_sha256"]:
                    raise ValueError("original record bundle pin differs")
                with O.source_member(path, selected["member"]) as member:
                    metadata = W.read_serialized(member)
                    obj = next(row for row in metadata["objects"] if row["path_id"] == selected["path_id"])
                    member.seek(metadata["data_offset"] + obj["offset"])
                    body = B.exact(member, obj["bytes"])
                if hashlib.sha256(body).hexdigest() != selected["sha256"]:
                    raise ValueError("original record body drift")
                scripts[key] = selected, body, metadata["types"][obj["type_id"]]
            return scripts[key]

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

                    def read_controller_clip(row, pointer):
                        file_id, path_id = pointer
                        name = metadata["externals"][file_id - 1]["path"].split("/")[-1] if file_id else selected_member["name"]
                        if row["member"] != name or row["path_id"] != path_id:
                            raise ValueError("controller original clip PPtr drift")
                        clip_path = M.safe_input(pc, row["bundle"])
                        if B.sha(clip_path) != row["bundle_sha256"]:
                            raise ValueError("controller original clip bundle drift")
                        clip_bundle = B.Bundle(clip_path)
                        clip_member = clip_bundle.member(name)
                        clip_metadata = W.read_serialized(clip_member)
                        clip_object = next(obj for obj in clip_metadata["objects"] if obj["path_id"] == path_id)
                        clip_type = clip_metadata["types"][clip_object["type_id"]]
                        if clip_type["class_id"] != 74:
                            raise ValueError("controller loop input is not an original AnimationClip")
                        clip_member.seek(clip_metadata["data_offset"] + clip_object["offset"])
                        clip_body = B.exact(clip_member, clip_object["bytes"])
                        if hashlib.sha256(clip_body).hexdigest() != row["sha256"]:
                            raise ValueError("controller original clip body drift")
                        clip_root = SCHEMA.type_tree(io.BytesIO(clip_type["tree"]))
                        clip_spans = fields(clip_body, clip_root)[1]
                        start, stop = clip_spans[("m_MuscleClip", "m_LoopTime")]
                        if stop - start != 1 or clip_body[start] not in (0, 1):
                            raise ValueError("invalid original clip loop extent")
                        if B.sha(clip_path) != row["bundle_sha256"]:
                            raise ValueError("controller original clip input changed during production")
                        return bool(clip_body[start])

                    for selected in selected_member["objects"]:
                        obj = objects[selected["path_id"]]
                        typ = metadata["types"][obj["type_id"]]
                        if typ["class_id"] != selected["class_id"] or selected["class_id"] not in (
                            1,
                            4,
                            21,
                            23,
                            33,
                            54,
                            64,
                            65,
                            72,
                            74,
                            91,
                            95,
                            96,
                            104,
                            108,
                            114,
                            119,
                            120,
                            135,
                            136,
                            137,
                            156,
                            193,
                            198,
                            199,
                            205,
                            213,
                            215,
                            221,
                            222,
                            223,
                            224,
                            225,
                            226,
                            227,
                            228,
                            320,
                            330,
                        ):
                            raise ValueError("unqualified original object class")
                        member.seek(metadata["data_offset"] + obj["offset"])
                        body = B.exact(member, obj["bytes"])
                        if hashlib.sha256(body).hexdigest() != selected["sha256"]:
                            raise ValueError("original object-record body drift")
                        if "missing_script_base" in selected:
                            body, typ = O.missing_script_base(body, typ, selected["missing_script_base"], lambda row: original_record(row)[2])
                        if "preserve_original_script_hash" in selected:
                            if selected["preserve_original_script_hash"] is not True or "properties_hash" not in selected:
                                raise ValueError("original managed hash requires explicit script properties")
                        if "prune_absent_script_fields" in selected and (
                            selected["prune_absent_script_fields"] is not True
                            or "properties_hash" not in selected
                            or selected.get("preserve_original_script_hash")
                        ):
                            raise ValueError("current script projection requires SDK properties and unchanged original binding")
                        if "properties_hash" in selected:
                            if set(selected["properties_hash"]) != {"script"}:
                                raise ValueError("unknown managed record hash policy")
                            if identity_owner is None:
                                identity_owner = O.module("script_identity", Path(__file__).resolve().parents[3] / "scripts/lab/script_identity.py")
                            value = managed_record_hash(
                                body,
                                typ,
                                metadata,
                                selected_member["name"],
                                original_record(selected["properties_hash"]["script"]),
                                sdk_tree,
                                identity_owner,
                                preserve_original=selected.get("preserve_original_script_hash", False),
                            )
                            if selected.get("prune_absent_script_fields"):
                                if "managed" not in profile:
                                    raise ValueError("current script projection requires pinned original assemblies")
                                if runtime_fields is None:
                                    runtime_fields = identity_owner.OriginalScriptFields(pc, profile["managed"])
                                script_body = original_record(selected["properties_hash"]["script"])[1]
                                body, tree, removed = O.project_current_script_fields(
                                    body, typ["tree"], runtime_fields.names(script_body), sdk_tree, identity_owner
                                )
                                typ = {**typ, "tree": tree}
                                value = identity_owner.properties_hash(*O.script_fields(script_body)[1], tree, sdk_tree)
                                receipt.setdefault("pruned_script_fields", {})[str(obj["path_id"])] = removed
                            typ = {**typ, "hash": value}
                        root = None
                        if typ["class_id"] in (74, 91, 320) or any(
                            any(key in target.get("transform", {}) for key in ("control_exposed_name_default", "expanding_wave_scale"))
                            for target in selected["outputs"]
                        ):
                            if obj["type_id"] not in trees:
                                trees[obj["type_id"]] = SCHEMA.type_tree(io.BytesIO(typ["tree"]))
                            root = trees[obj["type_id"]]
                        for target in selected["outputs"]:
                            check_native_type(typ, target)
                            operations = target.get("transform", {})
                            if typ["class_id"] == 74:
                                result = transform(body, root, operations)
                            else:
                                result = transform_generic(
                                    body, typ["class_id"], operations, root, read_controller_clip, typ, material_keywords, original_record
                                )
                            digest = hashlib.sha256(result).hexdigest()
                            if digest != target["sha256"] or len(result) != target["bytes"]:
                                raise ValueError("produced object record differs from accepted hash")
                            row = {key: target[key] for key in ("bundle", "member", "path_id", "bytes", "sha256")}
                            row["offset"] = data.tell()
                            if "native_type_hash" in target:
                                row["native_type_hash"] = typ["hash"].hex()
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
        for path, (size, mtime, digest) in script_inputs.items():
            after = path.stat()
            if (after.st_size, after.st_mtime_ns) != (size, mtime) or B.sha(path) != digest:
                raise ValueError("original managed script changed during production")
        if sdk_path is not None and B.sha(sdk_path) != profile["sdk"]["sha256"]:
            raise ValueError("SDK script metadata changed during production")
        if keyword_sdk_path is not None and B.sha(keyword_sdk_path) != profile["material_keyword_sdk"]["sha256"]:
            raise ValueError("SDK material keyword declarations changed during production")
        if runtime_fields is not None:
            runtime_fields.verify()
            receipt["managed_field_inputs"] = dict(runtime_fields.pins)
        receipt["outputs"] = {name: {"bytes": (output / name).stat().st_size, "sha256": B.sha(output / name)} for name in ("objects.bin", "index.jsonl")}
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        if runtime_fields is not None:
            runtime_fields.close()
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, help="pinned owner SDK root for original managed type hashes")
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output, args.sdk)


if __name__ == "__main__":
    main()
