"""Whole shipped catalog discovery; no readiness whitelist or entitlement grants."""

from common import *
from scene_closure import REFERENCE
from collections import Counter, deque
import importlib.util
import io
import re
import struct


# The original Main Camera prefab's current opt-in overlay calls these shaders
# during activation. Keep the runtime key -> typed location identities intact;
# this is a narrow profile extension, not a broad shader-catalog import.
CAMERA_SHADER_ROOTS = {
    16022: ("41e90cbc5ad198a438128b019f8d8553", "RoR2/Base/Shaders/HGOutlineHighlight.shader"),
    16025: ("5e246b703e2090148a761d52af19744b", "RoR2/Base/Shaders/HGVisionLimit.shader"),
    15950: ("c14b6abb309b8c246add9e94a6920d7f", "RoR2/Base/Shaders/RampFog.shader"),
    2537: ("e4abd95960ed75f4a9f59cac7c40bd9d", "TranslucentImage/DownTent.shader"),
    2538: ("12e87e7c7fde8e74db9f75172456c5c3", "TranslucentImage/EfficientBlur.shader"),
    2539: ("d996ab4381100014d99e25e68e9aac84", "TranslucentImage/FillCrop.shader"),
    2540: ("b12e02e9a9b684543a286089a03cb04b", "TranslucentImage/QuickDumbBlur.shader"),
    16024: ("780f79b2a62a0df439dedf59c533eee6", "RoR2/Base/Shaders/HGSobelBuffer.shader"),
    15952: ("7d6541fe01591cd418caf48d3c099e52", "RoR2/Base/Shaders/SobelOutline.shader"),
}
SHADER_LOCATION_TYPE = "UnityEngine.Shader, UnityEngine.CoreModule, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"


def camera_shader_roots(metadata, closure):
    """Return the exact source paths and IDs needed by the original camera.

    Source keys can outlive filtered location rows. Refuse malformed or
    ambiguous rows rather than emitting a partially valid camera profile.
    """
    locations = {int(row["id"]): row for row in metadata["locations"]}
    keys = {row["key"]: row for row in metadata["keys"] if row.get("keyType", "System.String") == "System.String"}
    converted = closure["converted"]
    paths = set()
    for location_id, (guid, primary_key) in CAMERA_SHADER_ROOTS.items():
        row = locations.get(location_id)
        key = keys.get(guid)
        conversion = converted.get(str(location_id))
        if not row or row.get("type") != SHADER_LOCATION_TYPE or row.get("primaryKey") != primary_key:
            raise RuntimeError("Original camera shader location changed: " + str(location_id))
        if not key or key.get("locations") != [location_id]:
            raise RuntimeError("Original camera shader address key changed: " + guid)
        if not conversion or conversion.get("resolution") != "exact" or not conversion.get("source"):
            raise RuntimeError("Original camera shader source conversion is not exact: " + str(location_id))
        source = conversion["source"]
        if not source.startswith("Assets/") or ".." in Path(source).parts:
            raise RuntimeError("Original camera shader source path is unsafe: " + source)
        paths.add(source)
    return paths


def _shader_candidate_root(io, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or path.parts[0] != "work" or ".." in path.parts:
        raise RuntimeError("Shader override candidate path must be work-relative")
    root = io.work.joinpath(*path.parts[1:])
    if not root.resolve().is_relative_to(io.work.resolve()):
        raise RuntimeError("Shader override candidate escapes work/")
    cursor = io.work
    for part in path.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise RuntimeError("Shader override candidate path contains a symlink")
    return root


def _validated_shader_overrides(io, closure, metadata, mapped, export, project, destination):
    """Apply only the exact generator-owned shader candidates at existing typed mappings."""
    recipe_path = RECIPE / "shader-catalog-overrides.json"
    selection = io.read(recipe_path)
    if set(selection) != {"schema", "input_id", "enabled", "rows"} or selection.get("schema") != "whole-catalog-shader-overrides-r1":
        raise RuntimeError("Unknown shader override selection schema")
    if selection.get("enabled") is not False:
        raise RuntimeError("Public shader override identity allowlist must remain default-off")
    if selection.get("input_id") != closure["input_id"]:
        raise RuntimeError("Shader override selection belongs to a different accepted input")
    from catalog_rebuild import read_local_shader_override_selector, translucent_candidate_identity_matches

    local_selector = read_local_shader_override_selector(io.work, closure["input_id"])
    if local_selector is None or local_selector["enabled"] is not True:
        stale_marker = project / ".rebuild/catalog-shader-overrides.json"
        if stale_marker.is_symlink() or io.is_file(stale_marker):
            raise RuntimeError("Destination has a prior shader override receipt; rebuild it from a clean destination before disabling overrides")
        return None

    expected = [
        (
            16022,
            "41e90cbc5ad198a438128b019f8d8553",
            "RoR2/Base/Shaders/HGOutlineHighlight.shader",
            "Assets/RoR2/Base/Shaders/PostProcess/HGOutlineHighlight.shader",
            "outline-highlight",
            "shader_outline.py",
            "recipe/shader-outline-candidate.json",
            "private-outline-highlight-generated-candidate-r1",
            "manifest.json",
            "sources/OutlineHighlightCandidate.shader",
            "generated_shader_path",
            "Hopoo Games/Internal/Outline Highlight",
            -5736718617091362218,
            None,
        ),
        (
            15950,
            "c14b6abb309b8c246add9e94a6920d7f",
            "RoR2/Base/Shaders/RampFog.shader",
            "Assets/RoR2/Base/Shaders/CustomPostProcess/RampFog.shader",
            "ramp-fog",
            "shader_ramp_fog.py",
            "recipe/shader-ramp-fog-candidate.json",
            1,
            "candidate.json",
            "sources/RampFogCandidate.shader",
            "generated_shader",
            "Hidden/PostProcess/RampFog",
            2910825169780710437,
            None,
        ),
        (
            2537,
            "e4abd95960ed75f4a9f59cac7c40bd9d",
            "TranslucentImage/DownTent.shader",
            "Assets/Le Tai's Asset/TranslucentImage/FormerResources/DownTent.shader",
            "translucent-camera",
            "shader_translucent.py",
            "recipe/shader-translucent-candidate.json",
            "local-source-bound-translucent-wrapper-candidate-r1",
            "manifests/DownTent.json",
            "sources/DownTent.shader",
            "generated_shader_path",
            "Hidden/DownTent",
            8446615176080386013,
            "b950b7b50f8e9734e8b26f23f8409418",
        ),
        (
            2538,
            "12e87e7c7fde8e74db9f75172456c5c3",
            "TranslucentImage/EfficientBlur.shader",
            "Assets/Le Tai's Asset/TranslucentImage/FormerResources/EfficientBlur.shader",
            "translucent-camera",
            "shader_translucent.py",
            "recipe/shader-translucent-candidate.json",
            "local-source-bound-translucent-wrapper-candidate-r1",
            "manifests/EfficientBlur.json",
            "sources/EfficientBlur.shader",
            "generated_shader_path",
            "Hidden/EfficientBlur",
            6370232586618374777,
            "f7022f9f8b1c05f45b0e69d890d31534",
        ),
        (
            2539,
            "d996ab4381100014d99e25e68e9aac84",
            "TranslucentImage/FillCrop.shader",
            "Assets/Le Tai's Asset/TranslucentImage/FormerResources/FillCrop.shader",
            "translucent-camera",
            "shader_translucent.py",
            "recipe/shader-translucent-candidate.json",
            "local-source-bound-translucent-wrapper-candidate-r1",
            "manifests/FillCrop.json",
            "sources/FillCrop.shader",
            "generated_shader_path",
            "Hidden/FillCrop",
            5721449320467667425,
            "89c413d50c7159d42a05c19230c43769",
        ),
        (
            2540,
            "b12e02e9a9b684543a286089a03cb04b",
            "TranslucentImage/QuickDumbBlur.shader",
            "Assets/Le Tai's Asset/TranslucentImage/FormerResources/QuickDumbBlur.shader",
            "translucent-camera",
            "shader_translucent.py",
            "recipe/shader-translucent-candidate.json",
            "local-source-bound-translucent-wrapper-candidate-r1",
            "manifests/QuickDumbBlur.json",
            "sources/QuickDumbBlur.shader",
            "generated_shader_path",
            "UI/QuickDumbBlur",
            -5627814109785558414,
            "e5c4572c0a575514bb041a5a82e33cea",
        ),
        (
            8943,
            "62decc840d5afaa49886d8b13165939e",
            "RoR2/Base/Core/CameraEffects/HGScreenDamage.shader",
            "Assets/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader",
            "screen-damage",
            "shader_ramp_fog.py",
            "recipe/shader-screen-damage-candidate.json",
            1,
            "candidate.json",
            "sources/ScreenDamageCandidate.shader",
            "generated_shader",
            "Hopoo Games/Post Process/Screen Damage",
            916309824485114785,
            "ed4a1bae3abd8f34b905b509b4ff70e0",
        ),
        (
            16024,
            "780f79b2a62a0df439dedf59c533eee6",
            "RoR2/Base/Shaders/HGSobelBuffer.shader",
            "Assets/RoR2/Base/Shaders/PostProcess/HGSobelBuffer.shader",
            "sobel-buffer",
            "shader_ramp_fog.py",
            "recipe/shader-sobel-buffer-candidate.json",
            1,
            "candidate.json",
            "sources/SobelBufferCandidate.shader",
            "generated_shader",
            "Hopoo Games/Internal/SobelBuffer",
            -583016510457714391,
            "6d9e1738bf3095e42a34d9feb449ad3b",
        ),
        (
            15952,
            "7d6541fe01591cd418caf48d3c099e52",
            "RoR2/Base/Shaders/SobelOutline.shader",
            "Assets/RoR2/Base/Shaders/CustomPostProcess/SobelOutline.shader",
            "sobel-outline",
            "shader_ramp_fog.py",
            "recipe/shader-sobel-outline-candidate.json",
            1,
            "candidate.json",
            "sources/SobelOutlineCandidate.shader",
            "generated_shader",
            "Hidden/PostProcess/SobelOutline",
            2831377250017133402,
            "0af91730b526684408399853ee967ce8",
        ),
    ]
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) not in (2, 6, 7, len(expected)):
        raise RuntimeError("Shader override selection must contain a historical two/six-root profile or the complete current profile")
    expected = expected[: len(rows)]
    locations = {int(row["id"]): row for row in metadata["locations"]}
    keys = {row["key"]: row for row in metadata["keys"] if row.get("keyType", "System.String") == "System.String"}
    output_rows = []
    prepared = []
    for row, spec in zip(rows, expected, strict=True):
        (
            location_id,
            guid,
            primary_key,
            source_path,
            candidate_kind,
            generator,
            generator_recipe,
            candidate_schema,
            manifest_name,
            shader_rel,
            manifest_path_field,
            shader_name,
            object_path_id,
            exporter_guid,
        ) = spec
        target_relative = mapped.get(source_path)
        expected_target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
        if target_relative != expected_target:
            raise RuntimeError("Shader override requires its original WholeGame catalog destination: " + str(location_id))
        exact = {
            "location_id": location_id,
            "guid": guid,
            "primary_key": primary_key,
            "type": SHADER_LOCATION_TYPE,
            "source_asset_path": source_path,
            "candidate_kind": candidate_kind,
            "generator": generator,
            "generator_recipe": generator_recipe,
            "manifest": manifest_name,
            "shader": shader_rel,
            "manifest_path_field": manifest_path_field,
            "candidate_schema": candidate_schema,
            "shader_name": shader_name,
        }
        if exporter_guid is not None:
            exact["exporter_guid"] = exporter_guid
        if set(row) != set(exact) | {"generator_sha256", "generator_recipe_sha256"} or any(row.get(key) != value for key, value in exact.items()):
            raise RuntimeError("Shader override selection identity or generator mapping changed: " + str(location_id))
        if row.get("generator_sha256") != sha(ROOT / "scripts/lab" / generator):
            raise RuntimeError("Shader override generator source changed: " + generator)
        if row.get("generator_recipe_sha256") != sha(ROOT / generator_recipe):
            raise RuntimeError("Shader override generator recipe changed: " + generator_recipe)
        catalog_row = locations.get(location_id)
        key_row = keys.get(guid)
        conversion = closure["converted"].get(str(location_id))
        if (
            not catalog_row
            or catalog_row.get("type") != SHADER_LOCATION_TYPE
            or catalog_row.get("primaryKey") != primary_key
            or not key_row
            or key_row.get("locations") != [location_id]
            or not conversion
            or conversion.get("resolution") != "exact"
            or conversion.get("source") != source_path
            or mapped.get(source_path) != target_relative
        ):
            raise RuntimeError("Shader override no longer matches the validated catalog mapping: " + str(location_id))
        generator_recipe_data = io.read(ROOT / generator_recipe)
        stable_output = generator_recipe_data.get("stable_output")
        if not isinstance(stable_output, str) or "{input_id}" not in stable_output:
            raise RuntimeError("Shader candidate recipe lacks its input-bound stable output root: " + candidate_kind)
        candidate_directory = _shader_candidate_root(io, "work/" + stable_output.format(input_id=closure["input_id"]))
        manifest_path = candidate_directory / manifest_name
        shader_path = candidate_directory / shader_rel
        if manifest_path.is_symlink() or shader_path.is_symlink() or not manifest_path.is_file() or not shader_path.is_file():
            raise RuntimeError("Shader override candidate files are absent or linked: " + candidate_kind)
        manifest = io.read(manifest_path)
        if (
            manifest.get("schema") != candidate_schema
            or manifest.get("generator_sha256") != row["generator_sha256"]
            or manifest.get("recipe_sha256") != row["generator_recipe_sha256"]
        ):
            raise RuntimeError("Shader override candidate provenance differs from the current generators: " + candidate_kind)
        source = manifest.get("source", {})
        if source.get("input_id") != closure["input_id"]:
            raise RuntimeError("Shader override candidate belongs to a different accepted input")
        if candidate_kind == "outline-highlight":
            if (
                manifest.get("success") is not True
                or manifest.get("object_path_id") != object_path_id
                or source.get("catalog_key") != guid
                or source.get("catalog_location") != location_id
                or source.get("asset_path") != source_path
            ):
                raise RuntimeError("Outline candidate identity or completion changed")
        elif candidate_kind == "translucent-camera":
            if not translucent_candidate_identity_matches(manifest, generator_recipe_data, location_id, guid, source_path, object_path_id, shader_name):
                raise RuntimeError("Translucent camera candidate identity, pass map, or qualification changed")
        elif (
            manifest.get("kind") != f"local-source-bound-{candidate_kind}-candidate"
            or source.get("shader_path_id") != object_path_id
            or source.get("shader_name") != shader_name
        ):
            raise RuntimeError("Native post-process candidate identity changed")
        candidate_bytes = io.read_bytes(shader_path)
        if manifest.get(manifest_path_field) != shader_rel or manifest.get("generated_shader_sha256") != sha(shader_path):
            raise RuntimeError("Shader override candidate output differs from its manifest: " + candidate_kind)
        if __import__("hashlib").sha256(candidate_bytes).hexdigest() != manifest.get("generated_shader_sha256"):
            raise RuntimeError("Shader override candidate changed while it was being read: " + candidate_kind)
        if not re.match(rb"\s*Shader\s+" + re.escape(json.dumps(shader_name).encode()) + rb"\s*\{", candidate_bytes):
            raise RuntimeError("Shader override candidate declaration changed: " + candidate_kind)
        if manifest.get("semantic_equivalence_proven") is not False:
            raise RuntimeError("Shader override may not claim semantic equivalence")
        if candidate_kind == "outline-highlight" and (
            manifest.get("android_compile_or_render_tested") is not False or manifest.get("appearance_parity_proven") is not False
        ):
            raise RuntimeError("Outline candidate must retain its unqualified status")
        if candidate_kind in {"ramp-fog", "screen-damage", "sobel-buffer", "sobel-outline"}:
            ramp_receipt_path = candidate_directory / "receipt.json"
            if ramp_receipt_path.is_symlink() or not ramp_receipt_path.is_file():
                raise RuntimeError("Native post-process generator receipt is absent or linked")
            ramp_receipt = io.read(ramp_receipt_path)
            if (
                ramp_receipt.get("success") is not True
                or ramp_receipt.get("input_id") != closure["input_id"]
                or ramp_receipt.get("bundle_sha256") != source.get("bundle_sha256")
                or ramp_receipt.get("generated_shader_sha256") != manifest["generated_shader_sha256"]
                or ramp_receipt.get("source_bundle_unchanged") is not True
                or ramp_receipt.get("unity_compiled") is not False
                or ramp_receipt.get("android_shader_acceptance") is not False
                or ramp_receipt.get("visual_parity_proven") is not False
            ):
                raise RuntimeError("Native post-process generator receipt is incomplete or inconsistent")
        if not target_relative:
            raise RuntimeError("Shader override has no validated project mapping")
        meta = project / (target_relative + ".meta")
        meta_hash_before = io.sha(meta)
        meta_bytes_before = len(io.read_bytes(meta))
        meta_text = io.read_text(meta)
        meta_guids = re.findall(r"^guid:[ \t]*([a-f0-9]{32})[ \t]*$", meta_text, re.M)
        if len(meta_guids) != 1 or (exporter_guid is not None and meta_guids[0] != exporter_guid):
            raise RuntimeError("Shader override requires its exact original exporter GUID: " + target_relative)
        original_source_hash = io.sha(export / source_path)
        source_meta = export / (source_path + ".meta")
        if source_meta.is_symlink() or not source_meta.is_file():
            raise RuntimeError("Shader override source .meta is missing or linked: " + source_path)
        original_meta_hash = io.sha(source_meta)
        if original_meta_hash != meta_hash_before:
            raise RuntimeError("Shader override source and project .meta bytes differ: " + target_relative)
        prepared.append(
            dict(
                project_path=project / target_relative,
                meta_path=meta,
                candidate_bytes=candidate_bytes,
                meta_hash=meta_hash_before,
                receipt_row=dict(
                    location_id=location_id,
                    guid=guid,
                    **({"exporter_guid": exporter_guid} if exporter_guid is not None else {}),
                    type=SHADER_LOCATION_TYPE,
                    primary_key=primary_key,
                    source_asset_path=source_path,
                    target=target_relative,
                    original_source_sha256=original_source_hash,
                    original_meta_sha256=original_meta_hash,
                    generator=generator,
                    generator_sha256=row["generator_sha256"],
                    generator_recipe=generator_recipe,
                    generator_recipe_sha256=row["generator_recipe_sha256"],
                    candidate_manifest_path="work/" + (Path(stable_output.format(input_id=closure["input_id"])) / manifest_name).as_posix(),
                    candidate_shader_path="work/" + (Path(stable_output.format(input_id=closure["input_id"])) / shader_rel).as_posix(),
                    candidate_manifest_sha256=sha(manifest_path),
                    candidate_shader_sha256=manifest["generated_shader_sha256"],
                    candidate_shader_bytes=len(candidate_bytes),
                    preserved_meta_sha256=meta_hash_before,
                    preserved_meta_bytes=meta_bytes_before,
                ),
            )
        )
    # Validate both complete candidate/identity/meta chains before the first write.
    selector_path = io.work / "config/shader-catalog-overrides.json"
    if sha(selector_path) != local_selector["sha256"]:
        raise RuntimeError("Local shader override selector changed during staging")
    for candidate in prepared:
        io.apply(candidate["project_path"], data=candidate["candidate_bytes"])
        if io.sha(candidate["meta_path"]) != candidate["meta_hash"]:
            raise RuntimeError("Shader override changed the original catalog .meta")
        output_rows.append(candidate["receipt_row"])
    receipt = dict(
        schema="whole-catalog-shader-override-receipt-r2",
        input_id=closure["input_id"],
        enabled=True,
        selector_path="work/config/shader-catalog-overrides.json",
        selector_sha256=local_selector["sha256"],
        unity_compiled=False,
        android_accepted=False,
        visual_parity_proven=False,
        rows=output_rows,
    )
    receipt_path = destination / "shader-overrides.json"
    io.write(receipt_path, receipt)
    receipt_result = dict(receipt, path=io.label(receipt_path), sha256=io.sha(receipt_path))
    # Keep the per-attempt receipt immutable, and always mirror the active receipt
    # into the selected project so current-project StageIO gets the same disable guard.
    receipt_mirror = project / ".rebuild/catalog-shader-overrides-receipt.json"
    io.write(receipt_mirror, receipt)
    marker = dict(
        schema="whole-catalog-shader-override-marker-r2",
        input_id=closure["input_id"],
        receipt_path=receipt_mirror.relative_to(project).as_posix(),
        receipt_sha256=io.sha(receipt_mirror),
        selector_path="work/config/shader-catalog-overrides.json",
        selector_sha256=local_selector["sha256"],
    )
    io.write(project / ".rebuild/catalog-shader-overrides.json", marker)
    return receipt_result


