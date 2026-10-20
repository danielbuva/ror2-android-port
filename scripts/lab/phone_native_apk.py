"""Swap only a hash-bound ARM64 library into the authored content fixture.

The matching metadata stays byte-identical. Alignment and signing follow separately.
Keep this file beside the unchanged phone_apk.py wire-format helper on Android.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zipfile


_SPEC = importlib.util.spec_from_file_location("_fixture_apk_wire", Path(__file__).with_name("phone_apk.py"))
_WIRE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_WIRE)
NATIVE = "lib/arm64-v8a/libil2cpp.so"
METADATA = "assets/bin/Data/Managed/Metadata/global-metadata.dat"


def repack(apk, library, output, version_code, *, apk_sha256, library_sha256, metadata_sha256):
    apk, library, output = map(Path, (apk, library, output))
    if output.resolve() in (apk.resolve(), library.resolve()):
        raise ValueError("Refusing to overwrite a native fixture input")
    if library.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("Native fixture library exceeds the probe bound")
    native = library.read_bytes()
    if hashlib.sha256(apk.read_bytes()).hexdigest() != apk_sha256 or hashlib.sha256(native).hexdigest() != library_sha256:
        raise ValueError("Native fixture input hash mismatch")
    if len(native) < 64 or native[:7] != b"\x7fELF\x02\x01\x01" or struct.unpack_from("<HH", native, 16) != (3, 183):
        raise ValueError("Expected an ELF64 little-endian ARM64 shared library")
    with zipfile.ZipFile(apk) as source:
        infos = source.infolist()
        names = [item.filename for item in infos]
        if (
            len(infos) > 4096
            or sum(item.file_size for item in infos) > 512 * 1024 * 1024
            or len(set(names)) != len(names)
            or not {NATIVE, METADATA, _WIRE.BUNDLE} <= set(names)
        ):
            raise ValueError("Native fixture archive bounds/identity differ")
        if hashlib.sha256(source.read(METADATA)).hexdigest() != metadata_sha256:
            raise ValueError("Native fixture metadata hash mismatch")
        manifest, previous = _WIRE.update_manifest(source.read("AndroidManifest.xml"), version_code)
        with output.open("xb") as target, zipfile.ZipFile(target, "w") as destination:
            for item in infos:
                name = item.filename
                upper = name.upper()
                if upper.startswith("META-INF/") and (upper == "META-INF/MANIFEST.MF" or upper.endswith((".RSA", ".SF", ".DSA", ".EC"))):
                    continue
                data = manifest if name == "AndroidManifest.xml" else native if name == NATIVE else source.read(item)
                destination.writestr(item, data)
    return {
        "package": _WIRE.PACKAGE,
        "previous_version_code": previous,
        "version_code": version_code,
        "library_sha256": library_sha256,
        "metadata_sha256": metadata_sha256,
        "apk_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "aligned": False,
        "signed": False,
    }


def stage_action(request):
    from common import WORK, now

    request = Path(request).resolve()
    if not request.is_relative_to(WORK.resolve()):
        raise ValueError("Native packaging request must be ignored local state")
    value = json.loads(request.read_text())
    if set(value) != {"apk", "apk_sha256", "library", "library_sha256", "metadata_sha256", "version_code"}:
        raise ValueError("Native packaging request fields differ")
    if any(not Path(value[key]).resolve().is_relative_to(WORK.resolve()) for key in ("apk", "library")):
        raise ValueError("Native fixture inputs must be local ignored outputs")
    destination = WORK / "rebuild/phone-native-packaging" / now()
    destination.mkdir(parents=True, exist_ok=False)
    output = destination / "unsigned.apk"
    result = repack(
        value["apk"], value["library"], output, value["version_code"], **{key: value[key] for key in ("apk_sha256", "library_sha256", "metadata_sha256")}
    )
    result.update(apk=str(output), inputs=value)
    (destination / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("apk", "library", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--version-code", type=int, required=True)
    for name in ("apk-sha256", "library-sha256", "metadata-sha256"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(repack(**vars(parser.parse_args()))))
