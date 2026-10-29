"""Generate stage population and identity contexts from original serialized records.

Public selectors pin legitimate inputs, never accepted output or exported scenes.
Original member digests replace historical exporter hashes with explicit provenance.
"""

import argparse
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import time

try:
    from . import player_ui as U
except ImportError:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_contexts_ui", Path(__file__).with_name("player_ui.py"))
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)

ROOT = Path(__file__).resolve().parents[3]
FILE = "2be99f2f55a9941d98f7de611a7b9288"
TARGET = "apk/assets/bin/Data/" + FILE
I = U.module("_contexts_identity", ROOT / "scripts/lab/source_identity_metadata.py")
C = U.module("_contexts_catalog", ROOT / "scripts/lab/catalog_reader.py")
P, W = U.P, U.W


def single(value):
    """The shortest decimal preserving the original Single, as in scene export."""
    bits = struct.pack("<f", value)
    for digits in range(1, 10):
        rounded = float(format(value, "." + str(digits) + "g"))
        if struct.pack("<f", rounded) == bits:
            return rounded
    raise ValueError("no finite Single round trip")


def local(pointer):
    U.require(pointer["m_FileID"] == 0, "stage hierarchy pointer is external")
    return str(pointer["m_PathID"])


def graph_records(asset, suppression):
    games, transforms, identities, toggles = {}, {}, [], []
    for obj in asset.objects.values():
        kind = obj.type.value
        if kind not in (1, 4, 224, 114):
            continue
        fields = obj.read_typetree()
        key = str(obj.path_id)
        if kind == 1:
            games[key] = dict(name=fields["m_Name"], active_self=bool(fields["m_IsActive"]))
        elif kind in (4, 224):
            transforms[key] = dict(
                gameObject=local(fields["m_GameObject"]),
                father=local(fields["m_Father"]),
                children=[local(p) for p in fields["m_Children"]],
                rootOrder=fields.get("m_RootOrder", 0),
            )
        elif "m_SceneId" in fields:
            identities.append(
                dict(
                    scene_id=fields["m_SceneId"]["m_Value"], source_component_file_id=obj.path_id, source_game_object_file_id=int(local(fields["m_GameObject"]))
                )
            )
        elif "toggleGroups" in fields:
            groups = [dict(min_enabled=g["minEnabled"], max_enabled=g["maxEnabled"], objects=[local(p) for p in g["objects"]]) for g in fields["toggleGroups"]]
            toggles.append(dict(source_component_file_id=obj.path_id, source_game_object_file_id=int(local(fields["m_GameObject"])), groups=groups))
    # Original binary records do not retain YAML's synthesized sibling index.
    for parent in transforms.values():
        for index, child in enumerate(parent["children"]):
            U.require(transforms[child]["father"] != "0", "child is also a hierarchy root")
            transforms[child]["rootOrder"] = index
    if suppression is not None:
        roots = [row["gameObject"] for row in transforms.values() if row["father"] == "0"]
        selected = [key for key in roots if games[key]["name"] in suppression["required"] + suppression["optional"]]
        names = [games[key]["name"] for key in selected]
        U.require(all(names.count(name) == 1 for name in suppression["required"]) and len(names) == len(set(names)), "global source roots differ")
        for key in selected:
            games[key]["active_self"] = False
    return games, transforms, identities, toggles


def population(asset, selected, pools, games, transforms):
    classic = asset.objects[selected["classic_stage_info"]].read_typetree()
    director = asset.objects[selected["scene_director"]].read_typetree()
    boolean = ("ignoreArtifactsThatRebuildCards", "contentSourceMixLimitOverride", "contentInteractableOnlySourceMixLimitOverride")
    integer = (
        "contentSourceMixLimitOverrideValue",
        "contentInteractableOnlySourceMixLimitOverrideValue",
        "sceneDirectorInteractibleCredits",
        "sceneDirectorMonsterCredits",
    )
    result = dict(
        fields={**{k: bool(classic[k]) for k in boolean}, **{k: int(classic[k]) for k in integer}},
        director_fields={
            k: bool(director[k]) if k == "usePlacedSpawnPoints" else single(director[k])
            for k in ("usePlacedSpawnPoints", "expRewardCoefficient", "eliteBias", "spawnDistanceMultiplier")
        },
    )
    U.require(director["monsterSpawnTargetOverride"] == dict(m_FileID=0, m_PathID=0), "unsupported original monster target override")
    for name in ("monsterDccsPool", "interactableDccsPool"):
        result[name] = pools[U.reference_key(asset, classic[name])]
    owners = {row["gameObject"]: key for key, row in transforms.items()}

    def path(pointer):
        current, names, seen = owners[local(pointer)], [], set()
        while current != "0":
            U.require(current not in seen, "cyclic bonus-credit path")
            seen.add(current)
            row = transforms[current]
            names.append(games[row["gameObject"]]["name"])
            current = row["father"]
        return "/".join(reversed(names))

    result["bonus_credits"] = [
        dict(path=path(row["objectThatGrantsPointsIfEnabled"]), points=row["points"]) for row in classic["bonusInteractibleCreditObjects"]
    ]
    return result


