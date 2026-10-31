"""Construct complete native managers from public policy and produced player files."""

from contextlib import closing
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import struct
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


U = module("_managers_ui", HERE / "player_ui.py")
G = module("_managers_graph", HERE / "manager_graph.py")
SET = module("_managers_settings", HERE / "manager_settings.py")
SDK = module("_managers_sdk", HERE / "manager_sdk.py")


class Sources(U.Sources):
    U = U
    root = ROOT

    def public(self, selected):
        name = PurePosixPath(selected["path"])
        U.require(not name.is_absolute() and ".." not in name.parts and "\\" not in str(name), "unsafe manager public input")
        path = ROOT / name
        U.require(path.resolve(strict=True).is_relative_to(ROOT), "manager public input leaves source tree")
        self.pin(path, selected)
        return path

    def recipe_by_hash(self, digest):
        paths = [p for p in (ROOT / "recipe").glob("owner-*textures.json") if U.P.sha(p) == digest]
        U.require(len(paths) == 1, "manager texture recipe absent/ambiguous")
        return self.json(paths[0])

    def native_fields(self, obj):
        return G.native_fields(obj, U)


def h128(value):
    raw = bytes.fromhex(value) if isinstance(value, str) else value
    U.require(len(raw) == 16, "native hash width differs")
    return {f"bytes[{i}]": byte for i, byte in enumerate(raw)}


def scripts(files, originals, pointer):
    original = originals["MonoManager"]
    out = copy.deepcopy(G.native_fields(original, U))
    default = files.asset("Library/unity default resources")
    registry = files.asset("globalgamemanagers.assets")
    sdk_ids = []
    for ptr in out["m_Scripts"]:
        fid = ptr["m_FileID"]
        U.require(0 < fid <= len(original.asset.externals), "original script provider differs")
        if original.asset.externals[fid - 1]["path"] == "Library/unity default resources":
            U.require(ptr["m_PathID"] in default.objects and default.objects[ptr["m_PathID"]].type.value == 115, "SDK MonoScript absent")
            sdk_ids.append(ptr["m_PathID"])
    registry_ids = sorted(pid for pid, obj in registry.objects.items() if obj.type.value == 115)
    out["m_Scripts"] = [pointer("Library/unity default resources", pid) for pid in sdk_ids] + [
        pointer("globalgamemanagers.assets", pid) for pid in registry_ids
    ]
    hashes = {}
    for asset, ids in ((default, sdk_ids), (registry, registry_ids)):
        for pid in ids:
            row = U.S._script_record(asset.objects[pid].get_raw_data())
            asm, namespace, cls = row["identity"]
            key = U.S.md4((cls + namespace + asm).encode())
            U.require(key not in hashes, "duplicate emitted MonoScript identity")
            hashes[key] = row["properties"]
    out["m_ScriptHashes"] = [(h128(key), h128(value)) for key, value in sorted(hashes.items(), key=lambda row: struct.unpack("<QQ", row[0]))]
    return out


def graphics(fields, settings, files, shader_lookup, sdk_asset, sdk_selection, pointer, hashes, binary, shader_profile):
    shader_names = {pid: G.native_fields(obj, U)["m_ParsedForm"]["m_Name"] for pid, obj in sdk_asset.objects.items() if obj.type.value == 48}

    def shader(pid):
        name = shader_names[pid]
        rows = shader_lookup.get(name, [])
        U.require(len(rows) <= 1, "ambiguous native graphics Shader")
        return pointer(*rows[0]) if rows else pointer("", 0)

    for name, value in settings.items():
        if name in fields and isinstance(value, dict) and "m_Shader" in value:
            fields[name] = dict(m_Mode=value["m_Mode"], m_Shader=shader(value["m_Shader"]["fileID"]))
    ids = [row["fileID"] for row in settings["m_AlwaysIncludedShaders"]] + [row["id"] for row in sdk_selection["hidden"]]
    U.require(len(ids) == len(set(ids)), "duplicate internal graphics Shader")
    fields["m_AlwaysIncludedShaders"] = [shader(pid) for pid in ids]
    U.require(all(p["m_PathID"] for p in fields["m_AlwaysIncludedShaders"]), "included graphics Shader has no producer")
    material = G.native_fields(sdk_asset.objects[settings["m_SpritesDefaultMaterial"]["fileID"]], U)
    matches = [
        pid
        for pid, obj in files.asset("globalgamemanagers.assets").objects.items()
        if obj.type.value == 21 and files.fields("globalgamemanagers.assets", pid)[0]["m_Name"] == material["m_Name"]
    ]
    U.require(len(matches) == 1, "generated native Sprite material is ambiguous")
    fields["m_SpritesDefaultMaterial"] = pointer("globalgamemanagers.assets", matches[0])
    tiers = {}
    # Existing capability owner derives each tier from the actual supplied SDK.
    image = binary.read_bytes()
    for index, quality in enumerate((0, 1, 1), 1):
        selected = copy.deepcopy(shader_profile["settings"])
        selected["tier0"]["standardShaderQuality"] = quality
        word = hashes.platform_caps(image, selected)
        tiers["defines_Tier" + str(index)] = [word & 0xFFFFFFFF, word >> 32]
    fields["m_ShaderDefinesPerShaderCompiler"] = [dict(shaderPlatform=18, **tiers)]
    return fields


