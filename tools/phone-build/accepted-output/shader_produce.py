"""Source-derived Android Shader48 records; no accepted-byte suppliers.

Native record layout follows the pinned ShaderSubProgram reader and existing
shader_segments.parameter_layout. Fresh compiler reflection owns every resource,
constant and vertex-channel binding. Final content construction uses original
PC schema and authored ShaderLab, never a target object body.
"""

from copy import deepcopy
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import time


def spooky(data):
    """Zero-seed little-endian SpookyHash V2, Bob Jenkins (public domain).

    Python expression of the public algorithm, avoiding a native hash provider
    during phone reconstruction. Reference: burtleburtle.net/bob/c/SpookyV2.h.
    """
    mask, constant = (1 << 64) - 1, 0xDEADBEEFDEADBEEF

    def rotate(value, bits):
        return ((value << bits) | (value >> (64 - bits))) & mask

    def short_mix(state):
        for i, bits in enumerate((50, 52, 30, 41, 54, 48, 38, 37, 62, 34, 5, 36)):
            a, b, c = (i + 2) % 4, (i + 3) % 4, i % 4
            state[a] = (rotate(state[a], bits) + state[b]) & mask
            state[c] ^= state[a]

    if len(data) < 192:
        state = [0, 0, constant, constant]
        cursor = 0
        while cursor + 32 <= len(data):
            a, b, c, d = struct.unpack_from("<4Q", data, cursor)
            state[2] = (state[2] + a) & mask
            state[3] = (state[3] + b) & mask
            short_mix(state)
            state[0] = (state[0] + c) & mask
            state[1] = (state[1] + d) & mask
            cursor += 32
        if len(data) - cursor >= 16:
            a, b = struct.unpack_from("<2Q", data, cursor)
            state[2] = (state[2] + a) & mask
            state[3] = (state[3] + b) & mask
            short_mix(state)
            cursor += 16
        tail = data[cursor:]
        state[3] = (state[3] + (len(data) << 56)) & mask
        state[2] = (state[2] + (int.from_bytes(tail[:8], "little") if tail else constant)) & mask
        state[3] = (state[3] + (int.from_bytes(tail[8:], "little") if tail else constant)) & mask
        for i, bits in enumerate((15, 52, 26, 51, 28, 9, 47, 54, 32, 25, 63)):
            a, b = (i + 3) % 4, (i + 2) % 4
            state[a] ^= state[b]
            state[b] = rotate(state[b], bits)
            state[a] = (state[a] + state[b]) & mask
    else:
        state = [0, 0, constant] * 4
        cursor = 0
        while cursor + 96 <= len(data):
            block = struct.unpack_from("<12Q", data, cursor)
            for i, bits in enumerate((11, 32, 43, 31, 17, 28, 39, 57, 55, 54, 22, 46)):
                state[i] = (state[i] + block[i]) & mask
                state[(i + 2) % 12] ^= state[(i + 10) % 12]
                state[(i + 11) % 12] ^= state[i]
                state[i] = rotate(state[i], bits)
                j = (i + 11) % 12
                state[j] = (state[j] + state[(i + 1) % 12]) & mask
            cursor += 96
        tail = data[cursor:]
        final = tail + bytes(95 - len(tail)) + bytes([len(tail)])
        state = [(a + b) & mask for a, b in zip(state, struct.unpack("<12Q", final))]
        for _ in range(3):
            for i, bits in enumerate((44, 15, 34, 21, 38, 33, 10, 13, 38, 53, 42, 54)):
                a, b, c = (i + 11) % 12, (i + 1) % 12, (i + 2) % 12
                state[a] = (state[a] + state[b]) & mask
                state[c] ^= state[a]
                state[b] = rotate(state[b], bits)
    return struct.pack("<2Q", *state[:2])


VERSION = 202012090


def words(*values):
    return struct.pack("<" + "I" * len(values), *values)


def string(value):
    data = value.encode("utf-8")
    return words(len(data)) + data + bytes(-len(data) % 4)


def reflection(rows):
    result = {"inputs": [], "buffers": [], "textures": [], "bindings": []}
    current = None
    for line in rows:
        kind, fields = line.split(": ", 1)
        fields = fields.split()
        if kind == "input":
            result["inputs"].append(list(map(int, fields)))
        elif kind == "cb":
            name, size, count = fields
            current = {"name": name, "size": int(size), "count": int(count), "constants": []}
            result["buffers"].append(current)
        elif kind == "const":
            if current is None:
                raise ValueError("constant before constant buffer")
            name, offset, kind, matrix, rows, columns, array = fields
            current["constants"].append(
                {
                    "name": name,
                    "offset": int(offset),
                    "type": int(kind),
                    "matrix": bool(int(matrix)),
                    "rows": int(rows),
                    "columns": int(columns),
                    "array": int(array),
                }
            )
        elif kind == "cbbind":
            name, index = fields
            result["bindings"].append({"name": name, "index": int(index)})
        elif kind == "texbind":
            name, texture, sampler, multisample, dimension = fields
            result["textures"].append(
                {"name": name, "texture": int(texture), "sampler": int(sampler), "multisample": bool(int(multisample)), "dimension": int(dimension)}
            )
        else:
            raise ValueError("unsupported reflection kind: " + kind)
    for buffer in result["buffers"]:
        if len(buffer["constants"]) != buffer["count"]:
            raise ValueError("constant buffer count differs")
    return result


