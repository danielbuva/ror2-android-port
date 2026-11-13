"""Build the authored default player scene from original records and source lighting."""

import argparse
from contextlib import closing
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import struct
import time

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


M = module("_scene_managers", HERE / "player_managers.py")
SDK = module("_scene_sdk", HERE / "scene_sdk.py")
U = M.U
EXTERNALS = ("sharedassets0.assets", "Library/unity default resources", "globalgamemanagers.assets")
CLASSES = {"GameObject": 1, "Transform": 4, "Camera": 20, "MeshRenderer": 23, "MeshFilter": 33, "BoxCollider": 65, "Light": 108, "MonoBehaviour": 114}


def pointer(pid=0, fid=0):
    return dict(m_FileID=fid, m_PathID=pid)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def rotation(euler):
    U.require(len(euler) == 3 and euler[2] == 0, "default scene supports XY Euler authoring")
    x, y = [f32(f32(f32(v) * f32(math.pi / 180)) * f32(0.5)) for v in euler[:2]]
    sx, cx, sy, cy = [f32(v) for v in (math.sin(x), math.cos(x), math.sin(y), math.cos(y))]
    return dict(zip("xyzw", (f32(cy * sx), f32(sy * cx), f32(-sy * sx), f32(cy * cx))))


def native_copy(obj, overrides):
    """Rebind preserved references by provider name; replaced fields need no donor."""
    fields = copy.deepcopy(M.G.native_fields(obj, U))

    def remap(ptr):
        fid, pid = ptr["m_FileID"], ptr["m_PathID"]
        if not pid:
            return pointer()
        U.require(0 < fid <= len(obj.asset.externals), "unbound original scene-local reference")
        path = obj.asset.externals[fid - 1]["path"]
        U.require(path in EXTERNALS, "unbound original scene provider: " + path)
        return pointer(pid, EXTERNALS.index(path) + 1)

    for key in fields:
        if key in overrides:
            fields[key] = overrides[key]
        else:
            U.map_pointers(fields[key], remap)
    U.require(overrides.keys() <= fields.keys(), "scene assignment absent from native schema")
    return fields


def bootstrap(path):
    import yaml

    U.require(yaml.__version__ == "6.0.3", "unqualified scene settings parser")
    raw = re.sub(r"^%.*\n", "", path.read_text(), flags=re.M)
    raw = re.sub(r"^--- !u!\d+ &\d+", "---", raw, flags=re.M)
    documents = list(yaml.safe_load_all(raw))
    U.require(all(isinstance(d, dict) and len(d) == 1 for d in documents), "invalid public scene settings")
    roots = [next(iter(d.values())) for d in documents]
    cameras = [d for d in roots if "near clip plane" in d]
    lighting = [d for d in roots if "m_GISettings" in d]
    U.require(len(cameras) == len(lighting) == 1, "ambiguous public scene defaults")
    return cameras[0], lighting[0]


