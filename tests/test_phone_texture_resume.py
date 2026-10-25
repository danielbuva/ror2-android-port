"""Durable texture-prefix recovery with authored bundles and real process death."""

import json
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_phone_texture_producer import FIXTURE, ROOT, T, authored_body, digest


class TextureResumeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pc = self.root / "pc"
        self.pc.mkdir()
        empty = {"offset": 0, "size": 0, "path": ""}
        bodies, textures = [], []
        for number, colour in enumerate((0xF800, 0x07E0)):
            encoded = struct.pack("<HHI", colour, 0, 0)
            pixels = bytes([255, 0, 0] if number == 0 else [0, 255, 0]) * 16
            body, fields = authored_body("Source", 8, 10, encoded, empty)
            outputs = []
            for inline in (False, True) if number == 0 else (False,):
                name = f"Target {number} {inline}"
                stream = empty if inline else {"offset": 64, "size": 48, "path": "target.resS"}
                result, _ = authored_body(name, 48, 3, pixels if inline else b"", stream)
                outputs.append(
                    {
                        "bundle": "target.bundle",
                        "member": "CAB-target",
                        "path_id": number * 2 + int(inline),
                        "name": name,
                        "inline": inline,
                        "stream": stream,
                        "usage": 0,
                        "alpha_optional": False,
                        "bytes": len(result),
                        "sha256": digest(result),
                        "pixel_bytes": len(pixels),
                        "pixel_sha256": digest(pixels),
                    }
                )
            start, _ = fields["image data"]
            textures.append(
                {
                    "offset": sum(map(len, bodies)),
                    "bytes": len(body),
                    "sha256": digest(body),
                    "fields": fields,
                    "pixels": {"member": None, "offset": start + 4, "bytes": len(encoded), "sha256": digest(encoded)},
                    "operation": "dxt1-rgb",
                    "width": 4,
                    "height": 4,
                    "outputs": outputs,
                }
            )
            bodies.append(body)
        source = self.pc / "authored.bundle"
        source.write_bytes(FIXTURE.bundle([("CAB-authored", b"".join(bodies), 4)]))
        profile = {
            "input_id": T.MESH.INPUT_ID,
            "bundles": [{"path": source.name, "sha256": digest(source.read_bytes()), "members": [{"name": "CAB-authored", "textures": textures}]}],
        }
        self.profile = self.root / "profile.json"
        self.profile.write_text(json.dumps(profile))
        self.fresh, self.interrupted = self.root / "fresh", self.root / "interrupted"
        T.produce(self.profile, T.BUNDLE.sha(self.profile), self.pc, self.fresh)

    def kill_batch(self, function="pixels_input"):
        # Kill before a second canonical encode, or before the second output of
        # the first canonical texture. No Python finally handler can run.
        code = """
import importlib.util, os, signal, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("texture", sys.argv[1])
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
original = getattr(t, sys.argv[5])
calls = 0
def interrupted(*args, **kwargs):
    global calls
    calls += 1
    if calls == 2:
        os.kill(os.getpid(), signal.SIGKILL)
    return original(*args, **kwargs)
setattr(t, sys.argv[5], interrupted)
p = Path(sys.argv[2])
t.produce(p, t.BUNDLE.sha(p), Path(sys.argv[3]), Path(sys.argv[4]))
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                str(ROOT / "tools/phone-build/accepted-output/texture_produce.py"),
                str(self.profile),
                str(self.pc),
                str(self.interrupted),
                function,
            ],
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, -signal.SIGKILL, result.stderr.decode())
        receipt = json.loads((self.interrupted / "result.json").read_text())
        self.assertFalse(receipt["success"])
        self.assertEqual(receipt["objects"], 0)  # Initial pins survived SIGKILL.

    def resume(self, output=None, **kwargs):
        return T.produce(self.profile, T.BUNDLE.sha(self.profile), self.pc, output or self.interrupted, resume=True, **kwargs)

    def assert_fresh(self):
        for name in ("objects.bin", "resources.bin", "index.jsonl"):
            self.assertEqual((self.interrupted / name).read_bytes(), (self.fresh / name).read_bytes(), name)

    def test_data_is_durable_before_each_index_commit(self):
        output = self.root / "durable"
        events = []
        fsync = T.os.fsync

        def record(fd):
            inode = T.os.fstat(fd).st_ino
            for name in ("objects.bin", "resources.bin", "index.jsonl"):
                if (output / name).stat().st_ino == inode:
                    events.append(name)
            fsync(fd)

        with patch.object(T.os, "fsync", side_effect=record):
            T.produce(self.profile, T.BUNDLE.sha(self.profile), self.pc, output)
        self.assertEqual(events, ["objects.bin", "resources.bin", "index.jsonl"] * 3)

    def test_sigkill_resumes_without_reencoding_completed_canonical_texture(self):
        self.kill_batch()
        with patch.object(T, "pixels_input", wraps=T.pixels_input) as pixels:
            receipt = self.resume()
        self.assertEqual(pixels.call_count, 1)
        self.assertEqual((receipt["objects"], receipt["resource_bytes"], receipt["success"]), (3, 96, True))
        self.assert_fresh()
        with patch.object(T, "pixels_input", side_effect=AssertionError("completed texture reencoded")):
            self.assertTrue(self.resume()["success"])

    def test_partial_canonical_output_and_uncommitted_tails_are_recovered(self):
        self.kill_batch("body_output")
        for name, tail in (("objects.bin", b"incomplete object"), ("resources.bin", b"incomplete resource"), ("index.jsonl", b'{"bundle":')):
            with (self.interrupted / name).open("ab") as stream:
                stream.write(tail)
        (self.interrupted / "result.json.tmp").write_text("interrupted replacement")
        with patch.object(T, "pixels_input", wraps=T.pixels_input) as pixels, patch.object(T, "body_output", wraps=T.body_output) as bodies:
            self.assertTrue(self.resume()["success"])
        self.assertEqual((pixels.call_count, bodies.call_count), (2, 2))
        self.assert_fresh()
        self.assertFalse((self.interrupted / "result.json.tmp").exists())

    def test_corrupt_committed_data_and_index_identity_or_extent_refuse(self):
        self.kill_batch()
        for corruption in ("objects.bin", "resources.bin", "path_id", "offset", "order"):
            with self.subTest(corruption=corruption):
                output = self.root / corruption
                shutil.copytree(self.interrupted, output)
                if corruption.endswith(".bin"):
                    path = output / corruption
                    value = path.read_bytes()
                    path.write_bytes(bytes([value[0] ^ 1]) + value[1:])
                else:
                    path = output / "index.jsonl"
                    rows = [json.loads(line) for line in path.read_text().splitlines()]
                    if corruption == "order":
                        rows.reverse()
                    else:
                        rows[0][corruption] += 1
                    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                before = {p.name: p.read_bytes() for p in output.iterdir()}
                with self.assertRaisesRegex(ValueError, "checkpoint.*drift"):
                    self.resume(output)
                self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_profile_tool_input_drift_unknown_output_and_implicit_resume_refuse(self):
        self.kill_batch()
        with self.assertRaisesRegex(ValueError, "explicitly resumed"):
            T.produce(self.profile, T.BUNDLE.sha(self.profile), self.pc, self.interrupted)
        original = self.profile.read_text()
        self.profile.write_text(original + "\n")
        with self.assertRaisesRegex(ValueError, "checkpoint.*drift"):
            self.resume()
        self.profile.write_text(original)
        codec = self.root / "authored-codec"
        codec.write_bytes(b"authored unused codec")
        with self.assertRaisesRegex(ValueError, "checkpoint.*drift"):
            self.resume(jpeg_codec=codec, jpeg_codec_sha256=T.BUNDLE.sha(codec))
        unknown = self.interrupted / "unknown"
        unknown.touch()
        with self.assertRaisesRegex(ValueError, "unknown texture checkpoint"):
            self.resume()
        unknown.unlink()
        source = self.pc / "authored.bundle"
        source.write_bytes(b"changed original")
        with self.assertRaisesRegex(ValueError, "bundle drift"):
            self.resume()


if __name__ == "__main__":
    unittest.main()
