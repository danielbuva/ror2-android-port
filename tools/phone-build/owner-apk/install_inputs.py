"""Bind a verified public install recipe to private, locally admitted originals.

No network operations, uploaded inputs, private packet profiles or replay sources.
The assembly receipt is generated from this phone's verified producer outputs.
"""

import hashlib
import importlib.util
from pathlib import Path
import re


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


HERE = Path(__file__).resolve().parent
UPDATES = module("install_input_updates", HERE / "updates.py")
STAGES = ("admission", "staging", "assembly", "textures", "native", "apk", "signing", "install")


def validate_plan(plan, files):
    if (
        not isinstance(plan, dict)
        or set(plan) != {"schema", "required_inputs", "stages", "workspace_bytes", "configuration"}
        or type(plan["schema"]) is not int
        or plan["schema"] != 1
    ):
        raise ValueError("explicit install plan schema 1 required")
    if UPDATES.relative(plan["required_inputs"]) not in files:
        raise ValueError("required-input manifest absent from signed bundle")
    if type(plan["workspace_bytes"]) is not int or not 0 <= plan["workspace_bytes"] <= 2**60:
        raise ValueError("nonnegative bounded workspace estimate required")
    config = plan["configuration"]
    if not isinstance(config, dict) or set(config) != {"bindings"} or not isinstance(config["bindings"], dict):
        raise ValueError("public install configuration contains only input bindings")
    for name, path in config["bindings"].items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name):
            raise ValueError("bounded named input binding required")
        if path != ".":
            UPDATES.relative(path)
    stages = plan["stages"]
    if not isinstance(stages, list) or len(stages) != len(STAGES):
        raise ValueError("all eight explicit install stages required")
    jobs = set()
    for expected, row in zip(STAGES, stages):
        if not isinstance(row, dict) or set(row) != {"id", "title", "jobs"} or row["id"] != expected:
            raise ValueError("ordered install stages required")
        if not isinstance(row["title"], str) or not row["title"].strip() or len(row["title"]) > 100 or any(ord(c) < 32 for c in row["title"]):
            raise ValueError("short stage title required")
        if not isinstance(row["jobs"], list) or (expected not in {"assembly", "textures", "native"} and row["jobs"]):
            raise ValueError("producer jobs belong only to production stages")
        for job in row["jobs"]:
            if UPDATES.relative(job) not in files or job in jobs:
                raise ValueError("each stage job must occur once in signed files")
            jobs.add(job)
    return plan


def verified_file(repo, index, name):
    path = UPDATES.within(repo, name, exists=True)
    if name not in index["files"] or not path.is_file() or UPDATES.RELEASE.digest(path) != index["files"][name]:
        raise ValueError("signed install source changed: " + name)
    return path


def input_description(plan, manifest):
    """Bound the entire cross-language UI document, not only its input JSON."""
    importer = module("install_game_import", HERE / "game_import.py")
    catalog = importer.validate_catalog(manifest)
    manifest = catalog["supported"][0]
    manifest_sha256 = hashlib.sha256(UPDATES.RELEASE.signed_bytes(manifest)).hexdigest()
    description = {
        "schema": 1,
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "catalog": catalog,
        "catalog_sha256": hashlib.sha256(UPDATES.RELEASE.signed_bytes(catalog)).hexdigest(),
        "supported_versions": [
            {"manifest": row, "manifest_sha256": hashlib.sha256(UPDATES.RELEASE.signed_bytes(row)).hexdigest()} for row in catalog["supported"]
        ],
        "recognized_versions": [
            {"manifest": row, "manifest_sha256": hashlib.sha256(UPDATES.RELEASE.signed_bytes(row)).hexdigest()} for row in catalog["recognized"]
        ],
        "workspace_bytes": plan["workspace_bytes"],
        "import_root": "import",
        "stages": plan["stages"],
    }
    if len(UPDATES.RELEASE.signed_bytes(description)) > 3 * 1024**2:
        raise ValueError("phone input description exceeds bounded UI metadata limit")
    return description


