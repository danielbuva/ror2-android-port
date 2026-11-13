"""Real Git worktrees select authored staging independently of canonical HEAD."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import nullcontext

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build
import composition_io
import whole_catalog
import project_input_rebuild
import original_game_audio_build_hook as audio_hook
from common import read, write, sha
from test_original_audio_stage import write_set, stage_module as audio_stage


class LaneSourceStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve() / "canonical"
        self.base.mkdir()
        self.git(self.base, "init", "-q")
        self.git(self.base, "config", "user.name", "Fixture")
        self.git(self.base, "config", "user.email", "fixture.invalid")
        (self.base / ".gitignore").write_text("/work/\n")
        self.name = "runtime/Owned.cs"
        self.guid = "a" * 32
        for path, data in {
            "tools/unity/" + self.name: "// lane runtime\n",
            "tools/unity/" + self.name + ".meta": "fileFormatVersion: 2\nguid: " + self.guid + "\n",
            "tools/android-write-interruption/LabPendingWriteStop.java": "// lane observer\n",
            "tools/catalog/OwnedHost.cs": "// lane host\n",
            "tools/catalog/WholeCatalogBuild.cs": "// lane builder\n",
            "recipe/templates/BaselineHost.cs": "// lane baseline host\n",
            "android/Assets/Editor/BootstrapMcp.cs": "// lane bootstrap\n",
            "tools/unity/support/audio/Bootstrap.cs": "// lane audio bootstrap\n",
        }.items():
            target = self.base / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data)
        write(
            self.base / "recipe/project-inputs.json",
            {
                "editors": [
                    dict(
                        path="Assets/Editor/BaselineHost.cs",
                        template="templates/BaselineHost.cs",
                        sha256=hashlib.sha256(b"// lane baseline host\n").hexdigest(),
                    )
                ],
                "settings_templates": [],
            },
        )
        write(self.base / "recipe/runtime-sources.json", [self.name])
        write(self.base / "recipe/project-layout.json", {"runtime_source_guids": {self.name: self.guid}})
        self.git(self.base, "add", ".")
        self.git(self.base, "commit", "-qm", "lane source fixture")
        self.seed = self.git(self.base, "rev-parse", "HEAD")
        self.root = self.base.parent / "lane"
        self.git(self.base, "worktree", "add", "--detach", str(self.root), self.seed)
        extra = self.base / "tools/catalog/SourceCameraGraphicsHost.cs"
        extra.write_text("// newer canonical host\n")
        (self.base / "tools/unity/support/audio/Bootstrap.cs").write_text("// newer canonical bootstrap\n")
        self.git(self.base, "add", ".")
        self.git(self.base, "commit", "-qm", "canonical unmerged source fixture")
        self.canonical = self.git(self.base, "rev-parse", "HEAD")
        self.work = self.root / "work"
        self.project = self.work / "lab-project"
        (self.project / "Assets/Editor").mkdir(parents=True)
        (self.project / "Assets/LabLoadingScene").mkdir()
        shutil.copy2(extra, self.project / "Assets/Editor" / extra.name)
        (self.project / "Assets/Editor/SourceCameraGraphicsHost.cs.meta").write_text("guid: " + "b" * 32 + "\n")
        (self.project / "Assets/LabLoadingScene/Owned.cs").write_text("// inherited runtime\n")
        (self.project / "Assets/Editor/OwnedHost.cs").write_text("// inherited host\n")
        generated = self.project / "Assets/LabLoadingScene/WholeRuntimeConfig.cs"
        generated.write_text("// generated fixture, never replace\n")
        self.generated_name = generated.name
        (self.project / "Assets/generated-content.bin").write_bytes(b"generated content stays exact")
        write(
            self.work / "config/build-lane.json",
            dict(checkout=str(self.root), canonical_work=str(self.base / "work"), seed_commit=self.seed, canonical_source_commit=self.canonical),
        )
        # Real manifest validation/staging, with synthetic authored assembly bytes
        # in place of Unity compilation. The compiler input is the selected Git tree.
        context = patch.object(audio_stage, "ROOT", self.root)
        context.start()
        self.addCleanup(context.stop)
        manifest, _, _ = write_set(self.work, False)
        self.manifest = manifest
        self.set_compiled_bootstrap(self.base)
        audio_stage.stage(self.project, manifest, None, None)
        self.newer_dll = (self.project / audio_stage.DEFAULT_TARGETS["bootstrap"]).read_bytes()
        self.original_assets = {str(p.relative_to(self.project)): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        for module in (build, whole_catalog, composition_io, project_input_rebuild):
            for name, value in (("ROOT", self.root), ("WORK", self.work), ("RECIPE", self.root / "recipe")):
                if hasattr(module, name):
                    context = patch.object(module, name, value)
                    context.start()
                    self.addCleanup(context.stop)
        for context in (
            patch.object(whole_catalog, "BUILD_EDITOR_SOURCES", ["OwnedHost.cs", "WholeCatalogBuild.cs"]),
            patch.object(build, "WHOLE_GENERATED_RUNTIME_SOURCES", {self.generated_name}),
            patch.object(audio_hook, "restage_authored_for_lane", side_effect=self.stage_audio),
        ):
            context.start()
            self.addCleanup(context.stop)

    def git(self, root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    def set_compiled_bootstrap(self, source):
        manifest = read(self.manifest)
        row = next(row for row in manifest["outputs"] if row["role"] == "bootstrap")
        output = self.work / row["source"]
        output.write_bytes((source / "tools/unity/support/audio/Bootstrap.cs").read_bytes())
        row["sha256"] = sha(output)
        write(self.manifest, manifest)

    def stage_audio(self, project, work):
        self.assertEqual(work, self.work)
        audio_stage.restore_authored(project)
        self.set_compiled_bootstrap(self.root)
        return audio_stage.restage_authored(project, self.manifest, None, None)

    def test_inherited_extra_editor_is_retired_with_git_bytes_and_receipt(self):
        result = build.restage_lane_sources()
        self.assertFalse((self.project / "Assets/Editor/SourceCameraGraphicsHost.cs").exists())
        self.assertFalse((self.project / "Assets/Editor/SourceCameraGraphicsHost.cs.meta").exists())
        row = result["retired"][0]
        self.assertEqual(row["source_commit"], self.canonical)
        self.assertEqual(row["sha256"], hashlib.sha256(b"// newer canonical host\n").hexdigest())
        self.assertEqual(result["removed"], [row["target"]])
        self.assertTrue((self.base / row["source"]).exists())
        self.assertEqual(self.git(self.base, "rev-parse", "HEAD"), self.canonical)
        self.assertEqual(read(self.work / "config/lane-staging.json")["retired"], result["retired"])

    def test_newer_bootstrap_dll_is_replaced_from_lane_source_with_preimage(self):
        result = build.restage_lane_sources()
        path = self.project / audio_stage.DEFAULT_TARGETS["bootstrap"]
        self.assertEqual(path.read_bytes(), (self.root / "tools/unity/support/audio/Bootstrap.cs").read_bytes())
        self.assertNotEqual(path.read_bytes(), self.newer_dll)
        row = result["audio_authored_restage"]["replaced"][0]
        self.assertEqual(row["before_sha256"], hashlib.sha256(self.newer_dll).hexdigest())
        # The ordinary stager must accept the refreshed ownership receipt next.
        audio_stage.restore_authored(self.project)
        audio_stage.stage(self.project, self.manifest, None, None)

    def test_lane_owned_sources_and_generated_content_survive_repeat_staging(self):
        build.restage_lane_sources()
        build.restage_lane_sources()
        for target, source in (
            ("Assets/LabLoadingScene/Owned.cs", "tools/unity/" + self.name),
            ("Assets/Editor/OwnedHost.cs", "tools/catalog/OwnedHost.cs"),
            ("Assets/Editor/WholeCatalogBuild.cs", "tools/catalog/WholeCatalogBuild.cs"),
            ("Assets/Editor/BaselineHost.cs", "recipe/templates/BaselineHost.cs"),
            ("Assets/Editor/BootstrapMcp.cs", "android/Assets/Editor/BootstrapMcp.cs"),
        ):
            self.assertEqual((self.project / target).read_bytes(), (self.root / source).read_bytes())
        for target in ("Assets/generated-content.bin", "Assets/LabLoadingScene/" + self.generated_name):
            self.assertEqual((self.project / target).read_bytes(), self.original_assets[target])
        self.assertEqual(
            (self.project / "Assets/LabLoadingScene/Owned.cs.meta").read_bytes(), (self.root / ("tools/unity/" + self.name + ".meta")).read_bytes()
        )

    def test_existing_lane_without_snapshot_commit_uses_verified_canonical_git_source(self):
        marker = self.work / "config/build-lane.json"
        facts = read(marker)
        del facts["canonical_source_commit"]
        write(marker, facts)
        result = build.restage_lane_sources()
        self.assertEqual(result["retired"][0]["source_commit"], self.canonical)

    def test_plain_player_build_refuses_pending_plugin_receipt_until_composition(self):
        build.restage_lane_sources()
        with (
            patch.object(build, "host_build_lock", return_value=nullcontext()),
            patch.object(build, "assert_build_unblocked"),
            patch.object(build, "preflight_host"),
        ):
            with self.assertRaisesRegex(RuntimeError, "compose the complete audio receipt"):
                build.build("vulkan")

    def test_audio_overlay_content_and_receipt_remain_exact_and_pending_drift_refuses(self):
        receipt = self.project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
        original_receipt = receipt.read_bytes()
        # A camera-owned game assembly can intentionally differ from the audio
        # receipt. Authored-only refresh must neither replace it nor rebind it.
        game = self.project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
        game.write_bytes(b"camera overlay fixture")
        build.restage_lane_sources()
        self.assertEqual(receipt.read_bytes(), original_receipt)
        self.assertEqual(game.read_bytes(), b"camera overlay fixture")
        dll = self.project / audio_stage.DEFAULT_TARGETS["bootstrap"]
        dll.write_bytes(b"unreceipted plugin edit")
        with self.assertRaisesRegex(ValueError, "preimage drift"):
            audio_stage.restore_authored(self.project)
        self.assertEqual(dll.read_bytes(), b"unreceipted plugin edit")

    def test_edited_inherited_source_refuses_before_removal_or_dll_replacement(self):
        path = self.project / "Assets/Editor/SourceCameraGraphicsHost.cs"
        path.write_text("// local uncommitted edit\n")
        with self.assertRaisesRegex(RuntimeError, "unchanged committed"):
            build.restage_lane_sources()
        self.assertTrue(path.exists())
        self.assertEqual((self.project / audio_stage.DEFAULT_TARGETS["bootstrap"]).read_bytes(), self.newer_dll)


if __name__ == "__main__":
    unittest.main()
