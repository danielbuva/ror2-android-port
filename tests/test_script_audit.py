"""Destination import contracts and read-only working-editor comparison payload."""

import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import script_audit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "android/Assets/Editor/LabBuild.cs"


class ScriptAuditTests(unittest.TestCase):
    def report(self, missing=2, type_name="TMPro.TextMeshProUGUI, Unity.TextMeshPro"):
        return dict(
            schema=1,
            selection=list(script_audit.UI_PREFABS),
            uiValid=True,
            missingScripts=missing,
            assets=[dict(path="Assets/Other.prefab", missingScripts=missing, error=None)],
            monoScripts=[dict(path="Assets/Plugins/Unity.TextMeshPro.dll", guid="a" * 32, localId=123, type=type_name)],
        )

    def test_selection_includes_all_catalog_probe_and_ui_assets(self):
        manifest = dict(locations=[dict(path="Assets/catalog.asset"), dict(path="Assets/catalog.asset")])
        scene = dict(scene="Assets/start.unity", nextStageScenes=["Assets/next.unity"], prefabAssets=["Assets/body.prefab"], api="vulkan")
        selection = script_audit.build_selection(manifest, scene)
        self.assertEqual(selection, sorted(set(selection)))
        self.assertEqual(
            set(selection),
            set(script_audit.UI_PREFABS)
            | {"Assets/catalog.asset", "Assets/start.unity", "Assets/next.unity", "Assets/body.prefab", "Assets/Recovered/geometry.obj"},
        )

    def test_payload_reuses_exact_auditor_and_does_not_import_save_or_write(self):
        payload = script_audit.mcp_payload(list(script_audit.UI_PREFABS))
        self.assertEqual(payload["action"], "execute")
        source = SOURCE.read_text()
        shared = source.split("// SCRIPT_AUDIT_BEGIN\n")[1].split("// SCRIPT_AUDIT_END")[0]
        self.assertTrue(payload["code"].endswith(shared))
        # Unity 2021.3's preview-scene loader is internal (CS0117 in the exact editor).
        self.assertNotIn("PreviewScene", shared)
        self.assertIn("m_Script: ", shared)
        self.assertIn("GetMonoBehavioursWithMissingScriptCount", shared)
        self.assertIn('FindProperty("targetLabel")', shared)
        self.assertIn("GetComponentsInChildren<UnityEngine.Transform>(true)", shared)
        for mutation in ("ImportAsset(", "Refresh(", "SaveAssets(", "SaveScene(", "WriteAllText(", "LoadPrefabContents("):
            self.assertNotIn(mutation, shared)

    def test_compare_keeps_equal_nonzero_counts_without_an_allowance(self):
        result = script_audit.compare(self.report(), self.report())
        self.assertTrue(result["equal"])
        self.assertEqual(result["destination_missing_scripts"], 2)

    def test_compare_detects_lost_null_or_changed_script_identity(self):
        for change in ("omitted", "unresolved", "rebound"):
            destination = self.report()
            if change == "omitted":
                destination["monoScripts"] = []
            else:
                destination["monoScripts"][0]["type"] = None if change == "unresolved" else "Other.Type, Other"
            with self.subTest(change=change):
                result = script_audit.compare(self.report(), destination)
                self.assertFalse(result["equal"])
                self.assertEqual(len(result["lost_mono_scripts"]), 1)

    def test_compare_detects_per_asset_regression_even_if_total_matches(self):
        destination = self.report()
        destination["assets"][0]["missingScripts"] = 3
        self.assertFalse(script_audit.compare(self.report(), destination)["equal"])

    def test_compare_rejects_selection_drift_failed_ui_and_unreadable_scene(self):
        destination = self.report()
        destination["selection"].append("Assets/new.unity")
        with self.assertRaisesRegex(ValueError, "selections differ"):
            script_audit.compare(self.report(), destination)
        for field, value in (("uiValid", False), ("error", "scene load failed")):
            destination = self.report()
            if field == "error":
                destination["assets"][0][field] = value
            else:
                destination[field] = value
            self.assertFalse(script_audit.compare(self.report(), destination)["equal"])

    def test_real_build_body_is_byte_identical_to_main_before_this_fix(self):
        body = SOURCE.read_bytes().split(b" public static void Build(){", 1)[1].split(b" [Serializable] class SceneProbeConfig", 1)[0]
        self.assertEqual(hashlib.sha256(body).hexdigest(), "e4d2710868d12a1e853f7074b0a7af55ef8151f937aa130d6517114828eb240b")

    def test_destination_gates_before_calling_unchanged_build_and_never_filters_messages(self):
        source = SOURCE.read_text()
        destination = source.split("public static void BuildDestination(){", 1)[1].split("[Serializable] class ScriptSelection", 1)[0]
        self.assertLess(destination.index("plugin-reimport.json"), destination.index("ReimportDestinationDependents(selection"))
        self.assertLess(destination.index("ReimportDestinationDependents(selection"), destination.index("InspectDestinationScripts(selection)"))
        self.assertLess(destination.index('gate["uiValid"]'), destination.index("\n   Build();"))
        self.assertIn("LogType.Error||type==LogType.Exception||type==LogType.Assert", destination)
        self.assertIn("result.errors+=importErrors", destination)
        self.assertNotIn("message.Contains", destination)
        real = source.split(" public static void Build(){", 1)[1]
        self.assertNotIn("ReimportDestinationDependents", real)
        self.assertNotIn("ManagedPlugins", real)
        self.assertNotIn("InspectDestinationScripts", real)


class ScriptAuditHostTests(unittest.TestCase):
    def test_import_repair_and_auditor_with_unity_doubles(self):
        import os
        import shutil
        import subprocess
        import tempfile

        editor = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        mono = editor / "MonoBleedingEdge/bin/mono"
        csc = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        newtonsoft = editor / "Managed/Newtonsoft.Json.dll"
        if not all(path.exists() for path in (mono, csc, newtonsoft)):
            self.skipTest("matching host C# compiler unavailable")
        source = SOURCE.read_text()
        # Only compile the repair and audit, with authored doubles for Unity APIs.
        methods = source.split(" [Serializable] class ScriptImports", 1)[1].split(" public static void Build(){", 1)[0]
        fixture = (ROOT / "tests/fixtures/destination_script_import_host.cs").read_text()
        fixture += "\npublic static class LabBuild { [Serializable] class ScriptImports" + methods
        fixture += "public static void Repair(string[] selection){var plugins=ManagedPlugins();foreach(string path in plugins)UnityEditor.AssetDatabase.ImportAsset(path,UnityEditor.ImportAssetOptions.ForceUpdate|UnityEditor.ImportAssetOptions.ForceSynchronousImport);ReimportDestinationDependents(selection,plugins);}\n}\n"
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            host = scratch / "Host.cs"
            host.write_text(fixture)
            shutil.copyfile(newtonsoft, scratch / newtonsoft.name)
            executable = scratch / "Host.exe"
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-r:" + str(newtonsoft), "-out:" + str(executable), str(host)],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(executable)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("host contracts passed", executed.stdout)
