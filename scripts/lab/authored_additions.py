"""Generate tracked shader additions and their authored importers, without history."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from common import RECIPE, ROOT, WORK, read


def load_recipe(path=None):
    recipe = read(path or RECIPE / "authored-additions.json")
    if set(recipe) != {"schema_version", "assets"} or recipe["schema_version"] != 1 or not isinstance(recipe["assets"], list) or not recipe["assets"]:
        raise RuntimeError("Invalid authored additions recipe")
    outputs, guids = set(), set()
    for asset in recipe["assets"]:
        if set(asset) != {"source", "source_sha256", "output", "guid"}:
            raise RuntimeError("Invalid authored addition")
        for key, prefix in (("source", "tools/unity/runtime/shaders/"), ("output", "Assets/LabLoadingScene/Resources/")):
            value = asset[key]
            if not isinstance(value, str) or not value.startswith(prefix) or PurePosixPath(value).as_posix() != value or ".." in PurePosixPath(value).parts:
                raise RuntimeError("Invalid authored addition path")
        if Path(asset["source"]).name != Path(asset["output"]).name or Path(asset["source"]).suffix not in (".shader", ".cginc"):
            raise RuntimeError("Invalid authored shader selection")
        if not re.fullmatch(r"[a-f0-9]{64}", asset["source_sha256"]) or not re.fullmatch(r"[a-f0-9]{32}", asset["guid"]):
            raise RuntimeError("Invalid authored addition identity")
        if asset["output"] in outputs or asset["guid"] in guids:
            raise RuntimeError("Duplicate authored addition identity")
        outputs.add(asset["output"])
        guids.add(asset["guid"])
    return recipe


def generate_asset(asset, root=None):
    root = Path(root or ROOT).resolve()
    source = root / asset["source"]
    if root not in source.resolve().parents:
        raise RuntimeError("Authored addition escapes repository")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != asset["source_sha256"]:
        raise RuntimeError("Authored addition source hash mismatch: " + asset["source"])
    return data, shader_importer(asset["guid"], source.suffix == ".shader")


def shader_importer(guid, shader=True):
    """Author a minimal importer while preserving the selected asset identity."""
    if not re.fullmatch(r"[a-f0-9]{32}", guid):
        raise RuntimeError("Invalid shader importer GUID")
    # Independently authored minimal Unity importer schema. Preserve significant trailing spaces.
    meta = (
        "fileFormatVersion: 2\nguid: "
        + guid
        + ("\nShaderImporter:\n" if shader else "\nShaderIncludeImporter:\n")
        + "  externalObjects: {}\n"
        + ("  defaultTextures: []\n  nonModifiableTextures: []\n  preprocessorOverride: 0\n" if shader else "")
        + "  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
    ).encode()
    return meta


def prepare(rows, recipe=None, root=None):
    """Prepare the entire cohort before staging writes; selected rows may relocate targets."""
    assets = {asset["output"]: asset for asset in (recipe or load_recipe())["assets"]}
    prepared = {}
    for row in rows:
        asset = assets.get(row["old"])
        if asset is None:
            continue
        if row["old"] in prepared or row["guid"] != asset["guid"]:
            raise RuntimeError("Authored addition disagrees with composition identity")
        prepared[row["old"]] = generate_asset(asset, root)
    if prepared.keys() != assets.keys():
        raise RuntimeError("Composition omits authored additions")
    return prepared


def check(work=None, root=None):
    """Read-only migration-stage oracle comparison, including normalized bytes and metadata."""
    from composition_migration import normalize_addition

    work, root = Path(work or WORK), Path(root or ROOT)
    selection = read(work / "config/composition-migration.json")
    if selection["input_id"] != read(work / "config/accepted-input.json")["input_id"]:
        raise RuntimeError("Composition belongs to a different accepted input")
    previous = root / selection["previous_project"]
    evidence = root / selection["evidence"]
    guidmap = read(evidence / "rebase-analysis.json")["guidmap"]
    remaps = read(RECIPE / "hud-ui-remaps.json")
    if remaps["input_id"] != selection["input_id"]:
        raise RuntimeError("UI bindings belong to a different input")
    assets = load_recipe()["assets"]
    differences, identical = [], 0
    for asset in assets:
        data, meta = generate_asset(asset, root)
        source = previous / asset["output"]
        original = source.read_bytes()
        oracle = normalize_addition(original, guidmap, remaps)
        changed = []
        if data != oracle:
            changed.append(asset["output"])
        if meta != Path(str(source) + ".meta").read_bytes():
            changed.append(asset["output"] + ".meta")
        differences.extend(changed)
        identical += not changed
    return {"total": len(assets), "identical": identical, "differences": differences}


def check_action():
    result = check()
    print(json.dumps(result, indent=2))
    if result["differences"]:
        raise SystemExit(1)
