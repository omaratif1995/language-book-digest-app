# Behavioral evaluation cases

Use these cases when revising the skill. Test with raw lesson pages, not an old generated sheet. Passing schema validation is necessary but not sufficient: a fresh evaluator must also judge the selection and teaching quality.

## Positive cases

### MENSCHEN B1, lesson 12

- Preserve the complete small workplace-event field when the lesson explicitly teaches all seven items.
- Teach every explicit grammar point separately enough to understand it: Genitiv, the taught adjective endings, `trotz`, and the small but important `außer + Dativ` rule.
- Extract reusable invitation, acceptance, refusal, question, and information-request templates from communication boxes and model/productive texts.
- Give every selected vocabulary item a natural lesson-grounded example.
- Reinforce a few worthwhile supporting words or constructions inside those examples without creating more cards.
- Reject the every-token interpretation: names, dates, itinerary facts, routine instructions, and ordinary reading support do not become cards merely because they occur.

### MENSCHEN B1, lesson 16

- Preserve both explicitly taught modal alternatives if the lesson contrasts `nicht brauchen zu` and `nur brauchen zu`.
- Do not promote every word from a narrative to standalone vocabulary.
- Keep examples focused enough that the learner can still identify the card's primary target.

### Picture vocabulary

- Inspect labels visually when text extraction loses layout or pairs a word with the wrong image.
- Keep a coherent, explicitly taught small field intact rather than dropping arbitrary members to meet a quota.

### Productive writing

- Inspect model emails, prompts, and response tasks for reusable Redemittel even when no box is labelled `Redemittel`.
- Preserve useful placeholders and register differences without reproducing the full model text.

### Story and originality

- The Geschichte is a real story with a pull, reuses at least 80 % of the vocabulary cards, every grammar point and half of the Redemittel, and still reads naturally.
- Nothing in the sheet names the source: a course book with its title, publisher, ISBN and character names on every page produces a sheet with none of them, and with the learner's own unit title.
- Examples are newly written: no character from the book, no copied sentence, no book statistic.
- Examples pass the quality bar: adult, specific, useful, level-appropriate; neither silly nor A1-flat.

## Mechanical failure cases

The pipeline must reject:

- an essential item marked `embedded` or `exclude`;
- an embedded realization absent from the target-language text of its home card;
- a selected vocabulary or Redemittel card without a natural example;
- an explicit source region with no candidate decision;
- a pending source region, item, or supplied-but-unreviewed dependency in a reviewed release;
- stale source, inventory, lesson, or review hashes;
- old lesson fields for goals, Start material, practice, recap, coverage, or source notes;
- HTML with a fourth learner section, audit/status prose, a legend, exercise, summary, fold, hidden content, or vocabulary table;
- a truncated verb lemma such as `sich` or `jemandem` without the actual verb;
- grammar with fewer than two examples;
- learner text containing a `private_terms` name or an ISBN;
- a story form that does not occur in its paragraph, underlined forms that overlap, a story that skips a grammar point or uses under 60 % of the vocabulary; and
- a story without a `story_quality` review check.

## Semantic failure cases

A fresh evaluator must fail a sheet that is mechanically valid but has any of these defects:

- artificial filler examples;
- inflated vocabulary selected mainly because it appears in the source;
- omission of an explicitly taught point because it appears only once;
- arbitrary trimming of a coherent small taught set;
- overloaded examples that hide several unfamiliar targets in one sentence;
- false or missing register guidance;
- copied grammar tables without meaning, use, or a memorable rule;
- Redemittel limited to a labelled box while reusable writing patterns are missed;
- silly, empty or A1-flat examples (*Das Seminar ist interessant.*);
- a story that is a list of lesson words, retells the source, or stuffs several new items into each sentence; or
- V5.1-style inventories, source machinery, or coverage accounting exposed in learner HTML.

## Acceptance comparison

Compare the candidate sheet with a strong V3 sheet for psychological size and scanability, not for exact card count. Accept only when it keeps that compact feel while improving natural examples, grammar completeness and accuracy, and reusable Redemittel. The target is near-lossless compression of learning value, not near-lossless reproduction of source text.