def copy_catalog_asset(source, target):
    """Bulk imports must not launch one subprocess for every asset and meta file."""
    import ctypes
    import shutil
    import sys

    source, target = Path(source), Path(target)
    if source.is_symlink() or target.is_symlink():
        raise RuntimeError("Catalog import refuses symlinks")
    if source.resolve() == target.resolve():
        raise RuntimeError("Catalog snapshot destination must differ from its source")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    if not target.exists() and sys.platform == "darwin":
        clone = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True).clonefile
        clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
        clone.restype = ctypes.c_int
        if clone(str(source).encode(), str(target).encode(), 0) == 0:
            return
    shutil.copy2(source, target)


def work_path(work, value):
    """Resolve a recorded `work/...` path against the selected inputs, as StageIO.resolve does (J726)."""
    path = Path(value)
    return work.joinpath(*path.parts[1:]) if path.parts and path.parts[0] == "work" else ROOT / path


def read_catalog(path):
    data = read(path)
    if data.get("schemaVersion") == 2:
        for row in data["locations"]:
            # Shared arrays stay shared; flattening the shipped graph costs hundreds of MB.
            row["dependencies"] = data["dependencySets"][row["dependencySet"]]
    return data


def catalog_path(out):
    receipt = out / "catalog-metadata.json"
    if not receipt.exists():
        return out / "source-catalog.json"
    record = read(receipt)
    path = (out / record["filename"]).resolve()
    if out.resolve() not in path.parents or sha(path) != record["sha256"]:
        raise RuntimeError("Catalog metadata receipt mismatch")
    return path


def catalog_roots(data, categories):
    keys = {row["key"]: set(row["locations"]) for row in data["keys"] if row.get("keyType", "System.String") == "System.String"}
    labels = {row["name"]: row["key"] for row in data["labels"]}
    missing = set(categories) - labels.keys()
    if missing:
        raise RuntimeError("Original provider categories absent: " + str(sorted(missing)))
    packs = []
    roots = set()
    for provider in data["providers"]:
        label = "ContentPack:" + provider["identifier"]
        if label not in keys:
            raise RuntimeError("Original provider label absent: " + label)
        groups = {name: sorted(keys[label] & keys.get(labels[name], set())) for name in categories}
        roots.update(location for group in groups.values() for location in group)
        packs.append(dict(provider, label=label, categories=groups))
    return packs, roots


def resolve_path(internal_id, source_paths, folded_paths=None):
    """Only the exporter's punctuation replacement; ambiguous results stay unresolved."""
    if internal_id in source_paths:
        return internal_id, "exact"
    path = Path(internal_id)
    sanitized = str(path.with_name(path.stem.replace(",", "_").strip() + path.suffix))
    if sanitized in source_paths:
        return sanitized, "exported-filename"
    folded = folded_paths.get(sanitized.casefold(), []) if folded_paths is not None else [p for p in source_paths if p.casefold() == sanitized.casefold()]
    if len(folded) == 1:
        return folded[0], "exported-filename-case"
    return None, "unresolved-conversion"


def scene_guid_owners(candidates, data, input_id):
    """Keep catalog GUID targets and give colliding exported scenes local IDs.

    A scene address and a serialized asset GUID are different identities. Only
    repair scenes when the original catalog explicitly disambiguates both paths.
    """
    index, repairs = {}, []
    locations = {row["id"]: row for row in data["locations"]}
    keys = {row["key"]: row["locations"] for row in data["keys"] if row.get("keyType", "System.String") == "System.String"}
    scene_paths = {
        row["internalId"] for row in data["locations"] if row.get("type", "").split(",")[0] == "UnityEngine.ResourceManagement.ResourceProviders.SceneInstance"
    }
    for guid, paths in candidates.items():
        if len(paths) == 1:
            index[guid] = paths[0]
            continue
        targets = {locations[identity]["internalId"] for identity in keys.get(guid, [])}
        if len(targets) != 1 or not targets <= set(paths) or not set(paths) <= scene_paths or any(not path.endswith(".unity") for path in paths):
            raise RuntimeError("Ambiguous exported GUID identity: " + guid)
        owner = next(iter(targets))
        index[guid] = owner
        for path in sorted(set(paths) - {owner}):
            generated = digest(dict(input_id=input_id, source_guid=guid, scene_path=path))[:32]
            if generated in candidates or generated in index:
                raise RuntimeError("Generated scene GUID collision")
            index[generated] = path
            repairs.append(
                dict(
                    source=path,
                    source_guid=guid,
                    guid=generated,
                    catalog_guid_owner=owner,
                    reason="Distinct original scene address; exported GUID belongs to another scene",
                )
            )
    return index, repairs


def runtime_key_roots(data, candidates, legacy_aliases=None):
    """Exact IL address literals; provider labels retain their own typed loader.

    A stage name or label appearing in an unrelated string comparison is not an
    asset request. Accept catalog addresses, internal paths, GUID keys and exact
    aliases resolved by the shipped LegacyResourcesAPI initializer only.
    """
    keys = {row["key"]: row["locations"] for row in data["keys"] if row.get("keyType", "System.String") == "System.String"}
    locations = {row["id"]: row for row in data["locations"]}
    roots, edges = set(), []
    for row in candidates:
        key = (legacy_aliases or {}).get(row["key"], row["key"])
        found = [
            identity
            for identity in keys.get(key, [])
            if locations[identity]["internalId"].startswith("Assets/")
            and (re.fullmatch(r"[a-fA-F0-9]{32}", key) or key in (locations[identity].get("primaryKey"), locations[identity]["internalId"]))
        ]
        if found:
            roots.update(found)
            edges.append(dict(key=key, source_key=row["key"], locations=found, methods=row["methods"]))
    return roots, edges


def entity_state_gameobject_fields(source_root):
    """Read EntityStateGameObject field identity from the exact accepted C# source."""
    source_root = Path(source_root)
    classes = {}
    # This deliberately narrow field-declaration recognizer is checked against
    # the accepted RoR2.dll metadata for every selected EntityStateConfiguration.
    # It retains every declared field type so a derived non-target field masks
    # a same-named inherited EntityStateGameObject field.
    field_pattern = re.compile(
        r"(?m)^[ \t]*(?:public|protected|private|internal)\s+"
        r"(?:(?:static|readonly|volatile|new|const|extern|unsafe|fixed)\s+)*"
        r"(?P<type>(?:global::)?[A-Za-z_][\w.]*(?:\s*<[^;\n]+>)?(?:\[\])?\??)\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*(?:=[^;\n]*)?;"
    )
    class_pattern = re.compile(r"\bclass\s+([A-Za-z_]\w*)(?:\s*:\s*([^\{]+?))?\s*(?=\{)")
    namespace_pattern = re.compile(r"\bnamespace\s+([A-Za-z_][\w.]*)\s*\{")
    using_pattern = re.compile(r"(?m)^\s*using\s+([A-Za-z_][\w.]*)\s*;")

    def code_only(source):
        """Mask comments and literals while preserving offsets and braces."""
        chars = list(source)
        i, state = 0, "code"
        while i < len(source):
            current = source[i]
            following = source[i + 1] if i + 1 < len(source) else ""
            if state == "code":
                if current == "/" and following == "/":
                    chars[i] = chars[i + 1] = " "
                    i += 2
                    state = "line"
                    continue
                if current == "/" and following == "*":
                    chars[i] = chars[i + 1] = " "
                    i += 2
                    state = "block"
                    continue
                if current == '"':
                    chars[i] = " "
                    state = "string"
                elif current == "'":
                    chars[i] = " "
                    state = "char"
            elif state == "line":
                if current == "\n":
                    state = "code"
                else:
                    chars[i] = " "
            elif state == "block":
                if current == "*" and following == "/":
                    chars[i] = chars[i + 1] = " "
                    i += 2
                    state = "code"
                    continue
                if current != "\n":
                    chars[i] = " "
            else:
                if current == "\\":
                    chars[i] = " "
                    if i + 1 < len(source):
                        if source[i + 1] != "\n":
                            chars[i + 1] = " "
                        i += 2
                        continue
                elif (state == "string" and current == '"') or (state == "char" and current == "'"):
                    chars[i] = " "
                    state = "code"
                elif current != "\n":
                    chars[i] = " "
            i += 1
        return "".join(chars)

    def matching_brace(code, opening):
        depth = 0
        for pos in range(opening, len(code)):
            if code[pos] == "{":
                depth += 1
            elif code[pos] == "}":
                depth -= 1
                if depth == 0:
                    return pos
        raise RuntimeError("Unbalanced accepted C# class or namespace source")

    for path in source_root.rglob("*.cs"):
        text = path.read_text(errors="replace")
        code = code_only(text)
        imports = using_pattern.findall(code)
        namespaces = []
        for namespace in namespace_pattern.finditer(code):
            opening = code.find("{", namespace.end() - 1)
            namespaces.append((namespace.start(), matching_brace(code, opening), namespace.group(1)))
        class_rows = []
        for match in class_pattern.finditer(code):
            opening = code.find("{", match.end())
            if opening < 0:
                raise RuntimeError("Accepted C# class has no body")
            closing = matching_brace(code, opening)
            name, bases = match.groups()
            parent = None
            if bases:
                parent = re.split(r",|\bwhere\b", bases, maxsplit=1)[0].strip()
                parent = re.sub(r"<.*>$", "", parent).strip()
            namespace = [row for row in namespaces if row[0] < match.start() < row[1]]
            if not namespace:
                continue
            namespace_name = max(namespace, key=lambda row: row[0])[2]
            enclosing = [row for row in class_rows if row[1] < match.start() < row[2]]
            class_rows.append((match.start(), opening, closing, name, parent, namespace_name, enclosing, imports))
        for _, opening, closing, name, parent, namespace_name, enclosing, imports in class_rows:
            nesting = [row[3] for row in sorted(enclosing, key=lambda row: row[0])]
            full_name = namespace_name + "." + ("+".join(nesting + [name]) if nesting else name)
            # Keep only direct members; nested types cannot donate their fields.
            body = list(" " * (closing - opening - 1))
            depth = 0
            for pos in range(opening + 1, closing):
                char = code[pos]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                elif depth == 0:
                    body[pos - opening - 1] = code[pos]
            direct_fields = {match.group("name"): match.group("type").replace("global::", "") for match in field_pattern.finditer("".join(body))}
            previous = classes.get(full_name)
            if previous and previous["rawParent"] != parent:
                raise RuntimeError("Accepted C# partial class has conflicting base identity: " + full_name)
            container_names = nesting
            record = classes.setdefault(
                full_name, {"fields": {}, "rawParent": parent, "namespace": namespace_name, "containers": container_names, "imports": set()}
            )
            if record["containers"] != container_names:
                raise RuntimeError("Accepted C# partial class has conflicting container identity: " + full_name)
            record["imports"].update(imports)
            for field_name, field_type in direct_fields.items():
                if field_name in record["fields"] and record["fields"][field_name] != field_type:
                    raise RuntimeError("Accepted C# partial class has conflicting field identity: " + full_name + "." + field_name)
                record["fields"][field_name] = field_type
    for full_name, record in classes.items():
        parent = record["rawParent"]
        resolved_parent = None
        if parent:
            if "." in parent or "+" in parent:
                resolved_parent = parent
            else:
                if record["containers"]:
                    nested_parent = record["namespace"] + "." + "+".join(record["containers"] + [parent])
                    if nested_parent in classes:
                        resolved_parent = nested_parent
                namespace_parts = record["namespace"].split(".")
                if not resolved_parent:
                    lexical = [".".join(namespace_parts[:i]) + "." + parent for i in range(len(namespace_parts), 0, -1)]
                    lexical_match = next((name for name in lexical if name in classes), None)
                    if lexical_match:
                        resolved_parent = lexical_match
                    else:
                        imported = {namespace + "." + parent for namespace in record["imports"] if namespace + "." + parent in classes}
                        if len(imported) == 1:
                            resolved_parent = next(iter(imported))
                        elif len(imported) > 1:
                            raise RuntimeError("Accepted C# imported base type name is ambiguous: " + full_name + " -> " + parent)
                if not resolved_parent:
                    matches = [key for key in classes if key.endswith("." + parent)]
                    if len(matches) == 1:
                        resolved_parent = matches[0]
                    elif len(matches) > 1:
                        raise RuntimeError("Accepted C# base type name is ambiguous: " + full_name + " -> " + parent)
        record["parent"] = resolved_parent
    result = {}
    for full_name, record in classes.items():
        effective_fields = {}
        current = full_name
        visited = set()
        while current in classes and current not in visited:
            visited.add(current)
            for field_name, field_type in classes[current]["fields"].items():
                effective_fields.setdefault(field_name, field_type)
            current = classes[current]["parent"]
        result[full_name] = {field_name for field_name, field_type in effective_fields.items() if field_type.rsplit(".", 1)[-1] == "EntityStateGameObject"}
    if not result:
        raise RuntimeError("Accepted EntityStateGameObject source field index is empty")
    return result


