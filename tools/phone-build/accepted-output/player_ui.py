"""Produce source-owned player UI graphs from original files and public policy.

Current policy reconstructs the authored offline Menu, preserving original
assets and typed relationships with deterministic local IDs. No accepted player,
exported prefab, cached graph or historical ID map is read. Outputs are private.
"""

import argparse
from collections import Counter
from contextlib import ExitStack, closing
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import struct
import time
import uuid


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


HERE = Path(__file__).resolve().parent
P = module("_ui_player_data", HERE / "player_data.py")
T = module("_ui_texture", HERE / "texture_produce.py")
S, W = P.SCRIPT, P.W


def require(condition, message):
    if not condition:
        raise ValueError(message)


def node_from_tree(tree):
    from UnityPy.helpers.TypeTreeNode import TypeTreeNode
    from UnityPy.streams import EndianBinaryReader

    return TypeTreeNode.parse_blob(EndianBinaryReader(tree, endian="<"), 22)


def encode(fields, node):
    from UnityPy.helpers.TypeTreeHelper import write_typetree
    from UnityPy.streams import EndianBinaryWriter

    writer = EndianBinaryWriter(endian="<")
    write_typetree(fields, node, writer)
    return writer.bytes


def explicit_tree(tree):
    """Resolve source common-string offsets through the pinned parser vocabulary."""
    rows = node_from_tree(tree).to_dict_list()
    return S._tree(
        [
            dict(
                type=n["m_Type"],
                name=n["m_Name"],
                level=n["m_Level"],
                size=n["m_ByteSize"],
                version=n["m_Version"],
                flags=n["m_TypeFlags"],
                meta=n["m_MetaFlag"],
            )
            for n in rows
        ]
    )


class Object:
    def __init__(self, asset, row):
        self.asset, self.row, self.path_id = asset, row, row["path_id"]
        self.typ = asset.layout["types"][row["type_id"]]
        self.type = N(value=self.typ["class_id"])

    @property
    def node(self):
        tid = self.row["type_id"]
        if tid not in self.asset.nodes:
            tree = self.typ.get("tree") or self.asset.native_trees.get((self.typ["class_id"], self.typ["hash"]))
            self.asset.nodes[tid] = node_from_tree(tree) if tree else None
        return self.asset.nodes[tid]

    def get_raw_data(self):
        self.asset.stream.seek(self.asset.layout["data_offset"] + self.row["offset"])
        return W.B.exact(self.asset.stream, self.row["bytes"])

    def read_typetree(self):
        from UnityPy.helpers.TypeTreeHelper import read_typetree
        from UnityPy.streams import EndianBinaryReader

        require(self.node is not None, "original object has no transfer schema")
        raw = self.get_raw_data()
        return read_typetree(self.node, EndianBinaryReader(raw, endian="<"), byte_size=len(raw))


class Asset:
    def __init__(self, name, stream, native_trees):
        self.name, self.stream, self.nodes = name, stream, {}
        self.layout = W.read_serialized(stream)
        self.native_trees = native_trees
        for typ in self.layout["types"]:
            if typ["class_id"] != 114 and typ.get("tree"):
                native_trees.setdefault((typ["class_id"], typ["hash"]), typ["tree"])
        self.externals = self.layout["externals"]
        self.objects = {row["path_id"]: Object(self, row) for row in self.layout["objects"]}


class Sources:
    """Bounded member access, provider pinning and deterministic reader teardown."""

    def __init__(self, pc):
        self.pc = Path(pc).resolve(strict=True)
        self.stack, self.assets, self.bundles, self.pins = ExitStack(), {}, {}, {}
        self.native_trees = {}

    def close(self):
        self.assets.clear()
        self.bundles.clear()
        self.native_trees.clear()
        self.stack.close()

    def pin(self, path, expected=None):
        path = Path(path).resolve(strict=True)
        value = {"bytes": path.stat().st_size, "sha256": P.sha(path)}
        if expected:
            require(all(value[k] == v for k, v in expected.items() if k in value), "UI input hash/size differs")
        self.pins[str(path)] = value
        return value

    def json(self, path, expected=None):
        self.pin(path, expected)
        return json.loads(Path(path).read_text())

    def asset_file(self, path, key, expected=None, member=None):
        if key not in self.assets:
            self.pin(path, expected)
            if member:
                bundle = self.bundles.setdefault(str(path), W.B.Bundle(Path(path)))
                stream = bundle.member(member)
            else:
                stream = self.stack.enter_context(Path(path).open("rb"))
                stream.size = Path(path).stat().st_size
            self.assets[key] = Asset(key, stream, self.native_trees)
            self.assets[key].bundle = bundle if member else None
        return self.assets[key]

    def asset(self, selected):
        path = P.OBJECTS.M.safe_input(self.pc, selected["path"])
        key = selected.get("member", selected["path"])
        return self.asset_file(path, key, selected, selected.get("member"))

    def recheck(self):
        for path, value in list(self.pins.items()):
            self.pin(path, value)


