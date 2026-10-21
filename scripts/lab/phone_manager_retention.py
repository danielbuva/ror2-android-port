"""Experimental support: read SDK manager bindings, never manager state or roots.

Android/host: python3 -I -S phone_manager_retention.py OWNER_SDK NEW_REPORT.json
Only explicit authored sibling tooling is loaded; inspected SDK code is data.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

_spec = importlib.util.spec_from_file_location("_retention_context", Path(__file__).with_name("phone_manager_context.py"))
context = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(context)
operands = context.operands
registry, literals, search = context.registry, context.literals, operands.search
CONSUMERS = ("__Z36CompileGlobalGameManagerDependencies", "__Z28CompileGlobalGameManagerFile")
METHOD = "ShouldWriteForBuild"
SOURCES = ("phone_manager_retention.py", *context.SOURCES)


def encoded_type(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*", name):
        raise ValueError("Unsupported manager ABI type name")
    return "".join(str(len(part)) + part for part in name.split("::"))


def unique_symbol(image, prefix):
    matches = [name for name in image.symbols if name.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous manager consumer")
    return matches[0]


def load(word):
    if word & 0xFFC00000 != 0xF9400000:
        return None
    return word & 31, (word >> 5) & 31, ((word >> 10) & 4095) * 8


def effects(word):
    value = search.effects(word)
    if value is not None:
        return value
    # Public integer instruction families: destination effects only. No result
    # is inferred from ADD/SUB-register, logical-immediate or bitfield arithmetic.
    if word & 0x7F200000 in (0x0B000000, 0x4B000000) or word & 0x7F800000 in (0x12000000, 0x53000000):
        return {word & 31}
    return None


class ManagerOrigins:
    """Prove a nonzero object source; unknown effects or paths refuse."""

    def __init__(self, words, dominance):
        self.words, self.dominance = words, dominance

    def origin(self, use, register, budget=32):
        if budget <= 0 or not 0 <= register < 31 or use not in self.dominance:
            raise ValueError("Unqualified manager operand")
        for pc in range(use - 4, min(self.words) - 1, -4):
            word = self.words[pc]
            changes = effects(word)
            if changes is None:
                raise ValueError("Unknown manager operand effect")
            if register not in changes:
                continue
            if pc not in self.dominance[use]:
                raise ValueError("Manager operand definition can be skipped")
            if word & 0xFC000000 == 0x94000000:
                if register != 0:
                    raise ValueError("Manager operand escaped a clobbering call")
                return ("call", pc + registry.signed(word & 0x3FFFFFF, 26) * 4)
            source = search.move(word)
            if source is not None:
                return self.origin(pc, source, budget - 1)
            if word & 0xFFE00C00 == 0x9A800000 and (word >> 16) & 31 == 31:
                # A CSEL between this pointer and zero preserves the origin of
                # a nonzero result. The condition/result is not evaluated.
                return ("nullable", self.origin(pc, (word >> 5) & 31, budget - 1))
            raise ValueError("Unknown manager object producer")
        return ("parameter", register)


def dispatch(image, words):
    indirect = [pc for pc, word in words.items() if word & 0xFFFFFC1F == 0xD63F0000]
    if len(indirect) != 1:
        raise ValueError("Expected one bounded manager virtual call")
    call = indirect[0]
    first, second = load(words.get(call - 12, 0)), load(words.get(call - 8, 0))
    move = words.get(call - 4, 0)
    if (
        first is None
        or second is None
        or first[2] != 0
        or second[1] != first[0]
        or second[0] != (words[call] >> 5) & 31
        or move & 31 != 0
        or search.move(move) != first[1]
        or any(register == 31 for register in (*first[:2], *second[:2]))
    ):
        raise ValueError("Manager virtual receiver or load sequence differs")
    # BLR has a normal return edge for this graph only. No SDK bytes are changed
    # or executed. Indirect branches elsewhere still refuse in graph().
    flow = dict(words)
    flow[call] = 0xD503201F
    dominance = literals.dominators(literals.graph(flow))
    if call not in dominance or any(pc not in dominance[call] for pc in (call - 12, call - 8, call - 4)):
        raise ValueError("Manager virtual definition can be skipped")
    origin = ManagerOrigins(words, dominance).origin(call - 12, first[1])
    expected = ("nullable", ("call", image.symbol(context.CONTEXT)))
    if origin != expected:
        raise ValueError("Virtual receiver is not the nullable manager-context result")
    if second[2] % 8 or second[2] == 0:
        raise ValueError("Unqualified manager virtual offset")
    return dict(
        call=call,
        receiver_register=first[1],
        vptr_offset=first[2],
        function_offset=second[2],
        nonzero_receiver_source="manager-context",
        nullable_receiver=True,
    )


def table_binding(image, row, records, offset):
    name = row["qualified_name"]
    encoding = encoded_type(name)
    suffix = "N" + encoding + "E" if "::" in name else encoding
    table = image.symbol("__ZTV" + suffix)
    typeinfo = image.symbol("__ZTI" + suffix)
    typename = image.symbol("__ZTS" + suffix)
    ends = [address for address in image.symbol_addresses if address > table]
    if not ends or not 16 < min(ends) - table <= 16384 or (min(ends) - table) % 8:
        raise ValueError("Unqualified manager vtable extent")
    # Require this complete primary table's exact RTTI identity. This is not a
    # general assumption that every ABI table has only two header words.
    if struct.unpack("<2Q", image.at(table, 16)) != (0, typeinfo) or struct.unpack("<Q", image.at(typeinfo + 8, 8))[0] != typename:
        raise ValueError("Manager primary vtable/typeinfo identity differs")
    if search.cstring(image, typename) != suffix:
        raise ValueError("Manager RTTI type-name identity differs")
    address_point = table + 16
    if offset < 0 or offset % 8 or address_point + offset + 8 > min(ends):
        raise ValueError("Manager dispatch escapes its primary vtable")
    target = struct.unpack("<Q", image.at(address_point + offset, 8))[0]
    by_name = {r["qualifiedName"]: r for r in records}
    by_pointer = {r["self"]: r for r in records}
    if len(by_name) != len(records) or len(by_pointer) != len(records) or name not in by_name:
        raise ValueError("Missing or ambiguous manager native ancestry")
    if row["persistent_type_id"] != by_name[name]["persistentTypeID"]:
        raise ValueError("Manager declaration/native identity differs")
    current, visited, matches = by_name[name], set(), []
    while True:
        if current["self"] in visited:
            raise ValueError("Cyclic manager native ancestry")
        visited.add(current["self"])
        symbol = "__ZNK" + encoded_type(current["qualifiedName"]) + str(len(METHOD)) + METHOD + "Ev"
        if symbol in image.symbols and image.symbol(symbol) == target:
            matches.append((current["qualifiedName"], symbol))
        if not current["parent"]:
            break
        if current["parent"] not in by_pointer:
            raise ValueError("Missing manager native parent")
        current = by_pointer[current["parent"]]
    if len(matches) != 1:
        raise ValueError("Manager write target is missing or ambiguous in native ancestry")
    owner, symbol = matches[0]
    return dict(
        context_index=row["context_index"],
        persistent_type_id=row["persistent_type_id"],
        qualified_name=name,
        role=row["role"],
        vtable=table,
        address_point=address_point,
        function_offset=offset,
        implementation_owner=owner,
        implementation_symbol=symbol,
        implementation_address=target,
    )


def decode(image):
    declarations = context.decode(image)
    consumers = []
    for prefix in CONSUMERS:
        name = unique_symbol(image, prefix)
        consumers.append(dict(symbol=name, **dispatch(image, literals.function_words(image, name))))
    offsets = {row["function_offset"] for row in consumers}
    if len(offsets) != 1:
        raise ValueError("Manager build consumers use different virtual offsets")
    records = registry.static_records(image) + literals.extra_records(image, registry.call_argument, registry.direct_calls)
    bindings = [table_binding(image, row, records, consumers[0]["function_offset"]) for row in declarations["registrations"]]
    return dict(global_count=declarations["global_count"], level_count=declarations["level_count"], consumers=consumers, bindings=bindings)


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private manager retention report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in SOURCES}
    result = decode(registry.MachO(data))
    if binary.read_bytes() != data or any(
        hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest for name, digest in sources.items()
    ):
        raise ValueError("Manager retention SDK or source drift")
    result.update(
        schema=1,
        profile="manager-write-bindings-v1",
        binary_sha256=registry.BINARY_SHA256,
        sources=sources,
        executes_sdk=False,
        normal_control_flow_only=True,
        live_context_qualified=False,
        target_retention_qualified=False,
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
    report = inspect(*sys.argv[1:])
    print(json.dumps({key: report[key] for key in ("profile", "global_count", "level_count", "root_generation_qualified")}))
