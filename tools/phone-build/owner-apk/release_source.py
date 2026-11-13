"""Explicit debug-only loopback release source; production trust is never replaced.

The Android worker supplies debuggability from ApplicationInfo, not private JSON.
The host lab writes only a public key and source URL to debug-release-source.json.
"""

import re
import urllib.parse
import urllib.request


class DebugReleaseTransport:
    """A local test publisher reached by adb reverse, with same-base redirects."""

    def __init__(self, base_url):
        if not isinstance(base_url, str):
            raise ValueError("debug release base URL required")
        parsed = urllib.parse.urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or not 1 <= parsed.port <= 65535
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/")
            or not parsed.path.endswith("/")
            or "%" in parsed.path
            or "\\" in parsed.path
            or any(part in {".", ".."} for part in parsed.path.split("/"))
        ):
            raise ValueError("debug release source requires an explicit http://127.0.0.1:port/ base URL")
        self.base_url = base_url

    def allowed(self, url):
        if not isinstance(url, str) or not url.startswith(self.base_url):
            raise ValueError("debug release URL must stay inside the explicit loopback base")
        suffix = url[len(self.base_url) :]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", suffix) or suffix in {".", ".."}:
            raise ValueError("debug release URL must name one local release asset")

    def metadata_url(self):
        return self.base_url + "latest.json"

    def asset_url(self, url, name):
        self.allowed(url)
        if url != self.base_url + name:
            raise ValueError("debug release asset differs from its declared name")
        return url

    def open(self, url):
        self.allowed(url)
        owner = self

        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                owner.allowed(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        request = urllib.request.Request(url, headers={"User-Agent": "RoR2-owner-installer-debug/1"})
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect()).open(request, timeout=30)


def configure(trust, override, *, debuggable, validate_public_key):
    """Return copied trust and transport, or unchanged production configuration.

    Presence is not opt-in: enabled must be the boolean true. A release build
    rejects even malformed/stale override configuration before trusting it.
    """
    if override is None:
        return trust, None
    if debuggable is not True:
        raise ValueError("test release source and publisher key are forbidden in release builds")
    if not isinstance(override, dict) or set(override) != {"enabled", "base_url", "key_id", "public_key"} or override["enabled"] is not True:
        raise ValueError("debug release override requires explicit enabled=true, base_url, key_id and public_key")
    transport = DebugReleaseTransport(override["base_url"])
    key_id = override["key_id"]
    if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", key_id) or key_id in trust["keys"]:
        raise ValueError("test publisher requires a new key ID; production keys cannot be replaced")
    validate_public_key(override["public_key"])
    return {**trust, "keys": {**trust["keys"], key_id: override["public_key"]}}, transport
