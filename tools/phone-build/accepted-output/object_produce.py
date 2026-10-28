"""Produce a complete qualified prefab or scene bundle's objects from original PC records.

UnityPy 1.25.3 and AssetRipper 1ac666f document the serialized type/script
relationships. Bodies and embedded type trees come from the owner's input;
checked native export policies and authored bundle-container metadata transform
those original records without an accepted-output byte provider.
"""

import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import time


def module(name, path=None):
    spec = importlib.util.spec_from_file_location("_objects_" + name, path or Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


W, M = module("unity_write"), module("mesh_produce")
B = W.B


def source_member(path, member):
    """Open an original bundle member or its named native serialized file."""
    with path.open("rb") as stream:
        signature = stream.read(8)
        if signature != b"UnityFS\0":
            if member != path.name:
                raise ValueError("native serialized source member identity differs")
            stream.seek(0)
            raw = B.exact(stream, path.stat().st_size)
            result = io.BytesIO(raw)
            result.size = len(raw)
            return result
    return B.Bundle(path).member(member)


def remap(body, references):
    """Replace checked 12-byte PPtrs; preserve every other source byte."""
    result = bytearray(body)
    previous = -12
    for row in sorted(references, key=lambda item: item["offset"]):
        offset = row["offset"]
        if type(offset) is not int or offset < previous + 12 or offset % 4 or offset + 12 > len(body):
            raise ValueError("invalid or overlapping PPtr extent")
        if list(struct.unpack_from("<iq", body, offset)) != row["from"]:
            raise ValueError("original PPtr identity drift")
        struct.pack_into("<iq", result, offset, *row["to"])
        previous = offset
    return bytes(result)


def remap_record(body, typ, references, externals):
    """Relocate produced bodies only at PPtrs declared by the original schema."""
    records = module("record_produce")
    _, spans = records.fields(body, records.SCHEMA.type_tree(io.BytesIO(typ["tree"])))
    pointers = {start for key, (start, end) in spans.items() if end - start == 12 and key + ("m_FileID",) in spans and key + ("m_PathID",) in spans}
    for reference in references:
        if reference["offset"] not in pointers:
            raise ValueError("produced record relocation is not a schema PPtr")
        file_id, _ = reference["to"]
        if not 0 <= file_id <= len(externals):
            raise ValueError("produced record relocation has an absent external file")
    return remap(body, references)


def demote_material_keywords(body, *, sort_invalid=False):
    """Retain original keywords as invalid for the qualified dummy shader.

    The authored dummy shader declares no material keywords. Preserve the
    original valid-then-invalid order by default, every keyword string and all other
    original material values; no shader/material payload comes from a recipe.
    """
    stream = io.BytesIO(body)

    def string():
        start = stream.tell()
        size = B.unpack(stream, "<I")[0]
        label = B.exact(stream, size).decode("utf-8")
        B.exact(stream, -stream.tell() % 4)
        return label, body[start : stream.tell()]

    string()  # Original material name.
    B.exact(stream, 12)  # Shader PPtr, relocated separately.
    start = stream.tell()
    valid_count = B.unpack(stream, "<I")[0]
    if valid_count > len(body) // 4:
        raise ValueError("invalid material keyword count")
    keywords = [string() for _ in range(valid_count)]
    invalid_count = B.unpack(stream, "<I")[0]
    if invalid_count > len(body) // 4:
        raise ValueError("invalid material keyword count")
    keywords.extend(string() for _ in range(invalid_count))
    end = stream.tell()
    if sort_invalid:
        keywords.sort(key=lambda item: item[0].encode("utf-16-be"))
    return body[:start] + struct.pack("<II", 0, valid_count + invalid_count) + b"".join(chunk for _, chunk in keywords) + body[end:]


def remove_components(body, removals):
    """Apply checked component omissions from the accepted scene export."""
    count = struct.unpack_from("<I", body)[0]
    end = 4 + count * 12
    if end > len(body):
        raise ValueError("truncated original GameObject component array")
    selected = {}
    for removal in removals:
        index = removal["index"]
        if type(index) is not int or not 0 <= index < count or index in selected:
            raise ValueError("invalid or repeated omitted component index")
        if struct.unpack_from("<iq", body, 4 + index * 12) != (0, removal["path_id"]):
            raise ValueError("omitted original component identity drift")
        selected[index] = removal["path_id"]
    kept = [body[4 + index * 12 : 16 + index * 12] for index in range(count) if index not in selected]
    return struct.pack("<I", len(kept)) + b"".join(kept) + body[end:]


def append_components(body, identities):
    """Append existing source-produced components, preserving the original tail."""
    count = struct.unpack_from("<I", body)[0]
    end = 4 + count * 12
    if end > len(body):
        raise ValueError("truncated original GameObject component array")
    return struct.pack("<I", count + len(identities)) + body[4:end] + b"".join(struct.pack("<iq", 0, identity) for identity in identities) + body[end:]


def clear_static_renderers(body, expected):
    """Clear only the original occlusion static-renderer array, retaining portals."""
    count = struct.unpack_from("<I", body, 28)[0]
    end = 32 + count * 12
    if count != expected or end > len(body):
        raise ValueError("original occlusion static-renderer array drift")
    return body[:28] + bytes(4) + body[end:]


def deactivate_global_owner(body, name):
    """Apply authored scene and prefab root suppression."""
    if name not in {
        "SceneInfo",
        "Director",
        "GameManager",
        "RoR2Application",
        "BeetleBody",
        "BeetleGuardBody",
        "BeetleGuardMaster",
        "BeetleQueen2Body",
        "CommandoBody",
        "PlayerMaster",
        "Teleporter1",
    }:
        raise ValueError("unknown original global owner")
    stream = io.BytesIO(body)
    count = B.unpack(stream, "<I")[0]
    if count > len(body) // 12:
        raise ValueError("truncated original global owner components")
    B.exact(stream, count * 12 + 4)  # Original components and layer.
    size = B.unpack(stream, "<I")[0]
    if size > len(body):
        raise ValueError("truncated original global owner name")
    original = B.exact(stream, size).decode("utf-8")
    B.exact(stream, -stream.tell() % 4)
    B.exact(stream, 2)  # Preserve original tag.
    active = B.exact(stream, 1)
    if original != name or active != b"\x01" or stream.tell() != len(body):
        raise ValueError("global suppression requires the named active original GameObject")
    return body[:-1] + bytes(1)


def rebuild_director_deck(body, tree, categories):
    """Select source category/card spans with the authored deck's default omissions."""
    records = module("record_produce")
    _, spans = records.fields(body, records.SCHEMA.type_tree(io.BytesIO(tree)))
    name_start, name_end = spans["m_Name",]
    name_size = struct.unpack_from("<I", body, name_start)[0]
    name = body[name_start + 4 : name_start + 4 + name_size].decode("utf-8")
    category_start, category_end = spans["categories",]
    result = io.BytesIO()
    result.write(body[:name_start])
    aligned_string(result, "Android supported " + name)
    result.write(body[name_end:category_start])
    result.write(struct.pack("<I", len(categories)))
    omitted_fields = {
        "spawnDistance",
        "preventOverhead",
        "minimumStageCompletions",
        "requiredUnlockable",
        "forbiddenUnlockable",
        "requiredUnlockableDef",
        "forbiddenUnlockableDef",
    }
    for category in categories:
        path = ("categories", "Array", str(category["source_index"]))
        start, end = spans[path]
        cards_start, cards_end = spans[path + ("cards",)]
        result.write(body[start:cards_start])
        result.write(struct.pack("<I", len(category["cards"])))
        for card in category["cards"]:
            card_path = path + ("cards", "Array", str(card["source_index"]))
            card_start, card_end = spans[card_path]
            for field in ("isExclusivelyElite", "eliteDef"):
                first, last = spans[card_path + (field,)]
                if body[first:last] != bytes(last - first):
                    raise ValueError("authored director deck requires original non-elite defaults")
            replacements = []
            if not set(card["omit_fields"]) <= omitted_fields:
                raise ValueError("unknown authored director card omission")
            for field in card["omit_fields"]:
                first, last = spans[card_path + (field,)]
                data = bytes(4) if field in ("requiredUnlockable", "forbiddenUnlockable") else bytes(last - first)
                replacements.append((first, last, data))
            cursor = card_start
            for first, last, data in sorted(replacements):
                result.write(body[cursor:first])
                result.write(data)
                cursor = last
            result.write(body[cursor:card_end])
        tail = body[cards_end:end]
        if category["omit_weight"]:
            first, last = spans[path + ("selectionWeight",)]
            if (first, last) != (cards_end, end) or last - first != 4:
                raise ValueError("original director category weight layout drift")
            tail = bytes(4)
        result.write(tail)
    result.write(body[category_end:])
    return result.getvalue()


def empty_mesh_renderer(body, tree):
    """Project an original empty renderer through the authored adapter flags."""
    records = module("record_produce")
    _, spans = records.fields(body, records.SCHEMA.type_tree(io.BytesIO(tree)))
    start, end = spans[("m_Materials", "Array")]
    if body[start:end] != bytes(4):
        raise ValueError("empty renderer requires an original empty material array")
    result = bytearray(body)
    for name in ("#349", "m_CastShadows", "m_ReceiveShadows"):
        # m_Enabled uses Unity's common-string offset 349 in release schemas.
        start, end = spans[("m_Enabled" if name == "#349" and ("m_Enabled",) in spans else name,)]
        if end - start != 1 or body[start] not in (0, 1):
            raise ValueError("original empty renderer flag schema drift")
        result[start] = 0
    return bytes(result)


def omit_surface_effects(body, tree):
    """Apply the authored SurfaceDef effect and sound omissions to source spans."""
    records = module("record_produce")
    root = records.SCHEMA.type_tree(io.BytesIO(tree))
    _, spans = records.fields(body, root)
    replacements = []
    for name in ("impactEffectPrefab", "footstepEffectPrefab", "impactSoundString", "materialSwitchString"):
        nodes = [node for node in root.children if node.name == name]
        if len(nodes) != 1:
            raise ValueError("original SurfaceDef field absent or ambiguous")
        node = nodes[0]
        start, end = spans[name,]
        if name.endswith("Prefab"):
            if not node.kind.startswith("PPtr<") or end - start != 12:
                raise ValueError("original SurfaceDef effect is not a PPtr")
            replacement = bytes(12)
        else:
            if node.kind != "string":
                raise ValueError("original SurfaceDef sound field is not a string")
            replacement = bytes(4)
        replacements.append((start, end, replacement))
    result, cursor = bytearray(), 0
    for start, end, replacement in sorted(replacements):
        result.extend(body[cursor:start])
        result.extend(replacement)
        cursor = end
    result.extend(body[cursor:])
    return bytes(result)


def normalize_exported_prefab_name(body, authored_root=None):
    """Apply the pinned exporter's filename projection to a prefab root name."""
    stream = io.BytesIO(body)
    count = B.unpack(stream, "<I")[0]
    if count > len(body) // 12:
        raise ValueError("truncated original prefab components")
    B.exact(stream, count * 12 + 4)
    start = stream.tell()
    size = B.unpack(stream, "<I")[0]
    name = B.exact(stream, size).decode("utf-8")
    B.exact(stream, -stream.tell() % 4)
    tail = B.exact(stream, 3)
    if stream.tell() != len(body):
        raise ValueError("original prefab GameObject tail drift")
    if authored_root is not None:
        # nova_bridge.stage_enemy_spine extracts one original scene director
        # into this authored prefab; Unity uses the prefab filename at its root.
        if authored_root != "EnemyClosure/FastDirector.prefab" or name != "Director":
            raise ValueError("unknown authored prefab root or original name")
        name = "FastDirector"
    name = name.replace("(Clone)", "").replace("(Instance)", "").strip() or "GameObject"
    name = "".join("_" if char in ",[]:/" or ord(char) < 32 else char for char in name)
    result = io.BytesIO()
    result.write(body[:start])
    aligned_string(result, name)
    result.write(tail)
    return result.getvalue()


def rebuild_bezier_line(body, sources, source_profiles, line_selector, behaviour_selector, wind_angles=None, build_rounding=None):
    """Re-evaluate an original BezierCurveLine using Unity float32 Lerp.

    Called before PPtr relocation. Geometry operands come from original records;
    optional numeric angles preserve our build wind state. Source schemas locate
    the line array and declare the curve field contract.
    Original local TRS operands are evaluated leaf-to-root with float32 rounding.
    """
    import math

    records = module("record_produce")
    schema = records.SCHEMA

    def single(value):
        value = struct.unpack("<f", struct.pack("<f", value))[0]
        if not math.isfinite(value):
            raise ValueError("nonfinite original Bezier operand")
        return value

    def read(selector, class_id):
        data, typ = source_record(sources, selector)
        if typ["class_id"] != class_id:
            raise ValueError("original Bezier record class drift")
        return data, typ

    line, line_type = read(line_selector, 120)
    curve, curve_type = read(behaviour_selector, 114)
    source = line_selector[0]
    if behaviour_selector[0] != source or body != line:
        raise ValueError("Bezier curve must belong to original line member")
    _, spans = records.fields(line, schema.type_tree(io.BytesIO(line_type["tree"])))
    start, end = spans[("m_Positions",)]
    count = struct.unpack_from("<I", line, start)[0]
    if not 2 <= count <= 100000 or end - start != 4 + count * 12:
        raise ValueError("original line position array drift")
    _, fields = records.fields(curve, schema.type_tree(io.BytesIO(curve_type["tree"])))
    names = [node.name for node in schema.type_tree(io.BytesIO(curve_type["tree"])).children]
    if names[-7:] != ["v0", "p1", "v1", "endTransform", "animateBezierWind", "windMagnitude", "windFrequency"]:
        raise ValueError("original BezierCurveLine schema drift")
    if (
        len(curve) != 108
        or fields[("v0",)] != (32, 44)
        or fields[("p1",)] != (44, 56)
        or fields[("v1",)] != (56, 68)
        or fields[("endTransform",)] != (68, 80)
        or fields[("animateBezierWind",)] != (80, 84)
    ):
        raise ValueError("original BezierCurveLine body layout drift")
    if curve[80] != 0:
        if not isinstance(wind_angles, list) or len(wind_angles) != 3:
            raise ValueError("animated Bezier wind requires captured build angles")
        wind_angles = tuple(single(value) for value in wind_angles)
    elif wind_angles is not None:
        raise ValueError("captured wind requires an animated original curve")
    go_pointer = struct.unpack_from("<iq", line)
    if go_pointer != struct.unpack_from("<iq", curve) or go_pointer[0] or not go_pointer[1]:
        raise ValueError("original curve/line GameObject differs")
    go, _ = read([source, go_pointer[1]], 1)
    components = [struct.unpack_from("<iq", go, 4 + i * 12) for i in range(struct.unpack_from("<I", go)[0])]
    if any(file_id for file_id, _ in components) or components.count((0, line_selector[1])) != 1 or components.count((0, behaviour_selector[1])) != 1:
        raise ValueError("original curve/line component membership drift")
    transforms = [pid for _, pid in components if source_record(sources, [source, pid])[1]["class_id"] == 4]
    if len(transforms) != 1:
        raise ValueError("original Bezier GameObject transform differs")
    transform, _ = read([source, transforms[0]], 4)
    if struct.unpack_from("<iq", transform) != go_pointer:
        raise ValueError("original Bezier transform belongs to another GameObject")
    # The script record is already selected for source-derived scene metadata.
    file_id, pid = struct.unpack_from("<iq", curve, 16)
    meta = sources[source][3]
    if not 0 <= file_id <= len(meta["externals"]):
        raise ValueError("original Bezier script link drift")
    member = source_profiles[source]["member"] if not file_id else meta["externals"][file_id - 1]["path"].rsplit("/", 1)[-1]
    script_sources = [i for i, selected in enumerate(source_profiles) if selected["member"] == member and pid in sources[i][4]]
    if len(script_sources) != 1:
        raise ValueError("original Bezier script provider differs")
    script, _ = read([script_sources[0], pid], 115)
    if script_fields(script)[1] != ("BezierCurveLine", "", "RoR2.dll"):
        raise ValueError("original Bezier script identity differs")

    def world(identity):
        position = (0.0, 0.0, 0.0)
        seen = set()
        while identity:
            if identity in seen:
                raise ValueError("original transform parent cycle")
            seen.add(identity)
            transform, transform_type = source_record(sources, [source, identity])
            if transform_type["class_id"] not in (4, 224):
                raise ValueError("original Bezier record class drift (ancestor)")
            children = struct.unpack_from("<I", transform, 52)[0]
            if len(transform) != 68 + children * 12 + (40 if transform_type["class_id"] == 224 else 0):
                raise ValueError("original Bezier transform layout drift")
            local = struct.unpack_from("<3f", transform, 28)
            scale = struct.unpack_from("<3f", transform, 40)
            x, y, z, w = (single(value) for value in struct.unpack_from("<4f", transform, 12))
            x2, y2, z2 = single(x + x), single(y + y), single(z + z)
            xx, yy, zz = single(x * x2), single(y * y2), single(z * z2)
            xy, xz, yz = single(x * y2), single(x * z2), single(y * z2)
            wx, wy, wz = single(w * x2), single(w * y2), single(w * z2)
            rotation = (
                (single(1 - single(yy + zz)), single(xy - wz), single(xz + wy)),
                (single(xy + wz), single(1 - single(xx + zz)), single(yz - wx)),
                (single(xz - wy), single(yz + wx), single(1 - single(xx + yy))),
            )
            scaled = tuple(single(value * factor) for value, factor in zip(position, scale))
            position = tuple(
                single(single(single(single(row[0] * scaled[0]) + single(row[1] * scaled[1])) + single(row[2] * scaled[2])) + offset)
                for row, offset in zip(rotation, local)
            )
            father_file, identity = struct.unpack_from("<iq", transform, 56 + children * 12)
            if father_file:
                raise ValueError("original Bezier parent escapes source scene")
        return position

    p0 = world(transforms[0])
    end_file, end_id = struct.unpack_from("<iq", curve, 68)
    if end_file:
        raise ValueError("original Bezier endTransform escapes source scene")
    p1 = world(end_id) if end_id else struct.unpack_from("<3f", curve, 44)
    v0, v1 = struct.unpack_from("<3f", curve, 32), struct.unpack_from("<3f", curve, 56)

    if wind_angles is not None:
        magnitude = struct.unpack_from("<3f", curve, 84)
        frequency = struct.unpack_from("<3f", curve, 96)
        delta = tuple(single(single(single(math.pi / 180) * endpoint) * rate) for endpoint, rate in zip((p1[0], p1[2], p1[1]), frequency))
        v0 = tuple(single(value + single(single(math.sin(angle)) * scale)) for value, angle, scale in zip(v0, wind_angles, magnitude))
        v1 = tuple(
            single(value + single(single(math.sin(single(angle + step))) * scale)) for value, angle, step, scale in zip(v1, wind_angles, delta, magnitude)
        )

    def add(a, b):
        return tuple(single(x + y) for x, y in zip(a, b))

    def lerp(a, b, t):
        return tuple(single(x + single(single(y - x) * t)) for x, y in zip(a, b))

    positions = bytearray()
    for index in range(count):
        t = single(index / (count - 1))
        a = lerp(p0, add(p0, v0), t)
        b = lerp(p1, add(p1, v1), single(1.0 - t))
        positions.extend(struct.pack("<3f", *lerp(a, b, t)))
    # Captured build arithmetic words are scoped to the checked original curve.
    # The complete geometry is still evaluated above from the legitimate input.
    for capture in build_rounding or []:
        word = capture["word"]
        if not isinstance(word, int) or not 0 <= word < count * 3:
            raise ValueError("captured Bezier rounding word outside original array")
        offset = word * 4
        if struct.unpack_from("<I", positions, offset)[0] != capture["evaluated_bits"]:
            raise ValueError("captured Bezier rounding operand drift")
        replacement = struct.pack("<I", capture["build_bits"])
        single(struct.unpack("<f", replacement)[0])
        positions[offset : offset + 4] = replacement
    return body[: start + 4] + positions + body[end:]


def aligned_string(stream, value):
    data = value.encode("utf-8")
    stream.write(struct.pack("<I", len(data)) + data)
    W.padding(stream, 4)


def asset_bundle(selected, identities):
    """Build Unity's release AssetBundle metadata, without target body literals."""
    stream = io.BytesIO()
    aligned_string(stream, selected["name"])
    scene = "scene_path" in selected
    if scene:
        preload = []
        assets = [{"path": selected["scene_path"], "root": 0, "preload": []}]
    elif "assets" in selected:
        assets = selected["assets"]
        preload = [pointer for asset in assets for pointer in asset["preload"]]
        if any(file_id == 0 and path_id not in identities for file_id, path_id in preload):
            raise ValueError("container preload references an absent local object")
    else:
        local = [(0, identity) for identity in sorted(identities)]
        external = selected["external_objects"]
        preload = external + local if selected.get("external_preload_first", False) else local + external
        assets = [{"path": selected["asset"], "root": selected["root"], "preload": preload}]
    stream.write(struct.pack("<I", len(preload)))
    for file_id, path_id in preload:
        stream.write(struct.pack("<iq", file_id, path_id))
    stream.write(struct.pack("<I", len(assets)))
    start = 0
    containers = []
    for asset in assets:
        if not scene and asset["root"] not in identities:
            raise ValueError("container root references an absent local object")
        containers.append((asset, start))
        start += len(asset["preload"])
    for asset, start in sorted(containers, key=lambda item: item[0]["path"].lower()):
        aligned_string(stream, asset["path"] if scene else asset["path"].lower())
        stream.write(struct.pack("<iiiq", start, len(asset["preload"]), 0, asset["root"]))
    stream.write(struct.pack("<iiiqI", 0, 0, 0, 0, 1))
    aligned_string(stream, "" if scene else selected["name"])
    dependencies = [] if scene else selected["dependencies"]
    stream.write(struct.pack("<I", len(dependencies)))
    for dependency in dependencies:
        aligned_string(stream, dependency)
    # Release bundle: streamed-scene marker, explicit layout off, path flags.
    stream.write(struct.pack("<B3xiii", scene, 0, 7, 0))
    return stream.getvalue()


def preload_data(bundle, selected, members, packed=None):
    """Collect scene dependencies from checked relocated external PPtrs."""
    references = set()
    names = {member["name"] for member in members}
    for member in members:
        for row in member["objects"]:
            dependencies = packed.get((member["name"], row["path_id"]), (None, {}))[1].get("dependencies", []) if packed else []
            relocations = row.get("record_references", [])
            moved = {}
            for reference in relocations:
                original = tuple(reference["from"])
                if original in moved and moved[original] != reference["to"]:
                    raise ValueError("ambiguous produced dependency relocation")
                moved[original] = reference["to"]
            dependencies = [{**ref, "to": moved.get(tuple(ref["to"]), ref["to"])} for ref in dependencies]
            for reference in [*row.get("references", []), *relocations, *dependencies]:
                file_id, path_id = reference["to"]
                if not file_id or not path_id:
                    continue
                if not 1 <= file_id <= len(member["externals"]):
                    raise ValueError("scene reference has an absent external file")
                name = member["externals"][file_id - 1]
                if name not in names:
                    references.add((selected["externals"].index(name) + 1, path_id))
    for dependency in bundle.get("preload_dependencies", []):
        file_id, path_id = dependency["to"]
        if not 1 <= file_id <= len(selected["externals"]) or not path_id:
            raise ValueError("original preload dependency has an absent destination")
        if "source" not in dependency and selected["externals"][file_id - 1].rsplit("/", 1)[-1] != "unity default resources":
            raise ValueError("original preload builtin destination drift")
        references.add((file_id, path_id))
    stream = io.BytesIO()
    aligned_string(stream, "")
    stream.write(struct.pack("<I", len(references)))
    for pointer in sorted(references):
        stream.write(struct.pack("<iq", *pointer))
    stream.write(struct.pack("<I", len(bundle["dependencies"])))
    for name in bundle["dependencies"]:
        aligned_string(stream, name)
    stream.write(bytes(1))
    return stream.getvalue()


def json_layout(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: json_layout(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_layout(item) for item in value]
    return value


def make_layout(selected, records, scene_members=(), engine="2021.3.45f2"):
    """Canonical release order: script records first, then remaining path IDs."""
    local_scripts = sorted(row["path_id"] for row in records if row["type"]["class_id"] == 115)
    scripts = (
        sorted({pointer for row in records if row["type"]["class_id"] == 114 if (pointer := struct.unpack_from("<iq", row["body"], 16)) != (0, 0)})
        if scene_members
        else [(0, identity) for identity in local_scripts]
    )
    physical = sorted(records, key=lambda row: (row["path_id"] not in local_scripts, row["path_id"]))
    types, objects, bodies = [], [], {}
    offset = 0
    for row in physical:
        typ = copy.deepcopy(row["type"])
        null_script = False
        if typ["class_id"] == 114:
            file_id, script = struct.unpack_from("<iq", row["body"], 16)
            if (file_id, script) == (0, 0):
                if not scene_members or len(row["body"]) != 32 or typ["script_type"] != -1 or typ["hash"] != bytes(16) or typ["script_id"] != bytes(16):
                    raise ValueError("original null-script MonoBehaviour metadata drift")
                null_script = True
            else:
                if (file_id and not scene_members) or (not file_id and script not in local_scripts) or not 0 <= file_id <= len(selected["externals"]):
                    raise ValueError("MonoBehaviour script absent from produced bundle")
                typ["script_type"] = scripts.index((file_id, script))
        # Unity retains an individual type slot for each missing-script component.
        if null_script or typ not in types:
            types.append(typ)
        type_id = len(types) - 1 if null_script else types.index(typ)
        offset = (offset + 7) // 8 * 8
        identity = row["path_id"]
        if identity in bodies:
            raise ValueError("duplicate produced object identity")
        bodies[identity] = row["body"]
        objects.append({"path_id": identity, "offset": offset, "bytes": len(row["body"]), "type_id": type_id})
        offset += len(row["body"])
    # Unity's native resources live outside the AssetBundles.
    native = {"Resources/unity_builtin_extra": 0x0F, "Library/unity default resources": 0x0E}
    externals = [
        {"empty": "", "guid": bytes(8) + bytes([native[name]]) + bytes(7), "type": 0, "path": name}
        if name in native
        else {
            "empty": "",
            "guid": bytes(16),
            "type": 0,
            "path": "archive:/" + (name.removesuffix(".sharedAssets") if name in scene_members else name) + "/" + name,
        }
        for name in selected["externals"]
    ]
    return {
        "engine": engine,
        "platform": 13,
        "trees": True,
        "types": types,
        "objects": sorted(objects, key=lambda row: row["path_id"]),
        "scripts": scripts,
        "externals": externals,
        "ref_types": [],
        "user": "",
    }, bodies


def record_packs(members, supplied, bundle):
    """Read selected independently produced records; receipts pin their providers."""
    selections = [(member["name"], row) for member in members for row in member["objects"]]
    required = {row["record"] for _, row in selections if "record" in row}
    records, providers = {}, {}
    for directory, receipt_sha256 in supplied:
        directory = Path(directory).resolve(strict=True)
        receipt = directory / "result.json"
        if B.sha(receipt) != receipt_sha256:
            raise ValueError("record producer receipt drift")
        value = json.loads(receipt.read_text())
        profile = value.get("profile_sha256")
        if value.get("success") is not True or value.get("input_id") != M.INPUT_ID or profile not in required or profile in providers:
            raise ValueError("unexpected or unsuccessful record producer")
        if not {"objects.bin", "index.jsonl"} <= value["outputs"].keys() or value["outputs"].keys() - {"objects.bin", "resources.bin", "index.jsonl"}:
            raise ValueError("incomplete record producer outputs")
        providers[profile] = directory, receipt_sha256, value
    if providers.keys() != required:
        raise ValueError("missing source-produced record pack")
    check_record_packs(providers)
    for profile, (directory, _, _) in providers.items():
        wanted = {(member, row["path_id"]) for member, row in selections if row.get("record") == profile}
        with (directory / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                key = row["member"], row["path_id"]
                if row["bundle"] != bundle["name"] or key not in wanted:
                    continue
                if key in records:
                    raise ValueError("duplicate produced record identity")
                records[key] = directory, row
        if not wanted <= records.keys():
            raise ValueError("produced record missing")
    return records, providers


def check_record_packs(providers):
    for directory, receipt_sha256, value in providers.values():
        for name, pin in value["outputs"].items():
            path = directory / name
            if path.stat().st_size != pin["bytes"] or B.sha(path) != pin["sha256"]:
                raise ValueError("record producer output drift")
        if B.sha(directory / "result.json") != receipt_sha256:
            raise ValueError("record producer receipt drift")


def record_extent(path, row):
    offset, size = row["offset"], row["bytes"]
    if type(offset) is not int or type(size) is not int or offset < 0 or not 0 <= size <= B.LIMIT or offset + size > path.stat().st_size:
        raise ValueError("produced record extent escapes pack")
    with path.open("rb") as stream:
        stream.seek(offset)
        data = B.exact(stream, size)
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("produced record extent drift")
    return data


def source_record(sources, selector):
    source, identity = selector
    _, _, member, metadata, objects = sources[source]
    row = objects[identity]
    member.seek(metadata["data_offset"] + row["offset"])
    return B.exact(member, row["bytes"]), metadata["types"][row["type_id"]]


def check_preload_dependencies(sources, source_profiles, dependencies):
    """Admit original preload GameObjects, direct managed roots and builtins."""
    for dependency in dependencies:
        preload, preload_type = source_record(sources, dependency["preload_source"])
        if preload_type["class_id"] != 150 or hashlib.sha256(preload).hexdigest() != dependency["preload_sha256"]:
            raise ValueError("original scene preload drift")
        stream = io.BytesIO(preload)
        size = B.unpack(stream, "<I")[0]
        B.exact(stream, size)
        stream.seek((stream.tell() + 3) // 4 * 4)
        count = B.unpack(stream, "<I")[0]
        pointers = [B.unpack(stream, "<iq") for _ in range(count)]
        pointer = tuple(dependency["source_pointer"])
        metadata = sources[dependency["preload_source"][0]][3]
        file_id, path_id = pointer
        if not 0 <= file_id <= len(metadata["externals"]):
            raise ValueError("original preload external file drift")
        member = metadata["externals"][file_id - 1]["path"].rsplit("/", 1)[-1] if file_id else source_profiles[dependency["preload_source"][0]]["member"]
        if "source" not in dependency:
            if not file_id or member != "unity default resources" or pointers.count(pointer) != 1 or not path_id or dependency["to"][1] != path_id:
                raise ValueError("original preload builtin relationship drift")
            continue
        body, typ = source_record(sources, dependency["source"])
        source_class = dependency.get("source_class_id", 1)
        if source_class not in (1, 114) or typ["class_id"] != source_class or hashlib.sha256(body).hexdigest() != dependency["source_sha256"]:
            raise ValueError("original preload GameObject drift")
        selector = dependency["source"]
        if any(kind in dependency for kind in ("rigidbody", "transform", "animator")):
            if source_class != 1:
                raise ValueError("original preload component owner is not a GameObject")
            kind, class_id, size = (
                ("Rigidbody", 54, 36) if "rigidbody" in dependency else ("Animator", 95, 56) if "animator" in dependency else ("Transform", 4, 68)
            )
            witness = dependency[kind.lower()]
            component_body, component_type = source_record(sources, witness["source"])
            if component_type["class_id"] != class_id or len(component_body) != size or hashlib.sha256(component_body).hexdigest() != witness["sha256"]:
                raise ValueError(f"original preload {kind} drift")
            if witness["source"][0] != selector[0] or struct.unpack_from("<iq", component_body) != (0, selector[1]):
                raise ValueError(f"original preload {kind} GameObject drift")
            count = struct.unpack_from("<I", body)[0]
            if 4 + count * 12 > len(body):
                raise ValueError("truncated original preload GameObject components")
            components = [struct.unpack_from("<iq", body, 4 + i * 12) for i in range(count)]
            index = witness["component_index"]
            component = (0, witness["source"][1])
            if type(index) is not int or not 0 <= index < count or components[index] != component or components.count(component) != 1:
                raise ValueError(f"original preload {kind} component membership drift")
            selector = witness["source"]
        if pointers.count(pointer) != 1 or path_id != selector[1] or member != source_profiles[selector[0]]["member"]:
            raise ValueError("original preload GameObject relationship drift")


def legacy_animate_fields(body, tree, identity_owner):
    """Project current zero-valued additions to the J133 retained field shape."""
    nodes = identity_owner.tree_nodes(tree)
    top = [i for i, node in enumerate(nodes) if node["level"] == 1]
    names = [nodes[i]["name"] for i in top]
    required = ["disableObjectOnEnd", "resetOnEnable"]
    present = [name for name in required if name in names]
    if not present:
        if names.count("disableOnEnd") != 1 or names.count("time") != 1 or names.index("time") != names.index("disableOnEnd") + 1:
            raise ValueError("original legacy AnimateShaderAlpha field order drift")
        return body, tree
    if present != required or any(names.count(name) != 1 for name in required):
        raise ValueError("original AnimateShaderAlpha field membership drift")
    first = names.index(required[0])
    if first == 0 or names[first - 1 : first + 3] != ["disableOnEnd", *required, "time"]:
        raise ValueError("original AnimateShaderAlpha field order drift")
    indices = [top[first], top[first + 1]]
    for index in indices:
        node = nodes[index]
        if node["type"] != "UInt8" or node["size"] != 1 or not node["meta"] & 0x4000 or index + 1 < len(nodes) and nodes[index + 1]["level"] > 1:
            raise ValueError("original AnimateShaderAlpha field schema drift")
    records = module("record_produce")
    _, spans = records.fields(body, records.SCHEMA.type_tree(io.BytesIO(tree)))
    ranges = [spans[(name,)] for name in required]
    if ranges[0][1] != ranges[1][0] or any(end - start != 4 or body[start:end] != bytes(4) for start, end in ranges):
        raise ValueError("original AnimateShaderAlpha fields must be zero aligned values")
    count, _ = struct.unpack_from("<II", tree)
    buffer = tree[8 + count * 32 :]
    rows = [list(struct.unpack_from("<HBBIIiiiQ", tree, 8 + i * 32)) for i in range(count)]
    removed = []
    for index in indices:
        start = rows[index][4]
        if start & 0x80000000:
            raise ValueError("original AnimateShaderAlpha field label drift")
        end = buffer.index(bytes(1), start) + 1
        removed.append((start, end))
    remaining = [row for i, row in enumerate(rows) if i not in indices]
    for i, row in enumerate(remaining):
        row[6] = i
        for k in (3, 4):
            offset = row[k]
            if offset & 0x80000000:
                continue
            if any(start <= offset < end for start, end in removed):
                raise ValueError("omitted AnimateShaderAlpha label is still referenced")
            row[k] -= sum(end - start for start, end in removed if end <= offset)
    chunks, cursor = [], 0
    for start, end in sorted(removed):
        chunks.append(buffer[cursor:start])
        cursor = end
    chunks.append(buffer[cursor:])
    strings = b"".join(chunks)
    projected = struct.pack("<II", len(remaining), len(strings)) + b"".join(struct.pack("<HBBIIiiiQ", *row) for row in remaining) + strings
    return body[: ranges[0][0]] + body[ranges[-1][1] :], projected


def legacy_animate_hash_tree(tree, sdk_tree, identity_owner):
    """Hash SDK editor Curve/Keyframe nodes; preserve serialized runtime schema."""
    source = identity_owner.tree_nodes(tree)
    native = identity_owner.tree_nodes(sdk_tree)

    def extent(nodes, index):
        end = index + 1
        while end < len(nodes) and nodes[end]["level"] > nodes[index]["level"]:
            end += 1
        return end

    src = [i for i, node in enumerate(source) if node["type"] == "AnimationCurve" and node["name"] == "alphaCurve"]
    sdk = [i for i, node in enumerate(native) if node["type"] == "AnimationCurve" and node["name"] == "m_Falloff"]
    if len(src) != 1 or len(sdk) != 1:
        raise ValueError("original/SDK AnimateShaderAlpha curve schema absent")
    i, j = src[0], sdk[0]
    end = extent(source, i)
    shift = source[i]["level"] - native[j]["level"]
    editor = [{**node, "level": node["level"] + shift} for node in native[j : extent(native, j)]]
    editor[0]["name"] = source[i]["name"]
    key = [k for k, node in enumerate(editor) if node["type"] == "Keyframe"]
    tangent = [k for k, node in enumerate(editor) if node["name"] == "tangentMode"]
    if len(key) != 1 or len(tangent) != 1 or editor[key[0]]["size"] != 32 or editor[tangent[0]]["type"] != "int" or editor[tangent[0]]["size"] != 4:
        raise ValueError("SDK editor Keyframe tangent schema drift")
    runtime = [dict(node) for k, node in enumerate(editor) if k != tangent[0]]
    runtime[key[0]]["size"] -= 4
    if runtime != source[i:end]:
        raise ValueError("original runtime AnimationCurve differs from SDK editor projection")
    revised = source[:i] + editor + source[end:]
    strings = bytearray()
    labels = {}

    def label(value):
        if value not in labels:
            labels[value] = len(strings)
            strings.extend(value.encode() + bytes(1))
        return labels[value]

    rows = [
        struct.pack("<HBBIIiiiQ", n["version"], n["level"], n["flags"], label(n["type"]), label(n["name"]), n["size"], k, n["meta"], 0)
        for k, n in enumerate(revised)
    ]
    return struct.pack("<II", len(rows), len(strings)) + b"".join(rows) + strings


def omit_character_master_field(tree, identity_owner):
    """Remove only the measured final original debug field from its native schema."""
    nodes = identity_owner.tree_nodes(tree)
    node = nodes[-1]
    count, length = struct.unpack_from("<II", tree)
    end = 8 + 32 * count
    suffix = b"isUnkillable\0"
    if (
        (node["name"], node["type"], node["level"], node["size"]) != ("isUnkillable", "UInt8", 1, 1)
        or not node["meta"] & 0x4000
        or not tree[end:].endswith(suffix)
    ):
        raise ValueError("original CharacterMaster final field drift")
    for offset in range(8, end - 32, 32):
        for position in (offset + 4, offset + 8):
            label = struct.unpack_from("<I", tree, position)[0]
            if not label & 0x80000000 and label >= length - len(suffix):
                raise ValueError("original CharacterMaster final field string is shared")
    return struct.pack("<II", count - 1, length - len(suffix)) + tree[8 : end - 32] + tree[end : -len(suffix)]


def omit_run_presence_counters(tree, identity_owner):
    """Retain the original RunPresence fields preceding its two cached counters."""
    nodes = identity_owner.tree_nodes(tree)
    if [(n["name"], n["type"], n["level"], n["size"]) for n in nodes[-2:]] != [
        ("cachedActiveCount", "int", 1, 4),
        ("cachedInActiveCount", "int", 1, 4),
    ]:
        raise ValueError("original RunPresence cached counter schema drift")
    return identity_owner._tree(nodes[:-2])


def script_fields(body):
    """Read original release MonoScript identity and its properties-hash extent."""
    stream = io.BytesIO(body)

    def string():
        size = struct.unpack("<I", B.exact(stream, 4))[0]
        value = B.exact(stream, size).decode("utf-8")
        stream.seek((stream.tell() + 3) // 4 * 4)
        return value

    string()  # m_Name
    B.exact(stream, 4)  # m_ExecutionOrder
    offset = stream.tell()
    B.exact(stream, 16)
    return offset, (string(), string(), string())


def fieldless_script_type(body, typ, script, sdk_tree, identity_owner):
    """Derive a fieldless component's metadata from its qualified MonoScript."""
    if typ["class_id"] != 114 or len(body) != 32 or body[28:] != bytes(4):
        raise ValueError("fieldless script requires the original empty-name base component")
    nodes = identity_owner.tree_nodes(typ["tree"])
    fields = [n["name"] for n in nodes if n["level"] == 1]
    if fields != ["m_GameObject", "m_Enabled", "m_Script", "m_Name"]:
        raise ValueError("fieldless script prototype has custom fields")
    offset, names = script_fields(script)
    properties = identity_owner.properties_hash(*names, typ["tree"], sdk_tree)
    if properties != script[offset : offset + 16]:
        raise ValueError("fieldless schema differs from produced MonoScript properties")
    return {**typ, "hash": properties, "script_id": identity_owner.md4("".join(names).encode())}


def copy_original_bundle(profile, profile_sha256, pc, output):
    """Preserve prepare.py's original Windows bundle copy without a project."""
    if set(profile) != {"input_id", "original_bundle"}:
        raise ValueError("unknown original bundle profile")
    selected = profile["original_bundle"]
    if set(selected) != {"path", "bytes", "sha256"} or not 0 < selected["bytes"] <= B.LIMIT:
        raise ValueError("invalid original bundle selection")
    pc = pc.resolve(strict=True)
    source = M.safe_input(pc, selected["path"])
    output = output.parent.resolve(strict=True) / output.name
    if output.exists() or output.is_symlink() or output.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("original bundle output must be new and outside original input")
    before = source.stat()
    if before.st_size != selected["bytes"] or B.sha(source) != selected["sha256"]:
        raise ValueError("original bundle input drift")
    if shutil.disk_usage(output.parent).free < selected["bytes"] + 2 * 1024**3:
        raise ValueError("insufficient original bundle output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": profile["input_id"], "profile_sha256": profile_sha256}
    try:
        destination = output / "payload/windows-shaders.bundle"
        destination.parent.mkdir()
        shutil.copyfile(source, destination)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or B.sha(source) != selected["sha256"]:
            raise ValueError("original bundle changed during production")
        if destination.stat().st_size != selected["bytes"] or B.sha(destination) != selected["sha256"]:
            raise ValueError("persisted original bundle differs")
        receipt["outputs"] = {"payload/windows-shaders.bundle": {"bytes": selected["bytes"], "sha256": selected["sha256"]}}
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def custom_reflection_probe(body, typ):
    """Retain the authored baked-to-Custom mode adapter; relocate textures separately."""
    if typ["class_id"] != 215:
        raise ValueError("custom reflection policy requires an original ReflectionProbe")
    records = module("record_produce")
    root = records.SCHEMA.type_tree(io.BytesIO(typ["tree"]))
    _, fields = records.fields(body, root)
    if ("m_Mode",) not in fields or ("m_CustomBakedTexture",) not in fields:
        raise ValueError("original reflection mode/texture fields missing")
    start, end = fields[("m_Mode",)]
    texture_start, texture_end = fields[("m_CustomBakedTexture",)]
    if end - start != 4 or body[start:end] != bytes(4):
        raise ValueError("original reflection mode is not Baked")
    if texture_end - texture_start != 12 or body[texture_start:texture_end] != bytes(12):
        raise ValueError("original custom reflection texture is not null")
    return body[:start] + struct.pack("<i", 2) + body[end:]


def strip_compute_programs(body, typ):
    """Remove original DXBC compute resources while retaining native declarations.

    This is the observed class-72 projection, not executable Android compute.
    Existing source-schema spans identify arrays; no target bytes are inputs.
    """
    if typ["class_id"] != 72:
        raise ValueError("compute projection requires original ComputeShader")
    records = module("record_produce")
    root = records.SCHEMA.type_tree(io.BytesIO(typ["tree"]))
    if [child.name for child in root.children] != ["m_Name", "variants"]:
        raise ValueError("original ComputeShader schema drift")
    _, fields = records.fields(body, root)
    edits = []

    def extent(path):
        if path not in fields:
            raise ValueError("original ComputeShader field missing")
        return fields[path]

    def count(path):
        start, end = extent(path)
        if end - start < 4:
            raise ValueError("truncated original ComputeShader array")
        return struct.unpack_from("<I", body, start)[0]

    def clear(path):
        start, end = extent(path)
        count(path)
        edits.append((start, end, bytes(4)))

    if count(("variants",)) != 1:
        raise ValueError("only the observed single compute renderer is qualified")
    variant = ("variants", "Array", "0")
    for name, value in (("targetRenderer", 2), ("targetLevel", 0)):
        start, end = extent(variant + (name,))
        if body[start:end] != struct.pack("<I", value):
            raise ValueError("original compute renderer/level drift")
    start, end = extent(variant + ("resourcesResolved",))
    if body[start:end] != b"\x01\0\0\0":
        raise ValueError("original compute resources are not resolved")
    clear(variant + ("constantBuffers",))
    kernel_count = count(variant + ("kernels",))
    programs = 0
    for kernel in range(kernel_count):
        parent = variant + ("kernels", "Array", str(kernel), "variantMap")
        for index in range(count(parent)):
            pair = parent + ("Array", str(index))
            # The native map value is a common-string label; select its actual
            # schema path through its direct code field, never a guessed offset.
            candidates = [path[:-1] for path in fields if len(path) == len(pair) + 2 and path[: len(pair)] == pair and path[-1] == "code"]
            if len(candidates) != 1:
                raise ValueError("original compute program schema drift")
            program = candidates[0]
            arrays = ("cbVariantIndices", "cbs", "textures", "builtinSamplers", "inBuffers", "outBuffers", "code")
            names = {path[-1] for path in fields if len(path) == len(program) + 1 and path[:-1] == program}
            if names != set(arrays) | {"threadGroupSize", "requirements"}:
                raise ValueError("original compute program fields differ")
            start, end = extent(program + ("code",))
            size = count(program + ("code",))
            if size < 4 or end - start != (4 + size + 3) // 4 * 4 or body[start + 4 : start + 8] != b"DXBC":
                raise ValueError("original compute program is not DXBC")
            for name in arrays:
                clear(program + (name,))
            start, end = extent(program + ("threadGroupSize",))
            if end - start != 16 or count(program + ("threadGroupSize",)) != 3:
                raise ValueError("original compute thread group dimensions differ")
            edits.append((start, end, body[start : start + 4] + bytes(12)))
            programs += 1
    if not programs:
        raise ValueError("original ComputeShader has no compiled programs")
    result, cursor = bytearray(), 0
    for start, end, replacement in sorted(edits):
        if start < cursor:
            raise ValueError("overlapping original compute field spans")
        result.extend(body[cursor:start])
        result.extend(replacement)
        cursor = end
    result.extend(body[cursor:])
    return bytes(result)


def plugin_import_order(body):
    """Use PluginImporter's default for the selected original RoR2 DLL script."""
    offset, names = script_fields(body)
    if names[2] not in {"RoR2.dll", "AK.Wwise.Unity.MonoBehaviour.dll", "Unity.TextMeshPro.dll"}:
        raise ValueError("plugin import order requires an admitted original DLL script")
    return body[: offset - 4] + bytes(4) + body[offset:]


def default_material(selected, sources, sdk, output):
    """Reuse the player owner's SDK Material / original Shader projection."""
    if sdk is None:
        raise ValueError("default material requires the pinned owner SDK")
    source = selected["sdk_source"]
    path = M.safe_input(sdk.resolve(strict=True), source["path"])
    if output.is_relative_to(sdk.resolve()) or B.sha(path) != source["sha256"]:
        raise ValueError("SDK default material drift or output overlap")
    with path.open("rb") as stream:
        stream.size = path.stat().st_size
        metadata = W.read_serialized(stream)
        row = next(row for row in metadata["objects"] if row["path_id"] == source["path_id"])
        definition = metadata["types"][row["type_id"]]
        stream.seek(metadata["data_offset"] + row["offset"])
        body = B.exact(stream, row["bytes"])
    shader, shader_type = source_record(sources, selected["shader_source"])
    if definition["class_id"] != 21 or shader_type["class_id"] != 48:
        raise ValueError("default material requires SDK Material and original Shader")
    body = module("player_data").shared_default_material(body, definition, shader)
    if B.sha(path) != source["sha256"]:
        raise ValueError("SDK default material changed during production")
    return remap(body, selected.get("references", []))


def produce(profile_path, profile_sha256, pc, output, codec_path, codec_sha256, packs=(), sdk=None):
    if B.sha(profile_path) != profile_sha256:
        raise ValueError("object profile drift")
    profile = json.loads(profile_path.read_text())
    if "original_bundle" in profile:
        if profile["input_id"] != M.INPUT_ID:
            raise ValueError("unknown original bundle input")
        return copy_original_bundle(profile, profile_sha256, pc, output)
    if codec_path is None or codec_sha256 is None:
        raise ValueError("object serialization requires the pinned codec")
    scene = "members" in profile["bundle"]
    required = {"input_id", "sources", "bundle"} | (set() if scene else {"objects"})
    if set(profile) - {"sdk"} != required or profile["input_id"] != M.INPUT_ID:
        raise ValueError("unknown object input profile")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("object output must be new and outside original input")
    selected_bundle = profile["bundle"]
    engine = selected_bundle.get("engine", "2021.3.45f2")
    if engine not in ("2021.3.45f2", "2021.3.33f1"):
        raise ValueError("unqualified source bundle engine")
    selected_members = selected_bundle["members"] if scene else [{**selected_bundle, "name": selected_bundle["member"], "objects": profile["objects"]}]
    expected = sum(row["bytes"] for member in selected_members for row in member["objects"])
    if not 0 < expected <= B.LIMIT:
        raise ValueError("object bundle exceeds bounded producer capacity")
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient object output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": M.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0}
    try:
        sdk_path, sdk_tree = None, None
        if "sdk" in profile:
            if sdk is None:
                raise ValueError("script properties require the pinned owner SDK")
            sdk_path = M.safe_input(sdk.resolve(strict=True), profile["sdk"]["path"])
            if output.is_relative_to(sdk.resolve()) or B.sha(sdk_path) != profile["sdk"]["sha256"]:
                raise ValueError("SDK script metadata drift or output overlap")
            with sdk_path.open("rb") as stream:
                stream.size = sdk_path.stat().st_size
                metadata = W.read_serialized(stream)
            row = next(row for row in metadata["objects"] if row["path_id"] == profile["sdk"]["path_id"])
            typ = metadata["types"][row["type_id"]]
            if typ["class_id"] != 114:
                raise ValueError("SDK script base is not MonoBehaviour")
            sdk_tree = typ["tree"]
        properties = {}
        identity_owner = module("script_identity", Path(__file__).resolve().parents[3] / "scripts/lab/script_identity.py") if sdk_tree is not None else None
        sources = []
        for selected in profile["sources"]:
            path = M.safe_input(pc, selected["path"])
            before = path.stat()
            if B.sha(path) != selected["sha256"]:
                raise ValueError("original object bundle drift")
            member = source_member(path, selected["member"])
            metadata = W.read_serialized(member)
            sources.append((path, before, member, metadata, {row["path_id"]: row for row in metadata["objects"]}))
        check_preload_dependencies(sources, profile["sources"], selected_bundle.get("preload_dependencies", []))
        records, layouts, members = [], [], []
        packed, providers = record_packs(selected_members, packs, selected_bundle)
        receipt["record_packs"] = {profile: pin for profile, (_, pin, _) in providers.items()}
        resources = {}
        # Load only when needed: the player owner already shares this writer and
        # owns the qualified standalone Sprite recovery arithmetic.
        sprites = module("player_data") if any("importer_guid" in row for member in selected_members for row in member["objects"]) else None
        for selected_member in selected_members:
            member_records = []
            identities = [
                row["path_id"] for row in selected_member["objects"] if "source" in row or "record" in row or row.get("generate") == "DefaultMaterial"
            ]
            for selected in selected_member["objects"]:
                if "record" in selected:
                    directory, row = packed[selected_member["name"], selected["path_id"]]
                    body = record_extent(directory / "objects.bin", row)
                    source, identity = selected["type_source"]
                    typ = sources[source][3]["types"][sources[source][4][identity]["type_id"]]
                    if "record_references" in selected:
                        body = remap_record(body, typ, selected["record_references"], selected_member["externals"])
                    if "resource" in row:
                        resource = row["resource"]
                        extent = resource["stream"]
                        prefix = "archive:/" + selected_member["name"] + "/"
                        name = extent["path"].removeprefix(prefix)
                        if not extent["path"].startswith(prefix) or Path(name).name != name or name == selected_member["name"]:
                            raise ValueError("produced resource belongs to another bundle")
                        data = record_extent(directory / "resources.bin", resource)
                        offset, end = extent["offset"], extent["offset"] + len(data)
                        if extent["size"] != len(data) or offset < 0 or end > B.LIMIT:
                            raise ValueError("produced resource exceeds bounded bundle capacity")
                        resources.setdefault(name, []).append((offset, data))
                elif "source" in selected:
                    source, identity = selected["source"]
                    _, _, member, metadata, objects = sources[source]
                    row = objects[identity]
                    member.seek(metadata["data_offset"] + row["offset"])
                    body = B.exact(member, row["bytes"])
                    if hashlib.sha256(body).hexdigest() != selected["source_sha256"]:
                        raise ValueError("original object body drift")
                    typ = metadata["types"][row["type_id"]]
                    if "type_source" in selected:
                        _, schema = source_record(sources, selected["type_source"])
                        if (
                            typ.get("tree")
                            or not schema.get("tree")
                            or any(typ.get(key) != schema.get(key) for key in ("class_id", "stripped", "script_type", "hash", "script"))
                        ):
                            raise ValueError("native source schema identity differs")
                        typ = schema
                    if "custom_reflection_probe" in selected:
                        if selected["custom_reflection_probe"] is not True:
                            raise ValueError("custom reflection projection requires the named source policy")
                        body = custom_reflection_probe(body, typ)
                    if "strip_compute_programs" in selected:
                        if selected["strip_compute_programs"] is not True:
                            raise ValueError("compute projection requires the named source policy")
                        body = strip_compute_programs(body, typ)
                    if "remove_components" in selected:
                        if typ["class_id"] != 1:
                            raise ValueError("component omission requires an original GameObject")
                        body = remove_components(body, selected["remove_components"])
                    if "append_components" in selected:
                        if typ["class_id"] != 1 or any(identity not in identities for identity in selected["append_components"]):
                            raise ValueError("component addition requires an original GameObject and existing produced components")
                        body = append_components(body, selected["append_components"])
                    if "clear_static_renderers" in selected:
                        if typ["class_id"] != 29:
                            raise ValueError("static-renderer removal requires original OcclusionCullingSettings")
                        body = clear_static_renderers(body, selected["clear_static_renderers"])
                    if "bezier_curve_line" in selected:
                        body = rebuild_bezier_line(
                            body,
                            sources,
                            profile["sources"],
                            selected["source"],
                            selected["bezier_curve_line"],
                            selected.get("bezier_wind_angles"),
                            selected.get("bezier_build_rounding"),
                        )
                    if "importer_guid" in selected:
                        if typ["class_id"] != 213:
                            raise ValueError("Sprite importer policy requires an original Sprite")
                        if "crop_rectangle_offset" in selected:
                            body = sprites.sprite_crop(body, selected["crop_rectangle_offset"])
                        body = sprites.sprite_key(body, selected["importer_guid"])
                    if "inactive_map_zone" in selected:
                        if selected["inactive_map_zone"] is not True or typ["class_id"] != 1 or not body or body[-1] != 1:
                            raise ValueError("inactive MapZone policy requires an active original GameObject")
                        body = body[:-1] + bytes(1)
                    if "normalize_exported_prefab_name" in selected:
                        if typ["class_id"] != 1 or selected["normalize_exported_prefab_name"] is not True:
                            raise ValueError("exported prefab name requires an original GameObject")
                        body = normalize_exported_prefab_name(body)
                    if "authored_prefab_root" in selected:
                        if typ["class_id"] != 1 or selected["authored_prefab_root"] != "EnemyClosure/FastDirector.prefab":
                            raise ValueError("authored prefab root requires the named original GameObject")
                        body = normalize_exported_prefab_name(body, selected["authored_prefab_root"])
                    if "inactive_global_owner" in selected:
                        if typ["class_id"] != 1:
                            raise ValueError("global suppression requires an original GameObject")
                        body = deactivate_global_owner(body, selected["inactive_global_owner"])
                    if "disable_original_behaviour" in selected:
                        if selected["disable_original_behaviour"] is not True or typ["class_id"] != 114 or body[12:16] != b"\x01\0\0\0":
                            raise ValueError("disabled original behaviour requires an enabled MonoBehaviour")
                        body = body[:12] + bytes(1) + body[13:]
                    if "missing_script_base" in selected:
                        # A component whose script is absent from the build keeps only the base
                        # MonoBehaviour fields; Unity serializes it with the base (script-less) type.
                        base = selected["missing_script_base"]
                        if typ["class_id"] != 114 or set(base) != {"bytes", "type_source"} or not 0 < base["bytes"] <= len(body):
                            raise ValueError("missing-script base requires an original MonoBehaviour")
                        _, base_type = source_record(sources, base["type_source"])
                        if base_type["class_id"] != 114 or int(base_type["script_type"]) != -1:
                            raise ValueError("missing-script base requires the original base MonoBehaviour type")
                        body, typ = body[: base["bytes"]], copy.deepcopy(base_type)
                    if "plugin_import_default_execution_order" in selected:
                        if selected["plugin_import_default_execution_order"] is not True or typ["class_id"] != 115:
                            raise ValueError("plugin import order requires an original MonoScript")
                        body = plugin_import_order(body)
                    if "omit_animate_shader_alpha_legacy_fields" in selected:
                        if (
                            selected["omit_animate_shader_alpha_legacy_fields"] is not True
                            or typ["class_id"] not in (114, 115)
                            or "properties_hash" not in selected
                            or sdk_tree is None
                        ):
                            raise ValueError("legacy AnimateShaderAlpha policy requires source script properties")
                        if typ["class_id"] == 114:
                            body, schema = legacy_animate_fields(body, typ["tree"], identity_owner)
                            typ = {**typ, "tree": schema}
                    if "director_deck" in selected:
                        if typ["class_id"] != 114 or "properties_hash" not in selected or sdk_tree is None:
                            raise ValueError("director deck requires original script properties")
                        script, _ = source_record(sources, selected["properties_hash"]["script"])
                        if script_fields(script)[1] != ("DirectorCardCategorySelection", "RoR2", "RoR2.dll"):
                            raise ValueError("director deck requires original DirectorCardCategorySelection")
                        body = rebuild_director_deck(body, typ["tree"], selected["director_deck"])
                    if "surface_effect_omissions" in selected:
                        if selected["surface_effect_omissions"] is not True or typ["class_id"] != 114 or "properties_hash" not in selected or sdk_tree is None:
                            raise ValueError("surface omissions require original SurfaceDef script properties")
                        script, _ = source_record(sources, selected["properties_hash"]["script"])
                        if script_fields(script)[1] != ("SurfaceDef", "RoR2", "RoR2.dll"):
                            raise ValueError("surface omissions require original SurfaceDef")
                        body = omit_surface_effects(body, typ["tree"])
                    if "empty_mesh_renderer" in selected:
                        if selected["empty_mesh_renderer"] is not True or typ["class_id"] != 23:
                            raise ValueError("empty renderer requires an original MeshRenderer")
                        body = empty_mesh_renderer(body, typ["tree"])
                    body = remap(body, selected.get("references", []))
                    if "keyword_policy" in selected:
                        if typ["class_id"] != 21 or selected["keyword_policy"] not in ("dummy-shader-demote-valid", "dummy-shader-sort-invalid"):
                            raise ValueError("unqualified material keyword policy")
                        body = demote_material_keywords(body, sort_invalid=selected["keyword_policy"] == "dummy-shader-sort-invalid")
                else:
                    source = selected["type_source"]
                    if isinstance(source, list):
                        _, typ = source_record(sources, source)
                    else:
                        candidates = [row for row in sources[source][3]["types"] if row["class_id"] == 142]
                        if len(candidates) != 1:
                            raise ValueError("missing original AssetBundle type")
                        typ = candidates[0]
                    if selected.get("generate") == "PreloadData":
                        if typ["class_id"] != 150:
                            raise ValueError("scene preload requires original PreloadData type")
                        body = preload_data(selected_bundle, selected_member, selected_members, packed)
                    elif selected.get("generate") == "DefaultMaterial":
                        if typ["class_id"] != 21:
                            raise ValueError("default material requires original Material type")
                        body = default_material(selected, sources, sdk, output)
                    else:
                        if selected.get("generate", "AssetBundle") != "AssetBundle" or typ["class_id"] != 142:
                            raise ValueError("bundle container requires original AssetBundle type")
                        body = asset_bundle(selected_bundle, identities)
                if "properties_hash" in selected:
                    if sdk_tree is None:
                        raise ValueError("script properties require SDK metadata")
                    selectors = selected["properties_hash"]
                    omit_master = selected.get("omit_character_master_unkillable", False)
                    omit_alpha = selected.get("omit_animate_shader_alpha_legacy_fields", False)
                    omit_presence = selected.get("omit_run_presence_counters", False)
                    key = tuple(selectors["script"]), tuple(selectors["behaviour"]), omit_master, omit_alpha, omit_presence
                    if key not in properties:
                        script, script_type = source_record(sources, selectors["script"])
                        original_behaviour, behaviour_type = source_record(sources, selectors["behaviour"])
                        if script_type["class_id"] != 115 or behaviour_type["class_id"] != 114:
                            raise ValueError("script properties selectors have wrong classes")
                        _, names = script_fields(script)
                        schema = behaviour_type["tree"]
                        if omit_master:
                            if omit_master is not True or names != ("CharacterMaster", "RoR2", "RoR2.dll"):
                                raise ValueError("final field omission requires original CharacterMaster")
                            schema = omit_character_master_field(schema, identity_owner)
                        if omit_alpha:
                            if omit_alpha is not True or names != ("AnimateShaderAlpha", "RoR2", "RoR2.dll"):
                                raise ValueError("legacy schema requires original AnimateShaderAlpha")
                            _, schema = legacy_animate_fields(original_behaviour, schema, identity_owner)
                            schema = legacy_animate_hash_tree(schema, sdk_tree, identity_owner)
                        if omit_presence:
                            if omit_presence is not True or names != ("RunPresence", "RoR2", "RoR2.dll"):
                                raise ValueError("cached counter omission requires original RunPresence")
                            schema = omit_run_presence_counters(schema, identity_owner)
                        properties[key] = identity_owner.properties_hash(*names, schema, sdk_tree)
                    value = properties[key]
                    if typ["class_id"] == 115:
                        offset, _ = script_fields(body)
                        body = body[:offset] + value + body[offset + 16 :]
                    elif typ["class_id"] == 114:
                        typ = copy.deepcopy(typ)
                        if omit_master:
                            if body[-4:] not in (bytes(4), b"\x01\0\0\0"):
                                raise ValueError("original CharacterMaster final value drift")
                            body = body[:-4]
                            typ["tree"] = omit_character_master_field(typ["tree"], identity_owner)
                        if omit_presence:
                            if body[-8:] != bytes(8):
                                raise ValueError("original RunPresence cached counters must be zero")
                            body = body[:-8]
                            typ["tree"] = omit_run_presence_counters(typ["tree"], identity_owner)
                        typ["hash"] = value
                    else:
                        raise ValueError("script properties require MonoScript or MonoBehaviour")
                if "fieldless_script_record" in selected:
                    if sdk_tree is None or selected["fieldless_script_record"] is not True:
                        raise ValueError("fieldless script record requires the named SDK policy")
                    if typ["class_id"] != 114 or len(body) < 28:
                        raise ValueError("fieldless script record requires a MonoBehaviour")
                    file_id, script_id = struct.unpack_from("<iq", body, 16)
                    scripts = [s for s in selected_member["objects"] if s["path_id"] == script_id and "record" in s]
                    if file_id or len(scripts) != 1:
                        raise ValueError("fieldless script requires a local produced MonoScript record")
                    script_selection = scripts[0]
                    _, script_type = source_record(sources, script_selection["type_source"])
                    directory, script_row = packed[selected_member["name"], script_id]
                    script = record_extent(directory / "objects.bin", script_row)
                    if script_type["class_id"] != 115 or hashlib.sha256(script).hexdigest() != script_selection["sha256"]:
                        raise ValueError("fieldless MonoScript record identity differs")
                    typ = fieldless_script_type(body, typ, script, sdk_tree, identity_owner)
                    receipt.setdefault("fieldless_script_records", {})[str(script_id)] = script_selection["sha256"]
                if "managed_pointer_schema" in selected:
                    if sdk_tree is None or typ["class_id"] != 114:
                        raise ValueError("managed pointer schema requires SDK and MonoBehaviour")
                    policy = selected["managed_pointer_schema"]
                    script, script_type = source_record(sources, policy["script"])
                    _, base_type = source_record(sources, policy["base"])
                    _, pointer_type = source_record(sources, policy["pointer"])
                    if script_type["class_id"] != 115 or base_type["class_id"] != 114 or pointer_type["class_id"] != 114:
                        raise ValueError("managed pointer schema selectors have wrong classes")
                    derived, inputs = identity_owner.pointer_script_schema(pc, policy["managed"], script, base_type["tree"], pointer_type["tree"], sdk_tree)
                    typ = copy.deepcopy(base_type)
                    typ.update(derived)
                    receipt.setdefault("managed_schema_inputs", {}).update(inputs)
                if len(body) != selected["bytes"] or hashlib.sha256(body).hexdigest() != selected["sha256"]:
                    raise ValueError("produced object differs from accepted hash")
                member_records.append({"path_id": selected["path_id"], "body": body, "type": typ, "member": selected_member["name"]})
            layout, bodies = make_layout(selected_member, member_records, [member["name"] for member in selected_members] if scene else (), engine)
            serialized = io.BytesIO()
            W.write_serialized(serialized, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
            serialized_bytes = serialized.getvalue()
            if hashlib.sha256(serialized_bytes).hexdigest() != selected_member["serialized_sha256"]:
                raise ValueError("produced serialized structure differs from accepted hash")
            layout["data_offset"] = struct.unpack_from(">q", serialized_bytes, 32)[0]
            layout["bytes"] = len(serialized_bytes)
            layouts.append({"name": selected_member["name"], **layout} if scene else layout)
            members.append((selected_member["name"], 4, len(serialized_bytes), lambda data=serialized_bytes: io.BytesIO(data)))
            records.extend(sorted(member_records, key=lambda row: row["path_id"]))
        payload = output / "payload"
        payload.mkdir()
        name = selected_bundle["name"]
        if name in ("", ".", "..") or Path(name).name != name:
            raise ValueError("invalid output bundle name")
        bundle_path = payload / name
        for name, extents in resources.items():
            data = bytearray()
            for offset, extent in sorted(extents):
                if offset < len(data):
                    raise ValueError("overlapping produced resource extents")
                data.extend(bytes(offset - len(data)))
                data.extend(extent)
            if name in selected_bundle.get("resource_alignment", {}):
                if selected_bundle["resource_alignment"][name] != 16 or not name.endswith(".resS"):
                    raise ValueError("unqualified native resource alignment")
                data.extend(bytes(-len(data) % 16))
            members.append((name, 0, len(data), lambda data=data: io.BytesIO(data)))
        with W.codec(codec_path, codec_sha256) as compress, bundle_path.open("xb") as stream:
            W.write_bundle(stream, members, compress, engine=engine)
        if bundle_path.stat().st_size != selected_bundle["bytes"] or B.sha(bundle_path) != selected_bundle["sha256"]:
            raise ValueError("produced UnityFS differs from accepted hash")
        with (output / "objects.bin").open("xb") as data, (output / "index.jsonl").open("x") as index:
            for row in records:
                body = row["body"]
                index.write(
                    json.dumps(
                        {
                            "bundle": selected_bundle["name"],
                            "member": row["member"],
                            "path_id": row["path_id"],
                            "offset": data.tell(),
                            "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest(),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                data.write(body)
                receipt["objects"] += 1
                receipt["object_bytes"] += len(body)
        (output / "layout.json").write_text(json.dumps(json_layout({"members": layouts} if scene else layouts[0]), sort_keys=True, indent=2) + "\n")
        for selected, (path, before, _, _, _) in zip(profile["sources"], sources, strict=True):
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or B.sha(path) != selected["sha256"]:
                raise ValueError("original object input changed during production")
        check_record_packs(providers)
        if sdk_path is not None and B.sha(sdk_path) != profile["sdk"]["sha256"]:
            raise ValueError("SDK script metadata changed during production")
        with (output / "objects.bin").open("rb") as data:
            for line in (output / "index.jsonl").read_text().splitlines():
                row = json.loads(line)
                data.seek(row["offset"])
                if hashlib.sha256(B.exact(data, row["bytes"])).hexdigest() != row["sha256"]:
                    raise ValueError("persisted object extent drift")
        receipt["outputs"] = {
            name: {"bytes": (output / name).stat().st_size, "sha256": B.sha(output / name)}
            for name in ("objects.bin", "index.jsonl", "layout.json", "payload/" + selected_bundle["name"])
        }
        receipt["serialized_sha256"] = (
            {member["name"]: member["serialized_sha256"] for member in selected_members} if scene else selected_bundle["serialized_sha256"]
        )
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, help="owner's pinned Unity SDK root; required only for script properties derivation")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codec", type=Path, help="pinned codec; required for serialization, unnecessary for the original Windows bundle copy")
    parser.add_argument("--codec-sha256")
    parser.add_argument(
        "--record-pack",
        nargs=2,
        action="append",
        default=[],
        metavar=("DIRECTORY", "RECEIPT_SHA256"),
        help="independently produced record pack and pinned result.json; repeat for each producer",
    )
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output, args.codec, args.codec_sha256, args.record_pack, args.sdk)


if __name__ == "__main__":
    main()
