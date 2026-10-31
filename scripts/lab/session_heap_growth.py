#!/usr/bin/env python3
"""Compare private MemorySnapshotDataTools exports without printing heap content.

Reuse the pinned Unity parser (86af1fe8), empty-array correction and root logger;
this script is not another .snap parser. Only indices, declared sizes, type names
and directed connections are analyzed. Snapshot paths are read privately only to
bind exports to the selected capture receipt. Object names, addresses, strings,
paths and raw root labels are never printed.

Native-bridge reachability is inclusive, NOT exclusive retained size. The pinned
upstream export alone omits static/GC root seeds; the reviewed same-export root
logger supplies those indices without a runtime walk. Captures perturb memory;
their endpoint delta is not the uninstrumented matched-menu acceptance slope.
"""

import argparse
from collections import defaultdict
from collections import deque
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile


TYPE_NAME = re.compile(r"[A-Za-z_<][A-Za-z0-9_.+`\[\],<>*&-]{0,511}\Z")
UNKNOWN_TYPE = "<unavailable-type>"
ROOT_LINE = re.compile(r"^LAB_(STATIC_ROOT|GC_HANDLE_ROOT) (\d+) (.+)$")
PLAYER_STATS = "RoR2.Stats.PlayerStatsComponent"
ROOT_DEPTH = 24
ROOT_VISITS = 100000
REPOSITORY = Path(__file__).resolve().parents[2]
PARSER_PIN = "86af1fe8b60bfcb5e6fbe63e85377887aec32ef5"
PARSER_REFERENCE = "work/reference-repos/Unity-Technologies__MemorySnapshotDataTools"
PATCHES = ("recipe/memory-snapshot-data-tools-empty-array.patch", "recipe/memory-snapshot-data-tools-root-labels.patch")
PATCH_HASHES = {
    PATCHES[0]: "f254b871e76dadcde2ff3983ccaf65cd7cb99425ab02e35ee2176d81ed499215",
    PATCHES[1]: "6cd71ec2c3c2101945dbe9ca9ec8ff1b43910266467688e1c3d67e66ee40fde4",
}
EXPORT_GENERATOR = "session_heap_growth_pinned_msdt_root_labels"


class AnalysisError(Exception):
    """Only fixed authored reason codes may cross the public-output boundary."""


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error repeats arbitrary arguments, including paths.
        raise AnalysisError("invalid_arguments")


def type_name(value):
    return value if isinstance(value, str) and TYPE_NAME.fullmatch(value) else UNKNOWN_TYPE


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private_path(value, root=None):
    """Work may be the lab's intentional symlink; resolve only its owned child."""
    root = REPOSITORY if root is None else Path(root)
    path = Path(value)
    path = path if path.is_absolute() else root / path
    resolved = path.resolve()
    if not resolved.is_relative_to((root / "work/coordination").resolve()):
        raise AnalysisError("export_output_outside_coordination")
    return resolved


