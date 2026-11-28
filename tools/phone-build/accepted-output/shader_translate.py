"""Translate bounded source DXBC Shader and ComputeShader records to Unity Vulkan."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "scripts/lab"))

import object_produce as objects
import shader_produce as shader

COMPUTE_PROFILE = "owner-compute-shader-translation-v1"
GRAPHICS_PROFILE = "owner-graphics-shader-translation-v1"
SIGNED_PROFILES = {
    COMPUTE_PROFILE: (72, {"dxbc", "spirv_val"}),
    GRAPHICS_PROFILE: (48, {"dxbc", "spirv_val", "smolv", "spirv_cross", "glslang"}),
}


def signature_rows(dxbc, chunk_kind):
    """Read the original D3D11 input or output signature."""
    chunk_count = struct.unpack_from("<I", dxbc, 28)[0]
    for offset in struct.unpack_from(f"<{chunk_count}I", dxbc, 32):
        kind, size = struct.unpack_from("<4sI", dxbc, offset)
        if kind == chunk_kind:
            signature = dxbc[offset + 8 : offset + 8 + size]
            break
    else:
        raise ValueError(f"graphics translation requires a {chunk_kind.decode()} signature")
    count, start = struct.unpack_from("<2I", signature)
    for index in range(count):
        name_offset, semantic_index, system_value, _, register = struct.unpack_from("<5I", signature, start + 24 * index)
        end = signature.index(b"\0", name_offset)
        yield signature[name_offset:end].upper(), semantic_index, system_value, register


def vertex_channels(dxbc):
    """Map D3D inputs to Unity channels and serialized Vulkan bindings."""
    channels = []
    for name, semantic_index, system_value, register in signature_rows(dxbc, b"ISGN"):
        if system_value:
            continue
        if name == b"TEXCOORD" and semantic_index < 8:
            channel = 4 + semantic_index
        elif name in (b"POSITION", b"NORMAL", b"TANGENT", b"COLOR") and semantic_index == 0:
            channel = (b"POSITION", b"NORMAL", b"TANGENT", b"COLOR").index(name)
        else:
            raise ValueError(f"unqualified vertex semantic {name!r} index {semantic_index}")
        # Unity 2021 Vulkan adds 13 in the channel table. The SPIR-V
        # location itself is still the original register.
        channels.append((channel, 13 + register))
    return sorted(channels)


def fragment_color_mask(dxbc):
    mask = 0
    for name, semantic_index, _, _ in signature_rows(dxbc, b"OSGN"):
        if name == b"SV_TARGET":
            mask |= 1 << semantic_index
    # The exact-editor envelope keeps bit zero set for depth-only passes.
    return mask or 1


def stage_parameters(layout, vertex, *, vertex_binding_base=2, shared_draw_call=None):
    """Route source-layout resources to the linked pass's descriptor sets."""
    stage_flag = 0x04000000 if vertex else 0x08000000
    rows, descriptors = [], []

    def constant_row(name, variable):
        return (
            f"const: {name} {variable['offset']} {variable['type']} {int(variable['matrix'])} {variable['rows']} {variable['columns']} {variable['array_size']}"
        )

    for buffer in layout["buffers"]:
        slot = buffer["slot"] + (vertex_binding_base if vertex else 0)
        name = buffer["name"]
        draw_call = name == "UnityDrawCallInfo"
        if not draw_call and not name.startswith("UnityInstancing_"):
            name = ("vs_" if vertex else "fs_") + name
        if draw_call and shared_draw_call is not None:
            slot = shared_draw_call
        descriptors.extend(("cbv", str(buffer["slot"]), "1", str(slot)))
        if draw_call and shared_draw_call is not None and vertex:
            continue  # The fragment metadata declares the binding for both stages.
        variables = buffer["variables"]
        # The SDK's Vulkan runtime binding exposes two integers. DXBC pads
        # the register to 16 bytes, while both translated stages read lane 0.
        size = 8 if draw_call else buffer["size"]
        rows.append(f"cb: {name} {size} {len(variables)}")
        rows.extend(constant_row(variable["name"], variable) for variable in variables)
        for structure in buffer.get("structures", []):
            name_prefix = structure["name"]
            rows.append(f"const: {name_prefix} {structure['offset']} 0 2 {structure['stride']} 0 {structure['array_size']}")
            rows.extend(constant_row(f"{name_prefix}.{variable['name']}", variable) for variable in structure["variables"])
        visibility = 0x0C000000 if draw_call and shared_draw_call is not None else stage_flag
        rows.append(f"cbbind: {name} {visibility | 0x10000 | slot}")
    textures = layout["textures"]
    image_base = max(3, 1 + max((texture["sampler"] for texture in textures), default=-1))
    bound_samplers = set()
    for texture in textures:
        source_slot = texture["slot"]
        sampler = texture["sampler"]
        dimension = texture["dimension"]
        multisampled = texture.get("multisampled", False)
        if dimension is None:
            # The native variant texture binding packs the dimension above its MSAA bit.
            dimension, multisampled = divmod(texture["native_texture_descriptor"], 2)
        if vertex or dimension not in (2, 4) or multisampled or source_slot < 0 or sampler < 0:
            raise ValueError("unqualified Vulkan texture binding")
        image_slot = image_base + source_slot
        descriptors.extend(("texture", str(source_slot), "0", str(image_slot)))
        if sampler not in bound_samplers:
            descriptors.extend(("sampler", str(sampler), "0", str(sampler)))
            bound_samplers.add(sampler)
        rows.append(f"texbind: {texture['name']} {stage_flag | image_slot} {stage_flag | sampler} 0 {dimension}")
    return rows, descriptors


