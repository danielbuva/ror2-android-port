import importlib.util
from pathlib import Path
import plistlib
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
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})