def command(argv, cwd, stdout_path, stderr_path, timeout=3600):
    """Private output and a reaped process group, including interrupted exports."""
    with Path(stdout_path).open("wb") as stdout, Path(stderr_path).open("wb") as stderr:
        child = subprocess.Popen([str(part) for part in argv], cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            raise
        finally:
            # Build/export children share this newly created group, never the
            # caller's group. Do not leave compiler workers after parent exit.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        if code:
            raise AnalysisError("private_export_command_failed")


def dotnet_command(root, arguments):
    # No private path is interpolated into shell text. Source the repository's
    # established SDK selection and disable compiler/build-server reuse.
    return [
        "/bin/sh",
        "-c",
        '. "$1"; shift; export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER=1 MSBUILDDISABLENODEREUSE=1; exec "$DOTNET_ROOT/dotnet" "$@"',
        "session-heap-dotnet",
        root / "scripts/env.sh",
        *arguments,
    ]


def export_pair(receipt_path, pair, menus, expected_apk_sha256, output, root=None):
    """Export the exact pair with reviewed patches; never copy a dirty worktree."""
    root = REPOSITORY if root is None else Path(root)
    out = private_path(output, root)
    if out.exists():
        raise AnalysisError("new_export_directory_required")
    out.mkdir(parents=True)
    receipt_path = Path(receipt_path)
    receipt_path = receipt_path if receipt_path.is_absolute() else root / receipt_path
    patch_hashes = {name: file_sha256(root / name) for name in PATCHES}
    if patch_hashes != PATCH_HASHES:
        raise AnalysisError("reviewed_parser_patches_required")
    manifest = {
        "success": False,
        "generator": EXPORT_GENERATOR,
        "parser_commit": PARSER_PIN,
        "patch_sha256": patch_hashes,
        "capture_receipt_sha256": file_sha256(receipt_path),
        "apk_sha256": expected_apk_sha256,
        "menus": menus,
        "exports": [],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="parser-", dir=out) as temporary:
            temporary = Path(temporary)
            archive = temporary / "source.tar"
            command(["git", "-C", root / PARSER_REFERENCE, "archive", "--format=tar", PARSER_PIN], root, archive, out / "archive.stderr", 120)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(archive) as packed:
                packed.extractall(source, filter="data")
            command(["git", "init", "--quiet"], source, out / "init.stdout", out / "init.stderr", 120)
            for index, patch in enumerate(PATCHES):
                for checking in (True, False):
                    action = "check" if checking else "apply"
                    argv = ["git", "apply", "--unidiff-zero", *(["--check"] if checking else []), root / patch]
                    command(argv, source, out / ("patch-%d-%s.stdout" % (index, action)), out / ("patch-%d-%s.stderr" % (index, action)), 120)
            command(
                dotnet_command(root, ["build", "Cli", "-c", "Release", "--disable-build-servers", "-p:UseSharedCompilation=false"]),
                source,
                out / "build.stdout",
                out / "build.stderr",
            )
            for menu, (snapshot, snapshot_hash) in zip(menus, pair):
                database_path = out / ("menu-%d.duckdb" % menu)
                roots_path = out / ("menu-%d.roots.log" % menu)
                command(
                    dotnet_command(
                        root, ["run", "--project", "Cli", "-c", "Release", "--no-build", "--", "export", snapshot, database_path, "--validate", "minimal"]
                    ),
                    source,
                    out / ("menu-%d.export.stdout" % menu),
                    roots_path,
                )
                if not database_path.is_file() or not database_path.stat().st_size or file_sha256(snapshot) != snapshot_hash:
                    raise AnalysisError("export_snapshot_or_database_mismatch")
                with roots_path.open() as lines:
                    if not any(ROOT_LINE.fullmatch(line.rstrip("\r\n")) for line in lines):
                        raise AnalysisError("export_root_sidecar_missing")
                manifest["exports"].append(
                    {
                        "menu": menu,
                        "snapshot_sha256": snapshot_hash,
                        "database_file": database_path.name,
                        "database_sha256": file_sha256(database_path),
                        "root_sidecar_file": roots_path.name,
                        "root_sidecar_sha256": file_sha256(roots_path),
                    }
                )
        if patch_hashes != {name: file_sha256(root / name) for name in PATCHES}:
            raise AnalysisError("parser_patch_drift")
        manifest["success"] = True
    finally:
        temporary_receipt = out / "export-receipt.json.tmp"
        temporary_receipt.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        temporary_receipt.replace(out / "export-receipt.json")
    return out / "export-receipt.json"


def read_export_pair(export_receipt, capture_receipt, pair, menus, expected_apk_sha256, root=None):
    """Only same-export parser indices enter root attribution; no device logs."""
    root = REPOSITORY if root is None else Path(root)
    path = private_path(export_receipt, root)
    manifest = json.loads(path.read_text())
    capture_receipt = Path(capture_receipt)
    capture_receipt = capture_receipt if capture_receipt.is_absolute() else root / capture_receipt
    if (
        manifest.get("success") is not True
        or manifest.get("generator") != EXPORT_GENERATOR
        or manifest.get("parser_commit") != PARSER_PIN
        or manifest.get("patch_sha256") != PATCH_HASHES
        or {name: file_sha256(root / name) for name in PATCHES} != PATCH_HASHES
        or manifest.get("capture_receipt_sha256") != file_sha256(capture_receipt)
        or manifest.get("apk_sha256") != expected_apk_sha256
        or manifest.get("menus") != menus
        or len(manifest.get("exports", [])) != len(pair)
    ):
        raise AnalysisError("export_provenance_mismatch")
    result = []
    for entry, menu, (_, snapshot_hash) in zip(manifest["exports"], menus, pair):
        if entry.get("menu") != menu or entry.get("snapshot_sha256") != snapshot_hash:
            raise AnalysisError("export_snapshot_binding_mismatch")
        files = []
        for key in ("database", "root_sidecar"):
            name = entry[key + "_file"]
            selected = path.parent / name
            if Path(name).name != name or selected.resolve().parent != path.parent or not selected.is_file() or file_sha256(selected) != entry[key + "_sha256"]:
                raise AnalysisError("export_file_hash_mismatch")
            files.append(selected)
        result.append(files)
    return result


def capture_pair(receipt_path, menus, expected_apk_sha256, root=None):
    """Select exact snapshot records, never latest folders or filename guesses."""
    root = REPOSITORY if root is None else Path(root)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_apk_sha256):
        raise AnalysisError("invalid_expected_apk_digest")
    path = Path(receipt_path)
    if not path.is_absolute():
        path = root / path
    receipt = json.loads(path.read_text())
    if receipt.get("success") is not True or receipt.get("mode") != "capture" or receipt.get("apk_sha256") != expected_apk_sha256:
        raise AnalysisError("successful_matching_capture_required")
    evidence = (root / receipt["stage_evidence"]).resolve()
    if not evidence.is_relative_to((root / "work").resolve()):
        raise AnalysisError("capture_evidence_outside_work")
    stage = json.loads((evidence / "result.json").read_text())
    snapshots = receipt.get("memory_snapshots")
    if (
        stage.get("success") is not True
        or stage.get("apk_sha256") != expected_apk_sha256
        or stage.get("runtime_errors")
        or stage.get("failures")
        or stage.get("memory_snapshots") != snapshots
    ):
        raise AnalysisError("capture_receipt_stage_mismatch")
    pair = []
    for menu in menus:
        item = snapshots[str(menu)]
        if not isinstance(item.get("file"), str) or not re.fullmatch(r"session-%d-[0-9a-f]{32}\.snap" % menu, item["file"]):
            raise AnalysisError("capture_snapshot_name_mismatch")
        snapshot = (evidence / item["file"]).resolve()
        if snapshot.parent != evidence or not snapshot.is_file() or snapshot.stat().st_size != item["bytes"] or file_sha256(snapshot) != item["sha256"]:
            raise AnalysisError("capture_snapshot_hash_mismatch")
        pair.append((snapshot, item["sha256"]))
    return pair