def source_key(selected, pid):
    return selected.get("member", selected["path"]), pid


def reference_key(asset, ptr):
    file_id, pid = ptr["m_FileID"], ptr["m_PathID"]
    if not file_id:
        return asset.name, pid
    require(0 < file_id <= len(asset.externals), "original UI external index escapes its file")
    return asset.externals[file_id - 1]["path"].rsplit("/", 1)[-1], pid


def original_identities(asset):
    return {o.path_id: S._script_record(o.get_raw_data())["identity"] for o in asset.objects.values() if o.type.value == 115}


def identity(obj, scripts):
    if obj.type.value != 114:
        return obj.node.m_Type
    file_id, pid = struct.unpack_from("<iq", obj.get_raw_data(), 16)
    require(file_id > 0 and pid in scripts, "unresolved original UI MonoScript")
    assembly, namespace, cls = scripts[pid]
    return assembly.removesuffix(".dll") + ":" + namespace + "." + cls


def hierarchy(asset, root):
    rows, visiting = [], set()

    def walk(pid, path):
        require(pid not in visiting, "cyclic or multiply owned UI hierarchy")
        visiting.add(pid)
        game = asset.objects[pid]
        require(game.type.value == 1, "UI hierarchy root is not a GameObject")
        fields = game.read_typetree()
        components = [asset.objects[p["component"]["m_PathID"]] for p in fields["m_Component"]]
        transforms = [o for o in components if o.type.value in (4, 224)]
        require(len(transforms) == 1, "UI GameObject has ambiguous transform")
        rows.append(dict(path=path, id=pid, name=fields["m_Name"], components=[o.path_id for o in components]))
        names = Counter()
        for ptr in transforms[0].read_typetree()["m_Children"]:
            child = asset.objects[ptr["m_PathID"]].read_typetree()["m_GameObject"]["m_PathID"]
            name = asset.objects[child].read_typetree()["m_Name"]
            count = names[name]
            names[name] += 1
            walk(child, path + "/" + name + ("[" + str(count) + "]" if count else ""))

    walk(root, "$")
    return rows


def map_pointers(value, transform):
    if isinstance(value, dict):
        if set(value) == {"m_FileID", "m_PathID"}:
            value.update(transform(value))
        else:
            for child in value.values():
                map_pointers(child, transform)
    elif isinstance(value, list):
        for child in value:
            map_pointers(child, transform)


