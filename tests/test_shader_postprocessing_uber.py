from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
CANONICAL = HERE.parents[1]
sys.path.insert(0, str(CANONICAL / "scripts/lab"))
import shader_postprocessing_uber as uber


class UberContractTests(unittest.TestCase):
    def test_shared_postprocessing_include_replay_and_bloom_only_replay(self):
        import importlib.util
        import shutil
        import types

        lab = CANONICAL / "scripts/lab"
        sys.path.insert(0, str(lab))
        catalog_spec = importlib.util.spec_from_file_location("r36_shared_catalog_rebuild", lab / "catalog_rebuild.py")
        catalog = importlib.util.module_from_spec(catalog_spec)
        catalog_spec.loader.exec_module(catalog)
        rebuild_spec = importlib.util.spec_from_file_location("r36_shared_rebuild", lab / "rebuild.py")
        rebuild = importlib.util.module_from_spec(rebuild_spec)
        rebuild_spec.loader.exec_module(rebuild)

        def digest(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()

        class ReplayIO:
            def __init__(self, work, project, export):
                self.work, self.project, self.export = work, project, export

            @staticmethod
            def is_file(path):
                return Path(path).is_file()

            @staticmethod
            def sha(path):
                return digest(path)

            @staticmethod
            def read_bytes(path):
                return Path(path).read_bytes()

            @staticmethod
            def read(path):
                if Path(path).name == "reconstruction.json":
                    return {"projects": ["accepted-export"]}
                return json.loads(Path(path).read_text(encoding="utf-8"))

            @staticmethod
            def resolve(_path):
                return export

            @staticmethod
            def flush():
                return None

        with tempfile.TemporaryDirectory(dir=CANONICAL) as temporary:
            root = Path(temporary)
            work, project, export = root / "work", root / "project", root / "export"
            work.mkdir()
            project.mkdir()
            export.mkdir()
            (work / "config").mkdir()
            (work / "config/reconstruction.json").write_text('{"projects":["accepted-export"]}', encoding="utf-8")
            (work / "config/accepted-input.json").write_text('{"input_id":"fixture-input"}', encoding="utf-8")
            relative = "Assets/WholeGame/Shader/PostProcessing/StdLib.hlsl"
            meta_relative = relative + ".meta"
            body, meta = b"shared include bytes\n", b"guid: " + b"a" * 32 + b"\n"
            for base in (project, export):
                target = base / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                Path(str(target) + ".meta").write_bytes(meta)
            candidate_root = root / "candidate"
            candidate = candidate_root / "includes/StdLib.hlsl"
            candidate_meta = Path(str(candidate) + ".meta")
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(body)
            candidate_meta.write_bytes(meta)
            bloom_body = {
                "target": relative,
                "meta_target": meta_relative,
                "candidate_path": "includes/StdLib.hlsl",
                "candidate_meta_path": "includes/StdLib.hlsl.meta",
                "candidate_sha256": digest(candidate),
                "candidate_meta_sha256": digest(candidate_meta),
                "guid": "a" * 32,
                "_generated_only": True,
            }
            bloom_rows = {
                relative: bloom_body,
                meta_relative: {**{key: value for key, value in bloom_body.items() if key != "_generated_only"}, "_generated_meta": True},
            }
            uber_body = {
                "target": relative,
                "meta_target": meta_relative,
                "candidate_path": "includes/StdLib.hlsl",
                "sha256": digest(candidate),
                "meta_sha256": digest(candidate_meta),
                "guid": "a" * 32,
                "candidate_sha256": digest(candidate),
                "_generated_only": True,
                "_uber_generated": True,
            }
            uber_rows = {
                relative: uber_body,
                meta_relative: {**uber_body, "candidate_path": "includes/StdLib.hlsl.meta", "candidate_sha256": digest(candidate_meta), "_uber_meta": True},
            }
            recipe_dir = root / "recipe"
            recipe_dir.mkdir()
            (recipe_dir / "shader-postprocessing-bloom-candidate.json").write_text(
                json.dumps({"stable_output": "generated/bloom/{input_id}"}), encoding="utf-8"
            )
            (recipe_dir / "shader-postprocessing-uber-candidate.json").write_text(json.dumps({"stable_output": "generated/uber/{input_id}"}), encoding="utf-8")
            bloom_output = work / "generated/bloom/fixture-input"
            bloom_output.mkdir(parents=True)
            (bloom_output / "includes").mkdir()
            shutil.copyfile(candidate, bloom_output / "includes/StdLib.hlsl")
            shutil.copyfile(candidate_meta, bloom_output / "includes/StdLib.hlsl.meta")
            fake_bloom = types.ModuleType("shader_postprocessing_bloom")
            fake_bloom.candidate_root = lambda _work, _input, _recipe: bloom_output
            module_patch = patch.dict(sys.modules, {"shader_postprocessing_bloom": fake_bloom})
            module_patch.start()
            self.addCleanup(module_patch.stop)
            io = ReplayIO(work, project, export)
            with (
                patch.object(catalog, "RECIPE", recipe_dir),
                patch.object(catalog, "ROOT", CANONICAL),
                patch.object(catalog, "postprocessing_bloom_rows", return_value=bloom_rows),
                patch.object(catalog, "postprocessing_uber_rows", return_value=uber_rows),
            ):
                catalog.verify_outputs(io, {relative, meta_relative}, {}, input_id="fixture-input", postprocessing_bloom={}, postprocessing_uber={})
                with self.assertRaisesRegex(RuntimeError, "unequal shared generated content"):
                    unequal = {**uber_rows, relative: {**uber_body, "sha256": "0" * 64, "candidate_sha256": "0" * 64}}
                    with patch.object(catalog, "postprocessing_uber_rows", return_value=unequal):
                        catalog.verify_outputs(io, {relative, meta_relative}, {}, input_id="fixture-input", postprocessing_bloom={}, postprocessing_uber={})

            # The legacy-only replay must still take Bloom's generated-include branch.
            bloom_only_project = root / "bloom-only-project"
            shutil.copytree(project, bloom_only_project)
            with (
                patch.object(catalog, "RECIPE", recipe_dir),
                patch.object(catalog, "ROOT", CANONICAL),
                patch.object(catalog, "postprocessing_bloom_rows", return_value=bloom_rows),
                patch.object(catalog, "postprocessing_uber_rows", return_value={}),
            ):
                catalog.verify_outputs(
                    ReplayIO(work, bloom_only_project, export),
                    {relative, meta_relative},
                    {},
                    input_id="fixture-input",
                    postprocessing_bloom={},
                    postprocessing_uber=None,
                )

            # Also exercise compare's independently implemented dispatch and merge.
            comparison_destination = root / "comparison-destination"
            shutil.copytree(project, comparison_destination)

            class Resolver:
                def __init__(self, _work):
                    pass

                @staticmethod
                def resolve(_path):
                    return export

            import composition_io

            with (
                patch.object(rebuild, "_catalog_shader_override_rows", return_value={}),
                patch.object(rebuild, "_catalog_postprocessing_bloom_rows", return_value=bloom_rows),
                patch.object(rebuild, "_catalog_postprocessing_uber_rows", return_value=uber_rows),
                patch.object(rebuild, "RECIPE", recipe_dir),
                patch.object(composition_io, "StageIO", Resolver),
            ):
                result = rebuild.compare(
                    comparison_destination,
                    project,
                    {relative, meta_relative},
                    {},
                    lambda _path: False,
                    work=work,
                )
            self.assertTrue(result["equal"], result)

    def test_official_shader_contract_requires_name_pass_zero_and_bloom_inputs(self):
        recipe = {"shader_name": "Hidden/PostProcessing/Uber", "source_pass_count": 3, "selected_pass": 0}
        shader = b"""Shader "Hidden/PostProcessing/Uber"
{
HLSLPROGRAM
float4 _MainTex;
float4 _BloomTex;
#define BLOOM_LOW
Pass
{}
Pass
{}
Pass
{}
}"""
        uber.validate_uber_contract(shader, recipe)
        for bad in (
            shader.replace(b"Hidden/PostProcessing/Uber", b"Hidden/Other"),
            shader.replace(b"Pass\n{}\nPass\n{}\nPass\n{}", b"Pass {}"),
            shader.replace(b"BLOOM_LOW", b"OTHER"),
        ):
            with self.assertRaises(RuntimeError):
                uber.validate_uber_contract(bad, recipe)

    def test_include_closure_preserves_shader_root_paths_and_rejects_escape(self):
        files = {
            "Builtins/Uber.shader": b'#include "../StdLib.hlsl"\n#include "Distortion.hlsl"',
            "StdLib.hlsl": b"// std",
            "Builtins/Distortion.hlsl": b'#include "../StdLib.hlsl"',
        }
        closure = uber.include_closure(files, "Builtins/Uber.shader")
        self.assertEqual(set(closure), set(files))
        candidate = uber.rewrite_includes(files["Builtins/Uber.shader"], closure)
        self.assertIn(b'"PostProcessing/StdLib.hlsl"', candidate)
        self.assertIn(b'"PostProcessing/Builtins/Distortion.hlsl"', candidate)
        files["Builtins/Distortion.hlsl"] = b'#include "../../../outside.hlsl"'
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            uber.include_closure(files, "Builtins/Uber.shader")

    def test_stable_candidate_path_is_input_bound_and_existing_drift_refuses(self):
        recipe = {"stable_output": "generated/uber/{input_id}"}
        work = Path("/tmp/work-root")
        self.assertEqual(uber.candidate_root(work, "input-a", recipe), work / "generated/uber/input-a")
        self.assertNotEqual(uber.candidate_root(work, "input-a", recipe), uber.candidate_root(work, "input-b", recipe))

    def test_source_join_accepts_exact_profile_and_refuses_resource_drift(self):
        import hashlib

        def sha(data: bytes) -> str:
            return hashlib.sha256(data).hexdigest()

        with tempfile.TemporaryDirectory(dir=CANONICAL) as temporary:
            export = Path(temporary)
            paths = {
                "source_camera_prefab": "Assets/RoR2/Base/Core/Camera/Main Camera.prefab",
                "resource": "Assets/MonoBehaviour/PostProcessResources_53.asset",
                "shader": "Assets/Shader/Hidden_PostProcessing_Uber_53.shader",
                "profile": "Assets/RoR2/Base/Scenes/title/PostProcessing/ppRunBase.asset",
            }
            bodies = {
                "source_camera_prefab": b"  m_Resources: {fileID: 11400000, guid: " + b"a" * 32 + b", type: 2}\n  stopNaNPropagation: 1\n",
                "resource": b"  uber: {fileID: 4800000, guid: " + b"b" * 32 + b", type: 3}\n",
                "shader": b'Shader "Hidden/PostProcessing/Uber"\n{ Pass {} }\n',
                "profile": b"--- !u!114\n  m_Name: Bloom\n  active: 1\n  enabled:\n    overrideState: 1\n    value: 1\n--- !u!114\n  m_Name: ColorGrading\n  active: 1\n  enabled:\n    overrideState: 1\n    value: 0\n--- !u!114\n  m_Name: AutoExposure\n  active: 1\n  enabled:\n    overrideState: 1\n    value: 0\n",
            }
            for key, relative in paths.items():
                target = export / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bodies[key])
                (Path(str(target) + ".meta")).write_text(
                    "guid: " + (({"source_camera_prefab": "c", "resource": "a", "shader": "b", "profile": "d"}[key]) * 32) + "\n", encoding="utf-8"
                )
            hashes = {key: sha(value) for key, value in bodies.items()}
            meta_hashes = {key: sha((export / (relative + ".meta")).read_bytes()) for key, relative in paths.items()}
            recipe = {
                "camera_contract": {
                    "source_camera_prefab": paths["source_camera_prefab"],
                    "source_camera_prefab_sha256": hashes["source_camera_prefab"],
                    "source_camera_prefab_meta_sha256": meta_hashes["source_camera_prefab"],
                    "resources_guid": "a" * 32,
                    "stopNaNPropagation": 1,
                    "resource": paths["resource"],
                    "resource_sha256": hashes["resource"],
                    "resource_meta_sha256": meta_hashes["resource"],
                    "resource_asset_guid": "a" * 32,
                    "shader": paths["shader"],
                    "shader_guid": "b" * 32,
                    "shader_sha256": hashes["shader"],
                    "shader_meta_sha256": meta_hashes["shader"],
                    "profile": paths["profile"],
                    "profile_sha256": hashes["profile"],
                    "profile_meta_sha256": meta_hashes["profile"],
                    "profile_bloom_active": True,
                    "profile_bloom_enabled": True,
                    "profile_color_grading_enabled": False,
                    "profile_auto_exposure_enabled": False,
                }
            }
            identity = uber.validate_source_join(export, recipe)
            self.assertEqual(identity["shader_meta_guid"], "b" * 32)
            self.assertEqual(identity["resource_meta_guid"], "a" * 32)
            (export / paths["resource"]).write_bytes(b"  uber: {fileID: 4800000, guid: " + b"e" * 32 + b", type: 3}\n")
            with self.assertRaisesRegex(RuntimeError, "drift"):
                uber.validate_source_join(export, recipe)

    def test_actual_stager_receipt_preservation_disable_and_unknown_preimage(self):
        def sha(data: bytes) -> str:
            return hashlib.sha256(data).hexdigest()

        class IO:
            def __init__(self, work: Path, project: Path):
                self.work, self.project, self.rebuilding, self.export = work, project, False, None
                self.writes = []

            @staticmethod
            def is_file(path):
                return Path(path).is_file()

            @staticmethod
            def sha(path):
                return sha(Path(path).read_bytes())

            def apply(self, path, *, data=None, copy=None, **_):
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(Path(copy).read_bytes() if copy else data)
                self.writes.append(path)

            @staticmethod
            def write(path, value):
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

            @staticmethod
            def read(path):
                return json.loads(Path(path).read_text(encoding="utf-8"))

            @staticmethod
            def read_bytes(path):
                return Path(path).read_bytes()

            def resolve(self, _):
                return self.export

            @staticmethod
            def flush():
                return None

        with tempfile.TemporaryDirectory(dir=CANONICAL) as temporary:
            root = Path(temporary)
            work, project, export, attempt = root / "work", root / "project", root / "export", root / "attempt"
            work.mkdir()
            project.mkdir()
            export.mkdir()
            paths = {
                "source_camera_prefab": "Assets/Game/Main Camera.prefab",
                "resource": "Assets/Game/PostProcessResources.asset",
                "shader": "Assets/Game/Uber.shader",
                "profile": "Assets/Game/Profile.asset",
            }
            bodies = {
                "source_camera_prefab": b"m_Resources: {fileID: 1, guid: " + b"a" * 32 + b", type: 2}\nstopNaNPropagation: 1\n",
                "resource": b"uber: {fileID: 2, guid: " + b"b" * 32 + b", type: 3}\n",
                "shader": b'Shader "Hidden/Dummy" { Pass {} }\n',
                "profile": b"--- !u!114\n  m_Name: Bloom\n  active: 1\n  enabled:\n    overrideState: 1\n    value: 1\n--- !u!114\n  m_Name: ColorGrading\n  active: 1\n  enabled:\n    overrideState: 1\n    value: 0\n--- !u!114\n  m_Name: AutoExposure\n  active: 1\n  enabled:\n    overrideState: 1\n    value: 0\n",
            }
            metas = {
                "source_camera_prefab": b"guid: " + b"c" * 32 + b"\n",
                "resource": b"guid: " + b"a" * 32 + b"\n",
                "shader": b"guid: " + b"b" * 32 + b"\n",
                "profile": b"guid: " + b"d" * 32 + b"\n",
            }
            for key, relative in paths.items():
                target = export / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bodies[key])
                Path(str(target) + ".meta").write_bytes(metas[key])
            package_source = (
                b'Shader "Hidden/PostProcessing/Uber"\n{\n#include "../StdLib.hlsl"\n_MainTex; _BloomTex; BLOOM_LOW;\nPass\n{}\nPass\n{}\nPass\n{}\n}\n'
            )
            include_source, include_meta = b"// package include\n", b"guid: " + b"e" * 32 + b"\n"
            with tempfile.TemporaryDirectory(dir=CANONICAL) as package_temp:
                package_root = Path(package_temp) / "package"
                shader_path = package_root / "PostProcessing/Shaders/Builtins/Uber.shader"
                shader_path.parent.mkdir(parents=True)
                shader_path.write_bytes(package_source)
                include_path = package_root / "PostProcessing/Shaders/StdLib.hlsl"
                include_path.write_bytes(include_source)
                Path(str(include_path) + ".meta").write_bytes(include_meta)
                (package_root / "package.json").write_text(json.dumps({"version": "2.3.0", "repository": {"revision": "test-revision"}}))
                (package_root / "LICENSE.md").write_bytes(b"test license")
                archive = work / "packages/post.tgz"
                archive.parent.mkdir(parents=True)
                with tarfile.open(archive, "w:gz") as tar:
                    tar.add(package_root / "package.json", "package/package.json")
                    tar.add(package_root / "LICENSE.md", "package/LICENSE.md")
                    tar.add(shader_path, "package/PostProcessing/Shaders/Builtins/Uber.shader")
                    tar.add(include_path, "package/PostProcessing/Shaders/StdLib.hlsl")
                    tar.add(Path(str(include_path) + ".meta"), "package/PostProcessing/Shaders/StdLib.hlsl.meta")
                contract = {key: value for key, value in paths.items()}
                contract.update(
                    {
                        "source_camera_prefab_sha256": sha(bodies["source_camera_prefab"]),
                        "source_camera_prefab_meta_sha256": sha(metas["source_camera_prefab"]),
                        "resource_sha256": sha(bodies["resource"]),
                        "resource_meta_sha256": sha(metas["resource"]),
                        "resource_asset_guid": "a" * 32,
                        "shader_sha256": sha(bodies["shader"]),
                        "shader_meta_sha256": sha(metas["shader"]),
                        "shader_guid": "b" * 32,
                        "profile_sha256": sha(bodies["profile"]),
                        "profile_meta_sha256": sha(metas["profile"]),
                        "resources_guid": "a" * 32,
                        "stopNaNPropagation": 1,
                    }
                )
                recipe = {
                    "schema": uber.SCHEMA,
                    "input_id": "fixture-input",
                    "enabled_by_default": False,
                    "camera_contract": contract,
                    "package_archive": "work/packages/post.tgz",
                    "package_sha256": sha(archive.read_bytes()),
                    "package_version": "2.3.0",
                    "package_repository_revision": "test-revision",
                    "package_license_sha256": sha(b"test license"),
                    "package_uber_shader_sha256": sha(package_source),
                    "source_pass_count": 3,
                    "selected_pass": 0,
                    "shader_name": "Hidden/PostProcessing/Uber",
                    "stable_output": "generated/uber/{input_id}",
                    "include_target_prefix": "Assets/WholeGame/Shader/PostProcessing/",
                }
                recipe_path = root / "recipe.json"
                recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
                activation = work / "config/postprocessing-uber.json"
                activation.parent.mkdir(parents=True)
                activation.write_text(
                    json.dumps({"schema": "whole-catalog-postprocessing-uber-activation-r1", "input_id": "fixture-input", "enabled": True}), encoding="utf-8"
                )
                io = IO(work, project)
                io.export = export
                (work / "config").mkdir(parents=True, exist_ok=True)
                (work / "config/accepted-input.json").write_text(json.dumps({"input_id": "fixture-input"}), encoding="utf-8")
                (work / "config/reconstruction.json").write_text(json.dumps({"projects": ["accepted-export"]}), encoding="utf-8")
                mapped = {relative: "Assets/WholeGame/" + relative.removeprefix("Assets/") for relative in paths.values()}
                owners = {
                    "b" * 32: mapped[paths["shader"]],
                    "a" * 32: mapped[paths["resource"]],
                    "c" * 32: mapped[paths["source_camera_prefab"]],
                    "d" * 32: mapped[paths["profile"]],
                }
                for relative in (paths["shader"], paths["resource"], paths["source_camera_prefab"]):
                    target = project / mapped[relative]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bodies[next(key for key, value in paths.items() if value == relative)])
                    Path(str(target) + ".meta").write_bytes(metas[next(key for key, value in paths.items() if value == relative)])
                with patch.object(uber, "RECIPE", recipe_path):
                    receipt = uber.stage(io, export=export, mapped=mapped, owners=owners, destination=attempt, input_id="fixture-input")
                    self.assertIsNotNone(receipt)
                    target_shader = project / mapped[paths["shader"]]
                    self.assertEqual(
                        target_shader.read_bytes(),
                        uber.rewrite_includes(package_source, {"Builtins/Uber.shader": package_source, "StdLib.hlsl": include_source}),
                    )
                    for relative in (paths["resource"], paths["source_camera_prefab"]):
                        self.assertEqual((project / mapped[relative]).read_bytes(), bodies[next(key for key, value in paths.items() if value == relative)])
                    self.assertEqual(Path(str(target_shader) + ".meta").read_bytes(), metas["shader"])
                    self.assertEqual((project / "Assets/WholeGame/Shader/PostProcessing/StdLib.hlsl").read_bytes(), include_source)
                    self.assertEqual((project / "Assets/WholeGame/Shader/PostProcessing/StdLib.hlsl.meta").read_bytes(), include_meta)
                    self.assertTrue((project / ".rebuild/postprocessing-uber.json").is_file())
                    import importlib.util

                    sys.path.insert(0, str(Path.cwd() / "scripts/lab"))
                    catalog_path = CANONICAL / "scripts/lab/catalog_rebuild.py"
                    spec = importlib.util.spec_from_file_location("r36_draft_catalog_rebuild", catalog_path)
                    catalog_rebuild = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(catalog_rebuild)

                    recipe_dir = root / "recipes"
                    recipe_dir.mkdir()
                    (recipe_dir / "shader-postprocessing-uber-candidate.json").write_text(json.dumps(recipe), encoding="utf-8")
                    with patch.object(catalog_rebuild, "RECIPE", recipe_dir), patch.object(catalog_rebuild, "ROOT", Path(__file__).resolve().parents[1]):
                        self.assertEqual(
                            json.loads((project / ".rebuild/postprocessing-uber.json").read_text())["receipt_path"], ".rebuild/postprocessing-uber-receipt.json"
                        )
                        self.assertTrue((project / ".rebuild/postprocessing-uber-receipt.json").is_file())
                        marker_data = json.loads((project / ".rebuild/postprocessing-uber.json").read_text())
                        self.assertEqual(marker_data["receipt_sha256"], sha((project / marker_data["receipt_path"]).read_bytes()))
                        loaded = catalog_rebuild.read_postprocessing_uber_receipt(project, "fixture-input", work)
                        replay_rows = catalog_rebuild.postprocessing_uber_rows(loaded, "fixture-input", set(), {}, candidate_work=work)
                        catalog_rebuild.verify_outputs(io, set(replay_rows), {}, input_id="fixture-input", postprocessing_uber=loaded)
                    self.assertIn("Assets/WholeGame/Shader/PostProcessing/StdLib.hlsl", replay_rows)
                    self.assertIn("Assets/WholeGame/Shader/PostProcessing/StdLib.hlsl.meta", replay_rows)
                    import sys as sys_module

                    import shutil

                    with patch.dict(sys_module.modules, {"catalog_rebuild": catalog_rebuild}):
                        rebuild_path = CANONICAL / "scripts/lab/rebuild.py"
                        rebuild_spec = importlib.util.spec_from_file_location("r36_draft_rebuild", rebuild_path)
                        rebuild_module = importlib.util.module_from_spec(rebuild_spec)
                        rebuild_spec.loader.exec_module(rebuild_module)
                        destination = root / "destination"
                        shutil.copytree(project, destination)

                        class Resolver:
                            def __init__(self, _work):
                                pass

                            def resolve(self, _value):
                                return export

                        import composition_io

                        with (
                            patch.object(catalog_rebuild, "RECIPE", recipe_dir),
                            patch.object(catalog_rebuild, "ROOT", CANONICAL),
                            patch.object(rebuild_module, "RECIPE", recipe_dir),
                            patch.object(composition_io, "StageIO", Resolver),
                        ):
                            expected_outputs = set(replay_rows)
                            expected_outputs.update(mapped[paths[key]] + suffix for key in ("resource", "source_camera_prefab") for suffix in ("", ".meta"))
                            provenance = {
                                path: {"sha256": sha((project / path).read_bytes()), "size": (project / path).stat().st_size}
                                for path in expected_outputs - set(replay_rows)
                            }
                            comparison = rebuild_module.compare(destination, project, expected_outputs, provenance, lambda path: path in provenance, work=work)
                    self.assertTrue(comparison["equal"], comparison)
                    # The exact candidate is also an accepted stage preimage.
                    with patch.object(uber, "RECIPE", recipe_path):
                        self.assertIsNotNone(uber.stage(io, export=export, mapped=mapped, owners=owners, destination=attempt, input_id="fixture-input"))
                    before = len(io.writes)
                    target_shader.write_bytes(b"unknown local edit")
                    with self.assertRaisesRegex(RuntimeError, "unknown staged Uber"):
                        uber.stage(io, export=export, mapped=mapped, owners=owners, destination=attempt, input_id="fixture-input")
                    self.assertEqual(len(io.writes), before)
                    stable_candidate = work / "generated/uber/fixture-input/sources/Hidden_PostProcessing_Uber_53.shader"
                    stable_candidate.write_bytes(b"candidate drift")
                    with self.assertRaisesRegex(RuntimeError, "Existing stable Uber candidate differs"):
                        uber.stage(io, export=export, mapped=mapped, owners=owners, destination=attempt, input_id="fixture-input")
                    self.assertEqual(len(io.writes), before)

    def test_disabled_activation_refuses_old_marker_before_writes(self):
        class IO:
            work = Path("/tmp/nonexistent-uber-work")
            project = Path("/tmp/uber-project")

            def is_file(self, path):
                return Path(path).is_file()

        with tempfile.TemporaryDirectory(dir=CANONICAL) as temporary:
            io = IO()
            io.work, io.project = Path(temporary) / "work", Path(temporary) / "project"
            marker = io.project / ".rebuild/postprocessing-uber.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "prior Uber receipt"):
                uber.check_staging_activation(io, "input")


if __name__ == "__main__":
    unittest.main()
