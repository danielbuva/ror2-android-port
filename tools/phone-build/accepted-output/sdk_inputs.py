"""Extract exact SDK inputs from an owner's pinned Unity component.

Current experimental acquisition support. No installer/Editor is run, no download
or license acceptance is performed, and no SDK bits are distributed by this tool.
Outputs and raw receipts must stay private. Android execution is unqualified.
"""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import struct
import time
import xml.etree.ElementTree as ET
import zlib


URL = "https://download.unity3d.com/download_unity/88f88f591b2e/MacEditorTargetInstaller/UnitySetup-Android-Support-for-Editor-2021.3.45f2.pkg"
COMPONENT_BYTES = 586545150
COMPONENT_SHA256 = "0e4476332c902ab8800bafbb521f5893ec706daedbb639da07a8fe43e6e9bc49"
PREFIX = "PlaybackEngines/AndroidPlayer/"
FILES = {
    "Data/unity default resources": (4222168, "fcbf1c513378f79a04c9250fb1efc466f5a7d5ca9d93af961daa3e0b957859f3"),
    "Variations/il2cpp/Development/Libs/arm64-v8a/libmain.so": (13312, "0fe51173f05822dd432430f8f6b6411c95713b1b4f55d45ae394cc77153a02cd"),
    "Variations/il2cpp/Development/Libs/arm64-v8a/libunity.so": (60927416, "69e63737c6aa6a2159831b7d274a31b6dec3b42f6b23fd9d368ba97f655ac4af"),
}
# Generic SDK Java/resource inputs for the fixed accepted Android package.
ANDROID_FILES = {
    "Variations/il2cpp/Development/Classes/classes.jar": (141718, "fba234caa7eff370ba1a57fbbb8e9314d295d7bff4e4477541d58f3d8c25218e"),
    "Source/com/unity3d/player/UnityPlayerActivity.java": (5110, "69b0c6d5d1503a22bbd8706571cd24241ac593e96b8359daa397c5c7057f2b59"),
    "Apk/LauncherManifest.xml": (527, "20d02042d43a5fce4a9d4fdc5b83ec5d285374c04de08aa2d08b54e052dfa969"),
    "Apk/UnityManifest.xml": (657, "c8155dab9861429e65797b4f9a1ec52345a1d900b7a5e6f3c3dac59369cef926"),
    "Apk/res/mipmap-anydpi-v26/app_icon.xml": (266, "44cc3246d167bd718fb61feaba493850ff95255c1ddbb8854c0e4c0534832f96"),
    "Apk/res/mipmap-anydpi-v26/app_icon_round.xml": (266, "44cc3246d167bd718fb61feaba493850ff95255c1ddbb8854c0e4c0534832f96"),
    "Apk/res/mipmap-mdpi/app_icon.png": (1746, "ca4cf311409e14f4b14714b4e2c969cc62d40c1c2a5310a175e5878732c42800"),
    "Apk/res/mipmap-mdpi/ic_launcher_background.png": (318, "75ef53c4d4418a640fa25e4706e3db1cce1872f866c5d1e25b1a6e95355b4408"),
    "Apk/res/mipmap-mdpi/ic_launcher_foreground.png": (4549, "b069982e0f75f5621f9d06f066f50e0617bfeb9b14e06d5768a070ddccf727b0"),
    "Apk/res/values/freeformwindow.xml": (359, "425d3881c49fbdc050a94641abe5c55bc56aca2e214fba010c4b1ed3a8f3f9bc"),
    "Apk/res/values/ids.xml": (111, "8f9e8dc7a26056d00606d53359a35fae3aa2db85ccb231b583922f7733791ee0"),
    "Apk/res/values/strings.xml": (182, "4d585291da9e6b24535aaee77af493e46fe362ead583f33c8bd96cdf275ee8a6"),
    "Apk/res/values/styles.xml": (529, "fda849fd2348634bd568b66991363523447fe1a70f8045c50c05a8d69a1c6505"),
    "Apk/res/values-v21/styles.xml": (169, "b45ea725fa49146986e5c8778ea63c4cb8307367abb6c9cc4b49d86eb2b36f6d"),
    "Apk/res/values-v28/styles.xml": (245, "e75ff390b53c5cd714e9ebe0e356a048418a81b7b075ffb6af7c295c10902712"),
    "Apk/res/values-v30/freeformwindow.xml": (395, "f879f85c06803e416f089e0546c75fe6d32c75ee8e9158c8c569fe89a1fbfbbb"),
}

