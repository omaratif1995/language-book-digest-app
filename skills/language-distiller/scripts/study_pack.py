#!/usr/bin/env python3
"""Validate internal lesson records and render a compact study sheet.

The sheet has three teaching sections (Wortschatz, Grammatik, Redemittel) and, when the
lesson data has a story, a closing Geschichte that recycles the lesson in one catchy text.
Mechanical checks cannot judge pedagogical selection or German accuracy. Those
require a real source comparison and language review.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import html
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import language  # noqa: E402


SCHEMA = 2
KINDS = {"vocabulary", "grammar", "expression", "source_only"}
CHECKS = {"source_inspection", "selection_quality", "vocabulary_quality",
          "grammar_accuracy", "redemittel_value", "example_integration", "compression"}
SECTIONS = {"vocabulary": "vocabulary", "grammar": "grammar", "redemittel": "expression"}
HOME_KINDS = {"vocabulary": "vocabulary", "grammar": "grammar", "expression": "redemittel"}
LESSON_KEYS = {"schema_version", "lesson_id", "inventory_sha256", "title", "level",
               "target_language", "gloss_language", "vocabulary", "grammar", "redemittel"}
OPTIONAL_LESSON_KEYS = {"story"}
FORBIDDEN_LEARNER_FIELDS = {"goal", "core_ids", "start_grammar_id", "start_expression_id",
                            "start_labels", "contexts", "practice", "recap", "later"}
STORY_CHECK = "story_quality"
STORY_MIN_PARAGRAPHS = 3
STORY_MIN_VOCABULARY_SHARE = 0.6
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
ISBN = re.compile(r"\b97[89](?:[-\s]?\d){10}\b")
TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "master-template.html"


class PackError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackError(message)


def obj(value, where):
    require(isinstance(value, dict), f"{where}: expected an object")
    return value


def seq(value, where, minimum=0):
    require(isinstance(value, list), f"{where}: expected a list")
    require(len(value) >= minimum, f"{where}: needs at least {minimum} item(s)")
    return value


def string(value, where):
    require(isinstance(value, str) and bool(value.strip()), f"{where}: expected nonempty text")
    return value


def optional_string(value, where):
    require(isinstance(value, str), f"{where}: expected text")
    return value


def field(record, name, where):
    return string(record.get(name), f"{where}.{name}")


def identifier(value, where):
    value = string(value, where)
    require(IDENTIFIER.fullmatch(value), f"{where}: invalid identifier")
    return value


def unique_strings(value, where, minimum=0):
    values = seq(value, where, minimum)
    for index, item in enumerate(values):
        string(item, f"{where}[{index}]")
    require(len(set(values)) == len(values), f"{where}: duplicate value")
    return values


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_field(record, name, where):
    value = field(record, name, where)
    require(HASH.fullmatch(value), f"{where}.{name}: expected lowercase SHA-256")
    return value


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"JSON has duplicate key {key!r}")
        result[key] = value
    return result


def load_json(path):
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_keys,
                           parse_constant=lambda value: (_ for _ in ()).throw(PackError(f"Invalid number: {value}")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackError(f"{Path(path).name}: invalid UTF-8 JSON: {error}") from error
    obj(value, str(path))
    require(type(value.get("schema_version")) is int and value["schema_version"] == SCHEMA,
            f"{Path(path).name}: schema_version must be {SCHEMA}")
    identifier(value.get("lesson_id"), f"{Path(path).name}.lesson_id")
    return value, hashlib.sha256(raw).hexdigest()


def exact_matches(text, target):
    """Occurrences of `target` in `text` that do not start or end inside another word."""
    edge = r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_]"
    prefix = r"(?<!\w)" if re.fullmatch(edge, target[0]) else ""
    suffix = r"(?!\w)" if re.fullmatch(edge, target[-1]) else ""
    return list(re.finditer(prefix + re.escape(target) + suffix, text))


def target_spans(example, where):
    obj(example, where)
    text = field(example, "de", where)
    field(example, "en", where)
    targets = unique_strings(example.get("targets"), f"{where}.targets", 1)
    spans = []
    for target in targets:
        matches = exact_matches(text, target)
        require(matches, f"{where}: exact target {target!r} is absent or inside another word")
        spans.extend((match.start(), match.end()) for match in matches)
    spans.sort()
    require(all(left[1] <= right[0] for left, right in zip(spans, spans[1:])),
            f"{where}: target spans overlap")
    return spans


def validate_examples(record, where, minimum=1):
    records = seq(record.get("examples"), f"{where}.examples", minimum)
    for index, example in enumerate(records):
        target_spans(example, f"{where}.examples[{index}]")
    return records


NON_TARGET_KEYS = {"id", "targets", "en", "gloss", "when", "register", "meaning",
                   "rule", "usage", "label"}


def target_visible_strings(value):
    """Flatten target-language learner strings for exact embedded realizations."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from target_visible_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in NON_TARGET_KEYS:
                yield from target_visible_strings(item)


