"""Stage the fixed app-host experiment from public source and owner SDK jars."""

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
METADATA = ROOT / "recipe/owner-app-host-tools.json"
JAVA_SOURCES = (
    "ToolHostActivity.java",
    "AcquisitionFixture.java",
    "OwnerInstaller.java",
    "OwnerAlphaInstall.java",
    "OwnerUpdateState.java",
    "OwnerBuildService.java",
    "OwnerInputImport.java",
    "OwnerInputSource.java",
    "OwnerToolDownload.java",
    "OwnerGraphicsPicker.java",
    "../owner-apk/graphics/GraphicsDriverPackage.java",
    "../owner-apk/graphics/GraphicsDriverPolicy.java",
    "../owner-apk/graphics/GraphicsDriverProviders.java",
    "../owner-apk/graphics/GraphicsDriverFixture.java",
)
UPDATE_NETWORK_MODULES = {
    "libpyext__socket.so": "python/lib/python3.14/lib-dynload/_socket.cpython-314-aarch64-linux-android.so",
    "libpyext__ssl.so": "python/lib/python3.14/lib-dynload/_ssl.cpython-314-aarch64-linux-android.so",
}
MMAP_MODULE = "libpyext_mmap.so"
MMAP_LINK = "python/lib/python3.14/lib-dynload/mmap.cpython-314-aarch64-linux-android.so"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise ValueError("Unsafe fixture input path")
    return path


def validate_update_network(extra):
    """Require caller-pinned network modules before starting any installer build.

    The base tool experiment did not need networking. Reuse its explicit
    backend-tools.json native/link contract rather than guess provider hashes.
    """
    if not isinstance(extra, dict) or not isinstance(extra.get("natives"), dict) or not isinstance(extra.get("links"), dict):
        raise ValueError("Installer HTTPS requires pinned _socket and _ssl modules in backend-tools.json natives/links")
    for target, link in UPDATE_NETWORK_MODULES.items():
        row = extra["natives"].get(target)
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or extra["links"].get(link) != target:
            raise ValueError("Installer HTTPS requires explicit native provider and Python link: " + target)
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Installer HTTPS provider needs supplied SHA-256: " + target)
        path = Path(row["path"])
        if not path.is_absolute() or path != path.resolve() or not path.is_file() or path.name != PurePosixPath(link).name:
            raise ValueError("Installer HTTPS provider must be a canonical matching Python 3.14 module: " + target)
        if digest(path) != row["sha256"]:
            raise ValueError("Installer HTTPS native provider drift: " + target)


