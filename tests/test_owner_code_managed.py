"""Owner-managed inputs are source providers, never prepared game outputs."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/managed.py"
SPEC = importlib.util.spec_from_file_location("owner_code_managed_tests", PATH)
MANAGED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANAGED)


class OwnerCodeManagedTests(unittest.TestCase):
    def test_nested_python_uses_the_embedded_android_host_abi(self):
        native = "/installed/lib/arm64/"
        runtime = "/private/runtime/python"
        with patch.multiple(sys, platform="android", executable=native + "libpythonhost.so", prefix=runtime):
            self.assertEqual(
                MANAGED.python_command("producer.py", isolated=True),
                [native + "libpythonhost.so", native + "libpython3.14.so", runtime, "producer.py"],
            )
        self.assertEqual(MANAGED.python_command("producer.py", isolated=True), [sys.executable, "-I", "producer.py"])

    def test_signed_sdk_compiler_uses_explicit_android_runtime_and_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk = root / "SDK with spaces"
            relative = "DotNetSdkRoslyn/csc.dll"
            compiler_path = sdk / "Unity.app/Contents" / relative
            compiler_path.parent.mkdir(parents=True)
            compiler_path.write_bytes(b"authored compiler fixture")
            inputs = {"compiler/csc.dll": (relative, MANAGED.native.sha(compiler_path))}
            launcher = root / "installed-dotnet"
            assembly = root / "Fixture.dll"
            source = root / "Source File.cs"
            reference = root / "SDK Reference.dll"
            with patch.object(sys.modules["phone_sdk_compiler"], "INPUTS", inputs):
                compiler = MANAGED.SdkCompiler(sdk, launcher, root)
                with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                    compiler.compile(assembly, [source], [reference], ["-target:library"])
                runtime = json.loads(compiler.runtime_config.read_text())
                self.assertEqual(runtime["runtimeOptions"]["framework"]["version"], "8.0.32")
                rsp = assembly.with_suffix(".rsp")
                self.assertEqual(
                    run.call_args.args[0],
                    [str(launcher), "exec", "--runtimeconfig", str(compiler.runtime_config), str(compiler_path), "-noconfig", "-nostdlib+", "@" + str(rsp)],
                )
                response = rsp.read_text().splitlines()
                self.assertIn("-r:" + json.dumps(str(reference)), response)
                self.assertIn(json.dumps(str(source)), response)
                compiler_path.write_bytes(b"changed fixture")
                with self.assertRaisesRegex(ValueError, "Pinned SDK Roslyn"):
                    compiler.verify()

    def test_current_runtime_manifest_reaches_reference_resolution(self):
        # Exercise the real current manifest, which outgrew the old 128-file
        # guard. Stop at SDK resolution; no compiler or game inputs are needed.
        class ReferencesReached(Exception):
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(MANAGED.phone_unity_compile, "references", side_effect=ReferencesReached):
                with self.assertRaises(ReferencesReached):
                    MANAGED.gameplay(root, root, {}, root, {}, None, root, {}, [root] * 3, [root] * 14)
                (root / "gameplay").rmdir()
                with self.assertRaisesRegex(ValueError, "source membership changed"):
                    MANAGED.gameplay(root, root, {}, root, {}, None, root, {}, [], [root] * 14)

    def test_fixed_target_uses_staged_paths_and_case_insensitive_source_order(self):
        public = [Path(n) for n in ("TeleportMaterialBoundary.cs", "TeleporterWorldBoundary.cs", "ActiveClientBoundary.cs", "LabDiagnostics.cs")]
        support, maps = [Path("support/Affix.cs")], [Path("maps/OriginalBodyVisualMap.cs")]
        self.assertEqual(
            [p.name for p in MANAGED.target_source_order(public, support, maps)],
            [
                "LabDiagnostics.cs",
                "ActiveClientBoundary.cs",
                "OriginalBodyVisualMap.cs",
                "TeleporterWorldBoundary.cs",
                "TeleportMaterialBoundary.cs",
                "Affix.cs",
            ],
        )

    def test_postprocessor_only_sees_selected_providers_from_each_reference_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk, original = root / "sdk", root / "original"
            sdk.mkdir()
            original.mkdir()
            selected = sdk / "netstandard.dll"
            selected.write_bytes(b"authored selected provider")
            (original / selected.name).write_bytes(b"authored conflicting sibling")
            game = original / "Game.dll"
            game.write_bytes(b"authored game-reference fixture")
            staged = MANAGED.postprocessor_references([selected, game], root / "references")
            self.assertEqual({p.name for p in staged}, {selected.name, game.name})
            self.assertEqual(staged[0].read_bytes(), selected.read_bytes())
            self.assertEqual(staged[1].read_bytes(), game.read_bytes())
            self.assertEqual({p.parent for p in staged}, {root / "references"})
            self.assertEqual((original / selected.name).read_bytes(), b"authored conflicting sibling")

    def test_source_profile_has_no_historical_or_generated_supplier(self):
        self.assertEqual(MANAGED.native.sha(MANAGED.PROFILE), MANAGED.PROFILE_SHA)
        profile = json.loads(MANAGED.PROFILE.read_text())
        self.assertEqual(len(profile["base_providers"]), 320)
        self.assertEqual(sum(r["provider"] == "sdk" for r in profile["base_providers"].values()), 272)
        self.assertEqual(sum(r["provider"] == "original" for r in profile["base_providers"].values()), 48)
        self.assertEqual(len(profile["produced_assemblies"]), 12)
        self.assertEqual(len(profile["support_sources"]), 14)
        self.assertNotIn("work/", MANAGED.PROFILE.read_text())
        self.assertNotIn("/Users/", MANAGED.PROFILE.read_text())
        self.assertFalse(set(profile["base_providers"]) & set(profile["produced_assemblies"]))

    def test_base_providers_stay_in_original_or_sdk_roots_and_refuse_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sdk, game = root / "sdk", root / "game"
            sdk.mkdir()
            game.mkdir()
            a, b = sdk / "Sdk.dll", game / "Original.dll"
            a.write_bytes(b"independently authored SDK input")
            b.write_bytes(b"independently authored original input")
            profile = {
                "base_providers": {
                    "Sdk.dll": {"provider": "sdk", "relative": a.name, "sha256": MANAGED.native.sha(a)},
                    "Original.dll": {"provider": "original", "relative": b.name, "sha256": MANAGED.native.sha(b)},
                }
            }
            self.assertEqual(MANAGED.base_providers(profile, sdk, game), {"Sdk.dll": a, "Original.dll": b})
            b.write_bytes(b"changed original")
            with self.assertRaisesRegex(ValueError, "base provider drift"):
                MANAGED.base_providers(profile, sdk, game)
            profile["base_providers"]["Sdk.dll"]["relative"] = "../escape.dll"
            with self.assertRaisesRegex(ValueError, "relative"):
                MANAGED.base_providers(profile, sdk, game)

    def test_source_request_cannot_supply_a_prepared_game_dll(self):
        with self.assertRaisesRegex(ValueError, "explicit package"):
            MANAGED.bind_paths({"prepared_game": "unused.dll"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            values = {}
            for name in MANAGED.INPUT_FIELDS:
                path = root / name
                if name in {"packages", "netstandard_ref"}:
                    path.mkdir()
                else:
                    path.write_bytes(b"independently authored input")
                values[name] = str(path)
            self.assertEqual(len(MANAGED.bind_paths(values)), 10)
            signed = {k: v for k, v in values.items() if k != "decoder"}
            self.assertEqual(set(MANAGED.bind_paths(signed, signed_audio=True)), set(signed))
            with self.assertRaisesRegex(ValueError, "decoder for historical staging"):
                MANAGED.bind_paths(signed)
            values["dotnet"] = values["packages"]
            with self.assertRaisesRegex(ValueError, "provider kind"):
                MANAGED.bind_paths(values)

    def test_signed_stage_binds_index_and_copy_to_the_same_workspace_without_decoder(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(MANAGED.wwise_bank_index, "owner_index") as index,
            patch.object(MANAGED.owner_audio_prefab, "reconstruct") as prefab,
            patch.object(MANAGED.wwise_init_platform, "produce_owner") as init,
            patch.object(MANAGED.legacy, "run") as legacy,
            patch.object(MANAGED, "invoke") as invoke,
        ):
            work, game = Path(temporary).resolve(), Path("/owner/game")
            output = work / "managed"
            output.mkdir()
            stage, prefab_path, bank_path, init_dir = MANAGED.stage_source_audio(work, game, output)
        index.assert_called_once_with(work, bank_path.parent, False, decoder_executable=None)
        prefab.assert_called_once_with(work, prefab_path.parent)
        init.assert_called_once_with(work, game, init_dir)
        legacy.assert_not_called()
        command, destination, label = invoke.call_args.args
        arguments = dict(zip(command[2::2], command[3::2]))
        self.assertEqual(arguments["--owner-work"], work)
        self.assertEqual(arguments["--bank-index"], bank_path)
        self.assertEqual(arguments["--output-dir"], stage)
        self.assertEqual((destination, label), (output, "stage-audio"))


if __name__ == "__main__":
    unittest.main()
