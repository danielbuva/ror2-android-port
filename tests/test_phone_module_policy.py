from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phone_module_policy as subject
from phone_content import SOURCES


def module(controlled=0, dependencies=(), strippable=1):
    return {"controlledByBuiltinPackage": controlled, "dependencies": list(dependencies), "strippable": strippable}


def inputs():
    editor = {"Foundation": module(strippable=0), "Leaf": module(1, ["Foundation"]), "Branch": module(1), "Absent": module()}
    packages = {
        subject.PREFIX + name.lower(): {"name": subject.PREFIX + name.lower(), "version": "1.0.0", "type": "module", "dependencies": {}}
        for name in ("Leaf", "Branch")
    }
    packages[subject.PREFIX + "branch"]["dependencies"] = {subject.PREFIX + "leaf": "1.0.0"}
    return editor, {k: v for k, v in editor.items() if k != "Absent"}, {"dependencies": {subject.PREFIX + "branch": "1.0.0"}}, packages


def yaml(rows):
    lines = list(subject.HEADER)
    for name, row in rows.items():
        lines += ["  - name: " + name, "    dependencies:" + ("" if row["dependencies"] else " []")]
        lines += ["      - " + name for name in row["dependencies"]]
        lines += ["    " + key + ": " + str(row[key]) for key in ("strippable", "controlledByBuiltinPackage")]
    return "\n".join(lines) + "\n"


class PhoneModulePolicyTests(unittest.TestCase):
    def test_sdk_schema_preserves_dependencies_and_refuses_unrecognized_yaml(self):
        editor, *_ = inputs()
        value = yaml(editor)
        self.assertEqual(subject.modules(value), editor)
        for changed in (
            value.replace("%YAML 1.1", "%YAML 1.2"),
            value + "  unexpected: true\n",
            value.replace("strippable: 1", "strippable: 2"),
            value.replace("      - Foundation", "      - Unknown"),
            value + value[value.index("  - name: ") :],
            value.replace("dependencies: []", "dependencies: &alias []"),
            value.replace("      - Foundation", "      - Foundation\n      - Foundation"),
            value.replace("dependencies: []", "dependencies:"),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                subject.modules(changed)

    def test_transitive_package_closure_and_target_absence_are_separate_reasons(self):
        args = inputs()
        before = deepcopy(args)
        result = subject.policy(*args)
        self.assertEqual(args, before)
        self.assertEqual(result["enabledPackages"], [subject.PREFIX + "branch", subject.PREFIX + "leaf"])
        self.assertEqual(result["forceIncludeModules"], [])
        self.assertEqual(result["forceExcludeModules"], ["Absent"])
        self.assertEqual(result["reasons"], {"Absent": ["unavailable-in-target-sdk"]})
        args[2]["dependencies"] = {}
        self.assertEqual(subject.policy(*args)["forceExcludeModules"], ["Absent", "Branch", "Leaf"])
        del args[1]["Leaf"]
        self.assertEqual(subject.policy(*args)["reasons"]["Leaf"], ["builtin-package-disabled", "unavailable-in-target-sdk"])

    def test_unknown_package_versions_callbacks_and_inconsistent_sdk_data_refuse(self):
        for mutate in (
            lambda e, t, m, p: m.update(registry="custom"),
            lambda e, t, m, p: m["dependencies"].update({"custom.package": "1.0.0"}),
            lambda e, t, m, p: m["dependencies"].update({subject.PREFIX + "branch": "2.0.0"}),
            lambda e, t, m, p: t.update(Foreign=module()),
            lambda e, t, m, p: t["Leaf"].update(controlledByBuiltinPackage=0),
            lambda e, t, m, p: p.pop(subject.PREFIX + "leaf"),
            lambda e, t, m, p: p.update({subject.PREFIX + "leaf": None}),
            lambda e, t, m, p: p[subject.PREFIX + "branch"].update(type="library"),
            lambda e, t, m, p: p[subject.PREFIX + "leaf"]["dependencies"].update({subject.PREFIX + "branch": "1.0.0"}),
            lambda e, t, m, p: p[subject.PREFIX + "leaf"]["dependencies"].update({"foreign": "1.0.0"}),
            lambda e, t, m, p: e["Absent"].update(strippable=0),
        ):
            # Keep target and editor independent so a flag disagreement is observable.
            args = tuple(deepcopy(value) for value in inputs())
            mutate(*args)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                subject.policy(*args)

    def test_stage_uses_only_sdk_and_manifest_data_and_rejects_custom_project_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, editor, target = (root / name for name in ("project", "editor", "target"))
            e, t, manifest, packages = inputs()
            for name, folder in SOURCES.items():
                path = project / folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// Authored fixture placeholder.\n")
            for name in ("Assets/Fixture.unity", "Assets/StreamingAssets/phone-fixture.bundle"):
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("authored fixture data")
            (project / "Packages").mkdir()
            (project / "Packages/manifest.json").write_text(json.dumps(manifest))
            lock = {
                "dependencies": {
                    name: {"version": "1.0.0", "source": "builtin", "depth": 0, "dependencies": row["dependencies"]} for name, row in packages.items()
                }
            }
            (project / "Packages/packages-lock.json").write_text(json.dumps(lock))
            (editor / "Resources").mkdir(parents=True)
            target.mkdir()
            (editor / "Resources/modules.asset").write_text(yaml(e))
            (target / "modules.asset").write_text(yaml(t))
            for name, row in packages.items():
                path = editor / "Resources/PackageManager/BuiltInPackages" / name / "package.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(row))
            with (
                patch.object(subject, "EDITOR_SHA", subject.sha(editor / "Resources/modules.asset")),
                patch.object(subject, "TARGET_SHA", subject.sha(target / "modules.asset")),
            ):
                configuration = subject.stage_support(root / "stage", {"profile": subject.PROFILE}, project, editor, target)
                self.assertIs(configuration["captured_policy_staged"], False)
                result = subject.evaluate_stage(root / "stage")
                self.assertEqual(result["forceExcludeModules"], ["Absent"])
                self.assertEqual(len(result["input_hashes"]), 5)
                with self.assertRaises(FileExistsError):
                    subject.stage_support(root / "stage", {"profile": subject.PROFILE}, project, editor, target)
                with self.assertRaisesRegex(ValueError, "explicit"):
                    subject.stage_support(root / "invalid", {}, project, editor, target)
                (project / "Assets/Editor/Custom.cs").write_text("// Unknown editor callback.\n")
                with self.assertRaisesRegex(ValueError, "Custom"):
                    subject.stage_support(root / "custom", {"profile": subject.PROFILE}, project, editor, target)
                (project / "Assets/Editor/Custom.cs").unlink()
                lock["dependencies"][subject.PREFIX + "leaf"]["source"] = "registry"
                (project / "Packages/packages-lock.json").write_text(json.dumps(lock))
                with self.assertRaisesRegex(ValueError, "non-builtin"):
                    subject.stage_support(root / "external", {"profile": subject.PROFILE}, project, editor, target)
                (root / "stage/target-modules.asset").write_text("unknown SDK")
                with self.assertRaisesRegex(ValueError, "drift"):
                    subject.evaluate_stage(root / "stage")
