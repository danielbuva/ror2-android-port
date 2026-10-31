"""Private positive app-host experiment; no game inputs, policy or runtime changes."""

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
source = Path(__file__).resolve().parent
toolroot = Path(sys.argv[1]).resolve(strict=True)
material = Path(sys.argv[2]).resolve(strict=True)
out = Path(sys.argv[3]).resolve()
out.mkdir(mode=0o700, exist_ok=False)
native = toolroot / "usr"
packaging = toolroot / "packaging/usr"
java = packaging / "lib/jvm/java-21-openjdk/bin/java"
runtime = native / "lib/dotnet"
env = dict(os.environ, LD_LIBRARY_PATH=":".join(str(toolroot / p) for p in ["packaging/usr/lib", "python/usr/lib", "usr/lib"]))
receipt = dict(schema=1, success=False, game_inputs=False, security_qualified=False, commands=[], inputs={})


def run(label, *args, timeout=180):
    args = list(map(str, args))
    p = subprocess.run(args, env=env, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout)
    (out / (label + ".log")).write_bytes(p.stdout + p.stderr)
    receipt["commands"].append(dict(label=label, exit=p.returncode))
    if p.returncode:
        raise RuntimeError(label + " exit " + str(p.returncode))


def bind(p):
    receipt["inputs"][str(p)] = sha(p)


def copy(p, q):
    bind(p)
    q.parent.mkdir(exist_ok=True, parents=True)
    shutil.copyfile(p, q)


