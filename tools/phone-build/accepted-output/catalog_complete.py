"""Complete a pinned source catalog against actual produced Android containers.

Typed identity follows pinned R2API AddressReferencedAsset; duplicate container
keys follow UnityPy ContainerHelper, but invalid endpoints are never skipped.
This validates advertised endpoints, not every gameplay reference in a bundle.
"""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


W = module("_catalog_complete_write", HERE / "unity_write.py")
S = module("_catalog_complete_identity", ROOT / "scripts/lab/script_identity.py")
# Public Unity ClassIDType values; RuntimeAnimatorController is an abstract base.
NATIVE_TYPES = {
    "GameObject": {1},
    "Material": {21},
    "Texture2D": {28},
    "Mesh": {43},
    "Shader": {48},
    "PhysicMaterial": {134},
    "Cubemap": {89},
    "Avatar": {90},
    "RuntimeAnimatorController": {91, 221},
    "AnimationClip": {74},
    "Font": {128},
    "TerrainData": {156},
    "AnimatorOverrideController": {221},
    "Sprite": {213},
    "AvatarMask": {319},
    "LightingSettings": {850595691},
}


def text(stream):
    (size,) = W.B.unpack(stream, "<I")
    value = W.B.exact(stream, size).decode("utf-8")
    W.B.align(stream)
    return value


def containers(body):
    """Retain every duplicate key and its own preload interval."""
    stream = io.BytesIO(body)
    text(stream)
    (count,) = W.B.unpack(stream, "<I")
    preload = [W.B.unpack(stream, "<iq") for _ in range(count)]
    (count,) = W.B.unpack(stream, "<I")
    rows = []
    for _ in range(count):
        path = text(stream)
        start, size, file_id, path_id = W.B.unpack(stream, "<iiiq")
        if start < 0 or size < 0 or start + size > len(preload):
            raise ValueError("container preload extent invalid: " + path)
        rows.append((path, (file_id, path_id), preload[start : start + size]))
    W.B.exact(stream, 24)  # main asset and runtime compatibility
    text(stream)
    (count,) = W.B.unpack(stream, "<I")
    for _ in range(count):
        text(stream)
    (scene,) = W.B.unpack(stream, "<?")
    return rows, scene


def script_identity(body):
    stream = io.BytesIO(body)
    text(stream)
    W.B.exact(stream, 20)  # execution order and properties hash
    name, namespace, assembly = text(stream), text(stream), text(stream)
    return name, namespace, assembly


class ProducedMembers:
    def __init__(self):
        self.members = {}
        self.bundles = {}

    def add(self, name, stream, bundle):
        if name in self.members:
            raise ValueError("duplicate produced serialized member: " + name)
        layout = W.read_serialized(stream)
        if layout["platform"] != 13:
            raise ValueError("expected produced Android serialized member")
        self.members[name] = (stream, layout, {row["path_id"]: row for row in layout["objects"]})
        self.bundles.setdefault(bundle, []).append(name)

    def record(self, member, pointer):
        file_id, path_id = pointer
        layout = self.members[member][1]
        if not 0 <= file_id <= len(layout["externals"]) or not path_id:
            raise ValueError("invalid produced PPtr: " + str(pointer))
        if file_id:
            member = layout["externals"][file_id - 1]["path"].rsplit("/", 1)[-1]
        if member not in self.members or path_id not in self.members[member][2]:
            raise ValueError("missing produced PPtr target: " + member + ":" + str(path_id))
        stream, layout, records = self.members[member]
        row = records[path_id]
        stream.seek(layout["data_offset"] + row["offset"])
        return member, layout["types"][row["type_id"]], W.B.exact(stream, row["bytes"])

    def managed_identity(self, member, typ, body):
        if len(body) < 28:
            raise ValueError("truncated produced MonoBehaviour")
        script_member, script_type, script = self.record(member, struct.unpack_from("<iq", body, 16))
        if script_type["class_id"] != 115:
            raise ValueError("produced m_Script is not a MonoScript")
        identity = script_identity(script)
        if typ["script_id"] != S.md4("".join(identity).encode()):
            raise ValueError("produced MonoScript binding differs from serialized type")
        return identity