def learner_strings(value):
    """Every string a learner can see or hear: titles, cards, glosses, examples and the story."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from learner_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in ("id", "card", "targets", "uses", "schema_version", "lesson_id", "inventory_sha256"):
                yield from learner_strings(item)


def story_sentences(text, prof=None):
    """Split one story paragraph into sentences (stable, so audio clips and highlights line up). A sentence ends at
    . ! ? or … (plus closing quotes) before the next sentence's first letter, digit, quote or dash; the language's
    profile says which letters start a sentence and which abbreviations end none (language.sentence_rules)."""
    end, not_end = language.sentence_rules(prof or language.profile("de"))
    sentences, start = [], 0
    for match in end.finditer(text):
        if not_end.search(text[start:match.end()]):
            continue                                  # z. B., Dr., am 3. Mai: not the end of a sentence
        sentences.append(text[start:match.end()].strip())
        start = match.end()
    if text[start:].strip():
        sentences.append(text[start:].strip())
    return sentences


def sentence_spans(text, prof=None):
    """(start, end) of each story sentence inside its paragraph."""
    spans, cursor = [], 0
    for sentence in story_sentences(text, prof):
        start = text.index(sentence, cursor)
        spans.append((start, start + len(sentence)))
        cursor = start + len(sentence)
    return spans


def story_marks(paragraph, sections):
    """Spans of the lesson words and phrases a paragraph uses (first occurrence of each), for highlighting."""
    marks = []
    for use in paragraph.get("uses", []):
        if sections.get(use["card"]) in ("vocabulary", "redemittel"):
            match = exact_matches(paragraph["de"], use["form"])[0]
            marks.append((match.start(), match.end(), use["card"]))
    return sorted(marks)


def validate_story(lesson, nodes, node_sections, blockers, notes):
    story = obj(lesson["story"], "lesson.story")
    require(set(story) <= {"title", "paragraphs"}, "lesson.story accepts only title and paragraphs")
    field(story, "title", "lesson.story")
    paragraphs = seq(story.get("paragraphs"), "lesson.story.paragraphs", STORY_MIN_PARAGRAPHS)
    used, words, prof = {}, 0, language.profile(lesson["target_language"])
    for index, paragraph in enumerate(paragraphs, 1):
        where = f"story paragraph {index}"
        obj(paragraph, where)
        require(set(paragraph) <= {"de", "en", "uses"}, f"{where}: accepts only de, en and uses")
        text = field(paragraph, "de", where)
        field(paragraph, "en", where)
        words += language.word_count(prof, text)
        bounds = sentence_spans(text, prof)
        for use_index, use in enumerate(seq(paragraph.get("uses", []), f"{where}.uses")):
            obj(use, f"{where}.uses[{use_index}]")
            card, form = field(use, "card", where), field(use, "form", where)
            require(card in nodes, f"{where}: uses unknown card {card}")
            matches = exact_matches(text, form)
            require(matches, f"{where}: the form {form!r} of {card} is absent or inside another word")
            first = matches[0]
            require(any(a <= first.start() and first.end() <= b for a, b in bounds),
                    f"{where}: the form {form!r} runs across two sentences")
            used.setdefault(card, []).append(index)
        marks = story_marks(paragraph, node_sections)
        require(all(left[1] <= right[0] for left, right in zip(marks, marks[1:])),
                f"{where}: highlighted words and phrases overlap")
    sections = {"vocabulary": [], "grammar": [], "redemittel": []}
    for nid, section in node_sections.items():
        sections[section].append(nid)
    unused_grammar = [nid for nid in sections["grammar"] if nid not in used]
    if unused_grammar:
        blockers.append("Story never uses grammar point(s) " + ", ".join(unused_grammar))
    vocabulary = sections["vocabulary"]
    share = sum(nid in used for nid in vocabulary) / len(vocabulary) if vocabulary else 1.0
    if share < STORY_MIN_VOCABULARY_SHARE:
        blockers.append(f"Story uses only {share:.0%} of the vocabulary cards (needs {STORY_MIN_VOCABULARY_SHARE:.0%})")
    phrases = sections["redemittel"]
    notes.append(f"Story: {words} words, {len(paragraphs)} paragraphs; vocabulary {share:.0%}, "
                 f"grammar {len(sections['grammar']) - len(unused_grammar)}/{len(sections['grammar'])}, "
                 f"Redemittel {sum(nid in used for nid in phrases)}/{len(phrases)}")
    unused = [nid for nid in vocabulary + phrases if nid not in used]
    if unused:
        notes.append("Story leaves out: " + ", ".join(unused))
    if not 200 <= words <= 700:
        notes.append(f"Story has {words} words; 250-600 usually reads well in one sitting")


def runs(words, n):
    """Every run of n words in a row."""
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def example_notes(lesson, inventory, notes):
    """Hints for the language review: flat or copied examples, verbs without Perfekt. Never blockers.
    Words are counted the language's way (language.words): in Japanese or Chinese two characters make a word."""
    prof = language.profile(lesson["target_language"])
    n, first = language.run_length(prof, 6), prof.get("first_person")
    evidence = set()
    for item in inventory.get("items", []):
        for source in item.get("sources", []):
            evidence |= runs(language.words(prof, source.get("evidence", "")), n)
    short, copied, starts = [], [], []
    for section in ("vocabulary", "grammar", "redemittel"):
        for record in lesson[section]:
            for example in record["examples"]:
                words = language.words(prof, example["de"])
                if language.spaced(prof):
                    starts.append(words[0] if words else "")
                else:
                    starts.append(first if first and example["de"].strip().startswith(first) else "")
                if language.word_count(prof, example["de"]) < 5:
                    short.append(record["id"])
                if section != "redemittel" and runs(words, n) & evidence:
                    copied.append(record["id"])
    if short:
        notes.append("Very short examples (check they are not too simple): " + ", ".join(sorted(set(short))))
    if copied:
        notes.append("Examples that repeat six or more source words in a row (write your own): " + ", ".join(sorted(set(copied))))
    if first and starts and starts.count(first) / len(starts) > 0.4:
        notes.append(f"{starts.count(first)} of {len(starts)} examples start with «{first.capitalize()}»; vary the subjects")
    hint = prof.get("verb_hint")                  # German: the Perfekt belongs on every verb card
    missing = [record["id"] for record in lesson["vocabulary"]
               if hint and record["pos"] == "verb" and not re.search(hint["forms"], record.get("forms", ""))]
    if missing:
        notes.append(hint["note"] + ": " + ", ".join(missing))


