"""Read the diagnostic attempt embedded in the exact installed lab APK."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TEXT_ASSET_NAME = "MovementBatchProbe"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attempt_from_installed(installed: dict, *, loader=None) -> str:
    """Return the unique MovementBatchProbe attempt from owned APK bytes.

    `installed` must be the result of `Device.owned()`. No build pointer,
    mutable project resource, or run-folder evidence is consulted.
    """
    if not isinstance(installed, dict):
        raise RuntimeError("Installed ownership receipt is invalid")
    apk_hash = installed.get("apk_sha256")
    apk_value = installed.get("apk")
    if (not isinstance(apk_hash, str) or len(apk_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in apk_hash)
            or not isinstance(apk_value, str) or not apk_value):
        raise RuntimeError("Installed ownership receipt lacks APK path/hash")
    apk = Path(apk_value).expanduser()
    if not apk.is_file() or apk.is_symlink():
        raise RuntimeError("Installed receipt APK is missing or unsafe")
    try:
        apk_bytes = apk.read_bytes()
    except OSError as exc:
        raise RuntimeError("Installed receipt APK cannot be read") from exc
    if hashlib.sha256(apk_bytes).hexdigest() != apk_hash:
        raise RuntimeError("Installed receipt APK bytes changed")
    if loader is None:
        try:
            import UnityPy
        except ImportError as exc:
            raise RuntimeError("UnityPy is unavailable to inspect the installed APK") from exc
        loader = UnityPy.load
    try:
        # Parse the exact byte snapshot whose digest was verified above.
        env = loader(apk_bytes)
        matches = []
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            asset = obj.read()
            if getattr(asset, "m_Name", None) != TEXT_ASSET_NAME:
                continue
            text = getattr(asset, "m_Script", None)
            if isinstance(text, bytes):
                text = text.decode("utf-8-sig")
            if not isinstance(text, str):
                raise RuntimeError("MovementBatchProbe TextAsset is not UTF-8 text")
            value = json.loads(text)
            if not isinstance(value, dict):
                raise RuntimeError("MovementBatchProbe TextAsset is not a JSON object")
            matches.append(value)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Cannot read MovementBatchProbe from receipt-bound APK") from exc
    if len(matches) != 1:
        raise RuntimeError("Receipt-bound APK must contain exactly one MovementBatchProbe TextAsset")
    attempt = matches[0].get("attempt")
    if not isinstance(attempt, str) or not attempt.strip():
        raise RuntimeError("Receipt-bound MovementBatchProbe has no valid attempt")
    return attempt
