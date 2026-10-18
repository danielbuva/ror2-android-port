"""Host importer identities: public schemas and recorded IDs, never oracle-derived outputs."""

import hashlib
from pathlib import Path
import re

from common import RECIPE, read
from composition_io import StageIO
from scene_rebuild import finish, require_step


# Folder importers are left to Unity: no serialized asset references a folder GUID (J575),
# and J548 keeps unneeded game folder inventories out of public recipes.
GROUPS = ("scripts", "shaders", "other")
SERIALIZED = frozenset(
    (
        ".asset",
        ".prefab",
        ".unity",
        ".mat",
        ".controller",
        ".anim",
        ".overrideController",
        ".playable",
        ".renderTexture",
        ".guiskin",
        ".mask",
        ".lighting",
        ".terrainlayer",
        ".spriteatlas",
    )
)


def membership(recipe):
    paths = [path for group in GROUPS for path in recipe[group]]
    if len(paths) != len(set(paths)):
        raise RuntimeError("Duplicate importer recipe membership")
    return frozenset(paths)


IMPORTER_PATHS = membership(read(RECIPE / "importer-identities.json"))


def render(recipe, layout, input_id):
    """Pure generation; public recipes are the only identity/settings inputs."""
    from rebuild import relative_path

    if recipe["schema"] != 1 or recipe["input_id"] != input_id:
        raise RuntimeError("Importer identities require accepted input")
    if set(recipe) != {"schema", "input_id", *GROUPS}:
        raise RuntimeError("Importer recipe groups differ")
    membership(recipe)
    payload, identities = {}, set()
    for group in GROUPS:
        for path, row in recipe[group].items():
            relative_path(path)
            if not path.startswith("Assets/") or not path.endswith(".meta"):
                raise RuntimeError("Invalid importer path")
            template = {"scripts": "script", "shaders": "shader"}.get(group)
            if group == "scripts":
                if set(row) == {"runtime_source"}:
                    source = row["runtime_source"]
                    if path != "Assets/LabLoadingScene/" + Path(source).name + ".meta":
                        raise RuntimeError("Runtime script staging identity differs")
                    guid = layout["runtime_source_guids"].get(source)
                elif set(row) == {"guid"}:
                    guid = row["guid"]
                else:
                    raise RuntimeError("Invalid script importer identity")
                if not path.endswith(".cs.meta"):
                    raise RuntimeError("Invalid script importer path")
            elif group == "other":
                if set(row) != {"template", "guid"} or row["template"] not in ("default", "text", "model"):
                    raise RuntimeError("Invalid asset importer template")
                template, guid = row["template"], row["guid"]
            else:
                guid = row
                if group == "shaders" and not path.startswith("Assets/LabLoadingScene/Resources/"):
                    raise RuntimeError("Invalid shader importer path")
                if group == "shaders" and not path.endswith(".shader.meta"):
                    raise RuntimeError("Invalid shader importer suffix")
            if not isinstance(guid, str) or not re.fullmatch("[0-9a-f]{32}", guid) or guid in identities:
                raise RuntimeError("Invalid or duplicate importer GUID")
            identities.add(guid)
            payload[path] = (RECIPE / ("templates/" + template + "-importer.meta")).read_text().format(guid=guid).encode()
    return payload


def folder_references(destination, folders):
    """Scan Assets bodies (including importer references, excluding their own GUID line).

    Text GUID tokens are measured in YAML, JSON, XML and importer files. Binary serialized assets also
    get conservative raw 16-byte and Unity four-little-endian-word GUID scans.
    This reports references; it never changes or allocates folder identities.
    """
    destination = destination.resolve()
    guids = {guid.encode(): path for path, guid in folders.items()}
    raw = {}
    for path, guid in folders.items():
        value = bytes.fromhex(guid)
        for spelling in (value, b"".join(value[i : i + 4][::-1] for i in range(0, 16, 4))):
            raw.setdefault(spelling, set()).add(path)
    binary_pattern = re.compile(b"|".join(re.escape(value) for value in raw)) if raw else None
    references, files, serialized, binary = [], 0, 0, 0
    for asset in sorted((destination / "Assets").rglob("*")):
        if asset.is_symlink():
            raise RuntimeError("Folder reference scan refuses links")
        if not asset.is_file():
            continue
        with asset.open("rb") as stream:
            header = stream.read(5)
            if header != b"%YAML" and asset.suffix not in SERIALIZED | {".meta", ".json", ".xml"}:
                continue
            data = header + stream.read()
        files += 1
        if asset.suffix == ".meta":
            data = re.sub(rb"(?m)^guid: [0-9a-f]{32}\r?\n", b"", data)
        found = {guids[value.lower()] for value in re.findall(rb"[0-9a-fA-F]{32}", data) if value.lower() in guids}
        if asset.suffix in SERIALIZED or data.startswith(b"%YAML"):
            serialized += 1
            if not data.startswith(b"%YAML"):
                binary += 1
                if binary_pattern:
                    for match in binary_pattern.finditer(data):
                        found.update(raw[match[0]])
        if found:
            references.append(dict(path=asset.relative_to(destination).as_posix(), folders=sorted(found)))
    return dict(files_scanned=files, serialized_assets=serialized, binary_serialized_assets=binary, references=references, referencing_files=len(references))


def importer_identities(destination, work, input_id, expected, provenance):
    require_step(destination, "runtime-sources", input_id)
    recipe = read(RECIPE / "importer-identities.json")
    if membership(recipe) != expected:
        raise RuntimeError("Importer recipe and provenance membership differ")
    io = StageIO(work, destination)
    io.preflight()
    payload = render(recipe, read(RECIPE / "project-layout.json"), input_id)
    for path, data in payload.items():
        target = destination / path.removesuffix(".meta")
        if path in (recipe["scripts"] | recipe["shaders"]) and not target.is_file():
            raise RuntimeError("Importer target missing: " + path)
        io.apply(destination / path, data)
    # Hash/size gate the entire buffered cohort before publishing anything.
    for path, data in payload.items():
        row = provenance[path]
        if hashlib.sha256(data).hexdigest() != row["sha256"] or len(data) != row["size"]:
            raise RuntimeError("Rebuilt importer differs from provenance: " + path)
    report = dict(input_id=input_id, placed={group: len(recipe[group]) for group in GROUPS})
    io.write(destination / ".rebuild/importer-identities-result.json", report)
    finish(io, "importer-identities", input_id, expected, provenance)
    return report
