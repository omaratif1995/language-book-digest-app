# Learner-sheet specification

The HTML is a compact reference to study and listen to, not a workbook or a record of the build process.

A small header names the level, the unit and the topic. **It never names the source**: no book title, publisher, ISBN, author, teacher, school or character names, anywhere in the sheet. List such names in the inventory's `private_terms`, and the validator refuses any learner text that contains them. Write the lesson title yourself, from the topic (*Auslandssemester*, *Alternatives Wohnen*); do not copy the source's chapter title.

After the header, render these `h2` sections in this order:

1. `Wortschatz`
2. `Grammatik`
3. `Redemittel`
4. `Geschichte`: the closing story (see [story-writing.md](story-writing.md))

No other learner-facing section or meta panel is allowed. Do not add a goal, Start route, summary, article legend, navigation, source status, media warning, practice, quiz, culture box, progress indicator, strategy, inventory or coverage note. Practice and games belong to the course app, not the sheet.

If embedded audio was requested, a compact listening control may appear inside the identifying header, and small pronunciation buttons may sit beside the German strings they play. These are controls, not another section.

## Wortschatz

Use a few meaningful semantic groups when they improve scanning. Do not create Core/Later tiers.

Every selected item is an individual card with:

- clean headword and concise English meaning;
- article and useful plural/no-plural information for a noun;
- for a verb: the Perfekt (*hat/ist* + Partizip II), with (!) for an irregular form, plus the reflexive/separable form, preposition and case or the collocation the lesson uses; and
- one marked, translated, natural example (see [example-sentence-rules.md](example-sentence-rules.md)).

A second example is justified only by a different important source-taught use. A complete small explicit word field should stay coherent. Incidental text words do not become cards simply because they occurred.

Forms are supporting text, not an excuse for a mini dictionary entry. Omit principal-part clutter the lesson does not need; the Perfekt of a verb is never clutter.

## Grammatik

Use one rule card per concept the learner needs to distinguish. Include all explicitly taught grammar, including small rules. Separate concepts when merging would make the learner decode too much at once.

Each card contains:

- `meaning`: what the structure communicates or when it is used;
- `rule`: the shortest accurate formation/choice explanation;
- one or more compact `patterns`;
- normally 2–4 marked, translated examples; and
- optional `contrast` only when it prevents a likely error.

Let examples carry explanation. Do not copy a complete textbook table when a compact pattern plus examples teaches the same decision. Do not impose a number of rule cards.

## Redemittel

Group by communicative function supported by the lesson. All reusable speaking, writing and e-mail language stays in this one section; do not split it into skill-specific sections.

Each phrase card contains:

- reusable `frame` first, with placeholders such as `…`;
- short English meaning;
- one concise use cue;
- register only when it matters; and
- one marked, translated example.

Combine truly interchangeable variants when this saves repetition and the difference remains clear. Keep opposite moves, different constructions or materially different registers separate. Never copy a whole letter, dialogue or reading passage.

## Geschichte

One original story of four to seven paragraphs that reuses most of the lesson: at least 80 % of the vocabulary cards, every grammar point and at least half of the Redemittel, in natural sentences. The lesson's words and phrases are underlined, with their meaning on hover or tap. Each paragraph's English translation is folded under *Übersetzung*: the only content on the sheet that may be folded, because it is a check, not the text to read. [story-writing.md](story-writing.md) describes how to write it.

## Density and presentation

Prefer the visual density of the earlier v3 sheets: short cards, modest group headings and generous enough spacing to scan. Keep article colours on the noun itself if useful, but no legend. Keep all selected learning content visible; apart from the story's translations, do not use folding, tabs or hidden "more" content.

The page should feel finished without a footer, recap or instruction block. Its four sections are the study experience.
