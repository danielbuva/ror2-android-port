"""Actual atomic staging preserves hashes and source independence with clones."""

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/lab" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtifactCloneHookTests(unittest.TestCase):
    def test_atomic_camera_and_music_copies_preserve_bytes_and_do_not_hardlink(self):
        hooks = ((load("native_view_camera_build_hook"), "_atomic_copy"), (load("original_music_output_observer_build_hook"), "_copy_verified"))
        for hook, name in hooks:
            with self.subTest(owner=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                source, target = root / "source.dll", root / "target.dll"
                source.write_bytes(b"authored new assembly")
                target.write_bytes(b"authored old assembly")
                new_hash = hashlib.sha256(source.read_bytes()).hexdigest()
                old_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                invoke = getattr(hook, name)
                if name == "_atomic_copy":
                    invoke(source, target, new_hash, replace_hash=old_hash)
                else:
                    invoke(source, target, new_hash, old_hash)
                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
                target.write_bytes(b"later authored mutation")
                self.assertEqual(source.read_bytes(), b"authored new assembly")

    def test_wrong_source_hash_keeps_the_prior_owned_target(self):
        for hook in (load("native_view_camera_build_hook"), load("original_music_output_observer_build_hook")):
            with self.subTest(owner=hook.__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                source, target = root / "source.dll", root / "target.dll"
                source.write_bytes(b"authored source")
                target.write_bytes(b"prior authored target")
                old_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, "hash"):
                    if hasattr(hook, "_atomic_copy"):
                        hook._atomic_copy(source, target, "0" * 64, replace_hash=old_hash)
                    else:
                        hook._copy_verified(source, target, "0" * 64, old_hash)
                self.assertEqual(target.read_bytes(), b"prior authored target")


if __name__ == "__main__":
    unittest.main()
