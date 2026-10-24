"""Synthetic owner-input and output-lifecycle contracts; no game or editor data."""

import copy
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import actions
import assembly_transforms
import owner_assemblies as owner
import rebuild
from common import ROOT, RECIPE, digest, read, sha, write


class OwnerAssemblyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "clone"
        self.root.mkdir()
        self.work = self.base / "input-work"
        self.installation = self.base / "installation"
        self.managed = self.installation / "Risk of Rain 2_Data/Managed"
        self.managed.mkdir(parents=True)
        self.recipe = self.root / "recipe"
        (self.recipe / "templates").mkdir(parents=True)
        shutil.copyfile(RECIPE / "templates/original-assembly.meta", self.recipe / "templates/original-assembly.meta")
        self.rows = []
        for index, name in enumerate(("RoR2.dll", "Transformed.dll")):
            (self.managed / name).write_bytes(("authored original " + name).encode())
            self.rows.append(
                dict(
                    path="Assets/Plugins/" + name,
                    source=name,
                    sha256=sha(self.managed / name),
                    guid=f"a{index:031x}",
                    time_created=123,
                    execution_order={"Fixture.Component": -15},
                )
            )
        files = []
        for path in sorted(self.installation.rglob("*")):
            if path.is_file():
                files.append(
                    dict(path=path.relative_to(self.installation).as_posix(), sha256=sha(path), size=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns)
                )
        self.identity = digest([(row["path"], row["sha256"]) for row in files])
        write(self.work / "inventory/files.json", dict(input_id=self.identity, files=files))
        write(self.work / "config/accepted-input.json", dict(input_id=self.identity))
        write(self.work / "config/local.json", dict(game_path=str(self.installation)))
        write(self.recipe / "original-assemblies.json", dict(schema=1, input_id=self.identity, assemblies=self.rows))
        self.body = b"authored transformed fixture"
        self.transforms = dict(
            input_id=self.identity,
            cecil_sha256="c" * 64,
            tool_sources={},
            steps=[dict(inputs={"Transformed.dll": self.rows[1]["sha256"]}, outputs={"Transformed.dll": hashlib.sha256(self.body).hexdigest()})],
        )
        self.destination = self.root / "work/rebuild/owner-prefix"
        self.source = dict(commit="e" * 40, uncommitted=False, files={})
        for patcher in (
            patch.object(owner, "ROOT", self.root),
            patch.object(owner, "RECIPE", self.recipe),
            patch.object(rebuild, "ROOT", self.root),
            patch.object(rebuild, "RECIPE", self.recipe),
            patch.object(assembly_transforms, "load_recipe", return_value=self.transforms),
            patch.object(assembly_transforms, "generate", side_effect=self.generate),
            patch.object(owner, "source_state", side_effect=lambda _: copy.deepcopy(self.source)),
            patch.object(owner.shutil, "disk_usage", return_value=SimpleNamespace(free=20 * 1024**3)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def generate(self, managed, attempt, transforms):
        self.assertEqual(managed, self.managed)
        self.assertEqual(transforms, self.transforms)
        self.assertTrue(attempt.is_relative_to(self.destination))
        output = attempt / "Transformed.dll"
        output.write_bytes(self.body)
        return {"Transformed.dll": output}

    def stage(self):
        return owner.stage(self.destination, self.work)

    def input_snapshot(self):
        return {
            str(path): (path.read_bytes(), path.stat().st_mtime_ns) for tree in (self.work, self.installation) for path in tree.rglob("*") if path.is_file()
        }

    def test_fresh_input_generates_exact_prefix_without_project_or_provenance(self):
        before = self.input_snapshot()
        self.assertFalse((self.work / "receipts/provenance-map.json").exists())
        self.assertFalse((self.work / "lab-project").exists())
        result = self.stage()
        self.assertTrue(result["success"])
        self.assertEqual((result["phase"], result["output_files"]), ("complete", 4))
        self.assertEqual(self.input_snapshot(), before)
        project = self.destination / "project"
        expected = {row["path"] + suffix for row in self.rows for suffix in ("", ".meta")}
        self.assertEqual({path.relative_to(project).as_posix() for path in project.rglob("*") if path.is_file()}, expected)
        self.assertEqual((project / self.rows[1]["path"]).read_bytes(), self.body)
        self.assertFalse((project / ".port-input.json").exists())
        self.assertFalse((self.work / "config/current-build.json").exists())
        self.assertEqual(result["manifest_sha256"], sha(self.destination / "manifest.json"))
        self.assertEqual(read(self.destination / "receipt.json"), result)
        for key in ("full_project_qualified", "phone_build_qualified", "runtime_qualified"):
            self.assertIs(result[key], False)

    def test_public_profile_is_explicit_and_uses_same_full_output_gate(self):
        selectors = dict(assembly_profile="public-dotnet8", tool_archives="archives", tool_launcher="launcher", tool_host="host10")

        def generated(managed, attempt, transforms, **options):
            self.assertEqual(options, dict(archives="archives", launcher="launcher", host="host10"))
            write(attempt / "public-tools-receipt.json", dict(profile="public-dotnet8", success=True))
            return self.generate(managed, attempt, transforms)

        with patch("public_transform_tools.generate", side_effect=generated):
            result = owner.stage(self.destination, self.work, **selectors)
        self.assertTrue(result["success"])
        self.assertEqual(result["transform_profile"], "public-dotnet8")
        self.assertIsNone(result["cecil_sha256"])
        self.assertEqual(result["public_tools_receipt_sha256"], sha(self.destination / "attempt/public-tools-receipt.json"))

    def test_partial_unknown_and_mixed_profile_selectors_refuse_before_destination(self):
        for options in (dict(assembly_profile="unknown"), dict(tool_archives="unexpected"), dict(assembly_profile="public-dotnet8", tool_host="host10")):
            with self.subTest(options=options), self.assertRaisesRegex(RuntimeError, "Public profile requires"):
                owner.stage(self.destination, self.work, **options)
            self.assertFalse(self.destination.exists())

    def test_existing_success_or_failure_destination_is_never_reused(self):
        self.stage()
        before = {path.relative_to(self.destination): path.read_bytes() for path in self.destination.rglob("*") if path.is_file()}
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            self.stage()
        self.assertEqual(before, {path.relative_to(self.destination): path.read_bytes() for path in self.destination.rglob("*") if path.is_file()})

    def test_approval_inventory_identity_and_current_input_drift_refuse_before_attempt(self):
        original = read(self.work / "inventory/files.json")
        for change in ("approval", "inventory", "input"):
            with self.subTest(change=change):
                if change == "approval":
                    write(self.work / "config/accepted-input.json", dict(input_id="f" * 64))
                elif change == "inventory":
                    altered = copy.deepcopy(original)
                    altered["files"][0]["sha256"] = "f" * 64
                    write(self.work / "inventory/files.json", altered)
                else:
                    (self.managed / "RoR2.dll").write_bytes(b"authored drift")
                with self.assertRaises(RuntimeError):
                    self.stage()
                self.assertFalse(self.destination.exists())
                write(self.work / "config/accepted-input.json", dict(input_id=self.identity))
                write(self.work / "inventory/files.json", original)

    def test_wrong_recipe_identity_and_unsafe_membership_refuse_before_attempt(self):
        recipe = read(self.recipe / "original-assemblies.json")
        for change in ("identity", "path", "duplicate"):
            altered = copy.deepcopy(recipe)
            if change == "identity":
                altered["input_id"] = "f" * 64
            elif change == "path":
                altered["assemblies"][0]["path"] = "../Original.dll"
            else:
                altered["assemblies"].append(altered["assemblies"][0])
            write(self.recipe / "original-assemblies.json", altered)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.stage()
            self.assertFalse(self.destination.exists())

    def test_protected_external_and_symlink_destinations_refuse_without_writes(self):
        before = self.input_snapshot()
        for target in (self.base / "outside", self.work / "lab-project", self.installation / "prefix"):
            with self.subTest(target=target), self.assertRaises(RuntimeError):
                owner.stage(target, self.work)
            self.assertFalse(target.exists())
        (self.root / "work").mkdir()
        (self.root / "work/rebuild").symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.stage()
        self.assertEqual(self.input_snapshot(), before)

    def test_explicit_destination_and_existing_host_headroom_are_required(self):
        with self.assertRaisesRegex(RuntimeError, "explicit"):
            owner.stage(None, self.work)
        with patch.object(owner.shutil, "disk_usage", return_value=SimpleNamespace(free=1)), self.assertRaisesRegex(RuntimeError, "10 GiB"):
            self.stage()
        self.assertFalse(self.destination.exists())

    def test_bad_transform_output_preserves_failed_attempt_without_project(self):
        self.body = b"authored incorrect output"
        with self.assertRaisesRegex(RuntimeError, "public output contract"):
            self.stage()
        self.assertFalse((self.destination / "project").exists())
        self.assertTrue((self.destination / "attempt/Transformed.dll").exists())
        self.assertEqual(read(self.destination / "receipt.json")["phase"], "failed")

    def test_bad_missing_or_extra_metadata_cohort_refuses_before_project(self):
        original = rebuild.assembly_payload
        for mutation in ("meta", "missing", "extra"):
            self.destination = self.root / ("work/rebuild/" + mutation)

            def altered(*args, **kwargs):
                payload = original(*args, **kwargs)
                key = self.rows[0]["path"] + ".meta"
                if mutation == "meta":
                    payload[key] = b"wrong authored metadata"
                elif mutation == "missing":
                    del payload[key]
                else:
                    payload["../escape"] = b"unexpected authored output"
                return payload

            with self.subTest(mutation=mutation), patch.object(rebuild, "assembly_payload", side_effect=altered), self.assertRaises(RuntimeError):
                self.stage()
            self.assertFalse((self.destination / "project").exists())

    def test_source_and_input_changes_during_generation_preserve_refused_attempt(self):
        original = self.generate

        def changed(managed, attempt, transforms):
            outputs = original(managed, attempt, transforms)
            self.source["uncommitted"] = True
            return outputs

        with patch.object(assembly_transforms, "generate", side_effect=changed), self.assertRaisesRegex(RuntimeError, "changed during"):
            self.stage()
        self.assertEqual(read(self.destination / "receipt.json")["phase"], "failed")
        self.assertFalse((self.destination / "project").exists())
        self.destination = self.root / "work/rebuild/input-race"

        def input_changed(managed, attempt, transforms):
            outputs = original(managed, attempt, transforms)
            (managed / "RoR2.dll").write_bytes(b"authored external change")
            return outputs

        with patch.object(assembly_transforms, "generate", side_effect=input_changed), self.assertRaisesRegex(RuntimeError, "input changed"):
            self.stage()
        self.assertFalse((self.destination / "project").exists())

    def test_tool_failure_and_receipt_failure_preserve_the_first_error(self):
        normal_write = owner.write

        def failed_record(path, value):
            if path.name == "receipt.json" and value.get("phase") == "failed":
                raise OSError("authored receipt failure")
            return normal_write(path, value)

        with (
            patch.object(assembly_transforms, "generate", side_effect=RuntimeError("authored tool first failure")),
            patch.object(owner, "write", side_effect=failed_record),
            self.assertRaisesRegex(RuntimeError, "authored tool first failure; failed to record"),
        ):
            self.stage()
        self.assertTrue((self.destination / "attempt").is_dir())
        self.assertFalse(read(self.destination / "receipt.json")["success"])


class OwnerAssemblyInterfaceTests(unittest.TestCase):
    def test_registry_dispatch_selects_only_the_named_host_owner(self):
        function = Mock()
        args = SimpleNamespace(action="owner-assembly-prefix", dest="new-output", work_dir="reviewed-inputs")
        with patch.object(actions, "import_module", return_value=SimpleNamespace(stage_action=function)):
            actions.dispatch(args)
        function.assert_called_once_with(dest="new-output", work="reviewed-inputs")

    def test_cli_requires_new_destination_and_keeps_rebuild_only_options_separate(self):
        for extra in ([], ["--dest", "work/rebuild/fixture", "--step", "assemblies"], ["--dest", "work/rebuild/fixture", "--compare-only"]):
            command = [sys.executable, str(ROOT / "scripts/lab/main.py"), "prototype", "--action", "owner-assembly-prefix", *extra]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_public_profile_cli_rejects_partial_and_unrelated_selectors(self):
        for extra in (
            ["prototype", "--action", "owner-assembly-prefix", "--dest", "work/rebuild/fixture", "--assembly-profile", "public-dotnet8"],
            ["prototype", "--action", "owner-assembly-prefix", "--dest", "work/rebuild/fixture", "--tool-host", "host10"],
            ["doctor", "--assembly-profile", "public-dotnet8", "--tool-archives", "cache", "--tool-launcher", "dotnet", "--tool-host", "host10"],
        ):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/lab/main.py"), *extra], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