def compile_spirv(tools, directory, index, dxbc, descriptors, *, glsl_stage=None, flip_vertex_y=True):
    source = directory / f"{index}.dxbc"
    spirv = directory / f"{index}.spv"
    source.write_bytes(dxbc)
    subprocess.run([tools["dxbc"], source, spirv, *descriptors], check=True)
    if glsl_stage:
        glsl = directory / f"{index}.{glsl_stage}"
        flip = ["--flip-vert-y"] if glsl_stage == "vert" and flip_vertex_y else []
        subprocess.run([tools["spirv_cross"], spirv, "--version", "450", "--vulkan-semantics", *flip, "--output", glsl], check=True)
        if glsl_stage == "geom":
            # Match the SDK: flip each emitted position, then restore the
            # source value in case the shader reads it again after emission.
            source_code, emissions = re.subn(
                r"(?m)^([ \t]*)EmitVertex\(\);[ \t]*$",
                r"\1{\n\1    float sourceY = gl_Position.y;\n\1    gl_Position.y = -sourceY;\n"
                r"\1    EmitVertex();\n\1    gl_Position.y = sourceY;\n\1}",
                glsl.read_text(),
            )
            if not emissions:
                raise ValueError("geometry translation requires standalone EmitVertex calls")
            glsl.write_text(source_code)
        subprocess.run([tools["glslang"], "-V", "--target-env", "vulkan1.0", "-o", spirv, glsl], check=True)
    subprocess.run([tools["spirv_val"], "--target-env", "vulkan1.0", spirv], check=True)
    return spirv.read_bytes()


