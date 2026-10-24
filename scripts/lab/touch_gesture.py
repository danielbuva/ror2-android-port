"""Scoped Android 13+ multi-touch diagnostic for an already running owned APK.

Compiles authored Java through the bundled SDK; no Unity/editor operation.
Every event uses the platform targetUid overload. Temporary device files are
removed; a failed dispatch stops only the still-matching owned game process.
"""

import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import uuid

from common import ROOT, WORK, digest, now, read, sha, toolchain, write
from device import Device, PACKAGE
from installed_attempt import bind_installed_apk, validate_expected_apk_sha256
from session_cleanup_check import _remote_path_state


def validate_request(value):
    if not isinstance(value, dict) or set(value) != {"pid", "width", "height", "steps"}:
        raise ValueError("Gesture requires pid, width, height and steps only")
    if not isinstance(value["pid"], str) or not re.fullmatch(r"[1-9][0-9]*", value["pid"]):
        raise ValueError("Gesture requires the observed game PID")
    if any(type(value[key]) is not int or value[key] <= 0 for key in ("width", "height")):
        raise ValueError("Gesture requires positive viewport dimensions")
    steps = value["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 128:
        raise ValueError("Use 1 to 128 touch steps")
    active = set()
    wait = 0
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("Each gesture step is an object")
        if step.get("action") == "wait":
            if set(step) != {"action", "ms"} or type(step["ms"]) is not int or step["ms"] < 0:
                raise ValueError("Wait uses nonnegative integer milliseconds")
            wait += step["ms"]
            if wait > 30000:
                raise ValueError("Gesture waits exceed 30 seconds")
            continue
        if set(step) != {"action", "id", "x", "y"} or step["action"] not in {"down", "move", "up"}:
            raise ValueError("Touch uses down/move/up, id, x and y")
        if type(step["id"]) is not int or not 0 <= step["id"] <= 9:
            raise ValueError("Pointer IDs must be 0 to 9")
        for axis, limit in (("x", value["width"]), ("y", value["height"])):
            if type(step[axis]) not in (int, float) or not math.isfinite(step[axis]) or not 0 <= step[axis] < limit:
                raise ValueError("Touch coordinate lies outside the declared viewport")
        held = step["id"] in active
        if step["action"] == "down":
            if held:
                raise ValueError("Pointer already held")
            active.add(step["id"])
        elif not held:
            raise ValueError("Pointer is not held")
        elif step["action"] == "up":
            active.remove(step["id"])
    # A deliberate final hold is canceled by the Java driver's finally block.
    return value


def compile_tool():
    source = ROOT / "tools/android-touch-gesture/LabTouchGesture.java"
    sdk = Path(os.environ["UNITY_ANDROID_ROOT"]) / "SDK"
    android = sdk / "platforms" / ("android-" + str(toolchain()["android_api"])) / "android.jar"
    build_tools = sdk / "build-tools" / toolchain()["android_build_tools"]
    identity = dict(source_sha256=sha(source), android_jar_sha256=sha(android), d8_sha256=sha(build_tools / "lib/d8.jar"))
    root = WORK / "touch-gesture-tool"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / digest(identity)
    if destination.exists():
        receipt = read(destination / "receipt.json")
        if receipt.get("identity") != identity or sha(destination / "classes.dex") != receipt.get("dex_sha256"):
            raise RuntimeError("Touch tool cache differs; preserve and inspect it")
        return destination / "classes.dex"
    with tempfile.TemporaryDirectory(prefix="compile-", dir=root) as temporary:
        directory = Path(temporary)
        classes = directory / "classes"
        classes.mkdir()
        commands = [
            [str(Path(os.environ["JAVA_HOME"]) / "bin/javac"), "-source", "8", "-target", "8", "-cp", str(android), "-d", str(classes), str(source)],
            [str(build_tools / "d8"), "--min-api", "30", "--lib", str(android), "--output", str(directory)],
        ]
        for index, command in enumerate(commands):
            if index == 1:
                command.extend(str(path) for path in sorted(classes.glob("*.class")))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (directory / ("compile-%d.log" % index)).write_text(result.stdout + result.stderr)
            if result.returncode:
                failure = root / ("failed-" + uuid.uuid4().hex)
                failure.mkdir()
                for path in directory.glob("*.log"):
                    (failure / path.name).write_bytes(path.read_bytes())
                write(failure / "identity.json", identity)
                raise RuntimeError("Touch tool compilation failed: " + result.stdout + result.stderr)
        destination.mkdir()
        for path in directory.glob("*.log"):
            (destination / path.name).write_bytes(path.read_bytes())
        (destination / "classes.dex").write_bytes((directory / "classes.dex").read_bytes())
        write(destination / "receipt.json", dict(identity=identity, dex_sha256=sha(destination / "classes.dex")))
    return destination / "classes.dex"


def owned_display_zero_focus(text):
    """Require the owned window on display 0, never a second-screen match."""
    displays = list(re.finditer(r"^  Display: mDisplayId=([0-9]+)\b", text, re.M))
    primary = [index for index, match in enumerate(displays) if match[1] == "0"]
    if len(primary) != 1:
        return False
    index = primary[0]
    block = text[displays[index].end() : displays[index + 1].start() if index + 1 < len(displays) else len(text)]
    focus = re.findall(r"^  mCurrentFocus=(.*)$", block, re.M)
    return len(focus) == 1 and re.fullmatch(r"Window\{[^\n]*\s" + re.escape(PACKAGE) + r"/[^\n]*\}", focus[0]) is not None


def run(target, expected_apk_sha256=None):
    expected = validate_expected_apk_sha256(expected_apk_sha256)
    if expected is None:
        raise ValueError("touch-gesture requires --expected-apk-sha256")
    request = Path(target).resolve(strict=True)
    if request.stat().st_size > 65536:
        raise ValueError("Gesture request exceeds 64 KiB")
    value = validate_request(read(request))
    device = Device()
    installed = device.owned()
    bind_installed_apk(installed, expected_sha256=expected)
    if device.sh("pidof", PACKAGE, check=False).strip() != value["pid"]:
        raise RuntimeError("Gesture PID differs from the currently owned game process")
    if int(device.sh("getprop", "ro.build.version.sdk")) < 33:
        raise RuntimeError("Targeted touch injection requires Android 13 or newer")
    window = device.sh("dumpsys", "window", "displays")
    if not owned_display_zero_focus(window):
        raise RuntimeError("The owned game is not the focused window")
    packages = device.sh("cmd", "package", "list", "packages", "-U", PACKAGE)
    matches = [match for line in packages.splitlines() if (match := re.fullmatch(r"package:" + re.escape(PACKAGE) + r" uid:([0-9]+)", line.strip()))]
    if len(matches) != 1 or int(matches[0][1]) < 10000:
        raise RuntimeError("Cannot bind touch injection to the owned application UID")
    match = matches[0]
    dex = compile_tool()
    output = device.evidence_directory("experiments", "touch-gesture", now())
    output.mkdir(parents=True, exist_ok=False)
    write(output / "request.json", value)
    write(output / "binding.json", dict(apk_sha256=expected, pid=value["pid"], uid=int(match[1]), dex_sha256=sha(dex), request_sha256=sha(request)))
    prefix = "/data/local/tmp/ror2lab-touch-" + uuid.uuid4().hex
    remote = (prefix + ".dex", prefix + ".json")
    if any(_remote_path_state(device, path) != "absent" for path in remote):
        raise RuntimeError("Temporary touch target already exists; preserve it")
    dispatched = False
    result = dict(success=False)
    try:
        for local, path in zip((dex, output / "request.json"), remote):
            device.cmd("push", str(local), path)
            if device.sh("sha256sum", path).split()[0] != sha(local):
                raise RuntimeError("Temporary touch input hash differs")
        dispatched = True
        command = shlex.join(["env", "CLASSPATH=" + remote[0], "app_process", "/system/bin", "LabTouchGesture", remote[1], match[1]])
        raw = device.cmd("shell", command, timeout=90)
        (output / "driver.log").write_text(raw)
        result = json.loads(raw.strip().splitlines()[-1])
        if result.get("success") is not True:
            raise RuntimeError("Touch driver did not report completion")
        return dict(result, evidence=str(output.relative_to(WORK.parent)), apk_sha256=expected)
    except Exception as error:
        result = dict(success=False, error=str(error))
        try:
            if dispatched and device.sh("pidof", PACKAGE, check=False).strip() == value["pid"]:
                bind_installed_apk(device.owned(), expected_sha256=expected)
                device.sh("am", "force-stop", PACKAGE)
        except Exception as cleanup:
            result["stop_error"] = str(cleanup)
        raise
    finally:
        errors = []
        for path in remote:
            try:
                device.sh("rm", "-f", path)
                if _remote_path_state(device, path) != "absent":
                    errors.append("temporary touch file remains")
            except Exception as cleanup:
                errors.append(str(cleanup))
        was_success = result.get("success") is True
        result["cleanup_errors"] = errors
        if errors:
            result["success"] = False
        write(output / "result.json", result)
        if errors and was_success:
            raise RuntimeError("Touch temporary-file cleanup failed; see " + str(output))
