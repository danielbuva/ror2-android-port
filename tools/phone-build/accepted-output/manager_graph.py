"""Resource roots and direct dependency closure from current produced player files."""

from collections import deque
import io
import hashlib
from pathlib import Path, PurePosixPath
import re
import tarfile


def member(archive, name):
    rows = [row for row in archive.getmembers() if row.name == name]
    if len(rows) != 1 or not rows[0].isfile() or rows[0].size > 32 * 1024**2:
        raise ValueError("invalid SDK package declaration")
    return archive.extractfile(rows[0]).read()


def resource_key(path):
    parts = PurePosixPath(path).parts
    if "Resources" not in parts:
        return None
    return str(PurePosixPath(*parts[parts.index("Resources") + 1 :]).with_suffix("")).lower()


def roots(store, player, shaders, source_text, copies, additions, contexts, package, reflection_text, ui_resources):
    out = {}

    def add(name, file="", pid=0):
        key = name.lower()
        if key in out:
            raise ValueError("duplicate source resource root: " + key)
        out[key] = dict(file=file, id=pid)

    prefix = re.findall(r'const string Output = "Assets/LabLoadingScene/Resources/([^"]+)"', source_text)
    store.U.require(len(prefix) == 1, "public HUD resource prefix differs")
    prefix = prefix[0]
    for row in shaders["shaders"]:
        key = resource_key(row["filename"])
        if key:
            add(key, row["file"], 1)
    for group in player["objects"]:
        asset = store.asset(group["source"])
        for row in group["objects"]:
            if row.get("rename"):
                add(prefix + "/" + row["rename"], group["file"], row["path_id"])
            obj = asset.objects[row["source_path_id"]]
            if obj.type.value == 114 and obj.read_typetree().get("m_Name") == "TMP Settings":
                add("TMP Settings", group["file"], row["path_id"])
    for row in player["text_assets"]["files"]:
        if row.get("name"):
            add((prefix + "/" if row.get("language") else "") + row["name"], row["file"], 1)
    saved = re.findall(r'Save\((?:hud|menu), "([^"]+)"\)', source_text)
    for name in saved:
        key = (prefix + "/" + name).lower()
        store.U.require(key in ui_resources, "source UI resource phase absent")
        add(key, ui_resources[key]["file"], ui_resources[key]["path_id"])
    add("WholeStageContexts", contexts["file"], 1)
    for group in player["sprites"]["files"]:
        if group.get("full_rectangle"):
            asset = store.asset(group.get("source", player["sprites"]["source"]))
            row = group["objects"][0]
            name = asset.objects[row["source_path_id"]].read_typetree()["m_Name"]
            add(prefix + "/Owned full-rectangle " + name, group["file"], row["path_id"])
    wanted = set()
    paths = [row["output"] for row in additions["assets"]] + [row[1] for row in copies["copies"]]
    for path in paths:
        key = resource_key(path)
        if key and path.endswith(".png") and key not in out:
            wanted.add(key)
    for profile in player["textures"]:
        recipe = store.recipe_by_hash(profile["profile_sha256"])
        mapping = {(row["bundle"], row["member"], row["path_id"]): row["file"] for row in profile["files"]}
        for bundle in recipe["bundles"]:
            for asset in bundle["members"]:
                for texture in asset["textures"]:
                    for row in texture["outputs"]:
                        key = row.get("name", "").lower()
                        identity = row["bundle"], row["member"], row["path_id"]
                        if key in wanted and identity in mapping:
                            add(key, mapping[identity], 1)
                            wanted.remove(key)
    store.U.require(not wanted, "original texture resource has no produced provider")
    raw = package.read_bytes()
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        resource = member(archive, shaders["tmp_mobile"]["package"]["resource"])
    store.U.require(hashlib.sha256(resource).hexdigest() == shaders["tmp_mobile"]["package"]["resource_sha256"], "TMP resource package differs")
    with tarfile.open(fileobj=io.BytesIO(resource)) as archive:
        for row in archive.getmembers():
            if row.name.endswith("/pathname"):
                path = member(archive, row.name).decode().strip()
                if PurePosixPath(path).parent.as_posix() == "Assets/TextMesh Pro/Shaders" and path.endswith(".cginc"):
                    add(prefix + "/FontShader/" + PurePosixPath(path).stem)
    for path in re.findall(r'stage / "Resources/([^\"]+\.cginc)"', reflection_text):
        add(str(PurePosixPath(path).with_suffix("")))
    return out


