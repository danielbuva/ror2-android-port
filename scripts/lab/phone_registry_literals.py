"""Read bounded compiled metadata literals; never run or import SDK code."""

import struct


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def function_words(image, name):
    start = image.symbol(name)
    following = [value for values in image.symbols.values() for value in values if value > start]
    if not following or min(following) - start > 16384 or (min(following) - start) % 4:
        raise ValueError("Unqualified metadata-constructor extent")
    return {pc: struct.unpack("<I", image.at(pc, 4))[0] for pc in range(start, min(following), 4)}


def graph(words):
    edges = {}
    for pc, word in words.items():
        target = None
        if word & 0xFC000000 == 0x14000000:
            target = pc + signed(word & 0x3FFFFFF, 26) * 4
            next_steps = [target]
        elif word & 0xFF000010 == 0x54000000 or word & 0x7E000000 == 0x34000000:
            target = pc + signed((word >> 5) & 0x7FFFF, 19) * 4
            next_steps = [pc + 4, target]
        elif word & 0x7E000000 == 0x36000000:
            target = pc + signed((word >> 5) & 0x3FFF, 14) * 4
            next_steps = [pc + 4, target]
        elif word & 0xFFFFFC1F == 0xD65F0000 or word & 0xFFE0001F == 0xD4200000:
            next_steps = []
        elif word & 0xFFFFFC1F in (0xD61F0000, 0xD63F0000):
            raise ValueError("Indirect metadata-constructor control flow")
        else:
            next_steps = [pc + 4]
        edges[pc] = [step for step in next_steps if step in words]
    return edges


def dominators(edges):
    start = min(edges)
    reachable, pending = set(), [start]
    while pending:
        pc = pending.pop()
        if pc not in reachable:
            reachable.add(pc)
            pending.extend(edges[pc])
    predecessors = {pc: set() for pc in reachable}
    for pc in reachable:
        for target in edges[pc]:
            if target in reachable:
                predecessors[target].add(pc)
    result = {pc: ({pc} if pc == start else set(reachable)) for pc in reachable}
    changed = True
    while changed:
        changed = False
        for pc in sorted(reachable - {start}):
            common = set.intersection(*(result[p] for p in predecessors[pc]))
            value = {pc} | common
            if value != result[pc]:
                result[pc], changed = value, True
    return result


def store(word):
    """Return (base, offset, width, register, vector) slices for public store formats."""
    rn, rd = (word >> 5) & 31, word & 31
    if word & 0x3A400000 == 0x28000000:
        if (word >> 23) & 3 != 2:
            return None  # Frame writeback is checked separately.
        vector = bool(word & 0x4000000)
        width = (4 << ((word >> 30) & 3)) if vector else (8 if word & 0x80000000 else 4)
        if width > 16:
            raise ValueError("Invalid metadata store width")
        offset = signed((word >> 15) & 127, 7) * width
        return [(rn, offset, width, rd, vector), (rn, offset + width, width, (word >> 10) & 31, vector)]
    if word & 0x3F400000 == 0x39000000:
        width = 1 << ((word >> 30) & 3)
        return [(rn, ((word >> 10) & 4095) * width, width, rd, False)]
    if word & 0x3FC00000 == 0x3D800000:
        return [(rn, ((word >> 10) & 4095) * 16, 16, rd, True)]
    if word & 0x3B600000 == 0x38000000 and (word >> 10) & 3 == 0:
        vector = bool(word & 0x4000000)
        width = 16 if vector and word & 0x800000 else 1 << ((word >> 30) & 3)
        return [(rn, signed((word >> 12) & 511, 9), width, rd, vector)]
    return None


def changes_frame(word):
    if word & 0x7F000000 in (0x11000000, 0x51000000) and word & 31 == 31:
        return True
    if (word >> 5) & 31 == 31:
        if word & 0x3A000000 == 0x28000000 and word & 0x800000:
            return True
        if word & 0x3B200000 == 0x38000000 and (word >> 10) & 3 in (1, 3):
            return True
    return False


def vector_zero(words, pc, register):
    for position in range(pc - 4, min(words) - 1, -4):
        word = words[position]
        if word & 0xFFFFFFE0 == 0x6F00E400:
            return word & 31 == register
        if store(word) is None or any(not part[4] for part in store(word)):
            return False
    return False


def untouched_parameter(words, pc, register):
    """Recognize an unchanged entry argument in the simple non-object constructor."""
    for position in range(min(words), pc, 4):
        word = words[position]
        if store(word) is not None or word & 0xFFFFFFE0 == 0x6F00E400:
            continue
        if word & 0xFFC00000 == 0xFD400000:  # LDR D writes only a vector register.
            continue
        if (
            word & 0x9F000000 in (0x10000000, 0x90000000)
            or word & 0x7F000000 in (0x11000000, 0x51000000)
            or word & 0x7FE0FFE0 == 0x2A0003E0
            or word & 0x7F800000 in (0x12800000, 0x52800000, 0x72800000)
        ):
            if word & 31 == register:
                return False
        elif word != 0xD503201F:
            return False
    return True


