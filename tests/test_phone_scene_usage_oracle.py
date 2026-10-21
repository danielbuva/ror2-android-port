import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_scene_usage_oracle as oracle


class SceneUsageOracleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in oracle.SOURCES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// authored source fixture\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: fixture"], cwd=self.root, check=True)
        self.editor = self.root / "Contents/MacOS/AuthoredEditor"
        self.editor.parent.mkdir(parents=True)
        self.editor.write_bytes(b"authored non-executable editor substitute")
        self.work = self.root / "work"
        self.pin = patch.object(oracle.guard, "BINARY_SHA256", oracle.guard.sha(self.editor))
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def invoke(self, execute):
        proxy = SimpleNamespace(check_output=subprocess.check_output, run=execute, SubprocessError=subprocess.SubprocessError)
        with patch.object(oracle, "subprocess", proxy):
            return oracle.run(self.root, self.work, self.editor)

    def report(self, destination, inputs):
        project = destination / "project"
        scene = project / "Assets/Fixture.unity"
        scene.write_text("%YAML 1.1\n--- !u!1 &1\nGameObject:\n")
        compiled = destination / "player-scripts/Assembly-CSharp.dll"
        loaded = project / "Library/ScriptAssemblies/Assembly-CSharp.dll"
        for path in (compiled, loaded):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"authored assembly observation stand-in")
        object_row = dict(
            guid="1" * 32,
            local_id=1,
            file_type=0,
            file_path="",
            instance_id=123,
            loaded_name="",
            resolved=False,
            support_queried=False,
            supported=False,
            types_returned_null=True,
            types=[],
            loaded_types=[],
        )
        return dict(
            schema=1,
            unity=oracle.guard.VERSION,
            source_commit=inputs["source_commit"],
            profile="authored-default-scene-dependencies-v1",
            phase="complete",
            failure="",
            game_inputs=False,
            player_built=False,
            root_generation_qualified=False,
            settings=dict(
                target="Android",
                group="Android",
                backend="IL2CPP",
                architecture="ARM64",
                stripping="Low",
                graphics=["Vulkan"],
                strip_engine=False,
                script_options=3,
                content_flags=4,
                api="AuthoredApi",
            ),
            scene="Assets/Fixture.unity",
            scene_sha256=oracle.guard.sha(scene),
            type_db_hash="a" * 32,
            compiled_assemblies=[dict(path=str(compiled), sha256=oracle.guard.sha(compiled))],
            loaded_assemblies=[dict(path=str(loaded), sha256=oracle.guard.sha(loaded))],
            scene_types=[dict(assembly="Authored, Version=1.0.0.0", name="Fixture")],
            manager_types=[],
            loaded_scene=[
                dict(
                    instance_id=321,
                    name="Authored",
                    supported=True,
                    identifier_available=False,
                    types=[dict(assembly="Authored", name="LiveSceneObject")],
                    identifiers=[],
                )
            ],
            groups=[dict(name=name, objects=[copy.deepcopy(object_row)] if name == "scene_references" else []) for name in sorted(oracle.GROUPS)],
            global_usage=[dict(name=name, fields=[dict(name="authoredField", value="False")]) for name in ("scene", "graphics", "managers")],
        )

    def test_success_is_bound_to_fresh_project_source_mutex_and_false_qualification(self):
        calls, locks = [], []

        @contextmanager
        def lock(path, **kwargs):
            locks.append((path, kwargs))
            yield

        def execute(args, **kwargs):
            calls.append(args)
            destination = Path(args[args.index("-projectPath") + 1]).parent
            inputs = json.loads((destination / "inputs.json").read_text())
            report = self.report(destination, inputs)
            self.assertEqual(kwargs["env"]["ROR2_PHONE_BUILD_SOURCE"], inputs["source_commit"])
            self.assertEqual(kwargs["timeout"], 600)
            Path(kwargs["env"]["ROR2_SCENE_USAGE_REPORT"]).write_text(json.dumps(report))
            return SimpleNamespace(returncode=0, stdout=b"authored output", stderr=b"")

        with patch.object(oracle, "host_build_lock", lock):
            destination, receipt = self.invoke(execute)
        self.assertTrue(receipt["success"], receipt)
        self.assertFalse(receipt["root_generation_qualified"])
        self.assertFalse(receipt["game_inputs"])
        self.assertTrue(destination.is_relative_to(self.work / "rebuild/phone-wrapper-oracle"))
        self.assertEqual(locks[0][0], self.root / "work/coordination/unity-build.lock")
        self.assertEqual(locks[0][1]["timeout"], 1)
        self.assertEqual(calls[0][calls[0].index("-executeMethod") + 1], "SceneUsageOracle.Check")
        self.assertEqual((destination / "launch.txt").read_bytes(), b"authored output")

    def test_unknown_sdk_and_uncommitted_sources_refuse_before_staging(self):
        self.editor.write_bytes(b"different authored editor")
        with self.assertRaisesRegex(ValueError, "Exact owner SDK"):
            self.invoke(lambda *a, **kw: self.fail("Must not launch"))
        self.assertFalse(self.work.exists())
        self.editor.write_bytes(b"authored non-executable editor substitute")
        (self.root / oracle.SOURCES[-1]).write_text("// changed fixture\n")
        with self.assertRaisesRegex(ValueError, "Commit scene usage"):
            self.invoke(lambda *a, **kw: self.fail("Must not launch"))
        self.assertFalse(self.work.exists())

    def test_parent_link_refuses_before_any_outside_write(self):
        self.work.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.work / "rebuild").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "without links"):
            self.invoke(lambda *a, **kw: self.fail("Must not launch"))
        self.assertEqual(list(outside.iterdir()), [])

    def test_lock_contention_child_failure_and_timeout_keep_failed_receipts(self):
        @contextmanager
        def locked(*args, **kwargs):
            raise RuntimeError("authored contention")
            yield

        with patch.object(oracle, "host_build_lock", locked):
            destination, receipt = self.invoke(lambda *a, **kw: self.fail("Must not launch"))
        self.assertFalse(receipt["success"])
        self.assertIsNone(receipt["exit_code"])
        self.assertIn("contention", receipt["error"])
        self.assertTrue((destination / "receipt.json").is_file())
        destination, receipt = self.invoke(lambda *a, **kw: SimpleNamespace(returncode=7, stdout=b"first failure", stderr=b""))
        self.assertEqual(receipt["exit_code"], 7)
        self.assertFalse(receipt["success"])
        self.assertEqual((destination / "launch.txt").read_bytes(), b"first failure")

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("authored child", 600)

        destination, receipt = self.invoke(timeout)
        self.assertFalse(receipt["success"])
        self.assertTrue((destination / "receipt.json").is_file())

    def test_foreign_asset_or_source_drift_refuses_after_child_exit(self):
        for kind in ("foreign", "source"):
            with self.subTest(kind=kind):

                def execute(args, **kwargs):
                    if kind == "foreign":
                        project = Path(args[args.index("-projectPath") + 1])
                        (project / "Assets/Foreign.dll").write_bytes(b"authored negative control")
                    else:
                        (self.root / oracle.SOURCES[0]).write_text("// source drift\n")
                    return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

                _, receipt = self.invoke(execute)
                self.assertFalse(receipt["success"])
                self.assertIn("Foreign" if kind == "foreign" else "source drift", receipt["error"])

    def test_report_refuses_fake_scope_types_support_and_assembly_evidence(self):
        destination, inputs = oracle.stage(self.root, self.work, self.editor)
        original = self.report(destination, inputs)
        oracle.validate_report(original, inputs, destination, self.editor)
        changes = [
            lambda r: r.update(root_generation_qualified=True),
            lambda r: r.update(phase="manager-dependencies"),
            lambda r: r["settings"].update(backend="Mono"),
            lambda r: r.update(scene_types=[dict(assembly="Authored", name="")]),
            lambda r: r["groups"].append(r["groups"][0]),
            lambda r: next(g["objects"][0] for g in r["groups"] if g["objects"]).update(supported=True),
            lambda r: next(g["objects"][0] for g in r["groups"] if g["objects"]).update(types=[dict(assembly="A", name="Invented")]),
            lambda r: r["compiled_assemblies"][0].update(path=str(self.editor)),
            lambda r: r["loaded_assemblies"][0].update(sha256="0" * 64),
            lambda r: r["global_usage"][0]["fields"].append(dict(name="otherLayout", value="0")),
            lambda r: r["loaded_scene"][0].update(identifier_available=True),
            lambda r: r["loaded_scene"][0].update(types=[]),
            lambda r: r.update(loaded_scene=r["loaded_scene"] * 2),
        ]
        for change in changes:
            with self.subTest(change=change):
                report = copy.deepcopy(original)
                change(report)
                with self.assertRaises(ValueError):
                    oracle.validate_report(report, inputs, destination, self.editor)

    def test_shared_wrappers_remain_repeated_observations_with_no_native_identity_claim(self):
        destination, inputs = oracle.stage(self.root, self.work, self.editor)
        report = self.report(destination, inputs)
        report["scene_types"] *= 2
        report["manager_types"] = report["scene_types"] * 3
        group = next(g for g in report["groups"] if g["objects"])
        row = group["objects"][0]
        row.update(types_returned_null=False, types=report["scene_types"] * 2)
        oracle.validate_report(report, inputs, destination, self.editor)
        self.assertEqual(len(report["scene_types"]), 2)
        self.assertEqual(len(report["manager_types"]), 6)
        self.assertEqual(len(row["types"]), 4)
        self.assertFalse(report["root_generation_qualified"])


class SceneUsageSdkCompilationTests(unittest.TestCase):
    def test_collector_compiles_against_the_actual_sdk_without_starting_unity(self):
        contents = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        mono = contents / "MonoBleedingEdge/bin/mono"
        compiler = contents / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("Optional exact-editor compiler absent")
        root = Path(__file__).resolve().parents[1]
        refs = sorted((contents / "Managed/UnityEngine").glob("*.dll"))
        self.assertTrue(refs)
        with tempfile.TemporaryDirectory() as temporary:
            built = subprocess.run(
                [
                    str(mono),
                    str(compiler),
                    "-nologo",
                    "-target:library",
                    "-out:" + str(Path(temporary) / "AuthoredOracle.dll"),
                    *("-r:" + str(path) for path in refs),
                    str(root / "tools/phone-build/SceneUsageOracle.cs"),
                    str(root / "tools/phone-build/ContentFixture.cs"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
