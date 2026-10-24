#!/usr/bin/env python3
"""Validate internal lesson records and render a compact three-section study sheet.

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


SCHEMA = 2
KINDS = {"vocabulary", "grammar", "expression", "source_only"}
CHECKS = {"source_inspection", "selection_quality", "vocabulary_quality",
          "grammar_accuracy", "redemittel_value", "example_integration", "compression"}
SECTIONS = {"vocabulary": "vocabulary", "grammar": "grammar", "redemittel": "expression"}
HOME_KINDS = {"vocabulary": "vocabulary", "grammar": "grammar", "expression": "redemittel"}
LESSON_KEYS = {"schema_version", "lesson_id", "inventory_sha256", "title", "level",
               "target_language", "gloss_language", "vocabulary", "grammar", "redemittel"}
FORBIDDEN_LEARNER_FIELDS = {"goal", "core_ids", "start_grammar_id", "start_expression_id",
                            "start_labels", "contexts", "practice", "recap", "later"}
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
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


def target_spans(example, where):
    obj(example, where)
    text = field(example, "de", where)
    field(example, "en", where)
    targets = unique_strings(example.get("targets"), f"{where}.targets", 1)
    spans = []
    for target in targets:
        edge = r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_]"
        prefix = r"(?<!\w)" if re.fullmatch(edge, target[0]) else ""
        suffix = r"(?!\w)" if re.fullmatch(edge, target[-1]) else ""
        matches = list(re.finditer(prefix + re.escape(target) + suffix, text))
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


def validate_bundle(inventory_path, lesson_path, review_path=None, source_path=None):
    inventory, inventory_hash = load_json(inventory_path)
    lesson, lesson_hash = load_json(lesson_path)
    require(inventory["lesson_id"] == lesson["lesson_id"], "Inventory and lesson IDs differ")
    require(set(lesson) == LESSON_KEYS,
            "Lesson top-level fields must contain only the three-section v2 contract; unexpected/missing: " +
            ", ".join(sorted(set(lesson) ^ LESSON_KEYS)))
    require(not (set(lesson) & FORBIDDEN_LEARNER_FIELDS), "Learner-meta fields are forbidden in v2 lesson data")
    require(hash_field(lesson, "inventory_sha256", "lesson") == inventory_hash,
            "Lesson inventory_sha256 is stale")
    source_hash = hash_field(inventory, "source_sha256", "inventory")
    for name in ("book", "scope_label"):
        field(inventory, name, "inventory")
    for name in ("title", "level", "target_language", "gloss_language"):
        field(lesson, name, "lesson")
    require(lesson["target_language"].split("-")[0].lower() == "de",
            "This skill revision is for German learner sheets (target_language de)")

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
                if record["pos"] == "noun":
                    article = field(record, "article", nid)
                    require(article in ("der", "die", "das"), f"{nid}: German noun needs der/die/das")
                    require(not record["lemma"].startswith(article + " "), f"{nid}: do not repeat article in lemma")
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
        require(set(checks) == CHECKS, "Review must record the seven v2 checks")
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


def render_html(bundle, draft=False, template_path=TEMPLATE):
    require(draft or (bundle.reviewed and bundle.source_verified),
            "Reviewed rendering needs a passing current review and --source; otherwise use --draft")
    template = Path(template_path).read_text(encoding="utf-8")
    style = re.search(r"<style\b[^>]*>.*?</style>", template, re.I | re.S)
    require(style, "Shared template has no style block")
    lesson, support = bundle.lesson, bundle.lesson["gloss_language"]
    status = "draft" if draft else "reviewed"
    parts = ['<!DOCTYPE html>', f'<html lang="{esc(lesson["target_language"])}"><head>',
             '<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">',
             f'<meta name="study-pack-status" content="{status}">',
             f'<title>{esc(lesson["lesson_id"])} — {esc(lesson["title"])}</title>', style.group(0),
             '</head><body><main class="wrap">',
             f'<header class="hero"><div class="lekt">{esc(bundle.inventory["book"])} · {esc(lesson["level"])} · {esc(lesson["lesson_id"])}</div><h1>{esc(lesson["title"])}</h1></header>',
             '<h2><span class="num">1</span> Wortschatz</h2><div class="rule-under"></div>']
    previous = None
    for record in lesson["vocabulary"]:
        if record["group"] != previous:
            parts.append(f'<h3>{esc(record["group"])}</h3><div class="grid">')
            if previous is not None:
                # Move the just-opened group after closing the previous grid.
                parts[-1] = '</div>' + parts[-1]
            previous = record["group"]
        article = record.get("article", "")
        article_html = f'<span class="art-{esc(article)}">{esc(article)}</span> ' if article else ""
        forms = f'<p class="forms">{esc(record["forms"])}</p>' if record.get("forms", "").strip() else ""
        parts.append(f'<article class="voc" id="{esc(record["id"])}"><div class="top"><span class="de">{article_html}{esc(record["lemma"])}</span><span class="en">{esc(record["gloss"])}</span></div>{forms}{example_html(record, support)}</article>')
    if previous is not None:
        parts.append('</div>')
    parts.extend(['<h2><span class="num">2</span> Grammatik</h2><div class="rule-under"></div>'])
    for record in lesson["grammar"]:
        patterns = ''.join(f'<p><b>{esc(pattern["label"])}:</b> {esc(pattern["form"])}</p>' for pattern in record["patterns"])
        contrast = f'<p class="contrast"><b>Important:</b> {esc(record["contrast"])}</p>' if record.get("contrast") else ""
        parts.append(f'<article class="rule" id="{esc(record["id"])}"><h3>{esc(record["title"])}</h3><p><b>Meaning:</b> {esc(record["meaning"])}</p><p><b>Rule:</b> {esc(record["rule"])}</p><div class="patterns">{patterns}</div>{contrast}{example_html(record, support)}</article>')
    parts.extend(['<h2><span class="num">3</span> Redemittel</h2><div class="rule-under"></div>'])
    previous = None
    for record in lesson["redemittel"]:
        if record["group"] != previous:
            parts.append(f'<h3>{esc(record["group"])}</h3>')
            previous = record["group"]
        register = f' · {esc(record["register"])}' if record.get("register") else ""
        variants = ''.join(f'<p class="variant">{esc(variant["form"])} — {esc(variant["usage"])}</p>' for variant in record.get("variants", []))
        parts.append(f'<article class="phrase" id="{esc(record["id"])}"><div class="head">{esc(record["frame"])}</div><p class="meaning">{esc(record["gloss"])}</p><div class="when">{esc(record["when"])}{register}</div>{variants}{example_html(record, support)}</article>')
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args(argv)
    try:
        bundle = validate_bundle(args.inventory, args.lesson, args.review, args.source)
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
