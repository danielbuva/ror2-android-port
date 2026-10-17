import contextlib
from datetime import datetime
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/journal-index.py"
SPEC = importlib.util.spec_from_file_location("journal_index", SCRIPT)
journal_index = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = journal_index
SPEC.loader.exec_module(journal_index)


def porcelain(lines: list[str], timestamp: int = 0, tz: str = "+0900") -> str:
    records = []
    for number, line in enumerate(lines, 1):
        records.extend(
            [
                f"{'a' * 40} {number + 20} {number} 1",
                "author Example",
                f"author-time {timestamp + number * 86400}",
                f"author-tz {tz}",
                f"committer-time {timestamp + 30 * 86400}",
                "filename docs/PORTING_JOURNAL.md",
                "\t" + line,
            ]
        )
    return "\n".join(records) + "\n"


class JournalParsingTests(unittest.TestCase):
    def test_headings_combined_ids_qualifiers_and_source_line_numbers(self):
        journal = (
            "# Porting journal\n\n## J361/J362 — Combined trial\n\nFirst trial. More.\n"
            "### Nested detail\nDetails.\n"
            "### J363 — Entry written at H3\nThird trial.\n"
            "## J349 preparation — Paused trial\n\nSecond trial.\n"
        )
        entries = journal_index.parse_journal(journal)
        self.assertEqual([entry.entry_id for entry in entries], ["J361/J362", "J363", "J349"])
        self.assertEqual([entry.line_number for entry in entries], [3, 8, 10])
        self.assertEqual(entries[2].summary, "Second trial.")
        self.assertEqual(entries[0].title, "Combined trial")
        self.assertEqual(entries[0].summary, "First trial.")
        self.assertEqual(entries[1].title, "Entry written at H3")
        self.assertEqual(entries[2].title, "preparation — Paused trial")
        self.assertEqual(entries[0].anchor, "j361j362--combined-trial")

    def test_fenced_examples_are_not_entries(self):
        journal = "```md\n## J1 — Example\n```\n## J2 — Real\nObserved.\n"
        self.assertEqual([entry.entry_id for entry in journal_index.parse_journal(journal)], ["J2"])

    def test_first_sentence_does_not_split_paths_or_decimals(self):
        body = "\nRecorded `work/x/latest.json` at 58.68 FPS\nwith no errors. Next step.\n"
        self.assertEqual(
            journal_index.first_sentence(body),
            "Recorded `work/x/latest.json` at 58.68 FPS with no errors.",
        )

    def test_first_sentence_ignores_punctuation_inside_code_spans(self):
        for code in ["`work/x/latest.json. more`", "``literal ` ticks. more``"]:
            with self.subTest(code=code):
                sentence = f"Inspect {code} before retrying!"
                self.assertEqual(journal_index.first_sentence(sentence + " Next."), sentence)

    def test_sentence_endings_and_empty_or_unpunctuated_body(self):
        for sentence in ['The result was "passed."', "Did it pass?", "It passed!"]:
            with self.subTest(sentence=sentence):
                self.assertEqual(journal_index.first_sentence(sentence + " More."), sentence)
        self.assertEqual(journal_index.first_sentence("\n\n"), "")
        self.assertEqual(journal_index.first_sentence("One\nunfinished observation"), "One unfinished observation")

    def test_summary_is_capped_at_160_characters(self):
        self.assertEqual(journal_index.first_sentence("x" * 160), "x" * 160)
        self.assertEqual(journal_index.first_sentence("x" * 200 + ". Next."), "x" * 159 + "…")

    def test_github_slug_punctuation_spaces_markup_and_unicode(self):
        cases = {
            "J361/J362 — Shader (A/B), 58.68!": "j361j362--shader-ab-5868",
            "  Two  spaces / slash — dash  ": "two--spaces--slash--dash",
            "A `file_name.json` and _italic_ **bold** [link](target.md)": "a-file_namejson-and-italic-bold-link",
            "État 中文 Θ 🚀": "état-中文-θ-",
            "Keep-under_score\tNow": "keep-under_scorenow",
        }
        for heading, expected in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(journal_index.github_slug(heading), expected)

    def test_duplicate_anchors_consider_other_heading_levels_and_collisions(self):
        journal = "# J1 — Trial\n### Notes: J1 — Trial-1\n#### J1 — Trial-1\n## J1 — Trial\nObserved.\n## J1 — Trial\nAgain.\n"
        entries = journal_index.parse_journal(journal)
        self.assertEqual([entry.anchor for entry in entries], ["j1--trial-2", "j1--trial-3"])

    def test_pipe_escaping_and_newest_first_rendering(self):
        journal = "## J2 — Older | trial\nA | B. Next.\n## J1 — Newest\nLatest.\n"
        rendered = journal_index.render_index(journal, {1: "2026-09-12", 3: "2026-10-16"})
        rows = [line for line in rendered.splitlines() if line.startswith("| [")]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].startswith("| [J1]"))
        self.assertIn("[J2](PORTING_JOURNAL.md#j2--older--trial)", rows[1])
        self.assertIn(r"Older \| trial | A \| B.", rows[1])
        self.assertEqual(journal_index.escape_cell("a|b||c"), r"a\|b\|\|c")
        self.assertEqual(rendered, journal_index.render_index(journal, {3: "2026-10-16", 1: "2026-09-12"}))

    def test_missing_heading_date_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Missing Git blame date"):
            journal_index.render_index("## J1 — Trial\nObserved.\n", {})


class BlameAndCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()
        self.journal = self.root / journal_index.JOURNAL
        self.index = self.root / journal_index.INDEX
        self.journal.write_text("## J1 — Trial\nFirst sentence. Next.\n", encoding="utf-8")
        self.blame = patch.object(journal_index.subprocess, "check_output")
        self.git = self.blame.start()
        self.addCleanup(self.blame.stop)
        self.git.return_value = porcelain(self.journal.read_text().splitlines())

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return journal_index.main(list(args), root=self.root)

    def test_blame_uses_final_line_numbers_author_time_and_one_call(self):
        dates = journal_index.blame_dates(self.root)
        self.assertEqual(
            dates,
            {
                1: "1970-01-02",
                2: "1970-01-03",
            },
        )
        self.git.assert_called_once_with(
            ["git", "blame", "--line-porcelain", "docs/PORTING_JOURNAL.md"],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            stderr=journal_index.subprocess.PIPE,
        )

    @unittest.skipUnless(hasattr(time, "tzset"), "requires local timezone switching")
    def test_blame_dates_use_author_timezone_not_machine_timezone(self):
        # 1970-01-02T03:00Z is 01-01 20:00 at -0700; the author's date must win.
        try:
            for zone in ("UTC", "UTC+8", "UTC-9"):
                with patch.dict(os.environ, {"TZ": zone}):
                    time.tzset()
                    self.git.return_value = porcelain(["## J1 — Trial"], timestamp=3 * 3600, tz="-0700")
                    self.assertEqual(journal_index.blame_dates(self.root), {1: "1970-01-01"})
        finally:
            time.tzset()

    def test_generate_is_byte_identical_and_calls_blame_once_per_run(self):
        self.assertEqual(self.command(), 0)
        self.git.assert_called_once()
        expected = self.index.read_bytes()
        self.git.reset_mock()
        self.assertEqual(self.command(), 0)
        self.git.assert_called_once()
        self.assertEqual(self.index.read_bytes(), expected)

    def test_check_detects_missing_stale_and_fresh_index_without_writing(self):
        self.assertEqual(self.command("--check"), 1)
        self.assertFalse(self.index.exists())
        self.assertEqual(self.command(), 0)
        self.assertEqual(self.command("--check"), 0)
        self.index.write_bytes(b"stale\r\n")
        self.assertEqual(self.command("--check"), 1)
        self.assertEqual(self.index.read_bytes(), b"stale\r\n")

    def test_check_detects_changed_journal_and_heading_date(self):
        self.assertEqual(self.command(), 0)
        self.journal.write_text("## J1 — Trial\nChanged evidence.\n", encoding="utf-8")
        self.assertEqual(self.command("--check"), 1)
        self.assertEqual(self.command(), 0)
        self.git.return_value = porcelain(self.journal.read_text().splitlines(), timestamp=3 * 86400)
        self.assertEqual(self.command("--check"), 1)


if __name__ == "__main__":
    unittest.main()