def environment(store, selected, result, request, images, bundle):
    value = store.json(result[0], dict(sha256=result[1]))
    asked = store.json(request[0], dict(sha256=request[1]))
    expected = selected["environment"]
    U.require(value.get("schema") == "owner-runtime-environment-v1" and value.get("success") is True, "source environment capture incomplete")
    U.require(value["unity_version"] == "2021.3.45f2" and value["graphics_api"] == "Vulkan", "environment SDK/API differs")
    U.require(value["texture_format"] == "RGBAHalf" and value["hdr_decode"] == [1, 1, 0, 0], "environment native HDR representation differs")
    U.require(value["ambient_semantics"] == "RenderSettings.ambientProbe (final)", "environment probe semantics differ")
    U.require(
        value["source_recipe_sha256"] == asked["source_recipe_sha256"] == selected["public_inputs"]["environment"]["sha256"], "environment source owner differs"
    )
    U.require(re.fullmatch("[a-f0-9]{32}", asked["id"]) is not None, "invalid environment operation identity")
    U.require(value["width"] == asked["width"] == expected["width"] and value["mips"] == 8, "environment resolution differs")
    U.require(
        asked["material"] == expected["material"] and asked["light_euler"] == dict(zip("xyz", expected["light_euler"])),
        "environment source scene policy differs",
    )
    U.require(value["bundle_sha256"] == asked["bundle_sha256"] == bundle[1], "environment material provider differs")
    store.pin(bundle[0], dict(sha256=bundle[1]))
    # Independently bind captured uniforms/keywords to the legitimate default sky.
    material_source = store.asset(selected["sources"]["shared"])
    originals = [M.G.native_fields(o, U) for o in material_source.objects.values() if o.type.value == 21]
    originals = [d for d in originals if d["m_Name"] == "Default-Skybox"]
    native_bundle = U.W.B.Bundle(Path(bundle[0]))
    names = [name for name in native_bundle.members if not name.endswith((".resS", ".resource"))]
    U.require(len(names) == 1, "source sky bundle member is ambiguous")
    asset = store.asset_file(bundle[0], "source-sky-bundle", dict(sha256=bundle[1]), names[0])
    materials = [M.G.native_fields(o, U) for o in asset.objects.values() if o.type.value == 21]
    U.require(len(materials) == len(originals) == 1, "source sky material is ambiguous")
    for key in ("m_ValidKeywords", "m_SavedProperties"):
        U.require(materials[0][key] == originals[0][key], "captured source sky parameters differ from original default")
    rows = value["images"]
    U.require(
        len(rows) == 48 and {(r["face"], r["mip"]) for r in rows} == {(f, m) for f in range(6) for m in range(8)}, "incomplete source environment faces/mips"
    )
    pixels = {}
    for row in rows:
        width = max(1, expected["width"] >> row["mip"])
        name = "face-" + str(row["face"]) + "-mip-" + str(row["mip"]) + ".rgba16f"
        U.require(row["file"] == name and row["width"] == width and row["bytes"] == width * width * 8, "invalid source environment extent")
        path = Path(images) / name
        store.pin(path, dict(sha256=row["sha256"], bytes=row["bytes"]))
        raw = path.read_bytes()
        U.require(all(all(math.isfinite(v) for v in pixel) for pixel in struct.iter_unpack("<4e", raw)), "source environment contains nonfinite pixels")
        pixels[row["face"], row["mip"]] = raw
    ambient = value["ambient"]
    U.require(len(ambient) == 27 and all(math.isfinite(v) for v in ambient), "invalid source ambient coefficients")
    return b"".join(pixels[f, m] for f in range(6) for m in range(8)), ambient


def runtime_script(store, shapes, native, registry):
    original = next(o for o in shapes.objects.values() if o.type.value == 114)
    base = []
    for node in U.S.tree_nodes(U.explicit_tree(original.typ["tree"])):
        if node["level"] == 1 and node["name"] not in {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}:
            break
        base.append(node)
    U.require([n["name"] for n in base if n["level"] == 1] == ["m_GameObject", "m_Enabled", "m_Script", "m_Name"], "source runtime component base differs")
    tree = U.S._tree(base)
    candidates = [(pid, U.S._script_record(obj.get_raw_data())) for pid, obj in registry.objects.items() if obj.type.value == 115]
    selected = [(pid, d) for pid, d in candidates if d["identity"] == ("Assembly-CSharp.dll", "", "LabDiagnostics")]
    U.require(len(selected) == 1, "source scene script identity is ambiguous")
    sid, script = selected[0]
    U.require(
        U.S.properties_hash("LabDiagnostics", "", "Assembly-CSharp.dll", tree, native) == script["properties"],
        "source scene script schema differs from registry",
    )
    typ = dict(class_id=114, stripped=0, script_type=0, script_id=U.S.md4(b"LabDiagnosticsAssembly-CSharp.dll"), hash=script["properties"], tree=tree)
    return sid, typ, U.node_from_tree(tree)


