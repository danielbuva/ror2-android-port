"""Execute the production source-enabled state-machine restoration contract."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT_MARKER = Path("recipe/runtime-sources.json")
OWNER_RELATIVE = Path("tools/unity/runtime/world/AutomaticSpawnBoundary.cs")


def find_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / ROOT_MARKER).is_file():
            return parent
    raise RuntimeError("could not locate repository root")


def member(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed member: {signature}")


class AutomaticSpawnRestorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = find_root(Path(__file__).resolve())
        cls.candidate = (cls.root / OWNER_RELATIVE).read_text(encoding="utf-8")

    def test_capture_call_release_and_strict_count_contract(self) -> None:
        source = " ".join(self.candidate.split())
        roots = "var rootEntityStateMachines = body.GetComponents<EntityStateMachine>();"
        snapshot = "var sourceEnabledRootStateMachines = rootEntityStateMachines.Where("
        disable = "foreach (var component in body.GetComponents<MonoBehaviour>()) {"
        selection = "if (IsPlayableSpine())"
        call = "RestoreCapturedEnabledRootStateMachines(sourceEnabledRootStateMachines, cfg.integratedWorld)"
        capture_filter = ".Where(stateMachine => stateMachine && stateMachine.enabled).ToArray()"
        self.assertLess(source.index(roots), source.index(snapshot))
        self.assertLess(source.index(snapshot), source.index(disable))
        self.assertIn(capture_filter, source)
        self.assertLess(source.index(selection), source.index(call))
        self.assertIn("sourceEnabledRootStateMachines = null;", source)
        self.assertLess(source.index("sourceEnabledRootStateMachines = null;"), source.index("body.gameObject.SetActive(true)"))
        count = source.split("if (!cfg.combatSpine)", 1)[1].split("Physics.gravity =", 1)[0]
        self.assertIn("restoredSourceEnabledStateMachines", count)
        self.assertIn("int restoredSourceEnabledStateMachines = RestoreCapturedEnabledRootStateMachines(", source)
        helper = member(source, "internal static int RestoreCapturedEnabledRootStateMachines(")
        self.assertIn("if (!integratedWorld || captured == null)", helper)
        self.assertIn("foreach (var stateMachine in captured)", helper)
        self.assertIn("if (stateMachine && !stateMachine.enabled)", helper)
        self.assertIn("stateMachine.enabled = true;", helper)
        self.assertIn("return restored;", helper)

    def test_exact_production_restore_helper_with_fake_null_and_native_identity(self) -> None:
        compiler_root = Path(
            os.environ.get(
                "UNITY_EDITOR_PATH",
                "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
            )
        )
        compiler = compiler_root / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        mono = compiler_root / "MonoBleedingEdge/bin/mono"
        if not compiler.is_file() or not mono.is_file():
            self.skipTest("pinned Unity Roslyn/Mono host compiler is unavailable")

        helper = member(self.candidate, "internal static int RestoreCapturedEnabledRootStateMachines(")
        harness = f"""using System;
namespace UnityEngine {{
    public class Object {{
        public bool destroyed;
        public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.destroyed;
    }}
}}
public sealed class EntityStateMachine : UnityEngine.Object {{
    public string name; public bool enabled; public string state; public int networkIndex; public string customName;
}}
public static class ProductionRestore {{ {helper} }}
public static class Program {{
    static void Need(bool value, string message) {{ if (!value) throw new Exception(message); }}
    public static int Main() {{
        var body = new EntityStateMachine {{ name="Body", enabled=true, state="GenericCharacterMain", networkIndex=0, customName="Body" }};
        var weapon = new EntityStateMachine {{ name="Weapon", enabled=true, state="Idle", networkIndex=1, customName="Weapon" }};
        var offhand = new EntityStateMachine {{ name="Weapon2", enabled=false, state="Uninitialized", networkIndex=-1, customName="Weapon2" }};
        var disabledAtSource = new EntityStateMachine {{ name="SourceDisabled", enabled=false, state="Idle", networkIndex=-1, customName="Extra" }};
        var destroyed = new EntityStateMachine {{ name="Destroyed", enabled=false, state="Idle", networkIndex=-1 }};
        destroyed.destroyed = true;
        // Mirrors the production snapshot's pre-disable membership: Body/Weapon/Weapon2 were enabled at entry;
        // SourceDisabled was disabled and is therefore absent from this captured array.
        var captured = new[] {{ body, weapon, offhand, destroyed }};
        var networkRoster = new[] {{ body, weapon }};
        string offhandState = offhand.state, offhandCustomName = offhand.customName;
        int offhandNetworkIndex = offhand.networkIndex;
        int baselineCount = ProductionRestore.RestoreCapturedEnabledRootStateMachines(new[] {{ body, weapon }}, true);
        Need(baselineCount == 0 && body.enabled && weapon.enabled, "already-enabled baseline callbacks must remain unchanged");
        int restored = ProductionRestore.RestoreCapturedEnabledRootStateMachines(captured, true);
        Need(restored == 1 && offhand.enabled, "exact helper must restore and count the captured offhand");
        Need(body.enabled && weapon.enabled && restored == 1, "already re-enabled Body/Weapon must not be counted twice");
        Need(!disabledAtSource.enabled, "source-disabled machine excluded from capture must remain disabled");
        Need(!destroyed.enabled, "fake-null machine must be skipped safely");
        Need(offhand.state == offhandState && offhand.customName == offhandCustomName && offhand.networkIndex == offhandNetworkIndex,
            "restoration must preserve state, custom identity, and network index");
        Need(Object.ReferenceEquals(networkRoster[0], body) && Object.ReferenceEquals(networkRoster[1], weapon),
            "network roster identity must remain unchanged");
        var minimalOffhand = new EntityStateMachine {{ name="Weapon2", enabled=false, state="Uninitialized", networkIndex=-1 }};
        int minimalCount = ProductionRestore.RestoreCapturedEnabledRootStateMachines(new[] {{ minimalOffhand }}, false);
        Need(minimalCount == 0 && !minimalOffhand.enabled, "non-integrated path must not restore callbacks");
        Need(ProductionRestore.RestoreCapturedEnabledRootStateMachines(null, true) == 0, "null snapshot is unavailable and restores nothing");
        return 0;
    }}
}}
"""
        with tempfile.TemporaryDirectory(prefix="toolbot-spawn-policy-", dir=Path(__file__).resolve().parent) as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "ProductionRestore.cs"
            assembly_path = temp / "ProductionRestore.exe"
            source_path.write_text(harness, encoding="utf-8")
            subprocess.run(
                [str(mono), str(compiler), "-noconfig", f"-out:{assembly_path}", str(source_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run([str(mono), str(assembly_path)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
