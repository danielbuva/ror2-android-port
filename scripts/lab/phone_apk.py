"""Repackage only the authored phone-content fixture; no game APKs or signing.

Standard-library Android-host probe. Binary XML fields follow AOSP's public
ResXMLTree/string-pool wire format. Native alignment and signing are separate
steps performed after this writer, never before it.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


PACKAGE = "dev.ror2lab.phonecontentfixture"
BUNDLE = "assets/phone-fixture.bundle"
ANDROID_NAMESPACE = "http://schemas.android.com/apk/res/android"


def _chunks(data, start, end):
    while start < end:
        if end - start < 8:
            raise ValueError("Truncated Android resource header")
        kind, header, size = struct.unpack_from("<HHI", data, start)
        if header < 8 or size < header or size > end - start:
            raise ValueError("Invalid Android resource chunk size")
        yield kind, start, header, size
        start += size


def _strings(data, start, header, size):
    if header < 28:
        raise ValueError("Truncated string pool")
    count, styles, flags, relative = struct.unpack_from("<IIII", data, start + 8)
    end = start + size
    if count > 4096 or start + header + (count + styles) * 4 > end or relative < header + (count + styles) * 4 or relative >= size:
        raise ValueError("Invalid fixture string pool bounds")
    utf8 = bool(flags & 0x100)

    def length(position):
        unit = 1 if utf8 else 2
        if position + unit > end:
            raise ValueError("Truncated string length")
        first = int.from_bytes(data[position : position + unit], "little")
        position += unit
        high = 0x80 if utf8 else 0x8000
        if first & high:
            if position + unit > end:
                raise ValueError("Truncated extended string length")
            second = int.from_bytes(data[position : position + unit], "little")
            first = ((first & ~high) << (8 if utf8 else 16)) | second
            position += unit
        return first, position

    result = []
    for index in range(count):
        relative_offset = struct.unpack_from("<I", data, start + header + index * 4)[0]
        position = start + relative + relative_offset
        if position < start + relative or position >= end:
            raise ValueError("Invalid string offset")
        count, position = length(position)
        if utf8:
            count, position = length(position)
        byte_count = count if utf8 else count * 2
        terminator = 1 if utf8 else 2
        if byte_count + terminator > end - position or any(data[position + byte_count : position + byte_count + terminator]):
            raise ValueError("Invalid string data bounds/terminator")
        result.append(data[position : position + byte_count].decode("utf-8" if utf8 else "utf-16-le"))
    return result


def update_manifest(data, version_code):
    """Change the typed integer in this fixture's manifest, preserving all else."""
    if type(version_code) is not int or not 1 <= version_code <= 2147483647 or len(data) > 1024 * 1024:
        raise ValueError("Invalid fixture version or manifest bound")
    if len(data) < 8 or struct.unpack_from("<HHI", data) != (3, 8, len(data)):
        raise ValueError("Expected one complete Android binary XML document")
    strings = None
    package = None
    version = None
    for kind, start, header, size in _chunks(data, 8, len(data)):
        if kind == 1:
            if strings is not None:
                raise ValueError("Duplicate manifest string pool")
            strings = _strings(data, start, header, size)
        elif kind == 0x102:
            if strings is None or header < 16 or size < header + 20:
                raise ValueError("Invalid manifest element")
            namespace, name, attributes_start, attribute_size, count = struct.unpack_from("<IIHHH", data, start + header)
            if name >= len(strings):
                raise ValueError("Invalid element name")
            if strings[name] != "manifest":
                continue
            if package is not None or attribute_size != 20 or attributes_start < 20:
                raise ValueError("Ambiguous manifest element")
            offset = start + header + attributes_start
            if count * attribute_size > start + size - offset:
                raise ValueError("Truncated manifest attributes")
            for index in range(count):
                position = offset + index * attribute_size
                ns, name, raw, value_size, reserved, value_type, value = struct.unpack_from("<IIIHBBI", data, position)
                if name >= len(strings) or value_size != 8 or reserved != 0:
                    raise ValueError("Invalid manifest attribute")
                if strings[name] == "package" and ns == 0xFFFFFFFF:
                    if package is not None or value_type != 3 or value >= len(strings):
                        raise ValueError("Expected a literal fixture package")
                    package = strings[value]
                elif strings[name] == "versionCode" and ns < len(strings) and strings[ns] == ANDROID_NAMESPACE:
                    if version is not None or value_type not in (0x10, 0x11):
                        raise ValueError("Expected one literal fixture version code")
                    version = (position, value)
    if package != PACKAGE or version is None:
        raise ValueError("Refusing a different or unversioned package")
    position, previous = version
    if version_code <= previous:
        raise ValueError("Fixture version code must increase")
    result = bytearray(data)
    struct.pack_into("<I", result, position + 8, 0xFFFFFFFF)  # No stale raw string value.
    struct.pack_into("<I", result, position + 16, version_code)
    return bytes(result), previous


