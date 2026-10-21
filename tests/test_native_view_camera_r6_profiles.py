from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]
R6 = Path(os.environ["CAMERA_R6_HISTORICAL_ROOT"]).expanduser().resolve() if os.environ.get("CAMERA_R6_HISTORICAL_ROOT") else None
R6_RECEIPT_HASHES = {
    "default-game-3124": "3cc59e969fee9263a7e607dc9de94850dbc3154726bd380f120604d10ab47be3",
    "post-audio-r4-1034-api-d540": "26e70c8c13f4e4c030da33547b162579c1f702e840131f92a92cb923e0795e1b",
    "post-audio-point-sound-6f96-api-d540": "09f0b8c2323961288f357c9c84deb840a2753ce77d3e796d2e1930ebd6a60d7f",
    "post-audio-r10-1ced-game-6f96": "c0924434a05c08d66104d2ee336e84fba73ef7bec1266d6fd13a2d34a95cee9b",
}
REPO = next((parent for parent in (CANDIDATE, *CANDIDATE.parents) if (parent / "AGENTS.md").is_file()), CANDIDATE)
EXPECTED = {
    "default-game-3124": {
        "input": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
        "api": "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c",
        "output": "494ba9acd8ea34bed17ac56edb9a49eafa8cb5afd2f91466b95ca0d71ce3b8cd",
    },
    "post-audio-r4-1034-api-d540": {
        "input": "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c",
        "api": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
        "output": "83513fd59e81d84d093a1f9fb6d5eaaafb6382165f060dbd1b96b14990164aeb",
    },
    "post-audio-point-sound-6f96-api-d540": {
        "input": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
        "api": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
        "output": "0da94add5e860c6f3dd05f4e69d3019208e9d58294874eb373619d1756b8876d",
    },
    "post-audio-r10-1ced-game-6f96": {
        "input": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
        "api": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
        "output": "0da94add5e860c6f3dd05f4e69d3019208e9d58294874eb373619d1756b8876d",
    },
    "post-audio-music-observer-6f96-api-d540": {
        "input": "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef",
        "api": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
        "output": "4bd3b240ce5a9cb620d14ce4041f493ba013b9700d792dc9c99c8666f3af06f0",
    },
    "post-audio-music-observer-r10-1ced": {
        "input": "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef",
        "api": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
        "output": "4bd3b240ce5a9cb620d14ce4041f493ba013b9700d792dc9c99c8666f3af06f0",
    },
}
RESTORE_ONLY = {
    ("default-game-3124", "d5fc522e83cb6f6f6845b2a8b7e5de28011031fe2f3b54c0716c52db9679c65c"),
    ("post-audio-r4-1034-api-d540", "e4aeeb5acb7b81922a0a6603d01c1d407c57e9b00852b5e15ef70838e1961e5b"),
    ("post-audio-point-sound-6f96-api-d540", "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384"),
    ("post-audio-r10-1ced-game-6f96", "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384"),
    ("post-audio-music-observer-6f96-api-d540", "a2054dcfc5d14d2fdfba0fd0e61851e4a153b842be6bb6f1c0e1df8ef634762e"),
    ("post-audio-music-observer-r10-1ced", "a2054dcfc5d14d2fdfba0fd0e61851e4a153b842be6bb6f1c0e1df8ef634762e"),
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


def load_hook(path: Path):
    spec = importlib.util.spec_from_file_location("private_native_camera_hook", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load private candidate camera hook")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeViewCameraR6ProfileTests(unittest.TestCase):
    def test_exact_active_profiles_and_outputs_are_closed(self):
        pins = json.loads((REPO / "recipe/native-view-camera-transform.json").read_text())
        hook = load_hook(CANDIDATE / "scripts/lab/native_view_camera_build_hook.py")
        self.assertEqual(set(pins["profiles"]), set(EXPECTED))
        self.assertEqual(set(pins["resolver_profiles"]), set(EXPECTED))
        for name, want in EXPECTED.items():
            with self.subTest(profile=name):
                row = pins["profiles"][name]
                resolver = pins["resolver_profiles"][name]
                self.assertEqual(row["input_sha256"], want["input"])
                self.assertEqual(row["output_sha256"], want["output"])
                output_key = {
                    "default-game-3124": "camera_default",
                    "post-audio-r4-1034-api-d540": "camera_after_audio",
                    "post-audio-point-sound-6f96-api-d540": "camera_after_point_sound",
                    "post-audio-r10-1ced-game-6f96": "camera_after_r10_1ced",
                    "post-audio-music-observer-6f96-api-d540": "music_camera_output",
                    "post-audio-music-observer-r10-1ced": "music_camera_output",
                }[name]
                self.assertEqual(hook.HASHES[output_key], want["output"])
                self.assertEqual(resolver["api_sha256"], want["api"])
                # R6 receipts are immutable historical evidence from before
                # EH preservation. Verify their historical output against the
                # restore-only allowlist, never against current active pins.
                receipt_path = R6 / f"profile-{name}.json" if R6 is not None else None
                if receipt_path is not None and receipt_path.is_file():
                    self.assertEqual(digest(receipt_path), R6_RECEIPT_HASHES[name])
                    receipt = json.loads(receipt_path.read_text())
                    self.assertEqual(receipt["input_sha256"], want["input"])
                    self.assertEqual(receipt["api_sha256"], want["api"])
                    historical = receipt["new_output_sha256"]
                    self.assertIn((name, historical), RESTORE_ONLY)
                    generated = R6 / "isolated-repo" / receipt["output_relative_path"]
                    if generated.is_file():
                        self.assertEqual(digest(generated), historical)

    def test_pre_r6_outputs_are_restore_only_and_not_active_generation_pins(self):
        pins = json.loads((REPO / "recipe/native-view-camera-transform.json").read_text())
        hook = (CANDIDATE / "scripts/lab/native_view_camera_build_hook.py").read_text()
        restore_rows = {(row["profile"], row["output_sha256"]) for row in pins["restore_only_outputs"]}
        self.assertEqual(restore_rows, RESTORE_ONLY)
        active_outputs = {row["output_sha256"] for row in pins["profiles"].values()}
        self.assertTrue(active_outputs.isdisjoint(output for _, output in RESTORE_ONLY))
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
            ("camera_default_delegate_previous_restore_only", "d5fc522e83cb6f6f6845b2a8b7e5de28011031fe2f3b54c0716c52db9679c65c"),
            ("camera_after_audio_delegate_previous_restore_only", "e4aeeb5acb7b81922a0a6603d01c1d407c57e9b00852b5e15ef70838e1961e5b"),
            ("camera_after_point_sound_delegate_previous_restore_only", "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384"),
            ("camera_music_observer_delegate_previous_restore_only", "a2054dcfc5d14d2fdfba0fd0e61851e4a153b842be6bb6f1c0e1df8ef634762e"),
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