def serialized_entity_state_gameobject_references(text, state_fields):
    """Find only typed EntityStateGameObject values in native state configs."""
    target = re.search(r"(?m)^\s+assemblyQualifiedName:\s*([^,\n]+),", text)
    if not target:
        return []
    state_type = target.group(1).strip()
    typed_fields = state_fields.get(state_type, set())
    if not typed_fields:
        return []
    result = []
    blocks = re.finditer(r"(?m)^    - fieldName: ([^\n]+)\n((?:^      .*\n?)*)", text)
    for block in blocks:
        field_name = block.group(1).strip()
        if field_name not in typed_fields:
            continue
        value = re.search(r"(?m)^        stringValue: ([^\n]*)$", block.group(2))
        if not value:
            continue
        key = value.group(1).strip()
        if re.fullmatch(r"[a-fA-F0-9]{32}", key):
            result.append(dict(field=field_name, key=key.lower(), targetType=state_type))
    return result


def entity_state_reference_closure(text, source, state_fields, key_locations, converted, location_metadata):
    """Resolve typed native state asset refs through the original catalog identity."""
    edges, pending, issues = [], [], []
    for edge in serialized_entity_state_gameobject_references(text, state_fields):
        targets = key_locations.get(edge["key"], [])
        matches = [identity for identity in targets if location_metadata.get(identity, {}).get("type", "").split(",")[0] == "UnityEngine.GameObject"]
        resolved = []
        edge_record = dict(
            source=source,
            key=edge["key"],
            locations=targets,
            requestedType="UnityEngine.GameObject",
            matchingLocations=matches,
            resolved=resolved,
            field=edge["field"],
            targetType=edge["targetType"],
            kind="EntityStateGameObject",
        )
        edge_record["locationIdentity"] = [
            dict(
                id=identity,
                type=location_metadata[identity].get("type"),
                provider=location_metadata[identity].get("provider"),
                internalId=location_metadata[identity].get("internalId"),
                primaryKey=location_metadata[identity].get("primaryKey"),
            )
            for identity in targets
            if identity in location_metadata
        ]
        edges.append(edge_record)
        if not targets:
            issues.append(dict(source=source, key=edge["key"], field=edge["field"], category="asset-reference-key-missing"))
        elif not matches:
            issues.append(
                dict(
                    source=source,
                    key=edge["key"],
                    field=edge["field"],
                    locations=targets,
                    requestedType="UnityEngine.GameObject",
                    category="asset-reference-requested-type-missing",
                )
            )
        elif len(matches) != 1:
            issues.append(
                dict(
                    source=source,
                    key=edge["key"],
                    field=edge["field"],
                    locations=matches,
                    requestedType="UnityEngine.GameObject",
                    category="asset-reference-requested-type-ambiguous",
                )
            )
        elif matches[0] not in converted:
            issues.append(
                dict(
                    source=source,
                    key=edge["key"],
                    field=edge["field"],
                    locations=matches,
                    requestedType="UnityEngine.GameObject",
                    category="asset-reference-conversion-unresolved",
                )
            )
        else:
            resolved.append(converted[matches[0]]["source"])
            edge_record["resolved"] = list(resolved)
            pending.extend(resolved)
    return edges, pending, issues


def analyze(source, export, index, helper, native_overrides=None, runtime_candidates=(), legacy_aliases=None, state_source_root=None):
    data = read_catalog(source)
    categories = list(dict.fromkeys(re.findall(r"FindLocationsThenAddLoadOperation(?:<[^>]+>)?\(AddressablesLabels\.(\w+)", helper)))
    if not categories:
        raise RuntimeError("Original provider category contract absent")
    packs, roots = catalog_roots(data, categories)
    locations = {row["id"]: row for row in data["locations"]}
    if len(locations) != len(data["locations"]):
        raise RuntimeError("Duplicate catalog location identity")
    for row in locations.values():
        if not set(row["dependencies"]) <= locations.keys():
            raise RuntimeError("Broken original catalog dependency")
    runtime_roots, runtime_edges = runtime_key_roots(data, runtime_candidates, legacy_aliases)
    seeds = roots | runtime_roots
    # Indexed source identity, rather than a filesystem search per resource.
    paths = set(index.values())
    folded_paths = {}
    for path in paths:
        folded_paths.setdefault(path.casefold(), []).append(path)
    converted = {}
    unresolved = []
    for row in locations.values():
        if not row["internalId"].startswith("Assets/"):
            continue
        path, reason = resolve_path(row["internalId"], paths, folded_paths)
        if native_overrides and str(row["id"]) in native_overrides:
            converted[row["id"]] = native_overrides[str(row["id"])]
        elif path:
            converted[row["id"]] = dict(source=path, resolution=reason)
        else:
            unresolved.append(
                dict(
                    id=row["id"],
                    internalId=row["internalId"],
                    type=row["type"],
                    owning_bundle=row["dependencies"][0] if row["dependencies"] else None,
                    dependency_count=len(row["dependencies"]),
                    category=reason,
                    catalog_root=row["id"] in roots,
                    runtime_root=row["id"] in runtime_roots,
                )
            )
    key_locations = {row["key"]: row["locations"] for row in data["keys"] if row.get("keyType", "System.String") == "System.String"}
    state_fields = entity_state_gameobject_fields(state_source_root) if state_source_root is not None else {}
    # Serialized references and runtime AssetReference keys are different edges.
    pending = deque(converted[identity]["source"] for identity in sorted(seeds) if identity in converted)
    seen = set()
    issues = []
    soft_edges = []
    scripts = set()
    total_bytes = 0
    suffixes = Counter()
    while pending:
        relative = pending.popleft()
        if relative in seen:
            continue
        seen.add(relative)
        path = export / relative
        if not path.is_file():
            issues.append(dict(source=relative, category="indexed-source-file-missing"))
            continue
        total_bytes += path.stat().st_size
        suffixes[path.suffix] += 1
        if path.suffix in {".dll", ".cs"}:
            scripts.add(relative)
            continue
        with path.open("rb") as stream:
            if stream.read(5) != b"%YAML":
                continue
        text = path.read_text()
        for guid in {g for _, g, _ in REFERENCE.findall(text) if g and not g.startswith("0000000000000000")}:
            target = index.get(guid)
            if target:
                pending.append(target)
            else:
                issues.append(dict(source=relative, guid=guid, category="serialized-guid-missing"))
        # BakedEffectData.assetGUID feeds EffectDef's original async reference;
        # unlike Unity's AssetReference it has no m_ prefix in serialized data.
        # Native state preloads store runtime GUID keys as plain YAML strings,
        # outside both PPtr and AssetReference fields. Follow the entire family.
        preload_blocks = re.findall(r"^  preloadGUIDReferences:[ \t]*\n((?:  -[^\n]*\n?)*)", text, re.M)
        preloads = {value.strip() for block in preload_blocks for value in re.findall(r"^  -(.*)$", block, re.M)}
        invalid_preloads = sorted(key for key in preloads if not re.fullmatch(r"[a-f0-9]{32}", key))
        if invalid_preloads:
            issues.append(dict(source=relative, keys=invalid_preloads, category="invalid-preload-key"))
        valid_preloads = preloads - set(invalid_preloads)
        for guid in set(re.findall(r"\b(?:m_AssetGUID|assetGUID):\s*([a-f0-9]{32})", text)) | valid_preloads:
            targets = key_locations.get(guid, [])
            if guid in valid_preloads:
                runtime_roots.update(targets)
                runtime_edges.append(dict(key=guid, locations=targets, source=relative, field="preloadGUIDReferences"))
            resolved = [converted[x]["source"] for x in targets if x in converted]
            soft_edges.append(dict(source=relative, key=guid, locations=targets, resolved=resolved))
            pending.extend(resolved)
            if not targets:
                issues.append(dict(source=relative, key=guid, category="asset-reference-key-missing"))
            elif len(resolved) != len(targets):
                issues.append(dict(source=relative, key=guid, locations=targets, category="asset-reference-conversion-unresolved"))
        # EntityStateConfiguration serializes EntityStateGameObject.AssetReference
        # keys in stringValue, not an m_AssetGUID member. Follow only fields whose
        # accepted native state declaration confirms that exact value type.
        state_edges, state_paths, state_issues = entity_state_reference_closure(text, relative, state_fields, key_locations, converted, locations)
        soft_edges.extend(state_edges)
        pending.extend(state_paths)
        issues.extend(state_issues)
    summary = dict(
        keys=len(data["keys"]),
        locations=len(locations),
        providers=len(packs),
        provider_categories=len(categories),
        catalog_roots=len(roots),
        resolved_roots=len(roots & converted.keys()),
        runtime_key_edges=len(runtime_edges),
        runtime_roots=len(runtime_roots),
        resolved_runtime_roots=len(runtime_roots & converted.keys()),
        unresolved_runtime_roots=sorted(runtime_roots - converted.keys()),
        root_types=dict(Counter(locations[x]["type"].split(",")[0] if locations[x]["type"] else "unresolved-type" for x in roots)),
        converted_locations=len(converted),
        unresolved_locations=len(unresolved),
        unresolved_root_locations=[row["id"] for row in unresolved if row["catalog_root"]],
        closure_files=len(seen),
        closure_bytes=total_bytes,
        closure_suffixes=dict(suffixes),
        soft_reference_edges=len(soft_edges),
        issues=dict(Counter(row["category"] for row in issues)),
        quarantine=[],
        scope="Host metadata/serialized closure only. Unresolved conversion is not incompatibility. No loading, registration, gameplay, ownership or Android acceptance.",
    )
    return dict(
        summary=summary,
        packs=packs,
        roots=sorted(roots),
        runtime_roots=sorted(runtime_roots),
        runtime_key_edges=runtime_edges,
        converted=converted,
        unresolved=unresolved,
        files=sorted(seen),
        scripts=sorted(scripts),
        soft_edges=soft_edges,
        issues=issues,
    )


def native_candidates(records, exports):
    """A typed original container identity must have one matching exported owner."""
    result = []
    issues = []
    for row in records:
        candidates = exports.get((str(Path(row["address"]).parent), row["type"], row["name"]), [])
        if len(candidates) == 1:
            result.append(dict(source=candidates[0], name=row["name"], type=row["type"], native_path_id=row["path_id"], serialized_file=row["serialized_file"]))
        else:
            issues.append(dict(native=row, candidates=candidates, category="ambiguous-exported-object" if candidates else "exported-object-unresolved"))
    return result, issues


def reconcile():
    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    result, conversions = reconcile_into(out, ROOT / read(out / "native-latest.json")["path"])
    print(json.dumps(dict(result["summary"], original_typed_conversions=len(conversions)), indent=2))


def reconcile_into(out, native, work=WORK):
    """Typed native conversions and the reconciled closure for the audit in `out` (J725)."""
    export = work_path(work, read(work / "config/reconstruction.json")["projects"][0])
    closure = read(out / "host-closure.json")
    index = read(out / "source-guid-index.json")
    metadata = read_catalog(catalog_path(out))
    # Unity class IDs are source serialization tags, independent of filename extensions.
    class_names = {
        1: "GameObject",
        21: "Material",
        28: "Texture2D",
        43: "Mesh",
        48: "Shader",
        74: "AnimationClip",
        89: "Cubemap",
        90: "Avatar",
        213: "Sprite",
        687078895: "SpriteAtlas",
        115: "MonoScript",
        114: "MonoBehaviour",
        142: "AssetBundle",
        258: "LightProbes",
        128: "Font",
        152: "MovieTexture",
        329: "VideoClip",
        83: "AudioClip",
    }
    exported = {}
    for relative in set(index.values()):
        path = export / relative
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            prefix = stream.read(16384)
        text = prefix.decode(errors="replace") if prefix.startswith(b"%YAML") else ""
        header = re.search(r"^--- !u!(\d+)", text, re.M)
        name = re.search(r"^  m_Name: (.*)$", text, re.M)
        if header and name:
            kind = class_names.get(int(header[1]))
            object_name = name[1]
            if object_name.startswith('"'):
                object_name = json.loads(object_name)
            elif object_name.startswith("'") and object_name.endswith("'"):
                object_name = object_name[1:-1].replace("''", "'")
        elif path.suffix.lower() in {".png", ".tga", ".jpg", ".bmp", ".exr"}:
            kind, object_name = "Texture2D", path.stem
        else:
            continue
        if kind:
            exported.setdefault((str(Path(relative).parent), kind, object_name), []).append(relative)
    containers = {}
    for receipt in native.glob("*.json"):
        if not receipt.stem.isdigit():
            continue
        data = read(receipt)
        for row in data["containers"]:
            if "type" in row:
                containers.setdefault((data["location"], row["address"].casefold(), row["type"]), []).append(row)
    conversions = {}
    issues = []
    for row in closure["unresolved"]:
        owner = row.get("owning_bundle", (row.get("dependencies") or [None])[0])
        if owner is None or not row["type"]:
            continue
        kind = row["type"].split(",")[0].rsplit(".", 1)[-1]
        original = containers.get((owner, row["internalId"].casefold(), kind), [])
        if not original:
            issues.append(dict(location=row["id"], category="typed-native-container-unresolved"))
            continue
        objects, failures = native_candidates(original, exported)
        if failures or len(objects) != 1:
            issues.append(
                dict(
                    location=row["id"],
                    category="typed-native-export-unresolved",
                    objects=objects,
                    failures=failures,
                    requires_subobject_selection=len(objects) > 1,
                )
            )
            continue
        conversions[str(row["id"])] = dict(
            source=objects[0]["source"], resolution="original-typed-container", native=objects[0], original_internal_id=row["internalId"]
        )
    write(out / "native-conversions.json", dict(conversions=conversions, issues=issues, quarantine=[]))
    collision_receipt = out / "typed-import-conversions.json"
    if collision_receipt.exists():
        corrected = read(collision_receipt)
        if corrected["metadata_sha256"] != sha(catalog_path(out)):
            raise RuntimeError("Typed import corrections belong to a different catalog")
        conversions.update(corrected["conversions"])
    assembly_hash = sha(game(work) / "Risk of Rain 2_Data/Managed/RoR2.dll")
    key = digest(dict(input=assembly_hash, ilspy="11.0.0.9375", args="project-referencepath-csharp9-v2"))
    helper = work / "decompiled/RoR2" / key[:16] / "RoR2.ContentManagement/AddressablesLoadHelper.cs"
    contract = read(out / "original-catalog-contract.json")
    if contract["input_sha256"] != assembly_hash:
        raise RuntimeError("Runtime key metadata belongs to different input")
    legacy_hash = next(
        row["sha256"] for row in read(work / "inventory/files.json")["files"] if row["path"] == "Risk of Rain 2_Data/Managed/LegacyResourcesAPI.dll"
    )
    if contract.get("legacyInputSha256") != legacy_hash:
        raise RuntimeError("Refresh the native catalog contract for the accepted legacy assembly")
    result = analyze(
        catalog_path(out),
        export,
        index,
        helper.read_text(),
        conversions,
        contract.get("assetKeyCandidates", []),
        contract.get("legacyAliases", {}),
        helper.parents[1],
    )
    result["source_catalog_sha256"] = closure["source_catalog_sha256"]
    result["metadata_sha256"] = sha(catalog_path(out))
    result["input_id"] = closure["input_id"]
    result["native_conversion_count"] = len(conversions)
    write(out / "reconciled-closure.json", result)
    return result, conversions


