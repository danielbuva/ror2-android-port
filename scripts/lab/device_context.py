"""Pure device selection and per-device state addressing helpers.

This module deliberately knows nothing about ADB. Callers provide an attached
device inventory and perform any device operations only after selection.
"""

import json
import hashlib
import os
from pathlib import Path
import re
import shutil


_SERIAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_STORAGE_MODES = {"adopted", "internal"}
ACTIVATION_MARKER = ".device-context-active.json"
MIGRATED_RECEIPTS = ("installed.json", "storage.json", "runtime.json", "last-run.json", "sync.json", "diagnostics.json")
_COMMAND_SELECTORS = None


def set_command_selector(cli_selector, env_selector):
    """Freeze CLI/environment selectors for one parsed command invocation."""
    global _COMMAND_SELECTORS
    _COMMAND_SELECTORS = (cli_selector, env_selector)
    return _COMMAND_SELECTORS


def command_selectors():
    """Return frozen command selectors, or read LAB_DEVICE before CLI setup."""
    if _COMMAND_SELECTORS is not None:
        return _COMMAND_SELECTORS
    return (None, os.environ.get("LAB_DEVICE"))


class DeviceContextError(ValueError):
    """A selector, device inventory, storage profile, or migration is unsafe."""


def validate_serial(serial):
    """Return a serial safe as one directory segment, rejecting path syntax."""
    if not isinstance(serial, str) or not _SERIAL.fullmatch(serial):
        raise DeviceContextError("Device serial is not a safe path segment")
    return serial


def select_device(configuration, attached, *, env_selector=None, cli_selector=None):
    """Select the configured device or an explicitly allowlisted override.

    ``attached`` is an iterable of mappings containing ``serial`` and ``state``
    fields, usually captured by an outer device transport layer. This function
    does not discover devices or run commands.
    """
    if not isinstance(configuration, dict):
        raise DeviceContextError("Device configuration must be an object")

    default_serial = validate_serial(configuration.get("device_serial"))
    allowlist = configuration.get("device_serials")
    if allowlist is not None:
        if not isinstance(allowlist, list):
            raise DeviceContextError("device_serials must be a list")
        validated_allowlist = [validate_serial(value) for value in allowlist]
        if len(set(validated_allowlist)) != len(validated_allowlist):
            raise DeviceContextError("device_serials must not contain duplicates")
        if default_serial not in validated_allowlist:
            raise DeviceContextError("Configured default device_serial must be in device_serials")
    if env_selector is not None and cli_selector is not None and env_selector != cli_selector:
        raise DeviceContextError("LAB_DEVICE and --device select different devices")

    selector = cli_selector if cli_selector is not None else env_selector
    if selector is None:
        selector = default_serial
    else:
        selector = validate_serial(selector)
        if allowlist is None or selector not in validated_allowlist:
            raise DeviceContextError("Explicit device selector is not in device_serials allowlist")

    records = list(attached)
    if len(records) > 1 and env_selector is None and cli_selector is None:
        raise DeviceContextError("Multiple attached devices require an explicit selector")
    seen = set()
    authorized = []
    for record in records:
        if not isinstance(record, dict):
            raise DeviceContextError("Attached-device records must be objects")
        serial = validate_serial(record.get("serial"))
        if serial in seen:
            raise DeviceContextError("Attached-device inventory contains duplicate serials")
        seen.add(serial)
        if record.get("state") == "device":
            authorized.append(serial)

    if selector not in authorized:
        raise DeviceContextError("Selected device is not attached and authorized")
    return selector


def device_state_paths(work_root, serial):
    """Address a serial's receipts under an isolated work/device/<serial>/ tree."""
    root = Path(work_root) / "device" / validate_serial(serial)
    return {
        "root": root,
        "installed": root / "installed.json",
        "storage": root / "storage.json",
        "runtime": root / "runtime.json",
        "last_run": root / "last-run.json",
        "sync": root / "sync.json",
        "diagnostics": root / "diagnostics.json",
        "install_counter": root / "device-install-limit.json",
        "activation_marker": root / ACTIVATION_MARKER,
    }