def python_wheel_pins(plan, extra):
    """Bind public wheels and locally built Android wheels before transfer."""
    if not extra or "python_wheels" not in extra:
        return {}
    pins = dict(plan.get("python_wheels", {}))
    built = extra.get("python_built_wheels", {})
    for project, source in plan.get("python_source_wheels", {}).items():
        prefix = project + "-"
        suffix = "-py3-none-any.whl" if source.get("pure") else "-android_24_arm64_v8a.whl"
        matches = [name for name in built if name.startswith(prefix) and name.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError("Toolhost Python closure requires one built wheel for " + project)
        name = matches[0]
        relative(name)
        if len(PurePosixPath(name).parts) != 1 or not re.fullmatch(r"[0-9a-f]{64}", built[name]):
            raise ValueError("Invalid built wheel pin: " + name)
        pins[name] = built[name]
    if built.keys() - pins.keys():
        raise ValueError("Unexpected built wheel in toolhost closure")
    return pins


def stage_python_wheels(extra, pins, destination, *, native_directory=None, native_files=None, links=None):
    """Install package data and route Android ELF files through PackageManager."""
    if not extra or "python_wheels" not in extra:
        return {}
    if MMAP_MODULE not in extra["natives"] or extra["links"].get(MMAP_LINK) != MMAP_MODULE:
        raise ValueError("Player Python wheels require an explicit mmap provider and Python link")
    source = Path(extra["python_wheels"]).resolve(strict=True)
    inputs = {}
    for name, expected in pins.items():
        path = source / name
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Player Python wheel drift: " + name)
        inputs[path] = data
    for path, data in inputs.items():
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                name = relative(member.filename)
                content = archive.read(member)
                if content.startswith(b"\x7fELF"):
                    if native_directory is None or not path.name.endswith("-android_24_arm64_v8a.whl"):
                        raise ValueError("Unexpected native executable in Python wheel: " + str(name))
                    if len(content) < 20 or content[4:6] != b"\x02\x01" or struct.unpack_from("<HH", content, 16) != (3, 183):
                        raise ValueError("Python wheel native must be AArch64 ELF shared object: " + str(name))
                    if not re.search(r"\.so(?:\.[0-9]+)*$", name.name):
                        raise ValueError("Unsupported native Python wheel path: " + str(name))
                    provider = (
                        name.name
                        if re.fullmatch(r"lib[-+A-Za-z0-9_.]+\.so", name.name)
                        else ("libpywheel_" + hashlib.sha256(str(name).encode()).hexdigest()[:24] + ".so")
                    )
                    target = native_directory / provider
                    native_directory.mkdir(parents=True, exist_ok=True)
                    if provider in native_files and target.read_bytes() != content:
                        raise ValueError("Python wheel native name collision: " + provider)
                    native_files[provider] = target
                    links["python/lib/player-packages/" + str(name)] = provider
                    if name.name.startswith("lib") and provider != name.name:
                        links["native-links/" + name.name] = provider
                else:
                    target = destination / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with target.open("xb") as stream:
                        stream.write(content)
                elif target.read_bytes() != content:
                    raise ValueError("Python wheel file collision: " + str(name))
    return {str(path): pins[path.name] for path in inputs}


def stage_texture_sdk_guest(extra, pins, destination):
    """Stage the pinned x86-64 QEMU inputs as app assets."""
    if not extra or "texture_sdk_guest" not in extra:
        return {}
    required = {"libqemu-x86_64.so", "libtexture-pixels.so", "libtexture-etc.so", "libc++_shared.so"}
    if not required <= extra["natives"].keys():
        raise ValueError("Texture SDK guest requires QEMU, pixels, ETC and libc++ native providers")
    source = Path(extra["texture_sdk_guest"]).resolve(strict=True)
    inputs = {}
    for name, expected in pins.items():
        data = (source / relative(name)).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Texture SDK guest input drift: " + name)
        inputs[name] = data
    for name, data in inputs.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {str(source / name): expected for name, expected in pins.items()}


def load_metadata():
    data = json.loads(METADATA.read_text())
    if data.get("schema") != 1 or data.get("kind") != "owner-app-host-tools-v1" or data.get("python_version") != "3.14.8":
        raise ValueError("Unsupported app-host tool profile")
    targets = set()
    for row in data["natives"]:
        relative(row["path"])
        if row["root"] not in ("python", "usr") or not re.fullmatch(r"lib[-A-Za-z0-9_.]+\.so", row["target"]) or row["target"] in targets:
            raise ValueError("Invalid native fixture entry")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid native fixture digest")
        targets.add(row["target"])
    for name, target in data["links"].items():
        relative(name)
        if not name.startswith(("python/lib/python3.14/lib-dynload/", "native-links/")) or target not in targets:
            raise ValueError("Invalid native fixture link")
    for name, expected in data["public_profile_source_hashes"].items():
        relative(name)
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid public fixture source digest")
    return data


def tool_manifest(source, destination, package=None, game_package=None):
    """Keep Java class identities when selecting a separate owned tool package."""
    tree = ET.parse(source)
    manifest = tree.getroot()
    original = manifest.attrib["package"]
    package = package or original
    if not re.fullmatch(r"dev\.ror2lab\.[A-Za-z][A-Za-z0-9_.]*", package) or package in {
        "dev.ror2lab.arm64",
        "dev.ror2lab.converted",
        "dev.ror2lab.alpha",
        game_package,
    }:
        raise ValueError("separate lab tool package required")
    android = "{http://schemas.android.com/apk/res/android}"
    if game_package is not None:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", game_package):
            raise ValueError("explicit game applicationId required")
        queries = manifest.find("queries")
        if queries is None:
            queries = ET.SubElement(manifest, "queries")
        # Rewrite game-package visibility, retaining the narrow public Settings intent.
        for old in queries.findall("package"):
            queries.remove(old)
        ET.SubElement(queries, "package", {android + "name": game_package})
    for node in manifest.iter():
        if node.tag in {"activity", "instrumentation", "provider", "receiver", "service"}:
            name = node.attrib.get(android + "name", "")
            if name.startswith("."):
                node.set(android + "name", original + name)
        if node.tag == "instrumentation":
            node.set(android + "targetPackage", package)
        if node.tag == "provider":
            node.set(android + "authorities", package + ".apk")
    if package == "dev.ror2lab.installertest":
        application = manifest.find("application")
        fixture = "dev.ror2lab.phonebuildhostfixture.AcquisitionFixture"
        ET.SubElement(application, "activity", {android + "name": fixture + "$Result", android + "exported": "false"})
        ET.SubElement(
            application,
            "provider",
            {
                android + "name": fixture + "$Provider",
                android + "authorities": package + ".acquisition",
                android + "exported": "true",
                android + "grantUriPermissions": "true",
                android + "permission": "android.permission.MANAGE_DOCUMENTS",
            },
        )
    manifest.set("package", package)
    ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def stage(profile_source, sdk, destination, *, root=ROOT, owner_backend=False, release_trust=None, backend_tools=None):
    profile_source = Path(profile_source).resolve(strict=True)
    sdk = Path(sdk).resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    owned = (root.resolve() / "work").resolve()
    if destination != destination.resolve() or not destination.is_relative_to(owned) or destination.exists():
        raise ValueError("Fixture destination must be new under this checkout's ignored work/")
    if profile_source == destination or destination in profile_source.parents or sdk == destination or sdk in destination.parents:
        raise ValueError("Fixture destination overlaps its supplied inputs")
    metadata = load_metadata()
    files = {}

    def bind(source, name):
        if source.is_symlink() or not source.is_file():
            raise ValueError("Fixture input must be a regular file")
        files[name] = (source, digest(source))

    for name, expected in metadata["public_profile_source_hashes"].items():
        path = profile_source / name
        if path != path.resolve() or not path.resolve().is_relative_to(profile_source):
            raise ValueError("Public source path contains links")
        bind(path, "repo/" + name)
        if files["repo/" + name][1] != expected:
            raise ValueError("Public transform source drift: " + name)
    for name in (
        "owner-apk/build_owner_apk.py",
        "owner-apk/release.py",
        "owner-apk/updates.py",
        "owner-apk/release_source.py",
        "owner-apk/public_release.py",
        "owner-apk/release_jobs.py",
        "owner-apk/game_import.py",
        "owner-apk/install_flow.py",
        "owner-apk/atomic_io.py",
        "owner-apk/alpha_policy.py",
        "owner-apk/ProfileStore.java",
        "owner-apk/ProfileRetentionProvider.java",
        "owner-apk/install_inputs.py",
        "owner-apk/binary_manifest.py",
        "owner-code/GnuToolAdapter.c",
        "accepted-output/package.py",
        "accepted-output/assemble.py",
        "accepted-output/phone_runner.py",
    ):
        bind(SOURCE.parent / name, "repo/tools/phone-build/" + name)
    if owner_backend:
        names = (
            subprocess.check_output(["git", "ls-files", "-z", "--", "scripts", "tools", "recipe", "environment", "launcher", ".gitignore", "dev"], cwd=root)
            .decode()
            .split("\0")
        )
        for name in filter(None, names):
            bind(root / name, "repo/" + name)
    for name in (
        "NativePythonHost.c",
        "NativeDotnetMuxer.c",
        "NativeJavaHost.c",
        "run_profile.py",
        "check_python.py",
        "stage.py",
        "build_fixture.py",
        "AndroidManifest.xml",
    ):
        bind(SOURCE / name, name)
    for name in JAVA_SOURCES:
        bind(SOURCE / name, Path(name).name)
    for name in ("NativeToolHost.c", "Hello.cs"):
        bind(SOURCE.parent / "native-host" / name, name)
    # This is build-time public trust, never a key learned from a downloaded release.
    trust_source = Path(release_trust).resolve(strict=True) if release_trust else SOURCE / "release-trust.json"
    trust = json.loads(trust_source.read_text())
    if set(trust) != {"repository", "application_id", "keys"} or not isinstance(trust["keys"], dict):
        raise ValueError("Explicit public release trust configuration required")
    bind(trust_source, "release-trust.json")
    if backend_tools is not None:
        bind(Path(backend_tools), "backend-tools.json")
        if owner_backend and not python_wheel_pins(metadata, json.loads(Path(backend_tools).read_bytes())):
            raise ValueError("Owner backend requires the pinned Python wheelhouse")
    bind(METADATA, "python-native-plan.json")
    for name, path in {
        "android.jar": "platforms/android-33/android.jar",
        "d8.jar": "build-tools/34.0.0/lib/d8.jar",
        "apksigner.jar": "build-tools/34.0.0/lib/apksigner.jar",
    }.items():
        bind(sdk / path, name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    receipt = dict(schema=1, success=False, game_inputs=False, source_hint=metadata["source_head"], files={})
    try:
        for name, (source, expected) in files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
            if digest(source) != expected or digest(path) != expected:
                raise RuntimeError("Fixture source/copy drift")
            receipt["files"][name] = expected
        receipt["success"] = True
    except Exception as error:
        receipt["failure"] = str(error)
        raise
    finally:
        (destination / "stage-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-source", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--owner-backend", action="store_true", help="stage current authored owners for the headless whole-player backend")
    parser.add_argument("--release-trust", type=Path, help="explicit publisher public-key configuration; default remains unprovisioned")
    parser.add_argument("--backend-tools", type=Path, help="private native provider and alias plan for the installer builder")
    args = parser.parse_args()
    result = stage(
        args.profile_source, args.sdk, args.dest, owner_backend=args.owner_backend, release_trust=args.release_trust, backend_tools=args.backend_tools
    )
    print(json.dumps(dict(success=result["success"], files=len(result["files"]))))