RESERVE = 2 * 1024**3


def exact(stream, count):
    value = stream.read(count)
    if len(value) != count:
        raise ValueError("truncated component")
    return value


class Limit(io.RawIOBase):
    def __init__(self, source, length):
        self.source, self.remaining = source, length

    def readable(self):
        return True

    def read(self, count=-1):
        count = self.remaining if count < 0 else min(count, self.remaining)
        value = self.source.read(count)
        self.remaining -= len(value)
        return value


def xml(value):
    if b"<!DOCTYPE" in value.upper() or b"<!ENTITY" in value.upper():
        raise ValueError("component XML declarations refused")
    return ET.fromstring(value)


def inflated(value, size):
    if size > 16 * 1024**2:
        raise ValueError("component metadata bound exceeded")
    decoder = zlib.decompressobj()
    result = decoder.decompress(value, size + 1)
    if len(result) != size or not decoder.eof or decoder.unused_data:
        raise ValueError("component metadata size differs")
    return result


def payload_location(stream, size):
    magic, header, version, compressed, unpacked, checksum = struct.unpack(">IHHQQI", exact(stream, 28))
    if magic != 0x78617221 or header != 28 or version != 1 or checksum != 1 or compressed > 1024**2:
        raise ValueError("unsupported XAR header")
    toc = xml(inflated(exact(stream, compressed), unpacked))
    selected = {}

    def visit(node, parent="", depth=0):
        if depth > 32:
            raise ValueError("component directory bound exceeded")
        name = node.findtext("name")
        if not name or "/" in name or name in (".", ".."):
            raise ValueError("unsafe component entry")
        path = parent + "/" + name if parent else name
        data = node.find("data")
        if data is not None and path in ("TargetSupport.pkg.tmp/Payload", "TargetSupport.pkg.tmp/PackageInfo"):
            offset, length, expanded = (int(data.findtext(key)) for key in ("offset", "length", "size"))
            absolute = header + compressed + offset
            if path in selected or min(offset, length, expanded) < 0 or absolute + length > size:
                raise ValueError("component extent differs")
            selected[path] = (absolute, length, expanded, data.find("encoding").attrib["style"])
        for child in node.findall("file"):
            visit(child, path, depth + 1)

    for node in toc.findall("./toc/file"):
        visit(node)
    if len(selected) != 2:
        raise ValueError("component payload/identity missing")
    offset, length, expanded, encoding = selected["TargetSupport.pkg.tmp/PackageInfo"]
    if length > 1024**2 or encoding != "application/x-gzip":
        raise ValueError("unsupported component identity")
    stream.seek(offset)
    info = xml(inflated(exact(stream, length), expanded))
    if info.get("identifier") != "com.unity3d.AndroidPlayer" or info.get("install-location") != "/Applications/Unity/PlaybackEngines/AndroidPlayer":
        raise ValueError("component identity/root differs")
    offset, length, expanded, encoding = selected["TargetSupport.pkg.tmp/Payload"]
    if length != expanded or encoding != "application/octet-stream":
        raise ValueError("unsupported payload encoding")
    return offset, length


