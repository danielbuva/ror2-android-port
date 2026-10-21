from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import phone_linker_roots
from phone_linker import strip, stripped_input
from phone_linker_roots import compose, generate, native_types, project_subset, scene_subset, sha, verify


def project():
    return {
        "serializedTypes": [],
        "typesInScenes": [
            {
                "managedAssemblyName": "Fixture.dll",
                "nativeClass": "Root",
                "fullManagedTypeName": "Fixture.Script",
                "moduleName": "Core",
                "usedInScenes": ["Assets/Fixture.unity"],
            }
        ],
        "forceIncludeModules": [],
        "forceExcludeModules": ["Unused"],
    }


def registry():
    return {
        "executes_sdk": False,
        "root_generation_qualified": False,
        "records": [
            {
                "self": 1,
                "parent": 0,
                "name": "Root",
                "qualifiedName": "Fixture::Root",
                "nativeNamespace": "Fixture",
                "module": "Core",
                "baseName": "",
                "baseModule": "",
                "base_resolved": True,
                "persistentTypeID": 100,
            },
            {
                "self": 2,
                "parent": 1,
                "name": "Child",
                "qualifiedName": "Fixture::Child",
                "nativeNamespace": "Fixture",
                "module": "Core",
                "baseName": "Root",
                "baseModule": "Core",
                "base_resolved": True,
                "persistentTypeID": 101,
            },
        ],
    }


def fixture(stage, *, module_policy=False):
    """An authored fake SDK reader exercises the isolated tool boundary without SDK data."""
    stage.mkdir()
    (stage / "registry").mkdir()
    (stage / "registry/owner-sdk").write_bytes(b"authored SDK input")
    (stage / "registry/phone_registry_literals.py").write_text("# Authored fixture helper.\n")
    configuration = {
        "profile": "authored-fixture",
        "sdk_binary_sha256": sha(stage / "registry/owner-sdk"),
        "native_order": "qualifiedName-ordinal",
        "project_roots_from_desktop": True,
        "captured_native_table_staged": False,
    }
    source = (
        "import hashlib, json\nfrom pathlib import Path\n"
        "PROFILE = " + repr(configuration["profile"]) + "\nBINARY_SHA256 = " + repr(configuration["sdk_binary_sha256"]) + "\n"
        "def inspect(binary, output):\n"
        "    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()\n"
        "    if sha(binary) != BINARY_SHA256: raise ValueError('Unknown authored SDK')\n"
        "    result = " + repr(registry()) + "\n"
        "    result.update(profile=PROFILE, binary_sha256=BINARY_SHA256, reader_sha256=sha(__file__), literal_reader_sha256=sha(Path(__file__).with_name('phone_registry_literals.py')))\n"
        "    with Path(output).open('x') as stream: stream.write(json.dumps(result))\n"
        "    return result\n"
    )
    (stage / "registry/phone_registry.py").write_text(source)
    shutil.copyfile(phone_linker_roots.__file__, stage / "phone_linker_roots.py")
    (stage / "project-root-data.json").write_text(json.dumps(project()))
    if module_policy:
        configuration["module_policy"] = {
            "profile": "authored-module-fixture",
            "captured_policy_staged": False,
            "package_closure_validated": True,
            "enabled_package_count": 1,
        }
        (stage / "module-policy").mkdir()
        (stage / "module-policy/input.json").write_text(json.dumps({"excluded": ["Regenerated"]}))
        (stage / "phone_module_policy.py").write_text(
            "import json, hashlib\nfrom pathlib import Path\nPROFILE = 'authored-module-fixture'\n"
            "def evaluate_stage(directory):\n"
            "    path = Path(directory) / 'input.json'\n"
            "    return dict(profile=PROFILE, enabledPackages=['authored'], forceIncludeModules=[], "
            "forceExcludeModules=json.loads(path.read_text())['excluded'], "
            "input_hashes={'input.json': hashlib.sha256(path.read_bytes()).hexdigest()})\n"
        )
        (stage / "project-root-data.json").write_text(json.dumps(scene_subset(project())))
    (stage / "plan.json").write_text(
        json.dumps(
            {
                "native_registry": configuration,
                "game_inputs": False,
                "desktop_editor_roots": True,
                "arguments": [{"output": "native-roots/EditorToUnityLinkerData.json", "prefix": "--editor-data-file="}],
            }
        )
    )
    return configuration