def native_parameters(reflect, common=None):
    """Move only shared reflection rows to the serialized common tables."""
    common = reflect if common is None else common
    buffers = [{"name": "", "size": 0, "constants": []}] + reflect["buffers"]
    result = [words(VERSION, len(buffers))]
    for buffer in buffers:
        variables = [] if buffer in common["buffers"] else buffer.get("constants", [])
        result.append(string(buffer["name"]) + words(buffer["size"], len(variables)))
        # SDK SaveParametersToData writes the vector array, then matrices.
        for variable in sorted(variables, key=lambda row: row["matrix"]):
            result.append(
                string(variable["name"])
                + words(variable["type"], variable["rows"], variable["columns"], int(variable["matrix"]), variable["array"], variable["offset"])
            )
        result.append(words(0))  # No structured constants in this source cohort.
    bindings = [row for row in reflect.get("bindings", []) if row not in common.get("bindings", [])]
    textures = [row for row in reflect.get("textures", []) if row not in common.get("textures", [])]
    result.append(words(len(textures) + len(bindings)))
    # SDK SaveParametersToData writes noncommon textures before CB bindings.
    result.extend(
        string(row["name"]) + words(0, row["texture"], row["sampler"], ((row["dimension"] & 0xFF) << 1) | int(row["multisample"])) for row in textures
    )
    result.extend(string(row["name"]) + words(1, row["index"], 0) for row in bindings)
    return b"".join(result)


def native_executable(payload, gpu_type, reflect, keywords=()):
    channels = reflect["inputs"]
    mask = 0
    for channel, binding in channels:
        if channel not in range(32) or binding < 0:
            raise ValueError("unqualified vertex channel")
        mask |= 1 << channel
    # Native keyword strings sort independently of source keyword registration.
    head = words(VERSION, gpu_type, 0, 0, 0, 0, len(keywords)) + b"".join(string(keyword) for keyword in sorted(keywords)) + words(len(payload))
    return head + payload + bytes(-len(payload) % 4) + words(mask, len(channels)) + b"".join(words(*row) for row in channels)


def segment(records):
    cursor = 4 + 12 * len(records)
    table = []
    for record in records:
        table.append(words(cursor, len(record), 0))
        cursor += len(record)
    return words(len(records)) + b"".join(table) + b"".join(records)


def common_parameters(reflect):
    names = []

    def index(name):
        if name not in names:
            names.append(name)
        return names.index(name)

    result = {
        k: []
        for k in (
            "m_VectorParams",
            "m_MatrixParams",
            "m_TextureParams",
            "m_BufferParams",
            "m_ConstantBuffers",
            "m_ConstantBufferBindings",
            "m_UAVParams",
            "m_Samplers",
        )
    }
    for texture in reflect["textures"]:
        result["m_TextureParams"].append(
            {
                "m_NameIndex": index(texture["name"]),
                "m_Index": texture["texture"],
                "m_SamplerIndex": texture["sampler"],
                "m_MultiSampled": texture["multisample"],
                "m_Dim": texture["dimension"],
            }
        )
    # Native CreateNamesTable allocates every CB name before its members.
    for buffer in reflect["buffers"]:
        index(buffer["name"])
    for buffer in reflect["buffers"]:
        row = {
            "m_NameIndex": index(buffer["name"]),
            "m_MatrixParams": [],
            "m_VectorParams": [],
            "m_StructParams": [],
            "m_Size": buffer["size"],
            # Native DeduplicateParameters marks each common CB partial,
            # including fragment buffers; the name prefix is irrelevant.
            "m_IsPartialCB": True,
        }
        # SDK CreateNamesTable visits vector members before matrix members.
        for constant in sorted(buffer["constants"], key=lambda row: row["matrix"]):
            value = {"m_NameIndex": index(constant["name"]), "m_Index": constant["offset"], "m_ArraySize": constant["array"], "m_Type": constant["type"]}
            if constant["matrix"]:
                value["m_RowCount"] = constant["rows"]
                row["m_MatrixParams"].append(value)
            else:
                value["m_Dim"] = constant["columns"]
                row["m_VectorParams"].append(value)
        result["m_ConstantBuffers"].append(row)
    for binding in reflect["bindings"]:
        result["m_ConstantBufferBindings"].append({"m_NameIndex": index(binding["name"]), "m_Index": binding["index"], "m_ArraySize": 1})
    return {"m_NameIndices": sorted([[name, i] for i, name in enumerate(names)]), "m_CommonParameters": result}


def variant_records(variants, keyword_names):
    """Factor fresh reflection and emit parameters before linked executables."""
    reflects = [reflection(variant["compilation"]["reflection"]) for variant in variants]
    common = {key: [row for row in reflects[0][key] if all(row in reflect[key] for reflect in reflects[1:])] for key in ("buffers", "bindings", "textures")}
    records, parameters, programs = [], [], []

    def intern(record):
        if record not in records:
            records.append(record)
        return records.index(record)

    for reflect in reflects:
        parameters.append(intern(native_parameters(reflect, common)))
    for variant, reflect in zip(variants, reflects):
        compiled = variant["compilation"]
        index = intern(native_executable(compiled["data"], compiled["gpu_program_type"], reflect, variant["keywords"]))
        programs.append(
            {
                "m_BlobIndex": index,
                "m_KeywordIndices": sorted(keyword_names.index(key) for key in variant["keywords"]),
                "m_ShaderRequirements": variant["requirements"],
                "m_GpuProgramType": compiled["gpu_program_type"],
            }
        )
    return segment(records), common_parameters(common), programs, parameters


def default(node):
    """Construct an empty typed value from original native schema, never a body."""
    if node.m_Type == "string":
        return ""
    if node.m_Children and node.m_Children[0].m_Type == "Array":
        return []
    if node.m_Children:
        return {child.m_Name: default(child) for child in node.m_Children}
    return False if node.m_Type == "bool" else 0


def child(node, name):
    return next(row for row in node.m_Children if row.m_Name == name)


def item(node):
    return node.m_Children[0].m_Children[1]


def value(number=0, name="<noninit>"):
    return {"val": float(number), "name": name}


