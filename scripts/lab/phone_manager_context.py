"""Read manager registration declarations from a pinned owner SDK as data.

This does not evaluate manager state, target support or object retention, and
never supplies project/linker roots or executes an inspected SDK instruction.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

_spec = importlib.util.spec_from_file_location("_manager_context_operands", Path(__file__).with_name("phone_wrapper_population.py"))
operands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(operands)  # Authored sibling tooling only, never SDK code.

registry, literals = operands.registry, operands.literals
INITIALIZE = "__ZN14ManagerContext17InitializeClassesEv"
LOOKUP = "__ZNK11TypeManager15ClassNameToRTTIEPKcb"
CONTEXT = "__Z21GetManagerFromContexti"
ASSET_DEPENDENCIES = "__Z43ShouldIncludeGlobalManagerAssetDependenciesi"
SOURCES = (
    "phone_manager_context.py",
    "phone_wrapper_population.py",
    "phone_registry.py",
    "phone_registry_literals.py",
    "phone_wrapper_search.py",
    "phone_native_flags.py",
    "phone_managed_types.py",
)


def capacity(image, words):
    """Read the context argument's positive bound, followed by its LT guard."""
    matches = []
    reader = operands.Origins(image, words)
    for pc, word in words.items():
        if word & 0xFFC003FF == 0x7100001F and words.get(pc + 4, 0) & 0xFF00001F == 0x5400000B:
            count = (word >> 10) & 4095
            target = pc + 4 + registry.signed((words[pc + 4] >> 5) & 0x7FFFF, 19) * 4
            if not 0 < count <= 64 or target <= pc + 4 or target not in words or reader.origin(pc, 0) != ("parameter", 0):
                raise ValueError("Unsupported manager context bound/guard")
            matches.append(count)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous manager context capacity")
    return matches[0]


def pointer_store(word):
    if word & 0xFFC00000 != 0xF9000000:
        return None
    return word & 31, (word >> 5) & 31, ((word >> 10) & 4095) * 8


def entries(image, words, count, lookup):
    """Keep explicit lookup/result/name store associations, including indices.

    Call order is deliberately not used as context order. The SDK registers
    level and some later global managers in a different declaration order.
    """
    reader = operands.Origins(image, words)
    found = {}
    for pc in operands.calls(words, lookup):
        name_address = reader.constant(pc, 1)
        name = operands.search.cstring(image, name_address)
        if not name or reader.constant(pc, 2) != 0:
            raise ValueError("Unknown manager lookup name/options")
        stores = []
        for position in range(pc + 4, pc + 20, 4):
            word = words.get(position, 0)
            store = pointer_store(word)
            if store is not None:
                stores.append((position, *store))
                if len(stores) == 2:
                    break
            elif word & 0xFF800000 != 0xD2800000 or word & 31 == 31:
                raise ValueError("Unknown instruction between manager lookup/stores")
            # A literal MOV may initialize another local between the call and
            # stores. Operand proofs below still reject a clobbered result,
            # context pointer or registered name; branches/calls cannot pass.
        if len(stores) != 2:
            raise ValueError("Incomplete manager registration stores")
        type_pc, type_register, type_base, type_offset = stores[0]
        name_pc, name_register, name_base, name_offset = stores[1]
        if (
            reader.origin(type_pc, type_register) != ("call", pc, lookup)
            or reader.origin(type_pc, type_base) != ("parameter", 0)
            or reader.origin(name_pc, name_base) != ("parameter", 0)
            or reader.constant(name_pc, name_register) != name_address
        ):
            raise ValueError("Manager registration source/context differs")
        index, remainder = divmod(type_offset - count * 8, 8)
        if remainder or not 0 <= index < count or name_offset != count * 16 + index * 8 or index in found:
            raise ValueError("Invalid, repeated or mismatched manager slot")
        found[index] = dict(context_index=index, name=name, name_address=name_address, lookup_pc=pc, type_offset=type_offset, name_offset=name_offset)
    if set(found) != set(range(count)) or len({r["name"] for r in found.values()}) != count:
        raise ValueError("Manager registration declaration coverage differs")
    return [found[i] for i in range(count)]


