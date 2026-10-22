"""Current experimental SDK initializer interval; never a live map producer."""

from pathlib import Path
import importlib.util
import re

_spec = importlib.util.spec_from_file_location("_target_constructor", Path(__file__).with_name("phone_target_constructor.py"))
ctor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctor)
f = ctor.f
SOURCES = ("phone_target_geometry.py", *ctor.SOURCES)
FUNCTION = "__GLOBAL__sub_I_Editor_Src_BuildPipeline_1.cpp"
OBJECT = "__ZL25m_BuildTargetPlatformKeys"


def add_immediate(word):
    if word & 0xFFC00000 != 0x91000000:
        raise ValueError("Unknown pointer addition")
    return word & 31, (word >> 5) & 31, (word >> 10) & 4095


def plain_store(word):
    stores = f.literals.store(word)
    if stores is None or len(stores) != 1:
        raise ValueError("Unknown map-header store")
    return stores[0]


def derive(image):
    words = f.literals.function_words(image, FUNCTION)
    dominance = f.literals.dominators(f.literals.graph(words))
    address = image.symbol(OBJECT)
    setup_candidates = []
    for pc, word in words.items():
        if word & 0x9F000000 != 0x90000000:
            continue
        try:
            register, pointer = f.pair_constant(words, pc)
        except ValueError:
            continue
        if pointer != address or f.search.move(words.get(pc + 8, 0)) != register:
            continue
        setup_candidates.append((pc, register))
    if len(setup_candidates) != 1:
        raise ValueError("Missing or ambiguous fresh key-map initialization")
    setup, obj = setup_candidates[0]
    array, stack, base = add_immediate(words[setup - 4])
    cursor = words[setup + 8] & 31
    if stack != 31 or base % 8 or not 0 < base < 65536 or not 19 <= obj <= 28 or not 19 <= array <= 28:
        raise ValueError("Initializer list is not an owned aligned stack interval")
    first_store = words[setup + 12]
    if (
        not ctor.pre_store(first_store)
        or first_store >> 30 != 3
        or first_store & 31 != 31
        or (first_store >> 5) & 31 != cursor
        or f.registry.signed((first_store >> 12) & 511, 9) != 8
        or plain_store(words[setup + 16]) != (obj, 16, 8, 31, False)
        or plain_store(words[setup + 20]) != (obj, 0, 8, cursor, False)
    ):
        raise ValueError("Map object does not initialize an empty pointer header")
    end, source, span = add_immediate(words[setup + 24])
    sentinel, sentinel_address = f.pair_constant(words, setup + 28)
    if source != array or sentinel_address != address + 8 or not 19 <= end <= 28 or not 19 <= sentinel <= 28 or len({obj, array, end, sentinel}) != 4:
        raise ValueError("Initializer interval/end/map receivers alias or differ")
    frames = [pc for pc, word in words.items() if pc < setup - 4 and word & 0xFFC003FF == 0xD10003FF]
    if not frames:
        raise ValueError("Missing bounded stack-frame allocation")
    frame_pc = max(frames)
    frame_size = (words[frame_pc] >> 10) & 4095
    if not 0 < span <= frame_size or base + span > frame_size:
        raise ValueError("Initializer array escapes its allocated frame")
    node_targets = {
        image.symbol(name)
        for name in image.symbols
        if "__treeINS_12__value_typeI19BuildTargetPlatformN4core12basic_string" in name and "16__construct_nodeIJRKNS_4pair" in name
    }
    nodes = [pc for pc in words if f.call_target(words, pc) in node_targets]
    if len(node_targets) != 1 or len(nodes) != 1:
        raise ValueError("Unknown or ambiguous typed key/string node consumer")
    node = nodes[0]
    if f.search.move(words.get(node - 8, 0)) != obj or words[node - 8] & 31 != 0 or f.search.move(words.get(node - 4, 0)) != array or words[node - 4] & 31 != 1:
        raise ValueError("Node consumer does not receive this map/current list record")
    result_register, result_base, result_slot = add_immediate(words[node - 12])
    if result_register != 8 or result_base != 31 or result_slot % 8 or not 0 <= result_slot < base:
        raise ValueError("Node return does not select a separate aligned stack slot")
    iteration = []
    for pc, word in words.items():
        if pc <= node or word & 0xFFC00000 != 0x91000000:
            continue
        destination, source, stride = add_immediate(word)
        if destination != array or source != array:
            continue
        compare = words.get(pc + 4)
        branch = words.get(pc + 8, 0)
        if compare != 0xEB00001F | end << 16 | array << 5 or branch & 31 != 0:
            continue
        exit_pc = f.branch_target(branch, pc + 8, "conditional")
        if exit_pc <= pc + 8 or exit_pc not in words:
            continue
        iteration.append((pc, stride, exit_pc))
    if len(iteration) != 1:
        raise ValueError("Missing unique forward list iteration/end comparison")
    step, stride, exit_pc = iteration[0]
    if not 0 < stride <= 1024 or span % stride or not 1 <= span // stride <= 128:
        raise ValueError("Unqualified initializer span/stride/count")
    typed_pair = r"__ZNSt3__14pairIK19BuildTargetPlatformN4core12basic_stringIcNS3_20StringStorageDefaultIcEEEEEC1IS1_RA([0-9]+)_KcLb0EEEOT_OT0_"
    extents = {ctor.prove(image, name)["record_write_extent"] for name in image.symbols if re.fullmatch(typed_pair, name)}
    if len(extents) != 1 or stride < next(iter(extents)):
        raise ValueError("Initializer stride overlaps typed constructor record writes")
    loop_start = setup + 36
    protected = {obj, array, end, sentinel}
    for pc in range(loop_start, exit_pc, 4):
        word = words[pc]
        changed = ctor.effects(word)
        if changed is None:
            raise ValueError("Unknown loop operand effect")
        if changed & protected and not (pc == step and changed & protected == {array}):
            raise ValueError("Initializer loop clobbers a map/list/end receiver")
        target = f.direct_branch(word, pc)
        if target is not None and not loop_start <= target <= exit_pc:
            raise ValueError("Unaccounted initializer-loop exit")
    for pc in range(frame_pc + 4, exit_pc, 4):
        if f.literals.changes_frame(words[pc]):
            raise ValueError("Initializer stack frame changes during list lifetime")
    if any(pc not in dominance[node] for pc in range(setup - 4, setup + 36, 4)) or frame_pc not in dominance[node]:
        raise ValueError("Initializer interval/header setup can be skipped")
    if any(pc not in dominance[node] for pc in (node - 12, node - 8, node - 4)):
        raise ValueError("Typed consumer arguments can be skipped")
    return dict(
        object_address=address,
        frame_allocation=frame_pc,
        frame_bytes=frame_size,
        list_base=base,
        list_span=span,
        list_stride=stride,
        list_count=span // stride,
        constructor_write_extent=next(iter(extents)),
        setup=setup,
        node_consumer=node,
        node_return_slot=result_slot,
        loop_start=loop_start,
        loop_step=step,
        loop_exit=exit_pc,
        array_register=array,
        end_register=end,
        map_register=obj,
        sentinel_register=sentinel,
        tree_population_qualified=False,
        target_support_qualified=False,
        root_generation_qualified=False,
    )
