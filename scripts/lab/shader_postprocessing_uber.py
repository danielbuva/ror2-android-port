"""Generate a source-camera-bound Unity Post Processing Uber candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "recipe/shader-postprocessing-uber-candidate.json"
INCLUDE = re.compile(r'(?m)^\s*#include\s+["<]([^">]+)[">]')
PASS = re.compile(r"(?m)^\s*Pass\s*$")
SCHEMA = "whole-catalog-postprocessing-uber-candidate-r1"
RECEIPT_SCHEMA = "whole-catalog-postprocessing-uber-receipt-r1"
MARKER_SCHEMA = "whole-catalog-postprocessing-uber-marker-r1"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise RuntimeError("Unsafe Uber candidate path")
    return path


def parse_guid(path: Path) -> str:
    matches = re.findall(r"(?m)^guid: ([0-9a-f]{32})$", path.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one source asset GUID")
    return matches[0]


def validate_source_join(export: Path, recipe: dict) -> dict:
    contract = recipe["camera_contract"]
    paths = {key: export / safe_path(contract[key]) for key in ("source_camera_prefab", "resource", "shader", "profile")}
    metas = {key: Path(str(paths[key]) + ".meta") for key in paths}
    expected = {
        "source_camera_prefab": contract["source_camera_prefab_sha256"],
        "resource": contract["resource_sha256"],
        "shader": contract["shader_sha256"],
        "profile": contract["profile_sha256"],
    }
    expected_meta = {
        "source_camera_prefab": contract["source_camera_prefab_meta_sha256"],
        "resource": contract["resource_meta_sha256"],
        "shader": contract["shader_meta_sha256"],
        "profile": contract["profile_meta_sha256"],
    }
    if any(not p.is_file() or p.is_symlink() or digest(p) != expected[k] for k, p in paths.items()):
        raise RuntimeError("Uber source camera/profile/resource input drift")
    if any(not p.is_file() or p.is_symlink() or digest(p) != expected_meta[k] for k, p in metas.items()):
        raise RuntimeError("Uber source metadata drift")
    if parse_guid(metas["shader"]) != contract["shader_guid"] or parse_guid(metas["resource"]) != contract["resource_asset_guid"]:
        raise RuntimeError("Uber shader/resource GUID changed")
    resource_text = paths["resource"].read_text(encoding="utf-8")
    prefab_text = paths["source_camera_prefab"].read_text(encoding="utf-8")
    profile_text = paths["profile"].read_text(encoding="utf-8")
    field = re.compile(r"(?m)^\s*uber: \{fileID: [0-9-]+, guid: ([0-9a-f]{32}), type: [0-9]+\}$")
    resource_guid = re.compile(r"(?m)^\s*m_Resources: \{fileID: [0-9-]+, guid: ([0-9a-f]{32}), type: [0-9]+\}$")
    stop_nan = re.compile(r"(?m)^\s*stopNaNPropagation: ([0-9]+)$")
    if (
        field.findall(resource_text) != [contract["shader_guid"]]
        or resource_guid.findall(prefab_text) != [contract["resources_guid"]]
        or stop_nan.findall(prefab_text) != [str(contract["stopNaNPropagation"])]
    ):
        raise RuntimeError("Main Camera does not select the exact PostProcessResources.uber shader")
    settings = {}
    for block in re.split(r"(?=--- !u!114)", profile_text):
        name = re.search(r"(?m)^  m_Name: (.+)$", block)
        active = re.search(r"(?m)^  active: ([01])$", block)
        enabled = re.search(r"(?m)^  enabled:\n    overrideState: ([01])\n    value: ([01])$", block)
        if name and active and enabled:
            settings[name.group(1)] = (active.group(1) == "1", enabled.group(1) == "1", enabled.group(2) == "1")
    required = {
        "Bloom": (True, True, True),
        "ColorGrading": (True, True, False),
        "AutoExposure": (True, True, False),
    }
    if any(settings.get(key) != value for key, value in required.items()):
        raise RuntimeError("Source run profile no longer has the active Bloom / disabled grading and exposure contract")
    return {**contract, "shader_meta_guid": parse_guid(metas["shader"]), "resource_meta_guid": parse_guid(metas["resource"])}


def archive_files(archive: Path, recipe: dict) -> dict[str, bytes]:
    if not archive.is_file() or archive.is_symlink() or digest(archive) != recipe["package_sha256"]:
        raise RuntimeError("Pinned local Post Processing archive is absent or changed")
    files = {}
    with tarfile.open(archive, "r:gz") as tar:
        package = json.load(tar.extractfile("package/package.json"))
        license_bytes = tar.extractfile("package/LICENSE.md").read()
        if package.get("version") != recipe["package_version"] or package.get("repository", {}).get("revision") != recipe["package_repository_revision"]:
            raise RuntimeError("Pinned Post Processing package revision changed")
        if digest_bytes(license_bytes) != recipe["package_license_sha256"]:
            raise RuntimeError("Pinned Post Processing license changed")
        for member in tar.getmembers():
            prefix = "package/PostProcessing/Shaders/"
            if member.name.startswith(prefix) and member.name.endswith((".hlsl", ".meta", ".shader", ".compute")):
                stream = tar.extractfile(member)
                if stream:
                    files[member.name[len(prefix) :]] = stream.read()
    source = files.get("Builtins/Uber.shader")
    if source is None or digest_bytes(source) != recipe["package_uber_shader_sha256"]:
        raise RuntimeError("Pinned official Uber shader source changed")
    return files


def include_closure(files: dict[str, bytes], source_path: str) -> dict[str, bytes]:
    result, pending = {}, [source_path]
    while pending:
        name = pending.pop()
        if name in result:
            continue
        data = files.get(name)
        if data is None:
            raise RuntimeError("Missing transitive Uber include: " + name)
        result[name] = data
        for include in INCLUDE.findall(data.decode("utf-8")):
            parts = list(PurePosixPath(name).parent.parts)
            for component in PurePosixPath(include).parts:
                if component == "..":
                    if not parts:
                        raise RuntimeError("Uber include escapes shader root")
                    parts.pop()
                elif component not in ("", "."):
                    parts.append(component)
            child = PurePosixPath(*parts).as_posix()
            if child.endswith(".hlsl"):
                pending.append(child)
    return result


def rewrite_includes(shader: bytes, closure: dict[str, bytes], prefix: str = "PostProcessing/") -> bytes:
    text = shader.decode("utf-8")
    for path in closure:
        if path.endswith(".hlsl"):
            parts = PurePosixPath(path).parts
            replacement = prefix + "/".join(parts)
            text = text.replace(f'"../{PurePosixPath(path).name}"', f'"{replacement}"')
            text = text.replace(f'"{PurePosixPath(path).name}"', f'"{replacement}"')
    return text.encode("utf-8")


def validate_programs(export: Path, files: dict[str, bytes], recipe: dict) -> None:
    """Bind compatible public programs to the original camera's exact resource slots."""
    resource = (export / safe_path(recipe["camera_contract"]["resource"])).read_text(encoding="utf-8")
    for row in recipe.get("programs", []):
        source = export / safe_path(row["source_path"])
        meta = Path(str(source) + ".meta")
        package = files.get(row["package_path"], b"")
        package_meta = files.get(row["package_path"] + ".meta", b"")
        if (
            not source.is_file()
            or source.is_symlink()
            or digest(source) != row["source_sha256"]
            or not meta.is_file()
            or meta.is_symlink()
            or digest(meta) != row["source_meta_sha256"]
            or parse_guid(meta) != row["source_guid"]
            or digest_bytes(package) != row["package_sha256"]
            or digest_bytes(package_meta) != row["package_meta_sha256"]
            or re.findall(r"(?m)^\s*" + re.escape(row["field"]) + r": \{fileID: [0-9-]+, guid: ([0-9a-f]{32}), type: [0-9]+\}$", resource)
            != [row["source_guid"]]
        ):
            raise RuntimeError("Source camera program/resource identity changed: " + row["field"])
        if row["kernels"]:
            native = re.findall(r"(?m)^ +name: (\S+)$", source.read_text(encoding="utf-8"))
            kernels = re.findall(r"(?m)^\s*#pragma kernel (\w+)", package.decode("utf-8"))
            if kernels != row["kernels"] or native != kernels:
                raise RuntimeError("Original and public compute kernel contracts differ: " + row["field"])
            groups = [
                list(struct.unpack("<III", bytes.fromhex(value)))
                for value in re.findall(r"(?m)^\s*threadGroupSize: ([0-9a-f]{24})$", source.read_text(encoding="utf-8"))
            ]
            if groups != row["kernel_thread_groups"]:
                raise RuntimeError("Original compute thread groups differ: " + row["field"])


