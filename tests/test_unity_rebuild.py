"""R9 host contracts: subprocess is mocked; no Unity or device is contacted."""

from contextlib import ExitStack
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build
import build_entry_rebuild
import composition_io
import rebuild
import unity_rebuild as r9
import whole_catalog
from common import read, sha, write


class UnityRebuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / "shared-work"
        self.dest = self.root / "work/rebuild/input/lab-project"
        self.dest.mkdir(parents=True)
        self.input_id = "a" * 64
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "receipts/provenance-map.json", {})
        for name in (
            "lab-project/Library/keep",
            "config/current-build.json",
            "device/installed.json",
            "build-cache/known/result.json",
            "generated-android-data/keep",
        ):
            p = self.work / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("protected")
        write(self.dest / ".rebuild/catalog-inputs/integration-latest.json", dict(path="destination/.rebuild/catalog-inputs/integration/one"))
        write(self.dest / ".rebuild/catalog-inputs/integration/one/manifest.json", dict(input_id=self.input_id, attempt="integration-pinned", locations=[]))
        write(self.dest / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json", dict(input_id=self.input_id, attempt="integration-pinned"))
        write(self.dest / ".rebuild/composition/scene-probe-build.json", dict(scene="Assets/example"))
        baseline = self.root / "smoke/ProjectSettings/ProjectSettings.asset"
        baseline.parent.mkdir(parents=True)
        baseline.write_text("public baseline")
        (self.dest / "ProjectSettings").mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for module in (r9, rebuild, build, composition_io):
            self.stack.enter_context(patch.object(module, "ROOT", self.root))
        self.stack.enter_context(patch.dict(r9.os.environ, {"UNITY_EDITOR": "/pinned/Unity"}))
        self.stack.enter_context(patch.object(composition_io.StageIO, "preflight"))
        self.stack.enter_context(patch.object(build_entry_rebuild, "validate_bindings", return_value={"equal": True}))
        self.source_validator = build.validate_staged_runtime_sources
        for name in ("validate_staged_runtime_sources",):
            self.stack.enter_context(patch.object(build, name))
        key = self.root / ".local/android-user/.android/debug.keystore"
        key.parent.mkdir(parents=True)
        key.write_bytes(b"synthetic signing fixture")
        self.before = self.snapshot()

    def snapshot(self):
        return {str(p.relative_to(self.work)): p.read_bytes() for p in self.work.rglob("*") if p.is_file()}

    def fake_run(self, command, **kwargs):
        if command[0] == "/bin/ps":
            return SimpleNamespace(stdout=b"", returncode=0)
        self.assertEqual(command[command.index("-projectPath") + 1], str(self.dest))
        self.assertNotIn("-cacheServerEndpoint", command)
        self.assertEqual(kwargs["cwd"], self.dest)
        scratch = Path(command[command.index("-labWorkRoot") + 1])
        self.assertTrue(scratch.is_relative_to(self.dest))
        self.assertTrue(Path(kwargs["env"]["GRADLE_USER_HOME"]).is_relative_to(scratch))
        manifest = read(scratch / "experiments/whole-catalog/manifest.json")
        write(scratch / "generated-android-data/whole-catalog.json", dict(manifest, bundles={}))
        request = read(scratch / "build-request.json")
        self.assertEqual((Path(kwargs["env"]["ANDROID_USER_HOME"]) / "debug.keystore").read_bytes(), b"synthetic signing fixture")
        self.assertFalse(request["reusePayload"])
        self.assertEqual(request["api"], "vulkan")
        apk = scratch / "lab-build/lab-vulkan.apk"
        self.zip(apk, {"assets/bin/Data/level0": b"fresh"})
        write(scratch / "lab-build/result.json", dict(success=True, errors=0, request_id=request["request_id"], apk=str(apk)))
        return SimpleNamespace(returncode=0)

    @staticmethod
    def zip(path, files, timestamp=(2025, 1, 1, 0, 0, 0)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in files.items():
                archive.writestr(zipfile.ZipInfo(name, timestamp), content)

    def test_shared_entry_point_builds_full_content_and_keeps_all_live_bytes(self):
        with patch.object(r9, "run", side_effect=self.fake_run):
            result = whole_catalog.build_integration(destination=self.dest, work=self.work)
        self.assertEqual(result["apk_sha256"], sha(result["apk"]))
        self.assertTrue(Path(result["payload_directory"]).is_relative_to(self.dest))
        payload = read(Path(result["payload_directory"]) / "whole-catalog.json")
        bootstrap = read(self.dest / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json")
        self.assertEqual(payload["attempt"], bootstrap["attempt"])
        self.assertEqual(self.before, self.snapshot())
        self.assertFalse((self.dest / ".rebuild/unity-build.lock").exists())
        self.assertEqual((self.dest / "ProjectSettings/ProjectSettings.asset").read_text(), "public baseline")

    def test_destination_rejects_code_only_before_any_mutation(self):
        with patch.object(r9, "execute_build") as execute:
            with self.assertRaisesRegex(RuntimeError, "payload reuse"):
                whole_catalog.build_integration(code_only=True, destination=self.dest, work=self.work)
            execute.assert_not_called()

    def test_manifest_bootstrap_mismatch_fails_both_r9_entry_points_before_unity(self):
        bootstrap = self.dest / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json"
        for identity in (
            dict(input_id=self.input_id, attempt="integration-stale"),
            dict(input_id="wrong", attempt="integration-pinned"),
            dict(input_id=self.input_id),
        ):
            write(bootstrap, identity)
            with patch.object(r9, "run", return_value=SimpleNamespace(stdout=b"")) as run:
                for invoke in (lambda: r9.preflight_destination(self.dest, self.work), lambda: r9.execute_build(self.dest, self.work, "vulkan")):
                    with self.assertRaisesRegex(RuntimeError, "manifest/bootstrap"):
                        invoke()
                self.assertTrue(all(call.args[0][0] == "/bin/ps" for call in run.call_args_list))
            self.assertFalse((self.dest / ".rebuild/unity").exists())
        bootstrap.unlink()
        with self.assertRaises(FileNotFoundError):
            r9.destination_manifest(self.dest, self.input_id)

    def test_refuses_destination_and_working_editors_and_stale_project_locks(self):
        for project in (self.dest, self.work / "lab-project", self.root / "work/lab-project"):
            for spelling in (str(project), '"' + str(project) + '"'):
                with patch.object(r9, "run", return_value=SimpleNamespace(stdout=("/Editor/Unity -projectPath " + spelling).encode())):
                    with self.assertRaisesRegex(RuntimeError, "Close"):
                        r9.refuse_open_editors(self.dest, self.work)
            lock = project / "Temp/UnityLockfile"
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.touch()

            def holder(pids):
                return lambda command, **kwargs: SimpleNamespace(stdout=pids if command[0] == "/usr/sbin/lsof" else b"", returncode=0)

            with patch.object(r9, "run", side_effect=holder(b"4242\n")), self.assertRaisesRegex(RuntimeError, "UnityLockfile held"):
                r9.refuse_open_editors(self.dest, self.work)
            # A lock no process holds is left in place and does not block.
            with patch.object(r9, "run", side_effect=holder(b"")):
                r9.refuse_open_editors(self.dest, self.work)
            self.assertTrue(lock.exists())
            lock.unlink()

    def test_folder_importers_differ_only_by_minted_guid_or_absent_empty_folder(self):
        project = self.work / "lab-project"
        body = "fileFormatVersion: 2\nguid: {}\nfolderAsset: yes\nDefaultImporter:\n  userData: \n"
        for root, guid in ((project, "1" * 32), (self.dest, "2" * 32)):
            (root / "Assets/Kept").mkdir(parents=True, exist_ok=True)
            (root / "Assets/Kept/file.txt").write_text("x")
            (root / "Assets/Kept.meta").write_text(body.format(guid))
        (project / "Assets/Empty").mkdir()
        (project / "Assets/Empty.meta").write_text(body.format("3" * 32))
        (project / "Assets/Full").mkdir()
        (project / "Assets/Full/file.txt").write_text("x")
        (project / "Assets/Full.meta").write_text(body.format("4" * 32))
        (self.dest / "Assets/Edited").mkdir()
        (project / "Assets/Edited").mkdir()
        (project / "Assets/Edited/file.txt").write_text("x")
        (project / "Assets/Edited.meta").write_text(body.format("5" * 32))
        (self.dest / "Assets/Edited.meta").write_text(body.format("6" * 32).replace("yes", "no"))
        paths = {"Assets/Kept.meta", "Assets/Empty.meta", "Assets/Full.meta", "Assets/Edited.meta"}
        rows = {row["path"]: row["status"] for row in r9.compare_files(self.dest, project, paths, {p: dict(sha256="0" * 64) for p in paths})["rows"]}
        self.assertEqual(
            rows,
            {
                "Assets/Kept.meta": "folder_guid_minted",
                "Assets/Empty.meta": "empty_folder_absent",
                "Assets/Full.meta": "different",
                "Assets/Edited.meta": "different",
            },
        )
        references = r9.minted_folder_references(self.dest)
        self.assertEqual(references["referencing_files"], 0)
        (self.dest / "Assets/Ref.prefab").write_text("%YAML 1.1\nfolder: {guid: " + "2" * 32 + "}\n")
        self.assertEqual(r9.minted_folder_references(self.dest)["referencing_files"], 1)

    def test_lock_excludes_second_r9_and_is_removed_after_failure(self):
        with self.assertRaisesRegex(RuntimeError, "fixture"):
            with r9.build_lock(self.dest):
                with self.assertRaisesRegex(RuntimeError, "already active"):
                    with r9.build_lock(self.dest):
                        self.fail("concurrent build")
                raise RuntimeError("fixture")
        self.assertFalse((self.dest / ".rebuild/unity-build.lock").exists())

    def test_failure_retains_run_without_publishing_success(self):
        def fail(command, **kwargs):
            if command[0] == "/bin/ps":
                return SimpleNamespace(stdout=b"")
            return SimpleNamespace(returncode=1)

        with patch.object(r9, "run", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "no terminal receipt"):
                build.build("vulkan", destination=self.dest, work=self.work)
        self.assertEqual(len(list((self.dest / ".rebuild/unity").glob("*/invocation.json"))), 1)
        self.assertEqual(self.before, self.snapshot())

    def test_timeout_releases_lock_preserves_evidence(self):
        def timeout(command, **kwargs):
            if command[0] == "/bin/ps":
                return SimpleNamespace(stdout=b"")
            raise subprocess.TimeoutExpired(command, 14400)

        with patch.object(r9, "run", side_effect=timeout):
            with self.assertRaises(subprocess.TimeoutExpired):
                build.build("vulkan", destination=self.dest, work=self.work)
        self.assertFalse((self.dest / ".rebuild/unity-build.lock").exists())
        self.assertEqual(self.before, self.snapshot())

    def test_manifest_cannot_follow_live_pointer(self):
        write(self.dest / ".rebuild/catalog-inputs/integration-latest.json", dict(path="work/experiments/old"))
        with patch.object(r9, "run", side_effect=self.fake_run):
            with self.assertRaisesRegex(RuntimeError, "regenerated R3"):
                build.build("vulkan", destination=self.dest, work=self.work)

    def test_wrong_request_and_external_apk_fail_closed(self):
        for kind in ("request", "path", "errors"):

            def invalid(command, **kwargs):
                process = self.fake_run(command, **kwargs)
                if command[0] != "/bin/ps":
                    scratch = Path(command[command.index("-labWorkRoot") + 1])
                    path = scratch / "lab-build/result.json"
                    result = read(path)
                    if kind == "request":
                        result["request_id"] = "stale"
                    elif kind == "path":
                        result["apk"] = str(self.work / "known.apk")
                    else:
                        result["errors"] = 1
                    write(path, result)
                return process

            with self.subTest(kind=kind), patch.object(r9, "run", side_effect=invalid):
                with self.assertRaises(RuntimeError):
                    build.build("vulkan", destination=self.dest, work=self.work)

    def test_reference_is_baseline_hash_not_merely_current_build(self):
        apk = self.work / "known.apk"
        apk.write_bytes(b"device verified")
        (self.root / "docs").mkdir()
        (self.root / "docs/BASELINE.md").write_text("| APK | `" + sha(apk) + "` |")
        write(self.work / "config/current-build.json", dict(apk=str(apk), apk_sha256="f" * 64))
        write(self.work / "device/installed.json", dict(apk=str(apk), apk_sha256=sha(apk)))
        self.assertEqual(r9.reference_apk(self.work), apk)
        apk.write_bytes(b"corrupt")
        with self.assertRaisesRegex(RuntimeError, "missing or changed"):
            r9.reference_apk(self.work)

    def test_hash_comparison_keeps_missing_and_provenance_drift(self):
        project = self.work / "lab-project"
        (self.dest / "same").write_bytes(b"same")
        (project / "same").write_bytes(b"same")
        (self.dest / "changed").write_bytes(b"new")
        (project / "changed").write_bytes(b"old")
        rows = {name: dict(sha256="f" * 64) for name in ("same", "changed", "missing")}
        result = r9.compare_files(self.dest, project, rows, rows)
        self.assertEqual(result["counts"], dict(identical=1, folder_guid_minted=0, empty_folder_absent=0, different=2))
        self.assertFalse(result["rows"][-1]["provenance_matches"])

    def test_apk_comparison_reports_all_entries_and_metadata_without_normalization(self):
        a, b = self.root / "a.apk", self.root / "b.apk"
        self.zip(a, {"same": b"same", "assets/bin/Data/level0": b"new", "extra": b"x", "unknown": b"new"})
        self.zip(b, {"same": b"same", "assets/bin/Data/level0": b"old", "missing": b"x", "unknown": b"old"}, (2024, 1, 1, 0, 0, 0))
        result = r9.compare_apks(a, b)
        self.assertEqual(result["counts"], dict(identical=1, different=2, added=1, missing=1))
        rows = {row["name"]: row for row in result["entries"]}
        self.assertTrue(rows["same"]["zip_metadata_different"])
        self.assertEqual(rows["assets/bin/Data/level0"]["classification"], "unexplained-scene-difference")
        self.assertIn("parser_error", rows["assets/bin/Data/level0"]["detail"])
        self.assertEqual(rows["unknown"]["classification"], "unexplained-content-difference")
        self.assertNotEqual(rows["unknown"]["destination"]["sha256"], rows["unknown"]["reference"]["sha256"])

    def test_coordinator_compares_all_three_groups_and_saves_destination_receipt(self):
        paths = ["settings", "link", "graph", "generated"]
        provenance = {p: dict(producer="unity-generated" if p in paths[2:] else "unknown", sha256="f" * 64) for p in paths}
        importer = next(iter(rebuild.IMPORTER_PATHS))
        provenance[importer] = dict(producer="unity-generated", sha256="f" * 64)
        apk = self.dest / "output.apk"
        self.zip(apk, {"same": b"same"})
        bindings = dict(equal=True, r9_obligations={p: {} for p in paths[:2]}, unity_import_deferred=["graph"])
        with (
            patch.object(build_entry_rebuild, "validate_bindings", return_value=bindings),
            patch.object(r9, "reference_apk", return_value=apk),
            patch.object(r9, "preflight_destination"),
            patch.object(whole_catalog, "build_integration", return_value=dict(apk=str(apk), apk_sha256=sha(apk), input_id=self.input_id)) as execute,
        ):
            result = r9.unity_build(self.dest, self.work, self.input_id, provenance)
            execute.assert_called_once_with(destination=self.dest, work=self.work)
            self.assertEqual(len(result["groups"]["r9_obligations"]["rows"]), 2)
            self.assertEqual(len(result["groups"]["unity_import_deferred"]["rows"]), 1)
            self.assertEqual(len(result["groups"]["unity_generated"]["rows"]), 2)
            self.assertFalse(result["equal"])
            before = (self.dest / ".rebuild/unity-build.json").read_bytes()
            execute.reset_mock()
            r9.unity_build(self.dest, self.work, self.input_id, provenance, compare_only=True)
            execute.assert_not_called()
            self.assertEqual((self.dest / ".rebuild/unity-build.json").read_bytes(), before)

    def test_binding_failure_prevents_unity_and_receipts(self):
        with (
            patch.object(build_entry_rebuild, "validate_bindings", return_value=dict(equal=False)),
            patch.object(whole_catalog, "build_integration") as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "validate-bindings"):
                r9.unity_build(self.dest, self.work, self.input_id, {})
            execute.assert_not_called()
        self.assertFalse((self.dest / ".rebuild/unity-build.json").exists())

    def test_real_build_cache_route_does_not_enter_destination_path(self):
        cached = self.work / "build-cache/key/result.json"
        apk = cached.parent / "lab.apk"
        apk.parent.mkdir(parents=True)
        apk.write_bytes(b"cached APK")
        write(cached, dict(success=True, errors=0, apk=str(apk), apk_sha256=sha(apk), payload={}))
        with (
            patch.object(build, "WORK", self.work),
            patch.object(build, "preflight"),
            patch.object(build, "validate_staged_runtime_sources"),
            patch.object(build, "stage_android_assets"),
            patch.object(build, "build_cache_key", return_value="key") as key,
            patch.object(r9, "execute_build") as isolated,
        ):
            result = build.build("vulkan")
            key.assert_called_once_with(self.work / "lab-project", "vulkan")
            isolated.assert_not_called()
            self.assertEqual(read(self.work / "config/current-build.json"), result)
            self.assertEqual(result["apk"], str(apk))

    def test_level0_classifies_only_exhaustively_attributed_hash_bytes(self):
        a_pair, b_pair = b"a" * 16 + b"A" * 16, b"b" * 16 + b"B" * 16
        a, b = b"prefix" + a_pair + b"suffix", b"prefix" + b_pair + b"suffix"
        types = [[(114, 0, a_pair[:16], a_pair[16:])], [(114, 0, b_pair[:16], b_pair[16:])]]
        with patch.object(r9, "serialized_types", side_effect=types):
            result = r9.level0_difference(a, b)
        self.assertEqual(result["classification"], "unity-script-type-hashes-only")
        self.assertEqual(result["script_type_hash_fields"][0]["offset"], 6)
        with patch.object(r9, "serialized_types", side_effect=types):
            result = r9.level0_difference(a, b[:-1] + b"X")
        self.assertEqual(result["classification"], "unexplained-scene-difference")
        self.assertFalse(result["other_bytes_equal"])

    def test_destination_preflight_cli_and_install_sync_options_keep_existing_routes(self):
        import common
        import device
        import runpy
        from io import StringIO

        script = str(Path(__file__).resolve().parents[1] / "scripts/lab/main.py")
        with patch.object(common, "WORK", self.work), patch("sys.stdout", new_callable=StringIO):
            for command, option, value in (("install", "--apk", "destination.apk"), ("sync-data", "--payload-dir", "destination-payload")):
                with patch.object(sys, "argv", [script, command, option, value]), patch.object(device, "Device") as factory:
                    factory.return_value.install.return_value = {}
                    factory.return_value.sync.return_value = {}
                    runpy.run_path(script, run_name="__main__")
                    if command == "install":
                        factory.return_value.install.assert_called_once_with(value)
                    else:
                        factory.return_value.sync.assert_called_once_with(Path(value))
            with (
                patch.object(sys, "argv", [script, "preflight", "--dest", str(self.dest), "--work-dir", str(self.work)]),
                patch.object(r9, "preflight_destination", return_value=dict(success=True)) as isolated,
                patch.object(build, "preflight") as live,
            ):
                runpy.run_path(script, run_name="__main__")
                isolated.assert_called_once_with(str(self.dest), str(self.work))
                live.assert_not_called()

    def test_real_full_and_code_only_build_receipts_and_payload_paths_are_unchanged(self):
        import shutil
        from io import StringIO

        write(self.work / "inventory/files.json", dict(input_id=self.input_id))
        apk = self.work / "lab-build/lab-vulkan.apk"
        apk.parent.mkdir(parents=True)
        apk.write_bytes(b"real route fixture")
        installed = (self.work / "device/installed.json").read_bytes()

        def editor(target, action):
            self.assertEqual(target, "lab")
            if action == "build":
                request = read(self.work / "build-request.json")
                write(self.work / "lab-build/result.json", dict(success=True, errors=0, result="Succeeded", apk=str(apk), request_id=request["request_id"]))
            return "mock dispatch"

        for code_only in (False, True):
            with (
                self.subTest(code_only=code_only),
                patch.object(build, "WORK", self.work),
                patch.object(build, "preflight"),
                patch.object(build, "validate_staged_runtime_sources"),
                patch.object(build, "stage_android_assets"),
                patch.object(build, "validate_whole_payload_reuse") as reuse,
                patch.object(build, "build_cache_key", return_value="ordinary-key"),
                patch.object(build, "editor", side_effect=editor),
                patch.object(build, "copy_build_artifact", side_effect=shutil.copy2),
                patch.object(r9, "execute_build") as isolated,
                patch("sys.stdout", new_callable=StringIO),
            ):
                result = build.build("vulkan", force=True, reuse_payload=code_only)
                isolated.assert_not_called()
                self.assertEqual(reuse.call_count, int(code_only))
                request = read(self.work / "build-request.json")
                self.assertEqual(request["reusePayload"], code_only)
                self.assertEqual(result["apk"], str(self.work / "build-cache/ordinary-key/lab-vulkan.apk"))
                self.assertEqual(result["payload"], {"keep": sha(self.work / "generated-android-data/keep")})
                self.assertEqual(read(self.work / "config/current-build.json"), result)
                self.assertEqual(read(self.work / "build-cache/ordinary-key/result.json"), result)
                self.assertEqual((self.work / "device/installed.json").read_bytes(), installed)

    def test_shared_source_validator_reads_destination_selection_and_keeps_default_work_unchanged(self):
        selected = self.dest / ".rebuild/selected"
        write(selected / "whole-catalog-build.json", {})
        write(selected / "scene-probe-build.json", dict(scene="Assets/rebuilt.unity"))
        with (
            patch.object(build, "WORK", self.work),
            patch.object(build, "validate_runtime_source_membership", return_value=[]),
            patch.object(build, "validate_project_layout"),
            patch.object(build, "validate_runtime_config"),
            patch.object(build, "_read_public_recipe", return_value=dict(scene="Assets/rebuilt.unity")),
        ):
            self.source_validator(self.dest, work=selected)
        self.assertEqual(self.before, self.snapshot())

    def test_signing_key_missing_refuses_in_place_build_identity(self):
        key = r9.debug_signing_key(self.work)
        before = key.read_bytes()
        with patch.object(r9, "run", side_effect=self.fake_run):
            build.build("vulkan", destination=self.dest, work=self.work)
        self.assertEqual(key.read_bytes(), before)
        key.unlink()
        with self.assertRaisesRegex(RuntimeError, "signing key required"):
            r9.debug_signing_key(self.work)
