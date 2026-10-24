"""Host-only R3/R4 replay over the catalog analysis regenerated in the destination (J725)."""

from pathlib import Path, PurePosixPath
import hashlib
import json
import re

from common import RECIPE, ROOT, read, sha
from composition_io import StageIO


SHADER_OVERRIDE_ROWS = (
    (
        16022,
        "41e90cbc5ad198a438128b019f8d8553",
        "RoR2/Base/Shaders/HGOutlineHighlight.shader",
        "Assets/RoR2/Base/Shaders/PostProcess/HGOutlineHighlight.shader",
        None,
    ),
    (15950, "c14b6abb309b8c246add9e94a6920d7f", "RoR2/Base/Shaders/RampFog.shader", "Assets/RoR2/Base/Shaders/CustomPostProcess/RampFog.shader", None),
    (
        2537,
        "e4abd95960ed75f4a9f59cac7c40bd9d",
        "TranslucentImage/DownTent.shader",
        "Assets/Le Tai's Asset/TranslucentImage/FormerResources/DownTent.shader",
        "b950b7b50f8e9734e8b26f23f8409418",
    ),
    (
        2538,
        "12e87e7c7fde8e74db9f75172456c5c3",
        "TranslucentImage/EfficientBlur.shader",
        "Assets/Le Tai's Asset/TranslucentImage/FormerResources/EfficientBlur.shader",
        "f7022f9f8b1c05f45b0e69d890d31534",
    ),
    (
        2539,
        "d996ab4381100014d99e25e68e9aac84",
        "TranslucentImage/FillCrop.shader",
        "Assets/Le Tai's Asset/TranslucentImage/FormerResources/FillCrop.shader",
        "89c413d50c7159d42a05c19230c43769",
    ),
    (
        2540,
        "b12e02e9a9b684543a286089a03cb04b",
        "TranslucentImage/QuickDumbBlur.shader",
        "Assets/Le Tai's Asset/TranslucentImage/FormerResources/QuickDumbBlur.shader",
        "e5c4572c0a575514bb041a5a82e33cea",
    ),
    (
        8943,
        "62decc840d5afaa49886d8b13165939e",
        "RoR2/Base/Core/CameraEffects/HGScreenDamage.shader",
        "Assets/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader",
        "ed4a1bae3abd8f34b905b509b4ff70e0",
    ),
    (
        16024,
        "780f79b2a62a0df439dedf59c533eee6",
        "RoR2/Base/Shaders/HGSobelBuffer.shader",
        "Assets/RoR2/Base/Shaders/PostProcess/HGSobelBuffer.shader",
        "6d9e1738bf3095e42a34d9feb449ad3b",
    ),
    (
        15952,
        "7d6541fe01591cd418caf48d3c099e52",
        "RoR2/Base/Shaders/SobelOutline.shader",
        "Assets/RoR2/Base/Shaders/CustomPostProcess/SobelOutline.shader",
        "0af91730b526684408399853ee967ce8",
    ),
)
SHADER_OVERRIDE_GENERATORS = {
    16022: (
        "shader_outline.py",
        "recipe/shader-outline-candidate.json",
        "private-outline-highlight-generated-candidate-r1",
        "manifest.json",
        "sources/OutlineHighlightCandidate.shader",
        "generated_shader_path",
        "Hopoo Games/Internal/Outline Highlight",
        -5736718617091362218,
    ),
    2537: (
        "shader_translucent.py",
        "recipe/shader-translucent-candidate.json",
        "local-source-bound-translucent-wrapper-candidate-r1",
        "manifests/DownTent.json",
        "sources/DownTent.shader",
        "generated_shader_path",
        "Hidden/DownTent",
        8446615176080386013,
    ),
    2538: (
        "shader_translucent.py",
        "recipe/shader-translucent-candidate.json",
        "local-source-bound-translucent-wrapper-candidate-r1",
        "manifests/EfficientBlur.json",
        "sources/EfficientBlur.shader",
        "generated_shader_path",
        "Hidden/EfficientBlur",
        6370232586618374777,
    ),
    2539: (
        "shader_translucent.py",
        "recipe/shader-translucent-candidate.json",
        "local-source-bound-translucent-wrapper-candidate-r1",
        "manifests/FillCrop.json",
        "sources/FillCrop.shader",
        "generated_shader_path",
        "Hidden/FillCrop",
        5721449320467667425,
    ),
    2540: (
        "shader_translucent.py",
        "recipe/shader-translucent-candidate.json",
        "local-source-bound-translucent-wrapper-candidate-r1",
        "manifests/QuickDumbBlur.json",
        "sources/QuickDumbBlur.shader",
        "generated_shader_path",
        "UI/QuickDumbBlur",
        -5627814109785558414,
    ),
    15950: (
        "shader_ramp_fog.py",
        "recipe/shader-ramp-fog-candidate.json",
        1,
        "candidate.json",
        "sources/RampFogCandidate.shader",
        "generated_shader",
        "Hidden/PostProcess/RampFog",
        2910825169780710437,
    ),
    8943: (
        "shader_ramp_fog.py",
        "recipe/shader-screen-damage-candidate.json",
        1,
        "candidate.json",
        "sources/ScreenDamageCandidate.shader",
        "generated_shader",
        "Hopoo Games/Post Process/Screen Damage",
        916309824485114785,
    ),
    16024: (
        "shader_ramp_fog.py",
        "recipe/shader-sobel-buffer-candidate.json",
        1,
        "candidate.json",
        "sources/SobelBufferCandidate.shader",
        "generated_shader",
        "Hopoo Games/Internal/SobelBuffer",
        -583016510457714391,
    ),
    15952: (
        "shader_ramp_fog.py",
        "recipe/shader-sobel-outline-candidate.json",
        1,
        "candidate.json",
        "sources/SobelOutlineCandidate.shader",
        "generated_shader",
        "Hidden/PostProcess/SobelOutline",
        2831377250017133402,
    ),
}