def audit():
    out = WORK / "experiments/whole-catalog" / now()
    out.mkdir(parents=True)
    result = audit_into(out)
    write(out.parent / "latest.json", dict(path=str(out.relative_to(ROOT)), status="host-audit"))
    print(json.dumps(result["summary"], indent=2))


def audit_into(out, work=WORK):
    """Host catalog audit into `out`; writes no live pointer (J725)."""
    export = work_path(work, read(work / "config/reconstruction.json")["projects"][0])
    # The accepted decompilation location is receipted by recovery.py.
    assembly_hash = sha(game(work) / "Risk of Rain 2_Data/Managed/RoR2.dll")
    expected_hash = next(row["sha256"] for row in read(work / "inventory/files.json")["files"] if row["path"] == "Risk of Rain 2_Data/Managed/RoR2.dll")
    if assembly_hash != expected_hash:
        raise RuntimeError("Original input drift; review and explicitly accept before conversion")
    decompile_key = digest(dict(input=assembly_hash, ilspy="11.0.0.9375", args="project-referencepath-csharp9-v2"))
    candidates = [
        path.parent / "RoR2.ContentManagement/AddressablesLoadHelper.cs"
        for path in (work / "decompiled/RoR2").glob("*/result.json")
        if read(path).get("success") and read(path).get("input_sha256") == assembly_hash and read(path).get("cache_key") == decompile_key
    ]
    if len(candidates) != 1:
        raise RuntimeError("Expected one accepted original load helper; review input selection")
    helper = candidates[0]
    export_source_catalog(out, work=work)
    source = out / "source-catalog.json"
    # Generated index only caches original GUID metadata, never supplies a readiness filter.
    candidates = {}
    for meta in (export / "Assets").rglob("*.meta"):
        match = re.search(r"^guid:\s*([a-f0-9]{32})", meta.read_text(errors="replace"), re.M)
        if not match:
            continue
        relative = str(Path(str(meta)[:-5]).relative_to(export))
        candidates.setdefault(match[1], []).append(relative)
    data = read_catalog(source)
    index, repairs = scene_guid_owners(candidates, data, read(work / "inventory/files.json")["input_id"])
    write(out / "source-guid-repairs.json", repairs)
    if (
        list(dict.fromkeys(re.findall(r"FindLocationsThenAddLoadOperation(?:<[^>]+>)?\(AddressablesLabels\.(\w+)", helper.read_text())))
        != read(out / "original-catalog-contract.json")["categories"]
    ):
        raise RuntimeError("Recovered provider categories disagree with original IL")
    contract = read(out / "original-catalog-contract.json")
    result = analyze(
        source,
        export,
        index,
        helper.read_text(),
        runtime_candidates=contract.get("assetKeyCandidates", []),
        legacy_aliases=contract.get("legacyAliases", {}),
        state_source_root=helper.parents[1],
    )
    result["input_id"] = read(work / "inventory/files.json")["input_id"]
    result["source_catalog_sha256"] = sha(export / "Assets/StreamingAssets/aa/catalog.json")
    result["metadata_sha256"] = sha(source)
    result["helper_sha256"] = sha(helper)
    write(out / "host-closure.json", result)
    write(out / "source-guid-index.json", index)
    return result


def export_source_catalog(out, filename="source-catalog.json", work=WORK):
    """Read the shipped catalog schema on the host; no editor is involved (J714).

    `catalog_reader` mirrors the original ContentCatalogData.CreateLocator and is
    byte-identical to the retired ExportCatalog editor query. The provider contract,
    label literals and provider identifiers come from shipped IL."""
    from boundaries import probe_tool
    from catalog_reader import dumps, read_shipped

    export = work_path(work, read(work / "config/reconstruction.json")["projects"][0])
    original = game(work) / "Risk of Rain 2_Data/Managed/RoR2.dll"
    expected = next(row["sha256"] for row in read(work / "inventory/files.json")["files"] if row["path"] == "Risk of Rain 2_Data/Managed/RoR2.dll")
    contract = json.loads(run(probe_tool() + ["--catalog-contract", original], timeout=120).stdout)
    if contract["input_sha256"] != expected:
        raise RuntimeError("Provider contract belongs to unaccepted input")
    expected_legacy = next(
        row["sha256"] for row in read(work / "inventory/files.json")["files"] if row["path"] == "Risk of Rain 2_Data/Managed/LegacyResourcesAPI.dll"
    )
    if contract["legacyInputSha256"] != expected_legacy:
        raise RuntimeError("Legacy resource contract belongs to unaccepted input")
    write(out / "original-catalog-contract.json", contract)
    names = json.loads(run(probe_tool() + ["--catalog-names", original] + contract["providers"], timeout=120).stdout)
    # The editor query expanded RuntimePath against the lab project it ran in; keep that form.
    record = read_shipped(export / "Assets/StreamingAssets/aa/catalog.json", str(work / "lab-project/Assets/StreamingAssets/aa"), names)
    (out / filename).write_text(dumps(record), encoding="utf-8")


def export_catalog(out, template, filename):
    """Run a read-only catalog template through the already pinned, idle lab editor."""
    export = ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
    code = (ROOT / "tools/catalog" / template).read_text()
    code = code.replace("CATALOG", json.dumps(str(export / "Assets/StreamingAssets/aa/catalog.json")))
    code = code.replace("OUTPUT", json.dumps(str(out / filename)))
    client = """import asyncio,json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
 request=json.loads(Path(__file__).with_suffix('.json').read_text())
 async with streamablehttp_client('http://127.0.0.1:8080/mcp') as (r,w,_):
  async with ClientSession(r,w) as session:
   await session.initialize()
   instances=json.loads((await session.read_resource('mcpforunity://instances')).contents[0].text)['instances']
   matches=[row for row in instances if row['name']=='lab-project']
   if len(matches)!=1:raise RuntimeError('Expected one connected lab editor')
   await session.call_tool('set_active_instance',{'instance':matches[0]['id']})
   project=(await session.read_resource('mcpforunity://project/info')).model_dump(mode='json')
   if request['project'] not in json.dumps(project):raise RuntimeError('Selected project mismatch')
   response=(await session.call_tool('execute_code',{'action':'execute','code':request['code']})).model_dump(mode='json')
   Path(request['response']).write_text(json.dumps(response,indent=2))
   if response.get('isError') or response.get('structuredContent',{}).get('success') is not True:raise RuntimeError(str(response))
asyncio.run(main())
"""
    script = out / (Path(template).stem + "-query.py")
    script.write_text(client)
    version = toolchain()["unity_version"]
    code = (
        "if(Application.unityVersion!="
        + json.dumps(version)
        + '||EditorUtility.scriptCompilationFailed||EditorApplication.isCompiling||EditorApplication.isUpdating||EditorApplication.isPlayingOrWillChangePlaymode||BuildPipeline.isBuildingPlayer)throw new System.Exception("Catalog evidence requires the exact editor with current compiled source and idle state");'
        + code
    )
    write(script.with_suffix(".json"), dict(project=str(WORK / "lab-project"), code=code, response=str(out / (Path(template).stem + "-query-result.json"))))
    run([ROOT / ".local/tools/unity-mcp/Server/.venv/bin/python", script], timeout=180)


def contracts():
    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    destination = out / ("runtime-contracts-" + now())
    destination.mkdir()
    export_catalog(destination, "ExportRuntimeContracts.cs.txt", "runtime-contracts.json")
    runtime = read(destination / "runtime-contracts.json")
    imported = {(row["guid"], str(row["fileId"])): row for row in runtime["scripts"]}
    export = ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
    remaps = read(RECIPE / "hud-ui-remaps.json")
    if remaps["input_id"] != read(WORK / "config/accepted-input.json")["input_id"] or remaps["source_UI_sha256"] != sha(
        export / "Assets/Plugins/UnityEngine.UI.dll"
    ):
        raise RuntimeError("Existing measured UI remaps do not belong to this input")
    ui_remaps = {row["from"]: row for row in remaps["rows"]}
    index = read(out / "source-guid-index.json")
    closure = read(out / "reconciled-closure.json")
    contracts = {}
    for relative in closure["files"]:
        path = export / relative
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(5) != b"%YAML":
                continue
        text = path.read_text()
        for file_id, guid in re.findall(r"m_Script: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: \d+\}", text):
            key = guid + ":" + file_id
            row = contracts.setdefault(key, dict(guid=guid, file_id=file_id, source_script=index.get(guid), consumers=[]))
            row["consumers"].append(relative)
            found = imported.get((guid, file_id))
            row["imported"] = found
            row["status"] = "bound" if found and found["type"] else "binding-unresolved"
            prior = ui_remaps.get("{fileID: " + file_id + ", guid: " + guid + ", type: 3}")
            if row["status"] != "bound" and prior:
                target = re.search(r"fileID: (-?\d+), guid: ([a-f0-9]{32})", prior["to"])
                measured = imported.get((target[2], target[1])) if target else None
                if not measured or measured["type"] != prior["type"]:
                    raise RuntimeError("Measured package UI binding regressed")
                row["remap"] = prior
                row["target_imported"] = measured
                row["status"] = "binding-remap-verified"
    result = dict(
        contracts=list(contracts.values()),
        summary=dict(Counter(row["status"] for row in contracts.values())),
        initializers=runtime["initializers"],
        quarantine=[],
        scope="Imported MonoScript identities and original initializer dependency graph. No content registration or platform checks invoked; remaps need typed validation.",
    )
    write(destination / "result.json", result)
    write(out / "contracts-latest.json", dict(path=str(destination.relative_to(ROOT))))
    print(json.dumps(dict(result["summary"], initializers=len(runtime["initializers"])), indent=2))


