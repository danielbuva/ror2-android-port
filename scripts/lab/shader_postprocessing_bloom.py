"""Input-bound recovery of Unity Post Processing 2.3.0's Bloom pass contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

from common import RECIPE, ROOT, WORK, read, sha

SCHEMA = "whole-catalog-postprocessing-bloom-candidate-r2"
ACTIVATION_SCHEMA = "whole-catalog-postprocessing-bloom-activation-r1"
RECEIPT_SCHEMA = "whole-catalog-postprocessing-bloom-receipt-r2"
MARKER_SCHEMA = "whole-catalog-postprocessing-bloom-marker-r2"
SHADER_NAME = "Hidden/PostProcessing/Bloom"
GUID = re.compile(r"(?m)^guid: ([0-9a-f]{32})\r?$")
BLOOM_REF = re.compile(r"(?m)^\s+bloom: \{fileID: [0-9-]+, guid: ([0-9a-f]{32}), type: [0-9]+\}\r?$")
INCLUDE = re.compile(r'(?m)^\s*#include\s+["<]([^">]+)[">]')
PASS_LINE = re.compile(r"(?m)^\s*Pass\s*$")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise RuntimeError("Unsafe Bloom candidate relative path: " + value)
    return path


def load_recipe(input_id: str) -> dict:
    recipe = read(RECIPE / "shader-postprocessing-bloom-candidate.json")
    if (
        recipe.get("schema") != SCHEMA
        or recipe.get("input_id") != input_id
        or recipe.get("package_version") != "2.3.0"
        or recipe.get("shader_name") != SHADER_NAME
        or recipe.get("enabled_by_default") is not False
        or recipe.get("companion_copy_std", {}).get("shader_name") != "Hidden/PostProcessing/CopyStd"
    ):
        raise RuntimeError("Bloom candidate recipe is not pinned to this accepted input and package")
    members = recipe.get("expected_members")
    if not isinstance(members, list) or not members or len(members) != len({row.get("shader") for row in members}):
        raise RuntimeError("Bloom candidate recipe has missing or duplicate source membership")
    if not isinstance(recipe.get("expected_package_include_sha256"), dict):
        raise RuntimeError("Bloom candidate recipe lacks its exact HLSL include closure")
    return recipe


def parse_guid(meta_bytes: bytes) -> str:
    matches = GUID.findall(meta_bytes.decode("utf-8"))
    if len(matches) != 1:
        raise RuntimeError("Bloom shader metadata must contain exactly one GUID")
    return matches[0]


def validate_pass_contract(shader: bytes, renderer: bytes, recipe: dict) -> None:
    text = shader.decode("utf-8")
    if not re.search(r'^\s*Shader\s+"Hidden/PostProcessing/Bloom"\s*$', text, re.M):
        raise RuntimeError("Official Bloom shader name changed")
    names = tuple(re.findall(r"(?m)^\s*//\s*[0-8]:\s*(.*?)\s*$", text))
    pass_count = len(re.findall(r"(?m)^\s*Pass\s*$", text))
    if names != tuple(recipe["pass_names"]) or pass_count != 9:
        raise RuntimeError("Bloom shader no longer has the exact nine-pass renderer contract")
    source = renderer.decode("utf-8")
    enum_match = re.search(r"enum Pass\s*\{([^}]+)\}", source, re.S)
    expected = (
        "Prefilter13",
        "Prefilter4",
        "Downsample13",
        "Downsample4",
        "UpsampleTent",
        "UpsampleBox",
        "DebugOverlayThreshold",
        "DebugOverlayTent",
        "DebugOverlayBox",
    )
    if enum_match is None or tuple(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", enum_match.group(1))) != expected:
        raise RuntimeError("Bloom renderer enum no longer matches the shader's ordered passes")
    if recipe.get("runtime_selected_passes") != [1, 3, 5]:
        raise RuntimeError("Bloom recipe fast-mode call contract changed")


def archive_files(archive_path: Path, recipe: dict) -> dict[str, bytes]:
    if archive_path.is_symlink() or not archive_path.is_file() or sha(archive_path) != recipe["package_sha256"]:
        raise RuntimeError("Pinned local Unity Post Processing package is absent or changed")
    files: dict[str, bytes] = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())
        for name in names:
            if name.startswith("package/PostProcessing/Shaders/") and name.endswith((".hlsl", ".meta", ".shader")):
                member = archive.getmember(name)
                stream = archive.extractfile(member)
                if stream is not None:
                    files[name.removeprefix("package/PostProcessing/Shaders/")] = stream.read()
        expected = {
            "package/package.json": None,
            "package/LICENSE.md": recipe["package_license_sha256"],
            "package/PostProcessing/Runtime/Effects/Bloom.cs": recipe["package_bloom_renderer_sha256"],
            "package/PostProcessing/Shaders/Builtins/Bloom.shader": recipe["package_bloom_shader_sha256"],
            "package/PostProcessing/Shaders/Builtins/CopyStd.shader": recipe["package_copy_std_shader_sha256"],
        }
        for name, expected_sha in expected.items():
            stream = archive.extractfile(name)
            if stream is None:
                raise RuntimeError("Pinned Post Processing package member is missing: " + name)
            data = stream.read()
            if expected_sha is not None and digest_bytes(data) != expected_sha:
                raise RuntimeError("Pinned Post Processing package member changed: " + name)
            if name.endswith("package.json"):
                package = json.loads(data)
                if package.get("version") != recipe["package_version"]:
                    raise RuntimeError("Pinned Post Processing package version changed")
        renderer = archive.extractfile("package/PostProcessing/Runtime/Effects/Bloom.cs")
        shader = archive.extractfile("package/PostProcessing/Shaders/Builtins/Bloom.shader")
        copy_std = archive.extractfile("package/PostProcessing/Shaders/Builtins/CopyStd.shader")
        if renderer is None or shader is None or copy_std is None:
            raise RuntimeError("Pinned package lacks its Bloom source pair")
        files["__BloomRenderer.cs"] = renderer.read()
        files["__Bloom.shader"] = shader.read()
        files["__CopyStd.shader"] = copy_std.read()
    expected_closure = recipe["expected_package_include_sha256"]
    closure = include_closure(files, "Builtins/Bloom.shader")
    closure_names = {name for name in closure if name.endswith(".hlsl")}
    closure_names |= {name + ".meta" for name in closure_names}
    if closure_names != set(expected_closure):
        raise RuntimeError("Pinned Bloom transitive HLSL closure changed")
    for name, expected_sha in expected_closure.items():
        if name not in files or digest_bytes(files[name]) != expected_sha:
            raise RuntimeError("Pinned Bloom include source or metadata changed: " + name)
    return files


def include_closure(files: dict[str, bytes], source_name: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    pending = [source_name]
    while pending:
        name = pending.pop()
        if name in result:
            continue
        source = files.get(name)
        if source is None:
            raise RuntimeError("Pinned Bloom include is missing: " + name)
        result[name] = source
        for included in INCLUDE.findall(source.decode("utf-8")):
            if included.startswith("/") or "\\" in included:
                raise RuntimeError("Bloom include path is absolute or malformed")
            parts = list(PurePosixPath(name).parent.parts)
            for part in PurePosixPath(included).parts:
                if part == "..":
                    if not parts:
                        raise RuntimeError("Bloom include escapes the package shader root")
                    parts.pop()
                elif part not in ("", "."):
                    parts.append(part)
            dependency = PurePosixPath(*parts).as_posix()
            if dependency.endswith(".hlsl"):
                pending.append(dependency)
    return result


def validate_export_members(export: Path, mapped: dict[str, str], recipe: dict) -> list[dict]:
    members = []
    expected_paths = set()
    for expected in recipe["expected_members"]:
        source_path = safe_relative(expected["shader"]).as_posix()
        resource_path = safe_relative(expected["resource"]).as_posix()
        expected_paths.add(source_path)
        shader = export / source_path
        meta = export / (source_path + ".meta")
        resource = export / resource_path
        if any(path.is_symlink() or not path.is_file() for path in (shader, meta, resource)):
            raise RuntimeError("Pinned Bloom source, metadata, or resource is absent or linked: " + source_path)
        shader_bytes, meta_bytes, resource_bytes = shader.read_bytes(), meta.read_bytes(), resource.read_bytes()
        if (
            digest_bytes(shader_bytes) != expected["shader_sha256"]
            or digest_bytes(meta_bytes) != expected["meta_sha256"]
            or digest_bytes(resource_bytes) != expected["resource_sha256"]
            or parse_guid(meta_bytes) != expected["guid"]
        ):
            raise RuntimeError("Bloom source identity or hash differs from accepted recipe: " + source_path)
        resource_text = resource_bytes.decode("utf-8")
        if BLOOM_REF.findall(resource_text) != [expected["guid"]]:
            raise RuntimeError("PostProcessResources bloom reference does not match exact shader GUID: " + resource_path)
        if mapped.get(source_path) != "Assets/WholeGame/" + source_path.removeprefix("Assets/"):
            raise RuntimeError("Bloom source does not map to its exact WholeGame path: " + source_path)
        if mapped.get(resource_path) != "Assets/WholeGame/" + resource_path.removeprefix("Assets/"):
            raise RuntimeError("Bloom resource does not map to its exact WholeGame path: " + resource_path)
        if shader_bytes.count(('Shader "' + SHADER_NAME + '"').encode()) != 1 or len(PASS_LINE.findall(shader_bytes.decode("utf-8"))) != 1:
            raise RuntimeError("Refusing to replace a non-dummy Bloom shader: " + source_path)
        members.append({**expected, "source_bytes": shader_bytes, "meta_bytes": meta_bytes, "resource_bytes": resource_bytes})
    actual = {path for path in mapped if PurePosixPath(path).name.startswith("Hidden_PostProcessing_Bloom") and path.endswith(".shader")}
    if actual != expected_paths:
        raise RuntimeError("Mapped Bloom shader membership differs from the exact accepted recipe")
    return members


def candidate_root(work: Path, input_id: str, recipe: dict) -> Path:
    relative = safe_relative(recipe["stable_output"].format(input_id=input_id))
    if relative.parts[0] != "generated-shader-candidates":
        raise RuntimeError("Bloom output root is not the pinned generated-shader directory")
    target = work.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(work.resolve()):
        raise RuntimeError("Bloom candidate output escapes work/")
    if any(path.is_symlink() for path in (target, *target.parents) if path.is_relative_to(work)):
        raise RuntimeError("Bloom candidate output contains a symlink")
    return target


def validate_copy_std_member(export: Path, mapped: dict[str, str], recipe: dict) -> dict:
    expected = recipe["companion_copy_std"]
    source_path = safe_relative(expected["shader"]).as_posix()
    resource_path = safe_relative(expected["resource"]).as_posix()
    camera = expected["source_camera_prefab"]
    camera_path = safe_relative(camera["path"]).as_posix()
    shader, meta, resource = export / source_path, export / (source_path + ".meta"), export / resource_path
    resource_meta = export / (resource_path + ".meta")
    prefab, prefab_meta = export / camera_path, export / (camera_path + ".meta")
    inputs = (shader, meta, resource, resource_meta, prefab, prefab_meta)
    if any(path.is_symlink() or not path.is_file() for path in inputs):
        raise RuntimeError("Exact source-camera CopyStd source, metadata, or resource is absent or linked")
    shader_bytes, meta_bytes, resource_bytes = shader.read_bytes(), meta.read_bytes(), resource.read_bytes()
    resource_meta_bytes, prefab_bytes, prefab_meta_bytes = resource_meta.read_bytes(), prefab.read_bytes(), prefab_meta.read_bytes()
    if (
        digest_bytes(shader_bytes) != expected["shader_sha256"]
        or digest_bytes(meta_bytes) != expected["meta_sha256"]
        or digest_bytes(resource_bytes) != expected["resource_sha256"]
        or parse_guid(meta_bytes) != expected["guid"]
        or digest_bytes(resource_meta_bytes) != expected["resource_meta_sha256"]
        or parse_guid(resource_meta_bytes) != expected["resource_asset_guid"]
        or digest_bytes(prefab_bytes) != camera["sha256"]
        or digest_bytes(prefab_meta_bytes) != camera["meta_sha256"]
    ):
        raise RuntimeError("Exact source-camera CopyStd input identity changed")
    reference = re.compile(r"(?m)^\s*copyStd: \{fileID: [0-9-]+, guid: ([0-9a-f]{32}), type: [0-9]+\}\r?$")
    if reference.findall(resource_bytes.decode("utf-8")) != [expected["guid"]]:
        raise RuntimeError("Source camera PostProcessResources copyStd reference changed")
    resource_reference = re.compile(r"(?m)^\s*m_Resources: \{fileID: [0-9-]+, guid: ([0-9a-f]{32}), type: [0-9]+\}\r?$")
    stop_nan = re.compile(r"(?m)^\s*stopNaNPropagation: ([0-9]+)\r?$")
    if (
        resource_reference.findall(prefab_bytes.decode("utf-8")) != [camera["resources_guid"]]
        or camera["resources_guid"] != expected["resource_asset_guid"]
        or stop_nan.findall(prefab_bytes.decode("utf-8")) != [str(camera["stopNaNPropagation"])]
    ):
        raise RuntimeError("Pinned source-camera prefab no longer selects CopyStd pass 1 through PostProcessResources_53")
    if (
        mapped.get(source_path) != "Assets/WholeGame/" + source_path.removeprefix("Assets/")
        or mapped.get(resource_path) != "Assets/WholeGame/" + resource_path.removeprefix("Assets/")
        or mapped.get(camera_path) != "Assets/WholeGame/" + camera_path.removeprefix("Assets/")
    ):
        raise RuntimeError("Exact source-camera CopyStd input does not map to its pinned WholeGame path")
    if shader_bytes.count(('Shader "' + expected["shader_name"] + '"').encode()) != 1 or len(PASS_LINE.findall(shader_bytes.decode("utf-8"))) != 1:
        raise RuntimeError("Exact source-camera CopyStd shader is not the expected one-pass placeholder")
    return {
        **expected,
        "source_camera_prefab_sha256": camera["sha256"],
        "source_camera_prefab_meta_sha256": camera["meta_sha256"],
        "resource_meta_sha256": expected["resource_meta_sha256"],
        "source_bytes": shader_bytes,
        "meta_bytes": meta_bytes,
        "resource_bytes": resource_bytes,
    }


def validate_copy_std_contract(shader: bytes, recipe: dict) -> None:
    expected = recipe["companion_copy_std"]
    text = shader.decode("utf-8")
    if not re.search(r'^\s*Shader\s+"' + re.escape(expected["shader_name"]) + r'"\s*$', text, re.M):
        raise RuntimeError("Official CopyStd shader name changed")
    pass_names = tuple(re.findall(r"(?m)^\s*//\s*[01]\s*-\s*(.*?)\s*$", text))
    if (
        len(PASS_LINE.findall(text)) != 2
        or pass_names != tuple(expected.get("runtime_passes", ()))
        or expected.get("selected_pass") != 1
        or expected.get("runtime_passes") != ["Copy", "Copy + NaN killer"]
    ):
        raise RuntimeError("Official CopyStd shader no longer satisfies its exact two-pass source-camera contract")


def require_known_stage_preimage(current_sha: str, source_sha: str, candidate_sha: str, path: str) -> None:
    if current_sha not in (source_sha, candidate_sha):
        raise RuntimeError("Refusing to replace an unknown staged shader body: " + path)


def generate_candidate(work: Path, export: Path, mapped: dict[str, str], input_id: str, *, allow_create=True) -> tuple[Path, dict]:
    recipe = load_recipe(input_id)
    package = work / Path(recipe["package_archive"]).relative_to("work")
    files = archive_files(package, recipe)
    members = validate_export_members(export, mapped, recipe)
    copy_std_member = validate_copy_std_member(export, mapped, recipe)
    official_shader = files["__Bloom.shader"]
    renderer = files["__BloomRenderer.cs"]
    validate_pass_contract(official_shader, renderer, recipe)
    shader_text = official_shader.decode("utf-8")
    for include in ("StdLib", "Colors", "Sampling"):
        shader_text = shader_text.replace(f'"../{include}.hlsl"', f'"PostProcessing/{include}.hlsl"')
    candidate_shader = shader_text.encode("utf-8")
    validate_pass_contract(candidate_shader, renderer, recipe)
    official_copy_std = files["__CopyStd.shader"]
    validate_copy_std_contract(official_copy_std, recipe)
    output = candidate_root(work, input_id, recipe)
    output_files: dict[str, bytes] = {}
    rows = []
    for member in members:
        source_path = member["shader"]
        name = PurePosixPath(source_path).name
        relative = PurePosixPath("sources") / name
        output_files[relative.as_posix()] = candidate_shader
        rows.append(
            {
                "source_asset_path": source_path,
                "resource_asset_path": member["resource"],
                "guid": member["guid"],
                "original_source_sha256": member["shader_sha256"],
                "original_meta_sha256": member["meta_sha256"],
                "resource_sha256": member["resource_sha256"],
                "candidate_path": relative.as_posix(),
                "candidate_shader_sha256": digest_bytes(candidate_shader),
            }
        )
    include_rows = []
    copy_std = recipe["companion_copy_std"]
    copy_std_relative = safe_relative(copy_std["candidate_path"])
    output_files[copy_std_relative.as_posix()] = official_copy_std
    copy_std_row = {
        **{key: value for key, value in copy_std_member.items() if key not in ("source_bytes", "meta_bytes", "resource_bytes")},
        "candidate_path": copy_std_relative.as_posix(),
        "candidate_sha256": digest_bytes(official_copy_std),
        "package_shader_sha256": digest_bytes(official_copy_std),
    }
    closure = include_closure(files, "Builtins/Bloom.shader")
    for name in sorted(closure):
        if not name.endswith(".hlsl"):
            continue
        relative = PurePosixPath("includes") / PurePosixPath(name)
        relative_meta = PurePosixPath(str(relative) + ".meta")
        output_files[relative.as_posix()] = closure[name]
        output_files[relative_meta.as_posix()] = files[name + ".meta"]
        include_rows.append(
            {
                "package_path": name,
                "candidate_path": relative.as_posix(),
                "candidate_meta_path": relative_meta.as_posix(),
                "candidate_sha256": digest_bytes(closure[name]),
                "candidate_meta_sha256": digest_bytes(files[name + ".meta"]),
                "guid": parse_guid(files[name + ".meta"]),
            }
        )
    generator_path = Path(__file__).resolve()
    recipe_path = RECIPE / "shader-postprocessing-bloom-candidate.json"
    manifest = {
        "schema": SCHEMA,
        "input_id": input_id,
        "recipe_sha256": sha(recipe_path),
        "generator_sha256": sha(generator_path),
        "package_sha256": recipe["package_sha256"],
        "pass_count": 9,
        "runtime_selected_passes": [1, 3, 5],
        "rows": rows,
        "copy_std": copy_std_row,
        "includes": include_rows,
        "unity_compiled": False,
        "android_accepted": False,
        "visual_parity_proven": False,
    }
    output_files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise RuntimeError("Bloom candidate output is not a regular directory")
        actual = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
        if actual != set(output_files) or any(path.is_symlink() for path in output.rglob("*")):
            raise RuntimeError("Bloom candidate output contains stale or unexpected files")
        for relative, data in output_files.items():
            if (output / relative).read_bytes() != data:
                raise RuntimeError("Existing Bloom candidate differs from deterministic output: " + relative)
    else:
        if not allow_create:
            raise RuntimeError("Isolated replay requires the generator-owned Bloom candidate; live work inputs stay read-only")
        output.mkdir(parents=True)
        for relative, data in output_files.items():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return output, manifest


def read_activation(work: Path, input_id: str) -> dict | None:
    path = work / "config/postprocessing-bloom.json"
    if path.is_symlink():
        raise RuntimeError("Bloom activation may not be a symlink")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 4096:
        raise RuntimeError("Bloom activation is not a bounded regular file")
    data = read(path)
    if (
        set(data) != {"schema", "input_id", "enabled"}
        or data.get("schema") != ACTIVATION_SCHEMA
        or data.get("input_id") != input_id
        or type(data.get("enabled")) is not bool
    ):
        raise RuntimeError("Bloom activation has an unknown schema or accepted input")
    return {**data, "sha256": sha(path)}


def check_staging_activation(io, input_id: str) -> dict | None:
    """Refuse disabling an existing batch before any catalog imports write."""
    activation = read_activation(io.work, input_id)
    marker_path = io.project / ".rebuild/postprocessing-bloom.json"
    if activation is None or activation["enabled"] is False:
        if marker_path.is_symlink() or io.is_file(marker_path):
            raise RuntimeError("Destination has a prior Bloom receipt; rebuild it cleanly before disabling the Bloom batch")
        return None
    return activation


def stage(io, *, export: Path, mapped: dict[str, str], owners: dict[str, str], destination: Path, input_id: str) -> dict | None:
    """Stage Bloom candidates and a separate replay receipt during whole-catalog integration."""
    activation = check_staging_activation(io, input_id)
    if activation is None:
        return None
    marker_path = io.project / ".rebuild/postprocessing-bloom.json"
    recipe = load_recipe(input_id)
    output, manifest = generate_candidate(io.work, export, mapped, input_id, allow_create=not io.rebuilding)
    prepared = []
    rows = []
    for generated, recipe_row in zip(manifest["rows"], recipe["expected_members"], strict=True):
        source_path = generated["source_asset_path"]
        target_relative = mapped[source_path]
        target = io.project / target_relative
        meta_target = Path(str(target) + ".meta")
        resource_target = io.project / mapped[generated["resource_asset_path"]]
        require_known_stage_preimage(io.sha(target), generated["original_source_sha256"], generated["candidate_shader_sha256"], target_relative)
        if io.sha(meta_target) != generated["original_meta_sha256"] or io.sha(resource_target) != generated["resource_sha256"]:
            raise RuntimeError("Bloom metadata/resource changed before shader staging: " + source_path)
        candidate_path = output / generated["candidate_path"]
        prepared.append((target, candidate_path.read_bytes(), meta_target, generated["original_meta_sha256"], resource_target, generated["resource_sha256"]))
        rows.append(
            {
                **generated,
                "target": target_relative,
                "preserved_meta_sha256": generated["original_meta_sha256"],
                "preserved_meta_bytes": len(io.read_bytes(meta_target)),
            }
        )
    copy_std = manifest["copy_std"]
    copy_target = mapped[copy_std["shader"]]
    copy_meta_target = io.project / (copy_target + ".meta")
    copy_resource_target = io.project / mapped[copy_std["resource"]]
    copy_resource_meta_target = Path(str(copy_resource_target) + ".meta")
    require_known_stage_preimage(io.sha(io.project / copy_target), copy_std["shader_sha256"], copy_std["candidate_sha256"], copy_target)
    if (
        io.sha(copy_meta_target) != copy_std["meta_sha256"]
        or io.sha(copy_resource_target) != copy_std["resource_sha256"]
        or io.sha(copy_resource_meta_target) != copy_std["resource_meta_sha256"]
    ):
        raise RuntimeError("CopyStd metadata/resource changed before source-camera companion staging")
    copy_candidate = output / copy_std["candidate_path"]
    prepared.append(
        (
            io.project / copy_target,
            copy_candidate.read_bytes(),
            copy_meta_target,
            copy_std["meta_sha256"],
            copy_resource_target,
            copy_std["resource_sha256"],
        )
    )
    copy_std_receipt = {
        **copy_std,
        "target": copy_target,
        "preserved_meta_sha256": copy_std["meta_sha256"],
        "preserved_meta_bytes": len(io.read_bytes(copy_meta_target)),
    }
    include_rows = []
    for include in manifest["includes"]:
        candidate = output / include["candidate_path"]
        candidate_meta = output / include["candidate_meta_path"]
        target_relative = recipe["include_target_prefix"] + PurePosixPath(include["candidate_path"]).relative_to("includes").as_posix()
        meta_relative = target_relative + ".meta"
        target = io.project / target_relative
        meta_target = io.project / meta_relative
        guid = include["guid"]
        prior_owner = owners.get(guid)
        if prior_owner is not None and prior_owner != target_relative:
            raise RuntimeError("Official Bloom include GUID collides with another imported asset")
        if io.is_file(target) or io.is_file(meta_target):
            if (
                not io.is_file(target)
                or not io.is_file(meta_target)
                or io.sha(target) != include["candidate_sha256"]
                or io.sha(meta_target) != include["candidate_meta_sha256"]
            ):
                raise RuntimeError("Existing Bloom include asset differs from its pinned package")
        prepared.append((target, candidate.read_bytes(), meta_target, None, None, None))
        prepared.append((meta_target, candidate_meta.read_bytes(), None, None, None, None))
        owners[guid] = target_relative
        include_rows.append(
            {
                "target": target_relative,
                "meta_target": meta_relative,
                "candidate_path": include["candidate_path"],
                "candidate_meta_path": include["candidate_meta_path"],
                "candidate_sha256": include["candidate_sha256"],
                "candidate_meta_sha256": include["candidate_meta_sha256"],
                "guid": guid,
            }
        )
    for target, data, meta_target, meta_sha, resource_target, resource_sha in prepared:
        if meta_sha is not None and io.sha(meta_target) != meta_sha:
            raise RuntimeError("Bloom source metadata changed during staging")
        io.apply(target, data=data)
        if resource_target is not None and io.sha(resource_target) != resource_sha:
            raise RuntimeError("Bloom staging changed its serialized PostProcessResources asset")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "input_id": input_id,
        "activation_path": "work/config/postprocessing-bloom.json",
        "activation_sha256": activation["sha256"],
        "recipe_sha256": sha(RECIPE / "shader-postprocessing-bloom-candidate.json"),
        "generator_sha256": sha(Path(__file__).resolve()),
        "candidate_manifest_path": "work/" + output.relative_to(io.work).as_posix() + "/manifest.json",
        "candidate_manifest_sha256": sha(output / "manifest.json"),
        "rows": rows,
        "copy_std": copy_std_receipt,
        "includes": include_rows,
        "unity_compiled": False,
        "android_accepted": False,
        "visual_parity_proven": False,
    }
    receipt_path = destination / "postprocessing-bloom-receipt.json"
    io.write(receipt_path, receipt)
    mirror = io.project / ".rebuild/postprocessing-bloom-receipt.json"
    io.write(mirror, receipt)
    io.write(
        marker_path,
        {
            "schema": MARKER_SCHEMA,
            "input_id": input_id,
            "receipt_path": mirror.relative_to(io.project).as_posix(),
            "receipt_sha256": io.sha(mirror),
            "activation_path": "work/config/postprocessing-bloom.json",
            "activation_sha256": activation["sha256"],
        },
    )
    return {**receipt, "path": io.label(receipt_path), "sha256": io.sha(receipt_path)}
