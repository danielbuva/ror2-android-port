"""Produce the complete managed provider cohort from original owner/tool inputs.

Composition of existing producers, not a runtime replacement or project importer.
Licensed Wwise declarations/native inputs and generic packages remain supplied.
"""

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import assembly_transforms  # noqa: E402
import body_visual_map  # noqa: E402
import catalog_reader  # noqa: E402
import common_assets_map  # noqa: E402
import original_game_audio_produce as audio  # noqa: E402
import owner_audio_prefab  # noqa: E402
import phone_unity_compile  # noqa: E402
import public_transform_tools  # noqa: E402
import wwise_bank_index  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


native = load(HERE / "native.py", "managed_native_support")
legacy = load(HERE / "legacy_init.py", "managed_legacy_init")
packages_owner = load(ROOT / "tools/phone-build/package-assemblies/produce.py", "managed_package_owner")
PROFILE = ROOT / "recipe/owner-managed-code.json"
PROFILE_SHA = "585c11e0626ad1e7326c2b1d7f5b67e5ec2c02cd55a0e34a59fcb24651f3e5b0"
INPUT_FIELDS = {
    "packages",
    "netstandard_ref",
    "newtonsoft",
    "dotnet",
    "ilspy_dll",
    "decoder",
    "wwise_android_source",
    "wwise_os_string_source",
    "wwise_abi_native",
    "wwise_native",
}


def invoke(argv, output, label, *, env=None, separate_stderr=False):
    environment = env if env is not None else dict(os.environ, TMPDIR=str(output / "tmp")) if sys.platform == "android" else None
    native.invoke([str(v) for v in argv], output, label, env=environment, separate_stderr=separate_stderr or sys.platform == "android")
    return output / "logs" / (label + ".log")


def bind_paths(values):
    if set(values) != INPUT_FIELDS:
        raise ValueError("explicit package, compiler, decompiler, decoder and licensed Wwise inputs required")
    paths = {k: native.canonical(v) for k, v in values.items()}
    if any(not paths[k].is_dir() for k in ("packages", "netstandard_ref")) or any(
        not p.is_file() for k, p in paths.items() if k not in {"packages", "netstandard_ref"}
    ):
        raise ValueError("invalid source/tool provider kind")
    return paths


def base_providers(profile, sdk, game):
    result = {}
    for name, row in profile["base_providers"].items():
        if native.relative(name).name != name or row["provider"] not in {"sdk", "original"}:
            raise ValueError("invalid managed base provider identity")
        root = sdk if row["provider"] == "sdk" else game
        path = native.canonical(root / native.relative(row["relative"]))
        if not path.is_relative_to(root) or native.sha(path) != row["sha256"]:
            raise ValueError("base provider drift: " + name)
        result[name] = path
    return result


def source_hashes(paths):
    return {str(p): native.sha(p) for p in paths}


def unchanged(bound):
    if any(native.sha(Path(p)) != digest for p, digest in bound.items()):
        raise ValueError("managed producer input/source drift")


