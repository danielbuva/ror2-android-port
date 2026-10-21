"""Data-only module policy for the authored builtin-package/no-overrides profile."""

import hashlib
import json
from pathlib import Path
import re
import shutil


PROFILE = "builtin-modules-no-overrides-v1"
EDITOR_SHA = "b4e891a4412fa03bd515d27997f2144c9500fedea9bc031c5d7137d3cec72361"
TARGET_SHA = "143d2be27e09a7e713afe60e7c7f7b73caeb96d95820958b08d93fa47df5bc5c"
PREFIX = "com.unity.modules."
HEADER = ["%YAML 1.1", "%TAG !u! tag:unity3d.com,2011:", "--- !u!877146078 &1", "PlatformModuleSetup:", "  m_ObjectHideFlags: 0", "  modules:"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def modules(text):
    """Accept only the observed SDK data schema, with no YAML tags/aliases beyond its header."""
    lines = text.splitlines()
    if lines[:6] != HEADER:
        raise ValueError("Unknown SDK module-data header")
    result, index = {}, 6
    while index < len(lines):
        match = re.fullmatch(r"  - name: ([A-Za-z][A-Za-z0-9]*)", lines[index])
        if not match or match[1] in result:
            raise ValueError("Malformed/duplicate SDK module identity")
        name = match[1]
        index += 1
        dependencies = []
        if index >= len(lines) or lines[index] not in ("    dependencies: []", "    dependencies:"):
            raise ValueError("Unknown SDK module dependencies")
        if lines[index].endswith("[]"):
            index += 1
        else:
            index += 1
            while index < len(lines) and lines[index].startswith("      - "):
                item = re.fullmatch(r"      - ([A-Za-z][A-Za-z0-9]*)", lines[index])
                if not item or item[1] in dependencies:
                    raise ValueError("Malformed SDK module dependency")
                dependencies.append(item[1])
                index += 1
            if not dependencies:
                raise ValueError("Empty SDK dependency block needs explicit []")
        flags = {}
        for field in ("strippable", "controlledByBuiltinPackage"):
            match = re.fullmatch(r"    " + field + r": ([01])", lines[index]) if index < len(lines) else None
            if not match:
                raise ValueError("Unknown SDK module flag/schema")
            flags[field] = int(match[1])
            index += 1
        result[name] = flags | {"dependencies": dependencies}
    if not result or any(dependency not in result for row in result.values() for dependency in row["dependencies"]):
        raise ValueError("Unresolved SDK module dependency")
    return result


def policy(editor, target, manifest, packages):
    if not isinstance(manifest, dict) or set(manifest) != {"dependencies"} or not isinstance(manifest["dependencies"], dict):
        raise ValueError("Unknown project package/override profile")
    if not set(target) <= set(editor):
        raise ValueError("Target SDK has foreign module identities")
    for name in target:
        if target[name]["controlledByBuiltinPackage"] != editor[name]["controlledByBuiltinPackage"]:
            raise ValueError("SDK builtin-control flags disagree")
    controlled = {PREFIX + name.lower(): name for name, row in editor.items() if row["controlledByBuiltinPackage"]}
    if len(controlled) != sum(bool(row["controlledByBuiltinPackage"]) for row in editor.values()) or set(packages) != set(controlled):
        raise ValueError("SDK builtin package/module identities differ")
    for name, item in packages.items():
        if (
            not re.fullmatch(r"com\.unity\.modules\.[a-z0-9]+", name)
            or not isinstance(item, dict)
            or item.get("name") != name
            or item.get("type") != "module"
            or item.get("version") != "1.0.0"
            or not isinstance(item.get("dependencies"), dict)
        ):
            raise ValueError("Unknown SDK builtin-package schema")
    for item in packages.values():
        for dependency, version in item["dependencies"].items():
            if dependency not in packages or version != packages[dependency].get("version"):
                raise ValueError("Unresolved/foreign SDK builtin dependency")
    enabled, active = set(), set()

    def resolve(name, version):
        if name not in packages or version != packages[name]["version"]:
            raise ValueError("Non-builtin or unqualified package version")
        if name in active:
            raise ValueError("Cyclic SDK package dependency")
        if name not in enabled:
            active.add(name)
            for dependency, requested in packages[name]["dependencies"].items():
                resolve(dependency, requested)
            active.remove(name)
            enabled.add(name)

    for name, version in manifest["dependencies"].items():
        resolve(name, version)
    disabled = {module for package, module in controlled.items() if package not in enabled}
    unavailable = set(editor) - set(target)
    excluded = disabled | unavailable
    if any(not editor[name]["strippable"] for name in excluded):
        raise ValueError("Policy would exclude an SDK nonstrippable module")
    return {
        "profile": PROFILE,
        "forceIncludeModules": [],
        "forceExcludeModules": sorted(excluded),
        "enabledPackages": sorted(enabled),
        "reasons": {
            name: (["builtin-package-disabled"] if name in disabled else []) + (["unavailable-in-target-sdk"] if name in unavailable else [])
            for name in sorted(excluded)
        },
        "custom_overrides_supported": False,
        "custom_callbacks_supported": False,
    }


def stage_support(destination, request, project, editor, target):
    from phone_content import SOURCES

    if request != {"profile": PROFILE}:
        raise ValueError("Select the explicit builtin-module/no-overrides profile")
    destination, project, editor, target = map(Path, (destination, project, editor, target))
    expected_scripts = {str(Path(folder) / name) for name, folder in SOURCES.items()}
    actual_files = {str(path.relative_to(project)) for path in (project / "Assets").rglob("*") if path.is_file() and path.suffix != ".meta"}
    expected_files = expected_scripts | {"Assets/Fixture.unity", "Assets/StreamingAssets/phone-fixture.bundle"}
    package_files = {path.name for path in (project / "Packages").iterdir()}
    if (
        actual_files != expected_files
        or package_files != {"manifest.json", "packages-lock.json"}
        or any(path.is_symlink() for folder in ("Assets", "Packages") for path in (project / folder).rglob("*"))
    ):
        raise ValueError("Custom editor/package sources need separate policy qualification")
    sources = {
        "editor-modules.asset": editor / "Resources/modules.asset",
        "target-modules.asset": target / "modules.asset",
        "manifest.json": project / "Packages/manifest.json",
    }
    if sha(sources["editor-modules.asset"]) != EDITOR_SHA or sha(sources["target-modules.asset"]) != TARGET_SHA:
        raise ValueError("Unknown SDK module-data version")
    destination.mkdir(parents=True, exist_ok=False)
    for name, path in sources.items():
        shutil.copyfile(path, destination / name)
    (destination / "packages").mkdir()
    for name, row in modules(sources["editor-modules.asset"].read_text()).items():
        if row["controlledByBuiltinPackage"]:
            package = PREFIX + name.lower()
            shutil.copyfile(editor / "Resources/PackageManager/BuiltInPackages" / package / "package.json", destination / "packages" / (package + ".json"))
    result = evaluate_stage(destination)
    lock = json.loads((project / "Packages/packages-lock.json").read_text())
    if (
        not isinstance(lock, dict)
        or set(lock) != {"dependencies"}
        or not isinstance(lock["dependencies"], dict)
        or set(lock["dependencies"]) != set(result["enabledPackages"])
    ):
        raise ValueError("Project package lock differs from builtin dependency closure")
    for name, row in lock["dependencies"].items():
        package = json.loads((destination / "packages" / (name + ".json")).read_text())
        if (
            not isinstance(row, dict)
            or set(row) != {"version", "depth", "source", "dependencies"}
            or row["source"] != "builtin"
            or row["version"] != package["version"]
            or row["dependencies"] != package["dependencies"]
            or type(row["depth"]) is not int
            or row["depth"] < 0
        ):
            raise ValueError("Project package lock has non-builtin/unqualified inputs")
    # This validates input/profile eligibility; policy values are regenerated on Android.
    return {"profile": PROFILE, "captured_policy_staged": False, "package_closure_validated": True, "enabled_package_count": len(result["enabledPackages"])}


def evaluate_stage(directory):
    directory = Path(directory)
    if sha(directory / "editor-modules.asset") != EDITOR_SHA or sha(directory / "target-modules.asset") != TARGET_SHA:
        raise ValueError("SDK module-data drift")
    package_files = sorted((directory / "packages").glob("*.json"))
    packages = {path.stem: json.loads(path.read_text()) for path in package_files}
    result = policy(
        modules((directory / "editor-modules.asset").read_text()),
        modules((directory / "target-modules.asset").read_text()),
        json.loads((directory / "manifest.json").read_text()),
        packages,
    )
    result["input_hashes"] = {
        path.relative_to(directory).as_posix(): sha(path)
        for path in [directory / "editor-modules.asset", directory / "target-modules.asset", directory / "manifest.json", *package_files]
    }
    return result
