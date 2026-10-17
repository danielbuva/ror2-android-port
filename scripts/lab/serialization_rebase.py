"""Rebase measured Android YAML adaptations onto a newly exported input.

Exporter component IDs can move even when GameObject IDs remain stable. Match
owners and script identities before applying a patch; reject ambiguous matches.
This operates only on local generated text, never the legitimate installation.
"""

import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


class RebaseConflict(RuntimeError):
    pass


def objects(text):
    parts = re.split(r"(?=^--- !u!)", text, flags=re.M)
    result = {}
    for block in parts[1:]:
        match = re.match(r"--- !u!(\d+) &(-?\d+)", block)
        if not match or match[2] in result:
            raise RebaseConflict("Invalid or duplicate serialized object identity")
        result[match[2]] = block
    return parts[0], result


def identity(block):
    kind = re.match(r"--- !u!(\d+)", block)[1]
    owner = re.search(r"^  m_GameObject: \{fileID: (-?\d+)\}", block, re.M)
    script = re.search(r"^  m_Script: (\{[^\n]+\})", block, re.M)
    return kind, owner[1] if owner else None, script[1] if script else None


def local_ids(text, mapping):
    # External references contain a GUID and must keep their own local ID.
    text = re.sub(r"\{fileID: (-?\d+)\}", lambda m: "{fileID: " + mapping.get(m[1], m[1]) + "}", text)
    return re.sub(r"(^--- !u!\d+ &)(-?\d+)", lambda m: m[1] + mapping.get(m[2], m[2]), text, flags=re.M)


def hierarchy_keys(rows):
    names = {fid: re.search(r"^  m_Name: (.*)$", block, re.M)[1] for fid, block in rows.items() if identity(block)[0] == "1"}
    transforms = {fid: block for fid, block in rows.items() if identity(block)[0] in ("4", "224")}
    parents = {}
    for block in transforms.values():
        owner = identity(block)[1]
        parent = re.search(r"^  m_Father: \{fileID: (-?\d+)\}", block, re.M)
        if owner in parents or not parent:
            raise RebaseConflict("Ambiguous transform hierarchy owner")
        parents[owner] = identity(transforms[parent[1]])[1] if parent[1] in transforms else None
    cache = {}

    def key(fid, visiting=()):
        if fid in cache:
            return cache[fid]
        if fid in visiting:
            raise RebaseConflict("Cyclic source transform hierarchy")
        parent = parents.get(fid)
        cache[fid] = (key(parent, visiting + (fid,)) if parent else ()) + (names[fid],)
        return cache[fid]

    return {fid: key(fid) for fid in names}


def owner_shape(rows, owner):
    """Source transform/mesh fields distinguish repeated named hierarchy nodes."""
    measured = {"m_LocalPosition", "m_LocalRotation", "m_LocalScale", "m_Mesh", "m_AnchorMin", "m_AnchorMax", "m_AnchoredPosition", "m_SizeDelta", "m_Pivot"}
    values = []
    for block in rows.values():
        kind, game_object, script = identity(block)
        if game_object == owner:
            _, data = fields(block)
            geometry = tuple(sorted((key, value) for key, value in data.items() if key in measured))
            if geometry:
                values.append((kind, geometry))
    return tuple(sorted(values))


def component_id_map(base, current, adapted=None, required=None):
    """Match stable named owners, then unique component/class/script contracts."""
    _, before = objects(base)
    _, after = objects(current)
    _, android = objects(adapted if adapted is not None else base)
    if required is None:
        required = set(before)
    required = set(required)
    required.update(identity(before[fid])[1] for fid in list(required) if fid in before and identity(before[fid])[1])
    old_keys, new_keys = hierarchy_keys(before), hierarchy_keys(after)
    owners = defaultdict(list)
    for fid, key in new_keys.items():
        owners[key].append(fid)
    mapping = {}
    missing = set()
    for fid, block in before.items():
        if fid not in required or identity(block)[0] != "1":
            continue
        candidate = after.get(fid)
        name = re.search(r"^  m_Name: (.*)$", block, re.M)
        other = re.search(r"^  m_Name: (.*)$", candidate or "", re.M)
        if candidate and identity(candidate)[0] == "1" and name and other and name[1] == other[1] and old_keys[fid] == new_keys.get(fid):
            mapping[fid] = fid
        elif len(owners[old_keys[fid]]) == 1:
            mapping[fid] = owners[old_keys[fid]][0]
        elif not owners[old_keys[fid]]:
            missing.add(fid)
        else:
            shape = owner_shape(before, fid)
            found = [candidate for candidate in owners[old_keys[fid]] if owner_shape(after, candidate) == shape]
            if len(found) == 1:
                mapping[fid] = found[0]
            else:
                raise RebaseConflict("Original GameObject owner ambiguous: " + fid)
    candidates = defaultdict(list)
    for fid, block in after.items():
        candidates[identity(block)].append(fid)
    for fid, block in before.items():
        kind, owner, script = identity(block)
        if fid not in required or kind == "1":
            continue
        if owner in missing:
            missing.add(fid)
            continue
        key = kind, mapping.get(owner, owner), script
        found = candidates[key]
        if len(found) > 1 and fid in android and android[fid] != block:
            _, old_fields = fields(block)
            _, android_fields = fields(android[fid])
            contract = {
                name: value
                for name, value in old_fields.items()
                if name not in {"m_GameObject", "m_Script", "m_ObjectHideFlags", "m_Name", "m_EditorClassIdentifier"}
                and value == android_fields.get(name)
                and not re.search(r"\{fileID: -?\d+\}", value)
            }
            if contract:
                found = [candidate for candidate in found if all(fields(after[candidate])[1].get(name) == value for name, value in contract.items())]
        if len(found) == 1:
            mapping[fid] = found[0]
        elif fid in found and after[fid] == block:
            mapping[fid] = fid
        elif not found:
            missing.add(fid)
        elif fid not in android or android[fid] == block:
            # No Android field adaptation to transfer. Keep the new original
            # records rather than assigning an arbitrary duplicate component.
            missing.add(fid)
        else:
            raise RebaseConflict("Component owner missing or ambiguous: " + fid + " " + str(key))
    if len(set(mapping.values())) != len(mapping):
        raise RebaseConflict("Several original objects map to one updated owner")
    return mapping, missing


