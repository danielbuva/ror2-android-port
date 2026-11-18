"""Rebuild the disposable installer on macOS with a retained Android runtime."""

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

PACKAGE = "dev.ror2lab.installertest"
KEY_DIR = Path("keys/installer-test")
KEY_FILES = ("owner.p12", "password")
MANAGED = Path("tools/phone-build/managed-host")
SIGNER = Path("tools/phone-build/owner-apk/build_owner_apk.py")
REPO_ASSETS = ("scripts", "tools", "recipe", "environment", "launcher", ".gitignore", "AGENTS.md", "dev")
RUNTIME_INPUTS = (
    MANAGED / "build_fixture.py",
    MANAGED / "NativePythonHost.c",
    MANAGED / "NativeDotnetMuxer.c",
    MANAGED / "NativeJavaHost.c",
    MANAGED.parent / "native-host/NativeToolHost.c",
    MANAGED.parent / "native-host/Hello.cs",
    "tools/phone-build/owner-code/GnuToolAdapter.c",
    "recipe/owner-app-host-tools.json",
    "recipe/owner-public-tools.json",
    "environment/toolchain.json",
    "scripts/env.sh",
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def signing_certificate(keys, java):
    if keys.is_symlink() or not keys.is_dir() or keys.stat().st_mode & 0o077:
        raise ValueError("private installer-test key directory required")
    for name in KEY_FILES:
        path = keys / name
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 != 0o600 or not path.stat().st_size:
            raise ValueError("both installer-test signing files must exist with mode 0600")
    try:
        password = (keys / "password").read_text()
    except UnicodeDecodeError:
        raise ValueError("installer-test signing password could not be read") from None
    environment = dict(os.environ, ROR2_OWNER_SIGNING_PASSWORD=password)
    result = subprocess.run(
        [java.with_name("keytool"), "-exportcert", "-alias", "owner", "-keystore", keys / "owner.p12", "-storepass:env", "ROR2_OWNER_SIGNING_PASSWORD"],
        env=environment,
        capture_output=True,
        timeout=30,
    )
    if result.returncode or not result.stdout:
        raise ValueError("installer-test certificate unavailable")
    return hashlib.sha256(result.stdout).hexdigest()


def backup_signing_key(keys, java, expected, fetch):
    if keys != keys.resolve():
        raise ValueError("canonical installer-test key directory required")
    keys.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not keys.exists():
        with tempfile.TemporaryDirectory(prefix=".installer-key-", dir=keys.parent) as directory:
            staging = Path(directory) / "key"
            staging.mkdir(mode=0o700)
            for name in KEY_FILES:
                descriptor = os.open(staging / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    fetch(name, stream)
            if signing_certificate(staging, java) != expected:
                raise ValueError("installer-test backup certificate differs")
            staging.rename(keys)
    if signing_certificate(keys, java) != expected:
        raise ValueError("existing installer-test key certificate differs")


def git(checkout, *args):
    return subprocess.check_output(["git", "-C", checkout, *args]).decode().strip()


def base_receipt(base):
    receipt = json.loads((base / "result.json").read_bytes())
    built = json.loads((base / "build-receipt.json").read_bytes())
    apk = base / "signed.apk"
    commit = receipt.get("source_commit") or ""
    request_key = receipt.get("cache_key") or ""
    if (
        receipt.get("success") is not True
        or receipt.get("package") != PACKAGE
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or (base.name != commit and (base.name != request_key or not re.fullmatch(r"[0-9a-f]{64}", request_key)))
        or not re.fullmatch(r"[0-9a-f]{64}", receipt.get("signer_sha256") or "")
        or built.get("success") is not True
        or built.get("game_inputs") is not False
        or built.get("apk_bytes") != apk.stat().st_size
        or built.get("apk_sha256") != receipt.get("apk_sha256")
        or digest(apk) != receipt["apk_sha256"]
    ):
        raise ValueError("installer-test base receipt or APK differs")
    return receipt, built["native_hashes"]


def copy_member(source, target):
    digest = hashlib.sha256()
    while data := source.read(1024 * 1024):
        target.write(data)
        digest.update(data)
    return digest.hexdigest()


def assemble(base, output, manifest, dex, sources, native_hashes, obsolete_signature):
    with zipfile.ZipFile(base) as original, zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=1) as apk:
        apk.write(dex, "classes.dex")
        apk.writestr("AndroidManifest.xml", manifest)
        assets = json.loads(original.read("assets/data-hashes.json"))
        assets = {name: value for name, value in assets.items() if not name.startswith("repo/") and "assets/" + name not in sources}
        retained = set()
        for row in original.infolist():
            name = row.filename
            if (
                obsolete_signature(name)
                or name.startswith("assets/repo/")
                or name in sources
                or name in {"AndroidManifest.xml", "classes.dex", "assets/data-hashes.json"}
            ):
                continue
            if name in retained:
                raise ValueError("duplicate retained APK member")
            retained.add(name)
            with original.open(row) as source, apk.open(copy.copy(row), "w") as target:
                actual = copy_member(source, target)
            if name.startswith("assets/") and assets.get(name.removeprefix("assets/")) != actual:
                raise ValueError("retained runtime asset differs")
            if name.startswith("lib/") and native_hashes.get(Path(name).name) != actual:
                raise ValueError("retained Android library differs")
        if retained != {"assets/" + name for name in assets} | {"lib/arm64-v8a/" + name for name in native_hashes}:
            raise ValueError("retained runtime member list differs")
        for name, path in sources.items():
            with path.open("rb") as source, apk.open(name, "w") as target:
                assets[name.removeprefix("assets/")] = copy_member(source, target)
        apk.writestr("assets/data-hashes.json", json.dumps(assets, sort_keys=True) + "\n")
    return assets


def build(checkout, base, zipalign, check=False):
    checkout = checkout.resolve(strict=True)
    version = git(checkout, "rev-parse", "HEAD")
    work = (checkout / "work").resolve(strict=True)
    cache = work / "coordination/lab-runner/toolhost"
    if base.resolve() != cache / base.name:
        raise ValueError("installer-test base must be in the private toolhost cache")
    base = base.resolve()
    receipt, native_hashes = base_receipt(base)
    git(checkout, "diff", "--quiet", "HEAD", "--", *REPO_ASSETS)
    git(checkout, "diff", "--quiet", receipt["source_commit"], version, "--", *RUNTIME_INPUTS)
    java = Path(os.environ["JAVA_HOME"]) / "bin/java"
    sdk = Path(os.environ["ANDROID_HOME"])
    tools = sdk / "build-tools/34.0.0"
    keys = work / KEY_DIR
    if signing_certificate(keys, java) != receipt["signer_sha256"]:
        raise ValueError("host key does not match the retained installer-test certificate")
    if check:
        return
    if (cache / version).exists():
        raise ValueError("installer-test output already exists for this commit")
    staging = load_module("toolhost_staging", checkout / MANAGED / "stage.py")
    signer = load_module("toolhost_signing", checkout / SIGNER)
    android = sdk / "platforms/android-33/android.jar"
    with tempfile.TemporaryDirectory(prefix=".installer-build-", dir=cache) as directory:
        output = Path(directory)
        classes = output / "classes"
        classes.mkdir()

        def run(*args):
            subprocess.run(args, check=True, timeout=600)

        run(
            java.with_name("javac"),
            "-source",
            "8",
            "-target",
            "8",
            "-parameters",
            "-bootclasspath",
            android,
            "-d",
            classes,
            *(checkout / MANAGED / name for name in staging.JAVA_SOURCES),
        )
        jar = output / "classes.jar"
        with zipfile.ZipFile(jar, "x") as archive:
            for path in sorted(classes.rglob("*.class")):
                archive.write(path, path.relative_to(classes).as_posix())
        run(java, "-cp", tools / "lib/d8.jar", "com.android.tools.r8.D8", "--min-api", "24", "--lib", android, "--output", output, jar)
        manifest = output / "AndroidManifest.xml"
        with zipfile.ZipFile(base / "signed.apk") as original:
            game_package = json.loads(original.read("assets/release-trust.json"))["application_id"]
        staging.tool_manifest(checkout / MANAGED / manifest.name, manifest, PACKAGE, game_package=game_package)
        wire = "{http://schemas.android.com/apk/res/android}"
        fields = ET.parse(manifest).getroot().attrib
        compiled = output / "compiled.apk"
        run(tools / "aapt", "package", "-f", "-M", manifest, "-I", android, "-F", compiled)
        names = git(checkout, "ls-tree", "-rz", "--name-only", version, "--", *REPO_ASSETS).split("\0")
        source_assets = {"assets/repo/" + name: checkout / name for name in names if name}
        source_assets["assets/run_profile.py"] = checkout / MANAGED / "run_profile.py"
        unsigned = output / "unsigned.apk"
        with zipfile.ZipFile(compiled) as archive:
            assets = assemble(
                base / "signed.apk",
                unsigned,
                archive.read(manifest.name),
                output / "classes.dex",
                source_assets,
                native_hashes,
                signer.ASSEMBLY.obsolete_signature,
            )
        request = output / "sign-request.json"
        save(
            request,
            {
                "unsigned": str(unsigned),
                "java": str(java),
                "zipalign": str(zipalign.resolve(strict=True)),
                "apksigner_jar": str(tools / "lib/apksigner.jar"),
                "key_directory": str(keys),
            },
        )
        signed = output / "signing"
        signature = signer.sign(request, signed)
        if not signature["success"] or signature["signer_sha256"] != receipt["signer_sha256"]:
            raise ValueError("Mac APK certificate differs from the installer-test base")
        git(checkout, "diff", "--quiet", version, "--", *REPO_ASSETS)
        if digest(base / "signed.apk") != receipt["apk_sha256"]:
            raise ValueError("installer-test base changed during the build")
        published = output / "cache"
        published.mkdir(mode=0o700)
        apk = published / "signed.apk"
        (signed / "signed.apk").rename(apk)
        evidence = {
            "success": True,
            "game_inputs": False,
            "source_commit": version,
            "base_commit": receipt["source_commit"],
            "base_apk_sha256": receipt["apk_sha256"],
            "apk_sha256": digest(apk),
            "apk_bytes": apk.stat().st_size,
        }
        save(
            published / "result.json",
            dict(
                evidence,
                package=PACKAGE,
                signer_sha256=signature["signer_sha256"],
                version_code=int(fields[wire + "versionCode"]),
                version_name=fields[wire + "versionName"],
            ),
        )
        save(published / "build-receipt.json", dict(evidence, native_hashes=native_hashes, asset_count=len(assets)))
        save(published / "stage-receipt.json", dict(evidence, files=assets))
        (published / ".prune-keep").touch()
        published.rename(cache / version)
    print("Installer-test APK built with the retained signing certificate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="previous installer-test entry in the private toolhost cache")
    parser.add_argument("--zipalign", type=Path, required=True, help="Mac Android Build Tools zipalign with -P 16 support")
    parser.add_argument("--check", action="store_true", help="validate the base, tracked source and local fixture certificate")
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[2], args.base, args.zipalign, args.check)
