from common import *
from build_lock import (
    HOST_BUILD_LOCK,
    active_lock_handoff,
    assert_build_unblocked,
    assert_host_build_lock_held,
    host_build_lock,
)
import re
import shutil
import time
import zipfile
import sys
import threading
import uuid
from contextlib import contextmanager
from build_timing import PhaseTiming, bee_timing, editor_log_cursor, editor_log_timing

_build_dispatch_state = threading.local()


@contextmanager
def coordinated_editor_operation():
    """Authorize a nested editor build action while its caller owns the lock."""
    assert_host_build_lock_held(HOST_BUILD_LOCK)
    previous = getattr(_build_dispatch_state, "active", False)
    _build_dispatch_state.active = True
    try:
        yield
    finally:
        _build_dispatch_state.active = previous


def sha256_file_member(archive_path, member):
    h = hashlib.sha256()
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_build_artifact(source, destination, *, verify=True):
    # Independent copy-on-write snapshots prevent repeated payloads exhausting host space.
    # Fall back to ordinary copies off APFS; artifact identity is always byte-checked.
    source = Path(source)
    destination = Path(destination)
    if not source.is_file() or source.is_symlink() or destination.is_symlink():
        raise RuntimeError("Build artifact paths must be regular files")
    before = file_identity(source)
    if source.resolve() == destination.resolve():
        raise RuntimeError("Build snapshot must have a different destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # cp -c cannot replace an existing destination; remove only this explicitly
    # selected disposable snapshot, never its source.
    destination.unlink(missing_ok=True)
    cloned = sys.platform == "darwin" and run(["/bin/cp", "-c", "-p", source, destination], check=False).returncode == 0
    if not cloned:
        shutil.copy2(source, destination)
    source_stat = source.stat()
    destination_stat = destination.stat()
    if (
        (source_stat.st_dev, source_stat.st_ino) == (destination_stat.st_dev, destination_stat.st_ino)
        or file_identity(source) != before
        or source_stat.st_size != destination_stat.st_size
        or (verify and sha(source) != sha(destination))
    ):
        raise RuntimeError("Build snapshot independence or hash verification failed")
    return str(destination)


def validate_runtime_support(project, recipe):
    config_path = project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
    if not config_path.exists():
        return
    config = read(config_path)
    required = config.get("objectiveSupportAssets", [])
    supplied = {path.casefold() for path in recipe.get("objectiveSupportAssets", [])}
    missing = [path for path in required if path.casefold() not in supplied]
    if missing:
        raise RuntimeError("Runtime objective support omitted from build recipe: " + ", ".join(missing))
    character = {path.casefold() for path in recipe.get("prefabAssets", [])}
    if character & supplied:
        raise RuntimeError("Runtime objective support has two explicit bundle owners")
    missing_effects = [path for path in config.get("objectiveEffectAssets", []) if path.casefold() not in character | supplied]
    if missing_effects:
        raise RuntimeError("Runtime objective effect has no explicit bundle owner: " + ", ".join(missing_effects))


def validate_project_generation(project, input_id):
    marker = Path(project) / ".port-input.json"
    if not marker.exists() or read(marker).get("input_id") != input_id:
        raise RuntimeError("Lab project belongs to another or unrecorded input generation; stage the reviewed migration before building")


def preflight_host():
    """Validate accepted host inputs and toolchain without querying a device."""
    cfg = config()
    base = game()
    inv = read(WORK / "inventory/files.json")
    current = {str(p.relative_to(base)): (p.stat().st_size, p.stat().st_mtime_ns) for p in base.rglob("*") if p.is_file()}
    prior = {x["path"]: (x["size"], x["mtime_ns"]) for x in inv["files"]}
    if current != prior:
        raise RuntimeError("Input changed: run ./dev inspect, review input-diff and explicitly adopt a new baseline")
    accepted = read(WORK / "config/accepted-input.json") if (WORK / "config/accepted-input.json").exists() else None
    if not accepted or accepted["input_id"] != inv["input_id"]:
        raise RuntimeError("Input not accepted; review inventory before updating work/config/accepted-input.json")
    validate_project_generation(WORK / "lab-project", inv["input_id"])
    if shutil.disk_usage(ROOT).free < 10 * 1024**3:
        raise RuntimeError("Less than 10 GiB host headroom")
    pin = toolchain()
    if inv["unity_versions"] != [pin["unity_version"]]:
        raise RuntimeError("Accepted game and exact editor pin differ")
    if (ROOT / "smoke/ProjectSettings/ProjectVersion.txt").read_text().find(pin["unity_version"] + " (" + pin["unity_revision"] + ")") < 0:
        raise RuntimeError("Unity source version pin changed")
    import plistlib

    plist = Path(os.environ["UNITY_EDITOR"]).parent.parent / "Info.plist"
    if plistlib.loads(plist.read_bytes()).get("CFBundleVersion") != pin["unity_version"]:
        raise RuntimeError("Selected editor differs from exact pin")
    tracked = run(["git", "ls-files", "-z"], check=True).stdout.decode().split("\0")
    bad = [
        p
        for p in tracked
        if p.startswith(("work/", "build/", "logs/", "screenshots/"))
        or Path(p).suffix.lower() in [".dll", ".exe", ".so", ".apk", ".aab", ".bnk", ".wem", ".bundle", ".keystore", ".jks"]
    ]
    if bad:
        raise RuntimeError("Restricted files tracked: " + str(bad))
    result = {
        "success": True,
        "input_id": inv["input_id"],
        "host_free_bytes": shutil.disk_usage(ROOT).free,
        "scope": "lab build; does not certify full game or semantic patches",
    }
    return result


def preflight():
    """CLI preflight includes device storage; builds use host-only gates."""
    result = preflight_host()
    from device import Device

    result["storage"] = Device().storage()
    write(WORK / "preflight.json", result)
    return result


def editor(target="lab", action="inspect"):
    coordinated_build = bool(getattr(_build_dispatch_state, "active", False))
    assert_build_unblocked()
    if action == "minimal-build":
        raise RuntimeError("The historical minimal-build editor action is unsupported; use ./dev build")
    if action in {"build", "presentation-payload"} and not coordinated_build:
        destination = "./dev build" if action == "build" else "the presentation-payload coordinator"
        raise RuntimeError("Direct editor build dispatch is disabled; use " + destination + " so the host lock covers result collection")
    with host_build_lock(HOST_BUILD_LOCK, operation=f"editor:{target}:{action}"):
        assert_build_unblocked()
        if action == "open":
            project = (
                WORK / "lab-project"
                if target == "lab"
                else ROOT / "smoke"
                if target == "smoke"
                else ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
            )
            project = project.resolve()
            if not project.is_dir():
                raise RuntimeError("Project does not exist: " + str(project))
            commands = run(["/bin/ps", "-axo", "command"]).stdout.decode().splitlines()
            if any(c.startswith(os.environ["UNITY_EDITOR"] + " ") and " -projectPath " + str(project) + " " in c for c in commands):
                return "Editor already open; inspect MCP connectivity with ./dev editor --target " + target
            env = os.environ.copy()
            env.update(
                {
                    "ANDROID_SDK_HOME": str(ROOT / ".local/android-user"),
                    "ANDROID_USER_HOME": str(ROOT / ".local/android-user/.android"),
                    "GRADLE_USER_HOME": str(ROOT / ".local/gradle"),
                }
            )
            stamp = now()
            log = WORK / "logs" / stamp[:8] / (target + "-editor-" + stamp + ".log")
            log.parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                [os.environ["UNITY_EDITOR"], "-batchmode", "-projectPath", str(project), "-executeMethod", "BootstrapMcp.Connect", "-logFile", str(log)]
                + (["-buildTarget", "Android"] if target == "lab" else []),
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            write(WORK / "editor" / (target + "-process.json"), {"pid": proc.pid, "project": str(project), "log": str(log)})
            return json.dumps(
                {"started": True, "pid": proc.pid, "log": str(log), "next": "Wait for import/MCP connection, then ./dev editor --target " + target}
            )
        if action == "minimal-build":
            preflight_host()
        env = os.environ.copy()
        handoff_env, pass_fds = active_lock_handoff()
        env.update(handoff_env)
        if coordinated_build:
            env["ROR2LAB_COORDINATED_BUILD"] = "1"
        return run(
            [ROOT / ".local/tools/unity-mcp/Server/.venv/bin/python", ROOT / "scripts/lab/editor.py", target, action],
            timeout=200,
            env=env,
            pass_fds=pass_fds,
        ).stdout.decode()


WHOLE_GENERATED_RUNTIME_SOURCES = {"OriginalBodyVisualMap.cs", "OriginalHealthVisualMap.cs", "OriginalGlobalCommonAssetMap.cs"}


def runtime_sources():
    names = read(RECIPE / "runtime-sources.json")
    if not isinstance(names, list) or any(
        not isinstance(name, str)
        or Path(name).is_absolute()
        or ".." in Path(name).parts
        or "\\" in name
        or Path(name).as_posix() != name
        or not name.endswith(".cs")
        for name in names
    ):
        raise RuntimeError("recipe/runtime-sources.json must list relative tools/unity C# paths")
    if names != sorted(set(names)):
        raise RuntimeError("recipe/runtime-sources.json must be sorted and unique")
    basenames = [Path(name).name for name in names]
    if len(basenames) != len(set(basenames)) or set(basenames) & WHOLE_GENERATED_RUNTIME_SOURCES:
        raise RuntimeError("recipe/runtime-sources.json has a staging basename collision")
    missing = [name for name in names if not (ROOT / "tools/unity" / name).is_file()]
    if missing:
        raise RuntimeError("Runtime manifest sources missing from tools/unity: " + ", ".join(missing))
    return names


def whole_player_inputs():
    inputs = {
        "Assets/LabDiagnostics.cs",
        "Assets/Lab.unity",
        "Assets/Lab.unity.meta",
        "Assets/LabLoadingScene/WholeCatalogPreservation.meta",
        "Assets/LabLoadingScene/WholeCatalogPreservation/link.xml",
        "Assets/LabLoadingScene/WholeCatalogPreservation/link.xml.meta",
    }
    # APK-only consumers of unchanged converted assets; retain Unity-owned metadata.
    inputs.update(
        "Assets/LabLoadingScene/" + name + suffix
        for name in [Path(source).name for source in runtime_sources()] + sorted(WHOLE_GENERATED_RUNTIME_SOURCES) + ["Resources/WholeStageContexts.json"]
        for suffix in ("", ".meta")
    )
    return inputs


WHOLE_PLAYER_INPUTS = whole_player_inputs()


def validate_runtime_source_membership(project):
    names = runtime_sources()
    known = {Path(name).name for name in names} | WHOLE_GENERATED_RUNTIME_SOURCES
    stage = Path(project) / "Assets/LabLoadingScene"
    unexpected = sorted(str(source.relative_to(stage)) for source in stage.rglob("*.cs") if source.is_file() and str(source.relative_to(stage)) not in known)
    if unexpected:
        raise RuntimeError(
            "Unlisted whole-catalog C# sources in Assets/LabLoadingScene: "
            + ", ".join(unexpected)
            + "; review recipe/runtime-sources.json or declare their build generator"
        )
    return names


def whole_payload_inputs(project):
    return {
        str(p.relative_to(project)): sha(p)
        for folder in ["Assets", "Packages", "ProjectSettings"]
        for p in (project / folder).rglob("*")
        if p.is_file() and str(p.relative_to(project)) not in WHOLE_PLAYER_INPUTS and not str(p.relative_to(project)).startswith("Assets/Editor/")
    }


def freeze_whole_payload(project, result):
    write(
        WORK / "whole-catalog-code-base.json",
        dict(files=whole_payload_inputs(project), allowed=sorted(WHOLE_PLAYER_INPUTS), payload=result["payload"], build_key=result["key"]),
    )


def validate_whole_payload_reuse(project):
    receipt = read(WORK / "whole-catalog-code-base.json")
    previous_allowed = set(receipt["allowed"])
    added = WHOLE_PLAYER_INPUTS - previous_allowed
    if previous_allowed - WHOLE_PLAYER_INPUTS or any(not p.startswith("Assets/LabLoadingScene/") or not p.endswith((".cs", ".cs.meta")) for p in added):
        raise RuntimeError("Unexpected code-only content exception")
    current = whole_payload_inputs(project)
    expected = {path: value for path, value in receipt["files"].items() if path not in added}
    if current != expected:
        raise RuntimeError("Content inputs changed; code-only bundle reuse rejected")
    current_payload = {p.name: sha(p) for p in (WORK / "generated-android-data").iterdir() if p.is_file()}
    if current_payload != receipt["payload"]:
        raise RuntimeError("Frozen whole-catalog payload identity changed")
    if added:
        write(WORK / "whole-catalog-code-base.json", dict(receipt, files=current, allowed=sorted(WHOLE_PLAYER_INPUTS)))


def validate_project_layout(project):
    """Check authored Unity identities and direct dependency pins without repairing them."""
    recipe_path = RECIPE / "project-layout.json"
    try:
        layout = read(recipe_path)
    except (OSError, ValueError) as error:
        raise RuntimeError("Cannot read recipe/project-layout.json") from error
    guids = layout.get("runtime_source_guids") if isinstance(layout, dict) else None
    dependencies = layout.get("dependencies") if isinstance(layout, dict) else None
    if not isinstance(guids, dict) or set(guids) != set(runtime_sources()):
        raise RuntimeError("recipe/project-layout.json runtime_source_guids must match recipe/runtime-sources.json exactly")
    # null marks a new source that Unity has not imported yet; record its GUID after the first build.
    known = [guid for guid in guids.values() if guid is not None]
    if any(not isinstance(guid, str) or not re.fullmatch(r"[0-9a-f]{32}", guid) for guid in known) or len(set(known)) != len(known):
        raise RuntimeError("recipe/project-layout.json must contain unique 32-character lowercase hex GUIDs")
    if (
        not isinstance(dependencies, dict)
        or not dependencies
        or any(not isinstance(name, str) or not name or not isinstance(version, str) or not version for name, version in dependencies.items())
    ):
        raise RuntimeError("recipe/project-layout.json dependencies must map package names to nonempty version or URL strings")
    project = Path(project)
    for source, expected in sorted(guids.items()):
        if expected is None:
            continue
        relative = "Assets/LabLoadingScene/" + Path(source).name + ".meta"
        meta = project / relative
        if not meta.is_file():
            raise RuntimeError("Project layout missing staged .meta: " + relative)
        with meta.open() as stream:
            guid_lines = [line.rstrip("\r\n") for line in stream if line.startswith("guid:")]
        if len(guid_lines) != 1 or not re.fullmatch(r"guid: [0-9a-f]{32}", guid_lines[0]):
            raise RuntimeError("Project layout invalid staged .meta GUID: " + relative)
        actual = guid_lines[0].split()[1]
        if actual != expected:
            raise RuntimeError(f"Project layout GUID mismatch: {relative}; expected {expected}, found {actual}; review recipe/project-layout.json")
    try:
        manifest = read(project / "Packages/manifest.json")
    except (OSError, ValueError) as error:
        raise RuntimeError("Project layout cannot read Packages/manifest.json") from error
    actual = manifest.get("dependencies") if isinstance(manifest, dict) else None
    if not isinstance(actual, dict):
        raise RuntimeError("Project layout Packages/manifest.json must contain a dependencies object")
    missing = sorted(set(dependencies) - set(actual))
    extra = sorted(set(actual) - set(dependencies))
    changed = sorted(name for name in set(actual) & set(dependencies) if actual[name] != dependencies[name])
    differences = []
    if missing:
        differences.append("missing packages: " + ", ".join(missing))
    if extra:
        differences.append("extra packages: " + ", ".join(extra))
    if changed:
        differences.append("changed packages: " + ", ".join(changed))
    if differences:
        raise RuntimeError("Project layout Packages/manifest.json differs from recipe/project-layout.json; " + "; ".join(differences))


def generate_runtime_config(project, io=None):
    """Replace the runtime resource with exactly the audited recipe, including JSON types."""
    (io.write if io else write)(Path(project) / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", _read_public_recipe("runtime-config.json"))


def generate_content_recipe(io=None):
    """Replace the bundle selection with exactly the audited recipe; retain no local extras."""
    (io.write if io else write)((io.work if io else WORK) / "scene-probe-build.json", _read_public_recipe("content.json"))


def validate_runtime_config(project):
    """Check the public runtime selection without writing config or rejecting local extras."""
    relative = "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
    _validate_public_recipe("runtime-config.json", Path(project) / relative, "Runtime config", relative)


def validate_content_recipe(work=None):
    """Check public bundle selectors against work without writing it or rejecting local extras."""
    _validate_public_recipe(
        "content.json", (Path(work) if work is not None else WORK) / "scene-probe-build.json", "Content recipe", "work/scene-probe-build.json"
    )


def _read_public_recipe(recipe_name):
    try:
        recipe = read(RECIPE / recipe_name)
    except (OSError, ValueError) as error:
        raise RuntimeError("Cannot read recipe/" + recipe_name) from error
    if not isinstance(recipe, dict) or not recipe:
        raise RuntimeError("recipe/" + recipe_name + " must contain a nonempty object")
    return recipe


def _validate_public_recipe(recipe_name, staged_path, label, relative):
    """Compare selected fields with strict JSON types; diagnostics disclose keys only."""
    recipe = _read_public_recipe(recipe_name)
    try:
        staged = read(staged_path)
    except (OSError, ValueError) as error:
        raise RuntimeError(label + " cannot read " + relative) from error
    if not isinstance(staged, dict):
        raise RuntimeError(label + " " + relative + " must contain an object")

    def equal(expected, actual):
        if type(expected) is not type(actual):
            return False
        if isinstance(expected, dict):
            return expected.keys() == actual.keys() and all(equal(value, actual[key]) for key, value in expected.items())
        if isinstance(expected, list):
            return len(expected) == len(actual) and all(equal(a, b) for a, b in zip(expected, actual))
        return expected == actual

    missing = sorted(recipe.keys() - staged.keys())
    changed = sorted(key for key in recipe.keys() & staged.keys() if not equal(recipe[key], staged[key]))
    differences = []
    if missing:
        differences.append("missing keys: " + ", ".join(missing))
    if changed:
        differences.append("changed keys: " + ", ".join(changed))
    if differences:
        # Report names only: staged values may contain private local data.
        raise RuntimeError(label + " " + relative + " differs from recipe/" + recipe_name + "; " + "; ".join(differences))


def validate_staged_runtime_sources(project, work=None):
    if not ((Path(work) if work is not None else WORK) / "whole-catalog-build.json").exists():
        return
    stage = Path(project) / "Assets/LabLoadingScene"
    stale = [
        name
        for name in validate_runtime_source_membership(project)
        if not (stage / Path(name).name).is_file() or (ROOT / "tools/unity" / name).read_bytes() != (stage / Path(name).name).read_bytes()
    ]
    if stale:
        raise RuntimeError("Whole-catalog runtime sources are not staged: " + ", ".join(stale[:12]) + "; run ./dev prototype --action whole-catalog-code-build")
    validate_project_layout(project)
    validate_runtime_config(project)
    validate_content_recipe(work=work)


def build_cache_key(project, api, android_symbols="none"):
    project = Path(project)
    inputs = {
        str(p.relative_to(project)): sha(p) for sub in ["Assets", "Packages", "ProjectSettings"] for p in sorted((project / sub).rglob("*")) if p.is_file()
    }
    external = {}
    recipe = WORK / "scene-probe-build.json"
    if recipe.exists():
        external["bundle_recipe"] = sha(recipe)
    whole = WORK / "whole-catalog-build.json"
    if whole.exists():
        manifest = Path(read(whole)["manifest"])
        if not manifest.is_absolute():
            manifest = ROOT / manifest
        if not manifest.is_file():
            raise RuntimeError("Whole-catalog build manifest is missing")
        external["whole_catalog_manifest"] = sha(manifest)
    identity = {
        "inputs": inputs,
        "external": external,
        "api": api,
        "editor": toolchain(),
        "backend": "IL2CPP-ARM64",
        "tool": sha(ROOT / "scripts/lab/build.py"),
    }
    if android_symbols != "none":
        identity["android_symbols"] = android_symbols
        if android_symbols == "debugging":
            identity["symbol_validator"] = sha(ROOT / "scripts/lab/symbol_artifacts.py")
    return digest(identity)


def stage_android_assets(project, io=None):
    """Place Android assets without starting Unity; the real copytree contract stays intact."""
    if io is None:
        shutil.copytree(ROOT / "android/Assets", project / "Assets", dirs_exist_ok=True, copy_function=lambda a, b: copy_build_artifact(a, b, verify=False))
    else:
        for source in sorted((ROOT / "android/Assets").rglob("*")):
            if source.is_file():
                io.apply(project / "Assets" / source.relative_to(ROOT / "android/Assets"), copy=source)


# Authored sources a whole-catalog build stages into the project (J738).
BUILD_SOURCE_PATHS = ("tools/unity", "tools/catalog", "android/Assets/Editor")


def build_source_identity():
    """The committed source a build stages; refuses uncommitted or untracked build sources."""

    def git(*args):
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout

    dirty = git("status", "--porcelain", "--untracked-files=all", "--", *BUILD_SOURCE_PATHS).splitlines()
    if dirty:
        raise RuntimeError(
            "Uncommitted build sources; commit them before building so the build is reproducible (J738): " + ", ".join(line[3:] for line in dirty[:10])
        )
    return dict(commit=git("rev-parse", "HEAD").strip(), clean_paths=list(BUILD_SOURCE_PATHS))


def build(
    api="gles",
    force=False,
    reuse_payload=False,
    destination=None,
    work=None,
    source=None,
    android_symbols="none",
    capture_player_linker_inputs=False,
    capture_il2cpp_invocation=False,
    iteration_mode="",
):
    timing = PhaseTiming()
    if api not in ["gles", "vulkan", "lab"]:
        raise RuntimeError("Build target must be gles or vulkan")
    if android_symbols not in {"none", "debugging"}:
        raise RuntimeError("Android symbols mode must be none or debugging")
    if iteration_mode not in {"", "export-splice", "scripts-only"}:
        raise RuntimeError("Unknown iteration mode")
    if iteration_mode and (not reuse_payload or destination is not None or android_symbols != "none" or capture_player_linker_inputs):
        raise RuntimeError("Iteration requires the current frozen payload and no symbols/captures")
    if destination is not None and android_symbols != "none":
        raise RuntimeError("Debugging symbols are supported only by the normal lab build path")
    if capture_il2cpp_invocation and not capture_player_linker_inputs:
        raise RuntimeError("IL2CPP invocation capture requires the pre-strip UnityLinker capture for a same-build join")
    if (capture_player_linker_inputs or capture_il2cpp_invocation) and destination is not None:
        raise RuntimeError("Unity linker/IL2CPP capture requires the current local Unity project")
    capture_request = {}
    request_id = now()
    if capture_player_linker_inputs:
        from player_linker_receipt import request_capture_fields

        capture_request = request_capture_fields(
            True,
            source,
            read(WORK / "inventory/files.json")["input_id"],
            capture_il2cpp_invocation=capture_il2cpp_invocation,
        )
        # Opt-in captures always get a fresh receipt namespace; cached player
        # results cannot stand in for a capture made by this exact request.
        request_id = request_id + "-" + uuid.uuid4().hex
    if api == "lab":
        api = "gles"
    assert_build_unblocked()
    with host_build_lock(HOST_BUILD_LOCK, operation="build: " + api), cached_hashes():
        assert_build_unblocked()
        if destination is not None:
            if reuse_payload:
                raise RuntimeError("Destination builds require full content; payload reuse is forbidden")
            from unity_rebuild import execute_build

            return execute_build(Path(destination), Path(work or WORK), api)
        preflight_host()
        project = WORK / "lab-project"
        anchor = None
        if iteration_mode:
            from iteration_apk import validate_anchor

            anchor = validate_anchor(WORK, read(WORK / "inventory/files.json")["input_id"], api)
        recipe = WORK / "scene-probe-build.json"
        if recipe.exists():
            validate_runtime_support(project, read(recipe))
        validate_staged_runtime_sources(project)
        # Keep staging, editor work and receipt collection in one host-wide critical section.
        stage_android_assets(project)
        if reuse_payload:
            validate_whole_payload_reuse(project)
        key = build_cache_key(project, api) if android_symbols == "none" else build_cache_key(project, api, android_symbols)
        if iteration_mode:
            key = digest({"build": key, "iteration_mode": iteration_mode, "request": request_id})
        if capture_player_linker_inputs:
            from player_linker_receipt import capture_cache_key

            key = capture_cache_key(key, request_id)
        dest = WORK / "build-cache" / key
        receipt = dest / "result.json"
        if android_symbols == "debugging" and dest.exists():
            if force:
                raise RuntimeError("Refuse to overwrite an existing symbol build cache")
            if not receipt.is_file():
                raise RuntimeError("Refuse to reuse or overwrite an incomplete symbol build cache")
            from symbol_artifacts import verify_cached_symbol_receipt

            verify_cached_symbol_receipt(receipt, dest)
        if receipt.exists() and capture_player_linker_inputs:
            raise RuntimeError("Refuse to reuse or overwrite an opted-in request-specific linker receipt")
        if receipt.exists() and not force and not capture_player_linker_inputs:
            r = read(receipt)
            if r.get("success") and r.get("errors", 0) == 0 and Path(r["apk"]).exists() and sha(r["apk"]) == r["apk_sha256"]:
                if android_symbols == "none" and r.get("android_symbols", "none") != "none":
                    raise RuntimeError("Build cache symbol mode does not match the requested normal build")
                for name, h in r.get("payload", {}).items():
                    source = dest / "payload" / name
                    if not source.is_file() or sha(source) != h:
                        raise RuntimeError("Cached payload is missing or changed: " + name)
                    copy_build_artifact(source, WORK / "generated-android-data" / name, verify=False)
                write(WORK / "config/current-build.json", r)
                print(json.dumps({"cached": True, **r}, indent=2))
                return r
        (WORK / "graphics-api.txt").write_text(api)
        result = WORK / "lab-build/result.json"
        if result.exists():
            result.rename(result.with_name("previous-" + now() + ".json"))
        request = {"request_id": request_id, "api": api, "reusePayload": reuse_payload}
        if iteration_mode:
            request["iterationMode"] = iteration_mode
        if capture_player_linker_inputs:
            request.update(capture_request)
        if android_symbols != "none":
            request["androidSymbols"] = android_symbols
        write(WORK / "build-request.json", request)
        timing.phases["staging_validation_hashes"] = time.monotonic() - timing.started
        log_cursor = editor_log_cursor(WORK)
        with timing.phase("editor_refresh"):
            print(editor("lab", "refresh"), flush=True)
        player_epoch = time.time()
        with timing.phase("editor_dispatch"):
            with coordinated_editor_operation():
                print(editor("lab", "build"), flush=True)
        wait_start = time.monotonic()
        dispatch_deadline = time.monotonic() + 120
        deadline = time.monotonic() + (3600 if (WORK / "whole-catalog-build.json").exists() else 1200)
        while time.monotonic() < deadline:
            if result.exists():
                if read(result).get("request_id") != request_id:
                    raise RuntimeError("Terminal build receipt belongs to a different request")
                break
            if time.monotonic() > dispatch_deadline and (
                not (WORK / "lab-build/started.json").exists() or read(WORK / "lab-build/started.json").get("request_id") != request_id
            ):
                raise RuntimeError("Queued build never started; inspect editor dispatch evidence")
            time.sleep(2)
        else:
            raise RuntimeError("Build timeout; inspect the editor log named in work/editor/lab-process.json; no cache stamp written")
        r = read(result)
        timing.phases["editor_wait"] = time.monotonic() - wait_start
        r["bee_timing"] = bee_timing(project, player_epoch, time.time())
        r["editor_log_timing"] = editor_log_timing(log_cursor)
        if not r["success"] or r.get("errors", 0) > 0:
            raise RuntimeError(r["result"] + "; build errors=" + str(r.get("errors", 0)))
        key = build_cache_key(project, api) if android_symbols == "none" else build_cache_key(project, api, android_symbols)
        if iteration_mode:
            key = digest({"build": key, "iteration_mode": iteration_mode, "request": request_id})
        if capture_player_linker_inputs:
            from player_linker_receipt import capture_cache_key

            key = capture_cache_key(key, request_id)
        dest = WORK / "build-cache" / key
        if dest.exists() and force and not capture_player_linker_inputs and not iteration_mode:
            key += "-build-" + request_id
            dest = WORK / "build-cache" / key
        receipt = dest / "result.json"
        if capture_player_linker_inputs and dest.exists():
            raise RuntimeError("Refuse to overwrite an existing request-specific linker output")
        dest.mkdir(parents=True, exist_ok=not capture_player_linker_inputs)
        build_report_output_path = str(Path(r["apk"]).resolve())
        apk = dest / ("lab-" + api + ".apk")
        if iteration_mode:
            from iteration_apk import assemble_export, GRADLE

            export = Path(r["apk"]).resolve()
            if not r.get("iteration_export_complete") or export != (project / GRADLE).resolve():
                raise RuntimeError("Unexpected iteration export output")
            r["iteration"] = {"mode": iteration_mode, **assemble_export(WORK, export, apk, anchor)}
        else:
            with timing.phase("apk_clone"):
                copy_build_artifact(r["apk"], apk, verify=False)
        with timing.phase("apk_hash"):
            apk_hash = sha(apk)
        r.update(
            {
                "apk": str(apk),
                "apk_sha256": apk_hash,
                "apk_cache_path": apk.name,
                "key": key,
                "graphics_api": api,
                "input_id": read(WORK / "inventory/files.json")["input_id"],
                "android_symbols": android_symbols,
            }
        )
        if source is not None:
            r["source"] = source
        if capture_il2cpp_invocation:
            r["build_report_output_path"] = build_report_output_path
        if capture_player_linker_inputs:
            capture_path = WORK / "lab-build/player-linker-inputs" / (request_id + ".json")
            if not capture_path.is_file():
                raise RuntimeError("Opted-in build lacks its same-request UnityLinker input capture")
            from player_linker_receipt import bind_successful_apk

            r = bind_successful_apk(
                r,
                read(capture_path),
                work_root=WORK,
                request_id=request_id,
                source_commit=source["commit"],
                input_id=capture_request["inputId"],
            )
        if capture_il2cpp_invocation:
            from bee_codegen_capture import collect_request_capture, editor_version_from_toolchain

            r["player_il2cpp_inputs"] = collect_request_capture(
                project_root=project,
                work_root=WORK,
                snapshot_destination=WORK / "lab-build/player-linker-inputs" / request_id / "bee",
                final_result=r,
                request_id=request_id,
                source_commit=source["commit"],
                input_id=capture_request["inputId"],
                editor_version=editor_version_from_toolchain(toolchain()),
            )
        symbols_start = time.monotonic()
        if android_symbols == "debugging":
            from symbol_artifacts import validate_fresh_symbol_package, verify_apk_symbol_pair

            expected_symbol_dir = WORK / "lab-build" / ("symbols-" + request_id)
            source_symbols = validate_fresh_symbol_package(r.get("symbolPackage"), expected_symbol_dir, request_id)
            symbols_zip = dest / "symbols.zip"
            copy_build_artifact(source_symbols, symbols_zip, verify=False)
            symbols_hash = sha(symbols_zip)
            libil2cpp_hash = sha256_file_member(apk, "lib/arm64-v8a/libil2cpp.so")
            pair = verify_apk_symbol_pair(
                apk, symbols_zip, expected_apk_sha256=sha(apk), expected_symbols_sha256=symbols_hash, expected_libil2cpp_sha256=libil2cpp_hash
            )
            r.update(
                {
                    "symbolPackage": str(symbols_zip),
                    "symbols_zip_cache_path": symbols_zip.name,
                    "symbols_zip_sha256": symbols_hash,
                    "libil2cpp_sha256": pair["libil2cpp_sha256"],
                    "libil2cpp_build_id": pair["libil2cpp_build_id"],
                    "symbol_sections": {"symtab": pair["symbols_has_symtab"], "debug_info": pair["symbols_has_debug_info"]},
                }
            )
        timing.phases["symbols_clone_hash_validation"] = time.monotonic() - symbols_start if android_symbols == "debugging" else 0.0
        payload = dest / "payload"
        with timing.phase("payload_clone_hash"):
            r["payload"] = {p.name: sha(p) for p in (WORK / "generated-android-data").glob("*") if p.is_file()}
            shutil.copytree(WORK / "generated-android-data", payload, dirs_exist_ok=True, copy_function=lambda a, b: copy_build_artifact(a, b, verify=False))
        from iteration_apk import write_anchor

        if not iteration_mode:
            with timing.phase("iteration_anchor"):
                write_anchor(WORK, project, r)
        r["timing"] = timing.report()
        write(receipt, r)
        write(WORK / "config/current-build.json", r)
        print(json.dumps(r, indent=2))
        return r
