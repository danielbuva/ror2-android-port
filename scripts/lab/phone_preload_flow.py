"""Bounded normal-flow operand ancestry for generated SDK declarations, never execution."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("_preload_record", Path(__file__).with_name("phone_target_records.py"))
records = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(records)
f = records.f
SOURCES = ("phone_preload_flow.py", *records.SOURCES)


def effects(word):
    # Separate SIMD value registers from GPRs; these unsigned-offset forms have
    # no address writeback. No floating-point value is evaluated.
    if word & 0xFFC00000 in (0xFD000000, 0xFD400000, 0x3D800000, 0x3DC00000, 0xBD000000, 0xBD400000):
        return set()
    if word & 0x9FF80C00 == 0x0F000400:  # SIMD modified immediate, no GPR result.
        return set()
    if word & 0x7F000000 == 0x31000000 or word & 0x7FE08000 == 0x1B000000 or word & 0x7F800000 == 0x32000000:
        return set() if word & 31 == 31 else {word & 31}
    if word & 0xFFE0FC00 == 0xB8207800:  # STR W register offset; no writeback.
        return set()
    return records.ctor.effects(word)


class Flow:
    """Sparse reaching definitions include out-of-line predecessors and backedges.

    Calls have only their normal continuation and ABI GPR clobbers. Exceptions,
    heap values, SDK call results and container semantics are never evaluated.
    """

    def __init__(self, words):
        if not words or len(words) > 32768 or sorted(words) != list(range(min(words), max(words) + 4, 4)):
            raise ValueError("Unbounded or discontinuous preload function")
        self.words = dict(words)
        self.entry = min(words)
        self._definitions, self._dominance = {}, {}
        self.edges = f.literals.graph(words)
        for pc, word in words.items():
            target = f.direct_branch(word, pc)
            if target is not None and target not in words:
                raise ValueError("Preload branch escapes its function")
        self.reachable = self.walk(self.entry)
        self.pred = {pc: set() for pc in self.reachable}
        for pc in self.reachable:
            for target in self.edges[pc]:
                self.pred[target].add(pc)

    def walk(self, start, stop=None):
        pending, visited = [start], set()
        while pending:
            pc = pending.pop()
            if pc == stop or pc in visited:
                continue
            visited.add(pc)
            pending.extend(self.edges[pc])
        return visited

    def definitions(self, use, register):
        key = use, register
        if key in self._definitions:
            return self._definitions[key]
        if use not in self.reachable or not 0 <= register <= 31:
            raise ValueError("Unreachable preload operand or invalid GPR")
        pending, visited, definitions = list(self.pred[use]), set(), set()
        if use == self.entry:
            definitions.add(None)
        while pending:
            pc = pending.pop()
            if pc in visited:
                continue
            visited.add(pc)
            writes = effects(self.words[pc])
            if writes is None:
                raise ValueError("Unknown preload GPR effect")
            if register in writes:
                definitions.add(pc)
            elif pc == self.entry:
                definitions.add(None)
            else:
                pending.extend(self.pred[pc])
        if not definitions:
            raise ValueError("Preload operand has no reaching definition")
        result = frozenset(definitions)
        if len(self._definitions) >= 8192:
            raise ValueError("Preload definition-query budget exhausted")
        self._definitions[key] = result
        return result

    def definition(self, use, register):
        return records.one(list(self.definitions(use, register)))

    def stack(self, use, register, budget=16):
        if budget <= 0:
            raise ValueError("Preload stack-alias budget exhausted")
        pc = self.definition(use, register)
        if pc is None:
            raise ValueError("Preload stack alias is an entry parameter")
        word = self.words[pc]
        if register == 31:
            if word & 0xFFC003FF != 0xD10003FF or not (word >> 10) & 4095:
                raise ValueError("SP lacks one fixed allocation anchor")
            return pc, 0, (word >> 10) & 4095
        source = f.search.move(word)
        if source is not None:
            if source == 31:
                raise ValueError("MOV zero-register value is not SP")
            return self.stack(pc, source, budget - 1)
        if word & 0xFFC00000 == 0x91000000:
            anchor, offset, extent = self.stack(pc, (word >> 5) & 31, budget - 1)
            offset += (word >> 10) & 4095
            if not 0 <= offset < extent:
                raise ValueError("Preload alias escapes its fixed allocation")
            return anchor, offset, extent
        raise ValueError("Unknown preload stack-alias producer")

    def constant(self, use, register, budget=16):
        if register == 31 or budget <= 0:
            raise ValueError("Missing preload scalar value")
        pc = self.definition(use, register)
        if pc is None:
            raise ValueError("Preload scalar is an entry parameter")
        word = self.words[pc]
        source = f.search.move(word)
        if source is not None:
            return self.constant(pc, source, budget - 1)
        kind, shift = word & 0x7F800000, ((word >> 21) & 3) * 16
        if kind not in (0x12800000, 0x52800000, 0x72800000) or not word & 0x80000000 and shift >= 32:
            raise ValueError("Unknown preload scalar producer")
        mask = (1 << (64 if word & 0x80000000 else 32)) - 1
        value = ((word >> 5) & 65535) << shift
        if kind == 0x12800000:
            return ~value & mask
        if kind == 0x72800000:
            value |= self.constant(pc, register, budget - 1) & ~(65535 << shift)
        return value & mask

    def literal(self, image, use, register):
        pc = self.definition(use, register)
        if pc is None or self.definition(pc, register) != pc - 4:
            raise ValueError("Literal address lacks its reaching page definition")
        destination, address = f.pair_constant(self.words, pc - 4)
        if destination != register:
            raise ValueError("Literal address uses a different receiver")
        return f.literal(image, address).encode("ascii") + b"\0"

    def buffer(self, use, register, grow, budget=16):
        """Link every normal pointer producer to one field, without running grow."""
        if budget <= 0 or register == 31:
            raise ValueError("Unqualified preload copy buffer")
        fields, paths = set(), set()
        for pc in self.definitions(use, register):
            if pc is None:
                raise ValueError("Preload copy buffer is an entry parameter")
            word = self.words[pc]
            if f.call_target(self.words, pc) == grow and register == 0:
                fields.add(self.stack(pc, 0))
                paths.add("grow-return")
            elif word & 0xFFC00000 == 0xF9400000:
                anchor, offset, extent = self.stack(pc, (word >> 5) & 31)
                offset += ((word >> 10) & 4095) * 8
                fields.add((anchor, offset, extent))
                paths.add("existing-field-storage")
            elif f.search.move(word) is not None:
                source = f.search.move(word)
                try:
                    fields.add(self.stack(pc, source))
                    paths.add("inline-field-address")
                except ValueError:
                    field, previous = self.buffer(pc, source, grow, budget - 1)
                    fields.add(field)
                    paths.update(previous)
            else:
                raise ValueError("Unknown preload copy-buffer producer")
        field = records.one(list(fields))
        if not 0 <= field[1] <= field[2] - 48:
            raise ValueError("Copy field does not fit its fixed allocation")
        return field, tuple(sorted(paths))

    def dominates(self, before, after):
        if before not in self.reachable or after not in self.reachable:
            raise ValueError("Unreachable preload control-flow query")
        key = before, after
        if key not in self._dominance:
            if len(self._dominance) >= 8192:
                raise ValueError("Preload dominance-query budget exhausted")
            self._dominance[key] = after not in self.walk(self.entry, stop=before)
        return self._dominance[key]

    def next_insertion(self, start, target):
        if start not in self.reachable:
            raise ValueError("Unreachable preload continuation")
        pending, visited, calls = [start], set(), set()
        while pending:
            pc = pending.pop()
            if pc in visited:
                continue
            visited.add(pc)
            if f.call_target(self.words, pc) == target:
                calls.add(pc)
            elif not self.edges[pc]:
                raise ValueError("Preload continuation can exit before insertion")
            else:
                pending.extend(self.edges[pc])
        return records.one(list(calls))
