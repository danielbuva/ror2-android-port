"""Current experimental native stage of the Editor-free owner code producer.

One explicit request, immutable owner inputs, a new private output. No captured
build graph, project, SDK modification, download, Editor or device operation.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/lab"))
from owner_assemblies import input_state  # noqa: E402

PROFILE = ROOT / "recipe/owner-native-arm64.json"
PROFILE_SHA = "868a0665d3550b53eebf0d57c8a50997f09a4a797e86a45ebd21f13004e6136d"
RESERVE = 2 * 1024**3


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


def plan(profile, sdk, output):
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
        jobs.append({"source": str(source), "output": str(obj), "kind": kind, "argv": argv})
    link = [str(sdk / profile["compiler"]), *arguments(profile["link"], roots, library=output / "libil2cpp.unstripped.so")]
    objects = [str(j["output"]) for j in jobs]
    linked = [v for v in link if v.endswith(".o")]
    if len(linked) != len(objects) or set(linked) != set(objects) or len(set(objects)) != len(objects):
        raise ValueError("compile/link object closure differs")
    return {"schema": 1, "jobs": jobs, "wrappers": wrappers, "link": link, "library": str(output / "libil2cpp.unstripped.so")}


def invoke(argv, output, name):
    started = time.monotonic()
    record = {"argv": argv, "exit_code": None}

    def interrupted(signum, frame):
        raise KeyboardInterrupt("native tool interrupted")

    previous = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, interrupted)
        with (output / "logs" / (name + ".log")).open("xb") as log:
            child = subprocess.Popen(
                argv,
                cwd=output,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(output / "tmp")},
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                record["exit_code"] = child.wait(timeout=600)
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


def run(request, *, plan_only=False):
    required = {"owner_work", "sdk_install", "converter_receipt", "converter_receipt_sha256", "sources", "sources_compressed", "metadata", "output"}
    if set(request) != required or not isinstance(request["sources_compressed"], bool):
        raise ValueError("explicit native request fields required")
    work, sdk, receipt, sources, metadata = [canonical(request[n]) for n in ("owner_work", "sdk_install", "converter_receipt", "sources", "metadata")]
    output = Path(request["output"])
    identity, game, inventory = input_state(work)
    if not output.is_relative_to(work) or output == work:
        raise ValueError("native output must be inside owner work")
    disjoint(output, (sdk, receipt, sources, metadata, game, work / "config", work / "inventory"))
    if sha(PROFILE) != PROFILE_SHA:
        raise ValueError("audited native profile drift")
    profile = json.loads(PROFILE.read_text())
    if identity != profile["input_id"]:
        raise ValueError("unqualified legitimate input")
    sdk_state = sdk_files(sdk, profile)
    providers, metadata_row = converter_inputs(receipt, request["converter_receipt_sha256"], sources, metadata, profile, request["sources_compressed"])
    value = plan(profile, sdk, output)
    output.mkdir(mode=0o700)
    result = {
        "schema": 1,
        "success": False,
        "phase": "planning",
        "input_id": identity,
        "profile_sha256": PROFILE_SHA,
        "source_sha256": sha(Path(__file__)),
        "phone_qualified": False,
        "runtime_qualified": False,
        "compile_tasks": 0,
    }
    try:
        for name in ("tmp", "logs", "objects", "cpp", "lumps", "job-results"):
            (output / name).mkdir()
        write(output / "plan.json", value)
        write(
            output / "inputs.json",
            {
                "inventory": inventory,
                "sdk": sdk_state,
                "converter_receipt_sha256": request["converter_receipt_sha256"],
                "sources": providers,
                "metadata": metadata_row,
            },
        )
        for target, members in value["wrappers"].items():
            Path(target).write_text(
                "// Authored SDK include wrapper; owner SDK source remains unchanged.\n" + "".join('#include "' + p + '"\n' for p in members)
            )
        if not plan_only:
            for index, job in enumerate(value["jobs"]):
                if shutil.disk_usage(output).free < RESERVE:
                    raise RuntimeError("native compilation reserve unavailable; outputs retained")
                source = Path(job["source"])
                if job["kind"] == "generated":
                    expand(providers[source.name], source)
                before = sha(source)
                invoke(job["argv"], output, str(index))
                if sha(source) != before:
                    raise ValueError("native input changed during compilation")
                obj = Path(job["output"])
                write(output / "job-results" / (str(index) + ".json"), {"source_sha256": before, "output_sha256": sha(obj), "bytes": obj.stat().st_size})
                result["compile_tasks"] += 1
                if job["kind"] == "generated":
                    source.unlink()
            size = sum(Path(j["output"]).stat().st_size for j in value["jobs"])
            if shutil.disk_usage(output).free < size + 1536 * 1024**2:
                raise RuntimeError("native link reserve unavailable; objects retained")
            invoke(value["link"], output, "link")
            target = output / "libil2cpp.so"
            invoke([str(sdk / profile["objcopy"]), "--strip-all", value["library"], str(target)], output, "strip")
            with target.open("rb") as stream:
                header = stream.read(64)
            if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<HH", header, 16) != (3, 183):
                raise ValueError("expected AArch64 shared ELF library")
            result.update(library_sha256=sha(target), library_bytes=target.stat().st_size)
        if sdk_files(sdk, profile) != sdk_state or input_state(work) != (identity, game, inventory):
            raise ValueError("owner SDK or game input state changed")
        if converter_inputs(receipt, request["converter_receipt_sha256"], sources, metadata, profile, request["sources_compressed"]) != (
            providers,
            metadata_row,
        ):
            raise ValueError("converter providers changed during native production")
        result.update(
            success=True, phase="planned" if plan_only else "native-built", metadata_sha256=metadata_row["sha256"], planned_compile_tasks=len(value["jobs"])
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
