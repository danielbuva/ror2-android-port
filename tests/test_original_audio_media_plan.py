from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "tools" / "unity" / "support" / "audio" / "generators"),
)
from original_media_plan import plan_external_media, required_copy_free_bytes  # noqa: E402


class ExternalMediaPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bank_root = "Audio/Windows"
        self.id = 12345
        self.data = b"fixture-full-wem"
        digest = hashlib.sha256(self.data).hexdigest()
        self.source_relative = f"{self.bank_root}/Media/{self.id}.wem"
        source = self.root / self.source_relative
        source.parent.mkdir(parents=True)
        source.write_bytes(self.data)
        self.index_rows = [
            {
                "path": "Music.bnk",
                "declared": [{"id": self.id, "streaming": True, "location": "Memory"}],
                "embedded": [{"id": self.id, "bytes": 8}],
            }
        ]
        self.xml_rows = [
            {
                "short_name": "Music",
                "media": [
                    {
                        "id": self.id,
                        "streaming": True,
                        "location": "Memory",
                        "path": f"Media/{self.id}.wem",
                    }
                ],
            }
        ]
        self.inventory_rows = [{"path": self.source_relative, "size": len(self.data), "sha256": digest}]

    def plan(self):
        return plan_external_media(
            ["Music"],
            self.index_rows,
            self.xml_rows,
            self.inventory_rows,
            self.root,
            self.bank_root,
        )

    def test_streamed_prefetch_still_requires_complete_external_file(self) -> None:
        plan = self.plan()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["media_id"], self.id)
        self.assertEqual(plan[0]["relative_path"], f"Media/{self.id}.wem")
        self.assertEqual(plan[0]["referenced_by"], ["Music"])

    def test_nonstreamed_memory_media_requires_embedded_bytes_but_not_wem(self) -> None:
        self.index_rows[0]["declared"] = [{"id": self.id, "streaming": False, "location": "Memory"}]
        self.index_rows[0]["embedded"] = [{"id": self.id, "bytes": 128}]
        self.xml_rows[0]["media"][0].update(streaming=False, path=None)
        self.inventory_rows = []
        self.assertEqual(self.plan(), [])
        self.index_rows[0]["embedded"] = []
        with self.assertRaisesRegex(ValueError, "not embedded"):
            self.plan()

    def test_missing_full_external_file_refuses(self) -> None:
        (self.root / self.source_relative).unlink()
        with self.assertRaisesRegex(ValueError, "missing, linked or size-drifted"):
            self.plan()

    def test_symlinked_media_ancestor_refuses_even_when_target_bytes_match(
        self,
    ) -> None:
        source = self.root / self.source_relative
        payload = self.root / "elsewhere" / source.name
        payload.parent.mkdir()
        payload.write_bytes(self.data)
        source.unlink()
        source.parent.rmdir()
        source.parent.symlink_to(payload.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "source path contains a symlink component"):
            self.plan()

    def test_inventory_hash_drift_refuses(self) -> None:
        self.inventory_rows[0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash differs"):
            self.plan()

    def test_unsafe_path_refuses_before_file_resolution(self) -> None:
        self.xml_rows[0]["media"][0]["path"] = f"Media/../{self.id}.wem"
        with self.assertRaisesRegex(ValueError, "unsafe or noncanonical"):
            self.plan()

    def test_noncanonical_repeated_separator_refuses(self) -> None:
        self.xml_rows[0]["media"][0]["path"] = f"Media//{self.id}.wem"
        with self.assertRaisesRegex(ValueError, "unsafe or noncanonical"):
            self.plan()

    def test_metadata_mode_conflict_refuses(self) -> None:
        self.xml_rows[0]["media"][0]["streaming"] = False
        with self.assertRaisesRegex(ValueError, "mode differs"):
            self.plan()

    def test_xml_external_mode_cannot_override_embedded_memory_declaration(
        self,
    ) -> None:
        self.index_rows[0]["declared"] = [{"id": self.id, "streaming": False, "location": "Memory"}]
        self.index_rows[0]["embedded"] = [{"id": self.id, "bytes": 8}]
        with self.assertRaisesRegex(ValueError, "mode differs between bank index and SoundbanksInfo"):
            self.plan()

    def test_duplicate_inventory_path_refuses_even_when_one_row_matches(self) -> None:
        self.inventory_rows.append(dict(self.inventory_rows[0], sha256="f" * 64))
        with self.assertRaisesRegex(ValueError, "one exact external media path"):
            self.plan()

    def test_same_id_referenced_by_two_banks_coalesces_once(self) -> None:
        self.index_rows.append(
            {
                "path": "UI.bnk",
                "declared": [{"id": self.id, "streaming": True, "location": "Memory"}],
                "embedded": [{"id": self.id, "bytes": 8}],
            }
        )
        self.xml_rows.append({"short_name": "UI", "media": [dict(self.xml_rows[0]["media"][0])]})
        plan = plan_external_media(
            ["Music", "UI"],
            self.index_rows,
            self.xml_rows,
            self.inventory_rows,
            self.root,
            self.bank_root,
        )
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["referenced_by"], ["Music", "UI"])

    def test_xml_only_external_reference_refuses(self) -> None:
        self.index_rows[0]["declared"] = []
        with self.assertRaisesRegex(ValueError, "missing from bank index"):
            self.plan()

    def test_unmapped_selected_bank_refuses(self) -> None:
        with self.assertRaisesRegex(ValueError, "map uniquely"):
            plan_external_media(
                ["Missing"],
                self.index_rows,
                self.xml_rows,
                self.inventory_rows,
                self.root,
                self.bank_root,
            )

    def test_free_space_accounts_for_remaining_files_and_atomic_temp_peak(self) -> None:
        self.assertEqual(required_copy_free_bytes([100, 40, 25]), 265)
        self.assertEqual(required_copy_free_bytes([]), 0)
        with self.assertRaisesRegex(ValueError, "positive integers"):
            required_copy_free_bytes([100, 0])
        with self.assertRaisesRegex(ValueError, "overflows"):
            required_copy_free_bytes([(1 << 63) - 1])


if __name__ == "__main__":
    unittest.main()
