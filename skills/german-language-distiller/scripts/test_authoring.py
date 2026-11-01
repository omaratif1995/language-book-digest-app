"""The authoring helper writes a bundle that study_pack.py accepts, story included."""
from pathlib import Path
import tempfile
import unittest

from authoring import Pack, ex, seal
import study_pack as pack


class AuthoringTests(unittest.TestCase):
    def test_pack_seal_and_validate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.txt"
            source.write_text("synthetic lesson", encoding="utf-8")
            p = Pack("U1", "Ein langer Tag", "synthetic scope", work_dir=root / "U1", book="Synthetic Book",
                     private_terms=["Synthetic Book"])
            p.page(0, "1", [("p0", "everything", "Synthetic.")])
            p.voc("v1", "Arbeit", "Termin", "noun", "appointment",
                  ex("Ich muss den Termin beim Zahnarzt leider verschieben.", "Unfortunately I have to move my dentist appointment.", "Termin"),
                  [("p0", "word list")], "Word list.", article="der", forms="Plural: die Termine")
            p.gram("g1", "trotz + Genitiv", "Something happens anyway.", "trotz takes the Genitiv.", [("m/n", "trotz des Regens")],
                   [ex("Trotz des Regens fahren wir an den See.", "Despite the rain we drive to the lake.", "Trotz des Regens"),
                    ex("Trotz der Kälte sitzen wir draußen.", "Despite the cold we sit outside.", "Trotz der Kälte")],
                   [("p0", "grammar box")], "Explicit grammar.")
            p.red("e1", "Fragen", "Ich wollte fragen, ob …", "I wanted to ask whether …", "Ask politely.",
                  ex("Ich wollte fragen, ob wir morgen frei haben.", "I wanted to ask whether we have tomorrow off.", "Ich wollte fragen, ob"),
                  [("p0", "box")], "Writing frame.")
            p.story("Regen am See", [
                ("Mein Termin beim Zahnarzt ist um acht. Danach habe ich frei.", "My dentist appointment is at eight. After that I'm free.",
                 [("v1", "Termin")]),
                ("Trotz des Regens fahre ich an den See. Das Wasser ist grau.", "Despite the rain I drive to the lake. The water is grey.",
                 [("g1", "Trotz des Regens")]),
                ("Ich schreibe meiner Chefin: Ich wollte fragen, ob ich morgen später komme. Sie lacht.",
                 "I write to my boss: I wanted to ask whether I can come later tomorrow. She laughs.",
                 [("e1", "Ich wollte fragen, ob")])])
            p.write()
            p.review([], "Synthetic.")
            seal(root / "U1", "U1", source)
            bundle = pack.validate_bundle(root / "U1" / "U1_Inventory_v2.json", root / "U1" / "U1_Lesson_v2.json",
                                          root / "U1" / "U1_Review_v2.json", source)
            self.assertTrue(bundle.reviewed, bundle.blockers)
            self.assertIn("Geschichte", pack.render_html(bundle))


if __name__ == "__main__":
    unittest.main()
