"""Host contracts for Captain's native PrepSupplyDrop identity."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "recipe" / "runtime-sources.json").is_file():
            return parent
    raise RuntimeError("could not find repository root from test location")


def member_after(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed member: {marker}")


def method_body(source: str, signature: str) -> str:
    member = member_after(source, signature)
    opening = member.index("{")
    return member[opening + 1 : -1]


class CaptainSetupIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = find_repo_root(Path(__file__).resolve())
        owner = root / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"
        cls.source = owner.read_text(encoding="utf-8")

    def test_canonical_policy_uses_serialized_machine_and_state(self) -> None:
        helper = method_body(
            self.source,
            "public static bool CaptainSetupSupplyBeaconIdentityMatches(",
        )
        self.assertIn('"Skillswap"', helper)
        self.assertIn('"EntityStates.Captain.Weapon.SetupSupplyDrop"', helper)
        self.assertIn("CaptainSetupSupplyBeaconIdentityMatches(captainSpecialSkillDef.activationStateMachineName", self.source)
        self.assertIn("captainSpecialStateType.FullName", self.source)
        self.assertIn("body.skillLocator.special != captainSupplyBeaconComponents[3]", self.source)
        self.assertIn("body.skillLocator.primary != captainSupplyBeaconComponents[0]", self.source)
        self.assertIn("body.skillLocator.secondary != captainSupplyBeaconComponents[1]", self.source)

    def test_extracted_production_policy_accepts_only_native_pair(self) -> None:
        compiler = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe")
        mono = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
        if not compiler.is_file() or not mono.is_file():
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")

        policy = member_after(
            self.source,
            "public static bool CaptainSetupSupplyBeaconIdentityMatches(",
        )
        wrapper = f"""using System;
public static class ProductionCaptureHelper {{
    {policy}
}}
public static class Program {{
    static void Require(bool condition, string message) {{
        if (!condition) throw new Exception(message);
    }}
    public static int Main() {{
        Require(ProductionCaptureHelper.CaptainSetupSupplyBeaconIdentityMatches(
            "Skillswap", "EntityStates.Captain.Weapon.SetupSupplyDrop"),
            "serialized Captain special identity should pass");
        Require(!ProductionCaptureHelper.CaptainSetupSupplyBeaconIdentityMatches(
            "Weapon", "EntityStates.Captain.Weapon.SetupSupplyDrop"),
            "Weapon is not the PrepSupplyDrop activation machine");
        Require(!ProductionCaptureHelper.CaptainSetupSupplyBeaconIdentityMatches(
            "Skillswap", "EntityStates.Captain.Weapon.CallSupplyDropHealing"),
            "the setup state must remain distinct from its call-drop skills");
        Require(!ProductionCaptureHelper.CaptainSetupSupplyBeaconIdentityMatches(null, null),
            "missing identity must fail closed");
        return 0;
    }}
}}
"""
        with tempfile.TemporaryDirectory(prefix="captain-setup-identity-", dir=Path(__file__).resolve().parent) as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "IdentityPolicyExtracted.cs"
            assembly_path = temp / "IdentityPolicyExtracted.exe"
            source_path.write_text(wrapper, encoding="utf-8")
            subprocess.run(
                [str(mono), str(compiler), "-noconfig", f"-out:{assembly_path}", str(source_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [str(mono), str(assembly_path)],
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
