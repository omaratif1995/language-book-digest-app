"""Structural regressions for the compact learner HTML."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import validate_study_pack as validator


VALID = '''<!doctype html><html><head><meta charset="UTF-8"><meta name="study-pack-status" content="reviewed"><style>body{color:white}</style></head><body>
<h2>1 Wortschatz</h2><article class="voc"><div class="ex">der <mark>Kollege</mark></div></article>
<h2>2 Grammatik</h2><article class="rule"><div class="ex"><mark>des Betriebsrats</mark></div><div class="ex"><mark>eines Jahres</mark></div></article>
<h2>3 Redemittel</h2><article class="phrase"><div class="ex"><mark>Vielen Dank</mark></div></article>
</body></html>'''


class HtmlValidatorTests(unittest.TestCase):
    def run_markup(self, markup):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sheet.html"
            path.write_text(markup, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                return validator.main([str(path)])

    def test_valid_three_section_sheet(self):
        self.assertEqual(self.run_markup(VALID), 0)

    def test_fourth_section_fails(self):
        markup = VALID.replace("</body>", "<h2>30-Sekunden-Merkhilfe</h2></body>")
        self.assertEqual(self.run_markup(markup), 1)

    def test_section_name_with_audit_suffix_fails(self):
        self.assertEqual(self.run_markup(VALID.replace("1 Wortschatz", "1 Wortschatz audit")), 1)

    def test_start_route_and_meta_panel_fail(self):
        markup = VALID.replace("<h2>1 Wortschatz", '<div class="goal start">Start here</div><h2>1 Wortschatz')
        self.assertEqual(self.run_markup(markup), 1)

    def test_source_note_fails(self):
        markup = VALID.replace("<h2>1 Wortschatz", '<aside class="source-note">Source review passed</aside><h2>1 Wortschatz')
        self.assertEqual(self.run_markup(markup), 1)

    def test_mark_outside_example_does_not_count(self):
        markup = VALID.replace('<div class="ex">der <mark>Kollege</mark></div>', '<mark>Kollege</mark><div class="ex">der Kollege</div>')
        self.assertEqual(self.run_markup(markup), 1)

    def test_vocabulary_table_fails(self):
        markup = VALID.replace('<article class="voc"><div class="ex">der <mark>Kollege</mark></div></article>', '<table><tr><td>der Kollege</td></tr></table>')
        self.assertEqual(self.run_markup(markup), 1)

    def test_hidden_or_folded_content_fails(self):
        self.assertEqual(self.run_markup(VALID.replace('<article class="voc"', '<article hidden class="voc"')), 1)
        self.assertEqual(self.run_markup(VALID.replace('<article class="voc">', '<details><article class="voc">').replace('</article>\n<h2>2', '</article></details>\n<h2>2', 1)), 1)

    def test_grammar_needs_two_examples(self):
        markup = VALID.replace('<div class="ex"><mark>eines Jahres</mark></div>', '')
        self.assertEqual(self.run_markup(markup), 1)

    def test_missing_machine_status_fails(self):
        self.assertEqual(self.run_markup(VALID.replace('<meta name="study-pack-status" content="reviewed">', '')), 1)

    def test_ordinary_later_or_progress_gloss_is_allowed(self):
        markup = VALID.replace("der <mark>Kollege</mark>", "Später mache ich <mark>Fortschritte</mark> — Later I make progress")
        self.assertEqual(self.run_markup(markup), 0)


if __name__ == "__main__":
    unittest.main()
