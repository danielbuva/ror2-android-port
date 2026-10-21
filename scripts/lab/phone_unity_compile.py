"""Compile the public Unity fixture from SDK/package-derived references only.

This isolated profile has no conditional source or custom packages/generators.
It does not produce a player, type database, game assembly or installer.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

PROFILE = "authored-unity-builtin-references-v1"
SOURCE = "scripts/lab/phone_unity_compile.py"
FIXTURE = "tools/phone-build/ContentFixture.cs"
FIXTURE_SHA = "f64ead0f0509900491888ff33404f7cdbd90cfc72c8e8520be22784361a3750a"
SOURCES = (SOURCE, "scripts/lab/phone_managed_compile.py", "scripts/lab/phone_module_policy.py", FIXTURE)
GROUPS = {
    "PlaybackEngines/AndroidPlayer/Variations/il2cpp/Managed": 64,
    "Unity.app/Contents/NetStandard/compat/2.1.0/shims/netfx": 17,
    "Unity.app/Contents/NetStandard/compat/2.1.0/shims/netstandard": 103,
    "Unity.app/Contents/NetStandard/Extensions/2.0.0": 1,
    "Unity.app/Contents/NetStandard/ref/2.1.0": 1,
}
REFERENCE_SHA = "5ed7d9fffe181c489ad8bbce79bbc9d35eafdbbad23e65a613391a8711dd951a"
PACKAGE_SHA = "f921be2dc22b03528b429772228b229bac2af92b483e0103a4124b121c13f58f"
MANIFEST = {"dependencies": {"com.unity.modules." + name: "1.0.0" for name in ("androidjni", "assetbundle", "jsonserialize", "unitywebrequest")}}
SUPPORT_SHA = {
    "phone_managed_compile": "ab8693a0a8854c315cd745c6552b77714ecbbd5b31705b06e902560111784efb",
    "phone_module_policy": "6d2b830b437e417530d41ab96fee3a2572247ea3752083dee7d10533229e0649",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def aggregate(hashes):
    return hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def support(name):
    # Explicit sibling files also work under Python -I -S; no ambient imports.
    path = Path(__file__).with_name(name + ".py")
    if name not in SUPPORT_SHA or path.is_symlink() or sha(path) != SUPPORT_SHA[name]:
        raise ValueError("Authored compiler support drift")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def references(base):
    result = {}
    for folder, count in GROUPS.items():
        paths = sorted((Path(base) / folder).glob("*.dll"))
        if len(paths) != count or any(p.is_symlink() or p != p.resolve() or not p.is_file() for p in paths):
            raise ValueError("Unknown SDK reference directory membership or links")
        result.update({p.relative_to(base).as_posix(): sha(p) for p in paths})
    if aggregate(result) != REFERENCE_SHA:
        raise ValueError("SDK reference closure drift")
    return result


def package_hashes(directory):
    paths = sorted(Path(directory).glob("*.json"))
    result = {p.name: sha(p) for p in paths}
    if any(p.is_symlink() for p in paths) or aggregate(result) != PACKAGE_SHA:
        raise ValueError("SDK builtin-package closure drift")
    return result


def stage(root, sdk, work):
    root, sdk, work = (Path(p).absolute() for p in (root, sdk, work))
    guard, policy = support("phone_managed_compile"), support("phone_module_policy")
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root):
        raise ValueError("Commit Unity compiler fixture sources before staging")
    if sha(root / SOURCE) != sha(__file__) or sha(sdk / "MacOS/Unity") != guard.SDK_BINARY_SHA256 or sha(root / FIXTURE) != FIXTURE_SHA:
        raise ValueError("Unknown owner SDK or authored Unity fixture")
    install = sdk.parents[1]
    refs = references(install)
    editor_modules, target_modules = sdk / "Resources/modules.asset", install / "PlaybackEngines/AndroidPlayer/modules.asset"
    if sha(editor_modules) != policy.EDITOR_SHA or sha(target_modules) != policy.TARGET_SHA:
        raise ValueError("SDK module-data drift")
    inputs = {"sdk/" + name: (install / name).read_bytes() for name in refs}
    for name, (source, digest) in guard.INPUTS.items():
        if name.startswith("compiler/"):
            if sha(sdk / source) != digest:
                raise ValueError("SDK compiler component drift")
            inputs[name] = (sdk / source).read_bytes()
    inputs.update({"module-policy/editor-modules.asset": editor_modules.read_bytes(), "module-policy/target-modules.asset": target_modules.read_bytes()})
    for name, row in policy.modules(editor_modules.read_text()).items():
        if row["controlledByBuiltinPackage"]:
            package = policy.PREFIX + name.lower()
            inputs["module-policy/packages/" + package + ".json"] = (sdk / "Resources/PackageManager/BuiltInPackages" / package / "package.json").read_bytes()
    inputs["module-policy/manifest.json"] = (json.dumps(MANIFEST, indent=2) + "\n").encode()
    inputs.update({Path(name).name: (root / name).read_bytes() for name in SOURCES[:-1]})
    inputs["source/ContentFixture.cs"] = (root / FIXTURE).read_bytes()
    packages = {Path(name).name: hashlib.sha256(data).hexdigest() for name, data in inputs.items() if name.startswith("module-policy/packages/")}
    if aggregate(packages) != PACKAGE_SHA:
        raise ValueError("SDK builtin-package closure drift")
    destination = work / "rebuild/phone-managed-compile" / ("unity-" + uuid.uuid4().hex)
    with guard.directory(destination, work, new=True):
        pass
    for name, data in inputs.items():
        guard.write_input(destination / name, data, work)
    receipt = dict(
        schema=1,
        profile=PROFILE,
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        sdk_binary_sha256=guard.SDK_BINARY_SHA256,
        game_inputs=False,
        inputs={name: sha(destination / name) for name in inputs},
    )
    guard.write_input(destination / "inputs.json", (json.dumps(receipt, indent=2) + "\n").encode(), work)
    validate(destination)
    # Re-read all SDK inputs: staging must not hide a changing supplier tree.
    if (
        refs != references(install)
        or sha(sdk / "MacOS/Unity") != guard.SDK_BINARY_SHA256
        or sha(editor_modules) != policy.EDITOR_SHA
        or sha(target_modules) != policy.TARGET_SHA
    ):
        raise ValueError("Owner SDK changed while staging")
    for name, (source, digest) in guard.INPUTS.items():
        if name.startswith("compiler/") and sha(sdk / source) != digest:
            raise ValueError("SDK compiler changed while staging")
    for package in package_hashes(destination / "module-policy/packages"):
        if sha(sdk / "Resources/PackageManager/BuiltInPackages" / Path(package).stem / "package.json") != sha(destination / "module-policy/packages" / package):
            raise ValueError("SDK package changed while staging")
    return destination, receipt


def validate(directory):
    directory = Path(directory).absolute()
    if directory != directory.resolve() or any(p.is_symlink() for p in directory.rglob("*")):
        raise ValueError("Unity compiler stage links are unsupported")
    guard, policy = support("phone_managed_compile"), support("phone_module_policy")
    receipt = json.loads((directory / "inputs.json").read_text())
    refs = references(directory / "sdk")
    packages = package_hashes(directory / "module-policy/packages")
    expected = {"sdk/" + name: digest for name, digest in refs.items()}
    expected.update({name: digest for name, (_, digest) in guard.INPUTS.items() if name.startswith("compiler/")})
    expected.update({"module-policy/packages/" + name: digest for name, digest in packages.items()})
    expected.update({Path(name).name: sha(Path(__file__).with_name(Path(name).name)) for name in SOURCES[:-1]})
    expected.update(
        {
            "source/ContentFixture.cs": FIXTURE_SHA,
            "module-policy/editor-modules.asset": policy.EDITOR_SHA,
            "module-policy/target-modules.asset": policy.TARGET_SHA,
            "module-policy/manifest.json": hashlib.sha256((json.dumps(MANIFEST, indent=2) + "\n").encode()).hexdigest(),
        }
    )
    if (
        receipt.get("schema") != 1
        or receipt.get("profile") != PROFILE
        or receipt.get("sdk_binary_sha256") != guard.SDK_BINARY_SHA256
        or receipt.get("game_inputs") is not False
        or not re.fullmatch("[0-9a-f]{40}", receipt.get("source_commit", ""))
        or receipt.get("inputs") != expected
    ):
        raise ValueError("Unity compiler input profile/identity differs")
    if any(sha(directory / name) != digest for name, digest in expected.items()):
        raise ValueError("Unity compiler input drift")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != set(expected) | {"inputs.json"}:
        raise ValueError("Foreign Unity compiler stage files or earlier output")
    return receipt


def project_references(directory, receipt):
    directory = Path(directory)
    policy = support("phone_module_policy").evaluate_stage(directory / "module-policy")
    selected, excluded = [], []
    target = support("phone_module_policy").modules((directory / "module-policy/target-modules.asset").read_text())
    for path, digest in sorted(references(directory / "sdk").items(), key=lambda item: item[0].casefold()):
        name = Path(path).name
        if "/Variations/il2cpp/Managed/" in path and name != "UnityEngine.dll":
            match = re.fullmatch(r"UnityEngine\.([A-Za-z][A-Za-z0-9]*)Module\.dll", name)
            if not match or match[1] not in target:
                raise ValueError("Unmapped target managed module")
            if match[1] in policy["forceExcludeModules"]:
                excluded.append(path)
                continue
        selected.append({"path": "sdk/" + path, "sha256": digest})
    return dict(
        schema=1,
        profile=PROFILE,
        source_commit=receipt["source_commit"],
        references=selected,
        excluded=excluded,
        module_policy=policy,
        game_inputs=False,
        unity_player_compilation_qualified=False,
    )


def compile_fixture(directory, launcher, host):
    directory, launcher = Path(directory).absolute(), Path(launcher).absolute()
    guard = support("phone_managed_compile")
    if host not in guard.RUNTIMES:
        raise ValueError("Select a qualified compiler build-tool profile")
    receipt = validate(directory)
    output = directory / "output"
    output.mkdir(exist_ok=False)
    (output / "tmp").mkdir()
    started = time.monotonic()
    result = dict(
        schema=1,
        source_commit=receipt["source_commit"],
        inputs_sha256=sha(directory / "inputs.json"),
        host=host,
        game_inputs=False,
        player_built=False,
        unity_player_compilation_qualified=False,
        managed_game_compilation_qualified=False,
        success=False,
    )
    try:
        report = project_references(directory, receipt)
        (output / "references.json").write_text(json.dumps(report, indent=2) + "\n")
        result.update(reference_report_sha256=sha(output / "references.json"), reference_count=len(report["references"]), launcher_sha256=sha(launcher))
        env = dict(
            os.environ, DOTNET_ROOT=str(launcher.parent), DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1", TMPDIR=str(output / "tmp")
        )
        runtime = subprocess.run([str(launcher), "--list-runtimes"], env=env, capture_output=True, text=True, timeout=30)
        (output / "runtimes.log").write_text(runtime.stdout + runtime.stderr)
        versions = [line.split()[1] for line in runtime.stdout.splitlines() if line.startswith("Microsoft.NETCore.App ")]
        if runtime.returncode or versions != [guard.RUNTIMES[host]]:
            raise ValueError("Unexpected Unity compiler tool runtime closure")
        result["runtime"] = versions[0]
        command = [
            str(launcher),
            "exec",
            "compiler/csc.dll",
            "/nologo",
            "/noconfig",
            "/nostdlib+",
            "/target:library",
            "/platform:anycpu",
            "/langversion:9.0",
            "/deterministic+",
            "/debug:portable",
            "/optimize-",
            "/pathmap:" + str(directory) + "=/owner-build",
            "/out:output/Assembly-CSharp.dll",
            "/refout:output/Assembly-CSharp.ref.dll",
            "/pdb:output/Assembly-CSharp.pdb",
            *["/r:" + row["path"] for row in report["references"]],
            "source/ContentFixture.cs",
        ]
        result["arguments"] = command
        with (output / "compiler.log").open("w") as log:
            child = subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        result["exit_code"] = child.returncode
        if child.returncode:
            raise RuntimeError("Unity fixture compiler failed; inspect retained log")
        formats = {"Assembly-CSharp.dll": b"MZ", "Assembly-CSharp.ref.dll": b"MZ", "Assembly-CSharp.pdb": b"BSJB"}
        if any(not (output / name).read_bytes().startswith(magic) for name, magic in formats.items()):
            raise ValueError("Invalid Unity fixture compiler output format")
        result["outputs"] = {name: sha(output / name) for name in formats}
        if any(sha(directory / name) != digest for name, digest in receipt["inputs"].items()):
            raise ValueError("Unity compiler inputs changed during compilation")
        result["success"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result["failure"] = str(error)
    result["elapsed_seconds"] = time.monotonic() - started
    with (output / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "stage":
        destination, receipt = stage(*sys.argv[2:])
        print(json.dumps(dict(stage=str(destination), **receipt)))
    elif len(sys.argv) == 5 and sys.argv[1] == "run":
        result = compile_fixture(*sys.argv[2:])
        print(json.dumps(result))
        raise SystemExit(0 if result["success"] else 1)
    else:
        raise SystemExit(
            "Usage: phone_unity_compile.py stage ROOT OWNER_SDK_CONTENTS WORK | run STAGE DOTNET sdk|android (authored fixture only; no conditional source, generators or custom packages)"
        )