def identity_metadata(records, source_hash, profile_hash, producer_hash):
    value = I.from_records(*records, source_hash)
    value.pop("source_scene_sha256")
    provenance = dict(original_scene_sha256=source_hash, identity_graph=value, profile_sha256=profile_hash, producer_sha256=producer_hash)
    value["source_scene_sha256"] = hashlib.sha256(json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    value.update(source_hash_representation="canonical-source-identity-graph-v1", original_scene_sha256=source_hash)
    return value


def pool_locations(sources, profile):
    catalog = sources.json(P.OBJECTS.M.safe_input(sources.pc, profile["catalog"]["path"]), profile["catalog"])
    del catalog  # The same pinned file is decoded by the shared catalog owner.
    catalog = C.read_shipped(sources.pc / profile["catalog"]["path"], "runtime", dict(labels=[], providers=[]))
    rows = [r for r in catalog["locations"] if (r["type"] or "").startswith("RoR2.DccsPool,")]
    keys = {r["internalId"].casefold(): r["primaryKey"] for r in rows}
    bundles = {catalog["locations"][catalog["dependencySets"][r["dependencySet"]][0]]["primaryKey"] for r in rows}
    selected = {Path(row["path"]).name: row for row in profile["pool_sources"]}
    U.require(set(selected) == bundles, "catalog pool suppliers differ from the admitted sources")
    locations = {}
    for name in sorted(bundles):
        source = selected[name]
        path = P.OBJECTS.M.safe_input(sources.pc, source["path"])
        sources.pin(path, source)
        with closing(U.Sources(sources.pc)) as readers:
            bundle = W.B.Bundle(path)
            for member, (_, _, flags) in bundle.members.items():
                if not flags & 4:
                    continue
                asset = readers.asset(dict(source, member=member))
                for obj in asset.objects.values():
                    if obj.type.value == 142:
                        for key, entry in obj.read_typetree()["m_Container"]:
                            if key.casefold() in keys:
                                address = U.reference_key(asset, entry["asset"])
                                U.require(address not in locations, "ambiguous catalog pool pointer")
                                locations[address] = keys[key.casefold()]
            readers.recheck()
    U.require(len(locations) == len(keys), "catalog pool references are incomplete")
    return locations


def produce(profile_path, profile_hash, pc, output):
    profile_path = Path(profile_path).resolve(strict=True)
    U.require(P.sha(profile_path) == profile_hash, "stage context profile drift")
    profile = json.loads(profile_path.read_text())
    U.require(
        profile["schema"] == "owner-source-stage-contexts-v1" and profile["input_id"] == P.INPUT_ID and profile["file"] == FILE, "unknown stage context input"
    )
    output = Path(output)
    output = output.parent.resolve(strict=True) / output.name
    pc = Path(pc).resolve(strict=True)
    U.require(
        not output.exists() and not output.is_symlink() and not output.is_relative_to(pc) and not pc.is_relative_to(output),
        "new disjoint context output required",
    )
    output.mkdir()
    started = time.monotonic()
    result = dict(success=False, input_id=profile["input_id"], profile_sha256=profile_hash, profile=str(profile_path), pc=str(pc), source_only=True, files={})
    with closing(U.Sources(pc)) as sources:
        try:
            sources.pin(profile_path, dict(sha256=profile_hash))
            producer_pins = {
                str(path.relative_to(ROOT)): P.sha(path)
                for path in (Path(__file__), Path(U.__file__), Path(P.__file__), Path(W.__file__), Path(W.B.__file__), Path(I.__file__), Path(C.__file__))
            }
            producer_hash = hashlib.sha256(json.dumps(producer_pins, sort_keys=True).encode()).hexdigest()
            pools = pool_locations(sources, profile)
            stages = {}
            for selected in profile["scenes"]:
                stage = selected["stage"]
                U.require(stage not in stages, "duplicate stage selector")
                with closing(U.Sources(pc)) as reader:
                    asset = reader.asset(dict(selected["source"], member=selected["member"]))
                    digest = hashlib.sha256()
                    asset.stream.seek(0)
                    while chunk := asset.stream.read(65536):
                        digest.update(chunk)
                    source_hash = digest.hexdigest()
                    records = graph_records(asset, profile["global_roots"] if "identity" in selected else None)
                    context = population(asset, selected, pools, *records[:2])
                    context.update(source_sha256=source_hash, source_hash_representation="original-serialized-scene-v22")
                    if "identity" in selected:
                        context[selected["identity"]] = identity_metadata(records, source_hash, profile_hash, producer_hash)
                    stages[stage] = context
                    reader.recheck()
                    sources.pins.update(reader.pins)
                print("Generated source stage context: " + stage, flush=True)
            value = dict(input_id=profile["input_id"], scope=profile["scope"], source_identity_schema_version=1, stages=stages)
            script = json.dumps(value, indent=2, sort_keys=True) + "\n"
            (output / "WholeStageContexts.json").write_text(script)
            asset = sources.asset(profile["text_asset_source"])
            types = [t for t in asset.layout["types"] if t["class_id"] == 49]
            U.require(len(types) == 1, "original TextAsset type metadata is ambiguous")
            body = io.BytesIO()
            P.OBJECTS.aligned_string(body, "WholeStageContexts")
            P.OBJECTS.aligned_string(body, script)
            data = body.getvalue()
            layout = dict(
                engine="2021.3.45f2",
                platform=13,
                trees=False,
                types=types,
                objects=[dict(path_id=1, offset=0, bytes=len(data), type_id=0)],
                scripts=[],
                externals=[],
                ref_types=[],
                user="",
            )
            destination = output / profile["file"]
            U.require(destination.parent == output, "unsafe context output filename")
            with destination.open("xb") as target:
                W.write_serialized(target, layout, lambda _: io.BytesIO(data))
            sources.recheck()
            U.require(all(P.sha(ROOT / path) == sha for path, sha in producer_pins.items()), "context producer changed")
            result.update(
                success=True,
                stages=len(stages),
                identity_graphs=sum("identity" in r for r in profile["scenes"]),
                producer_pins=producer_pins,
                sources=sources.pins,
                raw_exact=False,
                phone_qualified=False,
                files={profile["file"]: dict(bytes=destination.stat().st_size, sha256=P.sha(destination))},
            )
            return result
        except Exception as error:
            result["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            result["seconds"] = time.monotonic() - started
            (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def verify(receipt_path, receipt_hash):
    """Regenerate the entire named file; no metadata mask admits other changes."""
    receipt_path = Path(receipt_path).resolve(strict=True)
    U.require(P.sha(receipt_path) == receipt_hash, "stage context receipt drift")
    receipt = json.loads(receipt_path.read_text())
    U.require(receipt.get("success") is True and receipt.get("source_only") is True and set(receipt["files"]) == {FILE}, "incomplete stage context receipt")
    for relative, digest in receipt["producer_pins"].items():
        U.require(P.sha(ROOT / relative) == digest, "stage context producer changed")
    with tempfile.TemporaryDirectory(prefix="source-stage-contexts-") as directory:
        produced = produce(receipt["profile"], receipt["profile_sha256"], receipt["pc"], Path(directory) / "generated")
        U.require(produced["files"] == receipt["files"], "stage context output differs from regenerated source")
    item = receipt["files"][FILE]
    output = receipt_path.parent / FILE
    U.require(output.stat().st_size == item["bytes"] and P.sha(output) == item["sha256"], "persisted stage context output differs")
    U.require(P.sha(receipt_path) == receipt_hash, "stage context receipt changed during verification")
    return {TARGET: dict(item, path=str(output))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new private output directory")
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output)


if __name__ == "__main__":
    main()