class PhoneLinkerRootTests(unittest.TestCase):
    def test_module_mode_omits_captured_policy_and_binds_regenerated_data_and_source(self):
        poisoned = project() | {"forceIncludeModules": "unused poison", "forceExcludeModules": None, "allNativeTypes": "unused poison"}
        self.assertEqual(set(scene_subset(poisoned)), {"serializedTypes", "typesInScenes"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, output = root / "stage", root / "output"
            configuration = fixture(stage, module_policy=True)
            result = generate(stage, output, configuration)
            generated = json.loads((output / "native-roots/EditorToUnityLinkerData.json").read_text())
            self.assertEqual(generated["forceExcludeModules"], ["Regenerated"])
            self.assertEqual(verify(stage, output, result), result)
            self.assertIs(result["complete_editor_root_generation"], False)
            policy_path = output / "native-roots/module-policy.json"
            original = policy_path.read_bytes()
            policy_path.write_text("changed policy")
            with self.assertRaisesRegex(ValueError, "module-policy"):
                verify(stage, output, result)
            policy_path.write_bytes(original)
            source = stage / "phone_module_policy.py"
            source.write_text(source.read_text() + "\n# Changed authored source.\n")
            with self.assertRaisesRegex(ValueError, "module-policy"):
                verify(stage, output, result)
            (stage / "project-root-data.json").write_text(json.dumps(project()))
            with self.assertRaisesRegex(ValueError, "foreign/native/policy"):
                generate(stage, root / "leaked", configuration)

    def test_projection_ignores_captured_native_values_and_uses_independent_order(self):
        captured = project() | {"allNativeTypes": [{"name": "PoisonedCapture"}]}
        before = deepcopy(captured)
        result = compose(captured, registry())
        self.assertEqual(captured, before)
        self.assertEqual({k: result[k] for k in project()}, project())
        self.assertEqual([r["name"] for r in result["allNativeTypes"]], ["Child", "Root"])
        captured["allNativeTypes"] = "must never be read"
        reordered = registry()
        reordered["records"].reverse()
        self.assertEqual(compose(captured, reordered), result)
        self.assertNotIn("allNativeTypes", project_subset(captured))

    def test_unknown_project_roots_or_policy_are_not_silently_dropped(self):
        for change in (
            {"serializedTypes": ["unsupported"]},
            {"unknown": []},
            {"forceExcludeModules": ["Unused", "Unused"]},
            {"forceIncludeModules": ["Unused"]},
            {"typesInScenes": []},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                project_subset(project() | change)

    def test_incomplete_ambiguous_or_cyclic_native_metadata_refuses(self):
        for name, mutate in (
            ("foreign parent", lambda rows: rows[1].update(parent=99)),
            ("base contradiction", lambda rows: rows[1].update(baseModule="Other")),
            ("unresolved", lambda rows: rows[1].update(base_resolved=False)),
            ("duplicate pointer", lambda rows: rows[1].update(self=1)),
            ("duplicate name", lambda rows: rows[1].update(name="Root", qualifiedName="Fixture::Root")),
            ("namespace contradiction", lambda rows: rows[1].update(qualifiedName="Other::Child")),
            ("cycle", lambda rows: rows[0].update(parent=2, baseName="Child", baseModule="Core")),
        ):
            value = registry()
            mutate(value["records"])
            with self.subTest(name=name), self.assertRaises(ValueError):
                native_types(value)

    def test_generated_data_and_receipt_bind_sdk_sources_and_captured_project_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, output = root / "stage", root / "output"
            configuration = fixture(stage)
            result = generate(stage, output, configuration)
            self.assertEqual(result["counts"], {"native_types": 2, "types_in_scenes": 1})
            self.assertIs(result["complete_editor_root_generation"], False)
            self.assertEqual(verify(stage, output, result), result)
            with self.assertRaises(FileExistsError):
                generate(stage, output, configuration)
            (stage / "project-root-data.json").write_text(json.dumps(project() | {"forceExcludeModules": []}))
            with self.assertRaisesRegex(ValueError, "data drift"):
                verify(stage, output, result)

    def test_native_table_cannot_be_hidden_in_staged_project_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            configuration = fixture(stage)
            (stage / "inputs").mkdir()
            (stage / "inputs/EditorToUnityLinkerData.json").write_text("captured native table")
            with self.assertRaisesRegex(ValueError, "Captured native table"):
                generate(stage, root / "output", configuration)
            (stage / "inputs/EditorToUnityLinkerData.json").unlink()
            (stage / "project-root-data.json").write_text(json.dumps(project() | {"allNativeTypes": []}))
            with self.assertRaisesRegex(ValueError, "foreign/native"):
                generate(stage, root / "output", configuration)

    def test_converter_handoff_revalidates_the_generated_native_root_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            stage, output, project_root = (root / name for name in ("stage", "output", "project"))
            configuration = fixture(stage)
            native = generate(stage, output, configuration)
            original = project_root / "Library/Bee/artifacts/Android/ManagedStripped"
            stripped = output / "stripped"
            for folder in (original, stripped):
                folder.mkdir(parents=True)
                (folder / "Fixture.dll").write_bytes(b"authored assembly")
                (folder / "Fixture.pdb").write_bytes(b"authored symbols")
                (folder / "UnityLinkerToEditorData.json").write_text(json.dumps({"report": {"modules": []}}))
            request = {"project": str(project_root), "apk": str(root / "fixture.apk"), "sha256": "authored-apk"}
            (stage / "stage-receipt.json").write_text(json.dumps({"request": request}))
            manifest = {p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob("*") if p.is_file()}
            (stage / "input-manifest.json").write_text(json.dumps(manifest))
            result = {
                "success": True,
                "exit_code": 0,
                "input_manifest_sha256": sha(stage / "input-manifest.json"),
                "outputs": {p.relative_to(stripped).as_posix(): sha(p) for p in stripped.iterdir()},
                "native_roots": native,
            }
            (output / "result.json").write_text(json.dumps(result))
            selector = {"stage": str(stage), "output": str(output), "result_sha256": sha(output / "result.json")}
            self.assertEqual(stripped_input(selector, request), stripped)
            (output / "native-roots/EditorToUnityLinkerData.json").write_text("changed generated data")
            with self.assertRaisesRegex(ValueError, "data drift"):
                stripped_input(selector, request)

    def test_linker_receives_the_fresh_generated_path_and_sdk_failure_prevents_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            stage, output = root / "stage", root / "output"
            fixture(stage)

            def manifest():
                (stage / "input-manifest.json").write_text(
                    json.dumps({p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob("*") if p.is_file() and p.name != "input-manifest.json"})
                )

            def linker(argv, **kwargs):
                editor = next(x.split("=", 1)[1] for x in argv if x.startswith("--editor-data-file="))
                self.assertEqual(editor, str(output / "native-roots/EditorToUnityLinkerData.json"))
                self.assertEqual([x["name"] for x in json.loads(Path(editor).read_text())["allNativeTypes"]], ["Child", "Root"])
                (output / "stripped").mkdir()
                (output / "stripped/Assembly-CSharp.dll").write_bytes(b"authored output")
                return type("Result", (), {"returncode": 0})()

            manifest()
            with patch("phone_linker.subprocess.run", side_effect=linker) as run:
                self.assertTrue(strip(stage, root / "tools", output))
                run.assert_called_once()
            receipt = json.loads((output / "result.json").read_text())
            self.assertEqual(receipt["native_roots"]["native_types_origin"], "owner-sdk")
            (stage / "registry/owner-sdk").write_bytes(b"unknown SDK")
            manifest()  # Even a self-consistent manifest cannot bless an unknown SDK.
            with patch("phone_linker.subprocess.run") as run:
                self.assertFalse(strip(stage, root / "tools", root / "failed"))
                run.assert_not_called()
            self.assertIn("Unknown authored SDK", json.loads((root / "failed/result.json").read_text())["failure"])
