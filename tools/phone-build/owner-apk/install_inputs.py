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
ACQUIRED = "acquired/"


def validate_plan(plan, files):
    if (
        not isinstance(plan, dict)
        or set(plan) - {"acquired_inputs"} != {"schema", "required_inputs", "stages", "workspace_bytes", "configuration"}
        or type(plan["schema"]) is not int
        or plan["schema"] != 1
    ):
        raise ValueError("explicit install plan schema 1 required")
    if UPDATES.relative(plan["required_inputs"]) not in files:
        raise ValueError("required-input manifest absent from signed bundle")
    if "acquired_inputs" in plan and (UPDATES.relative(plan["acquired_inputs"]) not in files or plan["acquired_inputs"] == plan["required_inputs"]):
        raise ValueError("separate acquired-tool inventory required in signed bundle")
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


def acquired_inventory(value):
    """Read signed size and hash pins for owner-acquired regular files."""
    if not isinstance(value, dict) or not value:
        raise ValueError("nonempty acquired-tool inventory required")
    for name, pin in value.items():
        path = Path(UPDATES.relative(name))
        if (
            not name.startswith(ACQUIRED)
            or not name.isprintable()
            or any(str(parent) in value for parent in path.parents)
            or not isinstance(pin, dict)
            or set(pin) - {"url"} != {"bytes", "sha256"}
            or type(pin["bytes"]) is not int
            or not 0 <= pin["bytes"] <= 2**60
        ):
            raise ValueError("invalid acquired-tool inventory entry: " + name)
        UPDATES.ALPHA.sha256(pin["sha256"])
        if "url" in pin:
            validate_download(name, pin["url"])
    return value


def validate_download(name, url):
    """Permit immutable upstream source files and versioned public Maven JARs."""
    if not isinstance(url, str) or len(url) > 2048 or not re.fullmatch(r"https://[a-z.]+/[a-zA-Z0-9_./-]+", url):
        raise ValueError("unapproved tool download: " + name)
    UPDATES.relative(url.split("/", 3)[3])
    if name.startswith("acquired/asset-ripper/"):
        relative = name.removeprefix("acquired/asset-ripper/")
        if re.fullmatch(r"[0-9a-f]{40}/.+", relative) and url == "https://raw.githubusercontent.com/AssetRipper/AssetRipper/" + relative:
            return
    if name.startswith("acquired/android-sdk/") and name.endswith(".jar") and url.rsplit("/", 1)[-1] == Path(name).name:
        if url.startswith(
            (
                "https://dl.google.com/dl/android/maven2/com/android/tools/",
                "https://dl.google.com/dl/android/maven2/com/android/zipflinger/",
                "https://repo.maven.apache.org/maven2/com/google/guava/",
                "https://repo.maven.apache.org/maven2/com/squareup/javawriter/",
                "https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/",
                "https://repo.maven.apache.org/maven2/org/ow2/asm/",
            )
        ):
            return
    raise ValueError("unapproved tool download: " + name)


def verify_acquired(root, name, pin):
    path = UPDATES.within(root, name)
    if not path.is_file() or path.stat().st_size != pin["bytes"] or UPDATES.RELEASE.digest(path) != pin["sha256"]:
        raise ValueError("owner-acquired tool missing or changed: " + name + ". Use Acquire / resume required tools.")
    return path


def input_description(plan, manifest, acquired=None):
    """Bound the entire cross-language UI document, not only its input JSON."""
    importer = module("install_game_import", HERE / "game_import.py")
    catalog = importer.validate_catalog(manifest)
    tools = acquired_inventory(acquired) if "acquired_inputs" in plan else {}
    originals = {}
    for name, path in plan["configuration"]["bindings"].items():
        if tools and (path == "acquired" or path.startswith(ACQUIRED)):
            if path not in tools and not any(candidate.startswith(path + "/") for candidate in tools):
                raise ValueError(f"signed plan has no acquired tool for binding {name}: {path}")
        else:
            originals[name] = path
    for supported in catalog["supported"]:
        names = {row["path"] for row in supported["files"]}
        for name, path in originals.items():
            if path != "." and path not in names and not any(candidate.startswith(path + "/") for candidate in names):
                raise ValueError(f"supported game version {supported['game_version']} has no admitted original for binding {name}: {path}")
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
    if tools:
        description["acquired_inputs"] = tools
        description["acquired_inputs_sha256"] = hashlib.sha256(UPDATES.RELEASE.signed_bytes(tools)).hexdigest()
    if len(UPDATES.RELEASE.signed_bytes(description)) > 3 * 1024**2:
        raise ValueError("phone input description exceeds bounded UI metadata limit")
    return description


