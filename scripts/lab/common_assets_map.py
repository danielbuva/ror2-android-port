"""Generate the owned GlobalEventManager.CommonAssets binding from accepted input."""

import json
import re
from pathlib import Path


FIELD = re.compile(r"public static (\w+) (\w+);")
LOAD = re.compile(
    r"(?:AsyncOperationHandle<\w+>\s+)?(?P<handle>asyncOperationHandle2?)\s*=\s*"
    r'(?P<loader>LegacyResourcesAPI|Addressables)\.Load(?:Asset)?Async<(?P<asset>\w+)>\("(?P<path>[^"]+)"\);\s*'
    r"(?P=handle)\.Completed\s*\+=\s*delegate\(AsyncOperationHandle<(?P=asset)> x\)\s*\{\s*"
    r"(?P<field>\w+)\s*=\s*x\.Result(?P<component>\.GetComponent<CharacterMaster>\(\))?;\s*\};",
    re.S,
)


def extract(source: str):
    if source.count("public static class CommonAssets") != 1 or source.count("public static GlobalEventManager instance;") != 1:
        raise RuntimeError("Original global common-asset owner changed")
    block = source.split("public static class CommonAssets", 1)[1].split("public static GlobalEventManager instance;", 1)[0]
    declarations = {field: field_type for field_type, field in FIELD.findall(block)}
    rows = []
    for match in LOAD.finditer(block):
        loader, path, field, asset = (match.group(key) for key in ("loader", "path", "field", "asset"))
        field_type = declarations.get(field)
        converted = bool(match.group("component"))
        if not field_type or (converted and (asset, field_type) != ("GameObject", "CharacterMaster")) or (not converted and asset != field_type):
            raise RuntimeError("Original global common-asset field/type changed: " + field)
        rows.append((loader, path, field, asset, field_type))
    if len(rows) != len(declarations) or set(row[2] for row in rows) != set(declarations):
        raise RuntimeError("Original global common-asset initializer changed")
    return rows


def generate(source: Path, destination: Path, input_id: str, legacy_aliases: dict, manifest: dict, expected_missing: set):
    rows = extract(source.read_text())
    keys = {entry["key"] for entry in manifest["keys"] if isinstance(entry["key"], str)}
    available = []
    missing = []
    for loader, path, field, asset, field_type in rows:
        key = legacy_aliases.get(path) if loader == "LegacyResourcesAPI" else path
        present = bool(key and key in keys)
        available.append((loader, path, field, asset, field_type, "1" if present else "0"))
        if not present:
            missing.append(field)
    if set(missing) != expected_missing:
        raise RuntimeError("Original global common-asset closure changed: " + ",".join(missing))
    source_rows = ",\n".join("  new string[] {" + ",".join(json.dumps(value) for value in row) + "}" for row in available)
    code = (
        "// Generated from the accepted original GlobalEventManager.CommonAssets.Load.\n"
        "public static class OriginalGlobalCommonAssetMap {\n"
        " public const string InputId = " + json.dumps(input_id) + ";\n"
        " public static readonly string[][] Rows = new string[][] {\n" + source_rows + "\n };\n}\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(code)
    return {"rows": len(rows), "unlocated_fields": missing}
