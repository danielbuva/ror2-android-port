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
import re
from types import SimpleNamespace

PREFIX = "tools/phone-build/accepted-output/"
PLAYER_RESOURCE_ASSEMBLIES = ("System.Data", "System.Drawing", "mscorlib")
PLAYER_RESOURCE_ARTIFACTS = {
    "Resources/unity_builtin_extra": "builtin_extra",
    "unity default resources": "default_resources",
}
ANDROID_COMPONENT = "${inputs}/acquired/unity-android-support.pkg"
LINUX_COMPONENT = "${inputs}/acquired/unity-linux-editor.tar.xz"
LEGACY_SHADER_SDK = "${inputs}/acquired/unity-legacy-sdk/Contents"
PACKAGE_POLICY = "tools/phone-build/package-assemblies/profile.json"
PACKAGE_PRODUCER = "tools/phone-build/package-assemblies/produce.py"
PACKAGE_ARCHIVES = "${inputs}/acquired/unity-packages"
ASSET_RIPPER_SOURCE = "${inputs}/acquired/asset-ripper"
ASSET_RIPPER_TEMPLATES = "Source/AssetRipper.Export.UnityProjects/Shaders/Templates/"
SDK_GNU_ROOT = "${inputs}/acquired/android-sdk/linux"
SDK_GNU_LIBRARIES = SDK_GNU_ROOT + "/lib/x86_64-linux-gnu"
SDK_GNU_WITNESSES = [
    "${native}/libqemu-x86_64.so",
    "${native}/libc++_shared.so",
    SDK_GNU_ROOT + "/lib64/ld-linux-x86-64.so.2",
    *[
        SDK_GNU_LIBRARIES + "/" + name
        for name in ("libc.so.6", "libdl.so.2", "libgcc_s.so.1", "libm.so.6", "libpthread.so.0", "librt.so.1", "libstdc++.so.6", "libz.so.1")
    ],
]
INSTALLED_BUNDLE_CODEC = dict(
    path="${native}/libbundlelz4.so",
    sha256="${native_sha256:libbundlelz4.so}",
    bytes="${native_bytes:libbundlelz4.so}",
)
INSTALLED_CODE_TOOLS = {
    "dotnet": "libdotnetmuxer.so",
    "clang": "libclang.so",
    "linker": "lib-ld.lld-.so",
    "objcopy": "libobjcopy.so",
}
INSTALLED_CODE_WITNESSES = {"${native}/" + path for path in INSTALLED_CODE_TOOLS.values()} | {"${installed_runtime}/data-hashes.json"}
TEXTURE_NATIVE = {
    "jpeg_codec": "libtexture-jpeg.so",
    "etc_codec": "libtexture-etc.so",
}
PIXEL_DECODER = "libtexture-pixels.so"
TEXTURE_GUEST = "${installed_runtime}/texture-sdk/"
TEXTURE_GUEST_LIB = "linux/lib/x86_64-linux-gnu/"