def program_guid(target: str) -> str:
    return digest_bytes(("ror2lab/source-camera-program/" + target).encode())[:32]


def validate_uber_contract(shader: bytes, recipe: dict) -> None:
    text = shader.decode("utf-8")
    if not re.search(r'^\s*Shader\s+"Hidden/PostProcessing/Uber"\s*$', text, re.M):
        raise RuntimeError("Uber shader name changed")
    if len(PASS.findall(text)) != recipe["source_pass_count"] or recipe["selected_pass"] != 0:
        raise RuntimeError("Uber shader no longer satisfies source pass-zero contract")
    if "_MainTex" not in text or "BLOOM_LOW" not in text or "_BloomTex" not in text:
        raise RuntimeError("Uber shader does not preserve the active Bloom composite inputs")


def candidate_root(work: Path, input_id: str, recipe: dict) -> Path:
    return work / recipe["stable_output"].format(input_id=input_id)


def generate_candidate(work: Path, export: Path, input_id: str, *, allow_create: bool = True) -> tuple[Path, dict]:
    recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    if recipe.get("input_id") != input_id or recipe.get("enabled_by_default") is not False:
        raise RuntimeError("Uber candidate recipe is not pinned to this input")
    identity = validate_source_join(export, recipe)
    archive = work / Path(recipe["package_archive"]).relative_to("work")
    files = archive_files(archive, recipe)
    validate_programs(export, files, recipe)
    official = files["Builtins/Uber.shader"]
    closure = include_closure(files, "Builtins/Uber.shader")
    candidate = rewrite_includes(official, closure)
    validate_uber_contract(candidate, recipe)
    output_files = {"sources/Hidden_PostProcessing_Uber_53.shader": candidate}
    program_rows = []
    for row in recipe.get("programs", []):
        source_path = row["package_path"]
        program_closure = include_closure(files, source_path)
        closure.update(program_closure)
        relative = "programs/" + safe_path(row["target"]).name
        body = rewrite_includes(files[source_path], program_closure, recipe["include_target_prefix"])
        meta = re.sub(rb"(?m)^guid: [0-9a-f]{32}$", ("guid: " + program_guid(row["target"])).encode(), files[source_path + ".meta"])
        output_files[relative], output_files[relative + ".meta"] = body, meta
        program_rows.append({**row, "candidate_path": relative, "sha256": digest_bytes(body), "meta_sha256": digest_bytes(meta)})
    include_rows = []
    for name, data in sorted(closure.items()):
        if not name.endswith(".hlsl"):
            continue
        target = PurePosixPath("includes") / name
        meta_name = name + ".meta"
        meta = files.get(meta_name)
        if meta is None:
            raise RuntimeError("Uber include metadata is missing: " + name)
        output_files[target.as_posix()] = data
        output_files[(str(target) + ".meta")] = meta
        include_rows.append({"package_path": name, "candidate_path": target.as_posix(), "sha256": digest_bytes(data), "meta_sha256": digest_bytes(meta)})
    manifest = {
        "schema": SCHEMA,
        "input_id": input_id,
        "recipe_sha256": digest(RECIPE),
        "generator_sha256": digest(Path(__file__)),
        "package_sha256": recipe["package_sha256"],
        "source_identity": identity,
        "shader_candidate_sha256": digest_bytes(candidate),
        "pass_count": recipe["source_pass_count"],
        "selected_pass": 0,
        "includes": include_rows,
        "programs": program_rows,
        "unity_compiled": False,
        "android_accepted": False,
        "visual_parity_proven": False,
    }
    output_files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output = candidate_root(work, input_id, recipe)
    if output.exists():
        existing = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
        if (
            output.is_symlink()
            or existing != set(output_files)
            or any(p.is_symlink() for p in output.rglob("*"))
            or any((output / k).read_bytes() != v for k, v in output_files.items())
        ):
            raise RuntimeError("Existing stable Uber candidate differs from deterministic output")
    else:
        if not allow_create:
            raise RuntimeError("Replay requires the existing stable Uber candidate")
        output.mkdir(parents=True)
        for relative, data in output_files.items():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return output, manifest


