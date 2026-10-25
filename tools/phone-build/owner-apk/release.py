"""Public release contract and owner-local incremental production.

The installer verifies the signature before passing the release body here.
Entries describe public transformation dependencies, never downloadable game bytes.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath
import os


def signed_bytes(release):
    """Bytes signed by the publisher and verified by the installer trust key."""
    return json.dumps(release, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(release, installer_version, application_id, installed_version):
    if set(release) != {"version", "version_code", "application_id", "minimum_installer_version", "bundle_sha256", "entries"}:
        raise ValueError("explicit release fields required")
    if not isinstance(release["version"], str) or not release["version"].strip():
        raise ValueError("release version required")
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
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name or len(path.parts) < 2 or path.parts[0] not in {"apk", "payload"}:
            raise ValueError("relative apk/ or payload/ output required")
        if set(row) != {"recipe_sha256", "producer_sha256"}:
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
    root.mkdir(parents=True, exist_ok=True)
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
            output.parent.mkdir(parents=True, exist_ok=True)
            stage = output.with_name(output.name + ".building")
            stage.unlink(missing_ok=True)
            produce(name, dependencies, stage)
            if not stage.is_file():
                raise ValueError("producer did not produce entry: " + name)
            stage.replace(output)
            changed.append(name)
        rows[name] = {"dependencies": dict(dependencies), "sha256": digest(output)}
    result = {"input_sha256": input_sha256, "entries": rows}
    stage = state.with_suffix(".building")
    stage.write_text(json.dumps(result, sort_keys=True) + "\n")
    stage.replace(state)
    return {"rebuilt": changed, "reused": sorted(set(rows) - set(changed)), "outputs": {name: str(root / name) for name in rows}}


def sign_release(owner, release, signing_request, output, *, installer_version, application_id, installed_version):
    """Sign an assembled release with the existing owner; never replace lost keys.

    The installer supplies actual installed identity/version and assembles using
    release.version_code before calling. Installation remains its responsibility.
    """
    validate(release, installer_version, application_id, installed_version)
    request = dict(signing_request)
    keys = Path(request["key_directory"])
    if installed_version and not all((keys / name).is_file() for name in ("owner.p12", "password")):
        raise ValueError("owner key lost: export saves and reinstall; update refused")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    request_path = output.with_name(output.name + "-request.json")
    with request_path.open("x") as stream:
        json.dump(request, stream)
    # The existing signer checks private custody, key continuity and APK content.
    result = owner.sign(request_path, output)
    os.chmod(request_path, 0o600)
    return result
