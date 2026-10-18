"""Per-file host replacements for R2's store cohort; ledger pairs remain unretired."""

import hashlib
from pathlib import Path
import re

from authored_additions import shader_importer
from common import RECIPE, read, sha


def importer(asset):
    """Minimal Unity importer schemas; identity is supplied only by the public ledger."""
    path = Path(asset["path"])
    guid = asset["guid"]
    if not re.fullmatch("[a-f0-9]{32}", guid):
        raise RuntimeError("Invalid inherited importer GUID")
    if path.suffix in (".shader", ".cginc"):
        return shader_importer(guid, shader=path.suffix == ".shader")
    kinds = {".json": "TextScriptImporter", ".mat": "NativeFormatImporter", ".prefab": "PrefabImporter", ".asset": "NativeFormatImporter"}
    if path.suffix not in kinds:
        return None
    file_id = ""
    if path.suffix == ".mat":
        file_id = "  mainObjectFileID: 2100000\n"
    elif path.suffix == ".asset":
        ids = {"TMP Settings.asset": 11400000, "Owned full-rectangle texCrosshairNibBar.asset": 21300000}
        if path.name not in ids:
            return None
        file_id = f"  mainObjectFileID: {ids[path.name]}\n"
    # FastDirector's original authored prefab importer predates the editor's
    # trailing-space serialization. Retain that schema explicitly.
    space = "" if asset["path"] == "Assets/LabLoadingScene/EnemyClosure/FastDirector.prefab" else " "
    return (
        f"fileFormatVersion: 2\nguid: {guid}\n{kinds[path.suffix]}:\n  externalObjects: {{}}\n"
        + file_id
        + "".join(f"  {field}:{space}\n" for field in ("userData", "assetBundleName", "assetBundleVariant"))
    ).encode()


def replacements(io, ledger):
    """Generate without reading the store; mismatching candidates never replace it."""
    from shader_additions import private_input
    from unity_package_additions import generate_pairs
    from rebuild import relative_path
    from inherited_state import validate_input

    validate_input(io.work, ledger)
    recipe = read(RECIPE / "inherited-rebuild.json")
    if recipe["schema"] != 1 or recipe["input_id"] != ledger["input_id"]:
        raise RuntimeError("Inherited replay requires accepted input")
    assets = {a["path"]: a for a in ledger["assets"] if a["status"] == "inherited"}
    generated = {}
    for path, asset in assets.items():
        candidate = importer(asset)
        if candidate is not None and hashlib.sha256(candidate).hexdigest() == asset["meta_sha256"]:
            generated[path + ".meta"] = candidate
    for path, row in recipe["texture_importers"].items():
        asset = assets.get(path.removesuffix(".meta"))
        if asset is None or not path.endswith(".png.meta") or asset["guid"] != row["guid"]:
            raise RuntimeError("Inherited texture importer identity drift")
        relative_path(row["source"])
        if not row["source"].startswith("Assets/") or type(row["time_created"]) is not int or row["time_created"] < 0:
            raise RuntimeError("Invalid inherited texture importer recipe")
        reconstruction = read(io.work / "config/reconstruction.json")
        if reconstruction["input_id"] != ledger["input_id"]:
            raise RuntimeError("Inherited importer export input drift")
        export = private_input(io.work, reconstruction["projects"][0])
        source = export / row["source"]
        if not source.resolve().is_relative_to(export.resolve()) or sha(source) != row["source_sha256"]:
            raise RuntimeError("Inherited importer source drift")
        data, guids = re.subn(rb"(?m)^guid: [a-f0-9]{32}(?=\r?$)", b"guid: " + row["guid"].encode(), source.read_bytes())
        data, times = re.subn(rb"(?m)^timeCreated: [0-9]+(?=\r?$)", b"timeCreated: " + str(row["time_created"]).encode(), data)
        if guids != 1 or times != 1:
            raise RuntimeError("Inherited importer fields missing or ambiguous")
        if hashlib.sha256(data).hexdigest() == asset["meta_sha256"]:
            generated[path] = data
    package = read(RECIPE / "inherited-rebuild-package.json")
    selected = []
    for row in package["assets"]:
        asset = assets.get(row["output"])
        if asset is None:
            raise RuntimeError("Inherited package membership drift")
        selected.append(asset)
    pairs = generate_pairs(selected, verify=False, recipe_path=RECIPE / "inherited-rebuild-package.json")
    for path, pair in pairs.items():
        for suffix, key, data in zip(("", ".meta"), ("sha256", "meta_sha256"), pair):
            if hashlib.sha256(data).hexdigest() == assets[path][key]:
                generated[path + suffix] = data
    return generated


def remaining_reason(path):
    if path.endswith(".meta"):
        return "Importer generator absent or bytes differ from ledger"
    if path.endswith("FastDirector.prefab"):
        return "stage_enemy_spine rejects stale catalog/source record identities; reviewed source rebase required"
    if path.endswith("Strings.json"):
        return "Current English merge differs from inherited bytes (J562); retain store"
    if path.endswith("TMP_SDF-Mobile.shader"):
        return "Pinned TMP package shader differs from inherited bytes (J562); retain store"
    return "RecoveredHudBuilder.Generate requires Unity AssetDatabase/PrefabUtility/Sprite serialization and exact-editor identity fixture"


def report(io, expected, provenance):
    from inherited_state import load_ledger

    ledger = load_ledger()
    origins = getattr(io, "inherited_origins", {})
    targets = {a["project_path"] + suffix: a["path"] + suffix for a in ledger["assets"] for suffix in ("", ".meta")}
    regenerated, inherited = [], {}
    for path in sorted(expected):
        if provenance[path]["producer"] != "inherited-store":
            continue
        old = targets[path]
        if origins.get(old) == "regenerated":
            regenerated.append(path)
        elif origins.get(old) == "store":
            inherited[path] = remaining_reason(path)
        else:
            raise RuntimeError("Inherited replay lacks per-file origin: " + path)
    return dict(
        regenerated=regenerated, still_inherited=inherited, counts=dict(regenerated=len(regenerated), still_inherited=len(inherited)), j558_satisfied=False
    )