def copy_cpio(stream, output, wanted, started):
    found, position, members = {}, 0, 0
    while True:
        if time.monotonic() - started > 600:
            raise TimeoutError("SDK extraction deadline")
        magic = exact(stream, 6)
        position += 6
        if magic == b"070707":
            header = magic + exact(stream, 70)
            position += 70
            mode, namesize, size = (int(header[a:b], 8) for a, b in ((18, 24), (59, 65), (65, 76)))
            alignment = 1
        elif magic == b"070701":
            header = magic + exact(stream, 104)
            position += 104
            fields = [int(header[6 + i * 8 : 14 + i * 8], 16) for i in range(13)]
            mode, size, namesize, alignment = fields[1], fields[6], fields[11], 4
        else:
            raise ValueError("unsupported CPIO header")
        if not 1 <= namesize <= 8192 or size > 4 * 1024**3:
            raise ValueError("CPIO member bound exceeded")
        name = exact(stream, namesize)
        position += namesize
        if name[-1:] != b"\0":
            raise ValueError("CPIO name unterminated")
        name = name[:-1].decode()
        padding = (-position) % alignment
        exact(stream, padding)
        position += padding
        if name == "TRAILER!!!":
            if size:
                raise ValueError("nonempty CPIO trailer")
            while data := stream.read(65536):
                position += len(data)
                if any(data):
                    raise ValueError("unexpected archive tail")
            break
        members += 1
        if members > 100000:
            raise ValueError("CPIO member count exceeded")
        key = name.removeprefix("./")
        if name.startswith("/") or ".." in name.split("/") or "\\" in name or "\0" in name:
            raise ValueError("unsafe CPIO path")
        destination = None
        digest = hashlib.sha256()
        if key in wanted:
            if key in found or not stat.S_ISREG(mode) or size != wanted[key][0]:
                raise ValueError("selected SDK member type/size/identity differs")
            target = output / PREFIX / key
            if target.resolve() != target.absolute():
                raise ValueError("redirected SDK destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            destination = target.open("xb")
        try:
            remaining = size
            while remaining:
                if time.monotonic() - started > 600:
                    raise TimeoutError("SDK extraction deadline")
                data = exact(stream, min(65536, remaining))
                remaining -= len(data)
                position += len(data)
                if destination:
                    destination.write(data)
                    digest.update(data)
            if destination:
                if digest.hexdigest() != wanted[key][1]:
                    raise ValueError("selected SDK member hash differs")
                found[key] = {"bytes": size, "sha256": digest.hexdigest()}
        finally:
            if destination:
                destination.close()
        padding = (-position) % alignment
        exact(stream, padding)
        position += padding
    if set(found) != set(wanted):
        raise ValueError("selected SDK cohort incomplete")
    for name, row in found.items():
        with (output / PREFIX / name).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != row["sha256"]:
                raise ValueError("SDK independent readback differs")
    return {"files": found, "members_read": members, "uncompressed_archive_bytes": position}


def extract(component, output, *, android_package=False):
    wanted = FILES | ANDROID_FILES if android_package else FILES
    component, output = Path(component).absolute(), Path(output).absolute()
    if component != component.resolve(strict=True) or not component.is_file() or component.stat().st_size != COMPONENT_BYTES:
        raise ValueError("unsupported or redirected owner component")
    with component.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != COMPONENT_SHA256:
            raise ValueError("owner component hash differs")
    if output != output.resolve() or not output.parent.is_dir():
        raise ValueError("output parent redirected or absent")
    if shutil.disk_usage(output.parent).free < RESERVE + sum(row[0] for row in wanted.values()) + 16 * 1024**2:
        raise RuntimeError("insufficient SDK extraction reserve")
    output.mkdir(mode=0o700)
    started = time.monotonic()
    result = {
        "schema": 1,
        "success": False,
        "component_sha256": COMPONENT_SHA256,
        "editor_installer_device_actions": 0,
        "phone_qualified": False,
        "sdk_redistribution_qualified": False,
    }
    try:
        with component.open("rb") as source:
            offset, length = payload_location(source, COMPONENT_BYTES)
            source.seek(offset)
            limited = Limit(source, length)
            with gzip.GzipFile(fileobj=limited, mode="rb") as stream:
                result.update(copy_cpio(stream, output, wanted, started))
            if limited.remaining:
                raise ValueError("component payload incomplete")
        with component.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != COMPONENT_SHA256:
                raise ValueError("owner component changed")
        result["success"] = True
        return result
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True, help="owner-downloaded exact Unity Android support PKG")
    parser.add_argument("--output", required=True, help="new private SDK input directory; parent must exist")
    parser.add_argument("--android-package", action="store_true", help="also extract pinned generic SDK Java and Android resource inputs")
    args = parser.parse_args()
    print(json.dumps(extract(args.component, args.output, android_package=args.android_package)))


if __name__ == "__main__":
    main()
