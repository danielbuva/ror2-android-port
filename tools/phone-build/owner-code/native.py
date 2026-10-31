"""Current experimental native stage of the Editor-free owner code producer.

One explicit request, immutable owner inputs, a new private output. No captured
build graph, project, SDK modification, download, Editor or device operation.
"""

import argparse
from contextlib import ExitStack
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import shlex
import signal
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/lab"))

PROFILE = ROOT / "recipe/owner-native-arm64.json"
PROFILE_SHA = "868a0665d3550b53eebf0d57c8a50997f09a4a797e86a45ebd21f13004e6136d"
RESERVE = 2 * 1024**3


def input_state(work):
    # Generic SDK/APK packaging uses these helpers without game reconstruction
    # recipes. Load the owner validator only for actual native production.
    from owner_assemblies import input_state as owner_input_state

    return owner_input_state(work)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def relative(value):
    path = PurePosixPath(value)
    if not isinstance(value, str) or str(path) != value or path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("canonical relative native path required")
    if any(c in value for c in ('"', "\\", "\r", "\n", "\0")):
        raise ValueError("unsafe native path")
    return path


def canonical(value):
    path = Path(value)
    if not path.is_absolute() or path != path.resolve(strict=True) or any(c in str(path) for c in ('"', "\\", "\r", "\n", "\0")):
        raise ValueError("canonical explicit native input required")
    return path


def disjoint(output, inputs):
    if not output.is_absolute() or output.parent != output.parent.resolve(strict=True) or output.exists() or output.is_symlink() or ".." in output.parts:
        raise ValueError("new canonical output required")
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in inputs):
        raise ValueError("native output/input overlap")


def sdk_files(sdk, profile):
    files = {}
    for folder in ("Unity.app/Contents/il2cpp/libil2cpp", "Unity.app/Contents/il2cpp/external", "PlaybackEngines/AndroidPlayer/NDK"):
        for path in sorted((sdk / folder).rglob("*")):
            if path.is_file():
                if not path.resolve().is_relative_to(sdk):
                    raise ValueError("SDK source escapes installation")
                files[path.relative_to(sdk).as_posix()] = sha(path)
    for name in (
        profile["compiler"],
        profile["objcopy"],
        "PlaybackEngines/AndroidPlayer/NDK/source.properties",
        "PlaybackEngines/AndroidPlayer/Variations/il2cpp/Development/StaticLibs/arm64-v8a/baselib.a",
    ):
        path = sdk / relative(name)
        if not path.resolve(strict=True).is_relative_to(sdk):
            raise ValueError("SDK tool escapes installation")
        files[name] = sha(path)
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if len(files) != profile["sdk_files"] or digest != profile["sdk_digest"]:
        raise ValueError("pinned SDK source/tool cohort differs")
    return files


def converter_inputs(receipt, receipt_sha, sources, metadata, profile, compressed):
    if sha(receipt) != receipt_sha:
        raise ValueError("converter receipt drift")
    value = json.loads(receipt.read_text())
    if value.get("exit_code") != 0 or value.get("inputs_unchanged") is not True:
        raise ValueError("successful converter receipt required")
    expected = {"cpp/" + j["generated"] for j in profile["jobs"] if "generated" in j}
    files = value["files"]
    actual = {n for n in files if n.startswith("cpp/") and n.endswith((".cpp", ".c"))}
    if actual != expected:
        raise ValueError("generated translation-unit membership differs; review profile")
    suffix = ".gz" if compressed else ""
    providers = {}
    for name in sorted(expected):
        plain = PurePosixPath(name).name
        relative(plain)
        path = sources / (plain + suffix)
        if path.is_symlink() or path.resolve(strict=True) != path:
            raise ValueError("redirected generated source")
        row = files[name]
        if not isinstance(row["bytes"], int) or not 0 < row["bytes"] < 128 * 1024**2:
            raise ValueError("unqualified generated source size")
        providers[plain] = {"path": str(path), "provider_sha256": sha(path), "bytes": row["bytes"], "sha256": row["sha256"], "compressed": compressed}
    metadata_row = files["data/Metadata/global-metadata.dat"]
    if metadata.stat().st_size != metadata_row["bytes"] or sha(metadata) != metadata_row["sha256"]:
        raise ValueError("metadata differs from the same converter receipt")
    with metadata.open("rb") as stream:
        header = stream.read(8)
    if len(header) != 8 or struct.unpack("<II", header) != (0xFAB11BAF, 31):
        raise ValueError("qualified IL2CPP metadata version required")
    return providers, metadata_row


