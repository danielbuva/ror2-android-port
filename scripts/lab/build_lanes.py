"""Current isolated build lanes: committed source, APFS work clone, own editor/lock.

Device commands are deliberately outside this dispatcher. Use the canonical
device tooling and explicit APK/payload paths after the build.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from common import ROOT, read, write, copy_file_clone, sha, now, toolchain
from build_lock import host_build_lock, active_lock_handoff
from shared_checkout_build import clean, git


SKIP = {
    "build-cache",
    "captures",
    "cleanup-analysis",
    "coordination",
    "device",
    "device-install-limits",
    "device-switches",
    "editor",
    "host-tests",
    "lab-build",
    "lab-project",
    "logs",
    "migrations",
    "rebuild",
    "retired-storage",
    "runs",
    "tests",
    "__pycache__",
}


def primary(root=ROOT):
    return Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent


def location(name, root=ROOT):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", name or "") or name == "canonical":
        raise ValueError("Lane name must be 1–32 lowercase letters/digits/hyphens; canonical is reserved")
    return primary(root) / ".local/build-lanes" / name


def lock_path(name, root=ROOT):
    lane = location(name, root)
    return lane.parent / ".locks" / (name + ".lock")


def read_lane(name, root=ROOT):
    lane = location(name, root)
    facts = read(lane / "lane.json")
    if (
        lane.is_symlink()
        or facts.get("name") != name
        or Path(facts["checkout"]) != lane / "checkout"
        or Path(facts["lock"]) != lock_path(name, root)
        or Path(facts["canonical_work"]) != primary(root) / "work"
    ):
        raise RuntimeError("Lane ownership paths changed; preserve it for inspection")
    return facts


def check_space(path):
    free = shutil.disk_usage(path).free
    if free < 100 * 1024**3:
        raise RuntimeError("Less than 100 GiB free; prune generated outputs before creating/building a lane")
    return free


def clone(sources, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if sources:
        subprocess.run(["/bin/cp", "-c", "-R", "-P", *map(str, sources), str(destination)], check=True)


def clone_audio_inputs(source_work, work):
    """The current audio manifest explicitly names two legacy provider roots."""
    selection = work / "config/original-game-audio/selection.json"
    if not selection.exists():
        return
    roots = set()
    for value in read(selection).get("inputs", {}).values():
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("Audio lane input must stay relative to the prepared work root")
        if len(path.parts) >= 2 and path.parts[0] == "coordination":
            roots.add(source_work / Path(*path.parts[:2]))
    clone(sorted(roots), work / "coordination")


def create(name, port=None, root=ROOT):
    with host_build_lock(lock_path(name, root), operation="create build lane " + name):
        return _create(name, port, root)


def _create(name, port, root):
    root = Path(root).resolve()
    clean(root)
    base = primary(root)
    lane = location(name, root)
    if lane.exists():
        raise RuntimeError("Lane already exists; remove it explicitly before recreating")
    before = check_space(base)
    if sys.platform != "darwin":
        raise RuntimeError("Build lanes require macOS APFS clone copies; no full-copy fallback")
    if port is None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
    if not isinstance(port, int) or not 1024 <= port <= 65535 or port == 8080:
        raise ValueError("Lane MCP port must be 1024–65535, distinct from canonical 8080")
    source = git(root, "rev-parse", "HEAD")
    checkout = lane / "checkout"
    lane.mkdir(parents=True)
    started = time.monotonic()
    facts = dict(
        name=name,
        seed_commit=source,
        checkout=str(checkout),
        canonical_work=str(base / "work"),
        lock=str(lock_path(name, root)),
        mcp_port=port,
        free_before=before,
        complete=False,
    )
    write(lane / "lane.json", facts)
    # Snapshot only while the canonical staging/build owner is idle. Later lane
    # builds never take this lock or mutate the primary source checkout.
    with host_build_lock(base / "work/coordination/unity-build.lock", operation="clone build lane " + name):
        if any(read(marker).get("mcp_port") == port for marker in lane.parent.glob("*/lane.json") if marker.parent != lane):
            raise ValueError("Lane MCP port is already reserved; remove this incomplete lane and choose another port")
        subprocess.run(["git", "worktree", "add", "--detach", str(checkout), source], cwd=base, check=True, capture_output=True)
        source_work = base / "work"
        work = checkout / "work"
        clone([p for p in source_work.iterdir() if p.name not in SKIP], work)
        clone_audio_inputs(source_work, work)
        project = work / "lab-project"
        clone([p for p in (source_work / "lab-project").iterdir() if p.name not in {"Temp", "Logs"}], project)
        copy_file_clone(root / "android/Assets/Editor/BootstrapMcp.cs", project / "Assets/Editor/BootstrapMcp.cs")
        # Current-build source provenance remains useful for owned staging
        # retirement. Old APK/cache pointers are not iteration anchors here.
        (work / "config/iteration-base.json").unlink(missing_ok=True)
        for p in work.rglob("*"):
            if p.is_symlink():
                target = Path(os.readlink(p))
                if target.is_absolute() and target.is_relative_to(source_work):
                    p.unlink()
                    p.symlink_to(work / target.relative_to(source_work), target_is_directory=target.is_dir())
        local = checkout / ".local"
        local.mkdir(exist_ok=True)
        for name_ in ("lab-venv", "tools"):
            (local / name_).symlink_to(base / ".local" / name_, target_is_directory=True)
        # Gradle/user state is writable and therefore cloned, never shared.
        clone([base / ".local" / n for n in ("android-user", "gradle") if (base / ".local" / n).exists()], local)
        shutil.rmtree(local / "gradle/daemon", ignore_errors=True)
        facts.update(complete=True, clone_seconds=time.monotonic() - started, free_after=check_space(base))
        write(work / "config/build-lane.json", facts)
        write(lane / "lane.json", facts)
    return facts


def start_server(facts):
    lane = Path(facts["checkout"]).parent
    receipt = lane / "server.json"
    port = facts["mcp_port"]
    if receipt.exists():
        pid = read(receipt)["pid"]
        command = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
        if "mcp-for-unity" in command and "--http-port " + str(port) in command:
            return
    checkout = Path(facts["checkout"])
    log = (lane / "mcp-server.log").open("ab")
    environment = dict(os.environ, UNITY_MCP_TELEMETRY_ENABLED="false")
    for key in ("LAB_LANE", "PYTHONPATH", "ROR2LAB_UNITY_BUILD_LOCK_FD"):
        environment.pop(key, None)
    process = subprocess.Popen(
        [
            str(checkout / ".local/tools/unity-mcp/Server/.venv/bin/mcp-for-unity"),
            "--transport",
            "http",
            "--http-host",
            "127.0.0.1",
            "--http-port",
            str(port),
        ],
        cwd=checkout,
        env=environment,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    log.close()
    write(receipt, dict(pid=process.pid, port=port))
    deadline = time.monotonic() + 30
    while process.poll() is None and time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Lane MCP server failed to become ready; inspect its retained log")


def publish(facts):
    """Keep completed artifacts in canonical cache without moving its pointers."""
    work = Path(facts["checkout"]) / "work"
    result = read(work / "config/current-build.json")
    source = Path(result["apk"])
    if not result.get("success") or not source.resolve().is_relative_to(work / "build-cache") or sha(source) != result["apk_sha256"]:
        raise RuntimeError("Lane publication requires its verified successful build artifact")
    destination = Path(facts["canonical_work"]) / "build-cache" / ("lane-" + facts["name"] + "-" + result["request_id"])
    if not destination.resolve().is_relative_to(Path(facts["canonical_work"]) / "build-cache"):
        raise RuntimeError("Unsafe lane artifact request identity")
    if not destination.exists():
        shutil.copytree(source.parent, destination, copy_function=copy_file_clone)
        payload = Path(result["payload_directory"])
        if payload != source.parent / "payload":
            shutil.copytree(payload, destination / "payload", copy_function=copy_file_clone)
    if sha(destination / source.name) != result["apk_sha256"] or any(
        sha(destination / "payload" / name) != expected for name, expected in result["payload"].items()
    ):
        raise RuntimeError("Published lane artifact copy failed verification")
    result["apk"] = str(destination / source.name)
    result["payload_directory"] = str(destination / "payload")
    for key, basename in (("symbolPackage", "symbols.zip"), ("iteration_anchor", "iteration-base.json")):
        if result.get(key):
            result[key] = str(destination / basename)
    anchor = destination / "iteration-base.json"
    if anchor.exists():
        value = read(anchor)
        value.update(apk=result["apk"], payload_directory=result["payload_directory"])
        write(anchor, value)
    write(destination / "result.json", result)
    write(Path(facts["checkout"]).parent / "latest-build.json", result)
    return result


def remove(name, root=ROOT):
    lane = location(name, root)
    with host_build_lock(lock_path(name, root), operation="remove build lane", timeout=0):
        facts = read_lane(name, root)
        checkout = Path(facts["checkout"])
        canonical = Path(facts["canonical_work"])
        for receipt in (canonical / "device").glob("**/installed.json"):
            if str(read(receipt).get("apk", "")).startswith(str(checkout) + os.sep):
                raise RuntimeError("A device receipt still references this lane; retain it or use the published cache artifact")
        for receipt, token in (
            (checkout / "work/editor/lab-process.json", " -projectPath " + str(checkout / "work/lab-project")),
            (lane / "server.json", "--http-port " + str(facts["mcp_port"])),
        ):
            if not receipt.exists():
                continue
            pid = read(receipt)["pid"]
            command = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
            if command.strip() and token not in command:
                raise RuntimeError("Lane process identity changed; preserve it for inspection")
            if command.strip():
                os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + 20
                while subprocess.run(["/bin/ps", "-p", str(pid)], capture_output=True).returncode == 0:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Lane process did not stop; lane retained")
                    time.sleep(0.2)
        gradle_home = checkout / ".local/gradle"
        if gradle_home.is_dir():
            android = Path(
                os.environ.get("UNITY_ANDROID_ROOT", "/Applications/Unity/Hub/Editor/" + toolchain()["unity_version"] + "/PlaybackEngines/AndroidPlayer")
            )
            (launcher,) = (android / "Tools/gradle/lib").glob("gradle-launcher-*.jar")
            # Gradle's registry and stop RPC are scoped to this private home.
            stopped = subprocess.run(
                [
                    str(android / "OpenJDK/bin/java"),
                    "-classpath",
                    str(launcher),
                    "org.gradle.launcher.GradleMain",
                    "--gradle-user-home",
                    str(gradle_home),
                    "--stop",
                ],
                cwd=root,
                env=dict(os.environ, GRADLE_USER_HOME=str(gradle_home)),
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            write(lane / "gradle-stop.json", dict(output=stopped.stdout))
        evidence = canonical / "coordination/build-lanes" / (name + "-" + now())
        work = checkout / "work"
        for folder in ("config", "editor", "logs", "lab-build"):
            for source in (work / folder).rglob("*"):
                if source.is_file() and not source.is_symlink() and source.suffix in {".json", ".log", ".txt"}:
                    copy_file_clone(source, evidence / source.relative_to(work))
        for source in lane.iterdir():
            if source.is_file() and not source.is_symlink() and source.suffix in {".json", ".log", ".txt"}:
                copy_file_clone(source, evidence / source.name)
        if (checkout / ".git").is_file():
            clean(checkout)
            removed = subprocess.run(["git", "worktree", "remove", "--force", str(checkout)], cwd=root, capture_output=True, text=True)
            if removed.returncode and (checkout / ".git").exists():
                raise RuntimeError("Git worktree removal failed; preserve the lane: " + removed.stderr)
        # Git may remove its registration before reporting residual registry
        # files. Recovery must not run Git in the primary ancestor checkout.
        shutil.rmtree(lane)
        write(evidence / "removed.json", dict(facts, removed=True, free_after_remove=shutil.disk_usage(primary(root)).free))
    return dict(removed=True, evidence=str(evidence / "removed.json"))


def dispatch(name, arguments, root=ROOT):
    if not arguments or arguments[0] not in {"build", "editor", "preflight", "prototype"}:
        raise RuntimeError("LAB_LANE is for host build/editor/preflight actions only; unset it for canonical device operations")
    if arguments[0] == "preflight" and "--host-only" not in arguments:
        raise RuntimeError("Lane preflight requires --host-only; device checks stay canonical")
    if arguments[0] == "prototype":
        allowed = {"whole-catalog-build", "whole-catalog-code-build", "whole-catalog-fast-build", "whole-catalog-scripts-build"}
        if "--action" not in arguments or arguments[-1] == "--action" or arguments[arguments.index("--action") + 1] not in allowed:
            raise RuntimeError("LAB_LANE prototype supports only the four current whole-catalog build actions")
    clean(root)
    source = git(root, "rev-parse", "HEAD")
    with host_build_lock(lock_path(name, root), operation="lane " + name):
        facts = read_lane(name, root)
        if not facts.get("complete"):
            raise RuntimeError("Lane creation did not complete; remove and recreate it")
        check_space(primary(root))
        checkout = Path(facts["checkout"])
        clean(checkout)
        git(checkout, "switch", "--detach", source)
        if arguments[0] != "preflight":
            start_server(facts)
        env, descriptors = active_lock_handoff(facts["lock"])
        env = dict(os.environ, **env)
        env.pop("LAB_LANE", None)
        result = subprocess.run([str(checkout / "dev"), *arguments], cwd=checkout, env=env, pass_fds=descriptors)
        if git(root, "rev-parse", "HEAD") != source:
            raise RuntimeError("Worker HEAD changed during the lane operation")
        if result.returncode == 0 and arguments[0] in {"build", "prototype"}:
            artifact = publish(facts)
            print(json.dumps({"published_apk": artifact["apk"], "payload_directory": artifact["payload_directory"]}))
        return result.returncode


def main(arguments):
    parser = argparse.ArgumentParser(description="Current APFS build lanes; canonical work/device state stays unchanged.")
    parser.add_argument("--action", choices=("create", "list", "remove"), required=True)
    parser.add_argument("--name", default=os.environ.get("LAB_LANE"))
    parser.add_argument("--port", type=int, help="Private loopback MCP port (default: choose a free port)")
    args = parser.parse_args(arguments)
    if args.action == "list":
        result = [read(p) for p in (primary() / ".local/build-lanes").glob("*/lane.json")]
    elif args.action == "create":
        result = create(args.name, args.port)
    else:
        result = remove(args.name)
    print(json.dumps(result, indent=2))
    return 0