def references(value):
    if isinstance(value, dict):
        if set(value) == {"m_FileID", "m_PathID"}:
            yield value
        else:
            for child in value.values():
                yield from references(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from references(child)


def closure(roots, load):
    """Walk every nonzero source pointer, retaining cycles and script edges."""
    queue = deque((row["file"], row["id"]) for row in roots.values() if row["id"])
    seen, graph = set(), {}
    while queue:
        identity = queue.popleft()
        if identity in seen:
            continue
        seen.add(identity)
        fields, externals = load(*identity)  # Missing providers/objects refuse here.
        edges = set()
        for pointer in references(fields):
            file_id, pid = pointer["m_FileID"], pointer["m_PathID"]
            if not pid:
                continue
            if not 0 <= file_id <= len(externals):
                raise ValueError("invalid produced resource file ID")
            file = identity[0] if not file_id else externals[file_id - 1]
            edges.add((file, pid))
        queue.extend(sorted(edges))
        if edges:
            graph[identity] = sorted(edges)
    return graph, seen


def native_fields(obj, U):
    """Pinned parser declarations supply native structure, never object values."""
    if obj.node is None:
        U.require(obj.type.value != 114, "scripted resource has no original schema")
        from UnityPy.helpers.Tpk import get_typetree_node
        from UnityPy.helpers.UnityVersion import UnityVersion

        obj.asset.nodes[obj.row["type_id"]] = get_typetree_node(obj.type.value, UnityVersion.from_str(obj.asset.layout["engine"]))
    return obj.read_typetree()


class Files:
    def __init__(self, U, store, player, output, shader_root, shader_receipt, sdk, audit):
        self.U, self.store, self.output, self.sdk = U, store, Path(output), Path(sdk)
        self.paths, self.assets, self.schemas, self.manifests, self.native = {}, {}, {}, {}, {}
        for file, row in shader_receipt["files"].items():
            prefix = "apk/assets/bin/Data/"
            U.require(file.startswith(prefix) and ".." not in PurePosixPath(file).parts, "unsafe produced Shader filename")
            name = file[len(prefix) :]
            path = Path(shader_root) / file
            store.pin(path, row)
            self.paths[name] = path
        for group in [player["font"], *player["objects"]]:
            asset = store.asset(group["source"])
            for row in group["objects"]:
                self.schemas[group["file"], row["path_id"]] = asset.objects[row["source_path_id"]].node
        for phase in ("ui", "hud"):
            root = Path(audit) / (phase + "-source")
            receipt = store.json(root / "result.json")
            U.require(receipt.get("resources"), "source UI receipt lacks resources")
            names = {row["file"] for row in receipt["resources"].values()}
            U.require(len(names) == 1, "source UI phase has multiple graph files")
            name = next(iter(names))
            for row in store.json(root / "objects.json"):
                path = root / ("schema-" + str(row["type_id"]) + ".tree")
                store.pin(path)
                self.schemas[name, row["id"]] = U.node_from_tree(path.read_bytes())
                self.manifests[name, row["id"]] = row["fields"]

    def asset(self, file):
        name = PurePosixPath(file)
        self.U.require(not name.is_absolute() and ".." not in name.parts and "\\" not in file, "unsafe resource provider name")
        if file in self.assets:
            return self.assets[file]
        if file == "Library/unity default resources":
            path = self.sdk / "Data/unity default resources"
            self.store.pin(path, dict(zip(("bytes", "sha256"), self.U.P.SDK.FILES["Data/unity default resources"])))
        else:
            local = self.output / file
            path = local if local.is_file() else self.paths.get(file)
        self.U.require(path is not None, "missing produced player provider: " + file)
        path = Path(path)
        self.U.require(not path.is_symlink(), "redirected player provider")
        self.paths[file] = path
        asset = self.store.asset_file(path, "produced:" + file)
        self.assets[file] = asset
        return asset

    def fields(self, file, pid):
        asset = self.asset(file)
        self.U.require(pid in asset.objects, "produced resource object absent")
        obj = asset.objects[pid]
        key = file, pid
        if key in self.schemas:
            self.U.require(self.schemas[key] is not None, "original resource transfer schema absent")
            asset.nodes[obj.row["type_id"]] = self.schemas[key]
        if key in self.manifests:
            fields = self.manifests[key]
            self.U.require(self.U.encode(fields, obj.node) == obj.get_raw_data(), "source UI manifest differs from emitted binary")
        else:
            fields = native_fields(obj, self.U)
        return fields, [row["path"] for row in asset.externals]

    def shader_records(self, file):
        asset = self.asset(file)
        return [(pid, self.fields(file, pid)[0]["m_ParsedForm"]["m_Name"]) for pid, obj in asset.objects.items() if obj.type.value == 48]