def arguments(items, roots, *, source=None, obj=None, library=None):
    result = []
    for item in items:
        if isinstance(item, str):
            if item in {"SOURCE", "OBJECT", "LIBRARY"}:
                path = {"SOURCE": source, "OBJECT": obj, "LIBRARY": library}[item]
                if path is None:
                    raise ValueError("missing native argument binding")
                result.append(str(path))
            elif item.startswith(("/", "@")) or any(c in item for c in ("\r", "\n", "\0")):
                raise ValueError("unbound native argument")
            else:
                result.append(item)
        elif isinstance(item, dict) and set(item) == {"object"}:
            result.append(str(roots["output"] / "objects" / (str(item["object"]) + ".o")))
        elif isinstance(item, dict) and set(item) in ({"root", "path"}, {"root", "path", "prefix"}):
            prefix = item.get("prefix", "")
            if prefix not in {"", "-I"} or item["root"] not in roots:
                raise ValueError("invalid native path binding")
            result.append(prefix + str(roots[item["root"]] if item["path"] == "." else roots[item["root"]] / relative(item["path"])))
        else:
            raise ValueError("invalid native argument record")
    return result


def android_tool_state(tools):
    """Bind explicitly supplied Android tools; original SDK data stay pinned."""
    if set(tools) != {"dotnet", "clang", "linker", "objcopy", "resource_dir"}:
        raise ValueError("explicit Android compiler, linker, stripper, runtime and resources required")
    paths = {name: canonical(value) for name, value in tools.items()}
    if not paths["resource_dir"].is_dir() or any(not path.is_file() for name, path in paths.items() if name != "resource_dir"):
        raise ValueError("invalid Android tool kind")
    return {
        str(path): sha(path) for path in [*[p for n, p in paths.items() if n != "resource_dir"], *sorted(paths["resource_dir"].rglob("*"))] if path.is_file()
    }


def android_command(argv, sdk, tools, *, link=False):
    """J921's explicit Clang/LLD policy, with original target headers/libraries."""
    ndk = sdk / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64"
    sysroot = ndk / "sysroot"
    result = [tools["clang"], "--driver-mode=g++", "-fintegrated-cc1", "--sysroot=" + str(sysroot), "-resource-dir=" + tools["resource_dir"]]
    if link or "-std=c++11" in argv:
        result += ["-nostdinc++", "-isystem", str(sysroot / "usr/include/c++/v1")]
    result += [value for value in argv[1:] if value != "-fuse-ld=bfd" and not (link and value == "-static-libstdc++")]
    if link:
        arch = sysroot / "usr/lib/aarch64-linux-android"
        gcc = ndk / "lib/gcc/aarch64-linux-android/4.9.x"
        result += [
            "--ld-path=" + tools["linker"],
            "-B" + str(arch / "22"),
            "-L" + str(arch / "22"),
            "-L" + str(arch),
            "-L" + str(gcc),
            "-nostdlib++",
            "--unwindlib=none",
            str(arch / "libc++_static.a"),
            str(arch / "libc++abi.a"),
            str(gcc / "libgcc.a"),
        ]
    return result


