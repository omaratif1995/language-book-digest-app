#!/usr/bin/env python3
"""Check the compact learner HTML structure: three teaching sections and an optional closing Geschichte."""
from __future__ import annotations

import argparse
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
REQUIRED = ("Wortschatz", "Grammatik", "Redemittel")
STORY = "Geschichte"
ISBN = re.compile(r"\b97[89](?:[-\s]?\d){10}\b")
FORBIDDEN_TEXT = ("Start hier", "Start here", "Mini-Abruf", "30-Sekunden-Merkhilfe",
                  "coverage report", "coverage notes", "source coverage", "source review",
                  "source scope", "Later material", "progress tracking", "study route",
                  "article legend", "review status")
FORBIDDEN_CLASSES = {"goal", "start", "legend", "study-nav", "source-note", "summary", "practice", "quiz"}


def classes(attrs):
    return set(dict(attrs).get("class", "").split())


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.headings = [], [], []
        self.heading = None
        self.section = ""
        self.cards, self.rules = [], []
        self.hidden, self.disclosures, self.vocab_tables = [], [], []
        self.forbidden_classes, self.ids = [], {}
        self.story_paragraphs = 0

    def active(self, kind):
        for _, info in reversed(self.stack):
            if isinstance(info, dict) and info.get("kind") == kind:
                return info
        return None

    def handle_starttag(self, tag, attrs):
        info, attributes, cls = None, dict(attrs), classes(attrs)
        if cls & FORBIDDEN_CLASSES:
            self.forbidden_classes.append((self.getpos()[0], sorted(cls & FORBIDDEN_CLASSES)))
        if "hidden" in attributes or attributes.get("aria-hidden") == "true" or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attributes.get("style", ""), re.I):
            self.hidden.append(self.getpos()[0])
        if tag == "details" and not ("story-tr" in cls and self.section == STORY):
            self.disclosures.append(self.getpos()[0])     # only the story's translations may be folded
        if "story-p" in cls and self.section == STORY:
            self.story_paragraphs += 1
        if tag == "table" and self.section == "Wortschatz":
            self.vocab_tables.append(self.getpos()[0])
        if "id" in attributes:
            if attributes["id"] in self.ids:
                self.errors.append(f"duplicate ID {attributes['id']}")
            self.ids[attributes["id"]] = self.getpos()[0]
        if tag == "h2":
            self.heading = []
        elif tag in ("article", "div") and ("voc" in cls or "phrase" in cls):
            info = {"kind": "card", "classes": cls, "section": self.section, "line": self.getpos()[0], "examples": []}
            self.cards.append(info)
        elif tag in ("article", "div") and "rule" in cls:
            info = {"kind": "rule", "line": self.getpos()[0], "examples": []}
            self.rules.append(info)
        elif tag == "div" and "ex" in cls:
            info = {"kind": "example", "text": [], "marks": []}
            if self.active("card"):
                self.active("card")["examples"].append(info)
            if self.active("rule"):
                self.active("rule")["examples"].append(info)
        elif tag == "mark":
            info = {"kind": "mark", "text": []}
            if self.active("example"):
                self.active("example")["marks"].append(info)
        if tag not in VOID:
            self.stack.append((tag, info))

    def handle_data(self, data):
        if self.heading is not None:
            self.heading.append(data)
        for kind in ("example", "mark"):
            current = self.active(kind)
            if current:
                current["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "h2" and self.heading is not None:
            text = " ".join("".join(self.heading).split())
            self.headings.append(text)
            self.section = next((name for name in REQUIRED + (STORY,) if name.casefold() in text.casefold()), text)
            self.heading = None
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"extra closing </{tag}>")
            return
        opened, _ = self.stack[-1]
        if opened != tag:
            self.errors.append(f"closing </{tag}> does not match <{opened}>")
            return
        self.stack.pop()


def meaningful(example):
    return bool("".join(example["text"]).strip()) and any("".join(mark["text"]).strip() for mark in example["marks"])


def normalized_heading(heading):
    label = re.sub(r"^\s*\d+[.)]?\s*", "", heading).strip()
    return next((name for name in REQUIRED + (STORY,) if label.casefold() == name.casefold()), "")


def style(text):
    match = re.search(r"<style\b[^>]*>.*?</style>", text, re.I | re.S)
    return match.group(0) if match else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sheet", type=Path)
    ap.add_argument("--expected-style", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    try:
        text = args.sheet.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    parser = Parser()
    parser.feed(text)
    parser.close()
    failures, warnings = [], []
    if not re.search(r"<meta\s+charset=[\"']?utf-8", text, re.I):
        failures.append("missing UTF-8 meta")
    if parser.errors or parser.stack:
        failures.extend(parser.errors)
        if parser.stack:
            failures.append("unclosed tags")
    normalized = tuple(normalized_heading(heading) for heading in parser.headings)
    if normalized not in (REQUIRED, REQUIRED + (STORY,)):
        failures.append("the h2 sections must be Wortschatz, Grammatik, Redemittel and optionally Geschichte, in this order")
    if STORY in normalized and parser.story_paragraphs < 3:
        failures.append("the Geschichte needs at least three paragraphs")
    for card in parser.cards:
        if not card["examples"] or not all(meaningful(example) for example in card["examples"]):
            failures.append(f"card on line {card['line']} lacks a marked example")
    for rule in parser.rules:
        if len(rule["examples"]) < 2 or not all(meaningful(example) for example in rule["examples"]):
            failures.append(f"grammar rule on line {rule['line']} needs at least two marked examples")
    if parser.vocab_tables:
        failures.append("vocabulary tables are forbidden; selected words need example cards")
    if parser.hidden or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", style(text), re.I):
        failures.append("hidden learning content found")
    if parser.disclosures:
        failures.append("collapsible details found")
    if parser.forbidden_classes:
        failures.append("forbidden learner-facing meta section/class found")
    visible_text = " ".join(unescape(re.sub(r"<(?:style|script)\b.*?</(?:style|script)>", " ", text, flags=re.I | re.S)).split())
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", visible_text).split())
    for phrase in FORBIDDEN_TEXT:
        if phrase.casefold() in visible_text.casefold():
            failures.append(f"forbidden learner-facing text found: {phrase}")
    if ISBN.search(visible_text):
        failures.append("the sheet names an ISBN; learner output never names its source")
    external = re.findall(r"<(?:script|link|img|audio|video)\b[^>]+(?:src|href)=[\"']https?://", text, re.I)
    if external:
        failures.append("external dependency found")
    status = re.search(r'<meta\s+name=["\']study-pack-status["\']\s+content=["\'](draft|reviewed)["\']', text, re.I)
    if not status:
        failures.append("missing machine-only study-pack-status meta")
    if args.expected_style and style(text) != style(args.expected_style.read_text(encoding="utf-8")):
        warnings.append(f"style differs from {args.expected_style}")
    vocabulary = [c for c in parser.cards if "voc" in c["classes"]]
    phrases = [c for c in parser.cards if "phrase" in c["classes"]]
    print(f"Sheet: {args.sheet.name}")
    print(f"Sections: {' | '.join(parser.headings)}")
    print(f"Vocabulary: {len(vocabulary)}; grammar: {len(parser.rules)}; Redemittel: {len(phrases)}; "
          f"story paragraphs: {parser.story_paragraphs}")
    print("LIMIT: structure only; selection and German require source/language review.")
    for message in warnings:
        print("WARN: " + message)
    for message in failures:
        print("FAIL: " + message)
    return 1 if failures or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