def properties(prop_node, shaderlab):
    block = re.search(r"\bProperties\s*\{(.*?)\}\s*SubShader", shaderlab, re.S)
    if block is None:
        return []
    pattern = (
        r'((?:\[Normal\]\s*)*)(\w+)\s*\(\s*"([^"]+)"\s*,\s*(2D|Cube|Color|Vector|Float|Range\s*\([^)]*\))\s*\)\s*=\s*("[^"]+"\s*\{\s*\}|\([^)]*\)|[-+\d.eE]+)'
    )
    result = []
    for match in re.finditer(pattern, block[1]):
        attributes, name, description, kind, literal = match.groups()
        prop = default(prop_node)
        prop.update({"m_Name": name, "m_Description": description, "m_Type": {"Color": 0, "Vector": 1, "Float": 2, "2D": 4, "Cube": 4}.get(kind, 3)})
        # Recognized Normal is consumed into ShaderPropertyFlags.Normal.
        prop["m_Flags"] = 8 if attributes else 0
        prop["m_DefTexture"]["m_TexDim"] = 1
        if kind in ("2D", "Cube"):
            prop["m_DefTexture"] = {"m_DefaultName": re.search(r'"([^"]+)"', literal)[1], "m_TexDim": 2 if kind == "2D" else 4}
        else:
            values = [float(part.strip()) for part in literal.strip("()").split(",")]
            if len(values) != (4 if kind in ("Color", "Vector") else 1):
                raise ValueError("unsupported shader property default")
            if kind.startswith("Range"):
                limits = [float(part) for part in re.search(r"\(([^)]+)\)", kind)[1].split(",")]
                if len(limits) != 2:
                    raise ValueError("unsupported shader property range")
                values.extend(limits)
            for i, number in enumerate(values):
                prop[f"m_DefValue[{i}]"] = number
        result.append(prop)
    if re.sub(pattern, "", block[1]).strip():
        raise ValueError("unsupported shader property declaration")
    return result


def render_state(shaderlab, gpu_program_id):
    # Native defaults; source directives below override only declared state.
    blend = {
        name: value(number)
        for name, number in (
            ("srcBlend", 1),
            ("destBlend", 0),
            ("srcBlendAlpha", 1),
            ("destBlendAlpha", 0),
            ("blendOp", 0),
            ("blendOpAlpha", 0),
            ("colMask", 15),
        )
    }
    stencil = {name: value(number) for name, number in (("pass", 0), ("fail", 0), ("zFail", 0), ("comp", 8))}
    state = {"m_Name": "", **{f"rtBlend{i}": deepcopy(blend) for i in range(8)}, "rtSeparateBlend": False}
    state.update(
        {
            name: value(number)
            for name, number in (
                ("zClip", 1),
                ("zTest", 4),
                ("zWrite", 1),
                ("culling", 2),
                ("conservative", 0),
                ("offsetFactor", 0),
                ("offsetUnits", 0),
                ("alphaToMask", 0),
                ("stencilReadMask", 255),
                ("stencilWriteMask", 255),
                ("stencilRef", 0),
            )
        }
    )
    state.update({name: deepcopy(stencil) for name in ("stencilOp", "stencilOpFront", "stencilOpBack")})
    state.update(
        {name: value(0, binding) for name, binding in (("fogStart", "unity_FogStart"), ("fogEnd", "unity_FogEnd"), ("fogDensity", "unity_FogDensity"))}
    )
    state["fogColor"] = {**{axis: value() for axis in "xyzw"}, "name": "unity_FogColor"}
    state.update({"fogMode": -1, "gpuProgramID": gpu_program_id, "m_Tags": {"tags": []}, "m_LOD": 0, "lighting": False})
    tokens = {
        "Off": 0,
        "On": 1,
        "Front": 1,
        "Back": 2,
        "Never": 1,
        "Less": 2,
        "Equal": 3,
        "LEqual": 4,
        "Greater": 5,
        "NotEqual": 6,
        "GEqual": 7,
        "Always": 8,
        "Zero": 0,
        "One": 1,
        "SrcAlpha": 5,
        "OneMinusSrcAlpha": 10,
    }

    def scalar(token):
        if token.startswith("["):
            return value(0, token[1:-1])
        if token not in tokens:
            raise ValueError("unsupported source render state: " + token)
        return value(tokens[token])

    token = r"(\[[^\]]+\]|\w+)"
    source = re.sub(r"//[^\n]*", "", shaderlab)
    for command, field in (("Cull", "culling"), ("ZWrite", "zWrite"), ("ZTest", "zTest")):
        matches = re.findall(r"\b" + command + r"\s+" + token, source)
        if matches:
            state[field] = scalar(matches[-1])
    command = re.search(r"\bBlend\s+" + token + r"\s+" + token, source)
    if command:
        fields = command.groups()
        for field, operand in (("srcBlend", fields[0]), ("destBlend", fields[1]), ("srcBlendAlpha", fields[0]), ("destBlendAlpha", fields[1])):
            try:
                state["rtBlend0"][field] = scalar(operand)
            except ValueError as error:
                raise ValueError("unsupported source Blend") from error
    return state


def source_tags(shaderlab):
    # Source PC SerializedTagMap observations: every one of223 multitag maps in
    # the schema provider bundle is ordered by canonical key string, not source
    # declaration order. QUEUE's canonical spelling is the existing SDK registry.
    tags = re.search(r"\bTags\s*\{([^}]+)\}", shaderlab)
    result = []
    for key, text in re.findall(r'"([^"]+)"\s*=\s*"([^"]+)"', tags[1]) if tags else []:
        key = {"queue": "QUEUE", "ignoreprojector": "IGNOREPROJECTOR"}.get(key.casefold(), key)
        # SDK shadertag::Initialize interns literal true before authored input.
        if key == "IGNOREPROJECTOR":
            text = text.lower()
        result.append([key, text])
    return sorted(result)


def grab_pass(pass_node, texture_name):
    """Named ShaderLab GrabPass: no programs/hash and an unbound native state."""
    shader_pass = default(pass_node)
    shader_pass.update({"m_Type": 2, "m_TextureName": texture_name})
    state = render_state("", -1)
    for name in ("zClip", "zTest", "zWrite", "culling", "stencilReadMask", "stencilWriteMask", "fogStart", "fogEnd", "fogDensity"):
        state[name] = value()
    for name in ("stencilOp", "stencilOpFront", "stencilOpBack"):
        state[name]["comp"] = value()
    state["fogColor"]["name"] = "<noninit>"
    shader_pass["m_State"] = state
    return shader_pass