def copied_run(text, protected, source, prof=None):
    """The first run of six words that `text` shares with the source, unless it is mostly the card's own target phrase.
    Only phrases of three or more words count as protected (a Redemittel frame); single target words do not."""
    prof = prof or language.profile("de")
    n, joiner = language.run_length(prof, 6), " " if language.spaced(prof) else ""
    words = language.word_spans(prof, text)
    phrases = [phrase for phrase in protected if language.word_count(prof, phrase) >= 3]
    spans = [(m.start(), m.end()) for phrase in phrases for m in re.finditer(re.escape(phrase.casefold()), text.casefold())]
    for i in range(len(words) - n + 1):
        run = words[i:i + n]
        if tuple(w for w, _, _ in run) in source:
            if sum(any(a <= s and e <= b for a, b in spans) for _, s, e in run) < n * 2 // 3:
                return joiner.join(w for w, _, _ in run)
    return None


def source_copy_notes(lesson, source_text, notes):
    """Learner text must be the learner's own: report examples and story sentences that copy six source words
    (twelve characters in a language without spaces)."""
    prof = language.profile(lesson["target_language"])
    source = runs(language.words(prof, source_text), language.run_length(prof, 6))
    found = []
    for section in ("vocabulary", "grammar", "redemittel"):
        for record in lesson[section]:
            for index, example in enumerate(record["examples"]):
                run = copied_run(example["de"], example["targets"], source, prof)
                if run:
                    found.append(f'{record["id"]}#{index} «{run}»')
    for index, paragraph in enumerate((lesson.get("story") or {}).get("paragraphs", []), 1):
        run = copied_run(paragraph["de"], [use["form"] for use in paragraph.get("uses", [])], source, prof)
        if run:
            found.append(f"story p{index} «{run}»")
    if found:
        notes.append("Copied from the source, rewrite in your own words: " + "; ".join(found))


