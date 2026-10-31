"""Public release contract and owner-local incremental production.

The installer verifies the signature before passing the release body here.
Entries describe public transformation dependencies, never downloadable game bytes.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath
import os
import re
import tempfile
import importlib.util

_atomic_spec = importlib.util.spec_from_file_location("owner_atomic_io", Path(__file__).with_name("atomic_io.py"))
ATOMIC = importlib.util.module_from_spec(_atomic_spec)
_atomic_spec.loader.exec_module(ATOMIC)


_spec = importlib.util.spec_from_file_location("owner_alpha_policy", Path(__file__).with_name("alpha_policy.py"))
ALPHA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ALPHA)


def signed_bytes(release):
    """Bytes signed by the publisher and verified by the installer trust key."""
    return json.dumps(release, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(release, installer_version, application_id, installed_version):
    if not isinstance(release, dict) or set(release) - {"data_schema"} != {
        "version",
        "version_code",
        "application_id",
        "minimum_installer_version",
        "bundle_sha256",
        "entries",
    }:
        raise ValueError("explicit release fields required")
    if "data_schema" in release:
        ALPHA.data_schema(release["data_schema"])
    if not isinstance(release["version"], str) or not release["version"].strip():
        raise ValueError("release version required")
    if not isinstance(release["application_id"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", release["application_id"]):
        raise ValueError("Android applicationId required")
    if release["application_id"] != application_id:
        raise ValueError("release applicationId differs")
    code, minimum = release["version_code"], release["minimum_installer_version"]
    if type(code) is not int or not 1 <= code <= 2100000000 or code <= installed_version:
        raise ValueError("release versionCode must increase within Android bounds")
    if type(minimum) is not int or not 1 <= minimum <= installer_version:
        raise ValueError("installer upgrade required")
    if not isinstance(release["entries"], dict) or not release["entries"]:
        raise ValueError("release entries required")
    bundle = release["bundle_sha256"]
    if not isinstance(bundle, str) or len(bundle) != 64 or any(c not in "0123456789abcdef" for c in bundle):
        raise ValueError("public tools bundle SHA-256 required")
    for name, row in release["entries"].items():
        if not isinstance(name, str) or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise ValueError("relative apk/ or payload/ output required")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name or len(path.parts) < 2 or path.parts[0] not in {"apk", "payload"}:
            raise ValueError("relative apk/ or payload/ output required")
        if any(str(parent) in release["entries"] for parent in path.parents) or name + ".building" in release["entries"]:
            raise ValueError("overlapping release output paths")
        if not isinstance(row, dict) or set(row) != {"recipe_sha256", "producer_sha256"}:
            raise ValueError("entry dependency hashes required")
        for value in row.values():
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("SHA-256 dependency hash required")


def rebuild(release, *, installer_version, application_id, installed_version, input_sha256, root, produce):
    """Rebuild changed entries using existing source-only producer callbacks.

    produce(name, dependency_hashes, destination) must produce the complete file
    from legitimate originals. The installer dispatches it to the named existing
    producer after verifying its acquired recipe/tool hashes. A hash covers the
    entire dependency closure, including shared tools/configuration. The input
    hash is the accepted original-file inventory. Cache is private app data.
    """
    validate(release, installer_version, application_id, installed_version)
    root = Path(root).resolve()
    ATOMIC.mkdirs(root)
    state = root / "release-cache.json"
    previous = json.loads(state.read_text()) if state.exists() else {}
    old = previous.get("entries", {}) if previous.get("input_sha256") == input_sha256 else {}
    rows, changed = {}, []
    for name, dependencies in sorted(release["entries"].items()):
        output = root / name
        if not output.resolve().is_relative_to(root):
            raise ValueError("output escapes owner cache")
        cached = old.get(name, {})
        if cached.get("dependencies") != dependencies or not output.is_file() or digest(output) != cached.get("sha256"):
            ATOMIC.mkdirs(output.parent)
            stage = output.with_name(output.name + ".building")
            stage.unlink(missing_ok=True)
            try:
                produce(name, dependencies, stage)
                if stage.is_symlink() or not stage.is_file():
                    raise ValueError("producer did not produce entry: " + name)
                ATOMIC.publish(stage, output)
            finally:
                ATOMIC.discard(stage)
            changed.append(name)
        rows[name] = {"dependencies": dict(dependencies), "sha256": digest(output)}
        # Each verified output is independently resumable after the next producer
        # fails or is killed; stale/unvisited entries are never granted reuse.
        ATOMIC.write_json(state, {"input_sha256": input_sha256, "entries": rows})
    return {"rebuilt": changed, "reused": sorted(set(rows) - set(changed)), "outputs": {name: str(root / name) for name in rows}}


def sign_release(owner, release, signing_request, output, *, installer_version, application_id, installed_version, install_version_code=None):
    """Sign an assembled release with the existing owner; never replace lost keys.

    The installer supplies actual installed identity/version and assembles using
    a separately issued install_version_code before calling. Installation remains
    its responsibility; publisher ordering is never Android install ordering.
    """
    validate(release, installer_version, application_id, 0 if install_version_code is not None else installed_version)
    if install_version_code is not None:
        ALPHA.identity(application_id)
        if ALPHA.code(install_version_code) <= ALPHA.code(installed_version, zero=True):
            raise ValueError("issued install version must increase")
    request = dict(signing_request)
    keys = Path(request["key_directory"])
    if installed_version and not all((keys / name).is_file() for name in ("owner.p12", "password")):
        raise ValueError("owner key lost: restore the same private key; update refused")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=output.name + "-request-", suffix=".json", dir=output.parent)
    request_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(request, stream)
        # The existing signer checks private custody, key continuity and APK content.
        return owner.sign(request_path, output)
    finally:
        request_path.unlink(missing_ok=True)
