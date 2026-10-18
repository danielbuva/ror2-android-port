from common import *
import re
import shutil
import time
import zipfile
import sys


def copy_build_artifact(source, destination):
    # Independent copy-on-write snapshots prevent repeated payloads exhausting host space.
    # Fall back to ordinary copies off APFS; artifact identity is always byte-checked.
    source = Path(source)
    destination = Path(destination)
    if not source.is_file() or source.is_symlink() or destination.is_symlink():
        raise RuntimeError("Build artifact paths must be regular files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cloned = sys.platform == "darwin" and run(["/bin/cp", "-c", "-p", source, destination], check=False).returncode == 0
    if not cloned:
        shutil.copy2(source, destination)
    source_stat = source.stat()
    destination_stat = destination.stat()
    if (source_stat.st_dev, source_stat.st_ino) == (destination_stat.st_dev, destination_stat.st_ino) or sha(source) != sha(destination):
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


def preflight():
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
    from device import Device

    storage = Device().storage()
    result = {
        "success": True,
        "input_id": inv["input_id"],
        "host_free_bytes": shutil.disk_usage(ROOT).free,
        "storage": storage,
        "scope": "lab build; does not certify full game or semantic patches",
    }
    write(WORK / "preflight.json", result)
    return result


def editor(target="lab", action="inspect"):
    if action == "open":
        project = (
            WORK / "lab-project"
            if target == "lab"
            else ROOT / "smoke"
            if target == "smoke"
            else ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
        )
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
        return json.dumps({"started": True, "pid": proc.pid, "log": str(log), "next": "Wait for import/MCP connection, then ./dev editor --target " + target})
    if action == "minimal-build":
        preflight()
    return run([ROOT / ".local/tools/unity-mcp/Server/.venv/bin/python", ROOT / "scripts/lab/editor.py", target, action], timeout=200).stdout.decode()


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


def validate_content_recipe():
    """Check public bundle selectors against work without writing it or rejecting local extras."""
    _validate_public_recipe("content.json", WORK / "scene-probe-build.json", "Content recipe", "work/scene-probe-build.json")


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


def validate_staged_runtime_sources(project):
    if not (WORK / "whole-catalog-build.json").exists():
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
    validate_content_recipe()


def build_cache_key(project, api):
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
    return digest(
        {"inputs": inputs, "external": external, "api": api, "editor": toolchain(), "backend": "IL2CPP-ARM64", "tool": sha(ROOT / "scripts/lab/build.py")}
    )


def stage_android_assets(project, io=None):
    """Place Android assets without starting Unity; the real copytree contract stays intact."""
    if io is None:
        shutil.copytree(ROOT / "android/Assets", project / "Assets", dirs_exist_ok=True)
    else:
        for source in sorted((ROOT / "android/Assets").rglob("*")):
            if source.is_file():
                io.apply(project / "Assets" / source.relative_to(ROOT / "android/Assets"), copy=source)


def build(api="gles", force=False, reuse_payload=False):
    if api not in ["gles", "vulkan", "lab"]:
        raise RuntimeError("Build target must be gles or vulkan")
    if api == "lab":
        api = "gles"
    preflight()
    project = WORK / "lab-project"
    recipe = WORK / "scene-probe-build.json"
    if recipe.exists():
        validate_runtime_support(project, read(recipe))
    validate_staged_runtime_sources(project)
    # Copy changed tool-owned sources only. Never reset project settings during an incremental build.
    stage_android_assets(project)
    if reuse_payload:
        validate_whole_payload_reuse(project)
    key = build_cache_key(project, api)
    dest = WORK / "build-cache" / key
    receipt = dest / "result.json"
    if receipt.exists() and not force:
        r = read(receipt)
        if r.get("success") and r.get("errors", 0) == 0 and Path(r["apk"]).exists() and sha(r["apk"]) == r["apk_sha256"]:
            for name, h in r.get("payload", {}).items():
                source = dest / "payload" / name
                if not source.is_file() or sha(source) != h:
                    raise RuntimeError("Cached payload is missing or changed: " + name)
                copy_build_artifact(source, WORK / "generated-android-data" / name)
            write(WORK / "config/current-build.json", r)
            print(json.dumps({"cached": True, **r}, indent=2))
            return r
    (WORK / "graphics-api.txt").write_text(api)
    result = WORK / "lab-build/result.json"
    if result.exists():
        result.rename(result.with_name("previous-" + now() + ".json"))
    request_id = now()
    write(WORK / "build-request.json", {"request_id": request_id, "api": api, "reusePayload": reuse_payload})
    print(editor("lab", "refresh"), flush=True)
    print(editor("lab", "build"), flush=True)
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
    if not r["success"] or r.get("errors", 0) > 0:
        raise RuntimeError(r["result"] + "; build errors=" + str(r.get("errors", 0)))
    key = build_cache_key(project, api)
    dest = WORK / "build-cache" / key
    receipt = dest / "result.json"
    dest.mkdir(parents=True, exist_ok=True)
    apk = dest / Path(r["apk"]).name
    copy_build_artifact(r["apk"], apk)
    r.update({"apk": str(apk), "apk_sha256": sha(apk), "key": key, "graphics_api": api, "input_id": read(WORK / "inventory/files.json")["input_id"]})
    payload = dest / "payload"
    shutil.copytree(WORK / "generated-android-data", payload, dirs_exist_ok=True, copy_function=copy_build_artifact)
    r["payload"] = {p.name: sha(p) for p in payload.glob("*") if p.is_file()}
    write(receipt, r)
    write(WORK / "config/current-build.json", r)
    print(json.dumps(r, indent=2))
    return r