def produce(profile_path, profile_sha256, pc, sdk, builtin_extra, sdk_binary, shader_production, startup_receipt, player, output):
    """Parent-owned new player tree plus explicit source Shader/startup phases."""
    started = time.monotonic()
    output = Path(output)
    audit_root = output.parent.parent.parent.parent
    audit = audit_root / "managers-source"
    U.require(output.is_dir() and not (output / "globalgamemanagers").exists(), "manager parent output must be new")
    audit.mkdir(exist_ok=False)
    with closing(Sources(pc)) as store:
        selected = store.json(Path(profile_path), dict(sha256=profile_sha256))
        U.require(selected["schema"] == "owner-source-managers-v1" and selected["input_id"] == player["input_id"], "unsupported manager profile")
        public = {name: store.public(row) for name, row in selected["public_inputs"].items()}
        for name in ("player_managers.py", "manager_graph.py", "manager_settings.py", "manager_sdk.py"):
            store.pin(HERE / name)
        from UnityPy.enums import ClassIDType

        source_asset = store.asset(selected["source"])
        originals = {ClassIDType(obj.type.value).name: obj for obj in source_asset.objects.values()}
        U.require(len(originals) == len(source_asset.objects), "duplicate native manager type")
        shader_profile = store.json(public["shaders"])
        store.pin(sdk_binary, shader_profile["sdk"]["MacOS/Unity"])
        store.pin(builtin_extra, shader_profile["sdk"]["Resources/unity_builtin_extra"])
        shader_root = Path(shader_production[0])
        receipt = store.json(shader_root / "result.json", dict(sha256=shader_production[1]))
        U.require(
            receipt.get("success") is True and receipt["input_id"] == player["input_id"] and receipt["profile_sha256"] == U.P.sha(public["shaders"]),
            "complete source Shader phase required",
        )
        wanted = {row["file"] for row in shader_profile["shaders"]} | {"Resources/unity_builtin_extra"}
        U.require(set(receipt["files"]) == {"apk/assets/bin/Data/" + name for name in wanted}, "source Shader file cohort differs")
        files = G.Files(U, store, player, output, shader_root, receipt, sdk, audit_root)
        sdk_asset = store.asset_file(builtin_extra, "sdk-manager-builtin")
        sdk_names = {G.native_fields(obj, U)["m_ParsedForm"]["m_Name"] for obj in sdk_asset.objects.values() if obj.type.value == 48}
        lookup = {}
        for file in sorted(wanted | {"sharedassets0.assets", "Library/unity default resources"}):
            for pid, name in files.shader_records(file):
                lookup.setdefault(name, []).append((file, pid))
        U.require(all(len(rows) == 1 for rows in lookup.values()), "ambiguous produced Shader name")
        old_mapper = store.native_fields(originals["ScriptMapper"])
        names = {name for ptr, name in old_mapper["m_Shaders"]["m_ObjectToName"] if not ptr["m_PathID"] or name in sdk_names} | lookup.keys()
        ui = {}
        for phase in ("ui", "hud"):
            phase_result = store.json(audit_root / (phase + "-source/result.json"))
            ui.update({name.lower(): row for name, row in phase_result["resources"].items()})
        package_spec = shader_profile["tmp_mobile"]["package"]
        package = Path(sdk_binary).parent.parent / "Resources/PackageManager/Editor" / (package_spec["name"] + "-" + package_spec["version"] + ".tgz")
        store.pin(package, dict(sha256=package_spec["sha256"]))
        resource_roots = G.roots(
            store,
            player,
            shader_profile,
            public["hud_builder"].read_text(),
            store.json(public["copies"]),
            store.json(public["additions"]),
            store.json(public["contexts"]),
            package,
            public["bridge"].read_text(),
            ui,
        )
        graph, reachable = G.closure(resource_roots, files.fields)
        external = sorted(
            {file for file, _ in reachable}
            | {file for rows in lookup.values() for file, _ in rows}
            | {"globalgamemanagers.assets", "Library/unity default resources"}
        )

        def pointer(file, pid):
            return dict(m_FileID=external.index(file) + 1 if pid else 0, m_PathID=pid)

        inputs = dict(project=store.json(public["project_recipe"]))
        fields, settings, hashes = SET.produce(U, store, inputs, originals)
        fields["ResourceManager"] = dict(
            m_Container=[(name, pointer(row["file"], row["id"])) for name, row in sorted(resource_roots.items())],
            m_DependentAssets=[dict(m_Object=pointer(*key), m_Dependencies=[pointer(*p) for p in edges]) for key, edges in sorted(graph.items())],
        )
        fields["MonoManager"] = scripts(files, originals, pointer)
        mapper = old_mapper
        mapper["m_Shaders"]["m_ObjectToName"] = sorted(
            [(pointer(*lookup[name][0]) if name in lookup else pointer("", 0), name) for name in names],
            key=lambda row: (row[0]["m_FileID"], row[0]["m_PathID"], row[1]),
        )
        mapper["m_PreloadShaders"] = selected["policy"]["preload_shaders"]
        fields["ScriptMapper"] = mapper
        native = U.module("_manager_registry", ROOT / "scripts/lab/phone_registry.py")
        expansion = SDK.android_graphics(Path(sdk_binary), native)
        fields["GraphicsSettings"] = graphics(
            fields["GraphicsSettings"], settings["GraphicsSettings"], files, lookup, sdk_asset, expansion, pointer, hashes, Path(sdk_binary), shader_profile
        )
        startup = U.module("_manager_startup", HERE / "startup_metadata.py")
        startup.verify(startup_receipt[0], startup_receipt[1])
        startup_value = store.json(Path(startup_receipt[0]), dict(sha256=startup_receipt[1]))
        build_text = public["build"].read_text()
        scene = SET.single(build_text, r'scenes=new\[\]\{"([^"]+)"\}', "public scene selection differs", U.require)
        U.require("BuildOptions.Development" in build_text and "GraphicsDeviceType.Vulkan" in build_text, "public native build policy differs")
        build = store.native_fields(originals["BuildSettings"])
        paid = selected["policy"]["paid_capabilities"]
        U.require(
            set(paid) == {"hasPROVersion", "isNoWatermarkBuild", "hasAdvancedVersion"} and all(value is False for value in paid.values()),
            "public Personal profile cannot enable paid capabilities",
        )
        U.require(settings["ProjectSettings"]["m_BuildTargetBatching"] == [], "platform batching override requires qualification")
        build.update(paid)
        build.update(
            scenes=[scene],
            m_GraphicsAPIs=[21],
            isDebugBuild=True,
            enableDynamicBatching=selected["policy"]["dynamic_batching_default"],
            buildGUID={f"data[{i}]": int(startup_value["build_guid"][i * 8 : (i + 1) * 8][::-1], 16) for i in range(4)},
        )
        fields["BuildSettings"] = build
        U.require(set(fields) == set(originals), "native manager population differs")
        bodies, types, objects, offset = {}, [], [], 0
        for name, obj in sorted(originals.items(), key=lambda row: row[1].path_id):
            U.require(U.encode(store.native_fields(obj), obj.node) == obj.get_raw_data(), "original native transfer schema differs")
            body = U.encode(fields[name], obj.node)
            typ = obj.typ
            if typ not in types:
                types.append(typ)
            offset = (offset + 7) // 8 * 8
            objects.append(dict(path_id=obj.path_id, type_id=types.index(typ), offset=offset, bytes=len(body)))
            bodies[obj.path_id] = body
            offset += len(body)
        layout = dict(
            engine="2021.3.45f2",
            platform=13,
            trees=False,
            types=types,
            objects=objects,
            scripts=[],
            externals=[dict(empty="", guid=bytes(16), type=0, path=file) for file in external],
            ref_types=[],
            user="",
        )
        destination = output / "globalgamemanagers"
        with destination.open("xb") as stream:
            U.W.write_serialized(stream, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
        (audit / "fields.json").write_text(json.dumps(fields, indent=2) + "\n")
        (audit / "roots.json").write_text(json.dumps(resource_roots, indent=2) + "\n")
        store.recheck()
        result = dict(
            success=True,
            files={"globalgamemanagers": dict(bytes=destination.stat().st_size, sha256=U.P.sha(destination), source_role="source-native-managers")},
            objects=len(objects),
            resource_roots=len(resource_roots),
            dependent_assets=len(graph),
            shader_names=len(names),
            providers=store.pins,
            policy=selected["policy"],
            profile_sha256=profile_sha256,
            phone_qualified=False,
            runtime_qualified=False,
            historical_raw_exact=False,
            seconds=time.monotonic() - started,
        )
        (audit / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