def translucent_candidate_identity_matches(manifest, recipe, location_id, catalog_key, source_path, path_id, shader_name):
    """Match the four exact source identities and their measured pass/keyword shape."""
    source = manifest.get("source", {})
    shader_spec = next((row for row in recipe.get("shaders", []) if row.get("catalog_location") == location_id), None)
    if (
        shader_spec is None
        or manifest.get("schema") != recipe.get("candidate_schema")
        or manifest.get("success") is not True
        or source.get("bundle_sha256") != recipe.get("source", {}).get("bundle_sha256")
        or source.get("catalog_key") != catalog_key
        or source.get("catalog_location") != location_id
        or source.get("asset_path") != source_path
        or type(source.get("shader_path_id")) is not int
        or source.get("shader_path_id") != path_id
        or source.get("shader_name") != shader_name
        or shader_spec.get("catalog_key") != catalog_key
        or shader_spec.get("source_asset_path") != source_path
        or shader_spec.get("path_id") != path_id
        or shader_spec.get("serialized_name") != shader_name
        or manifest.get("semantic_equivalence_proven") is not False
        or any(
            manifest.get(field) is not False
            for field in ("android_compile_or_render_tested", "appearance_parity_proven", "unity_compiled", "android_accepted", "visual_parity_proven")
        )
    ):
        return False
    mapping = manifest.get("pass_mapping")
    if not isinstance(mapping, list) or len(mapping) != shader_spec.get("pass_count"):
        return False
    axes = shader_spec.get("keyword_axes", [])
    expected_variants = [[], list(axes)] if axes else [[]]
    return all(
        isinstance(row, dict)
        and row.get("pass_index") == index
        and row.get("keyword_variants") == expected_variants
        and isinstance(row.get("programs"), dict)
        and bool(row["programs"])
        for index, row in enumerate(mapping)
    )


def read_local_shader_override_selector(work, input_id):
    """Read the optional, input-bound local activation switch; absence means off."""
    work = Path(work).absolute()
    path = work / "config/shader-catalog-overrides.json"
    if work.is_symlink() or path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("Local shader override selector path may not contain symlinks")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 4096 or not path.resolve().is_relative_to(work.resolve()):
        raise RuntimeError("Local shader override selector is not a bounded regular file under work/")
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Local shader override selector is malformed") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "input_id", "enabled"}
        or data.get("schema") != "whole-catalog-shader-overrides-activation-r1"
        or data.get("input_id") != input_id
        or type(data.get("enabled")) is not bool
    ):
        raise RuntimeError("Local shader override selector has an unknown schema or input")
    return {**data, "sha256": hashlib.sha256(raw).hexdigest()}


def shader_override_rows(receipt, input_id, expected, provenance, candidate_work=None):
    """Validate the exact default shader exceptions to byte-identical replay."""
    if receipt is None:
        return {}
    candidate_work = Path(candidate_work or ROOT / "work")
    selector = read_local_shader_override_selector(candidate_work, input_id)
    if (
        selector is None
        or selector["enabled"] is not True
        or receipt.get("selector_path") != "work/config/shader-catalog-overrides.json"
        or receipt.get("selector_sha256") != selector["sha256"]
    ):
        raise RuntimeError("Shader override receipt does not match the current local selector")
    if (
        receipt.get("schema") != "whole-catalog-shader-override-receipt-r2"
        or receipt.get("input_id") != input_id
        or receipt.get("enabled") is not True
        or receipt.get("unity_compiled") is not False
        or receipt.get("android_accepted") is not False
        or receipt.get("visual_parity_proven") is not False
    ):
        raise RuntimeError("Shader override receipt is not a qualified source-only receipt")
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) not in (2, 6, 7, len(SHADER_OVERRIDE_ROWS)):
        raise RuntimeError("Shader override receipt must contain a historical two/six-root profile or the complete current profile")
    expected_rows = SHADER_OVERRIDE_ROWS[: len(rows)]
    result = {}
    for row, (location_id, guid, primary_key, source_path, exporter_guid) in zip(rows, expected_rows, strict=True):
        target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
        generator, generator_recipe, schema, manifest_name, shader_name, manifest_path_field, shader_name_value, object_path_id = SHADER_OVERRIDE_GENERATORS[
            location_id
        ]
        if (
            row.get("location_id") != location_id
            or row.get("guid") != guid
            or row.get("type") != "UnityEngine.Shader, UnityEngine.CoreModule, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"
            or row.get("primary_key") != primary_key
            or row.get("source_asset_path") != source_path
            or (exporter_guid is not None and row.get("exporter_guid") != exporter_guid)
            or row.get("target") != target
            or not isinstance(row.get("candidate_shader_sha256"), str)
            or row.get("generator") != generator
            or row.get("generator_recipe") != generator_recipe
            or row.get("generator_sha256") != sha(ROOT / "scripts/lab" / generator)
            or row.get("generator_recipe_sha256") != sha(ROOT / generator_recipe)
        ):
            raise RuntimeError("Shader override row differs from its exact catalog identity or provenance: " + str(location_id) + " " + repr(row))
        # These two catalog-added shaders are not members of the original
        # provenance map. If a future map does contain one, it must agree with
        # the exact receipt rather than widening this exception.
        source_provenance = provenance.get(target)
        if source_provenance is not None and (
            source_provenance.get("sha256") != row.get("original_source_sha256")
            or source_provenance.get("producer") != "repo-builder"
            or not any(item.get("function") == "whole_catalog.prepare_integration" for item in source_provenance.get("evidence", []))
        ):
            raise RuntimeError("Shader override source provenance conflicts with its receipt: " + target)
        meta_provenance = provenance.get(target + ".meta")
        if meta_provenance is not None and meta_provenance.get("sha256") != row.get("original_meta_sha256"):
            raise RuntimeError("Shader override metadata provenance conflicts with its receipt: " + target + ".meta")
        if exporter_guid is not None and row.get("exporter_guid") != exporter_guid:
            raise RuntimeError("Shader override exporter metadata GUID differs from its exact recipe: " + str(location_id))
        for field in (
            "original_source_sha256",
            "original_meta_sha256",
            "preserved_meta_sha256",
            "generator_sha256",
            "generator_recipe_sha256",
            "candidate_manifest_sha256",
            "candidate_shader_sha256",
        ):
            if not isinstance(row.get(field), str) or len(row[field]) != 64 or any(char not in "0123456789abcdef" for char in row[field]):
                raise RuntimeError("Shader override receipt has an invalid digest: " + field)
        if type(row.get("preserved_meta_bytes")) is not int or row["preserved_meta_bytes"] < 0:
            raise RuntimeError("Shader override receipt has an invalid preserved metadata size")
        recipe = read(ROOT / generator_recipe)
        stable_output = recipe.get("stable_output")
        if not isinstance(stable_output, str) or "{input_id}" not in stable_output:
            raise RuntimeError("Shader override generator recipe lacks an input-bound output path")
        expected_root = "work/" + stable_output.format(input_id=input_id)
        manifest_rel = row.get("candidate_manifest_path")
        shader_rel = row.get("candidate_shader_path")
        if manifest_rel != expected_root + "/" + manifest_name or shader_rel != expected_root + "/" + shader_name:
            raise RuntimeError("Shader override candidate path differs from its current recipe")
        manifest_path = candidate_work / Path(manifest_rel).relative_to("work")
        shader_path = candidate_work / Path(shader_rel).relative_to("work")
        if (
            any(path.is_symlink() for path in (*manifest_path.parents, manifest_path, *shader_path.parents, shader_path))
            or not manifest_path.is_file()
            or not shader_path.is_file()
            or sha(manifest_path) != row.get("candidate_manifest_sha256")
            or sha(shader_path) != row.get("candidate_shader_sha256")
            or shader_path.stat().st_size != row.get("candidate_shader_bytes")
        ):
            raise RuntimeError("Shader override candidate output changed after staging")
        candidate_manifest = read(manifest_path)
        if (
            candidate_manifest.get("schema") != schema
            or candidate_manifest.get("generator_sha256") != row["generator_sha256"]
            or candidate_manifest.get("recipe_sha256") != row["generator_recipe_sha256"]
            or candidate_manifest.get("source", {}).get("input_id") != input_id
            or candidate_manifest.get(manifest_path_field) != shader_name
            or candidate_manifest.get("generated_shader_sha256") != row["candidate_shader_sha256"]
        ):
            raise RuntimeError("Shader override candidate manifest no longer matches its input")
        if location_id == 16022:
            candidate_identity_matches = (
                candidate_manifest.get("success") is True
                and candidate_manifest.get("object_path_id") == object_path_id
                and candidate_manifest.get("source", {}).get("catalog_key") == guid
                and candidate_manifest.get("source", {}).get("catalog_location") == location_id
                and candidate_manifest.get("source", {}).get("asset_path") == source_path
            )
        elif location_id in (2537, 2538, 2539, 2540):
            candidate_identity_matches = (
                translucent_candidate_identity_matches(
                    candidate_manifest, read(ROOT / generator_recipe), location_id, guid, source_path, object_path_id, shader_name_value
                )
                and row.get("exporter_guid") == exporter_guid
            )
        else:
            candidate_identity_matches = (
                candidate_manifest.get("kind")
                == (
                    "local-source-bound-"
                    + {15950: "ramp-fog", 8943: "screen-damage", 16024: "sobel-buffer", 15952: "sobel-outline"}[location_id]
                    + "-candidate"
                )
                and candidate_manifest.get("source", {}).get("shader_path_id") == object_path_id
                and candidate_manifest.get("source", {}).get("shader_name") == shader_name_value
            )
        if not re.match(rb"\s*Shader\s+" + re.escape(json.dumps(shader_name_value).encode()) + rb"\s*\{", shader_path.read_bytes()):
            raise RuntimeError("Shader override candidate declaration changed")
        if not candidate_identity_matches:
            raise RuntimeError("Shader override candidate identity changed")
        result[target] = row
        result[target + ".meta"] = {**row, "_meta_only": True}
    return result


