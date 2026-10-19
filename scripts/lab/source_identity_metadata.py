"""Generate runtime-resolvable source identity metadata from a staged Unity scene."""

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


def read_scene(scene_path):
    source, raw, blocks, ordered = _blocks(scene_path)
    game_objects = {}
    transforms = {}
    game_transforms = {}
    for file_id, kind, block in ordered:
        if kind == 1:
            name = _unquote(_scalar(block, r"^  m_Name: (.*)$"))
            components = re.findall(r"^  - component: \{fileID: (-?\d+)\}$", block, re.M)
            if name is None:
                raise ValueError(f"GameObject has no name in {scene_path.name}: {file_id}")
            game_objects[file_id] = {"name": name, "components": components}
        elif kind in (4, 224):
            owner = _scalar(block, r"^  m_GameObject: \{fileID: (-?\d+)\}$")
            father = _scalar(block, r"^  m_Father: \{fileID: (-?\d+)\}$", "0")
            root_order = _scalar(block, r"^  m_RootOrder: (-?\d+)$")
            children_field = re.search(r"^  m_Children:(.*?)(?=^  m_Father:)", block, re.M | re.S)
            children = re.findall(r"^\s+- \{fileID: (-?\d+)\}$", children_field.group(1), re.M) if children_field else []
            if owner is None or root_order is None:
                raise ValueError(f"Transform is unresolved in {scene_path.name}: {file_id}")
            transforms[file_id] = {"gameObject": owner, "father": father, "rootOrder": int(root_order), "children": children}
            game_transforms[owner] = file_id

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
            raise ValueError(f"Transform graph is cyclic or incomplete in {scene_path.name}")
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
            raise ValueError(f"Referenced GameObject has no Transform in {scene_path.name}: {go_id}")
        reversed_path = []
        seen = set()
        while transform_id:
            if transform_id in seen or transform_id not in transforms:
                raise ValueError(f"Transform path is cyclic or incomplete in {scene_path.name}: {go_id}")
            seen.add(transform_id)
            row = transforms[transform_id]
            owner = row["gameObject"]
            name = game_objects[owner]["name"]
            father = row["father"]
            if father == "0":
                digest = root_hashes[transform_id]
                same_shape = root_shape_counts[(name, digest)]
                if same_shape != 1:
                    raise ValueError(f"Duplicate same-name, same-shape roots are ambiguous in {scene_path.name}: {name}")
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
                    raise ValueError(f"Serialized parent/child order mismatch in {scene_path.name}: {go_id}")
                index = parent["children"].index(transform_id)
                if row["rootOrder"] != index:
                    raise ValueError(f"Serialized sibling index differs from child list in {scene_path.name}: {go_id}")
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

    def component_script_id(block, expected_guid):
        match = re.search(r"^  m_Script: \{fileID: (-?\d+), guid: ([0-9a-f]+), type: 3\}$", block, re.M)
        if not match or match.group(2) != expected_guid:
            return None
        return int(match.group(1))

    identities = []
    toggle_controllers = []
    for component_id, kind, block in ordered:
        if kind != 114:
            continue
        owner = _scalar(block, r"^  m_GameObject: \{fileID: (-?\d+)\}$")
        if owner is None or owner not in game_objects:
            continue
        script_id = component_script_id(block, NETWORK_IDENTITY_GUID)
        if script_id is not None and script_id == 372142912 and "m_SceneId:" in block:
            scene_id = _scalar(block, r"^    m_Value: (\d+)$")
            if scene_id is None:
                raise ValueError(f"NetworkIdentity scene ID missing in {scene_path.name}: {component_id}")
            if int(scene_id) != 0:
                go = game_objects[owner]
                active = _scalar(blocks[owner][1], r"^  m_IsActive: ([01])$", "1") == "1"
                identities.append(
                    {
                        "scene_id": int(scene_id),
                        "name": go["name"],
                        "active_self": active,
                        "source_component_file_id": int(component_id),
                        "source_game_object_file_id": int(owner),
                    }
                )
        script_id = component_script_id(block, SCENE_TOGGLE_GUID)
        if script_id is not None and script_id == 1517225185 and re.search(r"^  toggleGroups:", block, re.M):
            toggle_controllers.append((component_id, owner, block))

    identities.sort(key=lambda row: row["scene_id"])
    if len({row["scene_id"] for row in identities}) != len(identities):
        raise ValueError(f"Duplicate nonzero NetworkIdentity scene ID in {scene_path.name}")
    controllers = []
    for component_id, owner_id, controller_block in toggle_controllers:
        controller_path = path_for(owner_id)
        group_text = controller_block.split("  toggleGroups:", 1)[1]
        groups = []
        for group in re.split(r"(?=^  - objects:)", group_text, flags=re.M):
            if not re.search(r"^  - objects:", group, re.M):
                continue
            refs = re.findall(r"^    - \{fileID: (-?\d+)\}$", group, re.M)
            minimum = _scalar(group, r"^    minEnabled: (-?\d+)$")
            maximum = _scalar(group, r"^    maxEnabled: (-?\d+)$")
            if minimum is None or maximum is None:
                raise ValueError(f"Toggle group range is incomplete in {scene_path.name}")
            objects = []
            for ref in refs:
                binding = path_for(ref)
                objects.append({"source_game_object_file_id": int(ref), "transform_path": binding})
            groups.append({"min_enabled": int(minimum), "max_enabled": int(maximum), "objects": objects})
        owner_identity = [row for row in identities if row["source_game_object_file_id"] == int(owner_id)]
        if len(owner_identity) > 1:
            raise ValueError(f"Toggle controller has multiple NetworkIdentity components in {scene_path.name}")
        controllers.append(
            {
                "scene_id": owner_identity[0]["scene_id"] if owner_identity else None,
                "source_component_file_id": int(component_id),
                "source_game_object_file_id": int(owner_id),
                "transform_path": controller_path,
                "groups": groups,
            }
        )

    return {
        "schema_version": 1,
        "source_scene_sha256": hashlib.sha256(raw).hexdigest(),
        "network_identities": identities,
        "toggle_controllers": controllers,
    }
