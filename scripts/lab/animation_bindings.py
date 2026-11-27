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
MOTION_GUID = re.compile(r"m_Motion: \{fileID: -?\d+, guid: ([a-f0-9]{32}), type: \d+\}")


def additive_clip_guids(controller, *, aim_only=False, override_layer=None):
    """Follow native additive-layer states and blend trees, without following transitions."""
    parts = re.split(r"^--- !u!\d+ &(-?\d+)\n", controller, flags=re.M)
    objects = dict(zip(parts[1::2], parts[2::2]))
    pending, guids = [], set()
    for body in objects.values():
        for layer in re.split(r"^  - serializedVersion:", body, flags=re.M)[1:]:
            if aim_only and not re.search(r"^    m_Name: Aim(?:Pitch|Yaw)$", layer, re.M):
                continue
            if re.search(r"^    m_BlendingMode: 1$", layer, re.M):
                pending.extend(re.findall(r"m_StateMachine: \{fileID: (-?\d+)\}", layer))
            if override_layer and re.search(r"^    m_Name: " + re.escape(override_layer) + r"$", layer, re.M):
                guids.update(MOTION_GUID.findall(layer))
                pending.extend(re.findall(r"m_Motion: \{fileID: (-?\d+)\}", layer))
    seen = set()
    while pending:
        identity = pending.pop()
        if identity == "0" or identity in seen:
            continue
        seen.add(identity)
        if identity not in objects:
            raise RuntimeError("Unresolved native additive state or blend tree")
        body = objects[identity]
        guids.update(MOTION_GUID.findall(body))
        pending.extend(re.findall(r"m_(?:State|StateMachine|Motion): \{fileID: (-?\d+)\}", body))
    return guids


def reference_curves(tree, exported):
    """Map source reference values onto imported Transform and named Animator curves."""
    paths = defaultdict(set)
    # Unity folds long YAML scalars after saving imported clips. Continuation
    # indentation is six spaces, while the next curve/field starts at two/four.
    for path in re.findall(r"^    path: ?([^\n]*(?:\n      [^\n]+)*)", exported, re.M):
        path = path.replace("\n      ", " ")
        if path.startswith('"'):
            path = json.loads(path)
        paths[zlib.crc32(path.encode())].add(path)
    values = tree["m_MuscleClip"]["m_ValueArrayReferencePose"]
    bindings = tree["m_ClipBindingConstant"]["genericBindings"]
    parameters = defaultdict(set)
    if any(binding["typeID"] != 4 for binding in bindings):
        floats = re.search(r"^  m_FloatCurves:\n(.*?)(?=^  \w|\Z)", exported, re.M | re.S)
        if floats:
            for name in re.findall(r"^    attribute: (.+)\n    path: *\n    classID: 95$", floats[1], re.M):
                parameters[zlib.crc32(name.encode())].add(name)
        for binding in bindings:
            if binding["typeID"] == 4:
                continue
            if (
                binding["typeID"] != 95
                or binding["path"] != 0
                or binding.get("customType")
                or binding.get("isPPtrCurve")
                or len(parameters[binding["attribute"]]) != 1
            ):
                return None
    if not values:
        return []
    curves, offset = [], 0
    for binding in bindings:
        attribute = binding["attribute"]
        if binding["typeID"] == 95:
            if offset >= len(values) or not math.isfinite(values[offset]):
                raise RuntimeError("Invalid native additive reference-pose values")
            curves.append(dict(path="", property=next(iter(parameters[attribute])), value=values[offset], animator=True))
            offset += 1
            continue
        candidates = paths[binding["path"]]
        if binding["typeID"] != 4 or binding.get("isPPtrCurve") or attribute not in (1, 2, 3, 4) or len(candidates) != 1:
            raise RuntimeError("Unsupported or ambiguous native additive reference binding: " + str(binding))
        property_name = {1: "m_LocalPosition", 2: "m_LocalRotation", 3: "m_LocalScale", 4: "localEulerAnglesRaw"}[attribute]
        axes = "xyzw" if attribute == 2 else "xyz"
        for axis in axes:
            if offset >= len(values) or not math.isfinite(values[offset]):
                raise RuntimeError("Invalid native additive reference-pose values")
            curves.append(dict(path=next(iter(candidates)), property=property_name + "." + axis, value=values[offset]))
            offset += 1
    if offset != len(values):
        raise RuntimeError("Native additive reference-pose binding cardinality changed")
    return curves


