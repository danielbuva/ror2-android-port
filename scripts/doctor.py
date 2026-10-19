#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import datetime
import re
from pathlib import Path
import argparse

root = Path(__file__).resolve().parents[1]
if os.environ.get("LAB_COORDINATION_GUARD") == "1" and (root / "work/coordination/claude-r9.lock").exists():
    raise SystemExit("Doctor blocked by work/coordination/claude-r9.lock")
parser = argparse.ArgumentParser()
parser.add_argument("--device")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()
sys.path.insert(0, str(root / "scripts/lab"))
from device_context import select_device, storage_policy, receipt_directory
pin = json.loads((root / "environment/toolchain.json").read_text())
checks = []


def check(name, ok, detail):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def run(args, timeout=20):
    if os.environ.get("LAB_COORDINATION_GUARD") == "1" and (root / "work/coordination/claude-r9.lock").exists():
        return False, "Doctor blocked by work/coordination/claude-r9.lock"
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


for tool in [
    "git",
    "gh",
    "jq",
    "rg",
    "fd",
    "curl",
    "wget",
    "python3",
    "uv",
    "dotnet",
    "cmake",
    "ninja",
    "pkg-config",
    "7zz",
    "magick",
    "ffmpeg",
    "scrcpy",
    "adb",
]:
    p = shutil.which(tool)
    check(tool, p, p or "Missing")
ok, out = run(["xcode-select", "-p"])
check("Command Line Tools", ok, out)
unity = Path(os.environ["UNITY_EDITOR"])
check("Unity editor", unity.is_file(), str(unity))
plist = unity.parent.parent / "Info.plist"
if plist.exists():
    import plistlib

    v = plistlib.loads(plist.read_bytes()).get("CFBundleVersion", "unknown")
    check("Unity exact version", v == pin["unity_version"], v)
for name, path in [
    ("Android SDK", Path(os.environ["ANDROID_HOME"]) / ("platforms/android-" + str(pin["android_api"]) + "/android.jar")),
    ("Android NDK", Path(os.environ["ANDROID_NDK_ROOT"]) / "source.properties"),
    ("Unity JDK", Path(os.environ["JAVA_HOME"]) / "bin/java"),
    ("Android module", Path(os.environ["UNITY_ANDROID_ROOT"]) / "UnityEditor.Android.Extensions.dll"),
]:
    check(name, path.exists(), str(path))
for name, cmd in [("ilspycmd", [str(root / "scripts/ilspycmd"), "--version"]), ("AssetRipper", [str(root / "scripts/assetripper"), "--version"])]:
    ok, out = run(cmd)
    check(name, ok, out)
check("SteamCMD", (root / ".local/tools/steamcmd/steamcmd.sh").exists(), "Run .local/tools/steamcmd/steamcmd.sh +quit to reverify")
ok, _ = run(["gh", "auth", "status"])
check("GitHub authentication", ok, "Authenticated" if ok else "Run gh auth login")
ok, out = run(["/opt/homebrew/bin/adb", "devices"])
target = None
try:
    config_path = root / "work/config/local.json"
    config = json.loads(config_path.read_text())
    if not ok:
        raise ValueError("ADB device inventory failed")
    inventory = [{"serial": p[0], "state": p[1]} for line in out.splitlines()[1:] if len(p := line.split()) >= 2]
    target = select_device(config, inventory, cli_selector=args.device, env_selector=os.environ.get("LAB_DEVICE"))
    check("ADB target", True, "Selected configured/allowlisted device authorized")
except (OSError, ValueError) as e:
    check("ADB target", False, str(e))
if target:
    base = ["/opt/homebrew/bin/adb", "-s", target, "shell"]
    ok, abi = run(base + ["getprop ro.product.cpu.abilist"])
    check("Target ARM64", ok and "arm64-v8a" in abi, abi)
    ok, vols = run(base + ["sm list-volumes all"])
    private = [l.split() for l in vols.splitlines() if l.startswith("private:") and " mounted " in l]
    try:
        mode = storage_policy(config, target)
    except ValueError:
        mode = None
    check("Configured storage mode", mode in ["adopted", "internal"], mode)
    adopted_ok = len(private) == 1 and len(private[0]) >= 3 and bool(re.fullmatch("[a-fA-F0-9-]+", private[0][2]))
    backing_ok = not private if mode == "internal" else adopted_ok if mode == "adopted" else False
    check("Configured storage backing", ok and backing_ok, "Internal-only device" if mode == "internal" else vols)
    for v in private if adopted_ok else []:
        ok, out = run(base + ["df -k /mnt/expand/" + v[2]])
        try:
            free = int(out.splitlines()[-1].split()[3])
            check("Adopted free space", ok and free > 1024 * 1024, f"{free / 1024 / 1024:.1f} GiB free (minimum check: 1 GiB)")
        except (ValueError, IndexError):
            check("Adopted free space", False, out)
    ok, out = run(base + ["df -k /data"])
    check("Internal storage query", ok, out)
ok, out = run(["codex", "mcp", "get", "unity-bootstrap"])
check("Unity MCP configuration", ok and "127.0.0.1:8080/mcp" in out, "unity-bootstrap at loopback port 8080")
python = root / ".local/tools/unity-mcp/Server/.venv/bin/python"
ok, out = run([str(python), str(root / "scripts/mcp-check.py")], 40)
check("Unity MCP server responds", ok, "MCP initialize/tools/resources probe" if ok else out[-500:])
if ok:
    d = json.loads(out)
    inst = d.get("mcpforunity://instances", {})
    texts = " ".join(x.get("text", "") for x in inst.get("contents", []))
    try:
        obj = json.loads(texts)
        instances = obj.get("instances", obj.get("data", {}).get("instances", []))
        connected = bool(instances)
    except (ValueError, AttributeError):
        connected = False
    check("Unity editor MCP connected", connected, texts[:800])
smoke_root = receipt_directory(root / "work", {"serial": target, "default_serial": config["device_serial"]}) if target else None
scoped_smokes = sorted(smoke_root.glob("bootstrap/*/result.json")) if smoke_root else []
smoke = scoped_smokes[-1] if scoped_smokes else root / "environment/smoke-result.json"
if target and target != config["device_serial"] and not scoped_smokes:
    smoke = smoke_root / "bootstrap/missing/result.json"
smoke_receipt = json.loads(smoke.read_text()) if smoke.exists() else {}
passed = bool(target and smoke_receipt.get("success") and smoke_receipt.get("serial") == target)
check("Completed ARM64 device smoke test", passed, str(smoke))
exercise = root / "environment/mcp-exercise.json"
check("Completed Unity MCP editor exercise", exercise.exists() and json.loads(exercise.read_text()).get("success", False), str(exercise))
result = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "ready": all(c["ok"] for c in checks), "checks": checks}
if "--json" in sys.argv:
    print(json.dumps(result, indent=2))
else:
    for c in checks:
        print(("OK   " if c["ok"] else "FAIL ") + c["name"] + ": " + str(c["detail"]).replace("\n", " | "))
    print("READY" if result["ready"] else "PARTIALLY READY")
sys.exit(0 if result["ready"] else 1)