def source_text_of(source_path, scope):
    """Text of the source for the originality check: a text file as it is, or the scope pages of a PDF."""
    path = Path(source_path)
    if path.suffix.lower() == ".pdf":
        try:
            import pymupdf
        except ImportError:
            return None
        with pymupdf.open(path) as pdf:
            return " ".join(pdf[index].get_text() for index in scope if index < pdf.page_count)
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def check_private_terms(lesson, inventory):
    """Learner output never names the source: no ISBN and none of the inventory's private_terms."""
    terms = unique_strings(inventory.get("private_terms", []), "inventory.private_terms")
    for text in learner_strings({key: lesson[key] for key in lesson if key not in ("target_language", "gloss_language")}):
        require(not ISBN.search(text), f"Learner text contains an ISBN: {text[:60]!r}")
        for term in terms:
            require(not exact_matches(text, term), f"Learner text names a private source term {term!r}: {text[:60]!r}")


@dataclass
class Bundle:
    inventory: dict
    lesson: dict
    review: dict | None
    hashes: dict
    nodes: dict
    node_sections: dict
    blockers: list
    notes: list
    source_verified: bool

    @property
    def reviewed(self):
        return self.review is not None and not self.blockers


def validate_bundle(inventory_path, lesson_path, review_path=None, source_path=None, source_text_path=None):
    inventory, inventory_hash = load_json(inventory_path)
    lesson, lesson_hash = load_json(lesson_path)
    require(inventory["lesson_id"] == lesson["lesson_id"], "Inventory and lesson IDs differ")
    require(set(lesson) - OPTIONAL_LESSON_KEYS == LESSON_KEYS,
            "Lesson top-level fields must contain only the three-section v2 contract (plus an optional story); "
            "unexpected/missing: " + ", ".join(sorted((set(lesson) - OPTIONAL_LESSON_KEYS) ^ LESSON_KEYS)))
    require(not (set(lesson) & FORBIDDEN_LEARNER_FIELDS), "Learner-meta fields are forbidden in v2 lesson data")
    require(hash_field(lesson, "inventory_sha256", "lesson") == inventory_hash,
            "Lesson inventory_sha256 is stale")
    source_hash = hash_field(inventory, "source_sha256", "inventory")
    for name in ("book", "scope_label"):
        field(inventory, name, "inventory")
    for name in ("title", "level", "target_language", "gloss_language"):
        field(lesson, name, "lesson")
    try:
        prof = language.profile(lesson["target_language"])
    except language.LanguageError as error:
        raise PackError(str(error)) from error

    blockers, notes = [], []
    scope = seq(inventory.get("scope_pages"), "inventory.scope_pages", 1)
    require(all(type(page) is int and page >= 0 for page in scope), "scope_pages must be nonnegative indexes")
    require(len(set(scope)) == len(scope), "scope_pages has duplicates")
    pages, regions = {}, {}
    for page in seq(inventory.get("pages"), "inventory.pages", 1):
        obj(page, "page")
        index = page.get("pdf_index")
        require(type(index) is int and index in scope and index not in pages,
                "Page index is duplicate or outside scope")
        field(page, "folio", f"page {index}")
        pages[index] = page
        for region in seq(page.get("regions"), f"page {index}.regions", 1):
            obj(region, "region")
            rid = identifier(region.get("id"), "region.id")
            require(rid not in regions, f"Duplicate region {rid}")
            for name in ("label", "note"):
                field(region, name, rid)
            require(region.get("method") in ("visual", "text", "visual+text"), f"{rid}: invalid method")
            require(region.get("status") in ("reviewed", "pending", "unreadable"), f"{rid}: invalid status")
            if region["status"] != "reviewed":
                blockers.append(f"Source region {rid} is {region['status']}")
            regions[rid] = index
    require(set(pages) == set(scope), "Page records do not match scope_pages")

    dependencies = seq(inventory.get("dependencies"), "inventory.dependencies")
    dependency_ids = set()
    for dep in dependencies:
        obj(dep, "dependency")
        did = identifier(dep.get("id"), "dependency.id")
        require(did not in dependency_ids, f"Duplicate dependency {did}")
        dependency_ids.add(did)
        for name in ("kind", "locator", "impact"):
            field(dep, name, did)
        require(dep.get("status") in ("missing", "pending", "provided", "reviewed"), f"{did}: invalid status")
        if dep["status"] != "reviewed":
            notes.append(f"{did} ({dep['status']}): {dep['impact']}")
        if dep["status"] in ("pending", "provided"):
            blockers.append(f"Dependency {did} has not been reviewed")

    nodes, node_sections = {}, {}
    for section in SECTIONS:
        for record in seq(lesson.get(section), f"lesson.{section}"):
            obj(record, section)
            nid = identifier(record.get("id"), f"{section}.id")
            require(nid not in nodes, f"Duplicate content ID {nid}")
            nodes[nid], node_sections[nid] = record, section
            if section == "vocabulary":
                for name in ("group", "lemma", "pos", "gloss"):
                    field(record, name, nid)
                optional_string(record.get("forms", ""), f"{nid}.forms")
                require(record["pos"] in ("noun", "verb", "adjective", "adverb", "pronoun",
                                                  "preposition", "conjunction", "other"), f"{nid}: invalid pos")
                if record["pos"] == "noun" and prof["articles"]:
                    article = field(record, "article", nid)
                    require(article in prof["articles"], f"{nid}: {prof['name']} noun needs {'/'.join(prof['articles'])}")
                    require(not record["lemma"].startswith(article + " "), f"{nid}: do not repeat article in lemma")
                if record["pos"] == "noun" and prof.get("noun_plural", True):
                    require(re.search(r"plural|\bpl\.|no plural|uncountable|singular.only|nur singular", record.get("forms", ""), re.I),
                            f"{nid}: noun forms need useful plural/no-plural information")
                if record["pos"] == "verb":
                    require(record["lemma"].strip().casefold() not in {"jemand", "jemanden", "jemandem", "etwas", "sich"},
                            f"{nid}: preserve the actual verb in lemma")
                validate_examples(record, nid, 1)
            elif section == "grammar":
                for name in ("title", "meaning", "rule"):
                    field(record, name, nid)
                for pattern in seq(record.get("patterns"), f"{nid}.patterns", 1):
                    obj(pattern, f"{nid}.pattern")
                    field(pattern, "label", nid)
                    field(pattern, "form", nid)
                if "contrast" in record:
                    field(record, "contrast", nid)
                count = len(validate_examples(record, nid, 2))
                if count > 4:
                    notes.append(f"{nid} has {count} grammar examples; review whether each teaches a distinct necessary contrast")
            else:
                for name in ("group", "frame", "gloss", "when"):
                    field(record, name, nid)
                if "register" in record:
                    field(record, "register", nid)
                for variant in seq(record.get("variants", []), f"{nid}.variants"):
                    obj(variant, f"{nid}.variant")
                    field(variant, "form", nid)
                    field(variant, "usage", nid)
                validate_examples(record, nid, 1)

    items, standalone_homes, referenced_regions = {}, set(), set()
    for item in seq(inventory.get("items"), "inventory.items", 1):
        obj(item, "inventory item")
        iid = identifier(item.get("id"), "item.id")
        require(iid not in items, f"Duplicate inventory item {iid}")
        items[iid] = item
        field(item, "label", iid)
        kind = item.get("kind")
        importance = item.get("importance")
        decision = item.get("decision")
        require(kind in KINDS, f"{iid}: invalid kind")
        require(importance in ("essential", "supporting", "incidental"), f"{iid}: invalid importance")
        require(decision in ("standalone", "embedded", "duplicate", "exclude", "pending"), f"{iid}: invalid decision")
        for source in seq(item.get("sources"), f"{iid}.sources", 1):
            obj(source, f"{iid}.source")
            index, rid = source.get("pdf_index"), field(source, "region", iid)
            require(type(index) is int and regions.get(rid) == index, f"{iid}: wrong/missing source region")
            field(source, "evidence", iid)
            referenced_regions.add(rid)
        if decision == "standalone":
            require(importance in ("essential", "supporting"), f"{iid}: incidental item cannot be standalone")
            home = field(item, "home", iid)
            field(item, "reason", iid)
            require(kind in HOME_KINDS and node_sections.get(home) == HOME_KINDS[kind], f"{iid}: wrong standalone home")
            require(home not in standalone_homes, f"{iid}: standalone home {home} already used")
            standalone_homes.add(home)
        elif decision == "embedded":
            require(importance == "supporting" and kind != "source_only", f"{iid}: only supporting learning can be embedded")
            home, realization = field(item, "home", iid), field(item, "realization", iid)
            field(item, "reason", iid)
            require(home in nodes, f"{iid}: embedded home missing")
            require(any(realization in value for value in target_visible_strings(nodes[home])),
                    f"{iid}: embedded realization is absent from target-language learner text in {home}")
        elif decision == "duplicate":
            field(item, "duplicate_of", iid)
            field(item, "reason", iid)
        elif decision == "exclude":
            require(importance == "incidental", f"{iid}: only incidental material may be excluded")
            field(item, "reason", iid)
        else:
            blockers.append(f"Inventory item {iid} is pending")
        if importance == "essential":
            require(decision in ("standalone", "duplicate"), f"{iid}: essential item must resolve to standalone")
    for rid in sorted(set(regions) - referenced_regions):
        blockers.append(f"Source region {rid} has no candidate record")
    for iid, item in items.items():
        if item["decision"] != "duplicate":
            continue
        current, visited = item, {iid}
        while current["decision"] == "duplicate":
            target = current["duplicate_of"]
            require(target in items and target not in visited, f"{iid}: missing/cyclic duplicate target")
            require(items[target]["kind"] == item["kind"], f"{iid}: duplicate changes kind")
            visited.add(target)
            current = items[target]
        require(current["decision"] == "standalone", f"{iid}: duplicate must resolve to standalone")
    require(set(nodes) == standalone_homes,
            "Every learner card needs exactly one standalone source decision; mismatch: " +
            ", ".join(sorted(set(nodes) ^ standalone_homes)))
    check_private_terms(lesson, inventory)
    if "story" in lesson:
        validate_story(lesson, nodes, node_sections, blockers, notes)
    example_notes(lesson, inventory, notes)

    review = None
    hashes = {"inventory": inventory_hash, "lesson": lesson_hash, "source": source_hash}
    if review_path:
        review, review_hash = load_json(review_path)
        hashes["review"] = review_hash
        require(review["lesson_id"] == lesson["lesson_id"], "Review lesson ID differs")
        for name, expected in (("inventory_sha256", inventory_hash), ("lesson_sha256", lesson_hash)):
            require(hash_field(review, name, "review") == expected, f"Review {name} is stale")
        field(review, "reviewer", "review")
        field(review, "scope_note", "review")
        require(review.get("method") in ("independent-source-comparison", "author-second-pass"), "Invalid review method")
        checks = obj(review.get("checks"), "review.checks")
        expected = CHECKS | ({STORY_CHECK} if "story" in lesson else set())
        require(set(checks) == expected, "Review must record the seven v2 checks" +
                (f" plus {STORY_CHECK} for the story" if "story" in lesson else ""))
        for name, value in checks.items():
            require(value in ("pass", "fail", "not_checked"), f"Review {name}: invalid result")
            if value != "pass":
                blockers.append(f"Review {name}: {value}")
        finding_ids = set()
        for finding in seq(review.get("findings"), "review.findings"):
            obj(finding, "finding")
            fid = identifier(finding.get("id"), "finding.id")
            require(fid not in finding_ids, f"Duplicate finding {fid}")
            finding_ids.add(fid)
            for name in ("severity", "issue", "status"):
                field(finding, name, fid)
            require(finding["status"] in ("open", "resolved"), f"{fid}: invalid status")
            if finding["status"] == "open":
                blockers.append(f"Review finding {fid} is open: {finding['issue']}")
            else:
                field(finding, "resolution", fid)
    else:
        blockers.append("No source/selection/language review supplied")

    verified = False
    if source_path:
        require(file_hash(source_path) == source_hash, "Source SHA-256 differs from inventory")
        verified = True
        if Path(source_path).suffix.lower() == ".pdf":
            try:
                import pymupdf
                with pymupdf.open(source_path) as source:
                    require(max(scope) < source.page_count, "scope_pages index outside PDF")
            except ImportError:
                notes.append("Source hash checked; PDF bounds unavailable because pymupdf is not installed")
            except (RuntimeError, ValueError) as error:
                raise PackError(f"Cannot verify PDF bounds: {error}") from error
    else:
        notes.append("Source bytes were not supplied for hash verification")
    text = (Path(source_text_path).read_text(encoding="utf-8") if source_text_path
            else source_text_of(source_path, scope) if source_path else None)
    if text:
        source_copy_notes(lesson, text, notes)
    elif source_path or source_text_path:
        notes.append("Source text unavailable for the originality check; pass --source-text with the lesson's text")
    return Bundle(inventory, lesson, review, hashes, nodes, node_sections, blockers, notes, verified)


