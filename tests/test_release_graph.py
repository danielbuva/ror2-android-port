"""Source graph contracts with authored supplier bodies; no game inputs."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/phone-build/owner-apk" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G, J = load("release_graph"), load("release_jobs")


class ReleaseGraphTests(unittest.TestCase):
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
            supplier = repo / "recipe/owner-supplier.json"
            supplier.write_text(json.dumps({"bundles": [{"members": [{"objects": []}]}]}))
            final = repo / "recipe/owner-final.json"
            final.write_text(json.dumps({"sources": [], "bundle": {"name": "authored"}, "objects": [{"record": G.digest(supplier)}]}))
            # Each owner checks receipt substitution before producing its output.
            script = """import argparse,hashlib,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--record-pack',nargs=2,action='append',default=[])
a,_=p.parse_known_args()
for path,pin in a.record_pack:
 assert hashlib.sha256((pathlib.Path(path)/'result.json').read_bytes()).hexdigest()==pin
out=pathlib.Path(a.output);out.mkdir()
for name in ('objects.bin','index.jsonl','result.json'):(out/name).write_text('authored')
(out/'payload').mkdir();(out/'payload/authored').write_text('source output')
"""
            for producer in ("record_produce", "object_produce"):
                (repo / G.PREFIX / (producer + ".py")).write_text(script)
            graph = G.Graph(repo, {})
            index = graph.compile(["recipe/owner-final.json"])
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
            self.assertEqual(destination.read_text(), "source output")
            self.assertEqual(progress, [False, False])
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
            final.write_text(json.dumps({"sources": [], "bundle": {"name": "authored"}, "objects": [{"record": "f" * 64}]}))
            with self.assertRaisesRegex(ValueError, "missing source supplier"):
                G.Graph(repo, {}).compile(["recipe/owner-final.json"])


if __name__ == "__main__":
    unittest.main()