def linux_tool_state(tools):
    """Hash an explicitly supplied Linux NDK and public user-mode runner."""
    if set(tools) != {"qemu", "clang", "linker", "objcopy", "loader_root", "library_dirs"}:
        raise ValueError("explicit Linux runner, NDK tools, GNU loader and libraries required")
    paths = {n: canonical(tools[n]) for n in ("qemu", "clang", "linker", "objcopy", "loader_root")}
    if any(not paths[n].is_file() for n in ("qemu", "clang", "linker", "objcopy")) or not paths["loader_root"].is_dir():
        raise ValueError("invalid Linux tool kind")
    directories = [canonical(p) for p in tools["library_dirs"]]
    if not directories or any(not p.is_dir() for p in directories):
        raise ValueError("explicit GNU library directories required")
    files = [paths[n] for n in ("qemu", "clang", "linker", "objcopy")]
    for folder in [paths["loader_root"], *directories]:
        files.extend(p for p in sorted(folder.rglob("*")) if p.is_file())
    return {str(p): sha(p) for p in files}


def linux_prefix(tools):
    return [tools["qemu"], "-L", tools["loader_root"], "-E", "LD_LIBRARY_PATH=" + ":".join(tools["library_dirs"]), "-E", "LC_ALL=C"]


def linux_driver_arguments(argv, sdk, tools):
    # Target data remain the exact accepted SDK's headers, startup objects and
    # runtime libraries. Only the host executables use the Linux NDK provider.
    ndk = sdk / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64"
    return [
        "--driver-mode=g++",
        "--sysroot=" + str(ndk / "sysroot"),
        "-resource-dir=" + str(ndk / "lib64/clang/9.0.8"),
        "--gcc-toolchain=" + str(ndk),
        "-B" + str(Path(tools["linker"]).parent),
        *argv[1:],
    ]


def linux_invoke(argv, output, name, sdk, tools, *, env, link=False, timeout=3600, pause_clock=None):
    """Run the unchanged driver's actual cc1/BFD command under QEMU.

    Android cannot exec a Linux child through binfmt_misc. Ask the original
    driver for its command and invoke that one child explicitly; no compiler
    policy, optimization, source or target library is substituted.
    """
    prefix = linux_prefix(tools)
    invoke([*prefix, tools["clang"], "-###", *linux_driver_arguments(argv, sdk, tools)], output, name + "-driver", env=env, pause_clock=pause_clock)
    rendered = (output / "logs" / (name + "-driver.log")).read_text()
    commands = [shlex.split(line) for line in rendered.splitlines() if line.lstrip().startswith('"')]
    if len(commands) != 1:
        raise ValueError("Linux NDK driver did not emit one tool command")
    command = commands[0]
    if link:
        if Path(command[0]).name not in {"ld", "ld.bfd", "aarch64-linux-android-ld", "aarch64-linux-android-ld.bfd"}:
            raise ValueError("Linux NDK driver did not select BFD")
        command[0] = tools["linker"]
    elif command[:2] != [tools["clang"], "-cc1"]:
        raise ValueError("Linux NDK driver did not select its cc1 compiler")
    invoke([*prefix, *command], output, name, env=env, timeout=timeout, pause_clock=pause_clock)


def burst_ndk(sdk, tools, output):
    """Expose unchanged target data and explicit GNU host tools to Burst."""
    original = sdk / "PlaybackEngines/AndroidPlayer/NDK"
    target = original / "toolchains/llvm/prebuilt/darwin-x86_64"
    output.mkdir()
    (output / "source.properties").symlink_to(original / "source.properties")
    host = output / "toolchains/llvm/prebuilt/linux-x86_64"
    host.mkdir(parents=True)
    for name in ("lib", "lib64", "include", "sysroot", "aarch64-linux-android"):
        (host / name).symlink_to(target / name, target_is_directory=True)
    (host / "bin").mkdir()
    for name, role in {"clang": "clang", "clang++": "clang", "ld": "linker", "aarch64-linux-android-ld": "linker", "llvm-objcopy": "objcopy"}.items():
        (host / "bin" / name).symlink_to(canonical(tools[role]))
    return output


