"""SDK source/form compiler API; no accepted record or retained program inputs.

Selections are caller-owned source-derived keyword sets per source snippet and tier.
An explicit empty tier selection retains source pass metadata without executables.
This helper deliberately does not choose payload/scene build retention policy.
"""

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

import shader_produce as P


def sdk_source(sdk, shader_id, expected_sha256):
    """Read an explicitly acquired SDK Shader source object, never cached JSON."""
    import UnityPy

    path = Path(sdk) / "Resources/unity_builtin_extra"
    P.checked(path, {"bytes": path.stat().st_size, "sha256": expected_sha256})
    obj = next(o for o in UnityPy.load(str(path)).objects if o.type.name == "Shader" and o.path_id == shader_id)
    return obj.read_typetree()


def source_ranks(snippet, selected):
    """Rank retained rows in Vulkan's SDK source enumeration without expanding it.

    The pinned SDK appends distinct stage1..6 global/local option arrays after
    stage0. Builtin combinations remain the vertex declarations. Last user
    choice varies fastest, followed by the innermost builtin combination.
    """
    axes = []
    for group in ("m_VariantsUserGlobal", "m_VariantsUserLocal"):
        merged = []
        for stage in range(7):
            for axis in snippet[group + str(stage)]:
                if axis not in merged:
                    merged.append(axis)
        axes.extend([[frozenset([name]) if name.strip("_") else frozenset() for name in axis] for axis in merged])
    axes.append([frozenset(name for name in row if name.strip("_")) for row in snippet["m_VariantsBuiltin0"] or [[]]])
    strides, available = [1] * (len(axes) + 1), [frozenset()] * (len(axes) + 1)
    for index in range(len(axes) - 1, -1, -1):
        strides[index] = len(axes[index]) * strides[index + 1]
        available[index] = available[index + 1].union(*axes[index])
    ranks = {}
    for wanted in {frozenset(keys) for keys in selected}:

        @lru_cache(None)
        def find(index, remaining):
            if not remaining <= available[index]:
                return None
            if index == len(axes):
                return 0
            for choice, keys in enumerate(axes[index]):
                if keys <= wanted:
                    rank = find(index + 1, remaining - keys)
                    if rank is not None:
                        return choice * strides[index + 1] + rank
            return None

        rank = find(0, wanted)
        if rank is None:
            raise ValueError("selected SDK keyword row is not declared for the linked Vulkan source")
        ranks[wanted] = rank
    return ranks


