"""Dependency-free native shader declaration and manifest selection policy.

No shader programs or material values live here. Callers supply original parsed
metadata and material rows; source recovery and runtime qualification are separate.
"""

import json

STAGES = ["progVertex", "progFragment", "progHull", "progDomain", "progGeometry"]


def variants(tree):
    result = {}
    keywords = tree["m_ParsedForm"]["m_KeywordNames"]
    for subshader_index, subshader in enumerate(tree["m_ParsedForm"]["m_SubShaders"]):
        for pass_index, p in enumerate(subshader["m_Passes"]):
            for stage in STAGES:
                tables = p[stage]["m_PlayerSubPrograms"]
                parameter_tables = p[stage]["m_ParameterBlobIndices"]
                if not tables and not parameter_tables:
                    continue
                if len(tables) != 4 or len(parameter_tables) != 4 or any(tables[:3]) or any(parameter_tables[:3]):
                    raise RuntimeError("Unmeasured shader platform tables")
                programs = tables[3]
                parameters = parameter_tables[3]
                if len(programs) != len(parameters):
                    raise RuntimeError("Shader variant/parameter lengths differ")
                for program, parameter in zip(programs, parameters):
                    index = program["m_BlobIndex"]
                    value = {
                        "index": index,
                        "parameter_index": parameter,
                        "gpu_type": program["m_GpuProgramType"],
                        "keywords": sorted(keywords[k] for k in program["m_KeywordIndices"]),
                        "pass": p["m_State"]["m_Name"],
                        "stage": stage,
                        "subshader_index": subshader_index,
                        "pass_index": pass_index,
                    }
                    if index in result:
                        previous = result[index]
                        if any(previous[k] != value[k] for k in ["parameter_index", "gpu_type", "keywords", "stage"]):
                            raise RuntimeError("Original shader program identity has conflicting consumers")
                        location = {k: value[k] for k in ["pass", "subshader_index", "pass_index"]}
                        consumers = previous.setdefault("consumers", [{k: previous[k] for k in location}])
                        if location not in consumers:
                            consumers.append(location)
                    else:
                        result[index] = value
    return result


FAMILIES = {
    "cloud": (-658352061839041481, "Hopoo Games/FX/Cloud Remap"),
    "opaque-cloud": (-704325499538927933, "Hopoo Games/FX/Opaque Cloud Remap"),
    "snow": (3671293666148614723, "Hopoo Games/Deferred/Snow Topped"),
    "terrain": (5954585457266417408, "Hopoo Games/Deferred/Triplanar Terrain Blend"),
    "grass": (-8989458460904117762, "Hopoo Games/Environment/Waving Grass"),
    "cloth": (-6170440028897955187, "Hopoo Games/Deferred/Wavy Cloth"),
    "ui-alpha": (-8085301563477162814, "Hopoo Games/UI/Animate Alpha"),
    "distortion": (1142643595885926041, "Hopoo Games/FX/Distortion"),
    "speedtree": (-8684109817920462965, "SpeedtreeOverride/SpeedtreeCustom"),
    "water-single": (-8115552462691183134, "CalmWater/Calm Water [DX11]"),
    "water": (-92852985697471365, "CalmWater/Calm Water [DX11] [Double Sided]"),
}

ENGINE = {
    "STEREO_INSTANCING_ON",
    "UNITY_SINGLE_PASS_STEREO",
    "STEREO_MULTIVIEW_ON",
    "STEREO_CUBEMAP_RENDER_ON",
    "INSTANCING_ON",
    "LIGHTPROBE_SH",
    "DYNAMICLIGHTMAP_ON",
    "SHADOWS_SHADOWMASK",
    "LIGHTMAP_ON",
    "DIRLIGHTMAP_COMBINED",
    "UNITY_HDR_ON",
    "SHADOWS_DEPTH",
    "SHADOWS_CUBE",
    "EDITOR_VISUALIZATION",
    "FOG_LINEAR",
    "FOG_EXP",
    "FOG_EXP2",
    "DIRECTIONAL",
    "LIGHTMAP_SHADOW_MIXING",
    "SHADOWS_SCREEN",
    "VERTEXLIGHT_ON",
    "POINT",
    "SPOT",
    "POINT_COOKIE",
    "DIRECTIONAL_COOKIE",
    "SOFTPARTICLES_ON",
}

