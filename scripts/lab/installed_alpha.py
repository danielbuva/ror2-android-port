"""Bind a phone-built alpha installation to its trusted installer and release."""

import hashlib
from pathlib import Path
import re
import zipfile

from device import Device
from installer_toolhost import load_module

PACKAGE = "dev.ror2lab.alpha"
ROOT = Path(__file__).resolve().parents[2]
RECEIPT_LIMIT = 4 * 1024**2
SHA256 = re.compile(r"[0-9a-f]{64}")
APPLICATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")


class InstalledAlphaDevice(Device):
    """Observe the installed game while the installer owns the transaction."""

    supported_packages = {PACKAGE}

    def __init__(self, selector, work_root):
        super().__init__(selector, work_root, package=PACKAGE)
        self.installed = None

    def owned(self):
        if self.installed is None or base_apk(self, PACKAGE) != self.installed["package_path"]:
            raise RuntimeError("Live alpha package path differs from its verified installation")
        return self.installed

    def read_receipt(self, name):
        if name == "installed.json":
            if self.installed is None:
                raise RuntimeError("Alpha installation has no verified ownership")
            return self.installed
        return super().read_receipt(name)

    def _installer_only(self, *args, **kwargs):
        raise RuntimeError("Alpha package and payload changes belong to its installer")

    install = sync = reset = _installer_only


def release_tools():
    return load_module("installed_alpha_updates", ROOT / "tools/phone-build/owner-apk/updates.py")


def installer_trust(apk, expected_sha256):
    """Read provisioned keys only from the explicitly authorized installer APK."""
    with Path(apk).open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
            raise ValueError("Authorized installer APK hash differs")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            trust = release_tools().public().load_json(archive.read("assets/release-trust.json"))
    if (
        not isinstance(trust, dict)
        or set(trust) != {"repository", "application_id", "keys"}
        or trust["application_id"] != PACKAGE
        or not isinstance(trust["keys"], dict)
        or not trust["keys"]
    ):
        raise ValueError("Authorized installer has no provisioned alpha release trust")
    return trust


def base_apk(device, package):
    path = device.sh("pm", "path", package, timeout=5)
    if not re.fullmatch(r"package:/[A-Za-z0-9_./=~+-]+/base\.apk", path):
        raise RuntimeError("Expected one installed base APK for " + package)
    return path


def apk_digest(device, package_path):
    observed = device.sh("sha256sum", "--", package_path.removeprefix("package:")).split()
    if not observed or not SHA256.fullmatch(observed[0]):
        raise RuntimeError("Installed APK digest unavailable")
    return observed[0]


def validate_selection(package, installer_package, installer_sha256, expected_source_sha256):
    if (
        package != PACKAGE
        or not APPLICATION_ID.fullmatch(installer_package)
        or installer_package in {PACKAGE, "dev.ror2lab.installertest"}
        or not SHA256.fullmatch(installer_sha256)
        or not SHA256.fullmatch(expected_source_sha256)
    ):
        raise ValueError("Explicit production installer and source release required")


def release_attempt(bundle, release, public):
    """Read the runtime attempt from the signed output's authored recipe."""
    profile_name = "recipe/owner-player-data.json"
    config_name = "recipe/runtime-config.json"
    with Path(bundle).open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != release["bundle_sha256"]:
            raise ValueError("Public tools bundle differs from the installed signed release")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            names = archive.namelist()

            def read(name, limit):
                if names.count(name) != 1 or archive.getinfo(name).file_size > limit:
                    raise ValueError("Expected one bounded public member: " + name)
                return archive.read(name)

            index = public.read_bundle_index(read(public.INDEX, public.MAX_BUNDLE_INDEX_BYTES), release)

            def recipe(name):
                data = read(name, public.MAX_JSON_BYTES)
                if hashlib.sha256(data).hexdigest() != index["files"].get(name):
                    raise ValueError("Public recipe hash differs: " + name)
                return data

            profile = public.load_json(recipe(profile_name))
            matches = [row for row in profile["text_assets"]["files"] if row.get("name") == "MovementBatchProbe"]
            if len(matches) != 1:
                raise ValueError("Signed player data must select one MovementBatchProbe")
            row = matches[0]
            member = row["file"]
            if Path(member).name != member or not {profile_name, config_name} <= set(
                index["entries"].get("apk/assets/bin/Data/" + member, {}).get("recipe_files", [])
            ):
                raise ValueError("MovementBatchProbe recipes are outside the signed APK member closure")
            config = recipe(config_name)
            if row.get("recipe") != {"path": Path(config_name).name, "bytes": len(config), "sha256": hashlib.sha256(config).hexdigest()}:
                raise ValueError("MovementBatchProbe runtime recipe differs from the signed player data")
            attempt = public.load_json(config).get("attempt")
            if not isinstance(attempt, str) or not attempt.strip():
                raise ValueError("Signed runtime recipe has no attempt")
            return attempt


def verify_installed(device, installer_package, installer_sha256, trust, expected_source_sha256, public_tools):
    """Read only the verified installer receipt and small PackageManager results."""
    validate_selection(device.package, installer_package, installer_sha256, expected_source_sha256)
    installer_path = base_apk(device, installer_package)
    if apk_digest(device, installer_path) != installer_sha256:
        raise RuntimeError("Live installer differs from the authorized APK")
    # The installer can publish the receipt before releasing a retention lease.
    # A pending transaction therefore forbids starting the game.
    source = device.sh(
        "run-as",
        installer_package,
        "sh",
        "-c",
        f"test ! -e files/owner-input/pending-install.json && head -c {RECEIPT_LIMIT + 1} files/owner-input/installed-release.json",
        timeout=5,
    )
    owner = release_tools()
    public = owner.public()
    receipt = public.load_json(source, max_bytes=RECEIPT_LIMIT)
    if (
        not isinstance(receipt, dict)
        or receipt.get("installed_readback_verified") is not True
        or receipt.get("application_id") != PACKAGE
        or receipt.get("source_sha256") != expected_source_sha256
    ):
        raise RuntimeError("Installer has no verified installation for the selected source release")
    release = public.verify_envelope(receipt.get("envelope"), trust["keys"])
    public.validate_alpha_release(release)
    if release != receipt.get("release") or owner.ALPHA.fingerprint(release) != expected_source_sha256:
        raise RuntimeError("Publisher signature differs from the installed source release")
    attempt = release_attempt(public_tools, release, public)
    version = owner.ALPHA.code(receipt.get("version_code"))
    signer = owner.ALPHA.sha256(receipt.get("signer_sha256"))
    package_path = base_apk(device, PACKAGE)
    details = device.sh("dumpsys", "package", PACKAGE, timeout=5)
    if re.findall(r"^\s*versionCode=(\d+)\b", details, re.M) != [str(version)]:
        raise RuntimeError("Live alpha version differs from the installer receipt")
    digest = apk_digest(device, package_path)
    if digest != receipt.get("sha256") or base_apk(device, PACKAGE) != package_path:
        raise RuntimeError("Live alpha APK differs from the installer receipt")
    return dict(
        serial=device.serial,
        package=PACKAGE,
        package_path=package_path,
        apk_sha256=digest,
        signer_sha256=signer,
        version_code=version,
        source_sha256=expected_source_sha256,
        publisher_version_code=release["version_code"],
        attempt=attempt,
    )
