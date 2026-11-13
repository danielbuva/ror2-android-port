"""Signed public-tool acquisition and private owner-build update orchestration.

Only a normal PackageInstaller success/readback can advance installed-release.json.
This module never installs, clears saves, obtains ownership, or downloads game data.
"""

import fcntl
import functools
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
MAX_METADATA = 4 * 1024**2
MAX_BUNDLE = 512 * 1024**2
MAX_EXPANDED = 2 * 1024**3
MAX_MEMBERS = 40000


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


RELEASE = module("owner_update_release", HERE / "release.py")
SOURCE = module("owner_update_source", HERE / "release_source.py")
ALPHA = RELEASE.ALPHA
ATOMIC = RELEASE.ATOMIC


@functools.lru_cache(maxsize=1)
def public():
    return module("owner_update_public", HERE / "public_release.py")


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError("canonical relative path required")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in {".", ".."} for p in path.parts) or ":" in value:
        raise ValueError("canonical relative path required")
    return value


def within(root, value, *, exists=False):
    root = Path(root).resolve()
    result = root / relative(value)
    if result.is_symlink() or result.resolve(strict=exists) != result or not result.is_relative_to(root):
        raise ValueError("path escapes private owner root or uses symlink")
    return result


write_json = ATOMIC.write_json


class GitHubTransport:
    """Bounded HTTPS only, including every redirect; never sends credentials."""

    def __init__(self, repository):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("explicit GitHub owner/repository required")
        self.repository = repository

    @staticmethod
    def allowed(url):
        parsed = urllib.parse.urlsplit(url)
        hosts = {"api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.fragment:
            raise ValueError("release URL must use approved credential-free GitHub HTTPS")

    def open(self, url):
        self.allowed(url)
        owner = self

        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                owner.allowed(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "RoR2-owner-installer/1"})
        return urllib.request.build_opener(Redirect()).open(request, timeout=30)

    def metadata_url(self):
        return "https://api.github.com/repos/" + self.repository + "/releases/latest"

    def asset_url(self, url, name):
        self.allowed(url)
        parsed = urllib.parse.urlsplit(url)
        prefix = "/" + self.repository + "/releases/download/"
        if parsed.hostname != "github.com" or not parsed.path.startswith(prefix) or parsed.path.rsplit("/", 1)[-1] != name or parsed.query:
            raise ValueError("release asset does not belong to configured repository")
        return url


def receive(transport, url, destination, limit):
    """Stream to a caller-owned stream; interrupted or oversized data never commits."""
    count, digest = 0, hashlib.sha256()
    with transport.open(url) as source:
        length = source.headers.get("Content-Length")
        if length is not None and (not length.isdecimal() or int(length) > limit):
            raise ValueError("release download exceeds size limit")
        while data := source.read(65536):
            count += len(data)
            if count > limit:
                raise ValueError("release download exceeds size limit")
            destination.write(data)
            digest.update(data)
        if length is not None and count != int(length):
            raise ValueError("incomplete release download")
    return count, digest.hexdigest()


def get_json(transport, url):
    buffer = io.BytesIO()
    receive(transport, url, buffer, MAX_METADATA)
    return public().load_json(buffer.getvalue())


def latest(transport, trusted_keys):
    metadata = get_json(transport, transport.metadata_url())
    if not isinstance(metadata, dict) or metadata.get("draft") is not False or metadata.get("prerelease") is not False:
        raise ValueError("only published stable releases are accepted")
    assets = {}
    for item in metadata.get("assets", []):
        name = item.get("name")
        if name in {"release.json", "release.sig", "public-tools.zip"}:
            if name in assets:
                raise ValueError("duplicate release asset")
            limit = MAX_BUNDLE if name == "public-tools.zip" else 16384 if name == "release.sig" else MAX_METADATA
            if type(item.get("size")) is not int or not 0 < item["size"] <= limit:
                raise ValueError("release asset size invalid")
            assets[name] = {"url": transport.asset_url(item["browser_download_url"], name), "bytes": item["size"]}
    if set(assets) != {"release.json", "release.sig", "public-tools.zip"}:
        raise ValueError("detached signed metadata and public tools assets required")
    envelope = {"release": get_json(transport, assets["release.json"]["url"]), "signature": get_json(transport, assets["release.sig"]["url"])}
    release = public().verify_envelope(envelope, trusted_keys)
    if metadata.get("tag_name") != "owner-v" + str(release["version_code"]):
        raise ValueError("release tag differs from signed version")
    return {"envelope": envelope, "release": release, "bundle": assets["public-tools.zip"]}