def inspect_native_bundle(identity, locations, file_index):
    """Read one accepted original container, including typed subasset entries."""
    import UnityPy

    basename = locations[identity]["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
    matches = file_index.get(basename, [])
    if len(matches) != 1:
        raise RuntimeError("Ambiguous or absent legitimate bundle input")
    source = game() / matches[0]["path"]
    if sha(source) != matches[0]["sha256"]:
        raise RuntimeError("Original bundle drift; explicitly review and accept")
    environment = UnityPy.load(str(source))
    containers = []
    for obj in environment.objects:
        if obj.type.name != "AssetBundle":
            continue
        for address, info in obj.read().m_Container:
            asset = info.asset.deref()
            containers.append(
                dict(address=address, type=asset.type.name, name=asset.peek_name(), path_id=asset.path_id, serialized_file=asset.assets_file.name)
            )
    if not containers:
        raise RuntimeError("No original asset container records")
    return dict(location=identity, source=matches[0]["path"], sha256=matches[0]["sha256"], containers=containers)


def native_inventory():
    """Read container object identities in bulk; never infer an FBX mesh from its filename."""
    import UnityPy

    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    destination = out / ("native-containers-" + now())
    destination.mkdir()
    result = native_inventory_into(out, destination)
    write(out / "native-latest.json", dict(path=str(destination.relative_to(ROOT))))
    print(json.dumps(dict(inspected=len(result["bundles"]), failures=len(result["errors"]), evidence=str(destination.relative_to(ROOT)))))
    if not result["success"]:
        raise RuntimeError("Original container inspection incomplete; preserve and inspect its first failure")


def native_inventory_into(out, destination, work=WORK):
    """Container receipts for the audit in `out`, written to `destination`; no live pointer (J725)."""
    import UnityPy

    metadata = read_catalog(catalog_path(out))
    closure = read(out / "host-closure.json")
    locations = {row["id"]: row for row in metadata["locations"]}
    bundle_ids = sorted({row.get("owning_bundle", (row.get("dependencies") or [None])[0]) for row in closure["unresolved"]} - {None})
    accepted = read(work / "inventory/files.json")
    if accepted["input_id"] != read(work / "config/accepted-input.json")["input_id"]:
        raise RuntimeError("Input drift; native inspection requires accepted input")
    file_index = {}
    for row in accepted["files"]:
        file_index.setdefault(Path(row["path"]).name, []).append(row)
    receipts = []
    errors = []
    object_errors = []
    for ordinal, identity in enumerate(bundle_ids):
        location = locations[identity]
        basename = location["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
        matches = file_index.get(basename, [])
        try:
            if len(matches) != 1:
                raise RuntimeError("Ambiguous or absent legitimate bundle input")
            source = game(work) / matches[0]["path"]
            if sha(source) != matches[0]["sha256"]:
                raise RuntimeError("Original bundle drift; explicitly review and accept")
            environment = UnityPy.load(str(source))
            containers = []
            for obj in environment.objects:
                if obj.type.name != "AssetBundle":
                    continue
                bundle = obj.read()
                for address, info in bundle.m_Container:
                    try:
                        asset = info.asset.deref()
                        containers.append(
                            dict(address=address, type=asset.type.name, name=asset.peek_name(), path_id=asset.path_id, serialized_file=asset.assets_file.name)
                        )
                    except Exception as exception:
                        failure = dict(address=address, category="native-object-read-failed", error=str(exception))
                        containers.append(failure)
                        object_errors.append(dict(failure, location=identity))
            if not containers:
                raise RuntimeError("No original asset container records")
            receipt = dict(location=identity, source=matches[0]["path"], sha256=matches[0]["sha256"], containers=containers)
            write(destination / (str(identity) + ".json"), receipt)
            receipts.append(dict(location=identity, containers=len(containers), source_sha256=matches[0]["sha256"]))
            del environment
        except Exception as exception:
            errors.append(dict(location=identity, category="native-container-inspection-failed", error=str(exception)))
        if ordinal % 40 == 0:
            write(destination / "progress.json", dict(inspected=ordinal + 1, total=len(bundle_ids), failures=len(errors)))
            print(json.dumps(dict(inspected=ordinal + 1, total=len(bundle_ids), failures=len(errors))), flush=True)
    result = dict(
        success=not errors and not object_errors,
        bundles=receipts,
        errors=errors,
        object_errors=object_errors,
        quarantine=[],
        scope="Original binary container identities only; no engine loading, asset equivalence or Android acceptance",
    )
    write(destination / "result.json", result)
    return result


def repair_support_source(export, mapped, project, destination, io=None):
    """Resolve one observed decompiler ambiguity from the original field types."""
    from composition_io import StageIO

    io = io or StageIO()
    relative = "Assets/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs"
    if relative not in mapped:
        return
    binary = game(io.work) / "Risk of Rain 2_Data/Managed/Assembly-CSharp.dll"
    expected = next(
        row["sha256"] for row in io.read(io.work / "inventory/files.json")["files"] if row["path"] == "Risk of Rain 2_Data/Managed/Assembly-CSharp.dll"
    )
    from boundaries import probe_tool

    # Read-only IL field contract; the rebuild no longer pins the previous record (J725).
    contract = json.loads(run(probe_tool() + [binary, "AffixBeadProjectileSound"], timeout=120).stdout)
    if contract["sha256"] != expected or len(contract["types"]) != 1:
        raise RuntimeError("Recovered support source requires the accepted original field contract")
    fields = {row["name"]: row["type"] for row in contract["types"][0]["fields"]}
    if fields != {"SpawnBeadChaseEvent": "AK.Wwise.Event", "ExplodeEvent": "AK.Wwise.Event"}:
        raise RuntimeError("Observed support source ambiguity changed; inspect original types")
    source = export / relative
    target = project / mapped[relative]
    text = source.read_text()
    corrected = "using Event = AK.Wwise.Event;\n" + text
    if io.read_text(target) not in (text, corrected):
        raise RuntimeError("Unexpected edits to recovered support source")
    io.apply(target, corrected)
    io.write(
        destination / "support-source-alias.json",
        dict(
            source=relative,
            target=mapped[relative],
            source_sha256=sha(source),
            output_sha256=io.sha(target),
            original_assembly_sha256=expected,
            fields=fields,
            scope="Qualify the two original audio-event field types; original methods unchanged; no audio availability claim",
        ),
    )


def source_mesh_subobjects(export, closure, metadata, native):
    """Resolve original GUID[subobject] mesh keys to exact native/exported objects.

    AssetRipper exports FBX mesh subobjects as separate .asset files. A typed
    main-FBX location cannot identify which mesh the shipped SkinDef requested.
    Require both the serialized name and the native container identity before
    adding a location; leave missing/ambiguous references explicit.
    """
    pattern = re.compile(r"m_AssetGUID: ([a-f0-9]{32})\s*\n\s*m_SubObjectName: ([^\n]+)\s*\n\s*m_SubObjectType: UnityEngine.Mesh,")
    locations = {row["id"]: row for row in metadata["locations"]}
    guid_locations = {
        row["key"]: row["locations"]
        for row in metadata["keys"]
        if row.get("keyType", "System.String") == "System.String" and re.fullmatch(r"[a-f0-9]{32}", row["key"])
    }
    issues = {row["location"]: row for row in native["issues"]}
    seen, resolved, unresolved = set(), [], []
    for relative in closure["files"]:
        path = export / relative
        if path.suffix not in {".asset", ".prefab", ".unity"} or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(5) != b"%YAML":
                continue
        for guid, raw_name in pattern.findall(path.read_text()):
            name = raw_name.strip()
            if name.startswith('"'):
                name = json.loads(name)
            elif name.startswith("'") and name.endswith("'"):
                name = name[1:-1].replace("''", "'")
            key = guid + "[" + name + "]"
            if key in seen:
                continue
            seen.add(key)
            mesh_ids = [identity for identity in guid_locations.get(guid, []) if locations[identity]["type"].startswith("UnityEngine.Mesh,")]
            candidates = []
            for identity in mesh_ids:
                issue = issues.get(identity)
                if issue:
                    candidates.extend(issue.get("objects", []))
                else:
                    candidates.append(closure["converted"].get(str(identity), {}).get("native", {}))
            matches = {
                (row["source"], row["native_path_id"])
                for row in candidates
                if row.get("type") == "Mesh" and row.get("name") == name and row.get("source") and (export / row["source"]).is_file()
            }
            if len(mesh_ids) == 1 and len(matches) == 1:
                source, path_id = next(iter(matches))
                resolved.append(dict(key=key, source=source, native_path_id=path_id, type=locations[mesh_ids[0]]["type"], original_location=mesh_ids[0]))
            else:
                unresolved.append(dict(key=key, source=relative, mesh_locations=mesh_ids, matching_native_exports=len(matches)))
    return resolved, unresolved


def exported_mesh_signature(path):
    """Compare structural mesh data, never a same-named export filename alone."""
    import hashlib

    text = path.read_text()
    vertex = re.search(r"^    m_VertexCount: (\d+)$", text, re.M)
    submeshes = re.search(r"^  m_SubMeshes:\n(.*?)(?=^  m_Shapes:)", text, re.M | re.S)
    index = re.search(r"^  m_IndexBuffer: ([0-9a-f]+)$", text, re.M)
    data = re.search(r"^    _typelessdata: ([0-9a-f]+)$", text, re.M)
    if not vertex or not submeshes or not index or not data:
        return None
    fields = ("firstByte", "indexCount", "topology", "baseVertex", "firstVertex", "vertexCount")
    rows = re.split(r"^  - serializedVersion: \d+\n", submeshes[1], flags=re.M)[1:]
    values = [tuple(int(re.search(r"^    " + field + r": (-?\d+)$", row, re.M)[1]) for field in fields) for row in rows]
    return (
        (int(vertex[1]), tuple(values), hashlib.sha256(bytes.fromhex(index[1])).hexdigest(), hashlib.sha256(bytes.fromhex(data[1])).hexdigest())
        if values
        else None
    )


def native_mesh_signature(tree):
    import hashlib

    fields = ("firstByte", "indexCount", "topology", "baseVertex", "firstVertex", "vertexCount")
    try:
        return (
            int(tree["m_VertexData"]["m_VertexCount"]),
            tuple(tuple(int(row[field]) for field in fields) for row in tree["m_SubMeshes"]),
            hashlib.sha256(bytes(tree["m_IndexBuffer"])).hexdigest(),
            hashlib.sha256(bytes(tree["m_VertexData"]["m_DataSize"])).hexdigest(),
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def recover_ambiguous_mesh_subobjects(export, unresolved, metadata, native, receipts, accepted, work=WORK):
    """Resolve only unique native/export mesh signatures from accepted binaries."""
    import UnityPy

    locations = {row["id"]: row for row in metadata["locations"]}
    issues = {row["location"]: row for row in native["issues"]}
    files = {row["path"]: row["sha256"] for row in accepted["files"]}
    if accepted["input_id"] != read(work / "config/accepted-input.json")["input_id"]:
        raise RuntimeError("Ambiguous mesh recovery requires accepted input")
    needed = {}
    for row in unresolved:
        if len(row["mesh_locations"]) != 1:
            continue
        identity = row["mesh_locations"][0]
        name = row["key"].split("[", 1)[1][:-1]
        failures = [
            failure
            for failure in issues.get(identity, {}).get("failures", [])
            if failure["category"] == "ambiguous-exported-object" and failure["native"]["type"] == "Mesh" and failure["native"]["name"] == name
        ]
        if len(failures) != 1:
            continue
        owner = locations[identity]["dependencies"][0]
        needed.setdefault(owner, []).append((row, identity, failures[0]))
    resolved = []
    for owner, requests in needed.items():
        receipt = receipts / ("%s.json" % owner)
        if not receipt.exists():
            continue
        evidence = read(receipt)
        source = evidence["source"]
        if evidence["location"] != owner or source not in files or evidence["sha256"] != files[source] or sha(game(work) / source) != files[source]:
            raise RuntimeError("Original mesh bundle receipt or accepted hash differs")
        environment = UnityPy.load(str(game(work) / source))
        objects = {(obj.assets_file.name, obj.path_id): obj for obj in environment.objects if obj.type.name == "Mesh"}
        for row, identity, failure in requests:
            original = failure["native"]
            obj = objects.get((original["serialized_file"], original["path_id"]))
            if obj is None:
                continue
            signature = native_mesh_signature(obj.read_typetree())
            matches = [
                candidate for candidate in failure["candidates"] if (export / candidate).is_file() and exported_mesh_signature(export / candidate) == signature
            ]
            if signature is None or len(matches) != 1:
                continue
            resolved.append(
                dict(
                    key=row["key"],
                    source=matches[0],
                    native_path_id=original["path_id"],
                    type=locations[identity]["type"],
                    original_location=identity,
                    resolution="native-mesh-signature",
                )
            )
        del environment
    return resolved


def _bundle_dependency_names(data, class_id):
    """Read release Android AssetBundle/PreloadData dependency names, not CAB links."""
    stream = io.BytesIO(data)

    def uint():
        return struct.unpack("<I", stream.read(4))[0]

    def skip(length):
        if length > len(data) - stream.tell():
            raise ValueError("Truncated bundle dependency record")
        stream.seek(length, 1)

    def text():
        length = uint()
        value = stream.read(length)
        if len(value) != length:
            raise ValueError("Truncated bundle dependency name")
        skip(-stream.tell() % 4)
        return value.decode("utf-8")

    text()  # NamedObject.m_Name
    skip(uint() * 12)  # PPtr preload table
    if class_id == 142:
        for _ in range(uint()):
            text()  # container asset path
            skip(20)  # AssetInfo: preload index/size, PPtr
        skip(24)  # main AssetInfo and runtime compatibility
        text()  # bundle name
    elif class_id != 150:
        raise ValueError("Expected AssetBundle or PreloadData")
    return [text() for _ in range(uint())]


def produced_bundle_metadata(files):
    """Hash real produced files and read their release Android dependency records.

    files maps bundle names to paths; neither target catalogs nor CAB externals
    supply dependencies. Reuses the bounded UnityFS/v22 reader without changing it.
    """
    spec = importlib.util.spec_from_file_location("_catalog_unity_write", ROOT / "tools/phone-build/accepted-output/unity_write.py")
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    result = {}
    for name, path in files.items():
        path = Path(path)
        bundle = writer.B.Bundle(path)
        dependencies = []
        records = 0
        for member_name in bundle.members:
            if member_name.endswith((".resS", ".resource")):
                continue
            member = bundle.member(member_name)
            layout = writer.read_serialized(member)
            if layout["platform"] != 13:
                raise ValueError("Expected produced Android bundle: " + name)
            for row in layout["objects"]:
                class_id = layout["types"][row["type_id"]]["class_id"]
                if class_id not in (142, 150):
                    continue
                member.seek(layout["data_offset"] + row["offset"])
                dependencies.extend(_bundle_dependency_names(writer.B.exact(member, row["bytes"]), class_id))
                records += 1
        if not records:
            raise ValueError("Produced bundle has no dependency record: " + name)
        result[name] = dict(sha256=sha(path), bytes=path.stat().st_size, dependencies=list(dict.fromkeys(dependencies)))
    return result


def integration_catalog(metadata, bundles, *, bundle_names):
    """Finish catalog bytes from produced file facts and a complete direct graph.

    Mirrors WholeCatalogBuild.Complete's member order and transitive dependency
    arrays. Native cycles are retained; the requesting bundle excludes itself.
    bundle_names must include every declared build, including bundles without
    location rows. Incomplete graphs cannot advertise unavailable content.
    """
    names = set(bundle_names)
    required = names | {row["bundle"] for row in metadata["locations"]}
    required.update(dependency for name in names if name in bundles for dependency in bundles[name]["dependencies"])
    missing = required - bundles.keys()
    if missing:
        raise ValueError("Missing produced catalog bundles: " + ", ".join(sorted(missing)))
    if required - names:
        raise ValueError("Catalog references undeclared bundles: " + ", ".join(sorted(required - names)))
    completed = {}
    for name in sorted(names):
        seen = {name}
        pending = list(bundles[name]["dependencies"])
        while pending:
            dependency = pending.pop()
            if dependency not in seen:
                seen.add(dependency)
                pending.extend(bundles[dependency]["dependencies"])
        seen.remove(name)
        row = bundles[name]
        completed[name] = dict(sha256=row["sha256"], bytes=row["bytes"], dependencies=sorted(seen))
    return json.dumps(dict(metadata, bundles=completed), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def integration_bundle_metadata(metadata, builds):
    """Assign location owners from explicit AssetBundleBuild declarations, without I/O.

    Mirrors WholeCatalogBuild.Append ownership, not imported dependencies or hashes.
    Callers supply every explicit build, including presentation and geometry inputs.
    """
    owners = {}
    names = {build["assetBundleName"] for build in builds}
    for build in builds:
        for path in build["assetNames"]:
            key = path.casefold()
            if key in owners:
                raise RuntimeError("Duplicate explicit bundle ownership: " + path)
            owners[key] = build["assetBundleName"]
    paths = {}
    for row in metadata["locations"]:
        key = row["path"].casefold()
        if key not in owners:
            paths.setdefault(key, row["path"])
    names.add("whole-game-content")
    for key, path in paths.items():
        if path.lower().endswith(".unity"):
            name = "whole-scene-" + Path(path).stem.lower()
            if name in names:
                raise RuntimeError("Scene bundle name collision: " + name)
            names.add(name)
        else:
            name = "whole-game-content"
        owners[key] = name
    return dict(metadata, locations=[dict(row, bundle=owners[row["path"].casefold()]) for row in metadata["locations"]])


def integration_metadata(metadata, closure, mapped, mesh_subobjects, *, attempt, camera_roots=None, bundle_builds=None):
    """Assemble catalog identities from regenerated inputs and explicit destination paths.

    No project, filesystem, or Editor access; callers own source GUID/path resolution.
    This is integration metadata, not a final bundle catalog or readiness proof.
    The current build adds camera roots by default; an accepted build predating
    that extension supplies an empty camera_roots iterable and its source mapping.
    """
    roots = set(closure["roots"]) | set(closure.get("runtime_roots", [])) | set(CAMERA_SHADER_ROOTS if camera_roots is None else camera_roots)
    locations = []
    for row in metadata["locations"]:
        conversion = closure["converted"].get(str(row["id"]))
        if conversion and conversion["source"] in mapped:
            locations.append(dict(id=row["id"], path=mapped[conversion["source"]], type=row["type"], primaryKey=row["primaryKey"], root=row["id"] in roots))
    next_location_id = max(row["id"] for row in metadata["locations"]) + 1
    subobject_keys = []
    for row in mesh_subobjects:
        if row["source"] not in mapped:
            raise RuntimeError("Exact original mesh subobject was not staged: " + row["key"])
        locations.append(dict(id=next_location_id, path=mapped[row["source"]], type=row["type"], primaryKey=row["key"], root=False))
        subobject_keys.append(dict(key=row["key"], keyType="System.String", locations=[next_location_id]))
        next_location_id += 1
    if not roots <= {row["id"] for row in locations}:
        raise RuntimeError("Provider roots lost during staging")
    result = dict(
        input_id=closure["input_id"],
        attempt=attempt,
        locations=locations,
        keys=metadata["keys"] + subobject_keys,
        providers=metadata["providers"],
        source_catalog_sha256=closure["source_catalog_sha256"],
        roots=sorted(roots),
        provider_roots=closure["roots"],
        runtime_roots=closure.get("runtime_roots", []),
        quarantine=[],
    )
    return result if bundle_builds is None else integration_bundle_metadata(result, bundle_builds)


def prepare_integration(io=None, *, attempt=None):
    """Import the complete discovered closure, reusing existing GUID owners once."""
    from composition_io import StageIO

    io = io or StageIO()
    if attempt is not None and (not io.rebuilding or not re.fullmatch(r"integration-[A-Za-z0-9._-]+", attempt)):
        raise RuntimeError("Pinned integration attempt requires destination rebuild")
    io.preflight()
    out = io.catalog()
    export = io.resolve(io.read(io.work / "config/reconstruction.json")["projects"][0])
    closure = io.read(out / "reconciled-closure.json")
    if closure["input_id"] != io.read(io.work / "config/accepted-input.json")["input_id"]:
        raise RuntimeError("Whole catalog belongs to different input")
    from catalog_rebuild import read_local_shader_override_selector

    current_selector = read_local_shader_override_selector(io.work, closure["input_id"])
    marker_path = io.project / ".rebuild/catalog-shader-overrides.json"
    if current_selector is None or current_selector["enabled"] is not True:
        if marker_path.is_symlink() or io.is_file(marker_path):
            raise RuntimeError("Destination has a prior shader override receipt; rebuild it from a clean destination before disabling overrides")
    from shader_postprocessing_bloom import check_staging_activation

    check_staging_activation(io, closure["input_id"])
    from shader_postprocessing_uber import check_staging_activation as check_uber_activation

    check_uber_activation(io, closure["input_id"])
    metadata = read_catalog(catalog_path(out))
    native = io.read(out / "native-conversions.json")
    mesh_subobjects, unresolved_mesh_subobjects = source_mesh_subobjects(export, closure, metadata, native)
    # The rebuild regenerates its own native receipts in the destination (J725).
    receipts = out / "native-containers" if io.rebuilding else io.resolve(io.read(out / "native-latest.json")["path"])
    recovered = recover_ambiguous_mesh_subobjects(
        export, unresolved_mesh_subobjects, metadata, native, receipts, io.read(io.work / "inventory/files.json"), io.work
    )
    mesh_subobjects.extend(recovered)
    unresolved_mesh_subobjects = [row for row in unresolved_mesh_subobjects if row["key"] not in {entry["key"] for entry in recovered}]
    index = io.read(out / "source-guid-index.json")
    guids = {path: guid for guid, path in index.items()}
    repairs = {row["source"]: row for row in io.read(out / "source-guid-repairs.json")} if (out / "source-guid-repairs.json").exists() else {}
    project = io.project
    owners = {}
    for meta in io.glob(project / "Assets", "**/*.meta"):
        match = re.search(r"^guid:\s*([a-f0-9]{32})", io.read_text(meta, errors="replace"), re.M)
        if match:
            if match[1] in owners:
                raise RuntimeError("Duplicate imported GUID; refuse ambiguous whole-content ownership")
            owners[match[1]] = str(Path(str(meta)[:-5]).relative_to(project))
    remaps = io.read(RECIPE / "hud-ui-remaps.json")
    if remaps["input_id"] != closure["input_id"]:
        raise RuntimeError("UI remaps belong to different input")
    camera_shader_paths = camera_shader_roots(metadata, closure)
    destination = out / (attempt if attempt is not None else "integration-" + now())
    io.mkdir(destination)
    mapped = {}
    copies = []
    # Copy each original identity once. Do not overwrite the accepted composition.
    for relative in sorted(set(closure["files"]) | camera_shader_paths | {row["source"] for row in mesh_subobjects}):
        source = export / relative
        guid = guids.get(relative)
        if not guid or not source.is_file():
            raise RuntimeError("Missing discovered source identity: " + relative)
        existing = owners.get(guid)
        if existing and (not io.rebuilding or io.is_file(project / existing)):
            mapped[relative] = existing
            continue
        if source.suffix == ".dll":
            # Exporter DLLs are not the receipted original runtime plugin inputs.
            # Their references are already measured through the binding remap table.
            continue
        target_relative = existing or "Assets/WholeGame/" + relative.removeprefix("Assets/")
        target = project / target_relative
        io.apply(target, copy=source, catalog=True)
        io.apply(Path(str(target) + ".meta"), copy=Path(str(source) + ".meta"), catalog=True)
        if relative in repairs:
            repair = repairs[relative]
            meta = Path(str(target) + ".meta")
            original = "guid: " + repair["source_guid"]
            if io.read_text(meta).count(original) != 1 or guid != repair["guid"]:
                raise RuntimeError("Measured scene GUID repair no longer matches export")
            io.apply(meta, io.read_text(meta).replace(original, "guid: " + guid))
        with source.open("rb") as stream:
            yaml = stream.read(5) == b"%YAML"
        if yaml:
            text = source.read_text()
            for row in remaps["rows"]:
                text = text.replace(row["from"], row["to"])
            if text != source.read_text():
                io.apply(target, text)
        mapped[relative] = target_relative
        owners[guid] = target_relative
        copies.append(dict(source=relative, target=target_relative, sha256=io.sha(target), meta_sha256=io.sha(Path(str(target) + ".meta"))))
    override_receipt = _validated_shader_overrides(io, closure, metadata, mapped, export, project, destination)
    from shader_postprocessing_bloom import stage as stage_postprocessing_bloom

    bloom_receipt = stage_postprocessing_bloom(io, export=export, mapped=mapped, owners=owners, destination=destination, input_id=closure["input_id"])
    from shader_postprocessing_uber import stage as stage_postprocessing_uber

    uber_receipt = stage_postprocessing_uber(io, export=export, mapped=mapped, owners=owners, destination=destination, input_id=closure["input_id"])
    if not io.rebuilding:
        repair_support_source(export, mapped, project, destination, io)
    for copied in copies:
        copied["sha256"] = io.sha(project / copied["target"])
    manifest = integration_metadata(metadata, closure, mapped, mesh_subobjects, attempt=destination.name)
    roots = manifest["roots"]
    locations = manifest["locations"]
    io.write(destination / "manifest.json", manifest)
    io.write(
        destination / "mesh-subobjects.json",
        dict(
            resolved=mesh_subobjects,
            unresolved=unresolved_mesh_subobjects,
            scope="Exact original serialized GUID/name/type and native container/export identity; unresolved refs stay explicit",
        ),
    )
    io.write(
        destination / "import-receipt.json",
        dict(
            copied=copies,
            reused=len(mapped) - len(copies),
            files=len(mapped),
            roots=len(roots),
            shader_overrides=override_receipt,
            postprocessing_bloom=bloom_receipt,
            postprocessing_uber=uber_receipt,
        ),
    )
    io.write(out / "integration-latest.json", dict(path=io.label(destination)))
    if not io.rebuilding:
        copy_catalog_asset(ROOT / "tools/unity/runtime/catalog/WholeCatalogLoader.cs", project / "Assets/LabLoadingScene/WholeCatalogLoader.cs")
        copy_catalog_asset(ROOT / "tools/unity/runtime/catalog/WholeCatalogBootstrap.cs", project / "Assets/LabLoadingScene/WholeCatalogBootstrap.cs")
        copy_catalog_asset(ROOT / "tools/catalog/WholeCatalogHost.cs", project / "Assets/Editor/WholeCatalogHost.cs")
    print(
        json.dumps(
            dict(
                copied=len(copies),
                reused=len(mapped) - len(copies),
                roots=len(roots),
                mapped_locations=len(locations),
                evidence=io.label(destination),
            )
        )
    )
    return override_receipt


def host_integration():
    """Cheap engine import/type checks before a large Android content build."""
    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    attempt = ROOT / read(out / "integration-latest.json")["path"]
    export_catalog(attempt, "ValidateWholeCatalog.cs.txt", "host-integration.json")
    result = read(attempt / "host-integration.json")
    print(json.dumps(result["summary"], indent=2))
    if not result["success"]:
        raise RuntimeError("Whole-content import has concrete failures; inspect host-integration.json")


def host_providers():
    import time

    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    attempt = ROOT / read(out / "integration-latest.json")["path"]
    result_path = attempt / "host-provider-result.json"
    if result_path.exists():
        result_path.rename(attempt / ("host-provider-previous-" + now() + ".json"))
    export_catalog(attempt, "StartWholeCatalog.cs.txt", "host-provider-dispatch.json")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if result_path.exists():
            result = read(result_path)
            if result.get("success") or result.get("error") or result.get("finished"):
                print(json.dumps(result, indent=2))
                if not result["success"]:
                    raise RuntimeError("Original content-provider integration failed; retain attributed evidence")
                return
        time.sleep(2)
    raise RuntimeError("Host provider dispatch has no terminal result; inspect before repeating")


def repair_root_bindings():
    """Resolve exporter filename collisions by measured script/type identity."""
    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    attempt = ROOT / read(out / "integration-latest.json")["path"]
    failed = read(attempt / "host-integration.json")["failures"]
    export = ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
    closure = read(out / "reconciled-closure.json")
    metadata = read_catalog(catalog_path(out))
    locations = {row["id"]: row for row in metadata["locations"]}
    contracts = ROOT / read(out / "contracts-latest.json")["path"]
    runtime = read(contracts / "runtime-contracts.json")
    scripts = {(row["guid"], str(row["fileId"])): row["type"] for row in runtime["scripts"]}
    conversions = read(out / "native-conversions.json")["conversions"]
    correction_path = out / "typed-import-conversions.json"
    if correction_path.exists():
        corrections = read(correction_path)
        if corrections["metadata_sha256"] != sha(catalog_path(out)):
            raise RuntimeError("Typed import corrections belong to a different catalog")
        conversions.update(corrections["conversions"])
    repairs = []
    file_index = {}
    for file in read(WORK / "inventory/files.json")["files"]:
        file_index.setdefault(Path(file["path"]).name, []).append(file)
    for failure in failed:
        row = locations[failure["id"]]
        if row["id"] not in set(closure["roots"]) | set(closure.get("runtime_roots", [])):
            raise RuntimeError("Unexpected non-root import failure")
        old = closure["converted"][str(row["id"])]["source"]
        wanted = row["type"].split(",")[0]
        if wanted in ("UnityEngine.Material", "UnityEngine.Texture2D"):
            owner = row["dependencies"][0]
            receipt = attempt / ("typed-import-native-" + str(owner) + ".json")
            if not receipt.exists():
                write(receipt, inspect_native_bundle(owner, locations, file_index))
            original = read(receipt)
            accepted = next(file for file in read(WORK / "inventory/files.json")["files"] if file["path"] == original["source"])
            if original["sha256"] != accepted["sha256"] or original["location"] != owner:
                raise RuntimeError("Typed subasset receipt belongs to different input")
            kind = wanted.rsplit(".", 1)[-1]
            native = [entry for entry in original["containers"] if entry["address"].casefold() == row["internalId"].casefold() and entry["type"] == kind]
            exported = {}
            for candidate in (export / old).parent.iterdir():
                if candidate.suffix == ".meta" or not candidate.is_file():
                    continue
                with candidate.open("rb") as stream:
                    prefix = stream.read(16384)
                text = prefix.decode(errors="replace") if prefix.startswith(b"%YAML") else ""
                header = re.search(r"^--- !u!(\d+)", text, re.M)
                name = re.search(r"^  m_Name: (.*)$", text, re.M)
                asset_kind = {21: "Material", 28: "Texture2D"}.get(int(header[1])) if header else None
                object_name = name[1] if name else None
                if candidate.suffix.lower() in (".png", ".tga", ".jpg", ".exr"):
                    asset_kind, object_name = "Texture2D", candidate.stem
                if asset_kind and object_name:
                    exported.setdefault((str(Path(old).parent), asset_kind, object_name), []).append(str(candidate.relative_to(export)))
            objects, issues = native_candidates(native, exported)
            if issues or len(objects) != 1:
                raise RuntimeError("Original typed subasset conversion remains ambiguous: " + str(dict(location=row["id"], objects=objects, issues=issues)))
            conversion = dict(source=objects[0]["source"], resolution="original-typed-container", native=objects[0], original_internal_id=row["internalId"])
            conversions[str(row["id"])] = conversion
            repairs.append(dict(location=row["id"], previous=old, conversion=conversion))
            continue
        name = Path(row["internalId"]).stem
        candidates = []
        for candidate in (export / old).parent.glob("*.asset"):
            with candidate.open("rb") as stream:
                text = stream.read(65536).decode(errors="replace")
            script = re.search(r"m_Script: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: \d+\}", text)
            object_name = re.search(r"^  m_Name: (.*)$", text, re.M)
            if script and object_name and object_name[1] == name and scripts.get((script[2], script[1])) == wanted:
                candidates.append(str(candidate.relative_to(export)))
        if len(candidates) != 1:
            raise RuntimeError("Typed collision unresolved: " + str(dict(location=row["id"], candidates=candidates)))
        conversion = dict(source=candidates[0], resolution="typed-script-export-collision", original_internal_id=row["internalId"], expected_type=wanted)
        conversions[str(row["id"])] = conversion
        repairs.append(dict(location=row["id"], previous=old, conversion=conversion))
    write(attempt / "typed-import-repairs.json", repairs)
    prior_corrections = read(out / "typed-import-conversions.json")["conversions"] if (out / "typed-import-conversions.json").exists() else {}
    prior_corrections.update({str(row["location"]): row["conversion"] for row in repairs})
    write(out / "typed-import-conversions.json", dict(metadata_sha256=sha(catalog_path(out)), conversions=prior_corrections))
    assembly_hash = sha(game() / "Risk of Rain 2_Data/Managed/RoR2.dll")
    key = digest(dict(input=assembly_hash, ilspy="11.0.0.9375", args="project-referencepath-csharp9-v2"))
    helper = WORK / "decompiled/RoR2" / key[:16] / "RoR2.ContentManagement/AddressablesLoadHelper.cs"
    contract = read(out / "original-catalog-contract.json")
    if contract["input_sha256"] != assembly_hash:
        raise RuntimeError("Runtime key metadata belongs to different input")
    result = analyze(
        catalog_path(out),
        export,
        read(out / "source-guid-index.json"),
        helper.read_text(),
        conversions,
        contract.get("assetKeyCandidates", []),
        contract.get("legacyAliases", {}),
        helper.parents[1],
    )
    result.update(input_id=closure["input_id"], source_catalog_sha256=closure["source_catalog_sha256"], metadata_sha256=sha(catalog_path(out)))
    write(out / "reconciled-closure.json", result)
    print(json.dumps(dict(repaired=len(repairs), closure_files=len(result["files"]))))


def source_identity_lifecycle_metadata(project, stage, source_scene_receipts):
    """Return receipt-bound source identity metadata, or None before source-scenes exists."""
    from source_scene_candidate import SCENES
    from source_identity_metadata import read_scene as source_identity_metadata

    staged_scene = Path(project) / "Assets/LabLoadingScene/SourceScenes" / stage / (stage + ".unity")
    if not staged_scene.is_file():
        return None
    if stage not in SCENES or not (SCENES[stage] == "Base" or stage == "lakes"):
        return None
    identity_metadata = source_identity_metadata(staged_scene)
    receipt_hash = (source_scene_receipts or {}).get(stage)
    if receipt_hash != identity_metadata["source_scene_sha256"]:
        raise RuntimeError("Generated source identity metadata differs from the source-scene receipt: " + stage)
    return identity_metadata


def original_stage_contexts(export, stages, input_id, pool_keys, project=None, source_scene_receipts=None, include_source_identity=False):
    """Recover native population policy from each original serialized scene."""
    from source_scene_candidate import SCENES

    export = Path(export)
    contexts = {}
    fields = {
        "ignoreArtifactsThatRebuildCards": bool,
        "contentSourceMixLimitOverride": bool,
        "contentSourceMixLimitOverrideValue": int,
        "contentInteractableOnlySourceMixLimitOverride": bool,
        "contentInteractableOnlySourceMixLimitOverrideValue": int,
        "sceneDirectorInteractibleCredits": int,
        "sceneDirectorMonsterCredits": int,
    }
    for stage in stages:
        if stage not in SCENES:
            raise RuntimeError("Unreviewed original stage population source: " + stage)
        scene_root = SCENES[stage]
        source = export / ("Assets/RoR2/" + scene_root + "/Scenes/" + stage + "/" + stage + ".unity")
        blocks = re.split(r"(?=^--- !u!)", source.read_text(), flags=re.M)
        records = [block for block in blocks if re.search(r"^  monsterDccsPool:", block, re.M)]
        if len(records) != 1:
            raise RuntimeError("Original stage population context is ambiguous: " + stage)
        record = records[0]
        result = {"source_sha256": sha(source), "fields": {}}
        for name in ["monsterDccsPool", "interactableDccsPool"]:
            match = re.search(r"^  " + name + r": \{fileID: [-0-9]+, guid: ([a-f0-9]{32}), type: [0-9]+\}", record, re.M)
            if not match:
                raise RuntimeError("Original stage pool reference missing: " + stage + "/" + name)
            if match[1] not in pool_keys:
                raise RuntimeError("Stage pool has no unique typed runtime location: " + stage + "/" + name)
            result[name] = pool_keys[match[1]]
        for name, kind in fields.items():
            match = re.search(r"^  " + name + r": (-?\d+)$", record, re.M)
            if not match:
                raise RuntimeError("Original stage population policy missing: " + stage + "/" + name)
            value = int(match[1])
            result["fields"][name] = bool(value) if kind is bool else value
        directors = [block for block in blocks if re.search(r"^  usePlacedSpawnPoints:", block, re.M)]
        if len(directors) != 1:
            raise RuntimeError("Original scene director is ambiguous: " + stage)
        result["director_fields"] = {}
        for name, kind in {"usePlacedSpawnPoints": bool, "expRewardCoefficient": float, "eliteBias": float, "spawnDistanceMultiplier": float}.items():
            match = re.search(r"^  " + name + r": ([-0-9.eE+]+)$", directors[0], re.M)
            if not match:
                raise RuntimeError("Original scene director policy missing: " + stage + "/" + name)
            result["director_fields"][name] = bool(int(match[1])) if kind is bool else float(match[1])
        if not re.search(r"^  monsterSpawnTargetOverride: \{fileID: 0\}$", directors[0], re.M):
            raise RuntimeError("Original scene monster target requires a measured binding: " + stage)
        objects = {}
        transforms = {}
        game_transforms = {}
        for block in blocks:
            header = re.match(r"--- !u!(\d+) &(-?\d+)", block)
            if not header:
                continue
            kind, identity = map(int, header.groups())
            if kind == 1:
                name = re.search(r"^  m_Name: (.*)$", block, re.M)
                if name:
                    objects[identity] = name[1]
            elif kind in (4, 224):
                owner = re.search(r"^  m_GameObject: \{fileID: (-?\d+)\}", block, re.M)
                parent = re.search(r"^  m_Father: \{fileID: (-?\d+)\}", block, re.M)
                if owner and parent:
                    transforms[identity] = (int(owner[1]), int(parent[1]))
                    game_transforms[int(owner[1])] = identity

        def object_path(identity):
            path = []
            seen = set()
            current = game_transforms.get(identity)
            while current:
                if current in seen or current not in transforms:
                    raise RuntimeError("Original bonus object hierarchy invalid: " + stage)
                seen.add(current)
                owner, current = transforms[current]
                path.append(objects[owner])
            if not path:
                raise RuntimeError("Original bonus object is absent: " + stage)
            return "/".join(reversed(path))

        bonus = re.search(r"^  bonusInteractibleCreditObjects:(.*?)(?=^  [A-Za-z_]\w*:|\Z)", record, re.S | re.M)
        if not bonus:
            raise RuntimeError("Original bonus credit policy missing: " + stage)
        entries = list(re.finditer(r"^  - objectThatGrantsPointsIfEnabled: \{fileID: (-?\d+)\}\n    points: (-?\d+)$", bonus[1], re.M))
        if bonus[1].strip() != "[]" and (not entries or len(entries) != bonus[1].count("objectThatGrantsPointsIfEnabled:")):
            raise RuntimeError("Original bonus credit entry is unresolved: " + stage)
        result["bonus_credits"] = [{"path": object_path(int(match[1])), "points": int(match[2])} for match in entries]
        if include_source_identity and project is not None:
            identity_metadata = source_identity_lifecycle_metadata(project, stage, source_scene_receipts)
            if identity_metadata is not None and stage in ("golemplains", "lakes"):
                result["source_identity_lifecycle"] = identity_metadata
            if stage == "shipgraveyard":
                if identity_metadata is None:
                    raise RuntimeError("Siren source-entry identity scene is not staged: " + stage)
                controllers = identity_metadata["toggle_controllers"]
                if len(controllers) != 1 or controllers[0]["scene_id"] != 11:
                    raise RuntimeError("Siren source-entry metadata requires its unique scene-ID-11 controller")
                result["siren_source_entry"] = identity_metadata
        if include_source_identity and stage in ("golemplains", "lakes") and "source_identity_lifecycle" not in result:
            raise RuntimeError("Supported source identity lifecycle scene is not staged: " + stage)
        contexts[stage] = result
    result = {
        "input_id": input_id,
        "stages": contexts,
        "scope": "Original pool, scene-director policy and bonus-credit object identities. This policy-only context does not validate source identity metadata.",
    }
    if include_source_identity:
        result["source_identity_schema_version"] = 1
        result["scope"] = (
            "Original pool, scene-director policy, bonus-credit object identities and receipt-bound serialized source-stage identity/toggle bindings. Runtime activation remains limited to the explicit Golemplains/Lakes lifecycle gate."
        )
    return result


# A player build only roots an assembly whose types it saw serialized. Asset bundles
# built earlier in the same editor process count; a code-only build in a fresh editor
# reuses the payload and sees none, so the linker then strips reflected Addressables
# operations (J30-J33, J505). Preserve the set the device-verified J503 build rooted
# instead of depending on editor process history (J506). A build that rebuilds the
# Timeline-bearing bundles in-process also roots Unity.Timeline, so code-only and full
# builds rooted different sets (J583); preserving it makes both agree.
BUNDLE_ROOT_ASSEMBLIES = (
    "AK.Wwise.Unity.API",
    "AK.Wwise.Unity.API.WwiseTypes",
    "GenericIK",
    "KinematicCharacterController",
    "Rewired_Core",
    "Unity.Postprocessing.Runtime",
    "Unity.ResourceManager",
    "Unity.Timeline",
    "com.unity.multiplayer-hlapi.Runtime",
)


def preservation_descriptor(roots):
    """Return the whole-catalog link.xml for measured type roots and bundle-rooted assemblies."""
    import xml.etree.ElementTree as ET

    linker = ET.Element("linker")
    for name in sorted(set(roots) | set(BUNDLE_ROOT_ASSEMBLIES)):
        assembly = ET.SubElement(linker, "assembly", fullname=name)
        if name in BUNDLE_ROOT_ASSEMBLIES:
            assembly.set("preserve", "all")
        for type_name in sorted(roots.get(name, ())):
            ET.SubElement(assembly, "type", fullname=type_name.replace("+", "/"), preserve="all")
    return ET.tostring(linker, encoding="unicode")


def generate_build_maps(io, manifest, contract, source, code_only=False):
    from animation_bindings import repair as repair_animation_bindings
    from body_visual_map import generate as generate_body_visual_map
    from common_assets_map import generate as generate_common_asset_map

    project = io.project
    visual_map = generate_body_visual_map(
        source, project / "Assets/LabLoadingScene/OriginalBodyVisualMap.cs", manifest["input_id"], contract["legacyAliases"], manifest, io=io
    )
    health_source = source.with_name("HealthComponent.cs")
    health_visual_map = generate_body_visual_map(
        health_source, project / "Assets/LabLoadingScene/OriginalHealthVisualMap.cs", manifest["input_id"], contract["legacyAliases"], manifest, io=io
    )
    if health_visual_map["unlocated_fields"]:
        raise RuntimeError("Original health visual references are absent from the accepted content closure")
    common_map = generate_common_asset_map(
        source.with_name("GlobalEventManager.cs"),
        project / "Assets/LabLoadingScene/OriginalGlobalCommonAssetMap.cs",
        manifest["input_id"],
        contract["legacyAliases"],
        manifest,
        {"groundOnHitPrefab", "hollowPack"},
        io=io,
    )
    io.write(io.work / "body-visual-map-latest.json", dict(body=visual_map, health=health_visual_map))
    io.write(io.work / "global-common-map-latest.json", common_map)
    animation_bindings = repair_animation_bindings(project, io=io)
    if code_only and animation_bindings["repaired"]:
        raise RuntimeError("Original animation curves changed; a content build is required")
    if animation_bindings["repaired"] or animation_bindings["unresolved"]:
        io.write(io.work / "animation-bindings-latest.json", animation_bindings)
    if io.is_file(io.work / "scene-probe-build.json") and not io.is_file(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"):
        raise RuntimeError("Composed session is not staged for this generation; migrate it before building against an old scene recipe")
    stage_config = project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
    if io.is_file(stage_config):
        stages = [row["name"] for row in io.read(stage_config).get("stageCombatDecks", [])]
        export = io.resolve(io.read(io.work / "config/reconstruction.json")["projects"][0])
        pool_keys = {}
        for row in manifest["locations"]:
            if not row["type"].startswith("RoR2.DccsPool,"):
                continue
            meta = io.read_text(project / (row["path"] + ".meta"))
            guid = re.search(r"^guid: ([a-f0-9]{32})$", meta, re.M)[1]
            if guid in pool_keys and pool_keys[guid] != row["primaryKey"]:
                raise RuntimeError("Ambiguous stage pool serialized owner")
            pool_keys[guid] = row["primaryKey"]
        if not stages:
            # An empty policy configuration has no source scenes to bind. Keep the
            # existing build-entry contract acyclic and emit the ordinary empty
            # context resource without requiring the later R6 receipt.
            stage_contexts = original_stage_contexts(export, stages, manifest["input_id"], pool_keys, include_source_identity=False)
        else:
            scene_receipt_path = io.work / "experiments/source-scenes/candidate.json"
            if not io.is_file(scene_receipt_path):
                raise RuntimeError("Source-stage identity metadata requires the generated source-scene receipt")
            scene_receipt = io.read(scene_receipt_path)
            source_scene_receipts = {row["name"]: row["candidate_sha256"] for row in scene_receipt.get("staged", [])}
            stage_contexts = original_stage_contexts(
                export, stages, manifest["input_id"], pool_keys, project, source_scene_receipts, include_source_identity=True
            )
        io.write(project / "Assets/LabLoadingScene/Resources/WholeStageContexts.json", stage_contexts)


def stage_runtime_sources(io, runtime_sources):
    """Stage runtime C# and seed only missing Unity metadata from authored sidecars."""
    layout = io.read(RECIPE / "project-layout.json")
    guids = layout.get("runtime_source_guids") if isinstance(layout, dict) else None
    if not isinstance(guids, dict) or set(guids) != set(runtime_sources):
        raise RuntimeError("Runtime metadata must match the exact project-layout source/GUID map")

    runtime = io.project / "Assets/LabLoadingScene"
    sources = []
    missing_metas = []
    basenames = set()
    for filename in runtime_sources:
        basename = Path(filename).name
        if basename in basenames:
            raise RuntimeError("Runtime source staging has a basename collision: " + basename)
        basenames.add(basename)
        source = ROOT / "tools/unity" / filename
        source_meta = Path(str(source) + ".meta")
        target = runtime / basename
        target_meta = Path(str(target) + ".meta")
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("Runtime source is absent or symlinked: " + filename)
        expected = guids.get(filename)
        if expected is not None and (not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{32}", expected) is None):
            raise RuntimeError("Runtime source has an invalid project-layout GUID: " + filename)
        if target.is_symlink():
            raise RuntimeError("Runtime source destination refuses symlinks: " + str(target))
        if target_meta.is_symlink():
            raise RuntimeError("Runtime metadata destination refuses symlinks: " + str(target_meta))
        if target_meta.exists() and not target_meta.is_file():
            raise RuntimeError("Runtime metadata destination is not a regular file: " + str(target_meta))

        sources.append((filename, source, target))
        has_source_meta = source_meta.exists() or source_meta.is_symlink()
        if expected is None:
            # Null GUIDs are intentional for first-import sources without authored
            # sidecars. A sidecar with a null recipe identity is a mismatch, not a bypass.
            if has_source_meta:
                raise RuntimeError("Null project-layout GUID conflicts with authored runtime metadata: " + filename)
            continue

        if has_source_meta:
            if source_meta.is_symlink() or not source_meta.is_file():
                raise RuntimeError("Authored runtime metadata is not a regular file: " + filename)
            try:
                lines = source_meta.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as error:
                raise RuntimeError("Cannot read authored runtime metadata: " + filename) from error
            guid_lines = [line for line in lines if line.startswith("guid:")]
            if len(guid_lines) != 1 or re.fullmatch(r"guid: [0-9a-f]{32}", guid_lines[0]) is None or guid_lines[0][6:] != expected:
                raise RuntimeError("Authored runtime metadata GUID differs from project-layout.json: " + filename)
        elif not io.is_file(target_meta):
            raise RuntimeError("Missing runtime metadata has no regular authored sidecar: " + filename)

        if io.is_file(target_meta):
            # Preserve Unity-owned metadata. The existing build layout validator
            # remains responsible for checking its GUID against the tracked recipe.
            continue
        missing_metas.append((filename, source_meta, target_meta))

    # Validate the whole cohort before staging any C# source, so a bad/missing
    # sidecar cannot leave a partially updated runtime selection in the project.
    for _filename, source, target in sources:
        io.apply(target, copy=source, catalog=True)
    for _filename, source_meta, target_meta in missing_metas:
        io.apply(target_meta, copy=source_meta, catalog=True)


BUILD_EDITOR_SOURCES = [
    "AndroidProgressionHost.cs",
    "AndroidDiscoveryHost.cs",
    "AndroidProfileHost.cs",
    "AndroidLifecycleHost.cs",
    "SurvivorSkillHost.cs",
    "SurvivorSkillInputHost.cs",
    "SirenEncounterHost.cs",
    "TeleporterLifetimeHost.cs",
    "TeleportOverlayLifetimeHost.cs",
    "EngiShieldHitGuardHost.cs",
    "EngineerNativeOutputObserverFixture.cs",
    "SirenEggDiagnosticInputExactEditorFixture.cs",
    "SourceCameraGraphicsHost.cs",
    "LightningStakeSourceContractFixture.cs",
    "TeleporterExitTraceSourceContractFixture.cs",
    "SkillResponseCleanupExactEditorFixture.cs",
    "SurvivorCombatOutputObserverFixture.cs",
    "DeveloperSkillVariantSelectionFixture.cs",
    "FirstStageDiagnosticGateFixture.cs",
    "NativeDirectorDeckSetterFixture.cs",
    "SourceIdentityTransformParityFixture.cs",
    "MercEvisImpactEffectExactEditorFixture.cs",
    "WholeCatalogBuild.cs",
]


def stage_editor_sources(io):
    for filename in BUILD_EDITOR_SOURCES:
        io.apply(io.project / "Assets/Editor" / filename, copy=ROOT / "tools/catalog" / filename, catalog=True)


def stage_build_sources(io, runtime_sources, manifest, contracts):
    project = io.project
    # Stage the tracked runtime selection; keep existing Unity-owned .meta files.
    stage_runtime_sources(io, runtime_sources)
    # Exact-editor host fixtures; stage together so none goes stale in the project.
    stage_editor_sources(io)
    # Bundle-only serialized components and reflected location types are invisible
    # to the APK linker. Preserve their measured contracts, not a tested whitelist.
    roots = {}
    for row in manifest["locations"]:
        type_name, assembly = row["type"].split(",")[:2]
        roots.setdefault(assembly.strip(), set()).add(type_name)
    for row in contracts["contracts"]:
        bound = row.get("target_imported") or row.get("imported")
        if bound and bound["type"]:
            roots.setdefault(bound["assembly"], set()).add(bound["type"])
    # Native achievement registration discovers these original classes through
    # reflection; preserve their metadata, constructors and threshold properties.
    progression = {
        "RoR2.UnlockableCatalog",
        "RoR2.AchievementManager",
        "RoR2.RegisterAchievementAttribute",
        "RoR2.LocalUser",
        "RoR2.UserAchievementManager",
        "RoR2.Achievements.*",
    }
    roots.setdefault("RoR2", set()).update(progression)
    link_path = project / "Assets/LabLoadingScene/WholeCatalogPreservation/link.xml"
    io.apply(link_path, preservation_descriptor(roots))


def generate_build_bootstrap(io, manifest, closure):
    project = io.project
    if closure["input_id"] != manifest["input_id"]:
        raise RuntimeError("Source preload evidence belongs to another accepted input")
    missing_preloads = sorted({row["key"] for row in closure["runtime_key_edges"] if row.get("field") == "preloadGUIDReferences" and not row.get("locations")})
    io.write(
        project / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json",
        dict(attempt=manifest["attempt"], input_id=manifest["input_id"], missingSourcePreloadKeys=missing_preloads),
    )


def build_integration(
    code_only=False,
    destination=None,
    work=None,
    android_symbols="none",
    capture_player_linker_inputs=False,
    capture_il2cpp_invocation=False,
    iteration_mode="",
    bundle_compression="",
):
    from build import build_source_identity
    from build_lock import HOST_BUILD_LOCK, assert_build_unblocked, host_build_lock

    assert_build_unblocked()
    with (
        host_build_lock(HOST_BUILD_LOCK, operation="whole-catalog staging and build"),
        cached_hashes(cache_path=None if destination is not None else WORK / "build-hash-cache.json", reuse=bool(iteration_mode)),
    ):
        assert_build_unblocked()
        # Stage and build only committed sources, and record the commit (J738).
        identity = build_source_identity()
        extra = {"iteration_mode": iteration_mode} if iteration_mode else {}
        if bundle_compression:
            extra["bundle_compression"] = bundle_compression
        result = _build_integration(
            code_only=code_only,
            destination=destination,
            work=work,
            source_identity=identity,
            android_symbols=android_symbols,
            capture_player_linker_inputs=capture_player_linker_inputs,
            capture_il2cpp_invocation=capture_il2cpp_invocation,
            **extra,
        )
        if build_source_identity() != identity:
            raise RuntimeError("Build sources changed during the build; its receipt names " + identity["commit"])
        return result


def stage_source_collision_policy(io):
    """Restore only the accepted game's collision matrix, preserving other lab settings."""
    import struct
    import UnityPy

    inventory = io.read(io.work / "inventory/files.json")
    accepted = io.read(io.work / "config/accepted-input.json")
    relative = "Risk of Rain 2_Data/globalgamemanagers"
    entries = [row for row in inventory["files"] if row["path"] == relative]
    source = game(io.work) / relative
    if inventory["input_id"] != accepted["input_id"] or len(entries) != 1 or sha(source) != entries[0]["sha256"]:
        raise RuntimeError("Source physics settings differ from the accepted input inventory")
    objects = list(UnityPy.load(str(source)).objects)
    physics = [obj.read_typetree() for obj in objects if obj.type.name == "PhysicsManager"]
    tags = [obj.read_typetree() for obj in objects if obj.type.name == "TagManager"]
    if len(physics) != 1 or len(tags) != 1:
        raise RuntimeError("Expected one original PhysicsManager and TagManager")
    rows = physics[0].get("m_LayerCollisionMatrix")
    layers = tags[0].get("layers")
    if not isinstance(rows, list) or len(rows) != 32 or any(type(row) is not int or not 0 <= row <= 0xFFFFFFFF for row in rows):
        raise RuntimeError("Original physics collision matrix must contain 32 uint32 rows")
    if not isinstance(layers, list) or len(layers) != 32 or any(not isinstance(name, str) for name in layers):
        raise RuntimeError("Original physics collision matrix requires its complete layer table")
    if any(bool(rows[a] & (1 << b)) != bool(rows[b] & (1 << a)) for a in range(32) for b in range(32)):
        raise RuntimeError("Original physics collision matrix is not symmetric")
    tag_text = io.read_text(io.project / "ProjectSettings/TagManager.asset")
    match = re.search(r"^  layers:\n(.*?)^  m_SortingLayers:", tag_text, re.M | re.S)
    current_layers = re.findall(r"^  -(?: (.*))?$", match[1], re.M) if match else []
    if current_layers != layers:
        raise RuntimeError("Staged physics layer names differ from original collision-matrix indices")
    path = io.project / "ProjectSettings/DynamicsManager.asset"
    before = io.read_text(path)
    pattern = r"(^  m_LayerCollisionMatrix: )[0-9a-fA-F]{256}(?=\n|$)"
    if len(re.findall(pattern, before, re.M)) != 1:
        raise RuntimeError("Staged physics collision matrix has an unexpected serialized shape")
    after = re.sub(pattern, lambda match: match[1] + struct.pack("<32I", *rows).hex(), before, flags=re.M)
    io.apply(path, data=after)
    io.write(
        io.project / ".rebuild/source-collision-policy.json", dict(input_id=inventory["input_id"], source_sha256=entries[0]["sha256"], layers=layers, rows=rows)
    )


def _build_integration(
    code_only=False,
    destination=None,
    work=None,
    source_identity=None,
    android_symbols="none",
    capture_player_linker_inputs=False,
    capture_il2cpp_invocation=False,
    iteration_mode="",
    bundle_compression="",
):
    import time

    staging_start = time.monotonic()
    from build import build, freeze_whole_payload, generate_content_recipe, generate_runtime_config, validate_runtime_source_membership
    from composition_io import StageIO

    if bundle_compression and (code_only or destination is not None or iteration_mode or android_symbols != "none" or capture_player_linker_inputs):
        raise RuntimeError("Uncompressed bundles require a full iteration build without symbols/captures")

    if iteration_mode and (not code_only or destination is not None or android_symbols != "none" or capture_player_linker_inputs):
        raise RuntimeError("Iteration requires current-project code-only build without symbols/capture")

    if capture_il2cpp_invocation and not capture_player_linker_inputs:
        raise RuntimeError("IL2CPP invocation capture requires --capture-player-linker-inputs for the pre-strip join")
    if destination is not None:
        if code_only:
            raise RuntimeError("Destination builds require full content; payload reuse is forbidden")
        if capture_player_linker_inputs or capture_il2cpp_invocation:
            raise RuntimeError("UnityLinker input capture is supported only for the current local whole-catalog build")
        # R1–R8 already supplied the host products. Share the Unity half only.
        if android_symbols != "none":
            raise RuntimeError("Debugging symbol builds are supported only by the current local whole-catalog build")
        from native_view_camera_build_hook import restore_previous_camera
        from original_music_output_observer_build_hook import restore as restore_previous_music_output_observer
        from original_game_audio_build_hook import stage_for_build
        from rebuild import safe_destination
        from source_scene_candidate import synchronize_audio

        destination_work = Path(work or WORK).resolve(strict=True)
        destination_input_id = read(destination_work / "config/accepted-input.json")["input_id"]
        destination_project = safe_destination(destination, destination_input_id, destination_work)
        # R6 owns scene content. R9 must not silently change its selected variant.
        synchronize_audio(StageIO(destination_work, destination_project), code_only=True)
        restore_previous_camera(destination_project, destination_work)
        restore_previous_music_output_observer(destination_project, destination_work)
        audio_inputs = stage_for_build(destination_project, WORK, selection_path=destination_work / "config/original-game-audio/selection.json")
        collision_io = StageIO(destination_work, destination_project)
        stage_source_collision_policy(collision_io)
        collision_io.flush()
        result = build("vulkan", force=True, reuse_payload=code_only, destination=destination, work=work)
        if isinstance(result, dict):
            result["source"] = source_identity
            result["original_audio"] = audio_inputs
            result["native_view_camera"] = {
                "staged": False,
                "reason": "destination rebuilds preserve the off-by-default camera owner but do not run its current-project transform; opt-in camera creation refuses when its merged marker is absent",
            }
        return result
    io = StageIO(WORK)
    project = io.project
    from original_game_audio_stage import restore_authored

    restore_authored(project)
    stage_source_collision_policy(io)
    # Both build paths own their config inputs; never inherit migration or probe extras.
    generate_runtime_config(project)
    generate_content_recipe()
    runtime_sources = validate_runtime_source_membership(project, **({"retire_previous": True} if not code_only else {}))
    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    attempt = ROOT / read(out / "integration-latest.json")["path"]
    if not read(attempt / "host-integration.json")["success"]:
        raise RuntimeError("Whole roots must pass typed import before building")
    manifest = read(attempt / "manifest.json")
    assembly_hash = sha(game() / "Risk of Rain 2_Data/Managed/RoR2.dll")
    decompile_key = digest(dict(input=assembly_hash, ilspy="11.0.0.9375", args="project-referencepath-csharp9-v2"))
    source = WORK / "decompiled/RoR2" / decompile_key[:16] / "RoR2/CharacterBody.cs"
    contract = read(out / "original-catalog-contract.json")
    if contract["input_sha256"] != assembly_hash or manifest["input_id"] != read(WORK / "config/accepted-input.json")["input_id"]:
        raise RuntimeError("Original body visual references belong to another accepted input")
    from source_scene_candidate import synchronize_audio

    synchronize_audio(io, code_only=code_only)
    generate_build_maps(io, manifest, contract, source, code_only)
    contract_dir = ROOT / read(out / "contracts-latest.json")["path"]
    from native_view_camera_build_hook import restore_previous_camera, stage_after_audio
    from original_music_output_observer_build_hook import restore as restore_previous_music_output_observer
    from original_game_audio_build_hook import stage_for_build

    restore_previous_camera(project, WORK)
    restore_previous_music_output_observer(project, WORK)
    audio_inputs = stage_for_build(project, WORK)
    camera_inputs = stage_after_audio(project, WORK, audio_inputs)
    stage_build_sources(io, runtime_sources, manifest, read(contract_dir / "result.json"))
    generate_build_bootstrap(io, manifest, read(out / "reconciled-closure.json"))
    write(WORK / "whole-catalog-build.json", dict(manifest=str(attempt / "manifest.json")))
    if code_only:
        for filename in runtime_sources:
            rel = "Assets/LabLoadingScene/" + Path(filename).name
            if sha(ROOT / "tools/unity" / filename) != sha(project / rel):
                raise RuntimeError("Code-only source was not staged: " + rel)
    previous = attempt / "build.json"
    if previous.exists():
        previous.rename(attempt / ("build-previous-" + now() + ".json"))
    staging_seconds = time.monotonic() - staging_start
    if bundle_compression:
        result = build("vulkan", force=True, source=source_identity, bundle_compression=bundle_compression)
    elif iteration_mode:
        result = build("vulkan", force=True, reuse_payload=True, source=source_identity, iteration_mode=iteration_mode)
    elif capture_player_linker_inputs:
        result = build(
            "vulkan",
            force=android_symbols == "none",
            reuse_payload=code_only,
            source=source_identity,
            android_symbols=android_symbols,
            capture_player_linker_inputs=True,
            capture_il2cpp_invocation=capture_il2cpp_invocation,
        )
    elif android_symbols == "none":
        result = build("vulkan", force=True, reuse_payload=code_only, source=source_identity)
    else:
        result = build(
            "vulkan",
            force=False,
            reuse_payload=code_only,
            source=source_identity,
            android_symbols=android_symbols,
        )
    if isinstance(result, dict):
        result["original_audio"] = audio_inputs
        result["native_view_camera"] = camera_inputs
        result["composition_staging_seconds"] = staging_seconds
    if not code_only:
        freeze_start = time.monotonic()
        freeze_whole_payload(project, result, **({"receipt": WORK / "whole-catalog-uncompressed-base.json"} if bundle_compression else {}))
        if isinstance(result, dict):
            result["payload_freeze_seconds"] = time.monotonic() - freeze_start
    if isinstance(result, dict):
        result["pipeline_wall_seconds"] = time.monotonic() - staging_start
        if "apk" in result and "key" in result:
            write(WORK / "build-cache" / result["key"] / "result.json", result)
            write(WORK / "config/current-build.json", result)
    write(attempt / "build.json", result)
    return result


def run_integration():
    """One broad, attributed device scan; leave the ordinary game launch available."""
    import time
    from device import Device, PACKAGE
    from build import preflight

    preflight()
    out = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    attempt = ROOT / read(out / "integration-latest.json")["path"]
    evidence = attempt / ("device-" + now())
    evidence.mkdir()
    d = Device()
    result = dict(success=False)
    selection_path = None
    try:
        result["install"] = d.install(read(WORK / "config/current-build.json")["apk"])
        result["bootstrap"] = d.launch()
        runtime = d.read_receipt("runtime.json")["persistentDataPath"]
        result["sync"] = d.sync()
        candidate_selection = runtime + "/whole-catalog-selection.json"
        if d.sh("sh", "-c", "test ! -e " + candidate_selection + " || echo present", check=False).strip() == "present":
            raise RuntimeError("Unexpected existing catalog launch selection")
        source = WORK / "generated-android-data/whole-catalog.json"
        write(evidence / "selection.json", dict(manifest_sha256=sha(source)))
        d.cmd("push", str(evidence / "selection.json"), candidate_selection)
        selection_path = candidate_selection
        d.sh("am", "force-stop", PACKAGE)
        previous_report = runtime + "/whole-catalog-result.json"
        previous = d.sh("cat", previous_report, check=False)
        if previous:
            (evidence / "previous-runtime.txt").write_text(previous)
        d.sh("rm", "-f", previous_report)
        d.display(True)
        result["launch"] = d.sh("am", "start", "-W", "-n", PACKAGE + "/com.unity3d.player.UnityPlayerActivity")
        started = time.monotonic()
        deadline = started + 480
        while time.monotonic() < deadline:
            pid = d.sh("pidof", PACKAGE, check=False).strip()
            if not pid:
                raise RuntimeError("Integrated catalog process exited")
            result["pid"] = pid
            text = d.sh("cat", previous_report, check=False)
            try:
                record = json.loads(text)
            except ValueError:
                record = None
            if record:
                write(evidence / "runtime.json", record)
                if record.get("finished"):
                    result["runtime"] = record
                    result["success"] = record["success"]
                    break
            time.sleep(1)
        if "runtime" not in result:
            raise RuntimeError("Whole-catalog scan has no terminal result")
        result["seconds"] = time.monotonic() - started
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        try:
            d.collect("all", evidence / "capture")
        finally:
            d.sh("am", "force-stop", PACKAGE)
            if selection_path:
                d.sh("rm", "-f", selection_path)
            d.display(False)
            write(evidence / "result.json", result)
            write(attempt / "device-latest.json", dict(path=str(evidence.relative_to(ROOT))))
    print(json.dumps(dict(success=result["success"], runtime=result.get("runtime"), evidence=str(evidence.relative_to(ROOT))), indent=2))
    if not result["success"]:
        raise RuntimeError("Whole-catalog Android integration failed; inspect first attributed failure")
