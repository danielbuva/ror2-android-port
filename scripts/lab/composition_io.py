"""Composition's write boundary and isolated R2 coordinator; live inputs are read-only."""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil

from common import RECIPE, ROOT, WORK, game, read, run, sha, toolchain, write


class StageIO:
    def __init__(self, work=None, destination=None):
        self.work = Path(work or WORK).absolute()
        self.rebuilding = destination is not None
        self.project = Path(destination) if self.rebuilding else self.work / "lab-project"
        self.pending = {}
        # Paths a later rebuild step produces; the real stage always has them already.
        self.deferred = frozenset()

    def catalog(self):
        return self.resolve(self.read(self.work / "experiments/whole-catalog/latest.json")["path"])

    def mkdir(self, path):
        if not self.rebuilding:
            self.output(path).mkdir()

    def label(self, path):
        return "work/" + str(Path(path).relative_to(self.work))

    def write(self, path, value):
        self.apply(path, value=value)

    def physical(self, path):
        path = Path(path)
        if self.rebuilding and path.is_relative_to(self.work) and not path.is_relative_to(self.project):
            redirected = self.output(path)
            if redirected.exists():
                return redirected
        return path

    def resolve(self, value):
        path = Path(value)
        if path.parts and path.parts[0] == "work":
            return self.work.joinpath(*path.parts[1:])
        return ROOT / path

    def read_bytes(self, path):
        path = Path(path)
        if path in self.pending:
            if self.pending[path] is None:
                raise FileNotFoundError(path)
            return self.pending[path]
        return self.physical(path).read_bytes()

    def read_text(self, path, **kwargs):
        return self.read_bytes(path).decode(errors=kwargs.get("errors", "strict")).replace("\r\n", "\n").replace("\r", "\n")

    def read(self, path):
        return json.loads(self.read_text(path))

    def sha(self, path):
        return hashlib.sha256(self.read_bytes(path)).hexdigest()

    def accepted(self, path, digest):
        return self.sha(path) == digest

    def is_file(self, path):
        path = Path(path)
        return self.pending[path] is not None if path in self.pending else self.physical(path).is_file()

    def glob(self, root, pattern):
        root = Path(root)
        paths = set(root.glob(pattern))
        paths.update(
            p
            for p in self.pending
            if p.is_relative_to(root) and (pattern.startswith("**/") or p.parent == root) and p.relative_to(root).match(pattern.removeprefix("**/"))
        )
        return sorted(p for p in paths if p not in self.pending or self.pending[p] is not None)

    def output(self, path):
        path = Path(path)
        if path.is_relative_to(self.project):
            target = path
        elif self.rebuilding and path.is_relative_to(self.work):
            target = self.project / ".rebuild/composition" / path.relative_to(self.work)
        elif not self.rebuilding and path.is_relative_to(self.work):
            target = path
        else:
            raise RuntimeError("Composition output escapes selected work/project root")
        root = self.project if self.rebuilding else self.work
        if ".." in target.parts or not target.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("Composition output escapes destination")
        for item in (target, *target.parents):
            if item.is_relative_to(root) and (item.is_symlink() or (item.is_file() and item.stat().st_nlink != 1)):
                raise RuntimeError("Composition output refuses links")
        return target

    def apply(self, path, data=None, *, copy=None, catalog=False, delete=False, missing_ok=False, value=None, source=None, reason=None):
        path = Path(path)
        target = self.output(path)
        if catalog and (Path(copy).is_symlink() or path.is_symlink()):
            raise RuntimeError("Catalog import refuses symlinks")
        if delete:
            if not missing_ok and not self.is_file(path):
                raise FileNotFoundError(path)
            data = None
        elif copy is not None:
            data = self.read_bytes(copy)
        elif value is not None:
            data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        elif isinstance(data, str):
            data = data.encode()
        if self.rebuilding:
            self.pending[path] = data
        elif delete:
            target.unlink(missing_ok=missing_ok)
        elif copy is not None:
            if catalog:
                from whole_catalog import copy_catalog_asset

                copy_catalog_asset(copy, target)
            else:
                shutil.copy2(copy, target)
        elif value is not None:
            write(target, value)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def flush(self):
        for path, data in self.pending.items():
            target = self.output(path)
            if data is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        self.pending.clear()

    def preflight(self):
        if not self.rebuilding:
            from build import preflight

            return preflight()
        # Same host/input gates as build.preflight. Device storage and its receipt
        # belong to install/build, never to this host-only reconstruction step.
        from build import validate_project_generation

        base = game(self.work)
        inv = read(self.work / "inventory/files.json")
        current = {str(p.relative_to(base)): (p.stat().st_size, p.stat().st_mtime_ns) for p in base.rglob("*") if p.is_file()}
        prior = {row["path"]: (row["size"], row["mtime_ns"]) for row in inv["files"]}
        if current != prior:
            raise RuntimeError("Input changed: inspect, review input-diff and explicitly adopt a new baseline")
        if read(self.work / "config/accepted-input.json")["input_id"] != inv["input_id"]:
            raise RuntimeError("Input not accepted")
        validate_project_generation(self.project, inv["input_id"])
        if shutil.disk_usage(ROOT).free < 10 * 1024**3:
            raise RuntimeError("Less than 10 GiB host headroom")
        pin = toolchain()
        if inv["unity_versions"] != [pin["unity_version"]]:
            raise RuntimeError("Accepted game and exact editor pin differ")
        if pin["unity_version"] + " (" + pin["unity_revision"] + ")" not in (ROOT / "smoke/ProjectSettings/ProjectVersion.txt").read_text():
            raise RuntimeError("Unity source version pin changed")
        plist = Path(os.environ["UNITY_EDITOR"]).parent.parent / "Info.plist"
        if plistlib.loads(plist.read_bytes()).get("CFBundleVersion") != pin["unity_version"]:
            raise RuntimeError("Selected editor differs from exact pin")
        tracked = run(["git", "ls-files", "-z"], check=True).stdout.decode().split("\0")
        if any(
            p.startswith(("work/", "build/", "logs/", "screenshots/"))
            or Path(p).suffix.lower() in [".dll", ".exe", ".so", ".apk", ".aab", ".bnk", ".wem", ".bundle", ".keystore", ".jks"]
            for p in tracked
        ):
            raise RuntimeError("Restricted files tracked")