def source_keyword_registration(preprocessing, builtin_keywords):
    """Register fog names retained by the source build's automatic fog stripping.

    J850 builds one EmptyScene Lab scene with fog disabled. Names remain
    registered while only the no-fog executable survives the build.
    """
    names, flags = (list(values) for values in builtin_keywords)
    for row in preprocessing["records"]:
        if not row["kind"].startswith("keywords") or "values" not in row:
            continue
        for axis in row["values"]:
            if row["kind"] != "keywordsUserGlobal" or axis != "__ FOG_LINEAR FOG_EXP FOG_EXP2":
                raise ValueError("unsupported authored shader keyword variants")
            for name in axis.split()[1:]:
                if name not in names:
                    names.append(name)
                    flags.append(0)
    return names, flags


def native_keywords(preprocessing, builtin_keywords):
    """Register emitted native-wrapper axes and retain their declaration order."""
    names, flags = (list(values) for values in builtin_keywords)
    sets = [[]]
    for row in preprocessing["records"]:
        if row["kind"] not in ("keywordsUserLocal", "keywordsUserGlobal") or row["fields"][1] != 0:
            continue
        for axis in row["values"]:
            options = axis.split()
            for name in options:
                if name != "__" and name not in names:
                    names.append(name)
                    flags.append(int(row["kind"] == "keywordsUserLocal"))
            sets = [keys + ([] if key == "__" else [key]) for keys in sets for key in options]
    return names, flags, sets


def construct(node, shaderlab, preprocessing, compilation, payload, compressed, editor_hash, builtin_keywords):
    """Construct the complete typed Shader value from source/native outputs."""
    if len(editor_hash) != 16:
        raise ValueError("source-derived editor hash must be 16 bytes")
    if not compilation["success"] or not payload:
        raise ValueError("fresh native compiler output drift")
    if re.findall(r"\b(?:CG|HLSL)PROGRAM\b", shaderlab) != ["CGPROGRAM"]:
        raise ValueError("only the single CGPROGRAM control is supported")
    records = preprocessing["records"]
    (snippet,) = preprocessing["snippets"]
    gpu_program_id = snippet["fields"][0]
    requirements = next(row["requirements"] for row in records if row["kind"] == "keywordsEnd")
    names, flags = source_keyword_registration(preprocessing, builtin_keywords)
    name = re.search(r'\bShader\s+"([^"]+)"', shaderlab).group(1)
    result = default(node)
    form_node = child(node, "m_ParsedForm")
    form = result["m_ParsedForm"]
    prop_node = item(child(child(form_node, "m_PropInfo"), "m_Props"))
    form["m_PropInfo"]["m_Props"] = properties(prop_node, shaderlab)
    sub_node = item(child(form_node, "m_SubShaders"))
    sub = default(sub_node)
    sub["m_Tags"]["tags"] = source_tags(shaderlab)
    pass_node = item(child(sub_node, "m_Passes"))
    shader_pass = default(pass_node)
    shader_pass.update(
        {
            "m_EditorDataHash": [{f"bytes[{i}]": b for i, b in enumerate(editor_hash)}],
            "m_Platforms": [18],
            "m_State": render_state(shaderlab, gpu_program_id),
            # Vertex bit1 and fragment bit2. Vulkan executable owns both stages.
            "m_ProgramMask": (1 << 1) | (1 << 2),
        }
    )
    # Parser state inheritance copies SubShader tags into the pass state.
    shader_pass["m_State"]["m_Tags"] = deepcopy(sub["m_Tags"])
    reflect = reflection(compilation["reflection"])
    tables = common_parameters(reflect)
    shader_pass["m_NameIndices"] = tables["m_NameIndices"]
    program = shader_pass["progVertex"]
    # J850's source project_input_rebuild.graphics_settings explicitly retains
    # Android graphics tiers0,1,2; slot3 is the non-tier-specific table.
    # This source has no tier-sensitive branches: reuse its linked executable.
    variant = {"m_BlobIndex": 1, "m_KeywordIndices": [], "m_ShaderRequirements": requirements, "m_GpuProgramType": compilation["gpu_program_type"]}
    program["m_PlayerSubPrograms"] = [[deepcopy(variant)] for _ in range(3)] + [[]]
    program["m_ParameterBlobIndices"] = [[0] for _ in range(3)] + [[]]
    program["m_CommonParameters"] = tables["m_CommonParameters"]
    form["m_KeywordNames"], form["m_KeywordFlags"] = names, flags
    shader_pass["m_SerializedKeywordStateMask"] = list(range(len(names)))
    sub["m_Passes"] = [shader_pass]
    grab = re.search(r'\bGrabPass\s*\{\s*"([^"]+)"\s*\}', shaderlab)
    if grab:
        sub["m_Passes"].insert(0, grab_pass(pass_node, grab[1]))
    form["m_SubShaders"] = [sub]
    form["m_Name"] = name
    raw = segment([native_parameters(reflect), native_executable(payload, compilation["gpu_program_type"], reflect)])
    # stageCounts counts serialized executable-owning stage tables. The linked
    # GPU25 pair is one native stage owner, although ProgramMask has two bits.
    stage_count = sum(
        bool(shader_pass[name]["m_PlayerSubPrograms"]) for name in ("progVertex", "progFragment", "progGeometry", "progHull", "progDomain", "progRayTracing")
    )
    result.update(
        {
            "platforms": [18],
            "offsets": [[0]],
            "compressedLengths": [[len(compressed)]],
            "decompressedLengths": [[len(raw)]],
            "compressedBlob": list(compressed),
            "stageCounts": [stage_count],
            "m_ShaderIsBaked": True,
        }
    )
    return result