def read_shader_override_receipt(project, input_id, work):
    """Load a persisted marker only when its input, selector, and receipt join."""
    project = Path(project)
    work = Path(work)
    marker_path = project / ".rebuild/catalog-shader-overrides.json"
    if marker_path.is_symlink():
        raise RuntimeError("Catalog shader override marker is not a regular file")
    if not marker_path.exists():
        return None
    if any(path.is_symlink() for path in (marker_path, *marker_path.parents)) or not marker_path.is_file():
        raise RuntimeError("Catalog shader override marker is not a regular file")
    marker = read(marker_path)
    if (
        set(marker) != {"schema", "input_id", "receipt_path", "receipt_sha256", "selector_path", "selector_sha256"}
        or marker.get("schema") != "whole-catalog-shader-override-marker-r2"
        or marker.get("input_id") != input_id
    ):
        raise RuntimeError("Catalog shader override marker belongs to a different input or schema")
    relative = Path(marker.get("receipt_path", ""))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(marker.get("receipt_path", "")):
        raise RuntimeError("Catalog shader override receipt path is unsafe")
    receipt_path = project / relative
    if (
        not receipt_path.resolve().is_relative_to(project.resolve())
        or any(path.is_symlink() for path in (receipt_path, *receipt_path.parents))
        or not receipt_path.is_file()
        or sha(receipt_path) != marker.get("receipt_sha256")
    ):
        raise RuntimeError("Catalog shader override receipt is missing or changed")
    selector = read_local_shader_override_selector(work, input_id)
    receipt = read(receipt_path)
    if (
        selector is None
        or selector["enabled"] is not True
        or marker.get("selector_path") != "work/config/shader-catalog-overrides.json"
        or marker.get("selector_sha256") != selector["sha256"]
        or receipt.get("selector_path") != marker["selector_path"]
        or receipt.get("selector_sha256") != marker["selector_sha256"]
    ):
        raise RuntimeError("Catalog shader override marker does not match the current local selector")
    return receipt


def read_postprocessing_bloom_receipt(project, input_id, work, io=None):
    """Read the Bloom batch's independent marker/receipt chain, if enabled."""
    from shader_postprocessing_bloom import MARKER_SCHEMA, read_activation

    project, work = Path(project), Path(work)
    is_file = io.is_file if io is not None else Path.is_file
    read_json = io.read if io is not None else read
    digest = io.sha if io is not None else sha
    marker_path = project / ".rebuild/postprocessing-bloom.json"
    if marker_path.is_symlink():
        raise RuntimeError("Bloom batch marker may not be a symlink")
    activation = read_activation(work, input_id)
    if not is_file(marker_path):
        if activation is not None and activation.get("enabled") is True:
            raise RuntimeError("Bloom batch is enabled but no staging receipt exists")
        return None
    if any(path.is_symlink() for path in (marker_path, *marker_path.parents)) or not is_file(marker_path):
        raise RuntimeError("Bloom batch marker is not a regular file")
    marker = read_json(marker_path)
    if (
        set(marker) != {"schema", "input_id", "receipt_path", "receipt_sha256", "activation_path", "activation_sha256"}
        or marker.get("schema") != MARKER_SCHEMA
        or marker.get("input_id") != input_id
    ):
        raise RuntimeError("Bloom batch marker belongs to another input or schema")
    if (
        activation is None
        or activation.get("enabled") is not True
        or marker.get("activation_path") != "work/config/postprocessing-bloom.json"
        or marker.get("activation_sha256") != activation["sha256"]
    ):
        raise RuntimeError("Bloom batch marker does not match the current local activation")
    relative = Path(marker.get("receipt_path", ""))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
        raise RuntimeError("Bloom batch receipt path is unsafe")
    receipt_path = project / relative
    if (
        not receipt_path.resolve().is_relative_to(project.resolve())
        or any(path.is_symlink() for path in (receipt_path, *receipt_path.parents))
        or not is_file(receipt_path)
        or digest(receipt_path) != marker.get("receipt_sha256")
    ):
        raise RuntimeError("Bloom batch receipt is missing or changed")
    return read_json(receipt_path)


