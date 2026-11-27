"""Run the existing whole-player backend in the installed headless tool host.

Caller-supplied original files and SDK remain private app data, never APK assets.
Select fixed-target source production or a supplied-provider infrastructure control.
"""

import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time


def package_job(request, inputs, runtime, installed, native):
    specification = importlib.util.spec_from_file_location("android_owner_apk", runtime / "repo/tools/phone-build/owner-apk/build_owner_apk.py")
    owner = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(owner)
    output = inputs / native.relative(request["output"])
    if not output.resolve().is_relative_to(inputs) or output.exists():
        raise ValueError("new private APK output required")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    selection = request.get("packaging", request.get("signing"))
    if (set(selection) - {"drift"} if "packaging" in request else set(selection)) != (
        {"targets", "manifest", "code", "key_directory", "version_code"} if "packaging" in request else {"unsigned", "key_directory"}
    ):
        raise ValueError("explicit APK assembly/signing inputs required")

    def path(name):
        value = (inputs / native.relative(name)).resolve()
        if not value.is_relative_to(inputs):
            raise ValueError("APK input escapes private owner files")
        return str(value)

    java = str(installed / "libjavatool.so")
    if "packaging" in request:
        build = {
            "targets": path(selection["targets"]),
            "manifest": path(selection["manifest"]),
            "manifest_sha256": owner.PROFILE,
            "code": {name: path(value) for name, value in selection["code"].items()},
            "frontend": str(runtime / "repo/launcher"),
            "wire_helper": str(runtime / "repo/scripts/lab/phone_apk.py"),
            "java": java,
            "javac": str(installed / "libjavactool.so"),
            "android_jar": str(runtime / "java-tools/android.jar"),
            "d8_jar": str(runtime / "java-tools/d8.jar"),
            "version_code": selection["version_code"],
        }
        if "drift" in selection:
            build["drift"] = {
                target: {name: {**row, "path": path(row["path"])} for name, row in receipts.items()} for target, receipts in selection["drift"].items()
            }
        native.write(output / "assembly-request.json", build)
        owner.build(output / "assembly-request.json", output / "assembly")
        unsigned = str(output / "assembly/owner-unsigned.apk")
    else:
        unsigned = path(selection["unsigned"])
    signing = {
        "unsigned": unsigned,
        "java": java,
        "keytool": str(installed / "libkeytool.so"),
        "zipalign": str(installed / "libzipalign.so"),
        "apksigner_jar": str(runtime / "java-tools/apksigner.jar"),
        "key_directory": path(selection["key_directory"]),
    }
    native.write(output / "sign-request.json", signing)
    result = owner.sign(output / "sign-request.json", output / "signing")
    ready = {"apk": str(output / "signing/signed.apk"), "sha256": result["apk_sha256"], "bytes": result["apk_bytes"]}
    native.write(output / "ready.json", ready)
    (output / "ready.json").replace(inputs / "owner-apk-ready.json")
    return result


def android_sdk_job(request, inputs, runtime, installed, native):
    """Produce generic Android entries with the pinned SDK/public tools."""
    selection = request["android_sdk"]
    if set(selection) != {"sdk", "android_jar", "aapt", "jars", "loader_root", "library_dirs"}:
        raise ValueError("explicit generic Android SDK/tool inputs required")
    spec = importlib.util.spec_from_file_location("owner_sdk_package", runtime / "repo/tools/phone-build/accepted-output/sdk_package.py")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)

    def path(value):
        result = (inputs / native.relative(value)).resolve(strict=True)
        if not result.is_relative_to(inputs):
            raise ValueError("Android SDK input escapes private owner files")
        return str(result)

    output = inputs / native.relative(request["output"])
    if output.resolve() != output or not output.is_relative_to(inputs):
        raise ValueError("Android SDK output escapes private owner files")
    output.parent.mkdir(parents=True, exist_ok=True)
    production = {name: path(selection[name]) for name in ("sdk", "android_jar", "aapt")}
    production.update(
        java=str(installed / "libjavatool.so"),
        javac=str(installed / "libjavactool.so"),
        jars={name: path(value) for name, value in selection["jars"].items()},
        output=str(output),
        aapt_prefix=[
            str(installed / "libqemu-x86_64.so"),
            "-L",
            path(selection["loader_root"]),
            "-E",
            "LD_LIBRARY_PATH=" + ":".join(path(p) for p in selection["library_dirs"]),
            "-E",
            "LC_ALL=C",
        ],
    )
    return owner.produce(production)