def native_state(source_state, gpu_program_id, ui):
    """Apply only state emitted by shader_materials' measured source wrappers."""
    state = render_state("Cull Off ZWrite Off ZTest Always", gpu_program_id)
    for name in ("m_Name", "m_Tags", "culling", "zWrite", "zTest", "stencilRef", "stencilReadMask", "stencilWriteMask"):
        state[name] = deepcopy(source_state[name])
    for name in ("srcBlend", "destBlend", "srcBlendAlpha", "destBlendAlpha", "colMask"):
        state["rtBlend0"][name] = deepcopy(source_state["rtBlend0"][name])
    state["stencilOp"] = deepcopy(source_state["stencilOp" if ui else "stencilOpFront"])
    return state


def construct_native(node, original, resource, preprocessing, variants, compressed, identity, builtin_keywords, ui):
    """Preserve PC fields explicitly emitted by the existing source owner."""
    result = default(node)
    form_node = child(node, "m_ParsedForm")
    sub_node = item(child(form_node, "m_SubShaders"))
    sub = default(sub_node)
    shader_pass = default(item(child(sub_node, "m_Passes")))
    source_form = original["m_ParsedForm"]
    source_sub = source_form["m_SubShaders"][0]
    source_state = source_sub["m_Passes"][0]["m_State"]
    (snippet,) = preprocessing["snippets"]
    state = native_state(source_state, snippet["fields"][0], ui)
    names, flags, _ = native_keywords(preprocessing, builtin_keywords)
    raw, tables, programs, parameters = variant_records(variants, names)
    shader_pass.update(
        {
            "m_EditorDataHash": [{f"bytes[{i}]": byte for i, byte in enumerate(identity)}],
            "m_Platforms": [18],
            "m_State": state,
            "m_ProgramMask": 6,
            "m_NameIndices": tables["m_NameIndices"],
            "m_SerializedKeywordStateMask": list(range(len(names))),
        }
    )
    shader_pass["progVertex"].update(
        {
            "m_PlayerSubPrograms": [deepcopy(programs) for _ in range(3)] + [[]],
            "m_ParameterBlobIndices": [parameters[:] for _ in range(3)] + [[]],
            "m_CommonParameters": tables["m_CommonParameters"],
        }
    )
    sub.update({"m_Tags": deepcopy(source_sub["m_Tags"]), "m_Passes": [shader_pass]})
    form = result["m_ParsedForm"]
    form.update({"m_Name": "Porting Lab/" + resource, "m_SubShaders": [sub], "m_KeywordNames": names, "m_KeywordFlags": flags})
    form["m_PropInfo"]["m_Props"] = deepcopy(source_form["m_PropInfo"]["m_Props"])
    for prop in form["m_PropInfo"]["m_Props"]:
        prop["m_Attributes"] = []  # Existing properties() emits known flag attributes only.
    result.update(
        {
            "platforms": [18],
            "offsets": [[0]],
            "compressedLengths": [[len(compressed)]],
            "decompressedLengths": [[len(raw)]],
            "compressedBlob": list(compressed),
            "stageCounts": [1],
            "m_ShaderIsBaked": True,
        }
    )
    return result


def native_ui_sources(root, pc, selected, tool, output):
    """Recover the bounded original UI cohort without retained analysis inputs."""
    import UnityPy

    sys.path.insert(0, str(root / "scripts/lab"))
    import shader_materials
    from shader_programs import NativePrograms
    from shader_segments import read_segments

    if selected["d3dasm_revision"] != shader_materials.PINS["d3dasm"][1]:
        raise ValueError("native UI public recovery source revision differs")

    def original(selection):
        environment = UnityPy.load(str(relative(pc, selection["path"])))
        obj = next(row for row in environment.objects if row.path_id == selection["path_id"] and row.assets_file.name == selection["member"])
        if hashlib.sha256(obj.get_raw_data()).hexdigest() != selection["body_sha256"]:
            raise ValueError("native UI original body differs")
        return obj.read_typetree()

    tree = original(selected["source"])
    raw, records, programs = read_segments(tree, bytes(tree["compressedBlob"]))
    context = tree, raw, records, programs, {}
    form = tree["m_ParsedForm"]
    features = set(form["m_KeywordNames"]) - shader_materials.ENGINE - {"UNITY_UI_CLIP_RECT", "UNITY_UI_ALPHACLIP"}
    keys = []
    for source in selected["materials"]:
        material = original(source)
        if material["m_Shader"]["m_PathID"] != selected["source"]["path_id"]:
            raise ValueError("native UI material shader identity differs")
        keys.append(tuple(sorted(set(material["m_ValidKeywords"]) & features)))
    result = {"programs": []}
    emitter = NativePrograms(output, result, tool, allow_independent=False)
    sources = {
        "AndroidNativeFamily6Variant" + str(index): shader_materials.ui_source(context, values, "AndroidNativeFamily6Variant" + str(index), emitter)
        for index, values in enumerate(sorted(set(keys)))
    }
    return tree, sources


