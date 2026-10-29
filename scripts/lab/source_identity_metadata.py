"""Generate runtime identity metadata from decoded records or staged Unity YAML."""

import base64
import hashlib
import json
import re

NETWORK_IDENTITY_GUID = "d382a022563c7517aadbc92ca1060016"
SCENE_TOGGLE_GUID = "951ce57ad999ac1f040a4dceb5f8b763"


def _scalar(block, pattern, default=None):
    match = re.search(pattern, block, re.M)
    return match.group(1) if match else default


def _unquote(value):
    if value is None:
        return None
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def _blocks(scene_path):
    raw = scene_path.read_bytes()
    source = raw.decode("utf-8", errors="strict").replace("\r\n", "\n")
    blocks = {}
    ordered = []
    for block in re.split(r"(?=^--- !u!)", source, flags=re.M):
        header = re.match(r"--- !u!(\d+) &(-?\d+)", block)
        if header:
            file_id = header.group(2)
            kind = int(header.group(1))
            blocks[file_id] = (kind, block)
            ordered.append((file_id, kind, block))
    return source, raw, blocks, ordered


def from_records(game_objects, transforms, identities, toggle_rows, source_scene_sha256, source_name="scene"):
    """Build the same identity contract from decoded original or staged records.

    Inputs use string local IDs and explicit active booleans. The caller owns
    source identity validation and the declared provenance digest representation.
    """
    game_transforms = {row["gameObject"]: fid for fid, row in transforms.items()}
    roots = [file_id for file_id, transform in transforms.items() if transform["father"] == "0"]
    root_name_counts = {}
    for transform_id in roots:
        name = game_objects[transforms[transform_id]["gameObject"]]["name"]
        root_name_counts[name] = root_name_counts.get(name, 0) + 1
    shape_cache = {}

    def shape(transform_id, active=None):
        if transform_id in shape_cache:
            return shape_cache[transform_id]
        active = set() if active is None else active
        if transform_id in active or transform_id not in transforms:
            raise ValueError(f"Transform graph is cyclic or incomplete in {source_name}")
        active.add(transform_id)
        row = transforms[transform_id]
        name = game_objects[row["gameObject"]]["name"]
        children = [shape(child, active) for child in row["children"]]
        active.remove(transform_id)
        encoded = base64.b64encode(name.encode("utf-8")).decode("ascii")
        signature = encoded + "|" + str(len(children)) + "[" + "".join(children) + "]"
        shape_cache[transform_id] = signature
        return signature

    root_hashes = {root: hashlib.sha256(shape(root).encode("ascii")).hexdigest() for root in roots}
    root_shape_counts = {}
    for root, digest in root_hashes.items():
        root_name = game_objects[transforms[root]["gameObject"]]["name"]
        key = (root_name, digest)
        root_shape_counts[key] = root_shape_counts.get(key, 0) + 1

    def path_for(go_id):
        if go_id == "0":
            return None
        transform_id = game_transforms.get(go_id)
        if transform_id is None:
            raise ValueError(f"Referenced GameObject has no Transform in {source_name}: {go_id}")
        reversed_path = []
        seen = set()
        while transform_id:
            if transform_id in seen or transform_id not in transforms:
                raise ValueError(f"Transform path is cyclic or incomplete in {source_name}: {go_id}")
            seen.add(transform_id)
            row = transforms[transform_id]
            owner = row["gameObject"]
            name = game_objects[owner]["name"]
            father = row["father"]
            if father == "0":
                digest = root_hashes[transform_id]
                same_shape = root_shape_counts[(name, digest)]
                if same_shape != 1:
                    raise ValueError(f"Duplicate same-name, same-shape roots are ambiguous in {source_name}: {name}")
                reversed_path.append(
                    {
                        "root": True,
                        "index": None,
                        "name": name,
                        "sibling_count": None,
                        "same_name_root_count": root_name_counts[name],
                        "root_shape_sha256": digest,
                        "same_name_same_shape_count": same_shape,
                    }
                )
                transform_id = None
            else:
                parent = transforms.get(father)
                if parent is None or transform_id not in parent["children"]:
                    raise ValueError(f"Serialized parent/child order mismatch in {source_name}: {go_id}")
                index = parent["children"].index(transform_id)
                if row["rootOrder"] != index:
                    raise ValueError(f"Serialized sibling index differs from child list in {source_name}: {go_id}")
                reversed_path.append(
                    {
                        "root": False,
                        "index": index,
                        "name": name,
                        "sibling_count": len(parent["children"]),
                        "same_name_root_count": None,
                        "root_shape_sha256": None,
                        "same_name_same_shape_count": None,
                    }
                )
                transform_id = father
        return list(reversed(reversed_path))

    identities = [
        dict(
            row,
            name=game_objects[str(row["source_game_object_file_id"])]["name"],
            active_self=game_objects[str(row["source_game_object_file_id"])]["active_self"],
        )
        for row in identities
        if row["scene_id"] != 0
    ]
    identities.sort(key=lambda row: row["scene_id"])
    if len({row["scene_id"] for row in identities}) != len(identities):
        raise ValueError(f"Duplicate nonzero NetworkIdentity scene ID in {source_name}")
    controllers = []
    for row in toggle_rows:
        component_id, owner_id = row["source_component_file_id"], row["source_game_object_file_id"]
        groups = []
        for group in row["groups"]:
            objects = [{"source_game_object_file_id": int(ref), "transform_path": path_for(str(ref))} for ref in group["objects"]]
            groups.append({"min_enabled": group["min_enabled"], "max_enabled": group["max_enabled"], "objects": objects})
        owner_identity = [item for item in identities if item["source_game_object_file_id"] == int(owner_id)]
        if len(owner_identity) > 1:
            raise ValueError(f"Toggle controller has multiple NetworkIdentity components in {source_name}")
        controllers.append(
            {
                "scene_id": owner_identity[0]["scene_id"] if owner_identity else None,
                "source_component_file_id": int(component_id),
                "source_game_object_file_id": int(owner_id),
                "transform_path": path_for(str(owner_id)),
                "groups": groups,
            }
        )
    return {"schema_version": 1, "source_scene_sha256": source_scene_sha256, "network_identities": identities, "toggle_controllers": controllers}


