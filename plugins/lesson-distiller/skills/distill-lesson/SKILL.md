---
name: distill-lesson
description: Distill a German course-book lesson (PDF pages, scans or notes) into a compact learner sheet with only Wortschatz, Grammatik and Redemittel, then optionally turn the finished units into one offline study app (listening with neural audio, spaced-repetition flashcards) and MP3 listening episodes. Use when a learner wants a book's high-value language without textbook noise, wants to study it on the phone, or asks for audio or flashcards of their lessons.
---

# Distill Lesson

Turn a supplied lesson into a psychologically manageable substitute for rereading it:

**complete source inspection → intelligent learning compression → concise learner sheet**

Optimize for learning value per line, not extracted-item count. The analysis may be exhaustive; the HTML must not look like an audit, workbook, learning dashboard, or second textbook.

## Non-negotiable learner output

Put new deliverables in the source’s sibling folder `<filename without final extension> - Digested`. Preserve earlier versions and choose a new versioned filename.

The learner-facing HTML contains a small identifying title and exactly these three sections, in this order:

1. `Wortschatz`
2. `Grammatik`
3. `Redemittel`

Do not render goals, Start routes, study instructions, article legends, navigation, source/review notes, coverage tables, cultural commentary sections, exercises, quizzes, summaries, “Later” material, progress UI, inventories, IDs or locations. Internal working JSON/reviews live under `_work` or `_skill_test`, never in the learner route. Read [section-spec.md](references/section-spec.md) before authoring.

Work only from material the learner owns or is licensed to use, and keep sources and outputs local. A digest of a commercial course book is for the learner's own study; do not publish the book's pages, audio or the digest itself on the learner's behalf.

Scripts live in this skill's `scripts/` folder. `<skill-dir>` below means the base directory Claude Code reports when this skill loads (plugin or standalone install alike). They need Python 3.10+; audio additionally needs `edge-tts` and ffmpeg (`imageio-ffmpeg` provides one).

## 1. Inspect the whole lesson internally

Read [source-extraction.md](references/source-extraction.md). Verify the actual lesson boundaries and inspect all relevant pages, picture vocabulary, margins, grammar/communication references, model texts and linked writing/speaking tasks. Text extraction is an aid, not visual inspection. Record missing audio internally and do not invent spoken-only content.

Create the internal inventory described in [data-contract.md](references/data-contract.md) before the lesson data. The inventory prevents silent omissions; it is not a list of things that must become cards.

For each candidate, ask:

> If the learner remembers this after finishing the lesson, will it materially improve their German?

Classify it as:

- **standalone**: deserves focused learner attention;
- **embedded**: worth reinforcing inside a selected example, grammar pattern or expression, but not worth another card;
- **duplicate**: the same learning decision already has a home; or
- **excluded**: source detail with no meaningful learning payoff here.

Explicit grammar, an explicit Wortfeld/Bildlexikon, and highly reusable communicative/writing patterns are essential and normally standalone. Names, dates, plot facts, one-off itineraries, routine instruction words and ordinary support vocabulary are usually excluded. Read [nugget-compression.md](references/nugget-compression.md) for the selection test. Do not use quotas as a substitute for judgment.

## 2. Write the three teaching sections

Author the structured lesson data from the selected inventory. The renderer must not mine old sheets, invent filler, or promote every source token.

### Wortschatz

Choose vocabulary that the lesson explicitly teaches or meaningfully needs: complete small Wortfeld/Bildlexikon sets, recurring topic words, words required for the lesson’s speaking/writing goal, and useful level-appropriate collocations or constructions the lesson wants noticed.

Every chosen item earns its card and has one natural, translated example. A second example is only for a genuinely different important usage. Nouns show article, meaning and useful plural when relevant. Verbs show reflexive form, separability, preposition/case or common construction when relevant. Never write filler such as `Die Einladung ist heute wichtig` or grammatically broken dictionary-form examples. Read [example-sentence-rules.md](references/example-sentence-rules.md).

Keep coherent small taught sets complete. Do not arbitrarily remove two items from seven workplace events merely to shorten the sheet. Conversely, appearing once in a reading does not make an ordinary word a vocabulary target.

### Grammatik

Include every grammar point the lesson explicitly teaches, including a small but important rule such as `außer + Dativ`. Separate concepts when that makes the choice easier to understand. For each point, teach compactly:

- meaning or purpose;
- the core rule;
- a usable pattern;
- normally 2–4 strong, translated examples; and
- one exception or contrast only when it prevents a likely misunderstanding.

Do not copy a whole reference chapter or omit a distinction because its box is small. Examples should carry much of the explanation. Grammar accuracy outranks aggressive compression.

### Redemittel

