"""Inspect authored binary XML/APK fixtures; no SDK, builder, or phone access."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


M = load("installer_manifest_inspect", "tools/phone-build/managed-host/inspect_manifest.py")
WIRE_WRITER = load("authored_manifest_pool", "tools/phone-build/owner-apk/binary_manifest.py")
SOURCE = "a" * 40


def manifest(names=(M.RECEIVER,), *, exported=False, enabled=None, app_enabled=None, package=M.PACKAGE, version=3, utf8=True, duplicate=False):
    def android(name, kind, value):
        return (M.ANDROID, name, kind, value)

    children = []
    for name in names:
        attrs = [android("name", 3, name)]
        if exported is not None:
            attrs.append(android("exported", 0x12, M.NONE if exported else 0))
        if enabled is not None:
            attrs.append(android("enabled", 0x12, M.NONE if enabled else 0))
        if duplicate:
            attrs.append(android("name", 3, name))
        children.append(("receiver", attrs, []))
    app_attrs = [] if app_enabled is None else [android("enabled", 0x12, M.NONE if app_enabled else 0)]
    tree = ("manifest", [(None, "package", 3, package), android("versionCode", 0x10, version)], [("application", app_attrs, children)])
    strings = ["android", M.ANDROID]

    def collect(node):
        tag, attrs, children = node
        for value in [tag, *(key for _, key, _, _ in attrs), *(value for _, _, kind, value in attrs if kind == 3)]:
            if value not in strings:
                strings.append(value)
        for child in children:
            collect(child)

    collect(tree)

    def element(node):
        tag, attrs, children = node
        values = b"".join(
            struct.pack(
                "<IIIHBBI", M.NONE if ns is None else strings.index(ns), strings.index(key), M.NONE, 8, 0, kind, strings.index(value) if kind == 3 else value
            )
            for ns, key, kind, value in attrs
        )
        start = struct.pack("<HHIII", 0x102, 16, 36 + len(values), 1, M.NONE)
        start += struct.pack("<IIHHHHHH", M.NONE, strings.index(tag), 20, 20, len(attrs), 0, 0, 0) + values
        end = struct.pack("<HHIIIII", 0x103, 16, 24, 1, M.NONE, M.NONE, strings.index(tag))
        return start + b"".join(element(child) for child in children) + end

    resources = [M.ATTR_IDS.get(value, 0) for value in strings]
    resource_map = struct.pack("<HHI", 0x180, 8, 8 + 4 * len(resources)) + struct.pack("<" + "I" * len(resources), *resources)
    namespace = lambda kind: struct.pack("<HHIIIII", kind, 16, 24, 1, M.NONE, 0, 1)
    body = WIRE_WRITER.string_pool(strings, utf8) + resource_map + namespace(0x100) + element(tree) + namespace(0x101)
    return struct.pack("<HHI", 3, 8, 8 + len(body)) + body


class InstallerManifestInspectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / SOURCE
        self.cache.mkdir()
        self.apk = self.cache / "signed.apk"
        self.receipt = self.cache / "result.json"
        self.write_cache()

    def write_cache(self, data=None, *, duplicate=False, entries=True):
        with warnings.catch_warnings(), zipfile.ZipFile(self.apk, "w", zipfile.ZIP_DEFLATED) as archive:
            warnings.simplefilter("ignore", UserWarning)
            if entries:
                archive.writestr("AndroidManifest.xml", manifest() if data is None else data)
                if duplicate:
                    archive.writestr("AndroidManifest.xml", manifest())
            archive.writestr("assets/unrelated", b"UNSHARED_SENTINEL")
        self.bind()

    def bind(self):
        self.digest = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        self.receipt.write_text(json.dumps(dict(success=True, source_commit=SOURCE, package=M.PACKAGE, version_code=3, apk_sha256=self.digest)))

    def invoke(self, root=None, source=SOURCE, digest=None):
        output = io.StringIO()
        with patch.dict(os.environ, {"LAB_TOOLHOST_ROOT": str(self.root if root is None else root)}), redirect_stdout(output):
            status = M.main(["--source", source, "--expected-apk-sha256", self.digest if digest is None else digest])
        text = output.getvalue()
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("UNSHARED_SENTINEL", text)
        self.assertNotIn(SOURCE, text)
        self.assertNotIn(self.digest, text)
        return status, json.loads(text)

    def test_exact_binary_manifest_utf8_utf16_and_defaults(self):
        for utf8 in (True, False):
            with self.subTest(utf8=utf8):
                self.write_cache(manifest(utf8=utf8))
                before = {p.name: p.read_bytes() for p in self.cache.iterdir()}
                status, row = self.invoke()
                self.assertEqual(status, 0)
                self.assertEqual(
                    row,
                    dict(
                        mode="inspect-installer-manifest",
                        status="observed",
                        cache_binding="verified",
                        receiver_declaration="exact",
                        receiver_exported="false",
                        receiver_enabled="true",
                        application_enabled="true",
                    ),
                )
                self.assertEqual(before, {p.name: p.read_bytes() for p in self.cache.iterdir()})

    def test_missing_and_package_remap_mismatch_are_distinct(self):
        for names, expected in (
            ([], "missing"),
            ([".OwnerInstaller$Result"], "misqualified"),
            (["OwnerInstaller$Result"], "misqualified"),
            (["authored.other.OwnerInstaller$Result"], "misqualified"),
        ):
            with self.subTest(names=names):
                self.write_cache(manifest(names))
                status, row = self.invoke()
                self.assertEqual(status, 0)
                self.assertEqual(row["receiver_declaration"], expected)

    def test_duplicate_receiver_and_security_declaration_fields(self):
        self.write_cache(manifest([M.RECEIVER, M.RECEIVER]))
        self.assertEqual(self.invoke()[1]["receiver_declaration"], "ambiguous")
        for kwargs, key, expected in (
            ({"exported": True}, "receiver_exported", "true"),
            ({"exported": None}, "receiver_exported", "unset"),
            ({"enabled": False}, "receiver_enabled", "false"),
            ({"app_enabled": False}, "application_enabled", "false"),
        ):
            with self.subTest(kwargs=kwargs):
                self.write_cache(manifest(**kwargs))
                self.assertEqual(self.invoke()[1][key], expected)

    def test_package_and_version_mismatch_refuse(self):
        for data, reason in ((manifest(package="authored.other"), "manifest-package-mismatch"), (manifest(version=4), "manifest-version-mismatch")):
            self.write_cache(data)
            status, row = self.invoke()
            self.assertEqual(status, 1)
            self.assertEqual(row["reason"], reason)

    def test_malformed_duplicate_attributes_resource_ids_and_namespace_refuse(self):
        original = manifest()
        wrong_resource = bytearray(original)
        resource = next(row for row in M.WIRE._chunks(original, 8, len(original)) if row[0] == 0x180)
        wrong_resource[resource[1] + 8 : resource[1] + resource[3]] = b"\0" * (resource[3] - 8)
        unbalanced = bytearray(original[:-24])
        struct.pack_into("<I", unbalanced, 4, len(unbalanced))
        for data in (b"UNSHARED_SENTINEL", original[:-1], manifest(duplicate=True), wrong_resource, unbalanced):
            with self.subTest(size=len(data)):
                self.write_cache(data)
                status, row = self.invoke()
                self.assertEqual(status, 1)
                self.assertEqual(row["reason"], "manifest-invalid")

    def test_source_and_hash_are_required_before_opening_cache(self):
        for source, digest in (("../UNSHARED_SENTINEL", self.digest), (SOURCE, "UNSHARED_SENTINEL")):
            with patch.object(M, "open_regular", side_effect=AssertionError("must not open")):
                status, row = self.invoke(source=source, digest=digest)
            self.assertEqual(status, 1)
            self.assertEqual(row["reason"], "source-and-apk-hash-required")

    def test_argument_errors_are_sanitized_and_abbreviation_refuses(self):
        valid = ["--source", SOURCE, "--expected-apk-sha256", self.digest]
        for arguments in ([], valid + ["--UNSHARED_SENTINEL"], ["--sou", SOURCE, "--expected-apk-sha256", self.digest]):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(M.main(arguments), 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertNotIn("UNSHARED_SENTINEL", stdout.getvalue())
            self.assertEqual(json.loads(stdout.getvalue())["reason"], "arguments-invalid")

    def test_aliased_string_pool_is_bounded_before_decoding(self):
        for utf8 in (True, False):
            pool = WIRE_WRITER.string_pool(["x" * 1024], utf8)
            original_start = struct.unpack_from("<I", pool, 20)[0]
            content = pool[original_start:]
            count, start = 4096, 28 + 4096 * 4
            amplified = struct.pack("<HHIIIIII", 1, 28, start + len(content), count, 0, 0x100 if utf8 else 0, start, 0)
            amplified += bytes(count * 4) + content
            self.write_cache(struct.pack("<HHI", 3, 8, 8 + len(amplified)) + amplified)
            with patch.object(M.WIRE, "_strings", side_effect=AssertionError("must bound before decoding")):
                self.assertEqual(self.invoke()[1]["reason"], "manifest-invalid")

    def test_receipt_requires_exact_source_package_hash_and_version(self):
        original = json.loads(self.receipt.read_text())
        for key, value in (("source_commit", "b" * 40), ("package", "authored.other"), ("success", False), ("apk_sha256", "b" * 64), ("version_code", True)):
            with self.subTest(key=key):
                self.receipt.write_text(json.dumps({**original, key: value}))
                self.assertEqual(self.invoke()[0], 1)
                self.receipt.write_text(json.dumps({k: v for k, v in original.items() if k != key}))
                self.assertEqual(self.invoke()[0], 1)

    def test_actual_apk_hash_and_duplicate_receipt_keys_refuse(self):
        self.apk.write_bytes(self.apk.read_bytes() + b"changed")
        self.assertEqual(self.invoke()[1]["reason"], "cache-apk-hash-mismatch")
        self.bind()
        self.receipt.write_text(self.receipt.read_text()[:-1] + ', "success": true}')
        self.assertEqual(self.invoke()[1]["reason"], "cache-receipt-invalid")

    def test_receipt_paths_are_ignored_and_only_manifest_member_is_opened(self):
        value = json.loads(self.receipt.read_text())
        value["apk"] = "UNSHARED_SENTINEL"
        self.receipt.write_text(json.dumps(value))
        opened = []
        actual = zipfile.ZipFile.open

        def observe(archive, member, *args, **kwargs):
            opened.append(member.filename)
            return actual(archive, member, *args, **kwargs)

        with patch.object(M.zipfile.ZipFile, "open", observe):
            self.assertEqual(self.invoke()[0], 0)
        self.assertEqual(opened, ["AndroidManifest.xml"])

    def test_missing_duplicate_and_oversized_manifest_refuse(self):
        for kwargs in ({"entries": False}, {"duplicate": True}, {"data": b"x" * (M.MAX_MANIFEST + 1)}):
            with self.subTest(kwargs=list(kwargs)):
                self.write_cache(**kwargs)
                self.assertEqual(self.invoke()[1]["reason"], "apk-manifest-unavailable")

    def test_zip_directory_is_bounded_before_zipfile_allocation(self):
        data = bytearray(self.apk.read_bytes())
        end = data.rfind(b"PK\x05\x06")
        struct.pack_into("<HH", data, end + 8, 65535, 65535)
        self.apk.write_bytes(data)
        self.bind()
        with patch.object(M.zipfile, "ZipFile", side_effect=AssertionError("must not allocate directory")):
            self.assertEqual(self.invoke()[1]["reason"], "apk-directory-invalid")

    def test_zip64_override_and_nonregular_cache_record_refuse(self):
        data = self.apk.read_bytes()
        end = data.rfind(b"PK\x05\x06")
        self.apk.write_bytes(data[:end] + b"PK\x06\x07" + bytes(16) + data[end:])
        self.bind()
        with patch.object(M.zipfile, "ZipFile", side_effect=AssertionError("must not follow ZIP64 directory")):
            self.assertEqual(self.invoke()[1]["reason"], "apk-directory-invalid")
        self.receipt.unlink()
        os.mkfifo(self.receipt)
        self.assertEqual(self.invoke()[1]["reason"], "cache-record-unavailable")

    def test_symlink_records_and_cache_refuse(self):
        for target in (self.apk, self.receipt):
            moved = target.with_suffix(".owned-copy")
            target.rename(moved)
            target.symlink_to(moved)
            self.assertEqual(self.invoke()[1]["reason"], "cache-record-unavailable")
            target.unlink()
            moved.rename(target)
        moved = self.root / "owned-cache"
        self.cache.rename(moved)
        self.cache.symlink_to(moved, target_is_directory=True)
        self.assertEqual(self.invoke()[1]["reason"], "cache-record-unavailable")

    def test_cache_directory_swap_cannot_redirect_opened_files(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        destination = Path(outside.name)
        for name in ("result.json", "signed.apk"):
            (destination / name).write_text("UNSHARED_SENTINEL")
        original, swapped = M.open_regular, False

        def replace_directory(path, maximum, *, dir_fd):
            nonlocal swapped
            if not swapped:
                self.cache.rename(self.root / "original-owned-cache")
                self.cache.symlink_to(destination, target_is_directory=True)
                swapped = True
            return original(path, maximum, dir_fd=dir_fd)

        with patch.object(M, "open_regular", replace_directory):
            status, row = self.invoke()
        self.assertEqual(status, 0)
        self.assertEqual(row["receiver_declaration"], "exact")

    def test_changed_artifact_refuses_without_exposing_stat_or_path(self):
        actual = os.fstat
        calls = 0

        def changing(descriptor):
            nonlocal calls
            calls += 1
            value = actual(descriptor)
            if calls == 4:
                return SimpleNamespace(st_size=value.st_size + 1, st_mtime_ns=value.st_mtime_ns, st_ctime_ns=value.st_ctime_ns)
            return value

        with patch.object(M.os, "fstat", changing):
            self.assertEqual(self.invoke()[1]["reason"], "cache-artifact-changed")

    def test_missing_cache_and_malformed_receipt_errors_are_fixed(self):
        self.assertEqual(self.invoke(root=self.root / "UNSHARED_SENTINEL")[1]["reason"], "malformed-or-unavailable-cache")
        self.receipt.write_text("UNSHARED_SENTINEL")
        self.assertEqual(self.invoke()[1]["reason"], "malformed-or-unavailable-cache")
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(M.main(["--source", SOURCE, "--expected-apk-sha256", self.digest]), 1)
        self.assertEqual(json.loads(output.getvalue())["reason"], "lab-root-required")


if __name__ == "__main__":
    unittest.main()