def generated_profile(profile, files):
    """Keep SDK native policy; compile every translation unit from this conversion."""
    result = json.loads(json.dumps(profile))
    modes = {Path(row["generated"]).suffix: row["arguments"] for row in profile["jobs"] if "generated" in row}
    jobs = [row for row in result["jobs"] if "generated" not in row]
    names = sorted(name.removeprefix("cpp/") for name in files if name.startswith("cpp/") and name.endswith((".cpp", ".c")))
    if not names:
        raise ValueError("target conversion emitted no native translation units")
    for name in names:
        if relative(name).name != name:
            raise ValueError("nested target translation unit requires qualification")
        jobs.append({"arguments": modes[Path(name).suffix], "generated": name})
    result["jobs"] = jobs
    generated = {row["generated"]: i for i, row in enumerate(jobs) if "generated" in row}
    remap, sdk_index = {}, 0
    for i, row in enumerate(profile["jobs"]):
        if "generated" in row:
            if row["generated"] in generated:
                remap[i] = generated[row["generated"]]
        else:
            remap[i] = sdk_index
            sdk_index += 1
    # Object order selects COMDAT definitions, static initialization order and
    # ARM64 erratum veneers. Keep the recorded policy when filtering a target.
    link, insertion = [], None
    for row in profile["link"]:
        if isinstance(row, dict) and "object" in row:
            old = row["object"]
            if old in remap:
                link.append({"object": remap[old]})
            if "generated" in profile["jobs"][old]:
                insertion = len(link)
        else:
            link.append(row)
    added = sorted(set(generated.values()) - set(remap.values()))
    link[insertion:insertion] = [{"object": i} for i in added]
    result["link"] = link
    return result


def plan(profile, sdk, output, android_tools=None):
    roots = {"sdk": sdk, "output": output, "cpp": output / "cpp"}
    jobs, wrappers = [], {}
    for index, item in enumerate(profile["jobs"]):
        if set(item) == {"arguments", "generated"}:
            source = roots["cpp"] / relative(item["generated"])
            kind = "generated"
        elif set(item) == {"arguments", "sdk"}:
            source = sdk / relative(item["sdk"])
            kind = "sdk"
        elif set(item) == {"arguments", "lump"} and item["lump"]:
            source = output / "lumps" / (str(index) + ".cpp")
            members = [sdk / relative(n) for n in item["lump"]]
            if any(not p.resolve(strict=True).is_relative_to(sdk) for p in members):
                raise ValueError("lump member escapes SDK")
            wrappers[str(source)] = [str(p) for p in members]
            kind = "lump"
        else:
            raise ValueError("invalid native job declaration")
        obj = output / "objects" / (str(index) + ".o")
        argv = [str(sdk / profile["compiler"]), *arguments(profile["arguments"][item["arguments"]], roots, source=source, obj=obj)]
        if android_tools:
            argv = android_command(argv, sdk, android_tools)
        jobs.append({"source": str(source), "output": str(obj), "kind": kind, "argv": argv})
    link = [str(sdk / profile["compiler"]), *arguments(profile["link"], roots, library=output / "libil2cpp.unstripped.so")]
    if android_tools:
        link = android_command(link, sdk, android_tools, link=True)
    objects = [str(j["output"]) for j in jobs]
    linked = [v for v in link if v.endswith(".o")]
    if len(linked) != len(objects) or set(linked) != set(objects) or len(set(objects)) != len(objects):
        raise ValueError("compile/link object closure differs")
    return {"schema": 1, "jobs": jobs, "wrappers": wrappers, "link": link, "library": str(output / "libil2cpp.unstripped.so")}


def elapsed_clock():
    # Android's guard records /proc/uptime, which uses BOOTTIME rather than
    # MONOTONIC across system suspend. Host fixtures need no Linux-only API.
    return time.clock_gettime(getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC))


