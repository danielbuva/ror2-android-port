"""Fresh preparation from authored Windows inputs and real native producers."""

import importlib
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"))
P = importlib.import_module("bundle_preload")


class BundlePreparationTests(unittest.TestCase):
    def test_original_identities_cover_texture_avatar_and_shared_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            target = dict(bundle="pack", member="CAB-pack", path_id=7)
            profile = dict(bundles=[dict(path="original.bundle", sha256="a" * 64, members=[dict(name="CAB-source")])])
            member = profile["bundles"][0]["members"][0]
            member["textures"] = [dict(path_id=11, outputs=[target, dict(target, path_id=8)])]
            member["avatars"] = [dict(path_id=12, outputs=[target])]
            path.write_text(json.dumps(profile))
            source_files = {}
            actual = P.module("bundle_prepare").original_identities(P, path, source_files)
            self.assertEqual(actual[("pack", "CAB-pack", 7)], {("original.bundle", "CAB-source", 11), ("original.bundle", "CAB-source", 12)})
            self.assertEqual(actual[("pack", "CAB-pack", 8)], {("original.bundle", "CAB-source", 11)})
            self.assertEqual(source_files, {"original.bundle": "a" * 64})

    def test_signed_dispatch_prepares_fresh_suppliers_catalog_and_runtime_donor(self):
        root_repo = Path(__file__).resolve().parents[1]
        G = P.O.module("_prepare_release_graph", root_repo / "tools/phone-build/owner-apk/release_graph.py")
        J = P.O.module("_prepare_release_jobs", root_repo / "tools/phone-build/owner-apk/release_jobs.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _, request, policy, pin = self.fixture(root)
            repo, inputs = root / "repo", root / "inputs"
            (repo / "recipe").mkdir(parents=True)
            inputs.mkdir()
            (root / "original").rename(inputs / "pc")
            (inputs / "sdk").mkdir()
            (root / "codec").rename(inputs / "codec")
            for cohort in ("tools/phone-build", "scripts/lab"):
                for source in (root_repo / cohort).rglob("*.py"):
                    destination = repo / source.relative_to(root_repo)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
            profiles = []
            for supplier in request["suppliers"]:
                name = supplier["name"]
                source = repo / ("recipe/owner-" + name + ".json")
                shutil.copyfile(root / (name + ".json"), source)
                profiles.append(source.relative_to(repo).as_posix())
                job = "recipe/jobs/owner-" + name + ".json"
                supplier["profile"] = dict(pin(source), path="${repo}/" + profiles[-1])
                for artifact in ("receipt", "objects", "index", "types"):
                    supplier[artifact] = G.Graph.artifact_pin(job, artifact)
                # No retained pack is available to the dispatcher.
                shutil.rmtree(root / ("pack-" + name))
            selected = [
                dict(
                    binding,
                    record=G.digest(repo / ("recipe/owner-" + binding["supplier"] + ".json")),
                    source=[binding["supplier"] + ".bundle", "CAB-" + binding["supplier"], binding["record_source"][2]],
                )
                for binding in policy["bindings"]
            ]
            source_profiles = [row["record"] for row in selected]
            for row in selected:
                row["record"] = "f" * 64  # Retained private selection, not a public producer.
                row["record_source"] = row["destination"]
            mapped = G.Graph(repo, {}).bundle_bindings(iter(selected), policy["bundle"], policy["member"], source_profiles=source_profiles)
            self.assertEqual(mapped["unresolved"], [])
            self.assertEqual([row["selection"]["record_source"] for row in mapped["bindings"]], [row["destination"] for row in selected])
            self.assertEqual(mapped["profiles"], sorted(profiles))
            policy["bindings"] = mapped["bindings"]
            request["suppliers"] = mapped["suppliers"]
            request.update(game_root="${input:pc}", codec=dict(path="${input:codec}", bytes=(inputs / "codec").stat().st_size, sha256="${input_sha256:codec}"))
            donor_identity = repo / "recipe/donor-identity.json"
            shutil.copyfile(root / "donor.json", donor_identity)
            donor_policy = dict(
                bundle="canonical",
                member="CAB-donor",
                bindings=[dict(policy["bindings"][-2], record_source=["pack-a", "packed-a", 40], destination=["canonical", "CAB-donor", 900])],
                asset_groups=[dict(guid="34" * 16, path="Assets/Canonical.asset", roots=[900])],
                assets=[dict(name="assets/canonical.asset", type="PhysicMaterial")],
            )
            donor_supplier = next(row for row in request["suppliers"] if row["name"] == donor_policy["bindings"][0]["supplier"])
            donor_request = dict(request, policy=donor_policy, suppliers=[donor_supplier], staged=[])
            donor_profile = repo / "recipe/owner-donor.json"
            donor_profile.write_text(json.dumps(dict(schema="owner-bundle-preload-release-v1", profiles=profiles[:1], request=donor_request)))
            donor_job = "recipe/jobs/owner-donor.json"
            donor_pin = G.Graph.artifact_pin(donor_job, "catalog_bundle")
            policy["canonical"].update(profile=dict(pin(donor_identity), path="${repo}/recipe/donor-identity.json"), bundle=donor_pin)
            policy["field_routes"][0]["target"] = ["content", "CAB-content", 300]
            policy["asset_groups"][0]["preload_roots"] = [["content", "CAB-content", 300]]
            request.update(policy=policy, staged=[dict(bundle="canonical", file=donor_pin)])
            wrapper = repo / "recipe/owner-content.json"
            wrapper.write_text(json.dumps(dict(schema="owner-bundle-preload-release-v1", profiles=[*profiles, "recipe/owner-donor.json"], request=request)))
            identity = dict(input_id="authored", attempt="fresh")
            bootstrap = repo / "recipe/bootstrap.json"
            bootstrap.write_text(json.dumps(identity))
            (repo / "recipe/registry-policy.json").write_text("{}")
            player = repo / "recipe/owner-fixture-player.json"
            player.write_text(
                json.dumps(
                    dict(
                        project_assemblies=[],
                        outputs={},
                        registry=dict(file="registry.assets", path="registry-policy.json"),
                        text_assets=dict(
                            files=[
                                dict(
                                    name="WholeCatalogBootstrap", recipe=dict(path="bootstrap.json", bytes=bootstrap.stat().st_size, sha256=G.digest(bootstrap))
                                )
                            ]
                        ),
                    )
                )
            )
            # Only the empty runtime registry is synthetic. All content producers,
            # preparation, emission, canonical repack, catalog and manifest run.
            fixture_script = repo / "tools/phone-build/accepted-output/startup_metadata.py"
            fixture_script.write_text(
                "import pathlib,sys\nout=pathlib.Path(sys.argv[1]);out.mkdir()\n"
                + "(out/'registry.assets').write_bytes(bytes.fromhex("
                + repr(self.serialized([]).hex())
                + "))\n"
                + "(out/'result.json').write_text('{\"success\":true}')\n"
            )
            metadata = inputs / "metadata.json"
            metadata.write_text(
                json.dumps(
                    dict(**identity, keys=[], locations=[dict(id=1, path="assets/root.asset", type="UnityEngine.PhysicMaterial, UnityEngine.PhysicsModule")])
                )
            )
            catalog_request = repo / "recipe/catalog-request.json"
            catalog_request.write_text(
                json.dumps(
                    dict(
                        schema="owner-catalog-inputs-v1", **identity, metadata=dict(pin(metadata), path="${input:metadata}", sha256="${input_sha256:metadata}")
                    )
                )
            )
            runtime, native = root / "runtime", root / "native"
            runtime.mkdir()
            native.mkdir()
            config = dict(bindings={key: key for key in ("pc", "sdk", "codec", "metadata")})
            config["bindings"]["metadata"] = "metadata.json"

            def compile_graph():
                graph = G.Graph(repo, {})
                player_job = "recipe/jobs/owner-fixture-player.json"
                graph.jobs[player_job] = dict(
                    schema=1,
                    script=G.PREFIX + "startup_metadata.py",
                    arguments=["${output}"],
                    needs=[],
                    outputs={"apk/assets/bin/Data/registry.assets": "registry.assets"},
                    artifacts={"receipt": "result.json"},
                )
                graph.profile_files[player_job] = player.relative_to(repo).as_posix()
                graph.job_profiles[player_job] = json.loads(player.read_text())
                index = graph.compile(
                    [wrapper.relative_to(repo).as_posix(), player.relative_to(repo).as_posix()],
                    bundle_manifest=True,
                    catalog_request=catalog_request.relative_to(repo).as_posix(),
                )
                for name, descriptor in graph.jobs.items():
                    path = repo / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(descriptor))
                    index["files"][name] = G.digest(path)
                release = {"entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]}}
                return graph, index, release

            def dispatch(index, release):
                progress = []
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
                for name, dependencies in release["entries"].items():
                    dispatcher.produce(name, dependencies, root / Path(name).name)
                return dispatcher, [(name, reused) for name, reused in progress if reused is not None]

            graph, index, release = compile_graph()
            content_job = "recipe/jobs/owner-content.json"
            self.assertIn("recipe/donor-identity.json", index["entries"]["payload/content"]["recipe_files"])
            self.assertIn("payload/canonical", release["entries"])
            self.assertEqual(graph.jobs[content_job]["outputs"]["payload/content"], "canonical/content.bundle")
            cold, progress = dispatch(index, release)
            self.assertTrue(all(reused is False for _, reused in progress))
            emitted = json.loads((cold.completed[content_job] / "result.json").read_bytes())
            self.assertEqual(emitted["canonical"]["canonical_roots"], 1)
            self.assertEqual(emitted["preparation"]["records"], 4)
            actual = json.loads((root / "whole-catalog.json").read_bytes())
            self.assertEqual(actual["bundles"]["content"]["sha256"], emitted["sha256"])
            self.assertNotEqual(actual["bundles"]["content"]["sha256"], actual["bundles"]["canonical"]["sha256"])
            manifest = graph.jobs["recipe/jobs/owner-bundle-manifest.json"]["request"]
            self.assertEqual({row["name"] for row in manifest["bundles"]}, {"content", "canonical"})
            _, progress = dispatch(index, release)
            self.assertTrue(all(reused is True for _, reused in progress))
            changed = json.loads(wrapper.read_text())
            changed["request"]["policy"]["asset_groups"][0]["preload_roots"] = []
            wrapper.write_text(json.dumps(changed))
            _, index, release = compile_graph()
            _, progress = dispatch(index, release)
            states = dict(progress)
            for job in ("recipe/jobs/owner-a.json", "recipe/jobs/owner-b.json", donor_job):
                self.assertTrue(states[job])
            for job in (content_job, "recipe/jobs/owner-catalog-complete.json", "recipe/jobs/owner-bundle-manifest.json"):
                self.assertFalse(states[job])

    def serialized(self, records, *, externals=(), platform=13, trees=True):
        layout, packed = P.O.make_layout(dict(externals=externals), records)
        layout.update(platform=platform, trees=trees)
        stream = io.BytesIO()
        P.O.W.write_serialized(stream, layout, lambda row: io.BytesIO(packed[row["path_id"]]))
        return stream.getvalue()

    def fixture(self, root):
        M, W = P.module("bundle_manifest"), P.module("unity_write")
        original = root / "original"
        original.mkdir()
        nodes = [dict(type="PhysicMaterial", name="Base", size=-1, level=0, meta=0, flags=0, version=1)]
        for field in ("next", "external", "duplicate"):
            for kind, name, size, level in (("PPtr<Object>", field, 12, 1), ("int", "m_FileID", 4, 2), ("SInt64", "m_PathID", 8, 2)):
                nodes.append(dict(type=kind, name=name, size=size, level=level, meta=0, flags=0, version=1))
        nodes.append(dict(type="int", name="tail", size=4, level=1, meta=0, flags=0, version=1))
        typ = dict(class_id=134, stripped=0, script_type=-1, hash=b"a" * 16, tree=M.S._tree(nodes), dependencies=[])

        def body(a=(0, 0), b=(0, 0), c=(0, 0)):
            return b"".join(struct.pack("<iq", *pointer) for pointer in (a, b, c)) + struct.pack("<i", 73)

        def bundle(path, member, bodies, externals, platform):
            layout, packed = P.O.make_layout(dict(externals=externals), [dict(path_id=pid, type=typ, body=raw) for pid, raw in bodies.items()])
            layout["platform"] = platform
            stream = io.BytesIO()
            W.write_serialized(stream, layout, lambda row: io.BytesIO(packed[row["path_id"]]))
            raw = stream.getvalue()
            with path.open("wb") as handle:
                W.write_bundle(handle, [(member, 4, len(raw), lambda: io.BytesIO(raw))], lambda block, method: block, flags=0x40)

        def pin(path):
            return dict(path=str(path), bytes=path.stat().st_size, sha256=P.O.B.sha(path))

        bundles = {"a": {10: body((1, 10), (1, 10), (0, 40)), 30: body(), 40: body()}, "b": {10: body((1, 10))}}
        suppliers = []
        bindings = []
        for name, bodies in bundles.items():
            path = original / (name + ".bundle")
            member = "CAB-" + name
            bundle(path, member, bodies, ["CAB-b" if name == "a" else "CAB-a"], 19)
            objects = []
            for pid, raw in bodies.items():
                target = dict(bundle="pack-" + name, member="packed-" + name, path_id=pid, bytes=len(raw), sha256=P.hashlib.sha256(raw).hexdigest())
                objects.append(dict(path_id=pid, class_id=134, sha256=target["sha256"], outputs=[target]))
                destination = {("a", 10): 100, ("b", 10): 200, ("a", 30): 300, ("a", 40): 400}[name, pid]
                bindings.append(
                    dict(
                        supplier=name,
                        record_source=[target[key] for key in ("bundle", "member", "path_id")],
                        destination=["content", "CAB-content", destination],
                    )
                )
            profile = root / (name + ".json")
            profile.write_text(
                json.dumps(dict(input_id=P.O.M.INPUT_ID, bundles=[dict(path=path.name, sha256=P.O.B.sha(path), members=[dict(name=member, objects=objects)])]))
            )
            pack = root / ("pack-" + name)
            P.A.produce(profile, P.O.B.sha(profile), original, pack)
            suppliers.append(
                dict(
                    name=name,
                    provider="supplier-" + name,
                    profile=pin(profile),
                    **{
                        key: pin(pack / filename)
                        for key, filename in (("receipt", "result.json"), ("index", "index.jsonl"), ("objects", "objects.bin"), ("types", "types.json"))
                    },
                )
            )
        external, donor = root / "external.bundle", root / "donor.bundle"
        bundle(external, "CAB-external", {10: body()}, [], 13)
        bundle(donor, "CAB-donor", {900: body()}, [], 13)
        donor_profile = root / "donor.json"
        donor_profile.write_text(
            json.dumps(
                dict(
                    bundle=dict(name="canonical", member="CAB-donor"),
                    sources=[dict(path="a.bundle", member="CAB-a")],
                    objects=[dict(path_id=900, source=[0, 40])],
                )
            )
        )
        codec = root / "codec"
        codec.write_text(
            "#!" + sys.executable + "\nimport sys, struct\n"
            "while header := sys.stdin.buffer.read(8):\n"
            " size, method = struct.unpack('<II', header)\n"
            " data = sys.stdin.buffer.read(size)\n"
            " extra = size - 15\n"
            " suffix = bytes([255]) * (extra // 255) + bytes([extra % 255]) if size >= 15 else b''\n"
            " encoded = bytes([min(size, 15) << 4]) + suffix + data\n"
            " sys.stdout.buffer.write(struct.pack('<I', len(encoded)) + encoded)\n"
            " sys.stdout.buffer.flush()\n"
        )
        codec.chmod(0o755)
        policy = dict(
            bundle="content",
            member="CAB-content",
            bindings=bindings,
            asset_groups=[
                dict(
                    guid="12" * 16,
                    path="Assets/Root.asset",
                    roots=[100, 200],
                    preload_roots=[["content", "CAB-content", 300], ["external", "CAB-external", 10]],
                )
            ],
            assets=[dict(name="assets/root.asset", type="PhysicMaterial")],
            field_routes=[dict(owner=["content", "CAB-content", 100], field=["external"], pointer=[1, 10], target=["external", "CAB-external", 10])],
            canonical=dict(
                profile=pin(donor_profile),
                bundle=pin(donor),
                pairs=[dict(duplicate=["content", "CAB-content", 400], canonical=["canonical", "CAB-donor", 900])],
            ),
        )
        policy_path = root / "policy.json"
        policy_path.write_text(json.dumps(policy))
        request = dict(
            schema="owner-bundle-preload-prepare-v1",
            policy=pin(policy_path),
            suppliers=suppliers,
            staged=[dict(bundle="external", file=pin(external)), dict(bundle="canonical", file=pin(donor))],
            managed_inputs={},
            game_root=str(original),
            codec=pin(codec),
        )
        inputs = root / "prepare.json"
        inputs.write_text(json.dumps(request))
        return inputs, request, policy, pin

    def test_fresh_preparation_emission_repack_and_warm_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, _, _, _ = self.fixture(root)
            result = P.prepare_request(inputs, root / "prepared")
            self.assertEqual((result["records"], result["endpoints"]), (4, 1))
            rows = list(P.json_rows(root / "prepared/selected-records.jsonl"))
            self.assertEqual([row["destination"][2] for row in rows], [100, 200, 300, 400])
            self.assertEqual([row["source"] for row in rows[:2]], [["a.bundle", "CAB-a", 10], ["b.bundle", "CAB-b", 10]])
            self.assertEqual([row["record_source"] for row in rows[:2]], [["pack-a", "packed-a", 10], ["pack-b", "packed-b", 10]])
            routes = list(P.json_rows(root / "prepared/routes.jsonl"))
            self.assertEqual(routes[0]["edges"][2], dict(field=["next"], pointer=[0, 200], target=["content", "CAB-content", 200]))
            first = P.produce_request(result["request"]["path"], root / "first", cache_directory=root / "cache")
            second = P.produce_request(result["request"]["path"], root / "second", cache_directory=root / "cache")
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertTrue(second["emission"]["cache_reused"])
            self.assertTrue(second["canonical"]["cache_reused"])
            W = P.module("unity_write")
            with W.B.Bundle(Path(second["bundle"])).member("CAB-content") as stream:
                layout = W.read_serialized(stream)
                actual = {}
                for row in layout["objects"]:
                    stream.seek(layout["data_offset"] + row["offset"])
                    raw = W.B.exact(stream, row["bytes"])
                    typ = layout["types"][row["type_id"]]
                    if typ["class_id"] == 142:
                        containers, _ = P.module("catalog_complete").containers(raw)
                    else:
                        actual[row["path_id"]] = P.pointers(raw, typ, {})
                        self.assertEqual(raw[-4:], struct.pack("<i", 73))
            self.assertEqual(actual[100]["next",], (0, 200))
            self.assertEqual(actual[200]["next",], (0, 100))
            externals = json.loads((root / "prepared/required.json").read_bytes())["externals"]
            self.assertEqual(actual[100]["duplicate",], (externals.index("CAB-donor") + 1, 900))
            self.assertEqual([entry[1] for entry in containers], [(0, 100), (0, 200)])
            self.assertIn((0, 300), containers[0][2])
            self.assertIn((externals.index("CAB-external") + 1, 10), containers[0][2])
            profile = json.loads(Path(second["catalog_profile"]["path"]).read_bytes())
            self.assertEqual(profile["bundle"]["asset_groups"][0]["roots"], [100, 200])
            self.assertEqual(second["catalog_bundle"]["sha256"], second["sha256"])

    def test_fresh_preparation_refuses_observed_contract_failures(self):
        for failure in ("body", "types", "ambiguous", "override"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                inputs, request, policy, pin = self.fixture(root)
                first = P.prepare_request(inputs, root / "baseline-prepared")
                P.produce_request(first["request"]["path"], root / "baseline", cache_directory=root / "cache")
                if failure == "body":
                    path = root / "pack-a/objects.bin"
                    path.write_bytes(b"corrupt")
                    request["suppliers"][0]["objects"] = pin(path)
                elif failure == "types":
                    path = root / "pack-a/types.json"
                    path.write_text("[]")
                    request["suppliers"][0]["types"] = pin(path)
                elif failure == "ambiguous":
                    policy["bindings"].append(dict(policy["bindings"][0], destination=["content", "CAB-content", 999]))
                else:
                    policy["field_routes"][0]["pointer"] = [1, 11]
                (root / "policy.json").write_text(json.dumps(policy))
                request["policy"] = pin(root / "policy.json")
                inputs.write_text(json.dumps(request))
                with self.assertRaises((ValueError, EOFError)):
                    P.prepare_request(inputs, root / "prepared")

    def test_fresh_native_output_completes_actual_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, request, policy, pin = self.fixture(root)
            # This catalog has one bundle; route all endpoints into its closure.
            policy.pop("canonical")
            policy["field_routes"][0]["target"] = ["content", "CAB-content", 300]
            policy["asset_groups"][0]["preload_roots"] = [["content", "CAB-content", 300]]
            request["staged"] = []
            (root / "policy.json").write_text(json.dumps(policy))
            request["policy"] = pin(root / "policy.json")
            inputs.write_text(json.dumps(request))
            prepared = P.prepare_request(inputs, root / "prepared")
            emitted = P.produce_request(prepared["request"]["path"], root / "emitted")
            registry = root / "registry.assets"
            registry.write_bytes(self.serialized([]))
            metadata = root / "metadata.json"
            metadata.write_text(
                json.dumps(
                    dict(
                        input_id="authored",
                        attempt="fresh",
                        keys=[],
                        locations=[dict(id=1, path="assets/root.asset", type="UnityEngine.PhysicMaterial, UnityEngine.PhysicsModule")],
                    )
                )
            )
            catalog = root / "catalog-inputs.json"
            catalog.write_text(
                json.dumps(
                    dict(
                        schema="owner-catalog-inputs-v1",
                        input_id="authored",
                        attempt="fresh",
                        metadata=pin(metadata),
                        profiles=[emitted["catalog_profile"]],
                        bundles={"content": emitted["catalog_bundle"]},
                        registry=pin(registry),
                    )
                )
            )
            result = P.module("catalog_complete").produce(catalog, root / "catalog")
            self.assertEqual(result["checks"], dict(locations=1, container_paths=1, runtime_scripts=0))
            actual = json.loads((root / "catalog/whole-catalog.json").read_bytes())
            self.assertEqual(actual["bundles"]["content"]["sha256"], emitted["sha256"])

    def test_fresh_sdk_full_witness_survives_moved_file_and_warm_emission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, request, policy, pin = self.fixture(root)
            original = root / "external.bundle"
            with P.O.B.Bundle(original).member("CAB-external") as stream:
                metadata = P.O.W.read_serialized(stream)
                row = metadata["objects"][0]
                stream.seek(metadata["data_offset"] + row["offset"])
                body = P.O.B.exact(stream, row["bytes"])
                typ = metadata["types"][row["type_id"]]
            sdk = root / "phone-sdk"
            sdk.write_bytes(self.serialized([dict(path_id=10, body=body, type=typ)], trees=False))
            destination = ["sdk", "Resources/unity_builtin_extra", 10]
            witness = dict(
                destination=destination,
                bytes=len(body),
                sha256=P.hashlib.sha256(body).hexdigest(),
                provider="original-sdk-path",
                provider_kind="serialized_file",
                provider_file_sha256=pin(sdk)["sha256"],
                class_id=typ["class_id"],
                native_type_hash=typ["hash"].hex(),
                schema=P.hashlib.sha256(typ["tree"]).hexdigest(),
                full_type=P.full_type_key(typ),
                type_layout=P.O.json_layout(typ),
                edges=[[0, 0]],
            )
            full = root / "sdk-full.json"
            full.write_text(json.dumps([witness]))
            request["staged"][0] = dict(bundle="sdk", member=destination[1], file=pin(sdk), full=pin(full))
            policy["field_routes"][0]["target"] = destination
            policy["asset_groups"][0]["preload_roots"][1] = destination
            (root / "policy.json").write_text(json.dumps(policy))
            request["policy"] = pin(root / "policy.json")
            inputs.write_text(json.dumps(request))
            prepared = P.prepare_request(inputs, root / "prepared")
            required = json.loads((root / "prepared/required.json").read_bytes())
            self.assertNotIn("sdk", required["dependencies"])
            aliases = json.loads((root / "prepared/provider-paths.json").read_bytes())
            self.assertEqual(Path(aliases[witness["provider"]]), sdk.resolve())
            cold = P.produce_request(prepared["request"]["path"], root / "cold", cache_directory=root / "cache")
            warm = P.produce_request(prepared["request"]["path"], root / "warm", cache_directory=root / "cache")
            self.assertEqual(cold["sha256"], warm["sha256"])
            self.assertTrue(warm["emission"]["cache_reused"])
            sdk.write_bytes(sdk.read_bytes()[:-1] + b"!")
            with self.assertRaisesRegex(ValueError, "input differs"):
                P.produce_request(prepared["request"]["path"], root / "drift", cache_directory=root / "cache")

    def test_fresh_managed_preparation_retains_script_identity_properties_and_null_source(self):
        E = P.module("bundle_endpoints")
        identity = P.O.module("_prepare_test_identity", Path(__file__).resolve().parents[1] / "scripts/lab/script_identity.py")
        for null in (False, True):
            with self.subTest(null=null), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                inputs, request, policy, pin = self.fixture(root)
                node = identity._node
                names = ("AuthoredBehaviour", "Fixture", "Authored.dll")
                props = bytes(range(16))
                script_stream = io.BytesIO()
                P.O.aligned_string(script_stream, names[0])
                script_stream.write(bytes(4) + props)
                for value in names:
                    P.O.aligned_string(script_stream, value)
                script = script_stream.getvalue()
                script_nodes = [node("MonoScript", "Base", -1, level=0)]

                def text_nodes(name):
                    return [
                        node("string", name, -1, meta=0x4000),
                        node("Array", "Array", -1, level=2, flags=1),
                        node("int", "size", 4, level=3),
                        node("char", "data", 1, level=3),
                    ]

                script_nodes += text_nodes("m_Name") + [node("int", "m_ExecutionOrder", 4), node("Hash128", "hash", 16)]
                for name in ("m_ClassName", "m_Namespace", "m_AssemblyName"):
                    script_nodes += text_nodes(name)
                script_type = dict(class_id=115, stripped=0, script_type=-1, hash=b"s" * 16, tree=identity._tree(script_nodes), dependencies=[])
                nodes = [node("MonoBehaviour", "Base", -1, level=0)]
                for name in ("m_GameObject", "m_Script"):
                    if name == "m_Script":
                        nodes.append(node("int", "m_Enabled", 4))
                    nodes += [node("PPtr<Object>", name, 12), node("int", "m_FileID", 4, level=2), node("SInt64", "m_PathID", 8, level=2)]
                nodes.append(node("int", "m_Name", 4))
                typ = dict(
                    class_id=114,
                    stripped=0,
                    script_type=-1 if null else 0,
                    script_id=bytes(16) if null else identity.md4("".join(names).encode()),
                    hash=bytes(16) if null else props,
                    tree=identity._tree(nodes),
                    dependencies=[],
                )
                body = struct.pack("<iqiiqi", 0, 0, 1, 0, 0 if null else 20, 0)
                source = root / "original/managed.bundle"
                raw = self.serialized([dict(path_id=10, type=typ, body=body), dict(path_id=20, type=script_type, body=script)], platform=19)
                with source.open("wb") as stream:
                    P.O.W.write_bundle(stream, [("CAB-managed", 4, len(raw), lambda: io.BytesIO(raw))], lambda block, method: block, flags=0x40)
                digest = P.hashlib.sha256(body).hexdigest()
                profile = root / "managed.json"
                profile.write_text(
                    json.dumps(
                        dict(
                            input_id=P.O.M.INPUT_ID,
                            bundles=[
                                dict(
                                    path=source.name,
                                    sha256=P.O.B.sha(source),
                                    members=[
                                        dict(
                                            name="CAB-managed",
                                            objects=[
                                                dict(
                                                    path_id=10,
                                                    class_id=114,
                                                    sha256=digest,
                                                    outputs=[dict(bundle="managed-pack", member="managed-member", path_id=10, bytes=len(body), sha256=digest)],
                                                )
                                            ],
                                        )
                                    ],
                                )
                            ],
                        )
                    )
                )
                pack = root / "managed-pack"
                P.A.produce(profile, P.O.B.sha(profile), root / "original", pack)
                request["suppliers"] = [
                    dict(
                        name="managed",
                        profile=pin(profile),
                        **{
                            key: pin(pack / filename)
                            for key, filename in (("receipt", "result.json"), ("objects", "objects.bin"), ("index", "index.jsonl"), ("types", "types.json"))
                        },
                    )
                ]
                destination = ["content", "CAB-content", 100]
                policy.update(
                    bindings=[dict(supplier="managed", record_source=["managed-pack", "managed-member", 10], destination=destination)],
                    asset_groups=[dict(guid="12" * 16, path="Assets/Managed.asset", roots=[100])],
                    assets=[dict(name="assets/managed.asset", type="AuthoredBehaviour")],
                )
                policy.pop("canonical")
                policy.pop("field_routes")
                sdk = root / "runtime-scripts"
                sdk.write_bytes(self.serialized([dict(path_id=70, type=script_type, body=script)]))
                request["staged"] = [] if null else [dict(bundle="sdk", member="Library/unity default resources", file=pin(sdk))]
                # SDK serialized resources require witnesses when tree-free; this one retains its tree.
                if not null:
                    full = root / "script-full.json"
                    full.write_text(
                        json.dumps(
                            [
                                dict(
                                    destination=["sdk", "Library/unity default resources", 70],
                                    bytes=len(script),
                                    sha256=P.hashlib.sha256(script).hexdigest(),
                                    provider=str(sdk),
                                    provider_kind="serialized_file",
                                    provider_file_sha256=P.O.B.sha(sdk),
                                    class_id=115,
                                    native_type_hash=script_type["hash"].hex(),
                                    schema=P.hashlib.sha256(script_type["tree"]).hexdigest(),
                                    full_type=P.full_type_key(script_type),
                                    type_layout=P.O.json_layout(script_type),
                                    edges=[],
                                )
                            ]
                        )
                    )
                    request["staged"][0]["full"] = pin(full)
                    policy["staged_bindings"] = [dict(source=[source.name, "CAB-managed", 20], destination=["sdk", "Library/unity default resources", 70])]
                (root / "policy.json").write_text(json.dumps(policy))
                request["policy"] = pin(root / "policy.json")
                inputs.write_text(json.dumps(request))
                result = P.prepare_request(inputs, root / "prepared")
                prepared = json.loads(Path(result["request"]["path"]).read_bytes())
                value = list(P.json_rows(root / "prepared/selected-records.jsonl"))[0]
                _, retained = P.ProducerRecords().record(value)
                if null:
                    proof = prepared["null_script_sources"][0]["type_source"]
                    self.assertEqual(proof["sha256"], digest)
                    qualification = E.Qualification(SimpleNamespace(**vars(P)), None, prepared, {}, {}, {})
                    qualification.game = (root / "original").resolve()
                    qualification.null_sources = {tuple(destination): proof}
                    self.assertEqual(qualification.null_source(value), typ)
                else:
                    self.assertEqual(P.pointers(retained, typ, {})[("m_Script",)], (1, 70))
                    original = json.loads((root / "prepared/original-script-properties.json").read_bytes())
                    self.assertEqual(original, [dict(identity=[names[2], names[1], names[0]], properties=props.hex())])
                    key = names[2], names[1], names[0]
                    context = dict(
                        identity_owner=identity,
                        current={key: dict(unsupported=True, unchanged_provider_sha256="ab" * 32, source_trees=[typ["tree"].hex()])},
                        normalizer=None,
                        sdk_tree=None,
                        member_tables=lambda value: [("sdk", "Library/unity default resources")],
                        registry_scripts={key: (script, script_type)},
                        original_script_properties={key: props.hex()},
                    )
                    check = E.managed_checker(SimpleNamespace(**vars(P)), **context)
                    value["current_registry_identity"] = list(key)
                    script_value = dict(current_registry_identity=list(key))
                    self.assertEqual(check(value, retained, typ, lambda target: (script_value, script, script_type)), key)
                    with self.assertRaisesRegex(ValueError, "native hash"):
                        check(value, retained, dict(typ, hash=b"x" * 16), lambda target: (script_value, script, script_type))

    def test_reverse_profile_keeps_actual_script_source_separate_from_hash_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.json"
            selectors = dict(script=[0, 51], behaviour=[0, 61])
            profile.write_text(
                json.dumps(
                    dict(
                        bundle=dict(name="pack", member="CAB-pack"),
                        sources=[dict(path="original", member="CAB-source")],
                        objects=[dict(path_id=2, source=[0, 51], properties_hash=selectors), dict(path_id=3, source=[0, 61], properties_hash=selectors)],
                    )
                )
            )
            sources = P.module("bundle_prepare").original_identities(SimpleNamespace(**vars(P)), profile)
            self.assertEqual(sources[("pack", "CAB-pack", 2)], {("original", "CAB-source", 51)})
            self.assertEqual(sources[("pack", "CAB-pack", 3)], {("original", "CAB-source", 61)})

    def test_policy_change_rebuilds_only_selected_closure_and_retained_suppliers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs, request, policy, pin = self.fixture(root)
            first = P.prepare_request(inputs, root / "first-prepared")
            initial = P.produce_request(first["request"]["path"], root / "first", cache_directory=root / "cache")
            supplier_pins = {name: pin(root / name) for name in ("pack-a/result.json", "pack-a/objects.bin", "pack-b/result.json", "pack-b/objects.bin")}
            # The next preparation can consume final retained tables and bodies;
            # their PPtrs are in the explicitly declared output namespace.
            externals = json.loads((root / "first-prepared/required.json").read_bytes())["externals"]
            namespace = [["content", "CAB-content"], *[["canonical" if name == "CAB-donor" else "external", name] for name in externals]]
            for index, supplier in enumerate(list(request["suppliers"])):
                directory = root / ("first-prepared/retained-" + str(index))
                name = "retained-" + supplier["name"]
                request["suppliers"].append(
                    dict(
                        supplier,
                        name=name,
                        provider=name,
                        **{
                            key: pin(directory / filename)
                            for key, filename in (("receipt", "result.json"), ("objects", "objects.bin"), ("index", "index.jsonl"), ("types", "types.json"))
                        },
                    )
                )
            for binding in policy["bindings"]:
                binding["supplier"] = "retained-" + binding["supplier"]
                binding["pointer_namespace"] = namespace
            policy["field_routes"] = []
            policy["asset_groups"][0]["preload_roots"] = [["external", "CAB-external", 10]]
            (root / "policy.json").write_text(json.dumps(policy))
            request["policy"] = pin(root / "policy.json")
            inputs.write_text(json.dumps(request))
            revised = P.prepare_request(inputs, root / "revised-prepared")
            self.assertEqual(revised["records"], 3)
            final = P.produce_request(revised["request"]["path"], root / "revised", cache_directory=root / "cache")
            self.assertNotEqual(initial["sha256"], final["sha256"])
            self.assertFalse(final["emission"]["cache_reused"])
            self.assertEqual(supplier_pins, {name: pin(root / name) for name in supplier_pins})
