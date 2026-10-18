"""Read-only, input-gated SurfaceDef transformations; no serialized payloads in recipes."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from common import RECIPE, ROOT, WORK, read

SURFACE_OPERATIONS = (
    {"op": "clear_reference", "field": "impactEffectPrefab", "value": None},
    {"op": "clear_reference", "field": "footstepEffectPrefab", "value": None},
    {"op": "set_field", "field": "impactSoundString", "value": ""},
    {"op": "set_field", "field": "materialSwitchString", "value": ""},
)


def apply_surface_operation(text, operation, *, strict=True):
    """Share the sanitizer's span-preserving field clearing; reject unreviewed operations."""
    if operation not in SURFACE_OPERATIONS:
        raise RuntimeError("Unknown field or unsupported SurfaceDef operation")
    field = operation["field"]
    replacement = " {fileID: 0}" if operation["op"] == "clear_reference" else ""
    generated, count = re.subn(r"^(  " + re.escape(field) + r":)[^\r\n]*", lambda match: match[1] + replacement, text, flags=re.M)
    if strict and count != 1:
        raise RuntimeError("SurfaceDef field must match exactly once: " + field)
    return generated


def asset_path(root, selector):
    """Require a canonical project-relative asset path, including resolved symlinks."""
    if not isinstance(selector, str):
        raise RuntimeError("Invalid asset selector")
    path = PurePosixPath(selector)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != selector or not selector.startswith("Assets/"):
        raise RuntimeError("Invalid asset selector")
    result = Path(root) / selector
    if not result.resolve().is_relative_to(Path(root).resolve()):
        raise RuntimeError("Asset selector escapes project")
    return result


def load_recipe(accepted, path=None):
    recipe = read(path or RECIPE / "asset-transforms.json")
    if set(recipe) != {"schema_version", "input_id", "assets"} or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise RuntimeError("Unsupported asset transform schema")
    if recipe["input_id"] != accepted:
        raise RuntimeError("Asset transforms belong to a different accepted input")
    if not isinstance(recipe["assets"], list) or not recipe["assets"]:
        raise RuntimeError("Asset transforms require a nonempty asset list")
    sources, outputs = set(), set()
    for asset in recipe["assets"]:
        if set(asset) != {"source", "source_sha256", "output", "operations"}:
            raise RuntimeError("Invalid asset transform entry")
        for name, seen in (("source", sources), ("output", outputs)):
            asset_path(Path.cwd(), asset[name])
            if not asset[name].endswith(".asset") or asset[name].casefold() in seen:
                raise RuntimeError("Duplicate or invalid asset transform selector")
            seen.add(asset[name].casefold())
        if not isinstance(asset["source_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", asset["source_sha256"]):
            raise RuntimeError("Invalid asset transform source hash")
        if asset["operations"] != list(SURFACE_OPERATIONS):
            raise RuntimeError("Unknown field or unsupported SurfaceDef operations")
    return recipe


def generate(source, asset):
    """Return transformed UTF-8 text from bytes after checking the exact source hash."""
    if hashlib.sha256(source).hexdigest() != asset["source_sha256"]:
        raise RuntimeError("Asset transform source hash mismatch: " + asset["source"])
    text = source.decode("utf-8")
    if len(re.findall(r"^--- !u!114 &-?\d+\r?$", text, re.M)) != 1 or len(re.findall(r"^--- !u!", text, re.M)) != 1:
        raise RuntimeError("SurfaceDef must contain exactly one MonoBehaviour record")
    if len(re.findall(r"^  isSlippery:", text, re.M)) != 1:
        raise RuntimeError("SurfaceDef marker missing or ambiguous")
    if asset["operations"] != list(SURFACE_OPERATIONS):
        raise RuntimeError("Unknown field or unsupported SurfaceDef operations")
    for operation in asset["operations"]:
        text = apply_surface_operation(text, operation)
    return text


def generate_asset(export, asset, guid=None):
    """Return asset/meta bytes; metadata follows composition's export importer rule."""
    source = asset_path(export, asset["source"])
    data = generate(source.read_bytes(), asset).encode("utf-8")
    meta = asset_path(export, asset["source"] + ".meta").read_bytes()
    matches = re.findall(rb"^guid: ([a-f0-9]{32})\r?$", meta, re.M)
    if len(matches) != 1:
        raise RuntimeError("Export metadata GUID missing or ambiguous")
    if guid is not None:
        if not re.fullmatch(r"[a-f0-9]{32}", guid):
            raise RuntimeError("Invalid current asset GUID")
        meta = re.sub(rb"(?<=guid: )[a-f0-9]{32}", guid.encode(), meta, count=1)
    return data, meta


def check(work=None, root=None):
    """Compare every generated asset/meta with the current project without writing."""
    work, root = Path(work or WORK), Path(root or ROOT)
    accepted = read(work / "config/accepted-input.json")["input_id"]
    reconstruction = read(work / "config/reconstruction.json")
    project = work / "lab-project"
    if reconstruction["input_id"] != accepted or read(project / ".port-input.json")["input_id"] != accepted:
        raise RuntimeError("Export/project belongs to a different accepted input")
    recipe = load_recipe(accepted)
    export = root / reconstruction["projects"][0]
    differences, identical = [], 0
    for asset in recipe["assets"]:
        data, meta = generate_asset(export, asset)
        changed = []
        for suffix, expected in (("", data), (".meta", meta)):
            target = asset_path(project, asset["output"] + suffix)
            if not target.is_file() or target.read_bytes() != expected:
                changed.append(asset["output"] + suffix)
        differences.extend(changed)
        identical += not changed
    return {"total": len(recipe["assets"]), "identical": identical, "differences": differences}


def check_action():
    result = check()
    print(json.dumps(result, indent=2))
    if result["differences"]:
        raise SystemExit(1)
