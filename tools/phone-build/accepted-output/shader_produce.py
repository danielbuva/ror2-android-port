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
import itertools
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
    result = {"inputs": [], "constants": [], "buffers": [], "textures": [], "bindings": [], "resource_buffers": []}
    current = None
    for line in rows:
        kind, fields = line.split(": ", 1)
        fields = fields.split()
        if kind == "input":
            result["inputs"].append(list(map(int, fields)))
        elif kind == "cb":
            name, size, count = fields
            current = {"name": name, "size": int(size), "count": int(count), "constants": [], "structures": []}
            result["buffers"].append(current)
        elif kind == "const":
            name, offset, kind, matrix, rows, columns, array = fields
            if int(matrix) == 2:
                if current is None:
                    raise ValueError("structured constant before constant buffer")
                current["structures"].append({"name": name, "offset": int(offset), "array": int(array), "size": int(rows), "constants": []})
            else:
                if int(matrix) not in (0, 1):
                    raise ValueError("unsupported reflected constant type")
                constant = {
                    "name": name,
                    "offset": int(offset),
                    "type": int(kind),
                    "matrix": bool(int(matrix)),
                    "rows": int(rows),
                    "columns": int(columns),
                    "array": int(array),
                }
                if "." in name:
                    prefix, constant["name"] = name.split(".", 1)
                    structure = next((row for row in current["structures"] if row["name"] == prefix), None) if current else None
                    if structure is None or "." in constant["name"]:
                        raise ValueError("undeclared or nested structured constant member")
                    structure["constants"].append(constant)
                else:
                    (result["constants"] if current is None else current["constants"]).append(constant)
        elif kind == "cbbind":
            name, index = fields
            result["bindings"].append({"name": name, "index": int(index)})
        elif kind == "bufferbind":
            name, index, array = fields
            result["resource_buffers"].append({"name": name, "index": int(index), "array": max(1, int(array))})
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
    globals = [row for row in reflect.get("constants", []) if row not in common.get("constants", [])]
    buffers = [{"name": "", "size": 0, "constants": globals}] + reflect["buffers"]
    result = [words(VERSION, len(buffers))]

    def variables(rows):
        # SDK SaveParametersToData writes the vector array, then matrices.
        for variable in sorted(rows, key=lambda row: row["matrix"]):
            result.append(
                string(variable["name"])
                + words(variable["type"], variable["rows"], variable["columns"], int(variable["matrix"]), variable["array"], variable["offset"])
            )

    for index, buffer in enumerate(buffers):
        shared = index > 0 and buffer in common["buffers"]
        constants = [] if shared else buffer.get("constants", [])
        result.append(string(buffer["name"]) + words(buffer["size"], len(constants)))
        variables(constants)
        structures = [] if shared else buffer.get("structures", [])
        result.append(words(len(structures)))
        for structure in structures:
            result.append(string(structure["name"]) + words(structure["offset"], structure["array"], structure["size"], len(structure["constants"])))
            variables(structure["constants"])
    bindings = [row for row in reflect.get("bindings", []) if row not in common.get("bindings", [])]
    textures = [row for row in reflect.get("textures", []) if row not in common.get("textures", [])]
    resource_buffers = [row for row in reflect.get("resource_buffers", []) if row not in common.get("resource_buffers", [])]
    result.append(words(len(textures) + len(bindings) + len(resource_buffers)))
    # SDK SaveParametersToData writes noncommon textures before CB bindings.
    result.extend(
        string(row["name"]) + words(0, row["texture"], row["sampler"] & 0xFFFFFFFF, ((row["dimension"] & 0xFF) << 1) | int(row["multisample"]))
        for row in textures
    )
    result.extend(string(row["name"]) + words(1, row["index"], 0) for row in bindings)
    result.extend(string(row["name"]) + words(2, row["index"], row["array"]) for row in resource_buffers)
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

    def constant_row(constant):
        value = {"m_NameIndex": index(constant["name"]), "m_Index": constant["offset"], "m_ArraySize": constant["array"], "m_Type": constant["type"]}
        value["m_RowCount" if constant["matrix"] else "m_Dim"] = constant["rows"] if constant["matrix"] else constant["columns"]
        return value

    for constant in sorted(reflect.get("constants", []), key=lambda row: row["matrix"]):
        result["m_MatrixParams" if constant["matrix"] else "m_VectorParams"].append(constant_row(constant))
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
            row["m_MatrixParams" if constant["matrix"] else "m_VectorParams"].append(constant_row(constant))
        structures = buffer.get("structures", [])
        for structure in structures:
            index(structure["name"])
        for structure in structures:
            member = {
                "m_NameIndex": index(structure["name"]),
                "m_Index": structure["offset"],
                "m_ArraySize": structure["array"],
                "m_StructSize": structure["size"],
                "m_VectorMembers": [],
                "m_MatrixMembers": [],
            }
            for constant in sorted(structure["constants"], key=lambda row: row["matrix"]):
                member["m_MatrixMembers" if constant["matrix"] else "m_VectorMembers"].append(constant_row(constant))
            row["m_StructParams"].append(member)
        result["m_ConstantBuffers"].append(row)
    for binding in reflect["bindings"]:
        result["m_ConstantBufferBindings"].append({"m_NameIndex": index(binding["name"]), "m_Index": binding["index"], "m_ArraySize": 1})
    # SDK CreateNamesTable visits resource buffers after CB bindings.
    for binding in reflect.get("resource_buffers", []):
        result["m_BufferParams"].append({"m_NameIndex": index(binding["name"]), "m_Index": binding["index"], "m_ArraySize": binding["array"]})
    return {"m_NameIndices": sorted([[name, i] for i, name in enumerate(names)]), "m_CommonParameters": result}


