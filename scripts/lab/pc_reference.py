"""Build and run the local Steam reference recorder in its own APFS clone."""

import argparse
import fcntl
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, WORK, game, read, sha, write

TOOLS = ROOT / "tools/pc-reference"
LOCAL = WORK / "coordination/pc-reference"
WINE = Path("/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine")
GAME_EXE = "Risk of Rain 2.exe"
MANAGED_DIR = "Risk of Rain 2_Data/Managed"
BOOTSTRAP = "BepInEx_win_x64_5.4.23.5.zip"
BOOTSTRAP_URL = f"https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.5/{BOOTSTRAP}"
BOOTSTRAP_SHA = "82f9878551030f54657792c0740d9d51a09500eeae1fba21106b0c441e6732c4"
CLONE_NAME = "ror2-reference"
RECEIPT = ".ror2lab-reference.json"
EXCLUDE = {"steam_appid.txt", "bepinex", "winhttp.dll", "doorstop_config.ini", ".doorstop_version"}
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")
FRAME = re.compile(r"frame(?:-[0-9]{4,})?\.png\Z")
ACTIONS = {"capture", "spawn", "state", "skill", "grapple", "ping", "fire-trail", "move"}


def steam_build(source):
    manifest = source.parent.parent / "appmanifest_632360.acf"
    match = re.search(r'"buildid"\s+"([0-9]+)"', manifest.read_text())
    if not match:
        raise RuntimeError("Steam app 632360 has no recorded build ID")
    return match[1]


def prepare_clone(source, drive):
    clone = drive / CLONE_NAME
    if source == clone or clone in source.parents or source in clone.parents:
        raise RuntimeError("Configured input and reference clone must be disjoint")
    identity = {"build": steam_build(source), "managed_sha256": sha(source / MANAGED_DIR / "RoR2.dll")}
    if clone.is_symlink():
        raise RuntimeError("Reference path must be a real directory")
    if clone.exists():
        receipt = clone / RECEIPT
        if receipt.is_symlink() or not receipt.is_file():
            raise RuntimeError("Reference path belongs to another installation")
        previous = read(receipt)
        if previous == identity:
            return clone, identity

    # Stage beside the destination so APFS can share the original blocks.
    with tempfile.TemporaryDirectory(prefix=".ror2-reference-", dir=drive) as staging:
        staged = Path(staging) / CLONE_NAME
        staged.mkdir()
        entries = sorted(p for p in source.iterdir() if p.name.casefold() not in EXCLUDE)
        subprocess.run(["/bin/cp", "-c", "-R", "-P", *entries, staged], check=True)
        if sha(staged / MANAGED_DIR / "RoR2.dll") != identity["managed_sha256"] or steam_build(source) != identity["build"]:
            raise RuntimeError("Steam input changed while staging the reference")
        write(staged / RECEIPT, identity)
        if clone.exists():
            old = Path(staging) / "old"
            clone.rename(old)
            try:
                staged.rename(clone)
            except OSError:
                old.rename(clone)
                raise
        else:
            staged.rename(clone)
    return clone, identity


def install_recorder(clone):
    archive = LOCAL / BOOTSTRAP
    if not archive.is_file():
        temporary = archive.with_suffix(".download")
        with urllib.request.urlopen(BOOTSTRAP_URL, timeout=45) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(archive)
    if sha(archive) != BOOTSTRAP_SHA:
        raise RuntimeError("Pinned BepInEx archive digest mismatch")
    with zipfile.ZipFile(archive) as package:
        # The archive is hash-pinned. Install only the process loader and its core.
        for path in package.namelist():
            if path.startswith("BepInEx/core/") or path in {"doorstop_config.ini", "winhttp.dll", ".doorstop_version"}:
                package.extract(path, clone)
    managed = clone / MANAGED_DIR
    mono_root = Path(os.environ["UNITY_EDITOR"]).parents[1] / "MonoBleedingEdge"
    compiler = mono_root / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    plugins = clone / "BepInEx/plugins"
    plugins.mkdir(exist_ok=True)
    if (clone / "steam_appid.txt").exists():
        raise RuntimeError("Reference directory contains an unexpected app ID override")
    if any(plugins.iterdir()) and {p.name for p in plugins.iterdir()} != {"Ror2Lab.Reference.dll"}:
        raise RuntimeError("Reference clone contains unexpected plug-ins")
    core = clone / "BepInEx/core"
    refs = [
        core / "0Harmony.dll",
        core / "BepInEx.dll",
        *managed.glob("UnityEngine.*.dll"),
        *[
            managed / (name + ".dll")
            for name in (
                "RoR2",
                "Facepunch.Steamworks",
                "HGCSharpUtils",
                "KinematicCharacterController",
                "Zio",
                "Rewired_Core",
                "AK.Wwise.Unity.API",
                "UnityEngine",
                "com.unity.multiplayer-hlapi.Runtime",
                "netstandard",
            )
        ],
    ]
    with tempfile.TemporaryDirectory(prefix=".recorder-", dir=clone) as temporary:
        assembly = Path(temporary) / "Ror2Lab.Reference.dll"
        subprocess.run(
            [
                mono_root / "bin/mono",
                compiler,
                "-nologo",
                "-nowarn:0649",
                "-target:library",
                "-deterministic",
                "-optimize+",
                f"-out:{assembly}",
                *(f"-r:{p}" for p in sorted(refs)),
                *sorted(TOOLS.glob("*.cs")),
            ],
            check=True,
        )
        assembly.replace(plugins / assembly.name)