def native_cloud_sources(root, pc, selected, tool, output):
    """Recover Cloud using the shared qualified manifest selection policy."""
    import UnityPy

    sys.path.insert(0, str(root / "scripts/lab"))
    import shader_materials
    import shader_metadata
    from shader_programs import NativePrograms
    from shader_segments import read_segments

    if selected["d3dasm_revision"] != shader_materials.PINS["d3dasm"][1]:
        raise ValueError("native Cloud public recovery source revision differs")
    selector_path = relative(root, selected["manifests"]["path"])
    checked(selector_path, selected["manifests"])
    selectors = json.loads(selector_path.read_text())
    pins = [(selector_path, selected["manifests"])]

    def original_bundle(row, digest):
        path = relative(pc, row["path"])
        pin = {"bytes": path.stat().st_size, "sha256": digest}
        checked(path, pin)
        pins.append((path, pin))
        return UnityPy.load(str(path))

    def original_object(objects, member, selected, digest):
        obj = objects[member, selected["path_id"]]
        if hashlib.sha256(obj.get_raw_data()).hexdigest() != digest:
            raise ValueError("native Cloud original body differs")
        return obj, obj.read_typetree()

    source = next(row for row in selectors["shaders"] if row["family"] == "cloud")
    environment = original_bundle(source, source["bundle_sha256"])
    objects = {(obj.assets_file.name, obj.path_id): obj for obj in environment.objects}
    _, tree = original_object(objects, source["member"], source, source["body_sha256"])
    raw, records, programs = read_segments(tree, bytes(tree["compressedBlob"]))
    context = tree, raw, records, programs, {}
    rows = []
    for bundle in selectors["materials"]:
        materials = [
            (member, row)
            for member in bundle["members"]
            for row in member["materials"]
            if (row["shader_member"], row["shader_path_id"]) == (source["member"], source["path_id"])
        ]
        if not materials:
            continue
        environment = original_bundle(bundle, bundle["sha256"])
        objects = {(obj.assets_file.name, obj.path_id): obj for obj in environment.objects}
        for member, selected_material in materials:
            obj, material = original_object(objects, member["name"], selected_material, selected_material["sha256"])
            pointer = material["m_Shader"]
            file_id = pointer["m_FileID"]
            if not 0 <= file_id <= len(obj.assets_file.externals):
                raise ValueError("native Cloud shader pointer extent differs")
            shader_member = member["name"] if file_id == 0 else obj.assets_file.externals[file_id - 1].path.rsplit("/", 1)[-1]
            if (shader_member, pointer["m_PathID"]) != (source["member"], source["path_id"]):
                raise ValueError("native Cloud original shader pointer differs")
            keys = set(material.get("m_ValidKeywords", [])) | set(material.get("m_InvalidKeywords", [])) | set(material.get("m_ShaderKeywords", "").split())
            rows.append((selected_material["asset"], tree["m_ParsedForm"]["m_Name"], ",".join(sorted(keys))))
    _, _, sets = shader_metadata.material_selection(rows, tree["m_ParsedForm"], "cloud")
    emitter = NativePrograms(output, {"programs": []}, tool, allow_independent=False)
    sources = {
        "AndroidNativeFamily0Variant" + str(index): shader_materials.cloud_source(context, keys, "AndroidNativeFamily0Variant" + str(index), emitter)
        for index, keys in enumerate(sets)
    }
    return tree, sources, pins


def sdk_read(image, address, size):
    """Read pinned ARM64 SDK data by Mach-O virtual address; never execute it."""
    if struct.unpack_from("<I", image)[0] != 0xFEEDFACF:
        raise ValueError("shader SDK metadata requires the pinned ARM64 Mach-O")
    cursor = 32
    for _ in range(struct.unpack_from("<I", image, 16)[0]):
        command, length = struct.unpack_from("<II", image, cursor)
        if command == 25:
            virtual, _, offset, extent = struct.unpack_from("<QQQQ", image, cursor + 24)
            if virtual <= address and address + size <= virtual + extent:
                return image[offset + address - virtual : offset + address - virtual + size]
        cursor += length
    raise ValueError("shader SDK data address outside file-backed segments")


def platform_caps(image, settings):
    """Evaluate the pinned SDK's Android/Vulkan tier-0 source settings.

    Attribute/default fields come from SDK BuildTargetDiscovery's Android
    preload. Keyword bit positions follow InitNonTierDependent and
    UpdateTierDependent; values come from authored settings, never a target key.
    """
    attributes = struct.unpack("<I", sdk_read(image, 0x1033B3B18, 4))[0]
    instruction = struct.unpack("<I", sdk_read(image, 0x101B5DA64, 4))[0]
    if instruction & 0xFFE0001F != 0x52800008:
        raise ValueError("shader SDK Android compression instruction differs")
    compression = (instruction >> 5) & 0xFFFF
    lightmap_quality = struct.unpack("<I", sdk_read(image, 0x10338E3FC, 4))[0]
    normal_rgb = not bool(compression & 0x20)
    cube_array = bool(attributes & (0x10 | 4))
    usage = 2 if lightmap_quality == 1 else ((2 if attributes & 0x20000 else 8) if lightmap_quality == 2 else (1 if attributes & 2 else 2))
    flags = 0x20002 | int(normal_rgb) | (int(not cube_array) << 7)
    flags |= int(settings["color_space"] == 0) << 22
    flags |= {1: 1 << 25, 2: 1 << 26, 8: 1 << 27}.get(usage, 0)
    flags |= int(settings["deferred_reflections"] != 0) << 3
    if settings["virtual_texturing"]:
        raise ValueError("virtual-texturing shader keyword policy is unqualified")
    flags |= settings["vulkan_pretransform"] << 29
    flags |= int(settings["shader_precision_model"] == 1) << 32
    tier = settings["tier0"]
    flags |= int(not tier["useCascadedShadowMaps"]) << 8
    flags |= tier["useDitherMaskForAlphaBlendedShadows"] << 9
    flags |= {0: 0x3000, 1: 0x800, 2: 0x400}[tier["standardShaderQuality"]]
    for bit, key in ((14, "useReflectionProbeBoxProjection"), (15, "useReflectionProbeBlending"), (16, "useDetailNormalMap")):
        flags |= tier[key] << bit
    if tier["enableLPPV"]:
        flags |= struct.unpack("<I", sdk_read(image, 0x1033B4490 + (18 - 4) * 4, 4))[0]
    return flags


def platform_keywords(sdk_image, settings):
    """Read the pinned SDK's platform-capability keyword registry."""
    bits = platform_caps(sdk_image, settings)
    pointers = struct.unpack("<33Q", sdk_read(sdk_image, 0x103C4F1B8, 33 * 8))
    names = [sdk_read(sdk_image, address, 128).split(b"\0")[0].decode() for address in pointers]
    return [name for bit, name in enumerate(names) if bits & (1 << bit)]


