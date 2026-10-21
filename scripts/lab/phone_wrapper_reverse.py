"""Derive a pinned SDK-only live-observer layout, never a wrapper mapping.

Runtime VM ranges include readable zero-fill tails. The existing file-backed
Mach-O reader remains unchanged and must still refuse reads from those tails.
"""

import struct

from phone_wrapper_population import Origins, REBUILD, literals, registry

MANAGER = "__Z19GetScriptingManagerv"
CONTEXT = "__Z21GetManagerFromContexti"
REVERSE = "__ZN16ScriptingManager27NativeTypeForScriptingClassE17ScriptingClassPtr"
MONO_SHA256 = "5d262167de4d3001a48f50baafcc03a55ceebaf817429e0dcc049cb0b0883995"
SOURCES = tuple(
    "scripts/lab/" + name + ".py"
    for name in (
        "phone_wrapper_reverse",
        "phone_wrapper_population",
        "phone_registry",
        "phone_registry_literals",
        "phone_wrapper_search",
        "phone_native_flags",
        "phone_managed_types",
    )
)


def readable_ranges(image):
    position = 32
    result = []
    commands = struct.unpack_from("<I", image.data, 16)[0]
    for _ in range(commands):
        command, length = struct.unpack_from("<II", image.data, position)
        if command == 0x19:
            start, size, _, file_size = struct.unpack_from("<QQQQ", image.data, position + 24)
            protection = struct.unpack_from("<I", image.data, position + 60)[0]
            if protection & 1 and size:
                if start + size > 2**64 or any(start < row["start"] + row["size"] and row["start"] < start + size for row in result):
                    raise ValueError("Overlapping or overflowing readable SDK VM ranges")
                result.append({"start": start, "size": size, "file_size": file_size})
        position += length
    if not result:
        raise ValueError("No readable SDK VM ranges")
    return result


def layout(image):
    manager = literals.function_words(image, MANAGER)
    branches = [(pc, word) for pc, word in manager.items() if word & 0xFC000000 == 0x14000000]
    if len(manager) != 2 or len(branches) != 1:
        raise ValueError("Unsupported SDK manager accessor")
    pc, word = branches[0]
    if pc + registry.signed(word & 0x3FFFFFF, 26) * 4 != image.symbol(CONTEXT):
        raise ValueError("Manager accessor does not select context")
    index = Origins(image, manager).constant(pc, 0)
    if not 0 <= index < 24:
        raise ValueError("Manager index out of supported range")
    context = literals.function_words(image, CONTEXT)
    slots = []
    for pc, word in context.items():
        # LDR Xt, [Xn, Wm, SXTW #3], the indexed manager-table load.
        if word & 0xFFE0FC00 != 0xF860D800:
            continue
        prefix = {p: w for p, w in context.items() if p <= pc}
        origins = Origins(image, prefix)
        if origins.origin(pc, (word >> 16) & 31) != ("parameter", 0):
            raise ValueError("Manager table index has another origin")
        slots.append(origins.constant(pc, (word >> 5) & 31) + index * 8)
    if len(slots) != 1:
        raise ValueError("Missing or ambiguous manager table")

    words = literals.function_words(image, REVERSE)
    loads = {}
    # Only this straight entry prefix supplies the manager's vector fields;
    # later indirect virtual calls are not interpreted by the operand reader.
    for pc, word in words.items():
        if pc > min(words) + 52:
            break
        if word & 0xFFC00000 == 0xF9400000:
            origins = Origins(image, {p: w for p, w in words.items() if p <= pc})
            if origins.origin(pc, (word >> 5) & 31) == ("parameter", 0):
                loads[word & 31] = ((word >> 10) & 4095) * 8
    differences = set()
    for word in words.values():
        if word & 0xFFE0FC00 == 0xEB000000:
            end, begin = (word >> 5) & 31, (word >> 16) & 31
            if begin in loads and end in loads and loads[end] == loads[begin] + 8:
                differences.add((loads[begin], loads[end], word & 31))
    if len(differences) != 1:
        raise ValueError("Missing or ambiguous reverse vector bounds")
    begin, end, difference_register = next(iter(differences))
    shifts = {
        (word >> 16) & 63 for word in words.values() if word & 0xFFC00000 == 0x93400000 and (word >> 5) & 31 == difference_register and (word >> 10) & 63 == 63
    }
    strides = {registry.signed((word >> 12) & 511, 9) for word in words.values() if word & 0xFFE00C00 == 0xF8400400}
    if len(shifts) != 1 or strides != {1 << next(iter(shifts))} or next(iter(strides)) != 16:
        raise ValueError("Unsupported reverse vector element size")
    ranges = readable_ranges(image)
    if sum(row["start"] <= slots[0] and slots[0] + 8 <= row["start"] + row["size"] for row in ranges) != 1:
        raise ValueError("Manager slot is outside readable SDK VM")
    rebuild = literals.function_words(image, REBUILD)
    forward = set()
    for pc, word in rebuild.items():
        if pc > min(rebuild) + 120:
            break
        if word & 0xFFC00000 == 0xF9400000 and word & 31 == 0:
            prefix = {p: w for p, w in rebuild.items() if p <= pc}
            if Origins(image, prefix).origin(pc, (word >> 5) & 31) == ("parameter", 0):
                forward.add(((word >> 10) & 4095) * 8)
    if len(forward) != 1:
        raise ValueError("Missing or ambiguous forward vector")
    forward_offset = next(iter(forward))
    # The SDK's dynamic_array size is independently evidenced by the count
    # stores in this same rebuild function, not supplied by the wrapper model.
    count_stores = []
    for pc, word in rebuild.items():
        if word & 0xFFC00000 != 0xF9000000 or ((word >> 10) & 4095) * 8 != forward_offset + 24:
            continue
        count_stores.append(pc)
    if len(count_stores) != 2:
        raise ValueError("Forward vector size stores differ")
    # Qualify the first assignment prefix only. A later shift on the zero-size
    # path is outside the existing operand reader; do not weaken that reader.
    pc = min(count_stores)
    word = rebuild[pc]
    if Origins(image, {p: w for p, w in rebuild.items() if p <= pc}).origin(pc, (word >> 5) & 31) != ("parameter", 0):
        raise ValueError("Forward count field has another base")
    return {
        "schema": 1,
        "manager_slot": slots[0],
        "begin_offset": begin,
        "end_offset": end,
        "stride": next(iter(strides)),
        "native_id_offset": 40,
        "forward_offset": forward_offset,
        "forward_count_offset": forward_offset + 24,
        "ranges": ranges,
    }