FEATURES = [
    "PRINT_CUTOFF",
    "SPLATMAP",
    "FORCE_SPEC",
    "DITHER",
    "CUTOUT",
    "USE_VERTEX_COLORS",
    "FRESNEL_EMISSION",
    "USE_VERTEX_COLORS_FOR_FRESNEL_EMISSION_AND_FLOWMAP",
    "FLOWMAP",
    "LIMBREMOVAL",
]


class NativeVariantUnavailable(RuntimeError):
    """No original program exists for the requested, recorded feature contract."""


class MetadataPrograms:
    def pair(self, context, pass_index, keys, subshader_index=0):
        matches = []
        for stage in ["progVertex", "progFragment"]:
            found = [
                r["index"]
                for r in context[2]
                if r["kind"] == "program"
                and r["stage"] == stage
                and r["keywords"] == sorted(keys)
                and any(c["pass_index"] == pass_index and c["subshader_index"] == subshader_index for c in r.get("consumers", [r]))
            ]
            if len(found) != 1:
                detail = dict(
                    shader=context[0]["m_ParsedForm"]["m_Name"], stage=stage, pass_index=pass_index, subshader_index=subshader_index, keywords=sorted(keys)
                )
                if not found:
                    raise NativeVariantUnavailable("Original native variant absent: " + json.dumps(detail, sort_keys=True))
                raise RuntimeError("Native feature/pass pair is ambiguous: " + json.dumps(dict(detail, matches=found), sort_keys=True))
            matches.append(found[0])
        return matches

    def quad(self, context, pass_index, keys):
        indices = []
        for stage in ["progVertex", "progHull", "progDomain", "progFragment"]:
            found = [
                r["index"]
                for r in context[2]
                if r["kind"] == "program"
                and r["stage"] == stage
                and r["keywords"] == sorted(keys)
                and any(c["subshader_index"] == 0 and c["pass_index"] == pass_index for c in r.get("consumers", [r]))
            ]
            if len(found) != 1:
                raise RuntimeError("Ambiguous native tessellation stage: " + stage + "/" + str(keys))
            indices.append(found[0])
        return indices


def material_selection(rows, form, family):
    features = set(FEATURES) if family == "standard" else set(form["m_KeywordNames"]) - ENGINE - {"UNITY_UI_CLIP_RECT", "UNITY_UI_ALPHACLIP"}
    if family == "speedtree":
        features -= {"ENABLE_WIND", "LOD_FADE_PERCENTAGE", "LOD_FADE_CROSSFADE"}
    materials = [row for row in rows if row[1] == form["m_Name"]]
    sets = sorted({tuple(sorted(set(row[2].split(",")) & features)) for row in materials})
    if not materials or len(sets) > 128:
        raise RuntimeError("Unexpected native material closure")
    return features, materials, sets


def standard_manifest(rows, context, resources=None):
    _, materials, sets = material_selection(rows, context[0]["m_ParsedForm"], "standard")
    emitter = MetadataPrograms()
    variants = []
    for i, keys in enumerate(sets):
        name = "AndroidNativeStandard" + str(i)
        if resources is not None and name not in resources:
            continue
        vertex, fragment = emitter.pair(context, 0, set(keys) | {"LIGHTPROBE_SH", "UNITY_HDR_ON"})
        variants.append({"resource": name, "keywords": list(keys), "vertex": vertex, "fragment": fragment})
    return {
        "features": FEATURES,
        "variants": variants,
        "source_material_count": len(materials),
        "scope": "Measured static material features, mono/noninstanced SH/HDR Standard and original custom lighting; other families/reflections/PC parity remain open",
    }