def postprocessing_bloom_rows(receipt, input_id, expected, provenance, candidate_work=None):
    """Validate Bloom's input-bound batch exception without changing six-row shader selection."""
    if receipt is None:
        return {}
    from shader_postprocessing_bloom import RECEIPT_SCHEMA, SCHEMA, candidate_root, load_recipe, read_activation

    candidate_work = Path(candidate_work or ROOT / "work")
    activation = read_activation(candidate_work, input_id)
    recipe = load_recipe(input_id)
    generator_sha = sha(ROOT / "scripts/lab/shader_postprocessing_bloom.py")
    recipe_sha = sha(RECIPE / "shader-postprocessing-bloom-candidate.json")
    if (
        activation is None
        or activation.get("enabled") is not True
        or receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("input_id") != input_id
        or receipt.get("activation_sha256") != activation["sha256"]
        or receipt.get("recipe_sha256") != recipe_sha
        or receipt.get("generator_sha256") != generator_sha
        or receipt.get("unity_compiled") is not False
        or receipt.get("android_accepted") is not False
        or receipt.get("visual_parity_proven") is not False
    ):
        raise RuntimeError("Bloom batch receipt does not match the accepted activation and authored generator")
    manifest_rel = receipt.get("candidate_manifest_path")
    expected_root = "work/" + recipe["stable_output"].format(input_id=input_id)
    if manifest_rel != expected_root + "/manifest.json":
        raise RuntimeError("Bloom candidate manifest path differs from its recipe")
    manifest_path = candidate_work / Path(manifest_rel).relative_to("work")
    if (
        any(path.is_symlink() for path in (manifest_path, *manifest_path.parents))
        or not manifest_path.is_file()
        or sha(manifest_path) != receipt.get("candidate_manifest_sha256")
    ):
        raise RuntimeError("Bloom candidate manifest is absent or changed")
    manifest = read(manifest_path)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("input_id") != input_id
        or manifest.get("recipe_sha256") != recipe_sha
        or manifest.get("generator_sha256") != generator_sha
        or manifest.get("package_sha256") != recipe["package_sha256"]
        or manifest.get("unity_compiled") is not False
        or manifest.get("android_accepted") is not False
        or manifest.get("visual_parity_proven") is not False
    ):
        raise RuntimeError("Bloom candidate manifest has stale provenance or qualification state")
    rows, manifest_rows = receipt.get("rows"), manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != len(recipe["expected_members"]) or not isinstance(manifest_rows, list) or len(manifest_rows) != len(rows):
        raise RuntimeError("Bloom batch receipt does not contain the exact shader membership")
    result = {}
    output = candidate_root(candidate_work, input_id, recipe)
    for row, generated, identity in zip(rows, manifest_rows, recipe["expected_members"], strict=True):
        source = identity["shader"]
        target = "Assets/WholeGame/" + source.removeprefix("Assets/")
        candidate_rel = generated.get("candidate_path")
        candidate = output / candidate_rel
        if (
            generated.get("source_asset_path") != source
            or generated.get("resource_asset_path") != identity["resource"]
            or generated.get("guid") != identity["guid"]
            or generated.get("original_source_sha256") != identity["shader_sha256"]
            or generated.get("original_meta_sha256") != identity["meta_sha256"]
            or generated.get("resource_sha256") != identity["resource_sha256"]
            or generated.get("candidate_shader_sha256") != recipe["candidate_bloom_shader_sha256"]
            or row.get("source_asset_path") != source
            or row.get("resource_asset_path") != identity["resource"]
            or row.get("guid") != identity["guid"]
            or row.get("target") != target
            or row.get("original_source_sha256") != identity["shader_sha256"]
            or row.get("original_meta_sha256") != identity["meta_sha256"]
            or row.get("resource_sha256") != identity["resource_sha256"]
            or row.get("candidate_path") != candidate_rel
            or row.get("candidate_shader_sha256") != generated.get("candidate_shader_sha256")
            or not candidate.is_file()
            or any(path.is_symlink() for path in (candidate, *candidate.parents))
            or sha(candidate) != generated.get("candidate_shader_sha256")
        ):
            raise RuntimeError("Bloom batch member differs from its exact source/resource/candidate identity")
        source_provenance = provenance.get(target)
        if source_provenance is not None and source_provenance.get("sha256") != identity["shader_sha256"]:
            raise RuntimeError("Bloom batch source conflicts with project provenance")
        result[target] = {
            **row,
            "_bloom_candidate": True,
            "candidate_shader_sha256": generated["candidate_shader_sha256"],
            "candidate_shader_bytes": candidate.stat().st_size,
        }
        result[target + ".meta"] = {**row, "_meta_only": True}
    copy_row, generated_copy = receipt.get("copy_std"), manifest.get("copy_std")
    copy_identity = recipe.get("companion_copy_std")
    if not isinstance(copy_row, dict) or not isinstance(generated_copy, dict) or not isinstance(copy_identity, dict):
        raise RuntimeError("Bloom batch lacks its exact source-camera CopyStd companion")
    copy_target = "Assets/WholeGame/" + copy_identity["shader"].removeprefix("Assets/")
    copy_candidate = output / copy_identity["candidate_path"]
    if (
        any(generated_copy.get(key) != value for key, value in copy_identity.items())
        or generated_copy.get("shader") != copy_identity["shader"]
        or generated_copy.get("resource") != copy_identity["resource"]
        or generated_copy.get("guid") != copy_identity["guid"]
        or generated_copy.get("shader_sha256") != copy_identity["shader_sha256"]
        or generated_copy.get("meta_sha256") != copy_identity["meta_sha256"]
        or generated_copy.get("resource_sha256") != copy_identity["resource_sha256"]
        or generated_copy.get("candidate_path") != copy_identity["candidate_path"]
        or generated_copy.get("package_shader_sha256") != recipe["package_copy_std_shader_sha256"]
        or generated_copy.get("candidate_sha256") != recipe["package_copy_std_shader_sha256"]
        or any(copy_row.get(key) != value for key, value in copy_identity.items())
        or copy_row.get("target") != copy_target
        or copy_row.get("candidate_path") != generated_copy.get("candidate_path")
        or copy_row.get("guid") != copy_identity["guid"]
        or copy_row.get("candidate_sha256") != generated_copy.get("candidate_sha256")
        or copy_row.get("candidate_sha256") != recipe["package_copy_std_shader_sha256"]
        or copy_row.get("preserved_meta_sha256") != copy_identity["meta_sha256"]
        or not copy_candidate.is_file()
        or any(path.is_symlink() for path in (copy_candidate, *copy_candidate.parents))
        or sha(copy_candidate) != generated_copy.get("candidate_sha256")
    ):
        raise RuntimeError("Source-camera CopyStd companion differs from its exact package/source/resource identity")
    copy_provenance = provenance.get(copy_target)
    if copy_provenance is not None and copy_provenance.get("sha256") != copy_identity["shader_sha256"]:
        raise RuntimeError("CopyStd source conflicts with project provenance")
    result[copy_target] = {
        **copy_row,
        "source_asset_path": copy_identity["shader"],
        "resource_asset_path": copy_identity["resource"],
        "original_source_sha256": copy_identity["shader_sha256"],
        "original_meta_sha256": copy_identity["meta_sha256"],
        "resource_sha256": copy_identity["resource_sha256"],
        "resource_meta_sha256": copy_identity["resource_meta_sha256"],
        "source_camera_prefab_path": copy_identity["source_camera_prefab"]["path"],
        "source_camera_prefab_sha256": copy_identity["source_camera_prefab"]["sha256"],
        "source_camera_prefab_meta_sha256": copy_identity["source_camera_prefab"]["meta_sha256"],
        "candidate_shader_sha256": generated_copy["candidate_sha256"],
        "candidate_shader_bytes": copy_candidate.stat().st_size,
        "_bloom_candidate": True,
    }
    result[copy_target + ".meta"] = {
        **copy_row,
        "source_asset_path": copy_identity["shader"],
        "original_meta_sha256": copy_identity["meta_sha256"],
        "preserved_meta_sha256": copy_identity["meta_sha256"],
        "_meta_only": True,
    }
    includes, generated_includes = receipt.get("includes"), manifest.get("includes")
    expected_hlsl_count = sum(name.endswith(".hlsl") for name in recipe["expected_package_include_sha256"])
    if (
        not isinstance(includes, list)
        or len(includes) != expected_hlsl_count
        or not isinstance(generated_includes, list)
        or len(includes) != len(generated_includes)
    ):
        raise RuntimeError("Bloom batch receipt does not contain the exact include closure")
    for row, generated in zip(includes, generated_includes, strict=True):
        target = recipe["include_target_prefix"] + PurePosixPath(generated["candidate_path"]).relative_to("includes").as_posix()
        meta_target = target + ".meta"
        source_path = output / generated["candidate_path"]
        source_meta = output / generated["candidate_meta_path"]
        if (
            row.get("target") != target
            or row.get("meta_target") != meta_target
            or row.get("candidate_path") != generated.get("candidate_path")
            or row.get("candidate_meta_path") != generated.get("candidate_meta_path")
            or row.get("candidate_sha256") != generated.get("candidate_sha256")
            or row.get("candidate_meta_sha256") != generated.get("candidate_meta_sha256")
            or row.get("guid") != generated.get("guid")
            or not source_path.is_file()
            or not source_meta.is_file()
            or any(path.is_symlink() for path in (source_path, source_meta, *source_path.parents, *source_meta.parents))
            or sha(source_path) != generated.get("candidate_sha256")
            or sha(source_meta) != generated.get("candidate_meta_sha256")
        ):
            raise RuntimeError("Bloom package include closure differs from its candidate receipt")
        result[target] = {**row, "_generated_only": True}
        result[meta_target] = {**row, "_generated_meta": True}
    return result


