"""Read-only, input-gated asset transformations; no serialized payloads in recipes."""

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath

from common import RECIPE, ROOT, WORK, read
from serialization_rebase import hierarchy_keys, identity, objects

SURFACE_OPERATIONS = (
    {"op": "clear_reference", "field": "impactEffectPrefab", "value": None},
    {"op": "clear_reference", "field": "footstepEffectPrefab", "value": None},
    {"op": "set_field", "field": "impactSoundString", "value": ""},
    {"op": "set_field", "field": "materialSwitchString", "value": ""},
)


def apply_surface_operation(text, operation, *, strict=True):
    """Share the sanitizer's span-preserving field clearing; reject unreviewed operations."""
    if operation not in SURFACE_OPERATIONS:
        raise RuntimeError("Unknown field or unsupported SurfaceDef operation")
    field = operation["field"]
    replacement = " {fileID: 0}" if operation["op"] == "clear_reference" else ""
    generated, count = re.subn(r"^(  " + re.escape(field) + r":)[^\r\n]*", lambda match: match[1] + replacement, text, flags=re.M)
    if strict and count != 1:
        raise RuntimeError("SurfaceDef field must match exactly once: " + field)
    return generated


def typed_value(value):
    """Serialize a typed scalar/reference, never a recipe-supplied YAML fragment."""
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        raise RuntimeError("Invalid typed field value")
    kind, data = value["type"], value["value"]
    if kind == "int" and type(data) is int:
        return str(data)
    if kind == "float" and type(data) in (int, float) and math.isfinite(data):
        return str(float(data))
    if kind == "bool" and type(data) is bool:
        return "1" if data else "0"
    if kind == "string" and isinstance(data, str):
        return json.dumps(data, ensure_ascii=False)
    if kind == "reference" and isinstance(data, dict):
        if set(data) == {"fileID"} and type(data["fileID"]) is int:
            return "{fileID: " + str(data["fileID"]) + "}"
        if (
            set(data) == {"fileID", "guid", "type"}
            and type(data["fileID"]) is int
            and type(data["type"]) is int
            and isinstance(data["guid"], str)
            and re.fullmatch(r"[a-f0-9]{32}", data["guid"])
        ):
            return "{fileID: " + str(data["fileID"]) + ", guid: " + data["guid"] + ", type: " + str(data["type"]) + "}"
    raise RuntimeError("Invalid typed field value")


def validate_field_operation(operation):
    if set(operation) != {"op", "owner", "field_path", "value", "expected_matches"} or operation["op"] != "set_field":
        raise RuntimeError("Invalid set_field operation")
    if type(operation["expected_matches"]) is not int or operation["expected_matches"] != 1:
        raise RuntimeError("set_field requires expected_matches exactly 1")
    owner = operation["owner"]
    if not isinstance(owner, dict) or set(owner) != {"hierarchy_path", "class_id", "script", "occurrence"}:
        raise RuntimeError("Invalid field owner selector")
    if (
        not isinstance(owner["hierarchy_path"], list)
        or not owner["hierarchy_path"]
        or any(not isinstance(part, str) or not part for part in owner["hierarchy_path"])
        or type(owner["class_id"]) is not int
        or owner["class_id"] < 1
        or type(owner["occurrence"]) is not int
        or owner["occurrence"] < 0
    ):
        raise RuntimeError("Invalid field owner selector")
    script = owner["script"]
    if owner["class_id"] == 114:
        typed_value({"type": "reference", "value": script})
        if set(script) != {"fileID", "guid", "type"}:
            raise RuntimeError("Component script identity requires external reference")
    elif script is not None:
        raise RuntimeError("Native class selector must have null script")
    path = operation["field_path"]
    if not isinstance(path, list) or not path or any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_]\w*", key) for key in path):
        raise RuntimeError("Invalid field path")
    typed_value(operation["value"])


def scalar_end(value):
    """Locate the end of a one-line YAML value, retaining whitespace/comments."""
    quote, escaped, depth = None, False, 0
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif quote == '"' and char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'" and (index == 0 or value[index - 1] in " {,:"):
            quote = char
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        elif char == "#" and depth == 0 and (index == 0 or value[index - 1].isspace()):
            return len(value[:index].rstrip())
    return len(value.rstrip())


