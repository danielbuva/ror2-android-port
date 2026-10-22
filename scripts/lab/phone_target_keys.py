"""Experimental static SDK target-key input bindings; never live target support.

Android/host: python3 -I -S THIS.py OWNER_SDK NEW_PRIVATE_REPORT.json
Only authored sibling tooling is loaded; SDK instructions are never executed.
"""

from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys

_spec = importlib.util.spec_from_file_location("_target_geometry", Path(__file__).with_name("phone_target_geometry.py"))
geometry_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geometry_module)
ctor, f = geometry_module.ctor, geometry_module.f
SOURCES = ("phone_target_keys.py", *geometry_module.SOURCES)
PAIR = r"__ZNSt3__14pairIK19BuildTargetPlatformN4core12basic_stringIcNS3_20StringStorageDefaultIcEEEEEC1IS1_RA([0-9]+)_KcLb0EEEOT_OT0_"


def scalar_immediate(word):
    if word & 0xFF800000 != 0x52800000 or (word >> 21) & 3 > 1 or word & 31 == 31:
        raise ValueError("Unknown 32-bit key/length immediate")
    return (((word >> 5) & 65535) << (((word >> 21) & 3) * 16)) & 0xFFFFFFFF


def stack_offset(origin, use, register):
    value = origin.at(use, register)
    if value == ("stack",):
        return 0
    if value[0] == "add" and value[1] == ("stack",):
        return value[2]
    raise ValueError("Record argument is not a proven stack-relative address")