def family_manifest(contexts, rows, topology="original-vertices", resources=None):
    emitter = MetadataPrograms()
    families, deferred = [], []
    for ordinal, (name, context) in enumerate(contexts.items()):
        form = context[0]["m_ParsedForm"]
        features, materials, sets = material_selection(rows, form, name)
        variants = []
        for i, keys in enumerate(sets):
            resource = "AndroidNativeFamily" + str(ordinal) + "Variant" + str(i)
            if resources is not None and resource not in resources:
                continue
            try:
                if name in ("water", "water-single"):
                    if topology == "original-vertices" and any(k.startswith("_DISPLACEMENTMODE_") for k in keys):
                        raise NativeVariantUnavailable("Displacement requires deferred original tessellation/PC draw evidence")
                    for pi in range(1, len(form["m_SubShaders"][0]["m_Passes"])):
                        for fog in (None, "FOG_LINEAR", "FOG_EXP"):
                            for sh in (False, True):
                                for shadow in (False, True):
                                    emitter.quad(
                                        context,
                                        pi,
                                        set(keys)
                                        | {"DIRECTIONAL"}
                                        | ({fog} if fog else set())
                                        | ({"LIGHTPROBE_SH"} if sh else set())
                                        | ({"SHADOWS_SCREEN"} if shadow else set()),
                                    )
                elif name == "ui-alpha":
                    for clip in (False, True):
                        for alpha in (False, True):
                            emitter.pair(context, 0, set(keys) | ({"UNITY_UI_CLIP_RECT"} if clip else set()) | ({"UNITY_UI_ALPHACLIP"} if alpha else set()))
                elif name == "cloud":
                    for sh in (False, True):
                        for soft in (False, True):
                            emitter.pair(
                                context, 0, set(keys) | {"DIRECTIONAL"} | ({"LIGHTPROBE_SH"} if sh else set()) | ({"SOFTPARTICLES_ON"} if soft else set())
                            )
                elif name == "distortion":
                    for soft in (False, True):
                        emitter.pair(context, 1, set(keys) | ({"SOFTPARTICLES_ON"} if soft else set()))
                elif name == "speedtree":
                    for lod in ("LOD_FADE_PERCENTAGE", "LOD_FADE_CROSSFADE"):
                        for wind in (False, True):
                            emitter.pair(context, 0, set(keys) | {"LIGHTPROBE_SH", "UNITY_HDR_ON", lod} | ({"ENABLE_WIND"} if wind else set()))
                    shadow_features = {
                        k
                        for r in context[2]
                        if r["kind"] == "program" and any(c["subshader_index"] == 0 and c["pass_index"] == 1 for c in r.get("consumers", [r]))
                        for k in r["keywords"]
                    } & features
                    for mode in ("SHADOWS_DEPTH", "SHADOWS_CUBE"):
                        for lod in ("LOD_FADE_PERCENTAGE", "LOD_FADE_CROSSFADE"):
                            for wind in (False, True):
                                emitter.pair(context, 1, (set(keys) & shadow_features) | {mode, lod} | ({"ENABLE_WIND"} if wind else set()))
                else:
                    emitter.pair(context, 0, set(keys) | {"LIGHTPROBE_SH", "UNITY_HDR_ON"})
                    shadow_features = {k for r in context[2] if r["kind"] == "program" and r["pass_index"] == 1 for k in r["keywords"]} & features
                    for mode in ("SHADOWS_DEPTH", "SHADOWS_CUBE"):
                        emitter.pair(context, 1, (set(keys) & shadow_features) | {mode})
                variants.append({"resource": resource, "keywords": list(keys)})
            except NativeVariantUnavailable as error:
                deferred.append(
                    {
                        "shader": form["m_Name"],
                        "keywords": list(keys),
                        "reason": str(error),
                        "materials": [row[0] for row in materials if tuple(sorted(set(row[2].split(",")) & features)) == keys],
                        "scope": "Existing explicitly approximate presentation only; original asset/gameplay retained",
                    }
                )
        families.append({"shader": form["m_Name"], "features": sorted(features), "variants": variants, "source_material_count": len(materials)})
    return {
        "families": families,
        "deferred_variants": deferred,
        "water_topology": topology,
        "water_geometry_approximation": topology == "original-vertices",
        "scope": "Measured static material features, mono/noninstanced HDR deferred; cloud SH/soft-particle variants; original reflection candidate, no PC semantic/visual parity",
    }