def compilation_flags(sdk_image, settings):
    """Evaluate the acquired SDK's capability-to-compilation bit moves."""
    bits = platform_caps(sdk_image, settings)
    return (((bits >> 17) & 1) << 28) | (((bits >> 6) & 1) << 14) | (((bits >> 32) & 1) << 31)


def editor_hash(snippet, sdk_image, capabilities, settings, common_bytes):
    """SDK ComputeShaderSnippetKey's base key, its second output.

    The first output additionally hashes keyword state/stage and is not the
    serialized pass identity. Cached preprocessing must also supply the snippet's
    include hash; toggling only the flag changes the key incorrectly.
    """
    version = capabilities[18][1] ^ struct.unpack("<I", sdk_read(sdk_image, 0x103396C84 + 18 * 4, 4))[0]
    if version & 0x80000000:
        version |= 0xFFFFFFFF00000000
    version |= 0x0C0BE49A00000000
    include_hash = struct.pack("<4I", *(word & 0xFFFFFFFF for word in snippet["fields"][6:10]))
    preimage = spooky(snippet["source"].encode()) + include_hash
    preimage += struct.pack("<2Q", (int(settings["caching_preprocessor"]) << 7) | (18 << 8), version)
    preimage += spooky(struct.pack("<Q", platform_caps(sdk_image, settings))) + spooky(common_bytes)
    return spooky(preimage)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(path, expected):
    if path.resolve(strict=True) != path or not path.is_file():
        raise ValueError("redirected shader input/output")
    if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
        raise ValueError("shader input/output differs: " + path.name)


