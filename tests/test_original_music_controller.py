from __future__ import annotations

import os
import ast
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_repository_root()
SOURCE_ROOT = Path(os.environ.get("ORIGINAL_MUSIC_SOURCE_ROOT", ROOT)).resolve()
UNITY = Path(
    os.environ.get(
        "UNITY_EDITOR_PATH",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
    )
)
MONO = UNITY / "MonoBleedingEdge/bin/mono"
CSC = UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CORE_MODULE = UNITY / "Managed/UnityEngine/UnityEngine.CoreModule.dll"
OWNER = Path(
    os.environ.get(
        "ORIGINAL_MUSIC_OWNER_SOURCE",
        SOURCE_ROOT / "tools/unity/runtime/session/PortSessionOriginalMusicControllerOwner.cs",
    )
).resolve()
CONTRACT = Path(
    os.environ.get(
        "ORIGINAL_MUSIC_CONTRACT_SOURCE",
        SOURCE_ROOT / "tools/unity/runtime/session/OriginalMusicControllerContract.cs",
    )
).resolve()
BOOTSTRAP = Path(
    os.environ.get(
        "ORIGINAL_MUSIC_BOOTSTRAP_SOURCE",
        SOURCE_ROOT / "tools/unity/support/audio/bootstrap/OriginalGameAudioPassivePcmOwner.cs",
    )
).resolve()
PRODUCER = Path(
    os.environ.get(
        "ORIGINAL_MUSIC_PRODUCER_SOURCE",
        SOURCE_ROOT / "scripts/lab/original_game_audio_produce.py",
    )
).resolve()
TESTS = Path(__file__).resolve().parent
PASSIVE_WINDOW = Path(
    os.environ.get(
        "ORIGINAL_PCM_WINDOW_SOURCE",
        SOURCE_ROOT / "tools/unity/support/audio/bootstrap/PassivePcmCaptureWindow.cs",
    )
).resolve()
PASSIVE_CONTRACT = (SOURCE_ROOT / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs").resolve()


def method_body(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"unclosed method body: {signature}")


class OriginalMusicControllerTests(unittest.TestCase):
    def test_actual_passive_window_callback_composes_music_without_replacing_guard(
        self,
    ) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn is unavailable")
        self.assertTrue(
            PASSIVE_WINDOW.is_file(),
            f"passive capture window source is unavailable: {PASSIVE_WINDOW}",
        )
        with tempfile.TemporaryDirectory(prefix="music-installed-guard-") as temp:
            output = Path(temp) / "InstalledGuardComposition.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-target:exe",
                    f"-out:{output}",
                    str(PASSIVE_WINDOW),
                    str(PASSIVE_CONTRACT),
                    str(TESTS / "InstalledGuardCompositionFixture.cs"),
                    str(TESTS / "InstalledGuardCompositionHarness.cs"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn(
                "PASS: 6 assertions against the actual passive window callback",
                ran.stdout,
            )

    def test_failed_preload_retains_root_until_callback_state_is_known(self) -> None:
        owner = OWNER.read_text()
        complete = method_body(owner, "void CompletePrefabLoad(")
        catch = complete.split("catch (Exception error)", 1)[1]
        self.assertIn("failedInstanceCleanupPending = ownedControllerRoot", catch)
        self.assertIn("sourceCallbackRetirementUnknown = true", catch)
        self.assertNotIn("Destroy(ownedControllerRoot)", catch)
        self.assertNotIn("ownedControllerRoot = null", catch)

        cleanup_gate = method_body(owner, "internal bool CanBeginFailedInstanceCleanup(")
        self.assertIn("!snapshot.sourceCallbackRetirementUnknown", cleanup_gate)
        self.assertIn("sourceSceneCallbackObserverAttached", cleanup_gate)
        self.assertIn("sourceSceneLoadedCallbackRetiredObserved", cleanup_gate)

        term = method_body(owner, "void BeforeOriginalAudioTerm(")
        self.assertIn("snapshot.sourceCallbackRetirementUnknown", term)
        self.assertIn("throw new InvalidOperationException", term)

        preload_start = complete.index("ownedController.PreloadForCutsceneStart()")
        observer_registration = complete.index("AttachSourceCallbackRetirementObserver()", preload_start)
        verification = complete.index("var cloneListeners", observer_registration)
        self.assertLess(preload_start, observer_registration)
        self.assertLess(observer_registration, verification)

    def test_owner_destroy_cannot_erase_an_unobserved_callback(self) -> None:
        owner = OWNER.read_text()
        on_destroy = method_body(owner, "void OnDestroy()")
        self.assertIn("if (sourceSceneCallbackObserverAttached)", on_destroy)
        self.assertIn("!snapshot.sourceSceneLoadedCallbackRetiredObserved", on_destroy)
        self.assertIn("snapshot.sourceCallbackRetirementUnknown = true", on_destroy)
        self.assertLess(
            on_destroy.index("snapshot.sourceCallbackRetirementUnknown = true"),
            on_destroy.index("sceneLoaded -= ObserveSceneLoadedAfterPreload"),
        )
        self.assertIn("sourceSceneCallbackObserverAttached = false", on_destroy)
        self.assertNotIn("ownedControllerRoot = null", on_destroy)

    def test_music_registers_with_the_already_installed_pcm_guard(self) -> None:
        bootstrap = BOOTSTRAP.read_text()
        registration = method_body(bootstrap, "internal static bool RegisterMusicBeforeTerm(Action handler)")
        self.assertIn(
            "processOwner.window.RegisterBeforeEngineTermParticipant(handler)",
            registration,
        )
        self.assertNotIn("SetValue", registration)
        self.assertNotIn("installedBeforeTermGuard =", registration)
        self.assertIn("ReadBeforeEngineTermGuard()", registration)

        window = PASSIVE_WINDOW.read_text()
        self.assertIn("Action ownedGuard = BeforeOriginalEngineTerm;", window)
        self.assertIn("ReferenceEquals(readBeforeEngineTermHandler(), ownedGuard)", window)
        pre_term = method_body(window, "internal void BeforeOriginalEngineTerm()")
        self.assertIn("RunBeforeTermParticipant();", pre_term)
        self.assertLess(
            pre_term.rindex("closed = true;"),
            pre_term.rindex("RunBeforeTermParticipant();"),
        )
        self.assertIn(
            "beforeTermParticipant();",
            method_body(window, "private void RunBeforeTermParticipant()"),
        )

    def test_reflection_surface_has_only_exact_preserve_annotations(self) -> None:
        bootstrap = BOOTSTRAP.read_text()
        self.assertIn("using UnityEngine.Scripting;", bootstrap)
        self.assertRegex(
            bootstrap,
            r"(?s)\[Preserve\]\s+internal sealed class OriginalGameAudioPassivePcmOwner",
        )
        self.assertRegex(
            bootstrap,
            r"(?s)\[Preserve\]\s+get\s*\{\s*lock \(Sync\) return processOwner;",
        )
        self.assertRegex(
            bootstrap,
            r"(?s)\[Preserve\]\s+internal static bool RegisterMusicBeforeTerm\(Action handler\)",
        )
        self.assertEqual(bootstrap.count("[Preserve]"), 3)

        producer = ast.parse(PRODUCER.read_text())
        source_hashes = None
        for node in producer.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "OWNER_SOURCE_HASHES" for target in node.targets):
                source_hashes = ast.literal_eval(node.value)
                break
        self.assertIsNotNone(source_hashes, "producer does not pin owner source hashes")
        self.assertEqual(
            source_hashes["bootstrap/OriginalGameAudioPassivePcmOwner.cs"],
            hashlib.sha256(BOOTSTRAP.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            source_hashes["bootstrap/PassivePcmCaptureWindow.cs"],
            hashlib.sha256(PASSIVE_WINDOW.read_bytes()).hexdigest(),
        )

    def test_passive_output_identity_sources_are_bound_by_producer(self) -> None:
        producer = ast.parse(PRODUCER.read_text())
        source_hashes = None
        for node in producer.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "OWNER_SOURCE_HASHES" for target in node.targets):
                source_hashes = ast.literal_eval(node.value)
                break
        self.assertIsNotNone(source_hashes, "producer does not pin owner source hashes")
        changed_inputs = {
            "../../runtime/session/PortSessionOriginalAudioOwner.cs": SOURCE_ROOT / "tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs",
            "bootstrap/OriginalGameAudioPassivePcmOwner.cs": SOURCE_ROOT / "tools/unity/support/audio/bootstrap/OriginalGameAudioPassivePcmOwner.cs",
            "bootstrap/PassivePcmCaptureWindow.cs": PASSIVE_WINDOW,
            "core/GameAudioOriginalPassivePcmContract.cs": PASSIVE_CONTRACT,
        }
        for role, source in changed_inputs.items():
            self.assertEqual(source_hashes[role], hashlib.sha256(source.read_bytes()).hexdigest(), role)

    def test_music_contract_mutants_against_authored_contract(self) -> None:
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn is unavailable")
        with tempfile.TemporaryDirectory(prefix="original-music-contract-") as temp:
            output = Path(temp) / "MusicControllerContractHarness.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-target:exe",
                    f"-out:{output}",
                    str(CONTRACT),
                    str(TESTS / "MusicControllerContractHarness.cs"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: 47 original music owner contract assertions", ran.stdout)

    def test_compiled_preserve_metadata_is_narrow(self) -> None:
        if not MONO.is_file() or not CSC.is_file() or not CORE_MODULE.is_file():
            self.skipTest("pinned Unity Mono/Roslyn/CoreModule is unavailable")
        with tempfile.TemporaryDirectory(prefix="original-music-preserve-") as temp:
            temp_path = Path(temp)
            output = temp_path / "BootstrapPreserveCandidate.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-target:exe",
                    f"-out:{output}",
                    f"-r:{CORE_MODULE}",
                    str(PASSIVE_CONTRACT),
                    str(BOOTSTRAP),
                    str(TESTS / "BootstrapPreservationDependencyFixture.cs"),
                    str(TESTS / "PreservedBootstrapReflectionHarness.cs"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            env = dict(os.environ, MONO_PATH=str(CORE_MODULE.parent))
            ran = subprocess.run(
                [str(MONO), str(output), str(output)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: exact reflection-bound bootstrap members", ran.stdout)


if __name__ == "__main__":
    unittest.main()
