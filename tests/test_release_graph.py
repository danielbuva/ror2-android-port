"""Source graph contracts with authored supplier bodies; no game inputs."""

import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/phone-build/owner-apk" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G, J = load("release_graph"), load("release_jobs")


class ReleaseGraphTests(unittest.TestCase):
    def test_install_plan_reports_unbound_producer_inputs(self):
        graph = G.Graph(ROOT, {})
        producer, dependency = "recipe/jobs/fixture.json", "recipe/jobs/dependency.json"
        graph.jobs[producer] = {
            "script": "fixture.py",
            "needs": [dependency],
            "arguments": ["${input:pc}", "${input:inventory}", "${input_relative:missing_root}/data"],
        }
        graph.jobs[dependency] = {
            "script": "dependency.py",
            "needs": [],
            "request": {"metadata": {"sha256": "${input_sha256:missing_digest}"}},
        }
        with self.assertRaisesRegex(ValueError, "install plan lacks admitted input bindings: missing_digest, missing_root$"):
            graph.attach_install_plan(
                {"entries": {"payload/fixture": {"job": producer}}}, required_inputs="recipe/input.json", workspace_bytes=0, bindings={"pc": "."}
            )

    def test_staged_phone_entry_points_run_without_a_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary).resolve()
            repo = app / "runtime/repo"
            cwd = app / "unrelated"
            native = app / "native"
            inputs = app / "owner-input"
            for directory in (cwd, native, inputs / "game", inputs / "sdk", inputs / "work/inventory"):
                directory.mkdir(parents=True)

            graph = G.Graph(ROOT, {})
            paths = graph.current_code_sources(signed_audio=True)
            self.assertFalse({"AGENTS.md", "PORTING_STATE.md"} & set(paths))
            graph.jobs["recipe/jobs/test-code.json"] = {"script": "tools/phone-build/owner-code/produce.py", "needs": []}
            graph.job_profiles["recipe/jobs/test-code.json"] = {}
            graph.public_files["recipe/jobs/test-code.json"] = paths
            entry = graph.entry("recipe/jobs/test-code.json")
            for name in set(entry["producer_files"] + entry["recipe_files"]) - set(graph.jobs):
                target = repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)

            def run(script, *arguments):
                return subprocess.run(
                    [sys.executable, "-I", "-B", "-S", str(repo / script), *map(str, arguments)],
                    cwd=cwd,
                    env={**os.environ, "PATH": str(cwd)},
                    text=True,
                    capture_output=True,
                    timeout=30,
                )

            for script in sorted(
                J.PRODUCERS - {"tools/phone-build/owner-code/run_android.py"}
                | {
                    "scripts/lab/original_game_audio_produce.py",
                    "tools/phone-build/accepted-output/phone_runner.py",
                    "tools/phone-build/owner-apk/build_owner_apk.py",
                    "tools/unity/support/audio/managed-producer/produce.py",
                    "tools/unity/support/audio/generators/stage_original_game_banks.py",
                    "tools/wwise-android-abi/generate.py",
                }
            ):
                with self.subTest(script=script):
                    result = run(script, "--help")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)

            request = inputs / "code.json"
            request.write_text(json.dumps(dict(source_inputs={}, audio_members=["Init.bnk"], output="conversion")))
            (inputs / "input-hashes.json").write_text("{}")
            (inputs / "work/inventory/files.json").write_text('{"files":[]}')
            # The real toolhost launch must reach owner-input validation after
            # importing the managed and audio owners from the staged tree.
            result = run("tools/phone-build/owner-code/run_android.py", request, repo.parent, native)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(str(inputs / "work/config/accepted-input.json"), result.stderr)
            self.assertIn("FileNotFoundError", result.stderr)

            result = run("tools/phone-build/managed-host/run_profile.py", repo.parent)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(str(app / "user-input/input-hashes.json"), result.stderr)

            request.write_text("{}")
            result = run("tools/phone-build/owner-apk/updates.py", request, repo.parent, native)
            self.assertEqual(result.returncode, 1, result.stderr)
            state = json.loads((inputs / "update-state.json").read_text())
            self.assertEqual(state, {"state": "ERROR", "message": "explicit trusted installer action/context required"})

    def test_private_record_pins_resolve_only_unique_source_and_output_pairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "recipe").mkdir()
            source = ["original.bundle", "CAB-source", 10]
            target = dict(bundle="pack", member="CAB-pack", path_id=20)

            def profile(name, outputs):
                path = repo / ("recipe/owner-" + name + ".json")
                path.write_text(
                    json.dumps(
                        dict(
                            bundles=[dict(path=source[0], sha256="a" * 64, members=[dict(name=source[1], objects=[dict(path_id=source[2], outputs=outputs)])])]
                        )
                    )
                )
                return G.digest(path)

            first = profile("first", [target, dict(target, path_id=21)])
            alias = profile("alias", [dict(target, path_id=22)])
            duplicate = profile("duplicate", [target])
            # An unrelated malformed recipe must remain unparsed.
            (repo / "recipe/owner-unused.json").write_text("unread")
            graph = G.Graph(repo, {})
            selected = dict(record="f" * 64, source=source, record_source=["pack", "CAB-pack", 20], destination=["content", "CAB-content", 7])
            resolved = graph.bundle_bindings([selected], "content", "CAB-content", source_profiles=[first, alias])
            self.assertEqual(resolved["unresolved"], [])
            self.assertEqual(
                resolved["bindings"],
                [
                    {key: selected[key] for key in ("source", "record_source", "destination")}
                    | dict(supplier=first, selection=dict(record=selected["record"], record_source=selected["record_source"]))
                ],
            )
            self.assertEqual([row["name"] for row in resolved["suppliers"]], [first])
            self.assertEqual(set(graph.jobs), {"recipe/jobs/owner-first.json"})
            ambiguous = graph.bundle_bindings([selected], "content", "CAB-content", source_profiles=[first, duplicate])
            self.assertEqual(ambiguous["bindings"], [])
            self.assertEqual(ambiguous["unresolved"][0]["reason"], "ambiguous source supplier profiles")
            self.assertEqual(len(ambiguous["unresolved"][0]["candidates"]), 3)
            moved = graph.bundle_bindings([dict(selected, record_source=["pack", "CAB-pack", 99])], "content", "CAB-content", source_profiles=[alias])
            self.assertEqual(moved["unresolved"], [])
            self.assertEqual(moved["bindings"][0]["record_source"], ["pack", "CAB-pack", 22])
            self.assertEqual(moved["bindings"][0]["selection"], dict(record="f" * 64, record_source=["pack", "CAB-pack", 99]))
            self.assertEqual(selected["record_source"], ["pack", "CAB-pack", 20])
            missing = graph.bundle_bindings([dict(selected, record_source=["pack", "CAB-pack", 99])], "content", "CAB-content", source_profiles=[first, alias])
            self.assertEqual(missing["bindings"], [])
            self.assertEqual(missing["unresolved"][0]["reason"], "ambiguous source supplier profiles")
            self.assertEqual(len(missing["unresolved"][0]["candidates"]), 3)
            foreign = graph.bundle_bindings([dict(selected, source=["other.bundle", *source[1:]])], "content", "CAB-content", source_profiles=[first])
            self.assertEqual(foreign["unresolved"][0]["candidates"], [])

    def test_bundle_binding_audit_keeps_missing_and_foreign_identities_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "recipe").mkdir()
            profile = repo / "recipe/owner-records.jsonl.gz"
            profile.write_bytes(gzip.compress(b'{"input_id":"authored"}\n'))
            graph = G.Graph(repo, {})
            pin = G.digest(profile)
            good = dict(record=pin, destination=["content", "CAB-content", 7], source=["a.bundle", "CAB-a", 10], record_source=["pack", "CAB-pack", 20])
            rows = [
                good,
                dict(good, destination=["content", "CAB-content", 8], source=["b.bundle", "CAB-b", 10]),
                dict(good),
                dict(good, destination=["content", "CAB-content", 9], record="f" * 64),
                {key: value for key, value in dict(good, destination=["content", "CAB-content", 11]).items() if key != "source"},
                dict(good, destination=["external", "CAB-content", 7]),
            ]
            result = graph.bundle_bindings(iter(rows), "content", "CAB-content")
            self.assertEqual(len(result["bindings"]), 2)
            self.assertNotEqual(result["bindings"][0]["source"], result["bindings"][1]["source"])
            self.assertEqual(len(result["suppliers"]), 1)
            supplier = result["suppliers"][0]
            self.assertEqual(supplier["profile"], dict(path="${repo}/recipe/owner-records.jsonl.gz", bytes=profile.stat().st_size, sha256=pin))
            self.assertEqual(supplier["types"], G.Graph.artifact_pin("recipe/jobs/owner-records.json", "types"))
            self.assertEqual(
                [row["reason"] for row in result["unresolved"]],
                [
                    "duplicate destination",
                    "missing source supplier profile",
                    "explicit source and record_source identities required",
                    "foreign or missing destination",
                ],
            )
            graph.jobs["recipe/jobs/owner-records.json"]["artifacts"].pop("types")
            incomplete = graph.bundle_bindings([good], "content", "CAB-content")
            self.assertEqual(incomplete["bindings"], [])
            self.assertEqual(incomplete["unresolved"][0]["reason"], "supplier requires a final container instead of a typed record pack")

    def test_current_witness_job_requires_and_signs_final_player_and_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "recipe").mkdir()
            source = repo / "tools/phone-build/metadata/Program.cs"
            source.parent.mkdir(parents=True)
            source.write_text("// authored metadata reader fixture\n")
            player = repo / "recipe/owner-player.json"
            player.write_text(json.dumps(dict(project_assemblies=[], outputs={}, registry=dict(file="registry.assets", path="registry.json"))))
            player_job = "recipe/jobs/owner-player.json"
            profile = repo / "recipe/owner-witness.json"
            profile.write_text(
                json.dumps(
                    dict(
                        schema="owner-bundle-managed-release-v1",
                        profiles=[player.relative_to(repo).as_posix()],
                        request=dict(
                            registry_receipt=G.Graph.artifact_pin(player_job, "registry_receipt"),
                            managed_providers=dict(path="${input:managed}/providers.json"),
                        ),
                    )
                )
            )
            graph = G.Graph(repo, {})
            job = graph.build(G.digest(profile))
            descriptor = graph.jobs[job]
            self.assertEqual(descriptor["needs"], [player_job])
            self.assertEqual(descriptor["artifacts"]["metadata"], "metadata.json")
            self.assertIn(source.relative_to(repo).as_posix(), graph.entry(job)["producer_files"])
            self.assertIn(player_job, graph.entry(job)["recipe_files"])
            value = json.loads(profile.read_text())
            value["request"]["registry_receipt"]["path"] = "${input:retained_registry}"
            profile.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "final player registry"):
                G.Graph(repo, {}).build(G.digest(profile))

    def test_catalog_fanin_binds_actual_outputs_and_embedded_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "recipe").mkdir()
            identity = dict(input_id="a" * 64, attempt="authored-startup")
            bootstrap = repo / "recipe/bootstrap.json"
            bootstrap.write_text(json.dumps(identity))
            metadata = repo / "recipe/metadata.json"
            metadata.write_text(json.dumps(identity))
            request = repo / "recipe/catalog-request.json"
            request.write_text(
                json.dumps(
                    dict(
                        schema="owner-catalog-inputs-v1",
                        metadata=dict(path="${input:catalog_metadata}", bytes=metadata.stat().st_size, sha256=G.digest(metadata)),
                        **identity,
                    )
                )
            )
            graph = G.Graph(repo, {})
            profiles = {
                "final": dict(sources=[], bundle=dict(name="authored", asset="asset")),
                "supplier": dict(bundles=[]),
                "windows": dict(original_bundle={}),
                "player": dict(
                    project_assemblies=[],
                    outputs={},
                    registry=dict(file="registry.assets", path="registry-policy.json"),
                    text_assets=dict(
                        files=[
                            dict(name="WholeCatalogBootstrap", recipe=dict(path="bootstrap.json", bytes=bootstrap.stat().st_size, sha256=G.digest(bootstrap)))
                        ]
                    ),
                ),
            }
            for name, profile in profiles.items():
                path = repo / ("recipe/" + name + ".json")
                path.write_text(json.dumps(profile))
                graph.profile_files[name] = path.relative_to(repo).as_posix()
                graph.job_profiles[name] = profile
                target = "apk/assets/bin/Data/registry.assets" if name == "player" else "payload/" + name
                if name == "final":
                    target = "payload/authored"
                graph.jobs[name] = dict(script=G.PREFIX + "object_produce.py", outputs={target: "actual/" + name}, artifacts={}, needs=[])
            name = graph.catalog_complete(list(profiles), "recipe/catalog-request.json")
            job = graph.jobs[name]
            self.assertIn(job["script"], J.PRODUCERS)
            self.assertEqual(job["needs"], ["final", "player"])
            self.assertEqual(set(job["request"]["bundles"]), {"authored"})
            self.assertEqual(len(job["request"]["profiles"]), 1)
            self.assertEqual(graph.jobs["final"]["artifacts"]["catalog_bundle"], "actual/final")
            self.assertEqual(graph.jobs["player"]["artifacts"]["catalog_registry"], "actual/player")
            closure = graph.entry(name)
            for path in ("recipe/catalog-request.json", "recipe/final.json", "recipe/player.json", "recipe/bootstrap.json"):
                self.assertIn(path, closure["recipe_files"])
            self.assertNotIn("recipe/metadata.json", closure["producer_files"])
            # Derived outputs must never feed back into the bundle population.
            (repo / "recipe/registry-policy.json").write_text("{}")
            for producer in ("catalog_complete", "bundle_manifest", "object_produce"):
                script = repo / G.PREFIX / (producer + ".py")
                script.parent.mkdir(parents=True, exist_ok=True)
                script.write_text("# authored fixture\n")
            selected = [graph.profile_files[value] for value in profiles]
            names = {G.digest(repo / graph.profile_files[value]): value for value in profiles}
            graph.build = lambda pin: names[pin]
            index = graph.compile(selected, bundle_manifest=True, catalog_request="recipe/catalog-request.json")
            self.assertIn("payload/whole-catalog.json", index["entries"])
            manifest = graph.jobs["recipe/jobs/owner-bundle-manifest.json"]["request"]
            self.assertNotIn("whole-catalog.json", [row["name"] for row in manifest["bundles"]])
            self.assertEqual(set(job["request"]["bundles"]), {"authored"})
            template = json.loads(request.read_text())
            policy = repo / "recipe/catalog-projection.json"
            policy.write_text("{}")
            projected = {key: value for key, value in template.items() if key != "metadata"} | {"projection": "recipe/catalog-projection.json"}
            request.write_text(json.dumps(projected))
            with self.assertRaisesRegex(ValueError, "requires original-input code conversion"):
                graph.catalog_complete(list(profiles), "recipe/catalog-request.json")
            code = "recipe/jobs/owner-code-conversion.json"
            graph.conversion = code
            graph.jobs[code] = dict(script="tools/phone-build/owner-code/produce.py", outputs={}, artifacts={}, needs=[])
            graph.job_profiles[code] = {}
            graph.catalog_complete(list(profiles), "recipe/catalog-request.json")
            job = graph.jobs[name]
            self.assertEqual(job["needs"], ["final", "player", code])
            self.assertEqual(job["request"]["projection"]["source"], graph.artifact_pin(code, "original_catalog"))
            self.assertEqual(graph.jobs[code]["artifacts"]["original_catalog"], "managed-production/original-catalog.json")
            self.assertIn("recipe/catalog-projection.json", graph.entry(name)["recipe_files"])
            request.write_text(json.dumps(template))
            changed = json.loads(request.read_text())
            changed["attempt"] = "other"
            request.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "catalog/bootstrap identity differs"):
                graph.catalog_complete(list(profiles), "recipe/catalog-request.json")
            changed["attempt"] = identity["attempt"]
            request.write_text(json.dumps(changed))
            bootstrap.write_text(json.dumps(dict(identity, attempt="other")))
            with self.assertRaisesRegex(ValueError, "bootstrap pin differs"):
                graph.catalog_complete(list(profiles), "recipe/catalog-request.json")
            graph.job_profiles["player"]["text_assets"]["files"][0]["recipe"].update(bytes=bootstrap.stat().st_size, sha256=G.digest(bootstrap))
            with self.assertRaisesRegex(ValueError, "catalog/bootstrap identity differs"):
                graph.catalog_complete(list(profiles), "recipe/catalog-request.json")

    @staticmethod
    def selected_fixture(repo):
        (repo / "recipe").mkdir()
        supplier = repo / "recipe/owner-supplier.json"
        supplier.write_text(json.dumps({"bundles": [{"members": [{"objects": []}]}]}))
        selected = repo / "recipe/owner-selected.json"
        selected.write_text(json.dumps({"sources": [], "bundle": {"name": "authored.bundle"}, "objects": [{"record": G.digest(supplier)}]}))
        for name in ("object_produce", "record_produce", "bundle_manifest"):
            path = repo / G.PREFIX / (name + ".py")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# authored fixture\n")
        return selected, supplier

    def test_single_profile_selection_only_parses_selected_dependency_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            selected, supplier = self.selected_fixture(repo)
            # Unselected malformed bodies must not be parsed during indexing.
            (repo / "recipe/owner-unselected.json").write_text("not JSON")
            with gzip.open(repo / "recipe/owner-unselected.jsonl.gz", "wt") as stream:
                stream.write('{"not_a_header": true}\n')
            reads = []
            read_bytes = Path.read_bytes

            def tracked(path, *args, **kwargs):
                reads.append(path)
                return read_bytes(path, *args, **kwargs)

            with mock.patch.object(Path, "read_bytes", tracked), mock.patch.object(G.gzip, "GzipFile", wraps=gzip.GzipFile) as compressed:
                graph = G.Graph(repo, {})
                self.assertEqual(reads, [])
                graph.compile([selected.relative_to(repo).as_posix()])
                self.assertEqual(reads, [selected, supplier])
                graph.build(G.digest(selected))
                self.assertEqual(reads, [selected, supplier])
                compressed.assert_not_called()
            with self.assertRaisesRegex(ValueError, "unknown compressed record profile header"):
                graph.build(G.digest(repo / "recipe/owner-unselected.jsonl.gz"))
            with self.assertRaises(json.JSONDecodeError):
                graph.build(G.digest(repo / "recipe/owner-unselected.json"))

    def test_supplier_changed_after_index_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            selected, supplier = self.selected_fixture(repo)
            graph = G.Graph(repo, {})
            supplier.write_text("not JSON")
            with self.assertRaisesRegex(ValueError, "source supplier profile drift"):
                graph.build(G.digest(selected))
            self.assertEqual(graph.jobs, {})

    def test_selected_compressed_header_is_checked_despite_job_name_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, supplier = self.selected_fixture(repo)
            compressed = supplier.with_suffix(".jsonl.gz")
            with gzip.open(compressed, "wt") as stream:
                stream.write('{"invalid_header": true}\n')
            graph = G.Graph(repo, {})
            graph.build(G.digest(supplier))
            with self.assertRaisesRegex(ValueError, "unknown compressed record profile header"):
                graph.build(G.digest(compressed))

    def test_lazy_graph_output_matches_eager_serialized_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            self.selected_fixture(repo)
            graph = G.Graph(repo, {})
            index = graph.compile(["recipe/owner-selected.json"], bundle_manifest=True)

            for name, job in graph.jobs.items():
                closure = graph.entry(name)
                self.assertEqual(job.pop("source_files"), sorted(set(closure["recipe_files"]) | set(closure["producer_files"])))

            def wire(value):
                return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()

            for name, job in graph.jobs.items():
                index["files"][name] = hashlib.sha256(wire(job)).hexdigest()
            # Descriptor fixture includes final object layouts and record type tables,
            # retaining exact closure ordering and source-index serialization.
            self.assertEqual(
                hashlib.sha256(wire({"index": index, "jobs": graph.jobs})).hexdigest(), "9073f8bf0e83bbab85307c0dcb5d625471949ac878e9b2dc8131a5160e84f062"
            )

    def test_scene_record_suppliers_close_published_consumers(self):
        graph = G.Graph(ROOT, {})
        for scene, supplier, count in (
            ("artifactworld01", "artifactworld01-native-records", 6),
            ("champrush", "champrush-director-records", 2),
            ("splash", "splash-director-records", 2),
            ("conduitcanyon", "conduitcanyon-director-records", 1),
        ):
            with self.subTest(scene=scene):
                profile = ROOT / ("recipe/owner-" + supplier + ".json")
                source = json.loads(profile.read_text())
                outputs = [row for bundle in source["bundles"] for member in bundle["members"] for obj in member["objects"] for row in obj["outputs"]]
                self.assertEqual(len(outputs), count)
                name = graph.build(G.digest(ROOT / ("recipe/owner-" + scene + ("-objects.json" if scene == "conduitcanyon" else "-whole-objects.json"))))
                self.assertIn("recipe/" + profile.name, graph.entry(name)["recipe_files"])
                self.assertIn("payload/whole-scene-" + scene, graph.jobs[name]["outputs"])

    def test_player_defaults_use_android_player_without_changing_shader_sdk(self):
        graph = G.Graph(ROOT, {})
        name = graph.build(G.digest(ROOT / "recipe/owner-player-data.json"))
        arguments = graph.jobs[name]["arguments"]
        self.assertEqual(arguments[arguments.index("--sdk") + 1], "${input:sdk_contents}/../../PlaybackEngines/AndroidPlayer")
        for job in graph.jobs.values():
            if Path(job["script"]).stem in {"shader_context", "shader_prefab", "payload_shader_records"}:
                args = job["arguments"]
                self.assertEqual(args[args.index("--sdk") + 1], "${input:sdk}")

    def test_barrier_job_binds_legacy_sdk_and_current_output_policy(self):
        graph = G.Graph(ROOT, {})
        barrier = graph.build(G.digest(ROOT / "recipe/owner-barrier-shaders.json"))
        args = graph.jobs[barrier]["arguments"]
        self.assertEqual(args[args.index("--legacy-sdk") + 1], "${input:legacy_sdk}")
        graph.build(G.digest(ROOT / "recipe/owner-commando-objects.json"))
        supported = {"object_produce", "record_remap", "record_produce", "mesh_produce", "avatar_produce", "texture_produce", "shader_context", "shader_prefab"}
        for job in graph.jobs.values():
            if Path(job["script"]).stem in supported:
                self.assertEqual(job["arguments"][job["arguments"].index("--comparison") + 1], "diagnostic")

    def test_object_sdk_profile_keeps_application_relative_resource_root(self):
        graph = G.Graph(ROOT, {})
        name = graph.build(G.digest(ROOT / "recipe/owner-objective-support-objects.json"))
        arguments = graph.jobs[name]["arguments"]
        root = arguments[arguments.index("--sdk") + 1]
        self.assertEqual(root, "${input:sdk_contents}/..")
        profile = graph.job_profiles[name]
        self.assertTrue(profile["sdk"]["path"].startswith("Contents/Resources/"))

    def test_final_object_layout_and_record_types_are_declared_artifacts(self):
        graph = G.Graph(ROOT, {})
        graph.build(G.digest(ROOT / "recipe/owner-commando-objects.json"))
        graph.build(G.digest(ROOT / "recipe/owner-whole-game-source-records.json"))
        shader_job = graph.build(G.digest(ROOT / "recipe/owner-player-shaders.json"))
        self.assertEqual(graph.jobs[shader_job]["artifacts"]["shared_types"], "shared-shaders/types.json")
        seen = set()
        for job in graph.jobs.values():
            producer = Path(job["script"]).stem
            if producer == "object_produce" and "objects" in job["artifacts"]:
                self.assertEqual(job["artifacts"]["layout"], "layout.json")
                seen.add(producer)
            if producer in {
                "record_produce",
                "record_remap",
                "mesh_produce",
                "avatar_produce",
                "texture_produce",
                "shader_context",
                "shader_prefab",
                "payload_shader_records",
            }:
                self.assertEqual(job["artifacts"]["types"], "types.json")
                seen.add(producer)
        self.assertIn("object_produce", seen)
        self.assertIn("record_produce", seen)

    def test_sprite_cohorts_bind_native_witness_and_standard_pack_artifacts(self):
        graph = G.Graph(ROOT, {})
        for cohort in (1, 2, 3):
            profile = ROOT / f"recipe/owner-commando-native-sprites-{cohort}.json"
            pin = G.digest(profile)
            name = graph.build(pin)
            job = graph.jobs[name]
            self.assertEqual(job["script"], G.PREFIX + "sprite_produce.py")
            self.assertEqual(job["arguments"][0], "produce")
            for argument in ("--pc-root", "--functional", "${input:sprite_native_" + pin + "}", "${input_sha256:sprite_native_" + pin + "}"):
                self.assertIn(argument, job["arguments"])
            self.assertEqual(job["artifacts"], {"receipt": "result.json", "objects": "objects.bin", "index": "index.jsonl", "types": "types.json"})

    def test_fallback_shader_job_binds_pinned_public_templates(self):
        graph = G.Graph(ROOT, {})
        name = graph.build(G.digest(ROOT / "recipe/owner-commando-fallback-shaders.json"))
        arguments = graph.jobs[name]["arguments"]
        self.assertEqual(arguments[arguments.index("--asset-ripper") + 1], "${input:asset_ripper}")

    def test_fresh_shader_jobs_bind_acquired_templates_and_cache_witnesses(self):
        graph = G.Graph(ROOT, {})
        graph.conversion = "recipe/jobs/code.json"
        graph.jobs[graph.conversion] = {"request": {"sdk_install": "${inputs}/acquired/sdk"}}
        for filename, flag, embedded in (
            ("owner-commando-fallback-shaders.json", "--asset-ripper", False),
            ("owner-player-shaders.json", "--asset-ripper-source", True),
        ):
            with self.subTest(filename=filename):
                job_name = graph.build(G.digest(ROOT / "recipe" / filename))
                job = graph.jobs[job_name]
                profile = graph.job_profiles[job_name]
                if embedded:
                    profile = profile["tmp_dummy"]
                root = G.ASSET_RIPPER_SOURCE + "/" + profile["exporter_revision"] + "/"
                prefix = "" if embedded else G.ASSET_RIPPER_TEMPLATES
                argv = job["arguments"]
                self.assertEqual(argv[argv.index(flag) + 1], G.ASSET_RIPPER_SOURCE)
                recovered_tools = set()
                for tool, filename in (("d3dasm", "libd3dasm.so"), ("hlsl-tool", "libhlsl-decompiler.so")):
                    if not embedded:
                        self.assertNotIn("--" + tool, argv)
                        continue
                    path = "${native}/" + filename
                    recovered_tools.add(path)
                    position = argv.index("--" + tool)
                    self.assertEqual(argv[position + 1 : position + 4], [path, "--" + tool + "-sha256", "${native_sha256:" + filename + "}"])
                self.assertEqual(
                    set(job["cache_witnesses"]),
                    {*G.SDK_GNU_WITNESSES, *recovered_tools, root + "LICENSE.md", *(root + prefix + name for name in profile["template_inputs"])},
                )
                extractor = "recipe/jobs/owner-sdk-shader-inputs.json"
                self.assertIn(extractor, job["needs"])
                self.assertEqual(graph.jobs[extractor]["cache_witnesses"], [G.LINUX_COMPONENT])
                data = G.Graph.artifact_pin(extractor, "data")["path"]
                self.assertEqual(argv[argv.index("--compiler-data") + 1], data)
                command = json.loads(argv[argv.index("--compiler-command") + 1])
                self.assertEqual(command[0], "${native}/libqemu-x86_64.so")
                self.assertEqual(command[-1], data + "/Tools/UnityShaderCompiler")
                self.assertIn("LD_LIBRARY_PATH=" + data + "/Tools:" + G.SDK_GNU_LIBRARIES, command)

        context = graph.build(G.digest(ROOT / "recipe/owner-commando-shader-context.json"))
        job = graph.jobs[context]
        extractor = "recipe/jobs/owner-sdk-shader-inputs.json"
        records = next(dependency for dependency in job["needs"] if dependency != extractor)
        self.assertIn(extractor, job["needs"])
        self.assertEqual(job["arguments"][job["arguments"].index("--record-pack") + 1], "${job_directory:" + records + ":receipt}")

        barrier = graph.build(G.digest(ROOT / "recipe/owner-barrier-shaders.json"))
        job = graph.jobs[barrier]
        self.assertEqual(job["arguments"][job["arguments"].index("--legacy-sdk") + 1], G.LEGACY_SHADER_SDK)
        for member in graph.job_profiles[barrier]["legacy_sdk"]:
            self.assertIn(G.LEGACY_SHADER_SDK + "/" + member, job["cache_witnesses"])

    def test_texture_jobs_bind_required_pinned_tools(self):
        graph = G.Graph(ROOT, {})
        for profile, bindings in (
            ("rgb", {"jpeg_codec", "etc_codec"}),
            ("uncompressed", {"jpeg_codec"}),
            ("alpha", {"etc_codec"}),
            ("rgba", {"etc_codec", "sdk_toolchain"}),
            ("rgb-mip", {"jpeg_codec", "etc_codec", "sdk_toolchain"}),
            ("cubemap", {"etc_codec", "sdk_toolchain"}),
        ):
            with self.subTest(profile=profile):
                name = graph.build(G.digest(ROOT / f"recipe/owner-{profile}-textures.json"))
                arguments = graph.jobs[name]["arguments"]
                for binding in ("jpeg_codec", "etc_codec", "sdk_toolchain"):
                    if binding in bindings:
                        flag = "--" + binding.replace("_", "-")
                        self.assertEqual(arguments[arguments.index(flag) + 1], "${input:" + binding + "}")
                        self.assertEqual(arguments[arguments.index(flag + "-sha256") + 1], "${input_sha256:" + binding + "}")
                    else:
                        self.assertNotIn("${input:" + binding + "}", arguments)

    def test_signed_texture_request_binds_installed_tools_and_pins_guest_inputs(self):
        spec = importlib.util.spec_from_file_location("texture_produce", ROOT / G.PREFIX / "texture_produce.py")
        texture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(texture)
        with tempfile.TemporaryDirectory() as directory:
            inputs = Path(directory).resolve()
            native, pc = inputs / "installed-native", inputs / "pc"
            native.mkdir()
            pc.mkdir()
            for installed in ("libtexture-jpeg.so", "libtexture-etc.so", "libqemu-x86_64.so", "libtexture-pixels.so", "libc++_shared.so"):
                (native / installed).write_text(installed)
            runtime = inputs / "installed-runtime"
            guest = runtime / "texture-sdk"
            pins = json.loads((ROOT / "recipe/owner-app-host-tools.json").read_text())["texture_sdk_guest"]
            guest_files = {}
            for name in pins:
                path = guest / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
                guest_files[name] = G.digest(path)

            graph = G.Graph(ROOT, {})
            graph.conversion = "recipe/jobs/owner-code.json"
            names = {key: graph.build(G.digest(ROOT / f"recipe/owner-{key}-textures.json")) for key in ("uncompressed", "alpha", "rgb-mip", "rgba")}
            jpeg, etc, sdk = (graph.jobs[names[key]] for key in ("uncompressed", "alpha", "rgb-mip"))
            self.assertIn("${native}/libtexture-jpeg.so", jpeg["arguments"])
            self.assertNotIn("--etc-codec", jpeg["arguments"])
            self.assertIn("${native}/libtexture-etc.so", etc["arguments"])
            self.assertEqual(etc["cache_witnesses"], ["${native}/libc++_shared.so"])
            self.assertNotIn("request", etc)
            self.assertNotIn("request", jpeg)
            extractor = "recipe/jobs/owner-sdk-texture-input.json"
            self.assertEqual(sdk["needs"], [extractor])
            self.assertEqual(graph.jobs[names["rgba"]]["needs"], [extractor])
            self.assertEqual(jpeg["needs"], [])
            self.assertEqual(etc["needs"], [])
            self.assertEqual(graph.jobs[extractor]["cache_witnesses"], [G.LINUX_COMPONENT])
            self.assertIn("--linux-texture", graph.jobs[extractor]["arguments"])
            acquired = inputs / "acquired/unity-linux-editor.tar.xz"
            acquired.parent.mkdir()
            acquired.write_text("owner SDK archive")
            extracted = inputs / "work/jobs/sdk-output"
            extracted.mkdir(parents=True)
            codec = extracted / "etccompress.so"
            codec.write_text("qualified owner SDK member")

            dispatch = object.__new__(J.Dispatcher)
            dispatch.repo, dispatch.inputs, dispatch.native = ROOT, inputs, native
            dispatch.installed_runtime = runtime
            dispatch.runtime = inputs / "release-runtime-view"
            dispatch.config = {"bindings": {"pc": "pc"}}
            dispatch.jobs_root = inputs / "work/jobs"
            dispatch.descriptors = graph.jobs
            dispatch.completed = {extractor: extracted}
            output, request_path = dispatch.jobs_root / "output", inputs / ".request.json"
            expanded = dispatch.expand(sdk["request"], sdk, output, request_path)
            self.assertEqual(
                {str(guest / name): pin for name, pin in pins.items()},
                {path: pin for path, pin in expanded["inputs"].items() if Path(path).is_relative_to(guest)},
            )
            expanded["inputs"].update({str(guest / name): pin for name, pin in guest_files.items()})
            J.UPDATES.write_json(request_path, expanded)
            arguments = dispatch.expand(sdk["arguments"], sdk, output, request_path)
            pin = arguments[arguments.index("--sdk-toolchain-sha256") + 1]
            self.assertEqual(arguments[arguments.index("--sdk-toolchain") + 1], str(request_path))
            self.assertEqual(pin, G.digest(request_path))
            verified = texture.sdk_inputs(request_path, pin, pc)
            self.assertEqual(verified["command"][0], str(native / "libqemu-x86_64.so"))
            self.assertEqual(verified["command"][-1], str(codec))
            self.assertEqual(verified["pixels"], str(native / "libtexture-pixels.so"))
            self.assertTrue(set(map(str, (guest / name for name in guest_files))) <= verified["inputs"].keys())

            before = dispatch.input_pins(names["rgb-mip"])
            acquired.write_text("changed SDK archive")
            after = dispatch.input_pins(names["rgb-mip"])
            self.assertNotEqual(before[G.LINUX_COMPONENT], after[G.LINUX_COMPONENT])
            guest_wrapper = guest / "texture-sdk-codec"
            guest_token = G.TEXTURE_GUEST + guest_wrapper.name
            guest_wrapper.write_text("changed packaged wrapper")
            self.assertNotEqual(before[guest_token], dispatch.input_pins(names["rgb-mip"])[guest_token])
            with self.assertRaisesRegex(ValueError, "tool input drift"):
                texture.sdk_inputs(request_path, pin, pc)
            guest_wrapper.write_text(guest_wrapper.name)
            codec.write_text("changed SDK member")
            with self.assertRaisesRegex(ValueError, "tool input drift"):
                texture.sdk_inputs(request_path, pin, pc)
            (native / "libtexture-pixels.so").write_text("changed installed provider")
            self.assertNotEqual(after["native_sha256:libtexture-pixels.so"], dispatch.input_pins(names["rgb-mip"])["native_sha256:libtexture-pixels.so"])

    def test_player_shader_suppliers_keep_serialized_and_nested_pack_contracts(self):
        graph = G.Graph(ROOT, {})
        player_path = ROOT / "recipe/owner-player-data.json"
        shader_path = ROOT / "recipe/owner-player-shaders.json"
        remap = graph.build(G.digest(ROOT / "recipe/owner-presentation-reused-records.json"))
        player = "recipe/jobs/owner-player-data.json"
        shaders = "recipe/jobs/owner-player-shaders.json"
        self.assertEqual(G.owner(json.loads(player_path.read_text())), "player_data")
        self.assertEqual(G.owner(json.loads(shader_path.read_text())), "shader_produce")
        args = graph.jobs[remap]["arguments"]
        for name in (player, shaders):
            position = args.index("${job_directory:" + name + ":receipt}")
            self.assertEqual(args[position - 1], "--serialized-producer")
        args = graph.jobs[player]["arguments"]
        position = args.index("${job_directory:" + shaders + ":shared_receipt}")
        self.assertEqual(args[position - 1], "--record-pack")
        self.assertEqual(args.count("--texture-pack"), 5)
        self.assertEqual(len(graph.jobs[shaders]["outputs"]), 369)
        self.assertEqual(len(graph.jobs[player]["outputs"]), 177)
        closure = graph.entry(remap)
        self.assertIn("recipe/owner-player-registry.json", closure["recipe_files"])
        self.assertIn("recipe/runtime-config.json", closure["recipe_files"])
        self.assertIn("recipe/owner-player-shader-manifests.json", closure["recipe_files"])
        self.assertIn("tools/unity/runtime/shaders/AndroidColorGrade.shader", closure["producer_files"])
        index = graph.compile(["recipe/owner-player-data.json", "recipe/owner-player-shaders.json"])
        self.assertEqual(len(index["entries"]), 546)
        for row in index["entries"].values():
            self.assertTrue(set(row["recipe_files"]) <= set(index["files"]) | set(graph.jobs))

    def test_complete_player_phases_declare_media_and_sign_policy(self):
        graph = G.Graph(ROOT, {}, "recipe/owner-player-phases.json")
        index = graph.compile(["recipe/owner-player-data.json", "recipe/owner-player-shaders.json"])
        player = "recipe/jobs/owner-player-data.json"
        job = graph.jobs[player]
        self.assertEqual(len(job["outputs"]), 210)
        registry = "apk/assets/bin/Data/" + graph.job_profiles[player]["registry"]["file"]
        self.assertEqual(job["artifacts"]["registry_body"], job["outputs"][registry])
        self.assertEqual(job["artifacts"]["registry_receipt"], "registry-source/result.json")
        self.assertEqual(job["artifacts"]["registry_schemas"], "registry-source/schemas.json")
        self.assertEqual(len(index["entries"]), 581)
        startup = "recipe/jobs/owner-startup-metadata.json"
        self.assertIn(startup, job["needs"])
        self.assertIn("${job:" + startup + ":receipt}", job["arguments"])
        self.assertNotIn("${input:startup_receipt}", job["arguments"])
        self.assertIn("smoke/ProjectSettings/ProjectSettings.asset", index["files"])
        self.assertIn("environment/toolchain.json", index["files"])
        for phase, row in graph.phases.items():
            self.assertIn("--" + phase + "-profile", job["arguments"])
            self.assertTrue(all("apk/assets/bin/Data/" + name in job["outputs"] for name in row["outputs"]))
            self.assertIn(row["profile"], graph.entry(player)["recipe_files"])
        self.assertIn("recipe/owner-player-phases.json", index["files"])
        self.assertIn("recipe/composition-export-copies.json", index["files"])
        self.assertIn("smoke/Assets/Bootstrap.unity", index["files"])
        self.assertIn("${job_directory:recipe/jobs/owner-player-shaders.json:receipt}", job["arguments"])
        decoder = ["--scene-environment-decoder", "${native}/libtexture-pixels.so", "${native_sha256:libtexture-pixels.so}"]
        start = job["arguments"].index(decoder[0])
        self.assertEqual(job["arguments"][start : start + len(decoder)], decoder)
        self.assertNotIn("${input_sha256:scene_environment_result}", job["arguments"])
        del graph.phases["scene"]["environment"]
        capture_arguments = graph.player_arguments({})
        self.assertIn("${input_sha256:scene_environment_result}", capture_arguments)
        self.assertNotIn(decoder[0], capture_arguments)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            target = "apk/assets/bin/Data/authored"
            selected = output / target
            selected.parent.mkdir(parents=True)
            selected.write_text("authored body")
            descriptor = dict(script=G.PREFIX + "player_data.py", outputs={target: target}, artifacts={"receipt": "result.json"})
            receipt = output / "result.json"
            receipt.write_text(json.dumps(dict(success=True, files={target: {}})))
            self.assertIn(target, J.Dispatcher.files_in(output, descriptor))
            receipt.write_text(json.dumps(dict(success=True, files={target: {}, "apk/assets/bin/Data/missing-media": {}})))
            with self.assertRaisesRegex(ValueError, "undeclared=.*missing-media"):
                J.Dispatcher.files_in(output, descriptor)
            receipt.write_text(json.dumps(dict(success=True, files={})))
            with self.assertRaisesRegex(ValueError, "missing=.*authored"):
                J.Dispatcher.files_in(output, descriptor)

    def test_native_job_binds_same_converter_and_reuses_both_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo, inputs = root / "repo", root / "inputs"
            (repo / "recipe").mkdir(parents=True)
            (inputs / "work").mkdir(parents=True)
            for name in ("sdk_install", "converter_sources"):
                (inputs / name).mkdir()
            metadata = inputs / "converter_metadata"
            metadata.write_bytes(b"independent metadata")
            (inputs / "converter_receipt").write_text(json.dumps({"metadata_sha256": G.digest(metadata)}))
            for name in ("recipe/owner-native-job-inputs.json", "recipe/owner-native-arm64.json"):
                shutil.copyfile(ROOT / name, repo / name)
            producer = repo / "tools/phone-build/owner-code/native.py"
            producer.parent.mkdir(parents=True)
            producer.write_text("""import hashlib,json,pathlib,sys
request=json.loads(pathlib.Path(sys.argv[1]).read_text())
receipt=pathlib.Path(request['converter_receipt'])
assert hashlib.sha256(receipt.read_bytes()).hexdigest()==request['converter_receipt_sha256']
metadata=pathlib.Path(request['metadata']).read_bytes()
assert hashlib.sha256(metadata).hexdigest()==json.loads(receipt.read_text())['metadata_sha256']
out=pathlib.Path(request['output']);assert out.is_relative_to(pathlib.Path(request['owner_work']))
out.mkdir();(out/'global-metadata.dat').write_bytes(metadata)
(out/'libil2cpp.so').write_bytes(b'independent native output')
(out/'result.json').write_text('{"success":true}')
""")
            graph = G.Graph(repo, {})
            index = graph.compile([], native_request="recipe/owner-native-job-inputs.json")
            self.assertEqual(len(index["entries"]), 2)
            self.assertIn("recipe/owner-native-arm64.json", index["files"])
            for name, descriptor in graph.jobs.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(descriptor))
                index["files"][name] = G.digest(path)
            release = {"entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]}}
            runtime, native = root / "runtime", root / "native"
            runtime.mkdir()
            native.mkdir()
            config = {"bindings": {name: name for name in ("sdk_install", "converter_receipt", "converter_sources", "converter_metadata")}}
            progress = []
            for attempt in range(3):
                if attempt == 2:
                    (inputs / "converter_receipt").write_text(json.dumps({"metadata_sha256": G.digest(metadata), "new_witness": True}))
                dispatcher = J.Dispatcher(
                    repo,
                    index,
                    release,
                    inputs,
                    runtime,
                    native,
                    config,
                    "a" * 64,
                    python=[sys.executable],
                    progress=lambda name, reused: progress.append(reused),
                )
                for name, dependencies in release["entries"].items():
                    destination = root / Path(name).name
                    dispatcher.produce(name, dependencies, destination)
            self.assertEqual(progress, [False, True, False])
            self.assertEqual((root / "global-metadata.dat").read_bytes(), metadata.read_bytes())
            self.assertEqual((root / "libil2cpp.so").read_bytes(), b"independent native output")

    def test_signed_install_shares_fresh_conversion_with_player_witness_and_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo, inputs, runtime, native = [root / name for name in ("repo", "inputs", "runtime", "native")]
            for path in (inputs, runtime, native):
                path.mkdir()

            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value) if isinstance(value, dict) else value)

            for name in (*G.INSTALLED_CODE_TOOLS.values(), "libhostfxr10.so"):
                write(native / name, "installed tool fixture " + name)
            write(runtime / "data-hashes.json", {"clang/21/include/header.h": "fixture v1"})
            original = inputs / "import/files/Data/source.txt"
            write(original, "owned fixture")
            input_manifest = "recipe/inputs.json"
            write(
                repo / input_manifest,
                {
                    "schema": 1,
                    "game_version": "synthetic-v1",
                    "files": [{"path": "Data/source.txt", "bytes": original.stat().st_size, "sha256": G.digest(original)}],
                },
            )
            authored = repo / "tools/unity/Fixture.cs"
            write(authored, "class Fixture {}")
            write(repo / "recipe/target.json", {"source_files": {"tools/unity/Fixture.cs": G.digest(authored)}})
            for stem in (
                "owner-managed-code",
                "owner-player-code",
                "owner-native-arm64",
                "owner-public-tools",
                "original-assemblies",
                "build-entry-inputs",
                "runtime-sources",
            ):
                write(repo / f"recipe/{stem}.json", {})
            write(repo / "recipe/assembly-transforms.json", {"tool_sources": {}})
            write(repo / "tools/phone-build/package-assemblies/profile.json", {})
            code_request, native_request, burst_request = [f"recipe/owner-{name}-request.json" for name in ("code", "native", "burst")]
            player_profile = "recipe/owner-player-fixture.json"
            write(repo / player_profile, {"project_assemblies": [], "outputs": {}, "registry": {"file": "registry.assets", "path": "registry.json"}})
            write(repo / "recipe/registry.json", {})
            player = "recipe/jobs/owner-player-fixture.json"
            witness_profile, witness = "recipe/owner-witness.json", "recipe/jobs/owner-witness.json"
            write(
                repo / witness_profile,
                dict(
                    schema="owner-bundle-managed-release-v1",
                    profiles=[player_profile],
                    request=dict(
                        registry_receipt=G.Graph.artifact_pin(player, "registry_receipt"),
                        managed_providers=dict(path="${input:retained_providers}"),
                        managed_receipt=dict(path="${input:retained_receipt}"),
                    ),
                ),
            )
            bundle_profile, bundle = "recipe/owner-bundle.json", "recipe/jobs/owner-bundle.json"
            write(
                repo / bundle_profile,
                dict(
                    schema="owner-bundle-preload-release-v1",
                    profiles=[player_profile, witness_profile],
                    request=dict(
                        policy=dict(bundle="fixture"),
                        codec=dict(path="${input:retained_codec}"),
                        managed_inputs=dict(
                            metadata=G.Graph.artifact_pin(witness, "metadata"),
                            **{"registry_" + key: G.Graph.artifact_pin(player, "registry_" + key) for key in ("body", "receipt", "schemas")},
                        ),
                    ),
                ),
            )
            write(repo / "tools/phone-build/metadata/Program.cs", "// synthetic metadata reader")
            sdk_witness, linker = inputs / "acquired/sdk/receipt.json", native / "linker"
            codec = native / "libbundlelz4.so"
            package_manifest = inputs / "acquired/package-set/input-hashes.json"
            write(package_manifest, {"packages/Fixture.cs": "fixture identity"})
            write(package_manifest.parent / "packages/Fixture.cs", "class PackageFixture {}")
            package_archive = inputs / "acquired/unity-packages/Fixture.tgz"
            write(package_archive, "compiler input v1")
            write(
                repo / G.PACKAGE_PRODUCER,
                """import json, pathlib, sys
ARCHIVES = {'Fixture.tgz': None}
if __name__ == '__main__':
    assert sys.argv[2:] == ['--prepare-inputs']
    request = json.loads(pathlib.Path(sys.argv[1]).read_text())
    output = pathlib.Path(request['output'])
    (output / 'packages').mkdir(parents=True)
    data = (pathlib.Path(request['archives']) / 'Fixture.tgz').read_bytes()
    (output / 'packages/Selected.cs').write_bytes(data)
    (output / 'result.json').write_text('{"success":true}')
""",
            )
            write(sdk_witness, "sdk fixture 1")
            write(linker, "linker fixture 1")
            write(codec, "codec fixture 1")
            write(
                repo / code_request,
                {
                    "owner_work": "${inputs}/work",
                    "output": "${output}",
                    "sdk_install": "${inputs}/acquired/sdk",
                    "source_inputs": {"original": "${input:original}", "packages": "${inputs}/acquired/package-set/packages"},
                    "target": {"profile": "${repo}/recipe/target.json", "source": "${repo}"},
                    "cache_witnesses": ["${inputs}/acquired/sdk/receipt.json", "${inputs}/acquired/package-set/input-hashes.json"],
                },
            )
            native_template = {
                "owner_work": "${inputs}/work",
                "output": "${output}",
                "sdk_install": "${inputs}/acquired/sdk",
                "android_tools": {"linker": "${native}/linker"},
                "cache_witnesses": ["${native}/linker"],
            }
            write(repo / native_request, native_template)
            producer_root = repo / "tools/phone-build/owner-code"
            write(
                producer_root / "produce.py",
                """import gzip, hashlib, json, pathlib, struct, sys
request = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert sys.argv[2:] == ['--stop-after-conversion']
work = pathlib.Path(request['owner_work'])
assert json.loads((work / 'inventory/files.json').read_text())['hash_mode'] == 'full'
source = pathlib.Path(request['source_inputs']['original']).read_bytes()
packages = pathlib.Path(request['source_inputs']['packages'])
metadata = struct.pack('<II', 0xFAB11BAF, 31) + (pathlib.Path(request['sdk_install']) / 'receipt.json').read_bytes()
metadata += (packages / 'Selected.cs').read_bytes()
frame = pathlib.Path(request['output']) / 'backend/sources/Fixture.cpp.gz'
frame.parent.mkdir(parents=True)
frame.write_bytes(gzip.compress(source, mtime=0))
converter = frame.parent.parent / 'converter'
metadata_path = converter / 'data/Metadata/global-metadata.dat'
metadata_path.parent.mkdir(parents=True)
metadata_path.write_bytes(metadata)
def pin(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
files = {'cpp/Fixture.cpp': pin(source), 'data/Metadata/global-metadata.dat': pin(metadata)}
for name in ('System.Data', 'System.Drawing', 'mscorlib'):
    relative = f'data/Resources/{name}.dll-resources.dat'
    path = converter / relative
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(source)
    files[relative] = pin(source)
(converter / 'result.json').write_text(json.dumps(dict(exit_code=0, inputs_unchanged=True, files={
    **files,
})))
managed = pathlib.Path(request['output']) / 'managed-production'
for name in ('gameplay/postprocessed/Assembly-CSharp.dll', 'packages/postprocessed/PackageFixture.dll',
             'maps/Map.cs', 'support/Support.cs', 'ordinary/RoR2.dll', 'ordinary/AK.Wwise.Unity.API.dll',
             'ordinary/AK.Wwise.Unity.MonoBehaviour.dll'):
    path = managed / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source)
(managed / 'result.json').write_text('{"success":true,"phase":"managed-produced"}')
(managed / 'providers.json').write_text(json.dumps({'Assembly-CSharp.dll': {
    'path': str(managed / 'gameplay/postprocessed/Assembly-CSharp.dll'), 'sha256': pin(source)['sha256'],
}}))
(managed / 'gameplay/inputs.json').write_text('{}')
(managed / 'packages/inputs.json').write_text(json.dumps({'package': pin((packages / 'Selected.cs').read_bytes())}))
(managed / 'gameplay/ilpp-references').symlink_to(managed / 'support', target_is_directory=True)
if 'audio_members' in request:
    assert 'decoder' not in request['source_inputs']
    tools = request['android_tools']
    assert tools['dotnet'] == request['source_inputs']['dotnet']
    assert pathlib.Path(tools['dotnet']).read_text().startswith('installed tool fixture ')
    assert pathlib.Path(tools['resource_dir']).parts[-2:] == ('clang', '21')
    stage = managed / 'staged'
    bank_root = 'Audio/GeneratedSoundBanks/Android'
    for relative in request['audio_members']:
        path = stage / bank_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source)
    (stage / 'stage-receipt.json').write_text(json.dumps({'inventory': pin(source)}))
    supplied = managed / 'supplied-sdk'
    supplied.mkdir()
    (supplied / 'libAkSoundEngine.so').write_bytes(b'local licensed library fixture')
    burst = frame.parent.parent / 'burst'
    burst.mkdir()
    (burst / 'lib_burst_generated.so').write_bytes(pathlib.Path(request['burst_tools']['runtime']).read_bytes())
    assert request['linux_tools']['adapter'].endswith('/libgnu-tool-adapter.so')
    (burst / 'burst.xml').write_text('<linker/>')
""",
            )
            write(
                repo / (G.PREFIX + "player_data.py"),
                """import argparse, hashlib, json, pathlib
parser = argparse.ArgumentParser()
for name in ('profile', 'output', 'pc', 'sdk', 'builtin-extra', 'editor-resources', 'converter', 'code-request', 'managed-production'):
    parser.add_argument('--' + name, type=pathlib.Path, required=True)
for name in ('profile-sha256', 'converter-receipt-sha256'):
    parser.add_argument('--' + name, required=True)
args = parser.parse_args()
request = json.loads(args.code_request.read_text())
packages = pathlib.Path(request['source_inputs']['packages'])
assert args.sdk.name == 'AndroidPlayer'
if 'target' in request:
    assert (packages.parent / 'input-hashes.json').is_file()
    assert (packages / 'Fixture.cs').read_text() == 'class PackageFixture {}'
    assert pathlib.Path(request['target']['source']) == args.profile.parent.parent
    assert args.sdk.parent.parent == packages.parent.parent / 'sdk'
else:
    data = (packages / 'Selected.cs').read_bytes()
    compiler = json.loads((args.managed_production / 'packages/inputs.json').read_text())
    assert hashlib.sha256(data).hexdigest() == compiler['package']['sha256']
receipt = (args.converter / 'result.json').read_bytes()
assert hashlib.sha256(receipt).hexdigest() == args.converter_receipt_sha256
providers = json.loads((args.managed_production / 'providers.json').read_text())
provider = providers['Assembly-CSharp.dll']
managed = pathlib.Path(provider['path']).read_bytes()
assert hashlib.sha256(managed).hexdigest() == provider['sha256']
files = {'registry.assets': managed, 'unity default resources': b'sdk defaults'}
for name in ('System.Data', 'System.Drawing', 'mscorlib'):
    relative = f'Resources/{name}.dll-resources.dat'
    data = (args.converter / 'data' / relative).read_bytes()
    assert hashlib.sha256(data).hexdigest() == json.loads(receipt)['files']['data/' + relative]['sha256']
    files['Managed/' + relative] = data
archive = 'apk/assets/bin/Data/'
for name, data in files.items():
    path = args.output / (archive + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
registry = args.output / 'registry-source'
registry.mkdir()
(registry / 'result.json').write_text(json.dumps({'managed_root': str(args.managed_production)}))
(registry / 'schemas.json').write_text('{}')
(args.output / 'result.json').write_text(json.dumps({'success': True, 'files': {archive + name: {} for name in files}}))
""",
            )
            write(
                repo / (G.PREFIX + "bundle_endpoints.py"),
                """import hashlib, json, pathlib, sys
_, command, request_path, output_flag, output = sys.argv
assert (command, output_flag) == ('--managed', '--output')
request = json.loads(pathlib.Path(request_path).read_text())
def read(name):
    pin = request[name]
    path = pathlib.Path(pin['path'])
    data = path.read_bytes()
    assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
    return path, json.loads(data)
_, registry = read('registry_receipt')
providers_path, providers = read('managed_providers')
receipt_path, receipt = read('managed_receipt')
assert providers_path.parent == receipt_path.parent == pathlib.Path(registry['managed_root'])
assert receipt['success'] and receipt['phase'] == 'managed-produced'
assert pathlib.Path(providers['Assembly-CSharp.dll']['path']).read_bytes() == b'owned fixture'
pathlib.Path(output).mkdir()
for name in ('result.json', 'runtime-request.json', 'providers.json', 'metadata.json', 'provider-aliases.json'):
    (pathlib.Path(output) / name).write_text('{}')
""",
            )
            write(
                repo / (G.PREFIX + "bundle_preload.py"),
                """import hashlib, json, pathlib, sys
_, command, request_path, output_flag, output = sys.argv
assert (command, output_flag) == ('--release', '--output')
request = json.loads(pathlib.Path(request_path).read_text())['request']
for pin in request['managed_inputs'].values():
    data = pathlib.Path(pin['path']).read_bytes()
    assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
pin = request['codec']
codec = pathlib.Path(pin['path'])
data = codec.read_bytes()
assert codec.name == 'libbundlelz4.so' and len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
out = pathlib.Path(output)
(out / 'emitted').mkdir(parents=True)
(out / 'emitted/fixture.bundle').write_bytes(b'synthetic bundle ' + data)
for name in ('result.json', 'catalog-profile.json'):
    (out / name).write_text('{}')
""",
            )
            shutil.copyfile(ROOT / "tools/phone-build/owner-code/native.py", producer_root / "native_contract.py")
            write(
                producer_root / "native.py",
                """import json, pathlib, sys
import native_contract as native
request = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert sys.argv[2:] == ['--from-conversion']
receipt, sources, metadata = (pathlib.Path(request[name]) for name in ('converter_receipt', 'sources', 'metadata'))
pin = request['converter_receipt_sha256']
previous = dict(jobs=[dict(arguments=0, generated='Previous.cpp')], link=[dict(object=0)])
profile = native.generated_profile(previous, native.converter_files(receipt, pin))
providers, _ = native.converter_inputs(receipt, pin, sources, metadata, profile, request['sources_compressed'])
out = pathlib.Path(request['output'])
out.mkdir()
native.expand(providers['Fixture.cpp'], out / 'source.cpp')
tools = request['android_tools']
if 'resource_dir' in tools:
    assert pathlib.Path(tools['resource_dir']).parts[-2:] == ('clang', '21')
    assert pathlib.Path(request['sdk_install']).parts[-2:] == ('acquired', 'sdk')
(out / 'libil2cpp.so').write_bytes((out / 'source.cpp').read_bytes() + pathlib.Path(tools['linker']).read_bytes())
(out / 'global-metadata.dat').write_bytes(metadata.read_bytes())
(out / 'result.json').write_text('{"success":true}')
""",
            )
            admission, plan = load("install_inputs"), load("install_flow")
            code, native_job = "recipe/jobs/owner-code-conversion.json", "recipe/jobs/owner-native-code.json"
            package_job = "recipe/jobs/owner-package-inputs.json"
            progress = []
            audio_layout = root / "private-stage-receipt.json"
            write(
                audio_layout,
                {
                    "schema": "original-game-wwise-bank-cohort-r2",
                    "output_relative_directory": "Audio/GeneratedSoundBanks/Android",
                    "outputs": [{"filename": "Init.bnk"}, {"filename": "Fixture.bnk"}],
                    "streamed_media": [{"relative_path": "Media/1.wem"}],
                    "private_inventory_receipt": "private authoring witness",
                },
            )

            def build(*, current=False):
                graph = G.Graph(repo, {})
                index = graph.compile(
                    [bundle_profile],
                    code_request=code_request,
                    native_request=native_request,
                    package_archives=True,
                    audio_stage_receipt=audio_layout if current else None,
                    burst_request=burst_request if current else None,
                )
                for name, job in graph.jobs.items():
                    write(repo / name, job)
                    index["files"][name] = G.digest(repo / name)
                graph.attach_install_plan(index, required_inputs=input_manifest, workspace_bytes=0, bindings={"original": "Data/source.txt", "pc": "."})
                if current:
                    self.assertIn("tools/wwise-android-abi/generate.py", graph.jobs[code]["source_files"])
                    self.assertIn("recipe/original-audio-owner-sources.json", graph.jobs[code]["source_files"])
                    self.assertIn("recipe/wwise-init-android.json", graph.jobs[code]["source_files"])
                    self.assertNotIn("tools/phone-build/legacy/transform_init.py.txt", graph.jobs[code]["source_files"])
                    self.assertIn("recipe/project-layout.json", graph.jobs[player]["source_files"])
                    self.assertIn("managed_package_inputs", graph.jobs[code]["artifacts"])
                    self.assertIn(package_job, graph.jobs[player]["needs"])
                    self.assertIn(code, graph.jobs[native_job]["needs"])
                    self.assertEqual(graph.jobs[native_job]["request"]["android_tools"], graph.jobs[code]["request"]["android_tools"])
                    self.assertTrue(G.INSTALLED_CODE_WITNESSES.issubset(graph.jobs[native_job]["cache_witnesses"]))
                    self.assertIn(burst_request, graph.jobs[code]["source_files"])
                    self.assertIn("recipe/owner-j850-code.json", graph.jobs[code]["source_files"])
                    self.assertNotIn("recipe/jobs/owner-burst-code.json", graph.jobs)
                    self.assertNotIn(str(audio_layout), json.dumps(graph.jobs[code]))
                    self.assertNotIn("private authoring witness", json.dumps(graph.jobs[code]))
                else:
                    self.assertIn("tools/unity/Fixture.cs", graph.jobs[code]["source_files"])
                    self.assertNotIn(package_job, graph.jobs[player]["needs"])
                self.assertEqual(graph.jobs[code]["needs"], [package_job])
                self.assertIn("recipe/runtime-sources.json", graph.jobs[player]["source_files"])
                self.assertEqual(graph.jobs[witness]["needs"], [code, player])
                release = {
                    "version": "synthetic",
                    "version_code": 2,
                    "application_id": "dev.ror2lab.synthetic",
                    "minimum_installer_version": 1,
                    "bundle_sha256": "a" * 64,
                    "entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]},
                }
                config = admission.prepare(index, repo, inputs)
                identity = J.UPDATES.input_identity(inputs, config)
                dispatcher = J.Dispatcher(
                    repo, index, release, inputs, runtime, native, config, identity, python=[sys.executable], progress=lambda *args: progress.append(args)
                )
                self.assertEqual(
                    plan.validate_plan(index["install_plan"], index, dispatcher.descriptor),
                    {package_job: "assembly", code: "assembly", player: "assembly", witness: "assembly", bundle: "assembly", native_job: "native"},
                )
                dispatcher.execute(bundle)
                dispatcher.execute(native_job)
                result = J.UPDATES.RELEASE.rebuild(
                    release,
                    installer_version=1,
                    application_id=release["application_id"],
                    installed_version=0,
                    input_sha256=identity,
                    root=inputs / "work/releases/cache",
                    produce=dispatcher.produce,
                    producer_sha256=dispatcher.output_sha256,
                )
                if current:
                    profile, _ = admission.assembly_profile(result["outputs"], inputs, release)
                    code_outputs = {
                        "apk/assets/stage-receipt.json",
                        "apk/assets/Audio/GeneratedSoundBanks/Android/Init.bnk",
                        "apk/assets/Audio/GeneratedSoundBanks/Android/Fixture.bnk",
                        "apk/assets/Audio/GeneratedSoundBanks/Android/Media/1.wem",
                        "apk/lib/arm64-v8a/libAkSoundEngine.so",
                        "apk/lib/arm64-v8a/lib_burst_generated.so",
                    }
                    self.assertEqual(set(graph.jobs[code]["outputs"]), code_outputs)
                    self.assertEqual({row["path"] for row in json.loads(profile.read_text())["targets"]} & code_outputs, code_outputs)
                    local_receipt = Path(result["outputs"]["apk/assets/stage-receipt.json"])
                    self.assertEqual(json.loads(local_receipt.read_text())["inventory"]["sha256"], G.digest(original))
                return result

            first = build()
            self.assertEqual(len(first["rebuilt"]), 8)
            self.assertEqual(Path(first["outputs"]["payload/fixture"]).read_text(), "synthetic bundle codec fixture 1")
            self.assertEqual(Path(first["outputs"]["apk/assets/bin/Data/registry.assets"]).read_bytes(), original.read_bytes())
            self.assertFalse(build()["rebuilt"])
            write(repo / native_request, dict(native_template, compile_timeout_seconds=60))
            self.assertFalse(build()["rebuilt"])
            write(linker, "linker fixture 2")
            archive_lib = "apk/lib/arm64-v8a/libil2cpp.so"
            changed = build()
            self.assertEqual(changed["rebuilt"], [archive_lib])
            self.assertEqual(Path(changed["outputs"][archive_lib]).read_bytes(), b"owned fixturelinker fixture 2")
            write(sdk_witness, "sdk fixture 2")
            self.assertEqual(build()["rebuilt"], ["apk/assets/bin/Data/Managed/Metadata/global-metadata.dat"])
            write(codec, "codec fixture 2")
            self.assertEqual(build()["rebuilt"], ["payload/fixture"])
            write(package_archive, "compiler input v2")
            self.assertEqual(build()["rebuilt"], ["apk/assets/bin/Data/Managed/Metadata/global-metadata.dat"])
            self.assertEqual(
                [cached for job, cached in progress if job == package_job],
                [False, True, True, True, True, True, False],
            )
            self.assertEqual(
                [event for event in progress if event[0] != package_job][:-5],
                [
                    (code, False),
                    (player, False),
                    (witness, False),
                    (bundle, False),
                    (native_job, False),
                    (code, True),
                    (player, True),
                    (witness, True),
                    (bundle, True),
                    (native_job, True),
                    (code, True),
                    (player, True),
                    (witness, True),
                    (bundle, True),
                    (native_job, False),
                    (code, True),
                    (player, True),
                    (witness, True),
                    (bundle, True),
                    (native_job, False),
                    (code, False),
                    (player, False),
                    (witness, False),
                    (bundle, False),
                    (native_job, False),
                    (code, True),
                    (player, True),
                    (witness, True),
                    (bundle, False),
                    (native_job, True),
                ],
            )
            self.assertEqual(progress[-5:], [(code, False), (player, False), (witness, False), (bundle, False), (native_job, False)])

            for path in G.Graph(ROOT, {}).current_code_sources(signed_audio=True):
                write(repo / path, (ROOT / path).read_text())
            request = json.loads((repo / code_request).read_text())
            with self.assertRaisesRegex(ValueError, "audio-bearing code"):
                G.Graph(repo, {}).compile([], code_request=code_request, native_request=native_request, audio_stage_receipt=audio_layout)
            del request["target"]
            request["source_inputs"]["decoder"] = "${native}/historical-audio-decoder"
            write(repo / code_request, request)
            write(repo / native_request, {name: value for name, value in native_template.items() if name not in {"android_tools", "cache_witnesses"}})
            write(repo / "recipe/owner-j850-code.json", {})
            burst_runtime = inputs / "acquired/burst/compiler"
            write(burst_runtime, "Burst fixture v1")
            write(
                repo / burst_request,
                {
                    "output": "${output}",
                    "burst_tools": {"command": ["${native}/libgnu-tool-adapter.so"], "runtime": "${inputs}/acquired/burst/compiler"},
                    "linux_tools": {"adapter": "${native}/libgnu-tool-adapter.so"},
                    "cache_witnesses": ["${inputs}/acquired/burst/compiler"],
                },
            )
            build(current=True)
            self.assertFalse(build(current=True)["rebuilt"])
            write(native / G.INSTALLED_CODE_TOOLS["dotnet"], "installed tool fixture updated")
            progress.clear()
            build(current=True)
            self.assertIn((code, False), progress)
            write(burst_runtime, "Burst fixture v2")
            self.assertEqual(build(current=True)["rebuilt"], ["apk/lib/arm64-v8a/lib_burst_generated.so"])
            write(runtime / "data-hashes.json", {"clang/21/include/header.h": "fixture v2"})
            progress.clear()
            self.assertFalse(build(current=True)["rebuilt"])
            self.assertIn((code, False), progress)
            self.assertIn((native_job, False), progress)

    def test_burst_job_dispatches_both_cohorts_and_invalidates_changed_policy(self):
        for source in (False, True):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                repo, inputs = root / "repo", root / "inputs"
                (repo / "recipe").mkdir(parents=True)
                (inputs / "work").mkdir(parents=True)
                policies = ("owner-player-code.json", "owner-native-arm64.json", "owner-j850-code.json")
                for policy in policies:
                    (repo / "recipe" / policy).write_text('{"authored_policy":1}')
                template = "recipe/burst-inputs.json"
                request = {
                    "owner_work": "${inputs}/work",
                    "sdk_install": "${input:sdk}",
                    "burst_tools": {"command": ["${input:runner}"], "runtime": "${input:compiler}"},
                    "output": "${output}",
                }
                request["source_inputs" if source else "managed"] = {"fixture": "${input:managed}"}
                (repo / template).write_text(json.dumps(request))
                producer = repo / "tools/phone-build/owner-code/produce.py"
                producer.parent.mkdir(parents=True)
                producer.write_text("""import json,pathlib,sys
assert sys.argv[2:]==['--burst-only']
request=json.loads(pathlib.Path(sys.argv[1]).read_text())
key='source_inputs' if 'source_inputs' in request else 'managed'
assert pathlib.Path(request[key]['fixture']).read_bytes()==b'authored managed input'
assert pathlib.Path(request['sdk_install']).is_file()
assert pathlib.Path(request['burst_tools']['command'][0]).is_file()
assert pathlib.Path(request['burst_tools']['runtime']).is_file()
out=pathlib.Path(request['output']);out.mkdir()
burst=out/('backend/burst' if key=='source_inputs' else 'burst');burst.mkdir(parents=True)
(burst/'lib_burst_generated.so').write_bytes(b'authored compiled Burst')
(burst/'burst.xml').write_text('<linker/>')
(out/'result.json').write_text('{"success":true}')
""")
                bindings = {name: name for name in ("sdk", "runner", "compiler", "managed")}
                for name in bindings:
                    (inputs / name).write_bytes(b"authored managed input")
                runtime, native = root / "runtime", root / "native"
                runtime.mkdir()
                native.mkdir()
                progress = []
                for changed in (False, False, True):
                    if changed:
                        (repo / "recipe" / policies[-1]).write_text('{"authored_policy":2}')
                    graph = G.Graph(repo, {})
                    index = graph.compile([], burst_request=template)
                    entry = "apk/lib/arm64-v8a/lib_burst_generated.so"
                    self.assertEqual(set(index["entries"]), {entry})
                    self.assertTrue({"recipe/" + name for name in policies} <= index["files"].keys())
                    for name, descriptor in graph.jobs.items():
                        path = repo / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(descriptor))
                        index["files"][name] = G.digest(path)
                    release = {"entries": {entry: J.UPDATES.public().entry_dependencies(index, entry)}}
                    dispatcher = J.Dispatcher(
                        repo,
                        index,
                        release,
                        inputs,
                        runtime,
                        native,
                        {"bindings": bindings},
                        "a" * 64,
                        python=[sys.executable],
                        progress=lambda name, reused: progress.append(reused),
                    )
                    dispatcher.produce(entry, release["entries"][entry], root / "library.so")
                    self.assertEqual((root / "library.so").read_bytes(), b"authored compiled Burst")
                    output = dispatcher.completed["recipe/jobs/owner-burst-code.json"]
                    xml = "backend/burst/burst.xml" if source else "burst/burst.xml"
                    self.assertEqual((output / xml).read_text(), "<linker/>")
                self.assertEqual(progress, [False, True, False])

    def test_sdk_jobs_share_private_component_and_reuse_complete_cohort(self):
        spec = importlib.util.spec_from_file_location("test_sdk_graph_owner", ROOT / G.PREFIX / "sdk_package.py")
        sdk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sdk)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo, inputs = root / "repo", root / "inputs"
            (repo / "recipe").mkdir(parents=True)
            (inputs / "work").mkdir(parents=True)
            template = "recipe/owner-sdk-android-job-inputs.json"
            shutil.copyfile(ROOT / template, repo / template)
            producer = repo / G.PREFIX / "sdk_package.py"
            producer.parent.mkdir(parents=True)
            component = inputs / "acquired/unity-android-support.pkg"
            component.parent.mkdir()
            component.write_text("owner archive fixture")
            (producer.parent / "sdk_inputs.py").write_text(
                """import argparse, json, pathlib
parser = argparse.ArgumentParser()
parser.add_argument('--component', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--android-package', action='store_true')
args = parser.parse_args()
assert args.android_package
assert args.component.read_text() == 'owner archive fixture', 'owner archive drift'
android = args.output / 'PlaybackEngines/AndroidPlayer'
android.mkdir(parents=True)
(android / 'defaults').write_text('verified fixture')
(args.output / 'result.json').write_text(json.dumps({'success': True}))
"""
            )
            producer.write_text(
                "SDK_ENTRIES = "
                + repr(sdk.SDK_ENTRIES)
                + "\n"
                + """if __name__ == '__main__':
    import json,pathlib,sys
    assert sys.argv[1]=='--request'
    request=json.loads(pathlib.Path(sys.argv[2]).read_text())
    assert len(request['jars'])==13
    sdk = pathlib.Path(request['sdk'])
    assert sdk.name == 'AndroidPlayer'
    assert (sdk / 'defaults').read_text() == 'verified fixture'
    for name in ('android_jar','aapt','java','javac'):
        assert pathlib.Path(request[name]).is_file()
    assert all(pathlib.Path(value).is_file() for value in request['jars'].values())
    qemu, loader_flag, loader, env_flag, libs, locale_flag, locale = request['aapt_prefix']
    assert pathlib.Path(qemu).is_file()
    assert (loader_flag, env_flag, locale_flag, locale) == ('-L', '-E', '-E', 'LC_ALL=C')
    assert (pathlib.Path(loader) / 'lib64/ld-linux-x86-64.so.2').is_file()
    assert libs == f'LD_LIBRARY_PATH={loader}/lib/x86_64-linux-gnu'
    out=pathlib.Path(request['output']);out.mkdir()
    for name in SDK_ENTRIES:
        path=out/'resources/apk'/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(('authored '+name).encode())
    (out/'result.json').write_text('{"success":true}')
"""
            )
            helper = G.PREFIX + "SdkAndroidCode.java"
            (repo / helper).write_text("// authored helper fixture\n")
            request = json.loads((repo / template).read_text())
            self.assertEqual(set(request["jars"]), set(sdk.TOOL_JARS))
            runtime, native = root / "runtime", root / "native"
            roots = {"${inputs}": inputs, "${installed_runtime}": runtime, "${native}": native}
            files = [*(request[name] for name in ("android_jar", "aapt", "java", "javac")), *request["jars"].values(), *request["cache_witnesses"]]
            for token in files:
                name, relative = token.split("/", 1)
                path = roots[name] / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("authored tool input")
            package = "recipe/jobs/owner-sdk-package.json"
            extraction = "recipe/jobs/owner-sdk-inputs.json"
            acquired = G.Graph(repo, {})
            acquired.compile([], sdk_request=template)
            self.assertEqual(acquired.jobs[package]["request"]["sdk"], request["sdk"])
            player_profile = "recipe/owner-player-fixture.json"
            (repo / player_profile).write_text(json.dumps({"project_assemblies": [], "outputs": ["registry.assets"]}))
            shutil.copyfile(ROOT / G.PREFIX / "player_data.py", producer.parent / "player_data.py")
            shared = G.Graph(repo, {})
            shared.compile([player_profile], sdk_request=template, sdk_component=True)
            player = shared.jobs["recipe/jobs/owner-player-fixture.json"]
            self.assertEqual(player["needs"], [extraction])
            self.assertEqual(player["arguments"][player["arguments"].index("--sdk") + 1], shared.jobs[package]["request"]["sdk"])
            graph = G.Graph(repo, {})
            index = graph.compile([], sdk_request=template, sdk_component=True)
            self.assertEqual(set(index["entries"]), {"apk/" + name for name in sdk.SDK_ENTRIES})
            self.assertIn(helper, index["files"])
            self.assertIn(template, index["files"])
            self.assertNotIn(str(component), index["files"])
            self.assertEqual(graph.jobs[extraction]["source_files"], [extraction, G.PREFIX + "sdk_inputs.py"])
            for name, descriptor in graph.jobs.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(descriptor))
                index["files"][name] = G.digest(path)
            release = {"entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]}}
            progress = []

            def dispatch():
                return J.Dispatcher(
                    repo,
                    index,
                    release,
                    inputs,
                    runtime,
                    native,
                    {"bindings": {}},
                    "a" * 64,
                    python=[sys.executable],
                    progress=lambda name, reused: progress.append((name, reused)),
                )

            for _ in range(2):
                dispatcher = dispatch()
                for name, dependencies in release["entries"].items():
                    destination = root / "results" / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    dispatcher.produce(name, dependencies, destination)
                    self.assertEqual(destination.read_bytes(), ("authored " + name.removeprefix("apk/")).encode())
            self.assertEqual(progress, [(extraction, False), (package, False), (extraction, True), (package, True)])
            (inputs / request["aapt"].removeprefix("${inputs}/")).write_text("updated tool input")
            dispatch().execute(package)
            self.assertEqual(progress[-2:], [(extraction, True), (package, False)])
            (native / "libqemu-x86_64.so").write_text("updated QEMU input")
            dispatch().execute(package)
            self.assertEqual(progress[-2:], [(extraction, True), (package, False)])
            component.write_text("changed archive fixture")
            with self.assertRaises(subprocess.CalledProcessError):
                dispatch().execute(package)
            component.write_text("owner archive fixture")
            (repo / helper).write_text("// changed helper\n")
            with self.assertRaisesRegex(ValueError, "verified public source changed"):
                dispatch().execute(package)

    def test_startup_source_job_executes_and_reuses_through_dispatcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo, inputs = root / "repo", root / "inputs"
            (repo / "recipe").mkdir(parents=True)
            for name in (G.PREFIX + "startup_metadata.py", "smoke/ProjectSettings/ProjectSettings.asset", "environment/toolchain.json"):
                target = repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            inputs.mkdir()
            (inputs / "inventory.json").write_text('{"authored_fixture": true}')
            graph = G.Graph(repo, {})
            startup = graph.startup()
            index = graph.compile([])
            job = repo / startup
            job.parent.mkdir(parents=True)
            job.write_text(json.dumps(graph.jobs[startup]))
            index["files"][startup] = G.digest(job)
            release = {"entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]}}
            runtime, native = root / "runtime", root / "native"
            runtime.mkdir()
            native.mkdir()
            config = {"bindings": {"inventory": "inventory.json"}}
            progress = []
            wait = subprocess.Popen.wait
            heartbeats = iter(range(3))

            def wait_with_heartbeats(process, timeout=None):
                if timeout is not None and next(heartbeats, None) is not None:
                    raise subprocess.TimeoutExpired(process.args, timeout)
                return wait(process)

            # Exercise the elapsed-time callbacks without depending on host load.
            with mock.patch.object(subprocess.Popen, "wait", wait_with_heartbeats):
                for pass_number in range(2):
                    dispatcher = J.Dispatcher(
                        repo,
                        index,
                        release,
                        inputs,
                        runtime,
                        native,
                        config,
                        "a" * 64,
                        python=[sys.executable],
                        progress=lambda name, reused: progress.append((name, reused)),
                    )
                    for name, dependency in release["entries"].items():
                        destination = root / (str(pass_number) + "-" + Path(name).name)
                        dispatcher.produce(name, dependency, destination)
                        self.assertTrue(destination.is_file())
            self.assertEqual(progress, [(startup, None)] * 3 + [(startup, False), (startup, True)])
            self.assertEqual((root / "0-boot.config").read_bytes(), (root / "1-boot.config").read_bytes())
            self.assertEqual((root / "0-unity_app_guid").read_bytes(), (root / "1-unity_app_guid").read_bytes())

    def test_compressed_hierarchy_suppliers_are_signed_without_expansion(self):
        graph = G.Graph(ROOT, {})
        for path in sorted((ROOT / "recipe").glob("owner-*.jsonl.gz")):
            job = graph.build(G.digest(path))
            self.assertEqual(graph.jobs[job]["script"], G.PREFIX + "record_produce.py")
            self.assertIn(path.relative_to(ROOT).as_posix(), graph.entry(job)["recipe_files"])
            self.assertEqual(graph.jobs[job]["needs"], [])
            self.assertEqual(set(graph.job_profiles[job]), {"input_id"})

    def test_generated_supplier_graph_executes_through_dispatcher_and_reuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, inputs = root / "repo", root / "inputs"
            (repo / "recipe").mkdir(parents=True)
            (repo / G.PREFIX).mkdir(parents=True)
            for name in ("pc", "sdk"):
                (inputs / name).mkdir(parents=True)
            (inputs / "codec").write_text("authored tool")
            runtime, native = root / "runtime", root / "native"
            runtime.mkdir()
            native.mkdir()
            supplier = repo / "recipe/owner-supplier.jsonl.gz"
            with gzip.open(supplier, "wt") as stream:
                stream.write(json.dumps({"input_id": "a" * 64}) + "\n")
                stream.write(json.dumps({"path": "original.bundle", "sha256": "b" * 64, "members": [{"objects": []}]}) + "\n")
            final = repo / "recipe/owner-final.json"
            final.write_text(json.dumps({"sources": [], "bundle": {"name": "authored"}, "objects": [{"record": G.digest(supplier)}]}))
            # Use the real manifest owner and its authored native fixture.
            for folder in ("tools/phone-build", "scripts/lab"):
                for source in (ROOT / folder).rglob("*.py"):
                    target = repo / source.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
            spec = importlib.util.spec_from_file_location("graph_manifest_fixture", ROOT / G.PREFIX / "bundle_manifest.py")
            manifest = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manifest)
            bundle = manifest.F.make_bundle()
            # Each owner checks receipt substitution before producing its output.
            script = """import argparse,gzip,hashlib,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--profile');p.add_argument('--profile-sha256');p.add_argument('--record-pack',nargs=2,action='append',default=[])
a,_=p.parse_known_args()
assert hashlib.sha256(pathlib.Path(a.profile).read_bytes()).hexdigest()==a.profile_sha256
if a.profile.endswith('.jsonl.gz'):
 with gzip.open(a.profile,'rt') as stream: assert json.loads(stream.readline())=={'input_id':'a'*64}
for path,pin in a.record_pack:
 assert hashlib.sha256((pathlib.Path(path)/'result.json').read_bytes()).hexdigest()==pin
out=pathlib.Path(a.output);out.mkdir()
for name in ('objects.bin','index.jsonl','types.json','layout.json','result.json'):(out/name).write_text('authored')
(out/'payload').mkdir();(out/'payload/authored').write_text('source output')
"""
            for producer in ("record_produce", "object_produce"):
                (repo / G.PREFIX / (producer + ".py")).write_text(script)
            script += "\n(out/'payload/authored').write_bytes(" + repr(bundle) + ")\n"
            (repo / G.PREFIX / "object_produce.py").write_text(script)
            graph = G.Graph(repo, {})
            index = graph.compile(["recipe/owner-final.json"], bundle_manifest=True)
            for name, job in graph.jobs.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(job))
                index["files"][name] = G.digest(path)
            release = {"entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]}}
            J.UPDATES.public().validate_bundle_index(index, release)
            progress = []
            dispatcher = J.Dispatcher(
                repo,
                index,
                release,
                inputs,
                runtime,
                native,
                {"bindings": {"pc": "pc", "sdk": "sdk", "codec": "codec"}},
                "a" * 64,
                python=[sys.executable],
                progress=lambda name, reused: progress.append(reused),
            )
            destination = root / "final"
            dispatcher.produce("payload/authored", release["entries"]["payload/authored"], destination)
            self.assertEqual(destination.read_bytes(), bundle)
            self.assertEqual(progress, [False, False])
            manifest_target = "payload/generated-android-data"
            dispatcher.produce(manifest_target, release["entries"][manifest_target], root / "manifest")
            import UnityPy

            objects = list(UnityPy.load(str(root / "manifest")).objects)
            native_manifest = next(obj.read_typetree() for obj in objects if obj.type.value == 290)
            self.assertEqual(dict(native_manifest["AssetBundleNames"]), {0: "authored"})
            self.assertEqual(progress[-1], False)
            second = J.Dispatcher(
                repo,
                index,
                release,
                inputs,
                runtime,
                native,
                dispatcher.config,
                "a" * 64,
                python=[sys.executable],
                progress=lambda name, reused: progress.append(reused),
            )
            second.produce("payload/authored", release["entries"]["payload/authored"], destination)
            self.assertEqual(progress[-2:], [True, True])
            second.produce(manifest_target, release["entries"][manifest_target], root / "manifest-reused")
            self.assertEqual(progress[-1], True)
            self.assertEqual((root / "manifest").read_bytes(), (root / "manifest-reused").read_bytes())
            request = dispatcher.descriptor("recipe/jobs/owner-bundle-manifest.json")
            row = request["request"]["bundles"][0]
            output = dispatcher.jobs_root / "attempt/output"
            expanded = dispatcher.expand(row, request, output, root / "request.json")
            self.assertIs(type(expanded["bytes"]), int)
            self.assertEqual(expanded["bytes"], len(bundle))
            with self.assertRaisesRegex(ValueError, "declared job dependency"):
                dispatcher.expand(row, {"needs": []}, output, root / "request.json")
            final.write_text(json.dumps({"sources": [], "bundle": {"name": "authored"}, "objects": [{"record": "f" * 64}]}))
            with self.assertRaisesRegex(ValueError, "missing source supplier"):
                G.Graph(repo, {}).compile(["recipe/owner-final.json"])


if __name__ == "__main__":
    unittest.main()