def describe(index, repo, inputs):
    """Publish only verified recipe metadata for the SAF UI before import."""
    plan = validate_plan(index.get("install_plan"), index["files"])
    manifest_file = verified_file(repo, index, plan["required_inputs"])
    description = input_description(plan, UPDATES.public().load_json(manifest_file.read_bytes()))
    UPDATES.write_json(UPDATES.within(inputs, "install-inputs.json"), description)
    return description


def prepare(index, repo, inputs):
    """Rehash admitted originals; generate private paths, never trust UI receipts."""
    description = describe(index, repo, inputs)
    importer = module("install_game_import", HERE / "game_import.py")
    imported_root = UPDATES.within(inputs, "import/files", exists=True)
    manifest = importer.select_version(importer.FolderSource(imported_root), description["catalog"])
    hashes = {}
    names = set()
    for row in manifest["files"]:
        name = "import/files/" + row["path"]
        path = UPDATES.within(inputs, name, exists=True)
        if not path.is_file() or path.stat().st_size != row["bytes"] or UPDATES.RELEASE.digest(path) != row["sha256"]:
            raise ValueError("imported game version/input differs: " + row["path"])
        hashes[name] = row["sha256"]
        names.add(row["path"])
    # Root/directory bindings must not expose leftovers from another game version.
    imported_root = UPDATES.within(inputs, "import/files", exists=True)
    observed = set()
    for position, path in enumerate(imported_root.rglob("*")):
        if position > 2 * len(names) + 10000:
            raise ValueError("unexpected private import tree exceeds input inventory")
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise ValueError("nonregular private import entry")
        if path.is_file():
            observed.add(path.relative_to(imported_root).as_posix())
    if observed != names:
        raise ValueError("private import contains files from another selection; import into a fresh version-bound folder")
    bindings = {}
    for name, relative in index["install_plan"]["configuration"]["bindings"].items():
        if relative != "." and relative not in names and not any(n.startswith(relative + "/") for n in names):
            raise ValueError("binding does not select admitted original files: " + name)
        bindings[name] = "import/files" + ("/" + relative if relative != "." else "")
        UPDATES.within(inputs, bindings[name], exists=True)
    UPDATES.write_json(
        UPDATES.within(inputs, "input-selection.json"),
        {
            "game_version": manifest["game_version"],
            "manifest_sha256": hashlib.sha256(UPDATES.RELEASE.signed_bytes(manifest)).hexdigest(),
            "catalog_sha256": description["catalog_sha256"],
        },
    )
    UPDATES.write_json(UPDATES.within(inputs, "input-hashes.json"), hashes)
    return {"manifest": "work/install/assembly.json", "key_directory": "signing/owner", "input_hashes": "input-hashes.json", "bindings": bindings}


def assembly_profile(outputs, inputs, release):
    """Hash local production into an assembly receipt, not a public target oracle."""
    if set(outputs) != set(release["entries"]):
        raise ValueError("produced file membership differs from signed release")
    cache = UPDATES.within(inputs, "work/releases/cache")
    rows = []
    for name, value in sorted(outputs.items()):
        path = UPDATES.within(cache, name, exists=True)
        if not name.startswith(("apk/", "payload/")) or Path(value).resolve(strict=True) != path or not path.is_file():
            raise ValueError("only verified cache outputs may enter assembly")
        rows.append({"path": name, "bytes": path.stat().st_size, "sha256": UPDATES.RELEASE.digest(path)})
    profile = {"schema": "owner-source-output-v1", "release_sha256": hashlib.sha256(UPDATES.RELEASE.signed_bytes(release)).hexdigest(), "targets": rows}
    path = UPDATES.within(inputs, "work/install/assembly.json")
    UPDATES.write_json(path, profile)
    return path, UPDATES.RELEASE.digest(path)
