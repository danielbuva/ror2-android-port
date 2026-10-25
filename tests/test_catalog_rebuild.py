"""R3/R4 synthetic replay, including the real builders and original write paths."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "scripts/lab/common.py").is_file())
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
sys.path.insert(1, str(REPO_ROOT / "scripts/lab"))
import catalog_analysis
import catalog_rebuild
import composition_io
import composition_migration
import whole_catalog
import rebuild
from common import read, sha, write
from composition_io import StageIO


class CatalogRebuildTests(unittest.TestCase):
    def test_default_shader_selection_pins_current_r3_generators_and_roots(self):
        candidate_root = Path(__file__).resolve().parents[1]
        selection = read(candidate_root / "recipe/shader-catalog-overrides.json")
        self.assertFalse(selection["enabled"])
        expected = {
            16022: (
                "scripts/lab/shader_outline.py",
                "recipe/shader-outline-candidate.json",
                "7cd674a8f0081a5e47669810c65e69c86349e91d280c1e4129c73111ec3ad608",
                "5019b4ea7b90b77eb7b24dbba12f13b56fe747476d341f7c7c69e1c60988f0e7",
                "generated-shader-candidates/outline-highlight-r4/{input_id}",
            ),
            15950: (
                "scripts/lab/shader_ramp_fog.py",
                "recipe/shader-ramp-fog-candidate.json",
                "a81eade20c1771e4511925a64d6c3b66fe7acab6ef3687fc19b08fe3b17dfece",
                "8f2bb4a94ff6a92259a3fc08b87058f0bfdec4604069e0afe8f5907693b75505",
                "generated-shader-candidates/ramp-fog-r5/{input_id}",
            ),
        }
        expected[8943] = (
            "scripts/lab/shader_ramp_fog.py",
            "recipe/shader-screen-damage-candidate.json",
            sha(REPO_ROOT / "scripts/lab/shader_ramp_fog.py"),
            sha(REPO_ROOT / "recipe/shader-screen-damage-candidate.json"),
            "generated-shader-candidates/screen-damage-r1/{input_id}",
        )
        for location, kind in ((16024, "sobel-buffer"), (15952, "sobel-outline")):
            recipe_path = f"recipe/shader-{kind}-candidate.json"
            expected[location] = (
                "scripts/lab/shader_ramp_fog.py",
                recipe_path,
                sha(REPO_ROOT / "scripts/lab/shader_ramp_fog.py"),
                sha(REPO_ROOT / recipe_path),
                f"generated-shader-candidates/{kind}-r1/{{input_id}}",
            )
        translucent = read(REPO_ROOT / "recipe/shader-translucent-candidate.json")
        translucent_generator = sha(REPO_ROOT / "scripts/lab/shader_translucent.py")
        translucent_recipe = sha(REPO_ROOT / "recipe/shader-translucent-candidate.json")
        for shader in translucent["shaders"]:
            expected[shader["catalog_location"]] = (
                "scripts/lab/shader_translucent.py",
                "recipe/shader-translucent-candidate.json",
                translucent_generator,
                translucent_recipe,
                translucent["stable_output"],
            )
        self.assertEqual({row["location_id"] for row in selection["rows"]}, set(expected))
        self.assertEqual(len(selection["rows"]), 9)
        for row in selection["rows"]:
            if 2537 <= row["location_id"] <= 2540:
                recipe_shader = next(item for item in translucent["shaders"] if item["catalog_location"] == row["location_id"])
                self.assertEqual(row["guid"], recipe_shader["catalog_key"])
                self.assertEqual(row["exporter_guid"], recipe_shader["guid"])
                self.assertNotEqual(row["guid"], row["exporter_guid"])
            script, recipe_path, script_hash, recipe_hash, stable_output = expected[row["location_id"]]
            self.assertEqual(row["generator"], Path(script).name)
            self.assertEqual(row["generator_recipe"], recipe_path)
            self.assertEqual(row["generator_sha256"], script_hash)
            self.assertEqual(row["generator_recipe_sha256"], recipe_hash)
            self.assertEqual(sha(REPO_ROOT / script), script_hash)
            self.assertEqual(sha(REPO_ROOT / recipe_path), recipe_hash)
            self.assertEqual(read(REPO_ROOT / recipe_path)["stable_output"], stable_output)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / "work"
        self.dest = self.root / "destination"
        self.export = self.work / "export"
        self.catalog = self.work / "catalog"
        self.recipes = self.root / "recipe"
        self.input_id = "a" * 64
        self.source = "Assets/Test.prefab"
        self.target = "Assets/WholeGame/Test.prefab"
        self.guid = "b" * 32
        self.body = "%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component:\n  - component: {fileID: 2}\n  ui: old-ui\n--- !u!114 &2\nMonoBehaviour:\n  m_Script: {fileID: 3, guid: 2b6c926553287666f24ffd5af5ba21cb, type: 3}\n"
        self.put(self.export / self.source, self.body)
        self.put(self.export / (self.source + ".meta"), "guid: " + self.guid + "\n")
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "config/reconstruction.json", dict(projects=["work/export"]))
        write(self.work / "experiments/whole-catalog/latest.json", dict(path="work/catalog"))
        write(self.work / "config/composition-migration.json", dict(input_id=self.input_id, evidence="work/evidence"))
        write(self.recipes / "hud-ui-remaps.json", dict(input_id=self.input_id, rows=[dict(**{"from": "old-ui", "to": "new-ui"})]))
        selection = json.loads((Path(__file__).resolve().parents[1] / "recipe/shader-catalog-overrides.json").read_text())
        selection["input_id"] = self.input_id
        write(self.recipes / "shader-catalog-overrides.json", selection)
        write(
            self.catalog / "reconciled-closure.json",
            dict(input_id=self.input_id, files=[self.source], roots=[1], converted={"1": dict(source=self.source)}, source_catalog_sha256="c" * 64),
        )
        write(self.catalog / "source-guid-index.json", {self.guid: self.source})
        write(self.catalog / "source-guid-repairs.json", [])
        write(self.catalog / "native-conversions.json", dict(issues=[]))
        write(self.catalog / "source-catalog.json", dict(locations=[dict(id=1, type="UnityEngine.GameObject", primaryKey="test")], keys=[], providers=[]))
        # The real catalog builder now requires the original camera's explicit
        # shader dependencies. Supply authored stand-ins to keep this replay
        # exercising its normal identity and copying paths.
        metadata = read(self.catalog / "source-catalog.json")
        closure = read(self.catalog / "reconciled-closure.json")
        index = read(self.catalog / "source-guid-index.json")
        for location_id, (address, primary_key) in whole_catalog.CAMERA_SHADER_ROOTS.items():
            source = f"Assets/SyntheticCamera{location_id}.shader"
            guid = f"{location_id:032x}"
            self.put(self.export / source, f'Shader "Synthetic/Camera{location_id}" {{}}\n')
            self.put(self.export / (source + ".meta"), "guid: " + guid + "\n")
            metadata["locations"].append(dict(id=location_id, type=whole_catalog.SHADER_LOCATION_TYPE, primaryKey=primary_key))
            metadata["keys"].append(dict(key=address, keyType="System.String", locations=[location_id]))
            closure["converted"][str(location_id)] = dict(source=source, resolution="exact")
            index[guid] = source
        write(self.catalog / "source-catalog.json", metadata)
        write(self.catalog / "reconciled-closure.json", closure)
        write(self.catalog / "source-guid-index.json", index)
        self.support = "Assets/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs"
        self.support_target = "Assets/WholeGame/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs"
        self.put(self.export / self.support, "class SyntheticSupport {}\n")
        self.binary = self.work / "game/Risk of Rain 2_Data/Managed/Assembly-CSharp.dll"
        self.put(self.binary, "synthetic binary")
        self.fields = dict(SpawnBeadChaseEvent="AK.Wwise.Event", ExplodeEvent="AK.Wwise.Event")
        write(self.work / "inventory/files.json", dict(files=[dict(path="Risk of Rain 2_Data/Managed/Assembly-CSharp.dll", sha256=sha(self.binary))]))
        for project in (self.dest, self.work / "lab-project"):
            write(project / ".port-input.json", dict(input_id=self.input_id))
            write(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", {})
            for name, guid in (
                ("Plugins/AK.Wwise.Unity.MonoBehaviour.dll", "2b6c926553287666f24ffd5af5ba21cb"),
                ("Plugins/Decalicious.dll", "90eda32cd325c26600dacf144354b407"),
                ("Plugins/RoR2.dll", "951ce57ad999ac1f040a4dceb5f8b763"),
                ("SilentProjectileBoundary.cs", "d" * 32),
            ):
                self.put(project / ("Assets/LabLoadingScene/" + name + ".meta"), "guid: " + guid + "\n")
        write(self.work / "scene-probe-build.json", dict(prefabAssets=[self.target]))
        write(self.dest / ".rebuild/composition/scene-probe-build.json", dict(prefabAssets=[self.target]))
        for name in ("WholeCatalogLoader.cs", "WholeCatalogBootstrap.cs"):
            self.put(self.root / "tools/unity/runtime/catalog" / name, "authored synthetic")
        self.put(self.root / "tools/catalog/WholeCatalogHost.cs", "authored synthetic")
        self.pin()
        write(self.recipes / "build-entry-inputs.json", dict(schema=2, input_id=self.input_id, bootstrap_attempt="integration-pinned", files={}))
        (self.work / "evidence").mkdir()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(patch.object(StageIO, "preflight"))
        for module in (composition_io, whole_catalog, composition_migration):
            stack.enter_context(patch.object(module, "ROOT", self.root))
            stack.enter_context(patch.object(module, "WORK", self.work))
        stack.enter_context(patch.object(catalog_rebuild, "ROOT", self.root))
        for module in (catalog_rebuild, whole_catalog, composition_migration):
            stack.enter_context(patch.object(module, "RECIPE", self.recipes))
        stack.enter_context(patch.object(whole_catalog, "game", return_value=self.work / "game"))
        stack.enter_context(patch.object(whole_catalog, "recover_ambiguous_mesh_subobjects", return_value=[]))
        write(self.catalog / "native-latest.json", dict(path="work/native"))
        self.contract = dict(sha256=sha(self.binary), types=[dict(fields=[dict(name=k, type=v) for k, v in self.fields.items()])])
        from types import SimpleNamespace

        stack.enter_context(patch.dict(sys.modules, boundaries=SimpleNamespace(probe_tool=lambda: ["synthetic-probe"])))

        # The IL probe reports the binary it actually read.
        stack.enter_context(
            patch.object(
                whole_catalog,
                "run",
                side_effect=lambda *a, **k: SimpleNamespace(stdout=json.dumps(dict(self.contract, sha256=sha(self.binary))).encode()),
            )
        )
        # Host regeneration is exercised by its own tests; here it publishes the synthetic cohort.
        stack.enter_context(patch.object(catalog_analysis, "regenerate", side_effect=self.regenerate))

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def regenerate(self, work, out, input_id):
        for name in catalog_analysis.OUTPUTS:
            source = self.catalog / name
            (out / name).write_bytes(source.read_bytes() if source.is_file() else b"{}")
        (out / "native-containers").mkdir()

    def pin(self):
        # Changed synthetic analysis is regenerated by the next destination stage.
        marker = self.dest / ".rebuild/catalog-inputs/analysis-complete.json"
        if marker.is_file():
            marker.unlink()

    def staging(self):
        return catalog_rebuild.CatalogIO(self.work, self.dest, self.input_id)

    def install_shader_candidates(self, include_translucent=False, include_screen_damage=False, include_sobel=False):
        selection = read(self.recipes / "shader-catalog-overrides.json")
        selection["enabled"] = False
        write(
            self.work / "config/shader-catalog-overrides.json",
            dict(schema="whole-catalog-shader-overrides-activation-r1", input_id=self.input_id, enabled=True),
        )
        metadata = read(self.catalog / "source-catalog.json")
        closure = read(self.catalog / "reconciled-closure.json")
        index = read(self.catalog / "source-guid-index.json")
        specs = [
            (
                16022,
                "41e90cbc5ad198a438128b019f8d8553",
                "RoR2/Base/Shaders/HGOutlineHighlight.shader",
                "Assets/RoR2/Base/Shaders/PostProcess/HGOutlineHighlight.shader",
                "outline-highlight",
                "Hopoo Games/Internal/Outline Highlight",
                -5736718617091362218,
                "shader_outline.py",
                "recipe/shader-outline-candidate.json",
                "private-outline-highlight-generated-candidate-r1",
                "manifest.json",
                "sources/OutlineHighlightCandidate.shader",
                "generated_shader_path",
            ),
            (
                15950,
                "c14b6abb309b8c246add9e94a6920d7f",
                "RoR2/Base/Shaders/RampFog.shader",
                "Assets/RoR2/Base/Shaders/CustomPostProcess/RampFog.shader",
                "ramp-fog",
                "Hidden/PostProcess/RampFog",
                2910825169780710437,
                "shader_ramp_fog.py",
                "recipe/shader-ramp-fog-candidate.json",
                1,
                "candidate.json",
                "sources/RampFogCandidate.shader",
                "generated_shader",
            ),
        ]
        if include_screen_damage:
            self.assertTrue(include_translucent)
            specs.append(
                (
                    8943,
                    "62decc840d5afaa49886d8b13165939e",
                    "RoR2/Base/Core/CameraEffects/HGScreenDamage.shader",
                    "Assets/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader",
                    "screen-damage",
                    "Hopoo Games/Post Process/Screen Damage",
                    916309824485114785,
                    "shader_ramp_fog.py",
                    "recipe/shader-screen-damage-candidate.json",
                    1,
                    "candidate.json",
                    "sources/ScreenDamageCandidate.shader",
                    "generated_shader",
                )
            )
            initial = "Assets/SyntheticCamera8943.shader"
            self.put(self.export / initial, 'Shader "Synthetic/ScreenDamage" {}\n')
            self.put(self.export / (initial + ".meta"), "guid: " + f"{8943:032x}" + "\n")
            closure["converted"]["8943"] = dict(source=initial, resolution="exact")
            closure["files"].append(initial)
            closure["roots"].append(8943)
            metadata["locations"].append(
                dict(id=8943, type=whole_catalog.SHADER_LOCATION_TYPE, primaryKey="RoR2/Base/Core/CameraEffects/HGScreenDamage.shader")
            )
            metadata["keys"].append(dict(key="62decc840d5afaa49886d8b13165939e", keyType="System.String", locations=[8943]))
            index[f"{8943:032x}"] = initial
        if include_sobel:
            self.assertTrue(include_screen_damage)
            for row in selection["rows"]:
                if row["candidate_kind"] not in ("sobel-buffer", "sobel-outline"):
                    continue
                loc = row["location_id"]
                kind = row["candidate_kind"]
                object_id = -583016510457714391 if kind == "sobel-buffer" else 2831377250017133402
                specs.append(
                    (
                        loc,
                        row["guid"],
                        row["primary_key"],
                        row["source_asset_path"],
                        kind,
                        row["shader_name"],
                        object_id,
                        row["generator"],
                        row["generator_recipe"],
                        row["candidate_schema"],
                        row["manifest"],
                        row["shader"],
                        row["manifest_path_field"],
                    )
                )
        rows = []
        for loc, guid, key, source_path, kind, name, object_id, generator, gen_recipe, schema, manifest_name, shader_rel, manifest_field in specs:
            old = closure["converted"][str(loc)]["source"]
            (self.export / old).unlink()
            (self.export / (old + ".meta")).unlink()
            self.put(self.export / source_path, 'Shader "Synthetic/Original" {}\n')
            exporter = {8943: "ed4a1bae3abd8f34b905b509b4ff70e0", 16024: "6d9e1738bf3095e42a34d9feb449ad3b", 15952: "0af91730b526684408399853ee967ce8"}.get(
                loc, ("e" if loc == 16022 else "f") * 32
            )
            self.put(self.export / (source_path + ".meta"), "guid: " + exporter + "\n")
            closure["files"] = [source_path if path == old else path for path in closure["files"]]
            closure["converted"][str(loc)] = dict(source=source_path, resolution="exact")
            index.pop(f"{loc:032x}", None)
            index[exporter if loc in (8943, 16024, 15952) else guid] = source_path
            asset = next(row for row in metadata["locations"] if row["id"] == loc)
            asset["primaryKey"] = key
            key_row = next(row for row in metadata["keys"] if row["locations"] == [loc])
            key_row["key"] = guid
            # Hash-pinned helper source/recipe are inert synthetic bytes for this host contract.
            self.put(self.root / "scripts/lab" / generator, "synthetic generator source\n")
            self.put(self.root / gen_recipe, json.dumps({"stable_output": f"generated-shader-candidates/{kind}-r3/{{input_id}}"}))
            generator_hash = sha(self.root / "scripts/lab" / generator)
            generator_recipe_hash = sha(self.root / gen_recipe)
            template = next(row for row in selection["rows"] if row["location_id"] == loc)
            template.update(generator_sha256=generator_hash, generator_recipe_sha256=generator_recipe_hash)
            root = self.work / f"generated-shader-candidates/{kind}-r3/{self.input_id}"
            shader = ('Shader "' + name + '" {}\n').encode()
            self.put(root / shader_rel, shader.decode())
            if kind == "outline-highlight":
                doc = dict(
                    schema=schema,
                    success=True,
                    generator_sha256=generator_hash,
                    recipe_sha256=generator_recipe_hash,
                    source=dict(input_id=self.input_id, catalog_key=guid, catalog_location=loc, asset_path=source_path),
                    object_path_id=object_id,
                    generated_shader_path=shader_rel,
                    generated_shader_sha256=hashlib.sha256(shader).hexdigest(),
                    semantic_equivalence_proven=False,
                    android_compile_or_render_tested=False,
                    appearance_parity_proven=False,
                )
                write(root / manifest_name, doc)
            else:
                doc = dict(
                    schema=1,
                    kind=f"local-source-bound-{kind}-candidate",
                    generator_sha256=generator_hash,
                    recipe_sha256=generator_recipe_hash,
                    source=dict(input_id=self.input_id, shader_path_id=object_id, shader_name=name, bundle_sha256="bundle"),
                    generated_shader=shader_rel,
                    generated_shader_sha256=hashlib.sha256(shader).hexdigest(),
                    semantic_equivalence_proven=False,
                )
                write(root / manifest_name, doc)
                write(
                    root / "receipt.json",
                    dict(
                        success=True,
                        generated_shader_sha256=doc["generated_shader_sha256"],
                        input_id=self.input_id,
                        bundle_sha256="bundle",
                        source_bundle_unchanged=True,
                        unity_compiled=False,
                        android_shader_acceptance=False,
                        visual_parity_proven=False,
                    ),
                )
            rows.append(template)
        write(self.catalog / "source-catalog.json", metadata)
        write(self.catalog / "reconciled-closure.json", closure)
        write(self.catalog / "source-guid-index.json", index)
        if include_translucent:
            rows.extend(row for row in selection["rows"] if row["location_id"] in (2537, 2538, 2539, 2540))
        order = {row["location_id"]: n for n, row in enumerate(selection["rows"])}
        selection["rows"] = sorted(rows, key=lambda row: order[row["location_id"]])
        write(self.recipes / "shader-catalog-overrides.json", selection)
        self.pin()
        return specs

    def install_translucent_candidates(self):
        selection = read(self.recipes / "shader-catalog-overrides.json")
        metadata = read(self.catalog / "source-catalog.json")
        closure = read(self.catalog / "reconciled-closure.json")
        index = read(self.catalog / "source-guid-index.json")
        generator_source = REPO_ROOT / "scripts/lab/shader_translucent.py"
        recipe_source = REPO_ROOT / "recipe/shader-translucent-candidate.json"
        self.put(self.root / "scripts/lab/shader_translucent.py", generator_source.read_text())
        self.put(self.recipes / "shader-translucent-candidate.json", recipe_source.read_text())
        recipe = read(self.recipes / "shader-translucent-candidate.json")
        generator_hash = sha(self.root / "scripts/lab/shader_translucent.py")
        recipe_hash = sha(self.recipes / "shader-translucent-candidate.json")
        specs = []
        for source_spec in recipe["shaders"]:
            location = source_spec["catalog_location"]
            catalog_key = source_spec["catalog_key"]
            exporter_guid = source_spec["guid"]
            source_path = source_spec["source_asset_path"]
            target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
            old = closure["converted"][str(location)]["source"]
            (self.export / old).unlink()
            (self.export / (old + ".meta")).unlink()
            self.put(self.export / source_path, 'Shader "Synthetic/Original" {}\n')
            self.put(self.export / (source_path + ".meta"), "guid: " + exporter_guid + "\n")
            self.put(self.dest / (target + ".meta"), "guid: " + exporter_guid + "\n")
            closure["converted"][str(location)] = dict(source=source_path, resolution="exact")
            index.pop(f"{location:032x}", None)
            index[exporter_guid] = source_path
            row = next(item for item in metadata["locations"] if item["id"] == location)
            row["primaryKey"] = source_spec["primary_key"]
            key_row = next(item for item in metadata["keys"] if item["locations"] == [location])
            key_row["key"] = catalog_key
            generator_recipe = "recipe/shader-translucent-candidate.json"
            stable = recipe["stable_output"].format(input_id=self.input_id)
            manifest_path = self.work / stable / source_spec["manifest"]
            shader_path = self.work / stable / source_spec["output"]
            shader = ('Shader "' + source_spec["serialized_name"] + '" {}\n').encode()
            self.put(shader_path, shader.decode())
            axes = source_spec.get("keyword_axes", [])
            variants = [[], axes] if axes else [[]]
            manifest = dict(
                schema=recipe["candidate_schema"],
                success=True,
                generator_sha256=generator_hash,
                recipe_sha256=recipe_hash,
                source=dict(
                    input_id=self.input_id,
                    bundle_sha256=recipe["source"]["bundle_sha256"],
                    asset_path=source_path,
                    catalog_key=catalog_key,
                    catalog_location=location,
                    shader_path_id=source_spec["path_id"],
                    shader_name=source_spec["serialized_name"],
                ),
                generated_shader_path=source_spec["output"],
                generated_shader_sha256=hashlib.sha256(shader).hexdigest(),
                semantic_equivalence_proven=False,
                android_compile_or_render_tested=False,
                appearance_parity_proven=False,
                unity_compiled=False,
                android_accepted=False,
                visual_parity_proven=False,
                pass_mapping=[dict(pass_index=i, keyword_variants=variants, programs={"1": {"stage": "progVertex"}}) for i in range(source_spec["pass_count"])],
            )
            self.put(manifest_path, json.dumps(manifest, sort_keys=True) + "\n")
            template = next(item for item in selection["rows"] if item["location_id"] == location)
            template.update(generator_sha256=generator_hash, generator_recipe_sha256=recipe_hash)
            specs.append((location, catalog_key, source_spec["primary_key"], source_path, exporter_guid, source_spec["serialized_name"], target))
        write(self.catalog / "source-catalog.json", metadata)
        write(self.catalog / "reconciled-closure.json", closure)
        write(self.catalog / "source-guid-index.json", index)
        write(self.recipes / "shader-catalog-overrides.json", selection)
        self.pin()
        return specs

    def test_six_shader_stage_keeps_catalog_and_exporter_guid_domains_distinct(self):
        specs = self.install_shader_candidates(include_translucent=True)
        translucent = self.install_translucent_candidates()
        staging = self.staging()
        staged = whole_catalog.prepare_integration(staging)
        staging.flush()
        self.assertTrue(staged["enabled"])
        self.assertEqual(len(staged["rows"]), 6)
        for location, catalog_key, primary_key, source_path, exporter_guid, name, target in translucent:
            self.assertEqual((self.dest / target).read_text(), 'Shader "' + name + '" {}\n')
            self.assertEqual((self.dest / (target + ".meta")).read_text(), "guid: " + exporter_guid + "\n")
            row = next(row for row in staged["rows"] if row["location_id"] == location)
            self.assertEqual(row["guid"], catalog_key)
            self.assertEqual(row["exporter_guid"], exporter_guid)
            self.assertNotEqual(row["guid"], row["exporter_guid"])

    def test_sobel_pair_preserves_source_exporter_identity_and_replays(self):
        self.install_shader_candidates(include_translucent=True, include_screen_damage=True, include_sobel=True)
        self.install_translucent_candidates()
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        staging.flush()
        receipt = catalog_rebuild.read_shader_override_receipt(self.dest, self.input_id, self.work)
        self.assertEqual(len(receipt["rows"]), 9)
        for loc, kind in ((16024, "sobel-buffer"), (15952, "sobel-outline")):
            row = next(item for item in receipt["rows"] if item["location_id"] == loc)
            self.assertNotEqual(row["guid"], row["exporter_guid"])
            self.assertIn(kind, row["generator_recipe"])
            self.assertEqual(sha(self.dest / (row["target"] + ".meta")), row["original_meta_sha256"])
        replayed = catalog_rebuild.shader_override_rows(receipt, self.input_id, set(), {}, candidate_work=self.work)
        self.assertEqual(len(replayed), 18)

    def test_screen_damage_seventh_row_preserves_exporter_identity_through_r3_r4(self):
        self.install_shader_candidates(include_translucent=True, include_screen_damage=True)
        self.install_translucent_candidates()
        staging = self.staging()
        staged = whole_catalog.prepare_integration(staging)
        staging.flush()
        self.assertTrue(staged["enabled"])
        receipt = catalog_rebuild.read_shader_override_receipt(self.dest, self.input_id, self.work)
        self.assertEqual(len(receipt["rows"]), 7)
        rows = catalog_rebuild.shader_override_rows(receipt, self.input_id, set(), {}, candidate_work=self.work)
        target = "Assets/WholeGame/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader"
        self.assertIn(target, rows)
        row = rows[target]
        self.assertEqual(row["location_id"], 8943)
        self.assertEqual(row["guid"], "62decc840d5afaa49886d8b13165939e")
        self.assertEqual(row["exporter_guid"], "ed4a1bae3abd8f34b905b509b4ff70e0")
        self.assertEqual(
            (self.dest / (target + ".meta")).read_bytes(), (self.export / "Assets/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader.meta").read_bytes()
        )
        self.assertEqual(len(rows), 14)

    def test_screen_damage_wrong_exporter_refuses_before_shader_writes(self):
        self.install_shader_candidates(include_translucent=True, include_screen_damage=True)
        self.install_translucent_candidates()
        source = self.export / "Assets/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader.meta"
        self.put(source, "guid: " + "f" * 32 + "\n")
        with self.assertRaisesRegex(RuntimeError, "exact original exporter GUID"):
            whole_catalog.prepare_integration(self.staging())
        self.assertFalse((self.dest / "Assets/WholeGame/RoR2/Base/Core/CameraEffects/HGScreenDamage.shader").exists())

    def test_translucent_wrong_exporter_meta_guid_refuses_before_any_shader_write(self):
        self.install_shader_candidates(include_translucent=True)
        translucent = self.install_translucent_candidates()
        _, _, _, source_path, _, _, target = translucent[0]
        self.put(self.export / (source_path + ".meta"), "guid: " + "f" * 32 + "\n")
        with self.assertRaisesRegex(RuntimeError, "exact original exporter GUID"):
            whole_catalog.prepare_integration(self.staging())
        self.assertFalse((self.dest / target).exists())

    def test_two_shader_candidates_override_only_exact_catalog_sources_and_preserve_meta(self):
        specs = self.install_shader_candidates()
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        staging.flush()
        for loc, guid, key, source_path, kind, name, object_id, *_ in specs:
            target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
            self.assertEqual((self.dest / target).read_bytes(), ('Shader "' + name + '" {}\n').encode())
            self.assertEqual((self.dest / (target + ".meta")).read_text(), "guid: " + ("e" if loc == 16022 else "f") * 32 + "\n")
        staged_manifest = read(next((self.dest / ".rebuild/catalog-inputs").glob("integration-*/manifest.json")))
        for loc, guid, key, source_path, kind, name, object_id, *_ in specs:
            target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
            location = next(row for row in staged_manifest["locations"] if row["id"] == loc)
            self.assertEqual(location["path"], target)
            self.assertEqual(location["primaryKey"], key)
        evidence = read(next((self.dest / ".rebuild/catalog-inputs").glob("integration-*/shader-overrides.json")))
        self.assertEqual([row["location_id"] for row in evidence["rows"]], [16022, 15950])
        self.assertTrue(all(row["preserved_meta_sha256"] for row in evidence["rows"]))
        imported = read(next((self.dest / ".rebuild/catalog-inputs").glob("integration-*/import-receipt.json")))
        self.assertEqual(imported["shader_overrides"]["sha256"], sha(next((self.dest / ".rebuild/catalog-inputs").glob("integration-*/shader-overrides.json"))))

    def test_outline_generator_identity_uses_catalog_fields_without_shader_name(self):
        specs = self.install_shader_candidates()
        root = self.work / f"generated-shader-candidates/{specs[0][4]}-r3/{self.input_id}"
        manifest = read(root / "manifest.json")
        self.assertNotIn("shader_name", manifest["source"])
        self.assertTrue(whole_catalog.prepare_integration(self.staging())["enabled"])

    def test_outline_wrong_catalog_identity_refuses_before_shader_writes(self):
        specs = self.install_shader_candidates()
        root = self.work / f"generated-shader-candidates/{specs[0][4]}-r3/{self.input_id}"
        manifest = read(root / "manifest.json")
        manifest["source"]["catalog_key"] = "f" * 32
        write(root / "manifest.json", manifest)
        with self.assertRaisesRegex(RuntimeError, "Outline candidate identity"):
            whole_catalog.prepare_integration(self.staging())
        self.assertFalse((self.dest / "Assets/WholeGame" / Path(specs[0][3]).relative_to("Assets")).exists())

    def test_changed_shader_declaration_refuses_even_with_updated_manifest_hash(self):
        specs = self.install_shader_candidates()
        root = self.work / f"generated-shader-candidates/{specs[0][4]}-r3/{self.input_id}"
        shader = root / specs[0][11]
        shader.write_text('Shader "Synthetic/WrongIdentity" {}\n')
        manifest = read(root / "manifest.json")
        manifest["generated_shader_sha256"] = sha(shader)
        write(root / "manifest.json", manifest)
        with self.assertRaisesRegex(RuntimeError, "candidate declaration changed"):
            whole_catalog.prepare_integration(self.staging())

    def test_shader_candidate_drift_refuses_without_flushing_project(self):
        specs = self.install_shader_candidates()
        source = self.work / f"generated-shader-candidates/{specs[1][4]}-r3/{self.input_id}/{specs[1][11]}"
        source.write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "output differs from its manifest"):
            whole_catalog.prepare_integration(self.staging())
        first_target = "Assets/WholeGame/" + specs[0][3].removeprefix("Assets/")
        second_target = "Assets/WholeGame/" + specs[1][3].removeprefix("Assets/")
        self.assertFalse((self.dest / first_target).exists())
        self.assertFalse((self.dest / second_target).exists())

    def test_shader_override_requires_exact_two_selection_rows(self):
        self.install_shader_candidates()
        selection = read(self.recipes / "shader-catalog-overrides.json")
        selection["rows"] = selection["rows"][:1]
        write(self.recipes / "shader-catalog-overrides.json", selection)
        with self.assertRaisesRegex(RuntimeError, "historical two/six-root"):
            whole_catalog.prepare_integration(self.staging())
        self.assertFalse((self.dest / "Assets/WholeGame/RoR2/Base/Shaders/PostProcess/HGOutlineHighlight.shader").exists())

    def test_shader_candidate_recipe_path_traversal_is_refused_before_staging(self):
        specs = self.install_shader_candidates()
        row = read(self.recipes / "shader-catalog-overrides.json")["rows"][0]
        recipe_path = self.root / row["generator_recipe"]
        write(recipe_path, {"stable_output": "../../outside/{input_id}"})
        row["generator_recipe_sha256"] = sha(recipe_path)
        selection = read(self.recipes / "shader-catalog-overrides.json")
        selection["rows"][0] = row
        write(self.recipes / "shader-catalog-overrides.json", selection)
        with self.assertRaisesRegex(RuntimeError, "work-relative"):
            whole_catalog.prepare_integration(self.staging())
        target = "Assets/WholeGame/" + specs[0][3].removeprefix("Assets/")
        self.assertFalse((self.dest / target).exists())

    def test_shader_override_selection_is_default_off_and_stale_enabled_receipt_refuses(self):
        staging = self.staging()
        self.assertIsNone(whole_catalog.prepare_integration(staging))
        staging.flush()
        self.assertFalse((self.dest / ".rebuild/catalog-shader-overrides.json").exists())
        self.put(self.dest / ".rebuild/catalog-shader-overrides.json", "stale")
        with self.assertRaisesRegex(RuntimeError, "prior shader override receipt"):
            whole_catalog.prepare_integration(self.staging())

    def test_local_shader_selector_is_strict_and_absence_is_default_off(self):
        staging = self.staging()
        self.assertIsNone(whole_catalog.prepare_integration(staging))
        selector = self.work / "config/shader-catalog-overrides.json"
        for malformed in (
            {"schema": "whole-catalog-shader-overrides-activation-r1", "input_id": self.input_id, "enabled": 1},
            {"schema": "whole-catalog-shader-overrides-activation-r1", "input_id": self.input_id, "enabled": True, "rows": []},
            {"schema": "whole-catalog-shader-overrides-activation-r1", "input_id": "f" * 64, "enabled": True},
            {"schema": "unknown", "input_id": self.input_id, "enabled": True},
        ):
            write(selector, malformed)
            with self.assertRaisesRegex(RuntimeError, "Local shader override selector"):
                whole_catalog.prepare_integration(self.staging())
        selector.write_text("{ malformed json")
        with self.assertRaisesRegex(RuntimeError, "selector is malformed"):
            whole_catalog.prepare_integration(self.staging())
        self.assertFalse((self.dest / ".rebuild/catalog-shader-overrides.json").exists())

    def test_shader_selector_digest_is_joined_and_disable_requires_clean_destination(self):
        specs = self.install_shader_candidates()
        staged = whole_catalog.prepare_integration(self.staging())
        self.assertEqual(staged["selector_path"], "work/config/shader-catalog-overrides.json")
        selector_path = self.work / "config/shader-catalog-overrides.json"
        self.assertEqual(staged["selector_sha256"], sha(selector_path))
        expected, provenance = self.shader_override_provenance(specs)
        catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, expected, provenance)
        marker = read(self.dest / ".rebuild/catalog-shader-overrides.json")
        self.assertEqual(marker["selector_sha256"], sha(selector_path))
        changed = read(selector_path)
        changed["enabled"] = False
        write(selector_path, changed)
        with self.assertRaisesRegex(RuntimeError, "does not match the current local selector|prior shader override receipt"):
            rebuild.compare(self.dest, self.work / "lab-project", set(), {}, lambda _path: False, work=self.work)
        with self.assertRaisesRegex(RuntimeError, "prior shader override receipt"):
            whole_catalog.prepare_integration(self.staging())

    def test_current_project_stage_persists_disable_guard_and_receipt_mirror(self):
        self.install_shader_candidates()
        io = StageIO(self.work)
        write(self.work / "experiments/whole-catalog/latest.json", dict(path="work/catalog"))
        staged = whole_catalog.prepare_integration(io)
        self.assertTrue(staged["enabled"])
        project = self.work / "lab-project"
        marker_path = project / ".rebuild/catalog-shader-overrides.json"
        mirror_path = project / ".rebuild/catalog-shader-overrides-receipt.json"
        marker = read(marker_path)
        self.assertTrue(mirror_path.is_file())
        self.assertEqual(marker["receipt_path"], ".rebuild/catalog-shader-overrides-receipt.json")
        self.assertEqual(marker["receipt_sha256"], sha(mirror_path))
        selector = read(self.work / "config/shader-catalog-overrides.json")
        selector["enabled"] = False
        write(self.work / "config/shader-catalog-overrides.json", selector)
        latest_path = self.catalog / "integration-latest.json"
        latest_before = latest_path.read_bytes()
        next_io = StageIO(self.work)
        write(self.work / "experiments/whole-catalog/latest.json", dict(path="work/catalog"))
        with self.assertRaisesRegex(RuntimeError, "prior shader override receipt"):
            whole_catalog.prepare_integration(next_io)
        self.assertEqual(latest_path.read_bytes(), latest_before)

    def test_compare_without_override_marker_does_not_require_work_config_and_rejects_dangling_marker(self):
        marker = self.dest / ".rebuild/catalog-shader-overrides.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        work_without_config = self.root / "work-without-config"
        work_without_config.mkdir()
        result = rebuild.compare(self.dest, self.work / "lab-project", set(), {}, lambda _path: False, work=work_without_config)
        self.assertEqual(result["different"], [])
        self.assertEqual(result["missing"], [])
        marker.symlink_to(self.root / "missing-marker-target")
        with self.assertRaisesRegex(RuntimeError, "marker is not a regular file"):
            rebuild._catalog_shader_override_rows(self.dest, self.work / "lab-project", work_without_config, set(), {})

    def shader_override_provenance(self, specs):
        expected, provenance = set(), {}
        oracle = self.work / "lab-project"
        for loc, guid, key, source_path, kind, name, object_id, *_ in specs:
            target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
            original = self.export / source_path
            meta = self.export / (source_path + ".meta")
            self.put(oracle / target, original.read_text())
            self.put(oracle / (target + ".meta"), meta.read_text())
            expected.update((target, target + ".meta"))
            provenance[target] = dict(
                sha256=sha(original),
                size=original.stat().st_size,
                producer="repo-builder",
                evidence=[dict(function="whole_catalog.prepare_integration")],
            )
            provenance[target + ".meta"] = dict(sha256=sha(meta), size=meta.stat().st_size, producer="repo-builder", evidence=[])
        return expected, provenance

    def compare_provenance_with_destination_inventory(self, provenance):
        result = dict(provenance)
        for path in self.dest.rglob("*"):
            if path.is_file():
                relative = path.relative_to(self.dest).as_posix()
                result.setdefault(relative, dict(sha256=sha(path), size=path.stat().st_size, producer="repo-builder", evidence=[]))
        return result

    def test_shader_override_full_catalog_verification_and_compare_are_receipt_backed(self):
        specs = self.install_shader_candidates()
        expected, provenance = self.shader_override_provenance(specs)
        catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, expected, provenance)
        self.assertTrue((self.dest / ".rebuild/catalog-shader-overrides.json").is_file())
        catalog_rebuild.dependencies(self.dest, self.work, self.input_id, expected, provenance)
        compare_provenance = self.compare_provenance_with_destination_inventory(provenance)
        result = rebuild.compare(self.dest, self.work / "lab-project", expected, compare_provenance, lambda path: path in expected, work=self.work)
        self.assertTrue(result["equal"], result)
        target = "Assets/WholeGame/" + specs[0][3].removeprefix("Assets/")
        candidate = self.dest / target
        before = candidate.read_bytes()
        candidate.write_bytes(before + b"\n// unreceipted drift\n")
        compare_provenance = self.compare_provenance_with_destination_inventory(provenance)
        drift = rebuild.compare(self.dest, self.work / "lab-project", expected, compare_provenance, lambda path: path in expected, work=self.work)
        self.assertIn(target, drift["different"])

    def test_shader_override_without_provenance_uses_exact_export_and_receipt(self):
        specs = self.install_shader_candidates()
        expected, provenance = self.shader_override_provenance(specs)
        targets = ["Assets/WholeGame/" + spec[3].removeprefix("Assets/") for spec in specs]
        for target in targets:
            provenance.pop(target)
            provenance.pop(target + ".meta")
            (self.work / "lab-project" / target).unlink()
            (self.work / "lab-project" / (target + ".meta")).unlink()
        catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, expected, provenance)
        catalog_rebuild.dependencies(self.dest, self.work, self.input_id, expected, provenance)
        compare_provenance = self.compare_provenance_with_destination_inventory(provenance)
        for target in targets:
            compare_provenance.pop(target, None)
            compare_provenance.pop(target + ".meta", None)
        result = rebuild.compare(self.dest, self.work / "lab-project", expected, compare_provenance, lambda path: path in expected, work=self.work)
        self.assertTrue(result["equal"], result)
        self.assertTrue(set(targets).issubset(result["identical"]))
        self.assertTrue({target + ".meta" for target in targets}.issubset(result["identical"]))
        original = self.export / specs[0][3]
        original.write_bytes(original.read_bytes() + b"\n// accepted export drift\n")
        receipt = catalog_rebuild.read_shader_override_receipt(self.dest, self.input_id, self.work)
        with self.assertRaisesRegex(RuntimeError, "does not match its exact builder receipt"):
            catalog_rebuild.verify_outputs(StageIO(self.work, self.dest), expected, provenance, receipt, self.input_id)

    def test_shader_override_compare_refuses_receipt_or_preserved_meta_drift(self):
        specs = self.install_shader_candidates()
        expected, provenance = self.shader_override_provenance(specs)
        catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, expected, provenance)
        meta = self.dest / ("Assets/WholeGame/" + specs[1][3].removeprefix("Assets/") + ".meta")
        meta.write_text("guid: " + "0" * 32 + "\n")
        compare_provenance = self.compare_provenance_with_destination_inventory(provenance)
        with self.assertRaisesRegex(RuntimeError, "did not preserve its exact source or .meta"):
            rebuild.compare(self.dest, self.work / "lab-project", expected, compare_provenance, lambda path: path in expected, work=self.work)
        meta.write_text((self.work / "lab-project" / meta.relative_to(self.dest)).read_text())
        marker = read(self.dest / ".rebuild/catalog-shader-overrides.json")
        receipt = self.dest / marker["receipt_path"]
        receipt.write_text(receipt.read_text() + " ")
        with self.assertRaisesRegex(RuntimeError, "receipt is missing or changed"):
            rebuild.compare(self.dest, self.work / "lab-project", expected, compare_provenance, lambda path: path in expected, work=self.work)

    def test_import_remaps_ui_and_flushes_only_destination(self):
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        self.assertFalse((self.dest / self.target).exists())
        self.assertIn("new-ui", staging.read_text(self.dest / self.target))
        staging.flush()
        self.assertEqual((self.dest / (self.target + ".meta")).read_text(), "guid: " + self.guid + "\n")
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})
        self.assertTrue(list((self.dest / ".rebuild/catalog-inputs").glob("integration-*/manifest.json")))

    def test_r3_fills_body_when_r2_only_placed_importer(self):
        self.put(self.dest / (self.target + ".meta"), "guid: " + self.guid + "\n")
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        self.assertIn("new-ui", staging.read_text(self.dest / self.target))

    def test_r4_fills_body_when_r2_only_placed_importer(self):
        self.put(self.dest / (self.target + ".meta"), "guid: " + self.guid + "\n")
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        self.assertNotIn("--- !u!114 &2", staging.read_text(self.dest / self.target))

    def test_sanitizer_uses_public_script_guid_before_r7(self):
        (self.dest / "Assets/LabLoadingScene/SilentProjectileBoundary.cs.meta").unlink()
        write(self.recipes / "project-layout.json", dict(runtime_source_guids={"runtime/world/SilentProjectileBoundary.cs": "d" * 32}))
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        self.assertNotIn("--- !u!114 &2", staging.read_text(self.dest / self.target))
        self.assertFalse(staging.is_file(self.dest / "Assets/LabLoadingScene/SilentProjectileBoundary.cs.meta"))

    def test_existing_guid_owner_is_reused(self):
        self.put(self.dest / "Assets/Existing.prefab", "owned")
        self.put(self.dest / "Assets/Existing.prefab.meta", "guid: " + self.guid + "\n")
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        staging.flush()
        self.assertFalse((self.dest / self.target).exists())
        manifest = read(next((self.dest / ".rebuild/catalog-inputs").glob("integration-*/manifest.json")))
        self.assertEqual(manifest["locations"][0]["path"], "Assets/Existing.prefab")

    def test_duplicate_owner_is_rejected(self):
        for name in ("A", "B"):
            self.put(self.dest / ("Assets/" + name + ".meta"), "guid: " + self.guid + "\n")
        with self.assertRaisesRegex(RuntimeError, "Duplicate imported GUID"):
            whole_catalog.prepare_integration(self.staging())

    def test_scene_guid_repair_uses_recorded_identity(self):
        write(self.catalog / "source-guid-repairs.json", [dict(source=self.source, source_guid=self.guid, guid="e" * 32)])
        index = read(self.catalog / "source-guid-index.json")
        del index[self.guid]
        index["e" * 32] = self.source
        write(self.catalog / "source-guid-index.json", index)
        self.pin()
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        self.assertEqual(staging.read_text(self.dest / (self.target + ".meta")), "guid: " + "e" * 32 + "\n")

    def test_failed_analysis_leaves_no_completion_marker(self):
        with patch.object(catalog_analysis, "regenerate", side_effect=RuntimeError("inspection incomplete")):
            with self.assertRaisesRegex(RuntimeError, "inspection incomplete"):
                self.staging()
        self.assertFalse((self.dest / ".rebuild/catalog-inputs/analysis-complete.json").exists())
        self.staging()
        self.assertTrue((self.dest / ".rebuild/catalog-inputs/analysis-complete.json").is_file())

    def test_analysis_is_regenerated_once_per_destination(self):
        self.staging()
        self.staging()
        self.assertEqual(catalog_analysis.regenerate.call_count, 1)

    def test_input_identity_drift_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "accepted input"):
            catalog_rebuild.CatalogIO(self.work, self.dest, "f" * 64)

    def test_real_prepare_preserves_original_paths(self):
        with patch.object(whole_catalog, "now", return_value="fresh-time"):
            whole_catalog.prepare_integration()
        self.assertEqual(read(self.catalog / "integration-fresh-time/manifest.json")["attempt"], "integration-fresh-time")
        self.assertIn("new-ui", (self.work / "lab-project" / self.target).read_text())
        self.assertTrue(list(self.catalog.glob("integration-*/import-receipt.json")))
        self.assertTrue((self.work / "lab-project/Assets/Editor/WholeCatalogHost.cs").is_file())
        self.assertFalse((self.work / "lab-project/.rebuild").exists())

    def test_pinned_attempt_is_rebuild_only_and_rejects_path_escape(self):
        for attempt in ("../escape", "integration-../../escape", ""):
            with self.assertRaisesRegex(RuntimeError, "Pinned integration"):
                whole_catalog.prepare_integration(self.staging(), attempt=attempt)
        with self.assertRaisesRegex(RuntimeError, "Pinned integration"):
            whole_catalog.prepare_integration(attempt="integration-pinned")

    def test_identity_pin_drift_or_wrong_input_fails_before_catalog_write(self):
        recipe = read(self.recipes / "build-entry-inputs.json")
        for change, message in ((dict(input_id="wrong"), "requires accepted input"), (dict(bootstrap_attempt="../escape"), "Invalid bootstrap")):
            write(self.recipes / "build-entry-inputs.json", dict(recipe, **change))
            with self.assertRaisesRegex(RuntimeError, message):
                catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, set(), {})
        self.assertFalse((self.dest / ".rebuild/catalog-inputs").exists())

    def test_dependency_walk_sanitizes_pending_import(self):
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        text = staging.read_text(self.dest / self.target)
        self.assertNotIn("--- !u!114 &2", text)
        self.assertIn("new-ui", text)
        staging.flush()
        self.assertTrue(list((self.dest / ".rebuild/composition/rebuild-dependencies").glob("dependency-stage-*/optional-content-transformation.json")))
        self.assertFalse((self.work / "lab-project" / self.target).exists())

    def test_real_dependencies_preserve_original_paths(self):
        composition_migration.stage_missing_sources()
        self.assertNotIn("--- !u!114 &2", (self.work / "lab-project" / self.target).read_text())
        self.assertTrue(list((self.work / "evidence").glob("dependency-stage-*/receipt.json")))
        self.assertFalse((self.work / "lab-project/.rebuild").exists())

    def test_support_source_reads_il_contract_and_destination_owner(self):
        index = read(self.catalog / "source-guid-index.json")
        index["e" * 32] = self.support
        write(self.catalog / "source-guid-index.json", index)
        self.pin()
        self.put(self.dest / self.support_target, (self.export / self.support).read_text())
        self.put(self.dest / (self.support_target + ".meta"), "guid: " + "e" * 32 + "\n")
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        self.assertTrue(staging.read_text(self.dest / self.support_target).startswith("using Event = AK.Wwise.Event;\n"))
        whole_catalog.run.assert_called_once()

    def test_real_support_repair_preserves_source_receipt_paths(self):
        project = self.work / "lab-project"
        self.put(project / self.support_target, (self.export / self.support).read_text())
        whole_catalog.repair_support_source(self.export, {self.support: self.support_target}, project, self.work / "evidence")
        self.assertTrue((project / self.support_target).read_text().startswith("using Event ="))
        self.assertTrue((self.work / "evidence/support-source-alias.json").is_file())
        whole_catalog.run.assert_called_once()

    def test_output_drift_does_not_flush_pending_project_files(self):
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            catalog_rebuild.verify_outputs(staging, {self.target}, {self.target: dict(sha256="0" * 64, size=1)})
        self.assertFalse((self.dest / self.target).exists())

    def test_dependencies_require_r3_marker(self):
        with self.assertRaisesRegex(RuntimeError, "Run catalog-closure"):
            catalog_rebuild.dependencies(self.dest, self.work, self.input_id, set(), {})

    def test_catalog_coordinator_hash_gate_and_marker(self):
        import hashlib

        content = self.body.replace("old-ui", "new-ui").encode()
        provenance = {self.target: dict(sha256=hashlib.sha256(content).hexdigest(), size=len(content))}
        catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, {self.target}, provenance)
        self.assertEqual((self.dest / self.target).read_bytes(), content)
        self.assertEqual(read(self.dest / ".rebuild/catalog-closure-complete.json")["input_id"], self.input_id)
        manifest = self.dest / ".rebuild/catalog-inputs/integration-pinned/manifest.json"
        self.assertEqual(read(manifest)["attempt"], "integration-pinned")
        before = manifest.read_bytes()
        with patch.object(whole_catalog, "now", return_value="another-time"):
            catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, {self.target}, provenance)
        self.assertEqual(manifest.read_bytes(), before)
        # R7 consumes this regenerated identity without replacing it. WholeCatalogBuild
        # carries the same manifest fields into the payload when adding bundle receipts.
        staging = self.staging()
        whole_catalog.generate_build_bootstrap(staging, read(manifest), dict(input_id=self.input_id, runtime_key_edges=[]))
        bootstrap = staging.read(self.dest / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json")
        self.assertEqual(bootstrap["attempt"], read(manifest)["attempt"])
        result = rebuild.compare(
            self.dest,
            self.dest,
            {self.target},
            {**provenance, **{p.relative_to(self.dest).as_posix(): {} for p in self.dest.rglob("*") if p.is_file()}},
            lambda path: path == self.target,
        )
        self.assertTrue(result["equal"])

    def test_catalog_requires_r2_destination_config(self):
        (self.dest / ".rebuild/composition/scene-probe-build.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "from R2"):
            catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, set(), {})

    def test_dependencies_coordinator_verifies_and_flushes(self):
        import hashlib

        write(self.dest / ".rebuild/catalog-closure-complete.json", dict(input_id=self.input_id))
        content = b"%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component:\n  ui: new-ui\n"
        provenance = {self.target: dict(sha256=hashlib.sha256(content).hexdigest(), size=len(content))}
        catalog_rebuild.dependencies(self.dest, self.work, self.input_id, {self.target}, provenance)
        self.assertEqual((self.dest / self.target).read_bytes(), content)

    def test_later_builder_scene_is_deferred_only_in_rebuild(self):
        scene = "Assets/LabLoadingScene/SourceScenes/synthetic/synthetic.unity"
        for config in (self.work / "scene-probe-build.json", self.dest / ".rebuild/composition/scene-probe-build.json"):
            write(config, dict(prefabAssets=[self.target], scenes=[scene]))
        write(self.dest / ".rebuild/catalog-closure-complete.json", dict(input_id=self.input_id))
        later = dict(producer="repo-builder", evidence=[dict(function="source_scene_candidate.prepare")])
        with patch.object(catalog_rebuild, "verify_outputs", side_effect=lambda staging, *_, **__: staging.flush()):
            catalog_rebuild.dependencies(self.dest, self.work, self.input_id, set(), {scene: later})
        receipt = read(next((self.dest / ".rebuild/composition/rebuild-dependencies").glob("dependency-stage-*/receipt.json")))
        self.assertEqual(receipt["deferred_to_later_steps"], [scene])
        with self.assertRaisesRegex(RuntimeError, "refuse original-source substitution"):
            composition_migration.stage_missing_sources()
        with self.assertRaisesRegex(RuntimeError, "refuse original-source substitution"):
            catalog_rebuild.dependencies(
                self.dest,
                self.work,
                self.input_id,
                set(),
                {scene: dict(producer="repo-builder", evidence=[dict(function="whole_catalog.prepare_integration")])},
            )

    def test_destination_config_is_required_after_r3(self):
        write(self.dest / ".rebuild/catalog-closure-complete.json", dict(input_id=self.input_id))
        (self.dest / ".rebuild/composition/scene-probe-build.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "destination composition config"):
            catalog_rebuild.dependencies(self.dest, self.work, self.input_id, set(), {})

    def test_support_binary_drift_is_rejected(self):
        self.put(self.dest / self.support_target, (self.export / self.support).read_text())
        staging = self.staging()
        self.put(self.binary, "changed binary")
        with self.assertRaisesRegex(RuntimeError, "accepted original field contract"):
            whole_catalog.repair_support_source(self.export, {self.support: self.support_target}, self.dest, self.dest / "receipt", staging)

    def test_auxiliary_reads_use_flushed_destination_config(self):
        staging = self.staging()
        write(self.work / "scene-probe-build.json", dict(prefabAssets=["Assets/MustNotRead.prefab"]))
        self.assertEqual(staging.read(self.work / "scene-probe-build.json")["prefabAssets"], [self.target])

    def test_coordinator_order_and_membership(self):
        self.assertEqual(list(rebuild.STEPS)[:6], ["assemblies", "shader-pipeline", "composition", "project-inputs", "catalog-closure", "dependencies"])
        self.assertEqual(rebuild.STEPS["catalog-closure"].evidence, ("whole_catalog.prepare_integration",))
        self.assertIn("whole_catalog.repair_support_source", rebuild.STEPS["dependencies"].evidence)