def bandit_gesture_layers(tree, controller):
    """Recover the synced layer and source motions omitted by the controller export."""
    names = dict(tree["m_TOS"])
    constant = tree["m_Controller"]
    layers = {names[row["data"]["m_Binding"]]: row["data"] for row in constant["m_LayerArray"]}
    base_name, override_name = "Gesture, Additive", "Gesture, Override"
    base, override = layers[base_name], layers[override_name]
    machine = base["m_StateMachineIndex"]
    if (override["m_StateMachineIndex"], base["m_StateMachineSynchronizedLayerIndex"], override["m_StateMachineSynchronizedLayerIndex"]) != (machine, 0, 1):
        raise RuntimeError("Original Bandit gesture layers changed their synchronized grouping")
    motions = []
    for row in constant["m_StateMachineArray"][machine]["data"]["m_StateConstantArray"]:
        state = row["data"]
        base_slot, override_slot = state["m_BlendTreeConstantIndexArray"]
        if override_slot == -1:
            continue
        if (base_slot, override_slot) != (-1, 0):
            raise RuntimeError("Original Bandit gesture has a distinct motion in both layers")
        motions.append(names[state["m_NameID"]])
    return dict(controller=controller, base=base_name, override=override_name, override_only=motions)


def bandit_side_weapon_motions(tree, clip_name):
    """Read SideWeapon's native motion slots without changing the base or StealthWeapon."""
    names = dict(tree["m_TOS"])
    constant = tree["m_Controller"]
    layers = {names[row["data"]["m_Binding"]]: row["data"] for row in constant["m_LayerArray"]}
    base, side, stealth = (layers[name] for name in ("Body", "Body, SideWeapon", "Body, StealthWeapon"))
    machine = base["m_StateMachineIndex"]
    if any(
        (layer["m_StateMachineIndex"], layer["m_StateMachineSynchronizedLayerIndex"]) != (machine, index) for index, layer in enumerate((base, side, stealth))
    ):
        raise RuntimeError("Original Bandit weapon layers changed their synchronized grouping")

    motions = []
    for row in constant["m_StateMachineArray"][machine]["data"]["m_StateConstantArray"]:
        state = row["data"]
        _, side_slot, _ = state["m_BlendTreeConstantIndexArray"]
        if side_slot == -1:
            continue
        nodes = [row["data"] for row in state["m_BlendTreeConstantArray"][side_slot]["data"]["m_NodeArray"]]
        root = nodes[0]
        motion = dict(state=names[state["m_NameID"]])
        if not root["m_ChildIndices"]:
            motion["clip"] = clip_name(root["m_ClipID"])
        else:
            children = [nodes[index] for index in root["m_ChildIndices"]]
            kind = root["m_BlendType"]
            if kind not in (0, 3) or any(node["m_ChildIndices"] for node in children):
                raise RuntimeError("Unsupported original Bandit SideWeapon blend tree: " + motion["state"])
            motion.update(kind=kind, parameter=names[root["m_BlendEventID"]])
            if kind == 0:
                thresholds = root["m_Blend1dData"]["data"]["m_ChildThresholdArray"]
                coordinates = [dict(threshold=value) for value in thresholds]
            else:
                motion["parameter_y"] = names[root["m_BlendEventYID"]]
                positions = root["m_Blend2dData"]["data"]["m_ChildPositionArray"]
                coordinates = [dict(position=value) for value in positions]
            motion["children"] = [
                dict(position, clip=clip_name(node["m_ClipID"]), time_scale=1 / node["m_Duration"], cycle_offset=node["m_CycleOffset"], mirror=node["m_Mirror"])
                for node, position in zip(children, coordinates, strict=True)
            ]
        motions.append(motion)
    return motions


def exported_clip_name(text):
    name = re.search(r"^  m_Name: (.*)$", text, re.M)[1]
    return json.loads(name) if name.startswith('"') else name