def construct(selected, templates, camera, gi, tags, mesh, script, pixels, ambient):
    roles, nodes = [], {}
    for node in selected["nodes"]:
        name = node["name"]
        U.require(name not in nodes and "/" not in name and node["components"] == list(dict.fromkeys(node["components"])), "ambiguous scene node/components")
        nodes[name] = node
        roles.extend((name + "/" + kind, CLASSES[kind]) for kind in ["GameObject", "Transform", *node["components"]])
    roles.extend(("$/" + kind, cid) for kind, cid in (("RenderSettings", 104), ("LightmapSettings", 157), ("NavMeshSettings", 196), ("Cubemap", 89)))
    ids = {role: i + 1 for i, (role, _) in enumerate(roles)}
    sid, script_type, script_node = script
    records = []
    for role, cid in roles:
        owner = role.rsplit("/", 1)[0]
        policy = nodes.get(owner)
        changes = {}
        if cid == 114:
            fields = U.zero(script_node)
            fields.update(m_GameObject=pointer(ids[owner + "/GameObject"]), m_Enabled=1, m_Script=pointer(sid, 3), m_Name="")
            records.append(dict(id=ids[role], role=role, fields=fields, node=script_node, typ=script_type))
            continue
        obj = templates[cid]
        original = M.G.native_fields(obj, U)
        if cid == 1:
            components = ["Transform", *policy["components"]]
            changes = dict(
                m_Component=[dict(component=pointer(ids[owner + "/" + k])) for k in components],
                m_Layer=0,
                m_Name=owner,
                m_Tag=tags[policy.get("tag", "Untagged")],
                m_IsActive=True,
            )
        elif cid == 4:
            changes = dict(
                m_GameObject=pointer(ids[owner + "/GameObject"]),
                m_LocalRotation=rotation(policy.get("euler", [0, 0, 0])),
                m_LocalPosition=dict(zip("xyz", policy.get("position", [0, 0, 0]))),
                m_LocalScale=dict(x=1, y=1, z=1),
                m_Children=[],
                m_Father=pointer(),
            )
        elif cid == 20:
            projected = M.SET.project(copy.deepcopy(original), camera)
            changes = {key: value for key, value in projected.items() if value != original[key]}
            changes.update(m_GameObject=pointer(ids[owner + "/GameObject"]), m_BackGroundColor=dict(zip("rgba", policy["background"])), m_ClearFlags=2)
        elif cid == 108:
            shadows = copy.deepcopy(original["m_Shadows"])
            shadows["m_Type"] = 0
            changes = dict(m_GameObject=pointer(ids[owner + "/GameObject"]), m_Color=dict(r=1, g=1, b=1, a=1), m_Shadows=shadows)
        elif cid == 23:
            changes = dict(m_GameObject=pointer(ids[owner + "/GameObject"]), m_CastShadows=1, m_Materials=[pointer(selected["material_id"], 1)])
        elif cid == 33:
            changes = dict(m_GameObject=pointer(ids[owner + "/GameObject"]), m_Mesh=pointer(mesh, 2))
        elif cid == 65:
            changes = dict(m_GameObject=pointer(ids[owner + "/GameObject"]), m_IsTrigger=False)
        elif cid == 104:
            changes = dict(
                m_SkyboxMaterial=pointer(selected["skybox_id"], 1),
                m_GeneratedSkyboxReflection=pointer(ids["$/Cubemap"]),
                m_AmbientProbe=dict(zip(original["m_AmbientProbe"], ambient)),
                m_IndirectSpecularColor=dict(r=ambient[0], g=ambient[9], b=ambient[18], a=1),
            )
        elif cid == 157:
            changes = dict(m_GISettings=M.SET.project(copy.deepcopy(original["m_GISettings"]), gi["m_GISettings"]), m_LightingSettings=pointer())
        elif cid == 89:
            width = selected["environment"]["width"]
            changes = dict(
                m_TextureFormat=17,
                m_LightmapFormat=0,
                m_ColorSpace=0,
                m_Width=width,
                m_Height=width,
                m_MipCount=8,
                m_CompleteImageSize=len(pixels) // 6,
                m_StreamData=dict(offset=0, size=0, path=""),
            )
            changes["image data"] = pixels
        records.append(dict(id=ids[role], role=role, fields=native_copy(obj, changes), node=obj.node, typ=dict(obj.typ)))
    return records