def verify_export(connection, snapshot):
    metadata = list(rows(connection, "SELECT snapshot_path FROM snapshot_info"))
    if len(metadata) != 1 or not isinstance(metadata[0][0], str) or Path(metadata[0][0]).resolve() != snapshot:
        raise AnalysisError("database_capture_binding_mismatch")


def natural(value):
    if type(value) is not int or value < 0:
        raise AnalysisError("invalid_numeric_data")
    return value


def node(kind, index):
    index = natural(index)
    if kind == "managed_object":
        return index
    if kind == "native_object":
        return -index - 1
    raise AnalysisError("unsupported_connection_kind")


@contextmanager
def database(path):
    path = Path(path)
    if not path.is_file():
        raise AnalysisError("database_unavailable")
    connection = None
    try:
        if path.suffix == ".duckdb":
            try:
                import duckdb
            except ImportError:
                raise AnalysisError("duckdb_python_dependency_unavailable") from None
            connection = duckdb.connect(str(path), read_only=True, config={"enable_external_access": False})
        elif path.suffix == ".db":
            connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
        else:
            raise AnalysisError("expected_exported_database")
        yield connection
    finally:
        if connection is not None:
            connection.close()


def rows(connection, query):
    """Stream the existing fixed schema; never construct SQL from input values."""
    cursor = connection.execute(query)
    while batch := cursor.fetchmany(8192):
        yield from batch


def totals(objects, selected=None):
    selected = objects.keys() if selected is None else selected
    count = size = 0
    for key in selected:
        if key >= 0:
            count += 1
            size += objects[key][1]
    return count, size


def reachable(edges, seeds):
    seen = set(seeds)
    pending = list(seen)
    while pending:
        for target in edges.get(pending.pop(), ()):
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return seen


def root_seeds(lines, objects):
    """The supplied snapshot-local sidecar is evidence; graph indegree is not.

    The label is deliberately discarded: even valid field/handle descriptions
    may contain addresses or values. The root's type comes from the heap table.
    """
    roots = defaultdict(set)
    for line in lines:
        match = ROOT_LINE.fullmatch(line.rstrip("\r\n"))
        if match is None:
            continue
        kind, index = match.group(1), int(match.group(2))
        if index not in objects:
            raise AnalysisError("root_sidecar_index_unresolved")
        roots[index].add(kind)
    if not roots:
        raise AnalysisError("root_sidecar_has_no_roots")
    return roots


