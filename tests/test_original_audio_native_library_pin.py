from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import os
import subprocess
import tempfile
import unittest


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


ROOT = repository_root()
TESTS = Path(__file__).resolve().parent
PRODUCER = ROOT / "scripts/lab/original_game_audio_produce.py"
GENERATOR = ROOT / "tools/unity/support/audio/generators/generate_accepted_request_pin.py"
PROVIDER = ROOT / "tools/unity/support/audio/bootstrap/GameAudioOriginalAcceptedRequestProvider.cs"
FIXTURES = TESTS / "fixtures"
DEPENDENCIES = FIXTURES / "native_library_pin_provider_dependencies.cs"
HARNESS = FIXTURES / "NativeLibraryPinProviderHarness.cs"
STALE_NATIVE_SHA256 = "bb5879b4eb38b81dc3830a1662ba467b60b595e7fedb88a1301d3161f8ab9304"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def provider_native_pin() -> str:
    source = PROVIDER.read_text(encoding="utf-8")
    match = re.search(r'AcceptedNativeLibrarySha256\s*=\s*"([0-9a-f]{64})"', source)
    if match is None:
        raise AssertionError("provider has no exact accepted native-library pin")
    return match.group(1)


def generated_pin_source(expected: dict[str, str], native_override: str | None = None) -> str:
    request = dict(expected)
    request.update(
        {
            "requested": "true",
            "passive_pcm_capture_requested": "false",
            "passive_pcm_capture_music_output_requested": "false",
            "passive_pcm_capture_after_authority_skill_requested": "false",
            "request_id": "0123456789abcdef0123456789abcdef",
            "request_receipt_sha256": "a" * 64,
            "build_input_contract_sha256": "b" * 64,
            "stage_receipt_sha256": "c" * 64,
        }
    )
    if native_override is not None:
        request["native_library_sha256"] = native_override
    names = {
        "Requested": request["requested"],
        "PassivePcmCaptureRequested": request["passive_pcm_capture_requested"],
        "PassivePcmCaptureMusicOutputRequested": request["passive_pcm_capture_music_output_requested"],
        "PassivePcmCaptureAfterAuthoritySkillRequested": request["passive_pcm_capture_after_authority_skill_requested"],
        "RequestId": request["request_id"],
        "RequestReceiptSha256": request["request_receipt_sha256"],
        "BuildInputContractSha256": request["build_input_contract_sha256"],
        "StageReceiptSha256": request["stage_receipt_sha256"],
        "AdaptedInitSha256": request["adapted_init_sha256"],
        "GameAssemblySha256": request["game_assembly_sha256"],
        "ComposedGameSha256": request["composed_game_sha256"],
        "RawApiSha256": request["raw_api_sha256"],
        "AdaptedApiSha256": request["adapted_api_sha256"],
        "ObservedApiSha256": request["observed_api_sha256"],
        "InstrumentedApiSha256": request["instrumented_api_sha256"],
        "NativeLibrarySha256": request["native_library_sha256"],
    }
    literals = []
    for name, value in names.items():
        if name in {"Requested", "PassivePcmCaptureRequested", "PassivePcmCaptureMusicOutputRequested", "PassivePcmCaptureAfterAuthoritySkillRequested"}:
            literals.append(f"    internal const bool {name} = {value};")
        else:
            literals.append(f'    internal const string {name} = "{value}";')
    return "internal static class GameAudioOriginalGeneratedRequestPin\n{\n" + "\n".join(literals) + "\n}\n"


def stage_pin_source(expected: dict[str, str]) -> str:
    names = ", ".join(f'"Bank{i:03}"' for i in range(153))
    return (
        "internal static class GameAudioOriginalGeneratedStagePin\n{\n"
        f'    internal const string ReceiptSha256 = "{"c" * 64}";\n'
        f'    internal const string AcceptedInputId = "{expected["accepted_input_id"]}";\n'
        f"    internal static readonly string[] BankNames = new string[] {{ {names} }};\n"
        "}\n"
    )


class NativePinSourceCoherenceTests(unittest.TestCase):
    def test_producer_generator_and_provider_share_one_native_pin(self) -> None:
        producer = load_module(PRODUCER, "native_pin_producer_contract")
        generator = load_module(GENERATOR, "native_pin_generator_contract")
        self.assertEqual(producer.LINEAGE["native_library_sha256"], generator.EXPECTED["native_library_sha256"])
        self.assertEqual(producer.LINEAGE["native_library_sha256"], provider_native_pin())
        self.assertIn("native_library_sha256", generator.CONTRACT_ROLES)


class NativePinProviderCompileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        unity = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        cls.mono = unity / "MonoBleedingEdge/bin/mono"
        cls.csc = unity / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not cls.mono.is_file() or not cls.csc.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn host compiler is unavailable")

    def compile_and_run(self, temp: Path, native_override: str | None, expected_refusal: str) -> None:
        generator = load_module(GENERATOR, "native_pin_generator_compile")
        dynamic_request_pin = temp / "GameAudioOriginalGeneratedRequestPin.cs"
        dynamic_stage_pin = temp / "GameAudioOriginalGeneratedStagePin.cs"
        dynamic_request_pin.write_text(generated_pin_source(generator.EXPECTED, native_override), encoding="utf-8")
        dynamic_stage_pin.write_text(stage_pin_source(generator.EXPECTED), encoding="utf-8")
        executable = temp / "provider-validation.exe"
        command = [
            str(self.mono),
            str(self.csc),
            "-nologo",
            "-langversion:latest",
            "-target:exe",
            f"-out:{executable}",
            str(DEPENDENCIES),
            str(PROVIDER),
            str(dynamic_stage_pin),
            str(dynamic_request_pin),
            str(HARNESS),
        ]
        compiled = subprocess.run(command, cwd=temp, capture_output=True, text=True, check=False)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        ran = subprocess.run([str(self.mono), str(executable), expected_refusal], cwd=temp, capture_output=True, text=True, check=False)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_actual_provider_accepts_current_lineage_and_refuses_stale_bb_mutant(self) -> None:
        producer = load_module(PRODUCER, "native_pin_provider_compile_contract")
        generator = load_module(GENERATOR, "native_pin_provider_compile_generator")
        current = producer.LINEAGE["native_library_sha256"]
        self.assertEqual(current, generator.EXPECTED["native_library_sha256"])
        self.assertEqual(current, provider_native_pin())
        with tempfile.TemporaryDirectory(prefix="native-pin-provider-current-") as name:
            self.compile_and_run(Path(name), None, "<null>")
        with tempfile.TemporaryDirectory(prefix="native-pin-provider-stale-") as name:
            self.compile_and_run(Path(name), STALE_NATIVE_SHA256, "audio_native_library_pin_mismatch")


if __name__ == "__main__":
    unittest.main()
