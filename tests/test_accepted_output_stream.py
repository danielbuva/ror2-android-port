"""Exercise stream/path boundaries from the actual Android receiver with authored bytes."""

import ast
import hashlib
import os
from pathlib import Path, PurePosixPath
import select
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/phone_decode.py"


def receiver_functions():
    # The receiver has Android-only startup. Compile its real pure boundaries,
    # leaving device admission and the executable module body unexecuted.
    tree = ast.parse(SCRIPT.read_text())
    names = {"owned_paths", "safe", "read_exact", "copy_stream"}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in functions} != names:
        raise AssertionError("receiver stream boundaries missing")
    namespace = {"PurePosixPath": PurePosixPath, "hashlib": hashlib, "select": select, "os": os, "guard": lambda: None}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SCRIPT), "exec"), namespace)
    return namespace


class AcceptedOutputStreamTests(unittest.TestCase):
    def test_startup_admits_only_canonical_owned_existing_roots(self):
        functions = receiver_functions()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            owner = base / "owned"
            owner.mkdir()
            work, inputs = (owner / name for name in ("run", "inputs"))
            work.mkdir()
            inputs.mkdir()
            manifest = owner / "input.json"
            manifest.write_text("authored manifest")
            outside = base / "outside"
            outside.mkdir()
            sentinel = outside / "sentinel"
            sentinel.write_text("untouched")
            original_listing = sorted(str(p.relative_to(base)) for p in base.rglob("*"))
            self.assertEqual(functions["owned_paths"](work, inputs, manifest, owner), (work, inputs, manifest, owner))
            # Every argument role must reject lexical traversal, including paths
            # that happen to resolve back inside the workspace.
            valid = (work, inputs, manifest, owner)
            for index, paths in enumerate(
                (
                    (owner / ".." / "outside", outside, owner / "inputs" / ".." / "run"),
                    (owner / ".." / "outside", outside),
                    (owner / ".." / "outside" / "sentinel", sentinel),
                    (owner / ".." / "owned",),
                )
            ):
                for selected in paths:
                    args = list(valid)
                    args[index] = selected
                    with self.subTest(role=index, selected=selected), self.assertRaises(ValueError):
                        functions["owned_paths"](*args)
            link = owner / "linked"
            link.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                functions["owned_paths"](link, inputs, manifest, owner)
            link.unlink()
            with self.assertRaisesRegex(ValueError, "absent"):
                functions["owned_paths"](owner / "missing", inputs, manifest, owner)
            self.assertEqual(sentinel.read_text(), "untouched")
            self.assertEqual(sorted(str(p.relative_to(base)) for p in base.rglob("*")), original_listing)
            self.assertFalse((outside / "process.json").exists())
            self.assertFalse((outside / "output").exists())

    def test_paths_refuse_escape_and_symlinks_without_touching_external_data(self):
        functions = receiver_functions()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "owned"
            root.mkdir()
            outside = Path(temporary) / "outside"
            outside.mkdir()
            sentinel = outside / "sentinel"
            sentinel.write_bytes(b"external authored sentinel")
            (root / "link").symlink_to(outside, target_is_directory=True)
            (root / "broken").symlink_to(outside / "absent")
            for name in ("", ".", "/absolute", "../outside/sentinel", "a/../../outside", "a/./b", "a//b", "a/", "link/sentinel", "broken"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    functions["safe"](root, name)
            self.assertEqual(functions["safe"](root, "payload/authored.bundle"), root / "payload/authored.bundle")
            self.assertEqual(sentinel.read_bytes(), b"external authored sentinel")
            self.assertFalse((root / "payload").exists())

    def test_exact_read_preserves_following_frame_and_refuses_truncation(self):
        functions = receiver_functions()
        reader, writer = os.pipe()
        try:
            functions["wire"] = reader
            os.write(writer, b"firstnext")
            os.close(writer)
            writer = None
            self.assertEqual(functions["read_exact"](5), b"first")
            self.assertEqual(functions["read_exact"](4), b"next")
            with self.assertRaisesRegex(EOFError, "truncated"):
                functions["read_exact"](1)
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)

    def test_copy_hashes_multiple_chunks_without_consuming_next_frame(self):
        functions = receiver_functions()
        payload = bytes(range(256)) * 1025
        # A regular file is select-readable and avoids platform-dependent pipe
        # capacity while exercising real os.read, incremental writes and hashes.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "wire"
            source.write_bytes(payload + b"next-frame")
            dest = root / "output"
            with source.open("rb", buffering=0) as stream:
                functions["wire"] = stream.fileno()
                self.assertEqual(functions["copy_stream"](len(payload), dest), hashlib.sha256(payload).hexdigest())
                self.assertEqual(functions["read_exact"](10), b"next-frame")
            self.assertEqual(dest.read_bytes(), payload)

    def test_existing_destination_refuses_before_consuming_input(self):
        functions = receiver_functions()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "wire"
            source.write_bytes(b"unchanged input")
            dest = root / "existing"
            dest.write_bytes(b"retained output")
            with source.open("rb", buffering=0) as stream:
                functions["wire"] = stream.fileno()
                with self.assertRaises(FileExistsError):
                    functions["copy_stream"](4, dest)
                self.assertEqual(stream.tell(), 0)
            self.assertEqual(dest.read_bytes(), b"retained output")

    def test_truncated_copy_retains_partial_output_without_false_success(self):
        functions = receiver_functions()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "wire"
            complete_chunk = b"a" * 65536
            source.write_bytes(complete_chunk + b"partial")
            dest = root / "failed-output"
            with source.open("rb", buffering=0) as stream:
                functions["wire"] = stream.fileno()
                with self.assertRaises(EOFError):
                    functions["copy_stream"](len(complete_chunk) + 100, dest)
            self.assertEqual(dest.read_bytes(), complete_chunk)
