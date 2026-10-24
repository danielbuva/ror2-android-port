"""Contracts for whole-player backend inputs, exact policy and source retention."""

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/produce.py"
SPEC = importlib.util.spec_from_file_location("owner_code_backend", PATH)
BACKEND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKEND)


class OwnerCodeBackendTests(unittest.TestCase):
    def test_android_failure_keeps_wall_memory_and_storage_measurements(self):
        runner_spec = importlib.util.spec_from_file_location("android_owner_runner_test", PATH.parent / "run_android.py")
        runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(runner)
        environment = patch.dict(runner.os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            inputs, runtime, installed = [root / n for n in ("inputs", "runtime", "installed")]
            for directory in (inputs / "game", inputs / "work/inventory", inputs / "work/config", inputs / "packages", runtime, installed):
                directory.mkdir(parents=True)
            original = inputs / "game/original.bin"
            original.write_bytes(b"independent owner input fixture")
            digest = BACKEND.native.sha(original)
            (inputs / "input-hashes.json").write_text(json.dumps({"game/original.bin": digest}))
            (inputs / "work/inventory/files.json").write_text(
                json.dumps({"files": [{"path": "original.bin", "sha256": digest, "size": original.stat().st_size}]})
            )
            request = inputs / "request.json"
            request.write_text(
                json.dumps({"source_inputs": {"packages": "packages"}, "target": {"profile": "recipe/fixture.json", "source": "packages"}, "output": "attempt"})
            )

            def fail(production):
                Path(production["output"]).mkdir()
                raise RuntimeError("independent converter failure fixture")

            backend = SimpleNamespace(native=BACKEND.native, run=fail)
            specification = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
            with (
                patch.object(runner.importlib.util, "spec_from_file_location", return_value=specification),
                patch.object(runner.importlib.util, "module_from_spec", return_value=backend),
            ):
                with self.assertRaisesRegex(RuntimeError, "converter failure fixture"):
                    runner.run(request, runtime, installed)
            measurements = json.loads((inputs / "work/attempt/android-measurements.json").read_text())
            self.assertGreaterEqual(measurements["wall_seconds"], 0)
            self.assertGreater(measurements["python_peak_rss_bytes"], 0)
            self.assertGreater(measurements["free_bytes_before"], 0)
            self.assertGreater(measurements["free_bytes_after"], 0)
            self.assertFalse(measurements["runtime_qualified"])
            self.assertEqual(BACKEND.native.sha(original), digest)
            measurement = inputs / "work/attempt/android-measurements.json"
            measurement.unlink()
            with (
                patch.object(runner.importlib.util, "spec_from_file_location", return_value=specification),
                patch.object(runner.importlib.util, "module_from_spec", return_value=backend),
            ):
                with self.assertRaises(FileExistsError):
                    runner.run(request, runtime, installed)
            self.assertFalse(measurement.exists())

    def test_explicit_target_source_cannot_drift_or_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            file = source / "Fixture.cs"
            file.write_text("// authored target source")
            profile = root / "target.json"
            profile.write_text(json.dumps({"source_commit": "fixture", "source_files": {"Fixture.cs": BACKEND.native.sha(file)}}))
            target, actual, digest = BACKEND.target_inputs({"profile": str(profile), "source": str(source)})
            self.assertEqual((target["source_commit"], actual, digest), ("fixture", source, BACKEND.native.sha(profile)))
            file.write_text("// changed target source")
            with self.assertRaisesRegex(ValueError, "target authored source drift"):
                BACKEND.target_inputs({"profile": str(profile), "source": str(source)})
            with self.assertRaisesRegex(ValueError, "target requires"):
                BACKEND.target_inputs({"source": str(source)})

    def test_sdk_descriptors_and_root_marker_are_checked_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            sdk = Path(temporary).resolve()
            names = [
                "Unity.app/Contents/il2cpp/build/deploy/Fixture.dll",
                "Unity.app/Contents/il2cpp/LinkerDescriptors/Default/fixture.xml",
                "Unity.app/Contents/il2cpp/il2cpp_root",
                "PlaybackEngines/AndroidPlayer/modules.asset",
                "PlaybackEngines/AndroidPlayer/Tools/AndroidNativeLink.xml",
            ]
            files = {}
            for name in names:
                path = sdk / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("" if name.endswith("il2cpp_root") else "independent SDK fixture")
                files[name] = BACKEND.native.sha(path)
            self.assertEqual(BACKEND.tools(sdk, {"tools": files}), files)
            (sdk / names[1]).write_text("changed descriptor")
            with self.assertRaisesRegex(ValueError, "configuration drift"):
                BACKEND.tools(sdk, {"tools": files})

    def test_complete_provider_membership_and_byte_drift_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "Fixture.dll"
            source.write_bytes(b"independently authored provider witness")
            request = {"Fixture.dll": {"path": str(source), "sha256": BACKEND.native.sha(source)}}
            profile = {"managed_assemblies": ["Fixture.dll"]}
            self.assertEqual(BACKEND.providers(request, profile)["Fixture.dll"]["bytes"], source.stat().st_size)
            with self.assertRaisesRegex(ValueError, "membership"):
                BACKEND.providers({}, profile)
            source.write_bytes(b"changed provider")
            with self.assertRaisesRegex(ValueError, "provider drift"):
                BACKEND.providers(request, profile)
            with self.assertRaisesRegex(ValueError, "relative"):
                BACKEND.providers({"../Fixture.dll": request["Fixture.dll"]}, {"managed_assemblies": ["../Fixture.dll"]})

    def test_fixed_target_requires_immutable_colocated_symbol_companions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            dll = root / "Fixture.dll"
            dll.write_bytes(b"independent assembly witness")
            request = {dll.name: {"path": str(dll), "sha256": BACKEND.native.sha(dll)}}
            profile = {"managed_assemblies": [dll.name], "symbol_assemblies": [dll.name]}
            with self.assertRaisesRegex(ValueError, "symbol companion missing"):
                BACKEND.providers(request, profile)
            pdb = dll.with_suffix(".pdb")
            pdb.write_bytes(b"independent debug symbol witness")
            before = BACKEND.providers(request, profile)
            self.assertEqual(set(before), {dll.name, pdb.name})
            pdb.write_bytes(b"changed symbols")
            self.assertNotEqual(BACKEND.providers(request, profile), before)
            pdb.unlink()
            elsewhere = root / "elsewhere.pdb"
            elsewhere.write_bytes(b"redirected symbols")
            pdb.symlink_to(elsewhere)
            with self.assertRaisesRegex(ValueError, "redirected"):
                BACKEND.providers(request, profile)

    def test_policy_keeps_whole_closure_and_original_checks(self):
        profile = json.loads(BACKEND.PROFILE.read_text())
        self.assertEqual(BACKEND.native.sha(BACKEND.PROFILE), BACKEND.PROFILE_SHA)
        self.assertEqual(len(profile["managed_assemblies"]), 332)
        self.assertEqual(len(set(profile["managed_assemblies"])), 332)
        self.assertNotIn("MCPForUnity.Runtime.dll", profile["managed_assemblies"])
        self.assertEqual(len(profile["converter_assemblies"]), 93)
        self.assertNotIn("allNativeTypes", profile["project"])
        self.assertNotIn("/Users/", BACKEND.PROFILE.read_text())
        linker = BACKEND.linker_command(Path("/sdk"), Path("/owner"), profile)
        self.assertIn("--rule-set=Conservative", linker)
        self.assertIn("--dotnetruntime=Il2Cpp", linker)
        self.assertEqual(len([v for v in linker if v.startswith("--include-unity-root-assembly=")]), 11)
        command = BACKEND.converter_command(Path("/sdk"), Path("/owner"), profile)
        self.assertEqual([Path(v.partition("=")[2]).name for v in command if v.startswith("--assembly=")], profile["converter_assemblies"])
        self.assertIn("--emit-null-checks", command)
        self.assertIn("--enable-array-bounds-check", command)
        self.assertNotIn("--enable-analytics", command)

    def test_source_frames_restore_exact_bytes_before_owned_expansion_retirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            converter = root / "converter"
            (converter / "cpp").mkdir(parents=True)
            source = converter / "cpp/Fixture.cpp"
            content = b"// independently authored source\n#include <stdint.h>\nint value = 7;\n"
            source.write_bytes(content)
            metadata = converter / "cpp/retained.dat"
            metadata.write_bytes(b"retained converter data")
            frames = BACKEND.preserve_sources(converter, {"cpp/Fixture.cpp": {"bytes": len(content), "sha256": BACKEND.native.sha(source)}}, root)
            self.assertEqual(gzip.decompress((frames / "Fixture.cpp.gz").read_bytes()), content)
            self.assertFalse(source.exists())
            self.assertTrue(metadata.is_file())
            ledger = json.loads((root / "source-frames.json").read_text())
            self.assertEqual(ledger["Fixture.cpp"]["provider_sha256"], BACKEND.native.sha(frames / "Fixture.cpp.gz"))
            restored = root / "restored.cpp"
            BACKEND.native.expand(ledger["Fixture.cpp"], restored)
            self.assertEqual(restored.read_bytes(), content)

    def test_source_to_source_include_refuses_without_retiring_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            converter = root / "converter"
            (converter / "cpp").mkdir(parents=True)
            source = converter / "cpp/Fixture.cpp"
            source.write_bytes(b'#include "Other.cpp"\n')
            row = {"bytes": source.stat().st_size, "sha256": BACKEND.native.sha(source)}
            with self.assertRaisesRegex(ValueError, "source-to-source include"):
                BACKEND.preserve_sources(converter, {"cpp/Fixture.cpp": row}, root)
            self.assertTrue(source.is_file())
            self.assertFalse((root / "source-frames.json").exists())

    def test_interstage_guard_rejects_staged_assembly_and_root_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "Fixture.dll"
            source.write_bytes(b"independent provider")
            output = root / "output"
            (output / "managed").mkdir(parents=True)
            (output / "configuration").mkdir()
            staged = output / "managed/Fixture.dll"
            staged.write_bytes(source.read_bytes())
            config = output / "configuration/roots.xml"
            config.write_text("<linker />")
            request = {"managed": {"Fixture.dll": {"path": str(source), "sha256": BACKEND.native.sha(source)}}}
            profile = {"managed_assemblies": ["Fixture.dll"]}
            before = BACKEND.providers(request["managed"], profile)
            state = ("fixture", root, {})
            configs = {"roots.xml": BACKEND.native.sha(config)}
            with patch.object(BACKEND, "tools", return_value={}), patch.object(BACKEND.native, "input_state", return_value=state):
                BACKEND.verify_inputs(request, profile, root, {}, before, root, state, output, configs)
                staged.write_bytes(b"changed stage")
                with self.assertRaisesRegex(ValueError, "managed inputs changed"):
                    BACKEND.verify_inputs(request, profile, root, {}, before, root, state, output, configs)
                staged.write_bytes(source.read_bytes())
                config.write_text("<linker><changed /></linker>")
                with self.assertRaisesRegex(ValueError, "root configuration changed"):
                    BACKEND.verify_inputs(request, profile, root, {}, before, root, state, output, configs)

    def test_wrong_converter_source_hash_refuses_before_retirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            converter = root / "converter"
            (converter / "cpp").mkdir(parents=True)
            source = converter / "cpp/Fixture.cpp"
            source.write_bytes(b"// independent drift witness\n")
            with self.assertRaisesRegex(ValueError, "source changed"):
                BACKEND.preserve_sources(converter, {"cpp/Fixture.cpp": {"bytes": source.stat().st_size, "sha256": "0" * 64}}, root)
            self.assertTrue(source.is_file())


if __name__ == "__main__":
    unittest.main()
