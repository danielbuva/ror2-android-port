"""Source graph contracts with authored supplier bodies; no game inputs."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
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

            def wire(value):
                return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()

            for name, job in graph.jobs.items():
                index["files"][name] = hashlib.sha256(wire(job)).hexdigest()
            # Captured from the eager implementation before changing its loader:
            # exact descriptors, dependency closure, ordering and index bytes.
            self.assertEqual(
                hashlib.sha256(wire({"index": index, "jobs": graph.jobs})).hexdigest(), "b08afa96036b9b10c90b4753fd99c0be13772e485234c5e90a5bfeca0ce369dd"
            )

    def test_object_sdk_profile_keeps_application_relative_resource_root(self):
        graph = G.Graph(ROOT, {})
        name = graph.build(G.digest(ROOT / "recipe/owner-objective-support-objects.json"))
        arguments = graph.jobs[name]["arguments"]
        root = arguments[arguments.index("--sdk") + 1]
        self.assertEqual(root, "${input:sdk_contents}/..")
        profile = graph.job_profiles[name]
        self.assertTrue(profile["sdk"]["path"].startswith("Contents/Resources/"))

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
            self.assertEqual(job["artifacts"], {"receipt": "result.json", "objects": "objects.bin", "index": "index.jsonl"})

    def test_fallback_shader_job_binds_pinned_public_templates(self):
        graph = G.Graph(ROOT, {})
        name = graph.build(G.digest(ROOT / "recipe/owner-commando-fallback-shaders.json"))
        arguments = graph.jobs[name]["arguments"]
        self.assertEqual(arguments[arguments.index("--asset-ripper") + 1], "${input:asset_ripper}")

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
        self.assertIn("${input_sha256:scene_environment_result}", job["arguments"])
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

    def test_sdk_job_signs_java_helper_expands_tools_and_reuses_complete_cohort(self):
        spec = importlib.util.spec_from_file_location("test_sdk_graph_owner", ROOT / G.PREFIX / "sdk_package.py")
        sdk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sdk)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo, inputs = root / "repo", root / "inputs"
            (repo / "recipe").mkdir(parents=True)
            (inputs / "work").mkdir(parents=True)
            template = "recipe/owner-sdk-job-inputs.json"
            shutil.copyfile(ROOT / template, repo / template)
            producer = repo / G.PREFIX / "sdk_package.py"
            producer.parent.mkdir(parents=True)
            producer.write_text(
                "SDK_ENTRIES = "
                + repr(sdk.SDK_ENTRIES)
                + "\n"
                + """if __name__ == '__main__':
    import json,pathlib,sys
    assert sys.argv[1]=='--request'
    request=json.loads(pathlib.Path(sys.argv[2]).read_text())
    assert len(request['jars'])==13
    for name in ('sdk','android_jar','aapt','java','javac'):
        assert pathlib.Path(request[name]).is_file()
    assert all(pathlib.Path(value).is_file() for value in request['jars'].values())
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
            bindings = {}
            for token in [request[name] for name in ("sdk", "android_jar", "aapt", "java", "javac")] + list(request["jars"].values()):
                key = token.removeprefix("${input:").removesuffix("}")
                bindings[key] = key
                (inputs / key).write_text("authored tool input")
            graph = G.Graph(repo, {})
            index = graph.compile([], sdk_request=template)
            self.assertEqual(set(index["entries"]), {"apk/" + name for name in sdk.SDK_ENTRIES})
            self.assertIn(helper, index["files"])
            self.assertIn(template, index["files"])
            for name, descriptor in graph.jobs.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(descriptor))
                index["files"][name] = G.digest(path)
            release = {"entries": {name: J.UPDATES.public().entry_dependencies(index, name) for name in index["entries"]}}
            runtime, native = root / "runtime", root / "native"
            runtime.mkdir()
            native.mkdir()
            progress = []
            for _ in range(2):
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
                for name, dependencies in release["entries"].items():
                    destination = root / "results" / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    dispatcher.produce(name, dependencies, destination)
                    self.assertEqual(destination.read_bytes(), ("authored " + name.removeprefix("apk/")).encode())
            self.assertEqual(progress, [False, True])
            (repo / helper).write_text("// changed helper\n")
            dispatcher = J.Dispatcher(repo, index, release, inputs, runtime, native, {"bindings": bindings}, "a" * 64, python=[sys.executable])
            with self.assertRaisesRegex(ValueError, "verified public source changed"):
                dispatcher.execute("recipe/jobs/owner-sdk-package.json")

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
                    progress=lambda name, reused: progress.append(reused),
                )
                for name, dependency in release["entries"].items():
                    destination = root / (str(pass_number) + "-" + Path(name).name)
                    dispatcher.produce(name, dependency, destination)
                    self.assertTrue(destination.is_file())
            self.assertEqual(progress, [False, True])
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
for name in ('objects.bin','index.jsonl','result.json'):(out/name).write_text('authored')
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