def translate_pass(original, shader_pass, raw, records, dxbc, directory, tools):
    from shader_segments import selected_layout

    has_geometry = shader_pass["m_ProgramMask"] == 14
    stage_names = ("progVertex", "progFragment", "progGeometry") if has_geometry else ("progVertex", "progFragment")
    stages = {}
    # Vertex and fragment share descriptor set 1. Keep the vertex range above all
    # fragment constant buffers, including those in instanced variants.
    for stage in stage_names:
        entries = shader_pass[stage]["m_PlayerSubPrograms"][3]
        stages[stage] = {}
        for entry in entries:
            index = entry["m_BlobIndex"]
            record, program = records[index], dxbc[index]
            keywords = tuple(record["keywords"])
            if keywords in stages[stage]:
                raise ValueError(f"duplicate {stage} source keyword variant: {keywords}")
            layout = selected_layout(original, raw, record, structured=True)
            stages[stage][keywords] = (index, program, layout, entry["m_ShaderRequirements"])

    vertices, fragments = stages["progVertex"], stages["progFragment"]
    fragment_keys = {keywords: keywords for keywords in vertices}
    # Terrain forward passes keep VERTEXLIGHT_ON in the vertex table only.
    # Use the matching original fragment while retaining the full vertex key.
    if not has_geometry and vertices.keys() != fragments.keys() and all("VERTEXLIGHT_ON" not in keywords for keywords in fragments):
        fragment_keys = {keywords: tuple(key for key in keywords if key != "VERTEXLIGHT_ON") for keywords in vertices}
    if not vertices or set(fragment_keys.values()) != fragments.keys():
        raise ValueError("Vulkan translation requires paired source keyword variants")
    geometry = stages.get("progGeometry")
    if has_geometry and vertices.keys() != geometry.keys():
        raise ValueError("Vulkan translation requires matching geometry source keyword variants")
    fragment_slots = (buffer["slot"] for _, _, layout, _ in fragments.values() for buffer in layout["buffers"])
    vertex_binding_base = max(2, max(fragment_slots, default=-1) + 1)
    variants = []
    for keywords, vertex_stage in vertices.items():
        fragment_stage = fragments[fragment_keys[keywords]]
        vertex_draw_call = next((buffer for buffer in vertex_stage[2]["buffers"] if buffer["name"] == "UnityDrawCallInfo"), None)
        fragment_draw_call = next((buffer for buffer in fragment_stage[2]["buffers"] if buffer["name"] == "UnityDrawCallInfo"), None)
        shared_draw_call = fragment_draw_call["slot"] if vertex_draw_call and fragment_draw_call else None
        reflection, codes, requirements = [], {}, 0
        sources = [("vert", vertex_stage), ("frag", fragment_stage)]
        if has_geometry:
            sources.append(("geom", geometry[keywords]))
        for stage, (index, program, layout, stage_requirements) in sources:
            if stage == "geom":
                if layout["buffers"] or layout["textures"]:
                    raise ValueError("geometry translation requires a resource-free stage")
                rows, descriptors = [], []
            else:
                vertex = stage == "vert"
                rows, descriptors = stage_parameters(layout, vertex, vertex_binding_base=vertex_binding_base, shared_draw_call=shared_draw_call)
                if vertex:
                    rows.extend(f"input: {channel} {register}" for channel, register in vertex_channels(program))
            glsl_stage = stage if stage in ("vert", "geom") else None
            spirv = compile_spirv(tools, directory, index, program, descriptors, glsl_stage=glsl_stage, flip_vertex_y=not has_geometry)
            codes[stage] = subprocess.run([tools["smolv"]], input=spirv, capture_output=True, check=True).stdout
            reflection.extend(rows)
            requirements |= stage_requirements
        executable = shader.linked_vulkan_program(
            codes["vert"],
            codes["frag"],
            alpha_clip="UNITY_UI_ALPHACLIP" in keywords,
            color_mask=fragment_color_mask(fragment_stage[1]),
            geometry=codes.get("geom"),
        )
        compilation = {"reflection": reflection, "data": executable, "gpu_program_type": 25}
        variants.append({"keywords": keywords, "requirements": requirements, "compilation": compilation})
    return variants


def translate_tree(original, directory, tools):
    import lz4.block
    from shader_segments import read_segments

    form = original["m_ParsedForm"]
    passes = [shader_pass for subshader in form["m_SubShaders"] for shader_pass in subshader["m_Passes"]]
    if not passes or any(p["m_Type"] != 0 or p["m_ProgramMask"] not in (6, 14) for p in passes):
        raise ValueError("translation requires ordinary vertex/fragment passes with optional geometry")
    source, records, dxbc = read_segments(original, bytes(original["compressedBlob"]))
    groups = []
    for ordinal, shader_pass in enumerate(passes):
        pass_directory = directory
        if len(passes) > 1:
            pass_directory = directory / f"pass-{ordinal}"
            pass_directory.mkdir()
        variants = translate_pass(original, shader_pass, source, records, dxbc, pass_directory, tools)
        groups.append(shader.variant_records(variants, form["m_KeywordNames"]))
    raw, packed = shader.merge_variant_records(groups)
    # Bundle preparation resolves these source dependency pointers against the
    # typed supplier bindings when it relocates the Shader.
    tree = shader.deepcopy(original)
    targets = (shader_pass for subshader in tree["m_ParsedForm"]["m_SubShaders"] for shader_pass in subshader["m_Passes"])
    for target, (pass_raw, _, _, _), (table, programs, parameters) in zip(targets, groups, packed):
        target["m_Platforms"] = [18]
        target["m_NameIndices"] = table["m_NameIndices"]
        target["m_EditorDataHash"] = [{f"bytes[{index}]": byte for index, byte in enumerate(shader.spooky(pass_raw))}]
        target["progVertex"].update(
            m_CommonParameters=table["m_CommonParameters"],
            m_PlayerSubPrograms=[shader.deepcopy(programs) for _ in range(3)] + [[]],
            m_ParameterBlobIndices=[parameters[:] for _ in range(3)] + [[]],
        )
        linked_stages = ("progFragment", "progGeometry") if target["m_ProgramMask"] == 14 else ("progFragment",)
        for stage in linked_stages:
            program = target[stage]
            program.update(
                m_CommonParameters={key: [] for key in program["m_CommonParameters"]},
                m_PlayerSubPrograms=[],
                m_ParameterBlobIndices=[],
            )
    compressed = lz4.block.compress(raw, mode="high_compression", compression=9, store_size=False)
    tree.update(
        platforms=[18],
        offsets=[[0]],
        compressedLengths=[[len(compressed)]],
        decompressedLengths=[[len(raw)]],
        compressedBlob=list(compressed),
        stageCounts=[1],
        m_ShaderIsBaked=True,
    )
    return tree