def verify_context(release, request, *, require_new=False):
    ALPHA.identity(request["application_id"])
    ALPHA.code(request.get("installed_version"), zero=True)
    ALPHA.code(request.get("installed_release_version"), zero=True)
    public().validate_alpha_release(release)
    RELEASE.validate(release, request["installer_version"], request["application_id"], 0)
    previous = request["installed_release_version"]
    if bool(previous) != bool(request["installed_version"]):
        raise ValueError("installed publisher/version ownership context is incomplete")
    if release["version_code"] < previous:
        raise ValueError("publisher release rollback refused; use explicit retained rollback")
    if require_new and release["version_code"] <= previous:
        raise ValueError("publisher release is already installed")


def extract_bundle(bundle, destination, release):
    """Validate the entire archive before any source file is exposed to execution."""
    bundle, destination = Path(bundle), Path(destination)
    if RELEASE.digest(bundle) != release["bundle_sha256"]:
        raise ValueError("public tools bundle hash differs")
    if destination.exists() or destination.is_symlink():
        raise ValueError("fresh extracted bundle directory required")
    with zipfile.ZipFile(bundle) as archive:
        items = archive.infolist()
        if len(items) > MAX_MEMBERS:
            raise ValueError("too many public bundle members")
        names, expanded = set(), 0
        for item in items:
            name = relative(item.filename)
            if name in names or item.is_dir() or item.flag_bits & 1:
                raise ValueError("duplicate, directory or encrypted bundle member")
            names.add(name)
            mode = item.external_attr >> 16
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                raise ValueError("nonregular public bundle member")
            expanded += item.file_size
            if item.file_size > MAX_BUNDLE or expanded > MAX_EXPANDED:
                raise ValueError("expanded public bundle exceeds size limit")
            if item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise ValueError("unsupported public bundle compression")
        if "bundle-index.json" not in names or archive.getinfo("bundle-index.json").file_size > MAX_METADATA:
            raise ValueError("bounded public bundle index required")
        index = public().load_json(archive.read("bundle-index.json"))
        public().validate_bundle_index(index, release)
        if names != set(index["files"]) | {"bundle-index.json"}:
            raise ValueError("public bundle membership differs from index")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(destination.parent).free < expanded + 64 * 1024**2:
            raise ValueError("insufficient space for verified public tools")
        stage = Path(tempfile.mkdtemp(prefix=".extract-", dir=destination.parent))
        try:
            for name, expected in index["files"].items():
                target = within(stage, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, count = hashlib.sha256(), 0
                with archive.open(name) as source, target.open("xb") as output:
                    while data := source.read(65536):
                        count += len(data)
                        if count > archive.getinfo(name).file_size:
                            raise ValueError("public member exceeded declared size")
                        digest.update(data)
                        output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != expected:
                    raise ValueError("public bundle member hash differs: " + name)
            write_json(stage / "bundle-index.json", index)
            # Sync nested entries before publishing the complete verified tree.
            for directory, _, _ in os.walk(stage, topdown=False):
                ATOMIC.sync_directory(directory)
            stage.rename(destination)
            ATOMIC.sync_directory(destination.parent)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return index


def acquire(candidate, root, transport, emit):
    release = candidate["release"]
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    emit("DOWNLOADING", "Downloading public recipes and tools; no game files.")
    handle, name = tempfile.mkstemp(prefix=".download-", dir=root)
    archive = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            size, digest = receive(transport, candidate["bundle"]["url"], stream, MAX_BUNDLE)
        if size != candidate["bundle"]["bytes"] or digest != release["bundle_sha256"]:
            raise ValueError("public tools download size/hash differs")
        emit("VERIFYING", "Verifying every public recipe and producer.")
        # Fresh extraction even for repeated attempts; no mutable cached code is trusted.
        destination = root / ("verified-" + next(tempfile._get_candidate_names()))
        index = extract_bundle(archive, destination, release)
        return destination, index
    finally:
        archive.unlink(missing_ok=True)


def input_identity(inputs, config):
    hashes = public().load_json(within(inputs, config.get("input_hashes", "input-hashes.json"), exists=True).read_bytes())
    if not hashes:
        raise ValueError("accepted original/tool inventory required")
    for name, expected in hashes.items():
        if name in {"work/config/local.json", "work/inventory/files.json"}:
            raise ValueError("update input-hashes must pin immutable originals/tools, not generated bookkeeping: " + name)
        path = within(inputs, name, exists=True)
        if not path.is_file() or RELEASE.digest(path) != expected:
            raise ValueError("owner input drift: " + name)
    # Private bindings and qualification pins affect output selection as well.
    return hashlib.sha256(RELEASE.signed_bytes({"inputs": hashes, "configuration": config})).hexdigest()


def changed_entries(release, cache, input_sha256):
    state = Path(cache) / "release-cache.json"
    old = public().load_json(state.read_bytes()) if state.exists() else {}
    entries = old.get("entries", {}) if old.get("input_sha256") == input_sha256 else {}
    changed = []
    for name, dependencies in sorted(release["entries"].items()):
        prior = entries.get(name, {})
        path = within(cache, name)
        if prior.get("dependencies") != dependencies or not path.is_file() or RELEASE.digest(path) != prior.get("sha256"):
            changed.append(name)
    return changed


def installed_changes(release, request, inputs):
    path = Path(inputs) / "installed-release.json"
    installed = public().load_json(path.read_bytes()) if path.exists() else {}
    previous = installed.get("release", {})
    known = installed.get("application_id") == request["application_id"] and installed.get("version_code") == request["installed_version"]
    if (
        not known
        or previous.get("application_id") != request["application_id"]
        or previous.get("version_code") != request.get("installed_release_version", previous.get("version_code"))
    ):
        previous = {}
        known = False
    entries = previous.get("entries", {})
    return {
        "changed_entries": sorted(name for name, hashes in release["entries"].items() if entries.get(name) != hashes),
        "removed_entries": sorted(set(entries) - set(release["entries"])),
        "installed_manifest_known": known,
    }


def assemble_sign(release, outputs, inputs, config, runtime, native, repo, work, context, emit, *, flow=None, issued=None, binding=None, retention_policy=None):
    """Use the existing complete-input APK assembler and durable owner signer."""
    ALPHA.code(issued)
    owner = module("update_owner_apk", repo / "tools/phone-build/owner-apk/build_owner_apk.py")
    sdk = module("update_sdk_package", repo / "tools/phone-build/accepted-output/sdk_package.py")
    code_names = owner.CODE_ENTRIES | sdk.SDK_ENTRIES
    if not {"apk/" + name for name in code_names} <= outputs.keys():
        raise ValueError("release lacks complete source-produced native/metadata/Burst and SDK outputs")
    selected = within(inputs, "work/releases/cache")
    for name, source in outputs.items():
        if Path(source).resolve(strict=True) != within(selected, name, exists=True):
            raise ValueError("assembly output map escapes verified incremental cache")
    # The existing assembler enumerates its pinned manifest, never directory
    # contents. Exact membership below excludes removed cached outputs without
    # copying multi-gigabyte reconstructed files to another staging tree.
    manifest, manifest_sha256 = within(inputs, config["manifest"]), owner.PROFILE
    if flow is not None:
        provision = module("owner_install_inputs", HERE / "install_inputs.py")
        manifest, manifest_sha256 = provision.assembly_profile(outputs, inputs, release)
    assembly = {
        "manifest": str(manifest),
        "manifest_sha256": manifest_sha256,
        "targets": str(selected),
        "code": {name: str(selected / "apk" / name) for name in code_names},
        "frontend": str(repo / "launcher"),
        "wire_helper": str(repo / "scripts/lab/phone_apk.py"),
        "java": str(native / "libjavatool.so"),
        "javac": str(native / "libjavactool.so"),
        "android_jar": str(runtime / "java-tools/android.jar"),
        "d8_jar": str(runtime / "java-tools/d8.jar"),
        "version_code": issued,
        "application_id": ALPHA.APPLICATION_ID,
        "retention_policy": retention_policy,
    }
    if "drift" in config:
        assembly["drift"] = {
            entry: {kind: {**pin, "path": str(within(inputs, pin["path"], exists=True))} for kind, pin in evidence.items()}
            for entry, evidence in config["drift"].items()
        }
    reuse_apk = (
        flow is not None and flow.reusable("apk") and flow.row("apk").get("input_sha256") == manifest_sha256 and flow.row("apk").get("version_code") == issued
    )
    if reuse_apk:
        work = within(inputs, flow.row("apk")["work"], exists=True)
    if flow is not None:
        flow.begin("apk")
    try:
        readiness = owner.check(assembly)
        expected = {row["path"] for row in readiness["entries"]}
        if set(outputs) != expected:
            raise ValueError("release output membership differs from complete APK/payload assembly profile")
        write_json(work / "readiness.json", readiness)
        if not readiness["assembly_ready"]:
            raise ValueError("source production incomplete; see private readiness.json")
        if not reuse_apk:
            write_json(work / "assembly-request.json", assembly)
            owner.build(work / "assembly-request.json", work / "assembly")
            if flow is not None:
                flow.row("signing")["status"] = "pending"
                flow.row("signing").pop("artifacts", None)
        if flow is not None:
            flow.row("apk").update(work=work.relative_to(inputs).as_posix(), input_sha256=manifest_sha256, version_code=issued)
            flow.artifacts("apk", [work / "assembly/owner-unsigned.apk"])
            flow.complete("apk")
    except Exception as error:
        if flow is not None:
            flow.fail(error)
        raise
    if reuse_apk and flow is not None and flow.reusable("signing"):
        return public().load_json((work / "signing-ready.json").read_bytes())
    emit("SIGNING", "Signing locally with the retained private owner key.")
    signing = {
        "unsigned": str(work / "assembly/owner-unsigned.apk"),
        "java": str(native / "libjavatool.so"),
        "keytool": str(native / "libkeytool.so"),
        "zipalign": str(native / "libzipalign.so"),
        "apksigner_jar": str(runtime / "java-tools/apksigner.jar"),
        "key_directory": str(within(inputs, config["key_directory"])),
    }

    def sign():
        # Each failed attempt is retained; the durable owner key is never moved.
        output = work / "signing"
        if output.exists():
            output = work / ("signing-" + next(tempfile._get_candidate_names()))
        result = RELEASE.sign_release(owner, release, signing, output, **context, install_version_code=issued)
        ready = {
            "apk": str(output / "signed.apk"),
            "sha256": result["apk_sha256"],
            "bytes": result["apk_bytes"],
            "application_id": release["application_id"],
            "version_code": issued,
            "release": release,
            "signer_sha256": result["signer_sha256"],
            **binding,
            "payload_sha256": payload_identity(output / "signed.apk"),
        }
        ALPHA.bind(
            within(inputs, "work/releases"), issued, apk_sha256=ready["sha256"], payload_sha256=ready["payload_sha256"], signer_sha256=ready["signer_sha256"]
        )
        if flow is not None:
            write_json(work / "signing-ready.json", ready)
            flow.artifacts("signing", [output / "signed.apk", work / "signing-ready.json"])
        return ready

    return flow.perform("signing", sign) if flow is not None else sign()


def payload_identity(apk):
    """Hash the embedded manifest which binds every retained payload byte."""
    with zipfile.ZipFile(apk) as archive:
        row = archive.getinfo("assets/owner-bootstrap/payload-index.json")
        if row.file_size > MAX_METADATA:
            raise ValueError("bounded retained payload manifest required")
        with archive.open(row) as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()


def toolchain_identity(runtime, native):
    """Bind the actual assembly/signing executables, not a wall-clock or Git order."""
    paths = {"java-tools/" + name: Path(runtime) / "java-tools" / name for name in ("android.jar", "d8.jar", "apksigner.jar")}
    paths.update({"native/" + name: Path(native) / name for name in ("libjavatool.so", "libjavactool.so", "libkeytool.so", "libzipalign.so")})
    return ALPHA.fingerprint({name: RELEASE.digest(path) for name, path in paths.items()})


def prune_releases(inputs):
    """Keep current + previous + active signed APKs; drop only generated copies.

    Receipt/log metadata stays. No source/input/profile paths are ever enumerated.
    A legacy or corrupt receipt stops pruning rather than risking its last APK.
    """
    root = within(inputs, "work/releases")
    if not root.exists():
        return
    keep = set()
    for name in ("installed-release.json", "previous-installed-release.json", "owner-apk-ready.json"):
        path = within(inputs, name)
        if not path.exists():
            continue
        receipt = public().load_json(path.read_bytes())
        if "apk" not in receipt:
            return
        keep.add(ALPHA.retained(inputs, receipt, installed=name != "owner-apk-ready.json"))
    for work in root.iterdir():
        if not work.name.startswith(("build-", "rollback-")) or work.is_symlink() or not work.is_dir():
            continue
        for path in work.rglob("*.apk"):
            if path.name not in {"owner-unsigned.apk", "rollback-unsigned.apk", "aligned.apk", "signed.apk"}:
                continue
            if path.resolve() != path or path in keep or not path.is_file():
                continue
            path.unlink()


def prepare_rollback(inputs, runtime, native, request, trust, config, emit):
    current = public().load_json(within(inputs, "installed-release.json", exists=True).read_bytes())
    previous = public().load_json(within(inputs, "previous-installed-release.json", exists=True).read_bytes())
    source = ALPHA.rollback(inputs, current, previous, request["installed_version"])
    if payload_identity(source) != ALPHA.sha256(previous["payload_sha256"]):
        raise ValueError("retained embedded payload manifest differs")
    release = public().verify_envelope(previous["envelope"], trust["keys"])
    if release != previous["release"]:
        raise ValueError("retained source manifest differs from publisher signature")
    public().validate_alpha_release(release)
    RELEASE.validate(release, request["installer_version"], ALPHA.APPLICATION_ID, 0)
    keys = within(inputs, config["key_directory"])
    if not all((keys / name).is_file() for name in ("owner.p12", "password")):
        raise ValueError("owner key lost: restore the same private key; rollback refused")
    # Retained embedded bytes constitute the exact compatible source/payload set.
    # Original input is not read or recopied for this forward-version operation.
    binding = {
        "source_sha256": ALPHA.fingerprint(release),
        "input_sha256": ALPHA.sha256(previous["input_sha256"]),
        "toolchain_sha256": toolchain_identity(runtime, native),
        "publisher_version_code": release["version_code"],
        "purpose": "rollback",
    }
    issued = ALPHA.reserve(within(inputs, "work/releases"), installed_version=request["installed_version"], binding=binding)
    (inputs / "owner-apk-ready.json").unlink(missing_ok=True)
    prune_releases(inputs)
    work = Path(tempfile.mkdtemp(prefix="rollback-", dir=within(inputs, "work/releases")))
    owner = module("rollback_owner_apk", HERE / "build_owner_apk.py")
    emit("BUILDING", "Preparing the retained compatible release; game profile/settings stay in place.")
    unsigned = work / "rollback-unsigned.apk"
    owner.reversion(source, unsigned, wire_helper=HERE.parents[2] / "scripts/lab/phone_apk.py", version_code=issued, expected_sha256=previous["sha256"])
    signing = {
        "unsigned": str(unsigned),
        "java": str(native / "libjavatool.so"),
        "keytool": str(native / "libkeytool.so"),
        "zipalign": str(native / "libzipalign.so"),
        "apksigner_jar": str(runtime / "java-tools/apksigner.jar"),
        "key_directory": str(keys),
    }
    emit("SIGNING", "Signing retained content with the same private owner key and a higher version.")
    result = RELEASE.sign_release(
        owner,
        release,
        signing,
        work / "signing",
        installer_version=request["installer_version"],
        application_id=ALPHA.APPLICATION_ID,
        installed_version=request["installed_version"],
        install_version_code=issued,
    )
    if toolchain_identity(runtime, native) != binding["toolchain_sha256"]:
        raise ValueError("owner toolchain changed during rollback")
    if result["signer_sha256"] != current["signer_sha256"]:
        raise ValueError("owner signer differs from retained installation; rollback refused")
    ready = {
        "apk": str(work / "signing/signed.apk"),
        "sha256": result["apk_sha256"],
        "bytes": result["apk_bytes"],
        "application_id": ALPHA.APPLICATION_ID,
        "version_code": issued,
        "release": release,
        "envelope": previous["envelope"],
        "signer_sha256": result["signer_sha256"],
        "payload_sha256": ALPHA.sha256(previous["payload_sha256"]),
        **binding,
    }
    ALPHA.bind(
        within(inputs, "work/releases"), issued, apk_sha256=ready["sha256"], payload_sha256=ready["payload_sha256"], signer_sha256=ready["signer_sha256"]
    )
    return ready


def _run(request_file, runtime, native, *, transport=None, debuggable=False):
    request_file, runtime, native = (Path(value).resolve(strict=True) for value in (request_file, runtime, native))
    inputs = request_file.parent
    flow = None
    update_state = {}

    def emit(state, message, **extra):
        update_state.clear()
        update_state.update(state=state, message=message, **extra)
        if flow is not None:
            update_state["pipeline"] = flow.snapshot()
        write_json(inputs / "update-state.json", update_state)

    def progress(value):
        update_state["pipeline"] = value
        write_json(inputs / "update-state.json", update_state)

    try:
        request = public().load_json(request_file.read_bytes())
        if set(request) - {"installer_package", "installer_signer_sha256"} != {
            "action",
            "application_id",
            "installed_version",
            "installed_release_version",
            "installer_version",
        } or request["action"] not in {
            "release-check",
            "release-build",
            "install-prepare",
            "release-rollback",
        }:
            raise ValueError("explicit trusted installer action/context required")
        ALPHA.identity(request["application_id"])
        trust = public().load_json((runtime / "release-trust.json").read_bytes())
        if (
            set(trust) != {"repository", "application_id", "keys"}
            or trust["application_id"] != request["application_id"]
            or not isinstance(trust["keys"], dict)
        ):
            raise ValueError("publisher trust is not provisioned in this installer")
        override_path = inputs / "debug-release-source.json"
        override = None
        if override_path.exists():
            if debuggable is not True:
                raise ValueError("test release source and publisher key are forbidden in release builds")
            override = public().load_json(override_path.read_bytes())
        trust, debug_transport = SOURCE.configure(trust, override, debuggable=debuggable, validate_public_key=public().public_numbers)
        if not trust["keys"]:
            raise ValueError("publisher trust is not provisioned in this installer")
        transport = debug_transport or transport or GitHubTransport(trust["repository"])
        context = {key: request[key] for key in ("application_id", "installed_version", "installer_version")}
        cache = within(inputs, "work/releases/cache")
        candidate_path = inputs / "release-candidate.json"
        config_path = inputs / "update-config.json"
        config = public().load_json(config_path.read_bytes()) if config_path.exists() else {}
        if set(config) - {"input_hashes", "manifest", "key_directory", "bindings", "drift"}:
            raise ValueError("unknown private update configuration")
        prune_releases(inputs)
        if request["action"] == "release-rollback":
            ready = prepare_rollback(inputs, runtime, native, request, trust, config, emit)
            write_json(inputs / "owner-apk-ready.json", ready)
            prune_releases(inputs)
            emit(
                "READY",
                "Retained release rebuilt with the same key and a higher install code; Android consent required.",
                release=ready["release"],
                rollback=True,
            )
            return
        emit("CHECKING", "Checking the signed public release.")
        if request["action"] == "release-check" or not candidate_path.exists():
            candidate = latest(transport, trust["keys"])
        else:
            candidate = public().load_json(candidate_path.read_bytes())
            verified = public().verify_envelope(candidate["envelope"], trust["keys"])
            if candidate["release"] != verified:
                raise ValueError("stored candidate differs from signed release")
            transport.asset_url(candidate["bundle"]["url"], "public-tools.zip")
        release = candidate["release"]
        verify_context(release, request)
        if release["version_code"] == request.get("installed_release_version", 0):
            emit("UP_TO_DATE", "The installed game is up to date.", release=release)
            return
        write_json(candidate_path, candidate)
        # Checking availability never depends on still-mounted owner originals.
        # A build establishes identity only after signed-plan admission below.
        identity = None
        changed = changed_entries(release, cache, identity) if identity else sorted(release["entries"])
        differences = installed_changes(release, request, inputs)
        if request["action"] == "release-check":
            emit("UPDATE_AVAILABLE", "Signed update available; game files will be rebuilt locally.", release=release, rebuild_entries=changed, **differences)
            return
        verify_context(release, request, require_new=True)
        keys = within(inputs, config["key_directory"]) if "key_directory" in config else None
        if context["installed_version"] and keys is not None and not all((keys / name).is_file() for name in ("owner.p12", "password")):
            raise ValueError("owner key lost: restore the same private key; update refused")
        (inputs / "owner-apk-ready.json").unlink(missing_ok=True)
        prune_releases(inputs)
        repo, index = acquire(candidate, within(inputs, "work/releases/downloads"), transport, emit)
        if "install_plan" in index:
            provision = module("owner_install_inputs", HERE / "install_inputs.py")
            description = provision.describe(index, repo, inputs)
            if request["action"] == "install-prepare":
                emit("INPUTS_REQUIRED", "Choose your legitimate game folder or ZIP to import privately.", import_requirements=description, release=release)
                return
            pipeline = module("owner_install_flow", HERE / "install_flow.py")
            flow = pipeline.Pipeline(inputs, release, description["manifest_sha256"], index["install_plan"], emit=progress)

            def admit():
                admitted = provision.prepare(index, repo, inputs)
                if "key_directory" in config:
                    # A signed recipe selects inputs, never a replacement signer.
                    # Retain the previously provisioned #159 private key location.
                    within(inputs, config["key_directory"])
                    admitted["key_directory"] = config["key_directory"]
                keys = within(inputs, admitted["key_directory"])
                if context["installed_version"] and not all((keys / name).is_file() for name in ("owner.p12", "password")):
                    raise ValueError("owner key lost: restore the same private key; update refused")
                if shutil.disk_usage(inputs).free < index["install_plan"]["workspace_bytes"] + 2 * 1024**3:
                    raise ValueError("insufficient private storage for reconstruction and safety reserve")
                write_json(config_path, admitted)
                return admitted, input_identity(inputs, admitted)

            config, identity = flow.perform("admission", admit)
        elif request["action"] == "install-prepare":
            raise ValueError("release lacks a reviewed signed phone install plan")
        elif config:
            identity = input_identity(inputs, config)
        if not {"manifest", "key_directory"} <= config.keys() or identity is None:
            raise ValueError("owner inputs and assembly configuration are not provisioned")
        binding = {
            "source_sha256": ALPHA.fingerprint(release),
            "input_sha256": identity,
            "toolchain_sha256": toolchain_identity(runtime, native),
            "publisher_version_code": release["version_code"],
            "purpose": "update",
        }
        issued = ALPHA.reserve(within(inputs, "work/releases"), installed_version=context["installed_version"], binding=binding)
        retention_policy = {
            "schema": 1,
            "installer_package": request.get("installer_package"),
            "installer_certificate_sha256": ALPHA.sha256(request.get("installer_signer_sha256")),
            "data_schema": release["data_schema"],
        }
        jobs = module("owner_update_jobs", HERE / "release_jobs.py")

        def stage():
            dispatcher = jobs.Dispatcher(repo, index, release, inputs, runtime, native, config, identity)
            if flow is not None:
                pipeline.validate_plan(index["install_plan"], index, dispatcher.descriptor)
                dispatcher.verify_sources(index["files"])
            return dispatcher

        dispatcher = flow.perform("staging", stage) if flow is not None else stage()
        emit("BUILDING", "Rebuilding changed files from verified owner inputs.", release=release, rebuild_entries=changed, **differences)
        if flow is not None:
            job_stages = pipeline.validate_plan(index["install_plan"], index, dispatcher.descriptor)
            completed = set()

            def produced(name, reused):
                if reused is not None:
                    completed.add(name)
                current = flow.state["current_stage"]
                flow.progress(sum(job_stages[job] == current for job in completed))

            dispatcher.progress = produced
            for row in index["install_plan"]["stages"]:
                if row["id"] in pipeline.PRODUCTION:
                    flow.perform(row["id"], lambda row=row: [dispatcher.execute(name) for name in row["jobs"]])
            flow.begin("apk")
        result = RELEASE.rebuild(release, **dict(context, installed_version=0), input_sha256=identity, root=cache, produce=dispatcher.produce)
        if input_identity(inputs, config) != identity:
            raise ValueError("owner inputs changed during update")
        work = Path(tempfile.mkdtemp(prefix="build-", dir=cache.parent))
        ready = assemble_sign(
            release,
            result["outputs"],
            inputs,
            config,
            runtime,
            native,
            repo,
            work,
            context,
            emit,
            flow=flow,
            issued=issued,
            binding=binding,
            retention_policy=retention_policy,
        )
        ready["envelope"] = candidate["envelope"]
        if input_identity(inputs, config) != identity:
            raise ValueError("owner inputs changed during signing")
        if toolchain_identity(runtime, native) != binding["toolchain_sha256"]:
            raise ValueError("owner toolchain changed during update")
        write_json(inputs / "owner-apk-ready.json", ready)
        prune_releases(inputs)
        if flow is not None:
            flow.await_install()
        emit("READY", "Owner-built update is ready for Android installation consent.", release=release, rebuilt=result["rebuilt"], reused=result["reused"])
    except Exception as error:
        if flow is not None and flow.state["status"] != "failed":
            flow.fail(error)
        try:
            emit("ERROR", str(error))
        except OSError:
            pass  # Reporting cannot overwrite the original ENOSPC/failure.
        raise


def run(request_file, runtime, native, *, transport=None, debuggable=False):
    """Hold an OS-owned lock across children; process death releases it safely."""
    lock = Path(request_file).resolve(strict=True).parent / ".release-update.lock"
    if lock.is_symlink():
        raise ValueError("update lock cannot be a symlink")
    with lock.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("an owner update is already running") from error
        previous = os.environ.get("ROR2_OWNER_UPDATE_LOCK_FD")
        os.environ["ROR2_OWNER_UPDATE_LOCK_FD"] = str(stream.fileno())
        try:
            _run(request_file, runtime, native, transport=transport, debuggable=debuggable)
        finally:
            if previous is None:
                os.environ.pop("ROR2_OWNER_UPDATE_LOCK_FD", None)
            else:
                os.environ["ROR2_OWNER_UPDATE_LOCK_FD"] = previous


if __name__ == "__main__":
    run(*sys.argv[1:], debuggable=os.environ.get("ROR2_INSTALLER_DEBUGGABLE") == "1")