def stage_bandit_side_weapon(io, controller, source, tree, *, code_only):
    from UnityPy.classes.PPtr import PPtr

    root = io.project / "Assets/WholeGame"
    export = io.resolve(io.read(io.work / "config/reconstruction.json")["projects"][0]) / "Assets"
    folder = (io.project / controller).relative_to(root).parent
    clips = {exported_clip_name(io.read_text(path)): path for path in io.glob(export / folder, "**/*.anim")}

    def clip_path(index):
        pointer = tree["m_AnimationClips"][index]
        clip = PPtr(assetsfile=source.assets_file, **pointer).deref()
        if clip.type.name != "AnimationClip":
            raise RuntimeError("Original Bandit SideWeapon motion does not reference a clip")
        path = clips[clip.peek_name()]
        target = root / path.relative_to(export)
        for suffix in ("", ".meta"):
            asset = Path(str(target) + suffix)
            if not io.is_file(asset):
                if code_only:
                    raise RuntimeError("Bandit SideWeapon clips changed; a content build is required")
                io.apply(asset, copy=Path(str(path) + suffix), catalog=True)
        return str(target.relative_to(io.project))

    motions = bandit_side_weapon_motions(tree, clip_path)
    return dict(controller=controller, motions=motions)


def stage_additive_reference_poses(io, *, code_only=False):
    """Discover current native additive clips, retaining source identity and pose values locally."""
    import UnityPy
    from common import game, sha
    from whole_catalog import catalog_path, read_catalog

    root = io.project / "Assets/WholeGame"
    requested = set()
    bandit = None
    for controller in io.glob(root, "**/*.controller"):
        # These controllers have exact-editor coverage for their source gestures.
        aim_only = controller.stem not in {"animCommando", "animHuntress", "animCaptain", "animBandit2", "animMage"}
        override_layer = "Gesture, Override" if controller.stem == "animBandit2" else None
        requested.update(additive_clip_guids(io.read_text(controller), aim_only=aim_only, override_layer=override_layer))
        if controller.stem == "animBandit2":
            bandit = str(controller.relative_to(io.project))
    clips = {}
    for meta in io.glob(root, "**/*.anim.meta"):
        guid = re.search(r"^guid: ([a-f0-9]{32})$", io.read_text(meta), re.M)
        if guid and guid[1] in requested:
            clip = Path(str(meta)[:-5])
            text = io.read_text(clip)
            name = exported_clip_name(text)
            key = (str(Path("Assets") / clip.relative_to(root).parent).lower(), name)
            if key in clips:
                raise RuntimeError("Ambiguous exported native additive clip: " + str(key) + ": " + str(clips[key][0]) + ": " + str(clip))
            clips[key] = (clip, text)
            requested.remove(guid[1])
    if requested:
        raise RuntimeError("Native additive layer references an absent exported clip")
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
        raise RuntimeError("Native additive inspection requires the accepted input inventory")
    file_index = defaultdict(list)
    for row in inventory["files"]:
        file_index[Path(row["path"]).name].append(row)
    found = {}
    gesture = None
    side_weapon = None
    for identity in sorted(bundle_ids):
        basename = locations[identity]["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
        matches = file_index[basename]
        if len(matches) != 1:
            raise RuntimeError("Ambiguous or absent native additive bundle")
        source = game(io.work) / matches[0]["path"]
        if sha(source) != matches[0]["sha256"]:
            raise RuntimeError("Original additive bundle drift; explicitly review and accept")
        environment = UnityPy.load(str(source))
        for obj in environment.objects:
            if bandit and obj.type.name == "AnimatorController" and obj.peek_name() == "animBandit2":
                if gesture is not None:
                    raise RuntimeError("Ambiguous original Bandit gesture controller")
                tree = obj.read_typetree()
                gesture = bandit_gesture_layers(tree, bandit)
                side_weapon = stage_bandit_side_weapon(io, bandit, obj, tree, code_only=code_only)
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
                curves = reference_curves(tree, text)
                row = dict(
                    clip=str(clip.relative_to(io.project)),
                    source=matches[0]["path"],
                    source_sha256=matches[0]["sha256"],
                    identities=[dict(serialized_file=asset.assets_file.name, path_id=asset.path_id)],
                    curves=curves or [],
                    status="unsupported-muscle-bindings" if curves is None else "source-reference" if curves else "no-source-reference",
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
        raise RuntimeError("Native additive clip missing from current source containers")
    result = dict(input_id=inventory["input_id"], clips=sorted(found.values(), key=lambda row: row["clip"]))
    if bandit:
        if gesture is None:
            raise RuntimeError("Original Bandit gesture controller missing from accepted additive bundles")
        result["bandit_gesture_layers"] = gesture
        result["bandit_side_weapon"] = side_weapon
    path = io.project / ".rebuild/source-animation-reference-poses.json"
    if code_only:
        if not io.is_file(path) or io.read(path) != result:
            raise RuntimeError("Original additive reference poses changed; a content build is required")
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