def translate_compute(original, directory, tools):
    tree = shader.deepcopy(original)
    (renderer,) = [row for row in tree["variants"] if row["targetRenderer"] == 2]
    if renderer["targetLevel"] != 0 or not renderer["resourcesResolved"] or not renderer["kernels"]:
        raise ValueError("unqualified DXBC compute renderer")
    renderer["targetRenderer"] = 21
    tree["variants"] = [renderer]
    for index, declaration in enumerate(renderer["kernels"]):
        if declaration["globalKeywords"] or declaration["localKeywords"]:
            raise ValueError("compute keyword variants require qualification")
        ((keywords, kernel),) = declaration["variantMap"]
        if keywords or not bytes(kernel["code"]).startswith(b"DXBC"):
            raise ValueError("unqualified DXBC compute resources or code")
        textures = kernel["textures"]
        builtins = kernel["builtinSamplers"]
        constants = kernel["cbs"]
        structured = kernel["inBuffers"]
        storage = kernel["outBuffers"]
        if (
            any(row["texDimension"] not in (2, 3, 5) or row["generatedName"] for row in textures)
            or len(constants) > 1
            or not storage
            or any(row["texDimension"] != -1 for row in structured)
            or any(row["texDimension"] not in (-1, 2, 3, 5) for row in storage)
            or any(row["samplerBindPoint"] != -1 or row["generatedName"] for row in [*constants, *structured, *storage])
        ):
            raise ValueError("unqualified compute binding layout")
        # Unity allocates set 0 in sampler, read-only and writable-resource order.
        descriptors = []
        sampler_registers = {row["samplerBindPoint"] for row in textures if row["samplerBindPoint"] != -1}
        sampler_registers.update(row["bindPoint"] for row in builtins)
        sampler_slots = {register: slot for slot, register in enumerate(sorted(sampler_registers))}
        for register, slot in sampler_slots.items():
            descriptors.extend(("sampler", str(register), "0", str(slot)))
        for row in builtins:
            row["bindPoint"] = sampler_slots[row["bindPoint"]]
        for row in textures:
            row["samplerBindPoint"] = sampler_slots.get(row["samplerBindPoint"], -1)
        input_start = len(sampler_slots)
        inputs = [*textures, *structured]
        # Unity encodes the descriptor set and writable-resource flag in bindPoint.
        for rows, kind, descriptor_set, start, flag in (
            (inputs, "texture", 0, input_start, 0),
            (storage, "storage", 0, input_start + len(inputs), 0x02000000),
            (constants, "cbv", 1, 0, 0),
        ):
            for slot, row in enumerate(sorted(rows, key=lambda row: row["bindPoint"]), start):
                descriptor_kind = "storage-image" if kind == "storage" and row["texDimension"] != -1 else kind
                if kind == "texture" and row["texDimension"] == -1:
                    descriptor_kind = "structured"
                descriptors.extend((descriptor_kind, str(row["bindPoint"]), str(descriptor_set), str(slot)))
                row["bindPoint"] = flag | (descriptor_set << 16) | slot
        kernel["code"] = compile_spirv(tools, directory, index, bytes(kernel["code"]), descriptors)
    return tree