try:
    for p in source.rglob("*"):
        if p.is_file():
            bind(p)
    plan = json.loads((source / "python-native-plan.json").read_text())
    extra_tools = source / "backend-tools.json"
    extra = json.loads(extra_tools.read_text()) if extra_tools.exists() else None
    spec = importlib.util.spec_from_file_location("fixture_staging", source / "stage.py")
    staging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(staging)
    # Refuse before any native/Java/APK build, not at the first phone download.
    staging.validate_update_network(extra)
    binary = out / "libtoolhost.so"
    run(
        "native-build",
        native / "bin/clang-21",
        "--target=aarch64-linux-android24",
        "--sysroot=" + str(native),
        "-resource-dir=" + str(native / "lib/clang/21"),
        "--ld-path=" + str(native / "bin/ld.lld"),
        "-B" + str(native / "lib"),
        "-L/system/lib64",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fPIE",
        "-pie",
        source / "NativeToolHost.c",
        "-ldl",
        "-o",
        binary,
    )
    native_files = {
        "libtoolhost.so": binary,
        "libhostfxr.so": runtime / "host/fxr/8.0.32/libhostfxr.so",
        "libcrypto.so": native / "lib/libcrypto.so.3",
        "libssl.so": native / "lib/libssl.so.3",
    }
    for name, filename in [("NativePythonHost", "libpythonhost.so"), ("NativeDotnetMuxer", "libdotnetmuxer.so")]:
        target = out / filename
        run(
            "build-" + name,
            native / "bin/clang-21",
            "--target=aarch64-linux-android24",
            "--sysroot=" + str(native),
            "-resource-dir=" + str(native / "lib/clang/21"),
            "--ld-path=" + str(native / "bin/ld.lld"),
            "-B" + str(native / "lib"),
            "-L/system/lib64",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fPIE",
            "-pie",
            source / (name + ".c"),
            "-ldl",
            "-o",
            target,
        )
        native_files[filename] = target
    for row in plan["natives"]:
        path = (toolroot / "python/usr" if row["root"] == "python" else native) / row["path"]
        if sha(path) != row["sha256"]:
            raise RuntimeError("Python native plan drift")
        if row["target"] in native_files and sha(native_files[row["target"]]) != row["sha256"]:
            raise RuntimeError("Native name collision")
        native_files[row["target"]] = path
    # Optional caller-supplied native build tools are installed by PackageManager,
    # never executed from writable assets. Every extra input is hash-bound.
    if extra:
        for name, row in extra["natives"].items():
            path = Path(row["path"])
            if not re.fullmatch(r"lib[-+A-Za-z0-9_.]+\.so", name) or name in native_files or sha(path) != row["sha256"]:
                raise RuntimeError("Backend native name or input drift: " + name)
            native_files[name] = path
        if "java_home" in extra:
            java_home = Path(extra["java_home"]).resolve(strict=True)
            for header in (java_home / "include/jni.h", java_home / "include/linux/jni_md.h"):
                bind(header)
            java_host = out / "libjavahost.so"
            run(
                "build-NativeJavaHost",
                native / "bin/clang-21",
                "--target=aarch64-linux-android24",
                "--sysroot=" + str(native),
                "-resource-dir=" + str(native / "lib/clang/21"),
                "--ld-path=" + str(native / "bin/ld.lld"),
                "-B" + str(native / "lib"),
                "-I" + str(java_home / "include"),
                "-I" + str(java_home / "include/linux"),
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fPIE",
                "-pie",
                source / "NativeJavaHost.c",
                "-Wl,--export-dynamic",
                "-ldl",
                "-o",
                java_host,
            )
            for name in ("libjavatool.so", "libjavactool.so", "libkeytool.so"):
                native_files[name] = java_host
            # Headless javac/keytool/apksigner closure. GUI/audio/debugger
            # libraries are not build-tool dependencies.
            for relative in (
                "server/libjvm.so",
                "libjimage.so",
                "libjava.so",
                "libverify.so",
                "libzip.so",
                "libnet.so",
                "libnio.so",
                "libextnet.so",
                "libjli.so",
            ):
                path = java_home / "lib" / relative
                if not path.is_file() or path.name in native_files:
                    raise RuntimeError("JDK native missing or name collision: " + relative)
                native_files[path.name] = path
                plan["links"]["java/" + path.relative_to(java_home).as_posix()] = path.name
        if "libqemu-x86_64.so" in native_files:
            adapter = source / "repo/tools/phone-build/owner-code/GnuToolAdapter.c"
            bind(adapter)
            run(
                "build-GnuToolAdapter",
                native / "bin/clang-21",
                "--target=x86_64-linux-gnu",
                "-ffreestanding",
                "-fPIC",
                "-O2",
                "-c",
                adapter,
                "-o",
                out / "gnu-adapter.o",
            )
            run("link-GnuToolAdapter", native / "bin/ld.lld", "-m", "elf_x86_64", "-shared", out / "gnu-adapter.o", "-o", out / "libgnu-tool-adapter.so")
    framework = runtime / "shared/Microsoft.NETCore.App/8.0.32"
    native_files.update({p.name: p for p in framework.glob("*.so")})
    assets = out / "assets"
    assets.mkdir()
    if extra:
        resources = Path(extra["clang_resources"])
        for p in resources.rglob("*"):
            if p.is_file():
                copy(p, assets / "clang/21" / p.relative_to(resources))
        plan["links"].update(extra["links"])
        if "java_home" in extra:
            for path in java_home.rglob("*"):
                if not path.is_file() or path.relative_to(java_home).parts[0] in {"bin", "include", "jmods"} or path.name == "src.zip":
                    continue
                with path.open("rb") as stream:
                    executable = stream.read(4) == b"\x7fELF"
                if not executable:
                    copy(path, assets / "java" / path.relative_to(java_home))
            for name in ("android.jar", "d8.jar", "apksigner.jar"):
                copy(source / name, assets / "java-tools" / name)
        if "libqemu-x86_64.so" in native_files:
            copy(out / "libgnu-tool-adapter.so", assets / "gnu/libgnu-tool-adapter.so")
        if "framework" in extra:
            framework_data = Path(extra["framework"])
            if not re.fullmatch(r"10\.[0-9]+\.[0-9]+", framework_data.name):
                raise RuntimeError("Backend framework must be an explicit .NET 10 version")
            for p in framework_data.iterdir():
                if p.is_file() and (p.suffix in (".dll", ".json") or p.name == ".version"):
                    copy(p, assets / "dotnet/shared/Microsoft.NETCore.App" / framework_data.name / p.name)
            for name in ("LICENSE.txt", "ThirdPartyNotices.txt"):
                copy(framework_data.parents[2] / name, assets / "notices/dotnet10" / name)
    for p in (toolroot / "python/usr/lib/python3.14").rglob("*"):
        if p.is_file() and p.suffix == ".py" and "__pycache__" not in p.parts:
            copy(p, assets / "python/lib/python3.14" / p.relative_to(toolroot / "python/usr/lib/python3.14"))
    copy(toolroot / "python/usr/lib/python3.14/LICENSE.txt", assets / "notices/Python-LICENSE.txt")
    copy(source / "run_profile.py", assets / "run_profile.py")
    copy(source / "release-trust.json", assets / "release-trust.json")
    for p in (source / "repo").rglob("*"):
        if p.is_file():
            copy(p, assets / "repo" / p.relative_to(source / "repo"))
    (assets / "python-links.json").write_text(json.dumps(plan["links"], sort_keys=True) + "\n")
    archive_source = Path(sys.argv[4]).resolve(strict=True)
    public = json.loads((source / "repo/recipe/owner-public-tools.json").read_text())
    for row in public["artifacts"]:
        archive = archive_source / row["filename"]
        if archive.stat().st_size != row["bytes"] or sha(archive) != row["sha256"]:
            raise RuntimeError("Phone-acquired archive drift")
        copy(archive, assets / "archives" / row["filename"])
    for p in framework.iterdir():
        if p.is_file() and (p.suffix in (".dll", ".json") or p.name == ".version"):
            copy(p, assets / "dotnet/shared/Microsoft.NETCore.App/8.0.32" / p.name)
    for p in (material / "compiler").iterdir():
        if p.is_file():
            copy(p, assets / "compiler" / p.name)
    for p in (material / "refs").glob("*.dll"):
        copy(p, assets / "refs" / p.name)
    for p in material.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".txt", ".md"):
            copy(p, assets / "notices" / p.relative_to(material))
    for p in runtime.glob("*LICENSE*"):
        copy(p, assets / "notices" / p.name)
    for p in runtime.glob("*NOTICE*"):
        copy(p, assets / "notices" / p.name)
    copy(source / "Hello.cs", assets / "Hello.cs")
    (assets / "Hello.runtimeconfig.json").write_text(
        json.dumps({"runtimeOptions": {"tfm": "net8.0", "framework": {"name": "Microsoft.NETCore.App", "version": "8.0.32"}}}) + "\n"
    )
    for p in native_files.values():
        bind(p)
    (assets / "native-hashes.json").write_text(json.dumps({name: sha(p) for name, p in native_files.items()}, sort_keys=True) + "\n")
    (assets / "data-hashes.json").write_text(
        json.dumps({p.relative_to(assets).as_posix(): sha(p) for p in assets.rglob("*") if p.is_file()}, sort_keys=True) + "\n"
    )
    classes = out / "classes"
    classes.mkdir()
    run(
        "javac",
        java.with_name("javac"),
        "-source",
        "8",
        "-target",
        "8",
        "-parameters",
        "-bootclasspath",
        source / "android.jar",
        "-d",
        classes,
        source / "ToolHostActivity.java",
        source / "OwnerInstaller.java",
        source / "OwnerAlphaInstall.java",
        source / "OwnerUpdateState.java",
        source / "OwnerBuildService.java",
        source / "OwnerInputImport.java",
        source / "OwnerInputSource.java",
    )
    jar = out / "classes.jar"
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as z:
        for p in classes.rglob("*.class"):
            z.write(p, p.relative_to(classes).as_posix())
    dex = out / "dex"
    dex.mkdir()
    run("dex", java, "-cp", source / "d8.jar", "com.android.tools.r8.D8", "--min-api", "24", "--lib", source / "android.jar", "--output", dex, jar)
    unsigned = out / "unsigned.apk"
    staging.tool_manifest(
        source / "AndroidManifest.xml",
        out / "AndroidManifest.xml",
        extra.get("package") if extra else None,
        game_package=json.loads((source / "release-trust.json").read_text())["application_id"],
    )
    run("aapt", packaging / "bin/aapt", "package", "-f", "-M", out / "AndroidManifest.xml", "-I", source / "android.jar", "-F", unsigned)
    with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(dex / "classes.dex", "classes.dex")
        for name, p in native_files.items():
            z.write(p, "lib/arm64-v8a/" + name)
        for p in assets.rglob("*"):
            if p.is_file():
                z.write(p, "assets/" + p.relative_to(assets).as_posix())
    signed = out / "signed.apk"
    signing_request = out / "sign-request.json"
    signing_request.write_text(
        json.dumps(
            {
                "unsigned": str(unsigned),
                "java": str(java),
                "zipalign": str(packaging / "bin/zipalign"),
                "apksigner_jar": str(source / "apksigner.jar"),
                "key_directory": str(toolroot / "owner-tool-key"),
            }
        )
        + "\n"
    )
    # Keep this key outside disposable builds so an update retains app data and
    # long-running source jobs. This signer belongs to the tool APK, not the game.
    run(
        "owner-sign",
        sys.executable,
        source / "repo/tools/phone-build/owner-apk/build_owner_apk.py",
        "--sign-request",
        signing_request,
        "--output",
        out / "signing",
        timeout=3600,
    )
    (out / "signing/signed.apk").rename(signed)
    for p, h in receipt["inputs"].items():
        if sha(p) != h:
            raise RuntimeError("build input changed")
    receipt.update(
        success=True,
        apk_sha256=sha(signed),
        native_hashes=json.loads((assets / "native-hashes.json").read_text()),
        asset_count=len(json.loads((assets / "data-hashes.json").read_text())),
        apk_bytes=signed.stat().st_size,
    )
except Exception as e:
    receipt["failure"] = str(e)
finally:
    (out / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({k: v for k, v in receipt.items() if k not in ["inputs", "native_hashes"]}))
sys.exit(0 if receipt["success"] else 1)
