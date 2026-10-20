"""No-device selector and stop-classification checks for the candidate runner."""

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB = REPO_ROOT / "scripts/lab/survivor_check.py"
REPO_LAB = REPO_ROOT / "scripts/lab"
sys.path.insert(0, str(REPO_LAB))
if not (REPO_LAB / "baseline.py").exists():
    for parent in Path(__file__).resolve().parents:
        fallback = parent / "scripts/lab"
        if (fallback / "baseline.py").exists():
            sys.path.insert(1, str(fallback))
            break
spec = importlib.util.spec_from_file_location("toolbot_survivor_check", LAB)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ENTRIES = [
    {"componentIndex": 1, "familyCatalogIndex": 142, "variantIndex": 3, "skillCatalogIndex": 193},
    {"componentIndex": 4, "familyCatalogIndex": 144, "variantIndex": 1, "skillCatalogIndex": 201},
]


class ToolbotOffhandRunner(unittest.TestCase):
    def completed_report(self):
        return {
            "phase": "integrated-world-playing",
            "error": "",
            "firstFailure": "",
            "stage": {"scene": "lakes"},
            "stageProgress": {"transitions": 0, "transporting": False},
            "profile": {"appliedRuns": 0},
            "debugAcceleration": {"everAssisted": True},
            "skillInputCoverage": {
                "mode": "toolbot-offhand-sequence",
                "toolbotOffhandRequested": True,
                "completed": True,
                "toolbotOffhandOutcome": "toolbot-offhand-activation-observed",
                "toolbotOffhandPhase": 6,
                "toolbotOffhandRequests": 2,
                "toolbotOffhandStanceObserved": True,
                "toolbotOffhandOverrideObserved": True,
                "toolbotOffhandWeapon2Observed": True,
                "toolbotOffhandBuzzsawStateObserved": True,
                "toolbotOffhandBodyState": "EntityStates.Toolbot.ToolbotDualWield",
                "toolbotOffhandSpecialDefinition": "ToolbotCancelDualWield",
                "toolbotOffhandSecondaryDefinition": "ToolbotBodyFireBuzzsaw",
                "toolbotOffhandSecondaryActivationMachine": "Weapon",
                "slots": [{}, {"inputBankEdges": 1, "requests": 1}, {}, {"inputBankEdges": 1, "requests": 1}],
            },
            "survivorSkills": {
                "slots": [
                    {"slot": "secondary", "authorityActivations": 1, "serverActivations": 1},
                    {"slot": "special", "authorityActivations": 1, "serverActivations": 1},
                ]
            },
        }

    def assess_completed_report(self, final):
        # The native inventory parser has independent contracts. Supply its
        # validated semantic result to isolate the terminal-report acceptance.
        inventory = {
            "status": "valid",
            "selectionSource": "native-master-loadout-live",
            "components": [
                dict(
                    entry,
                    selectedLoadoutVariantIndex=entry["variantIndex"],
                    selectedLoadoutSkillCatalogIndex=entry["skillCatalogIndex"],
                    runtimeSkillCatalogIndex=entry["skillCatalogIndex"],
                    runtimeDefinitionStatus="matches-selected-native-loadout",
                )
                for entry in ENTRIES
            ],
        }
        with patch.object(check, "post_spawn_skill_variant_catalog_inventory", return_value=inventory):
            return check.assess_toolbot_offhand(
                "toolbot-offhand-activation-observed", {"profile": {"appliedRuns": 0}}, final, [], {"survivor": "Toolbot", "entries": ENTRIES}
            )

    def test_terminal_report_requires_no_late_failure_or_stage_change(self):
        self.assertEqual(self.assess_completed_report(self.completed_report()), [])
        for field in ("error", "firstFailure"):
            with self.subTest(field=field):
                final = self.completed_report()
                final[field] = "failure after the successful polling sample"
                self.assertIn("final Toolbot offhand report contains a runtime failure", self.assess_completed_report(final))
        for progress, scene in (({"transitions": 1}, "goolake"), ({"transitions": 0, "transporting": True}, "lakes"), ({"transitions": False}, "lakes")):
            with self.subTest(progress=progress):
                final = self.completed_report()
                final["stageProgress"], final["stage"] = progress, {"scene": scene}
                self.assertIn("final Toolbot offhand report left the first stage", self.assess_completed_report(final))

    def test_absent_selector_keeps_default_and_exact_opt_in_is_assisted(self):
        default = check.survivor_selection("fixture", "Toolbot")
        self.assertNotIn("diagnosticToolbotOffhand", default)
        opted = check.survivor_selection("fixture", "Toolbot", {"survivor": "Toolbot", "entries": ENTRIES}, toolbot_offhand=True)
        self.assertIs(opted["diagnosticToolbotOffhand"], True)
        self.assertIn("Assisted MUL-T", opted["debugOptions"]["purpose"])
        with self.assertRaises(ValueError):
            check.survivor_selection("fixture", "Toolbot", None, toolbot_offhand=True)
        with self.assertRaises(ValueError):
            check.survivor_selection("fixture", "Commando", {"survivor": "Commando", "entries": ENTRIES}, toolbot_offhand=True)
        wrong = [dict(ENTRIES[0]), dict(ENTRIES[1])]
        wrong[1]["variantIndex"] = 0
        with self.assertRaises(ValueError):
            check.survivor_selection("fixture", "Toolbot", {"survivor": "Toolbot", "entries": wrong}, toolbot_offhand=True)

    def test_first_failure_and_stage_exit_precede_sequence_completion(self):
        report = {
            "error": "native error",
            "skillInputCoverage": {"mode": "toolbot-offhand-sequence", "completed": True, "toolbotOffhandOutcome": "toolbot-offhand-activation-observed"},
        }
        self.assertEqual(check.toolbot_offhand_stop_reason(report), "first-failure")
        report = {
            "stageProgress": {"transitions": 1},
            "skillInputCoverage": {"mode": "toolbot-offhand-sequence", "completed": True, "toolbotOffhandOutcome": "toolbot-offhand-activation-observed"},
        }
        self.assertEqual(check.toolbot_offhand_stop_reason(report), "left-first-stage")
        report = {
            "phase": "integrated-world-playing",
            "stageProgress": {"transitions": 0},
            "skillInputCoverage": {"mode": "toolbot-offhand-sequence", "completed": True, "toolbotOffhandOutcome": "toolbot-offhand-activation-observed"},
        }
        self.assertEqual(check.toolbot_offhand_stop_reason(report), "toolbot-offhand-activation-observed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