def read_postprocessing_uber_receipt(project, input_id, work, io=None):
    """Read the independent source-camera Uber receipt, if locally enabled."""
    from shader_postprocessing_uber import MARKER_SCHEMA, read_activation

    project, work = Path(project), Path(work)
    is_file = io.is_file if io is not None else Path.is_file
    read_json = io.read if io is not None else read
    digest = io.sha if io is not None else sha
    marker_path = project / ".rebuild/postprocessing-uber.json"
    if any(path.is_symlink() for path in (marker_path, *marker_path.parents)):
        raise RuntimeError("Uber batch marker may not be a symlink")
    activation = read_activation(work, input_id)
    if not is_file(marker_path):
        if activation is not None and activation.get("enabled") is True:
            raise RuntimeError("Uber batch is enabled but no staging receipt exists")
        return None
    marker = read_json(marker_path)
    if (
        set(marker) != {"schema", "input_id", "receipt_path", "receipt_sha256", "activation_path", "activation_sha256"}
        or marker.get("schema") != MARKER_SCHEMA
        or marker.get("input_id") != input_id
        or activation is None
        or activation.get("enabled") is not True
        or marker.get("activation_path") != "work/config/postprocessing-uber.json"
        or marker.get("activation_sha256") != activation["sha256"]
    ):
        raise RuntimeError("Uber marker does not match the current input-bound activation")
    relative = Path(marker["receipt_path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
        raise RuntimeError("Uber batch receipt path is unsafe")
    receipt_path = project / relative
    if (
        not receipt_path.resolve().is_relative_to(project.resolve())
        or any(path.is_symlink() for path in (receipt_path, *receipt_path.parents))
        or not is_file(receipt_path)
        or digest(receipt_path) != marker.get("receipt_sha256")
    ):
        raise RuntimeError("Uber batch receipt is missing or changed")
    return read_json(receipt_path)


def postprocessing_uber_rows(receipt, input_id, expected, provenance, candidate_work=None):
    """Validate the separate Uber batch receipt without changing Bloom receipts."""
    if receipt is None:
        return {}
    from shader_postprocessing_uber import RECEIPT_SCHEMA, SCHEMA, candidate_root, parse_guid, read_activation

    candidate_work = Path(candidate_work or ROOT / "work")
    activation = read_activation(candidate_work, input_id)
    recipe = read(RECIPE / "shader-postprocessing-uber-candidate.json")
    generator_path = ROOT / "scripts/lab/shader_postprocessing_uber.py"
    generator_sha, recipe_sha = sha(generator_path), sha(RECIPE / "shader-postprocessing-uber-candidate.json")
    if (
        activation is None
        or activation.get("enabled") is not True
        or receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("input_id") != input_id
        or receipt.get("activation_sha256") != activation["sha256"]
        or receipt.get("recipe_sha256") != recipe_sha
        or receipt.get("generator_sha256") != generator_sha
        or receipt.get("unity_compiled") is not False
        or receipt.get("android_accepted") is not False
        or receipt.get("visual_parity_proven") is not False
    ):
        raise RuntimeError("Uber receipt does not match current activation and authored generator")
    expected_manifest = "work/" + recipe["stable_output"].format(input_id=input_id) + "/manifest.json"
    if receipt.get("candidate_manifest_path") != expected_manifest:
        raise RuntimeError("Uber candidate manifest path differs from recipe")
    manifest_path = candidate_work / Path(expected_manifest).relative_to("work")
    if (
        any(p.is_symlink() for p in (manifest_path, *manifest_path.parents))
        or not manifest_path.is_file()
        or sha(manifest_path) != receipt.get("candidate_manifest_sha256")
    ):
        raise RuntimeError("Uber candidate manifest is absent or changed")
    manifest = read(manifest_path)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("input_id") != input_id
        or manifest.get("recipe_sha256") != recipe_sha
        or manifest.get("generator_sha256") != generator_sha
        or manifest.get("package_sha256") != recipe.get("package_sha256")
        or manifest.get("pass_count") != recipe.get("source_pass_count")
        or manifest.get("selected_pass") != recipe.get("selected_pass")
        or manifest.get("unity_compiled") is not False
        or manifest.get("android_accepted") is not False
        or manifest.get("visual_parity_proven") is not False
    ):
        raise RuntimeError("Uber candidate manifest has stale provenance or qualification state")
    contract = recipe["camera_contract"]
    shader_path = contract["shader"]
    target = "Assets/WholeGame/" + shader_path.removeprefix("Assets/")
    candidate_rel = "sources/Hidden_PostProcessing_Uber_53.shader"
    candidate = candidate_root(candidate_work, input_id, recipe) / candidate_rel
    identity = manifest.get("source_identity", {})
    if (
        receipt.get("shader_target") != target
        or receipt.get("source_sha256") != contract["shader_sha256"]
        or receipt.get("candidate_sha256") != manifest.get("shader_candidate_sha256")
        or receipt.get("resource_target") != "Assets/WholeGame/" + contract["resource"].removeprefix("Assets/")
        or receipt.get("resource_sha256") != contract["resource_sha256"]
        or receipt.get("resource_meta_sha256") != contract["resource_meta_sha256"]
        or receipt.get("camera_target") != "Assets/WholeGame/" + contract["source_camera_prefab"].removeprefix("Assets/")
        or receipt.get("camera_sha256") != contract["source_camera_prefab_sha256"]
        or receipt.get("camera_meta_sha256") != contract["source_camera_prefab_meta_sha256"]
        or identity.get("shader") != shader_path
        or identity.get("shader_sha256") != contract["shader_sha256"]
        or identity.get("shader_meta_sha256") != contract["shader_meta_sha256"]
        or identity.get("shader_meta_guid") != contract["shader_guid"]
        or identity.get("resource") != contract["resource"]
        or identity.get("resource_sha256") != contract["resource_sha256"]
        or identity.get("resource_meta_sha256") != contract["resource_meta_sha256"]
        or identity.get("resource_meta_guid") != contract["resource_asset_guid"]
        or identity.get("source_camera_prefab") != contract["source_camera_prefab"]
        or identity.get("source_camera_prefab_sha256") != contract["source_camera_prefab_sha256"]
        or identity.get("source_camera_prefab_meta_sha256") != contract["source_camera_prefab_meta_sha256"]
        or identity.get("profile") != contract["profile"]
        or identity.get("profile_sha256") != contract["profile_sha256"]
        or identity.get("profile_meta_sha256") != contract["profile_meta_sha256"]
        or manifest.get("shader_candidate_sha256") is None
        or not candidate.is_file()
        or any(p.is_symlink() for p in (candidate, *candidate.parents))
        or sha(candidate) != manifest["shader_candidate_sha256"]
    ):
        raise RuntimeError("Uber candidate does not match the exact source-camera contract")
    source_provenance = provenance.get(target)
    if source_provenance is not None and source_provenance.get("sha256") != contract["shader_sha256"]:
        raise RuntimeError("Uber source conflicts with project provenance")
    common = {
        "source_asset_path": shader_path,
        "resource_asset_path": contract["resource"],
        "source_camera_prefab_path": contract["source_camera_prefab"],
        "original_source_sha256": contract["shader_sha256"],
        "original_meta_sha256": contract["shader_meta_sha256"],
        "resource_sha256": contract["resource_sha256"],
        "resource_meta_sha256": contract["resource_meta_sha256"],
        "source_camera_prefab_sha256": contract["source_camera_prefab_sha256"],
        "source_camera_prefab_meta_sha256": contract["source_camera_prefab_meta_sha256"],
    }
    result = {
        target: {
            **common,
            "candidate_path": candidate_rel,
            "candidate_shader_sha256": manifest["shader_candidate_sha256"],
            "candidate_shader_bytes": candidate.stat().st_size,
            "_uber_candidate": True,
        }
    }
    result[target + ".meta"] = {
        **common,
        "preserved_meta_sha256": contract["shader_meta_sha256"],
        "preserved_meta_bytes": receipt["shader_meta_bytes"],
        "_meta_only": True,
    }
    includes = receipt.get("includes")
    generated = manifest.get("includes")
    if not isinstance(includes, list) or not isinstance(generated, list) or len(includes) != len(generated):
        raise RuntimeError("Uber receipt has incomplete include closure")
    for row, item in zip(includes, generated, strict=True):
        rel = PurePosixPath(recipe["include_target_prefix"]) / PurePosixPath(item["package_path"])
        candidate_path = item["candidate_path"]
        candidate_file = candidate_root(candidate_work, input_id, recipe) / candidate_path
        meta_candidate = Path(str(candidate_file) + ".meta")
        if (
            row.get("target") != rel.as_posix()
            or row.get("candidate_path") != candidate_path
            or row.get("sha256") != item.get("sha256")
            or row.get("meta_sha256") != item.get("meta_sha256")
            or not candidate_file.is_file()
            or not meta_candidate.is_file()
            or sha(candidate_file) != item["sha256"]
            or sha(meta_candidate) != item["meta_sha256"]
            or row.get("meta_target") != rel.as_posix() + ".meta"
            or row.get("guid") != parse_guid(meta_candidate)
        ):
            raise RuntimeError("Uber include row differs from stable candidate")
        result[rel.as_posix()] = {
            **row,
            "candidate_path": candidate_path,
            "candidate_sha256": item["sha256"],
            "_generated_only": True,
            "_uber_generated": True,
        }
        result[rel.as_posix() + ".meta"] = {
            **row,
            "candidate_path": candidate_path + ".meta",
            "candidate_sha256": item["meta_sha256"],
            "_generated_only": True,
            "_uber_generated": True,
            "_uber_meta": True,
        }
    return result


def merge_postprocessing_rows(bloom_rows, uber_rows):
    """Merge exact shared generated includes while retaining the legacy Bloom row."""
    merged = dict(bloom_rows)
    for path, uber in uber_rows.items():
        bloom = merged.get(path)
        if bloom is None:
            merged[path] = uber
            continue
        bloom_meta = bloom.get("_generated_meta") is True
        uber_meta = uber.get("_uber_meta") is True
        bloom_digest = bloom.get("candidate_meta_sha256") if bloom_meta else bloom.get("candidate_sha256")
        uber_digest = uber.get("candidate_sha256")
        if (
            not (bloom.get("_generated_only") or bloom.get("_generated_meta"))
            or not uber.get("_uber_generated")
            or bloom_meta != uber_meta
            or bloom_digest != uber_digest
            or bloom.get("guid") != uber.get("guid")
            or bloom.get("target") != uber.get("target")
            or bloom.get("meta_target") != uber.get("meta_target")
        ):
            raise RuntimeError("Post-processing shader batches claim unequal shared generated content: " + path)
        # Bloom's historical row schema and replay semantics remain canonical
        # for shared include paths. The independent Uber receipt still has to
        # prove identical bytes and GUID before the duplicate is collapsed.
    return merged


def bootstrap_identity(work, input_id):
    """The historical generation identity, recorded publicly in the build-entry recipe (J597)."""
    recipe = read(RECIPE / "build-entry-inputs.json")
    if recipe["schema"] != 2 or recipe["input_id"] != input_id:
        raise RuntimeError("Bootstrap identity requires accepted input")
    attempt = recipe.get("bootstrap_attempt", "")
    if not re.fullmatch(r"integration-[A-Za-z0-9._-]+", attempt):
        raise RuntimeError("Invalid bootstrap identity")
    return attempt


class CatalogIO(StageIO):
    def __init__(self, work, destination, input_id):
        super().__init__(work, destination)
        from catalog_analysis import ensure

        if read(self.work / "config/accepted-input.json")["input_id"] != input_id:
            raise RuntimeError("Catalog rebuild inputs require accepted input")
        # Audit, native inventory and reconcile run once per destination from the installation.
        self.analysis = ensure(self.work, self.project, input_id)

    def runtime_guid(self, name):
        import re
        from pathlib import PurePosixPath

        guids = read(RECIPE / "project-layout.json")["runtime_source_guids"]
        values = [guid for path, guid in guids.items() if PurePosixPath(path).name == name]
        if len(values) != 1 or not re.fullmatch("[0-9a-f]{32}", values[0] or ""):
            raise RuntimeError("Missing authored script identity: " + name)
        return values[0]

    def label(self, path):
        path = Path(path)
        return "destination/" + str(path.relative_to(self.project)) if path.is_relative_to(self.project) else super().label(path)

    def catalog(self):
        return self.analysis


def verify_outputs(io, expected, provenance, shader_overrides=None, input_id=None, postprocessing_bloom=None, postprocessing_uber=None):
    overrides = shader_override_rows(shader_overrides, input_id, expected, provenance, candidate_work=io.work)
    bloom_overrides = postprocessing_bloom_rows(postprocessing_bloom, input_id, expected, provenance, candidate_work=io.work)
    uber_overrides = postprocessing_uber_rows(postprocessing_uber, input_id, expected, provenance, candidate_work=io.work)
    if set(overrides) & set(bloom_overrides) or set(overrides) & set(uber_overrides):
        raise RuntimeError("Shader batch receipts claim the same project path")
    overrides.update(bloom_overrides)
    overrides = merge_postprocessing_rows(overrides, uber_overrides)
    expected = set(expected) | set(overrides)
    export = None
    if overrides:
        reconstruction = io.read(io.work / "config/reconstruction.json")
        projects = reconstruction.get("projects")
        if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], str):
            raise RuntimeError("Shader override verification requires the exact accepted export root")
        export = io.resolve(projects[0])
    for path, row in bloom_overrides.items():
        if row.get("_meta_only") or row.get("_generated_only") or row.get("_generated_meta"):
            continue
        source = export / row["source_asset_path"]
        source_meta = export / (row["source_asset_path"] + ".meta")
        resource = export / row["resource_asset_path"]
        resource_meta = export / (row["resource_asset_path"] + ".meta")
        camera_prefab = export / row["source_camera_prefab_path"] if "source_camera_prefab_path" in row else None
        camera_prefab_meta = Path(str(camera_prefab) + ".meta") if camera_prefab is not None else None
        camera_target = io.project / ("Assets/WholeGame/" + row["source_camera_prefab_path"].removeprefix("Assets/")) if camera_prefab is not None else None
        camera_target_meta = Path(str(camera_target) + ".meta") if camera_target is not None else None
        resource_target = io.project / ("Assets/WholeGame/" + row["resource_asset_path"].removeprefix("Assets/"))
        resource_target_meta = Path(str(resource_target) + ".meta")
        target_meta = io.project / (path + ".meta")
        if (
            not source.is_file()
            or source.is_symlink()
            or not source_meta.is_file()
            or source_meta.is_symlink()
            or not resource.is_file()
            or resource.is_symlink()
            or not io.is_file(target_meta)
            or not io.is_file(resource_target)
            or ("resource_meta_sha256" in row and (not resource_meta.is_file() or not io.is_file(resource_target_meta)))
            or (camera_prefab is not None and (not camera_prefab.is_file() or sha(camera_prefab) != row["source_camera_prefab_sha256"]))
            or (camera_prefab_meta is not None and (not camera_prefab_meta.is_file() or sha(camera_prefab_meta) != row["source_camera_prefab_meta_sha256"]))
            or (camera_target is not None and (not io.is_file(camera_target) or io.sha(camera_target) != row["source_camera_prefab_sha256"]))
            or (
                camera_target_meta is not None and (not io.is_file(camera_target_meta) or io.sha(camera_target_meta) != row["source_camera_prefab_meta_sha256"])
            )
            or sha(source) != row["original_source_sha256"]
            or sha(source_meta) != row["original_meta_sha256"]
            or sha(resource) != row["resource_sha256"]
            or io.sha(target_meta) != row["preserved_meta_sha256"]
            or io.sha(resource_target) != row["resource_sha256"]
            or (
                "resource_meta_sha256" in row
                and (sha(resource_meta) != row["resource_meta_sha256"] or io.sha(resource_target_meta) != row["resource_meta_sha256"])
            )
        ):
            raise RuntimeError("Bloom source, metadata, or serialized resource changed during replay: " + path)
    for path, row in uber_overrides.items():
        if row.get("_meta_only") or row.get("_generated_only"):
            continue
        source = export / row["source_asset_path"]
        source_meta = export / (row["source_asset_path"] + ".meta")
        resource = export / row["resource_asset_path"]
        resource_meta = export / (row["resource_asset_path"] + ".meta")
        camera = export / row["source_camera_prefab_path"]
        camera_meta = Path(str(camera) + ".meta")
        target_meta = io.project / (path + ".meta")
        resource_target = io.project / ("Assets/WholeGame/" + row["resource_asset_path"].removeprefix("Assets/"))
        resource_target_meta = Path(str(resource_target) + ".meta")
        camera_target = io.project / ("Assets/WholeGame/" + row["source_camera_prefab_path"].removeprefix("Assets/"))
        camera_target_meta = Path(str(camera_target) + ".meta")
        if (
            any(
                p.is_symlink()
                for p in (
                    source,
                    source_meta,
                    resource,
                    resource_meta,
                    camera,
                    camera_meta,
                    target_meta,
                    resource_target,
                    resource_target_meta,
                    camera_target,
                    camera_target_meta,
                )
            )
            or any(
                not p.is_file()
                for p in (
                    source,
                    source_meta,
                    resource,
                    resource_meta,
                    camera,
                    camera_meta,
                    target_meta,
                    resource_target,
                    resource_target_meta,
                    camera_target,
                    camera_target_meta,
                )
            )
            or sha(source) != row["original_source_sha256"]
            or sha(source_meta) != row["original_meta_sha256"]
            or sha(resource) != row["resource_sha256"]
            or sha(resource_meta) != row["resource_meta_sha256"]
            or sha(camera) != row["source_camera_prefab_sha256"]
            or sha(camera_meta) != row["source_camera_prefab_meta_sha256"]
            or io.sha(resource_target) != row["resource_sha256"]
            or io.sha(resource_target_meta) != row["resource_meta_sha256"]
            or io.sha(camera_target) != row["source_camera_prefab_sha256"]
            or io.sha(camera_target_meta) != row["source_camera_prefab_meta_sha256"]
            or io.sha(target_meta) != row["original_meta_sha256"]
        ):
            raise RuntimeError("Uber source/resource/camera identity changed during replay: " + path)
    for path in sorted(expected):
        target = io.project / path
        row = provenance.get(path, {})
        data = io.read_bytes(target) if io.is_file(target) else None
        if path in overrides:
            override = overrides[path]
            meta = io.project / (path + ".meta")
            if override.get("_meta_only"):
                if data is None or io.sha(target) != override["preserved_meta_sha256"] or len(data) != override["preserved_meta_bytes"]:
                    raise RuntimeError("Qualified shader override metadata differs from its exact receipt: " + path)
            elif (override.get("_generated_only") or override.get("_generated_meta")) and not override.get("_uber_generated"):
                recipe = read(RECIPE / "shader-postprocessing-bloom-candidate.json")
                from shader_postprocessing_bloom import candidate_root

                output = candidate_root(io.work, input_id, recipe)
                candidate_rel = override["candidate_meta_path"] if override.get("_generated_meta") else override["candidate_path"]
                candidate = output / candidate_rel
                expected_sha = override["candidate_meta_sha256"] if override.get("_generated_meta") else override["candidate_sha256"]
                if data is None or not candidate.is_file() or io.sha(target) != expected_sha or sha(candidate) != expected_sha:
                    raise RuntimeError("Bloom generated include differs from its exact candidate: " + path)
            elif override.get("_bloom_candidate"):
                recipe = read(RECIPE / "shader-postprocessing-bloom-candidate.json")
                from shader_postprocessing_bloom import candidate_root

                output = candidate_root(io.work, input_id, recipe)
                candidate = output / override["candidate_path"]
                if (
                    data is None
                    or not candidate.is_file()
                    or io.sha(target) != override["candidate_shader_sha256"]
                    or sha(candidate) != override["candidate_shader_sha256"]
                ):
                    raise RuntimeError("Bloom replacement shader differs from its exact candidate: " + path)
            elif override.get("_uber_candidate"):
                recipe = read(RECIPE / "shader-postprocessing-uber-candidate.json")
                from shader_postprocessing_uber import candidate_root

                candidate = candidate_root(io.work, input_id, recipe) / override["candidate_path"]
                if (
                    data is None
                    or not candidate.is_file()
                    or io.sha(target) != override["candidate_shader_sha256"]
                    or sha(candidate) != override["candidate_shader_sha256"]
                ):
                    raise RuntimeError("Uber replacement shader differs from its exact candidate: " + path)
            elif override.get("_uber_generated"):
                recipe = read(RECIPE / "shader-postprocessing-uber-candidate.json")
                from shader_postprocessing_uber import candidate_root

                candidate = candidate_root(io.work, input_id, recipe) / override["candidate_path"]
                if data is None or not candidate.is_file() or io.sha(target) != override["candidate_sha256"] or sha(candidate) != override["candidate_sha256"]:
                    raise RuntimeError("Uber generated include differs from its exact candidate: " + path)
            else:
                source = export / override["source_asset_path"]
                source_meta = export / (override["source_asset_path"] + ".meta")
                if (
                    source.is_symlink()
                    or source_meta.is_symlink()
                    or not source.is_file()
                    or not source_meta.is_file()
                    or io.sha(source) != override["original_source_sha256"]
                    or io.sha(source_meta) != override["original_meta_sha256"]
                    or data is None
                    or io.sha(target) != override["candidate_shader_sha256"]
                    or len(data) != override["candidate_shader_bytes"]
                    or not io.is_file(meta)
                    or io.sha(meta) != override["preserved_meta_sha256"]
                ):
                    raise RuntimeError("Qualified shader override does not match its exact builder receipt: " + path)
        elif data is None or io.sha(target) != row["sha256"] or len(data) != row["size"]:
            raise RuntimeError("Rebuilt catalog output differs from provenance: " + path)
    io.flush()