def validate_receipt_directory(work_root, candidate):
    """Validate an existing-or-future receipt directory under ``work_root``.

    Symlinks are permitted in ancestors of the explicitly selected work root
    itself (for example macOS ``/var``), but never in the receipt tree below
    that root. Missing components are allowed so callers can validate a path
    before creating it.
    """
    base = Path(os.path.abspath(os.fspath(work_root)))
    target = Path(os.path.abspath(os.fspath(candidate)))
    try:
        relative = target.relative_to(base)
    except ValueError as exc:
        raise DeviceContextError("Receipt directory is outside the selected work root") from exc

    cursor = base
    try:
        for component in relative.parts:
            cursor = cursor / component
            if cursor.is_symlink():
                raise DeviceContextError("Receipt directory contains a symlink")
            if cursor.exists() and not cursor.is_dir():
                raise DeviceContextError("Receipt directory component is not a directory")
        resolved_base = base.resolve(strict=False)
        resolved_target = target.resolve(strict=False)
        if not resolved_target.is_relative_to(resolved_base):
            raise DeviceContextError("Resolved receipt directory is outside the selected work root")
    except OSError as exc:
        raise DeviceContextError("Receipt directory cannot be validated") from exc
    return target


def receipt_directory(work_root, context):
    """Resolve receipt storage without changing legacy Nova command behavior.

    ``context`` is the selected serial, or a mapping with ``serial`` and
    ``default_serial``. The default device keeps using ``work/device/`` until
    its migration transaction atomically publishes an activation marker.
    Every additional device always receives a serial-specific directory.
    """
    if isinstance(context, dict):
        serial = context.get("serial")
        default_serial = context.get("default_serial")
    else:
        serial = context
        default_serial = None
    serial = validate_serial(serial)
    root = Path(work_root) / "device"
    scoped = root / serial
    # Validate both legacy and scoped candidates before consulting a marker.
    # This also catches dangling links, which Path.exists() alone misses.
    validate_receipt_directory(work_root, root)
    validate_receipt_directory(work_root, scoped)
    if serial != default_serial:
        return validate_receipt_directory(work_root, scoped)
    marker = scoped / ACTIVATION_MARKER
    if marker.is_symlink():
        raise DeviceContextError("Scoped receipt activation marker is not a regular file")
    if marker.exists() and not marker.is_file():
        raise DeviceContextError("Scoped receipt activation marker is not a regular file")
    if marker.is_file():
        try:
            value = json.loads(marker.read_text())
            identity = value.get("identity") if isinstance(value, dict) else None
            hashes = value.get("sha256") if isinstance(value, dict) else None
            marker_digest = value.get("marker_sha256") if isinstance(value, dict) else None
            payload = {key: value[key] for key in ("version", "serial", "identity", "sha256")} if isinstance(value, dict) else None
            if (
                value.get("version") != 1
                or value.get("serial") != serial
                or not isinstance(identity, dict)
                or identity.get("serial") != serial
                or not identity.get("package")
                or not identity.get("package_path")
                or not identity.get("apk_sha256")
                or not isinstance(hashes, dict)
                or "installed.json" not in hashes
                or not isinstance(marker_digest, str)
                or _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()) != marker_digest
            ):
                raise ValueError("marker identity mismatch")
            for name, expected_hash in hashes.items():
                if name not in MIGRATED_RECEIPTS and name != "device-install-limit.json":
                    raise ValueError("marker contains an unknown receipt name")
                if not isinstance(expected_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
                    raise ValueError("marker contains an invalid hash")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError, KeyError, ValueError) as exc:
            raise DeviceContextError("Scoped receipt activation marker is invalid") from exc
        return validate_receipt_directory(work_root, scoped)
    return validate_receipt_directory(work_root, root)


def storage_policy(configuration, serial):
    """Return an explicit per-device storage mode; never infer from device name."""
    serial = validate_serial(serial)
    profiles = configuration.get("device_settings") if isinstance(configuration, dict) else None
    profile = profiles.get(serial) if isinstance(profiles, dict) else None
    mode = profile.get("storage_mode") if isinstance(profile, dict) else None
    if mode is None and isinstance(configuration, dict) and serial == configuration.get("device_serial"):
        mode = configuration.get("storage_mode")
    if mode not in _STORAGE_MODES:
        raise DeviceContextError("Selected device needs an explicit adopted/internal storage_mode")
    return mode


