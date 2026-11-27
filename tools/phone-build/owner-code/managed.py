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
from phone_sdk_compiler import SdkCompiler, python_command  # noqa: E402
import public_transform_tools  # noqa: E402
import wwise_bank_index  # noqa: E402
import wwise_init_platform  # noqa: E402


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


def bind_paths(values, *, signed_audio=False):
    required = INPUT_FIELDS - {"decoder"} if signed_audio else INPUT_FIELDS
    if set(values) not in (required, INPUT_FIELDS):
        raise ValueError("explicit package, compiler, decompiler and licensed Wwise inputs required (decoder for historical staging)")
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


def maps_and_support(out, inputs, managed, probe, profile, identity, *, work=None, source_root=ROOT, probe_provider_sha256=None, android_tools=None):
    dotnet, ilspy = inputs["dotnet"], inputs["ilspy_dll"]
    decompiler_env = None
    if android_tools:
        (framework,) = Path(os.environ["ROR2LAB_BUILD_DOTNET_ROOT"]).glob("shared/Microsoft.NETCore.App/10.*")
        libraries = os.pathsep.join(filter(None, (str(framework), os.environ.get("LD_LIBRARY_PATH"))))
        decompiler_env = dict(os.environ, LD_LIBRARY_PATH=libraries, TMPDIR=str(out / "tmp"))
    version = invoke([dotnet, ilspy, "--disable-updatecheck", "--version"], out, "ilspy-version", env=decompiler_env).read_text()
    if profile["ilspy_version"] not in version:
        raise ValueError("qualified source decompiler version differs")
    decompile = [dotnet, ilspy, "--disable-updatecheck", "-lv", "CSharp9_0", "-r", managed]
    recipes = json.loads((source_root / "recipe/build-entry-inputs.json").read_text())["decompiled"]
    map_assembly = managed / recipes["assembly"]
    if native.sha(map_assembly) != recipes["assembly_sha256"]:
        raise ValueError("map source assembly differs")
    invoke([*decompile, "-p", "-o", out / "support-original", managed / "Assembly-CSharp.dll"], out, "support-original", env=decompiler_env)
    probe_env = decompiler_env
    if probe_provider_sha256:
        probe_env = dict(probe_env or os.environ, ROR2LAB_CECIL_SHA256=probe_provider_sha256)

    def query(arguments, label):
        return json.loads(invoke([dotnet, probe, *arguments], out, label, env=probe_env, separate_stderr=bool(probe_env)).read_text())

    contract = query(["--catalog-contract", managed / "RoR2.dll"], "catalog-contract")
    if contract["input_sha256"] != native.sha(managed / "RoR2.dll") or contract["legacyInputSha256"] != native.sha(managed / "LegacyResourcesAPI.dll"):
        raise ValueError("original catalog identity contract drift")
    names = query(["--catalog-names", managed / "RoR2.dll", *contract["providers"]], "catalog-names")
    catalog_path = managed.parent / "StreamingAssets/aa/catalog.json"
    inventory = json.loads(((work or ROOT / "work") / "inventory/files.json").read_text())
    expected = {r["path"]: r["sha256"] for r in inventory["files"]}
    catalog_sha = native.sha(catalog_path)
    if catalog_sha != expected[catalog_path.relative_to(managed.parent.parent).as_posix()]:
        raise ValueError("original catalog differs from accepted inventory")
    catalog = catalog_reader.read_shipped(catalog_path, "/_/owner-original-aa", names)
    native.write(out / "original-catalog.json", dict(catalog, input_id=identity, source_catalog_sha256=catalog_sha))
    manifest = {"keys": catalog["keys"]}
    generated = out / "maps"
    generated.mkdir()
    map_sources = out / "maps-original"
    map_sources.mkdir()
    for name, row in recipes["files"].items():
        relative = native.relative(row["path"])
        type_name = ".".join(relative.with_suffix("").parts)
        invoke([*decompile, "-t", type_name, "-o", map_sources, map_assembly], out, "maps-original-" + type_name, env=decompiler_env)
        source = map_sources / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        (map_sources / (type_name + ".decompiled.cs")).rename(source)
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