def export_membership(closure, recipe, mesh_sources=()):
    """Catalog closure/mesh relocation plus explicit residual identities.

    Closure and resolved meshes do not include every historical dependency or
    relocated file. Their minimal source/target membership is a public recipe.
    Provenance selects the unchanged subset; it never supplies source identities.
    """
    from rebuild import relative_path

    result = {}
    for source in set(closure["files"]) | set(mesh_sources):
        relative_path(source)
        if not source.startswith("Assets/") or source.endswith(".dll"):
            continue
        target = "Assets/WholeGame/" + source.removeprefix("Assets/")
        for suffix in ("", ".meta"):
            result[target + suffix] = source + suffix
    seen = set()
    for source, target in recipe["copies"]:
        relative_path(source)
        relative_path(target)
        if target in seen or (target in result and result[target] != source):
            raise RuntimeError("Conflicting export-copy membership")
        seen.add(target)
        result[target] = source
    return result


def initialize(io, input_id):
    """Initialize generation identity from R1's public recipe, never the live marker."""
    from assembly_transforms import load_recipe
    from composition_migration import assembly_paths

    originals = read(RECIPE / "original-assemblies.json")
    transforms = load_recipe()
    if originals["input_id"] != input_id or transforms["input_id"] != input_id:
        raise RuntimeError("Assembly generation recipes require accepted input")
    generation = dict(
        input_id=input_id,
        original_assemblies={row["source"]: row["sha256"] for row in originals["assemblies"]},
        transformed_assemblies={name: value for step in transforms["steps"] for name, value in step["outputs"].items()},
        phase="isolated-rebuild",
        unity=toolchain()["unity_version"],
    )
    assembly_paths(io.project, generation, io)
    marker = io.project / ".port-input.json"
    if marker.exists() and io.read(marker) != generation:
        raise RuntimeError("Rebuild generation marker drift")
    # Preflight validates a physical marker. This coordinator-owned file is outside
    # the provenance map's three areas and is never copied from the oracle.
    write(marker, generation)


def composition(destination, work, input_id, expected, provenance):
    from composition_migration import stage
    from composition_rebuild import pinned_catalog_input, pinned_catalog_path, recipe_inputs
    from shader_rebuild import composition_sources

    io = StageIO(work, destination)
    composition_sources(io, [group["selected_source"] for group in read(RECIPE / "shader-rebuild-inputs.json")["groups"]])
    reconstruction = read(work / "config/reconstruction.json")
    membership_recipe = read(RECIPE / "composition-export-copies.json")
    if reconstruction["input_id"] != input_id or membership_recipe["input_id"] != input_id or membership_recipe["schema"] != 1:
        raise RuntimeError("Composition export membership requires accepted input")
    export = io.resolve(reconstruction["projects"][0])
    closure = pinned_catalog_input(work, "reconciled-closure.json")
    if closure["input_id"] != input_id:
        raise RuntimeError("Catalog closure requires accepted input")
    from whole_catalog import read_catalog, source_mesh_subobjects

    # Reuse the catalog importer's existing typed/native mesh membership rule.
    # Ambiguous meshes remain explicit recipe identities here; native bundle
    # recovery/conversion itself is R3's responsibility.
    meshes, _ = source_mesh_subobjects(
        export, closure, read_catalog(pinned_catalog_path(work, "source-catalog.json")), pinned_catalog_input(work, "native-conversions.json")
    )
    membership = export_membership(closure, membership_recipe, [row["source"] for row in meshes])
    copies = {path: membership[path] for path in expected if provenance[path]["producer"] == "export-copy" and path in membership}
    if copies.keys() != {path for path in expected if provenance[path]["producer"] == "export-copy"}:
        raise RuntimeError("Incomplete export-copy membership")
    # Gate the entire export cohort before copying. No hash-based discovery or
    # fallback to the working project is allowed.
    for path, source in copies.items():
        target = destination / path
        io.output(target)
        original = export / source
        if original.is_symlink() or not original.resolve().is_relative_to(export.resolve()):
            raise RuntimeError("Export copy refuses redirects")
        row = provenance[path]
        if sha(original) != row["sha256"] or original.stat().st_size != row["size"]:
            raise RuntimeError("Export copy drift: " + source)
        if target.exists() and sha(target) != row["sha256"]:
            raise RuntimeError("Export destination conflict: " + path)
    initialize(io, input_id)
    io.preflight()
    for path, source in copies.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(export / source, target)
    io.apply(destination / "Packages/manifest.json", value=dict(dependencies=read(RECIPE / "project-layout.json")["dependencies"]))
    stage(io, recipe_inputs(io))
    # Check required products before publishing any staged transformations. Other
    # stage products are intermediate inputs to later builders, also retained.
    for path in sorted(expected):
        target = destination / path
        row = provenance[path]
        if not io.is_file(target) or io.sha(target) != row["sha256"] or len(io.read_bytes(target)) != row["size"]:
            raise RuntimeError("Composition output differs from provenance: " + path)
    from inherited_rebuild import report

    result = report(io, expected, provenance)
    io.write(destination / ".rebuild/inherited-rebuild-result.json", result)
    io.flush()
    return result
