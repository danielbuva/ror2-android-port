"""Compile existing source bundle recipes into incremental release job descriptors.

This host authoring step writes public JSON only. It never reads target APKs,
accepted bundles or generated record packs. Existing producer CLIs retain all
source, schema and reference checks. Unresolved suppliers are explicit failures.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

PREFIX = "tools/phone-build/accepted-output/"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def owner(profile):
    if "project_assemblies" in profile and "outputs" in profile:
        return "player_data"
    if "shaders" in profile and "authored_inputs" in profile and "includes_sha256" in profile:
        return "shader_produce"
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
            if key in {"record", "source_profile_sha256", "provider_profile_sha256", "shader_record"} and isinstance(child, str) and len(child) == 64:
                result.add(child)
            result.update(suppliers(child))
        for texture in value.get("textures", []) if isinstance(value.get("textures"), list) else []:
            if isinstance(texture, dict) and "profile_sha256" in texture:
                result.add(texture["profile_sha256"])
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
        # Large native-record recipes are streamed by record_produce itself.
        # Discover their identity without expanding the hierarchy into memory.
        for path in sorted((self.repo / "recipe").glob("owner-*.jsonl.gz")):
            with gzip.open(path, "rb") as stream:
                header = json.loads(stream.readline(8 * 1024**2 + 1))
            if set(header) != {"input_id"}:
                raise ValueError("unknown compressed record profile header: " + path.name)
            self.profiles[digest(path)] = (path.relative_to(self.repo).as_posix(), header)
        self.jobs = {}
        self.profile_files = {}
        self.job_profiles = {}

    def build(self, pin, active=()):
        if pin in active:
            raise ValueError("cyclic profile supplier: " + pin)
        if pin not in self.profiles:
            raise ValueError("missing source supplier profile: " + pin)
        path, profile = self.profiles[pin]
        name = "recipe/jobs/" + (Path(path).name.removesuffix(".jsonl.gz") if path.endswith(".jsonl.gz") else Path(path).stem) + ".json"
        if name in self.jobs:
            return name
        producer = "record_produce" if path.endswith(".jsonl.gz") else owner(profile)
        if producer is None or producer == "sprite_produce":
            raise ValueError("explicit producer wiring required for " + path)
        providers = {dependency: self.build(dependency, (*active, pin)) for dependency in suppliers(profile)}
        needs = list(providers.values())
        arguments = ["--profile", "${repo}/" + path, "--profile-sha256", pin, "--output", "${output}"]
        if producer != "record_remap":
            arguments += ["--pc-root" if producer in {"shader_context", "shader_prefab"} else "--pc", "${input:pc}"]
        if producer in {"record_produce", "shader_context", "shader_prefab", "payload_shader_records", "player_data"}:
            arguments += ["--sdk", "${input:sdk}"]
        if producer == "shader_produce":
            arguments += ["--sdk", "${input:sdk_contents}"]
        if producer in {"object_produce", "shader_prefab", "payload_shader_records", "shader_produce"} and "original_bundle" not in profile:
            arguments += ["--codec", "${input:codec}", "--codec-sha256", "${input_sha256:codec}"]
        if producer == "shader_context":
            if len(needs) != 1:
                raise ValueError("shader context requires one provider: " + path)
            arguments += ["--record-pack", "${job_directory:" + needs[0] + ":receipt}", "--receipt-sha256", "${sha256:" + needs[0] + ":receipt}"]
        elif producer in {"object_produce", "record_remap"}:
            for dependency in needs:
                dependency_owner = Path(self.jobs[dependency]["script"]).stem
                flag = "--serialized-producer" if producer == "record_remap" and dependency_owner in {"player_data", "shader_produce"} else "--record-pack"
                arguments += [flag, "${job_directory:" + dependency + ":receipt}", "${sha256:" + dependency + ":receipt}"]
        elif producer == "player_data":
            arguments += [
                "--builtin-extra",
                "${input:sdk_contents}/Resources/unity_builtin_extra",
                "--editor-resources",
                "${input:sdk_contents}/Resources/unity editor resources",
                "--converter",
                "${input:converter}",
                "--converter-receipt-sha256",
                "${input_sha256:converter_receipt}",
                "--code-request",
                "${input:code_request}",
                "--managed-production",
                "${input:managed}",
            ]
            for texture in profile.get("textures", []):
                dependency = providers[texture["profile_sha256"]]
                arguments += ["--texture-pack", "${job_directory:" + dependency + ":receipt}", "${sha256:" + dependency + ":receipt}"]
            if "shared_defaults" in profile:
                dependency = providers[profile["shared_defaults"]["shader_record"]]
                arguments += ["--record-pack", "${job_directory:" + dependency + ":shared_receipt}", "${sha256:" + dependency + ":shared_receipt}"]
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
        if producer in {"shader_produce", "player_data"}:
            artifacts = {"receipt": "result.json"}
            targets = [row["file"] for row in profile["shaders"]] if producer == "shader_produce" else list(profile["outputs"])
            if producer == "shader_produce":
                if "builtin" in profile:
                    targets.append("Resources/unity_builtin_extra")
                    artifacts.update(
                        {
                            "shared_receipt": "shared-shaders/result.json",
                            "shared_objects": "shared-shaders/objects.bin",
                            "shared_index": "shared-shaders/index.jsonl",
                        }
                    )
            else:
                targets += [
                    "unity default resources",
                    *["Managed/Resources/" + name + "-resources.dat" for name in ("System.Data.dll", "System.Drawing.dll", "mscorlib.dll")],
                ]
                if "registry" in profile:
                    targets.append(profile["registry"]["file"])
                if "shared_defaults" in profile:
                    targets.append(profile["shared_defaults"]["file"])
            outputs = {"apk/assets/bin/Data/" + target: "apk/assets/bin/Data/" + target for target in targets}
        self.jobs[name] = {"schema": 1, "script": PREFIX + producer + ".py", "arguments": arguments, "needs": needs, "outputs": outputs, "artifacts": artifacts}
        self.profile_files[name] = path
        self.job_profiles[name] = profile
        return name

    def entry(self, name):
        recipes, producers, visited = set(), set(), set()

        def visit(job):
            if job in visited:
                return
            visited.add(job)
            recipes.update((job, self.profile_files[job]))
            profile = self.job_profiles[job]
            producers.update(profile.get("authored_inputs", {}))
            if owner(profile) == "player_data":
                for row in profile.get("text_assets", {}).get("files", []):
                    if "recipe" in row:
                        recipes.add("recipe/" + row["recipe"]["path"])
                for row in (profile.get("registry"), profile.get("text_assets", {}).get("manifests")):
                    if row:
                        recipes.add("recipe/" + row["path"])
            producers.add(self.jobs[job]["script"])
            for dependency in self.jobs[job]["needs"]:
                visit(dependency)

        visit(name)
        # Owners import one another dynamically. Conservatively ship the authored
        # Python cohort, rather than omit a runtime import from a signed closure.
        producers.update(path.relative_to(self.repo).as_posix() for path in (self.repo / "tools/phone-build").rglob("*.py"))
        producers.update(path.relative_to(self.repo).as_posix() for path in (self.repo / "scripts/lab").rglob("*.py"))
        return {"job": name, "recipe_files": sorted(recipes), "producer_files": sorted(producers)}

    def compile(self, selected):
        entries = {}
        for path in selected:
            job = self.build(digest(self.repo / path))
            entry = self.entry(job)
            for output in self.jobs[job]["outputs"]:
                if output in entries:
                    raise ValueError("multiple selected profiles produce " + output)
                entries[output] = entry
        if not entries:
            raise ValueError("select at least one complete output profile")
        files = {path for row in entries.values() for key in ("recipe_files", "producer_files") for path in row[key] if path not in self.jobs}
        return {
            "schema": 1,
            "entries": entries,
            "files": {path: digest(self.repo / path) for path in sorted(files)},
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