def maps_and_support(out, inputs, managed, probe, profile, identity, *, work=None, source_root=ROOT, probe_provider_sha256=None):
    dotnet, ilspy = inputs["dotnet"], inputs["ilspy_dll"]
    version = invoke([dotnet, ilspy, "--disable-updatecheck", "--version"], out, "ilspy-version").read_text()
    if profile["ilspy_version"] not in version:
        raise ValueError("qualified source decompiler version differs")
    for name, assembly in (("support-original", "Assembly-CSharp.dll"), ("maps-original", "RoR2.dll")):
        invoke([dotnet, ilspy, "--disable-updatecheck", "-lv", "CSharp9_0", "-p", "-r", managed, "-o", out / name, managed / assembly], out, name)
    probe_env = dict(os.environ, ROR2LAB_CECIL_SHA256=probe_provider_sha256) if probe_provider_sha256 else None

    def query(arguments, label):
        return json.loads(invoke([dotnet, probe, *arguments], out, label, env=probe_env, separate_stderr=bool(probe_env)).read_text())

    contract = query(["--catalog-contract", managed / "RoR2.dll"], "catalog-contract")
    if contract["input_sha256"] != native.sha(managed / "RoR2.dll") or contract["legacyInputSha256"] != native.sha(managed / "LegacyResourcesAPI.dll"):
        raise ValueError("original catalog identity contract drift")
    names = query(["--catalog-names", managed / "RoR2.dll", *contract["providers"]], "catalog-names")
    catalog_path = managed.parent / "StreamingAssets/aa/catalog.json"
    inventory = json.loads(((work or ROOT / "work") / "inventory/files.json").read_text())
    expected = {r["path"]: r["sha256"] for r in inventory["files"]}
    if native.sha(catalog_path) != expected[catalog_path.relative_to(managed.parent.parent).as_posix()]:
        raise ValueError("original catalog differs from accepted inventory")
    catalog = catalog_reader.read_shipped(catalog_path, "/_/owner-original-aa", names)
    native.write(out / "original-catalog.json", catalog)
    manifest = {"keys": catalog["keys"]}
    recipes = json.loads((source_root / "recipe/build-entry-inputs.json").read_text())["decompiled"]
    if native.sha(managed / recipes["assembly"]) != recipes["assembly_sha256"]:
        raise ValueError("map source assembly differs")
    generated = out / "maps"
    generated.mkdir()
    for name, row in recipes["files"].items():
        source = out / "maps-original" / native.relative(row["path"])
        if native.sha(source) != row["sha256"]:
            raise ValueError("original map source decompilation differs: " + name)
        target = (
            generated
            / {
                "CharacterBody.cs": "OriginalBodyVisualMap.cs",
                "HealthComponent.cs": "OriginalHealthVisualMap.cs",
                "GlobalEventManager.cs": "OriginalGlobalCommonAssetMap.cs",
            }[name]
        )
        if name == "GlobalEventManager.cs":
            common_assets_map.generate(source, target, identity, contract["legacyAliases"], manifest, {"groundOnHitPrefab", "hollowPack"})
        else:
            body_visual_map.generate(source, target, identity, contract["legacyAliases"], manifest)
    selected = out / "support"
    selected.mkdir()
    for relative in profile["support_sources"]:
        matches = list((out / "support-original").rglob(Path(relative).name))
        if len(matches) != 1:
            raise ValueError("ambiguous or absent original support source: " + relative)
        target = selected / native.relative(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.name == "AffixBeadProjectileSound.cs":
            fields = query([managed / "Assembly-CSharp.dll", "AffixBeadProjectileSound"], "support-field-contract")["types"][0]["fields"]
            if {r["name"]: r["type"] for r in fields} != {"SpawnBeadChaseEvent": "AK.Wwise.Event", "ExplodeEvent": "AK.Wwise.Event"}:
                raise ValueError("original sound field contract differs")
            target.write_text("using Event = AK.Wwise.Event;\n" + matches[0].read_text())
        else:
            shutil.copyfile(matches[0], target)
    return sorted(generated.glob("*.cs")), [selected / n for n in profile["support_sources"]]


def audio_assemblies(out, sdk, work, inputs, raw, ordinary, staged, prefab, bank, init, managed_paths, manifest):
    destination = out / "audio"
    destination.mkdir()
    generated = destination / "generated"
    generated.mkdir()
    # This is the existing qualified diagnostic target configuration, not a new runtime selection.
    request_id = native.sha(PROFILE)[:32]
    request, contract = audio.generate_request_contract(
        destination,
        generated,
        request_id,
        manifest,
        managed_paths,
        inputs["wwise_native"],
        staged / "stage-receipt.json",
        staged,
        prefab,
        bank,
        init / "Init.bnk",
        init / "receipt.json",
        True,
        True,
        False,
    )
    stage_pin = audio.load_module(audio.TOOLS / "generate_runtime_stage_pin.py", "source_owner_stage_pin")
    request_pin = audio.load_module(audio.TOOLS / "generate_accepted_request_pin.py", "source_owner_request_pin")
    if (
        native.sha(audio.TOOLS / "generate_runtime_stage_pin.py") != audio.STAGE_PIN_TOOL_SHA256
        or native.sha(audio.TOOLS / "generate_accepted_request_pin.py") != audio.REQUEST_PIN_TOOL_SHA256
    ):
        raise ValueError("existing runtime request/stage generator drift")
    stage_source, request_source = generated / "GameAudioOriginalGeneratedStagePin.cs", generated / "GameAudioOriginalGeneratedRequestPin.cs"
    stage_pin.generate(staged / "stage-receipt.json", staged, stage_source, prefab, bank, init / "Init.bnk", init / "receipt.json")
    request_pin.emit(request, contract, staged / "stage-receipt.json", request_source)
    contents = sdk / "Unity.app/Contents"
    mono, csc = contents / "MonoBleedingEdge/bin/mono", contents / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    named = {Path(k).name: p for k, p in managed_paths.items()}
    plugin_refs = {
        "AK.Wwise.Unity.MonoBehaviour.dll": ordinary["AK.Wwise.Unity.MonoBehaviour.dll"],
        "AK.Wwise.Unity.API.dll": named["api-adapted.dll"],
        "RoR2.dll": named["game-optional-presentation-guarded.dll"],
    }
    absent = destination / "NO_PROJECT"
    if absent.exists():
        raise ValueError("standalone owner must not admit a project")
    core_options, core_refs = audio.unity_reference_options(contents, absent, plugin_refs)
    bootstrap_refs = {
        **plugin_refs,
        "AK.Wwise.Unity.API.dll": named["api-instrumented-composed.dll"],
        "RoR2.dll": named["game-original-owner-point-sound-composed.dll"],
    }
    bootstrap_options, refs = audio.unity_reference_options(contents, absent, bootstrap_refs)
    bound = source_hashes([*core_refs, *refs, mono, csc, *[audio.SOURCE / k for k in audio.OWNER_SOURCE_HASHES]])
    observer, core, bootstrap = [
        destination / (name + ".dll") for name in ("OriginalOwnerProbeObserver", "GameAudioOriginalCore", "GameAudioOriginalBootstrap")
    ]
    audio.compile_observer(mono, csc, observer, destination / "observer.log")
    point = destination / "GameAudioOriginalPointSoundBuildPin.cs"
    point.write_text(
        "// Requested artifact: the paired RoR2.dll contains the bounded diagnostic callsites.\ninternal static class GameAudioOriginalPointSoundBuildPin { internal const bool DiagnosticCallsitesPresent = true; }\n"
    )
    core_sources = [
        audio.SOURCE / ("core/" + n + ".cs")
        for n in ("GameAudioOriginalReadiness", "GameAudioOriginalPassivePcmContract", "GameAudioOriginalOwner", "PointSoundDiagnosticObserver")
    ] + [point]
    audio.compile_library("compile_core", mono, csc, core, core_sources, core_options, [observer], destination)
    bootstrap_sources = [
        p
        for p in sorted((audio.SOURCE / "bootstrap").glob("*.cs"))
        if p.name not in {"GameAudioOriginalGeneratedRequestPin.cs", "GameAudioOriginalGeneratedStagePin.cs"}
    ] + [request_source, stage_source]
    audio.compile_library(
        "compile_bootstrap", mono, csc, bootstrap, bootstrap_sources, bootstrap_options, [core, bootstrap_refs["AK.Wwise.Unity.API.dll"], observer], destination
    )
    unchanged(bound)
    return {p.name: p for p in (observer, core, bootstrap)}


def gameplay(out, sdk, inputs, original, ordinary, raw, package_output, audio_outputs, maps, support, *, source_root=None, android_tools=None):
    destination = out / "gameplay"
    destination.mkdir()
    if source_root:
        names = json.loads((source_root / "recipe/runtime-sources.json").read_text())
    else:
        import build

        names = build.runtime_sources()
    authored = source_root or ROOT
    public = [authored / "tools/unity" / native.relative(n) for n in names] + [authored / "android/Assets/LabDiagnostics.cs"]
    sources = public + support + maps
    if (source_root is None and len(public) != 128) or len(support) != 14 or len(maps) != 3:
        raise ValueError("current player source membership changed; review configuration")
    refs = {Path(p).name: sdk / p for p in phone_unity_compile.references(sdk)}
    plugins = {}
    transformed = {n: h for step in assembly_transforms.load_recipe()["steps"] for n, h in step["outputs"].items()}
    for row in json.loads((ROOT / "recipe/original-assemblies.json").read_text())["assemblies"]:
        name = row["source"]
        source = ordinary[name] if name in transformed else original / name
        if native.sha(source) != transformed.get(name, row["sha256"]):
            raise ValueError("original player reference drift: " + name)
        plugins[name] = source
    if raw is not None:
        plugins.update({"AK.Wwise.Unity.API.dll": raw / "api-instrumented-composed.dll", "RoR2.dll": raw / "game-original-owner-point-sound-composed.dll"})
    for row in json.loads((package_output / "result.json").read_text())["packages"]:
        path = package_output / "postprocessed" / (row["name"] + ".dll")
        if native.sha(path) != row["sha256"]:
            raise ValueError("fresh package changed")
        plugins[path.name] = path
    plugins.update(audio_outputs)
    plugins["Newtonsoft.Json.dll"] = inputs["newtonsoft"]
    refs.update(plugins)
    defines = packages_owner.symbols("2021.3.45f2", {}, {})
    for source in sources:
        for line in re.findall(r"^\s*#(?:if|elif).*", source.read_text(), re.M):
            if set(re.findall(r"[A-Z_][A-Z_0-9]*", line)) - {"UNITY_ANDROID", "UNITY_EDITOR"}:
                raise ValueError("unqualified player source conditional")
    bound = source_hashes([*sources, *refs.values()])
    native.write(destination / "inputs.json", {"sources": source_hashes(sources), "references": source_hashes(refs.values()), "defines": defines})
    contents = sdk / "Unity.app/Contents"
    options = (
        ["-nostdlib", "-noconfig", "-langversion:9", "-unsafe+", "-optimize-", "-debug:portable"]
        + ["-define:" + v for v in defines]
        + ["-r:" + str(p) for p in refs.values()]
    )
    assembly = destination / "Assembly-CSharp.dll"
    audio.compile_library(
        "compile_gameplay",
        Path(android_tools["dotnet"]) if android_tools else contents / "NetCoreRuntime/dotnet",
        contents / "DotNetSdkRoslyn/csc.dll",
        assembly,
        sources,
        options,
        [],
        destination,
    )
    post = destination / "postprocessed"
    post.mkdir()
    (destination / "tmp").mkdir()
    references = list(refs.values()) + [
        inputs["packages"] / "com.unity.collections@1.2.4/Unity.Collections.LowLevel.ILSupport/Unity.Collections.LowLevel.ILSupport.dll",
        inputs["packages"] / "com.unity.burst@1.8.11/Unity.Burst.Unsafe.dll",
    ]
    processor = package_output / "compiled/Unity.Burst.CodeGen.dll"
    bound.update(source_hashes([*references, processor, assembly]))
    args = ["-assembly", str(assembly), "-outputDir", str(post), "-processors", str(processor)]
    for path in references:
        args += ["-assemblyReferences", str(path)]
    for define in defines:
        args += ["-defines", define]
    folders = {p.parent for p in references} | {
        contents / "Managed",
        contents / "Tools/ILPostProcessorRunner",
        inputs["packages"] / "com.unity.burst@1.8.11/Unity.Burst.CodeGen",
    }
    for path in sorted(folders):
        args += ["-assemblyFolders", str(path)]
    rsp = destination / "generated-ilpp.rsp"
    rsp.write_text(" ".join(json.dumps(v) for v in args) + "\n")
    processor = contents / "Tools/ILPostProcessorRunner/ILPostProcessorRunner.exe"
    command = (
        [android_tools["dotnet"], "exec", "--runtimeconfig", package_output / "android.runtimeconfig.json", processor]
        if android_tools
        else [contents / "Tools/netcorerun/netcorerun", processor]
    )
    packages_owner.invoke(
        command + ["@" + str(rsp)],
        "gameplay.postprocess",
        destination,
    )
    unchanged(bound)
    return post / "Assembly-CSharp.dll"


def target_run(work, sdk, values, target, source_root, output, *, android_tools=None):
    """Produce the pre-audio accepted target from its pinned authored sources."""
    if set(values) != {"packages", "newtonsoft", "dotnet", "ilspy_dll", "archives"}:
        raise ValueError("target source inputs require packages, Newtonsoft, runtime, ILSpy and public archives")
    inputs = {k: native.canonical(v) for k, v in values.items()}
    state = native.input_state(work)
    profile = json.loads(PROFILE.read_text())
    if native.sha(PROFILE) != PROFILE_SHA or state[0] != profile["input_id"] or native.sha(inputs["newtonsoft"]) != profile["newtonsoft_sha256"]:
        raise ValueError("target managed input/profile drift")
    native.disjoint(output, [sdk, state[1], work / "config", work / "inventory", source_root, *inputs.values()])
    base = base_providers(profile, sdk, state[1])
    authored = {str(source_root / native.relative(n)): h for n, h in target["source_files"].items()}
    unchanged(authored)
    bound = (
        source_hashes([*base.values(), inputs["newtonsoft"], inputs["dotnet"], *[p for p in inputs["ilspy_dll"].parent.rglob("*") if p.is_file()]]) | authored
    )
    output.mkdir(mode=0o700)
    result = {"success": False, "phase": "public-transforms", "source_commit": target["source_commit"], "phone_qualified": False, "runtime_qualified": False}
    try:
        for name in ("logs", "tmp", "ordinary"):
            (output / name).mkdir()
        # Use the existing public compiler/Cecil producer, including all golden gates.
        runtime_env = {name: os.environ.get(name) for name in ("ROR2LAB_BUILD_DOTNET_ROOT", "ROR2LAB_BUILD_HOSTFXR")}
        try:
            if android_tools:
                # The audited public-tool profile enumerates exactly .NET 8.
                # ILSpy separately needs .NET 10; keep both installed while
                # exposing only the original framework to this producer.
                framework = Path(runtime_env["ROR2LAB_BUILD_DOTNET_ROOT"]) / "shared/Microsoft.NETCore.App/8.0.32"
                isolated = output / "public-dotnet"
                (isolated / "shared/Microsoft.NETCore.App").mkdir(parents=True)
                (isolated / "shared/Microsoft.NETCore.App/8.0.32").symlink_to(framework, target_is_directory=True)
                os.environ["ROR2LAB_BUILD_DOTNET_ROOT"] = str(isolated)
                os.environ["ROR2LAB_BUILD_HOSTFXR"] = str(inputs["dotnet"].parent / "libhostfxr.so")
            ordinary = public_transform_tools.generate(
                state[1] / "Risk of Rain 2_Data/Managed",
                output / "ordinary",
                assembly_transforms.load_recipe(),
                archives=inputs["archives"],
                launcher=inputs["dotnet"],
                host="android8" if android_tools else "host10",
            )
        finally:
            for name, value in runtime_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        result["phase"] = "packages"
        packages = output / "packages"
        package_request = {"sdk_install": str(sdk), "packages": str(inputs["packages"]), "output": str(packages)}
        if android_tools:
            package_request["android_tools"] = android_tools
        packages_owner.run(package_request)
        result["phase"] = "original-support-and-maps"
        maps, support = maps_and_support(
            output,
            inputs,
            state[1] / "Risk of Rain 2_Data/Managed",
            output / "ordinary/tool/AssemblyProbe.dll",
            profile,
            state[0],
            work=work,
            source_root=source_root,
            probe_provider_sha256=json.loads((output / "ordinary/public-tools-receipt.json").read_text())["provider_sha256"],
        )
        result["phase"] = "gameplay"
        game = gameplay(
            output,
            sdk,
            inputs,
            state[1] / "Risk of Rain 2_Data/Managed",
            ordinary,
            None,
            packages,
            {},
            maps,
            support,
            source_root=source_root,
            android_tools=android_tools,
        )
        produced = ordinary | {"Assembly-CSharp.dll": game, "Newtonsoft.Json.dll": inputs["newtonsoft"]}
        produced.update({p.name: p for p in (packages / "postprocessed").glob("*.dll")})
        providers = {n: {"path": str(p), "sha256": native.sha(p)} for n, p in (base | produced).items()}
        if set(providers) != set(target["player"]["managed_assemblies"]):
            raise ValueError("target managed membership differs")
        unchanged(bound)
        if native.input_state(work) != state:
            raise ValueError("target original inputs changed")
        native.write(output / "providers.json", providers)
        result.update(success=True, phase="managed-produced", managed_providers=len(providers), authored_sources=len(target["source_files"]))
        return providers
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        native.write(output / "result.json", result)


def run(work, sdk, values, output):
    work, sdk = native.canonical(work), native.canonical(sdk)
    output = Path(output)
    if work != ROOT / "work":
        raise ValueError("source owner currently requires this checkout's work root")
    state = native.input_state(work)
    if native.sha(PROFILE) != PROFILE_SHA:
        raise ValueError("audited managed profile drift")
    profile = json.loads(PROFILE.read_text())
    if state[0] != profile["input_id"]:
        raise ValueError("unsupported legitimate source input")
    inputs = bind_paths(values)
    if (
        native.sha(inputs["newtonsoft"]) != profile["newtonsoft_sha256"]
        or native.sha(inputs["decoder"]) != profile["decoder_sha256"]
        or native.sha(inputs["wwise_native"]) != audio.LINEAGE["native_library_sha256"]
    ):
        raise ValueError("qualified generic package/decoder/licensed native input differs")
    native.disjoint(output, [sdk, state[1], work / "config", work / "inventory", *inputs.values()])
    if not output.is_relative_to(work) or output == work:
        raise ValueError("new managed output must be inside owner work")
    base = base_providers(profile, sdk, state[1])
    reference_files = sorted(p for p in inputs["netstandard_ref"].rglob("*") if p.is_file())
    if not reference_files or any(p.resolve() != p for p in reference_files):
        raise ValueError("empty or redirected NETStandard reference package")
    bound = source_hashes(
        [*[p for k, p in inputs.items() if k not in {"packages", "netstandard_ref"}], *reference_files, *base.values(), PROFILE, Path(__file__)]
    )
    output.mkdir(mode=0o700)
    result = {
        "schema": 1,
        "success": False,
        "phase": "raw-managed",
        "input_id": state[0],
        "profile_sha256": PROFILE_SHA,
        "source_sha256": native.sha(Path(__file__)),
        "editor_or_project_used": False,
        "phone_qualified": False,
        "runtime_qualified": False,
        "licensed_native_independently_produced": False,
    }
    try:
        for name in ("logs", "tmp"):
            (output / name).mkdir()
        native.write(output / "inputs.json", {"explicit": {k: str(p) for k, p in inputs.items()}, "hashes": bound})
        raw = output / "raw"
        invoke(
            [
                sys.executable,
                "-I",
                ROOT / "tools/unity/support/audio/managed-producer/produce.py",
                "--android-source",
                inputs["wwise_android_source"],
                "--android-os-string-source",
                inputs["wwise_os_string_source"],
                "--native-so",
                inputs["wwise_abi_native"],
                "--llvm-nm",
                sdk / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm",
                "--unity-editor",
                sdk / "Unity.app/Contents/MacOS/Unity",
                "--dotnet",
                inputs["dotnet"],
                "--netstandard-ref",
                inputs["netstandard_ref"],
                "--output-dir",
                raw,
            ],
            output,
            "raw-managed",
        )
        manifest = json.loads((raw / "manifest.json").read_text())
        managed_paths = audio.verify_managed_output_manifest(manifest, work)
        result["phase"] = "packages-and-transforms"
        package_output = output / "packages"
        packages_owner.run({"sdk_install": str(sdk), "packages": str(inputs["packages"]), "output": str(package_output)})
        ordinary_dir = output / "ordinary"
        ordinary_dir.mkdir()
        ordinary = assembly_transforms.generate(
            state[1] / "Risk of Rain 2_Data/Managed",
            ordinary_dir,
            assembly_transforms.load_recipe(),
            dotnet=inputs["dotnet"],
            unity_editor=sdk / "Unity.app/Contents/MacOS/Unity",
        )
        unchanged(bound)
        if native.input_state(work) != state:
            raise ValueError("owner source state changed")
        result["phase"] = "source-audio-inputs"
        bank_dir, prefab_dir, init_dir = [output / n for n in ("bank-index", "prefab", "init")]
        wwise_bank_index.owner_index(work, bank_dir, True, decoder_executable=inputs["decoder"])
        owner_audio_prefab.reconstruct(work, prefab_dir)
        legacy.run(work, init_dir)
        prefab, bank = prefab_dir / "WwiseGlobal.prefab", bank_dir / "bank-index.json"
        staged = output / "staged"
        invoke(
            [
                sys.executable,
                ROOT / "tools/unity/support/audio/generators/stage_original_game_banks.py",
                "--prefab",
                prefab,
                "--bank-index",
                bank,
                "--soundbanks-info",
                state[1] / "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/SoundbanksInfo.xml",
                "--adapted-init",
                init_dir / "Init.bnk",
                "--init-receipt",
                init_dir / "receipt.json",
                "--output-dir",
                staged,
            ],
            output,
            "stage-audio",
        )
        result["phase"] = "audio-assemblies"
        audio.validate_owner_source_manifest()
        supplied = output / "supplied-sdk"
        supplied.mkdir()
        native_copy = supplied / "libAkSoundEngine.so"
        shutil.copyfile(inputs["wwise_native"], native_copy)
        if native.sha(native_copy) != audio.LINEAGE["native_library_sha256"]:
            raise ValueError("supplied licensed native copy differs")
        audio_outputs = audio_assemblies(
            output, sdk, work, inputs | {"wwise_native": native_copy}, raw, ordinary, staged, prefab, bank, init_dir, managed_paths, manifest
        )
        unchanged(bound)
        result["phase"] = "original-sources-and-maps"
        maps, support = maps_and_support(output, inputs, state[1] / "Risk of Rain 2_Data/Managed", ordinary_dir / "tool/AssemblyProbe.dll", profile, state[0])
        result["phase"] = "gameplay-assembly"
        game = gameplay(output, sdk, inputs, state[1] / "Risk of Rain 2_Data/Managed", ordinary, raw, package_output, audio_outputs, maps, support)
        produced = {
            "AK.Wwise.Unity.API.dll": raw / "api-instrumented-composed.dll",
            "AK.Wwise.Unity.MonoBehaviour.dll": ordinary["AK.Wwise.Unity.MonoBehaviour.dll"],
            "RoR2.dll": raw / "game-original-owner-point-sound-composed.dll",
            "Assembly-CSharp.dll": game,
            "Newtonsoft.Json.dll": inputs["newtonsoft"],
            **audio_outputs,
        }
        produced.update({p.name: p for p in (package_output / "postprocessed").glob("*.dll")})
        if set(produced) != set(profile["produced_assemblies"]):
            raise ValueError("complete produced provider membership differs")
        unchanged(bound)
        if native.input_state(work) != state or base_providers(profile, sdk, state[1]) != base:
            raise ValueError("owner managed inputs changed")
        all_providers = base | produced
        provider_rows = {n: {"path": str(p), "sha256": native.sha(p)} for n, p in all_providers.items()}
        native.write(output / "providers.json", provider_rows)
        result.update(
            success=True,
            phase="managed-produced",
            original_or_sdk_providers=len(base),
            produced_providers=len(produced),
            complete_providers=len(provider_rows),
            providers_sha256=native.sha(output / "providers.json"),
        )
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        native.write(output / "result.json", result)
    return provider_rows
