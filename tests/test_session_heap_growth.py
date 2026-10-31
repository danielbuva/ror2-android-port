"""Synthetic exported heap graphs only; never load snapshots or game material."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import session_heap_growth as heap


def fixture(path=None, managed=(), native=(), edges=()):
    connection = sqlite3.connect(path or ":memory:")
    connection.executescript(
        "CREATE TABLE managed_objects (managed_object_index INTEGER, managed_type_name TEXT, size_bytes INTEGER, address INTEGER);"
        "CREATE TABLE native_objects (native_object_index INTEGER, native_type_name TEXT, name TEXT, size_bytes INTEGER);"
        "CREATE TABLE connections (from_kind TEXT, from_index INTEGER, to_kind TEXT, to_index INTEGER, connection_type TEXT);"
        "CREATE TABLE snapshot_info (snapshot_path TEXT);"
        "INSERT INTO snapshot_info VALUES ('PRIVATE_CAPTURE_PATH');"
    )
    connection.executemany("INSERT INTO managed_objects VALUES (?, ?, ?, 12345)", managed)
    connection.executemany("INSERT INTO native_objects VALUES (?, ?, 'PRIVATE_OBJECT_CONTENT', 999999)", native)
    connection.executemany("INSERT INTO connections VALUES (?, ?, ?, ?, ?)", edges)
    connection.commit()
    return connection


def edge(source, target):
    return "managed_object", source, "managed_object", target, "managed_reference"


def bridge(source, target):
    return "native_object", source, "managed_object", target, "native_gc_handle_bridge"


def summary(managed=(), native=(), edges=(), roots=None):
    connection = fixture(managed=managed, native=native, edges=edges)
    try:
        return heap.summarize(connection, roots)
    finally:
        connection.close()


def capture(root, before, after):
    evidence = root / "work/evidence"
    evidence.mkdir(parents=True)
    snapshots = {}
    for menu, database in ((2, before), (4, after)):
        name = "session-%d-%s.snap" % (menu, "b" * 32)
        path = evidence / name
        path.write_bytes(("authored synthetic snapshot menu %d" % menu).encode())
        snapshots[str(menu)] = {"file": name, "bytes": path.stat().st_size, "sha256": heap.file_sha256(path)}
        connection = sqlite3.connect(database)
        connection.execute("UPDATE snapshot_info SET snapshot_path = ?", (str(path),))
        connection.commit()
        connection.close()
    stage = {"success": True, "apk_sha256": "a" * 64, "runtime_errors": [], "failures": [], "memory_snapshots": snapshots}
    (evidence / "result.json").write_text(json.dumps(stage))
    receipt = root / "work/capture.json"
    receipt.write_text(json.dumps(dict(stage, mode="capture", stage_evidence="work/evidence")))
    return receipt


def arguments(export_receipt="export.json", receipt="capture.json"):
    return ["--export-receipt", str(export_receipt), "--menus", "2", "4", "--receipt", str(receipt), "--expected-apk-sha256", "a" * 64]


def copy_patches(root):
    for name in heap.PATCHES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(heap.REPOSITORY / name, target)


def export_fixture(root, before, after, receipt):
    copy_patches(root)
    output = root / "work/coordination/export"
    output.mkdir(parents=True)
    pair = heap.capture_pair(receipt, [2, 4], "a" * 64, root)
    entries = []
    for menu, database, (_, snapshot_hash) in zip((2, 4), (before, after), pair):
        target = output / ("menu-%d.db" % menu)
        shutil.copyfile(database, target)
        with sqlite3.connect(database) as connection:
            row = connection.execute("SELECT managed_object_index FROM managed_objects LIMIT 1").fetchone()
        roots = output / ("menu-%d.roots.log" % menu)
        roots.write_text("LAB_STATIC_ROOT %d PRIVATE_GENERATED_LABEL\n" % (row[0] if row else 0))
        entries.append(
            {
                "menu": menu,
                "snapshot_sha256": snapshot_hash,
                "database_file": target.name,
                "database_sha256": heap.file_sha256(target),
                "root_sidecar_file": roots.name,
                "root_sidecar_sha256": heap.file_sha256(roots),
            }
        )
    manifest = {
        "success": True,
        "generator": heap.EXPORT_GENERATOR,
        "parser_commit": heap.PARSER_PIN,
        "patch_sha256": heap.PATCH_HASHES,
        "capture_receipt_sha256": heap.file_sha256(receipt),
        "apk_sha256": "a" * 64,
        "menus": [2, 4],
        "exports": entries,
    }
    path = output / "export-receipt.json"
    path.write_text(json.dumps(manifest))
    return path


class SessionHeapGrowthTests(unittest.TestCase):
    def test_real_duckdb_backend_reads_synthetic_export_read_only(self):
        try:
            import duckdb
        except ImportError:
            if os.environ.get("CI"):
                self.fail("CI must install the pinned DuckDB lab requirement")
            self.skipTest("DuckDB dependency absent in this local environment")
        self.assertEqual(duckdb.__version__, "1.4.4")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "authored.duckdb"
            connection = duckdb.connect(str(path))
            connection.execute(
                "CREATE TABLE managed_objects(managed_object_index BIGINT, managed_type_name VARCHAR, size_bytes BIGINT);"
                "CREATE TABLE native_objects(native_object_index BIGINT, native_type_name VARCHAR, name VARCHAR);"
                "CREATE TABLE connections(from_kind VARCHAR, from_index BIGINT, to_kind VARCHAR, to_index BIGINT, connection_type VARCHAR);"
                "CREATE TABLE snapshot_info(snapshot_path VARCHAR);"
            )
            connection.executemany("INSERT INTO managed_objects VALUES (?, ?, ?)", [(0, "Fixture.Root", 32), (1, heap.PLAYER_STATS, 64)])
            connection.execute("INSERT INTO native_objects VALUES (0, 'Fixture.Native', 'PRIVATE_OBJECT_CONTENT')")
            connection.executemany("INSERT INTO connections VALUES (?, ?, ?, ?, ?)", [bridge(0, 0), edge(0, 1), edge(1, 0)])
            connection.execute("INSERT INTO snapshot_info VALUES (?)", [str(Path(temporary) / "authored.snap")])
            connection.close()
            before_hash = heap.file_sha256(path)
            with heap.database(path) as connection:
                result = heap.summarize(connection, ["LAB_STATIC_ROOT 0 PRIVATE_FIELD_LABEL"])
                heap.verify_export(connection, Path(temporary) / "authored.snap")
                with self.assertRaises(duckdb.Error):
                    connection.execute("DELETE FROM managed_objects")
            self.assertEqual(result["total"], (2, 96))
            self.assertEqual(result["roots"], {("STATIC_ROOT", "Fixture.Root"): (2, 96)})
            self.assertEqual(result["root_paths"]["targets_with_proven_root_path"], 1)
            self.assertNotIn("PRIVATE", json.dumps(heap.compare(summary(), result, [2, 4])))
            self.assertEqual(heap.file_sha256(path), before_hash)

    def test_growth_joins_type_names_not_reused_indices(self):
        before = summary([(0, "Fixture.Stats", 100), (1, "Fixture.Old", 300)])
        after = summary([(0, "Fixture.New", 80), (9, "Fixture.Stats", 220)])
        report = heap.compare(before, after, [2, 4])
        self.assertEqual(report["managed_total"]["growth_bytes"], -100)
        self.assertEqual(report["managed_endpoint_delta_bytes_per_session"], -50)
        self.assertEqual([row["type"] for row in report["top_managed_type_growth"]], ["Fixture.Stats", "Fixture.New"])
        self.assertEqual(report["top_managed_type_growth"][0]["growth_bytes"], 120)
        self.assertEqual(report["top_managed_type_growth"][0]["growth_count"], 0)

    def test_cycles_duplicate_edges_and_multiple_roots_in_same_type_count_once(self):
        result = summary(
            [(1, "Fixture.Root", 10), (2, "Fixture.Array", 100)],
            [(0, "Fixture.Native"), (1, "Fixture.Native")],
            [bridge(0, 1), bridge(0, 1), bridge(1, 2), edge(1, 2), edge(2, 1)],
        )
        self.assertEqual(result["total"], (2, 110))
        self.assertEqual(result["native_bridges"], {"Fixture.Native": (2, 110)})

    def test_shared_descendants_overlap_between_bridge_types(self):
        result = summary(
            [(1, "Fixture.Root", 10), (2, "Fixture.Shared", 100), (3, "Fixture.Other", 20)],
            [(0, "Fixture.NativeA"), (1, "Fixture.NativeB")],
            [bridge(0, 1), bridge(1, 3), edge(1, 2), edge(3, 2)],
        )
        self.assertEqual(result["native_bridges"], {"Fixture.NativeA": (2, 110), "Fixture.NativeB": (2, 120)})
        report = heap.compare(summary(), result, [2, 4])
        self.assertTrue(report["native_bridge_groups_overlap"])
        self.assertFalse(report["exclusive_retained_size_available"])

    def test_native_paths_are_followed_but_native_bytes_are_not_managed_bytes(self):
        result = summary(
            [(1, "Fixture.Wrapper", 10), (2, "Fixture.Other", 20)],
            [(0, "Fixture.NativeA"), (1, "Fixture.NativeB")],
            [bridge(0, 1), ("managed_object", 1, "native_object", 1, "managed_native_bridge"), bridge(1, 2)],
        )
        self.assertEqual(result["native_bridges"]["Fixture.NativeA"], (2, 30))

    def test_no_inferred_gc_or_static_roots_from_zero_indegree(self):
        result = summary([(0, "Fixture.ZeroIndegree", 200)])
        report = heap.compare(summary(), result, [2, 4])
        self.assertEqual(report["top_native_bridge_reachable_growth"], [])
        self.assertFalse(report["gc_static_root_attribution_available"])
        self.assertIn("not_acceptance", report["scope"])

    def test_deterministic_growth_ties_and_limit(self):
        after = summary([(0, "Fixture.B", 100), (1, "Fixture.A", 100), (2, "Fixture.C", 50)])
        self.assertEqual([row["type"] for row in heap.compare(summary(), after, [2, 4], 2)["top_managed_type_growth"]], ["Fixture.A", "Fixture.B"])

    def test_same_heap_has_no_positive_growth(self):
        result = summary([(0, "Fixture.Stable", 400)])
        report = heap.compare(result, result, [2, 4])
        self.assertEqual(report["top_managed_type_growth"], [])
        self.assertEqual(report["managed_total"]["growth_bytes"], 0)

    def test_root_growth_is_ranked_by_descendant_bytes_not_number_of_bridges(self):
        before = summary([(0, "Fixture.Stats", 10)], [(0, "Fixture.Native")], [bridge(0, 0)])
        after = summary([(0, "Fixture.Stats", 10), (1, "Fixture.Array", 900)], [(0, "Fixture.Native")], [bridge(0, 0), edge(0, 1)])
        row = heap.compare(before, after, [2, 4])["top_native_bridge_reachable_growth"][0]
        self.assertEqual((row["type"], row["growth_count"], row["growth_bytes"]), ("Fixture.Native", 1, 900))

    def test_large_graph_uses_iterative_walk(self):
        count = 4000
        result = summary([(i, "Fixture.Link", 8) for i in range(count)], [(0, "Fixture.Native")], [bridge(0, 0)] + [edge(i, i + 1) for i in range(count - 1)])
        self.assertEqual(result["native_bridges"]["Fixture.Native"], (count, count * 8))

    def test_only_type_names_are_printed_and_invalid_names_are_not_echoed(self):
        synthetic_contact = "user" + "@" + "example.test"
        result = summary(
            [(0, "Fixture.Safe[]", 20), (1, "PRIVATE/PATH", 50), (2, "PRIVATE\nCONTENTS", 60), (3, synthetic_contact, 70)],
            [(0, "Fixture.Native")],
            [bridge(0, 0)],
        )
        output = json.dumps(heap.compare(summary(), result, [2, 4]))
        for private in ("PRIVATE", "example.test", "12345", "999999"):
            self.assertNotIn(private, output)
        self.assertIn("Fixture.Safe[]", output)
        self.assertIn(heap.UNKNOWN_TYPE, output)

    def test_generic_compiler_generated_and_nested_type_names(self):
        for value in ("System.Collections.Generic.List`1[Fixture.Stat]", "Fixture.Owner+<Run>d__1", "Fixture.Item[,]"):
            self.assertEqual(heap.type_name(value), value)

    def test_bad_edges_and_sizes_refuse_without_partial_result(self):
        for managed, edges in (
            ([(0, "Fixture.Bad", -1)], []),
            ([(0, "Fixture.Bad", 10)], [edge(0, 1)]),
            ([(0, "Fixture.Bad", 10)], [("unknown", 0, "managed_object", 0, "bad")]),
            ([(0, "Fixture.Bad", 10), (0, "Fixture.Bad", 10)], []),
        ):
            with self.subTest(managed=managed, edges=edges), self.assertRaises(heap.AnalysisError):
                summary(managed, edges=edges)

    def test_menu_indices_and_top_are_explicit(self):
        empty = summary()
        for menus in ([1, 4], [4, 2], [2, 2], [True, 4], [2]):
            with self.assertRaises(heap.AnalysisError):
                heap.compare(empty, empty, menus)
        for top in (0, 101, True):
            with self.assertRaises(heap.AnalysisError):
                heap.compare(empty, empty, [2, 4], top)

    def test_database_is_read_only_and_missing_file_is_not_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.db"
            fixture(path).close()
            with heap.database(path) as connection:
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("DELETE FROM managed_objects")
            missing = Path(temporary) / "missing.db"
            with self.assertRaises(heap.AnalysisError):
                with heap.database(missing):
                    pass
            self.assertFalse(missing.exists())

    def test_cli_is_path_free_and_does_not_modify_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            before, after = (Path(temporary) / name for name in ("PRIVATE_BEFORE.db", "PRIVATE_AFTER.db"))
            fixture(before, managed=[(0, "Fixture.Stats", 10)]).close()
            fixture(after, managed=[(1, "Fixture.Stats", 50)]).close()
            receipt = capture(Path(temporary), before, after)
            export_receipt = export_fixture(Path(temporary), before, after, receipt)
            hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (before, after)]
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr), mock.patch.object(heap, "REPOSITORY", Path(temporary)):
                status = heap.main(arguments(export_receipt, receipt))
            self.assertEqual(status, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertNotIn("PRIVATE", stdout.getvalue())
            self.assertNotIn(temporary, stdout.getvalue())
            self.assertEqual(json.loads(stdout.getvalue())["managed_total"]["growth_bytes"], 40)
            self.assertEqual(hashes, [hashlib.sha256(path.read_bytes()).hexdigest() for path in (before, after)])

    def test_cli_errors_do_not_echo_arguments_or_backend_exception_content(self):
        for argv in (["PRIVATE_ARGUMENT"], arguments("PRIVATE_PATH", "OTHER_PRIVATE_PATH")):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = heap.main(argv)
            self.assertEqual(status, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn("PRIVATE", stderr.getvalue())
        with (
            mock.patch.object(heap, "database", side_effect=RuntimeError("PRIVATE_BACKEND_VALUE")),
            mock.patch.object(heap, "capture_pair", return_value=[(None, ""), (None, "")]),
            mock.patch.object(heap, "read_export_pair", return_value=[(Path("a.db"), Path("a.log")), (Path("b.db"), Path("b.log"))]),
        ):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(heap.main(arguments()), 2)
            self.assertEqual(json.loads(stderr.getvalue()), {"error": "database_analysis_failed"})

    def test_only_explicit_snapshot_roots_produce_type_paths_and_labels_are_discarded(self):
        result = summary(
            [(0, "Fixture.Root", 10), (1, "Fixture.Link", 20), (2, heap.PLAYER_STATS, 30)],
            edges=[edge(0, 1), edge(1, 2), edge(2, 1)],
            roots=["PRIVATE_LOG_CONTENT", "LAB_STATIC_ROOT 0 PRIVATE/address/0x1234", "LAB_GC_HANDLE_ROOT 0 PRIVATE_HANDLE_VALUE"],
        )
        report = heap.compare(summary(), result, [2, 4])
        self.assertTrue(report["gc_static_root_attribution_available"])
        self.assertIsNone(report["top_gc_static_root_reachable_growth"])
        paths = report["after_player_stats_root_paths"]
        self.assertEqual(paths["targets_with_proven_root_path"], 1)
        self.assertEqual(paths["truncated_target_walks"], 0)
        self.assertEqual(len(paths["paths"]), 2)
        self.assertEqual(paths["paths"][0]["path_types"], ["Fixture.Root", "Fixture.Link", heap.PLAYER_STATS])
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertNotIn("0x1234", json.dumps(report))

    def test_root_growth_matches_kind_and_type_across_snapshot_local_indices(self):
        before = summary([(0, "Fixture.Root", 10), (1, heap.PLAYER_STATS, 30)], edges=[edge(0, 1)], roots=["LAB_STATIC_ROOT 0 field"])
        after = summary(
            [(8, "Fixture.Root", 10), (9, heap.PLAYER_STATS, 30), (10, "Fixture.Array", 600)],
            edges=[edge(8, 9), edge(9, 10)],
            roots=["LAB_STATIC_ROOT 8 field"],
        )
        growth = heap.compare(before, after, [2, 4])["top_gc_static_root_reachable_growth"]
        self.assertEqual(len(growth), 1)
        self.assertEqual((growth[0]["type"], growth[0]["root_kind"], growth[0]["growth_bytes"]), ("Fixture.Root", "STATIC_ROOT", 600))

    def test_missing_and_out_of_snapshot_root_indices_are_not_inferred(self):
        for roots in ([], ["LAB_STATIC_ROOT 999 label"], ["LAB_STATIC_ROOT -1 label"], ["Graph entry 0"]):
            with self.assertRaises(heap.AnalysisError):
                summary([(0, heap.PLAYER_STATS, 30)], roots=roots)

    def test_root_walk_limits_report_incomplete_instead_of_root_absence(self):
        objects = {i: ("Fixture.Link" if i else heap.PLAYER_STATS, 10) for i in range(30)}
        edges = {i: {i - 1} for i in range(1, 30)}
        for depth, visits in ((24, 100000), (24, 5)):
            result = heap.root_paths(objects, edges, {29: {"STATIC_ROOT"}}, depth, visits)
            self.assertEqual(result["targets_with_proven_root_path"], 0)
            self.assertEqual(result["truncated_target_walks"], 1)
            self.assertLessEqual(result["largest_visited_count"], visits)

    def test_capture_and_export_identity_are_hash_and_path_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before, after = root / "before.db", root / "after.db"
            fixture(before).close()
            fixture(after).close()
            receipt = capture(root, before, after)
            pair = heap.capture_pair(receipt, [2, 4], "a" * 64, root)
            with heap.database(before) as connection:
                heap.verify_export(connection, pair[0][0])
                with self.assertRaisesRegex(heap.AnalysisError, "binding_mismatch"):
                    heap.verify_export(connection, pair[1][0])
            with self.assertRaises(heap.AnalysisError):
                heap.capture_pair(receipt, [2, 4], "f" * 64, root)
            pair[1][0].write_bytes(b"changed synthetic bytes")
            with self.assertRaisesRegex(heap.AnalysisError, "hash_mismatch"):
                heap.capture_pair(receipt, [2, 4], "a" * 64, root)

    def test_measure_or_failed_capture_cannot_become_heap_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before, after = root / "before.db", root / "after.db"
            fixture(before).close()
            fixture(after).close()
            receipt = capture(root, before, after)
            original = json.loads(receipt.read_text())
            for changes in ({"mode": "measure"}, {"success": False}):
                receipt.write_text(json.dumps(dict(original, **changes)))
                with self.assertRaisesRegex(heap.AnalysisError, "matching_capture_required"):
                    heap.capture_pair(receipt, [2, 4], "a" * 64, root)

    def test_cli_does_not_accept_unproven_runtime_root_sidecar(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(heap.main(arguments() + ["--after-roots", "PRIVATE_LOG"]), 2)
        self.assertEqual(json.loads(stderr.getvalue()), {"error": "invalid_arguments"})

    def test_verified_export_files_and_generator_must_match_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before, after = root / "before.db", root / "after.db"
            fixture(before, managed=[(0, "Fixture.Root", 10)]).close()
            fixture(after, managed=[(7, "Fixture.Root", 20)]).close()
            receipt = capture(root, before, after)
            exported = export_fixture(root, before, after, receipt)
            pair = heap.capture_pair(receipt, [2, 4], "a" * 64, root)
            files = heap.read_export_pair(exported, receipt, pair, [2, 4], "a" * 64, root)
            original = json.loads(exported.read_text())
            for changes in (
                {"generator": "runtime_reflection_walk"},
                {"parser_commit": "b" * 40},
                {"capture_receipt_sha256": "b" * 64},
                {"patch_sha256": {}},
                {"success": False},
                {"menus": [4, 2]},
                {"apk_sha256": "b" * 64},
            ):
                exported.write_text(json.dumps(dict(original, **changes)))
                with self.assertRaisesRegex(heap.AnalysisError, "provenance_mismatch"):
                    heap.read_export_pair(exported, receipt, pair, [2, 4], "a" * 64, root)
            exported.write_text(json.dumps(original))
            for selected in files[1]:
                prior = selected.read_bytes()
                selected.write_bytes(prior + b"changed authored fixture")
                with self.assertRaisesRegex(heap.AnalysisError, "file_hash_mismatch"):
                    heap.read_export_pair(exported, receipt, pair, [2, 4], "a" * 64, root)
                selected.write_bytes(prior)
            original["exports"][1]["snapshot_sha256"] = pair[0][1]
            exported.write_text(json.dumps(original))
            with self.assertRaisesRegex(heap.AnalysisError, "snapshot_binding_mismatch"):
                heap.read_export_pair(exported, receipt, pair, [2, 4], "a" * 64, root)

    def test_root_paths_obey_requested_output_limit_without_hiding_walk_coverage(self):
        result = summary(
            [(0, "Fixture.A", 1), (1, "Fixture.B", 1), (2, "Fixture.C", 1), (3, heap.PLAYER_STATS, 30)],
            edges=[edge(0, 3), edge(1, 3), edge(2, 3)],
            roots=["LAB_STATIC_ROOT %d field" % i for i in range(3)],
        )
        paths = heap.compare(summary(), result, [2, 4], top=2)["after_player_stats_root_paths"]
        self.assertEqual(len(paths["paths"]), 2)
        self.assertEqual(paths["omitted_path_count"], 1)
        self.assertEqual(paths["targets_with_proven_root_path"], 1)


class SessionHeapExporterTests(unittest.TestCase):
    def setup_inputs(self, root):
        copy_patches(root)
        before, after = root / "before.db", root / "after.db"
        fixture(before).close()
        fixture(after).close()
        receipt = capture(root, before, after)
        pair = heap.capture_pair(receipt, [2, 4], "a" * 64, root)
        return receipt, pair

    def fake_command(self, calls, fail_build=False):
        def run(argv, cwd, stdout, stderr, timeout=3600):
            argv = list(map(str, argv))
            calls.append((argv, Path(cwd)))
            Path(stderr).write_text("")
            if "archive" in argv:
                with tarfile.open(stdout, "w") as archive:
                    payload = b"authored parser project placeholder"
                    member = tarfile.TarInfo("Cli/README.txt")
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            else:
                Path(stdout).write_text("PRIVATE_BUILD_OR_EXPORT_OUTPUT")
            if "build" in argv and fail_build:
                raise heap.AnalysisError("private_export_command_failed")
            if "export" in argv:
                index = argv.index("export")
                snapshot, database = Path(argv[index + 1]), Path(argv[index + 2])
                database.write_bytes(b"authored exported database fixture " + snapshot.read_bytes())
                Path(stderr).write_text("LAB_STATIC_ROOT 7 PRIVATE_SOURCE_FIELD\nLAB_GC_HANDLE_ROOT 7 12345\n")

        return run

    def test_export_archives_exact_pin_applies_both_checked_patches_and_binds_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt, pair = self.setup_inputs(root)
            calls = []
            with mock.patch.object(heap, "command", side_effect=self.fake_command(calls)):
                exported = heap.export_pair(receipt, pair, [2, 4], "a" * 64, "work/coordination/export", root)
            manifest = json.loads(exported.read_text())
            self.assertTrue(manifest["success"])
            self.assertEqual(manifest["parser_commit"], heap.PARSER_PIN)
            self.assertEqual(manifest["patch_sha256"], heap.PATCH_HASHES)
            self.assertEqual(manifest["capture_receipt_sha256"], heap.file_sha256(receipt))
            self.assertEqual(calls[0][0], ["git", "-C", str(root / heap.PARSER_REFERENCE), "archive", "--format=tar", heap.PARSER_PIN])
            patch_calls = [args for args, _ in calls if args[:2] == ["git", "apply"]]
            self.assertEqual(len(patch_calls), 4)
            self.assertEqual(["--check" in args for args in patch_calls], [True, False, True, False])
            self.assertTrue(all("--unidiff-zero" in args for args in patch_calls))
            builds = [args for args, _ in calls if "build" in args]
            self.assertEqual(len(builds), 1)
            self.assertIn("--disable-build-servers", builds[0])
            self.assertIn("DOTNET_CLI_TELEMETRY_OPTOUT=1", builds[0][2])
            exports = [args for args, _ in calls if "export" in args]
            self.assertEqual(len(exports), 2)
            self.assertTrue(all("--no-build" in args and "minimal" in args for args in exports))
            self.assertEqual(len(heap.read_export_pair(exported, receipt, pair, [2, 4], "a" * 64, root)), 2)
            self.assertFalse(list(exported.parent.glob("parser-*")))
            self.assertFalse((root / heap.PARSER_REFERENCE).exists())

    def test_failed_build_retains_failed_receipt_and_logs_but_removes_owned_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt, pair = self.setup_inputs(root)
            with mock.patch.object(heap, "command", side_effect=self.fake_command([], fail_build=True)), self.assertRaises(heap.AnalysisError):
                heap.export_pair(receipt, pair, [2, 4], "a" * 64, "work/coordination/export", root)
            out = root / "work/coordination/export"
            self.assertFalse(json.loads((out / "export-receipt.json").read_text())["success"])
            self.assertTrue((out / "build.stdout").is_file())
            self.assertFalse(list(out.glob("parser-*")))

    def test_export_refuses_existing_output_and_changed_reviewed_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt, pair = self.setup_inputs(root)
            out = root / "work/coordination/export"
            out.mkdir(parents=True)
            with mock.patch.object(heap, "command") as commands:
                with self.assertRaisesRegex(heap.AnalysisError, "new_export_directory"):
                    heap.export_pair(receipt, pair, [2, 4], "a" * 64, out, root)
                (root / heap.PATCHES[1]).write_text("changed authored patch")
                with self.assertRaisesRegex(heap.AnalysisError, "reviewed_parser_patches"):
                    heap.export_pair(receipt, pair, [2, 4], "a" * 64, "work/coordination/other", root)
                commands.assert_not_called()

    def test_export_requires_snapshot_index_root_output_from_exporter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt, pair = self.setup_inputs(root)
            base = self.fake_command([])

            def no_roots(argv, cwd, stdout, stderr, timeout=3600):
                base(argv, cwd, stdout, stderr, timeout)
                if "export" in argv:
                    Path(stderr).write_text("runtime reflection index 7 is not a snapshot root")

            with mock.patch.object(heap, "command", side_effect=no_roots), self.assertRaisesRegex(heap.AnalysisError, "root_sidecar_missing"):
                heap.export_pair(receipt, pair, [2, 4], "a" * 64, "work/coordination/export", root)

    def test_command_failure_or_timeout_reaps_only_its_new_process_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for waits in ([0, 0], [2, 0], [subprocess.TimeoutExpired("fixture", 1), 0, 0]):
                child = mock.Mock(pid=12345)
                child.wait.side_effect = waits
                with mock.patch.object(heap.subprocess, "Popen", return_value=child) as launch, mock.patch.object(heap.os, "killpg") as kill:
                    if waits[0] == 0:
                        heap.command(["authored-command"], root, root / "out", root / "err", 1)
                    else:
                        with self.assertRaises((heap.AnalysisError, subprocess.TimeoutExpired)):
                            heap.command(["authored-command"], root, root / "out", root / "err", 1)
                    self.assertTrue(launch.call_args.kwargs["start_new_session"])
                    kill.assert_called_with(12345, signal.SIGKILL)

    def test_cli_interruption_restores_signal_handler_and_prints_no_private_exception(self):
        original = signal.getsignal(signal.SIGTERM)
        argv = arguments()
        argv[:2] = ["--export-dir", "work/coordination/export"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(heap, "capture_pair", return_value=[]), mock.patch.object(heap, "export_pair", side_effect=KeyboardInterrupt("PRIVATE")):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(heap.main(argv), 130)
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
        self.assertEqual(json.loads(stderr.getvalue()), {"error": "heap_analysis_interrupted"})


if __name__ == "__main__":
    unittest.main()