def graph_records(asset, scripts, selected, labels):
    graph = hierarchy(asset, selected["root_path_id"])
    text_ids = {cid for row in graph for cid in row["components"] if identity(asset.objects[cid], scripts) == selected["text_identity"]}
    kept, removed = [], set()
    for row in graph:
        kept.append((row, row["id"]))
        for cid in row["components"]:
            obj = asset.objects[cid]
            ident = identity(obj, scripts)
            if (obj.type.value == 114 and not (ident.startswith("UnityEngine.UI:UnityEngine.UI.") or cid in text_ids)) or obj.type.value in (54, 95):
                removed.add(cid)
            else:
                kept.append((row, cid))
    kept.sort(key=lambda pair: (asset.objects[pair[1]].type.value == 114, asset.objects[pair[1]].type.value, pair[1]))
    allocation = {sid: i + 1 for i, (_, sid) in enumerate(kept)}
    extras = [dict(path="$", identity="Assembly-CSharp:.RecoveredHudPresentation", id=len(kept) + 1)]
    actions = []
    for policy in selected["buttons"]:
        matches = [row for row in graph if row["name"] == policy["name"]]
        require(len(matches) == 1, "original Menu action is absent or ambiguous")
        extra = dict(path=matches[0]["path"], identity="UnityEngine.UI:UnityEngine.UI.Button", id=len(kept) + len(extras) + 1)
        extras.append(extra)
        actions.append((matches[0], extra, policy))
    baked = {}
    for row in graph:
        for cid in row["components"]:
            if identity(asset.objects[cid], scripts) == "RoR2:RoR2.UI.LanguageTextMeshController":
                token = asset.objects[cid].read_typetree()["_token"]
                choices = [cid for cid in row["components"] if cid in text_ids]
                if not choices:
                    choices = [cid for child in graph if child["path"].startswith(row["path"] + "/") for cid in child["components"] if cid in text_ids]
                if choices:
                    baked[choices[0]] = labels.get(token, token or "")
    for game, _, policy in actions:
        for row in graph:
            if row["path"].startswith(game["path"] + "/") and row["name"] == "ButtonText":
                choices = [cid for cid in row["components"] if cid in text_ids]
                require(len(choices) == 1, "Menu button label is ambiguous")
                baked[choices[0]] = labels[policy["token"]] + policy["suffix"]
    glyphs = {row["id"] for row in graph if any(cid in text_ids and "<sprite" in asset.objects[cid].read_typetree()["m_text"] for cid in row["components"])}
    buttons = {row["id"] for row in graph if any(identity(asset.objects[cid], scripts) == "RoR2:RoR2.UI.HGButton" for cid in row["components"])}

    def remap(ptr):
        if ptr["m_FileID"] == 0:
            pid = ptr["m_PathID"]
            return dict(m_FileID=0, m_PathID=allocation[pid] if pid in allocation else 0 if pid in removed else pid)
        return ptr

    records = []
    for game, sid in kept:
        obj = asset.objects[sid]
        fields = copy.deepcopy(obj.read_typetree())
        if obj.type.value == 1:
            fields["m_Component"] = [v for v in fields["m_Component"] if v["component"]["m_PathID"] not in removed]
        map_pointers(fields, remap)
        if obj.type.value == 1:
            if game["path"] == "$":
                fields.update(m_Name=selected["root_name"], m_IsActive=False)
            elif game["name"] in selected["hidden_names"] or sid in glyphs or (sid in buttons and game["name"] not in {p["name"] for p in selected["buttons"]}):
                fields["m_IsActive"] = False
            elif game["name"] in selected["enabled_names"]:
                fields["m_IsActive"] = True
            for extra in extras:
                if extra["path"] == game["path"]:
                    fields["m_Component"].append(dict(component=dict(m_FileID=0, m_PathID=extra["id"])))
        elif obj.type.value == 225:
            fields["m_Alpha"] = 1.0
        elif obj.type.value == 223 and game["path"] == "$":
            fields.update(m_RenderMode=0, m_Camera=dict(m_FileID=0, m_PathID=0), m_SortingOrder=50)
        elif sid in text_ids:
            fields.update(useLanguageDefaultFont=False, m_RaycastTarget=False)
            if sid in baked:
                fields["m_text"] = baked[sid]
        records.append(dict(source_id=sid, path=game["path"], identity=identity(obj, scripts), id=allocation[sid], fields=fields, node=obj.node, typ=obj.typ))
    return graph, records, extras


def zero(node):
    if node.m_Type == "string":
        return ""
    if node.m_Children and node.m_Children[0].m_Type == "Array":
        return []
    if node.m_Children:
        return {child.m_Name: zero(child) for child in node.m_Children}
    return 0.0 if node.m_Type in {"float", "double"} else 0