def dependency_exclusions(image, words, count):
    """Decode only the pinned pair-of-inequalities metadata predicate."""
    ordered = sorted(words)
    if len(ordered) != 9 or ordered != list(range(min(words), max(words) + 4, 4)):
        raise ValueError("Unknown manager dependency predicate extent")
    w = [words[pc] for pc in ordered]
    base = w[0] & 31
    if (
        base in (0, 31)
        or w[0] & 0x9F000000 != 0x90000000
        or w[1] & 0xFFC00000 != 0x91000000
        or w[1] & 31 != base
        or (w[1] >> 5) & 31 != base
        or w[2] & 0xFFC00000 != 0x29400000
        or (w[2] >> 5) & 31 != base
        or (w[2] >> 15) & 127
    ):
        raise ValueError("Unknown manager dependency literal load")
    first, second = w[2] & 31, (w[2] >> 10) & 31
    if not (0 < first < 31 and 0 < second < 31 and first != second):
        raise ValueError("Aliased manager dependency predicate registers")
    expected = [
        0x6B00001F | first << 5,
        0x1A9F07E0 | first,
        0x6B00001F | second << 5,
        0x1A9F07E0 | second,
        0x0A000000 | second << 16 | first << 5,
        0xD65F03C0,
    ]
    if w[3:] != expected:
        raise ValueError("Unknown manager dependency predicate operations")
    immediate = registry.signed(((w[0] >> 5) & 0x7FFFF) << 2 | ((w[0] >> 29) & 3), 21)
    address = (ordered[0] & ~4095) + immediate * 4096 + ((w[1] >> 10) & 4095)
    values = struct.unpack("<2I", image.at(address, 8))
    if len(set(values)) != 2 or any(value >= count for value in values):
        raise ValueError("Invalid manager dependency exclusion indices")
    return dict(address=address, context_indices=list(values))


def classify(declarations, rows):
    registry.validate_persistent_ids(rows)
    pointers = {r["self"]: r for r in rows}
    if len(pointers) != len(rows):
        raise ValueError("Repeated native registry pointer")
    by_name = {}
    for row in rows:
        by_name.setdefault(row["name"], []).append(row)
    roots = {}
    for name, role in (("GlobalGameManager", "global"), ("LevelGameManager", "level")):
        if len(by_name.get(name, [])) != 1:
            raise ValueError("Missing or ambiguous native manager base")
        roots[by_name[name][0]["self"]] = role
    result = []
    for declaration in declarations:
        matches = by_name.get(declaration["name"], [])
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous declared native manager")
        row, seen, roles = matches[0], set(), set()
        node = row
        while True:
            if node["self"] in seen:
                raise ValueError("Cyclic native manager ancestry")
            seen.add(node["self"])
            if node["self"] in roots:
                roles.add(roots[node["self"]])
            if not node["parent"]:
                break
            if node["parent"] not in pointers:
                raise ValueError("Missing native manager parent")
            node = pointers[node["parent"]]
        if len(roles) != 1:
            raise ValueError("Declared native type has no unique manager role")
        result.append(dict(declaration, persistent_type_id=row["persistentTypeID"], qualified_name=row["qualifiedName"], role=roles.pop()))
    global_count = sum(r["role"] == "global" for r in result)
    if not 0 < global_count < len(result) or [r["role"] for r in result] != ["global"] * global_count + ["level"] * (len(result) - global_count):
        raise ValueError("Manager role/index partition differs")
    return result, global_count


def decode(image):
    count = capacity(image, literals.function_words(image, CONTEXT))
    declarations = entries(image, literals.function_words(image, INITIALIZE), count, image.symbol(LOOKUP))
    rows = registry.static_records(image) + literals.extra_records(image, registry.call_argument, registry.direct_calls)
    if len(rows) != 318:
        raise ValueError("Pinned native registry coverage differs")
    registrations, global_count = classify(declarations, rows)
    exclusions = dependency_exclusions(image, literals.function_words(image, ASSET_DEPENDENCIES), global_count)
    return dict(
        context_capacity=count,
        global_count=global_count,
        level_count=count - global_count,
        registrations=registrations,
        asset_dependency_exclusions=dict(exclusions, native_types=[registrations[i]["persistent_type_id"] for i in exclusions["context_indices"]]),
    )


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private manager metadata report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in SOURCES}
    result = decode(registry.MachO(data))
    if binary.read_bytes() != data or any(hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != value for name, value in sources.items()):
        raise ValueError("Manager SDK or reader source drift")
    result.update(
        schema=1,
        profile="manager-context-declarations-v1",
        binary_sha256=registry.BINARY_SHA256,
        sources=sources,
        executes_sdk=False,
        live_context_qualified=False,
        target_retention_qualified=False,
        root_generation_qualified=False,
    )
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: phone_manager_context.py OWNER_SDK_BINARY NEW_PRIVATE_REPORT")
    result = inspect(*sys.argv[1:])
    print(json.dumps({key: result[key] for key in ("context_capacity", "global_count", "level_count", "root_generation_qualified")}))