def apply_field_operation(text, operation):
    """Select one owner/record and replace only the scalar's value span.

    Hierarchy names are path segments; duplicate owner paths fail. Component
    occurrence is zero-based in source record order for a class/script identity.
    Nested paths address block mappings; arrays/inline subfields are unsupported.
    """
    validate_field_operation(operation)
    owner = operation["owner"]
    header, rows = objects(text)
    keys = hierarchy_keys({fid: block.replace("\r\n", "\n") for fid, block in rows.items()})
    owners = [fid for fid, path in keys.items() if list(path) == owner["hierarchy_path"]]
    if len(owners) != 1:
        raise RuntimeError("Field owner must match exactly once")
    script = None if owner["script"] is None else typed_value({"type": "reference", "value": owner["script"]})
    candidates = [fid for fid, block in rows.items() if identity(block) == (str(owner["class_id"]), owners[0], script)] if owner["class_id"] != 1 else owners
    index = owner["occurrence"]
    if index >= len(candidates):
        raise RuntimeError("Field component must match exactly once")
    fid = candidates[index]
    block = rows[fid]
    start, end = 0, len(block)
    for depth, key in enumerate(operation["field_path"], 1):
        pattern = r"^" + "  " * depth + re.escape(key) + r":(?P<space> *)(?P<value>[^\r\n]*)"
        matches = list(re.finditer(pattern, block[start:end], re.M))
        if len(matches) != 1:
            raise RuntimeError("Field path must match exactly once")
        match = matches[0]
        if depth == len(operation["field_path"]):
            # A mapping/sequence is not a scalar: never leave child payload behind.
            tail = block[start + match.end() : end]
            if re.match(r"\r?\n(?: {" + str(depth * 2 + 1) + r",}| {" + str(depth * 2) + r"}- )", tail):
                raise RuntimeError("Field value must be scalar or inline reference")
            a = start + match.start("value")
            b = a + scalar_end(match["value"])
            replacement = ("" if match["space"] else " ") + typed_value(operation["value"])
            rows[fid] = block[:a] + replacement + block[b:]
        else:
            if match["value"]:
                raise RuntimeError("Field path requires a block mapping")
            start += match.end()
            boundary = re.search(r"^ {0," + str(depth * 2) + r"}[^ \r\n]", block[start:end], re.M)
            if boundary:
                end = start + boundary.start()
    return header + "".join(rows.values())


