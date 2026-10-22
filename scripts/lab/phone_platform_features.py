"""Experimental static platform-define declarations from a pinned owner SDK.

No SDK instruction executes; target discovery, type/state retention and roots
remain unqualified. Android/host: python3 -I -S THIS.py OWNER_SDK NEW_REPORT.json
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

_spec = importlib.util.spec_from_file_location("_feature_retention", Path(__file__).with_name("phone_manager_retention.py"))
retention = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retention)
registry, literals, search = retention.registry, retention.literals, retention.search
FUNCTION = "__Z18GetPlatformDefinesPKcR13dynamic_arrayIS0_Lm0EE"
GROW = "__ZN13dynamic_arrayIPKcLm0EE4growEv"
RESERVE = "__ZN20dynamic_array_detail18dynamic_array_data7reserveEmmm"
ASSERT = "__Z20AssertImplementationiPKciiS0_"
SOURCES = ("phone_platform_features.py", *retention.SOURCES)


def literal(image, address):
    """Require a bounded ASCII literal in a declared file-backed C-string section."""
    commands = struct.unpack_from("<I", image.data, 16)[0]
    position = 32
    for _ in range(commands):
        command, length = struct.unpack("<2I", image.take(position, 8))
        if command == 0x19:
            count = struct.unpack("<I", image.take(position + 64, 4))[0]
            for index in range(count):
                at = position + 72 + index * 80
                start, size, offset = struct.unpack("<QQI", image.take(at + 32, 20))
                flags = struct.unpack("<I", image.take(at + 64, 4))[0]
                if flags & 255 == 2 and start <= address < start + size:
                    if image.at(start, size) != image.take(offset, size):
                        raise ValueError("Literal section is not file backed")
                    raw = image.at(address, min(256, start + size - address))
                    end = raw.find(b"\0")
                    if end < 0:
                        raise ValueError("Unterminated declaration literal")
                    return raw[:end].decode("ascii")
        position += length
    raise ValueError("Declaration pointer is outside a literal section")


def imported_stub(image, symbol):
    """Bind a Mach-O external stub through LC_DYSYMTAB, never guessed code bytes."""
    commands = struct.unpack_from("<I", image.data, 16)[0]
    position, symtab, indirect, stubs, libraries = 32, None, None, [], []
    for _ in range(commands):
        command, length = struct.unpack("<2I", image.take(position, 8))
        if command == 2:
            symtab = struct.unpack("<4I", image.take(position + 8, 16))
        elif command == 0xB:
            if length != 80 or indirect is not None:
                raise ValueError("Invalid indirect-symbol command")
            indirect = struct.unpack("<2I", image.take(position + 56, 8))
        elif command == 0x19:
            count = struct.unpack("<I", image.take(position + 64, 4))[0]
            for index in range(count):
                at = position + 72 + index * 80
                address, size, offset = struct.unpack("<QQI", image.take(at + 32, 20))
                flags, first, stride = struct.unpack("<3I", image.take(at + 64, 12))
                if flags & 255 == 8:
                    if not 0 < stride <= 64 or stride % 4 or size % stride or image.at(address, size) != image.take(offset, size):
                        raise ValueError("Invalid file-backed symbol-stub section")
                    stubs.append((address, size // stride, first, stride))
        elif command in (0xC, 0x80000018, 0x8000001F, 0x80000023):
            name_offset = struct.unpack("<I", image.take(position + 8, 4))[0]
            raw = image.take(position + name_offset, length - name_offset)
            end = raw.find(b"\0")
            if not 24 <= name_offset < length or end < 0:
                raise ValueError("Invalid imported-library name")
            libraries.append(raw[:end].decode("ascii"))
        position += length
    if symtab is None or indirect is None or not stubs:
        raise ValueError("Missing external stub metadata")
    symoff, count, stroff, strsize = symtab
    indices = image.take(indirect[0], indirect[1] * 4)
    strings = image.take(stroff, strsize)
    matches = []
    for base, number, first, stride in stubs:
        if first + number > indirect[1]:
            raise ValueError("Stub indices escape indirect-symbol table")
        for index in range(number):
            entry = struct.unpack_from("<I", indices, (first + index) * 4)[0]
            if entry & 0xC0000000:
                continue  # Local/absolute entries cannot bind this external symbol.
            if entry >= count:
                raise ValueError("Invalid indirect symbol index")
            name_at, kind, section, description, value = struct.unpack("<IBBHQ", image.take(symoff + entry * 16, 16))
            if name_at >= len(strings) or strings.find(b"\0", name_at) < 0:
                raise ValueError("Invalid imported-symbol name")
            name = strings[name_at : strings.index(b"\0", name_at)].decode("ascii")
            if name != symbol:
                continue
            ordinal = description >> 8
            if kind != 1 or section or value or not 1 <= ordinal <= len(libraries) or not libraries[ordinal - 1].endswith("/libSystem.B.dylib"):
                raise ValueError("Comparison import is not an undefined libSystem external")
            matches.append(base + index * stride)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous comparison stub")
    return matches[0]


def generated_words(image, name):
    start = image.symbol(name)
    following = [address for address in image.symbol_addresses if address > start]
    if not following or not 0 < min(following) - start <= 131072 or (min(following) - start) % 4:
        raise ValueError("Unqualified generated-declaration extent")
    end = min(following)
    if len(image.sections) != 1 or not image.sections[0][0] <= start < end <= image.sections[0][0] + image.sections[0][1]:
        raise ValueError("Generated declarations escape the instruction section")
    return {pc: struct.unpack("<I", image.at(pc, 4))[0] for pc in range(start, end, 4)}


def call_target(words, pc):
    word = words.get(pc, 0)
    return pc + registry.signed(word & 0x3FFFFFF, 26) * 4 if word & 0xFC000000 == 0x94000000 else None


def pair_constant(words, pc):
    first, second = words.get(pc, 0), words.get(pc + 4, 0)
    register = first & 31
    if first & 0x9F000000 != 0x90000000 or second & 0xFFC00000 != 0x91000000 or second & 31 != register or (second >> 5) & 31 != register or register == 31:
        raise ValueError("Unknown declaration pointer materialization")
    page = (pc & ~4095) + registry.signed(((first >> 5) & 0x7FFFF) << 2 | (first >> 29) & 3, 21) * 4096
    return register, page + ((second >> 10) & 4095)


def branch_target(word, pc, form):
    if form == "cbnz" and word & 0xFF00001F == 0x35000000:
        return pc + registry.signed((word >> 5) & 0x7FFFF, 19) * 4
    if form == "conditional" and word & 0xFF000010 == 0x54000000:
        return pc + registry.signed((word >> 5) & 0x7FFFF, 19) * 4
    if form == "direct" and word & 0xFC000000 == 0x14000000:
        return pc + registry.signed(word & 0x3FFFFFF, 26) * 4
    raise ValueError("Unknown declaration branch form")


def selectors(image, words, strcmp):
    calls = [pc for pc in words if call_target(words, pc) == strcmp]
    result = []
    for pc in calls:
        register, pointer = pair_constant(words, pc - 16)
        if search.move(words.get(pc - 8, 0)) != register or words[pc - 8] & 31 != 0 or words.get(pc - 4, 0) & 31 != 1:
            raise ValueError("Comparison literal argument differs")
        receiver = search.move(words[pc - 4])
        if receiver is None or not 19 <= receiver <= 28:
            raise ValueError("Comparison receiver is not preserved by the ABI")
        branch = pc + 4
        hoisted = []
        if words.get(branch, 0) & 0x9F000000 == 0x90000000:
            hoisted.append(pair_constant(words, branch))
            branch += 8
        following = branch_target(words.get(branch, 0), branch, "cbnz")
        name = literal(image, pointer)
        if not name or not all(c.isupper() or c.isdigit() or c == "_" for c in name):
            raise ValueError("Unknown selector string")
        result.append(
            dict(
                name=name,
                call=pc,
                literal_register=register,
                literal_pointer=pointer,
                receiver=receiver,
                hoisted=hoisted,
                branch=branch,
                start=branch + 4,
                end=following,
            )
        )
    if not result or len({row["name"] for row in result}) != len(result) or len({row["receiver"] for row in result}) != 1:
        raise ValueError("Missing, duplicate or mismatched platform selectors")
    for index, row in enumerate(result):
        expected = result[index + 1]["call"] - 16 if index + 1 < len(result) else row["end"]
        if row["end"] != expected or not row["start"] < row["end"] <= max(words):
            raise ValueError("Platform selector skips or overlaps another case")
    return result


def feature_effects(word):
    value = retention.effects(word)
    if value is not None:
        return value
    if word & 0xFFE00C00 == 0xF8400C00:  # 64-bit pre-index LDR writes base and destination.
        return {word & 31, (word >> 5) & 31}
    return None


def parameter_origin(words, dominance, use, register, budget=32):
    if budget <= 0 or register == 31 or use not in dominance:
        raise ValueError("Unqualified declaration parameter")
    for pc in range(use - 4, min(words) - 1, -4):
        word = words[pc]
        writes = feature_effects(word)
        if writes is None:
            raise ValueError("Unknown declaration parameter effect")
        if register not in writes:
            continue
        if pc not in dominance[use]:
            raise ValueError("Declaration parameter definition can be skipped")
        source = search.move(word)
        if source is not None:
            return parameter_origin(words, dominance, pc, source, budget - 1)
        if word & 0xFFE00C00 == 0xF8400C00 and register == (word >> 5) & 31 and register != word & 31:
            offset = registry.signed((word >> 12) & 511, 9)
            return ("offset", parameter_origin(words, dominance, pc, register, budget - 1), offset)
        raise ValueError("Unknown declaration parameter producer")
    return ("parameter", register)


def indexed_store(word):
    if word & 0xFFE0FC00 != 0xF8207800:
        return None
    return word & 31, (word >> 5) & 31, (word >> 16) & 31


def macro(image, pointer):
    value = literal(image, pointer)
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value):
        raise ValueError("Unknown feature declaration token")
    return value


def append_records(image, words, case, immutable):
    """Read only literal pointer appends in one closed selector body.

    No vector or SDK call is executed. Overflow diagnostics and growth side
    paths must rejoin this same append; unknown effects never supply a token.
    """
    out, platform = immutable
    cursor = case["start"]
    constants = {case["literal_register"]: case["literal_pointer"], **dict(case["hoisted"])}
    records, growth, capacity_base, fields = [], [], None, None
    while cursor < case["end"]:
        old = retention.load(words.get(cursor, 0))
        add = words.get(cursor + 4, 0)
        if old is None or old[1] != out or add & 0xFFC00000 != 0xB1000000 or (add >> 10) & 4095 != 1 or (add >> 5) & 31 != old[0]:
            raise ValueError("Unknown pointer-append size definition")
        previous, size_field = old[0], old[2]
        updated = add & 31
        if previous == updated or not 0 < size_field <= 64 or any(not 19 <= register <= 28 or register in immutable for register in (previous, updated)):
            raise ValueError("Append indices are not independent preserved values")
        constants.pop(previous, None)
        constants.pop(updated, None)
        overflow = words.get(cursor + 8, 0)
        if overflow & 31 != 3 or branch_target(overflow, cursor + 8, "conditional") != cursor + 44:
            raise ValueError("Unknown append overflow join")
        file_register, file_pointer = pair_constant(words, cursor + 12)
        message_register, message_pointer = pair_constant(words, cursor + 20)
        if (file_register, message_register) != (1, 4) or not literal(image, file_pointer) or not literal(image, message_pointer):
            raise ValueError("Unknown overflow diagnostic strings")
        assertion = cursor + 40
        if call_target(words, assertion) != image.symbol(ASSERT):
            raise ValueError("Unknown call before declaration append")
        values = [registry.call_argument(image, assertion, register, start=cursor + 12) for register in (0, 2, 3)]
        if values[0] != 0 or values[1] is None or not 0 < values[1] <= 65535 or values[2] != 0xFFFFFFFF:
            raise ValueError("Unknown overflow diagnostic arguments")
        constants = {register: value for register, value in constants.items() if 19 <= register <= 28}
        capacity = retention.load(words.get(cursor + 44, 0))
        if capacity is None or capacity[2] != 0 or not 19 <= capacity[1] <= 28 or capacity[1] in (out, platform, previous, updated):
            raise ValueError("Unqualified append capacity reference")
        if capacity_base is not None and capacity[1] != capacity_base:
            raise ValueError("Append capacity receiver changed")
        capacity_base = capacity[1]
        if capacity[0] in (out, platform, previous, updated, capacity_base):
            raise ValueError("Capacity load clobbers a preserved append operand")
        constants.pop(capacity[0], None)
        if words.get(cursor + 48) != 0xEB40041F | capacity[0] << 16 | updated << 5:
            raise ValueError("Unknown append capacity comparison")
        grow_branch = words.get(cursor + 52, 0)
        if grow_branch & 31 != 8:
            raise ValueError("Unknown append growth condition")
        grow = branch_target(grow_branch, cursor + 52, "conditional")
        join = cursor + 56
        if not min(words) <= grow < grow + 8 <= max(words) or case["start"] <= grow < case["end"]:
            raise ValueError("Growth side path escapes its declaration function")
        if (
            search.move(words.get(grow, 0)) != out
            or words[grow] & 31 != 0
            or call_target(words, grow + 4) != image.symbol(GROW)
            or branch_target(words.get(grow + 8, 0), grow + 8, "direct") != join
        ):
            raise ValueError("Growth path does not rejoin its own literal append")
        growth.append(grow)
        if context_store(words.get(join, 0)) != (updated, out, size_field):
            raise ValueError("Append size store differs from its loaded field")
        data = retention.load(words.get(cursor + 60, 0))
        if data is None or data[1] != out or data[2] == size_field or data[0] in (out, platform, capacity_base, previous, updated):
            raise ValueError("Unknown append data pointer")
        constants.pop(data[0], None)
        if fields is not None and fields != (size_field, data[2]):
            raise ValueError("Append vector fields changed")
        fields = (size_field, data[2])
        store = cursor + 64
        if words.get(store, 0) & 0x9F000000 == 0x90000000:
            register, pointer = pair_constant(words, store)
            if register in (out, platform, capacity_base, previous, updated, data[0]):
                raise ValueError("Literal pointer overwrites an append operand")
            constants[register] = pointer
            store += 8
        value = indexed_store(words.get(store, 0))
        if value is None or value[1:] != (data[0], previous) or value[0] not in constants:
            raise ValueError("Append value is not a proven literal pointer")
        records.append(dict(feature=macro(image, constants[value[0]]), pointer=constants[value[0]], start=cursor, store=store))
        cursor = store + 4
    if cursor != case["end"] or not records or len(set(growth)) != len(growth):
        raise ValueError("Missing, overlapping or aliased declaration records")
    return records, growth, capacity_base, fields


def context_store(word):
    return retention.context.pointer_store(word)


def direct_branch(word, pc):
    if word & 0xFC000000 == 0x14000000:
        return pc + registry.signed(word & 0x3FFFFFF, 26) * 4
    if word & 0xFF000010 == 0x54000000 or word & 0x7E000000 == 0x34000000:
        return pc + registry.signed((word >> 5) & 0x7FFFF, 19) * 4
    if word & 0x7E000000 == 0x36000000:
        return pc + registry.signed((word >> 5) & 0x3FFF, 14) * 4
    return None


def entry_bindings(image, words, cases, out, capacity):
    first = cases[0]["call"]
    prefix = {pc: word for pc, word in words.items() if pc <= first}
    dominance = literals.dominators(literals.graph(prefix))
    platform = cases[0]["receiver"]
    if len({out, platform, capacity}) != 3 or any(not 19 <= register <= 28 for register in (out, platform, capacity)):
        raise ValueError("Declaration receivers are not independent ABI-preserved values")
    if parameter_origin(prefix, dominance, first, platform) != ("parameter", 0) or parameter_origin(prefix, dominance, first, out) != ("parameter", 1):
        raise ValueError("Selector/output receivers differ from the input parameters")
    capacity_origin = parameter_origin(prefix, dominance, first, capacity)
    if capacity_origin[:2] != ("offset", ("parameter", 1)) or not 0 < capacity_origin[2] <= 64 or capacity_origin[2] % 8:
        raise ValueError("Capacity receiver is not an output-field address")
    protected = {out, platform, capacity}
    for case in cases:
        if case["literal_register"] in protected or any(register in protected | {0} for register, pointer in case["hoisted"]):
            raise ValueError("Selector materialization clobbers a preserved receiver")
    reserve = []
    for pc, word in prefix.items():
        if pc == first:
            continue
        target = call_target(prefix, pc)
        if target is not None:
            if target != image.symbol(RESERVE) or parameter_origin(prefix, dominance, pc, 0) != ("parameter", 1):
                raise ValueError("Unknown call or receiver in declaration setup")
            arguments = [registry.call_argument(image, pc, register, start=min(prefix)) for register in (1, 2, 3)]
            if arguments[0] is None or not 0 < arguments[0] <= 4096 or arguments[1:] != [8, 8]:
                raise ValueError("Unknown pointer-vector reservation arguments")
            reserve.append(pc)
        # Setup may save registers on the stack, never append hidden output.
        parts = literals.store(word)
        if parts is not None and any(part[0] != 31 for part in parts):
            raise ValueError("Declaration setup writes outside its stack frame")
        if indexed_store(word) is not None:
            raise ValueError("Declaration setup contains an unaccounted pointer append")
        destination = direct_branch(word, pc)
        if destination is not None and destination > first:
            raise ValueError("Setup bypasses platform selection")
    if len(reserve) != 1:
        raise ValueError("Expected one bounded declaration-vector reservation")
    return dict(
        platform_parameter=0,
        output_parameter=1,
        output_register=out,
        platform_register=platform,
        capacity_register=capacity,
        capacity_field=capacity_origin[2],
        reserve_call=reserve[0],
    )


def normal_exit(words, start):
    for pc in range(start, min(start + 64, max(words) + 4), 4):
        word = words[pc]
        if word == 0xD65F03C0:
            return pc + 4
        if word & 0x3A400000 == 0x28400000 and (word >> 5) & 31 == 31 and not word & 0x4000000:
            continue  # Integer register restores from the stack only.
        if word & 0xFFC003FF == 0x910003FF or word == 0xD503201F:
            continue  # SP restoration or alignment NOP, no output mutation.
        raise ValueError("Unmatched selectors do not reach a bounded plain return")
    raise ValueError("Missing declaration normal return")


def closed_body(words, case, records, growth, exit_end):
    allowed = {address + 8 for address in growth}
    for record, address in zip(records, growth):
        if address < exit_end:
            raise ValueError("Growth side path enters another selector or its return")
        # Each literal append ends at store. The fixed prefix is 64 bytes;
        # either a fresh address pair or a preserved literal supplies its value.
        start = record["start"]
        if branch_target(words[address + 8], address + 8, "direct") != start + 56:
            raise ValueError("Growth continuation aliases a different append")
    for pc, word in words.items():
        destination = direct_branch(word, pc)
        if destination is not None and case["start"] <= destination < case["end"] and not case["start"] <= pc < case["end"] and pc not in allowed:
            raise ValueError("Foreign branch enters the selected declaration body")


def decode(image):
    words = generated_words(image, FUNCTION)
    stub = imported_stub(image, "_strcmp")
    cases = selectors(image, words, stub)
    selected = [row for row in cases if row["name"] == "PLATFORM_ANDROID"]
    if len(selected) != 1:
        raise ValueError("Missing or ambiguous Android declaration case")
    case = selected[0]
    first = retention.load(words.get(case["start"], 0))
    if first is None:
        raise ValueError("Unknown Android output receiver")
    out = first[1]
    records, growth, capacity, fields = append_records(image, words, case, (out, case["receiver"]))
    binding = entry_bindings(image, words, cases, out, capacity)
    if binding["capacity_field"] in fields:
        raise ValueError("Declaration vector fields alias")
    exit_end = normal_exit(words, cases[-1]["end"])
    closed_body(words, case, records, growth, exit_end)
    return dict(
        platform_define=case["name"],
        comparison_stub=stub,
        selector_count=len(cases),
        selector_names=[row["name"] for row in cases],
        parameter_bindings=binding,
        size_field=fields[0],
        data_field=fields[1],
        declarations=records,
        growth_paths=growth,
        normal_exit_end=exit_end,
    )


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private platform-feature report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in SOURCES}
    result = decode(registry.MachO(data))
    if binary.read_bytes() != data or any(
        hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest for name, digest in sources.items()
    ):
        raise ValueError("Platform feature SDK or reader source drift")
    result.update(
        schema=1,
        profile="android-platform-feature-declarations-v1",
        binary_sha256=registry.BINARY_SHA256,
        sources=sources,
        executes_sdk=False,
        normal_control_flow_only=True,
        other_platforms_qualified=False,
        target_discovery_qualified=False,
        module_include_qualified=False,
        state_retention_qualified=False,
        native_usage_qualified=False,
        root_generation_qualified=False,
    )
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    inspect(*sys.argv[1:])
