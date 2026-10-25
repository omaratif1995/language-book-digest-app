#!/usr/bin/env python3
import unittest

import embed_audio
import speech


LESSON = {
    "title": "Ein Test",
    "target_language": "de",
    "vocabulary": [{
        "id": "v01", "group": "Dinge", "article": "das", "lemma": "Buch",
        "gloss": "book", "forms": "Plural: die Bücher",
        "examples": [{"de": "Ich lese das Buch.", "en": "I read the book."}],
    }],
    "grammar": [{
        "id": "g01", "title": "Präsens", "meaning": "It describes the present.",
        "rule": "Conjugate the verb.", "patterns": [{"label": "pattern", "form": "Subjekt + Verb"}],
        "examples": [
            {"de": "Ich lese.", "en": "I read."},
            {"de": "Wir lesen.", "en": "We read."},
        ],
    }],
    "redemittel": [{
        "id": "e01", "group": "Reagieren", "frame": "Das gefällt mir!",
        "gloss": "I like that!", "when": "React positively.",
        "variants": [{"form": "Sehr schön!", "usage": "React warmly."}],
        "examples": [{"de": "Das gefällt mir sehr gut!", "en": "I like that very much!"}],
    }],
}

HTML = """<!DOCTYPE html><html lang="de"><head><meta name="study-pack-status" content="reviewed"><style></style></head><body><main class="wrap">
<header class="hero"><h1>Ein Test</h1></header>
<h2>Wortschatz</h2><article class="voc" id="v01"><div class="top"><span class="de"><span class="art-das">das</span> Buch</span><span class="en">book</span></div><p class="forms">Plural: die Bücher</p><div class="ex">Ich lese das Buch. <span class="tr">— I read the book.</span></div></article>
<h2>Grammatik</h2><article class="rule" id="g01"><h3>Präsens</h3><div class="ex">Ich lese.<span class="tr">— I read.</span></div><div class="ex">Wir lesen.<span class="tr">— We read.</span></div></article>
<h2>Redemittel</h2><article class="phrase" id="e01"><div class="head">Das gefällt mir!</div><p class="variant">Sehr schön! — React warmly.</p><div class="ex">Das gefällt mir sehr gut!<span class="tr">— I like that very much!</span></div></article>
</main></body></html>"""


class EmbeddedAudioTests(unittest.TestCase):
    @unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")
    def test_plan_and_injection_are_self_contained(self):
        clips, sequence, controls, explain = embed_audio.build_plan(LESSON, "test-voice")
        self.assertEqual(list(explain), ["g01"])
        result = embed_audio.inject_audio(
            HTML, LESSON, {clip_id: "AAAA" for clip_id in clips}, sequence, controls)
        self.assertEqual(result.count("<h2"), 3)
        self.assertEqual(result.count('class="speak-button"'), len(controls))
        self.assertEqual(len(controls), 8)
        self.assertIn('id="listen-all"', result)
        self.assertIn("data:audio/mpeg;base64,", result)
        self.assertNotIn("https://", result)
        self.assertNotIn("speechSynthesis", result)

    def test_speakable_removes_visual_notation(self):
        self.assertEqual(embed_audio.speakable("Subjekt + werden + … + Partizip II"),
                         "Subjekt, werden, Partizip zwei")


if __name__ == "__main__":
    unittest.main()
