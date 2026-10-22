"""Experimental SDK record-copy/insertion/consumer operand links; never live targets.

Reads only owner-supplied SDK data. Host/Android: python3 -I -S THIS.py OWNER_SDK NEW_PRIVATE_REPORT
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

_spec = importlib.util.spec_from_file_location("_record_constructor", Path(__file__).with_name("phone_target_constructor.py"))
ctor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctor)
f = ctor.f
SOURCES = ("phone_target_records.py", *ctor.SOURCES)
RECORD = "__ZN20BuildTargetDiscovery20DiscoveredTargetInfoC2ERKS0_RK10MemLabelId"
ASSIGN = "__ZN4core20StringStorageDefaultIcE6assignERKS1_"
PAIR = "__ZN4core9base_pairIKNS_12basic_stringIcNS_20StringStorageDefaultIcEEEEN20BuildTargetDiscovery20DiscoveredTargetInfoELb1ELb1EEC2IS4_RKS7_EEOT_OT0_RK10MemLabelId"
INSERT = "__ZN20BuildTargetDiscovery23AddDiscoveredTargetInfoERNS_20DiscoveredTargetInfoE"
CONSUMER = "__ZN20BuildTargetDiscovery17GetPlatformDefineERKN4core12basic_stringIcNS0_20StringStorageDefaultIcEEEE"
LOWER = "__Z7ToLowerIN4core12basic_stringIcNS0_20StringStorageDefaultIcEEEEET_RKS5_"


def normal(image, symbol):
    whole = f.literals.function_words(image, symbol)
    ends = [pc for pc, word in whole.items() if word == 0xD65F03C0]
    if not ends:
        raise ValueError("Missing record-link normal return")
    return {pc: word for pc, word in whole.items() if pc <= ends[0]}


def calls(words, target):
    return [pc for pc in words if f.call_target(words, pc) == target]


def one(values):
    if len(values) != 1:
        raise ValueError("Missing or ambiguous record-link operand")
    return values[0]


def offset(value, base):
    if value == base:
        return 0
    if value[0] == "add" and value[1] == base and value[2] > 0:
        return value[2]
    raise ValueError("Record link has a different receiver/source")


def copied_strings(words, assign):
    origin = ctor.Origins(words)
    end = max(words)
    rows = []
    for pc in calls(words, assign):
        if pc not in origin.dom[end]:
            raise ValueError("Record string copy can be skipped")
        destination = offset(origin.at(pc, 0), ("parameter", 0))
        if destination != offset(origin.at(pc, 1), ("parameter", 1)):
            raise ValueError("Record string copy changes field")
        rows.append(destination)
    if len(rows) < 2 or rows[0] != 0 or rows != sorted(set(rows)):
        raise ValueError("Missing/repeated/unordered record string copies")
    spacing = rows[1]
    if not spacing or rows != list(range(0, len(rows) * spacing, spacing)):
        raise ValueError("Record string copy operands have gaps")
    return rows, spacing


def pair_value(words, assign, record, spacing):
    origin = ctor.Origins(words)
    key, value = one(calls(words, assign)), one(calls(words, record))
    if key >= value or any(pc not in origin.dom[max(words)] for pc in (key, value)):
        raise ValueError("Pair copies are reordered or skipped")
    if origin.at(key, 0) != ("parameter", 0) or origin.at(key, 1) != ("parameter", 1):
        raise ValueError("Pair key arguments differ")
    position = offset(origin.at(value, 0), ("parameter", 0))
    if position != spacing or origin.at(value, 1) != ("parameter", 2) or origin.at(value, 2) != ("parameter", 3):
        raise ValueError("Pair value/source/memory-label arguments differ")
    modes = []
    for pc, word in words.items():
        for base, field, width, source, vector in f.literals.store(word) or []:
            if pc < key and width == 1 and not vector and source != 31:
                if pc not in origin.dom[key]:
                    raise ValueError("Pair mode initialization can be skipped")
                pointer = ctor.add(origin.at(pc, base), field)
                if pointer[0] == "add" and pointer[1] == ("parameter", 0) and origin.at(pc, source) == ("constant", 1):
                    modes.append(pointer[2])
    mode = one(modes)
    if not 0 < mode < position:
        raise ValueError("Pair key mode is outside its field")
    return position, mode


def local_node_geometry(words, pair):
    """Local insertion block only; node selection, hash semantics and duplicates stay open."""
    pc = one(calls(words, pair))
    dom = f.literals.dominators(f.literals.graph(words))
    if any(at not in dom.get(pc, set()) for at in (pc - 12, pc - 8, pc - 4)):
        raise ValueError("Local pair arguments can be skipped")
    receiver, record_arg, header = words.get(pc - 12, 0), words.get(pc - 4, 0), words.get(pc + 4, 0)
    if receiver & 0xFFC0001F != 0x91000000 or record_arg & 31 != 2 or f.search.move(record_arg) is None:
        raise ValueError("Unknown local pair receiver/value operands")
    node = (receiver >> 5) & 31
    displacement = (receiver >> 10) & 4095
    if not 19 <= node <= 28 or not 0 < displacement <= 64 or displacement % 8:
        raise ValueError("Local node/key displacement is not a bounded preserved pointer")
    parts = f.literals.store(header)
    if parts is None or len(parts) != 1 or parts[0][:3] != (node, 0, 4) or parts[0][4]:
        raise ValueError("Pair receiver is not relative to the following node header write")
    return displacement


def consumer_geometry(words):
    """Require the local inline/heap field choice, without evaluating lookup or iteration."""
    rows = []
    dom = f.literals.dominators(f.literals.graph(words))
    for pc, word in words.items():
        if word & 0xFFC003E0 != 0x91000000:  # ADD Xd, X0, #field
            continue
        destination, field = word & 31, (word >> 10) & 4095
        mode_word, compare, branch, heap = (words.get(pc + n, 0) for n in (4, 8, 12, 16))
        mode_reg = mode_word & 31
        if mode_word & 0xFFC003E0 != 0x39400000 or compare != 0x7100041F | mode_reg << 5:
            continue
        if branch & 0xFF00001F != 0x54000000 or f.branch_target(branch, pc + 12, "conditional") != pc + 20:
            raise ValueError("Consumer reverses/skips the inline field choice")
        if heap != 0xF9400000 | destination << 5 | destination or not 19 <= destination <= 28:
            raise ValueError("Consumer heap pointer is not the selected field")
        if any(pc + previous not in dom.get(pc + following, set()) for previous, following in ((0, 4), (4, 8), (8, 12), (12, 16))):
            raise ValueError("Consumer field/mode choice can be entered midway")
        mode = (mode_word >> 10) & 4095
        if not 0 < mode - field < 64:
            raise ValueError("Consumer mode is outside its bounded string field")
        rows.append((field, mode - field))
    return one(rows)


def insertion_barriers(image):
    words = normal(image, INSERT)
    origin = ctor.Origins(words)
    check = one(calls(words, image.symbol("__ZN20BuildTargetDiscovery14CheckRenderersEPNS_20DiscoveredTargetInfoE")))
    module = one(calls(words, image.symbol("__ZN20BuildTargetDiscovery19HandleEditorModulesERKNS_20DiscoveredTargetInfoE")))
    lower = one(calls(words, image.symbol(LOWER)))
    reset = one(calls(words, image.symbol("__ZN20BuildTargetDiscovery20DiscoveredTargetInfo5ResetEv")))
    emplaces = [(pc, target) for pc in words if (target := f.call_target(words, pc)) is not None and module < pc < reset and pc != lower]
    # The normal sequence has only lower, emplace and temporary-string cleanup here.
    if len(emplaces) != 2:
        raise ValueError("Unknown insertion call sequence")
    emplace, target = emplaces[0]
    if not check < module < lower < emplace < reset:
        raise ValueError("Insertion prerequisites/reset are reordered")
    if any(before not in origin.dom[after] for before, after in ((check, emplace), (lower, emplace), (emplace, reset), (reset, max(words)))):
        raise ValueError("Insertion prerequisite or reset can be skipped")
    record = ("parameter", 1)
    if origin.at(check, 0) != record or origin.at(module, 0) != ("parameter", 0) or origin.at(module, 1) != record:
        raise ValueError("Insertion prerequisites use different records")
    branch_pc = module - 12
    branch = words.get(branch_pc, 0)
    if branch & 0xFFF80000 != 0x37000000 or f.direct_branch(branch, branch_pc) != module + 4:
        raise ValueError("Module handler is not conditionally bypassed by flag bit zero")
    flag_register = branch & 31
    flag = origin.at(branch_pc, flag_register)
    flag_offset = offset(flag[1], record) if flag[0] == "load" and flag[2] == 1 else None
    names = origin.at(lower, 0)
    name_offset = offset(names[1], record) if names[0] == "load" and names[2] == 8 else None
    if flag_offset is None or name_offset is None:
        raise ValueError("Missing insertion record flag/name-list load")
    if origin.at(emplace, 0) != ("parameter", 0) or origin.at(emplace, 2) != record or origin.at(reset, 0) != record:
        raise ValueError("Insertion/reset receiver or value differs")
    return (
        words,
        target,
        dict(
            record_flag_offset=flag_offset,
            name_list_pointer_offset=name_offset,
            renderer_check_precedes_insertion=True,
            conditional_module_handler_precedes_insertion=True,
            record_reset_follows_insertion=True,
        ),
    )


def derive(image):
    assign, record = image.symbol(ASSIGN), image.symbol(RECORD)
    fields, spacing = copied_strings(normal(image, RECORD), assign)
    value, key_mode = pair_value(normal(image, PAIR), assign, record, spacing)
    _, emplace, barriers = insertion_barriers(image)
    names = [
        name
        for name, values in image.symbols.items()
        if emplace in values and name.startswith("__ZN4core8hash_map") and "DiscoveredTargetInfo" in name and "7emplace" in name
    ]
    emplace_name = one(names)
    node = local_node_geometry(normal(image, emplace_name), image.symbol(PAIR))
    consumer_field, mode = consumer_geometry(normal(image, CONSUMER))
    record_field = consumer_field - node - value
    if mode != key_mode or record_field not in fields:
        raise ValueError("Consumer field does not align with a copied record string")
    return dict(
        string_copy_offsets=fields,
        string_copy_spacing=spacing,
        pair_record_offset=value,
        local_node_pair_offset=node,
        consumer_string_offset=consumer_field,
        consumer_mode_offset_within_string=mode,
        consumer_record_string_offset=record_field,
        **barriers,
        field_operand_alignment_qualified=True,
        node_selection_qualified=False,
        hash_container_semantics_qualified=False,
        constructor_result_qualified=False,
        tree_population_qualified=False,
        target_support_qualified=False,
        target_discovery_qualified=False,
        module_inclusion_qualified=False,
        native_usage_qualified=False,
        root_generation_qualified=False,
    )


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Select a new private target-record report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != f.registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in SOURCES}
    result = derive(f.registry.MachO(data))
    if binary.read_bytes() != data or any(
        hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest for name, digest in sources.items()
    ):
        raise ValueError("SDK or target-record source changed during inspection")
    result.update(
        schema=1,
        profile="native-target-record-links-v1",
        sdk_sha256=f.registry.BINARY_SHA256,
        sources=sources,
        executes_sdk=False,
        local_operand_links_only=True,
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
