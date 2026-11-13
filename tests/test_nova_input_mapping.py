"""Exercise production mapping admission and stick samples; no device input is simulated."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
ENGINE = EDITOR / "Managed/UnityEngine"


def production_member(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        depth += (source[position] == "{") - (source[position] == "}")
        if depth == 0:
            return source[start : position + 1]
    raise AssertionError(f"{declaration} does not close")


class NovaInputMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="nova-mapping-host-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = Path(cls.temp.name) / "mapping.exe"
        source = (ROOT / "tools/unity/runtime/input/NovaInputBridge.cs").read_text()
        members = "\n".join(
            production_member(source, declaration)
            for declaration in (
                "public class Mapping",
                "public class Raw",
                "public sealed class ButtonRebind",
                "public static class MappingStore",
                "public sealed class ControllerPresence",
                "static Vector2 Stick(",
                "static bool NeutralSample(",
            )
        )
        harness = Path(cls.temp.name) / "Production.cs"
        harness.write_text(
            "using System; using System.Linq; using UnityEngine;\n"
            "public static class AndroidOfflineSettings { public sealed class Values { public float deadzone=.18f; } "
            "public static Values current=new Values(); }\n"
            "public sealed class NovaInputBridge {\n" + members + "\n"
            "public static Vector2 SampleStick(Raw raw,int x,int y,float sign) { return Stick(raw,x,y,sign); }\n"
            "public static bool SampleNeutral(Raw raw,Mapping mapping) { return NeutralSample(raw,mapping); }\n}"
        )
        compiled = subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-r:System.Runtime.Serialization.dll",
                "-out:" + str(cls.exe),
                "-r:" + str(ENGINE / "UnityEngine.CoreModule.dll"),
                str(harness),
                str(ROOT / "tests/fixtures/NovaInputMappingHost.cs"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def case(self, name):
        result = subprocess.run(
            [str(MONO), str(self.exe), name, str(Path(self.temp.name) / name)],
            env=dict(os.environ, MONO_PATH=str(ENGINE)),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_mapping_requires_current_attempt_and_observation(self):
        self.case("provenance")

    def test_axes_buttons_and_signs_reject_invalid_or_ambiguous_bindings(self):
        self.case("binding-ranges")

    def test_interaction_is_optional_and_cannot_collide_with_other_buttons(self):
        self.case("interaction")

    def test_validation_does_not_change_current_or_candidate_bindings(self):
        self.case("nonmutating-validation")

    def test_radial_deadzone_rescales_clamps_and_honors_vertical_sign(self):
        self.case("stick")

    def test_all_buttons_and_mapped_axes_gate_controller_reacquisition(self):
        self.case("neutral-reacquisition")

    def test_reconnect_neutrality_matches_radial_stick_at_center_edge_and_diagonal(self):
        self.case("radial-neutral")

    def test_rebinding_excludes_opening_press_and_preserves_live_mapping(self):
        self.case("rebind-capture")

    def test_rebinding_rejects_collisions_multibuttons_and_disconnects(self):
        self.case("rebind-refusals")

    def test_saved_mapping_preserves_provenance_and_activates_only_on_reload(self):
        self.case("mapping-roundtrip")

    def test_mapping_recovery_ignores_pending_and_refuses_stale_backup(self):
        self.case("mapping-recovery")

    def test_failed_mapping_save_preserves_live_disk_and_allows_retry(self):
        self.case("mapping-save-failure")


if __name__ == "__main__":
    unittest.main()