def variant_records(variants, keyword_names):
    """Factor fresh reflection and emit parameters before linked executables."""
    reflects = [reflection(variant["compilation"]["reflection"]) for variant in variants]
    common = {
        key: [row for row in reflects[0][key] if all(row in reflect[key] for reflect in reflects[1:])]
        for key in ("constants", "buffers", "bindings", "textures", "resource_buffers")
    }
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
    blocks = source_blocks(shaderlab, "Properties")
    if not blocks:
        return []
    block = blocks[0][1]
    pattern = r'((?:\[[^\]]+\]\s*)*)(\w+)\s*\(\s*"([^"]*)"\s*,\s*(2DArray|2D|Cube|Color|Vector|Float|Range\s*\([^)]*\))\s*\)\s*=\s*("[^"]*"\s*\{\s*\}|\([^)]*\)|[-+\d.eE]+)'
    result = []
    known = {name: 1 << index for index, name in enumerate(("HideInInspector", "PerRendererData", "NoScaleOffset", "Normal", "HDR", "Gamma"))}
    for match in re.finditer(pattern, block, re.I):
        attributes, name, description, kind, literal = match.groups()
        kind = kind[0].upper() + kind[1:].lower() if kind.lower() in ("color", "vector", "float", "cube") else kind
        prop = default(prop_node)
        prop.update(
            {"m_Name": name, "m_Description": description, "m_Type": {"Color": 0, "Vector": 1, "Float": 2, "2D": 4, "Cube": 4, "2DArray": 4}.get(kind, 3)}
        )
        attributes = re.findall(r"\[([^\]]+)\]", attributes)
        prop["m_Flags"] = sum(known.get(attribute, 0) for attribute in attributes)
        prop["m_Attributes"] = [attribute for attribute in attributes if attribute not in known]
        prop["m_DefTexture"]["m_TexDim"] = 1
        if kind in ("2D", "Cube", "2DArray"):
            prop["m_DefTexture"] = {"m_DefaultName": re.search(r'"([^"]*)"', literal)[1], "m_TexDim": {"2D": 2, "Cube": 4, "2DArray": 5}[kind]}
        else:
            values = [float(part.strip()) for part in literal.strip("()").split(",")]
            if len(values) != (4 if kind in ("Color", "Vector") else 1):
                raise ValueError("unsupported shader property default")
            if kind.lower().startswith("range"):
                limits = [float(part) for part in re.search(r"\(([^)]+)\)", kind)[1].split(",")]
                if len(limits) != 2:
                    raise ValueError("unsupported shader property range")
                values.extend(limits)
            for index, number in enumerate(values):
                prop[f"m_DefValue[{index}]"] = number
        result.append(prop)
    if re.sub(pattern, "", block, flags=re.I).strip():
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
    commands = re.findall(r"\bBlend\s+" + token + r"\s+" + token, source)
    if commands:
        fields = commands[-1]
        for field, operand in (("srcBlend", fields[0]), ("destBlend", fields[1]), ("srcBlendAlpha", fields[0]), ("destBlendAlpha", fields[1])):
            try:
                state["rtBlend0"][field] = scalar(operand)
            except ValueError as error:
                raise ValueError("unsupported source Blend") from error
    for command, field in (("ReadMask", "stencilReadMask"), ("WriteMask", "stencilWriteMask"), ("Ref", "stencilRef")):
        binding = re.search(r"\b" + command + r"\s+\[([^\]]+)\]", source)
        if binding:
            state[field] = value(0, binding[1])
    for command, field in (("Comp", "comp"), ("Pass", "pass")):
        binding = re.search(r"\b" + command + r"\s+\[([^\]]+)\]", source)
        if binding:
            state["stencilOp"][field] = value(0, binding[1])
    mask = re.search(r"\bColorMask\s+\[([^\]]+)\]", source)
    if mask:
        state["rtBlend0"]["colMask"] = value(0, mask[1])
    if re.search(r"\bFog\s*\{\s*Mode\s+Off", source):
        state["fogMode"] = 0
    return state


def source_tags(shaderlab):
    """SDK-interned tag keys/values; SerializedTagMap orders canonical strings."""
    canonical = {
        "queue": "QUEUE",
        "lightmode": "LIGHTMODE",
        "ignoreprojector": "IGNOREPROJECTOR",
        "shadowsupport": "SHADOWSUPPORT",
        "rendertype": "RenderType",
        "disablebatching": "DisableBatching",
    }
    rows = {}
    for _, block in source_blocks(shaderlab, "Tags"):
        for key, text in re.findall(r'"([^"]+)"\s*=\s*"([^"]+)"', block):
            key = canonical.get(key.casefold(), key)
            if key in ("IGNOREPROJECTOR", "SHADOWSUPPORT"):
                text = text.lower()
            if key == "LIGHTMODE":
                text = text.upper()
            if key == "DisableBatching" and text.casefold() == "lodfading":
                text = "LodFading"
            rows[key] = text
    return sorted([[key, text] for key, text in rows.items()])


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


def source_blocks(text, word):
    result = []
    cursor = 0
    pattern = re.compile(r"\b" + word + r"\s*\{")
    while match := pattern.search(text, cursor):
        start, depth, quoted = match.end(), 1, False
        for end in range(start, len(text)):
            char = text[end]
            if char == '"' and text[end - 1] != "\\":
                quoted = not quoted
            if not quoted:
                depth += (char == "{") - (char == "}")
            if not depth:
                result.append((match.start(), text[start:end]))
                cursor = end + 1
                break
        else:
            raise ValueError("unclosed source ShaderLab block")
    return result


def pass_keywords(pre, builtins):
    names, flags = (list(values) for values in builtins)
    masks = {}
    for snippet in pre["snippets"]:
        gpu = snippet["fields"][0]
        mask = list(range(len(builtins[0])))
        for row in pre["records"]:
            if row["kind"] not in ("keywordsUserGlobal", "keywordsUserLocal", "keywordsBuiltin") or row["fields"][0] != gpu:
                continue
            for axis in row["values"]:
                for name in axis.split():
                    if name == "__":
                        continue
                    if name not in names:
                        names.append(name)
                        flags.append(int(row["kind"] == "keywordsUserLocal"))
                    if names.index(name) not in mask:
                        mask.append(names.index(name))
        masks[gpu] = sorted(mask)
    return names, flags, masks


