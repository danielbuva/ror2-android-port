import importlib.util
import os
from pathlib import Path
import plistlib
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audio_managed_producer", ROOT / "tools/unity/support/audio/managed-producer/produce.py")
PRODUCER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRODUCER)


class ManagedProducerTests(unittest.TestCase):
    def test_editor_identity_requires_both_version_and_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "environment").mkdir()
            (root / "environment/toolchain.json").write_text('{"unity_version":"2021.3.45f2","unity_revision":"88f88f591b2e"}')
            contents = root / "Unity.app/Contents"
            (contents / "MacOS").mkdir(parents=True)
            editor = contents / "MacOS/Unity"
            editor.write_bytes(b"authored fixture")
            with mock.patch.object(PRODUCER, "ROOT", root):
                for version, revision, accepted in (
                    ("2021.3.45f2", "88f88f591b2e", True),
                    ("2021.3.45f2", "wrong", False),
                    ("2021.3.44f1", "88f88f591b2e", False),
                ):
                    with self.subTest(version=version, revision=revision):
                        (contents / "Info.plist").write_bytes(plistlib.dumps({"CFBundleVersion": version, "UnityBuildNumber": revision}))
                        if accepted:
                            PRODUCER.validate_editor_identity(editor)
                        else:
                            with self.assertRaises(RuntimeError):
                                PRODUCER.validate_editor_identity(editor)

    def test_output_guard_refuses_existing_and_non_work_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            work = root / "work"
            work.mkdir()
            with mock.patch.object(PRODUCER, "WORK", work):
                with self.assertRaisesRegex(RuntimeError, "must be new"):
                    PRODUCER.output_directory(work)
                with self.assertRaisesRegex(RuntimeError, "under repository work"):
                    PRODUCER.output_directory(root / "outside")

    def test_compiler_receives_isolated_authored_project_without_writing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            project = source / "Probe.csproj"
            project.write_text('<Project Sdk="Microsoft.NET.Sdk"/>')
            (source / "Probe.cs").write_text("public class Probe {}")
            (source / "excluded.bin").write_bytes(b"authored control")
            before = {p.name: p.read_bytes() for p in source.iterdir()}
            output = root / "output"
            output.mkdir()
            with mock.patch.object(PRODUCER, "run") as invoke:
                PRODUCER.build_dotnet(project, output / "bin", root / "cecil", root / "dotnet", output, {})
            isolated = output / "authored-projects/Probe"
            command = invoke.call_args.args[0]
            self.assertEqual(command[2], str(isolated / "Probe.csproj"))
            self.assertEqual({p.name for p in isolated.iterdir()}, {"Probe.cs", "Probe.csproj"})
            self.assertIn("-p:BaseIntermediateOutputPath=" + str(isolated / "obj") + "/", command)
            self.assertIn("-p:EnableSourceLink=false", command)
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})

    def test_actual_helper_is_independent_of_revision_and_output_path(self):
        dotnet = shutil.which("dotnet")
        reference = Path.home() / ".nuget/packages/netstandard.library.ref/2.1.0"
        if not dotnet or not reference.is_dir():
            self.skipTest("optional .NET SDK and offline netstandard reference package unavailable")
        scratch = ROOT / "work/tests/original-audio-managed-repro"
        scratch.mkdir(parents=True, exist_ok=True)
        project = ROOT / "tools/unity/support/audio/managed-producer/source/owner-api/OriginalOwnerProbeObserver.csproj"
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            packages = root / "packages"
            shutil.copytree(reference, packages / "netstandard.library.ref/2.1.0")
            results = []
            original_run = PRODUCER.run
            for name, revision in (("first-root", "0" * 40), ("second-root", "1" * 40)):
                output = root / name
                (output / "logs").mkdir(parents=True)
                (output / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>")
                env = dict(os.environ, NUGET_PACKAGES=str(packages), DOTNET_CLI_HOME=str(output / "dotnet-home"), DOTNET_CLI_TELEMETRY_OPTOUT="1")

                def with_revision(command, **kwargs):
                    return original_run(command + ["-p:SourceRevisionId=" + revision], **kwargs)

                with mock.patch.object(PRODUCER, "run", side_effect=with_revision):
                    PRODUCER.build_dotnet(project, output / "bin", root / "unused-cecil", Path(dotnet), output, env)
                self.assertFalse(list((output / "authored-projects").rglob("*.sourcelink.json")))
                results.append((output / "bin/OriginalOwnerProbeObserver.dll").read_bytes())
            self.assertEqual(results[0], results[1])
