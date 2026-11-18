"""Compare serialized physics through named asset and GameObject identities."""

from collections import Counter, defaultdict
import io
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from zipfile import ZipFile

from manager_graph import native_fields
from manager_settings import COLLISION_MATRIX, project, yaml_settings
import player_ui as U

PROJECTILE = ("ProjectileController", "RoR2.Projectile", "RoR2.dll")


class PhysicsObjects:
    def __init__(self, catalog, bundles, container_table):
        from UnityPy.enums import ClassIDType

        self.catalog = catalog
        self.counters = Counter()
        self.assets = defaultdict(set)
        self.readers = {}
        game_objects, transforms = {}, {}
        self.components = {}
        native = {cls.value for cls in ClassIDType if "Collider" in cls.name or cls.name in ("Rigidbody", "Rigidbody2D", "CharacterController")}
        projectile_id = U.S.md4("".join(PROJECTILE).encode())
        for bundle in bundles:
            for member in catalog.bundles.get(bundle, ()):
                _, layout, records = catalog.members[member]
                for pid, row in records.items():
                    endpoint = (member, pid)
                    typ = layout["types"][row["type_id"]]
                    cls = typ["class_id"]
                    if cls in (1, 4, 224) or cls in native:
                        values = self.fields(endpoint)
                        if cls == 1:
                            game_objects[endpoint] = values
                        elif cls in (4, 224):
                            transforms[endpoint] = values
                        else:
                            self.components[endpoint] = (ClassIDType(cls).name, values)
                    elif cls == 114 and typ["script_id"] == projectile_id:
                        _, _, body = catalog.record(member, (0, pid))
                        if catalog.binding(member, typ, body) != PROJECTILE:
                            raise ValueError("projectile physics MonoScript identity differs")
                        self.components[endpoint] = (PROJECTILE[0], self.fields(endpoint))
                    elif cls == 142:
                        _, _, body = catalog.record(member, (0, pid))
                        for asset, fid, target in container_table(body)[1]:
                            endpoint = catalog.endpoint(member, (fid, target))
                            if endpoint and len(endpoint) == 2:
                                self.assets[asset].add(endpoint)

        roots = defaultdict(list)
        for asset, endpoints in self.assets.items():
            if len(endpoints) == 1:
                roots[next(iter(endpoints))].append(asset)
        self.targets = {endpoint: ("asset", min(names)) for endpoint, names in roots.items()}
        self.routes = self.game_object_routes(game_objects, transforms, roots)
        self.targets.update(self.routes)
        for endpoint, fields in transforms.items():
            route = self.routes.get(self.endpoint(endpoint, fields["m_GameObject"]))
            if route:
                self.targets[endpoint] = route + ("Transform",)
        self.objects = {}
        for owner, values in game_objects.items():
            self.counters["GameObject"] += 1
            route = self.routes.get(owner)
            if route is None:
                self.counters["unmatched:GameObject"] += 1
                continue
            self.objects[route + ("GameObject",)] = (owner, {"m_Layer": values["m_Layer"]})
            slots = Counter()
            for row in values["m_Component"]:
                endpoint = self.endpoint(owner, row["component"])
                if endpoint in self.components:
                    kind, fields = self.components.pop(endpoint)
                    if self.endpoint(endpoint, fields["m_GameObject"]) != owner:
                        raise ValueError("physics component and GameObject disagree about ownership")
                    slots[kind] += 1
                    self.counters[kind] += 1
                    key = route + (kind, slots[kind])
                    self.targets[endpoint] = key
                    self.objects[key] = (endpoint, {name: value for name, value in fields.items() if name not in ("m_GameObject", "m_Script")})
        for kind, _ in self.components.values():
            self.counters[kind] += 1
            self.counters["unmatched:" + kind] += 1

    def fields(self, endpoint):
        member, pid = endpoint
        if member not in self.readers:
            stream, layout, _ = self.catalog.members[member]
            self.readers[member] = SimpleNamespace(stream=stream, layout=layout, nodes={}, native_trees={})
        asset = self.readers[member]
        rows = self.catalog.members[member][2]
        return native_fields(U.Object(asset, rows[pid]), U)

    def endpoint(self, owner, ptr):
        return self.catalog.endpoint(owner[0], (ptr["m_FileID"], ptr["m_PathID"]))

    def game_object_routes(self, objects, transforms, roots):
        routes, ambiguous = {}, set()
        children = defaultdict(list)
        scene_roots = defaultdict(list)
        for node, fields in transforms.items():
            owner = self.endpoint(node, fields["m_GameObject"])
            if owner not in objects:
                continue
            if self.endpoint(node, fields["m_Father"]) is None and owner not in roots:
                scene_roots[(owner[0], objects[owner]["m_Name"])].append(owner)
            for ptr in fields.get("m_Children", []):
                child = self.endpoint(node, ptr)
                if child in transforms:
                    child_owner = self.endpoint(child, transforms[child]["m_GameObject"])
                    if child_owner in objects:
                        children[owner].append(child_owner)

        def visit(owner, route):
            if owner in routes:
                ambiguous.add(owner)
                return
            routes[owner] = route
            slots = Counter()
            for child in children[owner]:
                # An advertised child has its own cross-bundle identity.
                if child not in roots:
                    name = objects[child]["m_Name"]
                    slots[name] += 1
                    visit(child, route + ((name, slots[name]),))

        for owner, names in roots.items():
            if owner in objects:
                visit(owner, ("prefab", min(names), objects[owner]["m_Name"]))
        for (member, name), owners in scene_roots.items():
            if len(owners) == 1 and owners[0] not in routes:
                visit(owners[0], ("scene", member, name))
        return {owner: route for owner, route in routes.items() if owner not in ambiguous}

    def normalize(self, owner, value, unqualified, field):
        if isinstance(value, dict):
            if set(value) == {"m_FileID", "m_PathID"}:
                endpoint = self.endpoint(owner, value)
                if endpoint is None or endpoint in self.targets:
                    return self.targets.get(endpoint)
                unqualified[field] = endpoint
                return None
            return {key: self.normalize(owner, child, unqualified, field + (key,)) for key, child in value.items()}
        if isinstance(value, list):
            return [self.normalize(owner, child, unqualified, field + (index,)) for index, child in enumerate(value)]
        return value


