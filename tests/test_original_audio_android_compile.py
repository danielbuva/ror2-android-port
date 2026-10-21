from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
import uuid


def find_repo_root() -> Path:
    marker = Path("scripts/lab/original_game_audio_produce.py")
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from test path")


ROOT = find_repo_root()
PRODUCER_PATH = ROOT / "scripts/lab/original_game_audio_produce.py"
SOURCE = ROOT / "tools/unity/support/audio"
UNITY_CONTENTS = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO_DIR = UNITY_CONTENTS / "MonoBleedingEdge"
MONO = MONO_DIR / "bin/mono"
CSC = MONO_DIR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CECIL = MONO_DIR / "lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
OUTPUT_ROOT = ROOT / "work/coordination/original-audio-android-compile-review/r1"


def load_producer():
    spec = importlib.util.spec_from_file_location("original_game_audio_produce_test", PRODUCER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import the actual public audio producer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSPECTOR_SOURCE = r"""
using System;
using System.Linq;
using Mono.Cecil;

internal static class InspectMethod
{
    private static int Main(string[] args)
    {
        var module = ModuleDefinition.ReadModule(args[0]);
        var type = module.Types.Single(t => t.Name == "GameAudioOriginalAndroidNativeBootstrap");
        var method = type.Methods.Single(m => m.Name == "get_EnsureNativeLibraryLoaded");
        if (!method.HasBody) throw new InvalidOperationException("native-load getter has no IL body");
        foreach (var instruction in method.Body.Instructions)
        {
            var reference = instruction.Operand as MethodReference;
            var operand = reference != null ? reference.FullName : instruction.Operand;
            Console.WriteLine(instruction.OpCode.Code + "|" + (operand ?? ""));
        }
        return 0;
    }
}
"""


class OriginalAudioAndroidCompileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not all(path.is_file() for path in (MONO, CSC, CECIL)):
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn/Cecil unavailable")
        cls.producer = load_producer()
        local_path = ROOT / "work/config/local.json"
        if not local_path.is_file():
            raise unittest.SkipTest("configured legitimate game input unavailable")
        config = json.loads(local_path.read_text(encoding="utf-8"))
        managed = Path(config["game_path"]).resolve() / "Risk of Rain 2_Data/Managed"
        cls.plugin_overrides = {
            name: managed / name
            for name in (
                "AK.Wwise.Unity.API.dll",
                "AK.Wwise.Unity.MonoBehaviour.dll",
                "RoR2.dll",
            )
        }
        if not all(path.is_file() and not path.is_symlink() for path in cls.plugin_overrides.values()):
            raise unittest.SkipTest("required original managed assembly inputs unavailable")
        cls.options, cls.references = cls.producer.unity_reference_options(UNITY_CONTENTS, ROOT, cls.plugin_overrides)
        cls.work = OUTPUT_ROOT / ("pytest-" + uuid.uuid4().hex)
        cls.work.mkdir(parents=True, exist_ok=False)
        cls.logs = cls.work / "logs"
        cls.logs.mkdir()
        cls.inspector_source = cls.work / "InspectMethod.cs"
        cls.inspector_source.write_text(INSPECTOR_SOURCE, encoding="utf-8")
        cls.inspector = cls.work / "InspectMethod.exe"
        compiled = subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-target:exe",
                "-r:" + str(CECIL),
                "-out:" + str(cls.inspector),
                str(cls.inspector_source),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if compiled.returncode:
            raise AssertionError("Cecil IL inspector compile failed: " + compiled.stdout + compiled.stderr)

        cls.observer = cls.work / "OriginalOwnerProbeObserver.dll"
        cls.producer.run(
            "compile_observer",
            [
                str(MONO),
                str(CSC),
                "-target:library",
                "-deterministic+",
                "-out:" + str(cls.observer),
                str(SOURCE / "core/OriginalOwnerProbeObserver.cs"),
            ],
            cls.logs / "observer.log",
        )
        cls.core = cls.work / "GameAudioOriginalCore.dll"
        cls.producer.compile_library(
            "compile_core",
            MONO,
            CSC,
            cls.core,
            [SOURCE / "core/GameAudioOriginalReadiness.cs", SOURCE / "core/GameAudioOriginalOwner.cs"],
            cls.options,
            [cls.observer],
            cls.work,
        )

    def compile_bootstrap(self, name: str, options: list[str]) -> tuple[Path, str]:
        output = self.work / (name + ".dll")
        self.producer.compile_library(
            name,
            MONO,
            CSC,
            output,
            sorted((SOURCE / "bootstrap").glob("*.cs")),
            options,
            [
                self.core,
                self.plugin_overrides["AK.Wwise.Unity.API.dll"],
                self.observer,
            ],
            self.work,
        )
        env = {"MONO_PATH": str(CECIL.parent)}
        inspected = subprocess.run(
            [str(MONO), str(self.inspector), str(output)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
        return output, inspected.stdout

    def test_android_symbol_compiles_real_java_load_path_and_editor_excludes_it(self) -> None:
        self.assertIn("-define:UNITY_ANDROID", self.options)
        self.assertIn("UnityEngine.AndroidJNIModule.dll", {path.name for path in self.references})
        android_dll, android_il = self.compile_bootstrap("bootstrap-android", self.options)
        self.assertTrue(android_dll.is_file())
        self.assertIn("Newobj|System.Void UnityEngine.AndroidJavaClass::.ctor(System.String)", android_il)
        self.assertIn("CallStatic", android_il)
        self.assertIn("Ldstr|loadLibrary", android_il)
        self.assertIn("Ldstr|AkSoundEngine", android_il)

        editor_options = ["-define:UNITY_ANDROID,UNITY_EDITOR" if option == "-define:UNITY_ANDROID" else option for option in self.options]
        editor_dll, editor_il = self.compile_bootstrap("bootstrap-editor-negative", editor_options)
        self.assertTrue(editor_dll.is_file())
        self.assertNotIn("UnityEngine.AndroidJavaClass::.ctor", editor_il)
        self.assertNotIn("CallStatic", editor_il)
        self.assertNotIn("Ldstr|loadLibrary", editor_il)


if __name__ == "__main__":
    unittest.main()
