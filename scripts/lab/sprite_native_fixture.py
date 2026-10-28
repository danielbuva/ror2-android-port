"""Stage the current exact-editor Sprite runtime fixture; no Editor/device is started.

Source PNGs are referenced by path and hash. Generated geometry stays under work/.
Use the pinned Unity MCP menu action on this isolated project after compilation.
Phone reconstruction and complete-file acceptance remain separate gates.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "tools/phone-build/accepted-output/SpriteNativeFixture.cs"
BOOTSTRAP = "smoke/Assets/Editor/BootstrapMcp.cs"
MENU = """using System.IO;
using UnityEditor;
using UnityEngine;
public static class SpriteNativeFixtureMenu
{
    [MenuItem("Tools/P1/Run Sprite Native Fixture")]
    public static void Run()
    {
        var root = Path.GetDirectoryName(Application.dataPath);
        SpriteNativeFixture.Run(Path.Combine(root, "sprite-source-request.json"),
            Path.Combine(root, "sprite-source-result.json"));
    }
}
"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(root, request_path, output):
    root, request_path, output = (Path(p).resolve() for p in (root, request_path, output))
    output.relative_to(root / "work")
    if output.exists():
        raise ValueError("Use a new fixture output directory")
    request = json.loads(request_path.read_text())
    if set(request) != {"items"} or not isinstance(request["items"], list) or not 1 <= len(request["items"]) <= 256:
        raise ValueError("Invalid source Sprite fixture request")
    identities = set()
    for item in request["items"]:
        if set(item) != {"id", "png", "sha256", "rect", "pivot", "border", "pixels_per_unit", "extrude", "mesh_type"}:
            raise ValueError("Unknown source Sprite fixture fields")
        if not isinstance(item["id"], str) or not item["id"] or item["id"] in identities:
            raise ValueError("Sprite fixture source identities must be unique")
        identities.add(item["id"])
        path = Path(item["png"])
        if not path.is_absolute() or path.suffix.lower() != ".png" or sha(path) != item["sha256"]:
            raise ValueError("Source PNG path/hash changed")
        for name, count in (("rect", 4), ("pivot", 2), ("border", 4)):
            if len(item[name]) != count or any(type(v) not in (int, float) or not math.isfinite(v) for v in item[name]):
                raise ValueError("Invalid source Sprite coordinate extent")
        if (
            min(item["rect"][2:]) <= 0
            or type(item["pixels_per_unit"]) not in (int, float)
            or not math.isfinite(item["pixels_per_unit"])
            or item["pixels_per_unit"] <= 0
        ):
            raise ValueError("Invalid source Sprite scale")
        if type(item["extrude"]) is not int or not 0 <= item["extrude"] < 2**32 or type(item["mesh_type"]) is not int or item["mesh_type"] not in (0, 1):
            raise ValueError("Invalid source Sprite constructor selector")
    project = output / "project"
    for directory in (project / "Assets/Editor", project / "Packages", project / "ProjectSettings"):
        directory.mkdir(parents=True)
    shutil.copyfile(root / SOURCE, project / "Assets/SpriteNativeFixture.cs")
    shutil.copyfile(root / BOOTSTRAP, project / "Assets/Editor/BootstrapMcp.cs")
    (project / "Assets/Editor/SpriteNativeFixtureMenu.cs").write_text(MENU)
    manifest = json.loads((root / "smoke/Packages/manifest.json").read_text())
    for name in ("imageconversion", "physics2d", "jsonserialize"):
        manifest["dependencies"]["com.unity.modules." + name] = "1.0.0"
    (project / "Packages/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (project / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 2021.3.45f2\nm_EditorVersionWithRevision: 2021.3.45f2 (88f88f591b2e)\n")
    (project / "sprite-source-request.json").write_text(json.dumps(request, indent=2) + "\n")
    receipt = {
        "success": True,
        "project": str(project),
        "request_sha256": sha(request_path),
        "source_sha256": sha(root / SOURCE),
        "bootstrap_sha256": sha(root / BOOTSTRAP),
        "items": len(request["items"]),
        "scope": "current exact-editor diagnostic; no phone or bundle qualification",
    }
    (output / "stage-result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(ROOT, args.request, args.output)))


if __name__ == "__main__":
    main()
