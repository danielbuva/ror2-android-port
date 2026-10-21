"""Lazy prototype command registry; historical actions retain their original contracts."""

from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from importlib import import_module
import json
import sys
from typing import Callable


@dataclass(frozen=True)
class Action:
    name: str
    module: str
    function: str
    kwargs: dict
    status: str
    help: str
    handler: Callable | None = None


def _inherited_check(function, kwargs, args):
    return function(**(dict(kwargs, work=args.work_dir) if getattr(args, "work_dir", None) else kwargs))


def _rebuild_step(function, kwargs, args):
    return function(step=args.step, dest=args.dest, compare_only=args.compare_only, work=args.work_dir, **kwargs)


def _capture(function, kwargs, args):
    from common import WORK, now, write

    out = WORK / "receipts/project-manifest" / (now() + ".json")
    write(out, function(WORK / "lab-project", **kwargs))
    print(out)


def _compare(function, kwargs, args):
    from common import read

    result = function(*(read(path) for path in args.compare), **kwargs)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["equal"] else 1)


def _whole_catalog_code_build(function, kwargs, args):
    selected = dict(kwargs)
    if getattr(args, "debug_symbols", False):
        selected["android_symbols"] = "debugging"
    if getattr(args, "capture_player_linker_inputs", False):
        selected["capture_player_linker_inputs"] = True
    if getattr(args, "capture_il2cpp_invocation", False):
        selected["capture_il2cpp_invocation"] = True
    return function(**selected)


def _json_result(function, kwargs, args, **formatting):
    print(json.dumps(function(**kwargs), **formatting))


def _source_scene(function, kwargs, args):
    from source_scene_candidate import SCENES, stage_unavailable_audio

    staged = function(tuple(SCENES) if args.target == "all" else ("lakes",), **kwargs)
    boundary = stage_unavailable_audio()
    print(json.dumps({"scenes": staged, "audio_boundary": boundary}))


def _target(function, kwargs, args):
    return function(args.target, **kwargs)


def _survivor_target(function, kwargs, args):
    path = getattr(args, "skill_variants", None)
    slot = getattr(args, "skill_slot", None)
    offhand = getattr(args, "toolbot_offhand", False)
    captain_beacon = getattr(args, "captain_supply_beacon", False)
    selected = dict(kwargs)
    if path is not None:
        selected["skill_variants"] = path
    if slot is not None:
        selected["skill_slot"] = slot
    if offhand:
        selected["toolbot_offhand"] = True
    if captain_beacon:
        selected["captain_supply_beacon"] = True
    expected_apk_sha256 = getattr(args, "expected_apk_sha256", None)
    if expected_apk_sha256 is not None:
        selected["expected_apk_sha256"] = expected_apk_sha256
    return function(args.target, **selected)


def _session_cleanup_target(function, kwargs, args):
    # The global prototype target defaults to "lab"; preserve the old Commando
    # behavior unless a caller explicitly supplies a base survivor key.
    selected = kwargs if args.target == "lab" else dict(kwargs, survivor=args.target)
    if getattr(args, "skill_variants", None) is not None:
        selected = dict(selected, skill_variants=args.skill_variants)
    expected_apk_sha256 = getattr(args, "expected_apk_sha256", None)
    if expected_apk_sha256 is not None:
        selected = dict(selected, expected_apk_sha256=expected_apk_sha256)
    return _json_result(function, selected, args, indent=2)


def _session_memory(function, kwargs, args):
    if args.target != "lab":
        raise SystemExit("session-memory-check uses the ordinary Commando menu start; omit --target")
    expected_apk_sha256 = getattr(args, "expected_apk_sha256", None)
    selected = kwargs if expected_apk_sha256 is None else dict(kwargs, expected_apk_sha256=expected_apk_sha256)
    return _json_result(function, selected, args, indent=2)


def _timed_prepare(function, kwargs, args, *, seconds):
    from common import ROOT, WORK, read, write

    function(**kwargs)
    out = ROOT / read(WORK / "experiments/scene-runtime/current.json")["path"]
    attempt = read(out / "attempt.json")
    attempt["batch_seconds"] = deepcopy(seconds)
    write(out / "attempt.json", attempt)


def _movement_batch(function, kwargs, args):
    if args.debug_options:
        kwargs["debug_options"] = args.debug_options
    return function(**kwargs)


def _repair_reconstruction(function, kwargs, args):
    from common import ROOT

    sys.exit(function([sys.executable, str(ROOT / "patches/reconstruction-ambiguities.py")], **kwargs))


