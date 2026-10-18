import argparse
import sys
from common import *

p = argparse.ArgumentParser(description="Local RoR2 porting laboratory; generated evidence lives under ignored work/.")
p.add_argument(
    "command",
    choices=[
        "diagnostics",
        "test",
        "doctor",
        "inspect",
        "decompile",
        "export-project",
        "preflight",
        "check-baseline",
        "build",
        "install",
        "sync-data",
        "run",
        "logs",
        "crash",
        "screenshot",
        "reset",
        "smoke",
        "storage",
        "perf",
        "graphics",
        "editor",
        "prototype",
    ],
)
p.add_argument("--work-dir", help="Current: read-only local inputs for inherited-state-check, assembly-transforms-check or rebuild-step (default: work/)")
p.add_argument("--step", help="Current: rebuild-step name (assemblies, composition; validate-bindings reserved)")
p.add_argument("--dest", help="Current: rebuild-step destination beneath this clone's work/rebuild/")
p.add_argument("--compare-only", action="store_true", help="Current: compare an existing rebuild-step destination without writing")
p.add_argument("--full", action="store_true")
p.add_argument("--force", action="store_true")
p.add_argument("--json", action="store_true")
p.add_argument("--assembly")
p.add_argument("--target", default="lab")
p.add_argument("--action", default="inspect")
p.add_argument("--subtree", default="")
p.add_argument("--fields", action="store_true")
p.add_argument("--disable", action="store_true")
p.add_argument("--debug-options", help="Ignored local JSON for one integrated run; all acceleration defaults off")
p.add_argument("--stage-exit", action="store_true", help="Current: check-baseline through one original stage exit and 10 s of next-stage play")
p.add_argument("--compare", nargs=2, metavar=("A", "B"), help="Current: compare two project-manifest receipts")
a = p.parse_args()
if a.work_dir and (a.command != "prototype" or a.action not in {"inherited-state-check", "assembly-transforms-check", "rebuild-step"}):
    p.error("--work-dir requires prototype --action inherited-state-check, assembly-transforms-check or rebuild-step")
is_rebuild = a.command == "prototype" and a.action == "rebuild-step"
if is_rebuild and not a.step:
    p.error("rebuild-step requires --step NAME")
if (a.step or a.dest or a.compare_only) and not is_rebuild:
    p.error("--step, --dest and --compare-only require prototype --action rebuild-step")
if a.stage_exit and a.command != "check-baseline":
    p.error("--stage-exit requires check-baseline")
if a.debug_options and (a.command != "prototype" or a.action not in ["movement-batch-run", "movement-batch-retry"]):
    p.error("--debug-options requires movement-batch-run or movement-batch-retry")
if bool(a.compare) != (a.command == "prototype" and a.action == "project-manifest-compare"):
    p.error("--compare A B requires prototype --action project-manifest-compare and vice versa")
try:
    if a.command == "test":
        sys.exit(subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"]))
    elif a.command == "doctor":
        from health import doctor

        sys.exit(doctor(a.json))
    elif a.command == "inspect":
        from inventory import inspect

        inspect(a.full)
    elif a.command in ["decompile", "export-project"]:
        from recovery import decompile, export_project

        decompile(a.assembly, a.force) if a.command == "decompile" else export_project(a.force)
    elif a.command == "graphics":
        from graphics import graphics

        graphics()
    elif a.command == "prototype":
        # Action metadata and exceptional call contracts live in the lazy registry.
        from actions import dispatch, print_actions

        if a.action == "list":
            print_actions()
        else:
            dispatch(a)
    elif a.command == "diagnostics":
        from device import Device

        d = Device()
        d.owned()
        path = read(WORK / "device/runtime.json")["persistentDataPath"]
        if not path.endswith("/Android/data/" + __import__("device").PACKAGE + "/files"):
            raise RuntimeError("Unexpected diagnostics path")
        payload = WORK / "device/diagnostics.json"
        write(payload, {"enabled": not a.disable, "subtree": a.subtree, "fields": a.fields})
        d.cmd("push", str(payload), path + "/diagnostics.json")
        print(json.dumps({"success": True, "config": read(payload)}))
    elif a.command == "preflight":
        from build import preflight

        print(json.dumps(preflight(), indent=2))
    elif a.command == "check-baseline":
        from baseline import check_baseline

        result = check_baseline(stage_exit=a.stage_exit)
        print(json.dumps(result, indent=2))
        if not result["success"]:
            sys.exit(1)
    elif a.command == "build":
        from build import build

        build(a.target, a.force)
    elif a.command == "editor":
        from build import editor

        print(editor(a.target, a.action))
    elif a.command in ["install", "sync-data", "run", "logs", "crash", "screenshot", "reset", "smoke", "storage", "perf"]:
        from device import Device, smoke

        d = Device()
        if a.command == "smoke":
            from build import build

            r = build(a.target, a.force)
            smoke(r["apk"])
        elif a.command == "install":
            print(json.dumps(d.install(read(WORK / "config/current-build.json")["apk"]), indent=2))
        elif a.command == "sync-data":
            print(json.dumps(d.sync(), indent=2))
        elif a.command == "run":
            print(json.dumps(d.launch(), indent=2))
        elif a.command == "storage":
            print(json.dumps(d.storage(), indent=2))
        elif a.command == "reset":
            print(json.dumps(d.reset(), indent=2))
        else:
            print(json.dumps(d.collect(a.command, WORK / "captures" / now()), indent=2))
    else:
        raise RuntimeError("Unknown command")
except Exception as e:
    print(json.dumps({"success": False, "command": a.command, "error": str(e)}), file=sys.stderr)
    sys.exit(1)

finally:
    from device import Device

    if Device.display_awakened:
        Device().display(False)
