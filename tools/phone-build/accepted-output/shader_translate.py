"""Translate a source DXBC vertex/fragment Shader leaf to Unity Vulkan."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import lz4.block
import UnityPy

import object_produce as objects
import shader_produce as shader

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/lab"))
from shader_segments import read_segments, selected_layout


def vertex_channels(dxbc):
    """Map D3D inputs to Unity channels and serialized Vulkan bindings."""
    chunk_count = struct.unpack_from("<I", dxbc, 28)[0]
    for offset in struct.unpack_from(f"<{chunk_count}I", dxbc, 32):
        kind, size = struct.unpack_from("<4sI", dxbc, offset)
        if kind == b"ISGN":
            signature = dxbc[offset + 8 : offset + 8 + size]
            break
    else:
        raise ValueError("vertex translation requires an ISGN input signature")
    count, start = struct.unpack_from("<2I", signature)
    channels = []
    for index in range(count):
        name_offset, semantic_index, system_value, _, register = struct.unpack_from("<5I", signature, start + 24 * index)
        if system_value:
            continue
        end = signature.index(b"\0", name_offset)
        name = signature[name_offset:end].upper()
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


def stage_parameters(layout, vertex):
    """Route source-layout resources to the linked pass's descriptor sets."""
    stage_flag = 0x04000000 if vertex else 0x08000000
    rows, descriptors = [], []
    for buffer in layout["buffers"]:
        slot = buffer["slot"] + (2 if vertex else 0)
        name = ("vs_" if vertex else "fs_") + buffer["name"]
        variables = buffer["variables"]
        rows.append(f"cb: {name} {buffer['size']} {len(variables)}")
        for variable in variables:
            rows.append(
                f"const: {variable['name']} {variable['offset']} {variable['type']} {int(variable['matrix'])} "
                f"{variable['rows']} {variable['columns']} {variable['array_size']}"
            )
        rows.append(f"cbbind: {name} {stage_flag | 0x10000 | slot}")
        descriptors.extend(("cbv", str(buffer["slot"]), "1", str(slot)))
    for texture in layout["textures"]:
        # The measured UI pass uses three separate 2D images and samplers.
        source_slot = texture["slot"]
        sampler = texture["sampler"]
        if vertex or texture["dimension"] != 2 or texture["multisampled"] or source_slot not in range(3) or sampler < 0:
            raise ValueError("unqualified Vulkan UI texture binding")
        image_slot = source_slot + 3
        descriptors.extend(("texture", str(source_slot), "0", str(image_slot), "sampler", str(sampler), "0", str(source_slot)))
        rows.append(f"texbind: {texture['name']} {stage_flag | image_slot} {stage_flag | source_slot} 0 2")
    return rows, descriptors


def compile_stage(tools, directory, index, dxbc, descriptors, *, vertex):
    source = directory / f"{index}.dxbc"
    spirv = directory / f"{index}.spv"
    source.write_bytes(dxbc)
    subprocess.run([tools["dxbc"], source, spirv, *descriptors], check=True)
    if vertex:
        glsl = directory / f"{index}.vert"
        subprocess.run([tools["spirv_cross"], spirv, "--version", "450", "--vulkan-semantics", "--flip-vert-y", "--output", glsl], check=True)
        subprocess.run([tools["glslang"], "-V", "--target-env", "vulkan1.0", "-o", spirv, glsl], check=True)
    subprocess.run([tools["spirv_val"], "--target-env", "vulkan1.0", spirv], check=True)
    return subprocess.run([tools["smolv"]], input=spirv.read_bytes(), capture_output=True, check=True).stdout


def translate_tree(original, directory, tools):
    form = original["m_ParsedForm"]
    (subshader,) = form["m_SubShaders"]
    (shader_pass,) = subshader["m_Passes"]
    if shader_pass["m_Type"] != 0 or shader_pass["m_ProgramMask"] != 6 or original["m_Dependencies"]:
        raise ValueError("translation requires one leaf vertex/fragment pass")
    raw, records, dxbc = read_segments(original, bytes(original["compressedBlob"]))
    stages = {}
    for stage, vertex in (("progVertex", True), ("progFragment", False)):
        entries = shader_pass[stage]["m_PlayerSubPrograms"][3]
        stages[stage] = {}
        for entry in entries:
            index = entry["m_BlobIndex"]
            record, program = records[index], dxbc[index]
            layout = selected_layout(original, raw, record)
            rows, descriptors = stage_parameters(layout, vertex)
            if vertex:
                rows.extend(f"input: {channel} {register}" for channel, register in vertex_channels(program))
            code = compile_stage(tools, directory, index, program, descriptors, vertex=vertex)
            stages[stage][tuple(record["keywords"])] = (rows, code, entry["m_ShaderRequirements"])

    vertices, fragments = stages["progVertex"], stages["progFragment"]
    if not vertices or vertices.keys() != fragments.keys():
        raise ValueError("Vulkan translation requires paired source keyword variants")
    variants = []
    for keywords, (vertex_rows, vertex_code, vertex_requirements) in vertices.items():
        fragment_rows, fragment_code, fragment_requirements = fragments[keywords]
        executable = shader.linked_vulkan_program(vertex_code, fragment_code, alpha_clip="UNITY_UI_ALPHACLIP" in keywords)
        compilation = {"reflection": vertex_rows + fragment_rows, "data": executable, "gpu_program_type": 25}
        variants.append({"keywords": keywords, "requirements": vertex_requirements | fragment_requirements, "compilation": compilation})
    raw, table, programs, parameters = shader.variant_records(variants, form["m_KeywordNames"])
    tree = shader.deepcopy(original)
    target = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]
    target["m_Platforms"] = [18]
    target["m_NameIndices"] = table["m_NameIndices"]
    target["m_EditorDataHash"] = [{f"bytes[{index}]": byte for index, byte in enumerate(shader.spooky(raw))}]
    target["progVertex"].update(
        m_CommonParameters=table["m_CommonParameters"],
        m_PlayerSubPrograms=[shader.deepcopy(programs) for _ in range(3)] + [[]],
        m_ParameterBlobIndices=[parameters[:] for _ in range(3)] + [[]],
    )
    fragment = target["progFragment"]
    fragment.update(
        m_CommonParameters={key: [] for key in fragment["m_CommonParameters"]},
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


def produce(request):
    source_root = Path(request["pc"]).resolve(strict=True)
    source = request["source"]
    path = shader.relative(source_root, source["path"])
    shader.checked(path, source)
    output = Path(request["output"]).resolve()
    if output.is_relative_to(source_root) or source_root.is_relative_to(output):
        raise ValueError("translation output must be disjoint from original inputs")
    typ = objects.source_record_type(path, source["member"], source["path_id"], 48)
    obj = next(row for row in UnityPy.load(str(path)).objects if row.assets_file.name == source["member"] and row.path_id == source["path_id"])
    output.mkdir()
    directory = output / "programs"
    directory.mkdir()
    tree = translate_tree(obj.read_typetree(), directory, request["tools"])
    body = objects.W.write_shader_body(obj.serialized_type.node, tree)
    types = []
    type_id = objects.record_type(typ, types, {})
    row = dict(request["record"], offset=0, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), type_id=type_id)
    (output / "objects.bin").write_bytes(body)
    (output / "index.jsonl").write_text(json.dumps(row, sort_keys=True) + "\n")
    (output / "types.json").write_text(json.dumps(types, sort_keys=True, indent=2) + "\n")
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(json.loads(args.request.read_text())), sort_keys=True))
