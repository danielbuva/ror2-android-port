"""Regenerate the byte-proven native shader additions without reading the previous project."""

import contextlib
import hashlib
import io
from pathlib import Path, PurePosixPath
import tempfile

from authored_additions import shader_importer
from common import WORK, read, sha


def private_input(work, relative):
    from inherited_state import relative_path

    work = Path(work).resolve()
    relative_path(relative, "work/")
    path = (work / PurePosixPath(relative).relative_to("work")).resolve()
    if work not in path.parents:
        raise RuntimeError("Shader input escapes work")
    return path


def cohort(ledger):
    return [a for a in ledger["assets"] if a["status"] == "reproducible" and a["comparison"]["basis"] == "generated_shader_pair"]


def generate_pairs(assets, work=None, verify=True):
    """Run existing generators in isolated scratch; reuse pinned independent HLSL intermediates read-only."""
    import shader_deferred
    import shader_materials

    work = Path(work or WORK).resolve()
    selection = read(work / "config/composition-migration.json")
    accepted = read(work / "config/accepted-input.json")["input_id"]
    if selection["input_id"] != accepted:
        raise RuntimeError("Shader composition belongs to a different accepted input")
    generators = {
        "scripts/lab/shader_deferred.py:generate": shader_deferred.generate,
        "scripts/lab/shader_materials.py:generate": shader_materials.generate,
    }
    groups = {}
    for asset in assets:
        generator = asset["generator"]
        if generator["function"] not in generators:
            raise RuntimeError("Unsupported reproducible shader generator")
        output = generator["output"]
        if (
            output["selection"] != "work/config/composition-migration.json"
            or output["field"] != "shader_sources"
            or output["filename"] != Path(asset["path"]).name
            or Path(output["filename"]).suffix != ".shader"
        ):
            raise RuntimeError("Invalid reproducible shader output")
        for item in generator["inputs"]:
            if sha(private_input(work, item["path"])) != item["sha256"]:
                raise RuntimeError("Shader generator input drift")
        source = private_input(work, selection["shader_sources"][output["index"]])
        if source.name != "sources" or sha(source.parent / "receipt.json") != output["receipt_sha256"]:
            raise RuntimeError("Shader generator receipt drift")
        receipt = read(source.parent / "receipt.json")
        if not receipt["success"] or receipt["source_sha256_by_file"].get(output["filename"]) != output["sha256"]:
            raise RuntimeError("Shader generator output receipt disagrees with ledger")
        groups.setdefault((generator["function"], source.parent), []).append(asset)
    pairs = {}
    for (function, independent), group in groups.items():
        # No current pointers, caches, editor state or Wine bottles are written under work.
        with tempfile.TemporaryDirectory(prefix="ror2-shader-pairs-") as scratch, contextlib.redirect_stdout(io.StringIO()):
            out = Path(scratch)
            generators[function](output=out, resources={Path(a["path"]).stem for a in group}, work=work, root=work.parent, independent=independent)
            for asset in group:
                data = (out / "sources" / Path(asset["path"]).name).read_bytes()
                meta = shader_importer(asset["guid"])
                if verify and any(hashlib.sha256(value).hexdigest() != asset[key] for value, key in ((data, "sha256"), (meta, "meta_sha256"))):
                    raise RuntimeError("Generated shader pair differs from ledger: " + asset["path"])
                if asset["path"] in pairs:
                    raise RuntimeError("Duplicate generated shader addition")
                pairs[asset["path"]] = (data, meta)
    return pairs


def prepare(rows, work=None, ledger=None):
    from inherited_state import load_ledger

    ledger = load_ledger() if ledger is None else ledger
    work = Path(work or WORK).resolve()
    if read(work / "config/accepted-input.json")["input_id"] != ledger["input_id"]:
        raise RuntimeError("Shader ledger belongs to a different accepted input")
    assets = {a["path"]: a for a in cohort(ledger)}
    selected = {}
    for row in rows:
        asset = assets.get(row["old"])
        if asset is None:
            continue
        if row["old"] in selected or row["guid"] != asset["guid"] or row["target"] != asset["project_path"]:
            raise RuntimeError("Generated shader disagrees with composition identity")
        selected[row["old"]] = asset
    if selected.keys() != assets.keys():
        raise RuntimeError("Composition omits reproducible shaders")
    return generate_pairs(list(selected.values()), work)