def source_records(root, records):
    files = defaultdict(lambda: defaultdict(list))
    destinations = set()
    for record in records:
        source, target = record["source"], record["output"]
        destination = target["bundle"], target["member"], target["path_id"]
        if destination in destinations:
            raise ValueError("duplicate translated Shader destination")
        destinations.add(destination)
        files[source["path"]][source["member"]].append(record)
    for relative, members in files.items():
        path = shader.relative(root, relative)
        pins = {(row["source"]["bytes"], row["source"]["sha256"]) for group in members.values() for row in group}
        if len(pins) != 1:
            raise ValueError("original Shader file pins disagree: " + path.name)
        ((size, digest),) = pins
        shader.checked(path, {"bytes": size, "sha256": digest})
        for member, group in members.items():
            with objects.source_member(path, member) as stream:
                metadata = objects.W.read_serialized(stream)
                extents = {row["path_id"]: row for row in metadata["objects"]}
                for record in group:
                    source = record["source"]
                    extent = extents.get(source["path_id"])
                    if extent is None:
                        raise ValueError(f"original Shader is absent: {path.name}/{member}/{source['path_id']}")
                    typ = metadata["types"][extent["type_id"]]
                    if typ["class_id"] not in (48, 72):
                        raise ValueError("original record is not Shader or ComputeShader")
                    stream.seek(metadata["data_offset"] + extent["offset"])
                    body = objects.B.exact(stream, extent["bytes"])
                    if "body_sha256" in source and hashlib.sha256(body).hexdigest() != source["body_sha256"]:
                        raise ValueError(f"original Shader body differs: {path.name}/{member}/{source['path_id']}")
                    yield record["output"], typ, body


def produce(request):
    root = Path(request["pc"]).resolve(strict=True)
    output = Path(request["output"]).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("translation output must be disjoint from original inputs")
    profile = request.get("profile")
    input_id = None
    class_id = None
    tool_pins = {}
    tools = request["tools"]
    if profile is None:
        records = [{"source": request["source"], "output": request["record"]}]
    else:
        path = Path(profile["path"]).resolve(strict=True)
        shader.checked(path, profile)
        selection = json.loads(path.read_bytes())
        records = selection["typed_records"]
        if not records:
            raise ValueError("translated Shader profile is empty")
        schema = selection.get("schema")
        if schema in SIGNED_PROFILES:
            class_id, required_tools = SIGNED_PROFILES[schema]
            input_id = selection["input_id"]
            if input_id != objects.M.INPUT_ID or set(tools) != required_tools:
                raise ValueError(f"{schema} requires the accepted input and pinned tools: {sorted(required_tools)}")
            tool_pins = tools
            for pin in tool_pins.values():
                shader.checked(Path(pin["path"]), pin)
            tools = {name: pin["path"] for name, pin in tool_pins.items()}

    directory = output / "programs"
    directory.mkdir(parents=True)
    rows, types, type_ids = [], [], {}
    with (output / "objects.bin").open("xb") as stream:
        for target, typ, original in source_records(root, records):
            if class_id is not None and typ["class_id"] != class_id:
                raise ValueError(f"{schema} requires Unity class {class_id}")
            stage_dir = directory / str(len(rows))
            stage_dir.mkdir()
            node = objects.W.shader_node(typ["tree"])
            translate = translate_tree if typ["class_id"] == 48 else translate_compute
            tree = translate(objects.W.read_shader_body(node, original), stage_dir, tools)
            body = objects.W.write_shader_body(node, tree)
            rows.append(
                dict(target, offset=stream.tell(), bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), type_id=objects.record_type(typ, types, type_ids))
            )
            stream.write(body)
    (output / "index.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    (output / "types.json").write_text(json.dumps(types, sort_keys=True, indent=2) + "\n")
    if profile is None:
        return rows[0]
    receipt = {
        "success": True,
        "profile_sha256": profile["sha256"],
        "records": len(rows),
        "outputs": {
            name: {"bytes": (output / name).stat().st_size, "sha256": shader.sha(output / name)} for name in ("objects.bin", "index.jsonl", "types.json")
        },
    }
    if input_id is not None:
        for pin in tool_pins.values():
            shader.checked(Path(pin["path"]), pin)
        receipt["input_id"] = input_id
        receipt["tool_sha256"] = {name: pin["sha256"] for name, pin in tool_pins.items()}
    (output / "result.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(json.loads(args.request.read_text())), sort_keys=True))
