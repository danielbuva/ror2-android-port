"""Compile existing source bundle recipes into incremental release job descriptors.

This host authoring step writes public JSON only. It never reads target APKs,
accepted bundles or generated record packs. Existing producer CLIs retain all
source, schema and reference checks. Unresolved suppliers are explicit failures.
"""

import argparse
import hashlib
import json
from pathlib import Path

PREFIX = "tools/phone-build/accepted-output/"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def owner(profile):
    if "original_bundle" in profile or ("sources" in profile and "bundle" in profile):
        return "object_produce"
    if "source_type" in profile and "provider_profile_sha256" in profile:
        return "shader_context"
    if "shader_links" in profile:
        return "shader_prefab"
    if "records" in profile and profile["records"] and all("source_profile_sha256" in row for row in profile["records"]):
        return "record_remap"
    if "source_type" in profile or ("source" in profile and "shaders" in profile and "template_inputs" in profile):
        return "payload_shader_records"
    if "bundles" in profile:
        keys = {key for bundle in profile["bundles"] for member in bundle.get("members", []) for key in member}
        for key, producer in (("meshes", "mesh_produce"), ("avatars", "avatar_produce"), ("textures", "texture_produce"), ("objects", "record_produce")):
            if key in keys:
                return "sprite_produce" if key == "objects" and "schema" in profile else producer
    return None


def suppliers(value):
    result = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"record", "source_profile_sha256", "provider_profile_sha256"} and isinstance(child, str) and len(child) == 64:
                result.add(child)
            result.update(suppliers(child))
    elif isinstance(value, list):
        for child in value:
            result.update(suppliers(child))
    return sorted(result)


class Graph:
    def __init__(self, repo, extra_arguments):
        self.repo = Path(repo).resolve()
        self.extra = extra_arguments
        self.profiles = {}
        for path in sorted((self.repo / "recipe").glob("owner-*.json")):
            self.profiles[digest(path)] = (path.relative_to(self.repo).as_posix(), json.loads(path.read_text()))
        self.jobs = {}
        self.profile_files = {}

    def build(self, pin, active=()):
        if pin in active:
            raise ValueError("cyclic profile supplier: " + pin)
        if pin not in self.profiles:
            raise ValueError("missing source supplier profile: " + pin)
        path, profile = self.profiles[pin]
        name = "recipe/jobs/" + Path(path).stem + ".json"
        if name in self.jobs:
            return name
        producer = owner(profile)
        if producer is None or producer == "sprite_produce":
            raise ValueError("explicit producer wiring required for " + path)
        needs = [self.build(dependency, (*active, pin)) for dependency in suppliers(profile)]
        arguments = ["--profile", "${repo}/" + path, "--profile-sha256", pin, "--output", "${output}"]
        if producer != "record_remap":
            arguments += ["--pc-root" if producer in {"shader_context", "shader_prefab"} else "--pc", "${input:pc}"]
        if producer in {"record_produce", "shader_context", "shader_prefab", "payload_shader_records"}:
            arguments += ["--sdk", "${input:sdk}"]
        if producer in {"object_produce", "shader_prefab", "payload_shader_records"} and "original_bundle" not in profile:
            arguments += ["--codec", "${input:codec}", "--codec-sha256", "${input_sha256:codec}"]
        if producer == "shader_context":
            if len(needs) != 1:
                raise ValueError("shader context requires one provider: " + path)
            arguments += ["--record-pack", "${job_directory:" + needs[0] + ":receipt}", "--receipt-sha256", "${sha256:" + needs[0] + ":receipt}"]
        elif producer in {"object_produce", "record_remap"}:
            for dependency in needs:
                arguments += ["--record-pack", "${job_directory:" + dependency + ":receipt}", "${sha256:" + dependency + ":receipt}"]
        elif needs:
            raise ValueError("unsupported supplier contract: " + path)
        extra = self.extra.get(producer, [])
        if not isinstance(extra, list) or not all(isinstance(arg, str) for arg in extra):
            raise ValueError("producer extra arguments must be an argv list")
        arguments += extra
        outputs = {}
        artifacts = {"receipt": "result.json", "objects": "objects.bin", "index": "index.jsonl"}
        if "original_bundle" in profile:
            artifacts = {"receipt": "result.json"}
        if producer in {"mesh_produce", "texture_produce"}:
            artifacts["resources"] = "resources.bin"
        if producer == "object_produce":
            target = "payload/" + ("windows-shaders.bundle" if "original_bundle" in profile else profile["bundle"]["name"])
            outputs[target] = target
        self.jobs[name] = {"schema": 1, "script": PREFIX + producer + ".py", "arguments": arguments, "needs": needs, "outputs": outputs, "artifacts": artifacts}
        self.profile_files[name] = path
        return name

    def entry(self, name):
        recipes, producers = set(), set()

        def visit(job):
            recipes.update((job, self.profile_files[job]))
            producers.add(self.jobs[job]["script"])
            for dependency in self.jobs[job]["needs"]:
                visit(dependency)

        visit(name)
        # Owners import one another dynamically. Conservatively ship the authored
        # Python cohort, rather than omit a runtime import from a signed closure.
        producers.update(path.relative_to(self.repo).as_posix() for path in (self.repo / "tools/phone-build").rglob("*.py"))
        return {"job": name, "recipe_files": sorted(recipes), "producer_files": sorted(producers)}

    def compile(self, selected):
        entries = {}
        for path in selected:
            job = self.build(digest(self.repo / path))
            for output in self.jobs[job]["outputs"]:
                if output in entries:
                    raise ValueError("multiple selected profiles produce " + output)
                entries[output] = self.entry(job)
        if not entries:
            raise ValueError("select at least one complete output profile")
        return {
            "schema": 1,
            "entries": entries,
            "files": {
                path: digest(self.repo / path)
                for row in entries.values()
                for key in ("recipe_files", "producer_files")
                for path in row[key]
                if path not in self.jobs
            },
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--profile", action="append", required=True, help="repo-relative complete output profile; repeat for a cohort")
    parser.add_argument("--extra-arguments", type=Path, help="JSON producer name -> additional CLI argv, with dispatcher substitutions")
    parser.add_argument("--output", type=Path, required=True, help="new public job staging root; overlay into a release source checkout")
    args = parser.parse_args()
    graph = Graph(args.repo, json.loads(args.extra_arguments.read_text()) if args.extra_arguments else {})
    index = graph.compile(args.profile)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, job in graph.jobs.items():
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job, sort_keys=True, indent=2) + "\n")
        index["files"][name] = digest(path)
    (args.output / "source-index.json").write_text(json.dumps(index, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"jobs": len(graph.jobs), "entries": len(index["entries"])}))


if __name__ == "__main__":
    main()