Extract the best reusable templates from communication boxes, model texts, dialogues and productive tasks—especially writing. Cover the communicative jobs actually taught: invitations, replies, requests, reasons, opinions, formal email, small talk, complaints, or their lesson-specific equivalents.

Each card shows the reusable template first, a brief use cue, an English meaning and one natural example. Preserve placeholders (`…`) and concise formal/informal variants when they materially affect reuse. Do not copy full letters or create separate writing/reading/culture sections; all reusable language belongs here.

## 3. Use examples for implicit reinforcement

Selected examples may naturally recycle a supporting source word, earlier grammar or another useful collocation. This is the preferred way to increase coverage without increasing card count. The sentence must still be short, natural and easy to repeat; it must have one clear primary target.

Do not hide an explicitly taught grammar rule or essential vocabulary item only inside someone else’s example. Embedded coverage is for supporting material that genuinely improves the sentence, not for stuffing several unfamiliar decisions into one line. Record the exact embedded realization internally so it can be checked.

## 4. Review selection as well as accuracy

Run the mechanical validator, then use [quality-checklist.md](references/quality-checklist.md). Review in both directions:

- source → sheet: did an essential learning point disappear?
- sheet → source: does every card materially earn its space?

Check every German example, gloss, article/form, grammar statement, template and register. Independently compare the source when available; otherwise record an honest author second pass. Review findings and missing-media limitations remain internal or in the delivery message, never in the HTML.

Use the bundled version-2 pipeline:

```powershell
py -3 <skill-dir>/scripts/study_pack.py validate --inventory L01_Inventory_v2.json --lesson L01_Lesson_v2.json --review L01_Review_v2.json --source "BOOK.pdf"
py -3 <skill-dir>/scripts/study_pack.py render --inventory L01_Inventory_v2.json --lesson L01_Lesson_v2.json --review L01_Review_v2.json --source "BOOK.pdf" --output L01_Studysheet_v6.html
```

Without a completed review, render only to a filename containing `DRAFT`. Draft/review status is machine metadata, not learner-facing prose. Rendering creates only the HTML; internal evidence stays in `_work`.

Use [visual-design-system.md](references/visual-design-system.md) and the shared template. Run the HTML validator and, when possible, inspect desktop/mobile output. For a whole book, process and review each lesson separately and maintain an internal course map before claiming the full PDF is covered.

When the user requests audio, read [embedded-audio.md](references/embedded-audio.md). Keep the same three-section sheet and add unobtrusive pronunciation controls plus one whole-lesson playback control in the header. Generate clear neural speech ahead of time and embed the resulting audio bytes in the HTML; do not rely on browser speech synthesis or external media URLs. The whole-lesson control should reuse the embedded clips in reading order, so it does not duplicate the audio payload. Audio generation through a hosted service requires explicit permission to transmit the selected learner text to that service.

When revising or regression-testing this skill, apply [evaluation-cases.md](references/evaluation-cases.md). They deliberately test both directions of failure: omitting real teaching value and exposing source noise.

Do not promise that a digest alone guarantees competence or exam success. It should deliver the lesson’s concentrated learning value; listening, productive feedback and exam-specific performance require separate evidence. Read [competence-coverage.md](references/competence-coverage.md) only when making broader completion or exam-readiness claims.

Only read the flashcard references when the user explicitly requests Anki/CSV or a trainer. Those exports must use the same selected lesson data and must not broaden the learner sheet.

## 5. Turn finished units into a study app and listening episodes

When several units are reviewed and the learner wants to study on the phone, listen on the go, or practise with flashcards, read [course-app.md](references/course-app.md). It builds two deliverables from the same reviewed records, so nothing drifts:

- **one offline HTML study app**: *Lernen* (all sheets, 🔊 on every German item, a spoken grammar explanation, and a guided "listen to the whole unit" mode with pauses to repeat) and *Üben* (one card per sheet card, spaced repetition, tap to flip, swipe or tap to grade, skip, short rounds, a daily summary);
- **one MP3 episode per unit** for commuting: German, a pause to repeat aloud, English.

```powershell
py -3 <skill-dir>/scripts/course_audio.py plan --course course.json                          # offline: what would be synthesized
py -3 <skill-dir>/scripts/course_audio.py synth --course course.json --confirm-external-tts   # only after the user approved hosted TTS
py -3 <skill-dir>/scripts/course_audio.py episodes --course course.json --confirm-external-tts
py -3 <skill-dir>/scripts/build_course_app.py --course course.json --output Course_Studienpaket_v1.html
```

Only reviewed sheets go into the app. Without approval for hosted speech, build with `--no-audio`. The app is the course-level practice surface; it never changes the three-section sheets.