def esc(value):
    return html.escape(str(value), quote=True)


def marked(example):
    text, cursor, parts = example["de"], 0, []
    for start, end in target_spans(example, "example"):
        parts.extend((esc(text[cursor:start]), "<mark>" + esc(text[start:end]) + "</mark>"))
        cursor = end
    return "".join(parts) + esc(text[cursor:])


def example_html(record, gloss_language):
    return "\n".join('<div class="ex">' + marked(example) +
                     f' <span class="tr" lang="{esc(gloss_language)}">— {esc(example["en"])}</span></div>'
                     for example in record["examples"])


def story_html(lesson, node_sections):
    """Section 4: the story, one span per sentence (audio and highlighting) and the lesson's words underlined."""
    story, support, prof = lesson["story"], lesson["gloss_language"], language.profile(lesson["target_language"])
    hints = {record["id"]: (f'{record["article"]} ' if record.get("article") else "") + f'{record["lemma"]}: {record["gloss"]}'
             for record in lesson["vocabulary"]}
    hints.update({record["id"]: f'{record["frame"]}: {record["gloss"]}' for record in lesson["redemittel"]})
    parts = [f'<h2><span class="num">4</span> {esc(prof["sections"]["story"])}</h2><div class="rule-under"></div>',
             f'<article class="story" id="story"><h3>{esc(story["title"])}</h3>']
    number = 0
    for index, paragraph in enumerate(story["paragraphs"], 1):
        text, marks = paragraph["de"], story_marks(paragraph, node_sections)
        sentences = []
        for start, end in sentence_spans(text, prof):
            number += 1
            cursor, inner = start, []
            for mark_start, mark_end, card in marks:
                if start <= mark_start and mark_end <= end:
                    inner += [esc(text[cursor:mark_start]),
                              f'<span class="lw" data-card="{esc(card)}" title="{esc(hints[card])}">{esc(text[mark_start:mark_end])}</span>']
                    cursor = mark_end
            inner.append(esc(text[cursor:end]))
            sentences.append(f'<span class="ss" id="story-s{number}">{"".join(inner)}</span>')
        parts.append(f'<div class="story-p" id="story-p{index}"><p>{" ".join(sentences)}</p>'
                     f'<details class="story-tr"><summary>{esc(prof["translation"])}</summary><p lang="{esc(support)}">{esc(paragraph["en"])}</p></details></div>')
    parts.append('</article>')
    return "".join(parts)


