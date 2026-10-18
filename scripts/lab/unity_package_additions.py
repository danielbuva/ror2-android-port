"""Read byte-proven third-party additions from the operator's pinned Unity package."""

import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

from authored_additions import shader_importer
from common import RECIPE, WORK, read, toolchain


def cohort(ledger):
    return [a for a in ledger["assets"] if a["status"] == "reproducible" and a["comparison"]["basis"] == "unity_package_pair"]


def load_recipe(path=None):
    recipe = read(path or RECIPE / "unity-package-additions.json")
    if set(recipe) != {"schema_version", "package", "assets"} or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise RuntimeError("Invalid Unity package additions schema")
    package = recipe["package"]
    if set(package) != {"name", "version", "sha256", "resource", "resource_sha256"}:
        raise RuntimeError("Invalid Unity package selection")
    if (
        package["name"] != "com.unity.textmeshpro"
        or package["version"] != "3.0.6"
        or package["resource"] != "package/Package Resources/TMP Essential Resources.unitypackage"
    ):
        raise RuntimeError("Unsupported Unity package source")
    for digest in (package["sha256"], package["resource_sha256"]):
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise RuntimeError("Invalid Unity package hash")
    if not isinstance(recipe["assets"], list) or not recipe["assets"]:
        raise RuntimeError("Unity package additions require assets")
    outputs, guids = set(), set()
    for asset in recipe["assets"]:
        if set(asset) != {"source", "source_sha256", "output", "guid"}:
            raise RuntimeError("Invalid Unity package addition")
        for key, prefix in (("source", "Assets/TextMesh Pro/Shaders/"), ("output", "Assets/LabLoadingScene/Resources/RecoveredUI/FontShader/")):
            value = asset[key]
            if not isinstance(value, str) or not value.startswith(prefix) or ".." in PurePosixPath(value).parts or PurePosixPath(value).as_posix() != value:
                raise RuntimeError("Invalid Unity package asset path")
        if Path(asset["source"]).name != Path(asset["output"]).name or Path(asset["source"]).suffix != ".cginc":
            raise RuntimeError("Unsupported Unity package asset")
        if not re.fullmatch(r"[a-f0-9]{64}", asset["source_sha256"]) or not re.fullmatch(r"[a-f0-9]{32}", asset["guid"]):
            raise RuntimeError("Invalid Unity package asset identity")
        if asset["output"].casefold() in outputs or asset["guid"] in guids:
            raise RuntimeError("Duplicate Unity package addition")
        outputs.add(asset["output"].casefold())
        guids.add(asset["guid"])
    return recipe


def member(archive, name):
    matches = [m for m in archive.getmembers() if m.name == name]
    if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 32 * 1024 * 1024:
        raise RuntimeError("Unity package member missing, ambiguous or invalid")
    return archive.extractfile(matches[0]).read()


def generate_pairs(assets, verify=True, archive_path=None, recipe_path=None):
    """Read archives in memory, never extract third-party content into the repository."""
    recipe = load_recipe(recipe_path)
    package = recipe["package"]
    if archive_path is None:
        editor = Path(os.environ.get("UNITY_EDITOR", "/Applications/Unity/Hub/Editor/" + toolchain()["unity_version"] + "/Unity.app/Contents/MacOS/Unity"))
        archive_path = editor.parent.parent / "Resources/PackageManager/Editor" / (package["name"] + "-" + package["version"] + ".tgz")
    raw = Path(archive_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != package["sha256"]:
        raise RuntimeError("Unity package archive drift")
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        resource = member(archive, package["resource"])
    if hashlib.sha256(resource).hexdigest() != package["resource_sha256"]:
        raise RuntimeError("Unity resource archive drift")
    sources = {a["output"]: a for a in recipe["assets"]}
    pairs = {}
    with tarfile.open(fileobj=io.BytesIO(resource)) as archive:
        paths = {}
        for row in archive.getmembers():
            if row.name.endswith("/pathname"):
                selector = member(archive, row.name).decode().strip()
                if selector in paths:
                    raise RuntimeError("Ambiguous Unity package asset selector")
                paths[selector] = row.name.rsplit("/", 1)[0] + "/asset"
        for asset in assets:
            source = sources.get(asset["path"])
            if source is None or source["guid"] != asset["guid"] or asset["path"] in pairs:
                raise RuntimeError("Unity package addition disagrees with ledger identity")
            if source["source"] not in paths:
                raise RuntimeError("Unity package asset absent")
            data = member(archive, paths[source["source"]])
            if hashlib.sha256(data).hexdigest() != source["source_sha256"]:
                raise RuntimeError("Unity package asset source drift")
            pair = data, shader_importer(source["guid"], shader=False)
            if verify and any(hashlib.sha256(data).hexdigest() != asset[key] for data, key in zip(pair, ("sha256", "meta_sha256"))):
                raise RuntimeError("Unity package pair differs from ledger")
            pairs[asset["path"]] = pair
    return pairs


def prepare(rows, work=None, ledger=None):
    from inherited_state import load_ledger

    ledger = load_ledger() if ledger is None else ledger
    if read(Path(work or WORK) / "config/accepted-input.json")["input_id"] != ledger["input_id"]:
        raise RuntimeError("Unity package ledger belongs to a different accepted input")
    assets = {a["path"]: a for a in cohort(ledger)}
    selected = {}
    for row in rows:
        asset = assets.get(row["old"])
        if asset is None:
            continue
        if row["old"] in selected or row["guid"] != asset["guid"] or row["target"] != asset["project_path"]:
            raise RuntimeError("Unity package addition disagrees with composition identity")
        selected[row["old"]] = asset
    if selected.keys() != assets.keys() or set(assets) != {a["output"] for a in load_recipe()["assets"]}:
        raise RuntimeError("Composition, ledger and Unity package recipe membership disagree")
    return generate_pairs(list(selected.values()))
