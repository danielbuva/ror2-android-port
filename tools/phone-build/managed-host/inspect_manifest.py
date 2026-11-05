"""Read one hash-bound cached installer manifest/DEX; never build or use a phone.

Only fixed classifications leave this process. An observed declaration is not
device acceptance. Receipt paths are never followed and APK bytes are unchanged.
Source binding checks the receipt, not whether the private builder used each source.
"""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = "dev.ror2lab.installertest"
RECEIVER = "dev.ror2lab.phonebuildhostfixture.OwnerInstaller$Result"
ANDROID = "http://schemas.android.com/apk/res/android"
NONE = 0xFFFFFFFF
MAX_APK = 2 * 1024**3
MAX_MANIFEST = 1024**2
MAX_DEX = 64 * 1024**2
MAX_DEX_TOTAL = 128 * 1024**2
ATTR_IDS = {"name": 0x01010003, "enabled": 0x0101000E, "exported": 0x01010010, "versionCode": 0x0101021B}
SPEC = importlib.util.spec_from_file_location("installer_manifest_wire", ROOT / "scripts/lab/phone_apk.py")
WIRE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIRE)


class Refused(Exception):
    pass


def dex_receiver_definitions(data):
    """Count the exact receiver in class_defs, never strings/type references alone.

    This bounded observation is not a verifier for method bodies or installability.
    Only ordinary little-endian DEX 035-040 is supported; other formats refuse.
    """
    try:
        if not 112 <= len(data) <= MAX_DEX or data[:8] not in (b"dex\n035\0", b"dex\n037\0", b"dex\n038\0", b"dex\n039\0", b"dex\n040\0"):
            raise ValueError
        checksum = struct.unpack_from("<I", data, 8)[0]
        if checksum != zlib.adler32(memoryview(data)[12:]) or data[12:32] != hashlib.sha1(memoryview(data)[32:]).digest():
            raise ValueError
        size, header, endian = struct.unpack_from("<III", data, 32)
        if size != len(data) or header != 112 or endian != 0x12345678:
            raise ValueError
        data_size, data_offset = struct.unpack_from("<II", data, 104)
        if data_offset < 112 or data_offset % 4 or data_offset + data_size != size:
            raise ValueError
        ranges = []

        def table(at, width, maximum):
            count, offset = struct.unpack_from("<II", data, at)
            if count > maximum or (count == 0 and offset != 0):
                raise ValueError
            if count and (offset < 112 or offset % 4 or offset + count * width > data_offset):
                raise ValueError
            if count:
                ranges.append((offset, offset + count * width))
            return count, offset

        string_count, string_offset = table(56, 4, 1048576)
        type_count, type_offset = table(64, 4, 65536)
        class_count, class_offset = table(96, 32, 65536)
        ordered = sorted(ranges)
        if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValueError
        target = ("L" + RECEIVER.replace(".", "/") + ";").encode("ascii")
        seen, found = set(), 0
        for index in range(class_count):
            class_index = struct.unpack_from("<I", data, class_offset + 32 * index)[0]
            if class_index >= type_count or class_index in seen:
                raise ValueError
            seen.add(class_index)
            string_index = struct.unpack_from("<I", data, type_offset + 4 * class_index)[0]
            if string_index >= string_count:
                raise ValueError
            position = struct.unpack_from("<I", data, string_offset + 4 * string_index)[0]
            if not data_offset <= position < size:
                raise ValueError
            units = 0
            for shift in range(0, 35, 7):
                if position >= size:
                    raise ValueError
                value = data[position]
                position += 1
                if shift == 28 and value > 15:
                    raise ValueError
                units |= (value & 127) << shift
                if value < 128:
                    break
            else:
                raise ValueError
            if units == len(target) and data[position : position + len(target) + 1] == target + b"\0":
                found += 1
        return found
    except (ValueError, IndexError, TypeError, struct.error):
        raise Refused("dex-invalid") from None