# A right-to-left language (Arabic, Hebrew): the sheet stays left to right for its English, and every line of text
# takes its direction from its first letter, so an Arabic example reads right to left beside its English translation.
RTL_CSS = ("h1,h3,.de,.ex,.tr,.forms,.head,.meaning,.when,.variant,.patterns p,.contrast,.story-p p,.story-tr p,"
           ".story h3{unicode-bidi:plaintext}")


def render_html(bundle, draft=False, template_path=TEMPLATE):
    require(draft or (bundle.reviewed and bundle.source_verified),
            "Reviewed rendering needs a passing current review and --source; otherwise use --draft")
    template = Path(template_path).read_text(encoding="utf-8")
    style = re.search(r"<style\b[^>]*>.*?</style>", template, re.I | re.S)
    require(style, "Shared template has no style block")
    lesson, support = bundle.lesson, bundle.lesson["gloss_language"]
    prof = language.profile(lesson["target_language"])
    titles = {key: esc(name) for key, name in prof["sections"].items()}
    status = "draft" if draft else "reviewed"
    parts = ['<!DOCTYPE html>', f'<html lang="{esc(lesson["target_language"])}"><head>',
             '<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">',
             f'<meta name="study-pack-status" content="{status}">',
             f'<title>{esc(lesson["lesson_id"])} — {esc(lesson["title"])}</title>', style.group(0)]
    if prof.get("direction") == "rtl":
        parts.append(f"<style>{RTL_CSS}</style>")
    parts += ['</head><body><main class="wrap">',
             # The header names level and unit only: the source's title, publisher and ISBN stay in _work.
             f'<header class="hero"><div class="lekt">{esc(lesson["level"])} · {esc(lesson["lesson_id"])}</div><h1>{esc(lesson["title"])}</h1></header>',
             f'<h2><span class="num">1</span> {titles["vocabulary"]}</h2><div class="rule-under"></div>']
    previous = None
    for record in lesson["vocabulary"]:
        if record["group"] != previous:
            parts.append(f'<h3>{esc(record["group"])}</h3><div class="grid">')
            if previous is not None:
                # Move the just-opened group after closing the previous grid.
                parts[-1] = '</div>' + parts[-1]
            previous = record["group"]
        article = record.get("article", "")
        article_html = f'<span class="art-{esc(language.article_class(prof, article))}">{esc(article)}</span> ' if article else ""
        forms = f'<p class="forms">{esc(record["forms"])}</p>' if record.get("forms", "").strip() else ""
        parts.append(f'<article class="voc" id="{esc(record["id"])}"><div class="top"><span class="de">{article_html}{esc(record["lemma"])}</span><span class="en">{esc(record["gloss"])}</span></div>{forms}{example_html(record, support)}</article>')
    if previous is not None:
        parts.append('</div>')
    parts.extend([f'<h2><span class="num">2</span> {titles["grammar"]}</h2><div class="rule-under"></div>'])
    for record in lesson["grammar"]:
        patterns = ''.join(f'<p><b>{esc(pattern["label"])}:</b> {esc(pattern["form"])}</p>' for pattern in record["patterns"])
        contrast = f'<p class="contrast"><b>Important:</b> {esc(record["contrast"])}</p>' if record.get("contrast") else ""
        parts.append(f'<article class="rule" id="{esc(record["id"])}"><h3>{esc(record["title"])}</h3><p><b>Meaning:</b> {esc(record["meaning"])}</p><p><b>Rule:</b> {esc(record["rule"])}</p><div class="patterns">{patterns}</div>{contrast}{example_html(record, support)}</article>')
    parts.extend([f'<h2><span class="num">3</span> {titles["redemittel"]}</h2><div class="rule-under"></div>'])
    previous = None
    for record in lesson["redemittel"]:
        if record["group"] != previous:
            parts.append(f'<h3>{esc(record["group"])}</h3>')
            previous = record["group"]
        register = f' · {esc(record["register"])}' if record.get("register") else ""
        variants = ''.join(f'<p class="variant">{esc(variant["form"])} — {esc(variant["usage"])}</p>' for variant in record.get("variants", []))
        parts.append(f'<article class="phrase" id="{esc(record["id"])}"><div class="head">{esc(record["frame"])}</div><p class="meaning">{esc(record["gloss"])}</p><div class="when">{esc(record["when"])}{register}</div>{variants}{example_html(record, support)}</article>')
    if lesson.get("story"):
        parts.append(story_html(lesson, bundle.node_sections))
    parts.append('</main></body></html>')
    return "\n".join(parts) + "\n"


