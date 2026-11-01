"""Regression tests for v2 inspection → selection → compact rendering."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

import study_pack as pack


class StudyPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.bin"
        self.source.write_bytes(b"synthetic source fixture")
        self.inventory_path = self.root / "L12_Inventory_v2.json"
        self.lesson_path = self.root / "L12_Lesson_v2.json"
        self.review_path = self.root / "L12_Review_v2.json"
        src = [{"pdf_index": 0, "region": "p0-content", "evidence": "synthetic source cue"}]
        self.inventory = {
            "schema_version": 2, "lesson_id": "L12", "book": "Synthetic German B1",
            "source_sha256": pack.file_hash(self.source), "scope_label": "Synthetic print-only fixture",
            "scope_pages": [0], "pages": [{"pdf_index": 0, "folio": "1", "regions": [
                {"id": "p0-content", "label": "word field, grammar and invitation", "status": "reviewed",
                 "method": "visual+text", "note": "Synthetic test; not real source evidence."}]}],
            "items": [
                {"id": "iv1", "kind": "vocabulary", "label": "der Betriebsausflug", "importance": "essential",
                 "sources": copy.deepcopy(src), "decision": "standalone", "home": "v1", "reason": "Explicit word field."},
                {"id": "ig1", "kind": "grammar", "label": "trotz + Genitiv", "importance": "essential",
                 "sources": copy.deepcopy(src), "decision": "standalone", "home": "g1", "reason": "Explicit rule."},
                {"id": "ie1", "kind": "expression", "label": "Ich wollte mich erkundigen, ob", "importance": "essential",
                 "sources": copy.deepcopy(src), "decision": "standalone", "home": "e1", "reason": "Reusable writing frame."},
                {"id": "is1", "kind": "vocabulary", "label": "stattfinden", "importance": "supporting",
                 "sources": copy.deepcopy(src), "decision": "embedded", "home": "v1",
                 "realization": "findet dieses Jahr im Mai statt", "reason": "Useful event collocation in the selected example."},
                {"id": "ix1", "kind": "source_only", "label": "character name", "importance": "incidental",
                 "sources": copy.deepcopy(src), "decision": "exclude", "reason": "One-off story identity."}],
            "dependencies": []}
        self.lesson = {
            "schema_version": 2, "lesson_id": "L12", "inventory_sha256": "0" * 64,
            "title": "Ausflug des Jahres", "level": "B1", "target_language": "de", "gloss_language": "en",
            "vocabulary": [{"id": "v1", "group": "Betriebliche Veranstaltungen", "lemma": "Betriebsausflug",
                            "pos": "noun", "article": "der", "forms": "Plural: die Betriebsausflüge",
                            "gloss": "company outing", "examples": [{"de": "Unser Betriebsausflug findet dieses Jahr im Mai statt.",
                              "en": "Our company outing takes place in May this year.", "targets": ["Betriebsausflug"]}]}],
            "grammar": [{"id": "g1", "title": "trotz + Genitiv", "meaning": "Express a contrast despite an obstacle.",
                         "rule": "In standard German, trotz normally takes the genitive.",
                         "patterns": [{"label": "masculine/neuter", "form": "trotz des + noun -(e)s"}],
                         "contrast": "Do not confuse trotz with wegen: despite versus because of.", "examples": [
                           {"de": "Trotz des Regens findet der Ausflug statt.", "en": "Despite the rain, the outing takes place.", "targets": ["Trotz des Regens"]},
                           {"de": "Trotz der Verspätung beginnt die Feier.", "en": "Despite the delay, the celebration starts.", "targets": ["Trotz der Verspätung"]}]}],
            "redemittel": [{"id": "e1", "group": "Informationen erfragen", "frame": "Ich wollte mich erkundigen, ob …",
                             "gloss": "I wanted to ask whether …", "when": "Politely ask for information.",
                             "register": "polite; formal/neutral", "variants": [], "examples": [
                               {"de": "Ich wollte mich erkundigen, ob wir etwas mitbringen sollen.",
                                "en": "I wanted to ask whether we should bring anything.",
                                "targets": ["Ich wollte mich erkundigen, ob"]}]}]}
        self.review = {
            "schema_version": 2, "lesson_id": "L12", "inventory_sha256": "0" * 64,
            "lesson_sha256": "0" * 64, "reviewer": "synthetic reviewer",
            "method": "independent-source-comparison", "checks": dict.fromkeys(pack.CHECKS, "pass"),
            "findings": [], "scope_note": "Synthetic mechanics only."}

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def save(self):
        self.write(self.inventory_path, self.inventory)
        self.lesson["inventory_sha256"] = pack.file_hash(self.inventory_path)
        self.write(self.lesson_path, self.lesson)
        self.review["inventory_sha256"] = pack.file_hash(self.inventory_path)
        self.review["lesson_sha256"] = pack.file_hash(self.lesson_path)
        self.write(self.review_path, self.review)

    def bundle(self, review=True, source=True):
        self.save()
        return pack.validate_bundle(self.inventory_path, self.lesson_path,
                                    self.review_path if review else None,
                                    self.source if source else None)

    def test_reviewed_render_has_only_three_sections_and_no_meta_panels(self):
        rendered = pack.render_html(self.bundle())
        headings = re.findall(r"<h2\b[^>]*>(.*?)</h2>", rendered, re.S)
        plain = [re.sub(r"<[^>]+>", "", heading).strip() for heading in headings]
        self.assertEqual(plain, ["1 Wortschatz", "2 Grammatik", "3 Redemittel"])
        for forbidden in ("Start here", "Mini-Abruf", "30-Sekunden", "source-note", "legend", 'class="summary"'):
            self.assertNotIn(forbidden, rendered)
        self.assertNotIn("<details", rendered)              # only a story may fold its translations
        self.assertIn('<meta name="study-pack-status" content="reviewed">', rendered)

    def test_render_preserves_examples_and_escapes_content(self):
        self.lesson["vocabulary"][0]["gloss"] = "outing <script>alert(1)</script>"
        rendered = pack.render_html(self.bundle())
        self.assertNotIn("<script>alert", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<mark>Betriebsausflug</mark>", rendered)
        self.assertEqual(rendered.count('class="voc"'), 1)

    def test_style_is_canonical(self):
        rendered = pack.render_html(self.bundle())
        extract = lambda text: re.search(r"<style\b[^>]*>.*?</style>", text, re.S).group(0)
        self.assertEqual(extract(rendered), extract(pack.TEMPLATE.read_text(encoding="utf-8")))

    def test_embedded_realization_must_be_visible_in_declared_home(self):
        self.inventory["items"][3]["realization"] = "findet im Juni statt"
        with self.assertRaisesRegex(pack.PackError, "embedded realization"):
            self.bundle()

    def test_embedded_realization_cannot_exist_only_in_english_gloss(self):
        self.lesson["vocabulary"][0]["gloss"] = "findet dieses Jahr im Juni statt"
        self.inventory["items"][3]["realization"] = "findet dieses Jahr im Juni statt"
        with self.assertRaisesRegex(pack.PackError, "target-language learner text"):
            self.bundle()

    def test_essential_material_cannot_be_hidden_as_embedded(self):
        self.inventory["items"][3]["importance"] = "essential"
        with self.assertRaisesRegex(pack.PackError, "only supporting"):
            self.bundle()

    def test_incidental_material_cannot_be_a_card(self):
        self.inventory["items"][0]["importance"] = "incidental"
        with self.assertRaisesRegex(pack.PackError, "incidental item"):
            self.bundle()

    def test_supporting_material_cannot_be_excluded_as_noise(self):
        self.inventory["items"][3].update(decision="exclude")
        with self.assertRaisesRegex(pack.PackError, "only incidental"):
            self.bundle()

    def test_every_card_needs_one_standalone_source_decision(self):
        self.inventory["items"][0].update(decision="embedded", importance="supporting", realization="Betriebsausflug")
        with self.assertRaisesRegex(pack.PackError, "Every learner card"):
            self.bundle()

    def test_duplicate_must_resolve_to_same_kind_standalone(self):
        duplicate = copy.deepcopy(self.inventory["items"][0])
        duplicate.update(id="iv2", decision="duplicate", duplicate_of="iv1", reason="Same explicit word repeated")
        duplicate.pop("home")
        self.inventory["items"].append(duplicate)
        self.assertTrue(self.bundle().reviewed)
        duplicate["duplicate_of"] = "ig1"
        with self.assertRaisesRegex(pack.PackError, "changes kind"):
            self.bundle()

    def test_region_without_candidate_blocks_reviewed_release(self):
        self.inventory["pages"][0]["regions"].append({"id": "p0-extra", "label": "margin", "status": "reviewed", "method": "visual", "note": "checked"})
        bundle = self.bundle()
        self.assertIn("no candidate", " ".join(bundle.blockers))

    def test_pending_candidate_blocks(self):
        self.inventory["items"][4]["decision"] = "pending"
        bundle = self.bundle()
        self.assertIn("pending", " ".join(bundle.blockers))

    def test_wrong_example_target_fails(self):
        self.lesson["vocabulary"][0]["examples"][0]["targets"] = ["Ausflug"]
        with self.assertRaisesRegex(pack.PackError, "inside another word"):
            self.bundle()

    def test_overlapping_example_targets_fail(self):
        self.lesson["vocabulary"][0]["examples"][0]["targets"] = ["Betriebsausflug", "Ausflug"]
        with self.assertRaises(pack.PackError):
            self.bundle()

    def test_grammar_needs_two_examples(self):
        self.lesson["grammar"][0]["examples"].pop()
        with self.assertRaisesRegex(pack.PackError, "at least 2"):
            self.bundle()

    def test_noun_needs_article_and_plural_information(self):
        self.lesson["vocabulary"][0].pop("article")
        with self.assertRaises(pack.PackError):
            self.bundle()
        self.lesson["vocabulary"][0]["article"] = "der"
        self.lesson["vocabulary"][0]["forms"] = ""
        with self.assertRaisesRegex(pack.PackError, "plural"):
            self.bundle()

    def test_verb_headword_cannot_be_placeholder(self):
        record = self.lesson["vocabulary"][0]
        record.update(pos="verb", lemma="jemandem", forms="Dativ")
        record.pop("article")
        with self.assertRaisesRegex(pack.PackError, "actual verb"):
            self.bundle()

    def test_old_v51_meta_fields_are_rejected(self):
        self.lesson["goal"] = "An old dashboard field"
        with self.assertRaisesRegex(pack.PackError, "three-section"):
            self.bundle()

    def test_stale_review_fails(self):
        self.save()
        self.lesson["title"] = "Changed after review"
        self.write(self.lesson_path, self.lesson)
        with self.assertRaisesRegex(pack.PackError, "stale"):
            pack.validate_bundle(self.inventory_path, self.lesson_path, self.review_path, self.source)

    def test_source_hash_mismatch_fails(self):
        self.source.write_bytes(b"changed")
        with self.assertRaisesRegex(pack.PackError, "Source SHA"):
            self.bundle()

    def test_review_failure_blocks_release(self):
        self.review["checks"]["selection_quality"] = "fail"
        bundle = self.bundle()
        self.assertFalse(bundle.reviewed)
        self.assertIn("selection_quality", " ".join(bundle.blockers))

    def test_open_finding_blocks_release(self):
        self.review["findings"] = [{"id": "f1", "severity": "major", "issue": "Too many incidental cards", "status": "open"}]
        self.assertFalse(self.bundle().reviewed)

    def test_missing_audio_is_internal_note_not_release_blocker(self):
        self.inventory["dependencies"] = [{"id": "audio1", "kind": "audio", "locator": "track 1", "status": "missing", "impact": "Listening not reviewed."}]
        bundle = self.bundle()
        self.assertTrue(bundle.reviewed)
        self.assertIn("Listening not reviewed", " ".join(bundle.notes))
        self.assertNotIn("Listening not reviewed", pack.render_html(bundle))

    def test_pending_audio_blocks(self):
        self.inventory["dependencies"] = [{"id": "audio1", "kind": "audio", "locator": "track 1", "status": "provided", "impact": "Needs review."}]
        self.assertFalse(self.bundle().reviewed)

    def test_draft_requires_draft_filename_and_writes_only_html(self):
        bundle = self.bundle(review=False)
        bad = self.root / "preview.html"
        with self.assertRaisesRegex(pack.PackError, "DRAFT"):
            pack.render_files(bundle, bad, draft=True)
        output = self.root / "L12_DRAFT.html"
        paths = pack.render_files(bundle, output, draft=True)
        self.assertEqual(paths, (output,))
        self.assertEqual([p.name for p in self.root.glob("*DRAFT*")], [output.name])
        self.assertIn('content="draft"', output.read_text(encoding="utf-8"))

    def test_render_refuses_overwrite(self):
        output = self.root / "L12.html"
        pack.render_files(self.bundle(), output)
        with self.assertRaisesRegex(pack.PackError, "exists"):
            pack.render_files(self.bundle(), output)

    def test_duplicate_json_key_is_rejected(self):
        bad = self.root / "bad.json"
        bad.write_text('{"schema_version":2,"lesson_id":"L1","lesson_id":"L2"}', encoding="utf-8")
        with self.assertRaisesRegex(pack.PackError, "duplicate key"):
            pack.load_json(bad)

    def test_cli_validate_fails_without_review_unless_draft(self):
        self.save()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pack.main(["validate", "--inventory", str(self.inventory_path), "--lesson", str(self.lesson_path), "--source", str(self.source)]), 1)
            self.assertEqual(pack.main(["validate", "--inventory", str(self.inventory_path), "--lesson", str(self.lesson_path), "--source", str(self.source), "--draft"]), 0)

    # ---- the closing story (Geschichte) ----
    def add_story(self):
        self.lesson["story"] = {"title": "Sonne für alle", "paragraphs": [
            {"de": "Unser Betriebsausflug findet dieses Jahr am Bodensee statt. Alle freuen sich seit Wochen darauf.",
             "en": "Our company outing takes place at Lake Constance this year. Everyone has been looking forward to it for weeks.",
             "uses": [{"card": "v1", "form": "Betriebsausflug"}]},
            {"de": "Am Morgen regnet es in Strömen. Trotz des Regens steigen alle gut gelaunt in den Bus.",
             "en": "In the morning it is pouring. Despite the rain, everyone gets on the bus in a good mood.",
             "uses": [{"card": "g1", "form": "Trotz des Regens"}]},
            {"de": "Meine Kollegin schreibt dem Chef: „Ich wollte mich erkundigen, ob wir Schirme mitbringen sollen.“ Er schickt nur ein Foto von der Sonne.",
             "en": "My colleague writes to the boss: 'I wanted to ask whether we should bring umbrellas.' He just sends a photo of the sun.",
             "uses": [{"card": "e1", "form": "Ich wollte mich erkundigen, ob"}]}]}
        self.review["checks"][pack.STORY_CHECK] = "pass"

    def test_story_renders_as_fourth_section_with_sentences_and_lesson_words(self):
        self.add_story()
        rendered = pack.render_html(self.bundle())
        headings = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h2\b[^>]*>(.*?)</h2>", rendered, re.S)]
        self.assertEqual(headings, ["1 Wortschatz", "2 Grammatik", "3 Redemittel", "4 Geschichte"])
        self.assertEqual(rendered.count('class="ss"'), 6)
        self.assertEqual(rendered.count('class="story-p"'), 3)
        self.assertIn('<span class="lw" data-card="v1" title="der Betriebsausflug: company outing">Betriebsausflug</span>', rendered)
        self.assertIn('data-card="e1"', rendered)
        self.assertNotIn('data-card="g1"', rendered)         # grammar is checked for coverage, not underlined
        self.assertEqual(rendered.count('<details class="story-tr">'), 3)

    def test_story_needs_its_own_review_check(self):
        self.add_story()
        del self.review["checks"][pack.STORY_CHECK]
        with self.assertRaisesRegex(pack.PackError, "story_quality"):
            self.bundle()

    def test_story_forms_must_occur_in_their_paragraph(self):
        self.add_story()
        self.lesson["story"]["paragraphs"][0]["uses"][0]["form"] = "Betriebsausflüge"
        with self.assertRaisesRegex(pack.PackError, "absent"):
            self.bundle()

    def test_story_must_use_every_grammar_point(self):
        self.add_story()
        self.lesson["story"]["paragraphs"][1]["uses"] = []
        bundle = self.bundle()
        self.assertFalse(bundle.reviewed)
        self.assertIn("grammar point", " ".join(bundle.blockers))

    def test_story_sentences_respect_abbreviations_dates_and_dialogue(self):
        self.assertEqual(pack.story_sentences("Wir treffen uns am 3. Mai um acht. Kommst du mit?"),
                         ["Wir treffen uns am 3. Mai um acht.", "Kommst du mit?"])
        self.assertEqual(pack.story_sentences("Das kostet z. B. zehn Euro. Gut!"), ["Das kostet z. B. zehn Euro.", "Gut!"])
        self.assertEqual(pack.story_sentences("„Bist du sicher?“, fragt sie. „Ja!“ Er lacht."),
                         ["„Bist du sicher?“, fragt sie.", "„Ja!“", "Er lacht."])
        self.assertEqual(pack.story_sentences("Das war 2019. Dann zog ich um."), ["Das war 2019.", "Dann zog ich um."])

    def test_header_never_names_the_source(self):
        rendered = pack.render_html(self.bundle())
        self.assertNotIn("Synthetic German B1", rendered)
        self.assertIn('<div class="lekt">B1 · L12</div>', rendered)

    def test_private_terms_and_isbn_are_refused_in_learner_text(self):
        self.inventory["private_terms"] = ["Kollegin Krause"]
        self.lesson["redemittel"][0]["examples"][0]["en"] = "As Kollegin Krause asked: whether we should bring anything."
        with self.assertRaisesRegex(pack.PackError, "private source term"):
            self.bundle()
        self.inventory["private_terms"] = []
        self.lesson["redemittel"][0]["examples"][0]["en"] = "See ISBN 978-0-000-00000-0."
        with self.assertRaisesRegex(pack.PackError, "ISBN"):
            self.bundle()

    def test_source_text_check_flags_copied_story_and_examples_but_not_the_frame(self):
        self.add_story()
        source_text = self.root / "pages.txt"
        source_text.write_text("Am Morgen regnet es in Strömen, und alle bleiben im Bett. "
                               "Ich wollte mich erkundigen, ob wir morgen kommen dürfen.", encoding="utf-8")
        self.save()
        bundle = pack.validate_bundle(self.inventory_path, self.lesson_path, self.review_path, self.source, source_text)
        notes = " ".join(bundle.notes)
        self.assertIn("story p2 «am morgen regnet es in strömen»", notes)
        self.assertNotIn("e1#0", notes)          # the shared run is mostly the Redemittel frame itself
        source_text.write_text("Ich wollte mich erkundigen, ob wir etwas mitbringen sollen.", encoding="utf-8")
        bundle = pack.validate_bundle(self.inventory_path, self.lesson_path, self.review_path, self.source, source_text)
        self.assertIn("e1#0", " ".join(bundle.notes))   # the whole source sentence is copied

    def test_review_notes_flag_short_examples_and_verbs_without_perfekt(self):
        self.lesson["vocabulary"].append({"id": "v2", "group": "Betriebliche Veranstaltungen", "lemma": "feiern",
                                          "pos": "verb", "forms": "feiert", "gloss": "to celebrate",
                                          "examples": [{"de": "Wir feiern.", "en": "We celebrate.", "targets": ["feiern"]}]})
        self.inventory["items"].append({"id": "iv2", "kind": "vocabulary", "label": "feiern", "importance": "essential",
                                        "sources": [{"pdf_index": 0, "region": "p0-content", "evidence": "cue"}],
                                        "decision": "standalone", "home": "v2", "reason": "Word field."})
        notes = " ".join(self.bundle().notes)
        self.assertIn("Very short examples", notes)
        self.assertIn("without a Perfekt form", notes)


if __name__ == "__main__":
    unittest.main()