def managers(raw):
    stream = io.BytesIO(raw)
    stream.size = len(raw)
    asset = U.Asset("globalgamemanagers", stream, {})
    rows = defaultdict(list)
    for obj in asset.objects.values():
        if obj.type.value in (55, 78):
            rows[obj.type.value].append(obj)
    if any(len(rows[cls]) != 1 for cls in (55, 78)):
        raise ValueError("player lacks unique PhysicsManager and TagManager")
    return native_fields(rows[55][0], U), native_fields(rows[78][0], U)["layers"]


def compare_managers(candidate, reference, pc, pinned, emit):
    root = Path(__file__).resolve().parents[3]
    profile = json.loads((root / "recipe/owner-player-managers.json").read_bytes())
    setting = profile["public_inputs"]["settings_DynamicsManager"]
    settings_path = pinned(root / setting["path"], setting["sha256"])
    project_settings = yaml_settings(settings_path.read_bytes())
    sides = {}
    for side, apk in (("candidate", candidate), ("reference", reference)):
        with ZipFile(apk) as archive:
            sides[side] = managers(archive.read("assets/bin/Data/globalgamemanagers"))
    if pc:
        source = profile["source"]
        sides["source"] = managers(pinned(pc / source["path"], source["sha256"]).read_bytes())
    candidate_fields, layers = sides["candidate"]
    for side, (fields, other_layers) in sides.items():
        if side == "candidate":
            continue
        for key in sorted(candidate_fields.keys() | fields.keys()):
            if candidate_fields.get(key) != fields.get(key):
                emit("physics-manager-field", other_side=side, field=key, candidate=candidate_fields.get(key), other=fields.get(key))
        if layers != other_layers:
            emit("physics-layer-table", other_side=side, candidate=layers, other=other_layers)

    def serialized_setting(shape, value):
        if isinstance(shape, float):
            return struct.unpack("<f", struct.pack("<f", value))[0]
        if isinstance(shape, dict):
            return {key: serialized_setting(shape[key], child) for key, child in value.items()}
        return value

    projected = project(candidate_fields, project_settings)
    for field, value in projected.items():
        if serialized_setting(candidate_fields[field], value) != candidate_fields[field]:
            emit("physics-project-setting", field=field, candidate=candidate_fields[field], project=value)
    return dict(
        matrices={side: fields[COLLISION_MATRIX] for side, (fields, _) in sides.items()},
        project_matrix=projected[COLLISION_MATRIX],
        layer_tables={side: names for side, (_, names) in sides.items()},
        project_sha256=setting["sha256"],
    )


def compare_objects(sides, bundles, container_table, emit):
    indexes = {side: PhysicsObjects(catalog, bundles, container_table) for side, catalog in sides.items()}
    left, right = indexes["candidate"], indexes["reference"]
    compared = Counter()
    for route in sorted(left.objects.keys() | right.objects.keys(), key=repr):
        if route not in left.objects or route not in right.objects:
            side = "candidate" if route in left.objects else "reference"
            emit("physics-unmatched-route", side=side, route=route, object=indexes[side].objects[route][0])
            continue
        a, af = left.objects[route]
        b, bf = right.objects[route]
        compared[route[-1] if isinstance(route[-1], str) else route[-2]] += 1
        for field in sorted(af.keys() | bf.keys()):
            unqualified = {}
            x = left.normalize(a, af.get(field, "absent"), unqualified, ("candidate",))
            y = right.normalize(b, bf.get(field, "absent"), unqualified, ("reference",))
            details = dict(route=route, field=field, candidate_object=a, reference_object=b)
            if unqualified:
                emit("physics-unqualified-pointer", **details, pointers=list(unqualified.items()))
            elif x != y:
                emit("physics-object-field", **details, candidate=x, reference=y)
    for side, index in indexes.items():
        for endpoint, (kind, fields) in index.components.items():
            emit("physics-unmatched-component", side=side, kind=kind, object=endpoint, owner=index.endpoint(endpoint, fields["m_GameObject"]))
    return dict(compared=compared, inspected={side: index.counters for side, index in indexes.items()})
