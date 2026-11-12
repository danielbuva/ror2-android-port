"""Restore Animator parameter names that AssetRipper left as hashed placeholders.

The shipped clip binding retains the original CRC32 attribute and Animator
type ID. Only a unique parameter from the imported original controllers may
replace that placeholder; unknown hashes remain visible for later analysis.
"""

from collections import defaultdict
import json
import math
from pathlib import Path
import re
import zlib


PARAMETER = re.compile(r"^  - m_Name: (.+)$", re.M)
PLACEHOLDER = re.compile(r"^(    attribute: )typetree_0x([0-9A-Fa-f]+)_[^\r\n]+$", re.M)


def aim_clip_guids(controller):
    """Follow native aim-layer states and blend trees, without following transitions."""
    parts = re.split(r"^--- !u!\d+ &(-?\d+)\n", controller, flags=re.M)
    objects = dict(zip(parts[1::2], parts[2::2]))
    pending = []
    for body in objects.values():
        for layer in re.split(r"^  - serializedVersion:", body, flags=re.M)[1:]:
            if re.search(r"^    m_Name: Aim(?:Pitch|Yaw)$", layer, re.M):
                if not re.search(r"^    m_BlendingMode: 1$", layer, re.M):
                    continue
                pending.extend(re.findall(r"m_StateMachine: \{fileID: (-?\d+)\}", layer))
    seen, guids = set(), set()
    while pending:
        identity = pending.pop()
        if identity == "0" or identity in seen:
            continue
        seen.add(identity)
        if identity not in objects:
            raise RuntimeError("Unresolved native aim state or blend tree")
        body = objects[identity]
        guids.update(re.findall(r"m_Motion: \{fileID: -?\d+, guid: ([a-f0-9]{32}), type: \d+\}", body))
        pending.extend(re.findall(r"m_(?:State|StateMachine|Motion): \{fileID: (-?\d+)\}", body))
    return guids


def reference_curves(tree, exported):
    """Map the source reference-pose stream onto the exported Transform paths."""
    paths = defaultdict(set)
    # Unity folds long YAML scalars after saving imported clips. Continuation
    # indentation is six spaces, while the next curve/field starts at two/four.
    for path in re.findall(r"^    path: ?([^\n]*(?:\n      [^\n]+)*)", exported, re.M):
        path = path.replace("\n      ", " ")
        if path.startswith('"'):
            path = json.loads(path)
        paths[zlib.crc32(path.encode())].add(path)
    values = tree["m_MuscleClip"]["m_ValueArrayReferencePose"]
    if not values:
        return []
    curves, offset = [], 0
    for binding in tree["m_ClipBindingConstant"]["genericBindings"]:
        attribute = binding["attribute"]
        candidates = paths[binding["path"]]
        if binding["typeID"] != 4 or binding.get("isPPtrCurve") or attribute not in (1, 2, 3, 4) or len(candidates) != 1:
            raise RuntimeError("Unsupported or ambiguous native aim reference binding: " + str(binding))
        property_name = {1: "m_LocalPosition", 2: "m_LocalRotation", 3: "m_LocalScale", 4: "localEulerAnglesRaw"}[attribute]
        axes = "xyzw" if attribute == 2 else "xyz"
        for axis in axes:
            if offset >= len(values) or not math.isfinite(values[offset]):
                raise RuntimeError("Invalid native aim reference-pose values")
            curves.append(dict(path=next(iter(candidates)), property=property_name + "." + axis, value=values[offset]))
            offset += 1
    if offset != len(values):
        raise RuntimeError("Native aim reference-pose binding cardinality changed")
    return curves