def packaged_receiver_definition(archive, entries):
    selected = [row for row in entries if re.fullmatch(r"classes(?:[1-9][0-9]*)?\.dex", row.filename)]
    names = {row.filename for row in selected}
    expected = {"classes.dex", *("classes" + str(index) + ".dex" for index in range(2, len(selected) + 1))} if selected else set()
    if len(selected) > 16 or len(names) != len(selected) or names != expected or sum(row.file_size for row in selected) > MAX_DEX_TOTAL:
        raise Refused("apk-dex-unavailable")
    found = 0
    for row in selected:
        if not 0 < row.file_size <= MAX_DEX:
            raise Refused("apk-dex-unavailable")
        with archive.open(row) as member:
            data = member.read(MAX_DEX + 1)
        if len(data) != row.file_size:
            raise Refused("apk-dex-unavailable")
        found += dex_receiver_definitions(data)
    return "defined" if found == 1 else "missing" if found == 0 else "duplicate"


def bounded_strings(data, start, header, size):
    """Reject aliased/overlapping string amplification before decoding strings."""
    if header < 28:
        raise ValueError
    count, styles, flags, relative = struct.unpack_from("<IIII", data, start + 8)
    end = start + size
    if count > 4096 or styles or start + header + count * 4 > end or not header + count * 4 <= relative < size:
        raise ValueError
    utf8 = bool(flags & 0x100)

    def length(position):
        unit = 1 if utf8 else 2
        if position + unit > end:
            raise ValueError
        first = int.from_bytes(data[position : position + unit], "little")
        position += unit
        high = 0x80 if utf8 else 0x8000
        if first & high:
            if position + unit > end:
                raise ValueError
            second = int.from_bytes(data[position : position + unit], "little")
            first = ((first & ~high) << (8 if utf8 else 16)) | second
            position += unit
        return first, position

    total = 0
    for index in range(count):
        offset = struct.unpack_from("<I", data, start + header + index * 4)[0]
        position = start + relative + offset
        if not start + relative <= position < end:
            raise ValueError
        units, position = length(position)
        if utf8:
            units, position = length(position)
        byte_count = units if utf8 else 2 * units
        terminator = 1 if utf8 else 2
        total += byte_count
        if total > MAX_MANIFEST or byte_count + terminator > end - position or any(data[position + byte_count : position + byte_count + terminator]):
            raise ValueError
    return WIRE._strings(data, start, header, size)


