"""Current experimental SDK pair-copy operands; never constructor results."""

from pathlib import Path
import importlib.util

_spec = importlib.util.spec_from_file_location("_target_features", Path(__file__).with_name("phone_platform_features.py"))
f = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(f)
SOURCES = ("phone_target_constructor.py", *f.SOURCES)


def add(value, offset):
    if value[0] == "add":
        return add(value[1], value[2] + offset)
    return value if offset == 0 else ("add", value, offset)


def pre_store(word):
    return word & 0x3B600C00 == 0x38000C00 and not word & 0x4000000


def indexed_null(word):
    return word & 0xFFE0FC1F == 0x3820681F


def effects(word):
    if pre_store(word):
        return {(word >> 5) & 31}
    if indexed_null(word):
        return set()
    return f.feature_effects(word)


class Origins:
    def __init__(self, words):
        self.words = words
        self.dom = f.literals.dominators(f.literals.graph(words))

    def at(self, use, register, budget=48):
        if register == 31:
            return ("stack",)
        if budget <= 0 or use not in self.dom:
            raise ValueError("Unknown constructor operand")
        for pc in range(use - 4, min(self.words) - 1, -4):
            word = self.words[pc]
            changed = effects(word)
            if changed is None:
                raise ValueError("Unknown constructor operand effect")
            if register not in changed:
                continue
            if pc not in self.dom[use]:
                raise ValueError("Constructor operand definition can be skipped")
            target = f.call_target(self.words, pc)
            if target is not None:
                return ("return", target, pc, register)
            source = f.search.move(word)
            if source is not None:
                return ("constant", 0) if source == 31 else self.at(pc, source, budget - 1)
            if word & 0xFFC00000 == 0x91000000:
                return add(self.at(pc, (word >> 5) & 31, budget - 1), (word >> 10) & 4095)
            if pre_store(word) and (word >> 5) & 31 == register:
                return add(self.at(pc, register, budget - 1), f.registry.signed((word >> 12) & 511, 9))
            if word & 0x3B400000 == 0x39400000 and not word & 0x4000000:
                width = 1 << (word >> 30)
                return ("load", add(self.at(pc, (word >> 5) & 31, budget - 1), ((word >> 10) & 4095) * width), width)
            if word & 0x7F800000 == 0x52800000:
                return ("constant", ((word >> 5) & 65535) << (((word >> 21) & 3) * 16))
            if word & 0xFFE0FC00 == 0x4B000000:
                return ("subtract32", self.at(pc, (word >> 5) & 31, budget - 1), self.at(pc, (word >> 16) & 31, budget - 1))
            raise ValueError("Unknown constructor operand producer")
        return ("parameter", register)