def windows_path(path):
    return "Z:" + str(Path(path).resolve()).replace("/", "\\")


def positive_steam_account(output):
    match = re.search(r"^\s*ActiveUser\s+REG_DWORD\s+(0x[0-9a-f]+)\s*$", output, re.I | re.M)
    return bool(match and int(match[1], 16))


def memory_pressure_level():
    return int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"], text=True).strip())


def check_capture_memory():
    pressure = memory_pressure_level()
    if pressure >= 4:
        raise RuntimeError(f"Host memory pressure is critical (level {pressure})")
    summary = subprocess.check_output(["/usr/bin/memory_pressure", "-Q"], text=True)
    free = re.search(r"^System-wide memory free percentage: (\d+)%$", summary, re.M)
    if free is None:
        raise RuntimeError("Could not read free host memory from memory_pressure -Q")
    if int(free[1]) < 25:
        raise RuntimeError(f"Host memory is {free[1]}% free; captures require at least 25%")


def check_capture_host(command):
    steam = subprocess.run(["/usr/bin/pgrep", "-if", r'(^|[/\\]|[[:space:]"])steam[.]exe([[:space:]"]|$)'], capture_output=True)
    if steam.returncode == 1:
        raise RuntimeError("NEED owner: start and sign in to Steam in the reference bottle")
    steam.check_returncode()
    processes = subprocess.check_output([*command, "tasklist.exe"], text=True, timeout=35)
    if re.search(r"^\s*Steam\.exe\s+", processes, re.I | re.M) is None:
        raise RuntimeError("NEED owner: start and sign in to Steam in the reference bottle")
    if GAME_EXE.casefold() in processes.casefold():
        raise RuntimeError("A copy of the game is already running in the reference bottle")
    account = subprocess.run(
        [*command, "reg.exe", "query", r"HKCU\Software\Valve\Steam\ActiveProcess", "/v", "ActiveUser"],
        capture_output=True,
        text=True,
        timeout=35,
    )
    if account.returncode or not positive_steam_account(account.stdout):
        raise RuntimeError("NEED owner: sign in to Steam in the reference bottle")


def run_capture(command, log, timeout):
    check_capture_memory()
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True) as process:
        try:
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    return process.wait(timeout=min(1, remaining))
                except subprocess.TimeoutExpired:
                    pressure = memory_pressure_level()
                    if pressure >= 4:
                        raise RuntimeError(f"Capture aborted: host memory pressure reached critical level {pressure}") from None
            raise subprocess.TimeoutExpired(command, timeout)
        except BaseException:
            # Wine may give its GUI process a separate session. The unique
            # request argument identifies this capture in either session.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            request = command[-1]
            processes = subprocess.check_output(["/bin/ps", "-axww", "-o", "pid=,args="], text=True, errors="replace")
            for row in processes.splitlines():
                pid, arguments = row.split(maxsplit=1)
                if "--ror2lab-reference" in arguments and request in arguments:
                    with suppress(ProcessLookupError):
                        os.kill(int(pid), signal.SIGKILL)
            raise


