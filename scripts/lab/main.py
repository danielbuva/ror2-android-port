import argparse
import sys
from common import *

p = argparse.ArgumentParser(description="Local RoR2 porting laboratory; generated evidence lives under ignored work/.")
p.add_argument(
    "command",
    choices=[
        "diagnostics",
        "migrate-device-receipts",
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
p.add_argument(
    "--work-dir",
    help="Current: read-only inputs for rebuild/check actions, owner-assembly-prefix and destination preflight; install/sync-data/run/check-baseline use this work tree for device receipts (default: work/)",
)
p.add_argument(
    "--step",
    help="Current: rebuild-step name (assemblies, shader-pipeline, composition, project-inputs, catalog-closure, dependencies, stage-variants, source-scenes, build-entries, runtime-sources, importer-identities, validate-bindings, unity-build)",
)
p.add_argument(
    "--dest",
    help="Current: rebuild-step, owner-assembly-prefix or isolated preflight destination beneath this clone's work/rebuild/; owner prefix requires a new directory",
)
p.add_argument("--compare-only", action="store_true", help="Current: compare an existing rebuild-step destination without writing")
p.add_argument("--apk", help="Current: install this APK through the existing device safety/placement checks; preserves current-build")
p.add_argument("--payload-dir", help="Current: sync-data from this payload directory; preserves the shared generated payload")
p.add_argument("--full", action="store_true")
p.add_argument("--device", help="Current: explicit allowlisted serial (or LAB_DEVICE); required when several devices are attached")
p.add_argument("--host-only", action="store_true", help="Current: preflight host/input gates without device access")
p.add_argument("--force", action="store_true")
p.add_argument("--debug-symbols", action="store_true", help="Current: opt-in Unity Android Debugging symbols for the exact main APK build")
p.add_argument(
    "--capture-player-linker-inputs",
    action="store_true",
    help="Current: opt-in same-request pre-strip UnityLinker input inventory for whole-catalog-build or whole-catalog-code-build",
)
p.add_argument(
    "--capture-il2cpp-invocation",
    action="store_true",
    help="Current: additionally capture the same-request IL2CPP input directory for either whole-catalog build; requires --capture-player-linker-inputs",
)
p.add_argument("--json", action="store_true")
p.add_argument("--assembly")
p.add_argument("--target", default="lab")
p.add_argument("--action", default="inspect")
p.add_argument(
    "--profile-scope",
    choices=("pid", "app"),
    default="pid",
    help=("Current perf CPU scope: pid (default, exact selected PID) or app (explicit owned-package process set, task-clock:u; may include more than one PID)"),
)
p.add_argument("--subtree", default="")
p.add_argument("--fields", action="store_true")
p.add_argument("--disable", action="store_true")
p.add_argument("--skill-variants", help="Current: ignored local JSON for one base-survivor skill or cleanup check; per-run native skill catalog indices only")
p.add_argument(
    "--expected-apk-sha256",
    help="Current: optional exact SHA-256 of the APK already in the selected device ownership receipt for diagnostic checks; omission requires current-build equality at check start and never installs or labels the receipt APK current",
)
p.add_argument(
    "--skill-slot",
    choices=("primary", "secondary", "utility", "special"),
    help="Current: bounded assisted isolated slot diagnostic for one base survivor via survivor-kit-check",
)
p.add_argument(
    "--captain-supply-beacon",
    action="store_true",
    help="Current: bounded assisted native Captain PrepSupplyDrop/placement/deployable sequence; requires exactly --target Captain and default loadout",
)
p.add_argument(
    "--toolbot-offhand",
    action="store_true",
    help="Current: bounded assisted MUL-T Buzzsaw offhand sequence; requires --target Toolbot and exact --skill-variants",
)
p.add_argument("--debug-options", help="Ignored local JSON for one integrated run; all acceleration defaults off")
p.add_argument("--stage-exit", action="store_true", help="Current: check-baseline through one original stage exit and 10 s of next-stage play")
p.add_argument("--compare", nargs=2, metavar=("A", "B"), help="Current: compare two project-manifest receipts")
a = p.parse_args()
from device_context import set_command_selector

set_command_selector(a.device, os.environ.get("LAB_DEVICE"))
if a.host_only and a.command != "preflight":
    p.error("--host-only requires preflight")
whole_catalog_build = a.command == "prototype" and a.action in {"whole-catalog-build", "whole-catalog-code-build"}
if a.debug_symbols and not (a.command == "build" or whole_catalog_build):
    p.error("--debug-symbols requires build or a whole-catalog build action")
if a.capture_player_linker_inputs and not whole_catalog_build:
    p.error("--capture-player-linker-inputs requires a whole-catalog build action")
if a.capture_il2cpp_invocation and not whole_catalog_build:
    p.error("--capture-il2cpp-invocation requires a whole-catalog build action")
if a.capture_il2cpp_invocation and not a.capture_player_linker_inputs:
    p.error("--capture-il2cpp-invocation requires --capture-player-linker-inputs for the same-build pre-strip join")
# Device operations explicitly select the existing local receipt/config tree.
# Rebuild --work-dir remains a read-only input boundary.
if a.work_dir and a.command in {"install", "sync-data", "run", "check-baseline"}:
    import common

    common.WORK = WORK = Path(a.work_dir).expanduser().resolve()
if a.apk and a.command != "install":
    p.error("--apk requires install")
if a.payload_dir and a.command != "sync-data":
    p.error("--payload-dir requires sync-data")
if a.command == "perf" and a.action not in {"inspect", "collect", "cpu"}:
    p.error("perf --action must be collect or cpu (inspect preserves the existing collection behavior)")
if a.profile_scope != "pid" and not (a.command == "perf" and a.action == "cpu"):
    p.error("--profile-scope app requires perf --action cpu")
is_destination_preflight = a.command == "preflight" and a.dest is not None
if (
    a.work_dir
    and not is_destination_preflight
    and a.command not in {"install", "sync-data", "run", "check-baseline"}
    and (a.command != "prototype" or a.action not in {"inherited-state-check", "assembly-transforms-check", "rebuild-step", "owner-assembly-prefix"})
):
    p.error("--work-dir requires prototype --action inherited-state-check, assembly-transforms-check, rebuild-step or owner-assembly-prefix")
is_rebuild = a.command == "prototype" and a.action == "rebuild-step"
is_owner_assemblies = a.command == "prototype" and a.action == "owner-assembly-prefix"
if is_rebuild and not a.step:
    p.error("rebuild-step requires --step NAME")
if is_owner_assemblies and not a.dest:
    p.error("owner-assembly-prefix requires a new --dest")
if (a.step or a.compare_only) and not is_rebuild:
    p.error("--step and --compare-only require prototype --action rebuild-step")
if a.dest and not (is_destination_preflight or is_rebuild or is_owner_assemblies):
    p.error("--dest requires rebuild-step, owner-assembly-prefix or isolated preflight")
if a.stage_exit and a.command != "check-baseline":
    p.error("--stage-exit requires check-baseline")
if a.skill_variants and (a.command != "prototype" or a.action not in {"survivor-kit-check", "session-cleanup-check", "session-abandon-check"}):
    p.error("--skill-variants requires prototype --action survivor-kit-check, session-cleanup-check or session-abandon-check")
if a.expected_apk_sha256 is not None and (
    a.command != "prototype"
    or a.action not in {"survivor-kit-check", "session-cleanup-check", "session-abandon-check", "session-memory-check", "session-memory-root-check"}
):
    p.error(
        "--expected-apk-sha256 requires prototype --action survivor-kit-check, session-cleanup-check, "
        "session-abandon-check, session-memory-check or session-memory-root-check"
    )
if (a.skill_slot or a.toolbot_offhand or a.captain_supply_beacon) and (a.command != "prototype" or a.action != "survivor-kit-check"):
    p.error("--skill-slot, --toolbot-offhand and --captain-supply-beacon require prototype --action survivor-kit-check")
if a.debug_options and (a.command != "prototype" or a.action not in ["movement-batch-run", "movement-batch-retry"]):
    p.error("--debug-options requires movement-batch-run or movement-batch-retry")
if bool(a.compare) != (a.command == "prototype" and a.action == "project-manifest-compare"):
    p.error("--compare A B requires prototype --action project-manifest-compare and vice versa")
command_failed = False
try:
    if a.command == "test":
        sys.exit(subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"]))
    elif a.command == "doctor":
        from health import doctor

        sys.exit(doctor(a.json, a.device))
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
        path = d.read_receipt("runtime.json")["persistentDataPath"]
        if not path.endswith("/Android/data/" + __import__("device").PACKAGE + "/files"):
            raise RuntimeError("Unexpected diagnostics path")
        payload = d.receipt("diagnostics.json")
        d.write_receipt("diagnostics.json", {"enabled": not a.disable, "subtree": a.subtree, "fields": a.fields})
        d.cmd("push", str(payload), path + "/diagnostics.json")
        print(json.dumps({"success": True, "config": read(payload)}))
    elif a.command == "preflight":
        from build import preflight, preflight_host

        if is_destination_preflight:
            from unity_rebuild import preflight_destination

            print(json.dumps(preflight_destination(a.dest, a.work_dir), indent=2))
        else:
            print(json.dumps(preflight_host() if a.host_only else preflight(), indent=2))
    elif a.command == "check-baseline":
        from baseline import check_baseline

        result = check_baseline(stage_exit=a.stage_exit)
        print(json.dumps(result, indent=2))
        if not result["success"]:
            sys.exit(1)
    elif a.command == "build":
        from build import build

        build(a.target, a.force, android_symbols="debugging" if a.debug_symbols else "none")
    elif a.command == "editor":
        from build import editor

        print(editor(a.target, a.action))
    elif a.command in ["install", "sync-data", "run", "logs", "crash", "screenshot", "reset", "smoke", "storage", "perf", "migrate-device-receipts"]:
        from device import Device, smoke

        d = Device()
        if a.command == "smoke":
            from build import build

            r = build(a.target, a.force)
            smoke(r["apk"])
        elif a.command == "install":
            print(json.dumps(d.install(a.apk or read(WORK / "config/current-build.json")["apk"]), indent=2))
        elif a.command == "sync-data":
            print(json.dumps(d.sync(Path(a.payload_dir)) if a.payload_dir else d.sync(), indent=2))
        elif a.command == "run":
            print(json.dumps(d.launch(), indent=2))
        elif a.command == "storage":
            print(json.dumps(d.storage(), indent=2))
        elif a.command == "reset":
            print(json.dumps(d.reset(), indent=2))
        elif a.command == "migrate-device-receipts":
            print(json.dumps(d.migrate_receipts(), indent=2))
        elif a.command == "perf" and a.action == "cpu":
            from performance_capture import capture_cpu

            print(json.dumps(capture_cpu(d, duration_seconds=15, label=a.target, scope=a.profile_scope), indent=2))
        else:
            print(json.dumps(d.collect(a.command, WORK / "captures" / now()), indent=2))
    else:
        raise RuntimeError("Unknown command")
except Exception as e:
    command_failed = True
    print(json.dumps({"success": False, "command": a.command, "error": str(e)}), file=sys.stderr)
    sys.exit(1)

finally:
    from device import Device

    cleanup_errors = Device.sleep_awakened()
    if cleanup_errors:
        print(json.dumps({"success": False, "display_cleanup_errors": cleanup_errors}), file=sys.stderr)
        if not command_failed:
            sys.exit(1)
