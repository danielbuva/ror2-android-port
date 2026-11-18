import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipe"
GUID_REF = re.compile(r"^\{fileID: -?\d+, guid: [0-9a-f]{32}, type: 3\}$")


class RecipeAuditTests(unittest.TestCase):
    def test_projectile_boundary_uses_authored_registry_script_in_both_staged_profiles(self):
        identity = ["Assembly-CSharp.dll", "", "SilentProjectileBoundary"]
        for pack, bundle, count in (("commando", "commando", 26), ("objective", "objective-support", 6)):
            with self.subTest(bundle=bundle):
                supplier = RECIPE / f"owner-{pack}-reused-records.json"
                records = json.loads(supplier.read_bytes())["records"]
                (script,) = [row for row in records if row.get("script_identity") == identity]
                profile = json.loads((RECIPE / f"owner-{bundle}-objects.json").read_bytes())
                name, member, script_id = script["destination"]
                self.assertEqual((name, member), (profile["bundle"]["name"], profile["bundle"]["member"]))
                objects = {row["path_id"]: row for row in profile["objects"]}
                self.assertEqual(objects[script_id]["script_identity"], identity)
                self.assertEqual(objects[script_id]["record"], hashlib.sha256(supplier.read_bytes()).hexdigest())
                owners = []
                for row in objects.values():
                    pointers = {ref["offset"]: ref["to"] for ref in row.get("references", [])}
                    if pointers.get(16) == [0, script_id]:
                        self.assertTrue(row["fieldless_script_record"])
                        self.assertNotIn("sdk_event_system", row)
                        file_id, owner = pointers[0]
                        self.assertEqual(file_id, 0)
                        self.assertIn(owner, objects)
                        owners.append(owner)
                self.assertEqual(len(owners), count)
                self.assertEqual(len(set(owners)), count)

    def test_published_whole_scene_shader_digests_match_object_pack_references(self):
        references = {}
        for shader in RECIPE.glob("owner-*-whole-*-shaders.json"):
            scene = shader.stem.partition("-whole-")[0].removeprefix("owner-")
            objects = RECIPE / f"owner-{scene}-whole-objects.json"
            if not objects.exists():
                continue
            if scene not in references:
                profile = json.loads(objects.read_text())
                references[scene] = {row["record"] for member in profile["bundle"]["members"] for row in member["objects"] if "record" in row}
                del profile
            with self.subTest(recipe=shader.name):
                self.assertIn(hashlib.sha256(shader.read_bytes()).hexdigest(), references[scene])

    def test_controller_profile_has_native_member_rows(self):
        profile = json.loads((RECIPE / "owner-animator-controllers.json").read_text())
        for bundle in profile["bundles"]:
            for member in bundle["members"]:
                with self.subTest(bundle=bundle["path"]):
                    self.assertEqual(set(member), {"name", "objects"})
                    self.assertTrue(member["objects"])

    def test_every_recipe_is_listed_in_the_audit_record(self):
        record = (RECIPE / "README.md").read_text()
        for path in (*RECIPE.glob("*.json"), *RECIPE.glob("*.jsonl.gz")):
            with self.subTest(recipe=path.name):
                self.assertIn("| `" + path.name + "` |", record)

    def test_hud_ui_remaps_holds_only_input_gated_unity_ui_identities(self):
        recipe = json.loads((RECIPE / "hud-ui-remaps.json").read_text())
        self.assertEqual(set(recipe), {"input_id", "rows", "source_UI_sha256", "verification"})
        self.assertRegex(recipe["input_id"], r"^[0-9a-f]{64}$")
        self.assertRegex(recipe["source_UI_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(recipe["rows"])
        for row in recipe["rows"]:
            with self.subTest(type=row["type"]):
                self.assertEqual(set(row), {"canonical_path", "from", "to", "type"})
                self.assertTrue(row["type"].startswith("UnityEngine."))
                self.assertTrue(row["canonical_path"].startswith("Packages/com.unity.ugui/"))
                self.assertRegex(row["from"], GUID_REF)
                self.assertRegex(row["to"], GUID_REF)

    def test_no_reader_still_uses_the_local_copy(self):
        hits = subprocess.run(["git", "grep", "-n", "config/hud-ui-remaps.json", "--", "scripts", "tools"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(hits, "")


if __name__ == "__main__":
    unittest.main()
