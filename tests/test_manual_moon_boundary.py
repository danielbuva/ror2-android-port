from pathlib import Path
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


class ManualMoonBoundaryPatchTests(unittest.TestCase):
    def test_input_gate_precedes_pending_transport_and_producers(self):
        source = (CANDIDATE / "tools/unity/runtime/input/NovaInputBoundary.cs").read_text()
        first_gate = source.index("ManualMoonBoundary.HoldAutomaticProgression")
        transport = source.index("coordinator.TransportIntegratedStage")
        self.assertLess(first_gate, transport)
        self.assertIn("bridge.SetManualMoonAutomaticHold(pauseBeforeMoonBoundary);", source)
        self.assertIn("if (bringup && !pauseBeforeMoonBoundary &&", source)
        self.assertIn("if (bringup && !cfg.integratedWorld && !pauseBeforeMoonBoundary)", source)

    def test_transport_refusal_precedes_destination_resolution(self):
        source = (CANDIDATE / "tools/unity/runtime/stage/IntegratedStageBoundary.cs").read_text()
        refusal = source.index("ManualMoonBoundary.RefuseTransport")
        resolve = source.index("var next = integratedStageConfig.integratedStages")
        self.assertLess(refusal, resolve)
        self.assertIn("coordinator.pendingStage", source[refusal:resolve])

    def test_fixed_update_hold_masks_stale_automatic_requests_and_keeps_touch(self):
        bridge = (CANDIDATE / "tools/unity/runtime/input/NovaInputBridge.cs").read_text()
        fixture = (CANDIDATE / "tools/catalog/SurvivorSkillInputHost.cs").read_text()
        self.assertIn("ShouldHoldAutomaticDiagnosticInput(diagnosticInput, manualMoonAutomaticHold)", bridge)
        self.assertIn("manualMoonNeutralFixedTicks++", bridge)
        self.assertIn("holdAutomatic ? false : diagnosticEquipment, touchEquipment", bridge)
        self.assertIn("bank.skill1.down && !bank.skill2.down", fixture)
        self.assertIn("bridge.diagnosticPrimary && bridge.diagnosticInteract", fixture)
        self.assertIn("bank.aimDirection == bank.transform.forward", fixture)
        self.assertIn("bank.activateEquipment.down && bridge.manualMoonNeutralFixedTicks == 2", fixture)
        self.assertIn("!bridge.SetManualMoonAutomaticHold(true) && bank.skill1.down && bridge.touchEquipment", fixture)
        self.assertIn("ShouldHoldAutomaticDiagnosticInput(false, true)", fixture)

    def test_report_witness_requires_a_real_held_fixed_tick(self):
        source = (CANDIDATE / "tools/unity/runtime/input/NovaInputBoundary.cs").read_text()
        method = source[source.index("void ObserveManualMoonHold"):source.index("public IEnumerator NovaInputBoundary", source.index("void ObserveManualMoonHold"))]
        self.assertIn("bridge.manualMoonNeutralFixedTicks <= 0", method)
        self.assertIn("automaticDiagnosticInputHeldAtBoundary = true", method)
        self.assertIn("automaticDiagnosticHoldTransitions", method)
        self.assertIn("automaticDiagnosticHoldStage", method)
        self.assertIn("coordinator.r.nova = new NovaReport", source)

    def test_default_physical_skill_predicate_is_unchanged(self):
        bridge = (CANDIDATE / "tools/unity/runtime/input/NovaInputBridge.cs").read_text()
        self.assertIn("if (!diagnosticMode)\n            return physicalRequest;", bridge)
        self.assertIn("return diagnosticInput && requested;", bridge)


if __name__ == "__main__":
    unittest.main()