def read_activation(work: Path, input_id: str) -> dict | None:
    path = work / "config/postprocessing-uber.json"
    if path.is_symlink():
        raise RuntimeError("Uber activation may not be a symlink")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 4096:
        raise RuntimeError("Uber activation is not a bounded regular file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        set(data) != {"schema", "input_id", "enabled"}
        or data.get("schema") != "whole-catalog-postprocessing-uber-activation-r1"
        or data.get("input_id") != input_id
        or type(data.get("enabled")) is not bool
    ):
        raise RuntimeError("Uber activation has an unknown schema or accepted input")
    return {**data, "sha256": digest(path)}


def check_staging_activation(io, input_id: str) -> dict | None:
    activation = read_activation(io.work, input_id)
    marker = io.project / ".rebuild/postprocessing-uber.json"
    if activation is None or activation["enabled"] is False:
        if marker.is_symlink() or io.is_file(marker):
            raise RuntimeError("Destination has a prior Uber receipt; rebuild cleanly before disabling it")
        return None
    return activation


def stage(io, *, export: Path, mapped: dict[str, str], owners: dict[str, str], destination: Path, input_id: str) -> dict | None:
    activation = check_staging_activation(io, input_id)
    if activation is None:
        return None
    recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    output, manifest = generate_candidate(io.work, export, input_id, allow_create=not io.rebuilding)
    contract = recipe["camera_contract"]
    source = contract["shader"]
    target_relative = mapped.get(source)
    expected_target = "Assets/WholeGame/" + source.removeprefix("Assets/")
    if target_relative != expected_target:
        raise RuntimeError("Uber source asset does not map to its exact WholeGame path")
    target = io.project / target_relative
    meta_target = Path(str(target) + ".meta")
    resource_source = contract["resource"]
    resource_target_relative = mapped.get(resource_source)
    if resource_target_relative != "Assets/WholeGame/" + resource_source.removeprefix("Assets/"):
        raise RuntimeError("Uber PostProcessResources does not map to its exact WholeGame path")
    resource_target = io.project / resource_target_relative
    source_camera = contract["source_camera_prefab"]
    camera_target_relative = mapped.get(source_camera)
    if camera_target_relative != "Assets/WholeGame/" + source_camera.removeprefix("Assets/"):
        raise RuntimeError("Uber source camera prefab does not map to its exact WholeGame path")
    camera_target = io.project / camera_target_relative
    expected_candidate = manifest["shader_candidate_sha256"]
    source_sha = contract["shader_sha256"]
    if any(
        path.is_symlink()
        for path in (
            target,
            meta_target,
            resource_target,
            camera_target,
            *target.parents,
            *meta_target.parents,
            *resource_target.parents,
            *camera_target.parents,
        )
    ):
        raise RuntimeError("Uber source-camera staging refuses project symlinks")
    require_known_stage_preimage(io.sha(target), source_sha, expected_candidate, target_relative)
    if (
        io.sha(meta_target) != contract["shader_meta_sha256"]
        or io.sha(resource_target) != contract["resource_sha256"]
        or io.sha(camera_target) != contract["source_camera_prefab_sha256"]
    ):
        raise RuntimeError("Uber metadata/resource/camera changed before staging")
    candidate = output / "sources/Hidden_PostProcessing_Uber_53.shader"
    prepared = [(target, candidate.read_bytes())]
    # Includes are staged under the exact package-relative namespace. Existing bytes must be exact.
    include_rows, program_rows = [], []
    for kind, row in [("include", row) for row in manifest["includes"]] + [("program", row) for row in manifest["programs"]]:
        package_path = safe_path(row["package_path"])
        relative = PurePosixPath(recipe["include_target_prefix"]) / package_path if kind == "include" else safe_path(row["target"])
        target_include = io.project / relative
        candidate_include = output / row["candidate_path"]
        source_meta = Path(str(candidate_include) + ".meta")
        meta_relative = str(relative) + ".meta"
        target_meta = io.project / meta_relative
        if any(path.is_symlink() for path in (target_include, target_meta, *target_include.parents, *target_meta.parents)):
            raise RuntimeError("Uber include staging refuses project symlinks")
        guid = parse_guid(source_meta)
        owner = owners.get(guid)
        if owner is not None and owner != relative.as_posix():
            raise RuntimeError("Uber include GUID collides with an existing asset")
        if io.is_file(target_include) or io.is_file(target_meta):
            if (
                not io.is_file(target_include)
                or not io.is_file(target_meta)
                or io.sha(target_include) != row["sha256"]
                or io.sha(target_meta) != row["meta_sha256"]
            ):
                raise RuntimeError("Existing Uber include differs from its pinned official package bytes")
        else:
            prepared.extend(((target_include, candidate_include.read_bytes()), (target_meta, source_meta.read_bytes())))
        owners[guid] = relative.as_posix()
        (include_rows if kind == "include" else program_rows).append({**row, "target": relative.as_posix(), "meta_target": meta_relative, "guid": guid})
    # Finish every identity and preimage check before any project write.
    for path, data in prepared:
        io.apply(path, data=data)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "input_id": input_id,
        "activation_sha256": activation["sha256"],
        "recipe_sha256": digest(RECIPE),
        "generator_sha256": digest(Path(__file__)),
        "candidate_manifest_path": "work/" + output.relative_to(io.work).as_posix() + "/manifest.json",
        "candidate_manifest_sha256": digest(output / "manifest.json"),
        "shader_target": target_relative,
        "source_sha256": source_sha,
        "candidate_sha256": expected_candidate,
        "shader_meta_sha256": contract["shader_meta_sha256"],
        "shader_meta_bytes": (export / (source + ".meta")).stat().st_size,
        "resource_target": resource_target_relative,
        "resource_sha256": contract["resource_sha256"],
        "resource_meta_sha256": contract["resource_meta_sha256"],
        "camera_target": camera_target_relative,
        "camera_sha256": contract["source_camera_prefab_sha256"],
        "camera_meta_sha256": contract["source_camera_prefab_meta_sha256"],
        "includes": include_rows,
        "programs": program_rows,
        "unity_compiled": False,
        "android_accepted": False,
        "visual_parity_proven": False,
    }
    io.write(destination / "postprocessing-uber-receipt.json", receipt)
    mirror = io.project / ".rebuild/postprocessing-uber-receipt.json"
    io.write(mirror, receipt)
    io.write(
        io.project / ".rebuild/postprocessing-uber.json",
        {
            "schema": MARKER_SCHEMA,
            "input_id": input_id,
            "receipt_path": mirror.relative_to(io.project).as_posix(),
            "receipt_sha256": io.sha(mirror),
            "activation_path": "work/config/postprocessing-uber.json",
            "activation_sha256": activation["sha256"],
        },
    )
    return receipt


def require_known_stage_preimage(current_sha: str, source_sha: str, candidate_sha: str, path: str) -> None:
    if current_sha not in (source_sha, candidate_sha):
        raise RuntimeError("Refusing to replace unknown staged Uber shader body: " + path)
