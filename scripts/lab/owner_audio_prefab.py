"""Reconstruct one input-bound audio prefab from owner PC bundle data.

Experimental host support only: no Editor/exporter, target asset supplier or
runtime mutation. The single external GUID is audited export configuration.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from common import ROOT, read, write
from owner_assemblies import input_state
from script_identity import script_file_id


PROFILE = ROOT / "recipe/owner-audio-prefab.json"
PROFILE_SHA = "80c350f032d5af6ffa694dc1cef26d728ea9e54771bab8e41c05d9fd29a7d8a3"
ASSEMBLIES_SHA = "4d6ae8cd68b04a9df810460981f22ba64368a084f515f49153c9dfe9111d35e0"
BASE_MONO = {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}
SCRIPT_FIELDS = {
    "AK.Wwise.Unity.MonoBehaviour.dll|AkTerminator": BASE_MONO,
    "AK.Wwise.Unity.MonoBehaviour.dll|AkInitializer": BASE_MONO | {"InitializationSettings"},
    "RoR2.dll|RoR2.WwiseUtils.SoundbankLoader": BASE_MONO | {"soundbankStrings", "decodeBank", "saveDecodedBank"},
}


class Flow(dict):
    """A versioned Unity YAML inline value, not a separate asset supplier."""


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export_id(class_id, ordinal):
    """Class prefix plus the mathematical empty-input XXH64 seeded avalanche."""
    mask = (1 << 64) - 1
    value = (ordinal + 2870177450012600261) & mask
    value ^= value >> 33
    value = (value * 14029467366897019727) & mask
    value ^= value >> 29
    value = (value * 1609587929392839161) & mask
    return class_id * 10**15 + (value ^ (value >> 32)) % 10**15


def script_key(script):
    name = (script["namespace"] + "." if script["namespace"] else "") + script["class"]
    return script["assembly"] + "|" + name


def scalar(value):
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("unqualified non-finite prefab scalar")
        original = struct.pack("<f", value)
        for digits in range(1, 10):
            candidate = format(value, "." + str(digits) + "g")
            if struct.pack("<f", float(candidate)) == original:
                return candidate
        raise ValueError("float representation unavailable")
    if isinstance(value, Flow):
        return "{" + ", ".join(k + ": " + scalar(v) for k, v in value.items()) + "}"
    if isinstance(value, str):
        if any(c in value for c in "\r\n\0"):
            raise ValueError("unqualified multiline/control scalar")
        if not value:
            return ""
        if (re.fullmatch(r"[0-9a-f]{32}", value) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_./ -]*", value)) and value.lower() not in {
            "true",
            "false",
            "null",
            "yes",
            "no",
            "on",
            "off",
        }:
            return value
        return "'" + value.replace("'", "''") + "'"
    raise ValueError("unsupported prefab scalar")


def emit(mapping, indent=2):
    lines, space = [], " " * indent
    for key, value in mapping.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError("unqualified field name")
        if isinstance(value, list):
            if not value:
                lines.append(space + key + ": []")
                continue
            lines.append(space + key + ":")
            for item in value:
                if isinstance(item, dict) and not isinstance(item, Flow):
                    if len(item) != 1:
                        raise ValueError("unqualified sequence mapping")
                    name, member = next(iter(item.items()))
                    lines.append(space + "- " + name + ": " + scalar(member))
                else:
                    lines.append(space + "- " + scalar(item))
        elif isinstance(value, dict) and not isinstance(value, Flow):
            lines.append(space + key + ":")
            lines.extend(emit(value, indent + 2))
        else:
            lines.append(space + key + (":" if value == "" else ": " + scalar(value)))
    return lines


def render(rows, assembly_guids, external):
    """Serialize the supported rooted source graph; reject unknown relationships."""
    if len(rows) < 2 or [r["type"] for r in rows[:2]] != ["GameObject", "Transform"] or any(r["type"] != "MonoBehaviour" for r in rows[2:]):
        raise ValueError("unsupported prefab object graph")
    ids = {r["path_id"]: export_id(r["class_id"], i) for i, r in enumerate(rows)}
    if len(ids) != len(rows) or len(set(ids.values())) != len(rows):
        raise ValueError("duplicate source/export object identity")
    root = rows[0]["path_id"]
    refs = rows[0]["tree"].get("m_Component", [])
    if [r.get("component") for r in refs] != [{"m_FileID": 0, "m_PathID": r["path_id"]} for r in rows[1:]]:
        raise ValueError("component order/ownership differs")

    def convert(value):
        if isinstance(value, dict):
            if set(value) == {"m_FileID", "m_PathID"}:
                file_id, path_id = value["m_FileID"], value["m_PathID"]
                if path_id == 0:
                    return Flow(fileID=0)
                if file_id == 0 and path_id in ids:
                    return Flow(fileID=ids[path_id])
                if (file_id, path_id) in external:
                    return Flow(external[(file_id, path_id)])
                raise ValueError("unknown prefab reference")
            if value and set(value) <= {"x", "y", "z", "w"}:
                return Flow((k, convert(v)) for k, v in value.items())
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value

    lines = ["%YAML 1.1", "%TAG !u! tag:unity3d.com,2011:"]
    for row in rows:
        raw, kind = row["tree"], row["type"]
        expected_class = {"GameObject": 1, "Transform": 4, "MonoBehaviour": 114}[kind]
        if row["class_id"] != expected_class:
            raise ValueError("source class identity differs")
        if kind != "GameObject" and raw.get("m_GameObject") != {"m_FileID": 0, "m_PathID": root}:
            raise ValueError("component points outside source root")
        body = {"m_ObjectHideFlags": 0, "m_CorrespondingSourceObject": Flow(fileID=0), "m_PrefabInstance": Flow(fileID=0), "m_PrefabAsset": Flow(fileID=0)}
        if kind == "GameObject":
            if set(raw) != {"m_Component", "m_Layer", "m_Name", "m_Tag", "m_IsActive"} or raw["m_Tag"] != 0:
                raise ValueError("unsupported GameObject schema/tag")
            body = {"serializedVersion": 6, **body}
            body.update({k: convert(raw[k]) for k in ("m_Component", "m_Layer", "m_Name")})
            body.update(m_TagString="Untagged", m_Icon=Flow(fileID=0), m_NavMeshLayer=0, m_StaticEditorFlags=0, m_IsActive=raw["m_IsActive"])
        elif kind == "Transform":
            if (
                set(raw) != {"m_GameObject", "m_LocalRotation", "m_LocalPosition", "m_LocalScale", "m_Children", "m_Father"}
                or raw["m_LocalRotation"] != {"x": 0, "y": 0, "z": 0, "w": 1}
                or raw["m_Children"]
                or raw["m_Father"] != {"m_FileID": 0, "m_PathID": 0}
            ):
                raise ValueError("unsupported root transform")
            body.update({k: convert(raw[k]) for k in ("m_GameObject", "m_LocalRotation", "m_LocalPosition", "m_LocalScale")})
            body.update(
                m_ConstrainProportionsScale=0, m_Children=[], m_Father=Flow(fileID=0), m_RootOrder=0, m_LocalEulerAnglesHint=Flow(x=0.0, y=-0.0, z=-0.0)
            )
        else:
            script = row["script"]
            key = script_key(script)
            if key not in SCRIPT_FIELDS or set(raw) != SCRIPT_FIELDS[key] or script["assembly"] not in assembly_guids:
                raise ValueError("unsupported source script/schema")
            body.update(
                m_GameObject=convert(raw["m_GameObject"]),
                m_Enabled=raw["m_Enabled"],
                m_EditorHideFlags=0,
                m_Script=Flow(fileID=script_file_id(script["namespace"], script["class"]), guid=assembly_guids[script["assembly"]], type=3),
                m_Name=raw["m_Name"],
                m_EditorClassIdentifier="",
            )
            body.update({k: convert(v) for k, v in raw.items() if k not in BASE_MONO})
        lines.extend(["--- !u!" + str(row["class_id"]) + " &" + str(ids[row["path_id"]]), kind + ":", *emit(body)])
    return ("\n".join(lines) + "\n").encode()


def reconstruct(work, output):
    work, output = Path(work), Path(output)
    if (
        not work.is_absolute()
        or work != work.resolve(strict=True)
        or not output.is_absolute()
        or ".." in output.parts
        or output.parent != output.parent.resolve(strict=True)
    ):
        raise ValueError("canonical owner work and new output required")
    if not output.is_relative_to(work) or output == work or output.exists() or output.is_symlink():
        raise ValueError("new output must be inside owner work")
    if sha(PROFILE) != PROFILE_SHA or sha(ROOT / "recipe/original-assemblies.json") != ASSEMBLIES_SHA:
        raise ValueError("audited identity recipe changed")
    profile = read(PROFILE)
    identity, game, receipts = input_state(work)
    if identity != profile["input_id"] or output.is_relative_to(game) or game.is_relative_to(output):
        raise ValueError("unsupported input or output/source overlap")
    output.mkdir()
    result = {"schema": 1, "success": False, "input_id": identity, "editor_or_exporter_used": False, "phone_qualified": False}
    try:
        import UnityPy

        if UnityPy.__version__ != profile["unitypy_version"]:
            raise ValueError("source parser version differs")
        env, source_hashes = UnityPy.Environment(), {}
        for row in profile["inputs"]:
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe source path")
            path = game / relative
            if path != path.resolve(strict=True) or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
                raise ValueError("original bundle differs")
            source_hashes[row["path"]] = row["sha256"]
            env.load_file(str(path))
        primary = [o for o in env.objects if o.assets_file.name == profile["primary_collection"]]
        roots = [o for o in primary if o.path_id == profile["root"]["path_id"] and int(o.type) == profile["root"]["class_id"]]
        if len(roots) != 1 or roots[0].read_typetree().get("m_Name") != profile["root"]["name"]:
            raise ValueError("source root identity differs")
        go = roots[0]
        objects = {o.path_id: o for o in primary}
        selected = [go]
        for pointer in go.read_typetree()["m_Component"]:
            pointer = pointer["component"]
            if pointer["m_FileID"] != 0 or pointer["m_PathID"] not in objects:
                raise ValueError("unknown component reference")
            selected.append(objects[pointer["m_PathID"]])
        if dict(Counter(o.type.name for o in selected)) != profile["object_counts"]:
            raise ValueError("source object family differs")
        rows = []
        for obj in selected:
            row = {"path_id": obj.path_id, "type": obj.type.name, "class_id": int(obj.type), "tree": obj.read_typetree()}
            if obj.type.name == "MonoBehaviour":
                script = obj.read().m_Script.read()
                row["script"] = {"assembly": script.m_AssemblyName, "namespace": script.m_Namespace, "class": script.m_ClassName}
            rows.append(row)
        if dict(Counter(script_key(r["script"]) for r in rows if "script" in r)) != profile["script_counts"]:
            raise ValueError("source script family differs")
        external = {}
        for binding in profile["external_bindings"]:
            index = binding["source_file_id"]
            path = go.assets_file.externals[index - 1].path
            if path.rsplit("/", 1)[-1] != binding["source_collection"]:
                raise ValueError("external source collection differs")
            candidates = [o for o in env.objects if o.path_id == binding["source_path_id"] and o.assets_file.name == binding["source_collection"]]
            if (
                len(candidates) != 1
                or int(candidates[0].type) != binding["source_class_id"]
                or candidates[0].read_typetree().get("m_Name") != binding["source_name"]
            ):
                raise ValueError("external asset identity differs")
            script = candidates[0].read().m_Script.read()
            if script_key({"assembly": script.m_AssemblyName, "namespace": script.m_Namespace, "class": script.m_ClassName}) != binding["source_script"]:
                raise ValueError("external script identity differs")
            external[(index, binding["source_path_id"])] = binding["export"]
        assemblies = read(ROOT / "recipe/original-assemblies.json")
        value = render(rows, {r["source"]: r["guid"] for r in assemblies["assemblies"]}, external)
        if len(value) != profile["output"]["bytes"] or hashlib.sha256(value).hexdigest() != profile["output"]["sha256"]:
            raise ValueError("complete prefab output differs")
        if any(sha(game / path) != digest for path, digest in source_hashes.items()) or input_state(work) != (identity, game, receipts):
            raise ValueError("owner input changed during reconstruction")
        destination = output / "WwiseGlobal.prefab"
        with destination.open("xb") as stream:
            stream.write(value)
        if sha(destination) != profile["output"]["sha256"]:
            raise ValueError("complete prefab readback differs")
        result.update(
            success=True,
            bytes=len(value),
            prefab_sha256=sha(destination),
            source_hashes=source_hashes,
            inventory_receipts=receipts,
            producer_sha256=sha(Path(__file__)),
            profile_sha256=PROFILE_SHA,
            object_count=len(rows),
            script_count=sum("script" in r for r in rows),
            external_guid_is_export_configuration=True,
        )
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        write(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new private directory inside owner work")
    args = parser.parse_args()
    result = reconstruct(args.owner_work, args.output)
    print(json.dumps({k: result[k] for k in ("success", "bytes", "prefab_sha256", "object_count", "script_count")}, indent=2))


if __name__ == "__main__":
    main()
