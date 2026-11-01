"""Language profiles: German keeps its own texts, a Spanish course is built end to end, and every app text is translated."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

import build_course_app
import course_audio
import embed_audio
import language
import speech
import study_pack as pack
import validate_study_pack

NEEDS_DICTS = unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")
TEMPLATES = (build_course_app.APP_JS + build_course_app.PRACTICE + build_course_app.GAMES + build_course_app.FRAME
             + embed_audio.LISTEN_JS + embed_audio.LISTEN_HTML)


def spanish_lesson(root, lesson_id="S1"):
    """A tiny reviewed Spanish lesson with a story, rendered with the normal sheet renderer."""
    source = root / "source.txt"
    source.write_text("synthetic course source", encoding="utf-8")
    src = [{"pdf_index": 0, "region": "p0", "evidence": "synthetic"}]
    inventory = {
        "schema_version": 2, "lesson_id": lesson_id, "book": "Synthetic", "source_sha256": pack.file_hash(source),
        "scope_label": "synthetic", "scope_pages": [0],
        "pages": [{"pdf_index": 0, "folio": "1", "regions": [
            {"id": "p0", "label": "all", "status": "reviewed", "method": "text", "note": "synthetic"}]}],
        "items": [
            {"id": "i1", "kind": "vocabulary", "label": "el mercado", "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "v1", "reason": "test"},
            {"id": "i2", "kind": "grammar", "label": "ir a + infinitivo", "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "g1", "reason": "test"},
            {"id": "i3", "kind": "expression", "label": "Me gustaría …", "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "e1", "reason": "test"}],
        "dependencies": []}
    lesson = {
        "schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "title": "En el mercado", "level": "A2",
        "target_language": "es", "gloss_language": "en",
        "vocabulary": [{"id": "v1", "group": "Compras", "lemma": "mercado", "pos": "noun", "article": "el",
                        "forms": "Plural: los mercados", "gloss": "market",
                        "examples": [{"de": "Los sábados compro fruta fresca en el mercado.", "en": "On Saturdays I buy fresh fruit at the market.",
                                      "targets": ["mercado"]}]}],
        "grammar": [{"id": "g1", "title": "ir a + infinitivo", "meaning": "A plan for the near future.", "rule": "ir in the present + a + infinitive.",
                     "patterns": [{"label": "pattern", "form": "voy / vas / va + a + infinitivo"}], "contrast": "Not the simple future.",
                     "examples": [{"de": "Mañana voy a cocinar para mis amigos.", "en": "Tomorrow I am going to cook for my friends.",
                                   "targets": ["voy a cocinar"]},
                                  {"de": "Este verano vamos a viajar a Perú.", "en": "This summer we are going to travel to Peru.",
                                   "targets": ["vamos a viajar"]}]}],
        "redemittel": [{"id": "e1", "group": "En el café", "frame": "Me gustaría …", "gloss": "I would like …",
                        "when": "Order or ask politely.", "variants": [{"form": "Quisiera …", "usage": "just as polite"}],
                        "examples": [{"de": "Me gustaría un café con leche, por favor.", "en": "I would like a white coffee, please.",
                                      "targets": ["Me gustaría"]}]}],
        "story": {"title": "Un sábado en el mercado", "paragraphs": [
            {"de": "Hoy Lucía va al mercado con su hermano. Compran tomates y pan.", "en": "Today Lucía goes to the market with her brother. They buy tomatoes and bread.",
             "uses": [{"card": "v1", "form": "mercado"}]},
            {"de": "Esta noche vamos a cocinar juntos, dice ella. La cocina es pequeña.", "en": "We are going to cook together tonight, she says. The kitchen is small.",
             "uses": [{"card": "g1", "form": "vamos a cocinar"}]},
            {"de": "En el café pide: Me gustaría un té verde. Su hermano se ríe.", "en": "In the café she asks: I would like a green tea. Her brother laughs.",
             "uses": [{"card": "e1", "form": "Me gustaría"}]}]}}
    review = {"schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "lesson_sha256": "0" * 64,
              "reviewer": "synthetic", "method": "independent-source-comparison",
              "checks": {**dict.fromkeys(pack.CHECKS, "pass"), pack.STORY_CHECK: "pass"}, "findings": [], "scope_note": "synthetic"}
    paths = {name: root / f"{lesson_id}_{name}_v2.json" for name in ("Inventory", "Lesson", "Review")}
    paths["Inventory"].write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    lesson["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    paths["Lesson"].write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
    review["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    review["lesson_sha256"] = pack.file_hash(paths["Lesson"])
    paths["Review"].write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    bundle = pack.validate_bundle(paths["Inventory"], paths["Lesson"], paths["Review"], source)
    sheet = root / f"{lesson_id}_Studysheet_v1.html"
    pack.render_files(bundle, sheet)
    return paths["Lesson"], sheet


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(speech.use, language.profile("de"))      # speech keeps one language at a time
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_german_keeps_its_own_texts(self):
        german = language.profile("de-DE")
        self.assertEqual(language.ui_table(german), {})
        self.assertEqual(language.article_title(german), "Der · Die · Das")
        self.assertEqual(language.localize(TEMPLATES, language.ui_table(german)), TEMPLATES)

    def test_every_translated_text_is_still_in_the_app(self):
        sources = "".join(Path(module.__file__).read_text(encoding="utf-8")
                          for module in (build_course_app, embed_audio, course_audio))
        for german in language.UI_EN:
            self.assertRegex(sources, r"""['">]\s*""" + re.escape(german) + r"""\s*['"<]""", f"{german!r} is no longer in the app")

    def test_a_spanish_app_shows_no_german_text(self):
        spanish = language.localize(TEMPLATES, language.ui_table(language.profile("es")))
        for german in (key for key, english in language.UI_EN.items() if english != key):     # «Pause» is English too
            self.assertNotRegex(spanish, r"""(?:'|>|=")\s*""" + re.escape(german) + r"""\s*(?:'|<|")""", german)
        self.assertIn("'Listening Bingo'", spanish)
        self.assertIn("'Build the Spanish sentence: tap the words in order.'", spanish)

    def test_a_spanish_course_end_to_end(self):
        lesson, sheet = spanish_lesson(self.root)
        page = sheet.read_text(encoding="utf-8")
        self.assertIn('<html lang="es">', page)
        for title in ("Vocabulario", "Gramática", "Expresiones útiles", "Historia", "Traducción"):
            self.assertIn(title, page)
        self.assertIn('<span class="art-der">el</span> mercado', page)      # «el» borrows the masculine colour
        self.assertEqual(validate_study_pack.main([str(sheet)]), 0)
        course = self.root / "course.json"
        course.write_text(json.dumps({"title": "Curso de prueba", "units": [
            {"id": "S1", "label": "Unidad 1", "lesson": lesson.name, "sheet": sheet.name}]}), encoding="utf-8")
        loaded = course_audio.load_course(course)
        self.assertEqual((loaded["profile"]["code"], loaded["voices"]["de"]), ("es", "es-ES-ElviraNeural"))
        out = self.root / "app.html"
        build_course_app.build(loaded, out, audio=False)
        app = out.read_text(encoding="utf-8")
        self.assertIn('<html lang="es">', app)
        for english in (">Learn<", ">Practise<", ">Play<", "'Listening Bingo'", "'El · La'", "'Word Pairs'"):
            self.assertIn(english, app)
        for german in (">Lernen<", ">Spielen<", "'Hör-Bingo'", "'Der · Die · Das'"):
            self.assertNotIn(german, app)
        self.assertIn('"arts":["el","la"]', app)

    @NEEDS_DICTS
    def test_spanish_words_inside_english_are_spoken_in_spanish(self):
        speech.use(language.profile("es"))
        self.assertEqual(speech.segments("Use «mercado» for the market", "en"),
                         [("en", "Use "), ("de", "mercado"), ("en", " for the market")])
        clip = speech.make_clip("The word mañana means tomorrow.", "en", {"de": "es-ES-ElviraNeural", "en": "en-US-AvaNeural"})
        self.assertIn(("de", "mañana"), clip.parts)

    def test_an_unknown_language_says_how_to_add_one(self):
        with self.assertRaisesRegex(language.LanguageError, r"languages/xx\.json.*available: de, es"):
            language.profile("xx-YY")

    def test_a_course_keeps_one_language(self):
        spanish, sheet = spanish_lesson(self.root)
        data = json.loads(spanish.read_text(encoding="utf-8"))
        german = self.root / "D1_Lesson_v2.json"
        german.write_text(json.dumps(dict(data, target_language="de")), encoding="utf-8")
        course = self.root / "course.json"
        course.write_text(json.dumps({"title": "Mixed", "units": [
            {"id": "S1", "label": "1", "lesson": spanish.name, "sheet": sheet.name},
            {"id": "D1", "label": "2", "lesson": german.name, "sheet": sheet.name}]}), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "one target language"):
            course_audio.load_course(course)


if __name__ == "__main__":
    unittest.main()
