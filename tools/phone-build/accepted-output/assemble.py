"""Assemble hash-bound accepted APK entries with Android-compatible resource storage.

This writes a new unsigned archive only. Align and owner-sign afterwards using
permitted tools; content equality is not installation or game qualification.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zipfile


SPEC = importlib.util.spec_from_file_location("_accepted_packet", Path(__file__).with_name("package.py"))
PACKET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKET)


def obsolete_signature(name):
    name = name.upper()
    return name.startswith("META-INF/") and (name == "META-INF/MANIFEST.MF" or name.endswith((".RSA", ".DSA", ".EC", ".SF")))


def assemble(manifest, expected, targets, output):
    manifest, targets, output = map(Path, (manifest, targets, output))
    if output.resolve().is_relative_to(targets.resolve()):
        raise ValueError("APK output overlaps target input tree")
    _, value = PACKET.profile(manifest, expected)
    rows = {r["path"][4:]: r for r in value["targets"] if r["path"].startswith("apk/") and not obsolete_signature(r["path"][4:])}
    if not {"resources.arsc", "AndroidManifest.xml"} <= rows.keys():
        raise ValueError("required APK resource/manifest entries absent")
    # Opening exclusively occurs before any data is written, including failures.
    with output.open("xb") as destination, zipfile.ZipFile(destination, "w", compresslevel=3) as apk:
        for name, row in rows.items():
            source = PACKET.verify(targets, row)
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.file_size = row["bytes"]
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED if name == "resources.arsc" else zipfile.ZIP_DEFLATED
            if info.compress_type == zipfile.ZIP_STORED:
                # A valid private ZIP extra field aligns the local entry data.
                # The 4-byte field header is included in the padding calculation.
                start = destination.tell() + 30 + len(name.encode("utf-8"))
                padding = (-start - 4) % 4
                info.extra = struct.pack("<HH", 0xD935, padding) + b"\0" * padding
            digest = hashlib.sha256()
            count = 0
            with source.open("rb") as original, apk.open(info, "w") as entry:
                while data := original.read(65536):
                    entry.write(data)
                    digest.update(data)
                    count += len(data)
            if count != row["bytes"] or digest.hexdigest() != row["sha256"]:
                raise ValueError("APK source changed during assembly")
    with zipfile.ZipFile(output) as apk, output.open("rb") as raw:
        if set(apk.namelist()) != set(rows):
            raise ValueError("APK entry membership differs")
        for name, row in rows.items():
            with apk.open(name) as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != row["sha256"]:
                    raise ValueError("APK entry hash differs")
        resource = apk.getinfo("resources.arsc")
        raw.seek(resource.header_offset)
        header = raw.read(30)
        if header[:4] != b"PK\x03\x04":
            raise ValueError("APK local ZIP header differs")
        name_size, extra_size = struct.unpack_from("<HH", header, 26)
        resource_offset = resource.header_offset + 30 + name_size + extra_size
        if resource.compress_type != zipfile.ZIP_STORED or resource_offset % 4:
            raise ValueError("APK resource storage/alignment differs")
    return {
        "apk_sha256": PACKET.sha(output),
        "entries_verified": len(rows),
        "resources_stored": True,
        "resource_offset": resource_offset,
        "signed": False,
        "install_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "manifest-sha256", "targets", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(assemble(args.manifest, args.manifest_sha256, args.targets, args.output)))


if __name__ == "__main__":
    main()