def binary_manifest(data, version, *, package=PACKAGE):
    """Inspect bounded binary XML, without editing it or reading APK resources."""
    try:
        if len(data) > MAX_MANIFEST or len(data) < 8 or struct.unpack_from("<HHI", data) != (3, 8, len(data)):
            raise ValueError
        strings, resources, stack, receivers, namespaces = None, None, [], [], []
        manifest, application = None, None
        ended = False
        for number, (kind, start, header, size) in enumerate(WIRE._chunks(data, 8, len(data))):
            if number >= 8192:
                raise ValueError
            if kind == 1:
                if strings is not None or stack or ended or struct.unpack_from("<I", data, start + 12)[0]:
                    raise ValueError
                strings = bounded_strings(data, start, header, size)
            elif kind == 0x180:
                if strings is None or resources is not None or stack or ended or header != 8 or (size - 8) % 4:
                    raise ValueError
                if (size - 8) // 4 > len(strings):
                    raise ValueError
                resources = struct.unpack_from("<" + "I" * ((size - 8) // 4), data, start + 8)
            elif kind in (0x100, 0x101):
                if strings is None or header != 16 or size != 24:
                    raise ValueError
                prefix, uri = struct.unpack_from("<II", data, start + 16)
                if (prefix != NONE and prefix >= len(strings)) or uri >= len(strings):
                    raise ValueError
                namespace = (prefix, uri, len(stack))
                if kind == 0x100:
                    if ended or len(namespaces) >= 64:
                        raise ValueError
                    namespaces.append(namespace)
                elif not namespaces or namespaces.pop() != namespace:
                    raise ValueError
            elif kind == 0x102:
                if strings is None or resources is None or ended or header != 16 or size < 36 or len(stack) >= 32:
                    raise ValueError
                namespace, name, relative, stride, count = struct.unpack_from("<IIHHH", data, start + header)
                if namespace != NONE or name >= len(strings) or relative < 20 or stride != 20 or count > 128:
                    raise ValueError
                offset = start + header + relative
                if offset + count * stride > start + size:
                    raise ValueError
                tag, attrs = strings[name], {}
                for index in range(count):
                    ns, key, raw, value_size, reserved, value_type, value = struct.unpack_from("<IIIHBBI", data, offset + index * stride)
                    if key >= len(strings) or (ns != NONE and ns >= len(strings)) or (raw != NONE and raw >= len(strings)):
                        raise ValueError
                    if value_size != 8 or reserved or (value_type == 3 and value >= len(strings)):
                        raise ValueError
                    namespace_name = None if ns == NONE else strings[ns]
                    attribute = (namespace_name, strings[key])
                    if attribute in attrs:
                        raise ValueError
                    if namespace_name == ANDROID and strings[key] in ATTR_IDS:
                        if key >= len(resources) or resources[key] != ATTR_IDS[strings[key]]:
                            raise ValueError
                    attrs[attribute] = (value_type, strings[value] if value_type == 3 else value)
                if not stack:
                    if tag != "manifest" or manifest is not None:
                        raise ValueError
                    manifest = attrs
                elif tag == "application":
                    if stack != ["manifest"] or application is not None:
                        raise ValueError
                    application = attrs
                elif tag == "receiver":
                    if stack != ["manifest", "application"] or len(receivers) >= 256:
                        raise ValueError
                    receivers.append(attrs)
                stack.append(tag)
            elif kind == 0x103:
                if strings is None or not stack or header != 16 or size != 24:
                    raise ValueError
                namespace, name = struct.unpack_from("<II", data, start + 16)
                if namespace != NONE or name >= len(strings) or stack.pop() != strings[name]:
                    raise ValueError
                ended = not stack
            else:
                raise ValueError
        if stack or namespaces or not ended or manifest is None or application is None:
            raise ValueError
        if manifest.get((None, "package")) != (3, package):
            raise Refused("manifest-package-mismatch")
        actual_version = manifest.get((ANDROID, "versionCode"))
        if actual_version is None or actual_version[0] not in (0x10, 0x11) or actual_version[1] != version:
            raise Refused("manifest-version-mismatch")

        def boolean(attrs, name, default):
            value = attrs.get((ANDROID, name))
            if value is None:
                return default
            if value[0] != 0x12 or value[1] not in (0, 1, NONE):
                return "unresolved"
            return "false" if value[1] == 0 else "true"

        exact, misqualified = [], []
        for receiver in receivers:
            value = receiver.get((ANDROID, "name"))
            if value is None or value[0] != 3 or not re.fullmatch(r"\.?[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", value[1]):
                raise ValueError
            name = value[1]
            resolved = package + name if name.startswith(".") else package + "." + name if "." not in name else name
            if resolved == RECEIVER:
                exact.append(receiver)
            elif name.rsplit(".", 1)[-1] == "OwnerInstaller$Result":
                misqualified.append(receiver)
        result = {"receiver_declaration": "missing", "receiver_exported": "not-declared", "receiver_enabled": "not-declared"}
        if len(exact) + len(misqualified) > 1:
            result.update(receiver_declaration="ambiguous", receiver_exported="unresolved", receiver_enabled="unresolved")
        elif exact or misqualified:
            selected = (exact or misqualified)[0]
            result.update(
                receiver_declaration="exact" if exact else "misqualified",
                receiver_exported=boolean(selected, "exported", "unset"),
                receiver_enabled=boolean(selected, "enabled", "true"),
            )
        result["application_enabled"] = boolean(application, "enabled", "true")
        return result
    except Refused:
        raise
    except (ValueError, IndexError, TypeError, struct.error, UnicodeError):
        raise Refused("manifest-invalid") from None


@contextmanager
def open_directory(path, *, dir_fd=None):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
    except OSError:
        raise Refused("cache-record-unavailable") from None
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def open_regular(path, maximum, *, dir_fd):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError:
        raise Refused("cache-record-unavailable") from None
    stream = os.fdopen(descriptor, "rb")
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
        stream.close()
        raise Refused("cache-record-unavailable")
    return stream


def bounded_zip_directory(stream, size):
    """Bound the ordinary ZIP directory before ZipFile allocates entry objects."""
    stream.seek(max(0, size - 65557))
    tail = stream.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset < 22:
        raise Refused("apk-directory-invalid")
    _, disk, directory_disk, disk_entries, entries, length, position, comment = struct.unpack_from("<4s4H2IH", tail, offset)
    end = size - len(tail) + offset
    if (
        disk != 0
        or directory_disk != 0
        or disk_entries != entries
        or not 0 < entries <= 20000
        or length > 8 * 1024**2
        or position + length > end
        or len(tail) - offset != 22 + comment
    ):
        raise Refused("apk-directory-invalid")
    if end >= 20:
        stream.seek(end - 20)
        if stream.read(4) == b"PK\x06\x07":
            # ZIP64 would replace the bounded directory fields checked above.
            raise Refused("apk-directory-invalid")
    stream.seek(0)


def inspect(root, source, expected_hash):
    if not re.fullmatch(r"[0-9a-f]{40}", source or "") or not re.fullmatch(r"[0-9a-f]{64}", expected_hash or ""):
        raise Refused("source-and-apk-hash-required")
    if not root:
        raise Refused("lab-root-required")

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise Refused("cache-receipt-invalid")
            value[key] = item
        return value

    with open_directory(Path(root).resolve(strict=True)) as root_fd, open_directory(source, dir_fd=root_fd) as cache_fd:
        with open_regular("result.json", 65536, dir_fd=cache_fd) as stream:
            receipt = json.load(stream, object_pairs_hook=unique_object)
        if not isinstance(receipt, dict):
            raise Refused("cache-receipt-invalid")
        if receipt.get("success") is not True or receipt.get("source_commit") != source or receipt.get("package") != PACKAGE:
            raise Refused("cache-source-mismatch")
        version = receipt.get("version_code")
        if type(version) is not int or not 3 <= version <= 2100000000:
            raise Refused("cache-version-invalid")
        if receipt.get("apk_sha256") != expected_hash:
            raise Refused("cache-apk-hash-mismatch")
        with open_regular("signed.apk", MAX_APK, dir_fd=cache_fd) as stream:
            before = os.fstat(stream.fileno())
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != expected_hash:
                raise Refused("cache-apk-hash-mismatch")
            bounded_zip_directory(stream, before.st_size)
            with zipfile.ZipFile(stream) as archive:
                entries = archive.infolist()
                selected = [row for row in entries if row.filename == "AndroidManifest.xml"]
                if len(entries) > 20000 or len(selected) != 1 or not 0 < selected[0].file_size <= MAX_MANIFEST:
                    raise Refused("apk-manifest-unavailable")
                with archive.open(selected[0]) as member:
                    data = member.read(MAX_MANIFEST + 1)
                if len(data) != selected[0].file_size:
                    raise Refused("apk-manifest-unavailable")
                result = binary_manifest(data, version)
                result["receiver_dex_definition"] = packaged_receiver_definition(archive, entries)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise Refused("cache-artifact-changed")
    return {"mode": "inspect-installer-manifest", "status": "observed", "cache_binding": "verified", **result}


def main(argv=None):
    class FixedErrors(argparse.ArgumentParser):
        def error(self, message):
            raise Refused("arguments-invalid")

    parser = FixedErrors(description=__doc__, allow_abbrev=False)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-apk-sha256", required=True)
    try:
        args = parser.parse_args(argv)
        result = inspect(os.environ.get("LAB_TOOLHOST_ROOT"), args.source, args.expected_apk_sha256)
    except Refused as error:
        result = {"mode": "inspect-installer-manifest", "status": "refused", "reason": str(error)}
    except Exception:
        result = {"mode": "inspect-installer-manifest", "status": "refused", "reason": "malformed-or-unavailable-cache"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