# Every row describes the actual target call. Handlers preserve positional CLI
# arguments, result formatting, timing-file updates and exit codes where needed.
# Only the selected action's module is imported by dispatch().
_ENTRIES = (
    Action(
        "phone-wrapper-search",
        "phone_wrapper_search",
        "inspect_action",
        {},
        "current",
        "Experimental read-only SDK support: --target REQUEST.json selects the pinned owner SDK binary and extracts normal-path assembly/namespace lookup order with argument, branch and return checks. Executes no SDK code and produces no scene roots, game build, install or editor mutation.",
        handler=_target,
    ),
    Action(
        "phone-native-registry",
        "phone_registry",
        "inspect_action",
        {},
        "current",
        "Experimental read-only metadata support: --target REQUEST.json selects the exact owner SDK binary, stages authored Python readers and reports native registration/module coverage and persistent class IDs. Executes no SDK code, generates no linker roots and changes no editor, package or runtime.",
        handler=_target,
    ),
    Action(
        "phone-root-contract",
        "phone_roots",
        "inspect_action",
        {},
        "current",
        "Experimental read-only host contract: --target REQUEST.json binds an authored fixture/capture and inventories SDK native-type metadata without executing inspected assemblies. Reports explicit matches separately from name guesses; produces no roots, game build, install or editor mutation.",
        handler=_target,
    ),
    Action(
        "phone-linker-fixture",
        "phone_linker",
        "stage_action",
        {},
        "current",
        "Experimental: --target REQUEST.json binds the authored fixture APK/project and exact callback capture for Android UnityLinker replay. Optional native_registry selects a pinned owner SDK binary/hash. Optional module_policy selects builtin-modules-no-overrides-v1 with SDK/package-derived exclusions. Scene roots remain captured. No editor mutation, installation or game build.",
        handler=_target,
    ),
    Action(
        "phone-converter-fixture",
        "phone_converter",
        "stage_action",
        {},
        "current",
        "Experimental: stage the authored player's hash-bound stripped closure and exact supplied Unity converter from --target REQUEST.json. An optional linker selector consumes verified phone stripping output; desktop editor roots remain inputs. Build-tool host only; no game, editor mutation or installation.",
        handler=_target,
    ),
    Action(
        "phone-native-apk-fixture",
        "phone_native_apk",
        "stage_action",
        {},
        "current",
        "Experimental: --target REQUEST.json pins the authored fixture APK, matching metadata and ARM64 library hashes; writes a new unsigned native-swap fixture for separate alignment/signing and device checks. Never packages the game.",
        handler=_target,
    ),
    Action(
        "phone-native-fixture",
        "phone_native",
        "stage_action",
        {},
        "current",
        "Experimental: stage only the hash-bound authored content fixture's native graph from --target REQUEST.json, supplied Unity runtime and original NDK target inputs. An explicit converter selector may bind verified phone-generated C++; desktop stripping remains an input. No device or game build access.",
        handler=_target,
    ),
    Action(
        "phone-host-check",
        "phone_host_check",
        "check_action",
        {},
        "current",
        "Experimental: explicit --device and hash-bound --target REQUEST.json install only the authored sandbox fixture, verify installed native execution and writable-code refusal twice, then remove the owned package and sleep the display.",
        handler=_target,
    ),
    Action(
        "phone-package-check",
        "phone_package_check",
        "check_action",
        {},
        "current",
        "Experimental: explicit --device and hash-bound --target REQUEST.json check the separate phone content fixture, candidate refusal, two native reload cycles, increasing-version data retention and owned cleanup; never installs the game.",
        handler=_target,
    ),
    Action(
        "phone-apk-fixture",
        "phone_apk",
        "stage_action",
        {},
        "current",
        "Experimental: repackage only the authored content fixture from hash-bound --target REQUEST.json; writes a new unsigned APK, requiring later alignment/signing. No device or game build access.",
        handler=_target,
    ),
    Action(
        "phone-content-check",
        "phone_content",
        "run_editor",
        {},
        "current",
        "Experimental: check generated --target PROJECT in the exact editor under the primary checkout build mutex; no game project or device access.",
        handler=_target,
    ),
    Action(
        "phone-content-build",
        "phone_content",
        "run_editor",
        {"build": True},
        "current",
        "Experimental: build committed authored --target PROJECT as a separate ARM64 IL2CPP/Vulkan fixture APK under the primary checkout build mutex; no install or game build changes.",
        handler=_target,
    ),
    Action(
        "phone-content-fixture",
        "phone_content",
        "stage_action",
        {},
        "current",
        "Experimental: generate an authored TextAsset bundle and isolated exact-editor fixture under work/rebuild/phone-content; no game input, build, install or runtime change.",
    ),
    Action(
        "rebuild-step",
        "rebuild",
        "rebuild_action",
        {},
        "current",
        "Rebuild --step assemblies|shader-pipeline|composition|project-inputs|catalog-closure|dependencies|stage-variants|source-scenes|build-entries|runtime-sources|importer-identities|validate-bindings|unity-build in order under work/rebuild/<input_id>/lab-project (--dest overrides); --compare-only reads an existing destination.",
        handler=_rebuild_step,
    ),
    Action(
        "assembly-transforms-check",
        "assembly_transforms",
        "check_action",
        {},
        "current",
        "Rebuild the three transformed plugins from originals in disposable .local scratch and verify hashes; --work-dir selects read-only local inputs.",
        handler=_inherited_check,
    ),
    Action(
        "inherited-store-capture",
        "inherited_state",
        "capture_action",
        {},
        "current",
        "Capture exactly the ledger's inherited asset/meta pairs into work/inherited-store/<input_id>; refuse hash or identity drift.",
    ),
    Action(
        "inherited-state-check",
        "inherited_state",
        "check_action",
        {},
        "current",
        "Verify inherited-store hashes and regenerate byte-proven pairs in scratch; work stays read-only (--work-dir selects local work).",
        handler=_inherited_check,
    ),
    Action(
        "authored-additions-check",
        "authored_additions",
        "check_action",
        {},
        "current",
        "Compare tracked shader addition and generated importer bytes with migration staging; read-only.",
    ),
    Action(
        "asset-transforms-check",
        "asset_transforms",
        "check_action",
        {},
        "current",
        "Compare all recipe-generated asset/meta bytes with the project; read-only.",
    ),
    Action(
        "project-manifest-capture", "project_manifest", "capture", {}, "current", "Capture generated-project file hashes and external inputs.", handler=_capture
    ),
    Action(
        "project-manifest-compare",
        "project_manifest",
        "compare",
        {},
        "current",
        "Compare two receipts with --compare A B; exit 1 on differences.",
        handler=_compare,
    ),
    Action("input-update-check", "input_migration", "check_update", {}, "historical", "Check legitimate input for updates."),
    Action("composition-update-stage", "composition_migration", "stage", {}, "current", "Stage the current project composition."),
    Action(
        "composition-update-dependencies",
        "composition_migration",
        "stage_missing_sources",
        {},
        "current",
        "Stage missing source dependencies for the composition.",
    ),
    Action("stage-variants", "stage_variants", "stage", {}, "historical", "Report stage variants as JSON.", handler=_json_result),
    Action(
        "source-scene-prepare",
        "source_scene_candidate",
        "prepare",
        {},
        "historical",
        "Prepare source scenes and the unavailable-audio boundary (--target all for every scene).",
        handler=_source_scene,
    ),
    Action("whole-catalog-audit", "whole_catalog", "audit", {}, "historical", "Audit the original whole-catalog graph."),
    Action("whole-catalog-native", "whole_catalog", "native_inventory", {}, "historical", "Inventory native whole-catalog content."),
    Action("whole-catalog-reconcile", "whole_catalog", "reconcile", {}, "historical", "Reconcile whole-catalog inventory records."),
    Action("whole-catalog-contracts", "whole_catalog", "contracts", {}, "current", "Check whole-catalog resource and serialization contracts."),
    Action("whole-catalog-prepare", "whole_catalog", "prepare_integration", {}, "current", "Prepare the whole-catalog integration."),
    Action("whole-catalog-host", "whole_catalog", "host_integration", {}, "current", "Run the whole-catalog editor host fixture."),
    Action(
        "survivor-kit-check",
        "survivor_check",
        "check_survivors",
        {},
        "current",
        "Assisted world skill check: --target all or comma-separated base survivor keys; optional --skill-variants supplies one strict per-run catalog selector; --skill-slot primary|secondary|utility|special runs one bounded isolated native-input diagnostic; --toolbot-offhand runs the exact MUL-T Buzzsaw/Dual Wield sequence and requires --target Toolbot plus --skill-variants; --captain-supply-beacon runs native Captain PrepSupplyDrop, valid placement and owned deployable registration and requires exactly --target Captain with default loadout. Omit --expected-apk-sha256 to require current-build equality at check start; supplying it selects only a matching selected-device ownership receipt and its byte-verified APK, without calling it current.",
        handler=_survivor_target,
    ),
    Action(
        "session-cleanup-check",
        "session_cleanup_check",
        "check_session_cleanup",
        {},
        "current",
        "Observe an original first-stage loss, native cleanup and same-process restart; diagnostic automatic input, gameplay debug assists off. Optional --target selects one base survivor (default Commando); locked choices are diagnostic overrides, no expansion. Optional --skill-variants applies one strict per-run native catalog selector to both sessions. Omit --expected-apk-sha256 to require current-build equality at check start; supplying it binds this diagnostic to the selected device's matching ownership receipt and receipt APK bytes without calling that APK current.",
        handler=_session_cleanup_target,
    ),
    Action(
        "session-abandon-check",
        "session_cleanup_check",
        "check_session_cleanup",
        {"ending": "abandon"},
        "current",
        "After 60 s of ready first-stage play, observe original UI-driven end-run, native listener/template cleanup and same-process restart without an original loss/result; optional --target selects a base survivor (default Commando), locked choices are diagnostic overrides. Optional --skill-variants applies one strict per-run native catalog selector to both sessions. Omit --expected-apk-sha256 to require current-build equality at check start; supplying it binds this diagnostic to the selected device's matching ownership receipt and receipt APK bytes without calling that APK current.",
        handler=_session_cleanup_target,
    ),
    Action(
        "session-memory-check",
        "session_memory_check",
        "check_session_memory",
        {},
        "current",
        "Repeat five ordinary Commando menu-start, 60 s ready Lakes play and UI-abandon sessions in one process; each completed session must pass the session-abandon contract. Reports existing runtime resource samples and per-menu PSS as observations, not a leak fix or normal-game acceptance. Requires --expected-apk-sha256 bound to the selected device's ownership receipt.",
        handler=_session_memory,
    ),
    Action(
        "session-memory-root-check",
        "session_memory_check",
        "check_session_memory",
        {"root_walk": True},
        "current",
        "session-memory-check plus the opt-in menu-only completed-session root walk: before each later menu, SessionResourceBoundary walks static fields of loaded types and live MonoBehaviour/ScriptableObject roots (bounded, read-only; may run unrelated static constructors) and names reference paths to retained completed sessions. Diagnostic only. Requires --expected-apk-sha256.",
        handler=_session_memory,
    ),
    Action("whole-catalog-host-providers", "whole_catalog", "host_providers", {}, "current", "Run the whole-catalog native-provider host fixture."),
    Action("whole-catalog-repair-bindings", "whole_catalog", "repair_root_bindings", {}, "current", "Repair recorded whole-catalog root bindings."),
    Action(
        "whole-catalog-build",
        "whole_catalog",
        "build_integration",
        {},
        "current",
        "Compose content, stage explicit original-audio selection (default off), and build the player. Supports --debug-symbols, --capture-player-linker-inputs and --capture-il2cpp-invocation with the same contracts as whole-catalog-code-build.",
        handler=_whole_catalog_code_build,
    ),
    Action(
        "whole-catalog-code-build",
        "whole_catalog",
        "build_integration",
        {"code_only": True},
        "current",
        "Build player code while verifying and reusing the frozen payload. Optional --debug-symbols retains matching Unity IL2CPP symbols for this exact APK. --capture-player-linker-inputs opts into the request/source/input-bound pre-strip UnityLinker inventory. Add --capture-il2cpp-invocation to capture the same request's pre-launch rendered IL2CPP line and input directory; it requires --capture-player-linker-inputs and does not claim exact argv or composed-audio stage equivalence.",
        handler=_whole_catalog_code_build,
    ),
    Action("whole-catalog-run", "whole_catalog", "run_integration", {}, "current", "Install, sync and run the catalog-registration check."),
    Action("shader-recovery", "shader_recovery", "recover", {}, "historical", "Recover shaders for --target.", handler=_target),
    Action("shader-source", "shader_source", "generate", {}, "historical", "Generate recovered shader sources."),
    Action("shader-source-deferred", "shader_deferred", "generate", {}, "historical", "Generate deferred shader sources."),
    Action("shader-source-materials", "shader_materials", "generate", {}, "historical", "Generate material shader sources."),
    Action("presentation-payload", "presentation", "build_payload", {"stages": False, "recovered": False}, "historical", "Build the presentation payload."),
    Action(
        "stage-presentation-payload",
        "presentation",
        "build_payload",
        {"stages": True, "recovered": False},
        "historical",
        "Build the stage presentation payload.",
    ),
    Action(
        "recovered-presentation-payload",
        "presentation",
        "build_payload",
        {"stages": False, "recovered": True},
        "historical",
        "Build the recovered presentation payload.",
    ),
    Action("primary-fire-prepare", "primary_fire", "prepare", {}, "historical", "Prepare the primary fire probe."),
    Action("primary-fire-run", "primary_fire", "run", {}, "historical", "Run the primary fire probe."),
    Action("steam-exception-prepare", "scene_runtime", "steam_exception_prepare", {}, "historical", "Prepare the steam exception probe."),
    Action("steam-boundary-prepare", "scene_runtime", "steam_boundary_prepare", {}, "historical", "Prepare the steam boundary probe."),
    Action("profile-binding-prepare", "scene_runtime", "profile_binding_prepare", {}, "historical", "Prepare the profile binding probe."),
    Action("audio-guard-prepare", "scene_runtime", "audio_guard_prepare", {}, "historical", "Prepare the audio guard probe."),
    Action("audio-native-prepare", "scene_runtime", "audio_assets_prepare", {"native_availability": True}, "historical", "Prepare the audio native probe."),
    Action("audio-assets-prepare", "scene_runtime", "audio_assets_prepare", {}, "historical", "Prepare the audio assets probe."),
    Action(
        "audio-bank-index",
        "wwise_bank_index",
        "index",
        {"verify_decoder": True},
        "historical",
        "Index Wwise banks, verify the decoder and print JSON.",
        handler=partial(_json_result, sort_keys=True),
    ),
    Action("startup-integration-prepare", "scene_runtime", "startup_prepare", {"integration": True}, "historical", "Prepare the startup integration probe."),
    Action(
        "startup-ngss-prepare",
        "scene_runtime",
        "startup_prepare",
        {
            "loading_scene": True,
            "application_awake": True,
            "global_textures": True,
            "interpolation": True,
            "fps_queue": True,
            "volume": True,
            "volume_order": True,
            "ngss": True,
        },
        "historical",
        "Prepare the startup ngss probe.",
    ),
    Action(
        "startup-volume-order-prepare",
        "scene_runtime",
        "startup_prepare",
        {
            "loading_scene": True,
            "application_awake": True,
            "global_textures": True,
            "interpolation": True,
            "fps_queue": True,
            "volume": True,
            "volume_order": True,
        },
        "historical",
        "Prepare the startup volume order probe.",
    ),
    Action(
        "startup-volume-prepare",
        "scene_runtime",
        "startup_prepare",
        {"loading_scene": True, "application_awake": True, "global_textures": True, "interpolation": True, "fps_queue": True, "volume": True},
        "historical",
        "Prepare the startup volume probe.",
    ),
    Action(
        "startup-fps-prepare",
        "scene_runtime",
        "startup_prepare",
        {"loading_scene": True, "application_awake": True, "global_textures": True, "interpolation": True, "fps_queue": True},
        "historical",
        "Prepare the startup fps probe.",
    ),
    Action(
        "startup-interpolation-prepare",
        "scene_runtime",
        "startup_prepare",
        {"loading_scene": True, "application_awake": True, "global_textures": True, "interpolation": True},
        "historical",
        "Prepare the startup interpolation probe.",
    ),
    Action(
        "startup-textures-prepare",
        "scene_runtime",
        "startup_prepare",
        {"loading_scene": True, "application_awake": True, "global_textures": True},
        "historical",
        "Prepare the startup textures probe.",
    ),
    Action(
        "startup-application-prepare",
        "scene_runtime",
        "startup_prepare",
        {"loading_scene": True, "application_awake": True},
        "historical",
        "Prepare the startup application probe.",
    ),
    Action("startup-scene-prepare", "scene_runtime", "startup_prepare", {"loading_scene": True}, "historical", "Prepare the startup scene probe."),
    Action("startup-prepare", "scene_runtime", "startup_prepare", {}, "historical", "Prepare the startup probe."),
    Action("startup-run", "scene_runtime", "scene_run", {}, "historical", "Run the startup probe."),
    Action("skin-apply-prepare", "scene_runtime", "skin_apply_prepare", {}, "historical", "Prepare the skin apply probe."),
    Action("material-render-verify", "scene_runtime", "scene_run", {"verification": True}, "historical", "Run material-render verification."),
    Action(
        "grounded-motion-retry",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["state-ground-motion"], "retry": True},
        "historical",
        "Retry the grounded motion probe.",
    ),
    Action(
        "jump-input-retry-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"jump_items": True, "cases": ["state-jump-items", "state-jump-inventory", "state-jump-input"]},
        "historical",
        "Prepare the jump input retry probe.",
    ),
    Action(
        "barrier-effect-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "barrier_effect": True, "cases": ["body-state-spawn-state-barrier-asset"]},
        "historical",
        "Prepare the barrier effect probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-barrier-asset": 25,
                "body-state-spawn-state-barrier-init": 25,
                "body-state-spawn-state-barrier-completion": 25,
                "body-state-spawn-state-barrier-effect": 25,
                "body-state-spawn-state-auto-barrier": 85,
            },
        ),
    ),
    Action(
        "barrier-completion-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "barrier_effect": True, "cases": ["body-state-spawn-state-barrier-completion"]},
        "historical",
        "Prepare the barrier completion probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-barrier-asset": 25,
                "body-state-spawn-state-barrier-init": 25,
                "body-state-spawn-state-barrier-completion": 25,
                "body-state-spawn-state-barrier-effect": 25,
                "body-state-spawn-state-auto-barrier": 85,
            },
        ),
    ),
    Action(
        "barrier-lifecycle-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "barrier_effect": True, "cases": ["body-state-spawn-state-barrier-effect"]},
        "historical",
        "Prepare the barrier lifecycle probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-barrier-asset": 25,
                "body-state-spawn-state-barrier-init": 25,
                "body-state-spawn-state-barrier-completion": 25,
                "body-state-spawn-state-barrier-effect": 25,
                "body-state-spawn-state-auto-barrier": 85,
            },
        ),
    ),
    Action(
        "barrier-init-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-barrier-init"], "retry": True},
        "historical",
        "Run the barrier init probe.",
    ),
    Action(
        "barrier-lifecycle-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-barrier-effect"], "retry": True},
        "historical",
        "Run the barrier lifecycle probe.",
    ),
    Action("rewired-trial-inventory", "rewired_trial", "inventory", {}, "historical", "Inventory the Rewired trial candidate."),
    Action("rewired-trial-run", "rewired_trial", "controller_run", {}, "historical", "Run the rewired trial probe."),
    Action(
        "rewired-platform-prepare",
        "scene_runtime",
        "movement_batch_prepare",
        {"cases": ["rewired-platform-contract"]},
        "historical",
        "Prepare the rewired platform probe.",
    ),
    Action(
        "nova-whole-game-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
            "droplet_load": True,
            "droplet_flight": True,
            "droplet_collision": True,
            "default_pickup": True,
            "chest_ejection": True,
            "integrated_world": True,
        },
        "historical",
        "Prepare the nova whole game probe.",
    ),
    Action("nova-bridge-prepare", "nova_bridge", "prepare", {}, "historical", "Prepare the nova bridge probe."),
    Action("nova-director-batch-prepare", "nova_bridge", "prepare_spine", {"director_batch": True}, "historical", "Prepare the nova director batch probe."),
    Action(
        "nova-run-clock-prepare", "nova_bridge", "prepare_spine", {"director_batch": True, "run_clock": True}, "historical", "Prepare the nova run clock probe."
    ),
    Action(
        "nova-barrel-prepare",
        "nova_bridge",
        "prepare_spine",
        {"director_batch": True, "run_clock": True, "barrel": True},
        "historical",
        "Prepare the nova barrel probe.",
    ),
    Action(
        "nova-pickup-prepare",
        "nova_bridge",
        "prepare_spine",
        {"director_batch": True, "run_clock": True, "barrel": True, "pickup": True},
        "historical",
        "Prepare the nova pickup probe.",
    ),
    Action(
        "nova-money-cost-prepare",
        "nova_bridge",
        "prepare_spine",
        {"director_batch": True, "run_clock": True, "barrel": True, "pickup": True, "money": True},
        "historical",
        "Prepare the nova money cost probe.",
    ),
    Action(
        "nova-active-client-prepare",
        "nova_bridge",
        "prepare_spine",
        {"director_batch": True, "run_clock": True, "barrel": True, "pickup": True, "money": True, "client": True},
        "historical",
        "Prepare the nova active client probe.",
    ),
    Action(
        "nova-interaction-selection-prepare",
        "nova_bridge",
        "prepare_spine",
        {"director_batch": True, "run_clock": True, "barrel": True, "pickup": True, "money": True, "client": True, "selection": True},
        "historical",
        "Prepare the nova interaction selection probe.",
    ),
    Action(
        "nova-client-coin-prepare",
        "nova_bridge",
        "prepare_spine",
        {"director_batch": True, "run_clock": True, "barrel": True, "pickup": True, "money": True, "client": True, "selection": True, "client_coin": True},
        "historical",
        "Prepare the nova client coin probe.",
    ),
    Action(
        "nova-input-barrel-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
        },
        "historical",
        "Prepare the nova input barrel probe.",
    ),
    Action(
        "nova-chest-drop-table-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
        },
        "historical",
        "Prepare the nova chest drop table probe.",
    ),
    Action(
        "nova-chest-purchase-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
        },
        "historical",
        "Prepare the nova chest purchase probe.",
    ),
    Action(
        "nova-pickup-droplet-load-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
            "droplet_load": True,
        },
        "historical",
        "Prepare the nova pickup droplet load probe.",
    ),
    Action(
        "nova-pickup-droplet-flight-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
            "droplet_load": True,
            "droplet_flight": True,
        },
        "historical",
        "Prepare the nova pickup droplet flight probe.",
    ),
    Action(
        "nova-pickup-droplet-collision-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
            "droplet_load": True,
            "droplet_flight": True,
            "droplet_collision": True,
        },
        "historical",
        "Prepare the nova pickup droplet collision probe.",
    ),
    Action(
        "nova-default-pickup-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
            "droplet_load": True,
            "droplet_flight": True,
            "droplet_collision": True,
            "default_pickup": True,
        },
        "historical",
        "Prepare the nova default pickup probe.",
    ),
    Action(
        "nova-chest-ejection-prepare",
        "nova_bridge",
        "prepare_spine",
        {
            "director_batch": True,
            "run_clock": True,
            "barrel": True,
            "pickup": True,
            "money": True,
            "client": True,
            "selection": True,
            "client_coin": True,
            "input_barrel": True,
            "chest_drop": True,
            "chest_purchase": True,
            "droplet_load": True,
            "droplet_flight": True,
            "droplet_collision": True,
            "default_pickup": True,
            "chest_ejection": True,
        },
        "historical",
        "Prepare the nova chest ejection probe.",
    ),
    Action("nova-bridge-raw-run", "nova_bridge", "run_probe", {"physical": False, "retry": False}, "historical", "Run the nova bridge raw probe."),
    Action("nova-bridge-raw-retry", "nova_bridge", "run_probe", {"physical": False, "retry": True}, "historical", "Retry the nova bridge raw probe."),
    Action("nova-bridge-bind", "nova_bridge", "bind", {}, "historical", "Bind the measured Nova input mapping."),
    Action("nova-bridge-commando-run", "nova_bridge", "run_probe", {"physical": True, "retry": False}, "historical", "Run the nova bridge commando probe."),
    Action(
        "nova-input-prepare",
        "nova_input",
        "observe",
        {"capture": False},
        "historical",
        "Observe Nova input and print JSON.",
        handler=partial(_json_result, indent=2),
    ),
    Action(
        "nova-input-capture",
        "nova_input",
        "observe",
        {"capture": True},
        "historical",
        "Capture Nova input and print JSON.",
        handler=partial(_json_result, indent=2),
    ),
    Action(
        "spawn-automatic-skill-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-skill-neutral"]},
        "historical",
        "Prepare the spawn automatic skill probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-auto-skill-neutral": 85,
                "body-state-spawn-state-auto-skill-primary": 85,
                "body-state-spawn-state-auto-skill-secondary": 85,
                "body-state-spawn-state-auto-skill-utility": 85,
                "body-state-spawn-state-auto-skill-special": 85,
            },
        ),
    ),
    Action(
        "spawn-automatic-skill-primary-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-skill-primary"], "retry": True},
        "historical",
        "Run the spawn automatic skill primary probe.",
    ),
    Action(
        "spawn-automatic-skill-secondary-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-skill-secondary"], "retry": True},
        "historical",
        "Run the spawn automatic skill secondary probe.",
    ),
    Action(
        "spawn-automatic-skill-utility-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-skill-utility"], "retry": True},
        "historical",
        "Run the spawn automatic skill utility probe.",
    ),
    Action(
        "spawn-automatic-skill-special-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-skill-special"], "retry": True},
        "historical",
        "Run the spawn automatic skill special probe.",
    ),
    Action(
        "spawn-automatic-model-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-model-neutral"]},
        "historical",
        "Prepare the spawn automatic model probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-auto-model-neutral": 85,
                "body-state-spawn-state-auto-model-motion": 85,
                "body-state-spawn-state-auto-model-reverse": 85,
                "body-state-spawn-state-auto-model-aim": 85,
            },
        ),
    ),
    Action(
        "spawn-automatic-model-motion-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-model-motion"], "retry": True},
        "historical",
        "Run the spawn automatic model motion probe.",
    ),
    Action(
        "spawn-automatic-model-reverse-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-model-reverse"], "retry": True},
        "historical",
        "Run the spawn automatic model reverse probe.",
    ),
    Action(
        "spawn-automatic-model-aim-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-model-aim"], "retry": True},
        "historical",
        "Run the spawn automatic model aim probe.",
    ),
    Action(
        "spawn-automatic-direction-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-direction-neutral"]},
        "historical",
        "Prepare the spawn automatic direction probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-auto-direction-neutral": 85,
                "body-state-spawn-state-auto-direction-motion": 85,
                "body-state-spawn-state-auto-direction-reverse": 85,
                "body-state-spawn-state-auto-direction-aim": 85,
            },
        ),
    ),
    Action(
        "spawn-automatic-direction-motion-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-direction-motion"], "retry": True},
        "historical",
        "Run the spawn automatic direction motion probe.",
    ),
    Action(
        "spawn-automatic-direction-reverse-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-direction-reverse"], "retry": True},
        "historical",
        "Run the spawn automatic direction reverse probe.",
    ),
    Action(
        "spawn-automatic-direction-aim-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-direction-aim"], "retry": True},
        "historical",
        "Run the spawn automatic direction aim probe.",
    ),
    Action(
        "spawn-automatic-health-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-health"]},
        "historical",
        "Prepare the spawn automatic health probe.",
        handler=partial(_timed_prepare, seconds={"body-state-spawn-state-auto-health": 85, "body-state-spawn-state-auto-barrier": 85}),
    ),
    Action(
        "spawn-automatic-barrier-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-barrier"], "retry": True},
        "historical",
        "Run the spawn automatic barrier probe.",
    ),
    Action(
        "spawn-automatic-body-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-body"]},
        "historical",
        "Prepare the spawn automatic body probe.",
        handler=partial(_timed_prepare, seconds={"body-state-spawn-state-auto-body": 85, "body-state-spawn-state-auto-body-ground": 85}),
    ),
    Action(
        "spawn-automatic-body-ground-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-body-ground"], "retry": True},
        "historical",
        "Run the spawn automatic body ground probe.",
    ),
    Action(
        "spawn-automatic-gravity-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-gravity", "body-state-spawn-state-auto-land"]},
        "historical",
        "Prepare the spawn automatic gravity probe.",
        handler=partial(
            _timed_prepare,
            seconds={
                "body-state-spawn-state-auto-gravity": 85,
                "body-state-spawn-state-auto-land": 85,
                "body-state-spawn-state-auto-ground-stop": 85,
                "body-state-spawn-state-auto-ground-wall": 85,
            },
        ),
    ),
    Action(
        "spawn-automatic-ground-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-ground-stop", "body-state-spawn-state-auto-ground-wall"], "retry": True},
        "historical",
        "Run the spawn automatic ground probe.",
    ),
    Action(
        "spawn-automatic-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {
            "spawn_states": True,
            "teleport_material": True,
            "cases": ["body-state-spawn-state-transition", "body-state-spawn-state-main-motion", "body-state-spawn-state-auto-state"],
        },
        "historical",
        "Prepare the spawn automatic probe.",
        handler=partial(
            _timed_prepare, seconds={"body-state-spawn-state-auto-state": 80, "body-state-spawn-state-auto-motor": 80, "body-state-spawn-state-auto-motion": 80}
        ),
    ),
    Action(
        "spawn-automatic-motion-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "teleport_material": True, "cases": ["body-state-spawn-state-auto-motion"]},
        "historical",
        "Prepare the spawn automatic motion probe.",
        handler=partial(
            _timed_prepare, seconds={"body-state-spawn-state-auto-state": 80, "body-state-spawn-state-auto-motor": 80, "body-state-spawn-state-auto-motion": 80}
        ),
    ),
    Action(
        "spawn-automatic-motor-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-state-spawn-state-auto-motor", "body-state-spawn-state-auto-motion"], "retry": True},
        "historical",
        "Run the spawn automatic motor probe.",
    ),
    Action(
        "spawn-main-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {
            "spawn_states": True,
            "teleport_material": True,
            "cases": ["body-state-spawn-state-main-motor", "body-state-spawn-state-main-neutral", "body-state-spawn-state-main-motion"],
        },
        "historical",
        "Prepare the spawn main probe.",
    ),
    Action(
        "teleport-material-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {
            "spawn_states": True,
            "teleport_material": True,
            "cases": ["body-state-spawn-state-material", "body-state-spawn-state-overlay", "body-state-spawn-state-transition"],
        },
        "historical",
        "Prepare the teleport material probe.",
    ),
    Action(
        "spawn-state-exit-prepare",
        "scene_runtime",
        "body_start_loadout_prepare",
        {"spawn_states": True, "cases": ["body-state-spawn-state-buff-removal", "body-state-spawn-state-entry"]},
        "historical",
        "Prepare the spawn state exit probe.",
    ),
    Action("spawn-state-prepare", "scene_runtime", "body_start_loadout_prepare", {"spawn_states": True}, "historical", "Prepare the spawn state probe."),
    Action("body-start-loadout-prepare", "scene_runtime", "body_start_loadout_prepare", {}, "historical", "Prepare the body start loadout probe."),
    Action(
        "body-start-catalog-prepare",
        "scene_runtime",
        "body_root_order_prepare",
        {"start_items": True, "cases": ["body-state-spawn-loadout-catalog", "body-state-spawn-body-start-catalog"]},
        "historical",
        "Prepare the body start catalog probe.",
    ),
    Action(
        "body-catalog-prepare",
        "scene_runtime",
        "body_root_order_prepare",
        {"start_items": True, "cases": ["body-catalog-registration"]},
        "historical",
        "Prepare the body catalog probe.",
    ),
    Action(
        "body-start-boundary-prepare",
        "scene_runtime",
        "body_root_order_prepare",
        {"start_items": True, "cases": ["body-state-spawn-master-start", "body-state-spawn-body-start"]},
        "historical",
        "Prepare the body start boundary probe.",
    ),
    Action(
        "automatic-spawn-prepare",
        "scene_runtime",
        "body_root_order_prepare",
        {"cases": ["body-state-spawn-automatic"]},
        "historical",
        "Prepare the automatic spawn probe.",
    ),
    Action("body-root-order-prepare", "scene_runtime", "body_root_order_prepare", {}, "historical", "Prepare the body root order probe."),
    Action(
        "body-root-awake-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "cases": ["body-state-spawn-awake"]},
        "historical",
        "Prepare the body root awake probe.",
    ),
    Action(
        "reciprocal-spawn-observe-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "cases": ["body-state-spawn-original"]},
        "historical",
        "Prepare the reciprocal spawn observe probe.",
    ),
    Action(
        "reciprocal-spawn-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "cases": ["body-state-spawn-loadout", "body-state-spawn-original"]},
        "historical",
        "Prepare the reciprocal spawn probe.",
    ),
    Action(
        "master-tracker-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {
            "recovered": True,
            "jump_items": True,
            "cases": [
                "body-state-jump-serialize-master",
                "body-state-jump-client",
                "body-state-jump-owner",
                "body-state-jump-client-event",
                "body-state-jump-client-input",
            ],
        },
        "historical",
        "Prepare the master tracker probe.",
    ),
    Action(
        "recovered-body-serialization-retry-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "jump_items": True, "cases": ["body-state-jump-serialize-body"]},
        "historical",
        "Prepare the recovered body serialization retry probe.",
    ),
    Action(
        "recovered-serialization-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "jump_items": True, "cases": ["body-state-jump-serialize-body", "body-state-jump-serialize-master"]},
        "historical",
        "Prepare the recovered serialization probe.",
    ),
    Action(
        "state-catalog-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {
            "recovered": True,
            "jump_items": True,
            "cases": [
                "body-state-jump-catalog",
                "body-state-jump-client",
                "body-state-jump-owner",
                "body-state-jump-client-event",
                "body-state-jump-client-input",
            ],
        },
        "historical",
        "Prepare the state catalog probe.",
    ),
    Action(
        "recovered-client-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {
            "recovered": True,
            "jump_items": True,
            "cases": ["body-state-jump-client", "body-state-jump-owner", "body-state-jump-client-event", "body-state-jump-client-input"],
        },
        "historical",
        "Prepare the recovered client probe.",
    ),
    Action(
        "local-ownership-retry-prepare",
        "scene_runtime",
        "movement_batch_prepare",
        {"cases": ["network-local-connect", "network-local-owner"]},
        "historical",
        "Prepare the local ownership retry probe.",
    ),
    Action(
        "local-ownership-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "jump_items": True, "cases": ["body-state-jump-authority", "network-local-connect", "network-local-owner"]},
        "historical",
        "Prepare the local ownership probe.",
    ),
    Action(
        "body-jump-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "jump_items": True, "cases": ["body-state-jump-context", "body-state-jump-event", "body-state-jump-input"]},
        "historical",
        "Prepare the body jump probe.",
    ),
    Action("body-visual-prepare", "scene_runtime", "recovered_visual_prepare", {}, "historical", "Prepare the body visual probe."),
    Action(
        "body-grounded-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "cases": ["body-state-ground-stop", "body-state-ground-reverse", "body-state-ground-wall"]},
        "historical",
        "Prepare the body grounded probe.",
    ),
    Action(
        "body-landing-retry-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "cases": ["body-state-land"]},
        "historical",
        "Prepare the body landing retry probe.",
    ),
    Action(
        "body-gravity-prepare",
        "scene_runtime",
        "grounded_state_prepare",
        {"recovered": True, "cases": ["body-state-start", "body-state-gravity", "body-state-land"]},
        "historical",
        "Prepare the body gravity probe.",
    ),
    Action(
        "body-state-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "adoption": True, "stats": True, "stat_buffs": True, "cases": ["body-state-entry", "body-state-input", "body-state-motion"]},
        "historical",
        "Prepare the body state probe.",
    ),
    Action(
        "body-level-motor-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "adoption": True, "stats": True, "stat_buffs": True, "cases": ["body-level-stats", "body-computed-motor"]},
        "historical",
        "Prepare the body level motor probe.",
    ),
    Action(
        "body-buffs-methods-run",
        "scene_runtime",
        "movement_batch_run",
        {"cases": ["body-knockback-handler", "body-original-stats"], "retry": True},
        "historical",
        "Run the body buffs methods probe.",
    ),
    Action(
        "body-buffs-reference-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "adoption": True, "stats": True, "stat_buffs": True, "cases": ["body-awake", "body-stat-buffs"]},
        "historical",
        "Prepare the body buffs reference probe.",
    ),
    Action(
        "body-stats-buffs-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {
            "body_lifecycle": True,
            "adoption": True,
            "stats": True,
            "stat_buffs": True,
            "cases": ["body-stat-buffs", "body-knockback-handler", "body-original-stats"],
        },
        "historical",
        "Prepare the body stats buffs probe.",
    ),
    Action(
        "body-stats-motor-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "adoption": True, "stats": True, "cases": ["body-motor-awake", "body-original-stats"]},
        "historical",
        "Prepare the body stats motor probe.",
    ),
    Action(
        "body-stats-retry-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "adoption": True, "stats": True, "cases": ["body-skill-awake", "body-original-stats"]},
        "historical",
        "Prepare the body stats retry probe.",
    ),
    Action(
        "body-stats-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {
            "body_lifecycle": True,
            "adoption": True,
            "stats": True,
            "cases": ["team-manager-context", "body-team-context", "run-singleton-context", "body-original-stats"],
        },
        "historical",
        "Prepare the body stats probe.",
    ),
    Action(
        "body-adoption-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "adoption": True, "cases": ["body-adoption-content", "body-inventory-adoption"]},
        "historical",
        "Prepare the body adoption probe.",
    ),
    Action(
        "body-network-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "cases": ["body-network-state", "body-network-spawn", "master-network-spawn", "body-master-id"]},
        "historical",
        "Prepare the body network probe.",
    ),
    Action(
        "body-lifecycle-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"body_lifecycle": True, "cases": ["body-buff-storage", "body-awake", "body-registration", "master-awake"]},
        "historical",
        "Prepare the body lifecycle probe.",
    ),
    Action("jump-input-prepare", "scene_runtime", "grounded_state_prepare", {"jump_items": True}, "historical", "Prepare the jump input probe."),
    Action("grounded-state-prepare", "scene_runtime", "grounded_state_prepare", {}, "historical", "Prepare the grounded state probe."),
    Action(
        "gravity-state-prepare",
        "scene_runtime",
        "landing_batch_prepare",
        {"cases": ["gravity-rules", "gravity-fall", "gravity-jump-land", "state-input", "state-motion"]},
        "historical",
        "Prepare the gravity state probe.",
    ),
    Action(
        "landing-context-prepare", "scene_runtime", "landing_batch_prepare", {"cases": ["landing-context"]}, "historical", "Prepare the landing context probe."
    ),
    Action("landing-batch-prepare", "scene_runtime", "landing_batch_prepare", {}, "historical", "Prepare the landing batch probe."),
    Action(
        "motor-wall-prepare",
        "scene_runtime",
        "movement_batch_prepare",
        {"integrated": True, "cases": ["integrated-wall"]},
        "historical",
        "Prepare the motor wall probe.",
    ),
    Action("motor-integration-prepare", "scene_runtime", "movement_batch_prepare", {"integrated": True}, "historical", "Prepare the motor integration probe."),
    Action("kinematic-batch-prepare", "scene_runtime", "movement_batch_prepare", {"kinematic": True}, "historical", "Prepare the kinematic batch probe."),
    Action("movement-batch-prepare", "scene_runtime", "movement_batch_prepare", {}, "historical", "Prepare the movement batch probe."),
    Action(
        "movement-batch-run",
        "scene_runtime",
        "movement_batch_run",
        {},
        "historical",
        "Run the movement batch probe. Accepts --debug-options.",
        handler=_movement_batch,
    ),
    Action(
        "movement-batch-retry",
        "scene_runtime",
        "movement_batch_run",
        {"retry": True},
        "historical",
        "Retry the movement batch probe. Accepts --debug-options.",
        handler=_movement_batch,
    ),
    Action("direction-prepare", "scene_runtime", "direction_prepare", {}, "historical", "Prepare the direction probe."),
    Action("state-tick-prepare", "scene_runtime", "state_tick_prepare", {}, "historical", "Prepare the state tick probe."),
    Action("material-render-prepare", "scene_runtime", "material_render_prepare", {}, "historical", "Prepare the material render probe."),
    Action("skin-prepare", "scene_runtime", "skin_prepare", {}, "historical", "Prepare the skin probe."),
    Action("avatar-prepare", "scene_runtime", "avatar_prepare", {}, "historical", "Prepare the avatar probe."),
    Action("controller-prepare", "scene_runtime", "controller_prepare", {}, "historical", "Prepare the controller probe."),
    Action("controller-run", "scene_runtime", "scene_run", {}, "historical", "Run the controller probe."),
    Action("pose-prepare", "scene_runtime", "pose_prepare", {}, "historical", "Prepare the pose probe."),
    Action("prefab-bind", "scene_runtime", "prefab_bind", {}, "historical", "Bind the recovered prefab."),
    Action("prefab-prepare", "scene_runtime", "scene_prepare", {"include_prefab": True}, "historical", "Prepare the prefab probe."),
    Action("scene-arm", "scene_runtime", "scene_arm", {}, "historical", "Arm the scene runtime probe."),
    Action("scene-run", "scene_runtime", "scene_run", {}, "historical", "Run the scene probe."),
    Action("scene-prepare", "scene_runtime", "scene_prepare", {}, "historical", "Prepare the scene probe."),
    Action("scene-closure", "scene_closure", "scene_closure", {}, "historical", "Inspect scene dependency closure."),
    Action("dependency-boundaries", "boundaries", "dependency_boundaries", {}, "historical", "Probe recovered dependency boundaries."),
    Action("rewired-original", "boundaries", "rewired_original", {}, "historical", "Probe original Rewired virtual slots."),
    Action("collections-runtime", "boundaries", "collections_runtime", {}, "historical", "Probe the pinned collections runtime."),
    Action("ror2-slice", "boundaries", "ror2_slice", {}, "historical", "Run the original managed-code slice probe."),
    Action("original-closure-runtime", "boundaries", "ror2_slice", {"full_original": True}, "historical", "Run the full original managed closure probe."),
    Action("original-closure-prepare", "boundaries", "original_closure_prepare", {}, "historical", "Prepare the original closure probe."),
    Action("original-closure-build", "boundaries", "original_closure_build", {}, "historical", "Build the original managed closure probe."),
    Action("recompile", "experiments", "recompile", {}, "historical", "Probe compilation of recovered source."),
    Action("middleware", "experiments", "middleware", {}, "historical", "Inspect native Wwise version and bank metadata."),
    Action(
        "repair-reconstruction",
        "subprocess",
        "call",
        {},
        "historical",
        "Run the recorded reconstruction ambiguity patch; preserve its exit code.",
        handler=_repair_reconstruction,
    ),
    Action("storage-lifecycle", "lifecycle", "lifecycle", {}, "historical", "Run the disposable storage lifecycle experiment."),
    Action("references", "experiments", "references", {}, "historical", "Audit external GUID references in generated assets."),
    Action("reconstruction", "experiments", "reconstruction_report", {}, "historical", "Report recovered scene, shader and source inventory."),
)

ACTIONS = {action.name: action for action in _ENTRIES}

# argparse defaults to "inspect". All unrecognized names historically ran this
# same preparation; keep that fallback instead of rejecting unknown names.
DEFAULT_ACTION = Action("inspect", "prepare", "prepare", {}, "historical", "Stage the initial prototype; also the fallback for unknown action names.")


def dispatch(args):
    action = ACTIONS.get(args.action, DEFAULT_ACTION)
    function = getattr(import_module(action.module), action.function)
    # The old call expressions constructed fresh lists on every invocation.
    kwargs = deepcopy(action.kwargs)
    if action.handler is not None:
        return action.handler(function, kwargs, args)
    return function(**kwargs)


def print_actions():
    """List current actions first, followed by the historical actions and fallback."""
    entries = (*ACTIONS.values(), DEFAULT_ACTION)
    for status in ("current", "historical"):
        print(status + ":")
        for action in sorted(entries, key=lambda entry: entry.name):
            if action.status == status:
                print(f"  {action.name:<43} {action.help}")