def member_field(block, name):
    return re.search(r"^  " + name + r":[^\n]*\n(?:(?:  - |    ).*\n)*", block, re.M)


def rebase_members(base, adapted, current, name):
    fields = [member_field(block, name) for block in (base, adapted, current)]
    if not all(fields):
        return base, adapted, current
    old, android, updated = [field[0] for field in fields]
    if old == android:
        return base, adapted, current
    before = set(re.findall(r"fileID: (-?\d+)", old))
    retained = set(re.findall(r"fileID: (-?\d+)", android))
    removed = before - retained
    lines = updated.splitlines(keepends=True)
    lines = [line for line in lines if not any(fid in removed for fid in re.findall(r"fileID: (-?\d+)", line))]
    present = set(re.findall(r"fileID: (-?\d+)", "".join(lines)))
    for line in android.splitlines(keepends=True)[1:]:
        ids = set(re.findall(r"fileID: (-?\d+)", line))
        if ids and ids - before and not ids & present:
            lines.append(line)
            present.update(ids)
    replacement = "".join(lines)
    if len(lines) == 1:
        replacement = "  " + name + ": []\n"
    result = []
    # Resolve membership separately; source order wins for retained components.
    for block, field in zip((base, adapted, current), fields):
        result.append(block[: field.start()] + replacement + block[field.end() :])
    return tuple(result)


def merge_text(base, adapted, current):
    if base == adapted:
        return current
    if base == current or adapted == current:
        return adapted
    with tempfile.TemporaryDirectory() as temp:
        paths = [Path(temp) / name for name in ("android", "base", "updated")]
        for path, text in zip(paths, (adapted, base, current)):
            path.write_text(text)
        result = subprocess.run(["git", "merge-file", "--diff3", "-p", *map(str, paths)], capture_output=True)
        if result.returncode:
            raise RebaseConflict(result.stdout.decode(errors="replace"))
        return result.stdout.decode()


def fields(block):
    matches = list(re.finditer(r"^  ([A-Za-z_]\w*):", block, re.M))
    result = {}
    for i, match in enumerate(matches):
        if match[1] in result:
            raise RebaseConflict("Duplicate serialized field: " + match[1])
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        result[match[1]] = block[match.start() : end]
    return block[: matches[0].start()] if matches else block, result


def merge_block(base, adapted, current):
    if base == adapted:
        return current
    if base == current or adapted == current:
        return adapted
    for name in ("m_Component", "m_Children"):
        base, adapted, current = rebase_members(base, adapted, current, name)
    _, old = fields(base)
    _, android = fields(adapted)
    header, updated = fields(current)
    merged = []
    for name in dict.fromkeys([*updated, *android, *old]):
        before, after, value = old.get(name, ""), android.get(name, ""), updated.get(name, "")
        merged.append(merge_text(before, after, value))
    return header + "".join(merged)


