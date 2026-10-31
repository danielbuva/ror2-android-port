"""Compile standalone prefab SDK shaders and original dummy fallback forms.

Original forms/materials, acquired SDK declarations/default materials and pinned public
exporter templates are the only content providers. No accepted body, program,
pass-key or keyword/permutation table supplies production data.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import object_produce as O
import payload_shader_records as A
import shader_produce as P
import shader_sdk as SDK
import unity_write as W


def keyword_registry(source, seed):
    """Merge SDK declarations by snippet, stage, global/local axes, builtins."""
    names, flags = (list(values) for values in seed)
    for _, snippet in source["m_CompileInfo"]["m_Snippets"]:
        for stage in range(7):
            for group, flag in (("m_VariantsUserGlobal", 0), ("m_VariantsUserLocal", 1)):
                for axis in snippet[group + str(stage)]:
                    for name in axis:
                        if name.strip("_") and name not in names:
                            names.append(name)
                            flags.append(flag)
            for name in snippet["m_BuiltinKeywords"].split():
                if name not in names:
                    names.append(name)
                    flags.append(0)
    return names, flags


def original_fallback_dependencies(source, selected, original):
    """Retain original fallback edges, including an unresolved literal fallback."""
    witnesses = selected["fallback_original"]
    dependencies = source["m_Dependencies"]
    if dependencies != [{"m_FileID": 0, "m_PathID": row["original"]["path_id"]} for row in witnesses]:
        raise ValueError("Prefab original fallback dependencies differ")
    for row in witnesses:
        witness = row["original"]
        if (witness["path"], witness["member"]) != (selected["original"]["path"], selected["original"]["member"]):
            raise ValueError("Prefab original fallback member differs")
        if original(witness).read_typetree()["m_ParsedForm"]["m_Name"] != source["m_ParsedForm"]["m_FallbackName"]:
            raise ValueError("Prefab original fallback name differs")
    return [{"m_FileID": row["to"][0], "m_PathID": row["to"][1]} for row in witnesses]


def prefab_selections(source, *, retain_instancing=True, material_keywords=None, carrier=None):
    """Keep no-scene runtime axes, including source instancing alternatives."""
    snippets = dict(source["m_CompileInfo"]["m_Snippets"])
    selections = {}
    for sub_index, sub in enumerate(source["m_ParsedForm"]["m_SubShaders"]):
        original_passes = list(sub["m_Passes"])
        sub["m_Passes"] = [
            row
            for row in sub["m_Passes"]
            if not any(
                key.upper() == "LIGHTMODE" and value.upper() in {"META", "SCENESELECTIONPASS", "PICKING"} for key, value in row["m_State"]["m_Tags"]["tags"]
            )
        ]
        for row in sub["m_Passes"]:
            if row["m_Type"] == 0:
                identity = row["m_State"]["gpuProgramID"]
                snippet = snippets[identity]
                runtime = set(snippet["m_NonStrippedUserKeywords"].split())
                features = (
                    {
                        keyword
                        for group in ("m_VariantsUserGlobal", "m_VariantsUserLocal")
                        for stage in range(7)
                        for axis in snippet[group + str(stage)]
                        for keyword in axis
                    }
                    - runtime
                    - {"_", "__"}
                )
                if material_keywords is None:
                    variants = P.sdk_scene_variants(snippet, set(), retain_instancing=retain_instancing)
                else:
                    # Retain the default and actual material feature combinations.
                    admitted = {frozenset(), *(frozenset(keys & features) for keys in material_keywords)}
                    variants = [
                        variant
                        for variant in P.sdk_scene_variants(snippet, retain_instancing=retain_instancing)
                        if frozenset(set(variant) & features) in admitted
                    ]
                if carrier is not None:
                    declared = set().union(*(set(keys) for keys in variants))
                    # Vertex records include vertex-only runtime alternatives
                    # absent from original fragment records (e.g. vertex lights).
                    variants = A.original_feature_order(carrier, sub_index, original_passes.index(row), row, declared, variants, stage="progVertex")
                selections[identity] = [deepcopy(variants) for _ in range(3)]
    return selections


def terrain_selections(source, terrain, pointer):
    """Empty original detail prototypes create no instancing users."""
    database = terrain["m_DetailDatabase"]
    if pointer not in [database[f"m_DefaultShaders[{i}]"] for i in range(3)]:
        raise ValueError("Prefab TerrainData default Shader identity differs")
    if database["m_DetailPrototypes"]:
        raise ValueError("Prefab TerrainData has detail prototype usage")
    return prefab_selections(source, retain_instancing=False)


def particle_selections(source, original, material):
    """Filter original particle order by acquired default-material features."""
    if material["m_Shader"] != {"m_FileID": 0, "m_PathID": 211}:
        raise ValueError("Prefab particle default material shader differs")
    form = source["m_ParsedForm"]
    features = {name for name, flag in zip(form["m_KeywordNames"], form["m_KeywordFlags"], strict=True) if flag == 1}
    for _, snippet in source["m_CompileInfo"]["m_Snippets"]:
        runtime = set(snippet["m_NonStrippedUserKeywords"].split())
        for stage in range(7):
            for axis in snippet["m_VariantsUserGlobal" + str(stage)]:
                features.update(set(axis) - runtime - {"_", "__"})
    enabled = set(material.get("m_ValidKeywords", [])) | set(material.get("m_InvalidKeywords", [])) | set(material.get("m_ShaderKeywords", "").split())
    return A.particles_selections(source, [material], None, carrier=original, stripped_keywords=features - enabled)


def produce(profile_path, profile_pin, pc, sdk, asset_ripper, codec, codec_pin, output):
    import UnityPy
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    profile_path, pc, sdk, codec = (Path(p).resolve(strict=True) for p in (profile_path, pc, sdk, codec))
    P.checked(profile_path, {"bytes": profile_path.stat().st_size, "sha256": profile_pin})
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != A.INPUT_ID or not {"MacOS/Unity", "Tools/UnityShaderCompiler", "Resources/unity_builtin_extra"} <= profile["sdk"].keys():
        raise ValueError("Prefab Shader requires original input and explicit SDK providers")
    providers = [pc, sdk, profile_path, codec]
    if asset_ripper is not None:
        asset_ripper = Path(asset_ripper).resolve(strict=True)
        providers.append(asset_ripper)
    output = A.checked_output(output, providers)
    pins = [(profile_path, {"bytes": profile_path.stat().st_size, "sha256": profile_pin}), (codec, {"bytes": codec.stat().st_size, "sha256": codec_pin})]
    pins.extend((P.relative(sdk, name), pin) for name, pin in profile["sdk"].items())
    for record in profile["records"]:
        pins.append((P.relative(pc, record["original"]["path"]), record["original"]))
        pins.extend((P.relative(pc, material["path"]), material) for material in record.get("materials", []))
        if "terrain" in record:
            witness = record["terrain"]["original"]
            pins.append((P.relative(pc, witness["path"]), witness))
        pins.extend((P.relative(pc, row["original"]["path"]), row["original"]) for row in record.get("fallback_original", []))
    for path, pin in pins:
        P.checked(path, pin)
    inventory, common = P.includes(sdk / "CGIncludes")
    if inventory != profile["includes_sha256"]:
        raise ValueError("Prefab Shader include inputs differ")
    templates = {}
    if any(row["kind"] == "dummy" for row in profile["records"]):
        if asset_ripper is None:
            raise ValueError("Prefab dummy requires explicit public template provider")
        for name, pin in profile["template_inputs"].items():
            raw = subprocess.check_output(
                ["git", "-C", str(asset_ripper), "show", profile["exporter_revision"] + ":Source/AssetRipper.Export.UnityProjects/Shaders/Templates/" + name]
            )
            if len(raw) != pin["bytes"] or hashlib.sha256(raw).hexdigest() != pin["sha256"]:
                raise ValueError("Prefab Shader public template differs")
            templates[name] = raw.decode().replace("\r", "")
    originals, sdk_objects = {}, {}

    def original(selected, class_name="Shader"):
        path = P.relative(pc, selected["path"])
        originals.setdefault(path, None)
        if originals[path] is None:
            originals[path] = UnityPy.load(str(path))
        obj = next(obj for obj in originals[path].objects if (obj.assets_file.name, obj.path_id) == (selected["member"], selected["path_id"]))
        if obj.type.name != class_name or hashlib.sha256(obj.get_raw_data()).hexdigest() != selected["body_sha256"]:
            raise ValueError("Prefab original Shader body differs")
        return obj

    def original_materials(selected):
        materials = []
        for witness in selected["materials"]:
            path = P.relative(pc, witness["path"])
            if path not in originals:
                originals[path] = UnityPy.load(str(path))
            obj = next(obj for obj in originals[path].objects if (obj.assets_file.name, obj.path_id) == (witness["member"], witness["path_id"]))
            if obj.type.name != "Material" or hashlib.sha256(obj.get_raw_data()).hexdigest() != witness["body_sha256"]:
                raise ValueError("Prefab original material body differs")
            material = obj.read_typetree()
            pointer = material["m_Shader"]
            file_id = pointer["m_FileID"]
            member = obj.assets_file.name if file_id == 0 else obj.assets_file.externals[file_id - 1].path.rsplit("/", 1)[-1]
            if (member, pointer["m_PathID"]) != (selected["original"]["member"], selected["original"]["path_id"]):
                raise ValueError("Prefab original material shader differs")
            materials.append(material)
        return materials

    def sdk_source(identity):
        if identity not in sdk_objects:
            sdk_objects[identity] = SDK.sdk_source(sdk, identity, profile["sdk"]["Resources/unity_builtin_extra"]["sha256"])
        return deepcopy(sdk_objects[identity])

    def chain(identity):
        identities = [identity]
        for current in identities:
            for dep in sdk_source(current)["m_Dependencies"]:
                if dep["m_FileID"] or not dep["m_PathID"]:
                    raise ValueError("Prefab SDK dependency must resolve in the acquired SDK")
                if dep["m_PathID"] not in identities:
                    identities.append(dep["m_PathID"])
        return identities

    links = {row["sdk_shader"]: row["to"] for row in profile["shader_links"]}
    if len(links) != len(profile["shader_links"]):
        raise ValueError("Duplicate prefab SDK destination identity")

    def pointers(identities):
        return [{"m_FileID": links[i][0], "m_PathID": links[i][1]} for i in identities]

    repo = HERE.parents[2]
    sys.path.insert(0, str(repo / "scripts/lab"))
    sources = P.module("_prefab_source", repo / "scripts/lab/shader_source.py")
    compiler = P.module("_prefab_compiler", repo / "tools/phone-build/owner-code/shader.py")
    image = (sdk / "MacOS/Unity").read_bytes()
    tiers = [deepcopy(profile["settings"]) for _ in range(3)]
    for tier, quality in zip(tiers, (0, 1, 1)):
        tier["tier0"]["standardShaderQuality"] = quality
    output.mkdir()
    started = time.monotonic()
    receipt = {
        "success": False,
        "input_id": A.INPUT_ID,
        "profile_sha256": profile_pin,
        "source_only": True,
        "target_reads": False,
        "objects": 0,
        "object_bytes": 0,
    }
    try:
        if templates:
            (output / "AssetRipper-LICENSE.md").write_bytes(
                subprocess.check_output(["git", "-C", str(asset_ripper), "show", profile["exporter_revision"] + ":LICENSE.md"])
            )
        with (
            compiler.compiler([sdk / "Tools/UnityShaderCompiler"], sdk, output / "compiler", includes=[sdk / "CGIncludes"]) as connection,
            W.codec(codec, codec_pin) as compress,
            (output / "objects.bin").open("wb") as data,
            (output / "index.jsonl").open("w") as index,
        ):
            for ordinal, selected in enumerate(profile["records"]):
                obj = original(selected["original"])
                source, node = obj.read_typetree(), obj.serialized_type.node
                if selected["kind"] == "sdk":
                    identity = selected["sdk_shader"]
                    runtime = sdk_source(identity)
                    if any(source["m_ParsedForm"][key] != runtime["m_ParsedForm"][key] for key in ("m_Name", "m_PropInfo")):
                        raise ValueError("Prefab original/SDK Shader properties differ")
                    if "materials" in selected:
                        materials = original_materials(selected)
                        if identity == 211:
                            runtime, selections = A.particles_selections(runtime, materials, None, carrier=source)
                        else:
                            selections = prefab_selections(
                                runtime,
                                retain_instancing=any(material["m_EnableInstancingVariants"] for material in materials),
                                carrier=source,
                                material_keywords=[
                                    set(material.get("m_ValidKeywords", []))
                                    | set(material.get("m_InvalidKeywords", []))
                                    | set(material.get("m_ShaderKeywords", "").split())
                                    for material in materials
                                ],
                            )
                    elif "terrain" in selected:
                        witness = selected["terrain"]
                        terrain = original(witness["original"], "TerrainData")
                        file_id = witness["shader_file_id"]
                        member = terrain.assets_file.externals[file_id - 1].path.rsplit("/", 1)[-1] if file_id else terrain.assets_file.name
                        if member != selected["original"]["member"]:
                            raise ValueError("Prefab TerrainData Shader member differs")
                        selections = terrain_selections(runtime, terrain.read_typetree(), {"m_FileID": file_id, "m_PathID": obj.path_id})
                    elif "sdk_material" in selected:
                        material = next(
                            obj
                            for obj in UnityPy.load(str(sdk / "Resources/unity_builtin_extra")).objects
                            if obj.path_id == selected["sdk_material"] and obj.type.name == "Material"
                        )
                        material = material.read_typetree()
                        if material["m_Shader"] != {"m_FileID": 0, "m_PathID": identity}:
                            raise ValueError("Prefab SDK material shader differs")
                        if identity == 211:
                            runtime, selections = particle_selections(runtime, source, material)
                        else:
                            selections = prefab_selections(runtime, retain_instancing=bool(material["m_EnableInstancingVariants"]))
                    else:
                        if identity == 211:
                            raise ValueError("Prefab particle shader requires its SDK material")
                        selections = prefab_selections(runtime)
                    runtime["m_Dependencies"] = pointers(chain(identity)[1:])
                    leaf = output / str(ordinal)
                    leaf.mkdir()
                    body, _, _ = SDK.compile_body(
                        connection,
                        runtime,
                        node,
                        selections,
                        tiers,
                        image,
                        common,
                        compress,
                        leaf,
                        native_order={i: rows[0] for i, rows in selections.items()} if identity == 211 or "materials" in selected else None,
                    )
                elif selected["kind"] == "dummy":
                    filename = selected["source_filename"]
                    P.relative(repo, filename)
                    text, template = sources.dummy_shader_source(source["m_ParsedForm"], templates)
                    if template != selected["template"]:
                        raise ValueError("Prefab original dummy template differs")
                    tree = A.postprocessing_tree(connection, text, filename, source, node, profile["settings"], image, common, compress)
                    fallback = tree["m_ParsedForm"]["m_FallbackName"]
                    if "fallback_original" in selected:
                        tree["m_Dependencies"] = original_fallback_dependencies(source, selected, original)
                    else:
                        identity = selected["fallback_sdk_shader"]
                        fallback_source = sdk_source(identity)
                        if fallback_source["m_ParsedForm"]["m_Name"].removeprefix("Legacy Shaders/") != fallback:
                            raise ValueError("Prefab original/SDK fallback identity differs")
                        form = tree["m_ParsedForm"]
                        form["m_KeywordNames"], form["m_KeywordFlags"] = keyword_registry(fallback_source, (form["m_KeywordNames"], form["m_KeywordFlags"]))
                        tree["m_Dependencies"] = pointers(chain(identity))
                    writer = EndianBinaryWriter(endian="<")
                    write_typetree(tree, node, writer)
                    body = writer.bytes
                    (output / (str(ordinal) + ".shader")).write_text(text)
                else:
                    raise ValueError("Unknown prefab Shader source kind")
                for target in selected["outputs"]:
                    made = O.remap(body, target.get("references", []))
                    if len(made) != target["bytes"] or hashlib.sha256(made).hexdigest() != target["sha256"]:
                        raise ValueError("Prefab Shader record differs from accepted hash: " + str(ordinal))
                    row = {key: target[key] for key in ("bundle", "member", "path_id", "bytes", "sha256")}
                    row["offset"] = data.tell()
                    data.write(made)
                    index.write(json.dumps(row, sort_keys=True) + "\n")
                    receipt["objects"] += 1
                    receipt["object_bytes"] += len(made)
        for row in map(json.loads, (output / "index.jsonl").read_text().splitlines()):
            O.record_extent(output / "objects.bin", row)
        for path, pin in pins:
            P.checked(path, pin)
        for selected in profile["records"]:
            original(selected["original"])
            if "terrain" in selected:
                original(selected["terrain"]["original"], "TerrainData")
        if P.includes(sdk / "CGIncludes")[0] != inventory:
            raise ValueError("Prefab Shader include inputs changed")
        receipt.update(
            success=True, outputs={name: {"bytes": (output / name).stat().st_size, "sha256": P.sha(output / name)} for name in ("objects.bin", "index.jsonl")}
        )
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "profile-sha256", "pc-root", "sdk", "codec", "codec-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--asset-ripper")
    args = parser.parse_args()
    print(json.dumps(produce(args.profile, args.profile_sha256, args.pc_root, args.sdk, args.asset_ripper, args.codec, args.codec_sha256, args.output)))


if __name__ == "__main__":
    main()