def label_token(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", value):
        raise ValueError("Unknown target-key token")
    return value


def payload(image, words, origin, grow, record, setup):
    size_origin = origin.at(grow, 1)
    if size_origin[0] != "constant" or not 0 < size_origin[1] <= 128:
        raise ValueError("Unknown inline string size")
    length = size_origin[1]
    if stack_offset(origin, grow, 0) != record + 8:
        raise ValueError("Inline grow does not receive its record's string")
    values, pointers = {}, {}
    output = [None] * (length + 1)
    cursor = grow + 4
    while cursor < min(grow + 128, setup):
        word = words[cursor]
        if word & 0xFFC00000 == 0x39400000 and (word >> 5) & 31 == 31 and (word >> 10) & 4095 == record + 40:
            break
        if cursor not in origin.dom[setup]:
            raise ValueError("Inline payload instruction can be skipped")
        kind = word & 0x7F800000
        if kind in (0x52800000, 0x72800000):
            destination = word & 31
            shift = ((word >> 21) & 3) * 16
            if destination == 0 or not word & 0x80000000 and shift >= 32:
                raise ValueError("Payload immediate clobbers its buffer or has an invalid width")
            value = ((word >> 5) & 65535) << shift
            if kind == 0x72800000:
                if destination not in values:
                    raise ValueError("Uninitialized payload MOVK")
                value |= values[destination] & ~(65535 << shift)
            values[destination] = value & (0xFFFFFFFFFFFFFFFF if word & 0x80000000 else 0xFFFFFFFF)
            pointers.pop(destination, None)
        elif word & 0x9F000000 == 0x90000000:
            destination, address = f.pair_constant(words, cursor)
            if destination == 0 or cursor + 4 not in origin.dom[setup]:
                raise ValueError("Literal definition clobbers its buffer or can be skipped")
            pointers[destination] = f.literal(image, address).encode("ascii") + b"\0"
            values.pop(destination, None)
            cursor += 4
        elif word & 0xFFC00000 == 0xF9400000 or word & 0xFFE00C00 == 0xF8400000:
            destination, source = word & 31, (word >> 5) & 31
            if destination == 0 or source not in pointers:
                raise ValueError("Payload load clobbers its buffer or has no literal source")
            offset = ((word >> 10) & 4095) * 8 if word & 0xFFC00000 == 0xF9400000 else f.registry.signed((word >> 12) & 511, 9)
            data = pointers[source]
            if not 0 <= offset <= len(data) - 8:
                raise ValueError("Payload load escapes its declared C string")
            values[destination] = int.from_bytes(data[offset : offset + 8], "little")
            pointers.pop(destination, None)
        else:
            stores = f.literals.store(word) or []
            if len(stores) != 1:
                raise ValueError("Unknown inline payload instruction")
            base, offset, width, source, vector = stores[0]
            if base != 0 or vector or not 0 <= offset <= len(output) - width or source != 31 and source not in values:
                raise ValueError("Unqualified inline payload store")
            value = 0 if source == 31 else values[source]
            fragment = (value & ((1 << (width * 8)) - 1)).to_bytes(width, "little")
            for position, byte in enumerate(fragment, offset):
                if output[position] not in (None, byte):
                    raise ValueError("Conflicting inline payload writes")
                output[position] = byte
        cursor += 4
    else:
        raise ValueError("Missing inline mode/length continuation")
    if None in output or output[-1] != 0 or 0 in output[:-1]:
        raise ValueError("Incomplete inline payload or terminator")
    tag = words[cursor] & 31
    if words.get(cursor + 4) != 0x7100001F | tag << 5 | 1 << 10:
        raise ValueError("Inline length choice does not compare its mode tag")
    branch = words.get(cursor + 8, 0)
    heap = cursor + 24
    if branch & 31 != 1 or f.branch_target(branch, cursor + 8, "conditional") != heap:
        raise ValueError("Inline/heap length condition or join differs")
    capacity = None
    for pc in range(min(words), grow, 4):
        if f.literals.store(words[pc]) == [(31, record + 32, 1, words[pc] & 31, False)]:
            if pc not in origin.dom[grow]:
                raise ValueError("Inline capacity initialization can be skipped")
            value = origin.at(pc, words[pc] & 31)
            if value[0] != "constant":
                raise ValueError("Unknown inline capacity")
            capacity = value[1]
    if capacity is None or not length < capacity <= 255:
        raise ValueError("Unqualified fresh inline capacity")
    inline_value = scalar_immediate(words[cursor + 12])
    inline_register = words[cursor + 12] & 31
    if inline_value != capacity - length or f.literals.store(words[cursor + 16]) != [(31, record + 32, 1, inline_register, False)]:
        raise ValueError("Inline length store does not encode its supplied payload length")
    if f.branch_target(words.get(cursor + 20, 0), cursor + 20, "direct") != cursor + 32:
        raise ValueError("Inline length path does not rejoin after its heap alternative")
    heap_register = words[heap] & 31
    if scalar_immediate(words[heap]) != length or f.literals.store(words[heap + 4]) != [(31, record + 24, 8, heap_register, False)]:
        raise ValueError("Heap length store differs from supplied payload length")
    return label_token(bytes(output[:-1]).decode("ascii")), cursor + 32


def derive(image):
    geometry = geometry_module.derive(image)
    words = f.literals.function_words(image, geometry_module.FUNCTION)
    origin = ctor.Origins(words)
    setup = geometry["setup"]
    base, stride, span = (geometry[key] for key in ("list_base", "list_stride", "list_span"))
    targets = {}
    for symbol in image.symbols:
        match = re.fullmatch(PAIR, symbol)
        if match:
            address = image.symbol(symbol)
            if address in targets:
                raise ValueError("Ambiguous typed constructor identity")
            targets[address] = (symbol, int(match[1]))
    rows = []

    def index(record):
        offset = record - base
        if not 0 <= offset < span or offset % stride or offset + geometry["constructor_write_extent"] > span:
            raise ValueError("Record source is not contained in one consumed initializer slot")
        return offset // stride

    for pc in words:
        target = f.call_target(words, pc)
        if target not in targets:
            continue
        symbol, size = targets[target]
        if not all(at in origin.dom[setup] for at in range(pc - 24, pc + 4, 4)):
            raise ValueError("Constructor inputs/call can be skipped before map setup")
        record = stack_offset(origin, pc, 0)
        slot = index(record)
        immediate, store = words[pc - 20], words[pc - 16]
        key = scalar_immediate(immediate)
        parts = f.literals.store(store)
        if parts is None or len(parts) != 1 or parts[0][0] != 31 or parts[0][2:] != (4, immediate & 31, False):
            raise ValueError("Unknown typed-constructor scalar store")
        key_slot = stack_offset(origin, pc, 1)
        if key_slot != parts[0][1] or not 0 <= key_slot <= base - 4:
            raise ValueError("Scalar argument aliases the initializer or differs from its stored key")
        register, address = f.pair_constant(words, pc - 12)
        if register != 2:
            raise ValueError("Constructor string argument is not the supplied literal")
        label = label_token(f.literal(image, address))
        if len(label.encode("ascii")) + 1 != size:
            raise ValueError("Typed literal array extent differs from its C string")
        rows.append(
            dict(
                slot=slot,
                key=key,
                label=label,
                record_stack_offset=record,
                source="typed-constructor-arguments",
                call=pc,
                source_begin=pc - 24,
                source_end=pc + 4,
                constructor=symbol,
            )
        )

    grow_target = image.symbol("__ZN4core20StringStorageDefaultIcE4growEm")
    owner_target = image.symbol("__Z21SetCurrentMemoryOwnerRK10MemLabelId")
    for pc, word in words.items():
        if not geometry["frame_allocation"] < pc < setup:
            continue
        stores = f.literals.store(word) or []
        if len(stores) != 1:
            continue
        source_base, record, width, register, vector = stores[0]
        if source_base != 31 or vector or width != 4 or not base <= record < base + span or (record - base) % stride:
            continue
        slot = index(record)
        if words[pc - 4] & 31 != register:
            raise ValueError("Inline key store lost its immediate source")
        key = scalar_immediate(words[pc - 4])
        grow_calls = [at for at in range(pc + 4, min(pc + 160, setup), 4) if f.call_target(words, at) == grow_target]
        if len(grow_calls) != 1:
            raise ValueError("Missing or ambiguous inline string construction")
        grow = grow_calls[0]
        calls = [(at, f.call_target(words, at)) for at in range(pc + 4, grow + 4, 4) if f.call_target(words, at) is not None]
        if [target for at, target in calls] != [owner_target, grow_target] or any(at not in origin.dom[setup] for at in (pc - 4, pc, grow)):
            raise ValueError("Unknown or skipped inline constructor prerequisite")
        initial = {(record + 8, 31), (record + 40, None)}
        found = set()
        for at in range(pc + 4, grow, 4):
            parts = f.literals.store(words[at]) or []
            if len(parts) != 1:
                continue
            target_base, offset, size, value, vector = parts[0]
            if target_base != 31 or vector or size != 1:
                continue
            if offset == record + 8 and value == 31:
                found.add((offset, 31))
            elif offset == record + 40 and origin.at(at, value) == ("constant", 1):
                found.add((offset, None))
            if offset in (record + 8, record + 40) and at not in origin.dom[grow]:
                raise ValueError("Inline string initialization can be skipped")
        if found != initial:
            raise ValueError("Missing fresh inline string initialization")
        label, source_end = payload(image, words, origin, grow, record, setup)
        rows.append(
            dict(
                slot=slot,
                key=key,
                label=label,
                record_stack_offset=record,
                source="inline-copy-operands",
                key_store=pc,
                grow_call=grow,
                source_begin=pc - 4,
                source_end=source_end,
            )
        )
    rows.sort(key=lambda row: row["slot"])
    if [row["slot"] for row in rows] != list(range(geometry["list_count"])) or len({row["key"] for row in rows}) != len(rows):
        raise ValueError("Missing, duplicated or aliased initializer source slots/keys")
    ranges = sorted((row["source_begin"], row["source_end"]) for row in rows)
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("Overlapping constructor/source intervals")
    return dict(
        geometry=geometry,
        rows=rows,
        source_argument_slots_complete=True,
        constructor_result_qualified=False,
        tree_population_qualified=False,
        target_support_qualified=False,
        root_generation_qualified=False,
    )


def inspect(binary, output):
    """Bind a new private declaration report to unchanged source and SDK bytes."""
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private target-key report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != f.registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in SOURCES}
    result = derive(f.registry.MachO(data))
    if binary.read_bytes() != data or any(
        hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest for name, digest in sources.items()
    ):
        raise ValueError("SDK or target-key source changed during inspection")
    result.update(
        schema=1,
        profile="native-target-key-inputs-v1",
        sdk_sha256=f.registry.BINARY_SHA256,
        sources=sources,
        executes_sdk=False,
        normal_control_flow_only=True,
        game_inputs=False,
        target_discovery_qualified=False,
        module_inclusion_qualified=False,
        native_usage_qualified=False,
    )
    with output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    inspect(*sys.argv[1:])