def load_plan(plan):
    settings = plan.get("settings") if isinstance(plan, dict) else None
    if not isinstance(settings, dict) or any(type(settings.get(key)) is not int or settings[key] <= 0 for key in ("width", "height", "fps")):
        raise ValueError("Plan requires positive integer width, height and FPS")
    if type(settings.get("fov")) not in (float, int) or not 1 <= settings["fov"] < 179:
        raise ValueError("Plan requires a vertical field of view from 1 to 178 degrees")
    scenarios = plan.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Plan requires at least one scenario")
    seen = set()

    def check_ids(entries):
        if not isinstance(entries, list) or not entries:
            raise ValueError("Each scenario requires at least one step")
        for entry in entries:
            identifier = entry.get("id") if isinstance(entry, dict) else None
            if not isinstance(identifier, str) or not NAME.fullmatch(identifier) or identifier in seen:
                raise ValueError("Scenario and step IDs must be unique lowercase path components")
            seen.add(identifier)

    check_ids(scenarios)
    for scenario in scenarios:
        check_ids(scenario.get("steps"))
        seed = scenario.get("seed")
        if not isinstance(seed, str) or not seed.isascii() or not seed.isdecimal() or not 0 <= int(seed) < 2**64:
            raise ValueError("Scenario seed must be a decimal string in the unsigned 64-bit range")
        if not scenario.get("scene") or not scenario.get("body"):
            raise ValueError("Scenario requires an expected scene and survivor body")
        spawned = set()
        for step in scenario["steps"]:
            if step.get("action") not in ACTIONS:
                raise ValueError("Step requires a supported action")
            if step["action"] == "grapple":
                hold, window = step.get("holdSeconds"), step.get("recordSeconds")
                if not all(type(value) in (int, float) and math.isfinite(value) for value in (hold, window)) or not 0 < hold < window:
                    raise ValueError("Grapple requires a recording window longer than the positive hold")
            if "observeProjectileHitOn" in step:
                target, window, aim = step["observeProjectileHitOn"], step.get("recordSeconds"), step.get("aimDirection")
                if (
                    step["action"] != "skill"
                    or step.get("subject", "player") != "player"
                    or step.get("value") not in ("primary", "secondary", "utility", "special")
                    or not isinstance(target, str)
                    or target not in spawned
                    or type(window) not in (int, float)
                    or not 0 < window <= 2
                    or not isinstance(aim, list)
                    or len(aim) != 3
                    or not all(type(value) in (int, float) and math.isfinite(value) for value in aim)
                    or not any(aim)
                ):
                    raise ValueError("Projectile capture requires a player skill, earlier target spawn, aim direction and up to two seconds")
            if step["action"] == "spawn" and isinstance(step.get("subject"), str):
                spawned.add(step["subject"])
    return scenarios


def encode_capture_video(folder, timeline, ffmpeg, clip):
    if len(timeline) < 2 or any(not FRAME.fullmatch(frame["frame"]) for frame in timeline):
        raise RuntimeError("Capture video requires a valid PNG timeline")
    lines = ["ffconcat version 1.0"]
    for frame, next_frame in zip(timeline, timeline[1:]):
        duration = next_frame["seconds"] - frame["seconds"]
        if not math.isfinite(duration) or duration <= 0:
            raise RuntimeError("Capture frame timestamps must increase")
        lines.extend((f"file {frame['frame']}", "option framerate 1000", f"duration {duration:.6f}"))
    lines.extend((f"file {timeline[-1]['frame']}", "option framerate 1000"))
    receipt = folder / "video.ffconcat"
    receipt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-f", "concat", "-safe", "0", "-i", receipt, "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", clip],
        cwd=folder,
        timeout=60,
        check=True,
    )


def capture_files(output, scenario, result):
    steps = result["steps"]
    if [step["id"] for step in steps] != [step["id"] for step in scenario["steps"]]:
        raise RuntimeError("Result did not produce all planned steps in order")
    files = ["audio-events.jsonl"]
    if result.get("audio_capture_status") == "AK_Success":
        files.append("mix.wav")
    for planned, step in zip(scenario["steps"], steps):
        folder = step["id"]
        files.extend((f"{folder}/frame.png", f"{folder}/state.json"))
        files.extend(f"{folder}/{frame['frame']}" for frame in step["timeline"][1:])
        if planned.get("action") == "grapple":
            files.extend((f"{folder}/grapple-ticks.jsonl", f"{folder}/grapple.mp4"))
        if planned.get("observeProjectileHitOn"):
            files.extend((f"{folder}/projectile-trace.json", f"{folder}/projectile.mp4"))
    artifacts = {}
    for name in files:
        path = (output / name).resolve()
        if not path.is_relative_to(output) or not path.is_file():
            raise RuntimeError(f"Capture artifact is missing: {name}")
        artifacts[name] = sha(path)
    return artifacts


