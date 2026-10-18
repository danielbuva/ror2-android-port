"""Read-only script comparison and MCP audit payload; never starts or changes an editor."""

import argparse
import json
from pathlib import Path

from common import ROOT, read

UI_PREFABS = (
    "Assets/LabLoadingScene/Resources/RecoveredUI/Hud.prefab",
    "Assets/LabLoadingScene/Resources/RecoveredUI/Menu.prefab",
)


def build_selection(manifest, scene_config):
    """All explicit catalog/probe bundle inputs, before Unity expands dependencies."""

    def paths(value):
        if isinstance(value, str):
            if value.startswith("Assets/"):
                yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from paths(child)
        elif isinstance(value, list):
            for child in value:
                yield from paths(child)

    return sorted(set(paths(scene_config)) | {row["path"] for row in manifest["locations"]} | set(UI_PREFABS) | {"Assets/Recovered/geometry.obj"})


def mcp_payload(selection_file):
    """Execute the exact shared read-only method body without staging a C# file.

    The editor reads the selection from its file: inlined, a real build selection
    exceeds the MCP bridge's 50,000-character code limit (J580)."""
    source = (ROOT / "android/Assets/Editor/LabBuild.cs").read_text()
    body = source.split("// SCRIPT_AUDIT_BEGIN\n", 1)[1].split("// SCRIPT_AUDIT_END", 1)[0]
    path = json.dumps(str(Path(selection_file).resolve()), ensure_ascii=True)
    declaration = "var selection=Newtonsoft.Json.Linq.JObject.Parse(System.IO.File.ReadAllText(" + path + '))["assets"].ToObject<string[]>();\n'
    return dict(action="execute", code=declaration + body, compiler="auto")


def compare(reference, destination):
    """Compare counts and every MonoScript that the working project resolves."""
    if reference["selection"] != destination["selection"]:
        raise ValueError("Audit selections differ; run the working audit with the destination build-selection.json")
    left = {row["path"]: row for row in reference["assets"]}
    right = {row["path"]: row for row in destination["assets"]}
    differences = []
    for path in sorted(left.keys() | right.keys()):
        a, b = left.get(path), right.get(path)
        if a is None or b is None or a["missingScripts"] != b["missingScripts"] or a.get("error") or b.get("error"):
            differences.append(dict(path=path, working=a, destination=b))
    resolved = {(row["guid"], row["localId"]): row for row in reference["monoScripts"] if row["type"]}
    actual = {(row["guid"], row["localId"]): row for row in destination["monoScripts"]}
    lost = [dict(working=row, destination=actual.get(key)) for key, row in sorted(resolved.items()) if actual.get(key, {}).get("type") != row["type"]]
    return dict(
        equal=not differences and not lost and reference["uiValid"] and destination["uiValid"],
        working_missing_scripts=reference["missingScripts"],
        destination_missing_scripts=destination["missingScripts"],
        asset_differences=differences,
        lost_mono_scripts=lost,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selection", type=Path, help="Emit execute_code arguments for the lab MCP editor; reads the destination build-selection.json")
    mode.add_argument("--compare", nargs=2, type=Path, metavar=("WORKING_AUDIT", "DESTINATION_AUDIT"), help="Compare saved raw audit JSON reports")
    args = parser.parse_args()
    result = mcp_payload(args.selection) if args.selection else compare(*(read(path) for path in args.compare))
    print(json.dumps(result, indent=2))
    return 0 if args.selection or result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