def reference_remaps(operation):
    if set(operation) != {"op", "recipe", "recipe_sha256"} or operation["recipe"] != "hud-ui-remaps.json":
        raise RuntimeError("Unsupported reference remapping")
    data = (RECIPE / operation["recipe"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != operation["recipe_sha256"]:
        raise RuntimeError("Reference remapping recipe hash mismatch")
    return json.loads(data)


def validate_removal_operation(operation):
    if set(operation) != {"op", "file_ids", "expected_matches"} or operation["op"] != "remove_components":
        raise RuntimeError("Invalid remove_components operation")
    ids = operation["file_ids"]
    if (
        not isinstance(ids, list)
        or not ids
        or any(type(fid) is not int or fid == 0 or not -(2**63) <= fid < 2**63 for fid in ids)
        or len(set(ids)) != len(ids)
        or type(operation["expected_matches"]) is not int
        or operation["expected_matches"] != len(ids)
    ):
        raise RuntimeError("Invalid component removal identifiers or match count")


def apply_removal_operation(text, operation):
    """Remove source components and membership entries, preserving all other bytes.

    This narrow operation rejects surviving references to deleted components.
    Nulling references, retaining empty membership slots and deleting hierarchy
    objects require separate, explicit operations; none is inferred here.
    """
    validate_removal_operation(operation)
    header, rows = objects(text)
    removed = {str(fid) for fid in operation["file_ids"]}
    memberships = {}
    for fid in removed:
        if fid not in rows:
            raise RuntimeError("Component removal must match exactly once: " + fid)
        kind, owner, _ = identity(rows[fid])
        if kind in {"1", "4", "224"} or owner not in rows or identity(rows[owner])[0] != "1":
            raise RuntimeError("Removal requires a component with a surviving GameObject owner")
        memberships[fid] = owner
    counts = dict.fromkeys(removed, 0)
    for fid, block in list(rows.items()):
        if fid in removed:
            del rows[fid]
            continue
        if identity(block)[0] == "1":

            def remove_member(match):
                component = match[1]
                if component not in removed:
                    return match[0]
                if memberships[component] != fid:
                    raise RuntimeError("Component membership has the wrong owner")
                counts[component] += 1
                return ""

            rows[fid] = re.sub(r"^  - component: \{fileID: (-?\d+)\}\r?\n", remove_member, block, flags=re.M)
    if any(count != 1 for count in counts.values()):
        raise RuntimeError("Removed component membership must match exactly once")
    generated = header + "".join(rows.values())
    if any(match[1] in removed for match in re.finditer(r"\{fileID: (-?\d+)\}", generated)):
        raise RuntimeError("Component removal leaves a surviving local reference")
    return generated


def validate_operations(operations, accepted=None):
    if operations == list(SURFACE_OPERATIONS) or operations == [{"op": "identity"}]:
        return
    if not isinstance(operations, list) or not operations:
        raise RuntimeError("Unknown field or unsupported asset operations")
    for operation in operations:
        if not isinstance(operation, dict):
            raise RuntimeError("Invalid asset operation")
        if operation.get("op") == "remap_references":
            remaps = reference_remaps(operation)
            if accepted is not None and remaps["input_id"] != accepted:
                raise RuntimeError("Reference remapping belongs to a different accepted input")
        elif operation.get("op") == "set_field" and "owner" in operation:
            validate_field_operation(operation)
        elif operation.get("op") == "remove_components":
            validate_removal_operation(operation)
        else:
            raise RuntimeError("Unknown field or unsupported asset operations")


def asset_path(root, selector):
    """Require a canonical project-relative asset path, including resolved symlinks."""
    if not isinstance(selector, str):
        raise RuntimeError("Invalid asset selector")
    path = PurePosixPath(selector)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != selector or not selector.startswith("Assets/"):
        raise RuntimeError("Invalid asset selector")
    result = Path(root) / selector
    if not result.resolve().is_relative_to(Path(root).resolve()):
        raise RuntimeError("Asset selector escapes project")
    return result


def load_recipe(accepted, path=None):
    recipe = read(path or RECIPE / "asset-transforms.json")
    if set(recipe) != {"schema_version", "input_id", "assets"} or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise RuntimeError("Unsupported asset transform schema")
    if recipe["input_id"] != accepted:
        raise RuntimeError("Asset transforms belong to a different accepted input")
    if not isinstance(recipe["assets"], list) or not recipe["assets"]:
        raise RuntimeError("Asset transforms require a nonempty asset list")
    sources, outputs = set(), set()
    for asset in recipe["assets"]:
        if set(asset) != {"source", "source_sha256", "output", "operations"}:
            raise RuntimeError("Invalid asset transform entry")
        for name, seen in (("source", sources), ("output", outputs)):
            asset_path(Path.cwd(), asset[name])
            if PurePosixPath(asset[name]).suffix not in {".asset", ".prefab", ".renderTexture"} or asset[name].casefold() in seen:
                raise RuntimeError("Duplicate or invalid asset transform selector")
            seen.add(asset[name].casefold())
        if not isinstance(asset["source_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", asset["source_sha256"]):
            raise RuntimeError("Invalid asset transform source hash")
        validate_operations(asset["operations"], accepted)
    return recipe


def generate(source, asset):
    """Return transformed UTF-8 text from bytes after checking the exact source hash."""
    if hashlib.sha256(source).hexdigest() != asset["source_sha256"]:
        raise RuntimeError("Asset transform source hash mismatch: " + asset["source"])
    operations = asset["operations"]
    validate_operations(operations)
    text = source.decode("utf-8")
    if operations == [{"op": "identity"}]:
        return text
    if operations == list(SURFACE_OPERATIONS):
        if len(re.findall(r"^--- !u!114 &-?\d+\r?$", text, re.M)) != 1 or len(re.findall(r"^--- !u!", text, re.M)) != 1:
            raise RuntimeError("SurfaceDef must contain exactly one MonoBehaviour record")
        if len(re.findall(r"^  isSlippery:", text, re.M)) != 1:
            raise RuntimeError("SurfaceDef marker missing or ambiguous")
        for operation in operations:
            text = apply_surface_operation(text, operation)
    else:
        for operation in operations:
            if operation["op"] == "set_field":
                text = apply_field_operation(text, operation)
            elif operation["op"] == "remove_components":
                text = apply_removal_operation(text, operation)
            else:
                for row in reference_remaps(operation)["rows"]:
                    text = text.replace(row["from"], row["to"])

    return text


def generate_asset(export, asset, guid=None):
    """Return asset/meta bytes; metadata follows composition's export importer rule."""
    source = asset_path(export, asset["source"])
    source_data = source.read_bytes()
    if asset["operations"] == [{"op": "identity"}]:
        if hashlib.sha256(source_data).hexdigest() != asset["source_sha256"]:
            raise RuntimeError("Asset transform source hash mismatch: " + asset["source"])
        data = source_data
    else:
        data = generate(source_data, asset).encode("utf-8")
    meta = asset_path(export, asset["source"] + ".meta").read_bytes()
    matches = re.findall(rb"^guid: ([a-f0-9]{32})\r?$", meta, re.M)
    if len(matches) != 1:
        raise RuntimeError("Export metadata GUID missing or ambiguous")
    if guid is not None:
        if not re.fullmatch(r"[a-f0-9]{32}", guid):
            raise RuntimeError("Invalid current asset GUID")
        meta = re.sub(rb"(?<=guid: )[a-f0-9]{32}", guid.encode(), meta, count=1)
    return data, meta


def check(work=None, root=None):
    """Compare every generated asset with what the migration stage produces, without writing.

    The oracle is the stage's preview copy (local evidence) when one exists, else the generated
    project. Later current steps (the optional-content sanitizer, Unity's re-serialisation on
    import) still change some assets in the project; those are reported, not failed.
    """
    work, root = Path(work or WORK), Path(root or ROOT)
    accepted = read(work / "config/accepted-input.json")["input_id"]
    reconstruction = read(work / "config/reconstruction.json")
    project = work / "lab-project"
    if reconstruction["input_id"] != accepted or read(project / ".port-input.json")["input_id"] != accepted:
        raise RuntimeError("Export/project belongs to a different accepted input")
    recipe = load_recipe(accepted)
    export = root / reconstruction["projects"][0]
    selection = work / "config/composition-migration.json"
    preview = root / read(selection)["evidence"] / "preview" if selection.is_file() else None
    differences, later_changes, identical = [], [], 0
    removal_cohort = {"total": 0, "identical": 0, "components": 0}
    for asset in recipe["assets"]:
        data, meta = generate_asset(export, asset)
        oracle = asset_path(preview, asset["output"]) if preview is not None else None
        if oracle is None or not oracle.is_file():
            oracle = asset_path(project, asset["output"])
        changed = []
        if not oracle.is_file() or oracle.read_bytes() != data:
            changed.append(asset["output"])
        target_meta = asset_path(project, asset["output"] + ".meta")
        if not target_meta.is_file() or target_meta.read_bytes() != meta:
            changed.append(asset["output"] + ".meta")
        current = asset_path(project, asset["output"])
        if not changed and (not current.is_file() or current.read_bytes() != data):
            later_changes.append(asset["output"])
        differences.extend(changed)
        identical += not changed
        removals = [operation for operation in asset["operations"] if operation["op"] == "remove_components"]
        if removals:
            removal_cohort["total"] += 1
            removal_cohort["identical"] += not changed
            removal_cohort["components"] += sum(len(operation["file_ids"]) for operation in removals)
    result = {"total": len(recipe["assets"]), "identical": identical, "differences": differences, "changed_later_in_project": later_changes}
    if removal_cohort["total"]:
        result["component_removal_cohort"] = removal_cohort
    return result


def check_action():
    result = check()
    print(json.dumps(result, indent=2))
    if result["differences"]:
        raise SystemExit(1)
