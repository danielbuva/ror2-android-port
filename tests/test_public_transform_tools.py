"""Archive and execution-boundary contracts with authored synthetic data only."""

import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import assembly_transforms
import public_transform_tools as public
from common import read, sha


class PublicToolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.cache = self.root / "archives"
        self.cache.mkdir()
        self.content = b"authored source or reference fixture"
        self.recipe = dict(
            schema=1,
            kind="owner-public-dotnet8-v1",
            artifacts=[],
            notices=[],
            runtimes={"host10": {"version": "10.0.12", "roll_forward": "Major"}},
            compiler_version="fixture",
        )
        for role in ("compiler", "cecil", "references"):
            archive = self.cache / (role + (".tar.gz" if role == "cecil" else ".zip"))
            member = dict(archive="source/fixture.cs", path=role + "/fixture.cs", bytes=len(self.content), sha256=hashlib.sha256(self.content).hexdigest())
            if role == "cecil":
                member["git_blob"] = hashlib.sha1(b"blob " + str(len(self.content)).encode() + b"\0" + self.content).hexdigest()
                with tarfile.open(archive, "w:gz") as stream:
                    info = tarfile.TarInfo(member["archive"])
                    info.size = len(self.content)
                    stream.addfile(info, io.BytesIO(self.content))
            else:
                with zipfile.ZipFile(archive, "w") as stream:
                    stream.writestr(member["archive"], self.content)
            self.recipe["artifacts"].append(
                dict(
                    role=role,
                    filename=archive.name,
                    format="tar.gz" if role == "cecil" else "zip",
                    bytes=archive.stat().st_size,
                    sha256=sha(archive),
                    members=[member],
                )
            )
        self.destination = self.root / "materials"

    def paths(self):
        return public.archive_state(self.cache, self.recipe)

    def repin(self, role):
        artifact = next(a for a in self.recipe["artifacts"] if a["role"] == role)
        path = self.cache / artifact["filename"]
        artifact.update(bytes=path.stat().st_size, sha256=sha(path))

    def test_real_recipe_pins_expected_sources_references_and_notices(self):
        recipe = public.load_recipe()
        self.assertEqual(sum(len(a["members"]) for a in recipe["artifacts"]), 358)
        self.assertEqual(
            len([m for a in recipe["artifacts"] for m in a["members"] if m["path"].startswith("cecil-source/") and m["path"].endswith(".cs")]), 132
        )
        self.assertEqual(len([m for a in recipe["artifacts"] for m in a["members"] if m["path"].startswith("refs/")]), 163)
        self.assertEqual(recipe["runtimes"]["android8"]["version"], "8.0.32")
        with patch.object(public, "RECIPE_SHA256", "0" * 64), self.assertRaisesRegex(RuntimeError, "recipe drift"):
            public.load_recipe()

    def test_selected_members_extract_exactly_and_unused_members_never_execute(self):
        artifact = self.recipe["artifacts"][0]
        with zipfile.ZipFile(self.cache / artifact["filename"], "a") as stream:
            stream.writestr("../unselected.py", "raise RuntimeError('never execute or extract')")
        self.repin("compiler")
        with patch.object(public, "ROOT", self.root):
            manifest = public.extract(self.paths(), self.destination, self.recipe)
        self.assertEqual(len(manifest), 3)
        self.assertFalse((self.root / "unselected.py").exists())
        for artifact in self.recipe["artifacts"]:
            row = artifact["members"][0]
            self.assertEqual((self.destination / row["path"]).read_bytes(), self.content)

    def test_archive_mutation_refuses_before_extraction_directory(self):
        paths = self.paths()
        paths["compiler"].write_bytes(b"authored corruption")
        with self.assertRaisesRegex(RuntimeError, "before extraction"):
            public.extract(paths, self.destination, self.recipe)
        self.assertFalse(self.destination.exists())
        with self.assertRaisesRegex(RuntimeError, "archive drift"):
            self.paths()

    def test_archive_link_and_ancestor_link_refuse(self):
        original = self.cache / self.recipe["artifacts"][0]["filename"]
        saved = self.root / "saved.zip"
        original.rename(saved)
        original.symlink_to(saved)
        with self.assertRaisesRegex(RuntimeError, "archive drift"):
            self.paths()
        directory = self.root / "alias"
        directory.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "ancestor links"):
            public.archive_state(directory, self.recipe)

    def test_duplicate_zip_and_link_members_refuse(self):
        artifact = self.recipe["artifacts"][0]
        path = self.cache / artifact["filename"]
        for kind in ("duplicate", "link"):
            with zipfile.ZipFile(path, "w") as stream:
                info = zipfile.ZipInfo(artifact["members"][0]["archive"])
                if kind == "link":
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                stream.writestr(info, self.content)
                if kind == "duplicate":
                    with self.assertWarns(UserWarning):
                        stream.writestr(info, self.content)
            self.repin("compiler")
            with self.subTest(kind=kind), self.assertRaisesRegex(RuntimeError, "Duplicate|kind/size"):
                public.extract(self.paths(), self.root / kind, self.recipe)

    def test_tar_link_duplicate_and_missing_members_refuse(self):
        artifact = self.recipe["artifacts"][1]
        path = self.cache / artifact["filename"]
        for kind in ("link", "hardlink", "duplicate", "missing"):
            with tarfile.open(path, "w:gz") as stream:
                if kind != "missing":
                    info = tarfile.TarInfo(artifact["members"][0]["archive"])
                    if kind in {"link", "hardlink"}:
                        info.type = tarfile.SYMTYPE if kind == "link" else tarfile.LNKTYPE
                        info.linkname = "../../escape"
                        stream.addfile(info)
                    else:
                        info.size = len(self.content)
                        stream.addfile(info, io.BytesIO(self.content))
                        stream.addfile(info, io.BytesIO(self.content))
            self.repin("cecil")
            with self.subTest(kind=kind), self.assertRaisesRegex(RuntimeError, "kind/size|Missing"):
                public.extract(self.paths(), self.root / kind, self.recipe)

    def test_member_hash_git_blob_and_path_drift_refuse(self):
        for kind in ("hash", "git", "path"):
            recipe = copy.deepcopy(self.recipe)
            row = recipe["artifacts"][1]["members"][0]
            row[{"hash": "sha256", "git": "git_blob", "path": "path"}[kind]] = "../escape" if kind == "path" else "0" * (40 if kind == "git" else 64)
            with self.subTest(kind=kind), self.assertRaisesRegex(RuntimeError, "drift|Unsafe"):
                public.extract(self.paths(), self.root / kind, recipe)
            self.assertFalse((self.root / "escape").exists())

    def test_existing_material_directory_is_never_reused(self):
        self.destination.mkdir()
        marker = self.destination / "kept"
        marker.write_bytes(b"authored marker")
        with self.assertRaises(FileExistsError):
            public.extract(self.paths(), self.destination, self.recipe)
        self.assertEqual(marker.read_bytes(), b"authored marker")

    def test_unsafe_and_noncanonical_paths_refuse(self):
        for path in ("", ".", "/absolute", "../escape", "a/../escape", "a//b", "a\\b"):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                public.relative(path)

    def test_wrong_runtime_refuses_before_any_downloaded_compiler_execution(self):
        managed = self.root / "managed"
        managed.mkdir()
        (managed / "Original.dll").write_bytes(b"authored metadata")
        src = self.root / "tools/assembly-transforms/Program.cs"
        src.parent.mkdir(parents=True)
        src.write_text("authored tool source")
        witness = self.root / "witness.cs"
        witness.write_text("authored witness")
        self.recipe["witness"] = dict(path="witness.cs", sha256=sha(witness))
        transforms = dict(tool_sources={"tools/assembly-transforms/Program.cs": sha(src)}, steps=[dict(inputs={"Original.dll": sha(managed / "Original.dll")})])
        launcher = self.root / "dotnet"
        sentinel = self.root / "compiler-executed"
        launcher.write_text(
            "#!/bin/sh\nif [ \"$1\" = --list-runtimes ]; then\n echo 'Microsoft.NETCore.App 9.0.0 [fixture]'\nelse\n touch '" + str(sentinel) + "'\nfi\n"
        )
        launcher.chmod(0o700)
        attempt = self.root / "attempt"
        attempt.mkdir()
        with (
            patch.object(public, "ROOT", self.root),
            patch.object(public, "load_recipe", return_value=self.recipe),
            patch.object(assembly_transforms, "load_recipe", return_value=transforms),
            self.assertRaisesRegex(RuntimeError, "runtime closure"),
        ):
            public.generate(managed, attempt, transforms, archives=self.cache, launcher=launcher, host="host10")
        self.assertFalse(sentinel.exists())
        receipt = read(attempt / "public-tools-receipt.json")
        self.assertEqual(receipt["phase"], "failed")
        self.assertFalse(receipt["success"])
        self.assertTrue((attempt / "runtimes.stdout.log").exists())


if __name__ == "__main__":
    unittest.main()
