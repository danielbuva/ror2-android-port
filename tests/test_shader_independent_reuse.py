"""Reuse validated native intermediates without running Wine or changing shared tool state."""

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import shader_programs as programs
from common import digest, write


class IndependentReuseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.out = self.root / "output"
        self.out.mkdir()
        self.independent = self.root / "pipeline"
        self.tree = {"m_ParsedForm": {"m_Name": "Synthetic"}}
        self.context = (self.tree, b"", [{"keywords": []}], [b"synthetic native program"], {})
        self.layout = {"textures": []}
        self.hlsl = b"synthetic validated intermediate"
        stem = "program-" + digest("Synthetic")[:12] + "-0"
        path = self.independent / (stem + "-independent") / (stem + ".hlsl")
        path.parent.mkdir(parents=True)
        path.write_bytes(self.hlsl)
        self.record = {
            "shader": "Synthetic",
            "index": 0,
            "native_roundtrip_identical": True,
            "origin": "HLSLDecompiler validated fallback; d3dasm sample-c instruction counterexample preserved",
            "dxbc_sha256": hashlib.sha256(self.context[3][0]).hexdigest(),
            "hlsl_sha256": hashlib.sha256(self.hlsl).hexdigest(),
            "layout": self.layout,
        }
        write(self.independent / "receipt.json", {"programs": [self.record]})
        for name, replacement in (
            ("run", self.run_tool),
            ("selected_layout", lambda *args: copy.deepcopy(self.layout)),
            ("bind_hlsl", lambda *args: ("synthetic bound", [], {}, None, [])),
        ):
            patcher = patch.object(programs, name, side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.commands = []

    def run_tool(self, args):
        self.assertEqual(args[0], "synthetic-decompiler")
        self.commands.append(args)
        output = Path(args[-1])
        if "hlsl" in args:
            output.write_text("not decompiled")
        elif "--assemble" in args:
            output.write_bytes(self.context[3][0])
        else:
            output.write_text("synthetic assembly")

    def emitter(self, independent=True):
        return programs.NativePrograms(
            self.out, {"programs": []}, "synthetic-decompiler", allow_independent=False, independent=self.independent if independent else None
        )

    def test_hash_verified_intermediate_reuses_pure_binding_and_preserves_inputs(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.independent.rglob("*") if p.is_file()}
        emitter = self.emitter()
        self.assertEqual(emitter.bound(self.context, 0), ("synthetic bound", [], {}, []))
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.independent.rglob("*") if p.is_file()})
        self.assertEqual(emitter.bound(self.context, 0), ("synthetic bound", [], {}, []))
        self.assertEqual(len(self.commands), 3)

    def test_missing_reuse_never_falls_back_to_writable_bottle(self):
        with self.assertRaisesRegex(RuntimeError, "writable bottle"):
            self.emitter(False).bound(self.context, 0)
        self.assertEqual(len(self.commands), 3)

    def test_program_hlsl_validation_identity_and_bound_layout_drift_fail(self):
        for key, value in (
            ("dxbc_sha256", "0" * 64),
            ("hlsl_sha256", "0" * 64),
            ("native_roundtrip_identical", False),
            ("origin", "unvalidated"),
            ("index", 1),
            ("layout", {"textures": ["drift"]}),
        ):
            write(self.independent / "receipt.json", {"programs": [dict(self.record, **{key: value})]})
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "drift"):
                self.emitter().bound(self.context, 0)
