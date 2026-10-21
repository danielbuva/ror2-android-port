"""Read pinned owner-SDK native flags as data; no SDK execution or root producer."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def support(name):
    spec = importlib.util.spec_from_file_location("_flags_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Authored sibling readers only.
    return module


registry = support("phone_registry")
literals = support("phone_registry_literals")
FLAG_FIELDS = (56, 57, 58)
ROOT_CONSTRUCTOR = "__ZN6Object16StaticInitializeEv"
OTHER_CONSTRUCTOR = "__ZN11TypeManager21RegisterNonObjectTypeEiP4RTTIPKcS3_"
REGISTER = "__ZN11TypeManager12RegisterTypeERK20TypeRegistrationDesc"


def pack_flags(values):
    values = tuple(values)
    if len(values) != 3 or any(type(value) is not int or value not in (0, 1) for value in values):
        raise ValueError("Native flag bytes are not three literal booleans")
    return sum(value << bit for bit, value in enumerate(values))


def literal_bytes(image, function, target, fields=FLAG_FIELDS):
    """Prove individual stack bytes, including bytes inside a wider zero store.

    This handles a byte overwrite without treating the surrounding word as
    wholly redefined. Each selected byte must have a dominating constant store.
    Unknown effects, alias stores, frame changes, loops and escaping calls refuse.
    """
    if not fields or len(set(fields)) != len(fields) or any(type(field) is not int or not 0 <= field < 112 for field in fields):
        raise ValueError("Invalid native flag field selection")
    words = literals.function_words(image, function)
    calls = [pc for pc, word in words.items() if word & 0x7C000000 == 0x14000000 and pc + literals.signed(word & 0x3FFFFFF, 26) * 4 == target]
    if len(calls) != 1 or words.get(calls[0] - 4) != 0x910003E1:
        raise ValueError("Expected one registration using the current stack descriptor")
    call = calls[0]
    edges = literals.graph(words)
    dominance = literals.dominators(edges)
    if call not in dominance:
        raise ValueError("Native flag registration is unreachable")
    stores = [(pc, part) for pc, word in words.items() if pc < call for part in (literals.store(word) or [])]
    selected = {}
    for field in fields:
        overlapping = [(pc, part) for pc, part in stores if part[0] == 31 and part[1] <= field < part[1] + part[2]]
        if not overlapping:
            raise ValueError("Missing native flag byte")
        pc, (base, offset, width, register, vector) = max(overlapping, key=lambda item: item[0])
        if pc not in dominance[call]:
            raise ValueError("Native flag byte definition can be skipped")
        if vector:
            if not literals.vector_zero(words, pc, register):
                raise ValueError("Native flag vector is not a literal zero")
            value = 0
        else:
            value = 0 if register == 31 else registry.call_argument(image, pc, register)
            if value is None:
                raise ValueError("Native flag byte has no literal origin")
            value = (value >> (8 * (field - offset))) & 255
        selected[field] = (pc, value)
    first = min(pc for pc, value in selected.values())
    assertions = image.symbols.get("__Z20AssertImplementationiPKciiS0_", set())
    for pc in range(first, call, 4):
        word = words[pc]
        if not literals.known_literal_instruction(word) or literals.changes_frame(word) or any(step <= pc for step in edges[pc]):
            raise ValueError("Unknown effect, frame movement or loop after native flag setup")
        parts = literals.store(word)
        if parts and any(part[0] != 31 for part in parts):
            raise ValueError("Potential alias store after native flag setup")
        if parts is None and word & 0x0A000000 == 0x08000000 and (word >> 5) & 31 == 31:
            raise ValueError("Unknown stack access after native flag setup")
        if word & 0xFC000000 == 0x94000000:
            if pc + literals.signed(word & 0x3FFFFFF, 26) * 4 not in assertions:
                raise ValueError("Unknown call after native flag setup")
            for register in (1, 4):
                value = registry.call_argument(image, pc, register)
                if value is None:
                    raise ValueError("Assertion string argument has no literal origin")
                image.at(value, 1)
            for register in (2, 3):
                value = registry.call_argument(image, pc, register)
                if value is None or not 0 <= value <= 0xFFFFFFFF:
                    raise ValueError("Assertion integer argument has no literal origin")
    return tuple(selected[field][1] for field in fields)


def decode(image):
    records = registry.static_records(image)
    if len(records) != 305:
        raise ValueError("Pinned SDK static flag count differs")
    values = {row["self"]: pack_flags(image.at(image.symbol(row["symbol"]) + FLAG_FIELDS[0], 3)) for row in records}
    extra = literals.extra_records(image, registry.call_argument, registry.direct_calls)
    target = image.symbol(REGISTER)
    root_flags = pack_flags(literal_bytes(image, ROOT_CONSTRUCTOR, target))
    other_flags = pack_flags(literal_bytes(image, OTHER_CONSTRUCTOR, target))
    for row in extra:
        if row["self"] in values:
            raise ValueError("Repeated native flag record")
        values[row["self"]] = root_flags if row["symbol"] == ROOT_CONSTRUCTOR else other_flags
    records += extra
    registry.validate_persistent_ids(records)
    if len(records) != 318 or len(values) != 318 or len(extra) != 13:
        raise ValueError("Pinned SDK native flag identity set differs")
    return [
        {
            "persistentTypeID": row["persistentTypeID"],
            "flags": values[row["self"]],
            "isAbstract": bool(values[row["self"]] & 1),
            "isSealed": bool(values[row["self"]] & 2),
            "isEditorOnly": bool(values[row["self"]] & 4),
        }
        for row in sorted(records, key=lambda value: value["persistentTypeID"])
    ]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private native-flag report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {path.name: sha(path) for path in (Path(__file__), Path(registry.__file__), Path(literals.__file__))}
    rows = decode(registry.MachO(data))
    if sha(binary) != registry.BINARY_SHA256 or any(sha(Path(__file__).with_name(name)) != expected for name, expected in sources.items()):
        raise ValueError("SDK or reader changed during native flag inspection")
    report = {
        "schema": 1,
        "profile": registry.PROFILE,
        "binary_sha256": registry.BINARY_SHA256,
        "sources": sources,
        "executes_sdk": False,
        "flag_metadata_decoded": True,
        "cache_population_qualified": False,
        "root_generation_qualified": False,
        "records": rows,
    }
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: phone_native_flags.py OWNER_SDK_BINARY NEW_PRIVATE_REPORT.json")
    result = inspect(*sys.argv[1:])
    print(json.dumps({"records": len(result["records"]), "executes_sdk": False, "root_generation_qualified": False}))
