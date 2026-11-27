"""Translate bounded source DXBC Shader and ComputeShader records to Unity Vulkan."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import lz4.block

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


def compile_spirv(tools, directory, index, dxbc, descriptors, *, vertex=False):
    source = directory / f"{index}.dxbc"
    spirv = directory / f"{index}.spv"
    source.write_bytes(dxbc)
    subprocess.run([tools["dxbc"], source, spirv, *descriptors], check=True)
    if vertex:
        glsl = directory / f"{index}.vert"
        subprocess.run([tools["spirv_cross"], spirv, "--version", "450", "--vulkan-semantics", "--flip-vert-y", "--output", glsl], check=True)
        subprocess.run([tools["glslang"], "-V", "--target-env", "vulkan1.0", "-o", spirv, glsl], check=True)
    subprocess.run([tools["spirv_val"], "--target-env", "vulkan1.0", spirv], check=True)
    return spirv.read_bytes()


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
            spirv = compile_spirv(tools, directory, index, program, descriptors, vertex=vertex)
            code = subprocess.run([tools["smolv"]], input=spirv, capture_output=True, check=True).stdout
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
        if keywords or kernel["inBuffers"] or kernel["builtinSamplers"] or not bytes(kernel["code"]).startswith(b"DXBC"):
            raise ValueError("unqualified DXBC compute resources or code")
        textures = kernel["textures"]
        constants = kernel["cbs"]
        (storage,) = kernel["outBuffers"]
        if (
            len(textures) > 1
            or any(row["texDimension"] != 2 for row in textures)
            or len(constants) > 1
            or storage["texDimension"] != -1
            or any(row["samplerBindPoint"] != -1 or row["generatedName"] for row in [*textures, *constants, storage])
        ):
            raise ValueError("unqualified compute binding layout")
        # Images and storage share set 0; constants use set 1. Unity encodes
        # the descriptor set and the writable-buffer flag in bindPoint.
        descriptors = []
        for rows, kind, descriptor_set, start, flag in (
            (textures, "texture", 0, 0, 0),
            ([storage], "storage", 0, len(textures), 0x2000000),
            (constants, "cbv", 1, 0, 0),
        ):
            for slot, row in enumerate(rows, start):
                descriptors.extend((kind, str(row["bindPoint"]), str(descriptor_set), str(slot)))
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
    if profile is None:
        records = [{"source": request["source"], "output": request["record"]}]
    else:
        path = Path(profile["path"]).resolve(strict=True)
        shader.checked(path, profile)
        records = json.loads(path.read_bytes())["typed_records"]
        if not records:
            raise ValueError("translated Shader profile is empty")

    directory = output / "programs"
    directory.mkdir(parents=True)
    rows, types, type_ids = [], [], {}
    with (output / "objects.bin").open("xb") as stream:
        for target, typ, original in source_records(root, records):
            stage_dir = directory / str(len(rows))
            stage_dir.mkdir()
            node = objects.W.shader_node(typ["tree"])
            translate = translate_tree if typ["class_id"] == 48 else translate_compute
            tree = translate(objects.W.read_shader_body(node, original), stage_dir, request["tools"])
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
    (output / "result.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(json.loads(args.request.read_text())), sort_keys=True))