def stage_source_audio(work, game, output, *, decoder=None):
    bank_dir, prefab_dir, init_dir = [output / name for name in ("bank-index", "prefab", "init")]
    wwise_bank_index.owner_index(work, bank_dir, decoder is not None, decoder_executable=decoder)
    owner_audio_prefab.reconstruct(work, prefab_dir)
    if decoder is None:
        init_dir.mkdir()
        wwise_init_platform.produce_owner(work, game, init_dir)
    else:
        legacy.run(work, init_dir)
    prefab, bank = prefab_dir / "WwiseGlobal.prefab", bank_dir / "bank-index.json"
    staged = output / "staged"
    soundbanks_info = game / "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/SoundbanksInfo.xml"
    invoke(
        [
            *python_command(audio.TOOLS / "stage_original_game_banks.py"),
            "--prefab",
            prefab,
            "--bank-index",
            bank,
            "--soundbanks-info",
            soundbanks_info,
            "--adapted-init",
            init_dir / "Init.bnk",
            "--init-receipt",
            init_dir / "receipt.json",
            "--output-dir",
            staged,
            *(["--owner-work", work] if decoder is None else []),
        ],
        output,
        "stage-audio",
    )
    return staged, prefab, bank, init_dir


def audio_assemblies(
    out, sdk, inputs, ordinary, staged, prefab, bank, init, managed_paths, manifest, *, owner_work=None, sdk_compiler=None, pcm_after_skill=False
):
    destination = out / "audio"
    destination.mkdir()
    generated = destination / "generated"
    generated.mkdir()
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
        passive_pcm_capture_requested=True,
        passive_pcm_capture_music_output_requested=not pcm_after_skill,
        passive_pcm_capture_after_authority_skill_requested=pcm_after_skill,
        owner_work=owner_work,
    )
    stage_pin = audio.load_module(audio.TOOLS / "generate_runtime_stage_pin.py", "source_owner_stage_pin")
    request_pin = audio.load_module(audio.TOOLS / "generate_accepted_request_pin.py", "source_owner_request_pin")
    if (
        native.sha(audio.TOOLS / "generate_runtime_stage_pin.py") != audio.STAGE_PIN_TOOL_SHA256
        or native.sha(audio.TOOLS / "generate_accepted_request_pin.py") != audio.REQUEST_PIN_TOOL_SHA256
    ):
        raise ValueError("existing runtime request/stage generator drift")
    stage_source, request_source = generated / "GameAudioOriginalGeneratedStagePin.cs", generated / "GameAudioOriginalGeneratedRequestPin.cs"
    stage_pin.generate(staged / "stage-receipt.json", staged, stage_source, prefab, bank, init / "Init.bnk", init / "receipt.json", owner_work=owner_work)
    request_pin.emit(request, contract, staged / "stage-receipt.json", request_source, owner_work=owner_work)
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
    bootstrap_refs = {
        **plugin_refs,
        "AK.Wwise.Unity.API.dll": named["api-instrumented-composed.dll"],
        "RoR2.dll": named["game-original-owner-point-sound-composed.dll"],
    }
    if sdk_compiler:
        sdk_refs = [sdk / path for path in phone_unity_compile.references(sdk)]
        core_refs, refs = [*sdk_refs, *plugin_refs.values()], [*sdk_refs, *bootstrap_refs.values()]
        tools = [sdk_compiler.launcher, *sdk_compiler.inputs]
    else:
        core_options, core_refs = audio.unity_reference_options(contents, absent, plugin_refs)
        bootstrap_options, refs = audio.unity_reference_options(contents, absent, bootstrap_refs)
        tools = [mono, csc]
    bound = source_hashes([*core_refs, *refs, *tools, *[audio.SOURCE / k for k in audio.OWNER_SOURCE_HASHES]])
    observer, core, bootstrap = [
        destination / (name + ".dll") for name in ("OriginalOwnerProbeObserver", "GameAudioOriginalCore", "GameAudioOriginalBootstrap")
    ]
    point = destination / "GameAudioOriginalPointSoundBuildPin.cs"
    point.write_text(
        "// Requested artifact: the paired RoR2.dll contains the bounded diagnostic callsites.\ninternal static class GameAudioOriginalPointSoundBuildPin { internal const bool DiagnosticCallsitesPresent = true; }\n"
    )
    core_sources = [
        audio.SOURCE / ("core/" + n + ".cs")
        for n in ("GameAudioOriginalReadiness", "GameAudioOriginalPassivePcmContract", "GameAudioOriginalOwner", "PointSoundDiagnosticObserver")
    ] + [point]
    bootstrap_sources = [
        p
        for p in sorted((audio.SOURCE / "bootstrap").glob("*.cs"))
        if p.name not in {"GameAudioOriginalGeneratedRequestPin.cs", "GameAudioOriginalGeneratedStagePin.cs"}
    ] + [request_source, stage_source]
    if sdk_compiler:
        options = ["-target:library", "-langversion:9", "-define:UNITY_ANDROID"]
        env = dict(os.environ, TMPDIR=str(out / "tmp"))
        sdk_compiler.compile(observer, [audio.SOURCE / "core/OriginalOwnerProbeObserver.cs"], [sdk_compiler.corelib], options, env=env)
        sdk_compiler.compile(core, core_sources, [*core_refs, observer], options, env=env)
        sdk_compiler.compile(bootstrap, bootstrap_sources, [*refs, core, observer], options, env=env)
        sdk_compiler.verify()
    else:
        audio.compile_observer(mono, csc, observer, destination / "observer.log")
        audio.compile_library("compile_core", mono, csc, core, core_sources, core_options, [observer], destination)
        audio.compile_library(
            "compile_bootstrap",
            mono,
            csc,
            bootstrap,
            bootstrap_sources,
            bootstrap_options,
            [core, bootstrap_refs["AK.Wwise.Unity.API.dll"], observer],
            destination,
        )
    unchanged(bound)
    return {p.name: p for p in (observer, core, bootstrap)}