def texture_job(request, inputs, runtime, installed, native):
    """Run the existing source texture owner using private inputs and installed tools."""
    selection = request["textures"]
    if set(selection) - {"jpeg_codec", "etc_codec", "pixels_codec", "sdk_toolchain", "resume"} != {"profile", "profile_sha256", "pc"}:
        raise ValueError("explicit source texture profile and original inputs required")
    resume = selection.get("resume", False)
    if not isinstance(resume, bool):
        raise ValueError("texture resume selector must be boolean")

    def path(root, name, *, exists=True):
        value = (root / native.relative(name)).resolve(strict=exists)
        if not value.is_relative_to(root.resolve()):
            raise ValueError("texture path escapes its owner root")
        return value

    repo = runtime / "repo"
    spec = importlib.util.spec_from_file_location("android_owner_texture", repo / "tools/phone-build/accepted-output/texture_produce.py")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    options = {"resume": resume}
    for name in ("jpeg_codec", "etc_codec", "pixels_codec", "sdk_toolchain"):
        if name in selection:
            pin = selection[name]
            if set(pin) != {"path", "sha256"}:
                raise ValueError("explicit pinned texture tool required")
            # Executable native providers must reside in PackageManager's
            # read-only library directory; the SDK descriptor is private data.
            options[name] = path(inputs if name == "sdk_toolchain" else installed, pin["path"])
            options[name + "_sha256"] = pin["sha256"]
    output = path(inputs, request["output"], exists=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    return owner.produce(path(repo, selection["profile"]), selection["profile_sha256"], path(inputs, selection["pc"]), output, **options)


def prepare_inventory(inputs, native):
    work, game = inputs / "work", inputs / "game"
    inventory_path = work / "inventory/files.json"
    inventory = json.loads(inventory_path.read_text())
    for row in inventory["files"]:
        path = game / native.relative(row["path"])
        stats = path.stat()
        if native.sha(path) != row["sha256"] or stats.st_size != row["size"]:
            raise ValueError("copied original game input differs")
        row["mtime_ns"] = stats.st_mtime_ns
    inventory_path.write_text(json.dumps(inventory) + "\n")
    (work / "config").mkdir(exist_ok=True)
    (work / "config/local.json").write_text(json.dumps({"game_path": str(game)}) + "\n")


SIGNED_RELEASE_FIELDS = {"bundle", "envelope", "public_key", "key_id", "output"}
SIGNED_ARTIFACT_FIELDS = SIGNED_RELEASE_FIELDS | {"job", "artifact", "bindings"}


def signed_release_job(request, inputs, runtime, installed, native):
    """Qualify an artifact or the native cohort through the signed dispatcher."""
    owner = runtime / "repo/tools/phone-build/owner-apk"
    spec = importlib.util.spec_from_file_location("android_signed_release_jobs", owner / "release_jobs.py")
    jobs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jobs)
    updates = jobs.UPDATES
    publisher = updates.public()
    envelope = publisher.load_json(updates.within(inputs, request["envelope"], exists=True).read_bytes())
    key = updates.within(inputs, request["public_key"], exists=True).read_bytes()
    release = publisher.verify_envelope(envelope, {request["key_id"]: key})
    artifact_only = set(request) == SIGNED_ARTIFACT_FIELDS
    config = {"bindings": request["bindings"]} if artifact_only else {}
    identity = updates.input_identity(inputs, config)
    if not artifact_only:
        prepare_inventory(inputs, native)

    output = updates.within(inputs / "work", request["output"])
    output.mkdir(mode=0o700, parents=True)
    started = time.monotonic()
    free = shutil.disk_usage(output).free
    result = {"success": False}
    try:
        repo = output / "verified-repo"
        bundle = updates.within(inputs, request["bundle"], exists=True)
        index = updates.extract_bundle(bundle, repo, release)
        dispatcher = jobs.Dispatcher(repo, index, release, inputs, runtime, installed, config, identity)
        if artifact_only:
            job, artifact = request["job"], request["artifact"]
            sha256 = dispatcher.artifact_sha256(job, artifact)
            if updates.input_identity(inputs, config) != identity:
                raise ValueError("signed artifact input identity changed")
            result.update(success=True, job=job, artifact=artifact, sha256=sha256, bundle_sha256=release["bundle_sha256"])
            return result
        library = "apk/lib/arm64-v8a/libil2cpp.so"
        metadata = "apk/assets/bin/Data/Managed/Metadata/global-metadata.dat"
        burst = "apk/lib/arm64-v8a/lib_burst_generated.so"
        native_job = index["entries"][library]["job"]
        conversion_job = index["entries"][burst]["job"]
        descriptor = dispatcher.descriptor(native_job)
        if index["entries"][metadata]["job"] != native_job or conversion_job not in descriptor.get("needs", []):
            raise ValueError("signed native and Burst entries require the same conversion cohort")
        built = dispatcher.execute(native_job)
        conversion = publisher.load_json((dispatcher.completed[conversion_job] / "result.json").read_bytes())
        product = publisher.load_json((built / "result.json").read_bytes())
        if (
            conversion.get("success") is not True
            or conversion.get("phase") != "converted-native-planned"
            or conversion.get("upstream_managed_generation_qualified") is not True
        ):
            raise ValueError("signed managed conversion did not qualify")
        if (
            product.get("success") is not True
            or product.get("phase") != "native-built"
            or product["planned_compile_tasks"] <= 0
            or product["compile_tasks"] + product.get("reused_compile_tasks", 0) != product["planned_compile_tasks"]
        ):
            raise ValueError("signed native compile cohort incomplete")
        digests = {entry: dispatcher.output_sha256(entry) for entry in (library, metadata, burst)}
        if (digests[library], digests[metadata]) != (product["library_sha256"], product["metadata_sha256"]):
            raise ValueError("signed native output readback differs from producer receipt")
        burst_record = conversion["backend"]["burst"]
        if burst_record.get("success") is not True or digests[burst] != burst_record["library_sha256"]:
            raise ValueError("signed Burst output readback differs from producer receipt")
        if updates.input_identity(inputs, {}) != identity:
            raise ValueError("signed native input identity changed")
        result.update(
            success=True,
            phase=product["phase"],
            managed_providers=conversion["managed_providers"],
            burst=burst_record,
            native=product,
            output_sha256=digests,
            bundle_sha256=release["bundle_sha256"],
        )
    finally:
        result["measurements"] = dict(
            wall_seconds=time.monotonic() - started,
            children_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024,
            free_bytes_before=free,
            free_bytes_after=shutil.disk_usage(output).free,
        )
        native.write(output / "result.json", result)
    return result


