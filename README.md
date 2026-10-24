# Lesson Distiller

**Turn your German course book into something you can actually study on the go.**

Lesson Distiller is a [Claude Code](https://code.claude.com) skill. You give it a lesson from a German course book you own, as a PDF, scans or notes. It gives back:

1. **A compact study sheet per lesson**, with only what's worth remembering, in three sections:
   - **Wortschatz**: words with article, plural and forms, each with one natural example sentence and its translation.
   - **Grammatik**: every rule the lesson teaches, with meaning, rule, pattern and examples, plus a contrast where learners usually slip.
   - **Redemittel**: reusable phrases for e-mails, opinions, requests and small talk, each with a use cue and an example.
2. **One offline study app for the whole book**, a single HTML file that runs on your phone:
   - **Lernen:** every sheet, with 🔊 neural audio on every German word, example and phrase. "Ganze Lektion anhören" plays a whole unit as a guided listening session, with pauses to repeat and grammar explained in English.
   - **Üben:** flashcards with spaced repetition. Tap to flip, swipe right (knew it) or left (again), and practise in short rounds of 10 with a daily goal and a streak.
3. **MP3 listening episodes**, one per lesson (15–30 minutes): German, a pause to repeat, English. They're made for the commute.

![The study app: lesson view, grammar with spoken explanation, flashcard, answer](docs/app-screens.png)

*Screens from the included [sample course](examples/sample-course/), which uses original example content.*

## Why it works

Rereading a lesson feels productive but fades fast. Lesson Distiller reads the *whole* lesson (word lists, picture vocabulary, grammar boxes, model texts, workbook tasks) and keeps only what materially improves your German. Every card is checked for accuracy before it reaches you, so a lesson becomes a single page you can absorb.

The app then does the remembering for you. Spaced repetition decides what comes back and when, listening with pauses trains your ear and pronunciation, and the Redemittel cards ask the way an exam does: the situation is shown in English and you produce the German phrase.

## Install

In Claude Code:

```text
/plugin marketplace add omaratif1995/language-lesson-distiller
/plugin install lesson-distiller@lesson-distiller
```

Or copy `plugins/lesson-distiller/skills/distill-lesson/` into `~/.claude/skills/` (all projects) or `.claude/skills/` (one project).

**Requirements:** Python 3.10+. For audio, also run `pip install edge-tts imageio-ffmpeg`.

## Use

Just ask, for example:

- *"Distill Lektion 3 of `Kursbuch.pdf` and the matching Arbeitsbuch pages."*
- *"Do lessons 1–6 the same way and build the study app with audio."*
- *"Make MP3 listening episodes for all finished lessons."*

Or call the skill directly: `/lesson-distiller:distill-lesson`.

Claude inspects the pages, writes the lesson data, validates it with the bundled scripts and renders the sheet. Everything lands in a `<book> - Digested` folder next to your source. Earlier versions are kept.

## Privacy and copyright

- **Your own books only.** Use the skill with material you own or are licensed to use. The sheets and the app are for your own study; don't publish a commercial book's content.
- **Everything stays local**, except audio. Speech is generated with Microsoft's neural voices through `edge-tts`, which sends the selected sentences to that service. The skill asks before it does that, and you can always build without audio (`--no-audio`).
- **Progress stays on your device.** The app has no account and no tracking. Your progress lives in your phone's browser, and the backup button moves it between devices.

## Good to know

- **Language:** built and tested for German course books, with B1-level material in mind.
- **iPhone:** the Files and messenger preview doesn't run the app's buttons. Open it from a browser that runs local files, or host it privately. The MP3s play everywhere.
- **A study aid, not a guarantee.** A digest replaces rereading, not practice. Listening to real-speed German, speaking with a partner and timed exam practice are still on you.

## Repository layout

```text
.claude-plugin/marketplace.json          marketplace entry
plugins/lesson-distiller/                the plugin
  skills/distill-lesson/SKILL.md         the skill (workflow and quality rules)
  skills/distill-lesson/references/      authoring rules, data contract, app and audio design
  skills/distill-lesson/scripts/         validator, renderer, audio and app builders, tests
examples/sample-course/                  two original sample lessons, their sheets and the app
```

Run the tests with `python -m unittest` inside `scripts/`.

## License

[MIT](LICENSE)