def repack(apk, bundle, output, version_code):
    """Replace only the authored bundle/version; require later alignment/signing."""
    apk, bundle, output = map(Path, (apk, bundle, output))
    if output.resolve() in (apk.resolve(), bundle.resolve()):
        raise ValueError("Refusing to overwrite a supplied input")
    candidate = bundle.read_bytes()
    if len(candidate) > 1024 * 1024 or not candidate.startswith(b"UnityFS\0"):
        raise ValueError("Expected the small authored fixture bundle")
    with zipfile.ZipFile(apk) as source:
        infos = source.infolist()
        if len(infos) > 4096 or sum(item.file_size for item in infos) > 512 * 1024 * 1024:
            raise ValueError("Fixture APK exceeds the probe bounds")
        names = [item.filename for item in infos]
        if len(set(names)) != len(names) or BUNDLE not in names:
            raise ValueError("Ambiguous APK or missing authored fixture bundle")
        manifest, old_version = update_manifest(source.read("AndroidManifest.xml"), version_code)
        with output.open("xb") as target, zipfile.ZipFile(target, "w") as destination:
            for item in infos:
                name = item.filename
                upper = name.upper()
                if upper.startswith("META-INF/") and (upper == "META-INF/MANIFEST.MF" or upper.endswith((".RSA", ".SF", ".DSA", ".EC"))):
                    continue
                data = manifest if name == "AndroidManifest.xml" else candidate if name == BUNDLE else source.read(item)
                destination.writestr(item, data)
    return {
        "package": PACKAGE,
        "previous_version_code": old_version,
        "version_code": version_code,
        "bundle_sha256": hashlib.sha256(candidate).hexdigest(),
        "apk_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "aligned": False,
        "signed": False,
    }


def stage_action(request):
    """Host interface; the standalone CLI runs the identical repacker on Android."""
    from common import ROOT, WORK, now

    request = Path(request).resolve()
    if not request.is_relative_to(WORK.resolve()):
        raise ValueError("Select an ignored local fixture request with --target")
    value = json.loads(request.read_text())
    if set(value) != {"apk", "apk_sha256", "bundle", "bundle_sha256", "version_code"}:
        raise ValueError("Fixture request fields do not match the contract")
    for name in ("apk", "bundle"):
        path = Path(value[name]).resolve()
        if not path.is_relative_to(WORK.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != value[name + "_sha256"]:
            raise ValueError("Fixture input path/hash mismatch: " + name)
    destination = WORK / "rebuild/phone-packaging" / now()
    destination.mkdir(parents=True, exist_ok=False)
    output = destination / "unsigned.apk"
    result = repack(value["apk"], value["bundle"], output, value["version_code"])
    result.update({"apk": str(output), "inputs": value, "repacker_sha256": hashlib.sha256((ROOT / "scripts/lab/phone_apk.py").read_bytes()).hexdigest()})
    (destination / "repack-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version-code", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(repack(args.apk, args.bundle, args.output, args.version_code)))


if __name__ == "__main__":
    main()