def root_paths(objects, edges, roots, max_depth=ROOT_DEPTH, max_visits=ROOT_VISITS):
    """One shortest type-only witness per target/root; report incomplete walks."""
    reverse = defaultdict(set)
    for source, targets in edges.items():
        for target in targets:
            reverse[target].add(source)
    witnesses = defaultdict(set)
    targets = [key for key, (name, _) in objects.items() if key >= 0 and name == PLAYER_STATS]
    truncated = 0
    largest_walk = 0
    targets_with_roots = set()
    for target in targets:
        toward_target = {target: None}
        queue = deque([(target, 0)])
        incomplete = False
        while queue:
            current, depth = queue.popleft()
            if current in roots:
                path = []
                cursor = current
                while cursor is not None:
                    path.append(objects[cursor][0])
                    cursor = toward_target[cursor]
                for kind in roots[current]:
                    witnesses[(kind, tuple(path))].add(target)
                targets_with_roots.add(target)
                # A root can itself be retained by another root: keep walking.
            for parent in sorted(reverse.get(current, ())):
                if parent in toward_target:
                    continue
                if depth == max_depth or len(toward_target) == max_visits:
                    incomplete = True
                    continue
                toward_target[parent] = current
                queue.append((parent, depth + 1))
        truncated += incomplete
        largest_walk = max(largest_walk, len(toward_target))
    result = []
    for (kind, path), selected in sorted(witnesses.items()):
        count, size = totals(objects, selected)
        result.append({"root_kind": kind, "path_types": list(path), "target_count": count, "target_bytes": size})
    return {
        "target_type": PLAYER_STATS,
        "target_count": len(targets),
        "targets_with_proven_root_path": len(targets_with_roots),
        "truncated_target_walks": truncated,
        "largest_visited_count": largest_walk,
        "depth_limit": max_depth,
        "visited_limit": max_visits,
        "paths": result,
    }


def summarize(connection, root_lines=None):
    """Compare type groups, not unstable addresses/object indices across captures.

    root_lines is reserved for a verified same-export producer; the CLI does not
    accept runtime reflection ordinals or unproven user-labelled root files.
    """
    objects = {}
    by_type = defaultdict(lambda: [0, 0])
    for index, name, size in rows(connection, "SELECT managed_object_index, managed_type_name, size_bytes FROM managed_objects"):
        key = node("managed_object", index)
        if key in objects:
            raise AnalysisError("duplicate_object_index")
        name, size = type_name(name), natural(size)
        objects[key] = (name, size)
        by_type[name][0] += 1
        by_type[name][1] += size
    for index, name in rows(connection, "SELECT native_object_index, native_type_name FROM native_objects"):
        key = node("native_object", index)
        if key in objects:
            raise AnalysisError("duplicate_object_index")
        objects[key] = (type_name(name), 0)

    edges = defaultdict(set)
    bridge_seeds = defaultdict(set)
    for from_kind, from_index, to_kind, to_index, relation in rows(
        connection, "SELECT from_kind, from_index, to_kind, to_index, connection_type FROM connections"
    ):
        source, target = node(from_kind, from_index), node(to_kind, to_index)
        if source not in objects or target not in objects:
            raise AnalysisError("unresolved_connection_endpoint")
        edges[source].add(target)
        if relation == "native_gc_handle_bridge" and source < 0 <= target:
            bridge_seeds[objects[source][0]].add(source)

    # Native names and root labels can contain game text; use only native TYPE.
    # Shared descendants are counted once per group, but may occur in several
    # groups. No bridge group is an exclusive GC/static retaining root.
    bridges = {name: totals(objects, reachable(edges, seeds)) for name, seeds in bridge_seeds.items()}
    roots = root_seeds(root_lines, objects) if root_lines is not None else None
    roots_by_type = defaultdict(set)
    for index, kinds in (roots or {}).items():
        for kind in kinds:
            roots_by_type[(kind, objects[index][0])].add(index)
    root_totals = {key: totals(objects, reachable(edges, seeds)) for key, seeds in roots_by_type.items()}
    return {
        "types": dict(by_type),
        "native_bridges": bridges,
        "total": totals(objects),
        "roots": root_totals if roots is not None else None,
        "root_paths": root_paths(objects, edges, roots) if roots is not None else None,
    }


def delta(before, after):
    return {
        "before_count": before[0],
        "after_count": after[0],
        "growth_count": after[0] - before[0],
        "before_bytes": before[1],
        "after_bytes": after[1],
        "growth_bytes": after[1] - before[1],
    }


def growth_rows(before, after, top):
    result = []
    for name in before.keys() | after.keys():
        change = delta(before.get(name, (0, 0)), after.get(name, (0, 0)))
        if change["growth_bytes"] > 0 or change["growth_count"] > 0:
            result.append({"type": name, **change})
    result.sort(key=lambda row: (-row["growth_bytes"], -row["growth_count"], row["type"]))
    return result[:top]


