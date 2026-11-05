"""Compile existing source bundle recipes into incremental release job descriptors.

This host authoring step writes public JSON only. It never reads target APKs,
accepted bundles or generated record packs. Existing producer CLIs retain all
source, schema and reference checks. Unresolved suppliers are explicit failures.
"""

import argparse
import gzip
import hashlib
import importlib.util
import io
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
    def __init__(self, repo, extra_arguments, player_phases=None):
        self.repo = Path(repo).resolve()
        self.extra = extra_arguments
        self.phase_path = player_phases
        self.phases = json.loads((self.repo / player_phases).read_text()) if player_phases else {}
        self.phase_files = set()
        # Index content identities without retaining unrelated parsed recipes.
        # Dependency pins still resolve in the same sorted, last-match order.
        self.profiles = {}
        for pattern in ("owner-*.json", "owner-*.jsonl.gz"):
            for path in sorted((self.repo / "recipe").glob(pattern)):
                self.profiles[digest(path)] = path.relative_to(self.repo).as_posix()
        self.loaded_profiles = {}
        self.jobs = {}
        self.profile_files = {}
        self.job_profiles = {}

    def startup(self):
        """Share source startup identity between final files and managers."""
        name = "recipe/jobs/owner-startup-metadata.json"
        if name not in self.jobs:
            settings = "smoke/ProjectSettings/ProjectSettings.asset"
            toolchain = "environment/toolchain.json"
            prefix = "apk/assets/bin/Data/"
            self.jobs[name] = {
                "schema": 1,
                "script": PREFIX + "startup_metadata.py",
                "arguments": [
                    "--input-manifest",
                    "${input:inventory}",
                    "--settings",
                    "${repo}/" + settings,
                    "--toolchain",
                    "${repo}/" + toolchain,
                    "--output",
                    "${output}",
                ],
                "needs": [],
                "outputs": {prefix + target: "targets/" + prefix + target for target in ("boot.config", "unity_app_guid")},
                "artifacts": {"receipt": "result.json"},
            }
            self.job_profiles[name] = {"authored_inputs": {path: digest(self.repo / path) for path in (settings, toolchain)}}
        return name

    def player_arguments(self, providers):
        arguments = []
        for phase, row in self.phases.items():
            if phase not in {"ui", "hud", "stage-context", "manager", "scene"}:
                raise ValueError("unknown player phase: " + phase)
            path = self.repo / row["profile"]
            if digest(path) != row["sha256"]:
                raise ValueError("player phase profile drift: " + row["profile"])
            selected = json.loads(path.read_text())
            self.phase_files.add(row["profile"])
            # These owners read additional authored policy/schema inputs. Include
            # their public paths in the signed closure, never their private data.
            self.phase_files.update(item["path"] for item in selected.get("public_inputs", {}).values())
            self.phase_files.update("recipe/" + item["path"] for item in selected.get("texture_profiles", []))
            arguments += ["--" + phase + "-profile", "${repo}/" + row["profile"], row["sha256"]]
        if "ui" in self.phases:
            arguments += ["--ugui-source", "${input:ugui_source}"]
        if "manager" in self.phases:
            selected = json.loads((self.repo / self.phases["manager"]["profile"]).read_text())
            pin = selected["public_inputs"]["shaders"]["sha256"]
            dependency = providers.setdefault(pin, self.build(pin))
            startup = self.startup()
            providers["startup"] = startup
            arguments += [
                "--manager-shaders",
                "${job_directory:" + dependency + ":receipt}",
                "${sha256:" + dependency + ":receipt}",
                "--manager-startup",
                "${job:" + startup + ":receipt}",
                "${sha256:" + startup + ":receipt}",
            ]
        if {"manager", "scene"} & self.phases.keys():
            arguments += ["--sdk-binary", "${input:sdk_binary}"]
        if "scene" in self.phases:
            for name in ("result", "request", "bundle"):
                binding = "scene_environment_" + name
                arguments += ["--scene-environment-" + name, "${input:" + binding + "}", "${input_sha256:" + binding + "}"]
            arguments += ["--scene-environment-images", "${input:scene_environment_images}"]
        return arguments

    def build(self, pin, active=()):
        if pin in active:
            raise ValueError("cyclic profile supplier: " + pin)
        if pin not in self.profiles:
            raise ValueError("missing source supplier profile: " + pin)
        path = self.profiles[pin]
        name = "recipe/jobs/" + (Path(path).name.removesuffix(".jsonl.gz") if path.endswith(".jsonl.gz") else Path(path).stem) + ".json"
        if pin not in self.loaded_profiles:
            encoded = (self.repo / path).read_bytes()
            if hashlib.sha256(encoded).hexdigest() != pin:
                raise ValueError("source supplier profile drift: " + path)
            if path.endswith(".jsonl.gz"):
                # Verify compressed identity from the same bytes as the header;
                # never expand the native-record body into a Python hierarchy.
                with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as stream:
                    profile = json.loads(stream.readline(8 * 1024**2 + 1))
                if set(profile) != {"input_id"}:
                    raise ValueError("unknown compressed record profile header: " + Path(path).name)
            else:
                profile = json.loads(encoded)
            del encoded
            self.loaded_profiles[pin] = profile
        profile = self.loaded_profiles[pin]
        if name in self.jobs:
            return name
        producer = "record_produce" if path.endswith(".jsonl.gz") else owner(profile)
        if producer is None:
            raise ValueError("explicit producer wiring required for " + path)
        providers = {dependency: self.build(dependency, (*active, pin)) for dependency in suppliers(profile)}
        phase_arguments = self.player_arguments(providers) if producer == "player_data" else []
        needs = list(providers.values())
        arguments = ["--profile", "${repo}/" + path, "--profile-sha256", pin, "--output", "${output}"]
        if producer in {
            "object_produce",
            "record_remap",
            "record_produce",
            "mesh_produce",
            "avatar_produce",
            "texture_produce",
            "shader_context",
            "shader_prefab",
        }:
            arguments += ["--comparison", "diagnostic"]
        if producer == "payload_shader_records" and "legacy_sdk" in profile:
            arguments += ["--legacy-sdk", "${input:legacy_sdk}"]
        if producer != "record_remap":
            arguments += ["--pc-root" if producer in {"shader_context", "shader_prefab", "sprite_produce"} else "--pc", "${input:pc}"]
        if producer in {"record_produce", "shader_context", "shader_prefab", "payload_shader_records"}:
            arguments += ["--sdk", "${input:sdk}"]
        if producer == "player_data":
            # Player defaults belong to AndroidPlayer, not editor Contents.
            arguments += ["--sdk", "${input:sdk_contents}/../../PlaybackEngines/AndroidPlayer"]
        if producer == "object_produce" and "sdk" in profile:
            # Object profiles pin paths relative to Unity.app, while shader
            # tools bind its Contents directory. Preserve the profile root.
            arguments += ["--sdk", "${input:sdk_contents}/.."]
        if producer in {"shader_prefab", "shader_context", "payload_shader_records"} and profile.get("template_inputs"):
            arguments += ["--asset-ripper", "${input:asset_ripper}"]
        if producer == "sprite_produce":
            binding = "sprite_native_" + pin
            arguments = [
                "produce",
                *arguments,
                "--functional",
                "--native-output",
                "${input:" + binding + "}",
                "--native-sha256",
                "${input_sha256:" + binding + "}",
            ]
        if producer == "shader_produce":
            arguments += ["--sdk", "${input:sdk_contents}"]
        if producer == "texture_produce":
            textures = [texture for bundle in profile["bundles"] for member in bundle["members"] for texture in member["textures"]]
            operations = {texture["operation"] for texture in textures}
            bindings = []
            if operations & {"rgb-jpeg", "dxt1-rgb-jpeg"} or any(texture["operation"] in {"etc1", "etc1-mips"} and texture["jpeg"] for texture in textures):
                bindings.append("jpeg_codec")
            if operations & {"alpha8-etc2", "etc1", "etc1-mips", "sdk-rgba", "sdk-rgba-mips", "cube-mips", "cube-hdr", "cube-rgba-mips"}:
                bindings.append("etc_codec")
            if operations & {"sdk-rgba", "sdk-rgba-mips", "etc1-mips", "cube-mips", "cube-hdr", "cube-rgba-mips"}:
                bindings.append("sdk_toolchain")
            for binding in bindings:
                flag = "--" + binding.replace("_", "-")
                arguments += [flag, "${input:" + binding + "}", flag + "-sha256", "${input_sha256:" + binding + "}"]
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
        arguments += phase_arguments + extra
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
                for row in self.phases.values():
                    targets.extend(row["outputs"])
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
            recipes.add(job)
            if job in self.profile_files:
                recipes.add(self.profile_files[job])
            profile = self.job_profiles[job]
            producers.update(profile.get("authored_inputs", {}))
            if owner(profile) == "player_data":
                if self.phase_path:
                    recipes.add(self.phase_path)
                    for path in self.phase_files:
                        (recipes if path.startswith("recipe/") else producers).add(path)
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

    def bundle_manifest(self, selected_jobs):
        """Fan in final bundle artifacts; the existing owner checks dependencies."""
        bundles = []
        needs = []
        for job in sorted(set(selected_jobs)):
            descriptor = self.jobs[job]
            for target, path in sorted(descriptor["outputs"].items()):
                if not target.startswith("payload/"):
                    continue
                artifact = "manifest_bundle_" + str(len(bundles))
                descriptor["artifacts"][artifact] = path
                bundles.append(
                    {
                        "name": target.removeprefix("payload/"),
                        "path": "${job:" + job + ":" + artifact + "}",
                        "sha256": "${sha256:" + job + ":" + artifact + "}",
                        "bytes": "${bytes:" + job + ":" + artifact + "}",
                    }
                )
                if job not in needs:
                    needs.append(job)
        if not bundles:
            raise ValueError("bundle manifest requires selected complete bundle profiles")
        name = "recipe/jobs/owner-bundle-manifest.json"
        self.jobs[name] = {
            "schema": 1,
            "script": PREFIX + "bundle_manifest.py",
            "arguments": ["--inputs", "${request}", "--output", "${output}"],
            "request": {"schema": "owner-produced-bundle-inputs-v1", "bundles": bundles},
            "needs": needs,
            "outputs": {"payload/generated-android-data": "generated-android-data"},
            "artifacts": {"receipt": "result.json"},
        }
        self.job_profiles[name] = {}
        return name

    def native_code(self, request_path):
        """Produce native code and its matching metadata from one converter cohort."""
        request = json.loads((self.repo / request_path).read_text())
        if request.get("output") != "${output}":
            raise ValueError("native request must use the dispatcher output")
        name = "recipe/jobs/owner-native-code.json"
        self.jobs[name] = {
            "schema": 1,
            "script": "tools/phone-build/owner-code/native.py",
            "arguments": ["${request}"],
            "request": request,
            "needs": [],
            "outputs": {
                "apk/lib/arm64-v8a/libil2cpp.so": "libil2cpp.so",
                "apk/assets/bin/Data/Managed/Metadata/global-metadata.dat": "global-metadata.dat",
            },
            "artifacts": {"receipt": "result.json"},
        }
        self.profile_files[name] = request_path
        policy = "recipe/owner-native-arm64.json"
        self.job_profiles[name] = {"authored_inputs": {policy: digest(self.repo / policy)}}
        return name

    def sdk_package(self, request_path):
        """Keep SDK resources, Java code and native engine libraries in one job."""
        request = json.loads((self.repo / request_path).read_text())
        if request.get("output") != "${output}":
            raise ValueError("SDK request must use the dispatcher output")
        script = PREFIX + "sdk_package.py"
        spec = importlib.util.spec_from_file_location("graph_sdk_package", self.repo / script)
        sdk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sdk)
        name = "recipe/jobs/owner-sdk-package.json"
        self.jobs[name] = {
            "schema": 1,
            "script": script,
            "arguments": ["--request", "${request}"],
            "request": request,
            "needs": [],
            "outputs": {"apk/" + target: "resources/apk/" + target for target in sorted(sdk.SDK_ENTRIES)},
            "artifacts": {"receipt": "result.json"},
        }
        self.profile_files[name] = request_path
        helper = PREFIX + "SdkAndroidCode.java"
        self.job_profiles[name] = {"authored_inputs": {helper: digest(self.repo / helper)}}
        return name

    def burst_code(self, request_path):
        """Compile Burst from the same explicit managed/source input cohort."""
        request = json.loads((self.repo / request_path).read_text())
        if request.get("output") != "${output}":
            raise ValueError("Burst request must use the dispatcher output")
        root = "backend/burst/" if "source_inputs" in request else "burst/"
        name = "recipe/jobs/owner-burst-code.json"
        self.jobs[name] = {
            "schema": 1,
            "script": "tools/phone-build/owner-code/produce.py",
            "arguments": ["${request}", "--burst-only"],
            "request": request,
            "needs": [],
            "outputs": {"apk/lib/arm64-v8a/lib_burst_generated.so": root + "lib_burst_generated.so"},
            "artifacts": {"receipt": "result.json", "preservation": root + "burst.xml"},
        }
        self.profile_files[name] = request_path
        policies = ("recipe/owner-player-code.json", "recipe/owner-native-arm64.json", "recipe/owner-j850-code.json")
        self.job_profiles[name] = {"authored_inputs": {path: digest(self.repo / path) for path in policies}}
        return name

    def compile(self, selected, *, bundle_manifest=False, native_request=None, sdk_request=None, burst_request=None):
        entries = {}
        selected_jobs = [self.build(digest(self.repo / path)) for path in selected]
        startup = "recipe/jobs/owner-startup-metadata.json"
        if startup in self.jobs:
            selected_jobs.append(startup)
        if bundle_manifest:
            selected_jobs.append(self.bundle_manifest(selected_jobs))
        if native_request:
            selected_jobs.append(self.native_code(native_request))
        if sdk_request:
            selected_jobs.append(self.sdk_package(sdk_request))
        if burst_request:
            selected_jobs.append(self.burst_code(burst_request))
        for job in selected_jobs:
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
    parser.add_argument("--player-phases", help="repo-relative complete optional player phase/output declaration")
    parser.add_argument(
        "--bundle-manifest",
        action="store_true",
        help="generate the native manifest from every selected payload bundle; missing native dependencies fail production",
    )
    parser.add_argument("--native-request", help="repo-relative native request template; emits matching library and metadata from acquired converter inputs")
    parser.add_argument("--sdk-request", help="repo-relative SDK request template; emits Android resources, dex and engine libraries")
    parser.add_argument("--burst-request", help="repo-relative managed/source request template; compiles Burst and retains preservation roots")
    parser.add_argument("--extra-arguments", type=Path, help="JSON producer name -> additional CLI argv, with dispatcher substitutions")
    parser.add_argument("--output", type=Path, required=True, help="new public job staging root; overlay into a release source checkout")
    args = parser.parse_args()
    graph = Graph(args.repo, json.loads(args.extra_arguments.read_text()) if args.extra_arguments else {}, args.player_phases)
    index = graph.compile(
        args.profile,
        bundle_manifest=args.bundle_manifest,
        native_request=args.native_request,
        sdk_request=args.sdk_request,
        burst_request=args.burst_request,
    )
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