def paused_seconds(path):
    value = json.loads(path.read_text())
    if set(value) != {"paused_seconds", "paused_at"}:
        raise ValueError("explicit cumulative pause clock required")
    total, at = value["paused_seconds"], value["paused_at"]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in (total, *([] if at is None else [at]))):
        raise ValueError("invalid pause clock")
    now = elapsed_clock()
    if at is not None and at > now:
        raise ValueError("pause clock is ahead of BOOTTIME")
    return now, total + (now - at if at is not None else 0)


def wait_active(child, timeout, pause_clock, record):
    """Guard owns STOP/CONT; its independent clock survives a stopped parent."""
    started, initial_pause = paused_seconds(pause_clock)
    prior_pause = initial_pause
    while True:
        now, paused = paused_seconds(pause_clock)
        if paused + 0.000001 < prior_pause or paused - initial_pause > now - started + 0.01:
            raise ValueError("pause clock reset or exceeds elapsed time")
        prior_pause = paused
        active = max(0, now - started - (paused - initial_pause))
        record.update(active_seconds=active, paused_seconds=paused - initial_pause)
        code = child.poll()
        if code is not None:
            return code
        if active >= timeout:
            raise subprocess.TimeoutExpired(child.args, timeout)
        try:
            child.wait(timeout=min(0.1, timeout - active))
        except subprocess.TimeoutExpired:
            pass


def invoke(argv, output, name, *, env=None, separate_stderr=False, timeout=3600, pause_clock=None):
    started = time.monotonic()
    record = {"argv": argv, "exit_code": None, "timeout_seconds": timeout}

    def interrupted(signum, frame):
        raise KeyboardInterrupt("native tool interrupted")

    previous = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, interrupted)
        with ExitStack() as stack:
            log = stack.enter_context((output / "logs" / (name + ".log")).open("xb"))
            errors = stack.enter_context((output / "logs" / (name + ".stderr.log")).open("xb")) if separate_stderr else subprocess.STDOUT
            child = subprocess.Popen(
                argv,
                cwd=output,
                env=env if env is not None else {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(output / "tmp")},
                stdout=log,
                stderr=errors,
                start_new_session=True,
            )
            try:
                record["exit_code"] = wait_active(child, timeout, pause_clock, record) if pause_clock else child.wait(timeout=timeout)
            except BaseException:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                raise
        if record["exit_code"] != 0:
            raise RuntimeError("native stage failed: " + name)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        record["seconds"] = time.monotonic() - started
        write(output / "logs" / (name + ".process.json"), record)


def expand(row, destination):
    source = Path(row["path"])
    if sha(source) != row["provider_sha256"]:
        raise ValueError("generated source provider drift")
    opener = gzip.open if row["compressed"] else open
    digest, total = hashlib.sha256(), 0
    with opener(source, "rb") as incoming, destination.open("xb") as outgoing:
        while data := incoming.read(1024 * 1024):
            total += len(data)
            if total > row["bytes"]:
                raise ValueError("generated source exceeds converter size")
            digest.update(data)
            outgoing.write(data)
    if total != row["bytes"] or digest.hexdigest() != row["sha256"]:
        raise ValueError("generated source differs from converter receipt")


def lump_source(members):
    return "// Authored SDK include wrapper; owner SDK source remains unchanged.\n" + "".join('#include "' + p + '"\n' for p in members)


