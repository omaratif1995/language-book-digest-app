"""Offline tests for course_audio.py (planning only) and build_course_app.py."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

import study_pack as pack
import course_audio
import build_course_app
import speech

NEEDS_DICTS = unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")


def bundle(root, lesson_id, title, word, article, grammar_title, frame):
    """A tiny valid reviewed lesson, rendered with the normal sheet renderer."""
    source = root / "source.txt"
    if not source.exists():
        source.write_text("synthetic course source", encoding="utf-8")
    src = [{"pdf_index": 0, "region": "p0", "evidence": "synthetic"}]
    inventory = {
        "schema_version": 2, "lesson_id": lesson_id, "book": "Synthetic", "source_sha256": pack.file_hash(source),
        "scope_label": "synthetic", "scope_pages": [0],
        "pages": [{"pdf_index": 0, "folio": "1", "regions": [
            {"id": "p0", "label": "all", "status": "reviewed", "method": "text", "note": "synthetic"}]}],
        "items": [
            {"id": "i1", "kind": "vocabulary", "label": word, "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "v1", "reason": "test"},
            {"id": "i2", "kind": "grammar", "label": grammar_title, "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "g1", "reason": "test"},
            {"id": "i3", "kind": "expression", "label": frame, "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "e1", "reason": "test"}],
        "dependencies": []}
    lesson = {
        "schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "title": title, "level": "B1",
        "target_language": "de", "gloss_language": "en",
        "vocabulary": [{"id": "v1", "group": "Gruppe", "lemma": word, "pos": "noun", "article": article,
                        "forms": "Plural: –", "gloss": "test word",
                        "examples": [{"de": f"Hier ist {article} {word}.", "en": "Here it is.", "targets": [word]}]}],
        "grammar": [{"id": "g1", "title": grammar_title, "meaning": "A meaning.", "rule": "A rule.",
                     "patterns": [{"label": "pattern", "form": "A + B"}], "contrast": "A contrast.",
                     "examples": [{"de": "Trotz des Regens gehen wir.", "en": "Despite the rain we go.", "targets": ["Trotz des Regens"]},
                                  {"de": "Trotz der Kälte bleiben wir.", "en": "Despite the cold we stay.", "targets": ["Trotz der Kälte"]}]}],
        "redemittel": [{"id": "e1", "group": "Gruppe", "frame": frame, "gloss": "a frame", "when": "Use it.",
                        "variants": [{"form": "Variante …", "usage": "same"}],
                        "examples": [{"de": f"{frame.replace(' …', '')} heute.", "en": "today.", "targets": [frame.replace(" …", "")]}]}]}
    review = {"schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "lesson_sha256": "0" * 64,
              "reviewer": "synthetic", "method": "independent-source-comparison",
              "checks": dict.fromkeys(pack.CHECKS, "pass"), "findings": [], "scope_note": "synthetic"}
    paths = {name: root / f"{lesson_id}_{name}_v2.json" for name in ("Inventory", "Lesson", "Review")}
    paths["Inventory"].write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    lesson["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    paths["Lesson"].write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
    review["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    review["lesson_sha256"] = pack.file_hash(paths["Lesson"])
    paths["Review"].write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    loaded = pack.validate_bundle(paths["Inventory"], paths["Lesson"], paths["Review"], source)
    sheet = root / f"{lesson_id}_Studysheet_v1.html"
    pack.render_files(loaded, sheet)
    return paths["Lesson"], sheet


class CourseAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        units = []
        for uid, title, word, art, gt, frame in (("U1", "Erste Einheit", "Termin", "der", "trotz + Genitiv", "Ich wollte fragen …"),
                                                 ("U2", "Zweite Einheit", "Ausflug", "der", "wegen + Genitiv", "Wie wäre es mit …")):
            lesson, sheet = bundle(self.root, uid, title, word, art, gt, frame)
            units.append({"id": uid, "label": f"Einheit {uid[1:]}", "lesson": lesson.name, "sheet": sheet.name})
        self.course_path = self.root / "course.json"
        self.course_path.write_text(json.dumps({"title": "Test Kurs", "cache": "_work/audio", "units": units}), encoding="utf-8")

    @NEEDS_DICTS
    def test_plan_is_offline_and_deterministic(self):
        course = course_audio.load_course(self.course_path)
        clips, plan = course_audio.build_course_plan(course)
        again = course_audio.build_course_plan(course_audio.load_course(self.course_path))[1]
        self.assertEqual(plan, again)
        self.assertTrue((course["cache"] / "plan.json").is_file())
        unit = plan["units"]["U1"]
        for key in ("v1-head", "v1-ex-0", "g1-ex-0", "e1-head", "e1-variant-0", "e1-ex-0"):
            self.assertIn(key, unit["controls"])
        self.assertEqual(len(unit["explain"]["g1"]), 5)   # title, meaning, rule, one pattern, contrast
        self.assertEqual(len(course_audio.missing(course, clips)), len(clips))  # nothing synthesized offline

    @NEEDS_DICTS
    def test_narration_replaces_the_generated_explanation(self):
        (self.root / "narration.json").write_text(json.dumps(
            {"U1": {"g1": "Use «trotz» when something happens anyway. It takes the Genitiv: «trotz des Regens»."}}), encoding="utf-8")
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "narration": "narration.json"}), encoding="utf-8")
        course = course_audio.load_course(self.course_path)
        clips, plan = course_audio.build_course_plan(course)
        chain = plan["units"]["U1"]["explain"]["g1"]
        self.assertEqual(len(chain), 2)                    # title + the authored explanation
        self.assertEqual(len(plan["units"]["U2"]["explain"]["g1"]), 5)
        parts = clips[chain[1]].parts
        self.assertIn(("de", "trotz des Regens."), parts)
        self.assertTrue(all(lang == "en" for lang, text in parts if "anyway" in text or "takes the" in text))

    def test_app_without_audio(self):
        out = self.root / "app.html"
        result = build_course_app.build(course_audio.load_course(self.course_path), out, audio=False)
        page = out.read_text(encoding="utf-8")
        self.assertEqual(result["cards"], 6)
        self.assertEqual(page.count('<section class="unit"'), 2)
        self.assertIn('id="practice"', page)
        self.assertNotIn('class="speak-button"', page)
        self.assertNotIn('class="listen-all"', page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        cards = json.loads(re.search(r"CARDS=(\[.*?\]), ORDER=", page, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual([c["k"] for c in cards], ["w", "g", "r", "w", "g", "r"])
        self.assertEqual({c["id"] for c in cards}, {"U1-v1", "U1-g1", "U1-e1", "U2-v1", "U2-g1", "U2-e1"})
        self.assertNotIn("<button", cards[1]["f"], "grammar front must not contain the audio button")
        self.assertEqual([c["a"] for c in cards[:3]], ["der Termin = test word", "trotz + Genitiv", "Ich wollte fragen …"])
        for action in ('data-a="good"', 'data-a="again"', 'data-a="go"', 'id="undo"'):
            self.assertIn(action, page)
        self.assertNotIn('id="skip"', page)

    @NEEDS_DICTS
    def test_app_audio_controls_with_placeholder_payloads(self):
        out = self.root / "app_audio.html"
        build_course_app.build(course_audio.load_course(self.course_path), out, audio=True, placeholder_audio=True)
        page = out.read_text(encoding="utf-8")
        self.assertEqual(page.count('class="listen-all"'), 2)
        self.assertEqual(page.count('class="explain-button"'), 2)
        self.assertGreaterEqual(page.count('class="speak-button"'), 10)
        self.assertNotIn('type="text/plain" id="au-', page)   # placeholder: no payload blocks
        self.assertLess(page.index("<script>"), page.rindex("</main>") + 20)

    @NEEDS_DICTS
    def test_explanations_are_not_counted_as_german_clips(self):
        course = course_audio.load_course(self.course_path)
        unit_plan = course_audio.build_course_plan(course)[1]["units"]["U1"]
        unit = course["units"][0]
        used = set()
        build_course_app.add_audio_buttons(unit["sheet"].read_text(encoding="utf-8"),
                                           json.loads(unit["lesson"].read_text(encoding="utf-8")), unit_plan, used)
        self.assertTrue(used)
        self.assertFalse(used & set(unit_plan["explain"]["g1"]), "explanations get the smaller explain bitrate")

    def test_refuses_overwrite_and_unreviewed_sheets(self):
        out = self.root / "app.html"
        out.write_text("x", encoding="utf-8")
        self.assertEqual(build_course_app.main(["--course", str(self.course_path), "--output", str(out), "--no-audio"]), 1)
        sheet = self.root / "U1_Studysheet_v1.html"
        sheet.write_text(sheet.read_text(encoding="utf-8").replace('content="reviewed"', 'content="draft"'), encoding="utf-8")
        with self.assertRaises(Exception):
            build_course_app.build(course_audio.load_course(self.course_path), self.root / "app2.html", audio=False)


if __name__ == "__main__":
    unittest.main()