def render_files(bundle, output, draft=False, template_path=TEMPLATE):
    output = Path(output)
    require(output.suffix.lower() == ".html", "--output must be an HTML filename")
    require(output.parent.is_dir(), "Output directory does not exist")
    require(not output.exists(), "Output exists; use a new versioned filename")
    if draft:
        require("draft" in output.stem.casefold(), "Draft output filename must contain DRAFT")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render_html(bundle, draft, template_path))
    return (output,)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "render"))
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--source-text", type=Path,
                        help="UTF-8 text of the lesson pages, for the originality check (a PDF source is read directly when pymupdf is installed)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args(argv)
    try:
        bundle = validate_bundle(args.inventory, args.lesson, args.review, args.source, args.source_text)
        print("MECHANICAL PASS: internal source decisions, mappings, examples and hashes are consistent.")
        print("SEMANTIC REVIEW: " + (bundle.review["method"] if bundle.reviewed else "not accepted for reviewed release"))
        for message in bundle.blockers:
            print("BLOCKER: " + message)
        for message in bundle.notes:
            print("NOTE: " + message)
        print("LIMIT: software cannot judge pedagogical selection or German accuracy.")
        if args.command == "validate" and bundle.blockers and not args.draft:
            return 1
        if args.command == "render":
            require(args.output is not None, "render requires --output")
            for path in render_files(bundle, args.output, args.draft):
                print("WROTE: " + str(path))
        return 0
    except (PackError, OSError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