def run_plan(args, clone, identity, command, plan, scenarios):
    check_capture_host(command)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg and any(step["action"] == "grapple" or step.get("observeProjectileHitOn") for scenario in scenarios for step in scenario["steps"]):
        raise RuntimeError("Reference video capture requires ffmpeg")
    root = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=LOCAL))
    write(root / "plan.json", plan)
    manifest = {"schema_version": 1, "status": "running", "platform": "crossover-d3d11", **identity, "scenarios": []}
    try:
        for index, scenario in enumerate(scenarios):
            if index:
                check_capture_host(command)
            output = root / scenario["id"]
            output.mkdir()
            request = output / "request.json"
            write(request, {"settings": plan["settings"], "scenario": scenario})
            with (output / "wine.log").open("wb") as log:
                exit_code = run_capture(
                    [
                        *command,
                        "--dll",
                        "winhttp=n,b",
                        "--workdir",
                        clone,
                        clone / GAME_EXE,
                        "-force-d3d11",
                        "-screen-fullscreen",
                        "0",
                        "-screen-width",
                        str(plan["settings"]["width"]),
                        "-screen-height",
                        str(plan["settings"]["height"]),
                        "-logFile",
                        windows_path(output / "player.log"),
                        "--ror2lab-reference",
                        windows_path(request),
                    ],
                    log,
                    args.timeout,
                )
            terminal = output / "result.json"
            result = read(terminal) if terminal.is_file() else {"status": "failed", "error": "Recorder never produced a result"}
            manifest["scenarios"].append(
                {
                    "id": scenario["id"],
                    "result": str(terminal.relative_to(root)) if terminal.is_file() else None,
                    "exit_code": exit_code,
                    **result,
                }
            )
            if exit_code or result["status"] != "passed":
                raise RuntimeError(result.get("error") or f"{scenario['id']} exited with code {exit_code}")
            for step in result["steps"]:
                if step.get("grapple_ticks"):
                    clip = "grapple.mp4"
                elif step.get("projectile_trace"):
                    clip = "projectile.mp4"
                else:
                    continue
                encode_capture_video(output / step["id"], step["timeline"], ffmpeg, clip)
                step["video"] = f"{step['id']}/{clip}"
            manifest["scenarios"][-1]["sha256"] = capture_files(output, scenario, result)
        manifest["status"] = "passed"
    except BaseException as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        write(root / "manifest.json", manifest)
        print(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Current: record the Steam PC reference from a separate CrossOver clone")
    parser.add_argument("plan", type=Path, nargs="?", help="Capture plan JSON")
    parser.add_argument("--prepare-only", action="store_true", help="APFS-clone the input and compile the recorder without launching Steam or the game")
    parser.add_argument("--validate-plan", action="store_true", help="Validate a plan without accessing the local game")
    parser.add_argument("--scenario", help="Only run the named scenario from the plan")
    parser.add_argument("--timeout", type=int, default=240, help="Per-scenario launch-to-exit timeout in seconds")
    args = parser.parse_args(argv)
    if args.plan is None and not args.prepare_only:
        parser.error("a capture plan is required unless --prepare-only is set")
    try:
        plan = read(args.plan) if args.plan else None
        scenarios = load_plan(plan) if args.plan else None
        if args.scenario:
            scenarios = [scenario for scenario in scenarios or () if scenario["id"] == args.scenario]
            if not scenarios:
                raise ValueError("Scenario is not present in the plan")
        if args.validate_plan:
            if scenarios is None:
                raise ValueError("Plan validation requires a capture plan")
            print(f"Validated {len(scenarios)} scenario(s)")
            return 0
        source = game()
        drive = next((path for path in source.parents if path.name == "drive_c"), None)
        if drive is None or not (drive.parent / "cxbottle.conf").is_file() or not WINE.is_file():
            raise RuntimeError("Configured Steam input must be inside a local CrossOver bottle")
        LOCAL.mkdir(parents=True, exist_ok=True)
        with (LOCAL / "recorder.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            clone, identity = prepare_clone(source, drive)
            install_recorder(clone)
            if args.prepare_only:
                print(json.dumps({"status": "prepared", "reference_path": str(clone), **identity}))
            else:
                run_plan(args, clone, identity, [WINE, "--bottle", drive.parent.name, "--no-update"], plan, scenarios)
    except subprocess.CalledProcessError as error:
        print(f"pc-reference: {Path(error.cmd[0]).name} exited with code {error.returncode}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"pc-reference: {error}", file=sys.stderr)
        return 1
    return 0
