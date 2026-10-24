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
    if set(request) - {"linux_tools"} not in ({"managed", "output"}, {"source_inputs", "target", "output"}):
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
    if "managed" in request:
        providers = {}
        for name, row in request["managed"].items():
            providers[name] = {"path": str((inputs / backend.native.relative(row["path"])).resolve(strict=True)), "sha256": row["sha256"]}
        production["managed"] = providers
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
    result = backend.run(production)
    # Generated local state changed intentionally; immutable original/SDK/provider
    # checks remain separate from those three private setup files.
    immutable = {n: h for n, h in before.items() if n not in {"work/config/local.json", "work/inventory/files.json"}}
    for name, expected in immutable.items():
        if backend.native.sha(inputs / name) != expected:
            raise ValueError("Android owner input changed: " + name)
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