def compiled_jobs(folder, current, profile, sdk, inputs, *, resume=False):
    """Validate retained object receipts before relinking or continuing a failure."""
    old = json.loads((folder / "plan.json").read_text())
    previous = json.loads((folder / "inputs.json").read_text())
    result = json.loads((folder / "result.json").read_text())
    count = result.get("compile_tasks", 0) + result.get("reused_compile_tasks", 0)
    if resume:
        if result.get("success") is not False or result.get("phase") != "compiling" or not 0 <= count < len(current["jobs"]):
            raise ValueError("failed original compilation with a receipt prefix required for resume")
    elif result.get("success") is not True or result.get("phase") != "native-built" or count != len(current["jobs"]):
        raise ValueError("complete original compilation required for relinking")
    if result.get("input_id") != profile["input_id"]:
        raise ValueError("compiled original input differs")
    for name in ("sdk", "metadata", "converter_receipt_sha256"):
        if previous[name] != inputs[name]:
            raise ValueError("compiled native input differs: " + name)
    for name in ("android_tools", "linux_tools"):

        def identities(value):
            return sorted((Path(path).name, digest) for path, digest in (value or {}).items())

        if identities(previous[name]) != identities(inputs[name]):
            raise ValueError("compiled native tool cohort differs: " + name)
    source_state = lambda rows: {name: {k: v for k, v in row.items() if k != "path"} for name, row in rows.items()}
    if source_state(previous["sources"]) != source_state(inputs["sources"]):
        raise ValueError("compiled converter source cohort differs")
    compiler = "/" + profile["compiler"]
    if not old["jobs"][0]["argv"][0].endswith(compiler):
        raise ValueError("compiled SDK command binding differs")
    old_sdk = old["jobs"][0]["argv"][0][: -len(compiler)]
    old_output = str(Path(old["library"]).parent)
    output = str(Path(current["library"]).parent)

    def remap(value):
        if isinstance(value, str):
            return value.replace(old_sdk, str(sdk)).replace(old_output, output)
        if isinstance(value, list):
            return [remap(item) for item in value]
        return {remap(key): remap(item) for key, item in value.items()}

    if remap(old["jobs"]) != current["jobs"] or remap(old["wrappers"]) != current["wrappers"]:
        raise ValueError("compiled command policy differs; compile again")
    if {p.name for p in (folder / "job-results").iterdir()} != {str(i) + ".json" for i in range(count)}:
        raise ValueError("complete compiled job receipts required")
    rows = []
    for index, job in enumerate(current["jobs"][:count]):
        row = json.loads((folder / "job-results" / (str(index) + ".json")).read_text())
        if job["kind"] == "generated":
            source_sha = inputs["sources"][Path(job["source"]).name]["sha256"]
        elif job["kind"] == "lump":
            origin = row.get("lump_sdk_root", old_sdk)
            if (
                not isinstance(origin, str)
                or not Path(origin).is_absolute()
                or str(Path(origin)) != origin
                or ".." in Path(origin).parts
                or any(c in origin for c in ('"', "\\", "\r", "\n", "\0"))
            ):
                raise ValueError("invalid compiled lump SDK origin")
            members = [str(Path(origin) / Path(member).relative_to(old_sdk)) for member in old["wrappers"][old["jobs"][index]["source"]]]
            source_sha = hashlib.sha256(lump_source(members).encode()).hexdigest()
        else:
            source_sha = sha(job["source"])
        obj = folder / "objects" / (str(index) + ".o")
        if obj.is_symlink() or obj.resolve(strict=True) != obj:
            raise ValueError("compiled object/source receipt differs: " + str(index))
        expected = {"source_sha256": source_sha, "output_sha256": sha(obj), "bytes": obj.stat().st_size}
        if job["kind"] == "lump" and "lump_sdk_root" in row:
            expected["lump_sdk_root"] = origin
        if row != expected:
            raise ValueError("compiled object/source receipt differs: " + str(index))
        if job["kind"] == "lump" and origin != str(sdk):
            row = {**row, "lump_sdk_root": origin}
        rows.append((obj, row))
    return rows