def sdk_defaults(store, directory, pins):
    """Read constructor declarations from the separately supplied exact SDK."""
    texts = {}
    for name, expected in pins.items():
        path = Path(directory) / name
        store.pin(path, expected)
        text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        texts[name] = re.sub(r"//[^\n]*", "", text)

    def one(pattern, text):
        values = re.findall(pattern, text)
        require(len(values) == 1, "unsupported or ambiguous SDK UI declaration")
        return values[0]

    navigation = texts["Navigation.cs"]
    selectable = texts["Selectable.cs"]
    animation = texts["AnimationTriggers.cs"]
    one(r"m_OnClick\s*=\s*(new ButtonClickedEvent\(\))", texts["Button.cs"])
    mode = one(r"defaultNav\.m_Mode\s*=\s*Mode\.(\w+)", navigation)
    mode_value = int(one(r"\b" + mode + r"\s*=\s*(\d+)", navigation))
    transition = one(r"private Transition m_Transition\s*=\s*Transition\.(\w+)", selectable)
    enum_text = one(r"public enum Transition\s*\{([^}]+)\}", selectable)
    transition_value = [part.strip() for part in enum_text.split(",")].index(transition)
    interactable = one(r"private bool m_Interactable\s*=\s*(true|false)", selectable) == "true"
    values = dict(re.findall(r'private const string (\w+)\s*=\s*"([^"\n]*)"', animation))
    animations = {field: values[value] for field, value in re.findall(r"private string (m_\w+)\s*=\s*(\w+)", animation)}
    return dict(mode=mode_value, transition=transition_value, interactable=interactable, animations=animations)


def component_records(store, ui, scripts, graph, records, extras, native, managed, defaults):
    templates = {}
    for typ in ui.layout["types"]:
        for kind in ("Vector2f", "Vector3f", "Vector4f", "ColorRGBA", "Rectf", "RectOffset"):
            choices = S._native_subtrees(explicit_tree(typ["tree"]), kind)
            if choices:
                templates.setdefault(kind, choices[0])
    mono = next(o for o in ui.objects.values() if o.type.value == 114)
    base = []
    for node in S.tree_nodes(explicit_tree(mono.typ["tree"])):
        if node["level"] == 1 and node["name"] not in {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}:
            break
        base.append(node)
    require([n["name"] for n in base if n["level"] == 1] == ["m_GameObject", "m_Enabled", "m_Script", "m_Name"], "runtime MonoBehaviour base differs")
    receipt = store.json(Path(managed) / "result.json")
    require(receipt.get("success") is True and receipt.get("phase") == "managed-produced", "source-produced managed assemblies required")
    providers = store.json(Path(managed) / "providers.json")
    result = []
    with closing(S._RegistryTypes(store.pc / "Risk of Rain 2_Data/Managed", providers, store.pin, native, templates)) as clr:
        for extra in extras:
            assembly, full = extra["identity"].split(":", 1)
            namespace, cls = full.rsplit(".", 1)
            assembly += ".dll"
            tree = clr.script_schema((assembly, namespace, cls), {})
            require(tree is not None, "source Menu addition has no concrete CLR schema")
            custom = [n for name, nodes in S._fields(S.tree_nodes(tree)).items() if name not in {n["name"] for n in clr.base if n["level"] == 1} for n in nodes]
            runtime_tree = S._tree(base + custom)
            node = node_from_tree(runtime_tree)
            fields = zero(node)
            game = next(g for g in graph if g["path"] == extra["path"])
            owner = next(r["id"] for r in records if r["source_id"] == game["id"])
            fields.update(m_GameObject=dict(m_FileID=0, m_PathID=owner), m_Enabled=1, m_Script=dict(m_FileID=0, m_PathID=0))
            if cls == "Button":
                originals = [
                    ui.objects[c] for c in game["components"] if ui.objects[c].type.value == 114 and identity(ui.objects[c], scripts) == "RoR2:RoR2.UI.HGButton"
                ]
                require(len(originals) == 1, "original action button is ambiguous")
                source = originals[0].read_typetree()
                fields["m_Navigation"]["m_Mode"] = defaults["mode"]
                fields["m_Transition"] = defaults["transition"]
                fields["m_Interactable"] = defaults["interactable"]
                fields["m_AnimationTriggers"].update(defaults["animations"])
                fields["m_Colors"] = copy.deepcopy(source["m_Colors"])
                fields["m_TargetGraphic"] = copy.deepcopy(source["m_TargetGraphic"])
                require(fields["m_TargetGraphic"]["m_FileID"] == 0, "action graphic must belong to the source graph")
                fields["m_TargetGraphic"]["m_PathID"] = next(r["id"] for r in records if r["source_id"] == fields["m_TargetGraphic"]["m_PathID"])
            else:
                require(cls == "RecoveredHudPresentation", "unsupported authored Menu component")
                fields["isMenu"] = 1
                fields["startButton"] = dict(m_FileID=0, m_PathID=extras[1]["id"])
                fields["quitButton"] = dict(m_FileID=0, m_PathID=extras[2]["id"])
            result.append(dict(extra, fields=fields, node=node, typ=dict(class_id=114, stripped=0, script_type=-1, hash=bytes(16), tree=runtime_tree)))
    return result