def run(request_file, runtime, installed):
    request_file, runtime, installed = (Path(p).resolve(strict=True) for p in (request_file, runtime, installed))
    inputs = request_file.parent
    spec = importlib.util.spec_from_file_location("android_owner_backend", runtime / "repo/tools/phone-build/owner-code/produce.py")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    request = json.loads(request_file.read_text())
    if set(request) in (SIGNED_RELEASE_FIELDS, SIGNED_ARTIFACT_FIELDS):
        os.environ["TMPDIR"] = str(runtime / "tmp")
        Path(os.environ["TMPDIR"]).mkdir(exist_ok=True)
        print(json.dumps(signed_release_job(request, inputs, runtime, installed, backend.native)), flush=True)
        return
    before = json.loads((inputs / "input-hashes.json").read_text())

    def check_inputs():
        for name, expected in before.items():
            path = inputs / backend.native.relative(name)
            if not path.resolve(strict=True).is_relative_to(inputs) or backend.native.sha(path) != expected:
                raise ValueError("Android owner input drift: " + name)

    check_inputs()
    if set(request) == {"textures", "output"}:
        result = texture_job(request, inputs, runtime, installed, backend.native)
        check_inputs()
        print(json.dumps(result), flush=True)
        return
    if set(request) in ({"signing", "output"}, {"packaging", "output"}):
        result = package_job(request, inputs, runtime, installed, backend.native)
        check_inputs()
        print(json.dumps(result), flush=True)
        return
    if set(request) == {"android_sdk", "output"}:
        result = android_sdk_job(request, inputs, runtime, installed, backend.native)
        check_inputs()
        print(json.dumps(result), flush=True)
        return
    signed_code = set(request) == {"source_inputs", "audio_members", "output"}
    burst_only = request.pop("burst_only", False)
    if not isinstance(burst_only, bool):
        raise ValueError("Burst-only qualification selector must be boolean")
    if not signed_code and set(request) - {"linux_tools", "burst_tools", "compile_timeout_seconds", "pause_clock", "measure_jobs"} not in (
        {"managed", "output"},
        {"source_inputs", "target", "output"},
        {"managed", "target", "output"},
        {"relink", "target", "output"},
        {"resume", "target", "output"},
    ):
        raise ValueError("explicit managed providers or fixed-target source inputs and new output required")
    work, sdk = inputs / "work", inputs / "sdk"
    # Copy timestamps may differ. Preserve the reviewed path/content identity;
    # record this private copy's stats only after checking every original hash.
    prepare_inventory(inputs, backend.native)
    tools = {
        name: str(installed / filename)
        for name, filename in {"dotnet": "libdotnetmuxer.so", "clang": "libclang.so", "linker": "lib-ld.lld-.so", "objcopy": "libobjcopy.so"}.items()
    }
    tools["resource_dir"] = str(runtime / "clang/21")
    output = work / backend.native.relative(request["output"])
    os.environ["TMPDIR"] = str(runtime / "tmp")
    Path(os.environ["TMPDIR"]).mkdir(exist_ok=True)
    started = time.monotonic()
    free = __import__("shutil").disk_usage(work).free
    production = {"owner_work": str(work), "sdk_install": str(sdk), "output": str(output), "android_tools": tools}
    native_profile = None
    if "relink" in request or "resume" in request:
        mode = "resume" if "resume" in request else "relink"
        supplied = request[mode]
        if (
            set(supplied)
            != {"resume" if mode == "resume" else "compiled", "converter_receipt", "converter_receipt_sha256", "sources", "sources_compressed", "metadata"}
            or burst_only
            or "burst_tools" in request
        ):
            raise ValueError("explicit completed native compilation and converter providers required")

        def provider(value):
            resolved = (inputs / backend.native.relative(value)).resolve(strict=True)
            if not resolved.is_relative_to(inputs):
                raise ValueError("native provider escapes private owner files")
            return str(resolved)

        selection = {
            "profile": str(runtime / "repo" / backend.native.relative(request["target"]["profile"])),
            "source": provider(request["target"]["source"]),
        }
        backend.target_inputs(selection)
        for name in ("resume" if mode == "resume" else "compiled", "converter_receipt", "sources", "metadata"):
            production[name] = provider(supplied[name])
        production.update(converter_receipt_sha256=supplied["converter_receipt_sha256"], sources_compressed=supplied["sources_compressed"])
        native_profile = backend.native.generated_profile(
            json.loads(backend.native.PROFILE.read_text()), json.loads(Path(production["converter_receipt"]).read_text())["files"]
        )
    elif "managed" in request:
        providers = {}
        for name, row in request["managed"].items():
            providers[name] = {"path": str((inputs / backend.native.relative(row["path"])).resolve(strict=True)), "sha256": row["sha256"]}
        production["managed"] = providers
        if "target" in request:
            production["target"] = {
                "profile": str(runtime / "repo" / backend.native.relative(request["target"]["profile"])),
                "source": str((inputs / backend.native.relative(request["target"]["source"])).resolve(strict=True)),
            }
    else:
        production["source_inputs"] = {
            name: str((inputs / backend.native.relative(value)).resolve(strict=True)) for name, value in request["source_inputs"].items()
        }
        production["source_inputs"]["dotnet"] = tools["dotnet"]
        if signed_code:
            production["audio_members"] = request["audio_members"]
        else:
            production["target"] = {
                "profile": str(runtime / "repo" / backend.native.relative(request["target"]["profile"])),
                "source": str((inputs / backend.native.relative(request["target"]["source"])).resolve(strict=True)),
            }
    if "linux_tools" in request:
        supplied = request["linux_tools"]
        if set(supplied) != {"clang", "linker", "objcopy", "loader_root", "library_dirs"}:
            raise ValueError("explicit Linux NDK and GNU runtime providers required")
        production["linux_tools"] = {"qemu": str(installed / "libqemu-x86_64.so")}
        production["linux_tools"].update(
            {name: str(inputs / backend.native.relative(supplied[name])) for name in ("clang", "linker", "objcopy", "loader_root")}
        )
        production["linux_tools"]["library_dirs"] = [str(inputs / backend.native.relative(p)) for p in supplied["library_dirs"]]
    if "burst_tools" in request:
        supplied = request["burst_tools"]
        if set(supplied) != {"mono", "runtime"} or "linux_tools" not in production:
            raise ValueError("explicit GNU Mono/Burst providers and Linux tools required")
        mono, compiler = [inputs / backend.native.relative(supplied[name]) for name in ("mono", "runtime")]
        linux = production["linux_tools"]
        libraries = [
            str(compiler),
            str(mono / "usr/lib"),
            str(mono / "usr/lib/x86_64-linux-gnu"),
            str(mono / "lib/x86_64-linux-gnu"),
            *linux["library_dirs"],
        ]
        command = [linux["qemu"], "-L", linux["loader_root"]]
        for value in [
            "LD_LIBRARY_PATH=" + ":".join(libraries),
            "LD_PRELOAD=" + str(runtime / "gnu/libgnu-tool-adapter.so"),
            "MONO_CFG_DIR=" + str(mono / "etc"),
            "MONO_PATH=" + str(mono / "usr/lib/mono/4.5") + ":" + str(mono / "usr/lib/mono/4.5/Facades"),
            "ROR2_GNU_RUNNER=" + linux["qemu"],
            "ROR2_GNU_LOADER_ROOT=" + linux["loader_root"],
            "ROR2_GNU_NATIVE_LIBRARY_PATH=" + str(installed) + ":" + str(runtime / "native-links"),
        ]:
            command += ["-E", value]
        command.append(str(mono / "usr/bin/mono-sgen"))
        production["burst_tools"] = {"command": command, "runtime": str(compiler)}
    if "measure_jobs" in request:
        production["measure_jobs"] = request["measure_jobs"]
    if "compile_timeout_seconds" in request:
        production["compile_timeout_seconds"] = request["compile_timeout_seconds"]
    if os.environ.get("ROR2LAB_BUILD_PAUSE_CLOCK"):
        # The shared on-device supervisor owns this BOOTTIME clock, outside
        # the stopped producer family. Prefer its clock over an outer watcher.
        production["pause_clock"] = str(Path(os.environ["ROR2LAB_BUILD_PAUSE_CLOCK"]).resolve(strict=True))
    elif "pause_clock" in request:
        clock = (inputs / backend.native.relative(request["pause_clock"])).resolve(strict=True)
        if not clock.is_relative_to(inputs):
            raise ValueError("pause clock escapes private owner files")
        production["pause_clock"] = str(clock)
    output_preexisted = output.exists()
    try:
        if native_profile is not None:
            result = backend.native.run(production, profile=native_profile)
        elif signed_code:
            result = backend.run(production, stop_after_conversion=True)
        elif burst_only:
            result = backend.run(production, burst_only=True)
        else:
            result = backend.run(production)
        # Generated local state changed intentionally; immutable original/SDK/provider
        # checks remain separate from those three private setup files.
        immutable = {n: h for n, h in before.items() if n not in {"work/config/local.json", "work/inventory/files.json"}}
        for name, expected in immutable.items():
            if backend.native.sha(inputs / name) != expected:
                raise ValueError("Android owner input changed: " + name)
    finally:
        if not output_preexisted and output.is_dir():
            backend.native.write(
                output / "android-measurements.json",
                {
                    "wall_seconds": time.monotonic() - started,
                    "python_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                    "children_peak_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024,
                    "free_bytes_before": free,
                    "free_bytes_after": __import__("shutil").disk_usage(work).free,
                    "managed_providers_supplied": "managed" in request,
                    "runtime_qualified": False,
                },
            )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    run(*sys.argv[1:])
