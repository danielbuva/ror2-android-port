"""Contracts for whole-player backend inputs, exact policy and source retention."""

import gzip
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/produce.py"
SPEC = importlib.util.spec_from_file_location("owner_code_backend", PATH)
BACKEND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKEND)


class OwnerCodeBackendTests(unittest.TestCase):
    def burst_fixture(self, root):
        managed, runtime, ndk = [root / name for name in ("managed", "runtime", "ndk")]
        for folder in (managed, runtime, ndk):
            folder.mkdir()
        (managed / "Authored.dll").write_bytes(b"independent managed input witness")
        for name in ("bcl.exe", "libfixture.so"):
            (runtime / name).write_bytes(b"independent acquired-tool witness")
        tools = {"command": [str(Path(sys.executable).resolve())], "runtime": str(runtime), "ndk": str(ndk)}
        policy = {
            "runtime_files": {"bcl.exe": BACKEND.native.sha(runtime / "bcl.exe")},
            "backends": {"libfixture.so": BACKEND.native.sha(runtime / "libfixture.so")},
            "roots": ["Authored.dll"],
            "assembly_defines": {"Authored": ["AUTHORED"], "DeveloperMetadataOnly": ["SDK_FLAG"]},
            "options": ["--platform=Android", "--debug=Full"],
            "api_level": 22,
        }
        return tools, policy, managed

    def test_burst_metadata_only_assembly_is_not_a_supplied_dll_or_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            tools, policy, managed = self.burst_fixture(root)
            output = root / "output"

            def invoke(argv, directory, name, **kwargs):
                self.assertEqual(argv[-2], "+burstc")
                self.assertEqual(kwargs["env"]["BURST_ANDROID_MIN_API_LEVEL"], "22")
                options = (directory / "options.rsp").read_text().splitlines()
                self.assertIn("--assembly-defines=DeveloperMetadataOnly;SDK_FLAG", options)
                self.assertEqual([line for line in options if line.startswith("--root-assembly=")], ["--root-assembly=" + str(managed / "Authored.dll")])
                header = bytearray(64)
                header[:6] = b"\x7fELF\x02\x01"
                struct.pack_into("<HH", header, 16, 3, 183)
                (directory / "lib_burst_generated.so").write_bytes(header)
                (directory / "burst.xml").write_text("<linker />\n")

            with patch.object(BACKEND.native, "invoke", side_effect=invoke):
                result = BACKEND.burst(tools, policy, managed, output)
            self.assertTrue(result["success"])
            self.assertFalse(result["runtime_qualified"])
            self.assertFalse((managed / "DeveloperMetadataOnly.dll").exists())

    def test_burst_refuses_missing_roots_and_tool_drift_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            tools, policy, managed = self.burst_fixture(root)
            output = root / "output"
            policy["roots"].append("Missing.dll")
            with self.assertRaisesRegex(ValueError, "root cohort"):
                BACKEND.burst(tools, policy, managed, output)
            self.assertFalse(output.exists())
            policy["roots"].pop()
            (Path(tools["runtime"]) / "bcl.exe").write_bytes(b"changed tool witness")
            with self.assertRaisesRegex(ValueError, "compiler drift"):
                BACKEND.burst(tools, policy, managed, output)
            self.assertFalse(output.exists())

    def test_default_backend_reaches_native_without_a_fixed_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work, sdk, game = [root / name for name in ("work", "sdk", "game")]
            for folder in (work, sdk, game):
                folder.mkdir()
            assembly = game / "Fixture.dll"
            assembly.write_bytes(b"independent managed assembly fixture")
            profile = root / "player.json"
            profile.write_text(json.dumps({"input_id": "fixture", "managed_assemblies": [assembly.name], "converter_assemblies": [assembly.name]}))
            native_profile = root / "native.json"
            native_profile.write_text(json.dumps({"jobs": [{"generated": "Fixture.cpp"}]}))
            output = work / "production"

            def configuration(profile, sdk, output):
                (output / "configuration").mkdir()
                return {}

            def invoke(command, output, name, **kwargs):
                if name == "linker":
                    (output / "stripped").mkdir()
                    (output / "stripped/Fixture.dll").write_bytes(assembly.read_bytes())
                else:
                    (output / "converter/cpp").mkdir()
                    (output / "converter/cpp/Fixture.cpp").write_text("int fixture() { return 7; }\n")
                    (output / "converter/data/Metadata").mkdir(parents=True)
                    (output / "converter/data/Metadata/global-metadata.dat").write_bytes(b"independent metadata fixture")

            request = {
                "owner_work": str(work),
                "sdk_install": str(sdk),
                "managed": {assembly.name: {"path": str(assembly), "sha256": BACKEND.native.sha(assembly)}},
                "output": str(output),
            }
            with (
                patch.object(BACKEND, "PROFILE", profile),
                patch.object(BACKEND, "PROFILE_SHA", BACKEND.native.sha(profile)),
                patch.object(BACKEND.native, "PROFILE", native_profile),
                patch.object(BACKEND.native, "PROFILE_SHA", BACKEND.native.sha(native_profile)),
                patch.object(BACKEND.native, "input_state", return_value=("fixture", game, {})),
                patch.object(BACKEND, "tools", return_value={}),
                patch.object(BACKEND.native, "sdk_files", return_value={}),
                patch.object(BACKEND, "configuration", side_effect=configuration),
                patch.object(BACKEND, "linker_command", return_value=["fixture-linker"]),
                patch.object(BACKEND, "converter_command", return_value=["fixture-converter"]),
                patch.object(BACKEND.native, "invoke", side_effect=invoke),
                patch.object(BACKEND.native, "run", return_value={"success": True}) as build,
                patch.object(BACKEND.native, "generated_profile") as generated,
                patch.object(BACKEND, "target_inputs") as fixed_target,
            ):
                result = BACKEND.run(request)
            self.assertTrue(result["success"])
            self.assertEqual(result["phase"], "native-built")
            self.assertEqual(result["source_frames"], 1)
            build.assert_called_once()
            generated.assert_not_called()
            fixed_target.assert_not_called()

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

    def test_android_resume_routes_failed_prefix_and_active_clock_to_native_owner(self):
        specification = importlib.util.spec_from_file_location("android_resume_route_test", PATH.parent / "run_android.py")
        runner = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temporary, patch.dict(runner.os.environ):
            root = Path(temporary).resolve()
            inputs, runtime, installed = [root / n for n in ("inputs", "runtime", "installed")]
            for directory in (inputs / "work/config", inputs / "work/inventory", inputs / "game", inputs / "failed", inputs / "sources", runtime, installed):
                directory.mkdir(parents=True)
            (inputs / "input-hashes.json").write_text("{}")
            (inputs / "work/inventory/files.json").write_text('{"files": []}')
            (inputs / "metadata.dat").write_text("fixture metadata")
            (inputs / "converter.json").write_text('{"files": {"cpp/Fixture.cpp": {}}}')
            (inputs / "pause.json").write_text('{"paused_seconds": 0, "paused_at": null}')
            selection = {
                "resume": "failed",
                "converter_receipt": "converter.json",
                "converter_receipt_sha256": "fixture digest",
                "sources": "sources",
                "sources_compressed": True,
                "metadata": "metadata.dat",
            }
            request = inputs / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "resume": selection,
                        "target": {"profile": "recipe/fixture.json", "source": "sources"},
                        "output": "continued",
                        "compile_timeout_seconds": 7200,
                        "pause_clock": "pause.json",
                        "measure_jobs": [407, 410, 418],
                    }
                )
            )
            captured = {}

            def native_run(production, **kwargs):
                captured.update(production)
                Path(production["output"]).mkdir()
                return {"success": True}

            backend = SimpleNamespace(native=BACKEND.native, target_inputs=lambda value: None)
            module_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
            with (
                patch.object(runner.importlib.util, "spec_from_file_location", return_value=module_spec),
                patch.object(runner.importlib.util, "module_from_spec", return_value=backend),
                patch.object(BACKEND.native, "run", side_effect=native_run),
            ):
                runner.run(request, runtime, installed)
            self.assertEqual(captured["resume"], str(inputs / "failed"))
            self.assertEqual(captured["pause_clock"], str(inputs / "pause.json"))
            self.assertEqual(captured["compile_timeout_seconds"], 7200)
            self.assertEqual(captured["measure_jobs"], [407, 410, 418])
            self.assertNotIn("compiled", captured)
            baseline = json.loads(request.read_text())
            outside = root / "outside-provider"
            outside.mkdir()
            for mode in ("resume", "relink"):
                for name in ("compiled" if mode == "relink" else "resume", "converter_receipt", "sources", "metadata", "target_source"):
                    link = inputs / ("escape-" + mode + "-" + name)
                    link.symlink_to(outside, target_is_directory=True)
                    attempted = json.loads(json.dumps(baseline))
                    supplied = attempted.pop("resume")
                    if mode == "relink":
                        supplied["compiled"] = supplied.pop("resume")
                    attempted[mode] = supplied
                    attempted["output"] = "escaped-output"
                    if name == "target_source":
                        attempted["target"]["source"] = link.name
                    else:
                        supplied[name] = link.name
                    request.write_text(json.dumps(attempted))
                    with (
                        self.subTest(mode=mode, provider=name),
                        patch.object(runner.importlib.util, "spec_from_file_location", return_value=module_spec),
                        patch.object(runner.importlib.util, "module_from_spec", return_value=backend),
                        patch.object(BACKEND.native, "run", side_effect=AssertionError("native production must not start")),
                    ):
                        with self.assertRaisesRegex(ValueError, "provider escapes private"):
                            runner.run(request, runtime, installed)
                    self.assertFalse((inputs / "work/escaped-output").exists())

    def test_android_packaging_maps_pinned_drift_receipts_to_private_paths(self):
        specification = importlib.util.spec_from_file_location("android_packaging_route_test", PATH.parent / "run_android.py")
        runner = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            inputs, runtime, installed = [root / n for n in ("inputs", "runtime", "installed")]
            for directory in (inputs, runtime, installed):
                directory.mkdir()
            proofs = {
                name: {"path": name + ".json", "sha256": "fixture pin " + name} for name in ("historical_exact", "current_deterministic", "difference_map")
            }
            captured = {}

            def build(request, output):
                captured.update(json.loads(request.read_text()))

            owner = SimpleNamespace(PROFILE="fixture profile", build=build, sign=lambda request, output: {"apk_sha256": "fixture apk", "apk_bytes": 123})
            module_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
            selection = {
                "targets": "targets.json",
                "manifest": "manifest.json",
                "code": {},
                "key_directory": "key",
                "version_code": 1,
                "drift": {"assets/bin/Data/fixture": proofs},
            }
            with (
                patch.object(runner.importlib.util, "spec_from_file_location", return_value=module_spec),
                patch.object(runner.importlib.util, "module_from_spec", return_value=owner),
            ):
                runner.package_job({"packaging": selection, "output": "package"}, inputs, runtime, installed, BACKEND.native)
            for name, pin in captured["drift"]["assets/bin/Data/fixture"].items():
                self.assertEqual(pin, {"path": str(inputs / (name + ".json")), "sha256": proofs[name]["sha256"]})

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