def descriptor(image, function, target, constant_argument):
    """Read selected pointer fields of one stack literal passed to RegisterType.

    Definitions must dominate the call. Partial/conditional overwrites, later
    backedges, frame movement, unknown stack access and non-stack stores refuse.
    Only direct assertion calls may intervene; no descriptor address is passed
    to those calls. Field origins stay constant or explicit entry parameters.
    """
    words = function_words(image, function)
    calls = [pc for pc, word in words.items() if word & 0x7C000000 == 0x14000000 and pc + signed(word & 0x3FFFFFF, 26) * 4 == target]
    if len(calls) != 1:
        raise ValueError("Expected one metadata registration call")
    call = calls[0]
    if words.get(call - 4) != 0x910003E1:  # ADD x1, SP, 0: the descriptor address.
        raise ValueError("Metadata descriptor is not the current stack literal")
    edges, selected = graph(words), {}
    dominance = dominators(edges)
    if call not in dominance:
        raise ValueError("Metadata registration is unreachable")
    writes = [(pc, part) for pc, word in words.items() if pc < call for part in (store(word) or [])]
    for field in (0, 16, 24, 32, 80):
        overlaps = [(pc, part) for pc, part in writes if part[0] == 31 and part[1] < field + 8 and field < part[1] + part[2]]
        if not overlaps:
            raise ValueError("Missing metadata literal field")
        pc, (base, offset, width, register, vector) = max(overlaps, key=lambda item: item[0])
        if pc not in dominance[call] or offset > field or offset + width < field + 8:
            raise ValueError("Metadata field definition can be skipped or partially overwritten")
        if vector:
            if not vector_zero(words, pc, register):
                raise ValueError("Metadata vector field is not a literal zero")
            origin = ("constant", 0)
        else:
            value = 0 if register == 31 else constant_argument(image, pc, register)
            if value is not None:
                origin = ("constant", value)
            elif untouched_parameter(words, pc, register):
                origin = ("parameter", register)
            else:
                raise ValueError("Unknown metadata field origin")
        selected[field] = (pc, origin)
    first = min(pc for pc, origin in selected.values())
    assertions = image.symbols.get("__Z20AssertImplementationiPKciiS0_", set())
    for pc in range(first, call, 4):
        word = words[pc]
        if changes_frame(word) or any(step <= pc for step in edges[pc]):
            raise ValueError("Metadata frame or control-flow order changes after literal setup")
        parts = store(word)
        if parts and any(part[0] != 31 for part in parts):
            raise ValueError("Potential alias store after metadata literal setup")
        if parts is None and word & 0x0A000000 == 0x08000000 and (word >> 5) & 31 == 31:
            raise ValueError("Unknown stack access after metadata literal setup")
        if word & 0xFC000000 == 0x94000000:
            if pc + signed(word & 0x3FFFFFF, 26) * 4 not in assertions:
                raise ValueError("Unknown call after metadata literal setup")
            for register in (1, 4):
                value = constant_argument(image, pc, register)
                if value is None:
                    raise ValueError("Unknown assertion string argument")
                image.at(value, 1)  # A file-backed literal, never a stack address.
            for register in (2, 3):
                value = constant_argument(image, pc, register)
                if value is None or not 0 <= value <= 0xFFFFFFFF:
                    raise ValueError("Unknown assertion integer argument")
    return {field: origin for field, (pc, origin) in selected.items()}


def extra_records(image, constant_argument, direct_calls):
    target = image.symbol("__ZN11TypeManager12RegisterTypeERK20TypeRegistrationDesc")
    root = descriptor(image, "__ZN6Object16StaticInitializeEv", target, constant_argument)
    function = "__ZN11TypeManager21RegisterNonObjectTypeEiP4RTTIPKcS3_"
    template = descriptor(image, function, target, constant_argument)

    def row(fields, caller=None):
        values = {}
        for field, (kind, value) in fields.items():
            if kind == "parameter":
                if caller is None:
                    raise ValueError("Root metadata unexpectedly depends on an entry argument")
                value = constant_argument(image, caller, value)
                if value is None:
                    raise ValueError("Unknown non-object registration argument")
            elif kind != "constant":
                raise ValueError("Unqualified metadata origin kind")
            values[field] = value
        if values[0] != 0:
            raise ValueError("Unexpected extra native parent pointer")
        name, namespace, module = (image.string(values[field]) for field in (16, 24, 32))
        image.at(values[80], 80)
        return {
            "symbol": function if caller is not None else "__ZN6Object16StaticInitializeEv",
            "self": values[80],
            "parent": values[0],
            "name": name,
            "nativeNamespace": namespace,
            "qualifiedName": (namespace + "::" if namespace else "") + name,
            "module": module,
        }

    calls = direct_calls(image, {image.symbol(function)})
    if len(calls) != 12:
        raise ValueError("Pinned SDK non-object registration count differs")
    return [row(root)] + [row(template, pc) for pc, target in calls]
