# Lesson Distiller

**Turn your German course book into something you can actually study on the go.**

Lesson Distiller is an [Agent Skill](https://agentskills.io): a folder with instructions and Python scripts that an AI assistant follows. It works with Claude Code, OpenAI Codex, GitHub Copilot and other assistants that read the open Agent Skills format. You give it a lesson from a German course book you own, as a PDF, scans or notes. It gives back:

1. **A compact study sheet per lesson**, with only what's worth remembering, in three sections:
   - **Wortschatz**: words with article, plural and forms, each with one natural example sentence and its translation.
   - **Grammatik**: every rule the lesson teaches, with meaning, rule, pattern and examples, plus a contrast where learners usually slip.
   - **Redemittel**: reusable phrases for e-mails, opinions, requests and small talk, each with a use cue and an example.
2. **One offline study app for the whole book**, a single HTML file that runs on your phone:
   - **Lernen:** every sheet, with 🔊 neural audio on every German word, example and phrase, and a spoken explanation of each grammar point. "Ganze Lektion anhören" plays a whole unit as a guided listening session with pauses to repeat.
   - **Üben:** flashcards with spaced repetition and one tap per card. ✓ when you know it, and the next card appears; ✗ when you don't, and the answer opens. Practise in short rounds of 10, with a daily goal and a streak.
3. **MP3 listening episodes**, one per lesson (15–30 minutes): German, a pause to repeat, English. They're made for the commute.

![The study app: lesson view, grammar with spoken explanation, flashcard, answer](docs/app-screens.png)

*Screens from the included [sample course](examples/sample-course/), which uses original example content.*

## Why it works

Rereading a lesson feels productive but fades fast. Lesson Distiller reads the *whole* lesson (word lists, picture vocabulary, grammar boxes, model texts, workbook tasks) and keeps only what materially improves your German. Every card is checked for accuracy before it reaches you, so a lesson becomes a single page you can absorb.

The app then does the remembering for you. Spaced repetition decides what comes back and when. Listening with pauses trains your ear and pronunciation. The Redemittel cards ask the way an exam does: the situation is shown in English and you produce the German phrase.

**German always sounds German.** Every German word is spoken by a German voice, even inside an English explanation ("use «als» for the past"). English is spoken by an English voice. One bilingual voice would read short German words with English pronunciation.

## Install

Pick the line for your assistant. Every option installs the same folder, [`skills/distill-lesson/`](skills/distill-lesson/).

**Claude Code**

```text
/plugin marketplace add omaratif1995/language-lesson-distiller
/plugin install lesson-distiller@lesson-distiller
```

Or copy the folder to `~/.claude/skills/` (all projects) or `.claude/skills/` (one project).

**OpenAI Codex, GitHub Copilot and other Agent Skills clients**

Copy the folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```bash
git clone https://github.com/omaratif1995/language-lesson-distiller
mkdir -p ~/.agents/skills && cp -r language-lesson-distiller/skills/distill-lesson ~/.agents/skills/
```

On Windows: `Copy-Item -Recurse language-lesson-distiller\skills\distill-lesson $HOME\.agents\skills\`. GitHub Copilot also reads `~/.copilot/skills/` and `.github/skills/`. If your assistant doesn't find the skill, check its documentation for its skills folder, then restart it.

**Requirements:** Python 3.10 or newer. Audio also needs `pip install edge-tts pyspellchecker imageio-ffmpeg`.

## Use

Just ask, for example:

- *"Distill Lektion 3 of `Kursbuch.pdf` and the matching Arbeitsbuch pages."*
- *"Do lessons 1–6 the same way and build the study app with audio."*
- *"Make MP3 listening episodes for all finished lessons."*

The assistant inspects the pages, writes the lesson data, validates it with the bundled scripts and renders the sheet. Everything lands in a `<book> - Digested` folder next to your source, and earlier versions are kept.

The scripts also run on their own. That's useful for rebuilding the app after you edit a lesson file:

```bash
python skills/distill-lesson/scripts/study_pack.py render --inventory … --lesson … --review … --source … --output L01_Studysheet_v2.html
python skills/distill-lesson/scripts/course_audio.py plan --course _work/course.json
python skills/distill-lesson/scripts/build_course_app.py --course _work/course.json --output Course_App_v2.html
```

The skill's [references](skills/distill-lesson/references/) document the data format, the audio rules and the app.

## Privacy and copyright

- **Your own books only.** Use the skill with material you own or are licensed to use. The sheets and the app are for your own study; don't publish a commercial book's content.
- **Everything stays local**, except audio. Speech is generated with Microsoft's neural voices through `edge-tts`, which sends the selected sentences to that service. The skill asks before it does that, and you can always build without audio (`--no-audio`).
- **Progress stays on your device.** The app has no account and no tracking. Your progress lives in your phone's browser, and the backup button moves it between devices.

## Good to know

- **Language:** built and tested for German course books, with B1-level material in mind.
- **iPhone:** the Files and messenger previews don't run the app's buttons. Open the file in a browser that runs local files, or host it privately. The MP3s play everywhere.
- **A study aid, not a guarantee.** A digest replaces rereading, not practice. Listening to real-speed German, speaking with a partner and timed exam practice are still on you.

## Repository layout

```text
skills/distill-lesson/SKILL.md         the skill: workflow and quality rules
skills/distill-lesson/references/      authoring rules, data contract, audio and app design
skills/distill-lesson/scripts/         validator, renderer, speech, audio and app builders, tests
examples/sample-course/                two original sample lessons, their sheets and the app
.claude-plugin/                        Claude Code plugin and marketplace entry
```

Run the tests with `python -m unittest` inside `scripts/`. The speech tests need `pyspellchecker` and are skipped without it.

## License

[MIT](LICENSE)