def emit(records, sid, output):
    types, objects, bodies, manifest = [], [], {}, []
    cursor = 0
    for record in records:
        typ = record["typ"]
        if typ not in types:
            types.append(typ)
            tree = typ.get("tree")
            if tree is None:
                tree = U.S._tree(
                    [
                        dict(
                            type=n["m_Type"],
                            name=n["m_Name"],
                            level=n["m_Level"],
                            size=n["m_ByteSize"],
                            version=n["m_Version"],
                            flags=n.get("m_TypeFlags", 0),
                            meta=n["m_MetaFlag"],
                        )
                        for n in record["node"].to_dict_list()
                    ]
                )
            (output / ("schema-" + str(len(types) - 1) + ".tree")).write_bytes(U.explicit_tree(tree))
        body = U.encode(record["fields"], record["node"])
        cursor = (cursor + 7) // 8 * 8
        objects.append(dict(path_id=record["id"], type_id=types.index(typ), offset=cursor, bytes=len(body)))
        bodies[record["id"]] = body
        cursor += len(body)
        fields = copy.deepcopy(record["fields"])
        if "image data" in fields:
            fields["image data"] = dict(bytes=len(record["fields"]["image data"]))
        manifest.append(dict(id=record["id"], role=record["role"], class_id=typ["class_id"], fields=fields, sha256=hashlib.sha256(body).hexdigest()))
    layout = dict(
        engine="2021.3.45f2",
        platform=13,
        trees=False,
        types=types,
        objects=objects,
        scripts=[(3, sid)],
        externals=[dict(empty="", guid=bytes(16), type=0, path=p) for p in EXTERNALS],
        ref_types=[],
        user="",
    )
    with (output / "level0").open("xb") as stream:
        U.W.write_serialized(stream, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    (output / "objects.json").write_text(json.dumps(manifest, indent=2) + "\n")


def produce(profile_path, profile_sha256, pc, sdk, editor_resources, registry, shared, captured, output):
    started = time.monotonic()
    output, sdk = Path(output), Path(sdk)
    output.mkdir(exist_ok=False)
    with closing(M.Sources(pc)) as store:
        selected = store.json(profile_path, dict(sha256=profile_sha256))
        U.require(selected["schema"] == "owner-default-scene-v1", "unknown default scene recipe")
        public = {key: store.public(value) for key, value in selected["public_inputs"].items()}
        player = store.json(public["player"])
        U.require(player["input_id"] == selected["input_id"], "scene source input identity differs")
        code, symbols = [sdk / selected["sdk"][key]["path"] for key in ("code", "symbols")]
        for key, path in (("code", code), ("symbols", symbols)):
            store.pin(path, selected["sdk"][key])
        tags = SDK.builtin_tags(code, symbols, M.SDK)
        assets = {key: store.asset(value) for key, value in selected["sources"].items()}
        templates = {}
        for row in selected["templates"]:
            obj = assets[row["source"]].objects[row["path_id"]]
            U.require(obj.type.value == row["class_id"], "scene native source type differs")
            M.G.native_fields(obj, U)
            templates[row["class_id"]] = obj
        native = U.P.script_sdk_schema(editor_resources, player["script_properties_sdk"])
        store.pin(editor_resources, player["script_properties_sdk"])
        generated_registry = store.asset_file(registry[0], "generated-registry", dict(sha256=registry[1]))
        generated_shared = store.asset_file(shared[0], "generated-shared", dict(sha256=shared[1]))
        for pid, name in ((selected["material_id"], "Default-Material"), (selected["skybox_id"], "Default-Skybox")):
            obj = generated_shared.objects[pid]
            U.require(obj.type.value == 21 and M.G.native_fields(obj, U)["m_Name"] == name, "source scene shared material relationship differs")
        defaults = sdk / "Data/unity default resources"
        store.pin(defaults, selected["sdk"]["default"])
        resource = store.asset_file(defaults, "sdk-default")
        meshes = [pid for pid, obj in resource.objects.items() if obj.type.value == 43 and M.G.native_fields(obj, U)["m_Name"] == "Cube"]
        U.require(len(meshes) == 1, "SDK primitive Cube identity is ambiguous")
        pixels, ambient = environment(store, selected, *captured)
        script = runtime_script(store, assets["shapes"], native, generated_registry)
        records = construct(selected, templates, *bootstrap(public["bootstrap"]), tags, meshes[0], script, pixels, ambient)
        # Check every direct PPtr against the actual selected native/script provider.
        providers = {1: generated_shared, 2: resource, 3: generated_registry}
        local = {r["id"]: r for r in records}
        references = []
        for record in records:

            def check(ptr):
                fid, pid = ptr["m_FileID"], ptr["m_PathID"]
                if pid:
                    U.require(pid in (local if fid == 0 else providers[fid].objects), "source scene pointer has no provider")
                    references.append((record["id"], fid, pid))
                return ptr

            U.map_pointers(record["fields"], check)
        emit(records, script[0], output)
        store.recheck()
        result = dict(
            success=True,
            profile_sha256=profile_sha256,
            files={"level0": dict(bytes=(output / "level0").stat().st_size, sha256=U.P.sha(output / "level0"), source_role="pc-sdk-and-source-environment")},
            objects=len(records),
            references=len(references),
            builtin_tags=tags,
            provider_pins=store.pins,
            historical_raw_exact=False,
            phone_qualified=False,
            runtime_qualified=False,
            seconds=time.monotonic() - started,
        )
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "profile-sha256", "pc-root", "sdk", "editor-resources", "environment-images", "output"):
        parser.add_argument("--" + name, required=True)
    for name in ("registry", "shared-defaults", "environment-result", "environment-request", "environment-bundle"):
        parser.add_argument("--" + name, nargs=2, metavar=("PATH", "SHA256"), required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            produce(
                args.profile,
                args.profile_sha256,
                args.pc_root,
                args.sdk,
                args.editor_resources,
                args.registry,
                args.shared_defaults,
                (args.environment_result, args.environment_request, args.environment_images, args.environment_bundle),
                args.output,
            )
        )
    )


if __name__ == "__main__":
    main()
