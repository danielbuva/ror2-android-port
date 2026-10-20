import unittest

from phone_roots import coverage


class PhoneRootContractTests(unittest.TestCase):
    def test_explicit_native_identity_and_short_name_guesses_remain_distinct(self):
        def native(name, qualified):
            return {"name": name, "qualifiedName": qualified, "nativeNamespace": "Native", "module": "Fixture", "baseName": "", "baseModule": ""}

        def attribute(name):
            return {"name": "UnityEngine.NativeClassAttribute", "arguments": [{"type": "System.String", "value": name}]}

        inventory = {
            "assemblies": [
                {
                    "group": "sdk",
                    "assembly": "AuthoredFixture",
                    "types": [
                        {"name": "Managed.Renamed", "base_type": "System.Object", "native_attributes": [attribute("Native::Exact")]},
                        {"name": "Managed.Guess", "base_type": "System.Object", "native_attributes": []},
                        {"name": "Other.Guess", "base_type": "System.Object", "native_attributes": []},
                        {"name": "Managed.Unique", "base_type": "System.Object", "native_attributes": []},
                        {"name": "Managed.Short", "base_type": "System.Object", "native_attributes": [attribute("Short")]},
                    ],
                }
            ]
        }
        oracle = {
            "allNativeTypes": [
                native("Exact", "Native::Exact"),
                native("Guess", "Native::Guess"),
                native("Unique", "Native::Unique"),
                native("Short", "Native::Short"),
                native("Missing", "Native::Missing"),
            ]
        }
        result = coverage(inventory, oracle)["sdk"]
        self.assertEqual(result["unique_explicit_qualified_matches"], 1)
        self.assertEqual(result["unique_explicit_short_matches"], 1)
        self.assertEqual(result["ambiguous_managed_short_names"], 1)
        self.assertEqual(result["unique_managed_short_name_matches"], 2)
        self.assertFalse(result["root_generation_qualified"])
        self.assertTrue(all(row["native_module_and_base_proven"] is False for row in result["rows"]))

    def test_same_short_name_in_another_sdk_group_never_fills_missing_native_metadata(self):
        item = {"name": "Managed.Same", "base_type": "System.Object", "native_attributes": []}
        inventory = {"assemblies": [{"group": group, "assembly": "Fixture", "types": [item]} for group in ("editor", "player")]}
        oracle = {"allNativeTypes": [{"name": "Same", "qualifiedName": "Native::Same"}]}
        reports = coverage(inventory, oracle)
        for report in reports.values():
            self.assertEqual(report["unique_managed_short_name_matches"], 1)
            self.assertEqual(report["unique_explicit_qualified_matches"], 0)
            self.assertFalse(report["root_generation_qualified"])

    def test_managed_base_label_cannot_replace_a_different_native_base(self):
        item = {"name": "Managed.Texture", "base_type": "Managed.Object", "native_attributes": []}
        inventory = {"assemblies": [{"group": "sdk", "assembly": "Fixture", "types": [item]}]}
        oracle = {"allNativeTypes": [{"name": "Texture", "qualifiedName": "Native::Texture", "baseName": "NamedObject"}]}
        report = coverage(inventory, oracle)["sdk"]
        self.assertEqual(report["short_name_base_label_mismatches"], 1)
        self.assertEqual(report["short_name_base_label_matches"], 0)
        self.assertFalse(report["root_generation_qualified"])