def compare(before, after, menus, top=20):
    if len(menus) != 2 or any(type(menu) is not int or menu < 2 for menu in menus) or menus[1] <= menus[0]:
        raise AnalysisError("invalid_menu_interval")
    if type(top) is not int or not 1 <= top <= 100:
        raise AnalysisError("invalid_top_count")
    total = delta(before["total"], after["total"])
    root_growth = None
    if before["roots"] is not None and after["roots"] is not None:
        root_growth = []
        for key in before["roots"].keys() | after["roots"].keys():
            change = delta(before["roots"].get(key, (0, 0)), after["roots"].get(key, (0, 0)))
            if change["growth_bytes"] > 0 or change["growth_count"] > 0:
                root_growth.append({"root_kind": key[0], "type": key[1], **change})
        root_growth.sort(key=lambda row: (-row["growth_bytes"], -row["growth_count"], row["root_kind"], row["type"]))
        root_growth = root_growth[:top]
    paths = after["root_paths"]
    if paths is not None:
        selected = sorted(paths["paths"], key=lambda row: (-row["target_bytes"], -row["target_count"], row["root_kind"], row["path_types"]))
        paths = dict(paths, paths=selected[:top], omitted_path_count=max(0, len(selected) - top))
    return {
        "scope": "instrumented_heap_endpoint_comparison_not_acceptance",
        "menu_before": menus[0],
        "menu_after": menus[1],
        "completed_session_interval": menus[1] - menus[0],
        "managed_total": total,
        "managed_endpoint_delta_bytes_per_session": total["growth_bytes"] / (menus[1] - menus[0]),
        "top_managed_type_growth": growth_rows(before["types"], after["types"], top),
        "top_native_bridge_reachable_growth": growth_rows(before["native_bridges"], after["native_bridges"], top),
        "native_bridge_groups_overlap": True,
        "exclusive_retained_size_available": False,
        "gc_static_root_attribution_available": after["roots"] is not None,
        "top_gc_static_root_reachable_growth": root_growth,
        "after_player_stats_root_paths": paths,
        "limits": (
            "Export alone omits GC/static root seeds. Only supplied snapshot-bound sidecar indices are proven roots. "
            "Reachability groups overlap and are not exclusive retained size. Bounded paths do not establish absence of other roots or a leak fix."
        ),
    }


def main(argv=None):
    parser = PrivateArgumentParser(prog="session_heap_growth", description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--export-dir", help="New private work/coordination directory; build pinned parser, export and analyze")
    source.add_argument("--export-receipt", help="Explicit existing export receipt; verify and analyze read-only")
    parser.add_argument("--receipt", required=True, help="Explicit successful private session_memory_batch capture receipt")
    parser.add_argument("--expected-apk-sha256", required=True)
    parser.add_argument("--menus", nargs=2, type=int, required=True, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--top", type=int, default=20)
    previous_term = None
    try:
        args = parser.parse_args(argv)
        if args.menus[0] < 2 or args.menus[1] <= args.menus[0]:
            raise AnalysisError("invalid_menu_interval")
        if not 1 <= args.top <= 100:
            raise AnalysisError("invalid_top_count")
        pair = capture_pair(args.receipt, args.menus, args.expected_apk_sha256)
        export_receipt = args.export_receipt
        if args.export_dir:

            def interrupted(signum, frame):
                raise KeyboardInterrupt

            previous_term = signal.signal(signal.SIGTERM, interrupted)
            export_receipt = export_pair(args.receipt, pair, args.menus, args.expected_apk_sha256, args.export_dir)
        exports = read_export_pair(export_receipt, args.receipt, pair, args.menus, args.expected_apk_sha256)
        with database(exports[0][0]) as connection, exports[0][1].open() as root_lines:
            verify_export(connection, pair[0][0])
            before = summarize(connection, root_lines)
        with database(exports[1][0]) as connection, exports[1][1].open() as root_lines:
            verify_export(connection, pair[1][0])
            after = summarize(connection, root_lines)
        result = compare(before, after, args.menus, args.top)
    except AnalysisError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "heap_analysis_interrupted"}), file=sys.stderr)
        return 130
    except Exception:
        # Backend exceptions may include SQL values, input filenames or home paths.
        print(json.dumps({"error": "database_analysis_failed"}), file=sys.stderr)
        return 2
    finally:
        if previous_term is not None:
            signal.signal(signal.SIGTERM, previous_term)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
