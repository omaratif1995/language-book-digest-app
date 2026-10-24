# Merged HTML flashcard trainer

`build_course_app.py` implements this trainer as the *Üben* tab of the course app (see [course-app.md](course-app.md)), with the spaced-repetition schedule, rounds and gestures described there. The requirements below remain the acceptance criteria for any trainer.

Build this only when the user asks for an all-lesson practice surface, or offer it after several lesson sheets have been accepted. A study sheet remains the default deliverable; Anki CSV is optional, not a hidden dependency of the trainer.

## Data source

Render the trainer from the same structured lesson records used to render the sheets. This prevents card wording, examples, categories, and lesson labels from drifting.

If the user explicitly requested CSV, it may be parsed as the input. If no structured records or CSV exist, carefully reconstruct data from accepted sheets and state that it is a reconstruction; do not hand-copy an unverified deck from memory.

Each trainer record needs at least:

```json
{"lesson": 13, "category": "wortschatz", "tier": "core", "front": "das Geschirr", "back": "the dishes<br><i>…</i>"}
```

Use the learner’s recall direction: vocabulary/grammar prompt → answer; communicative job → phrase; task goal → frame. Keep one decision per card.

## Interaction

The self-contained HTML must include:

- lesson filter and category filters that match the sheet’s sections: Wortschatz, Grammatik, and Redemittel. Redemittel context may be a secondary filter, never a competing top-level section;
- lesson/category filters over the same pedagogically selected cards as the study sheets;
- flip on click and Space; previous/next on buttons and arrow keys;
- visible filtered-card count and a calm empty state;
- shuffle as an optional control; and
- optional local `know it` / `still learning` state only when it stays unobtrusive. Explain that browser-local state does not sync or replace spaced repetition.

Use the study-sheet colour tokens and text labels, but do not invent a second visual language. Keep the core loop—filter, recall, flip, next—usable with no setup and no network connection.

## Local-first requirements

- Inline CSS, JavaScript, and data. Never fetch a sibling CSV at runtime; `file://` pages often block it.
- Do not load CDN fonts, scripts, images, trackers, or analytics.
- Place the output inside the book's `<book title> - Digested` folder. Name the file by its purpose or level, for example `A22_Flashcard_Trainer.html`.

## Validate

Open the output directly from disk and test:

1. all filter combinations, including an empty result;
2. keyboard flip and navigation without focus becoming trapped;
3. vocabulary, grammar, Redemittel and single-lesson passes;
4. one card from every category against its original structured record; and
5. offline behaviour with the browser network disabled if practical.
