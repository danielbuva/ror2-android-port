"""Produce source-derived payload Shader record packs.

The retained J131 bundle uses Gamma/default Android tiers and the acquired
2021.3.33f1 source/common-include metadata. Compilation uses the current pinned
2021.3.45f2 compiler; neither Editor nor the old compiler is executed.
"""

from copy import deepcopy
from itertools import product
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

import shader_produce as P
import shader_sdk as SDK
import unity_write as W
from mesh_produce import INPUT_ID


def vertexlit_selections(source):
    """Declare the bounded non-scene, no-fog build's other multi_compile axes."""
    selections = {}
    for identity, snippet in source["m_CompileInfo"]["m_Snippets"]:
        axes = snippet["m_VariantsUserGlobal0"] + snippet["m_VariantsUserLocal0"] + snippet["m_VariantsBuiltin0"]
        selected = [[]]
        for axis in axes:
            if "FOG_LINEAR" in axis:
                axis = [next(name for name in axis if name in ("_", "__"))]
            selected = [head + ([] if name in ("_", "__") else [name]) for head, name in itertools.product(selected, axis)]
        selections[identity] = [deepcopy(selected) for _ in range(3)]
    return selections


def checked_output(path, providers):
    """Return a new output leaf disjoint from every read-only input tree."""
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError("shader record output must not be a symlink")
    output = path.parent.resolve(strict=True) / path.name
    for provider in providers:
        provider = Path(provider).resolve(strict=True)
        if output.is_relative_to(provider) or provider.is_relative_to(output):
            raise ValueError("shader record output overlaps a read-only input tree")
    if output.exists():
        raise ValueError("shader record output must be new")
    return output


def original_shader(asset, selected):
    """Read a pinned original Shader's form and runtime schema."""
    obj = asset.objects[selected["path_id"]]
    if obj.type.name != "Shader" or hashlib.sha256(obj.get_raw_data()).hexdigest() != selected["source_sha256"]:
        raise ValueError("original post-processing Shader body differs")
    return obj.read_typetree(), obj.serialized_type.node


def postprocessing_tree(connection, text, filename, original, node, settings, image, common, compress):
    """Compile one template source; the qualified tiers have identical programs."""
    pre = connection.preprocess(
        text,
        filename,
        platform_keywords=["SHADER_API_MOBILE"],
        caching_preprocessor=settings["caching_preprocessor"],
    )
    if not pre["success"]:
        raise ValueError("post-processing source preprocessing failed")
    compiled = {}
    for snippet in pre["snippets"]:
        identity = snippet["fields"][0]
        requirement = next(row for row in pre["records"] if row["kind"] == "keywordsEnd" and row["fields"] == [identity])
        if P.retained_keywords(pre, identity) != [[]]:
            raise ValueError("post-processing template must declare one empty keyword set")
        required = P.shader_requirements(requirement, [])
        responses = []
        for quality in (0, 1):
            tier = deepcopy(settings)
            tier["tier0"]["standardShaderQuality"] = quality
            response = connection.compile(
                snippet["source"],
                filename,
                stage="vertex",
                platform_keywords=P.platform_keywords(image, tier),
                keywords=[],
                flags=P.compilation_flags(image, tier),
                requirements=required,
            )
            if not response["success"] or not response["data"]:
                raise ValueError("post-processing source compilation failed")
            responses.append(response)
        if any(responses[0][key] != responses[1][key] for key in ("data", "reflection", "gpu_program_type")):
            raise ValueError("post-processing source Android tiers differ")
        compiled[identity] = {
            "identity": P.editor_hash(snippet, image, connection.capabilities, settings, common),
            "variants": [{"keywords": [], "requirements": required, "compilation": responses[0]}],
        }
    registry = (
        original["m_ParsedForm"]["m_KeywordNames"][:4],
        original["m_ParsedForm"]["m_KeywordFlags"][:4],
    )
    tree = P.construct(node, text, pre, compiled, compress, registry)
    if tree["m_Dependencies"]:
        raise ValueError("post-processing template has an unresolved dependency")
    return tree


