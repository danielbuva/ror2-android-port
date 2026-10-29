"""Generate public Android startup metadata; never read an accepted player.

The caller supplies its legitimate input inventory, authored PlayerSettings and
toolchain descriptor. Their complete hashes bind reproducible build identifiers.
These identifiers convey no ownership, entitlement or authentication result.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import uuid


PREFIX = "apk/assets/bin/Data/"
NAMES = {PREFIX + "boot.config", PREFIX + "unity_app_guid"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def render(inputs):
    """Retain authored engine policy, omit development connection discovery."""
    if set(inputs) != {"inventory", "settings", "toolchain", "producer"}:
        raise ValueError("startup inputs differ")
    for item in inputs.values():
        if pin(item["path"]) != item:
            raise ValueError("startup input changed")
    if inputs["producer"] != pin(__file__):
        raise ValueError("startup producer changed")
    toolchain = json.loads(Path(inputs["toolchain"]["path"]).read_text())
    if (toolchain.get("unity_version"), toolchain.get("unity_revision"), toolchain.get("architecture")) != ("2021.3.45f2", "88f88f591b2e", "arm64"):
        raise ValueError("unqualified startup toolchain")
    settings = Path(inputs["settings"]["path"]).read_text()

    def field(name):
        values = re.findall(r"^  " + re.escape(name) + r": ([01])$", settings, re.M)
        if len(values) != 1:
            raise ValueError("unsupported startup setting: " + name)
        return values[0]

    if field("gcIncremental") != "1":
        raise ValueError("startup profile requires incremental GC")
    # Public converter policy: no debugger wait and a 3 ms incremental GC slice.
    flags = {
        "wait-for-native-debugger": "0",
        "hdr-display-enabled": field("useHDRDisplay"),
        "gc-max-time-slice": "3",
        "androidStartInFullscreen": field("androidStartInFullscreen"),
        "androidRenderOutsideSafeArea": field("androidRenderOutsideSafeArea"),
    }
    # Paths are deliberately excluded: relocating identical admitted inputs must
    # not change build identity. Product/application/signing identities are not
    # changed here. The app GUID is distinct from BuildSettings.buildGUID.
    identity = json.dumps({key: value["sha256"] for key, value in inputs.items()}, sort_keys=True, separators=(",", ":"))
    app_guid = str(uuid.uuid5(uuid.NAMESPACE_URL, "ror2lab/startup/app/" + identity))
    build_guid = uuid.uuid5(uuid.NAMESPACE_URL, "ror2lab/startup/build/" + identity).hex
    return {
        PREFIX + "boot.config": "".join(f"{key}={value}\n" for key, value in flags.items()).encode(),
        PREFIX + "unity_app_guid": app_guid.encode(),
    }, build_guid


def produce(inventory, settings, toolchain, output):
    inputs = {key: pin(path) for key, path in {"inventory": inventory, "settings": settings, "toolchain": toolchain, "producer": __file__}.items()}
    files, build_guid = render(inputs)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    outputs = {}
    for name, body in files.items():
        path = output / "targets" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        outputs[name] = pin(path)
    if render(inputs) != (files, build_guid):
        raise ValueError("startup inputs changed during production")
    receipt = {"schema": "owner-startup-metadata-v1", "inputs": inputs, "outputs": outputs, "build_guid": build_guid, "device_qualified": False}
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def verify(path, expected_sha256):
    path = Path(path)
    if digest(path) != expected_sha256:
        raise ValueError("startup receipt changed")
    receipt = json.loads(path.read_text())
    if receipt["schema"] != "owner-startup-metadata-v1" or set(receipt["outputs"]) != NAMES:
        raise ValueError("unsupported startup receipt")
    files, build_guid = render(receipt["inputs"])
    if receipt["build_guid"] != build_guid:
        raise ValueError("startup build identity changed")
    for name, body in files.items():
        item = receipt["outputs"][name]
        if pin(item["path"]) != item or Path(item["path"]).read_bytes() != body:
            raise ValueError("startup output differs from public inputs")
    return receipt["outputs"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    produce(args.input_manifest, args.settings, args.toolchain, args.output)
