"""Reproduce hash-gated export identity additions and their inherited importers."""

import hashlib
from pathlib import Path
import re

from asset_transforms import asset_path, generate_asset
from common import RECIPE, WORK, read
from shader_additions import private_input


def cohort(ledger):
    return [a for a in ledger["assets"] if a["status"] == "reproducible" and a["comparison"]["basis"] == "export_identity_pair"]


def load_recipe(accepted, path=None):
    recipe = read(path or RECIPE / "export-additions.json")
    if set(recipe) != {"schema_version", "input_id", "assets"} or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise RuntimeError("Invalid export additions schema")
    if recipe["input_id"] != accepted:
        raise RuntimeError("Export additions belong to a different accepted input")
    if not isinstance(recipe["assets"], list) or not recipe["assets"]:
        raise RuntimeError("Export additions require assets")
    outputs, guids = set(), set()
    for asset in recipe["assets"]:
        if set(asset) != {"source", "source_sha256", "source_meta_sha256", "output", "guid", "operations", "importer_time_created"}:
            raise RuntimeError("Invalid export addition")
        for key in ("source", "output"):
            asset_path(Path.cwd(), asset[key])
            if Path(asset[key]).suffix != ".png":
                raise RuntimeError("Export identity addition must be a PNG")
        if not asset["output"].startswith("Assets/LabLoadingScene/Resources/") or asset["operations"] != [{"op": "identity"}]:
            raise RuntimeError("Unsupported export addition operation or output")
        if any(not isinstance(asset[key], str) or not re.fullmatch(r"[a-f0-9]{64}", asset[key]) for key in ("source_sha256", "source_meta_sha256")):
            raise RuntimeError("Invalid export addition hash")
        if not isinstance(asset["guid"], str) or not re.fullmatch(r"[a-f0-9]{32}", asset["guid"]):
            raise RuntimeError("Invalid export addition GUID")
        if type(asset["importer_time_created"]) is not int or asset["importer_time_created"] < 0:
            raise RuntimeError("Invalid export importer creation time")
        if asset["output"].casefold() in outputs or asset["guid"] in guids:
            raise RuntimeError("Duplicate export addition identity")
        outputs.add(asset["output"].casefold())
        guids.add(asset["guid"])
    return recipe


def generate_pair(export, asset):
    """Identity body; retain export importer bytes except its explicit GUID/time fields."""
    meta = asset_path(export, asset["source"] + ".meta").read_bytes()
    if hashlib.sha256(meta).hexdigest() != asset["source_meta_sha256"]:
        raise RuntimeError("Export addition importer source drift")
    data, meta = generate_asset(export, asset, asset["guid"])
    meta, count = re.subn(rb"(?m)^(timeCreated: )[0-9]+(?=\r?$)", lambda m: m[1] + str(asset["importer_time_created"]).encode(), meta)
    if count != 1:
        raise RuntimeError("Export importer creation time missing or ambiguous")
    return data, meta


def generate_pairs(assets, work=None, verify=True, recipe_path=None):
    """Return complete pairs without reading the previous project or writing any file."""
    work = Path(work or WORK).resolve()
    accepted = read(work / "config/accepted-input.json")["input_id"]
    reconstruction = read(work / "config/reconstruction.json")
    if reconstruction["input_id"] != accepted:
        raise RuntimeError("Export belongs to a different accepted input")
    export = private_input(work, reconstruction["projects"][0])
    recipe = load_recipe(accepted, recipe_path)
    sources = {a["output"]: a for a in recipe["assets"]}
    pairs = {}
    for asset in assets:
        source = sources.get(asset["path"])
        if source is None or source["guid"] != asset["guid"] or asset["path"] in pairs:
            raise RuntimeError("Export addition disagrees with ledger identity")
        pair = generate_pair(export, source)
        if verify and any(hashlib.sha256(data).hexdigest() != asset[key] for data, key in zip(pair, ("sha256", "meta_sha256"))):
            raise RuntimeError("Export addition pair differs from ledger: " + asset["path"])
        pairs[asset["path"]] = pair
    return pairs


def prepare(rows, work=None, ledger=None):
    from inherited_state import load_ledger

    ledger = load_ledger() if ledger is None else ledger
    work = Path(work or WORK).resolve()
    if read(work / "config/accepted-input.json")["input_id"] != ledger["input_id"]:
        raise RuntimeError("Export ledger belongs to a different accepted input")
    assets = {a["path"]: a for a in cohort(ledger)}
    selected = {}
    for row in rows:
        asset = assets.get(row["old"])
        if asset is None:
            continue
        if row["old"] in selected or row["guid"] != asset["guid"] or row["target"] != asset["project_path"]:
            raise RuntimeError("Export addition disagrees with composition identity")
        selected[row["old"]] = asset
    if selected.keys() != assets.keys():
        raise RuntimeError("Composition omits reproducible export additions")
    recipe = load_recipe(ledger["input_id"])
    if set(assets) != {a["output"] for a in recipe["assets"]}:
        raise RuntimeError("Export recipe and ledger membership disagree")
    return generate_pairs(list(selected.values()), work)