def postprocessor_references(references, directory):
    """Expose only selected providers, not conflicting siblings in their roots."""
    directory.mkdir()
    result = []
    for source in references:
        path = directory / source.name
        path.symlink_to(source)
        result.append(path)
    return result


def target_source_order(public, support, maps):
    """Match the target's flat Assets/LabLoadingScene and Scripts trees."""
    return [public[-1], *sorted(public[:-1] + maps, key=lambda path: path.name.casefold()), *support]


def gameplay(out, sdk, inputs, original, ordinary, package_output, audio_outputs, maps, support, *, source_root=None, android_tools=None, sdk_compiler=None):
    destination = out / "gameplay"
    destination.mkdir()
    if source_root:
        names = json.loads((source_root / "recipe/runtime-sources.json").read_text())
    else:
        import build

        names = build.runtime_sources()
    authored = source_root or ROOT
    public = [authored / "tools/unity" / native.relative(n) for n in names] + [authored / "android/Assets/LabDiagnostics.cs"]
    sources = target_source_order(public, support, maps) if source_root else public + support + maps
    # runtime_sources validates the current authored manifest, including missing
    # files and staging collisions. A historical count rejects new port releases.
    if len(support) != 14 or len(maps) != 3:
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
    options = ["-langversion:9", "-unsafe+", "-optimize-", "-debug:portable", *["-define:" + v for v in defines]]
    assembly = destination / "Assembly-CSharp.dll"
    if sdk_compiler:
        sdk_compiler.compile(assembly, sources, list(refs.values()), ["-target:library", *options], env=dict(os.environ, TMPDIR=str(out / "tmp")))
    else:
        audio.compile_library(
            "compile_gameplay",
            Path(android_tools["dotnet"]) if android_tools else contents / "NetCoreRuntime/dotnet",
            contents / "DotNetSdkRoslyn/csc.dll",
            assembly,
            sources,
            ["-nostdlib", "-noconfig", *options, *["-r:" + str(p) for p in refs.values()]],
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
    references = postprocessor_references(references, destination / "ilpp-references")
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
            android_tools=android_tools,
        )
        result["phase"] = "gameplay"
        game = gameplay(
            output,
            sdk,
            inputs,
            state[1] / "Risk of Rain 2_Data/Managed",
            ordinary,
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


def run(work, sdk, values, output, *, signed_audio=False, android_tools=None, pcm_after_skill=False):
    work, sdk = native.canonical(work), native.canonical(sdk)
    output = Path(output)
    if not signed_audio and work != (ROOT / "work").resolve():
        raise ValueError("source owner currently requires this checkout's work root")
    state = native.input_state(work)
    if native.sha(PROFILE) != PROFILE_SHA:
        raise ValueError("audited managed profile drift")
    profile = json.loads(PROFILE.read_text())
    if state[0] != profile["input_id"]:
        raise ValueError("unsupported legitimate source input")
    inputs = bind_paths(values, signed_audio=signed_audio)
    if (
        native.sha(inputs["newtonsoft"]) != profile["newtonsoft_sha256"]
        or (not signed_audio and native.sha(inputs["decoder"]) != profile["decoder_sha256"])
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
        compiler = SdkCompiler(sdk, inputs["dotnet"], output) if android_tools else None
        raw = output / "raw"
        invoke(
            [
                *python_command(ROOT / "tools/unity/support/audio/managed-producer/produce.py", isolated=True),
                "--android-source",
                inputs["wwise_android_source"],
                "--android-os-string-source",
                inputs["wwise_os_string_source"],
                "--native-so",
                inputs["wwise_abi_native"],
                *(
                    ["--owner-work", work]
                    if signed_audio
                    else ["--llvm-nm", sdk / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm"]
                ),
                *(["--android-sdk-install", sdk] if compiler else ["--unity-editor", sdk / "Unity.app/Contents/MacOS/Unity"]),
                "--dotnet",
                inputs["dotnet"],
                "--netstandard-ref",
                inputs["netstandard_ref"],
                "--observe-audio",
                "--output-dir",
                raw,
            ],
            output,
            "raw-managed",
            env=dict(os.environ, TMPDIR=str(output / "tmp")) if compiler else None,
        )
        manifest = json.loads((raw / "manifest.json").read_text())
        managed_paths = audio.verify_managed_output_manifest(manifest, work, native_abi_reader=signed_audio)
        result["phase"] = "packages-and-transforms"
        package_output = output / "packages"
        package_request = {"sdk_install": str(sdk), "packages": str(inputs["packages"]), "output": str(package_output)}
        if android_tools:
            package_request["android_tools"] = android_tools
        packages_owner.run(package_request)
        transform_recipe = assembly_transforms.load_recipe()
        if compiler:
            ordinary_dir = raw / "ordinary"
            by_name = {path.name: path for path in managed_paths.values() if path.parent == ordinary_dir}
            ordinary = {name: by_name[name] for step in transform_recipe["steps"] for name in step["outputs"]}
        else:
            ordinary_dir = output / "ordinary"
            ordinary_dir.mkdir()
            ordinary = assembly_transforms.generate(
                state[1] / "Risk of Rain 2_Data/Managed",
                ordinary_dir,
                transform_recipe,
                dotnet=inputs["dotnet"],
                unity_editor=sdk / "Unity.app/Contents/MacOS/Unity",
            )
        unchanged(bound)
        if native.input_state(work) != state:
            raise ValueError("owner source state changed")
        result["phase"] = "source-audio-inputs"
        owner_work = work if signed_audio else None
        staged, prefab, bank, init_dir = stage_source_audio(work, state[1], output, decoder=None if signed_audio else inputs["decoder"])
        result["phase"] = "audio-assemblies"
        audio.validate_owner_source_manifest()
        supplied = output / "supplied-sdk"
        supplied.mkdir()
        native_copy = supplied / "libAkSoundEngine.so"
        shutil.copyfile(inputs["wwise_native"], native_copy)
        if native.sha(native_copy) != audio.LINEAGE["native_library_sha256"]:
            raise ValueError("supplied licensed native copy differs")
        audio_outputs = audio_assemblies(
            output,
            sdk,
            inputs | {"wwise_native": native_copy},
            ordinary,
            staged,
            prefab,
            bank,
            init_dir,
            managed_paths,
            manifest,
            owner_work=owner_work,
            sdk_compiler=compiler,
            pcm_after_skill=pcm_after_skill,
        )
        observed_game = raw / "game-original-owner-audio-observed.dll"
        if observed_game not in managed_paths.values():
            raise ValueError("managed producer omitted the original audio lifecycle and post observers")
        audio_outputs.update({"AK.Wwise.Unity.API.dll": raw / "api-instrumented-composed.dll", "RoR2.dll": observed_game})
        unchanged(bound)
        result["phase"] = "original-sources-and-maps"
        maps, support = maps_and_support(
            output,
            inputs,
            state[1] / "Risk of Rain 2_Data/Managed",
            ordinary_dir / "tool/AssemblyProbe.dll",
            profile,
            state[0],
            work=work,
            android_tools=android_tools,
        )
        result["phase"] = "gameplay-assembly"
        game = gameplay(
            output,
            sdk,
            inputs,
            state[1] / "Risk of Rain 2_Data/Managed",
            ordinary,
            package_output,
            audio_outputs,
            maps,
            support,
            android_tools=android_tools,
            sdk_compiler=compiler,
        )
        produced = {
            "AK.Wwise.Unity.MonoBehaviour.dll": ordinary["AK.Wwise.Unity.MonoBehaviour.dll"],
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