def rebase_yaml(base, adapted, current):
    _, original = objects(base)
    _, android_objects = objects(adapted)
    required = set(original) - set(android_objects)
    for fid, block in android_objects.items():
        if fid not in original or block == original[fid]:
            continue
        _, old_fields = fields(original[fid])
        _, new_fields = fields(block)
        for name in old_fields.keys() | new_fields.keys():
            before, after = old_fields.get(name, ""), new_fields.get(name, "")
            if before == after:
                continue
            if name in ("m_Component", "m_Children"):
                refs = set(re.findall(r"fileID: (-?\d+)", before)) ^ set(re.findall(r"fileID: (-?\d+)", after))
                if not refs:
                    continue
            else:
                refs = set(re.findall(r"\{fileID: (-?\d+)\}", before + after))
            required.add(fid)
            required.update(ref for ref in refs if ref in original)
    mapping, missing = component_id_map(base, current, adapted, required)
    required.update(mapping)

    def remove_absent(text):
        header, rows = objects(text)
        text = header + "".join(block for fid, block in rows.items() if fid not in missing and (fid in required or fid not in original))
        # These objects were removed by the updated input, not quarantined.
        return re.sub(r"\{fileID: (-?\d+)\}", lambda m: "{fileID: 0}" if m[1] in missing else m[0], text)

    base, adapted = remove_absent(base), remove_absent(adapted)
    base = local_ids(base, mapping)
    adapted = local_ids(adapted, mapping)
    _, before = objects(base)
    _, android = objects(adapted)
    header, updated = objects(current)
    deleted = set(before) - set(android)
    merged = {}
    changed_deletions = []
    for fid, block in updated.items():
        if fid in deleted:
            if identity(before[fid]) != identity(block):
                raise RebaseConflict("Deleted object owner changed: " + fid)
            if before[fid] != block:
                changed_deletions.append(fid)
            continue
        if fid not in before:
            merged[fid] = block
        else:
            merged[fid] = merge_block(before[fid], android[fid], block)
    for fid in set(android) - set(before):
        if fid in updated and android[fid] != updated[fid]:
            raise RebaseConflict("Android object ID collides with updated source: " + fid)
        merged[fid] = android[fid]
    text = header + "".join(merged.values())
    # New fields can reference an explicitly removed optional component.
    text = local_ids(text, {fid: "0" for fid in deleted})
    return text, dict(remapped=sum(a != b for a, b in mapping.items()), removed=len(deleted), source_removed=len(missing), changed_deletions=changed_deletions)


def rebase_geometry(base, adapted, current):
    """Reapply the existing reduced-scene policy using current source records.

    This preserves the accepted composed geometry boundary, not stock scene
    startup. Its explicit callbacks/classes still require gameplay integration.
    """
    _, before = objects(base)
    _, android = objects(adapted)
    header, updated = objects(current)
    classes = {identity(block)[0] for block in android.values()} - {"114"}
    scripts = {identity(block)[2] for block in android.values() if identity(block)[0] == "114"}
    kept = {fid: block for fid, block in updated.items() if identity(block)[0] in classes or identity(block)[2] in scripts and identity(block)[0] == "114"}
    old_keys, new_keys = hierarchy_keys(before), hierarchy_keys(updated)
    owners = defaultdict(list)
    for fid, key in new_keys.items():
        owners[key].append(fid)
    changes = []
    for fid, block in android.items():
        if fid not in before:
            raise RebaseConflict("Reduced scene has an added Android object; review its identity")
        _, old_fields = fields(before[fid])
        _, adapted_fields = fields(block)
        changed = [name for name in old_fields.keys() | adapted_fields.keys() if old_fields.get(name) != adapted_fields.get(name) and name != "m_Component"]
        if not changed:
            continue
        kind, owner, _ = identity(block)
        if kind == "1" and changed == ["m_IsActive"]:
            source_owner = fid
        elif kind == "215" and set(changed) <= {"m_Mode", "m_CustomBakedTexture"}:
            source_owner = owner
        else:
            raise RebaseConflict("Unreviewed reduced-scene field changes: " + fid + " " + str(changed))
        matches = owners[old_keys[source_owner]]
        if len(matches) > 1:
            shape = owner_shape(before, source_owner)
            matches = [candidate for candidate in matches if owner_shape(updated, candidate) == shape]
        if len(matches) != 1:
            raise RebaseConflict("Reduced scene adapter owner is ambiguous: " + str(old_keys[source_owner]))
        target_owner = matches[0]
        candidates = [target_owner] if kind == "1" else [key for key, value in kept.items() if identity(value)[:2] == (kind, target_owner)]
        if len(candidates) != 1:
            raise RebaseConflict("Reduced scene adapter component is ambiguous: " + fid)
        target = candidates[0]
        h, data = fields(kept[target])
        for name in changed:
            data[name] = merge_text(old_fields.get(name, ""), adapted_fields.get(name, ""), data.get(name, ""))
        kept[target] = h + "".join(data.values())
        changes.append(dict(old=fid, current=target, fields=changed))
    removed = set(updated) - set(kept)
    for fid, block in list(kept.items()):
        if identity(block)[0] == "1":
            block = re.sub(r"^  - component: \{fileID: (-?\d+)\}\n", lambda m: "" if m[1] in removed else m[0], block, flags=re.M)
        kept[fid] = re.sub(r"\{fileID: (-?\d+)\}", lambda m: "{fileID: 0}" if m[1] in removed else m[0], block)
    return header + "".join(kept.values()), dict(
        policy="Existing reduced source scene, not stock scene lifecycle", kept=len(kept), removed=len(removed), adapters=changes
    )