def read_plan(index, repo):
    plan = validate_plan(index.get("install_plan"), index["files"])
    load = UPDATES.public().load_json
    manifest = load(verified_file(repo, index, plan["required_inputs"]).read_bytes())
    acquired = load(verified_file(repo, index, plan["acquired_inputs"]).read_bytes()) if "acquired_inputs" in plan else None
    return input_description(plan, manifest, acquired), acquired or {}


def write_description(inputs, description):
    UPDATES.write_json(UPDATES.within(inputs, "install-inputs.json"), description)


def describe(index, repo, inputs):
    """Publish only verified recipe metadata for the SAF UI before import."""
    description, _ = read_plan(index, repo)
    write_description(inputs, description)
    return description


def prepare(index, repo, inputs):
    """Rehash admitted originals; generate private paths, never trust UI receipts."""
    description, acquired = read_plan(index, repo)
    write_description(inputs, description)
    hashes = {}
    if acquired:
        for name, pin in acquired.items():
            verify_acquired(inputs, name, pin)
            hashes[name] = pin["sha256"]
        tool_root = UPDATES.within(inputs, "acquired", exists=True)
        staged = {path.relative_to(inputs).as_posix() for path in tool_root.rglob("*") if path.is_symlink() or not path.is_dir()}
        if staged != acquired.keys():
            raise ValueError("owner-acquired tool tree differs from signed inventory. Use Acquire / resume required tools.")
    importer = module("install_game_import", HERE / "game_import.py")
    imported_root = UPDATES.within(inputs, "import/files", exists=True)
    manifest = importer.select_version(importer.FolderSource(imported_root), description["catalog"])
    names = set()
    inventory = []
    # The native owners use the host inventory's Path ordering for identity.
    for row in sorted(manifest["files"], key=lambda row: Path(row["path"])):
        name = "import/files/" + row["path"]
        path = UPDATES.within(inputs, name, exists=True)
        stats = path.stat()
        if not path.is_file() or stats.st_size != row["bytes"] or UPDATES.RELEASE.digest(path) != row["sha256"]:
            raise ValueError("imported game version/input differs: " + row["path"])
        hashes[name] = row["sha256"]
        names.add(row["path"])
        inventory.append({"path": row["path"], "size": row["bytes"], "sha256": row["sha256"], "mtime_ns": stats.st_mtime_ns})
    # Root/directory bindings must not expose leftovers from another game version.
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
        if acquired and (relative == "acquired" or relative.startswith(ACQUIRED)):
            bindings[name] = relative
        else:
            bindings[name] = "import/files" + ("/" + relative if relative != "." else "")
        UPDATES.within(inputs, bindings[name], exists=True)
    bindings.setdefault("inventory", "input-hashes.json")
    input_id = hashlib.sha256(UPDATES.RELEASE.signed_bytes([(row["path"], row["sha256"]) for row in inventory])).hexdigest()
    UPDATES.write_json(UPDATES.within(inputs, "work/config/local.json"), {"game_path": str(imported_root)})
    UPDATES.write_json(UPDATES.within(inputs, "work/inventory/files.json"), {"schema": 1, "input_id": input_id, "hash_mode": "full", "files": inventory})
    UPDATES.write_json(UPDATES.within(inputs, "work/config/accepted-input.json"), {"input_id": input_id, "game_version": manifest["game_version"]})
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
