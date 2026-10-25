"""Run the existing whole-player backend in the installed headless tool host.

Caller-supplied original files and SDK remain private app data, never APK assets.
Select fixed-target source production or a supplied-provider infrastructure control.
"""

import importlib.util
import json
import os
from pathlib import Path
import resource
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
    if set(selection) != ({"targets", "manifest", "code", "key_directory", "version_code"} if "packaging" in request else {"unsigned", "key_directory"}):
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


def run(request_file, runtime, installed):
    request_file, runtime, installed = (Path(p).resolve(strict=True) for p in (request_file, runtime, installed))
    inputs = request_file.parent
    spec = importlib.util.spec_from_file_location("android_owner_backend", runtime / "repo/tools/phone-build/owner-code/produce.py")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    before = json.loads((inputs / "input-hashes.json").read_text())

    def check_inputs():
        for name, expected in before.items():
            path = inputs / backend.native.relative(name)
            if not path.resolve(strict=True).is_relative_to(inputs) or backend.native.sha(path) != expected:
                raise ValueError("Android owner input drift: " + name)

    check_inputs()
    request = json.loads(request_file.read_text())
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
    burst_only = request.pop("burst_only", False)
    if not isinstance(burst_only, bool):
        raise ValueError("Burst-only qualification selector must be boolean")
    if set(request) - {"linux_tools", "burst_tools"} not in (
        {"managed", "output"},
        {"source_inputs", "target", "output"},
        {"managed", "target", "output"},
        {"relink", "target", "output"},
    ):
        raise ValueError("explicit managed providers or fixed-target source inputs and new output required")
    work, sdk, game = [inputs / name for name in ("work", "sdk", "game")]
    inventory = json.loads((work / "inventory/files.json").read_text())
    for row in inventory["files"]:
        path = game / backend.native.relative(row["path"])
        if backend.native.sha(path) != row["sha256"] or path.stat().st_size != row["size"]:
            raise ValueError("copied original game input differs")
        row["mtime_ns"] = path.stat().st_mtime_ns
    # Copy timestamps may differ. Preserve the reviewed path/content identity;
    # record this private copy's stats only after checking every original hash.
    (work / "inventory/files.json").write_text(json.dumps(inventory) + "\n")
    (work / "config/local.json").write_text(json.dumps({"game_path": str(game)}) + "\n")
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
    if "relink" in request:
        supplied = request["relink"]
        if (
            set(supplied) != {"compiled", "converter_receipt", "converter_receipt_sha256", "sources", "sources_compressed", "metadata"}
            or burst_only
            or "burst_tools" in request
        ):
            raise ValueError("explicit completed native compilation and converter providers required")
        selection = {
            "profile": str(runtime / "repo" / backend.native.relative(request["target"]["profile"])),
            "source": str((inputs / backend.native.relative(request["target"]["source"])).resolve(strict=True)),
        }
        backend.target_inputs(selection)
        for name in ("compiled", "converter_receipt", "sources", "metadata"):
            production[name] = str((inputs / backend.native.relative(supplied[name])).resolve(strict=True))
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
        libraries = [str(compiler), str(mono / "usr/lib"), str(mono / "usr/lib/x86_64-linux-gnu"), *linux["library_dirs"]]
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
    output_preexisted = output.exists()
    try:
        if native_profile is not None:
            result = backend.native.run(production, profile=native_profile)
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