def relative(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or name in ("", "."):
        raise ValueError("unsafe shader input/output path")
    return root / path


def includes(directory):
    """Pin names and contents; return native hash's sorted file-content stream."""
    digest, contents = hashlib.sha256(), []
    for path in sorted(directory.iterdir(), key=lambda row: row.name):
        if not path.is_file():
            continue
        if path.resolve(strict=True) != path:
            raise ValueError("redirected shader include")
        data = path.read_bytes()
        digest.update(path.name.encode() + b"\0" + data)
        contents.append(data)
    return digest.hexdigest(), b"".join(contents)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def produce(profile_path, profile_sha256, pc, sdk, output, codec_path, codec_sha256, d3dasm_path=None, d3dasm_sha256=None):
    """Produce pinned authored Shader files from PC schema and the acquired SDK.

    SDK is the pinned Unity.app/Contents directory. MacOS/Unity is read only as
    source metadata; only Tools/UnityShaderCompiler executes. The final expected
    file hashes are comparators after complete independent serialization.
    """
    import UnityPy
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    root = Path(__file__).resolve().parents[3]
    profile_path, codec_path = Path(profile_path).absolute(), Path(codec_path).absolute()
    profile_pin = {"bytes": profile_path.stat().st_size, "sha256": profile_sha256}
    codec_pin = {"bytes": codec_path.stat().st_size, "sha256": codec_sha256}
    checked(profile_path, profile_pin)
    checked(codec_path, codec_pin)
    profile = json.loads(profile_path.read_text())
    pc, sdk = Path(pc).resolve(strict=True), Path(sdk).resolve(strict=True)
    output = Path(output)
    output = output.parent.resolve(strict=True) / output.name
    if output.exists():
        raise ValueError("shader output must be a new private directory")
    if any(output.is_relative_to(source) or source.is_relative_to(output) for source in (pc, sdk)):
        raise ValueError("shader output must be disjoint from original game and SDK")
    source = profile["source_type"]
    source_path = relative(pc, source["path"])
    pins = [(profile_path, profile_pin), (codec_path, codec_pin), (source_path, source)]
    pins.extend((relative(sdk, name), pin) for name, pin in profile["sdk"].items())
    pins.extend((relative(root, name), pin) for name, pin in profile["authored_inputs"].items())
    if "native_ui" in profile or "native_cloud" in profile:
        if d3dasm_path is None or d3dasm_sha256 is None:
            raise ValueError("native source recovery requires the explicitly supplied pinned public d3dasm tool")
        d3dasm_path = Path(d3dasm_path).absolute()
        pins.append((d3dasm_path, {"bytes": d3dasm_path.stat().st_size, "sha256": d3dasm_sha256}))
    if "native_ui" in profile:
        pins.extend((relative(pc, row["path"]), row) for row in [profile["native_ui"]["source"], *profile["native_ui"]["materials"]])
    for path, pin in pins:
        checked(path, pin)
        if path.is_relative_to(output) or output.is_relative_to(path):
            raise ValueError("shader output overlaps a pinned input")
    include_dir = sdk / "CGIncludes"
    inventory, common_bytes = includes(include_dir)
    if inventory != profile["includes_sha256"]:
        raise ValueError("shader SDK include inventory differs")
    destinations = []
    for shader in profile["shaders"]:
        name = shader["file"]
        if PurePosixPath(name).name != name or name in ("", ".", "..") or "\\" in name:
            raise ValueError("unsafe shader player filename")
        if "native_resource" in shader:
            if "native_ui" not in profile and "native_cloud" not in profile:
                raise ValueError("native shader lacks original input selectors")
        else:
            if shader["source"] not in profile["authored_inputs"]:
                raise ValueError("shader source lacks an authored input pin")
            relative(root, shader["source"])
        relative(root, shader["filename"])
        destinations.append("apk/assets/bin/Data/" + name)
    if len(destinations) != len(set(destinations)):
        raise ValueError("duplicate shader player file")
    W = module("_shader_unity_write", Path(__file__).with_name("unity_write.py"))
    compiler = module("_shader_compiler", Path(__file__).parents[1] / "owner-code/shader.py")
    layout = W.read_serialized(W.B.Bundle(source_path).member(source["member"]))
    selected = next(row for row in layout["objects"] if row["path_id"] == source["path_id"])
    native_type = layout["types"][selected["type_id"]]
    if native_type["class_id"] != 48:
        raise ValueError("original shader schema provider is not Shader48")
    environment = UnityPy.load(str(source_path))
    obj = next(row for row in environment.objects if row.path_id == source["path_id"])
    node = obj.serialized_type.node
    original_form = obj.read_typetree()["m_ParsedForm"]
    registry = original_form["m_KeywordNames"][:4], original_form["m_KeywordFlags"][:4]
    sdk_image = (sdk / "MacOS/Unity").read_bytes()
    compile_keywords = platform_keywords(sdk_image, profile["settings"])
    compile_flags = compilation_flags(sdk_image, profile["settings"])
    output.mkdir()
    native_sources = {}
    result = {
        "success": False,
        "input_id": profile["input_id"],
        "profile_sha256": profile_sha256,
        "inputs": {
            "source_type": source,
            "sdk": profile["sdk"],
            "includes_sha256": inventory,
            "authored": profile["authored_inputs"],
            "codec_sha256": codec_sha256,
        },
        "files": {},
    }
    started = time.monotonic()
    try:
        if "native_ui" in profile:
            recovery = output / "native-ui"
            recovery.mkdir()
            tree, sources = native_ui_sources(root, pc, profile["native_ui"], d3dasm_path, recovery)
            native_sources.update({name: (tree, source, True) for name, source in sources.items()})
            result["inputs"]["native_ui"] = profile["native_ui"]
            result["inputs"]["d3dasm_sha256"] = d3dasm_sha256
        if "native_cloud" in profile:
            recovery = output / "native-cloud"
            recovery.mkdir()
            tree, sources, providers = native_cloud_sources(root, pc, profile["native_cloud"], d3dasm_path, recovery)
            native_sources.update({name: (tree, source, False) for name, source in sources.items()})
            pins.extend(providers)
            result["inputs"]["native_cloud"] = profile["native_cloud"]
            result["inputs"]["d3dasm_sha256"] = d3dasm_sha256
        with (
            compiler.compiler([sdk / "Tools/UnityShaderCompiler"], sdk, output / "compiler", includes=[include_dir]) as connection,
            W.codec(codec_path, codec_sha256) as compress,
        ):
            for shader, name in zip(profile["shaders"], destinations):
                shaderlab = native_sources[shader["native_resource"]][1] if "native_resource" in shader else relative(root, shader["source"]).read_text()
                preprocessing = connection.preprocess(
                    shaderlab,
                    shader["filename"],
                    platform_keywords=["SHADER_API_MOBILE"],
                    caching_preprocessor=profile["settings"]["caching_preprocessor"],
                )
                if not preprocessing["success"] or len(preprocessing["snippets"]) != 1:
                    raise ValueError("single-pass source preprocessing failed")
                (snippet,) = preprocessing["snippets"]
                requirements = next(row["requirements"] for row in preprocessing["records"] if row["kind"] == "keywordsEnd")
                identity = editor_hash(snippet, sdk_image, connection.capabilities, profile["settings"], common_bytes)
                if "native_resource" in shader:
                    names, _, keyword_sets = native_keywords(preprocessing, registry)
                else:
                    keyword_sets = [[]]
                variants = []
                for keywords in keyword_sets:
                    compilation = connection.compile(
                        snippet["source"],
                        shader["filename"],
                        stage="vertex",
                        platform_keywords=compile_keywords,
                        keywords=keywords,
                        flags=compile_flags,
                        requirements=requirements,
                    )
                    if not compilation["success"] or not compilation["data"]:
                        raise ValueError("linked Vulkan shader compilation failed")
                    variants.append({"keywords": keywords, "requirements": requirements, "compilation": compilation})
                if "native_resource" in shader:
                    raw = variant_records(variants, names)[0]
                    original, _, ui = native_sources[shader["native_resource"]]
                    tree = construct_native(node, original, shader["native_resource"], preprocessing, variants, compress(raw, 9), identity, registry, ui)
                else:
                    reflect = reflection(compilation["reflection"])
                    raw = segment([native_parameters(reflect), native_executable(compilation["data"], compilation["gpu_program_type"], reflect)])
                    tree = construct(node, shaderlab, preprocessing, compilation, compilation["data"], compress(raw, 9), identity, registry)
                body_writer = EndianBinaryWriter(endian="<")
                write_typetree(tree, node, body_writer)
                body = body_writer.bytes
                destination = output / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                standalone = {
                    "engine": "2021.3.45f2",
                    "platform": 13,
                    "trees": False,
                    "types": [native_type],
                    "objects": [{"path_id": 1, "type_id": 0, "offset": 0, "bytes": len(body)}],
                    "scripts": [],
                    "externals": [],
                    "ref_types": [],
                    "user": "",
                }
                with destination.open("wb") as stream:
                    W.write_serialized(stream, standalone, lambda _: io.BytesIO(body))
                # Expected accepted size/hash only compare a fully persisted file.
                checked(destination, shader)
                result["files"][name] = {"bytes": destination.stat().st_size, "sha256": sha(destination)}
        for path, pin in pins:
            checked(path, pin)
        if includes(include_dir)[0] != inventory:
            raise ValueError("shader SDK includes changed during production")
        for name, pin in result["files"].items():
            checked(output / name, pin)
        result["success"] = True
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True, help="original installation root; output must be disjoint")
    parser.add_argument("--sdk", type=Path, required=True, help="pinned Unity.app/Contents SDK root; Editor is read as data only")
    parser.add_argument("--output", type=Path, required=True, help="new private target-tree root; parent must exist")
    parser.add_argument("--codec", type=Path, required=True)
    parser.add_argument("--codec-sha256", required=True)
    parser.add_argument("--d3dasm", type=Path, help="explicit tool built from the pinned public source; required for native source recovery")
    parser.add_argument("--d3dasm-sha256", help="expected SHA-256 of the caller-supplied public tool")
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.sdk, args.output, args.codec, args.codec_sha256, args.d3dasm, args.d3dasm_sha256)


if __name__ == "__main__":
    main()
