"""Exercise actual XAR/gzip/CPIO extraction using independently authored archives."""

import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib


PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/sdk_inputs.py"
SPEC = importlib.util.spec_from_file_location("sdk_inputs", PATH)
SDK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SDK)
DATA = b"independently authored SDK-input fixture\n"
NAME = "Data/owner.bin"
WANTED = {NAME: (len(DATA), hashlib.sha256(DATA).hexdigest())}


def cpio(entries, old=False):
    out = bytearray()
    for name, data, mode in [*entries, ("TRAILER!!!", b"", stat.S_IFREG | 0o644)]:
        name = (name + "\0").encode()
        if old:
            values = [0, 1, mode, 0, 0, 1, 0]
            header = "070707" + "".join(f"{v:06o}" for v in values) + f"{0:011o}{len(name):06o}{len(data):011o}"
            out += header.encode() + name + data
        else:
            values = [1, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
            out += ("070701" + "".join(f"{v:08x}" for v in values)).encode() + name
            out += bytes((-len(out)) % 4)
            out += data
            out += bytes((-len(out)) % 4)
    return bytes(out)


def component(entries, *, old=False, truncate=False):
    payload = gzip.compress(cpio(entries, old), mtime=0)
    if truncate:
        payload = payload[:-5]
    info = b'<pkg-info identifier="com.unity3d.AndroidPlayer" install-location="/Applications/Unity/PlaybackEngines/AndroidPlayer"/>'
    packed_info = zlib.compress(info)
    toc = f"""<xar><toc><file><name>TargetSupport.pkg.tmp</name>
    <file><name>Payload</name><data><offset>0</offset><length>{len(payload)}</length><size>{len(payload)}</size><encoding style="application/octet-stream"/></data></file>
    <file><name>PackageInfo</name><data><offset>{len(payload)}</offset><length>{len(packed_info)}</length><size>{len(info)}</size><encoding style="application/x-gzip"/></data></file>
    </file></toc></xar>""".encode()
    packed_toc = zlib.compress(toc)
    return struct.pack(">IHHQQI", 0x78617221, 28, 1, len(packed_toc), len(toc), 1) + packed_toc + payload + packed_info


class SDKInputTests(unittest.TestCase):
    def run_archive(self, root, archive, output):
        source = root / "owner.pkg"
        source.write_bytes(archive)
        with patch.multiple(SDK, COMPONENT_BYTES=len(archive), COMPONENT_SHA256=hashlib.sha256(archive).hexdigest(), FILES=WANTED, RESERVE=0):
            return SDK.extract(source, output)

    def test_complete_container_both_cpio_encodings_and_no_script_execution(self):
        for old in (False, True):
            with self.subTest(old=old), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                entries = [("./Scripts/postinstall", b"never execute or extract this", stat.S_IFREG | 0o755), ("./" + NAME, DATA, stat.S_IFREG | 0o644)]
                result = self.run_archive(root, component(entries, old=old), root / "new")
                self.assertTrue(result["success"])
                self.assertEqual((root / "new" / SDK.PREFIX / NAME).read_bytes(), DATA)
                self.assertEqual(result["members_read"], 2)
                self.assertFalse((root / "new/Scripts").exists())
                self.assertFalse(result["phone_qualified"])
                with self.assertRaises(FileExistsError):
                    self.run_archive(root, component(entries, old=old), root / "new")
                self.assertEqual((root / "new" / SDK.PREFIX / NAME).read_bytes(), DATA)

    def test_missing_duplicate_traversal_symlink_hash_and_truncation_refuse(self):
        good = (NAME, DATA, stat.S_IFREG | 0o644)
        cases = {
            "missing": component([]),
            "duplicate": component([good, good]),
            "traversal": component([("../escape", b"outside", stat.S_IFREG | 0o644), good]),
            "symlink": component([(NAME, DATA, stat.S_IFLNK | 0o777)]),
            "wrong-hash": component([(NAME, b"x" * len(DATA), stat.S_IFREG | 0o644)]),
            "truncated": component([good], truncate=True),
        }
        for label, archive in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                sentinel = root / "escape"
                sentinel.write_bytes(b"retain outside")
                with self.assertRaises((ValueError, EOFError)):
                    self.run_archive(root, archive, root / "new")
                self.assertEqual(sentinel.read_bytes(), b"retain outside")
                result = json.loads((root / "new/result.json").read_text())
                self.assertFalse(result["success"])

    def test_redirected_destination_never_writes_outside(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            outside = root / "outside"
            outside.mkdir()
            output = root / "output"
            output.mkdir()
            (output / "PlaybackEngines").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "redirected"):
                SDK.copy_cpio(io.BytesIO(cpio([(NAME, DATA, stat.S_IFREG | 0o644)])), output, WANTED, SDK.time.monotonic())
            self.assertEqual(list(outside.iterdir()), [])

    def test_unknown_component_refuses_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "unknown.pkg"
            source.write_bytes(b"unknown owner component")
            with self.assertRaisesRegex(ValueError, "unsupported"):
                SDK.extract(source, root / "new")
            self.assertFalse((root / "new").exists())
