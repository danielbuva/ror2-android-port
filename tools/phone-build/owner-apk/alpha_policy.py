"""Private alpha identity, durable issued codes and retained-release admission.

Publisher version ordering is independent of Android install codes. A reserved
code is permanently burned, including process death/cancellation before signing.
Only metadata and references live here; game profile/data is never copied.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

APPLICATION_ID = "dev.ror2lab.alpha"
MAX_VERSION_CODE = 2100000000


def code(value, *, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= MAX_VERSION_CODE:
        raise ValueError("alpha versionCode must be positive and at most 2100000000")
    return value


def identity(value):
    if value != APPLICATION_ID:
        raise ValueError("final alpha applicationId must be dev.ror2lab.alpha")


def sha256(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("SHA-256 identity required")
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def data_schema(value):
    if not isinstance(value, dict) or set(value) != {"writes", "reads"}:
        raise ValueError("signed data-schema writes/reads declaration required")
    writes, reads = value["writes"], value["reads"]
    if type(writes) is not int or writes < 1 or not isinstance(reads, list) or not reads:
        raise ValueError("positive data schema and nonempty readable schemas required")
    if any(type(item) is not int or item < 1 for item in reads) or len(set(reads)) != len(reads) or writes not in reads:
        raise ValueError("distinct positive readable schemas including written schema required")
    return value


def compatible(target, current):
    target, current = data_schema(target), data_schema(current)
    if current["writes"] not in target["reads"]:
        raise ValueError("retained release cannot read current profile/settings schema; rollback refused")


def write_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("owner ledger cannot be redirected")
    fd, temporary = tempfile.mkstemp(prefix=".issued-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _change(root, action, *, require_existing=False):
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("canonical private issued-version directory required")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path, lock = root / "issued-versions.json", root / ".issued-versions.lock"
    if path.is_symlink() or lock.is_symlink():
        raise ValueError("owner ledger cannot be redirected")
    with lock.open("a") as stream:
        os.chmod(lock, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        if require_existing and not path.is_file():
            raise ValueError("issued-version ledger lost; restore owner receipt before updating")
        state = json.loads(path.read_text()) if path.exists() else {"schema": 1, "application_id": APPLICATION_ID, "last_issued": 0, "issues": {}}
        if set(state) != {"schema", "application_id", "last_issued", "issues"} or state["schema"] != 1:
            raise ValueError("issued-version ledger is invalid; never reset it")
        identity(state["application_id"])
        code(state["last_issued"], zero=True)
        if not isinstance(state["issues"], dict):
            raise ValueError("issued-version ledger is invalid; never reset it")
        for number, row in state["issues"].items():
            if str(code(int(number))) != number or int(number) > state["last_issued"] or not isinstance(row, dict):
                raise ValueError("issued-version ledger is inconsistent")
        result = action(state)
        write_json(path, state)
        return result


def reserve(root, *, installed_version, binding):
    """Persist the high-water mark before returning; callers must never undo it."""
    code(installed_version, zero=True)
    if set(binding) != {"source_sha256", "input_sha256", "toolchain_sha256", "publisher_version_code", "purpose"}:
        raise ValueError("source/input/toolchain/publisher binding required before issuing")
    for name in ("source_sha256", "input_sha256", "toolchain_sha256"):
        sha256(binding[name])
    code(binding["publisher_version_code"])
    if binding["purpose"] not in {"update", "rollback"}:
        raise ValueError("explicit issue purpose required")

    def allocate(state):
        issued = max(installed_version, state["last_issued"]) + 1
        code(issued)  # Exhaustion is refusal, never wrap/reuse.
        state["last_issued"] = issued
        state["issues"][str(issued)] = {"status": "reserved", **binding}
        return issued

    return _change(root, allocate, require_existing=installed_version > 0)


def bind(root, issued, *, apk_sha256, payload_sha256, signer_sha256):
    code(issued)
    result = {name: sha256(value) for name, value in dict(apk_sha256=apk_sha256, payload_sha256=payload_sha256, signer_sha256=signer_sha256).items()}

    def finish(state):
        row = state["issues"].get(str(issued))
        if row is None or row.get("status") != "reserved":
            raise ValueError("unbound reserved version required; issued codes cannot be reused")
        row.update(status="signed", **result)

    _change(root, finish)


def retained(inputs, receipt, *, installed_version=None, installed=False):
    """Validate one immutable APK reference without copying its embedded payload."""
    inputs = Path(inputs).resolve(strict=True)
    identity(receipt.get("application_id"))
    version = code(receipt.get("version_code"))
    if (installed or installed_version is not None) and receipt.get("installed_readback_verified") is not True:
        raise ValueError("verified installed-release receipt required")
    if installed_version is not None and version != installed_version:
        raise ValueError("local ownership receipt differs from installed version")
    release = receipt.get("release", {})
    identity(release.get("application_id"))
    data_schema(release.get("data_schema"))
    sha256(receipt.get("signer_sha256"))
    sha256(receipt.get("sha256"))
    apk = Path(receipt.get("apk", ""))
    if not apk.is_absolute() or apk.resolve(strict=True) != apk or not apk.is_relative_to(inputs / "work/releases") or not apk.is_file():
        raise ValueError("retained signed APK must remain under private release storage")
    if type(receipt.get("bytes")) is not int or apk.stat().st_size != receipt["bytes"]:
        raise ValueError("retained signed APK size differs")
    with apk.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != receipt["sha256"]:
            raise ValueError("retained signed APK hash differs")
    return apk


def rollback(inputs, current, previous, installed_version):
    retained(inputs, current, installed_version=installed_version)
    source = retained(inputs, previous, installed=True)
    if current["signer_sha256"] != previous["signer_sha256"]:
        raise ValueError("retained release requires a different owner key; rollback refused")
    compatible(previous["release"]["data_schema"], current["release"]["data_schema"])
    return source
