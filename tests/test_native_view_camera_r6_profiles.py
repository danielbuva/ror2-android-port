from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]
R6 = CANDIDATE / "work/coordination/original-camera-update-next/r6"
REPO = next((parent for parent in (CANDIDATE, *CANDIDATE.parents) if (parent / "AGENTS.md").is_file()), CANDIDATE)
EXPECTED = {
    "default-game-3124": {
        "input": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
        "api": "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c",
        "output": "d5fc522e83cb6f6f6845b2a8b7e5de28011031fe2f3b54c0716c52db9679c65c",
    },
    "post-audio-r4-1034-api-d540": {
        "input": "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c",
        "api": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
        "output": "e4aeeb5acb7b81922a0a6603d01c1d407c57e9b00852b5e15ef70838e1961e5b",
    },
    "post-audio-point-sound-6f96-api-d540": {
        "input": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
        "api": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
        "output": "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384",
    },
    "post-audio-r10-1ced-game-6f96": {
        "input": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
        "api": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
        "output": "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384",
    },
}
RESTORE_ONLY = {
    ("default-game-3124", "236fab2c616b1a017971c316437ec1a9fa9f6b3999563263d4a8ab689a1e59b6"),
    ("post-audio-r4-1034-api-d540", "e16e01bc6545bb6d8248c9196be890b99cf60df721d1b894b8d9871a880c7f91"),
    ("post-audio-r4-1034", "e16e01bc6545bb6d8248c9196be890b99cf60df721d1b894b8d9871a880c7f91"),
    ("post-audio-point-sound-6f96-api-d540", "f6bc1a860e8abe2c82a397a83e55ec2050136e91763ade302ed0e181b320083c"),
    ("post-audio-r10-1ced-game-6f96", "f6bc1a860e8abe2c82a397a83e55ec2050136e91763ade302ed0e181b320083c"),
    ("default-game-3124", "e237af4fea2b04dfecb54593e39d98862078a66de4a08272b75531303fe4b33d"),
    ("post-audio-r4-1034-api-d540", "aa7ca07c363d6d2d144cc6d378264302846036661daa631b8a3a52dc9ed15ffc"),
    ("post-audio-point-sound-6f96-api-d540", "41b66d072085f70b6929dcd2a566fffff3f26b9c886d8781624e52ae8ab7e92f"),
    ("post-audio-r10-1ced-game-6f96", "41b66d072085f70b6929dcd2a566fffff3f26b9c886d8781624e52ae8ab7e92f"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeViewCameraR6ProfileTests(unittest.TestCase):
    def test_exact_active_profiles_and_outputs_are_closed(self):
        pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        self.assertEqual(set(pins["profiles"]), set(EXPECTED))
        self.assertEqual(set(pins["resolver_profiles"]), set(EXPECTED))
        for name, want in EXPECTED.items():
            with self.subTest(profile=name):
                row = pins["profiles"][name]
                resolver = pins["resolver_profiles"][name]
                self.assertEqual(row["input_sha256"], want["input"])
                self.assertEqual(row["output_sha256"], want["output"])
                self.assertEqual(resolver["api_sha256"], want["api"])
                # R6 receipts are immutable historical evidence from before
                # EH preservation. Verify their historical output against the
                # restore-only allowlist, never against current active pins.
                receipt_path = R6 / f"profile-{name}.json"
                if receipt_path.is_file():
                    receipt = json.loads(receipt_path.read_text())
                    self.assertEqual(receipt["input_sha256"], want["input"])
                    self.assertEqual(receipt["api_sha256"], want["api"])
                    historical = receipt["new_output_sha256"]
                    self.assertIn((name, historical), RESTORE_ONLY)
                    generated = R6 / "isolated-repo" / receipt["output_relative_path"]
                    if generated.is_file():
                        self.assertEqual(digest(generated), historical)

    def test_pre_r6_outputs_are_restore_only_and_not_active_generation_pins(self):
        pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        hook = (CANDIDATE / "scripts/lab/native_view_camera_build_hook.py").read_text()
        restore_rows = {(row["profile"], row["output_sha256"]) for row in pins["restore_only_outputs"]}
        expected_rows = RESTORE_ONLY
        self.assertEqual(restore_rows, expected_rows)
        active_outputs = {row["output_sha256"] for row in pins["profiles"].values()}
        self.assertTrue(active_outputs.isdisjoint(output for _, output in restore_rows))
        for key, value in (
            ("camera_default_previous_restore_only", "236fab2c616b1a017971c316437ec1a9fa9f6b3999563263d4a8ab689a1e59b6"),
            (
                "camera_after_audio_previous_restore_only",
                "e16e01bc6545bb6d8248c9196be890b99cf60df721d1b894b8d9871a880c7f91",
            ),
            (
                "camera_predecessor_f6bc_restore_only",
                "f6bc1a860e8abe2c82a397a83e55ec2050136e91763ade302ed0e181b320083c",
            ),
        ):
            self.assertIn(f'"{key}": "{value}"', hook)
        self.assertIn("is_restore_only_predecessor", hook)
        self.assertIn("camera_profiles", hook)

    def test_all_authored_camera_sources_match_recipe_pins(self):
        pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        for role, relative in pins["source_paths"].items():
            path = CANDIDATE / relative
            if not path.is_file():
                path = REPO / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(digest(path), pins["source_sha256"][role], role)


if __name__ == "__main__":
    unittest.main()
