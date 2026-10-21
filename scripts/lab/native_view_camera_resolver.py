"""Snapshot only the current project plugin and pinned Unity/Mono resolver inputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "environment/toolchain.json").is_file() and (parent / "recipe").is_dir())
WORK = ROOT / "work"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_dir(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("resolver source directory is missing or unsafe: " + str(path))
    resolved = path.resolve(strict=True)
    cursor = Path(path.anchor)
    for part in path.absolute().parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("resolver source path traverses a symlink: " + str(cursor))
    return resolved


def source_rows(project: Path, unity_contents: Path, expected_input: str, expected_api: str) -> list[dict]:
    """Describe the current plugin/Unity DLL inputs required by the Cecil pass."""
    project = _safe_dir(project)
    unity_contents = _safe_dir(unity_contents)
    plugin_roots = [
        _safe_dir(project / "Assets/LabLoadingScene/Plugins"),
        _safe_dir(project / "Assets/Plugins"),
    ]
    unity_engine = _safe_dir(unity_contents / "Managed/UnityEngine")
    mono_api = _safe_dir(unity_contents / "MonoBleedingEdge/lib/mono/4.7.2-api")
    sources: dict[str, tuple[Path, str]] = {}
    source_roots = [("current-project-plugin", root) for root in plugin_roots]
    source_roots.append(("pinned-unity-engine", unity_engine))
    for owner, root in source_roots:
        for path in sorted(root.glob("*.dll")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("resolver source DLL is unsafe: " + str(path))
            existing = sources.get(path.name)
            if existing is not None:
                if sha(existing[0]) != sha(path):
                    raise ValueError("resolver DLL filename collision has different bytes: " + path.name)
                continue
            sources[path.name] = (path, owner)
    bcl = mono_api / "mscorlib.dll"
    if bcl.is_symlink() or not bcl.is_file():
        raise ValueError("pinned Mono mscorlib reference is missing")
    if "mscorlib.dll" in sources and sha(sources["mscorlib.dll"][0]) != sha(bcl):
        raise ValueError("project mscorlib collides with pinned Mono BCL")
    sources["mscorlib.dll"] = (bcl, "pinned-mono-bcl")
    if sources.get("RoR2.dll", (None, ""))[0] is None or sha(sources["RoR2.dll"][0]) != expected_input:
        raise ValueError("current project plugin set does not contain the exact profile RoR2.dll")
    if sources.get("AK.Wwise.Unity.API.dll", (None, ""))[0] is None or sha(sources["AK.Wwise.Unity.API.dll"][0]) != expected_api:
        raise ValueError("current project plugin set does not contain the exact profile audio API")
    rows = []
    for name, (source, owner) in sorted(sources.items()):
        root = project if owner == "current-project-plugin" else unity_contents
        rows.append(
            {
                "path": name,
                "size": source.stat().st_size,
                "sha256": sha(source),
                "owner": owner,
                "source": source.relative_to(root).as_posix(),
            }
        )
    return rows


def materialize(profile: str, project: Path, input_path: Path, unity_contents: Path, output: Path, expected_input: str, expected_api: str) -> dict:
    project = _safe_dir(project)
    unity_contents = _safe_dir(unity_contents)
    input_path = input_path.resolve(strict=True)
    if sha(input_path) != expected_input:
        raise ValueError("resolver game input differs from its exact profile")
    rows = source_rows(project, unity_contents, expected_input, expected_api)
    output = Path(os.path.abspath(output.expanduser()))
    work = WORK.resolve(strict=True)
    if output == WORK or not output.is_relative_to(WORK):
        raise ValueError("resolver output must remain under ignored work/")
    cursor = WORK
    for part in output.relative_to(WORK).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("resolver output path traverses a symlink: " + str(cursor))
    if output.exists() or output.is_symlink():
        raise ValueError("resolver output must be a new immutable directory")
    resolved_output = output.resolve(strict=False)
    if resolved_output == work or not resolved_output.is_relative_to(work):
        raise ValueError("resolver output escapes ignored work/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    assemblies = output / "assemblies"
    assemblies.mkdir()
    for row in rows:
        name = row["path"]
        owner = row["owner"]
        source_root = project if owner == "current-project-plugin" else unity_contents
        source = source_root / Path(*Path(row["source"]).parts)
        if Path(row["source"]).is_absolute() or ".." in Path(row["source"]).parts or "\\" in row["source"] or Path(row["source"]).as_posix() != row["source"]:
            raise ValueError("resolver source-relative path is unsafe: " + name)
        target = assemblies / name
        before = sha(source)
        shutil.copyfile(source, target)
        if target.stat().st_ino == source.stat().st_ino or sha(source) != before or sha(target) != before or before != row["sha256"]:
            raise ValueError("resolver copy did not preserve an immutable exact DLL: " + name)
    receipt = {
        "schema": "native-view-camera-resolver-set-r2",
        "profile": profile,
        "input_sha256": expected_input,
        "api_sha256": expected_api,
        "count": len(rows),
        "files": rows,
        "source_inventory_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "source_roots": [
            "current project Assets/LabLoadingScene/Plugins/*.dll",
            "current project Assets/Plugins/*.dll",
            "pinned Unity 2021.3.45f2 Contents/Managed/UnityEngine/*.dll",
            "pinned Mono 4.7.2 mscorlib.dll",
        ],
        "player_linker_closure_verified": False,
        "il2cpp_closure_verified": False,
        "stage_to_apk_binding": False,
    }
    (output / "resolver-set.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