def run(request, *, plan_only=False, profile=None):
    required = {"owner_work", "sdk_install", "converter_receipt", "converter_receipt_sha256", "sources", "sources_compressed", "metadata", "output"}
    if set(request) - {
        "android_tools",
        "linux_tools",
        "compiled",
        "resume",
        "compile_timeout_seconds",
        "pause_clock",
        "measure_jobs",
    } != required or not isinstance(request["sources_compressed"], bool):
        raise ValueError("explicit native request fields required")
    work, sdk, receipt, sources, metadata = [canonical(request[n]) for n in ("owner_work", "sdk_install", "converter_receipt", "sources", "metadata")]
    output = Path(request["output"])
    identity, game, inventory = input_state(work)
    if not output.is_relative_to(work) or output == work:
        raise ValueError("native output must be inside owner work")
    disjoint(output, (sdk, receipt, sources, metadata, game, work / "config", work / "inventory"))
    if sha(PROFILE) != PROFILE_SHA:
        raise ValueError("audited native profile drift")
    supplied_profile = profile is not None
    profile = profile if supplied_profile else json.loads(PROFILE.read_text())
    if identity != profile["input_id"]:
        raise ValueError("unqualified legitimate input")
    sdk_state = sdk_files(sdk, profile)
    providers, metadata_row = converter_inputs(receipt, request["converter_receipt_sha256"], sources, metadata, profile, request["sources_compressed"])
    android_tools = request.get("android_tools")
    tool_state = android_tool_state(android_tools) if android_tools else None
    environment = dict(os.environ, TMPDIR=str(output / "tmp")) if android_tools or request.get("linux_tools") else None
    linux_tools = request.get("linux_tools")
    linux_state = linux_tool_state(linux_tools) if linux_tools else None
    value = plan(profile, sdk, output, None if linux_tools else android_tools)
    inputs = {
        "inventory": inventory,
        "sdk": sdk_state,
        "converter_receipt_sha256": request["converter_receipt_sha256"],
        "sources": providers,
        "metadata": metadata_row,
        "android_tools": tool_state,
        "linux_tools": linux_state,
    }
    measured = request.get("measure_jobs")
    if "measure_jobs" in request and (
        not isinstance(measured, list)
        or not measured
        or any(isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(value["jobs"]) for index in measured)
        or len(set(measured)) != len(measured)
        or plan_only
    ):
        raise ValueError("nonempty unique valid measurement job indexes required; no plan-only measurement")
    if "compiled" in request and "resume" in request:
        raise ValueError("select completed relink or failed compilation resume")
    timeout = request.get("compile_timeout_seconds", 3600)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("positive active compile timeout required")
    pause_clock = canonical(request["pause_clock"]) if "pause_clock" in request else None
    if pause_clock:
        paused_seconds(pause_clock)
    resuming = "resume" in request
    compiled = canonical(request["resume" if resuming else "compiled"]) if "compiled" in request or resuming else None
    if compiled:
        disjoint(output, [compiled])
    reused = compiled_jobs(compiled, value, profile, sdk, inputs, resume=resuming) if compiled else None
    output.mkdir(mode=0o700)
    result = {
        "schema": 1,
        "success": False,
        "phase": "planning",
        "input_id": identity,
        "profile_sha256": hashlib.sha256((json.dumps(profile, indent=2) + "\n").encode()).hexdigest() if supplied_profile else PROFILE_SHA,
        "source_sha256": sha(Path(__file__)),
        "phone_qualified": False,
        "runtime_qualified": False,
        "compile_tasks": 0,
        "compile_timeout_seconds": timeout,
    }
    if measured is not None:
        result["measured_jobs"] = measured
    if compiled:
        result.update(**{"resume" if resuming else "compiled": str(compiled)}, reused_compile_tasks=0)
    try:
        for name in ("tmp", "logs", "objects", "cpp", "lumps", "job-results"):
            (output / name).mkdir()
        write(output / "plan.json", value)
        if supplied_profile:
            write(output / "native-profile.json", profile)
        write(output / "inputs.json", inputs)
        for target, members in value["wrappers"].items():
            Path(target).write_text(lump_source(members))
        if not plan_only:
            result["phase"] = "compiling"
            for index, job in enumerate(value["jobs"]):
                if measured is not None and index not in measured:
                    continue
                if measured is None and reused is not None and index < len(reused):
                    obj, row = reused[index]
                    link = getattr(os, "link", None)
                    if link is not None:
                        link(obj, job["output"])
                    else:
                        # Android's embedded Python omits os.link.
                        if shutil.disk_usage(output).free < row["bytes"] + RESERVE:
                            raise RuntimeError("native reuse reserve unavailable; outputs retained")
                        shutil.copyfile(obj, job["output"])
                        if Path(job["output"]).stat().st_size != row["bytes"] or sha(Path(job["output"])) != row["output_sha256"]:
                            raise ValueError("reused native object copy differs from its receipt")
                    write(output / "job-results" / (str(index) + ".json"), row)
                    result["reused_compile_tasks"] += 1
                    continue
                if shutil.disk_usage(output).free < RESERVE:
                    raise RuntimeError("native compilation reserve unavailable; outputs retained")
                source = Path(job["source"])
                if job["kind"] == "generated":
                    expand(providers[source.name], source)
                before = sha(source)
                if linux_tools:
                    linux_invoke(job["argv"], output, str(index), sdk, linux_tools, env=environment, timeout=timeout, pause_clock=pause_clock)
                else:
                    invoke(job["argv"], output, str(index), env=environment, timeout=timeout, pause_clock=pause_clock)
                if sha(source) != before:
                    raise ValueError("native input changed during compilation")
                obj = Path(job["output"])
                write(output / "job-results" / (str(index) + ".json"), {"source_sha256": before, "output_sha256": sha(obj), "bytes": obj.stat().st_size})
                result["compile_tasks"] += 1
                if job["kind"] == "generated":
                    source.unlink()
            if measured is None:
                size = sum(Path(j["output"]).stat().st_size for j in value["jobs"])
                if shutil.disk_usage(output).free < size + 1536 * 1024**2:
                    raise RuntimeError("native link reserve unavailable; objects retained")
                result["phase"] = "linking"
                if linux_tools:
                    linux_invoke(value["link"], output, "link", sdk, linux_tools, env=environment, link=True, pause_clock=pause_clock)
                else:
                    invoke(value["link"], output, "link", env=environment, pause_clock=pause_clock)
                target = output / "libil2cpp.so"
                stripper = android_tools["objcopy"] if android_tools else str(sdk / profile["objcopy"])
                result["phase"] = "stripping"
                strip_command = [*linux_prefix(linux_tools), linux_tools["objcopy"]] if linux_tools else [stripper]
                invoke([*strip_command, "--strip-all", value["library"], str(target)], output, "strip", env=environment, pause_clock=pause_clock)
                with target.open("rb") as stream:
                    header = stream.read(64)
                if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<HH", header, 16) != (3, 183):
                    raise ValueError("expected AArch64 shared ELF library")
                result.update(library_sha256=sha(target), library_bytes=target.stat().st_size)
        if compiled and compiled_jobs(compiled, value, profile, sdk, inputs, resume=resuming) != reused:
            raise ValueError("compiled providers changed during relinking")
        if sdk_files(sdk, profile) != sdk_state or input_state(work) != (identity, game, inventory):
            raise ValueError("owner SDK or game input state changed")
        if android_tools and android_tool_state(android_tools) != tool_state:
            raise ValueError("Android tool inputs changed")
        if linux_tools and linux_tool_state(linux_tools) != linux_state:
            raise ValueError("Linux tool inputs changed")
        if converter_inputs(receipt, request["converter_receipt_sha256"], sources, metadata, profile, request["sources_compressed"]) != (
            providers,
            metadata_row,
        ):
            raise ValueError("converter providers changed during native production")
        result.update(
            success=True,
            phase="planned" if plan_only else "native-measured" if measured is not None else "native-built",
            metadata_sha256=metadata_row["sha256"],
            planned_compile_tasks=len(value["jobs"]),
        )
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        write(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--plan-only", action="store_true", help="validate all inputs and write the complete plan without compiling")
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.request.read_text()), plan_only=args.plan_only), indent=2))


if __name__ == "__main__":
    main()