def stage_aim_reference_poses(io, *, code_only=False):
    """Discover current native aim clips, retaining source identity and pose values locally."""
    import UnityPy
    from common import game, sha
    from whole_catalog import catalog_path, read_catalog

    root = io.project / "Assets/WholeGame"
    requested = set()
    for controller in io.glob(root, "**/*.controller"):
        requested.update(aim_clip_guids(io.read_text(controller)))
    clips = {}
    for meta in io.glob(root, "**/*.anim.meta"):
        guid = re.search(r"^guid: ([a-f0-9]{32})$", io.read_text(meta), re.M)
        if guid and guid[1] in requested:
            clip = Path(str(meta)[:-5])
            text = io.read_text(clip)
            name = re.search(r"^  m_Name: (.*)$", text, re.M)[1]
            name = json.loads(name) if name.startswith('"') else name
            key = (str(Path("Assets") / clip.relative_to(root).parent).lower(), name)
            if key in clips:
                raise RuntimeError("Ambiguous exported native aim clip")
            clips[key] = (clip, text)
            requested.remove(guid[1])
    if requested:
        raise RuntimeError("Native aim layer references an absent exported clip")
    if not clips:
        return dict(clips=[])
    metadata = read_catalog(catalog_path(io.catalog()))
    locations = {row["id"]: row for row in metadata["locations"]}
    parents = {key[0] for key in clips}
    bundle_ids = {
        metadata["dependencySets"][row["dependencySet"]][0]
        for row in metadata["locations"]
        if row.get("type", "").startswith("UnityEngine.AnimationClip,") and str(Path(row["internalId"]).parent).lower() in parents
    }
    inventory = io.read(io.work / "inventory/files.json")
    if inventory["input_id"] != io.read(io.work / "config/accepted-input.json")["input_id"]:
        raise RuntimeError("Native aim inspection requires the accepted input inventory")
    file_index = defaultdict(list)
    for row in inventory["files"]:
        file_index[Path(row["path"]).name].append(row)
    found = {}
    for identity in sorted(bundle_ids):
        basename = locations[identity]["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
        matches = file_index[basename]
        if len(matches) != 1:
            raise RuntimeError("Ambiguous or absent native aim bundle")
        source = game(io.work) / matches[0]["path"]
        if sha(source) != matches[0]["sha256"]:
            raise RuntimeError("Original aim bundle drift; explicitly review and accept")
        environment = UnityPy.load(str(source))
        for obj in environment.objects:
            if obj.type.name != "AssetBundle":
                continue
            for address, info in obj.read().m_Container:
                asset = info.asset.deref()
                if asset.type.name != "AnimationClip":
                    continue
                key = (str(Path(address).parent).lower(), asset.peek_name())
                if key not in clips:
                    continue
                clip, text = clips[key]
                tree = asset.read_typetree()
                # Humanoid reference streams include muscle channels. This repair
                # only changes the generic Transform stream proven on Commando.
                unsupported = any(binding["typeID"] != 4 for binding in tree["m_ClipBindingConstant"]["genericBindings"])
                curves = [] if unsupported else reference_curves(tree, text)
                row = dict(
                    clip=str(clip.relative_to(io.project)),
                    source=matches[0]["path"],
                    source_sha256=matches[0]["sha256"],
                    identities=[dict(serialized_file=asset.assets_file.name, path_id=asset.path_id)],
                    curves=curves,
                    status="unsupported-muscle-bindings" if unsupported else "source-reference" if curves else "no-source-reference",
                )
                if key in found:
                    if any(found[key][field] != row[field] for field in ("source_sha256", "curves", "status")):
                        raise RuntimeError("Ambiguous original aim clip reference pose: " + str(key))
                    if row["identities"][0] not in found[key]["identities"]:
                        found[key]["identities"].extend(row["identities"])
                else:
                    found[key] = row
        del environment
    if found.keys() != clips.keys():
        raise RuntimeError("Native aim clip missing from current source containers")
    result = dict(input_id=inventory["input_id"], clips=sorted(found.values(), key=lambda row: row["clip"]))
    path = io.project / ".rebuild/source-animation-reference-poses.json"
    if code_only:
        if not io.is_file(path) or io.read(path) != result:
            raise RuntimeError("Original aim reference poses changed; a content build is required")
    else:
        io.write(path, result)
    return result


def repair(project: Path, io=None):
    from composition_io import StageIO

    if io is None:
        io = StageIO(project)
        io.project = project
    root = project / "Assets/WholeGame"
    names = defaultdict(set)
    for controller in io.glob(root, "**/*.controller"):
        for name in PARAMETER.findall(io.read_text(controller, errors="replace")):
            names[zlib.crc32(name.encode("utf-8"))].add(name)

    changed = []
    unresolved = []
    for clip in io.glob(root, "**/*.anim"):
        source = io.read_text(clip, errors="replace")

        def replace(match):
            original_hash = int(match[2], 16)
            candidates = names[original_hash]
            # The serialized clip itself must independently identify this as
            # an Animator (class 95) float binding with the same hash.
            binding = re.search(r"^      attribute: " + str(original_hash) + r"\n      script: \{fileID: 0\}\n      typeID: 95$", source, re.M)
            if len(candidates) != 1 or not binding:
                unresolved.append((str(clip.relative_to(root)), match[2]))
                return match[0]
            name = next(iter(candidates))
            changed.append((str(clip.relative_to(root)), match[2], name))
            return match[1] + name

        repaired = PLACEHOLDER.sub(replace, source)
        if repaired != source:
            io.apply(clip, repaired)
    return {"repaired": changed, "unresolved": unresolved}
