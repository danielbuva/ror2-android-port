"""Experimental SDK preload assignment inputs, not constructed or available targets.

Reads owner SDK data only. Host/Android: python3 -I -S THIS.py OWNER_SDK NEW_PRIVATE_REPORT
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

_spec = importlib.util.spec_from_file_location("_preload_flow", Path(__file__).with_name("phone_preload_flow.py"))
flow_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flow_module)
records, f = flow_module.records, flow_module.f
SOURCES = ("phone_preload_inputs.py", *flow_module.SOURCES)
FUNCTION = "__ZN20BuildTargetDiscovery24PreloadKnownBuildTargetsEv"
GROW = "__ZN4core20StringStorageDefaultIcE4growEm"


def load(word):
    forms = {
        0x39400000: (1, False),
        0x79400000: (2, False),
        0xB9400000: (4, False),
        0xF9400000: (8, False),
        0xBD400000: (4, True),
        0xFD400000: (8, True),
        0x3DC00000: (16, True),
    }
    kind = word & 0xFFC00000
    if kind in forms:
        width, vector = forms[kind]
        return word & 31, (word >> 5) & 31, ((word >> 10) & 4095) * width, width, vector
    if word & 0xFFE00C00 in (0xF8400000, 0x3CC00000):
        vector = word & 0xFFE00C00 == 0x3CC00000
        return word & 31, (word >> 5) & 31, f.registry.signed((word >> 12) & 511, 9), 16 if vector else 8, vector
    return None


def stores(word):
    if word & 0xFFC00000 in (0xFD000000, 0xBD000000):
        width = 8 if word & 0x40000000 else 4
        return [((word >> 5) & 31, ((word >> 10) & 4095) * width, width, word & 31, True)]
    return f.literals.store(word)


def stack_memory(flow, pc, base, field):
    anchor, offset, extent = flow.stack(pc, base)
    offset += field
    if not 0 <= offset < extent:
        raise ValueError("Preload memory operand escapes its fixed allocation")
    return anchor, offset, extent


class Fragments:
    """Explicit register/direct-stack store ancestry, not evaluated SDK memory.

    Call memory effects and indirect-store aliasing remain separate gates. A
    direct spill link identifies its authored operands; it is not a proof that
    an SDK call cannot mutate memory or that a constructed record has a value.
    """

    def __init__(self, image, flow):
        self.image, self.flow = image, flow
        self.cache = {}
        self.spill_links = set()

    def vector_definitions(self, use, register):
        if use not in self.flow.reachable:
            raise ValueError("Unreachable vector input")
        pending, visited, definitions = list(self.flow.pred[use]), set(), set()
        while pending:
            pc = pending.pop()
            if pc in visited:
                continue
            visited.add(pc)
            word = self.flow.words[pc]
            part = load(word)
            writes = set()
            if f.call_target(self.flow.words, pc) is not None:
                writes = set(range(32))  # No vector preservation is assumed.
            elif part is not None and part[4]:
                writes.add(part[0])
            elif word & 0x9FF80C00 == 0x0F000400:
                writes.add(word & 31)
            elif word & 0x3A000000 == 0x28000000 and word & 0x4400000 == 0x4400000:
                writes.update((word & 31, (word >> 10) & 31))
            elif flow_module.effects(word) is None:
                raise ValueError("Unknown vector-input effect")
            if register in writes:
                definitions.add(pc)
            elif pc == self.flow.entry:
                definitions.add(None)
            else:
                pending.extend(self.flow.pred[pc])
        return frozenset(definitions)

    def spill_source(self, use, field, width):
        pending, visited, definitions = list(self.flow.pred[use]), set(), set()
        while pending:
            pc = pending.pop()
            if pc in visited:
                continue
            visited.add(pc)
            matched = False
            for base, offset, size, source, vector in stores(self.flow.words[pc]) or []:
                if base != 31:
                    continue
                anchor, current, extent = stack_memory(self.flow, pc, base, offset)
                if anchor == field[0] and current < field[1] + width and field[1] < current + size:
                    if current > field[1] or current + size < field[1] + width:
                        raise ValueError("Direct spill input is partially overwritten")
                    definitions.add((pc, source, vector, size, field[1] - current))
                    matched = True
            if matched:
                continue
            if pc == self.flow.entry or pc == field[0]:
                definitions.add(None)
            else:
                pending.extend(self.flow.pred[pc])
        source = records.one(list(definitions))
        if source is None:
            raise ValueError("Direct spill input lacks a complete store")
        pc, register, vector, size, offset = source
        self.spill_links.add((pc, use, field[1], width))
        return pc, register, vector, size, offset

    def value(self, use, register, width, vector=False, budget=16):
        if budget <= 0 or not 0 < width <= 16:
            raise ValueError("Preload fragment ancestry budget/width invalid")
        key = use, register, width, vector
        if key in self.cache:
            return self.cache[key]
        if register == 31 and not vector:
            return bytes(width), frozenset()
        definitions = self.vector_definitions(use, register) if vector else self.flow.definitions(use, register)
        pc = records.one(list(definitions))
        if pc is None:
            raise ValueError("Preload fragment is an entry parameter")
        word = self.flow.words[pc]
        part = load(word)
        if part is not None:
            _, base, offset, size, kind = part
            if size < width or kind != vector:
                raise ValueError("Preload fragment load changes register namespace/width")
            if base == 31:
                field = stack_memory(self.flow, pc, base, offset)
                stored, source, source_vector, stored_size, slice_offset = self.spill_source(pc, field, size)
                data, literals = self.value(stored, source, stored_size, source_vector, budget - 1)
                data = data[slice_offset : slice_offset + width]
            else:
                literal = self.flow.literal(self.image, pc, base)
                if not 0 <= offset <= len(literal) - size:
                    raise ValueError("Fragment load escapes its bounded C string")
                data, literals = literal[offset : offset + width], frozenset((literal,))
        elif not vector:
            source = f.search.move(word)
            if source is not None:
                data, literals = self.value(pc, source, width, False, budget - 1)
            else:
                data = (self.flow.constant(use, register) & ((1 << (width * 8)) - 1)).to_bytes(width, "little")
                literals = frozenset()
        else:
            raise ValueError("Unknown static vector-fragment producer")
        result = data, literals
        self.cache[key] = result
        return result


def continuation(flow, start, field, length):
    words = flow.words
    tag, compare, branch = (words.get(start + n, 0) for n in (0, 4, 8))
    reg = tag & 31
    part = load(tag)
    if part is None or part[3:] != (1, False) or stack_memory(flow, start, part[1], part[2]) != (field[0], field[1] + 32, field[2]):
        raise ValueError("Assignment mode load uses a different field")
    if compare != 0x7100041F | reg << 5 or branch & 0xFF00001F != 0x54000001:
        raise ValueError("Assignment mode comparison/condition differs")
    heap = f.branch_target(branch, start + 8, "conditional")
    if heap not in (start + 20, start + 24) or f.branch_target(words.get(heap - 4, 0), heap - 4, "direct") != heap + 8:
        raise ValueError("Assignment inline/heap continuations differ")
    for pc, expected_offset, width, expected_value in ((heap - 8, 24, 1, 24 - length), (heap + 4, 16, 8, length)):
        pieces = stores(words.get(pc, 0))
        if pieces is None or len(pieces) != 1:
            raise ValueError("Missing assignment length write")
        base, offset, size, source, vector = pieces[0]
        if vector or size != width or stack_memory(flow, pc, base, offset) != (field[0], field[1] + expected_offset, field[2]):
            raise ValueError("Assignment length write uses a different field")
        if pc == start + 12:
            # The compiler reuses the mode register on the EQ fallthrough when
            # the inline encoded length is exactly 1; it emits no MOV here.
            if not (expected_value == 1 and source == reg or expected_value == 0 and source == 31) or not flow.dominates(start + 8, pc):
                raise ValueError("Compressed inline length lacks its mode predicate")
        elif flow.constant(pc, source) & ((1 << (width * 8)) - 1) != expected_value & ((1 << (width * 8)) - 1) or not flow.dominates(pc - 4, pc):
            raise ValueError("Assignment length value differs or can be skipped")
    if not flow.dominates(start, start + 8) or not flow.dominates(start + 8, heap + 4):
        raise ValueError("Assignment mode selection can be entered midway")
    return heap + 8


def payload(image, flow, grow_pc, grow_target, field):
    fragments = Fragments(image, flow)
    length = flow.constant(grow_pc, 1)
    if not 0 < length <= 128:
        raise ValueError("Unsupported bounded preload payload length")
    output, literals = [None] * (length + 1), set()
    start, cursor = grow_pc + 4, grow_pc + 4
    buffer_paths = set()
    while cursor < start + 128:
        word = flow.words[cursor]
        if not flow.dominates(start, cursor):
            raise ValueError("Preload copy instruction can be skipped")
        part = load(word)
        if part is not None:
            destination, _, _, width, vector = part
            _, origins = fragments.value(cursor + 4, destination, width, vector)
            literals.update(origins)
        elif word & 0x9F000000 == 0x90000000:
            f.pair_constant(flow.words, cursor)
            if not flow.dominates(cursor, cursor + 4):
                raise ValueError("Literal materialization can be skipped")
            cursor += 4
        elif word & 0x7F800000 in (0x12800000, 0x52800000, 0x72800000):
            pass  # Stored bytes are traced through their actual reaching definitions.
        else:
            pieces = stores(word)
            if pieces is None or len(pieces) != 1:
                raise ValueError("Unknown preload literal-copy instruction")
            base, offset, width, source, vector = pieces[0]
            if base == 31:
                spill = stack_memory(flow, cursor, base, offset)
                if spill[0] != field[0] or spill[1] < field[1] + 48 and field[1] < spill[1] + width:
                    raise ValueError("Copy spill overlaps its assignment field")
                cursor += 4
                continue
            destination_field, paths = flow.buffer(cursor, base, grow_target)
            buffer_paths.update(paths)
            if destination_field != field or not 0 <= offset <= len(output) - width:
                raise ValueError("Preload copy store escapes or changes its field")
            if source == 31 and not vector:
                if width != 1 or offset != length:
                    raise ValueError("Preload zero store is not the supplied terminator")
                output[length] = 0
                break
            fragment, origins = fragments.value(cursor, source, width, vector)
            literals.update(origins)
            for at, byte in enumerate(fragment, offset):
                if output[at] not in (None, byte):
                    raise ValueError("Preload literal fragments conflict")
                output[at] = byte
        cursor += 4
    else:
        raise ValueError("Missing bounded preload copy terminator")
    if None in output or len(literals) != 1 or bytes(output) != next(iter(literals)):
        raise ValueError("Incomplete or changed preload literal copy")
    value = bytes(output[:-1]).decode("ascii")
    if not re.fullmatch(r"PLATFORM_[A-Z0-9_]+", value):
        raise ValueError("Unknown preload platform token")
    end = continuation(flow, cursor + 4, field, length)
    return value, end, sorted(buffer_paths), len(fragments.spill_links)


def derive(image):
    layout = records.derive(image)
    words = f.generated_words(image, FUNCTION)
    flow = flow_module.Flow(words)
    grow, insert = image.symbol(GROW), image.symbol(records.INSERT)
    insertions = [pc for pc in flow.reachable if f.call_target(words, pc) == insert]
    rows, unresolved, other = [], [], 0
    for pc in sorted(flow.reachable):
        if f.call_target(words, pc) != grow:
            continue
        try:
            field = flow.stack(pc, 0)
            insertion = flow.next_insertion(pc + 4, insert)
            record = flow.stack(insertion, 1)
        except ValueError as error:
            unresolved.append(dict(call=pc, reason=str(error)))
            continue
        if field[0] != record[0] or field[2] != record[2]:
            raise ValueError("Assignment/insertion aliases use different allocation anchors")
        relative = field[1] - record[1]
        if relative != layout["consumer_record_string_offset"]:
            other += 1
            continue
        value, end, paths, spill_links = payload(image, flow, pc, grow, field)
        if flow.next_insertion(end, insert) != insertion:
            raise ValueError("Assignment continuations reach different insertions")
        rows.append(
            dict(
                assignment_call=pc,
                copy_join=end,
                insertion=insertion,
                record_stack_offset=record[1],
                field_offset=relative,
                value=value,
                buffer_producers=paths,
                direct_spill_operand_links=spill_links,
                field_allocation_extent=field[2],
            )
        )
    if not rows or len({row["insertion"] for row in rows}) != len(rows):
        raise ValueError("Missing or repeated preload assignment inputs")
    if {row["insertion"] for row in rows} != set(insertions):
        raise ValueError("A preload insertion lacks a bound platform assignment")
    return dict(
        rows=rows,
        insertion_calls=len(insertions),
        unresolved_grow_calls=unresolved,
        other_field_grow_calls=other,
        input_operand_links_qualified=True,
        every_insertion_has_platform_operand_binding={row["insertion"] for row in rows} == set(insertions),
        all_grow_receivers_classified=not unresolved,
        all_record_inputs_complete=False,
        call_memory_effects_qualified=False,
        indirect_store_aliasing_qualified=False,
        record_values_qualified=False,
        constructor_result_qualified=False,
        hash_container_semantics_qualified=False,
        target_support_qualified=False,
        target_discovery_qualified=False,
        module_inclusion_qualified=False,
        native_usage_qualified=False,
        root_generation_qualified=False,
    )


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private preload-input report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != f.registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in SOURCES}
    result = derive(f.registry.MachO(data))
    if binary.read_bytes() != data or any(
        hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest for name, digest in sources.items()
    ):
        raise ValueError("SDK or preload-input source changed during inspection")
    result.update(
        schema=1,
        profile="native-preload-inputs-v1",
        sdk_sha256=f.registry.BINARY_SHA256,
        sources=sources,
        executes_sdk=False,
        normal_control_flow_only=True,
        game_inputs=False,
    )
    with output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    inspect(*sys.argv[1:])