def prove(image, symbol):
    whole = f.literals.function_words(image, symbol)
    ends = [pc for pc, word in whole.items() if word == 0xD65F03C0]
    if not ends:
        raise ValueError("Missing constructor return")
    end = ends[0]
    words = {pc: word for pc, word in whole.items() if pc <= end}
    origin = Origins(words)
    for pc, word in words.items():
        if effects(word) is None:
            raise ValueError("Unknown normal constructor instruction")
        target = f.direct_branch(word, pc)
        if target is not None and target not in words:
            raise ValueError("Constructor branch escapes normal scope")
    targets = (
        image.symbol("__Z21SetCurrentMemoryOwnerRK10MemLabelId"),
        f.imported_stub(image, "_strlen"),
        image.symbol("__ZN4core20StringStorageDefaultIcE4growEm"),
        f.imported_stub(image, "_memcpy"),
    )
    calls = [(pc, f.call_target(words, pc)) for pc in words if f.call_target(words, pc) is not None]
    if tuple(target for pc, target in calls) != targets or any(pc not in origin.dom[end] for pc, target in calls):
        raise ValueError("Unknown, skipped or reordered constructor call")
    owner, strlen, grow, memcpy = [pc for pc, target in calls]
    size = ("return", targets[1], strlen, 0)
    data = ("return", targets[2], grow, 0)
    output = ("parameter", 0)
    checks = (
        (origin.at(strlen, 0), ("parameter", 2)),
        (origin.at(grow, 0), add(output, 8)),
        (origin.at(grow, 1), size),
        (origin.at(memcpy, 0), data),
        (origin.at(memcpy, 1), ("parameter", 2)),
        (origin.at(memcpy, 2), size),
        (origin.at(end, 0), output),
    )
    if any(actual != expected for actual, expected in checks):
        raise ValueError("Constructor copy arguments/receiver differ")
    expected = {
        (0, 4, ("load", ("parameter", 1), 4)),
        (8, 1, ("constant", 0)),
        (24, 8, size),
        (32, 1, ("constant", 24)),
        (32, 1, ("subtract32", ("constant", 24), size)),
        (40, 1, ("constant", 1)),
        (44, 8, ("return", targets[0], owner, 0)),
        (52, 4, ("return", targets[0], owner, 1)),
    }
    records, nulls, positions = [], [], {}
    for pc, word in words.items():
        if indexed_null(word):
            if origin.at(pc, (word >> 5) & 31) != data or origin.at(pc, (word >> 16) & 31) != size or pc not in origin.dom[end]:
                raise ValueError("Constructor terminator lost its copy buffer/size")
            nulls.append(pc)
            continue
        parts = f.literals.store(word)
        if pre_store(word):
            parts = [((word >> 5) & 31, f.registry.signed((word >> 12) & 511, 9), 1 << (word >> 30), word & 31, False)]
        if parts is None:
            if word & 0x3A400000 == 0x28000000 and (word >> 5) & 31 == 31:
                continue  # Prologue saves only in this function's own stack frame.
            continue
        for base, offset, width, source, vector in parts:
            pointer = add(origin.at(pc, base), offset)
            if pointer[0] == "stack" or pointer[0] == "add" and pointer[1] == ("stack",):
                continue
            if pointer[0] != "add" and pointer != output or pointer[0] == "add" and pointer[1] != output or vector:
                raise ValueError("Constructor writes outside its record")
            offset = 0 if pointer == output else pointer[2]
            value = ("constant", 0) if source == 31 else origin.at(pc, source)
            record = (offset, width, value)
            if record not in expected:
                raise ValueError("Unknown constructor record field/value")
            records.append(record)
            positions[record] = pc
    if len(records) != len(expected) or set(records) != expected or len(nulls) != 1:
        raise ValueError("Missing, repeated or incomplete constructor writes")
    null = nulls[0]
    tag_pc, compare_pc, branch_pc = null + 4, null + 8, null + 12
    tag = words.get(tag_pc, 0)
    tag_register = tag & 31
    if tag & 0xFFC00000 != 0x39400000 or origin.at(compare_pc, tag_register) != ("load", add(output, 40), 1):
        raise ValueError("Length choice does not read this record's string mode")
    if words.get(compare_pc) != 0x7100001F | tag_register << 5 | 1 << 10:
        raise ValueError("Length choice does not compare the inline-mode tag")
    inline_record = (32, 1, ("subtract32", ("constant", 24), size))
    heap_record = (24, 8, size)
    inline_pc, heap_pc = positions[inline_record], positions[heap_record]
    branch = words.get(branch_pc, 0)
    if branch & 31 != 1 or f.branch_target(branch, branch_pc, "conditional") != heap_pc:
        raise ValueError("Constructor length branch reverses or skips mode-specific storage")
    if inline_pc != branch_pc + 12 or heap_pc != inline_pc + 8:
        raise ValueError("Length-field continuations are not the bounded inline/heap alternatives")
    inline_jump = inline_pc + 4
    if f.branch_target(words.get(inline_jump, 0), inline_jump, "direct") != heap_pc + 4:
        raise ValueError("Inline length update does not rejoin after the heap alternative")
    branches = {pc for pc, word in words.items() if f.direct_branch(word, pc) is not None}
    if branches != {branch_pc, inline_jump}:
        raise ValueError("Unaccounted constructor branch")
    for record, pc in positions.items():
        if record not in (inline_record, heap_record) and (pc not in origin.dom[memcpy] or pc not in origin.dom[end]):
            raise ValueError("Required constructor record initialization can be skipped")
    return {
        "normal_instruction_count": len(words),
        "direct_record_writes": len(records),
        "record_write_extent": max(offset + width for offset, width, value in records),
        "copy_arguments_linked": True,
        "terminator_linked": True,
        "constructor_result_qualified": False,
        "tree_population_qualified": False,
    }