def retained_keywords(pre, gpu, material_keywords=None):
    """Pinned EmptyScene policy, SDK axis order and original material features."""
    no_lightmap = {"LIGHTMAP_ON", "DIRLIGHTMAP_COMBINED", "DYNAMICLIGHTMAP_ON", "SHADOWS_SHADOWMASK", "LIGHTMAP_SHADOW_MIXING"}
    builtin = next((row["values"] for row in pre["records"] if row["kind"] == "keywordsBuiltin" and row["fields"] == [gpu, 0]), [])
    builtin = [row.split() for row in builtin if not set(row.split()) & no_lightmap] if builtin else [[]]
    axes = [
        axis for row in pre["records"] if row["kind"] in ("keywordsUserGlobal", "keywordsUserLocal") and row["fields"] == [gpu, 0] for axis in row["values"]
    ]
    feature_axes, multi_axes = [], []
    req = next(row for row in pre["records"] if row["kind"] == "keywordsEnd" and row["fields"] == [gpu])
    multi_names = set(req.get("keywords", "").split())
    for axis in axes:
        values = axis.split()
        if "FOG_LINEAR" in values or "INSTANCING_ON" in values:
            values = ["__"]
        options = [[] if name == "__" else [name] for name in values]
        (feature_axes if material_keywords is not None and set(values) - {"__"} - multi_names else multi_axes).append(options)
    multi = [sum(values, []) for values in itertools.product(*multi_axes)]
    features = [sum(values, []) for values in itertools.product(*feature_axes)]
    if material_keywords is not None:
        feature_names = {name for axis in feature_axes for option in axis for name in option}
        used = {frozenset(keys) & feature_names for keys in material_keywords}
        features = [keys for keys in features if frozenset(keys) in used]
    # User/multi axes outer, SDK builtin combinations next; actual source
    # material shader_feature combinations are the innermost source selection.
    return [builtin_keys + user_keys + feature_keys for user_keys, builtin_keys, feature_keys in itertools.product(multi, builtin, features)]


def shader_records(passes, keyword_names):
    """Merge fresh per-pass groups, preserving their local/native record order."""
    records, packed = [], []
    for variants in passes:
        raw, tables, programs, parameters = variant_records(variants, keyword_names)
        indices = []
        for index in range(struct.unpack_from("<I", raw)[0]):
            offset, size, _ = struct.unpack_from("<3I", raw, 4 + index * 12)
            record = raw[offset : offset + size]
            if record not in records:
                records.append(record)
            indices.append(records.index(record))
        programs = deepcopy(programs)
        for program in programs:
            program["m_BlobIndex"] = indices[program["m_BlobIndex"]]
        packed.append((tables, programs, [indices[index] for index in parameters]))
    return segment(records), packed


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


def shader_requirements(record, keywords):
    requirements = record["requirements"]
    for override in record["overrides"]:
        if override["keyword"] in keywords:
            requirements |= override["requirements"]
    return requirements


def fallback_externals(tree, shader_files):
    fallback = tree["m_ParsedForm"]["m_FallbackName"]
    if fallback not in shader_files:
        return []
    tree["m_Dependencies"] = [{"m_FileID": 1, "m_PathID": 1}]
    return [{"empty": "", "guid": bytes(16), "type": 0, "path": shader_files[fallback]}]