def catalog_closure(destination, work, input_id, expected, provenance):
    from whole_catalog import prepare_integration

    config = destination / ".rebuild/composition/scene-probe-build.json"
    if not config.is_file():
        raise RuntimeError("Catalog closure requires destination composition config from R2")
    attempt = bootstrap_identity(work, input_id)
    io = CatalogIO(work, destination, input_id)
    override_receipt = prepare_integration(io, attempt=attempt)
    bloom_receipt = read_postprocessing_bloom_receipt(destination, input_id, work, io=io)
    uber_receipt = read_postprocessing_uber_receipt(destination, input_id, work, io=io)
    verify_outputs(
        io, expected, provenance, shader_overrides=override_receipt, input_id=input_id, postprocessing_bloom=bloom_receipt, postprocessing_uber=uber_receipt
    )
    io.write(destination / ".rebuild/catalog-closure-complete.json", dict(input_id=input_id))
    io.flush()


def dependencies(destination, work, input_id, expected, provenance):
    from composition_migration import stage_missing_sources

    marker = destination / ".rebuild/catalog-closure-complete.json"
    if not marker.is_file() or read(marker)["input_id"] != input_id:
        raise RuntimeError("Run catalog-closure after composition before dependencies")
    from rebuild import STEPS

    io = CatalogIO(work, destination, input_id)
    # Required build entries that R5–R8 builders own cannot exist yet; validate-bindings checks them.
    built = {function for name in ("catalog-closure", "dependencies") for function in STEPS[name].evidence}
    io.deferred = frozenset(
        path
        for path, row in provenance.items()
        if row.get("producer") == "repo-builder" and row.get("evidence") and not any(item.get("function") in built for item in row["evidence"])
    )
    config = io.output(io.work / "scene-probe-build.json")
    if not config.is_file():
        raise RuntimeError("Dependencies require destination composition config from R2")
    stage_missing_sources(io)
    override_receipt = read_shader_override_receipt(destination, input_id, work)
    bloom_receipt = read_postprocessing_bloom_receipt(destination, input_id, work, io=io)
    uber_receipt = read_postprocessing_uber_receipt(destination, input_id, work, io=io)
    verify_outputs(
        io, expected, provenance, shader_overrides=override_receipt, input_id=input_id, postprocessing_bloom=bloom_receipt, postprocessing_uber=uber_receipt
    )
    io.write(destination / ".rebuild/dependencies-complete.json", dict(input_id=input_id))
    io.flush()