def plan_legacy_receipt_migration(source, target, *, serial, receipt, ownership_proof, coordination_lock):
    """Describe a safe copy-and-atomic-publish migration without performing it.

    The legacy source remains intact. This planner is separate from the explicit
    migration executor and is never invoked during selection or module import.
    """
    serial = validate_serial(serial)
    if Path(coordination_lock).exists():
        raise DeviceContextError("Legacy receipt migration is blocked while the coordination lock exists")
    if not isinstance(ownership_proof, dict):
        raise DeviceContextError("Legacy receipt migration requires ownership proof")
    if not isinstance(receipt, dict):
        raise DeviceContextError("Legacy receipt must be an object")
    if receipt.get("serial") != serial:
        raise DeviceContextError("Legacy receipt serial does not match selected device")
    if not receipt.get("package") or not receipt.get("package_path") or not receipt.get("apk_sha256"):
        raise DeviceContextError("Legacy receipt lacks package placement ownership identity")
    identity = {key: receipt[key] for key in ("serial", "package", "package_path", "apk_sha256")}
    if any(ownership_proof.get(key) != value for key, value in identity.items()):
        raise DeviceContextError("Ownership proof does not match legacy receipt identity")

    source = Path(source)
    target = Path(target)
    if source == target:
        raise DeviceContextError("Legacy receipt source and target must differ")
    return {
        "source": source,
        "temporary_target": target.with_name(target.name + ".migration-tmp"),
        "target": target,
        "steps": ["copy source bytes to temporary_target", "fsync temporary_target", "atomic replace temporary_target with target"],
        "preserve_source": True,
        "identity": identity,
        "preconditions": ["verify live package path still matches receipt", "target does not already exist", "verify source bytes before copying"],
    }


def _read_receipt_bytes(path):
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeviceContextError("Legacy receipt is unreadable JSON: " + path.name) from exc
    if not isinstance(value, dict):
        raise DeviceContextError("Legacy receipt must contain a JSON object: " + path.name)
    return raw, value


def _verified_ownership_identity(receipt, ownership_proof, serial):
    required = ("serial", "package", "package_path", "apk_sha256")
    if not isinstance(receipt, dict) or not isinstance(ownership_proof, dict):
        raise DeviceContextError("Legacy receipt migration requires ownership proof")
    if any(not receipt.get(key) for key in required):
        raise DeviceContextError("Legacy installed receipt lacks package placement ownership identity")
    identity = {key: receipt[key] for key in required}
    if identity["serial"] != serial:
        raise DeviceContextError("Legacy receipt serial does not match selected device")
    if any(ownership_proof.get(key) != value for key, value in identity.items()):
        raise DeviceContextError("Ownership proof does not match legacy receipt identity")
    return identity