def texture_sdk_request(library, guest_files):
    qemu = "libqemu-x86_64.so"
    pixels = PIXEL_DECODER
    return {
        "command": [
            "${native}/" + qemu,
            "-L",
            TEXTURE_GUEST + "linux",
            "-E",
            "LD_LIBRARY_PATH=" + TEXTURE_GUEST + TEXTURE_GUEST_LIB.rstrip("/"),
            "-E",
            "LC_ALL=C",
            TEXTURE_GUEST + "texture-sdk-codec",
            library["path"],
        ],
        "environment": {},
        "pixels": "${native}/" + pixels,
        "inputs": {
            **{"${native}/" + name: "${native_sha256:" + name + "}" for name in (qemu, pixels, "libc++_shared.so")},
            **{TEXTURE_GUEST + name: pin for name, pin in guest_files.items()},
            library["path"]: library["sha256"],
        },
    }


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def owner(profile):
    if profile.get("schema") == "owner-bundle-managed-release-v1":
        return "bundle_endpoints"
    if profile.get("schema") == "owner-bundle-preload-release-v1":
        return "bundle_preload"
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
        self.public_files = {}
        self.bundle_release_jobs = set()
        self.conversion = None
        self.android_sdk = None
        self.package_inputs = None

    def sdk_contents(self, acquired="${input:sdk_contents}"):
        if self.conversion:
            return self.jobs[self.conversion]["request"]["sdk_install"] + "/Unity.app/Contents"
        return acquired

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
            ugui = (
                self.sdk_contents() + "/Resources/PackageManager/BuiltInPackages/com.unity.ugui/Runtime/UI/Core" if self.conversion else "${input:ugui_source}"
            )
            arguments += ["--ugui-source", ugui]
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
            arguments += ["--sdk-binary", self.sdk_contents() + "/MacOS/Unity" if self.conversion else "${input:sdk_binary}"]
        scene_environment = self.phases.get("scene", {}).get("environment", "capture")
        if scene_environment == "original":
            arguments += ["--scene-environment-decoder", "${native}/" + PIXEL_DECODER, "${native_sha256:" + PIXEL_DECODER + "}"]
        elif scene_environment != "capture":
            raise ValueError("unknown default scene environment: " + scene_environment)
        elif "scene" in self.phases:
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
        if producer == "bundle_endpoints":
            return self.bundle_managed(path, profile, (*active, pin))
        if producer == "bundle_preload":
            return self.bundle_preload(path, profile, (*active, pin))
        if producer is None:
            raise ValueError("explicit producer wiring required for " + path)
        providers = {dependency: self.build(dependency, (*active, pin)) for dependency in suppliers(profile)}
        phase_arguments = self.player_arguments(providers) if producer == "player_data" else []
        needs = list(providers.values())
        request = None
        witnesses = []
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
            arguments += ["--legacy-sdk", LEGACY_SHADER_SDK if self.conversion else "${input:legacy_sdk}"]
            if self.conversion:
                witnesses.extend(LEGACY_SHADER_SDK + "/" + name for name in sorted(profile["legacy_sdk"]))
        if producer != "record_remap":
            arguments += ["--pc-root" if producer in {"shader_context", "shader_prefab", "sprite_produce"} else "--pc", "${input:pc}"]
        if producer in {"record_produce", "shader_context", "shader_prefab", "payload_shader_records"}:
            sdk = self.sdk_contents("${input:sdk}")
            if self.conversion and producer == "record_produce" and profile.get("sdk", {}).get("path", "").startswith("Contents/"):
                sdk += "/.."
            arguments += ["--sdk", sdk]
        if producer == "player_data":
            if self.android_sdk:
                needs.append(self.android_sdk)
                android = self.artifact_pin(self.android_sdk, "android_player")["path"]
            elif self.conversion:
                android = self.jobs[self.conversion]["request"]["sdk_install"] + "/PlaybackEngines/AndroidPlayer"
            else:
                android = self.sdk_contents() + "/../../PlaybackEngines/AndroidPlayer"
            arguments += ["--sdk", android]
        if producer == "object_produce" and "sdk" in profile:
            # Object profiles pin paths relative to Unity.app, while shader
            # tools bind its Contents directory. Preserve the profile root.
            arguments += ["--sdk", self.sdk_contents() + "/.."]
        if producer in {"shader_prefab", "shader_context", "payload_shader_records"} and profile.get("template_inputs"):
            arguments += ["--asset-ripper", ASSET_RIPPER_SOURCE if self.conversion else "${input:asset_ripper}"]
            if self.conversion:
                path_prefix = ASSET_RIPPER_SOURCE + "/" + profile["exporter_revision"] + "/"
                witnesses.extend(path_prefix + ASSET_RIPPER_TEMPLATES + name for name in profile["template_inputs"])
                if producer != "shader_context":
                    witnesses.append(path_prefix + "LICENSE.md")
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
            arguments += ["--sdk", self.sdk_contents()]
            if self.conversion:
                recovered = ("native_ui", "native_materials", "native_internal", "native_intersection")
                for flag, installed, required in (
                    ("d3dasm", "libd3dasm.so", any(key in profile for key in recovered)),
                    ("hlsl-tool", "libhlsl-decompiler.so", "native_internal" in profile),
                ):
                    if required:
                        native = "${native}/" + installed
                        arguments += ["--" + flag, native, "--" + flag + "-sha256", "${native_sha256:" + installed + "}"]
                        witnesses.append(native)
            if self.conversion and "tmp_dummy" in profile:
                provider = profile["tmp_dummy"]
                arguments += ["--asset-ripper-source", ASSET_RIPPER_SOURCE]
                path_prefix = ASSET_RIPPER_SOURCE + "/" + provider["exporter_revision"] + "/"
                witnesses.extend(path_prefix + name for name in provider["template_inputs"])
                witnesses.append(path_prefix + "LICENSE.md")
        if self.conversion and producer in {"shader_produce", "shader_context", "shader_prefab", "payload_shader_records"}:
            extractor = self.sdk_shader_extraction()
            needs.append(extractor)
            compiler_data = self.artifact_pin(extractor, "data")["path"]
            tools = compiler_data + "/Tools"
            command = [
                "${native}/libqemu-x86_64.so",
                "-L",
                SDK_GNU_ROOT,
                "-E",
                "LD_LIBRARY_PATH=" + tools + ":" + SDK_GNU_LIBRARIES,
                "-E",
                "LC_ALL=C",
                tools + "/UnityShaderCompiler",
            ]
            arguments += ["--compiler-command", json.dumps(command), "--compiler-data", compiler_data]
            witnesses.extend(SDK_GNU_WITNESSES)
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
                if not self.conversion:
                    path_token, pin_token = "${input:" + binding + "}", "${input_sha256:" + binding + "}"
                elif binding == "sdk_toolchain":
                    extractor = self.sdk_texture_extraction()
                    needs.append(extractor)
                    guest_files = json.loads((self.repo / "recipe/owner-app-host-tools.json").read_text())["texture_sdk_guest"]
                    request = texture_sdk_request(self.artifact_pin(extractor, "library"), guest_files)
                    witnesses.extend(TEXTURE_GUEST + name for name in guest_files)
                    path_token, pin_token = "${request}", "${request_sha256}"
                else:
                    installed = TEXTURE_NATIVE[binding]
                    path_token, pin_token = "${native}/" + installed, "${native_sha256:" + installed + "}"
                    if binding == "etc_codec" and "sdk_toolchain" not in bindings:
                        witnesses.append("${native}/libc++_shared.so")
                arguments += [flag, path_token, flag + "-sha256", pin_token]
        if producer in {"object_produce", "shader_prefab", "payload_shader_records", "shader_produce"} and "original_bundle" not in profile:
            codec = INSTALLED_BUNDLE_CODEC if self.conversion else dict(path="${input:codec}", sha256="${input_sha256:codec}")
            arguments += ["--codec", codec["path"], "--codec-sha256", codec["sha256"]]
        if producer == "shader_context":
            if len(providers) != 1:
                raise ValueError("shader context requires one provider: " + path)
            records = next(iter(providers.values()))
            arguments += ["--record-pack", "${job_directory:" + records + ":receipt}", "--receipt-sha256", "${sha256:" + records + ":receipt}"]
        elif producer in {"object_produce", "record_remap"}:
            for dependency in needs:
                dependency_owner = Path(self.jobs[dependency]["script"]).stem
                flag = "--serialized-producer" if producer == "record_remap" and dependency_owner in {"player_data", "shader_produce"} else "--record-pack"
                arguments += [flag, "${job_directory:" + dependency + ":receipt}", "${sha256:" + dependency + ":receipt}"]
        elif producer == "player_data":
            arguments += [
                "--builtin-extra",
                self.sdk_contents() + "/Resources/unity_builtin_extra",
                "--editor-resources",
                self.sdk_contents() + "/Resources/unity editor resources",
            ]
            if self.conversion:
                needs.append(self.conversion)
                fresh_arguments, request = self.player_conversion(needs)
                arguments += fresh_arguments
            else:
                arguments += [
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
        elif providers:
            raise ValueError("unsupported supplier contract: " + path)
        extra = self.extra.get(producer, [])
        if not isinstance(extra, list) or not all(isinstance(arg, str) for arg in extra):
            raise ValueError("producer extra arguments must be an argv list")
        arguments += phase_arguments + extra
        outputs = {}
        artifacts = {"receipt": "result.json", "objects": "objects.bin", "index": "index.jsonl"}
        if "original_bundle" in profile:
            artifacts = {"receipt": "result.json"}
        elif producer == "object_produce":
            artifacts["layout"] = "layout.json"
        if producer in {
            "record_produce",
            "record_remap",
            "mesh_produce",
            "avatar_produce",
            "texture_produce",
            "sprite_produce",
            "shader_context",
            "shader_prefab",
            "payload_shader_records",
        } or (producer == "shader_produce" and "typed_records" in profile):
            artifacts["types"] = "types.json"
        if producer in {"mesh_produce", "texture_produce"}:
            artifacts["resources"] = "resources.bin"
        if producer == "object_produce":
            target = "payload/" + ("windows-shaders.bundle" if "original_bundle" in profile else profile["bundle"]["name"])
            outputs[target] = target
            if "original_bundle" not in profile:
                artifacts["catalog_bundle"] = target
        if producer == "player_data" or (producer == "shader_produce" and "typed_records" not in profile):
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
                            "shared_types": "shared-shaders/types.json",
                        }
                    )
            else:
                targets += [
                    "unity default resources",
                    *["Managed/Resources/" + name + ".dll-resources.dat" for name in PLAYER_RESOURCE_ASSEMBLIES],
                ]
                for row in self.phases.values():
                    targets.extend(row["outputs"])
                if "registry" in profile:
                    targets.append(profile["registry"]["file"])
                    artifacts.update(
                        registry_body="apk/assets/bin/Data/" + profile["registry"]["file"],
                        registry_receipt="registry-source/result.json",
                        registry_schemas="registry-source/schemas.json",
                    )
                if "shared_defaults" in profile:
                    targets.append(profile["shared_defaults"]["file"])
            outputs = {"apk/assets/bin/Data/" + target: "apk/assets/bin/Data/" + target for target in targets}
            artifacts.update({artifact: "apk/assets/bin/Data/" + target for target, artifact in PLAYER_RESOURCE_ARTIFACTS.items() if target in targets})
        self.jobs[name] = {"schema": 1, "script": PREFIX + producer + ".py", "arguments": arguments, "needs": needs, "outputs": outputs, "artifacts": artifacts}
        if request is not None:
            self.jobs[name]["request"] = request
        if witnesses:
            self.jobs[name]["cache_witnesses"] = witnesses
        self.profile_files[name] = path
        self.job_profiles[name] = profile
        return name

    def bundle_managed(self, path, profile, active):
        """Generate current witnesses alongside the actual final player registry."""
        if set(profile) != {"schema", "profiles", "request"}:
            raise ValueError("unsupported managed witness release contract")
        name = "recipe/jobs/" + Path(path).stem + ".json"
        needs = [self.build(digest(self.repo / dependency), active) for dependency in profile["profiles"]]
        request = profile["request"]
        token = request["registry_receipt"]["path"]
        match = re.fullmatch(r"\$\{job:([^:}]+):registry_receipt\}", token)
        if match is None or match.group(1) not in needs or owner(self.job_profiles[match.group(1)]) != "player_data":
            raise ValueError("managed witnesses require final player registry artifacts")
        if self.conversion:
            needs.append(self.conversion)
            request = dict(
                request,
                managed_providers=self.artifact_pin(self.conversion, "managed_providers"),
                managed_receipt=self.artifact_pin(self.conversion, "managed_receipt"),
            )
        sources = {"tools/phone-build/metadata/Program.cs"}
        for value in re.findall(r'"([^"\n]*)"', json.dumps(request)):
            if value.startswith("${repo}/"):
                relative = value.removeprefix("${repo}/")
                source = self.repo / relative
                if not source.resolve().is_relative_to(self.repo) or not source.is_file():
                    raise ValueError("managed public input must be a repository file")
                sources.add(relative)
            for dependency, artifact in re.findall(r"\$\{(?:job|job_directory|job_relative|sha256|bytes):([^:}]+):([^}]+)\}", value):
                if dependency not in needs or artifact not in self.jobs[dependency]["artifacts"]:
                    raise ValueError("managed artifact requires a declared source producer")
        self.jobs[name] = dict(
            schema=1,
            script=PREFIX + "bundle_endpoints.py",
            arguments=["--managed", "${request}", "--output", "${output}"],
            request=request,
            needs=sorted(set(needs)),
            outputs={},
            artifacts=dict(
                receipt="result.json",
                runtime_request="runtime-request.json",
                managed_providers="providers.json",
                metadata="metadata.json",
                provider_aliases="provider-aliases.json",
            ),
        )
        self.profile_files[name], self.job_profiles[name], self.public_files[name] = path, profile, sources
        return name

    def source_suppliers(self, pins, sources):
        """Find explicit public pack selectors without opening generated packs."""
        modules = {}

        def module(name):
            if name not in modules:
                path = Path(__file__).resolve().parent.parent / "accepted-output" / (name + ".py")
                spec = importlib.util.spec_from_file_location("graph_source_" + name, path)
                modules[name] = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modules[name])
            return modules[name]

        result = {}
        for pin in sorted(set(pins)):
            if pin not in self.profiles:
                raise ValueError("missing source supplier profile: " + pin)
            path = self.repo / self.profiles[pin]
            if digest(path) != pin:
                raise ValueError("source supplier profile drift: " + self.profiles[pin])
            compressed = str(path).endswith(".jsonl.gz")
            if not compressed:
                profile = json.loads(path.read_bytes())
                producer = owner(profile)
                direct = {"record_produce", "mesh_produce", "avatar_produce", "texture_produce", "sprite_produce"}
                typed_shaders = producer == "shader_produce" and "typed_records" in profile
                registry_remap = producer == "record_remap" and "original_sources" in profile
                if producer not in direct and not typed_shaders and not registry_remap:
                    raise ValueError("source lookup requires direct typed record selectors: " + pin)
            # Reuse preparation's body selectors; type_source is never evidence
            # that a profile produces that original object's serialized body.
            reader = module("record_produce") if compressed else None
            identities = module("bundle_prepare").original_identities(SimpleNamespace(A=reader), path)
            for record, originals in identities.items():
                for source in originals & sources:
                    result.setdefault(source, set()).add((pin, record))
        return result

    def bundle_bindings(self, rows, bundle, member, source_profiles=()):
        """Map selected metadata to fresh pack jobs without reading pack bodies.

        The caller supplies only this member's selected records. Unresolved rows
        remain explicit; the result is not a runnable policy or graph admission.
        Routes, staged endpoints and managed witnesses retain their own owners.
        source_profiles opts into public selector discovery for private record
        pins. A unique producer output replaces the private pack identity while
        selection retains that prior identity; source and destination stay fixed.
        """
        if source_profiles:
            rows = list(rows)
            sources = {tuple(row["source"]) for row in rows if isinstance(row.get("source"), list) and len(row["source"]) == 3}
            candidates = self.source_suppliers(source_profiles, sources)
        else:
            candidates = {}
        bindings, suppliers, profiles, unresolved, destinations, failures = [], {}, set(), [], set(), {}
        for row in rows:
            destination = row.get("destination", [])
            pin = row.get("record")
            record_source = row.get("record_source")
            selection = None
            problem = None
            if len(destination) != 3 or tuple(destination[:2]) != (bundle, member):
                problem = "foreign or missing destination"
            elif tuple(destination) in destinations:
                problem = "duplicate destination"
            elif any(not isinstance(row.get(key), list) or len(row[key]) != 3 for key in ("source", "record_source")):
                problem = "explicit source and record_source identities required"
            elif pin not in self.profiles:
                available = candidates.get(tuple(row["source"]), set())
                matches = {candidate for candidate in available if candidate[1] == tuple(record_source)}
                if not matches:
                    matches = available
                if len(matches) == 1:
                    selection = dict(record=pin, record_source=record_source)
                    pin, supplier_record = next(iter(matches))
                    record_source = list(supplier_record)
                else:
                    problem = "ambiguous source supplier profiles" if matches else "missing source supplier profile"
            if problem is None and pin in failures:
                problem = failures[pin]
            elif problem is None and pin not in suppliers:
                try:
                    job = self.build(pin)
                    required = ("receipt", "objects", "index", "types")
                    if not set(required) <= self.jobs[job]["artifacts"].keys():
                        problem = "supplier requires a final container instead of a typed record pack"
                    else:
                        path = self.profiles[pin]
                        source = self.repo / path
                        suppliers[pin] = dict(
                            name=pin,
                            profile=dict(path="${repo}/" + path, sha256=pin, bytes=source.stat().st_size),
                            **{key: self.artifact_pin(job, key) for key in required},
                        )
                        profiles.add(path)
                except ValueError as error:
                    problem = str(error)
                if problem is not None:
                    failures[pin] = problem
            if len(destination) == 3:
                destinations.add(tuple(destination))
            if problem is not None:
                failure = dict(destination=destination, record=pin, reason=problem)
                if selection is not None:
                    failure["selection"] = selection
                if source_profiles and isinstance(row.get("source"), list) and len(row["source"]) == 3:
                    failure["candidates"] = [
                        dict(supplier=candidate, record_source=list(record)) for candidate, record in sorted(candidates.get(tuple(row["source"]), ()))
                    ]
                unresolved.append(failure)
            else:
                binding = {key: row[key] for key in ("destination", "source")} | dict(supplier=pin, record_source=record_source)
                if selection is not None:
                    binding["selection"] = selection
                bindings.append(binding)
        return dict(bindings=bindings, suppliers=[suppliers[key] for key in sorted(suppliers)], profiles=sorted(profiles), unresolved=unresolved)

    def bundle_preload(self, path, profile, active):
        """Bind fresh suppliers and actual final containers to a signed policy."""
        if set(profile) != {"schema", "profiles", "request"}:
            raise ValueError("unsupported bundle release contract")
        name = "recipe/jobs/" + Path(path).stem + ".json"
        needs = [self.build(digest(self.repo / dependency), active) for dependency in profile["profiles"]]
        request = profile["request"]
        if self.conversion:
            request = dict(request, codec=INSTALLED_BUNDLE_CODEC)
        policy = request["policy"]
        sources = set()

        def visit(value):
            if isinstance(value, dict):
                for item in value.values():
                    visit(item)
                if isinstance(value.get("path"), str) and value["path"].startswith("${repo}/"):
                    source = self.repo / value["path"].removeprefix("${repo}/")
                    if "sha256" in value and (digest(source) != value["sha256"] or source.stat().st_size != value["bytes"]):
                        raise ValueError("bundle public input pin differs")
            elif isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, str):
                if value.startswith("${repo}/"):
                    relative = value.removeprefix("${repo}/")
                    source = self.repo / relative
                    if source.resolve().is_relative_to(self.repo) is False or not source.is_file():
                        raise ValueError("bundle public input must be a repository file")
                    sources.add(relative)
                for dependency, artifact in re.findall(r"\$\{(?:job|job_directory|job_relative|sha256|bytes):([^:}]+):([^}]+)\}", value):
                    if dependency not in needs or artifact not in self.jobs[dependency]["artifacts"]:
                        raise ValueError("bundle artifact requires a declared source producer")

        visit(request)
        # Indirect managed witnesses must come from generators whose source and
        # input closure the dispatcher can invalidate, rather than retained JSON.
        managed = request["managed_inputs"]
        for key, value in managed.items():
            if key != "properties_sdk" and not value["path"].startswith("${job:"):
                raise ValueError("bundle managed witnesses require generated artifacts")
        if managed:
            registry_jobs = set()
            for key in ("body", "receipt", "schemas"):
                match = re.fullmatch(r"\$\{job:([^:}]+):registry_" + key + r"\}", managed["registry_" + key]["path"])
                if match is None:
                    raise ValueError("bundle registry requires final player artifacts")
                registry_jobs.add(match.group(1))
            if len(registry_jobs) != 1 or owner(self.job_profiles[next(iter(registry_jobs))]) != "player_data":
                raise ValueError("bundle registry must come from one final player producer")
        final = ("canonical/" if "canonical" in policy else "emitted/") + policy["bundle"] + ".bundle"
        self.jobs[name] = dict(
            schema=1,
            script=PREFIX + "bundle_preload.py",
            arguments=["--release", "${request}", "--output", "${output}"],
            request=dict(profile, request=request),
            needs=sorted(set(needs)),
            outputs={"payload/" + policy["bundle"]: final},
            artifacts={"receipt": "result.json", "catalog_profile": "catalog-profile.json", "catalog_bundle": final},
        )
        self.profile_files[name], self.job_profiles[name], self.public_files[name] = path, profile, sources

        def include(job):
            if job in self.bundle_release_jobs:
                return
            self.bundle_release_jobs.add(job)
            for dependency in self.jobs[job]["needs"]:
                include(dependency)

        include(name)
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
            for path in self.public_files.get(job, ()):
                (recipes if path.startswith("recipe/") else producers).add(path)
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

    def catalog_complete(self, selected_jobs, request_path):
        """Bind the source catalog to final containers and the embedded bootstrap."""
        request = json.loads((self.repo / request_path).read_text())
        common = {"schema", "input_id", "attempt"}
        if set(request) - common not in ({"metadata"}, {"projection"}) or not common <= request.keys() or request["schema"] != "owner-catalog-inputs-v1":
            raise ValueError("unsupported catalog request template")
        profiles, bundles, needs, registries = [], {}, [], []
        resources = {}
        if "projection" in request:
            if not self.conversion:
                raise ValueError("catalog projection requires original-input code conversion")
            policy = (self.repo / request["projection"]).resolve(strict=True)
            relative = policy.relative_to(self.repo).as_posix()
            self.jobs[self.conversion]["artifacts"]["original_catalog"] = "managed-production/original-catalog.json"
            request["projection"] = {
                "source": self.artifact_pin(self.conversion, "original_catalog"),
                "policy": dict(path="${repo}/" + relative, sha256=digest(policy), bytes=policy.stat().st_size),
            }
            needs.append(self.conversion)
        else:
            metadata = request["metadata"]
            if set(metadata) != {"path", "sha256", "bytes"}:
                raise ValueError("unsupported catalog metadata pin")
            if not metadata["path"].startswith("${input:") or not metadata["path"].endswith("}"):
                raise ValueError("catalog metadata must use a private input binding")
        for job in sorted(set(selected_jobs)):
            profile = self.job_profiles[job]
            descriptor = self.jobs[job]
            if owner(profile) == "player_data":
                bootstrap = [row["recipe"] for row in profile.get("text_assets", {}).get("files", []) if row.get("name") == "WholeCatalogBootstrap"]
                if len(bootstrap) != 1:
                    raise ValueError("catalog requires one embedded bootstrap")
                pin = bootstrap[0]
                path = self.repo / "recipe" / pin["path"]
                if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
                    raise ValueError("catalog bootstrap pin differs")
                identity = json.loads(path.read_text())
                if any(identity[key] != request[key] for key in ("input_id", "attempt")):
                    raise ValueError("catalog/bootstrap identity differs")
                target = "apk/assets/bin/Data/" + profile["registry"]["file"]
                descriptor["artifacts"]["catalog_registry"] = descriptor["outputs"][target]
                registries.append(self.artifact_pin(job, "catalog_registry"))
                needs.append(job)
            for target, artifact in PLAYER_RESOURCE_ARTIFACTS.items():
                if artifact in descriptor["artifacts"]:
                    member = Path(target).name
                    if member in resources:
                        raise ValueError("duplicate catalog player resource: " + member)
                    resources[member] = self.artifact_pin(job, artifact)
                    needs.append(job)
            if owner(profile) == "bundle_preload":
                bundle = profile["request"]["policy"]["bundle"]
                profiles.append(self.artifact_pin(job, "catalog_profile"))
                if bundle in bundles:
                    raise ValueError("duplicate final catalog bundle")
                bundles[bundle] = self.artifact_pin(job, "catalog_bundle")
                needs.append(job)
                continue
            if owner(profile) != "object_produce" or "original_bundle" in profile:
                continue
            path = self.profile_files[job]
            source = self.repo / path
            profiles.append(dict(path="${repo}/" + path, sha256=digest(source), bytes=source.stat().st_size))
            bundles[profile["bundle"]["name"]] = self.artifact_pin(job, "catalog_bundle")
            needs.append(job)
        if len(registries) != 1 or not bundles:
            raise ValueError("catalog requires final bundles and one selected player registry")
        request.update(profiles=profiles, bundles=bundles, registry=registries[0])
        if resources:
            request["resources"] = resources
        name = "recipe/jobs/owner-catalog-complete.json"
        self.jobs[name] = {
            "schema": 1,
            "script": PREFIX + "catalog_complete.py",
            "arguments": ["--inputs", "${request}", "--output", "${output}"],
            "request": request,
            "needs": sorted(set(needs)),
            "outputs": {"payload/whole-catalog.json": "whole-catalog.json"},
            "artifacts": {"receipt": "result.json"},
        }
        self.profile_files[name] = request_path
        if "projection" in request:
            self.public_files[name] = [relative]
        self.job_profiles[name] = {}
        return name

    @staticmethod
    def artifact_pin(job, artifact):
        return {
            "path": "${job:" + job + ":" + artifact + "}",
            "sha256": "${sha256:" + job + ":" + artifact + "}",
            "bytes": "${bytes:" + job + ":" + artifact + "}",
        }

    def fixed_code_sources(self, target):
        profile = target.get("profile", "")
        source = target.get("source", "")
        if not profile.startswith("${repo}/") or not (source == "${repo}" or source.startswith("${repo}/")):
            raise ValueError("code request must select a public target profile and authored source root")
        profile_path = self.repo / profile.removeprefix("${repo}/")
        source_root = self.repo if source == "${repo}" else self.repo / source.removeprefix("${repo}/")
        if any(path.resolve(strict=True) != path or not path.is_relative_to(self.repo) for path in (profile_path, source_root)):
            raise ValueError("code target profile and source must be canonical public paths")
        selected = json.loads(profile_path.read_text())
        paths = [profile_path.relative_to(self.repo).as_posix()]
        paths.extend((source_root / "recipe" / policy).relative_to(self.repo).as_posix() for policy in ("build-entry-inputs.json", "runtime-sources.json"))
        for relative, expected in selected["source_files"].items():
            path = source_root / relative
            if path.resolve(strict=True) != path or not path.is_relative_to(source_root) or digest(path) != expected:
                raise ValueError("code target authored source drift: " + relative)
            paths.append(path.relative_to(self.repo).as_posix())
        return paths

    def current_code_sources(self, *, signed_audio=False):
        runtime = "recipe/runtime-sources.json"
        audio_manifest = "recipe/original-audio-owner-sources.json"
        audio = self.repo / "tools/unity/support/audio"
        return [
            "environment/toolchain.json",
            "recipe/build-entry-inputs.json",
            runtime,
            "recipe/project-layout.json",
            # The shared rebuild helpers load these owner tables on import.
            "recipe/project-inputs.json",
            "recipe/importer-identities.json",
            audio_manifest,
            "recipe/owner-audio-prefab.json",
            "recipe/wwise-android-abi.json",
            "recipe/wwise-init-android.json" if signed_audio else "tools/phone-build/legacy/transform_init.py.txt",
            "android/Assets/LabDiagnostics.cs",
            *["tools/unity/" + path for path in json.loads((self.repo / runtime).read_text())],
            *[
                (audio / path).resolve().relative_to(self.repo).as_posix()
                for path in json.loads((self.repo / audio_manifest).read_text())["owner_source_hashes"]
            ],
            *[
                "tools/unity/support/audio/generators/" + name
                for name in ("generate_accepted_request_pin.py", "generate_runtime_stage_pin.py", "original_media_plan.py", "stage_original_game_banks.py")
            ],
            "tools/unity/support/audio/managed-producer/produce.py",
            *[
                "tools/unity/support/audio/managed-producer/" + name + suffix
                for name in (
                    "source/owner-api/OriginalOwnerProbeObserver",
                    "tools/composed/ComposedGameCecilTransform",
                    "tools/owner-api/OwnerApiCecilTransform",
                )
                for suffix in (".cs", ".csproj")
            ],
            "tools/wwise-android-abi/generate.py",
            *["tools/wwise-android-abi/" + name + suffix for name in ("CecilAbiTool", "CecilAbiWriter") for suffix in (".cs", ".csproj")],
        ]

    def code_conversion(self, request_path, audio_stage_receipt=None):
        """Run original-input managed production and preserve its converter cohort."""
        request = json.loads((self.repo / request_path).read_text())
        if request.get("output") != "${output}" or "source_inputs" not in request:
            raise ValueError("code request must select original source inputs and the dispatcher output")
        paths = self.fixed_code_sources(request["target"]) if "target" in request else self.current_code_sources(signed_audio=audio_stage_receipt is not None)
        paths += [
            "recipe/owner-managed-code.json",
            "recipe/owner-player-code.json",
            "recipe/owner-native-arm64.json",
            "recipe/original-assemblies.json",
            "recipe/assembly-transforms.json",
            "recipe/owner-public-tools.json",
            PACKAGE_POLICY,
        ]
        transforms = json.loads((self.repo / "recipe/assembly-transforms.json").read_text())
        paths.extend(transforms["tool_sources"])
        name = "recipe/jobs/owner-code-conversion.json"
        cache_witnesses = request.pop("cache_witnesses", [])
        outputs = {}
        if audio_stage_receipt is not None:
            if "target" in request:
                raise ValueError("audio packaging requires the current audio-bearing code producer")
            receipt = json.loads(Path(audio_stage_receipt).read_text())
            bank_root = "Audio/GeneratedSoundBanks/Android"
            banks = [row["filename"] for row in receipt["outputs"]]
            media = [row["relative_path"] for row in receipt["streamed_media"]]
            if (
                receipt.get("schema") != "original-game-wwise-bank-cohort-r2"
                or receipt.get("output_relative_directory") != bank_root
                or "Init.bnk" not in banks
                or len(banks) != len(set(banks))
                or len(media) != len(set(media))
                or any(not re.fullmatch(r"[A-Za-z0-9_.-]+\.bnk", name) for name in banks)
                or any(not re.fullmatch(r"Media/[0-9]+\.wem", name) for name in media)
            ):
                raise ValueError("canonical Wwise stage membership required")
            members = sorted([*banks, *media])
            request["source_inputs"].pop("decoder", None)
            request["source_inputs"]["dotnet"] = "${native}/" + INSTALLED_CODE_TOOLS["dotnet"]
            request["android_tools"] = {name: "${native}/" + path for name, path in INSTALLED_CODE_TOOLS.items()}
            request["android_tools"]["resource_dir"] = "${installed_runtime}/clang/21"
            cache_witnesses = sorted(set(cache_witnesses) | INSTALLED_CODE_WITNESSES | {"${native}/libhostfxr10.so"})
            request["audio_members"] = members
            outputs = {
                "apk/assets/stage-receipt.json": "managed-production/staged/stage-receipt.json",
                "apk/lib/arm64-v8a/libAkSoundEngine.so": "managed-production/supplied-sdk/libAkSoundEngine.so",
                **{f"apk/assets/{bank_root}/{member}": f"managed-production/staged/{bank_root}/{member}" for member in members},
            }
        if self.package_inputs:
            request["source_inputs"]["packages"] = self.artifact_pin(self.package_inputs, "packages")["path"]
        self.jobs[name] = {
            "schema": 1,
            "script": "tools/phone-build/owner-code/produce.py",
            "arguments": ["${request}", "--stop-after-conversion"],
            "request": request,
            "needs": [self.package_inputs] if self.package_inputs else [],
            "outputs": outputs,
            "artifacts": {
                "receipt": "backend/converter/result.json",
                "metadata": "backend/converter/data/Metadata/global-metadata.dat",
                "sources": "backend/sources",
            },
        }
        if cache_witnesses:
            self.jobs[name]["cache_witnesses"] = cache_witnesses
        self.profile_files[name] = request_path
        self.public_files[name] = paths
        self.job_profiles[name] = {}
        return name

    def player_conversion(self, needs):
        """Expose the converter resources and regular managed outputs used by the player."""
        conversion = self.jobs[self.conversion]
        managed = "managed-production/"
        conversion["artifacts"].update(
            managed_receipt=managed + "result.json",
            managed_providers=managed + "providers.json",
            managed_sources=managed + "gameplay/inputs.json",
            managed_gameplay=managed + "gameplay/postprocessed/Assembly-CSharp.dll",
            managed_packages=managed + "packages/postprocessed",
            managed_maps=managed + "maps",
            managed_support=managed + "support",
            **{"resource_" + assembly: "backend/converter/data/Resources/" + assembly + ".dll-resources.dat" for assembly in PLAYER_RESOURCE_ASSEMBLIES},
        )
        original_request = conversion["request"]
        packages = original_request["source_inputs"]["packages"]
        request = {"source_inputs": {"packages": packages}}
        if "target" in original_request:
            # The fixed registry also needs the importer-only TestRunner and MCP
            # sources, which the compiler package set does not select.
            request["source_inputs"]["packages"] = json.loads((self.repo / self.profile_files[self.conversion]).read_text())["source_inputs"]["packages"]
            request["target"] = {"source": original_request["target"]["source"]}
        else:
            conversion["artifacts"]["managed_package_inputs"] = managed + "packages/inputs.json"
            if self.package_inputs:
                needs.append(self.package_inputs)
        return [
            "--converter",
            "${job_directory:" + self.conversion + ":receipt}",
            "--converter-receipt-sha256",
            "${sha256:" + self.conversion + ":receipt}",
            "--code-request",
            "${request}",
            "--managed-production",
            "${job_directory:" + self.conversion + ":managed_receipt}",
        ], request

    def package_preparation(self):
        name = "recipe/jobs/owner-package-inputs.json"
        spec = importlib.util.spec_from_file_location("graph_package_producer", self.repo / PACKAGE_PRODUCER)
        packages = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packages)
        self.jobs[name] = {
            "schema": 1,
            "script": PACKAGE_PRODUCER,
            "arguments": ["${request}", "--prepare-inputs"],
            "request": {"archives": PACKAGE_ARCHIVES, "output": "${output}"},
            "needs": [],
            "outputs": {},
            "artifacts": {"receipt": "result.json", "packages": "packages"},
            "cache_witnesses": [f"{PACKAGE_ARCHIVES}/{archive}" for archive in sorted(packages.ARCHIVES)],
        }
        self.public_files[name] = [PACKAGE_POLICY]
        self.job_profiles[name] = {}
        return name

    def native_code(self, request_path, conversion=None):
        """Produce native code and its matching metadata from one converter cohort."""
        request = json.loads((self.repo / request_path).read_text())
        if request.get("output") != "${output}":
            raise ValueError("native request must use the dispatcher output")
        arguments = ["${request}"]
        cache_witnesses = request.pop("cache_witnesses", [])
        if conversion:
            converted = self.jobs[conversion]["request"]
            receipt = self.artifact_pin(conversion, "receipt")
            request.update(
                converter_receipt=receipt["path"],
                converter_receipt_sha256=receipt["sha256"],
                metadata=self.artifact_pin(conversion, "metadata")["path"],
                sources=self.artifact_pin(conversion, "sources")["path"],
                sources_compressed=True,
            )
            if "android_tools" in converted and not {"android_tools", "linux_tools"} & request.keys():
                request.update(sdk_install=converted["sdk_install"], android_tools=converted["android_tools"])
                cache_witnesses = sorted(set(cache_witnesses) | INSTALLED_CODE_WITNESSES)
            arguments.append("--from-conversion")
        name = "recipe/jobs/owner-native-code.json"
        self.jobs[name] = {
            "schema": 1,
            "script": "tools/phone-build/owner-code/native.py",
            "arguments": arguments,
            "request": request,
            "needs": [conversion] if conversion else [],
            "outputs": {
                "apk/lib/arm64-v8a/libil2cpp.so": "libil2cpp.so",
                "apk/assets/bin/Data/Managed/Metadata/global-metadata.dat": "global-metadata.dat",
            },
            "artifacts": {"receipt": "result.json"},
        }
        if cache_witnesses:
            self.jobs[name]["cache_witnesses"] = cache_witnesses
        self.profile_files[name] = request_path
        policy = "recipe/owner-native-arm64.json"
        self.job_profiles[name] = {"authored_inputs": {policy: digest(self.repo / policy)}}
        return name

    def conversion_burst(self, request_path):
        """Build Burst and check its preservation roots before stripping the same providers."""
        request = json.loads((self.repo / request_path).read_text())
        if request.get("output") != "${output}" or not all(isinstance(request.get(name), dict) for name in ("burst_tools", "linux_tools")):
            raise ValueError("signed Android Burst requires the dispatcher output and explicit Burst and Linux tools")
        conversion = self.jobs[self.conversion]
        conversion["request"].update(burst_tools=request["burst_tools"], linux_tools=request["linux_tools"])
        conversion["outputs"]["apk/lib/arm64-v8a/lib_burst_generated.so"] = "backend/burst/lib_burst_generated.so"
        conversion["artifacts"]["burst_preservation"] = "backend/burst/burst.xml"
        conversion["cache_witnesses"] = sorted(set(conversion["cache_witnesses"]) | set(request.get("cache_witnesses", [])))
        self.public_files[self.conversion].extend((request_path, "recipe/owner-j850-code.json"))

    def sdk_extraction(self):
        name = "recipe/jobs/owner-sdk-inputs.json"
        self.jobs[name] = {
            "schema": 1,
            "script": PREFIX + "sdk_inputs.py",
            "arguments": ["--component", ANDROID_COMPONENT, "--output", "${output}", "--android-package"],
            "needs": [],
            "outputs": {},
            "artifacts": {"receipt": "result.json", "android_player": "PlaybackEngines/AndroidPlayer"},
            "cache_witnesses": [ANDROID_COMPONENT],
        }
        self.job_profiles[name] = {}
        return name

    def sdk_texture_extraction(self):
        name = "recipe/jobs/owner-sdk-texture-input.json"
        if name not in self.jobs:
            self.jobs[name] = {
                "schema": 1,
                "script": PREFIX + "sdk_inputs.py",
                "arguments": ["--component", LINUX_COMPONENT, "--output", "${output}", "--linux-texture"],
                "needs": [],
                "outputs": {},
                "artifacts": {"receipt": "result.json", "library": "etccompress.so"},
                "cache_witnesses": [LINUX_COMPONENT],
            }
            self.job_profiles[name] = {}
        return name

    def sdk_shader_extraction(self):
        name = "recipe/jobs/owner-sdk-shader-inputs.json"
        if name not in self.jobs:
            self.jobs[name] = {
                "schema": 1,
                "script": PREFIX + "sdk_inputs.py",
                "arguments": ["--component", LINUX_COMPONENT, "--output", "${output}", "--linux-shader"],
                "needs": [],
                "outputs": {},
                "artifacts": {"receipt": "result.json", "data": "Data"},
                "cache_witnesses": [LINUX_COMPONENT],
            }
            self.job_profiles[name] = {}
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
        cache_witnesses = request.pop("cache_witnesses", [])
        tools = [*(request[key] for key in ("android_jar", "aapt", "java", "javac")), *request["jars"].values()]
        cache_witnesses = sorted(set(cache_witnesses) | {path for path in tools if path.startswith(("${inputs}/", "${installed_runtime}/", "${native}/"))})
        if self.android_sdk:
            request["sdk"] = self.artifact_pin(self.android_sdk, "android_player")["path"]
        self.jobs[name] = {
            "schema": 1,
            "script": script,
            "arguments": ["--request", "${request}"],
            "request": request,
            "needs": [self.android_sdk] if self.android_sdk else [],
            "outputs": {"apk/" + target: "resources/apk/" + target for target in sorted(sdk.SDK_ENTRIES)},
            "artifacts": {"receipt": "result.json"},
        }
        if cache_witnesses:
            self.jobs[name]["cache_witnesses"] = cache_witnesses
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

    def attach_install_plan(self, index, *, required_inputs, workspace_bytes, bindings):
        """Assign producers to the earliest install stage that has their inputs."""

        def load(name):
            path = Path(__file__).with_name(name + ".py")
            spec = importlib.util.spec_from_file_location("graph_" + name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        admission, flow = load("install_inputs"), load("install_flow")
        production = {stage: [] for stage in flow.PRODUCTION}
        positions = {}

        def assign(name):
            if name not in positions:
                job = self.jobs[name]
                producer = Path(job["script"]).stem
                minimum = {"texture_produce": 1, "native": 2, "sdk_package": 2}.get(producer, 0)
                position = max(minimum, max((assign(parent) for parent in job["needs"]), default=0))
                positions[name] = position
                production[flow.PRODUCTION[position]].append(name)
            return positions[name]

        for row in index["entries"].values():
            assign(row["job"])
        required_bindings = {binding for name in positions for binding in re.findall(r"\$\{input(?:_relative|_sha256)?:([^}]+)\}", json.dumps(self.jobs[name]))}
        unbound = sorted(required_bindings - bindings.keys() - {"inventory"})
        if unbound:
            raise ValueError("install plan lacks admitted input bindings: " + ", ".join(unbound))
        plan = {
            "schema": 1,
            "required_inputs": required_inputs,
            "workspace_bytes": workspace_bytes,
            "configuration": {"bindings": bindings},
            "stages": [{"id": stage, "title": stage.title(), "jobs": production.get(stage, [])} for stage in flow.STAGES],
        }
        files = index["files"].keys() | self.jobs.keys() | {required_inputs}
        admission.validate_plan(plan, files)
        manifest = admission.UPDATES.within(self.repo, required_inputs, exists=True)
        admission.input_description(plan, admission.UPDATES.public().load_json(manifest.read_bytes()))
        flow.validate_plan(plan, {**index, "files": files}, self.jobs.__getitem__)
        index["files"][required_inputs] = digest(manifest)
        index["install_plan"] = plan

    def compile(
        self,
        selected,
        *,
        bundle_manifest=False,
        code_request=None,
        native_request=None,
        sdk_request=None,
        sdk_component=False,
        package_archives=False,
        burst_request=None,
        catalog_request=None,
        audio_stage_receipt=None,
    ):
        entries = {}
        if package_archives and not code_request:
            raise ValueError("package archives require an original-input code request")
        if audio_stage_receipt is not None and not (code_request and native_request):
            raise ValueError("audio packaging requires code conversion and matching native production")
        self.package_inputs = self.package_preparation() if package_archives else None
        self.conversion = self.code_conversion(code_request, audio_stage_receipt) if code_request else None
        if audio_stage_receipt is not None and burst_request:
            self.conversion_burst(burst_request)
        self.android_sdk = self.sdk_extraction() if sdk_component else None
        selected_jobs = [self.build(digest(self.repo / path)) for path in selected]
        # Referenced donors and staged bundles remain runtime dependencies. Ship
        # their actual containers, while pack-only suppliers remain artifacts.
        selected_jobs = list(dict.fromkeys([*selected_jobs, *sorted(job for job in self.bundle_release_jobs if self.jobs[job]["outputs"])]))
        startup = "recipe/jobs/owner-startup-metadata.json"
        if startup in self.jobs:
            selected_jobs.append(startup)
        catalog_jobs = list(selected_jobs)
        if catalog_request:
            selected_jobs.append(self.catalog_complete(catalog_jobs, catalog_request))
        if bundle_manifest:
            selected_jobs.append(self.bundle_manifest(catalog_jobs))
        if self.conversion and not native_request and not any(self.conversion in job["needs"] for job in self.jobs.values()):
            raise ValueError("code conversion requires a player or native request consumer")
        if native_request:
            selected_jobs.append(self.native_code(native_request, self.conversion))
        if audio_stage_receipt is not None and self.conversion not in selected_jobs:
            selected_jobs.append(self.conversion)
        if sdk_request:
            selected_jobs.append(self.sdk_package(sdk_request))
        if burst_request and audio_stage_receipt is None:
            selected_jobs.append(self.burst_code(burst_request))
        if self.android_sdk and not any(self.android_sdk in job["needs"] for job in self.jobs.values()):
            raise ValueError("Android SDK component requires a player or SDK package consumer")
        for job in selected_jobs:
            entry = self.entry(job)
            for output in self.jobs[job]["outputs"]:
                if output in entries:
                    raise ValueError("multiple selected profiles produce " + output)
                entries[output] = entry
        if not entries:
            raise ValueError("select at least one complete output profile")
        for name, job in self.jobs.items():
            if job["script"] == PREFIX + "sdk_inputs.py":
                # The extractor imports only the standard library. A producer
                # change elsewhere in the release need not unpack the same SDK.
                job["source_files"] = [name, job["script"]]
            elif name == self.package_inputs:
                job["source_files"] = [name, PACKAGE_PRODUCER, PACKAGE_POLICY]
            else:
                closure = self.entry(name)
                job["source_files"] = sorted(set(closure["recipe_files"]) | set(closure["producer_files"]))
        files = {path for row in entries.values() for key in ("recipe_files", "producer_files") for path in row[key] if path not in self.jobs}
        return {
            "schema": 1,
            "entries": entries,
            "files": {path: digest(self.repo / path) for path in sorted(files)},
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--profile", action="append", default=[], help="repo-relative complete output profile; repeat for a cohort")
    parser.add_argument("--player-phases", help="repo-relative complete optional player phase/output declaration")
    parser.add_argument(
        "--bundle-manifest",
        action="store_true",
        help="generate the native manifest from every selected payload bundle; missing native dependencies fail production",
    )
    parser.add_argument("--catalog-request", help="repo-relative source catalog metadata template; validates actual final containers and runtime registry")
    parser.add_argument(
        "--code-request", help="repo-relative original-input code request; supplies fresh conversion to player, managed witness and native jobs"
    )
    parser.add_argument("--native-request", help="repo-relative native request; emits matching library and metadata from fresh or acquired conversion")
    parser.add_argument("--audio-stage-receipt", type=Path, help="private stage receipt used only to declare relative APK audio member names")
    parser.add_argument("--sdk-request", help="repo-relative SDK request template; emits Android resources, dex and engine libraries")
    parser.add_argument("--sdk-component", action="store_true", help="extract the private owner-supplied Android Support component for player and package jobs")
    parser.add_argument("--package-archives", action="store_true", help="prepare compile-selected sources from owner Unity package archives before conversion")
    parser.add_argument("--burst-request", help="repo-relative managed/source request template; compiles Burst and retains preservation roots")
    parser.add_argument("--extra-arguments", type=Path, help="JSON producer name -> additional CLI argv, with dispatcher substitutions")
    parser.add_argument("--install-plan", type=Path, help="JSON with required_inputs, workspace_bytes and original input bindings")
    parser.add_argument("--output", type=Path, required=True, help="new public job staging root; overlay into a release source checkout")
    args = parser.parse_args()
    graph = Graph(args.repo, json.loads(args.extra_arguments.read_text()) if args.extra_arguments else {}, args.player_phases)
    index = graph.compile(
        args.profile,
        bundle_manifest=args.bundle_manifest,
        catalog_request=args.catalog_request,
        code_request=args.code_request,
        native_request=args.native_request,
        sdk_request=args.sdk_request,
        sdk_component=args.sdk_component,
        package_archives=args.package_archives,
        burst_request=args.burst_request,
        audio_stage_receipt=args.audio_stage_receipt,
    )
    if args.install_plan:
        graph.attach_install_plan(index, **json.loads(args.install_plan.read_text()))
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