def write_object(output, name, obj, fields, externals, *, reuse_existing=False):
    require(re.fullmatch("[a-f0-9]{32}", name) is not None, "unsafe UI player filename")
    body = encode(fields, obj.node)
    typ = {**obj.typ, "script_type": -1}
    layout = dict(
        engine="2021.3.45f2",
        platform=13,
        trees=False,
        types=[typ],
        objects=[dict(path_id=1, type_id=0, offset=0, bytes=len(body))],
        scripts=[],
        externals=[dict(empty="", guid=bytes(16), type=0, path=p) for p in externals],
        ref_types=[],
        user="",
    )
    if reuse_existing:
        stream = io.BytesIO()
        W.write_serialized(stream, layout, lambda _: io.BytesIO(body))
        data = stream.getvalue()
        path = output / name
        try:
            with path.open("xb") as destination:
                destination.write(data)
        except FileExistsError:
            require(not path.is_symlink() and path.is_file(), "redirected UI media output")
            require(path.stat().st_size == len(data) and P.sha(path) == hashlib.sha256(data).hexdigest(), "shared UI media bytes differ")
    else:
        with (output / name).open("xb") as stream:
            W.write_serialized(stream, layout, lambda _: io.BytesIO(body))


def sprite_media(store, asset, obj, output):
    """Keep original Sprite identity/geometry and decode its complete texture."""
    require(obj.type.value == 213, "unresolved UI provider is not an original Sprite")
    sprite = obj.read_typetree()
    require(not sprite["m_SpriteAtlas"]["m_PathID"] and not sprite["m_RD"]["alphaTexture"]["m_PathID"], "UI media needs an atlas/alpha owner")
    member, pid = reference_key(asset, sprite["m_RD"]["texture"])
    texture_asset = store.assets[member]
    texture_obj = texture_asset.objects[pid]
    texture = texture_obj.read_typetree()
    require(texture_obj.type.value == 28 and texture["m_ImageCount"] == 1 and texture["m_TextureDimension"] == 2, "unsupported UI texture shape")
    width, height, fmt = texture["m_Width"], texture["m_Height"], texture["m_TextureFormat"]
    require(fmt in (3, 4, 9, 10, 12), "unqualified UI texture format")
    pixels = texture["image data"]
    stream = texture["m_StreamData"]
    if stream["size"]:
        require(not pixels and texture_asset.bundle is not None, "ambiguous original UI pixel backing")
        resource = texture_asset.bundle.member(stream["path"].rsplit("/", 1)[1])
        resource.seek(stream["offset"])
        pixels = W.B.exact(resource, stream["size"])
    require(len(pixels) == texture["m_CompleteImageSize"], "original UI mip extent differs")
    mips, cursor = [], 0
    for _ in range(texture["m_MipCount"]):
        size = ((width + 3) // 4) * ((height + 3) // 4) * (8 if fmt == 10 else 16) if fmt in (10, 12) else width * height * {3: 3, 4: 4, 9: 2}[fmt]
        mips.append(T.rgba_source(pixels[cursor : cursor + size], width, height, fmt))
        cursor += size
        width, height = max(1, width // 2), max(1, height // 2)
    require(cursor == len(pixels), "UI mip chain has unowned trailing bytes")
    texture["image data"] = b"".join(mips)
    texture["m_StreamData"] = dict(offset=0, size=0, path="")
    texture["m_TextureFormat"] = 4
    texture["m_CompleteImageSize"] = len(texture["image data"])
    texture_name = uuid.uuid5(uuid.NAMESPACE_URL, "ror2lab/source-player/" + member + "/" + str(pid)).hex
    sprite_name = uuid.uuid5(uuid.NAMESPACE_URL, "ror2lab/source-player/" + asset.name + "/" + str(obj.path_id)).hex
    sprite["m_RD"]["texture"] = dict(m_FileID=1, m_PathID=1)
    write_object(output, texture_name, texture_obj, texture, [], reuse_existing=True)
    write_object(output, sprite_name, obj, sprite, [texture_name])
    return {(member, pid): (texture_name, 1, ""), (asset.name, obj.path_id): (sprite_name, 1, "")}


class Linker:
    def __init__(self, store, ui, player, root, selected, builtin_extra, output):
        self.store, self.ui, self.output = store, ui, output
        self.aliases, self.externals, self.generated = {}, ["globalgamemanagers.assets"], set()
        selections = [{"source": player["sprites"]["source"], **row} for row in player["sprites"]["files"]] + player.get("objects", []) + [player["font"]]
        self.by_file = {row["file"]: row for row in selections}
        for row in selections:
            for obj in row["objects"]:
                self.aliases.setdefault(source_key(row["source"], obj["source_path_id"]), []).append((row["file"], obj["path_id"], obj.get("rename", "")))
        wanted = {row["profile_sha256"]: row for row in player["textures"]}
        seen = set()
        for item in selected["texture_profiles"]:
            path = P.OBJECTS.M.safe_input(root, item["path"])
            recipe = store.json(path, item)
            digest = P.sha(path)
            require(digest in wanted, "UI texture recipe is outside the player profile")
            seen.add(digest)
            mapping = {(row["bundle"], row["member"], row["path_id"]): row["file"] for row in wanted[digest]["files"]}
            for bundle in recipe["bundles"]:
                for member in bundle["members"]:
                    for texture in member["textures"]:
                        for target in texture["outputs"]:
                            key = target["bundle"], target["member"], target["path_id"]
                            if key in mapping:
                                self.aliases.setdefault((member["name"], texture["path_id"]), []).append((mapping[key], 1, ""))
        require(seen == set(wanted), "UI texture source recipe cohort is incomplete")
        candidates = []
        for row in player["sprites"]["files"]:
            source = row.get("source", player["sprites"]["source"])
            asset = store.asset(source)
            for obj in row["objects"]:
                candidates.append((asset.objects[obj["source_path_id"]].read_typetree(), row["file"], obj["path_id"]))
        builtin = player["builtin_ui"]
        store.pin(builtin_extra, builtin["source"])
        # The SDK's editor resource omits transfer trees and has editor-only
        # fields. Reuse the existing bounded runtime projection, then decode
        # against an original native schema with the identical class/hash.
        runtime = output / builtin["file"]
        if not runtime.exists():
            P.builtin_ui(store.pc, player, builtin_extra, runtime)
            self.generated.add(builtin["file"])
        sdk = store.asset_file(runtime, "sdk-builtin-ui-runtime", player["outputs"][builtin["file"]])
        for obj in ui.objects.values():
            if obj.type.value != 213 or (ui.name, obj.path_id) in self.aliases:
                continue
            fields = obj.read_typetree()
            for other, file, pid in candidates:
                if same_sprite(fields, other):
                    self.aliases.setdefault((ui.name, obj.path_id), []).append((file, pid, ""))
            for index, pid in enumerate(builtin["sprites"], len(builtin["textures"]) + 1):
                other = sdk.objects[index].read_typetree()
                if fields["m_Name"] == other["m_Name"]:
                    require(all(fields[key] == other[key] for key in ("m_Rect", "m_Pivot", "m_Border", "m_PixelsToUnits")), "SDK Sprite geometry differs")
                    self.aliases.setdefault((ui.name, obj.path_id), []).append((builtin["file"], index, ""))
        for source in selected["extra_sources"]:
            store.asset(source)

    def choose(self, key, prefix=None):
        if key not in self.aliases:
            require(key[0] in self.store.assets, "original UI dependency has no declared source")
            asset = self.store.assets[key[0]]
            require(key[1] in asset.objects, "original UI dependency does not exist")
            produced = sprite_media(self.store, asset, asset.objects[key[1]], self.output)
            for source, target in produced.items():
                self.aliases.setdefault(source, []).append(target)
                self.generated.add(target[0])
        choices = self.aliases[key]
        if prefix:
            choices = [row for row in choices if row[2].startswith(prefix)]
        else:
            plain = [row for row in choices if not row[2]]
            choices = plain or choices
        unique = {(row[0], row[1]) for row in choices}
        require(len(unique) == 1, "ambiguous UI destination provider")
        return next(iter(unique))

    def pointer(self, file, pid):
        if file not in self.externals:
            self.externals.append(file)
        return dict(m_FileID=self.externals.index(file) + 1, m_PathID=pid)

    def font_material(self, fields):
        key = reference_key(self.ui, fields["m_fontAsset"])
        file, _ = self.choose(key)
        selected = self.by_file[file]
        asset = self.store.asset(selected["source"])
        font = asset.objects[key[1]]
        material = font.read_typetree()["material"]
        require(reference_key(asset, material) == reference_key(self.ui, fields["m_sharedMaterial"]), "non-default font material needs its source policy")
        raw = font.get_raw_data()
        encoded = struct.pack("<iq", material["m_FileID"], material["m_PathID"])
        require(raw.count(encoded) == 1, "original font default-material field is ambiguous")
        links = [row for row in selected["objects"][0]["references"] if row["offset"] == raw.index(encoded)]
        require(len(links) == 1 and links[0]["from"] == [material["m_FileID"], material["m_PathID"]], "produced font default-material relationship differs")
        file_id, pid = links[0]["to"]
        require(file_id > 0, "produced font material must have its own provider")
        canonical = self.by_file[selected["externals"][file_id - 1]]
        obj = next(o for o in canonical["objects"] if o["path_id"] == pid)
        return self.choose(source_key(canonical["source"], obj["source_path_id"]), "FontMaterial")

    def fields(self, row, ids, script_ids):
        fields = copy.deepcopy(row["fields"])
        scripted = row["typ"]["class_id"] == 114
        material = self.font_material(fields) if scripted and "m_fontAsset" in fields else None
        native_material = None
        if "m_Material" in fields and fields["m_Material"]["m_PathID"]:
            native_material = self.choose(reference_key(self.ui, fields["m_Material"]), "NativeUiMaterial")
            fields["m_Material"] = dict(m_FileID=0, m_PathID=0)
        if scripted:
            fields["m_Script"] = dict(m_FileID=0, m_PathID=0)
        if material:
            fields["m_sharedMaterial"] = dict(m_FileID=0, m_PathID=0)

        def remap(ptr):
            if not ptr["m_PathID"]:
                return dict(m_FileID=0, m_PathID=0)
            if not ptr["m_FileID"] and ptr["m_PathID"] in ids:
                return ptr
            return self.pointer(*self.choose(reference_key(self.ui, ptr)))

        map_pointers(fields, remap)
        if material:
            fields["m_sharedMaterial"] = self.pointer(*material)
        if native_material:
            fields["m_Material"] = self.pointer(*native_material)
        if scripted:
            assembly, full = row["identity"].split(":", 1)
            namespace, cls = full.rsplit(".", 1)
            fields["m_Script"] = self.pointer("globalgamemanagers.assets", script_ids[assembly + ".dll", namespace, cls])
        return fields


def same_sprite(left, right):
    keys = ("m_Name", "m_RenderDataKey", "m_Rect", "m_Offset", "m_Border", "m_PixelsToUnits", "m_Pivot")
    return all(left[key] == right[key] for key in keys)


def produce(profile_path, profile_sha256, pc, player, builtin_extra, editor_resources, ugui_source, managed, registry, output):
    """Generate Menu and missing media inside an existing source player target tree.

    The parent player-data owner supplies its freshly derived registry value;
    no separate registry packet, private metadata cache or ID map is admitted.
    """
    started = time.monotonic()
    output, profile_path = Path(output), Path(profile_path).resolve(strict=True)
    require(output.is_dir(), "UI parent must create its new player-data target tree")
    with closing(Sources(pc)) as store:
        selected = store.json(profile_path, {"sha256": profile_sha256})
        require(selected["schema"] == "owner-source-menu-v1" and selected["input_id"] == player["input_id"], "unsupported source UI profile")
        ui = store.asset(selected["source"])
        scripts = original_identities(store.asset(selected["scripts_source"]))
        labels_text, language_pins = P.language_strings(store.pc, player["text_assets"]["language"])
        labels = {row["key"]: row["value"] for row in json.loads(labels_text)["entries"]}
        for path, pin in language_pins:
            store.pin(path, {"bytes": pin[0], "sha256": pin[1]})
        graph, records, extras = graph_records(ui, scripts, selected, labels)
        store.pin(editor_resources, player["script_properties_sdk"])
        native = P.script_sdk_schema(editor_resources, player["script_properties_sdk"])
        defaults = sdk_defaults(store, ugui_source, selected["sdk_ui_sources"])
        records += component_records(store, ui, scripts, graph, records, extras, native, managed, defaults)
        linker = Linker(store, ui, player, profile_path.parent, selected, builtin_extra, output)
        ids = {row["id"] for row in records}
        metadata, bodies, rows, scripts_table, manifest = [], {}, [], [], []
        audit = output.parent.parent.parent.parent / "ui-source"
        audit.mkdir(exist_ok=False)
        offset = 0
        for row in records:
            fields = linker.fields(row, ids, registry["script_ids"])
            typ = dict(row["typ"])
            if typ["class_id"] == 114:
                typ["tree"] = explicit_tree(typ["tree"])
                assembly, full = row["identity"].split(":", 1)
                namespace, cls = full.rsplit(".", 1)
                ident = assembly + ".dll", namespace, cls
                script_id = registry["script_ids"][ident]
                properties = S._script_record(registry["bodies"][script_id])["properties"]
                properties_from_schema = S.properties_hash(cls, namespace, ident[0], typ["tree"], native)
                require(properties == properties_from_schema, "UI body schema differs from source-produced script registry")
                script = (1, script_id)
                if script not in scripts_table:
                    scripts_table.append(script)
                typ.update(script_type=scripts_table.index(script), script_id=S.md4((cls + namespace + ident[0]).encode()), hash=properties)
            if typ not in metadata:
                metadata.append(typ)
                (audit / ("schema-" + str(len(metadata) - 1) + ".tree")).write_bytes(typ["tree"])
            type_id = metadata.index(typ)
            body = encode(fields, row["node"])
            offset = (offset + 7) // 8 * 8
            rows.append(dict(path_id=row["id"], type_id=type_id, offset=offset, bytes=len(body)))
            bodies[row["id"]] = body
            manifest.append(
                dict(
                    id=row["id"],
                    path=row["path"],
                    identity=row["identity"],
                    type_id=type_id,
                    fields=fields,
                    bytes=len(body),
                    sha256=hashlib.sha256(body).hexdigest(),
                )
            )
            offset += len(body)
        layout = dict(
            engine="2021.3.45f2",
            platform=13,
            trees=False,
            types=metadata,
            objects=rows,
            scripts=scripts_table,
            externals=[dict(empty="", guid=bytes(16), type=0, path=path) for path in linker.externals],
            ref_types=[],
            user="",
        )
        name = selected["file"]
        require(re.fullmatch("[a-f0-9]{32}", name) is not None, "unsafe UI output filename")
        with (output / name).open("xb") as stream:
            W.write_serialized(stream, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
        files = {
            file: dict(
                bytes=(output / file).stat().st_size, sha256=P.sha(output / file), source_role="pc-sdk-and-authored-ui", source=selected["source"]["path"]
            )
            for file in linker.generated | {name}
        }
        root = next(row["id"] for row in records if row["path"] == "$" and row["identity"] == "GameObject")
        (audit / "objects.json").write_text(json.dumps(manifest, indent=2) + "\n")
        store.recheck()
        result = dict(
            files=files,
            objects=len(records),
            resources={"RecoveredUI/Menu": dict(file=name, path_id=root)},
            profile_sha256=profile_sha256,
            provider_pins=store.pins,
            external_files=linker.externals,
            phone_qualified=False,
            runtime_qualified=False,
            historical_raw_exact=False,
            seconds=time.monotonic() - started,
        )
        (audit / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
