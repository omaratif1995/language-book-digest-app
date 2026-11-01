#!/usr/bin/env python3
"""Compact authoring for whole courses: one small Python script per unit writes the v2 JSON contract.

One call per learner card writes the lesson record *and* its standalone inventory decision, so the two can
never drift apart. Region ids resolve to pdf_index.

    from authoring import Pack, ex
    p = Pack("L01", "Erinnerungen", "Lesson 1 pages 8-15; audio not supplied", work_dir="_work/L01",
             level="B1", book="(internal source name)", private_terms=["Publisher name"])
    p.page(8, "8", [("p8-words", "picture vocabulary", "Seven labels visually checked.")])
    p.voc("v01", "Lebensphasen", "Vergangenheit", "noun", "the past",
          ex("Über die Vergangenheit spricht mein Opa nicht gern.", "My grandpa doesn't like talking about the past.", "Vergangenheit"),
          [("p8-words", "picture label")], "Explicit word field.", article="die", forms="no plural")
    ...
    p.story("Das Paket aus Chile", [(de, en, [("v01", "Vergangenheit"), ("g01", "als ich klein war")]), ...])
    p.write()
    p.review([("minor", "issue", "resolution")], "Print scope reviewed; audio not supplied.")
    seal("_work/L01", "L01", "BOOK.pdf")      # chain the hashes, then render with study_pack.py

The source's name stays in `book` and `scope_label`, which learners never see; list names that must never reach
learner text in `private_terms`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ZERO = "0" * 64
CHECKS = ("source_inspection", "selection_quality", "vocabulary_quality", "grammar_accuracy",
          "redemittel_value", "example_integration", "compression")


def ex(de, en, *targets):
    """One example: German text, English translation and the exact target spans to highlight."""
    return {"de": de, "en": en, "targets": list(targets)}


class Pack:
    def __init__(self, lesson_id, title, scope_label, work_dir, level="B1", book="", private_terms=()):
        self.id, self.title, self.level, self.book, self.scope_label = lesson_id, title, level, book, scope_label
        self.work = Path(work_dir)
        self.private_terms = list(private_terms)
        self.pages, self.region_index, self.items, self.deps = [], {}, [], []
        self.voc_, self.gram_, self.red_, self.story_ = [], [], [], None
        self._n = 0
        self.status, self.method = "reviewed", "visual+text"   # recorded on every source region of the next page() calls

    # ---- source map -------------------------------------------------------
    def page(self, pdf_index, folio, regions, method=None, status=None):
        regs = []
        for rid, label, note in regions:
            self.region_index[rid] = pdf_index
            regs.append({"id": rid, "label": label, "status": status or self.status, "method": method or self.method, "note": note})
        self.pages.append({"pdf_index": pdf_index, "folio": str(folio), "regions": regs})

    def _src(self, src):
        return [{"pdf_index": self.region_index[r], "region": r, "evidence": e} for r, e in src]

    def _item(self, kind, label, importance, src, decision, reason, **extra):
        self._n += 1
        rec = {"id": extra.pop("iid", f"i{self._n:03d}"), "kind": kind, "label": label, "importance": importance,
               "sources": self._src(src), "decision": decision, "reason": reason}
        rec.update(extra)
        self.items.append(rec)
        return rec["id"]

    # ---- learner cards ----------------------------------------------------
    def voc(self, vid, group, lemma, pos, gloss, examples, src, reason, article=None, forms="", imp="essential"):
        rec = {"id": vid, "group": group, "lemma": lemma, "pos": pos}
        if article:
            rec["article"] = article
        rec.update({"forms": forms, "gloss": gloss, "examples": examples if isinstance(examples, list) else [examples]})
        self.voc_.append(rec)
        return self._item("vocabulary", f"{article} {lemma}" if article else lemma, imp, src, "standalone", reason, home=vid)

    def gram(self, gid, title, meaning, rule, patterns, examples, src, reason, contrast=None, imp="essential"):
        rec = {"id": gid, "title": title, "meaning": meaning, "rule": rule,
               "patterns": [{"label": label, "form": form} for label, form in patterns]}
        if contrast:
            rec["contrast"] = contrast
        rec["examples"] = examples
        self.gram_.append(rec)
        return self._item("grammar", title, imp, src, "standalone", reason, home=gid)

    def red(self, eid, group, frame, gloss, when, examples, src, reason, register=None, variants=(), imp="essential"):
        rec = {"id": eid, "group": group, "frame": frame, "gloss": gloss, "when": when}
        if register:
            rec["register"] = register
        if variants:
            rec["variants"] = [{"form": form, "usage": usage} for form, usage in variants]
        rec["examples"] = examples if isinstance(examples, list) else [examples]
        self.red_.append(rec)
        return self._item("expression", frame, imp, src, "standalone", reason, home=eid)

    def story(self, title, paragraphs):
        """The closing Geschichte: [(German paragraph, English paragraph, [(card id, exact form), ...]), ...]."""
        self.story_ = {"title": title, "paragraphs": [
            {"de": de, "en": en, "uses": [{"card": card, "form": form} for card, form in uses]} for de, en, uses in paragraphs]}

    # ---- non-card decisions -------------------------------------------------
    def embed(self, kind, label, home, realization, src, reason):
        return self._item(kind, label, "supporting", src, "embedded", reason, home=home, realization=realization)

    def dup(self, kind, label, of, src, reason):
        return self._item(kind, label, "supporting", src, "duplicate", reason, duplicate_of=of)

    def exclude(self, label, src, reason, kind="source_only"):
        return self._item(kind, label, "incidental", src, "exclude", reason)

    def dep(self, did, kind, locator, impact, status="missing"):
        self.deps.append({"id": did, "kind": kind, "locator": locator, "status": status, "impact": impact})

    # ---- output -----------------------------------------------------------
    def _write(self, name, data):
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / f"{self.id}_{name}_v2.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                                                            encoding="utf-8", newline="\n")

    def write(self):
        inventory = {"schema_version": 2, "lesson_id": self.id, "book": self.book, "source_sha256": ZERO,
                     "scope_label": self.scope_label, "scope_pages": [p["pdf_index"] for p in self.pages],
                     "pages": self.pages, "items": self.items, "dependencies": self.deps}
        if self.private_terms:
            inventory["private_terms"] = self.private_terms
        lesson = {"schema_version": 2, "lesson_id": self.id, "inventory_sha256": ZERO, "title": self.title,
                  "level": self.level, "target_language": "de", "gloss_language": "en",
                  "vocabulary": self.voc_, "grammar": self.gram_, "redemittel": self.red_}
        if self.story_:
            lesson["story"] = self.story_
        self._write("Inventory", inventory)
        self._write("Lesson", lesson)
        print(f"{self.id}: {len(self.voc_)} vocabulary, {len(self.gram_)} grammar, {len(self.red_)} Redemittel, "
              f"{len(self.story_['paragraphs']) if self.story_ else 0} story paragraphs, {len(self.items)} inventory items")

    def review(self, findings, scope_note, reviewer="author second pass", method="author-second-pass"):
        """Every check passes only after you have done it; record what you found and fixed as findings."""
        checks = dict.fromkeys(CHECKS + (("story_quality",) if self.story_ else ()), "pass")
        self._write("Review", {"schema_version": 2, "lesson_id": self.id, "inventory_sha256": ZERO, "lesson_sha256": ZERO,
                               "reviewer": reviewer, "method": method, "checks": checks,
                               "findings": [{"id": f"f{i + 1:02d}", "severity": severity, "issue": issue,
                                             "status": "resolved", "resolution": resolution}
                                            for i, (severity, issue, resolution) in enumerate(findings)],
                               "scope_note": scope_note})


def seal(work_dir, lesson_id, source):
    """Chain the hashes source → inventory → lesson → review over the exact bytes, as study_pack.py checks them."""
    work = Path(work_dir)
    sha = lambda data: hashlib.sha256(data).hexdigest()

    def patch(name, **fields):
        path = work / f"{lesson_id}_{name}_v2.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(fields)
        raw = (json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
        path.write_bytes(raw)
        return sha(raw)

    inventory = patch("Inventory", source_sha256=sha(Path(source).read_bytes()))
    lesson = patch("Lesson", inventory_sha256=inventory)
    if (work / f"{lesson_id}_Review_v2.json").exists():
        patch("Review", inventory_sha256=inventory, lesson_sha256=lesson)
    return inventory, lesson
