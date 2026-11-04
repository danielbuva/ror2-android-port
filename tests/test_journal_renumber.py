import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/journal-renumber.py"
SPEC = importlib.util.spec_from_file_location("journal_renumber", SCRIPT)
journal_renumber = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = journal_renumber
SPEC.loader.exec_module(journal_renumber)


def entry(number, title, body="Synthetic evidence.", level="##"):
    return f"{level} J{number} — {title}\n\n{body}\n\n"


class RenumberTests(unittest.TestCase):
    def test_collision_preserves_main_and_changes_only_branch_heading(self):
        main = "# Journal\n\n" + entry(10, "Main", "Main evidence mentions J10.")
        addition = entry(10, "Branch", "Reference J10 and [main](#j10--main) stay unchanged.")
        updated, changes = journal_renumber.renumber(main, main + addition)
        self.assertEqual(updated, main + addition.replace("## J10", "## J11", 1))
        self.assertEqual(changes, [(7, "J10", "J11")])

    def test_main_highest_not_last_and_source_order_assigns_every_new_entry(self):
        first, last = entry(12, "High"), entry(9, "Low")
        main = first + last
        branch = entry(99, "First branch") + first + entry(9, "Second branch") + last
        updated, changes = journal_renumber.renumber(main, branch)
        self.assertEqual(updated, entry(13, "First branch") + first + entry(14, "Second branch") + last)
        self.assertEqual([change[2] for change in changes], ["J13", "J14"])
        self.assertEqual(journal_renumber.renumber(main, updated), (updated, []))

    def test_two_distinct_branch_entries_with_same_id_are_both_renumbered(self):
        main = entry(4, "Main")
        updated, changes = journal_renumber.renumber(main, main + entry(4, "First") + entry(4, "Second"))
        self.assertEqual(updated, main + entry(5, "First") + entry(6, "Second"))
        self.assertEqual(len(changes), 2)

    def test_historical_main_duplicates_combined_ids_and_h3_are_not_renumbered(self):
        main = entry("7/J8", "Combined") + entry(8, "Historical duplicate") + entry(15, "Legacy H3", level="###")
        updated, _ = journal_renumber.renumber(main, main + entry(8, "Branch"))
        self.assertEqual(updated, main + entry(16, "Branch"))

    def test_fenced_fake_heading_does_not_affect_max_or_become_new_entry(self):
        main = entry(4, "Main", "```md\n## J9999 — Example\n```\nSynthetic evidence.")
        updated, _ = journal_renumber.renumber(main, main + entry(4, "Branch"))
        self.assertEqual(updated, main + entry(5, "Branch"))

    def test_missing_edited_reordered_and_duplicate_main_are_refused(self):
        first, second = entry(1, "First"), entry(2, "Second")
        main = first + second
        for branch in (first, main.replace("First", "Changed"), second + first, main + first):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                journal_renumber.renumber(main, branch)

    def test_identical_main_duplicates_are_ambiguous(self):
        main = entry(1, "Same") * 2
        with self.assertRaisesRegex(ValueError, "identical duplicate"):
            journal_renumber.renumber(main, main)

    def test_duplicate_branch_content_even_with_different_ids_is_ambiguous(self):
        main = entry(1, "Main")
        for addition in (entry(2, "Main"), entry(2, "New") * 2, entry(2, "New") + entry(3, "New")):
            with self.subTest(addition=addition), self.assertRaisesRegex(ValueError, "duplicates"):
                journal_renumber.renumber(main, main + addition)

    def test_new_h3_combined_and_malformed_headings_are_refused(self):
        main = entry(1, "Main")
        for addition in (entry(2, "New", level="###"), entry("2/J3", "New"), "## New entry\nEvidence.\n"):
            with self.subTest(addition=addition), self.assertRaises(ValueError):
                journal_renumber.renumber(main, main + addition)

    def test_conflict_markers_and_changed_preamble_are_refused(self):
        main = "# Journal\n\n" + entry(1, "Main")
        for branch in (main + "<<<<<<< HEAD\n", main + "=======\n", main.replace("# Journal", "# Changed")):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                journal_renumber.renumber(main, branch)

    def test_append_to_main_without_trailing_blank_line_is_supported(self):
        main = entry(2, "Main").rstrip() + "\n"
        branch = main + "\n" + entry(2, "New")
        updated, _ = journal_renumber.renumber(main, branch)
        self.assertEqual(updated, main + "\n" + entry(3, "New"))

    def test_empty_baseline_and_unchanged_journal(self):
        self.assertEqual(journal_renumber.renumber("", entry(9, "First"))[0], entry(1, "First"))
        main = entry(5, "Only")
        self.assertEqual(journal_renumber.renumber(main, main), (main, []))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        self.journal = self.root / journal_renumber.JOURNAL
        self.index = self.root / journal_renumber.INDEX
        self.git("init", "-q", "--initial-branch=main")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic.invalid")
        self.base = entry(1, "Base")
        self.journal.write_text(self.base, encoding="utf-8")
        self.index.write_text("Old index\n", encoding="utf-8")
        self.commit("base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "topic")
        self.output = io.StringIO()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE, text=True)

    def commit(self, message):
        self.git("add", "docs")
        self.git("commit", "-qm", message)

    def command(self, *args):
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            return journal_renumber.main(list(args), root=self.root)

    def test_generate_real_blame_index_and_repeat_without_staging_or_committing(self):
        self.journal.write_text(self.base + entry(1, "Branch"), encoding="utf-8")
        old_head = self.git("rev-parse", "HEAD")
        old_staged = self.git("diff", "--cached")
        self.assertEqual(self.command(), 0, self.output.getvalue())
        self.assertEqual(self.journal.read_text(), self.base + entry(2, "Branch"))
        self.assertIn("[J2](PORTING_JOURNAL.md#j2--branch)", self.index.read_text())
        self.assertEqual(self.git("rev-parse", "HEAD"), old_head)
        self.assertEqual(self.git("diff", "--cached"), old_staged)
        expected = (self.journal.read_bytes(), self.index.read_bytes())
        self.assertEqual(self.command(), 0)
        self.assertEqual((self.journal.read_bytes(), self.index.read_bytes()), expected)
        with contextlib.redirect_stdout(self.output):
            self.assertEqual(journal_renumber.journal_index.main(["--check"], root=self.root), 0)

    def test_dry_run_and_ambiguous_input_leave_both_files_unchanged(self):
        for addition, args, code in ((entry(1, "Branch"), ["--dry-run"], 0), (self.base, [], 2)):
            with self.subTest(args=args, code=code):
                self.journal.write_text(self.base + addition, encoding="utf-8")
                before = (self.journal.read_bytes(), self.index.read_bytes())
                self.assertEqual(self.command(*args), code, self.output.getvalue())
                self.assertEqual((self.journal.read_bytes(), self.index.read_bytes()), before)

    def test_regeneration_failure_restores_original_journal_and_index(self):
        self.journal.write_text(self.base + entry(1, "Branch"), encoding="utf-8")
        before = (self.journal.read_bytes(), self.index.read_bytes())
        with patch.object(journal_renumber.journal_index, "blame_dates", side_effect=ValueError("synthetic failure")):
            self.assertEqual(self.command(), 2)
        self.assertEqual((self.journal.read_bytes(), self.index.read_bytes()), before)

    def diverge(self):
        self.journal.write_text(self.base + entry(2, "Branch"), encoding="utf-8")
        self.commit("topic entry")
        self.git("checkout", "-q", "main")
        self.journal.write_text(self.base + entry(2, "Main addition"), encoding="utf-8")
        self.commit("main entry")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-q", "topic")

    def test_unmerged_main_refuses_without_writes(self):
        self.diverge()
        before = (self.journal.read_bytes(), self.index.read_bytes())
        self.assertEqual(self.command(), 2)
        self.assertIn("merge origin/main", self.output.getvalue())
        self.assertEqual((self.journal.read_bytes(), self.index.read_bytes()), before)

    def test_resolved_text_during_real_conflicted_merge_and_after_merge_commit(self):
        self.diverge()
        with self.assertRaises(subprocess.CalledProcessError):
            self.git("merge", "--no-edit", "origin/main")
        before = (self.journal.read_bytes(), self.index.read_bytes())
        self.assertEqual(self.command(), 2)
        self.assertIn("conflict markers", self.output.getvalue())
        self.assertEqual((self.journal.read_bytes(), self.index.read_bytes()), before)
        main = self.base + entry(2, "Main addition")
        self.journal.write_text(main + entry(2, "Branch"), encoding="utf-8")
        self.assertEqual(self.command(), 0, self.output.getvalue())
        self.assertEqual(self.journal.read_text(), main + entry(3, "Branch"))
        self.commit("merge and renumber")
        self.assertEqual(self.command(), 0, self.output.getvalue())
        self.assertIn("[J3](PORTING_JOURNAL.md#j3--branch)", self.index.read_text())


if __name__ == "__main__":
    unittest.main()
