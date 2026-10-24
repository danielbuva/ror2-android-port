"""Owner-managed inputs are source providers, never prepared game outputs."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/managed.py"
SPEC = importlib.util.spec_from_file_location("owner_code_managed_tests", PATH)
MANAGED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANAGED)


class OwnerCodeManagedTests(unittest.TestCase):
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
            values["dotnet"] = values["packages"]
            with self.assertRaisesRegex(ValueError, "provider kind"):
                MANAGED.bind_paths(values)


if __name__ == "__main__":
    unittest.main()