def compile_body(connection, source, node, selections, tier_settings, sdk_image, common_bytes, compress, output, platform=18, *, native_order=None):
    """Compile complete SDK source form using explicit per-tier keyword choices.

    selections: {gpuProgramID: [tier0_sets, tier1_sets, tier2_sets]}, each set a
    list of declared keyword strings. tier_settings holds three source-derived
    setting dicts accepted by the existing platform_keywords/compilation_flags.
    Vulkan18 is the only qualified backend; a different platform fails closed.
    Native interning follows source rows across tiers even when their retained
    subsets differ. The caller's per-tier table order is preserved.
    native_order optionally supplies {gpuProgramID: [keyword_sets]} from original
    source metadata, replacing declaration rank only for native interning. Each
    pass order must contain every retained keyword identity exactly once.
    Returns (body, tree, raw). Payload/native metadata writers remain callers.
    """
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    if platform != 18 or len(tier_settings) != 3:
        raise ValueError("SDK source helper currently qualifies Vulkan18 and three Android tiers")
    output = Path(output)
    snippets = dict(source["m_CompileInfo"]["m_Snippets"])
    tree = P.default(node)
    for key in tree:
        if key in source:
            tree[key] = deepcopy(source[key])
    names = tree["m_ParsedForm"]["m_KeywordNames"]
    records, cache = [], {}

    def intern(data):
        if data not in records:
            records.append(data)
        return records.index(data)

    for sub in tree["m_ParsedForm"]["m_SubShaders"]:
        for shader_pass in sub["m_Passes"]:
            if shader_pass["m_Type"] != 0:
                continue
            identity = shader_pass["m_State"]["gpuProgramID"]
            snippet = snippets[identity]
            selected = selections[identity] if snippet["m_PlatformMask"] & (1 << platform) else [[], [], []]
            if len(selected) != 3:
                raise ValueError("source snippet needs three tier selections")
            ranks = source_ranks(snippet, [keys for tier in selected for keys in tier])
            if native_order is not None:
                order = [frozenset(keys) for keys in native_order.get(identity, [])]
                if identity not in native_order or len(order) != len(set(order)) or set(order) != set(ranks):
                    raise ValueError("native order must contain each retained SDK keyword row exactly once")
                ranks = {keys: rank for rank, keys in enumerate(order)}
            tiers, all_variants = [], []
            for sets, settings in zip(selected, tier_settings):
                variants = []
                for keywords in sets:
                    requirements = snippet["m_BaseRequirements"]
                    for override in snippet["m_KeywordTargetInfo"]:
                        if override["keywordName"] in keywords:
                            requirements |= override["requirements"]
                    caps = P.platform_keywords(sdk_image, settings)
                    flags = P.compilation_flags(sdk_image, settings)
                    key = identity, tuple(keywords), tuple(caps), flags, requirements
                    if key not in cache:
                        compilation = connection.compile(
                            snippet["m_Code"],
                            snippet["m_AssetPath"],
                            stage="vertex",
                            platform_keywords=caps,
                            keywords=keywords,
                            flags=flags,
                            requirements=requirements,
                        )
                        if not compilation["success"] or not compilation["data"]:
                            raise ValueError("SDK source compilation failed: " + json.dumps(compilation["diagnostics"]))
                        if compilation["gpu_program_type"] != 25:
                            raise ValueError("SDK source did not produce a linked Vulkan executable")
                        stem = f"snippet-{identity}-compile-{len(cache)}"
                        (output / (stem + ".bin")).write_bytes(compilation["data"])
                        (output / (stem + ".json")).write_text(json.dumps({k: v for k, v in compilation.items() if k != "data"}, indent=2) + "\n")
                        cache[key] = compilation
                    variant = {"keywords": keywords, "requirements": requirements, "compilation": cache[key]}
                    variants.append(variant)
                    all_variants.append(variant)
                tiers.append(variants)
            # SDK CompileGpuProgramSnippets emits each keyword row's tiers
            # together. Native parameter/executable interning follows that job
            # order; the serialized tier tables below keep their source order.
            all_variants = sorted(all_variants, key=lambda variant: ranks[frozenset(variant["keywords"])])
            positions = {id(variant): i for i, variant in enumerate(all_variants)}
            reflects = [P.reflection(v["compilation"]["reflection"]) for v in all_variants]
            common = {
                k: [r for r in reflects[0][k] if all(r in reflect[k] for reflect in reflects[1:])] if reflects else []
                for k in ("constants", "buffers", "bindings", "textures")
            }
            table = P.common_parameters(common)
            parameters = [intern(P.native_parameters(reflect, common)) for reflect in reflects]
            programs = []
            for variant, reflect in zip(all_variants, reflects):
                compiled = variant["compilation"]
                index = intern(P.native_executable(compiled["data"], compiled["gpu_program_type"], reflect, variant["keywords"]))
                programs.append(
                    {
                        "m_BlobIndex": index,
                        "m_KeywordIndices": sorted(names.index(k) for k in variant["keywords"]),
                        "m_ShaderRequirements": variant["requirements"],
                        "m_GpuProgramType": compiled["gpu_program_type"],
                    }
                )
            hash_bytes = bytes(snippet["m_IncludesHash"][f"bytes[{i}]"] for i in range(16))
            pre = {"source": snippet["m_Code"], "fields": [0] * 6 + list(struct.unpack("<4i", hash_bytes))}
            editor_hash = P.editor_hash(pre, sdk_image, connection.capabilities, tier_settings[0], common_bytes)
            shader_pass["m_EditorDataHash"] = [{f"bytes[{i}]": byte for i, byte in enumerate(editor_hash)}]
            shader_pass["m_Platforms"] = [platform]
            shader_pass["m_NameIndices"] = table["m_NameIndices"]
            program = shader_pass["progVertex"]
            program["m_CommonParameters"] = table["m_CommonParameters"]
            program["m_PlayerSubPrograms"], program["m_ParameterBlobIndices"] = [], []
            for variants in tiers:
                program["m_PlayerSubPrograms"].append([deepcopy(programs[positions[id(variant)]]) for variant in variants])
                program["m_ParameterBlobIndices"].append([parameters[positions[id(variant)]] for variant in variants])
            program["m_PlayerSubPrograms"].append([])
            program["m_ParameterBlobIndices"].append([])
    raw = P.segment(records)
    compressed = compress(raw, 9)
    tree.update(
        platforms=[platform],
        offsets=[[0]],
        compressedLengths=[[len(compressed)]],
        decompressedLengths=[[len(raw)]],
        compressedBlob=list(compressed),
        # SDK BlobMap starts with one linked-stage owner per requested backend,
        # including a backend whose snippets/variants produced no jobs.
        stageCounts=[1],
        m_ShaderIsBaked=True,
    )
    writer = EndianBinaryWriter(endian="<")
    write_typetree(tree, node, writer)
    body = writer.bytes
    (output / "body.bin").write_bytes(body)
    (output / "tree.json").write_text(json.dumps(tree, indent=2) + "\n")
    (output / "raw.bin").write_bytes(raw)
    (output / "result.json").write_text(
        json.dumps(
            {
                "source_only": True,
                "target_reads": False,
                "body_bytes": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "compiled_requests": len(cache),
                "records": len(records),
            },
            indent=2,
        )
        + "\n"
    )
    return body, tree, raw