def construct(node, shaderlab, preprocessing, compiled_passes, compress, builtin_keywords, original=None, ui=False, intersection=False):
    """Construct every pass from source declarations and fresh native programs."""
    tree = default(node)
    form_node = child(node, "m_ParsedForm")
    form = tree["m_ParsedForm"]
    names, flags, masks = pass_keywords(preprocessing, builtin_keywords)
    form.update({"m_Name": re.search(r'\bShader\s+"([^"]+)"', shaderlab)[1], "m_KeywordNames": names, "m_KeywordFlags": flags})
    source = re.sub(r"//[^\n]*", "", preprocessing["shaderlab"])
    for declaration, field in (("Fallback", "m_FallbackName"), ("CustomEditor", "m_CustomEditorName")):
        match = re.search(r"\b" + declaration + r'\s+"([^"]+)"', source)
        form[field] = match[1] if match else ""
    if original is None:
        prop_node = item(child(child(form_node, "m_PropInfo"), "m_Props"))
        form["m_PropInfo"]["m_Props"] = properties(prop_node, shaderlab)
    else:
        form["m_PropInfo"]["m_Props"] = deepcopy(original["m_ParsedForm"]["m_PropInfo"]["m_Props"])
        for prop in form["m_PropInfo"]["m_Props"]:
            prop["m_Attributes"] = []
    sub_node = item(child(form_node, "m_SubShaders"))
    pass_node = item(child(sub_node, "m_Passes"))
    ordered = []
    for _, sub_text in source_blocks(source, "SubShader"):
        passes = source_blocks(sub_text, "Pass")
        ordered.extend(int(re.search(r"\bGpuProgramID\s+(\d+)", text)[1]) for _, text in passes)
    raw, packed = shader_records([compiled_passes[gpu]["variants"] for gpu in ordered], names)
    packed = dict(zip(ordered, packed))
    for sub_index, (_, sub_text) in enumerate(source_blocks(source, "SubShader")):
        sub = default(sub_node)
        passes = source_blocks(sub_text, "Pass")
        header = sub_text[: passes[0][0]]
        sub["m_Tags"]["tags"] = source_tags(header)
        lod = re.search(r"\bLOD\s+(\d+)", header)
        sub["m_LOD"] = int(lod[1]) if lod else 0
        grabs = re.findall(r'\bGrabPass\s*\{\s*"([^"]+)"\s*\}', header)
        sub["m_Passes"] = [grab_pass(pass_node, name) for name in grabs]
        for pass_index, (_, text) in enumerate(passes):
            gpu = int(re.search(r"\bGpuProgramID\s+(\d+)", text)[1])
            compiled = compiled_passes[gpu]
            table, programs, parameters = packed[gpu]
            shader_pass = default(pass_node)
            if original is not None and not intersection:
                source_state = original["m_ParsedForm"]["m_SubShaders"][sub_index]["m_Passes"][pass_index + len(grabs)]["m_State"]
                state = native_state(source_state, gpu, ui)
            else:
                state = render_state(header + "\n" + text, gpu)
            name = re.search(r'\bName\s+"([^"]+)"', text)
            state.update({"m_Name": name[1] if name else "", "m_Tags": {"tags": source_tags(header + "\n" + text)}, "m_LOD": sub["m_LOD"]})
            shader_pass.update(
                {
                    "m_State": state,
                    "m_EditorDataHash": [{f"bytes[{index}]": byte for index, byte in enumerate(compiled["identity"])}],
                    "m_Platforms": [18],
                    "m_ProgramMask": 6,
                    "m_NameIndices": table["m_NameIndices"],
                    "m_SerializedKeywordStateMask": masks[gpu],
                    "m_HasInstancingVariant": "INSTANCING_ON" in [names[index] for index in masks[gpu]],
                }
            )
            shader_pass["progVertex"].update(
                {
                    "m_CommonParameters": table["m_CommonParameters"],
                    "m_PlayerSubPrograms": [deepcopy(programs) for _ in range(3)] + [[]],
                    "m_ParameterBlobIndices": [parameters[:] for _ in range(3)] + [[]],
                }
            )
            sub["m_Passes"].append(shader_pass)
        form["m_SubShaders"].append(sub)
    compressed = compress(raw, 9)
    tree.update(
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
    return tree


def native_state(source_state, gpu_program_id, ui):
    """Apply only state emitted by shader_materials' measured source wrappers."""
    state = render_state("Cull Off ZWrite Off ZTest Always", gpu_program_id)
    for name in ("m_Name", "m_Tags", "culling", "zWrite", "zTest", "stencilRef", "stencilReadMask", "stencilWriteMask"):
        state[name] = deepcopy(source_state[name])
    for name in ("srcBlend", "destBlend", "srcBlendAlpha", "destBlendAlpha", "colMask"):
        state["rtBlend0"][name] = deepcopy(source_state["rtBlend0"][name])
    state["stencilOp"] = deepcopy(source_state["stencilOp" if ui else "stencilOpFront"])
    return state


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


def native_material_sources(root, pc, selected, tool, output):
    """Recover the qualified native families from original objects, once."""
    import UnityPy

    sys.path.insert(0, str(root / "scripts/lab"))
    import shader_materials as M
    import shader_deferred as D
    import shader_metadata as metadata
    from shader_segments import read_segments
    from shader_programs import NativePrograms, NativeVariantUnavailable
    from shader_tessellation import TessellationPrograms

    if selected["d3dasm_revision"] != M.PINS["d3dasm"][1]:
        raise ValueError("native public recovery source revision differs")
    selector_path = relative(root, selected["manifests"]["path"])
    checked(selector_path, selected["manifests"])
    selectors = json.loads(selector_path.read_text())
    pins = [(selector_path, selected["manifests"])]
    contexts, types, rows = {}, {}, {}
    source_rows = [row for row in selectors["shaders"] if row["family"] != "ui-alpha"]
    source_keys = {(row["member"], row["path_id"]): row["family"] for row in source_rows}
    W = module("_native_material_writer", Path(__file__).with_name("unity_write.py"))

    def bundle(row, digest):
        path = relative(pc, row["path"])
        pin = {"bytes": path.stat().st_size, "sha256": digest}
        checked(path, pin)
        pins.append((path, pin))
        return path, UnityPy.load(str(path))

    for source in source_rows:
        path, environment = bundle(source, source["bundle_sha256"])
        obj = next(obj for obj in environment.objects if (obj.assets_file.name, obj.path_id) == (source["member"], source["path_id"]))
        if hashlib.sha256(obj.get_raw_data()).hexdigest() != source["body_sha256"]:
            raise ValueError("original native shader body differs")
        tree = obj.read_typetree()
        raw, records, programs = read_segments(tree, bytes(tree["compressedBlob"]))
        family = source["family"]
        contexts[family] = tree, raw, records, programs, {}
        layout = W.read_serialized(W.B.Bundle(path).member(source["member"]))
        types[family] = layout["types"][next(row for row in layout["objects"] if row["path_id"] == source["path_id"])["type_id"]]
        rows[family] = []
    for selected_bundle in selectors["materials"]:
        materials = [
            (member, row)
            for member in selected_bundle["members"]
            for row in member["materials"]
            if (row["shader_member"], row["shader_path_id"]) in source_keys
        ]
        if not materials:
            continue
        _, environment = bundle(selected_bundle, selected_bundle["sha256"])
        objects = {(obj.assets_file.name, obj.path_id): obj for obj in environment.objects}
        for member, selection in materials:
            obj = objects[member["name"], selection["path_id"]]
            if hashlib.sha256(obj.get_raw_data()).hexdigest() != selection["sha256"]:
                raise ValueError("original native material body differs")
            material = obj.read_typetree()
            pointer = material["m_Shader"]
            file_id = pointer["m_FileID"]
            if not 0 <= file_id <= len(obj.assets_file.externals):
                raise ValueError("original native shader pointer extent differs")
            member_name = member["name"] if file_id == 0 else obj.assets_file.externals[file_id - 1].path.rsplit("/", 1)[-1]
            key = member_name, pointer["m_PathID"]
            if key != (selection["shader_member"], selection["shader_path_id"]):
                raise ValueError("original native material shader pointer differs")
            family = source_keys[key]
            keys = set(material.get("m_ValidKeywords", [])) | set(material.get("m_InvalidKeywords", [])) | set(material.get("m_ShaderKeywords", "").split())
            rows[family].append((selection["asset"], contexts[family][0]["m_ParsedForm"]["m_Name"], ",".join(sorted(keys))))
    emitter = NativePrograms(output, {"programs": []}, tool, allow_independent=False)
    water = TessellationPrograms(output, {"programs": []}, tool, allow_independent=False)
    sources = {}
    for family in [*metadata.FAMILIES, "standard"]:
        if family not in contexts:
            continue
        context = contexts[family]
        features, _, sets = metadata.material_selection(rows[family], context[0]["m_ParsedForm"], family)
        for index, keys in enumerate(sets):
            resource = (
                "AndroidNativeStandard" + str(index)
                if family == "standard"
                else "AndroidNativeFamily" + str(list(metadata.FAMILIES).index(family)) + "Variant" + str(index)
            )
            try:
                if family == "standard":
                    _, source = D.standard_source(context, keys, resource, emitter)
                elif family == "cloud":
                    source = M.cloud_source(context, keys, resource, emitter)
                elif family == "distortion":
                    _, source = M.distortion_source(context, keys, resource, emitter)
                elif family == "speedtree":
                    _, source = M.speedtree_source(context, keys, resource, features, emitter)
                elif family in ("water", "water-single"):
                    _, source = M.water_source(context, keys, resource, water)
                else:
                    _, source = M.deferred_source(context, keys, resource, features, emitter)
            except NativeVariantUnavailable:
                continue
            sources[resource] = context[0], source, family, types[family]
    return sources, pins


def native_internal_sources(pc, selected, tool, output, connection, core):
    """Recover only original deferred-lighting/reflection objects from GGM."""
    import UnityPy
    import shader_deferred
    from shader_segments import read_segments
    from shader_programs import NativePrograms

    W = module("_native_internal_writer", Path(__file__).with_name("unity_write.py"))
    path = relative(pc, selected["path"])
    checked(path, selected)
    data = path.read_bytes()
    reader = io.BytesIO(data)
    reader.size = len(data)
    layout = W.read_serialized(reader)
    objects = {obj.path_id: obj for obj in UnityPy.load(str(path)).objects}
    emitter = NativePrograms(output, {"programs": []}, tool, allow_independent=False, native_decompiler=(connection, core))
    sources = {}
    for kind, identity in selected["objects"].items():
        tree = objects[identity].read_typetree()
        raw, records, programs = read_segments(tree, bytes(tree["compressedBlob"]))
        resource, source = shader_deferred.internal_source((tree, raw, records, programs, {}), kind, emitter)
        typ = layout["types"][next(row for row in layout["objects"] if row["path_id"] == identity)["type_id"]]
        sources[resource] = tree, source, kind, typ
    return sources


def original_materials(pc, selections):
    import UnityPy

    result = []
    for selection in selections:
        path = relative(pc, selection["path"])
        checked(path, selection)
        obj = next(
            obj
            for obj in UnityPy.load(str(path)).objects
            if obj.path_id == selection["path_id"] and ("member" not in selection or obj.assets_file.name == selection["member"])
        )
        if obj.type.name != "Material":
            raise ValueError("original TMP feature selector is not Material")
        result.append(obj.read_typetree())
    return result


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


def snippet_key(source, include_hash, key_flags, compiler_version, platform_capabilities, common_bytes):
    """SDK zero-seed 80-byte base key; key_flags is not compilation_flags.

    key_flags encodes cached preprocessing at bit7 and platform at bits8..15.
    Historical callers own their acquired SDK's version/caps/include context.
    """
    if len(include_hash) != 16:
        raise ValueError("snippet include hash must be 16 bytes")
    preimage = spooky(source.encode("utf-8")) + include_hash
    preimage += struct.pack("<2Q", key_flags, compiler_version)
    preimage += spooky(struct.pack("<Q", platform_capabilities)) + spooky(common_bytes)
    return spooky(preimage)


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
    return snippet_key(
        snippet["source"], include_hash, (int(settings["caching_preprocessor"]) << 7) | (18 << 8), version, platform_caps(sdk_image, settings), common_bytes
    )


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


def sdk_scene_variants(snippet, material_keywords=None, *, retain_instancing=False):
    """Declared SDK alternatives retained by the pinned fresh mono Lab scene."""
    rejected = {
        "FOG_LINEAR",
        "FOG_EXP",
        "FOG_EXP2",
        "INSTANCING_ON",
        "DOTS_INSTANCING_ON",
        "EDITOR_VISUALIZATION",
        "LIGHTMAP_ON",
        "DIRLIGHTMAP_COMBINED",
        "DYNAMICLIGHTMAP_ON",
        "SHADOWS_SHADOWMASK",
        "LIGHTMAP_SHADOW_MIXING",
        "STEREO_INSTANCING_ON",
        "STEREO_MULTIVIEW_ON",
        "STEREO_CUBEMAP_RENDER_ON",
        "UNITY_SINGLE_PASS_STEREO",
    }
    if retain_instancing:
        rejected.remove("INSTANCING_ON")
    axes = []
    for group in ("m_VariantsUserGlobal", "m_VariantsUserLocal"):
        merged = []
        for stage in range(7):
            for axis in snippet[group + str(stage)]:
                if axis not in merged:
                    merged.append(axis)
        axes.extend(merged)
    # The SDK distinguishes shader_feature names from multi_compile names in
    # this source field, including global features such as _EMISSION. A source
    # material selects features before expansion, while runtime axes survive.
    runtime = set(snippet["m_NonStrippedUserKeywords"].split()) if material_keywords is not None else None
    users = [[]]
    for axis in axes:
        retained = [
            name for name in axis if name not in rejected and (not name.strip("_") or material_keywords is None or name in runtime or name in material_keywords)
        ]
        users = [keys + ([name] if name.strip("_") else []) for keys in users for name in retained]
    builtins = [row for row in snippet["m_VariantsBuiltin0"] or [[]] if not (set(row) & rejected)]
    return [sorted(set(user + builtin)) for user in users for builtin in builtins]


def sdk_scene_selections(source, material_keywords=None):
    # SDK EmitPass removes META when the fresh scene has no realtime GI usage.
    for sub in source["m_ParsedForm"]["m_SubShaders"]:
        sub["m_Passes"] = [
            shader_pass
            for shader_pass in sub["m_Passes"]
            if not any(key.upper() == "LIGHTMODE" and text.upper() == "META" for key, text in shader_pass["m_State"]["m_Tags"]["tags"])
        ]
    snippets = dict(source["m_CompileInfo"]["m_Snippets"])
    return {
        shader_pass["m_State"]["gpuProgramID"]: [
            deepcopy(sdk_scene_variants(snippets[shader_pass["m_State"]["gpuProgramID"]], material_keywords)) for _ in range(3)
        ]
        for sub in source["m_ParsedForm"]["m_SubShaders"]
        for shader_pass in sub["m_Passes"]
        if shader_pass["m_Type"] == 0
    }


def project_tiers(root, settings, template_pin):
    """Use the same authored graphics-settings generator as the player build."""
    import project_input_rebuild

    template = relative(root, "smoke/ProjectSettings/GraphicsSettings.asset").read_bytes()
    graphics = project_input_rebuild.graphics_settings(template, template_pin["sha256"]).decode()
    tiers = []
    for fields in re.findall(r"m_Settings:\s*\n(.*?)\s*m_Automatic:", graphics, re.S):
        setting = deepcopy(settings)
        setting["tier0"] = {name: int(value) for name, value in re.findall(r"(\w+):\s*(-?\d+)", fields)}
        tiers.append(setting)
    if len(tiers) != 3:
        raise ValueError("source Android graphics tiers differ")
    return tiers


def produce_sdk_records(root, pc, sdk, profile, profile_sha256, output, connection, compress, sdk_image, common_bytes):
    """Append builtin complete-file framing and the shared Shader record pack."""
    import UnityPy
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    sys.path.insert(0, str(Path(__file__).parent))
    import shader_sdk

    W = module("_sdk_record_writer", Path(__file__).with_name("unity_write.py"))
    selected = profile["builtin"]
    source_path = relative(pc, selected["source"]["path"])
    checked(source_path, selected["source"])
    environment = UnityPy.load(str(source_path))
    pc_ids = {obj.path_id for obj in environment.objects if obj.type.name == "Shader"}
    node = next(obj for obj in environment.objects if obj.type.name == "Shader")._get_typetree_node()
    with source_path.open("rb") as stream:
        stream.size = source_path.stat().st_size
        layout = W.read_serialized(stream)
    native_type = next(typ for typ in layout["types"] if typ["class_id"] == 48)
    sdk_path = sdk / "Resources/unity_builtin_extra"
    checked(sdk_path, profile["sdk"]["Resources/unity_builtin_extra"])
    sdk_objects = {obj.path_id: obj for obj in UnityPy.load(str(sdk_path)).objects}
    sdk_shaders = {identity: obj for identity, obj in sdk_objects.items() if obj.type.name == "Shader"}
    graphics = relative(root, "smoke/ProjectSettings/GraphicsSettings.asset").read_text()
    settings_ids = set(map(int, re.findall(r"fileID: (\d+), guid: 0000000000000000f000000000000000", graphics)))
    # Android's native Video player resource is separate from the PC closure.
    candidates = sorted((pc_ids & sdk_shaders.keys()) | settings_ids | {16003})
    tiers = project_tiers(root, profile["settings"], profile["authored_inputs"]["smoke/ProjectSettings/GraphicsSettings.asset"])
    sprite_materials = original_materials(pc, selected["sprite_materials"])
    default_material = sdk_objects[10303].read_typetree()
    if (
        default_material["m_Shader"] != {"m_FileID": 0, "m_PathID": 46}
        or default_material["m_ValidKeywords"]
        or default_material["m_InvalidKeywords"]
        or any(row["m_EnableInstancingVariants"] for row in [default_material, *sprite_materials])
    ):
        raise ValueError("source default-material feature usage differs from the qualified fresh scene")
    if any(row["m_Shader"]["m_PathID"] != 10753 for row in sprite_materials):
        raise ValueError("source Sprite material shader relation differs")
    if "com.unity.rendering.hybrid" in json.loads(relative(root, "recipe/project-layout.json").read_text())["dependencies"]:
        raise ValueError("source mono/instancing usage differs")
    directory = output / "sdk-shaders"
    directory.mkdir()
    bodies = {}
    for identity in candidates:
        if identity not in sdk_shaders:
            continue
        source = sdk_shaders[identity].read_typetree()
        if not source["m_ParsedForm"]["m_SubShaders"]:
            continue
        selections = sdk_scene_selections(source)
        destination = directory / str(identity)
        destination.mkdir()
        body, _, _ = shader_sdk.compile_body(connection, source, node, selections, tiers, sdk_image, common_bytes, compress, destination)
        bodies[identity] = body
    rows, cursor = [], 0
    for identity, body in sorted(bodies.items()):
        cursor = (cursor + 7) & ~7
        rows.append({"path_id": identity, "type_id": 0, "offset": cursor, "bytes": len(body)})
        cursor += len(body)
    layout = {
        "engine": "2021.3.45f2",
        "platform": 13,
        "trees": False,
        "types": [native_type],
        "objects": rows,
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    name = "apk/assets/bin/Data/Resources/unity_builtin_extra"
    destination = output / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as stream:
        W.write_serialized(stream, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    checked(destination, selected)
    shared = profile["shared_shaders"]
    shared_path = relative(pc, shared["source"]["path"])
    checked(shared_path, shared["source"])
    shared_obj = next(obj for obj in UnityPy.load(str(shared_path)).objects if obj.path_id == shared["source"]["path_id"])
    shared_node = shared_obj._get_typetree_node()
    pack = output / "shared-shaders"
    pack.mkdir()
    local = {row["sdk_id"]: row["path_id"] for row in shared["records"]}
    with (pack / "objects.bin").open("wb") as objects, (pack / "index.jsonl").open("w") as index:
        for row in shared["records"]:
            identity = row["sdk_id"]
            source = sdk_shaders[identity].read_typetree()
            # The source primitive's SDK Default-Material has no features;
            # select that set before expanding the source runtime axes.
            material_keywords = set(default_material["m_ValidKeywords"]) if identity == default_material["m_Shader"]["m_PathID"] else None
            selections = sdk_scene_selections(source, material_keywords)
            folder = directory / str(identity)
            folder.mkdir()
            body, tree, _ = shader_sdk.compile_body(connection, source, shared_node, selections, tiers, sdk_image, common_bytes, compress, folder)
            dependencies = []
            for pointer in source["m_Dependencies"]:
                if pointer["m_FileID"] != 0:
                    raise ValueError("SDK shared shader dependency is not local to the source resource")
                shader_id = pointer["m_PathID"]
                dependencies.append({"m_FileID": 0 if shader_id in local else 1, "m_PathID": local.get(shader_id, shader_id)})
            tree["m_Dependencies"] = dependencies
            writer = EndianBinaryWriter(endian="<")
            write_typetree(tree, shared_node, writer)
            body = writer.bytes
            if len(body) != row["bytes"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
                raise ValueError("complete shared shader differs from expected comparator")
            index.write(
                json.dumps(
                    {
                        "bundle": "apk",
                        "member": shared["member"],
                        "path_id": row["path_id"],
                        "offset": objects.tell(),
                        "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            objects.write(body)
    receipt = {
        "success": True,
        "input_id": profile["input_id"],
        "profile_sha256": profile_sha256,
        "outputs": {name: {"bytes": (pack / name).stat().st_size, "sha256": sha(pack / name)} for name in ("objects.bin", "index.jsonl")},
    }
    (pack / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return name, {"bytes": destination.stat().st_size, "sha256": sha(destination)}


def select_authored_files(profile, filenames):
    """Select standalone authored rows without initializing unrelated providers."""
    if filenames is None:
        return profile
    wanted = set(filenames)
    rows = [row for row in profile["shaders"] if row["file"] in wanted]
    if not wanted or {row["file"] for row in rows} != wanted:
        raise ValueError("authored file selection must name existing shader files")
    if any("source" not in row for row in rows):
        raise ValueError("authored file selection requires tracked ShaderLab sources")
    selected = {key: profile[key] for key in ("input_id", "source_type", "sdk", "includes_sha256", "settings", "authored_inputs")}
    selected["shaders"] = rows
    selected["authored_inputs"] = {
        name: pin
        for name, pin in profile["authored_inputs"].items()
        if not name.startswith("scripts/lab/shader_") and name != "tools/phone-build/accepted-output/shader_sdk.py"
    }
    return selected


def produce(
    profile_path,
    profile_sha256,
    pc,
    sdk,
    output,
    codec_path,
    codec_sha256,
    d3dasm_path=None,
    d3dasm_sha256=None,
    hlsl_source=None,
    asset_ripper_source=None,
    *,
    compiler_command=None,
    compiler_data=None,
    authored_files=None,
):
    """Reproduce all selected standalone shaders from original PC/public inputs.

    The SDK compiler executes without the Editor/project. Public source providers
    are explicit pinned Git object trees; expected file hashes compare only fully
    persisted independent output. No retained generated source/body is read.
    """
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "scripts/lab"))
    profile_path, codec_path = Path(profile_path).absolute(), Path(codec_path).absolute()
    profile_pin = {"bytes": profile_path.stat().st_size, "sha256": profile_sha256}
    codec_pin = {"bytes": codec_path.stat().st_size, "sha256": codec_sha256}
    checked(profile_path, profile_pin)
    checked(codec_path, codec_pin)
    profile = select_authored_files(json.loads(profile_path.read_text()), authored_files)
    # Authored ShaderLab does not need native D3D recovery or UnityPy on Android.
    native = any(key in profile for key in ("native_ui", "native_materials", "native_internal", "native_intersection", "tmp_dummy", "tmp_mobile", "builtin"))
    if native:
        import UnityPy
        import shader_source as sources
        import shader_recovery as recovery
        from shader_segments import read_segments
        from shader_programs import NativePrograms

    pc, sdk = Path(pc).resolve(strict=True), Path(sdk).resolve(strict=True)
    output = Path(output)
    output = output.parent.resolve(strict=True) / output.name
    if output.exists():
        raise ValueError("shader output must be a new private directory")
    provider_roots = [pc, sdk] + [Path(path).resolve(strict=True) for path in (hlsl_source, asset_ripper_source) if path is not None]
    if any(output.is_relative_to(source) or source.is_relative_to(output) for source in provider_roots):
        raise ValueError("shader output must be disjoint from original and public source inputs")
    source = profile["source_type"]
    source_path = relative(pc, source["path"])
    pins = [(profile_path, profile_pin), (codec_path, codec_pin), (source_path, source)]
    pins.extend((relative(sdk, name), pin) for name, pin in profile["sdk"].items())
    pins.extend((relative(root, name), pin) for name, pin in profile["authored_inputs"].items())
    if "native_ui" in profile or "native_materials" in profile:
        if d3dasm_path is None or d3dasm_sha256 is None:
            raise ValueError("native recovery requires the explicit pinned public d3dasm tool")
        d3dasm_path = Path(d3dasm_path).absolute()
        pins.append((d3dasm_path, {"bytes": d3dasm_path.stat().st_size, "sha256": d3dasm_sha256}))
    if "native_ui" in profile:
        pins.extend((relative(pc, row["path"]), row) for row in [profile["native_ui"]["source"], *profile["native_ui"]["materials"]])
    if "native_internal" in profile:
        if hlsl_source is None:
            raise ValueError("custom lighting requires the explicit pinned public HLSLDecompiler source repository")
        pins.append((relative(pc, profile["native_internal"]["path"]), profile["native_internal"]))
    if "tmp_dummy" in profile:
        if asset_ripper_source is None:
            raise ValueError("TMP exporter requires the explicit pinned public AssetRipper source repository")
        pins.append((relative(pc, profile["tmp_dummy"]["source"]["path"]), profile["tmp_dummy"]["source"]))
    if "tmp_mobile" in profile:
        pins.extend((relative(pc, row["path"]), row) for row in profile["tmp_mobile"]["materials"])
    if "builtin" in profile:
        pins.append((relative(pc, profile["builtin"]["source"]["path"]), profile["builtin"]["source"]))
        pins.extend((relative(pc, row["path"]), row) for row in profile["builtin"]["sprite_materials"])
        pins.append((relative(pc, profile["shared_shaders"]["source"]["path"]), profile["shared_shaders"]["source"]))
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
        if "source" in shader:
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
        raise ValueError("original schema provider is not Shader48")
    node = W.shader_node(native_type["tree"])
    source_member = W.B.Bundle(source_path).member(source["member"])
    source_member.seek(layout["data_offset"] + selected["offset"])
    original_form = W.read_shader_body(node, W.B.exact(source_member, selected["bytes"]))["m_ParsedForm"]
    if "native_intersection" in profile:
        environment = UnityPy.load(str(source_path))
    registry = original_form["m_KeywordNames"][:4], original_form["m_KeywordFlags"][:4]
    sdk_image = (sdk / "MacOS/Unity").read_bytes()
    compile_keywords = platform_keywords(sdk_image, profile["settings"])
    compile_flags = compilation_flags(sdk_image, profile["settings"])
    output.mkdir()
    native_sources, shader_sources, template_inputs = {}, {}, {}
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
    if d3dasm_path is not None:
        result["inputs"]["d3dasm_sha256"] = d3dasm_sha256
    started = time.monotonic()
    try:
        if "native_ui" in profile:
            directory = output / "native-ui"
            directory.mkdir()
            tree, texts = native_ui_sources(root, pc, profile["native_ui"], d3dasm_path, directory)
            native_sources.update({name: (tree, text, "ui-alpha", native_type) for name, text in texts.items()})
        if "native_materials" in profile:
            directory = output / "native-materials"
            directory.mkdir()
            native, providers = native_material_sources(root, pc, profile["native_materials"], d3dasm_path, directory)
            native_sources.update(native)
            pins.extend(providers)
        include_dirs = [include_dir, root / "tools/unity/runtime/shaders"]
        if "tmp_mobile" in profile:
            package = sources.package_mobile_source(sdk, profile["tmp_mobile"]["package"])
            directory = output / "tmp-package"
            directory.mkdir()
            (directory / "TMPro_Properties.cginc").write_bytes(package["include"])
            include_dirs.append(directory)
            mobile_source = package["shader"].decode("utf-8")
            material_keywords = [row["m_ValidKeywords"] for row in original_materials(pc, profile["tmp_mobile"]["materials"])]
        if "tmp_dummy" in profile:
            selected = profile["tmp_dummy"]
            for name, pin in selected["template_inputs"].items():
                data = recovery.pinned_source(asset_ripper_source, selected["exporter_revision"], name)
                if len(data) != pin["bytes"] or hashlib.sha256(data).hexdigest() != pin["sha256"]:
                    raise ValueError("pinned public TMP template resource differs")
                template_inputs[Path(name).name] = data.decode().replace("\r", "")
            # GPL source remains caller supplied. Keep its notice with local outputs.
            (output / "AssetRipper-LICENSE.md").write_bytes(recovery.pinned_source(asset_ripper_source, selected["exporter_revision"], "LICENSE.md"))
            selected = selected["source"]
            tmp_objects = {obj.path_id: obj for obj in UnityPy.load(str(relative(pc, selected["path"]))).objects if obj.assets_file.name == selected["member"]}
        core = recovery.build_native_hlsl(hlsl_source, output / "native-hlsl-tool") if "native_internal" in profile else None
        with (
            compiler.compiler(
                compiler_command if compiler_command is not None else [sdk / "Tools/UnityShaderCompiler"],
                compiler_data if compiler_data is not None else sdk,
                output / "compiler",
                includes=include_dirs,
            ) as connection,
            W.codec(codec_path, codec_sha256) as compress,
        ):
            if "native_internal" in profile:
                directory = output / "native-internal"
                directory.mkdir()
                native_sources.update(native_internal_sources(pc, profile["native_internal"], d3dasm_path, directory, connection, core))
            if "native_intersection" in profile:
                identity = profile["native_intersection"]
                obj = next(obj for obj in environment.objects if (obj.assets_file.name, obj.path_id) == (source["member"], identity))
                tree = obj.read_typetree()
                raw, records, programs = read_segments(tree, bytes(tree["compressedBlob"]))
                directory = output / "native-intersection"
                directory.mkdir()
                emitter = NativePrograms(directory, {"programs": []}, d3dasm_path, allow_independent=False)
                text = sources.intersection_source((tree, raw, records, programs, {}), emitter)
                typ = layout["types"][next(row for row in layout["objects"] if row["path_id"] == identity)["type_id"]]
                native_sources["AndroidIntersectionPresentation"] = tree, text, "intersection", typ
            for shader in profile["shaders"]:
                if "native_resource" in shader:
                    shader_sources[shader["file"]] = native_sources[shader["native_resource"]][1]
                elif "tmp_dummy" in shader:
                    text, _ = sources.dummy_shader_source(tmp_objects[shader["tmp_dummy"]].read_typetree()["m_ParsedForm"], template_inputs)
                    shader_sources[shader["file"]] = text
                elif shader.get("tmp_mobile"):
                    shader_sources[shader["file"]] = mobile_source
                else:
                    shader_sources[shader["file"]] = relative(root, shader["source"]).read_text()
            names_to_files = {re.search(r'\bShader\s+"([^\"]+)"', text)[1]: name for name, text in shader_sources.items()}
            for shader, name in zip(profile["shaders"], destinations):
                text = shader_sources[shader["file"]]
                pre = connection.preprocess(
                    text, shader["filename"], platform_keywords=["SHADER_API_MOBILE"], caching_preprocessor=profile["settings"]["caching_preprocessor"]
                )
                if not pre["success"] or not pre["snippets"]:
                    raise ValueError("source shader preprocessing failed")
                compiled_passes = {}
                for snippet in pre["snippets"]:
                    gpu = snippet["fields"][0]
                    req = next(row for row in pre["records"] if row["kind"] == "keywordsEnd" and row["fields"] == [gpu])
                    identity = editor_hash(snippet, sdk_image, connection.capabilities, profile["settings"], common_bytes)
                    variants = []
                    for keywords in retained_keywords(pre, gpu, material_keywords if shader.get("tmp_mobile") else None):
                        requirements = shader_requirements(req, keywords)
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
                    compiled_passes[gpu] = {"identity": identity, "variants": variants}
                original, kind, typ = None, None, native_type
                if "native_resource" in shader:
                    original, _, kind, typ = native_sources[shader["native_resource"]]
                tree = construct(node, text, pre, compiled_passes, compress, registry, original, kind == "ui-alpha", kind == "intersection")
                externals = fallback_externals(tree, names_to_files)
                body = W.write_shader_body(node, tree)
                destination = output / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                standalone = {
                    "engine": "2021.3.45f2",
                    "platform": 13,
                    "trees": False,
                    "types": [typ],
                    "objects": [{"path_id": 1, "type_id": 0, "offset": 0, "bytes": len(body)}],
                    "scripts": [],
                    "externals": externals,
                    "ref_types": [],
                    "user": "",
                }
                with destination.open("wb") as stream:
                    W.write_serialized(stream, standalone, lambda _: io.BytesIO(body))
                checked(destination, shader)
                result["files"][name] = {"bytes": destination.stat().st_size, "sha256": sha(destination)}
            if "builtin" in profile:
                name, pin = produce_sdk_records(root, pc, sdk, profile, profile_sha256, output, connection, compress, sdk_image, common_bytes)
                result["files"][name] = pin
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
    parser.add_argument("--hlsl-source", type=Path, help="caller-supplied pinned public HLSLDecompiler Git repository; native core builds into new output")
    parser.add_argument("--asset-ripper-source", type=Path, help="caller-supplied pinned public AssetRipper Git repository; template bodies stay local")
    parser.add_argument("--compiler-command", type=json.loads, help="explicit compiler argv as a JSON array, including an Android GNU runner when required")
    parser.add_argument("--compiler-data", type=Path, help="acquired compiler SDK data root; --sdk still supplies the pinned metadata/includes")
    parser.add_argument(
        "--authored-file",
        action="append",
        help="current: produce only named standalone authored files from the pinned profile; repeatable, omits native/builtin/shared cohorts",
    )
    args = parser.parse_args()
    produce(
        args.profile,
        args.profile_sha256,
        args.pc,
        args.sdk,
        args.output,
        args.codec,
        args.codec_sha256,
        args.d3dasm,
        args.d3dasm_sha256,
        args.hlsl_source,
        args.asset_ripper_source,
        compiler_command=args.compiler_command,
        compiler_data=args.compiler_data,
        authored_files=args.authored_file,
    )


if __name__ == "__main__":
    main()