def validate_locations(metadata, members, registry):
    runtime_scripts = set()
    for member in members.bundles[registry]:
        layout = members.members[member][1]
        for path_id, row in members.members[member][2].items():
            if layout["types"][row["type_id"]]["class_id"] == 115:
                _, _, body = members.record(member, (0, path_id))
                runtime_scripts.add(script_identity(body))
    advertised = {}
    for bundle in set(row["bundle"] for row in metadata["locations"]):
        for member in members.bundles.get(bundle, []):
            layout = members.members[member][1]
            for path_id, row in members.members[member][2].items():
                if layout["types"][row["type_id"]]["class_id"] != 142:
                    continue
                _, _, body = members.record(member, (0, path_id))
                entries, scene = containers(body)
                for path, pointer, preload in entries:
                    for reference in preload:
                        members.record(member, reference)
                    if pointer == (0, 0):
                        if not scene or not path.lower().endswith(".unity") or preload:
                            raise ValueError("null container root requires streamed scene")
                        actual = "scene"
                    else:
                        owner, root_type, root = members.record(member, pointer)
                        actual = root_type["class_id"]
                        if actual == 114:
                            actual = members.managed_identity(owner, root_type, root)
                            if actual not in runtime_scripts:
                                raise ValueError("catalog MonoScript absent from current runtime registry: " + str(actual))
                    advertised.setdefault((bundle, path.casefold()), []).append(actual)
    for row in metadata["locations"]:
        expected = row["type"].split(", ")
        qualified = expected[0]
        candidates = advertised.get((row["bundle"], row["path"].casefold()), [])
        if qualified == "UnityEngine.ResourceManagement.ResourceProviders.SceneInstance":
            valid = "scene" in candidates
        elif qualified == "UnityEngine.Object":
            valid = bool(candidates) and any(value != "scene" for value in candidates)
        elif qualified.startswith("UnityEngine.") and qualified.removeprefix("UnityEngine.") in NATIVE_TYPES:
            valid = any(value in NATIVE_TYPES[qualified.removeprefix("UnityEngine.")] for value in candidates if isinstance(value, int))
        else:
            namespace, _, name = qualified.rpartition(".")
            identity = (name, namespace, expected[1] + ".dll")
            valid = identity in candidates
        if not valid:
            raise ValueError(
                "catalog endpoint absent or type differs: " + str(row["id"]) + " " + row["path"] + " expected " + qualified + " actual " + str(candidates)
            )
    return dict(locations=len(metadata["locations"]), container_paths=len(advertised), runtime_scripts=len(runtime_scripts))


def produce(inputs, output):
    inputs = Path(inputs).resolve(strict=True)
    request_bytes = inputs.read_bytes()
    request = json.loads(request_bytes)
    if (
        set(request) - {"resources"} != {"schema", "metadata", "profiles", "bundles", "registry", "input_id", "attempt"}
        or request["schema"] != "owner-catalog-inputs-v1"
    ):
        raise ValueError("unsupported catalog completion input contract")
    pins = {}

    def pinned(row):
        if set(row) != {"path", "sha256", "bytes"}:
            raise ValueError("unsupported catalog input pin")
        path = Path(row["path"])
        path = (inputs.parent / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)
        pin = dict(bytes=path.stat().st_size, sha256=W.B.sha(path))
        if pin != {key: row[key] for key in pin}:
            raise ValueError("catalog input differs: " + str(path))
        pins[path] = pin
        return path

    metadata = json.loads(pinned(request["metadata"]).read_bytes())
    if any(metadata[key] != request[key] for key in ("input_id", "attempt")):
        raise ValueError("catalog input/startup identity differs")
    profiles = [json.loads(pinned(row).read_bytes()) for row in request["profiles"]]
    files = {name: pinned(row) for name, row in request["bundles"].items()}
    registry = pinned(request["registry"])
    resources = {name: pinned(row) for name, row in request.get("resources", {}).items()}
    if not set(resources) <= {"unity_builtin_extra", "unity default resources"}:
        raise ValueError("unsupported player resource member")
    sys.path.insert(0, str(ROOT / "scripts/lab"))
    from whole_catalog import integration_bundle_metadata, integration_catalog, integration_profile_builds, produced_bundle_metadata

    builds = integration_profile_builds(profiles)
    metadata = integration_bundle_metadata(metadata, builds)
    names = {row["assetBundleName"] for row in builds} | {row["bundle"] for row in metadata["locations"]}
    if set(files) != names:
        raise ValueError("produced bundle population differs; missing=" + str(sorted(names - files.keys())) + " extra=" + str(sorted(files.keys() - names)))
    facts = produced_bundle_metadata(files)
    raw = integration_catalog(metadata, facts, bundle_names=names)
    members = ProducedMembers()
    for name, path in files.items():
        bundle = W.B.Bundle(path)
        for member in bundle.members:
            if not member.endswith((".resS", ".resource")):
                members.add(member, bundle.member(member), name)
    for name, path in resources.items():
        resource = io.BytesIO(path.read_bytes())
        resource.size = len(resource.getbuffer())
        members.add(name, resource, "@player-resources")
    stream = io.BytesIO(registry.read_bytes())
    stream.size = len(stream.getbuffer())
    members.add(registry.name, stream, "@runtime-registry")
    checks = validate_locations(metadata, members, "@runtime-registry")
    if inputs.read_bytes() != request_bytes or any(dict(bytes=path.stat().st_size, sha256=W.B.sha(path)) != pin for path, pin in pins.items()):
        raise ValueError("catalog inputs changed during production")
    output = Path(output)
    output.mkdir(exist_ok=False)
    (output / "whole-catalog.json").write_bytes(raw)
    receipt = dict(
        success=True,
        phase="catalog-completed",
        input_sha256=hashlib.sha256(request_bytes).hexdigest(),
        producer_sha256=W.B.sha(Path(__file__)),
        input_id=request["input_id"],
        attempt=request["attempt"],
        file=dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
        bundles=facts,
        checks=checks,
        runtime_qualified=False,
        phone_qualified=False,
    )
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.inputs, args.output)))


if __name__ == "__main__":
    main()
