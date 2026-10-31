import argparse
import sys
from common import *

if len(sys.argv) > 1 and sys.argv[1] == "lane" or os.environ.get("LAB_LANE"):
    from build_lanes import main, dispatch

    try:
        sys.exit(main(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == "lane" else dispatch(os.environ["LAB_LANE"], sys.argv[1:]))
    except Exception as error:
        print(json.dumps({"success": False, "command": "lane", "error": str(error)}), file=sys.stderr)
        sys.exit(1)

p = argparse.ArgumentParser(description="Local RoR2 porting laboratory; generated evidence lives under ignored work/.")
p.add_argument(
    "command",
    choices=[
        "lane",
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
    help="Current: read-only inputs for rebuild/check actions, owner-assembly-prefix and destination preflight; install/sync-data/run/check-baseline and session lifecycle/memory checks use this work tree for device receipts (default: work/)",
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
p.add_argument(
    "--assembly-profile",
    choices=("sdk", "public-dotnet8"),
    default="sdk",
    help="Current owner-assembly-prefix only: SDK default or opt-in public .NET 8 build tools; never a game runtime selection",
)
p.add_argument("--tool-archives", help="Current public-dotnet8 profile: read-only directory containing the three exact public archives")
p.add_argument("--tool-launcher", help="Current public-dotnet8 profile: explicit existing dotnet executable")
p.add_argument("--tool-host", choices=("host10", "android8"), help="Current public-dotnet8 profile: exact qualified build-tool runtime host")
p.add_argument("--apk", help="Current: install this APK through the existing device safety/placement checks; preserves current-build")
p.add_argument(
    "--install-mode",
    choices=("streaming", "incremental"),
    default="streaming",
    help="Current install transport: streaming (default, complete APK) or explicit incremental (requires matching v4 .idsig and device IncFS; still streams a new APK, not a delta; refuses unsupported devices without fallback)",
)
p.add_argument("--payload-dir", help="Current: sync-data from this payload directory; preserves the shared generated payload")
p.add_argument("--full", action="store_true")
p.add_argument("--device", help="Current: explicit allowlisted serial (or LAB_DEVICE); required when several devices are attached")
p.add_argument("--host-only", action="store_true", help="Current: preflight host/input gates without device access")
p.add_argument("--force", action="store_true")
p.add_argument("--debug-symbols", action="store_true", help="Current: opt-in Unity Android Debugging symbols for the exact main APK build")
p.add_argument(
    "--bundle-compression",
    choices=("uncompressed",),
    help="Current iteration only: whole-catalog-build in LAB_LANE with uncompressed bundles and verified unchanged-payload reuse; default acceptance setting stays chunked LZ4",
)
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
p.add_argument(
    "--gameplay-only",
    action="store_true",
    help="Current: alpha-stability-batch runs only heap and sustained stages; settings interruption remains unqualified",
)
p.add_argument(
    "--done-file", help="Current: alpha-stability-batch requires a new absolute host JSON receipt path; launch detached and inspect it after completion"
)
p.add_argument(
    "--prior-settings-batch",
    help="Current: alpha-stability-batch skips settings interruption using a retained successful same-APK settings stage; heap and sustained stages run fresh",
)
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
p.add_argument("--sessions", type=int, help="Current: session-memory-check/root-check series length, 3 to 32 (default: 5); automatic diagnostic input only")
p.add_argument(
    "--memory-snapshots",
    action="store_true",
    help="Current: session-memory-check only; capture private native/managed heaps at menus 2/4, allocating and pausing; separate from ordinary growth/performance",
)
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
p.add_argument(
    "--capture-in-destination",
    action="store_true",
    help="Current diagnostic: defer MainOutput capture to a destination-stage skill; requires --stage-exit, waits at most 30 s there",
)
p.add_argument("--compare", nargs=2, metavar=("A", "B"), help="Current: compare two project-manifest receipts")
a = p.parse_args()
from device_context import set_command_selector

set_command_selector(a.device, os.environ.get("LAB_DEVICE"))
if a.host_only and a.command != "preflight":
    p.error("--host-only requires preflight")
whole_catalog_build = a.command == "prototype" and a.action in {"whole-catalog-build", "whole-catalog-code-build", "shared-catalog-code-build"}
if a.bundle_compression and not (a.command == "prototype" and a.action == "whole-catalog-build" and lane_config()):
    p.error("--bundle-compression requires whole-catalog-build in an isolated LAB_LANE")
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
device_prototype_work = a.command == "prototype" and a.action in {
    "session-cleanup-check",
    "session-abandon-check",
    "session-memory-check",
    "session-memory-root-check",
    "touch-gesture",
    "settings-write-interrupt-check",
}
if a.work_dir and (a.command in {"install", "sync-data", "run", "check-baseline"} or device_prototype_work):
    import common

    common.WORK = WORK = Path(a.work_dir).expanduser().resolve()
if a.apk and a.command != "install":
    p.error("--apk requires install")
if a.install_mode != "streaming" and a.command != "install":
    p.error("--install-mode requires install")
if a.payload_dir and a.command != "sync-data":
    p.error("--payload-dir requires sync-data")
if a.command == "perf" and a.action not in {"inspect", "collect", "cpu"}:
    p.error("perf --action must be collect or cpu (inspect preserves the existing collection behavior)")
if a.profile_scope != "pid" and not (a.command == "perf" and a.action == "cpu"):
    p.error("--profile-scope app requires perf --action cpu")
is_destination_preflight = a.command == "preflight" and a.dest is not None
if (
    a.work_dir
    and not device_prototype_work
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
tool_options = (a.tool_archives, a.tool_launcher, a.tool_host)
if (a.assembly_profile != "sdk" or any(tool_options)) and not is_owner_assemblies:
    p.error("--assembly-profile and --tool-* require owner-assembly-prefix")
if (a.assembly_profile == "public-dotnet8" and not all(tool_options)) or (a.assembly_profile == "sdk" and any(tool_options)):
    p.error("public-dotnet8 requires all three --tool-* selectors; SDK accepts none")
if (a.step or a.compare_only) and not is_rebuild:
    p.error("--step and --compare-only require prototype --action rebuild-step")
if a.dest and not (is_destination_preflight or is_rebuild or is_owner_assemblies):
    p.error("--dest requires rebuild-step, owner-assembly-prefix or isolated preflight")
if a.stage_exit and a.command != "check-baseline":
    p.error("--stage-exit requires check-baseline")
if a.capture_in_destination and (a.command != "check-baseline" or not a.stage_exit):
    p.error("--capture-in-destination requires check-baseline --stage-exit")
if a.sessions is not None and (a.command != "prototype" or a.action not in {"session-memory-check", "session-memory-root-check"}):
    p.error("--sessions requires prototype --action session-memory-check or session-memory-root-check")
if a.memory_snapshots and (a.command != "prototype" or a.action != "session-memory-check"):
    p.error("--memory-snapshots requires prototype --action session-memory-check")
if a.skill_variants and (a.command != "prototype" or a.action not in {"survivor-kit-check", "session-cleanup-check", "session-abandon-check"}):
    p.error("--skill-variants requires prototype --action survivor-kit-check, session-cleanup-check or session-abandon-check")
if a.expected_apk_sha256 is not None and (
    a.command != "prototype"
    or a.action
    not in {
        "survivor-kit-check",
        "session-cleanup-check",
        "session-abandon-check",
        "session-memory-check",
        "session-memory-root-check",
        "touch-gesture",
        "settings-write-interrupt-check",
        "alpha-stability-batch",
    }
):
    p.error(
        "--expected-apk-sha256 requires prototype --action survivor-kit-check, session-cleanup-check, "
        "session-abandon-check, session-memory-check, session-memory-root-check, touch-gesture, settings-write-interrupt-check or alpha-stability-batch"
    )
is_alpha_batch = a.command == "prototype" and a.action == "alpha-stability-batch"
if a.gameplay_only and not is_alpha_batch:
    p.error("--gameplay-only requires prototype --action alpha-stability-batch")
if a.done_file is not None and not is_alpha_batch:
    p.error("--done-file requires prototype --action alpha-stability-batch")
if a.prior_settings_batch is not None and not is_alpha_batch:
    p.error("--prior-settings-batch requires prototype --action alpha-stability-batch")
if is_alpha_batch and (not a.done_file or not a.device or not a.expected_apk_sha256):
    p.error("alpha-stability-batch requires --device, --expected-apk-sha256 and --done-file")
if (a.skill_slot or a.toolbot_offhand or a.captain_supply_beacon) and (a.command != "prototype" or a.action != "survivor-kit-check"):
    p.error("--skill-slot, --toolbot-offhand and --captain-supply-beacon require prototype --action survivor-kit-check")
if a.debug_options and (a.command != "prototype" or a.action not in ["movement-batch-run", "movement-batch-retry"]):
    p.error("--debug-options requires movement-batch-run or movement-batch-retry")
if bool(a.compare) != (a.command == "prototype" and a.action in {"project-manifest-compare", "apk-member-compare"}):
    p.error("--compare A B requires prototype --action project-manifest-compare or apk-member-compare and vice versa")
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

        result = check_baseline(stage_exit=a.stage_exit, capture_in_destination=a.capture_in_destination)
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
            apk = a.apk or read(WORK / "config/current-build.json")["apk"]
            print(json.dumps(d.install(apk, mode=a.install_mode) if a.install_mode != "streaming" else d.install(apk), indent=2))
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
    # The detached batch publishes its receipt after all cleanup and lease
    # release. It owns display teardown inside that lease, including failures.
    if not is_alpha_batch:
        from device import Device

        cleanup_errors = Device.sleep_awakened()
        if cleanup_errors:
            print(json.dumps({"success": False, "display_cleanup_errors": cleanup_errors}), file=sys.stderr)
            if not command_failed:
                sys.exit(1)