def read_scene(scene_path):
    _, raw, _, ordered = _blocks(scene_path)
    game_objects, transforms = {}, {}
    for file_id, kind, block in ordered:
        if kind == 1:
            name = _unquote(_scalar(block, r"^  m_Name: (.*)$"))
            if name is None:
                raise ValueError(f"GameObject has no name in {scene_path.name}: {file_id}")
            game_objects[file_id] = {"name": name, "active_self": _scalar(block, r"^  m_IsActive: ([01])$", "1") == "1"}
        elif kind in (4, 224):
            owner = _scalar(block, r"^  m_GameObject: \{fileID: (-?\d+)\}$")
            father = _scalar(block, r"^  m_Father: \{fileID: (-?\d+)\}$", "0")
            root_order = _scalar(block, r"^  m_RootOrder: (-?\d+)$")
            children_field = re.search(r"^  m_Children:(.*?)(?=^  m_Father:)", block, re.M | re.S)
            children = re.findall(r"^\s+- \{fileID: (-?\d+)\}$", children_field.group(1), re.M) if children_field else []
            if owner is None or root_order is None:
                raise ValueError(f"Transform is unresolved in {scene_path.name}: {file_id}")
            transforms[file_id] = {"gameObject": owner, "father": father, "rootOrder": int(root_order), "children": children}

    def component_script_id(block, expected_guid):
        match = re.search(r"^  m_Script: \{fileID: (-?\d+), guid: ([0-9a-f]+), type: 3\}$", block, re.M)
        return int(match.group(1)) if match and match.group(2) == expected_guid else None

    identities, toggles = [], []
    for component_id, kind, block in ordered:
        if kind != 114:
            continue
        owner = _scalar(block, r"^  m_GameObject: \{fileID: (-?\d+)\}$")
        if owner is None or owner not in game_objects:
            continue
        if component_script_id(block, NETWORK_IDENTITY_GUID) == 372142912 and "m_SceneId:" in block:
            scene_id = _scalar(block, r"^    m_Value: (\d+)$")
            if scene_id is None:
                raise ValueError(f"NetworkIdentity scene ID missing in {scene_path.name}: {component_id}")
            identities.append(dict(scene_id=int(scene_id), source_component_file_id=int(component_id), source_game_object_file_id=int(owner)))
        if component_script_id(block, SCENE_TOGGLE_GUID) == 1517225185 and re.search(r"^  toggleGroups:", block, re.M):
            groups = []
            for group in re.split(r"(?=^  - objects:)", block.split("  toggleGroups:", 1)[1], flags=re.M):
                if not re.search(r"^  - objects:", group, re.M):
                    continue
                refs = re.findall(r"^    - \{fileID: (-?\d+)\}$", group, re.M)
                minimum = _scalar(group, r"^    minEnabled: (-?\d+)$")
                maximum = _scalar(group, r"^    maxEnabled: (-?\d+)$")
                if minimum is None or maximum is None:
                    raise ValueError(f"Toggle group range is incomplete in {scene_path.name}")
                groups.append(dict(min_enabled=int(minimum), max_enabled=int(maximum), objects=refs))
            toggles.append(dict(source_component_file_id=int(component_id), source_game_object_file_id=int(owner), groups=groups))
    return from_records(game_objects, transforms, identities, toggles, hashlib.sha256(raw).hexdigest(), scene_path.name)
