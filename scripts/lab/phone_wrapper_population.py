"""Reconstruct the pinned SDK wrapper cache from owner inputs, without SDK execution.

Forward cache entries, direct names and reverse registrations remain separate.
This experimental reader is not a scene-usage or linker-root producer.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def support(name):
    spec = importlib.util.spec_from_file_location("_population_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registry = support("phone_registry")
literals = support("phone_registry_literals")
search = support("phone_wrapper_search")
flags = support("phone_native_flags")
metadata = support("phone_managed_types")
REBUILD = "__ZN16ScriptingManager33RebuildNativeTypeToScriptingClassEv"
DERIVED = "__ZNK5Unity4Type21FindAllDerivedClassesER13dynamic_arrayIPKS0_Lm0EENS0_17TypeFilterOptionsE"
ADD = "__ZN16ScriptingManager43AddOutOfHierarchyNativeTypeToScriptingClassEPKN5Unity4TypeE17ScriptingClassPtr"
COMMON = "__Z25GetCommonScriptingClassesv"
CORLIB = "__Z36FillCommonScriptingClassesCorlibOnlyR22CommonScriptingClasses"
REQUIRE = "__ZL17RequireCorLibTypePKcS0_"
OPTIONAL = "__Z12OptionalTypePKcS0_S0_"
MANAGED_SET_SHA256 = "76d7a57034a225897e082df2f8c3937b1a949382cd68cb58ffec4ba18d997790"


def calls(words, target):
    return [pc for pc, word in words.items() if word & 0xFC000000 == 0x94000000 and pc + registry.signed(word & 0x3FFFFFF, 26) * 4 == target]


class Origins:
    """Prove a few ABI operands; unknown instructions/paths never supply values."""

    def __init__(self, image, words):
        self.image, self.words = image, words
        self.dominance = literals.dominators(literals.graph(words))

    def origin(self, use, register, budget=64):
        if budget <= 0 or register == 31 or use not in self.dominance:
            raise ValueError("Unqualified cache operand")
        for pc in range(use - 4, min(self.words) - 1, -4):
            word = self.words[pc]
            effects = search.effects(word)
            if effects is None:
                raise ValueError("Unknown instruction before cache operand")
            if register not in effects:
                continue
            if pc not in self.dominance[use]:
                raise ValueError("Cache operand can be redefined on another path")
            if word & 0xFC000000 == 0x94000000:
                if register != 0:
                    raise ValueError("Caller-saved cache operand escaped a call")
                return ("call", pc, pc + registry.signed(word & 0x3FFFFFF, 26) * 4)
            source = search.move(word)
            if source is not None:
                return self.origin(pc, source, budget - 1)
            rd, rn = word & 31, (word >> 5) & 31
            if word & 0xFFC00000 == 0xF9400000:
                return ("load", self.origin(pc, rn, budget - 1), ((word >> 10) & 4095) * 8)
            if word & 0x9F000000 in (0x10000000, 0x90000000):
                value = registry.signed(((word >> 5) & 0x7FFFF) << 2 | ((word >> 29) & 3), 21)
                return ("constant", (pc & ~4095) + value * 4096 if word & 0x80000000 else pc + value)
            if word & 0xFFC00000 == 0x91000000:
                base = self.origin(pc, rn, budget - 1)
                if base[0] == "constant":
                    return ("constant", base[1] + ((word >> 10) & 4095))
            if word & 0x7F800000 in (0x12800000, 0x52800000):
                value = registry.call_argument(self.image, pc + 4, rd)
                if value is not None:
                    return ("constant", value)
            raise ValueError("Unsupported cache operand definition")
        return ("parameter", register)

    def constant(self, use, register):
        value = self.origin(use, register)
        if value[0] != "constant":
            raise ValueError("Cache operand is not a literal")
        return value[1]

    def strings(self, use, registers):
        return [search.cstring(self.image, self.constant(use, register)) for register in registers]


def common_field(image, offset):
    words = literals.function_words(image, CORLIB)
    candidates = []
    for pc, word in words.items():
        parts = literals.store(word)
        if parts is None:
            continue
        for base, field, width, register, vector in parts:
            if field != offset or width != 8 or vector or base == 31:
                continue
            # Only the assignment prefix is relevant. A later indirect call is
            # not silently reinterpreted as a direct call or a source value.
            prefix = {address: value for address, value in words.items() if address <= pc}
            origins = Origins(image, prefix)
            if origins.origin(pc, base) == ("parameter", 0):
                source = origins.origin(pc, register)
                if source[0] != "call" or source[2] != image.symbol(REQUIRE):
                    raise ValueError("Common cache field has another producer")
                candidates.append(origins.strings(source[1], (0, 1)))
    if len(candidates) != 1:
        raise ValueError("Missing or ambiguous common cache field")
    namespace, name = candidates[0]
    return {"kind": "corlib", "namespace": namespace, "name": name}


def proxy_slot(image, address):
    names = [name for name, values in image.symbols.items() if values == {address} and name.endswith("16s_ScriptingClassE")]
    if len(names) != 1:
        raise ValueError("Missing or ambiguous proxy class slot")
    initializer = names[0].removesuffix("16s_ScriptingClassE") + "9InitProxyEv"
    words = literals.function_words(image, initializer)
    origins = Origins(image, words)
    found = []
    for pc, word in words.items():
        for base, offset, width, register, vector in literals.store(word) or []:
            if width != 8 or vector or base == 31:
                continue
            pointer = origins.origin(pc, base)
            if pointer[0] != "constant" or pointer[1] + offset != address:
                continue
            value = origins.origin(pc, register)
            if value[0] != "call" or value[2] != image.symbol(OPTIONAL):
                raise ValueError("Proxy class slot has another producer")
            assembly, namespace, name = origins.strings(value[1], (0, 1, 2))
            found.append({"kind": "assembly", "assembly": assembly, "namespace": namespace, "name": name})
    if len(found) != 1:
        raise ValueError("Missing or ambiguous proxy initialization")
    return found[0]


def profile(image):
    words = literals.function_words(image, REBUILD)
    origins = Origins(image, words)
    population = calls(words, image.symbol(DERIVED))
    if len(population) != 1 or registry.call_argument(image, population[0], 2) != 0:
        raise ValueError("Pinned all-descendant population option differs")
    root = origins.constant(population[0], 0)
    extras = []
    for pc in calls(words, image.symbol(ADD)):
        native = origins.constant(pc, 1)
        source = origins.origin(pc, 2)
        if source[0] == "call" and source[2] == image.symbol(search.FUNCTION):
            name, module = origins.strings(source[1], (0, 1))
            value = {"kind": "search", "module": module, "name": name}
        elif source[0] == "load":
            base, offset = source[1:]
            if base[0] == "call" and base[2] == image.symbol(COMMON):
                value = common_field(image, offset)
            elif base[0] == "constant":
                value = proxy_slot(image, base[1] + offset)
            else:
                raise ValueError("Unknown extra cache load origin")
        else:
            raise ValueError("Unknown extra cache registration origin")
        extras.append({"native": native, "source": value})
    if len(extras) != 6 or len({row["native"] for row in extras}) != 6:
        raise ValueError("Pinned extra cache registration coverage differs")
    return root, extras


def object_hierarchy(row, by_pointer, root):
    """Native derived-type ranges include the selected base itself."""
    seen = set()
    while True:
        if row["self"] in seen or row["self"] not in by_pointer:
            raise ValueError("Cyclic or missing native cache parent")
        seen.add(row["self"])
        if row["self"] == root:
            return True
        if not row["parent"]:
            return False
        if row["parent"] not in by_pointer:
            raise ValueError("Cyclic or missing native cache parent")
        row = by_pointer[row["parent"]]


def reconstruct(image, inventory):
    rows = registry.static_records(image)
    generated, functions = registry.module_assignments(image)
    modules, unresolved = registry.direct_module_assignments(image)
    if len(functions) != 73 or len(generated) != 235 or unresolved or set(modules) != {row["self"] for row in rows}:
        raise ValueError("Native cache module registration coverage differs")
    if any(modules.get(pointer) != module for pointer, module in generated.items()):
        raise ValueError("Native cache module registration sources disagree")
    for row in rows:
        row["module"] = modules[row["self"]]
    rows += literals.extra_records(image, registry.call_argument, registry.direct_calls)
    registry.validate_persistent_ids(rows)
    by_pointer = {row["self"]: row for row in rows}
    if len(rows) != 318 or len(by_pointer) != len(rows):
        raise ValueError("Native cache identity coverage differs")
    root, extras = profile(image)
    if root not in by_pointer or by_pointer[root]["parent"] != 0 or by_pointer[root]["name"] != "Object":
        raise ValueError("Native cache Object root differs")
    flag_values = {row["persistentTypeID"]: row["flags"] for row in flags.decode(image)}
    universe = metadata.MetadataUniverse(inventory, "engine-directory")
    steps = search.SearchReader(image).decode()["lookup_sequence"]

    def lookup(name, module):
        for step in steps:
            origin = step["assembly"]
            assembly = origin["template"].replace("%s", module) if origin["kind"] == "module-format" else origin["name"]
            if not assembly.endswith(".dll"):
                raise ValueError("Cache search assembly suffix differs")
            identity = universe.names.get(assembly[:-4])
            if identity is not None:
                value = universe.resolve(identity, step["namespace"] + "." + name)
                if value is not None:
                    return value
        return None

    object_identity = universe.names["UnityEngine"]

    def object_class(value):
        return value is not None and universe.derives_from(value["assembly_identity"], value["name"], object_identity, "UnityEngine.Object")

    def identity(value):
        return None if value is None else {"assembly_identity": value["assembly_identity"], "name": value["name"]}

    forward, reverse, direct = [], [], []
    for row in sorted(rows, key=lambda row: row["persistentTypeID"]):
        first = lookup(row["name"], row["module"])
        direct.append({"persistentTypeID": row["persistentTypeID"], "managed": identity(first)})
        if not object_hierarchy(row, by_pointer, root):
            continue
        ancestor, value = row, first
        while not object_class(value):
            if ancestor["self"] == root:
                raise ValueError("No inherited Object wrapper for populated native type")
            ancestor = by_pointer[ancestor["parent"]]
            value = lookup(ancestor["name"], ancestor["module"])
        forward.append({"persistentTypeID": row["persistentTypeID"], "flags": flag_values[row["persistentTypeID"]], "managed": identity(value)})
        if object_class(first):
            reverse.append({"persistentTypeID": row["persistentTypeID"], "managed": identity(first), "extra": False})
    for extra in extras:
        row = by_pointer.get(extra["native"])
        if row is None:
            raise ValueError("Extra cache identity is not in the native registry")
        source = extra["source"]
        if source["kind"] == "search":
            value = lookup(source["name"], source["module"])
        else:
            assembly = "mscorlib" if source["kind"] == "corlib" else source["assembly"].removesuffix(".dll")
            if assembly not in universe.names:
                raise ValueError("Missing extra cache assembly")
            value = universe.resolve(universe.names[assembly], source["namespace"] + "." + source["name"])
        if value is not None:
            reverse.append({"persistentTypeID": row["persistentTypeID"], "managed": identity(value), "extra": True})
    if len(forward) != 306:
        raise ValueError("Pinned forward cache population differs")
    keys = [(row["managed"]["assembly_identity"], row["managed"]["name"]) for row in reverse]
    if len(keys) != len(set(keys)):
        raise ValueError("Reverse cache has ambiguous managed identities")
    return {
        "forward": forward,
        "reverse": reverse,
        "direct": direct,
        "extra_registration_metadata": extras,
        "cache_population_qualified": False,
        "root_generation_qualified": False,
        "executes_sdk": False,
    }


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind_inventory(inventory, engine_directory, corlib):
    """Check a complete, relocatable owner-SDK file set before resolving absence."""
    engine_directory, corlib = Path(engine_directory), Path(corlib)
    files = [*engine_directory.glob("UnityEngine*.dll"), *engine_directory.glob("UnityEditor*.dll"), corlib]
    by_name = {path.name: path for path in files}
    if len(files) != 84 or len(by_name) != len(files) or any(not path.is_file() for path in files):
        raise ValueError("Incomplete or ambiguous owner managed SDK file set")
    manifest = sorted((name, sha(path)) for name, path in by_name.items())
    if hashlib.sha256(json.dumps(manifest, separators=(",", ":")).encode()).hexdigest() != MANAGED_SET_SHA256:
        raise ValueError("Unknown owner managed SDK file set")
    selected = [row for row in inventory["assemblies"] if row["group"] == "engine-directory"]
    rows = {Path(row["path"]).name: row for row in selected}
    if len(rows) != len(selected) or set(rows) != set(by_name):
        raise ValueError("Scoped inventory does not cover the complete selected SDK")
    for name, digest in manifest:
        if rows[name]["sha256"] != digest or rows[name]["assembly"] + ".dll" != name:
            raise ValueError("Scoped inventory and owner SDK identity disagree")
    return by_name, dict(manifest)


def inspect(binary, inventory_path, engine_directory, corlib, output):
    binary, inventory_path, output = Path(binary), Path(inventory_path), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private population report")
    binary_hash, inventory_hash = sha(binary), sha(inventory_path)
    if binary_hash != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    inventory = json.loads(inventory_path.read_text())
    if inventory.get("schema") != 2 or inventory.get("executes_inputs") is not False:
        raise ValueError("Non-executing scoped inventory required")
    files, manifest = bind_inventory(inventory, engine_directory, corlib)
    readers = [Path(__file__), Path(registry.__file__), Path(literals.__file__), Path(search.__file__), Path(flags.__file__), Path(metadata.__file__)]
    sources = {path.name: sha(path) for path in readers}
    report = reconstruct(registry.MachO(binary.read_bytes()), inventory)
    if sha(binary) != binary_hash or sha(inventory_path) != inventory_hash:
        raise ValueError("Population SDK or inventory changed during inspection")
    if any(sha(path) != manifest[name] for name, path in files.items()) or any(sha(path) != sources[path.name] for path in readers):
        raise ValueError("Population managed SDK or reader changed during inspection")
    report.update(
        schema=1, profile=registry.PROFILE, binary_sha256=binary_hash, inventory_sha256=inventory_hash, managed_set_sha256=MANAGED_SET_SHA256, sources=sources
    )
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 6:
        raise SystemExit("Usage: phone_wrapper_population.py OWNER_SDK_BINARY SCOPED_METADATA ENGINE_DIRECTORY CORLIB NEW_PRIVATE_REPORT")
    report = inspect(*sys.argv[1:])
    print(
        json.dumps(
            {
                "forward": len(report["forward"]),
                "reverse": len(report["reverse"]),
                "executes_sdk": False,
                "cache_population_qualified": False,
                "root_generation_qualified": False,
            }
        )
    )