def produce_postprocessing(
    profile_path,
    profile,
    profile_sha256,
    pc,
    sdk,
    asset_ripper,
    output,
    codec,
    codec_sha256,
):
    """Emit the source dummy cohort using current original forms and SDK context."""
    pc, sdk, asset_ripper = (Path(path).resolve(strict=True) for path in (pc, sdk, asset_ripper))
    output = checked_output(output, (pc, sdk, asset_ripper))
    codec = Path(codec).resolve(strict=True)
    source = profile["source"]
    source_path = P.relative(pc, source["path"])
    pins = [
        (
            profile_path,
            {"bytes": profile_path.stat().st_size, "sha256": profile_sha256},
        ),
        (source_path, source),
        (codec, {"bytes": codec.stat().st_size, "sha256": codec_sha256}),
    ]
    pins.extend((P.relative(sdk, name), pin) for name, pin in profile["sdk"].items())
    for path, pin in pins:
        P.checked(path, pin)
    include_pin, common = P.includes(sdk / "CGIncludes")
    if include_pin != profile["includes_sha256"]:
        raise ValueError("post-processing SDK include inputs differ")
    prefix = "Source/AssetRipper.Export.UnityProjects/Shaders/Templates/"
    templates = {}
    for name, pin in profile["template_inputs"].items():
        data = subprocess.check_output(
            [
                "git",
                "-C",
                str(asset_ripper),
                "show",
                profile["exporter_revision"] + ":" + prefix + name,
            ]
        )
        if len(data) != pin["bytes"] or hashlib.sha256(data).hexdigest() != pin["sha256"]:
            raise ValueError("post-processing shader template input differs")
        templates[name] = data.decode().replace("\r", "")
    import UnityPy
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    asset = next(asset for asset in UnityPy.load(str(source_path)).assets if asset.name == source["member"])
    repo = Path(P.__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "scripts/lab"))
    sources = P.module("_postprocessing_shader_source", repo / "scripts/lab/shader_source.py")
    compiler = P.module(
        "_postprocessing_shader_compiler",
        repo / "tools/phone-build/owner-code/shader.py",
    )
    image = (sdk / "MacOS/Unity").read_bytes()
    output.mkdir()
    started = time.monotonic()
    result = {
        "success": False,
        "input_id": profile["input_id"],
        "profile_sha256": profile_sha256,
        "outputs": {},
    }
    try:
        license_data = subprocess.check_output(
            [
                "git",
                "-C",
                str(asset_ripper),
                "show",
                profile["exporter_revision"] + ":LICENSE.md",
            ]
        )
        (output / "AssetRipper-LICENSE.md").write_bytes(license_data)
        rows = []
        with (
            compiler.compiler(
                [sdk / "Tools/UnityShaderCompiler"],
                sdk,
                output / "compiler",
                includes=[sdk / "CGIncludes"],
            ) as connection,
            W.codec(codec, codec_sha256) as compress,
            (output / "objects.bin").open("wb") as stream,
        ):
            for selected in profile["shaders"]:
                original, node = original_shader(asset, selected)
                filename = selected["source_filename"]
                P.relative(repo, filename)
                text, template = sources.dummy_shader_source(original["m_ParsedForm"], templates)
                if template != selected["template"]:
                    raise ValueError("original post-processing template selection differs")
                tree = postprocessing_tree(
                    connection,
                    text,
                    filename,
                    original,
                    node,
                    profile["settings"],
                    image,
                    common,
                    compress,
                )
                writer = EndianBinaryWriter(endian="<")
                write_typetree(tree, node, writer)
                body, offset = writer.bytes, stream.tell()
                stream.write(body)
                for selected_output in selected["outputs"]:
                    rows.append(
                        {
                            **selected_output,
                            "offset": offset,
                            "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest(),
                        }
                    )
        (output / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        for path, pin in pins:
            P.checked(path, pin)
        if P.includes(sdk / "CGIncludes")[0] != profile["includes_sha256"]:
            raise ValueError("post-processing SDK includes changed during production")
        result["outputs"] = {
            name: {
                "bytes": (output / name).stat().st_size,
                "sha256": P.sha(output / name),
            }
            for name in ("objects.bin", "index.jsonl")
        }
        result["success"] = True
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def validate_standard_scene(fog, maps, renderers):
    """Check source scene fog and actual lightmap use, independent of bake preferences."""
    if len(fog) != 1 or len(maps) != 1 or (fog[0]["m_Fog"] and fog[0]["m_FogMode"] != 1):
        raise ValueError("Standard source scene fog retention differs")
    lighting = maps[0]
    if lighting["m_Lightmaps"]:
        raise ValueError("Standard source scene lightmap usage differs")
    if any(
        lighting["m_EnlightenSceneMapping"][key]
        for key in (
            "m_Renderers",
            "m_Systems",
            "m_Probesets",
            "m_SystemAtlases",
            "m_TerrainChunks",
        )
    ):
        raise ValueError("Standard source scene realtime lighting differs")
    for value in renderers:
        if any(value[key] != 65535 for key in ("m_LightmapIndex", "m_LightmapIndexDynamic") if key in value):
            raise ValueError("Standard source renderer uses a lightmap")
    return "FOG_LINEAR" if fog[0]["m_Fog"] else None


def standard_selections(original_sdk, materials, fog_keyword="FOG_LINEAR"):
    """Return source runtime form and ordered per-tier Standard keyword rows."""
    source = deepcopy(original_sdk)
    if source["m_ParsedForm"]["m_Name"] != "Standard" or len(materials) not in (1, 2, 3):
        raise ValueError("bounded Standard source selection differs")
    form = source["m_ParsedForm"]
    snippets = dict(source["m_CompileInfo"]["m_Snippets"])
    features = {name for name, flag in zip(form["m_KeywordNames"], form["m_KeywordFlags"]) if flag == 1}
    for snippet in snippets.values():
        runtime_axes = set(snippet["m_NonStrippedUserKeywords"].split())
        for stage in range(2):
            for axis in snippet["m_VariantsUserGlobal" + str(stage)]:
                features.update(set(axis) - runtime_axes - {"_", "__"})
    selected_features = []
    for material in materials:
        keywords = set(material.get("m_ValidKeywords", [])) | set(material.get("m_InvalidKeywords", [])) | set(material.get("m_ShaderKeywords", "").split())
        selected_features.append(keywords & features)
    baked = {
        "LIGHTMAP_ON",
        "DYNAMICLIGHTMAP_ON",
        "SHADOWS_SHADOWMASK",
        "DIRLIGHTMAP_COMBINED",
        "LIGHTMAP_SHADOW_MIXING",
    }
    selections = {}
    for subshader in form["m_SubShaders"]:
        runtime_passes = []
        for shader_pass in subshader["m_Passes"]:
            tags = {name.upper(): value.upper() for name, value in shader_pass["m_State"]["m_Tags"]["tags"]}
            if tags.get("LIGHTMODE") == "META":
                continue
            runtime_passes.append(shader_pass)
            identity = shader_pass["m_State"]["gpuProgramID"]
            snippet = snippets[identity]
            allowed = {form["m_KeywordNames"][i] for i in shader_pass["m_SerializedKeywordStateMask"]}
            local = []
            for selected in selected_features:
                keys = sorted(selected & allowed)
                if keys not in local:
                    local.append(keys)
            if [] not in local:
                raise ValueError("original default Standard material is absent")
            builtin = []
            for stage in range(2):
                for keys in snippet["m_VariantsBuiltin" + str(stage)]:
                    if not baked.intersection(keys) and keys not in builtin:
                        builtin.append(keys)
            builtin = builtin or [[]]
            axes = []
            for stage in range(2):
                for axis in snippet["m_VariantsUserGlobal" + str(stage)]:
                    if set(axis) - {"_", "__"} <= features:
                        continue
                    choices = []
                    for name in axis:
                        if name.startswith("FOG_") and name != fog_keyword:
                            continue
                        if name == "INSTANCING_ON" and not any(material["m_EnableInstancingVariants"] for material in materials):
                            continue
                        choices.append([] if name in ("_", "__") else [name])
                    if choices not in axes:
                        axes.append(choices)
            global_rows = [sum(values, []) for values in product(*axes)] if axes else [[]]
            nonbase = [keys for keys in local if keys]
            ordered = []
            for global_keys in global_rows:
                cycle = [([], builtin[0])] + [(keys, engine) for engine in builtin[1:] for keys in nonbase + [[]]] + [(keys, builtin[0]) for keys in nonbase]
                for local_keys, engine_keys in cycle:
                    keys = sorted(set(local_keys + engine_keys + global_keys))
                    if keys not in ordered:
                        ordered.append(keys)
            selections[identity] = [deepcopy(ordered) for _ in range(3)]
        subshader["m_Passes"] = runtime_passes
    return source, selections


def produce_standard(profile_path, profile_sha256, pc, sdk, output, codec, codec_sha256):
    """Produce the bounded Standard source record through the shared SDK owner."""
    import UnityPy

    profile_path = Path(profile_path).resolve(strict=True)
    profile_pin = {"bytes": profile_path.stat().st_size, "sha256": profile_sha256}
    P.checked(profile_path, profile_pin)
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != INPUT_ID:
        raise ValueError("Standard requires the accepted current original input")
    pc, sdk = Path(pc).resolve(strict=True), Path(sdk).resolve(strict=True)
    codec = Path(codec).resolve(strict=True)
    codec_pin = {"bytes": codec.stat().st_size, "sha256": codec_sha256}
    output = checked_output(output, (pc, sdk, profile_path, codec))
    source = profile["source_type"]
    selections = [source, *profile["materials"], profile["scene"]]
    pins = [(profile_path, profile_pin), (codec, codec_pin)]
    pins.extend((P.relative(pc, selected["path"]), selected) for selected in selections)
    pins.extend((P.relative(sdk, name), pin) for name, pin in profile["compiler_sdk"].items())
    for path, pin in pins:
        P.checked(path, pin)
    inventory, common = P.includes(sdk / "CGIncludes")
    if inventory != profile["compiler_includes_sha256"]:
        raise ValueError("Standard SDK includes differ")

    def original_object(selected, kind):
        environment = UnityPy.load(str(P.relative(pc, selected["path"])))
        obj = next(
            obj for obj in environment.objects if (obj.assets_file.name, obj.path_id) == (selected["member"], selected["path_id"]) and obj.type.name == kind
        )
        if "body_sha256" in selected and hashlib.sha256(obj.get_raw_data()).hexdigest() != selected["body_sha256"]:
            raise ValueError("Standard original material body differs")
        return obj

    obj = original_object(source, "Shader")
    original = obj.read_typetree()
    sdk_id = profile.get("sdk_shader", 46)
    expected_name = {46: "Standard", 106: "Skybox/Procedural"}[sdk_id]
    if original["m_ParsedForm"]["m_Name"] != expected_name:
        raise ValueError("Standard native type source differs")
    materials = []
    for selected in profile["materials"]:
        material = original_object(selected, "Material")
        value = material.read_typetree()
        pointer = value["m_Shader"]
        if pointer["m_PathID"] != obj.path_id or not pointer["m_FileID"]:
            raise ValueError("Standard material shader source differs")
        external = material.assets_file.externals[pointer["m_FileID"] - 1].path
        if Path(external).name != source["member"]:
            raise ValueError("Standard material shader member differs")
        materials.append(value)
    environment = UnityPy.load(str(P.relative(pc, profile["scene"]["path"])))
    scene_objects = [obj for obj in environment.objects if "member" not in profile["scene"] or obj.assets_file.name == profile["scene"]["member"]]
    fog = [obj.read_typetree() for obj in scene_objects if obj.type.name == "RenderSettings"]
    maps = [obj.read_typetree() for obj in scene_objects if obj.type.name == "LightmapSettings"]
    fog_keyword = validate_standard_scene(
        fog,
        maps,
        [renderer.read_typetree() for renderer in scene_objects if renderer.type.name.endswith("Renderer")],
    )
    sdk_pin = profile["compiler_sdk"]["Resources/unity_builtin_extra"]["sha256"]
    sdk_source = SDK.sdk_source(sdk, sdk_id, sdk_pin)
    if sdk_id == 106:
        selected = profile["materials"][0]
        pointer = fog[0]["m_SkyboxMaterial"]
        render = next(row for row in scene_objects if row.type.name == "RenderSettings")
        if len(materials) != 1 or pointer["m_PathID"] != selected["path_id"] or not pointer["m_FileID"]:
            raise ValueError("source scene skybox material differs")
        if Path(render.assets_file.externals[pointer["m_FileID"] - 1].path).name != selected["member"]:
            raise ValueError("source scene skybox member differs")
        if original["m_Dependencies"] or sdk_source["m_Dependencies"]:
            raise ValueError("source skybox dependencies differ")
        source_runtime = sdk_source
        keyword_rows = P.sdk_scene_selections(
            source_runtime, set(materials[0].get("m_ValidKeywords", [])) | set(materials[0].get("m_ShaderKeywords", "").split())
        )
    else:
        source_runtime, keyword_rows = standard_selections(sdk_source, materials, fog_keyword)
        # SDK source Standard depends on its own Legacy/VertexLit6. The original
        # PC dependency independently resolves that same named shader in its CAB.
        dependencies = original["m_Dependencies"]
        if len(dependencies) != 1 or dependencies[0]["m_FileID"] != 0:
            raise ValueError("Standard original fallback relationship differs")
        fallback = obj.assets_file.objects[dependencies[0]["m_PathID"]]
        name = fallback.read_typetree()["m_ParsedForm"]["m_Name"]
        sdk_fallback = SDK.sdk_source(sdk, 6, sdk_pin)
        if fallback.type.name != "Shader" or name != "Legacy Shaders/VertexLit" or sdk_fallback["m_ParsedForm"]["m_Name"] != name:
            raise ValueError("Standard original/SDK fallback identities differ")
        if source_runtime["m_Dependencies"] != [{"m_FileID": 0, "m_PathID": 6}]:
            raise ValueError("Standard SDK fallback relationship differs")
        # All three selected scene members put Resources/unity_builtin_extra first.
        source_runtime["m_Dependencies"] = [{"m_FileID": 1, "m_PathID": 6}]
    tiers = [deepcopy(profile["settings"]) for _ in range(3)]
    for tier, quality in zip(tiers, (0, 1, 1)):
        tier["tier0"]["standardShaderQuality"] = quality
    repo = Path(P.__file__).resolve().parents[3]
    compiler = P.module("_payload_standard_compiler", repo / "tools/phone-build/owner-code/shader.py")
    output.mkdir()
    result = {
        "success": False,
        "input_id": INPUT_ID,
        "profile_sha256": profile_sha256,
        "outputs": {},
    }
    started = time.monotonic()
    try:
        native_output = output / "standard"
        native_output.mkdir()
        with (
            compiler.compiler(
                [sdk / "Tools/UnityShaderCompiler"],
                sdk,
                output / "compiler",
                includes=[sdk / "CGIncludes"],
            ) as connection,
            W.codec(codec, codec_sha256) as compress,
        ):
            # The supported shared API must retain SOURCE keyword_rows native
            # emission order; the old unfiltered source_ranks behavior differs.
            body, _, _ = SDK.compile_body(
                connection,
                source_runtime,
                obj.serialized_type.node,
                keyword_rows,
                tiers,
                (sdk / "MacOS/Unity").read_bytes(),
                common,
                compress,
                native_output,
                native_order={identity: rows[0] for identity, rows in keyword_rows.items()} if sdk_id == 46 else None,
            )
        # One produced byte extent supplies the three independently named rows.
        (output / "objects.bin").write_bytes(body)
        rows = []
        identities = set()
        for selected in profile["outputs"]:
            identity = tuple(selected[key] for key in ("bundle", "member", "path_id"))
            if identity in identities:
                raise ValueError("duplicate Standard output identity")
            identities.add(identity)
            rows.append({key: selected[key] for key in ("bundle", "member", "path_id")})
            rows[-1].update(offset=0, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        (output / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        for path, pin in pins:
            P.checked(path, pin)
        if P.includes(sdk / "CGIncludes")[0] != inventory:
            raise ValueError("Standard SDK includes changed during production")
        result["outputs"] = {
            name: {
                "bytes": (output / name).stat().st_size,
                "sha256": P.sha(output / name),
            }
            for name in ("objects.bin", "index.jsonl")
        }
        result["success"] = True
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def produce(
    profile_path,
    profile_sha256,
    pc,
    sdk,
    legacy_sdk,
    asset_ripper,
    output,
    codec,
    codec_sha256,
):
    """Read current originals/public SDK inputs and emit the existing record pack."""
    profile_path = Path(profile_path).resolve(strict=True)
    profile_pin = {"bytes": profile_path.stat().st_size, "sha256": profile_sha256}
    P.checked(profile_path, profile_pin)
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != INPUT_ID:
        raise ValueError("payload shaders require the accepted current original input")
    if "materials" in profile:
        return produce_standard(profile_path, profile_sha256, pc, sdk, output, codec, codec_sha256)
    if asset_ripper is None:
        raise ValueError("Barrier and post-processing require the public template source")
    if "shaders" in profile:
        return produce_postprocessing(
            profile_path,
            profile,
            profile_sha256,
            pc,
            sdk,
            asset_ripper,
            output,
            codec,
            codec_sha256,
        )
    if legacy_sdk is None:
        raise ValueError("Barrier shaders require the acquired legacy SDK metadata")
    pc, sdk, legacy_sdk, asset_ripper = (Path(path).resolve(strict=True) for path in (pc, sdk, legacy_sdk, asset_ripper))
    output = checked_output(output, (pc, sdk, legacy_sdk, asset_ripper))
    codec = Path(codec).resolve(strict=True)
    codec_pin = {"bytes": codec.stat().st_size, "sha256": codec_sha256}
    P.checked(codec, codec_pin)
    pins = [
        (profile_path, profile_pin),
        (codec, codec_pin),
        (P.relative(pc, profile["source_type"]["path"]), profile["source_type"]),
    ]
    pins.extend((P.relative(sdk, name), pin) for name, pin in profile["compiler_sdk"].items())
    pins.extend((P.relative(legacy_sdk, name), pin) for name, pin in profile["legacy_sdk"].items())
    for path, pin in pins:
        P.checked(path, pin)
    for root, field in (
        (sdk, "compiler_includes_sha256"),
        (legacy_sdk, "legacy_includes_sha256"),
    ):
        if P.includes(root / "CGIncludes")[0] != profile[field]:
            raise ValueError("shader SDK include inputs differ")
    import UnityPy
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    source = profile["source_type"]
    obj = next(
        obj
        for obj in UnityPy.load(str(P.relative(pc, source["path"]))).objects
        if (obj.assets_file.name, obj.path_id) == (source["member"], source["path_id"]) and obj.type.name == "Shader"
    )
    original, node = obj.read_typetree(), obj.serialized_type.node
    source_sdk = SDK.sdk_source(legacy_sdk, 34, profile["legacy_sdk"]["Resources/unity_builtin_extra"]["sha256"])
    repo = Path(P.__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "scripts/lab"))
    sources = P.module("_payload_shader_source", repo / "scripts/lab/shader_source.py")
    filename = profile["source_filename"]
    P.relative(repo, filename)
    prefix = "Source/AssetRipper.Export.UnityProjects/Shaders/Templates/"
    templates = {}
    for name, pin in profile["template_inputs"].items():
        data = subprocess.check_output(
            [
                "git",
                "-C",
                str(asset_ripper),
                "show",
                profile["exporter_revision"] + ":" + prefix + name,
            ]
        )
        if len(data) != pin["bytes"] or hashlib.sha256(data).hexdigest() != pin["sha256"]:
            raise ValueError("shader template input differs")
        templates[name] = data.decode().replace("\r", "")
    text, selected_template = sources.dummy_shader_source(original["m_ParsedForm"], templates)
    if selected_template != "SingleTexture":
        raise ValueError("Barrier source shader no longer selects its pinned template")
    settings = profile["settings"]
    tiers = [deepcopy(settings) for _ in range(3)]
    for tier, quality in zip(tiers, (0, 1, 1)):
        tier["tier0"]["standardShaderQuality"] = quality
    image = (sdk / "MacOS/Unity").read_bytes()
    legacy_image = (legacy_sdk / "MacOS/Unity").read_bytes()
    # Independently pinned SDK metadata: same snippet-key version and Android
    # target attributes/compression; SDK33 default tier source supplies 0/1/1.
    if P.sdk_read(legacy_image, 0x103340270 + 18 * 4, 4) != P.sdk_read(image, 0x103396C84 + 18 * 4, 4):
        raise ValueError("legacy source snippet version differs from the qualified compiler")
    if struct.unpack("<II", P.sdk_read(legacy_image, 0x10335A3E8, 8)) != (
        0x00702842,
        0x15,
    ):
        raise ValueError("legacy Android source attributes differ")
    if struct.unpack("<I", P.sdk_read(legacy_image, 0x101B24EFC, 4))[0] != 0x528003E8:
        raise ValueError("legacy Android source compression differs")
    # Shader SDK33's inherited Vulkan platform version accessor is mov w0,0;ret.
    if P.sdk_read((legacy_sdk / "Tools/UnityShaderCompiler").read_bytes(), 0x10003AF0C, 8) != bytes.fromhex("00008052c0035fd6"):
        raise ValueError("legacy Vulkan compiler metadata differs")
    _, common = P.includes(legacy_sdk / "CGIncludes")
    output.mkdir()
    result = {
        "success": False,
        "input_id": profile["input_id"],
        "profile_sha256": profile_sha256,
        "outputs": {},
    }
    started = time.monotonic()
    try:
        (output / "HGCloudRemap.shader").write_text(text)
        license_data = subprocess.check_output(
            [
                "git",
                "-C",
                str(asset_ripper),
                "show",
                profile["exporter_revision"] + ":LICENSE.md",
            ]
        )
        (output / "AssetRipper-LICENSE.md").write_bytes(license_data)
        vertex_output = output / "vertexlit"
        vertex_output.mkdir()
        compiler = P.module("_payload_shader_compiler", repo / "tools/phone-build/owner-code/shader.py")
        with (
            compiler.compiler(
                [sdk / "Tools/UnityShaderCompiler"],
                sdk,
                output / "compiler",
                includes=[sdk / "CGIncludes"],
            ) as connection,
            W.codec(codec, codec_sha256) as compress,
        ):
            vertex_body, vertex_tree, _ = SDK.compile_body(
                connection,
                source_sdk,
                node,
                vertexlit_selections(source_sdk),
                tiers,
                image,
                common,
                compress,
                vertex_output,
            )
            pre = connection.preprocess(
                text,
                filename,
                platform_keywords=["SHADER_API_MOBILE"],
                caching_preprocessor=settings["caching_preprocessor"],
            )
            if not pre["success"]:
                raise ValueError("Barrier source preprocessing failed")
            compiled = {}
            for snippet in pre["snippets"]:
                identity = snippet["fields"][0]
                requirements = next(row for row in pre["records"] if row["kind"] == "keywordsEnd" and row["fields"] == [identity])
                variants = []
                for keywords in P.retained_keywords(pre, identity):
                    required = P.shader_requirements(requirements, keywords)
                    compilation = connection.compile(
                        snippet["source"],
                        filename,
                        stage="vertex",
                        platform_keywords=P.platform_keywords(image, settings),
                        keywords=keywords,
                        flags=P.compilation_flags(image, settings),
                        requirements=required,
                    )
                    if not compilation["success"] or not compilation["data"]:
                        raise ValueError("Barrier source compilation failed")
                    variants.append(
                        {
                            "keywords": keywords,
                            "requirements": required,
                            "compilation": compilation,
                        }
                    )
                compiled[identity] = {
                    "identity": P.editor_hash(snippet, image, connection.capabilities, settings, common),
                    "variants": variants,
                }
            registry = (
                original["m_ParsedForm"]["m_KeywordNames"][:4],
                original["m_ParsedForm"]["m_KeywordFlags"][:4],
            )
            cloud_tree = P.construct(node, text, pre, compiled, compress, registry)
            fallback = cloud_tree["m_ParsedForm"]["m_FallbackName"]
            if vertex_tree["m_ParsedForm"]["m_Name"].removeprefix("Legacy Shaders/") != fallback:
                raise ValueError("Barrier source fallback identity differs")
            for name, flag in zip(
                vertex_tree["m_ParsedForm"]["m_KeywordNames"],
                vertex_tree["m_ParsedForm"]["m_KeywordFlags"],
            ):
                if name not in cloud_tree["m_ParsedForm"]["m_KeywordNames"]:
                    cloud_tree["m_ParsedForm"]["m_KeywordNames"].append(name)
                    cloud_tree["m_ParsedForm"]["m_KeywordFlags"].append(flag)
            cloud_tree["m_Dependencies"] = [{"m_FileID": 0, "m_PathID": profile["outputs"][1]["path_id"]}]
            writer = EndianBinaryWriter(endian="<")
            write_typetree(cloud_tree, node, writer)
            rows = []
            with (output / "objects.bin").open("wb") as stream:
                for selected, body in zip(profile["outputs"], (writer.bytes, vertex_body)):
                    rows.append({key: selected[key] for key in ("bundle", "member", "path_id")})
                    rows[-1].update(
                        offset=stream.tell(),
                        bytes=len(body),
                        sha256=hashlib.sha256(body).hexdigest(),
                    )
                    stream.write(body)
            (output / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        for path, pin in pins:
            P.checked(path, pin)
        for root, field in (
            (sdk, "compiler_includes_sha256"),
            (legacy_sdk, "legacy_includes_sha256"),
        ):
            if P.includes(root / "CGIncludes")[0] != profile[field]:
                raise ValueError("shader SDK includes changed during production")
        result["outputs"] = {
            name: {
                "bytes": (output / name).stat().st_size,
                "sha256": P.sha(output / name),
            }
            for name in ("objects.bin", "index.jsonl")
        }
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
    parser.add_argument(
        "--pc",
        type=Path,
        required=True,
        help="Read-only current legitimate PC installation",
    )
    parser.add_argument(
        "--sdk",
        type=Path,
        required=True,
        help="Current pinned Unity 2021.3.45f2 Contents; its compiler executes",
    )
    parser.add_argument(
        "--legacy-sdk",
        type=Path,
        help="Read-only Unity 2021.3.33f1 Contents for source/hash metadata; never executed",
    )
    parser.add_argument("--asset-ripper", type=Path, help="Read-only pinned public template Git source")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory disjoint from every input tree",
    )
    parser.add_argument("--codec", type=Path, required=True)
    parser.add_argument("--codec-sha256", required=True)
    args = parser.parse_args()
    result = produce(
        args.profile,
        args.profile_sha256,
        args.pc,
        args.sdk,
        args.legacy_sdk,
        args.asset_ripper,
        args.output,
        args.codec,
        args.codec_sha256,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