def _write_fsynced_new(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _verify_snapshot(snapshot):
    for path, expected in snapshot.items():
        try:
            current = path.read_bytes()
        except OSError as exc:
            raise DeviceContextError("Migration source disappeared before publish: " + path.name) from exc
        if _sha256(current) != _sha256(expected):
            raise DeviceContextError("Migration source changed before publish: " + path.name)


def _verify_target_hashes(target, hashes):
    for name, expected in hashes.items():
        path = target / name
        if not path.is_file() or path.is_symlink() or _sha256(path.read_bytes()) != expected:
            raise DeviceContextError("Staged receipt changed before activation: " + name)


def migrate_legacy_receipts(
    source,
    target,
    *,
    serial,
    ownership_proof,
    coordination_lock,
    install_counter=None,
):
    """Copy legacy receipts into a scoped tree and activate it atomically.

    This must be called explicitly after the coordination lock clears and a
    caller verifies live package ownership. It never deletes or rewrites source
    files. Existing target or staging paths are treated as conflicts.
    """
    serial = validate_serial(serial)
    if Path(coordination_lock).exists():
        raise DeviceContextError("Legacy receipt migration is blocked while the coordination lock exists")
    source = Path(source)
    target = Path(target)
    work_root = source.parent
    source = validate_receipt_directory(work_root, source)
    target = validate_receipt_directory(work_root, target)
    if source == target:
        raise DeviceContextError("Legacy receipt source and target must differ")
    if not source.is_dir():
        raise DeviceContextError("Legacy receipt directory is missing")
    if target.exists():
        raise DeviceContextError("Scoped receipt target already exists; inspect before migration")
    staging = validate_receipt_directory(work_root, target.with_name(target.name + ".migration-tmp"))
    if staging.exists():
        raise DeviceContextError("Temporary migration directory already exists; inspect before retry")

    installed_path = source / "installed.json"
    if not installed_path.is_file() or installed_path.is_symlink():
        raise DeviceContextError("Legacy installed ownership receipt is required")
    installed_raw, installed = _read_receipt_bytes(installed_path)
    identity = _verified_ownership_identity(installed, ownership_proof, serial)

    copied = []
    payloads = []
    snapshot = {installed_path: installed_raw}
    for name in MIGRATED_RECEIPTS:
        original = source / name
        if original.is_symlink():
            raise DeviceContextError("Legacy receipt must be a regular file: " + name)
        if not original.exists():
            continue
        if not original.is_file():
            raise DeviceContextError("Legacy receipt must be a regular file: " + name)
        if name == "installed.json":
            data, receipt = installed_raw, installed
        else:
            data, receipt = _read_receipt_bytes(original)
            snapshot[original] = data
        recorded_serial = receipt.get("serial")
        if recorded_serial is not None and recorded_serial != serial:
            raise DeviceContextError("Legacy receipt serial does not match selected device: " + name)
        if name == "runtime.json" and recorded_serial is None and identity["serial"] != serial:
            raise DeviceContextError("Runtime receipt without serial requires matching installed ownership proof")
        payloads.append((name, data))
        copied.append(name)

    counter_payload = None
    if install_counter is not None:
        counter_path = Path(install_counter)
        validate_receipt_directory(work_root, counter_path.parent)
        if counter_path.is_symlink():
            raise DeviceContextError("Per-device install counter must be a regular file")
        if counter_path.exists():
            if not counter_path.is_file():
                raise DeviceContextError("Per-device install counter must be a regular file")
            counter_bytes, counter = _read_receipt_bytes(counter_path)
            if counter.get("serial") != serial:
                raise DeviceContextError("Per-device install counter serial does not match selected device")
            counter_payload = counter_bytes
            snapshot[counter_path] = counter_bytes

    validate_receipt_directory(work_root, target.parent).mkdir(parents=True, exist_ok=True)
    validate_receipt_directory(work_root, staging)
    staging.mkdir()
    try:
        hashes = {}
        for name, data in payloads:
            _write_fsynced_new(staging / name, data)
            hashes[name] = _sha256(data)
        if counter_payload is not None:
            counter_name = "device-install-limit.json"
            _write_fsynced_new(staging / counter_name, counter_payload)
            copied.append(counter_name)
            hashes[counter_name] = _sha256(counter_payload)
        dir_fd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        _verify_snapshot(snapshot)
        if Path(coordination_lock).exists():
            raise DeviceContextError("Legacy receipt migration is blocked while the coordination lock exists")
        validate_receipt_directory(work_root, target)
        target.mkdir()
        for name in copied:
            os.replace(staging / name, target / name)
        staging.rmdir()
        dir_fd = os.open(target, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

        _verify_snapshot(snapshot)
        if Path(coordination_lock).exists():
            raise DeviceContextError("Legacy receipt migration is blocked while the coordination lock exists")
        validate_receipt_directory(work_root, target)

        marker_tmp = target / (ACTIVATION_MARKER + ".tmp")
        marker = target / ACTIVATION_MARKER
        marker_payload = {"version": 1, "serial": serial, "identity": identity, "sha256": hashes}
        marker_payload["marker_sha256"] = _sha256(json.dumps(marker_payload, sort_keys=True, separators=(",", ":")).encode())
        marker_data = json.dumps(marker_payload, sort_keys=True, indent=2).encode() + b"\n"
        _write_fsynced_new(marker_tmp, marker_data)
        if Path(coordination_lock).exists():
            marker_tmp.unlink()
            raise DeviceContextError("Legacy receipt migration is blocked while the coordination lock exists")
        validate_receipt_directory(work_root, target)
        _verify_snapshot(snapshot)
        _verify_target_hashes(target, hashes)
        if Path(coordination_lock).exists():
            marker_tmp.unlink()
            raise DeviceContextError("Legacy receipt migration is blocked while the coordination lock exists")
        os.replace(marker_tmp, marker)
        dir_fd = os.open(target, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        # A published-but-unmarked target remains inactive and blocks a blind
        # retry; keep it for inspection. The legacy source stays intact.
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "directory": target,
        "activation_marker": target / ACTIVATION_MARKER,
        "copied": copied,
        "source_preserved": True,
    }
