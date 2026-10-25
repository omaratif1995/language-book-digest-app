# Course study app and listening episodes

Use this when several units have reviewed sheets and the learner wants to study on the phone, listen on the go or practise with flashcards. Both deliverables are rendered from the same reviewed lesson records and sheets. They never change the three-section sheets.

## course.json

Write one `course.json` (usually in `_work/`). Paths are relative to the file.

```json
{
  "title": "Mein Kursbuch B1.1",
  "subtitle": "Lektion 1–12 · Wortschatz · Grammatik · Redemittel",
  "narration": "narration.json",
  "voices": {"de": "de-DE-KatjaNeural", "en": "en-US-AvaNeural"},
  "cache": "audio",
  "episodes_dir": "../Audio",
  "new_per_day": 20,
  "units": [
    {"id": "L01", "label": "Lektion 1", "lesson": "L01/L01_Lesson_v2.json", "sheet": "../L01_Studysheet_v2.html"}
  ]
}
```

List units in course order. Use the newest reviewed sheet of each unit; drafts are refused. `new_per_day` sets the trainer's default for new cards per day (20 suits most learners; 25 suits a near exam date). `voices` and `narration` are optional; the voices shown are the defaults.

## Pronunciation: German is always spoken by a German voice

Multilingual neural voices guess the language of each request, and the Edge service marks every request as American English. Short German words inside English ("als", "rund", "total") then come out with English pronunciation. `scripts/speech.py` therefore never asks one voice to speak both languages:

- German text (headwords, examples, frames, variants) goes to the German voice in one piece.
- English text (glosses, use cues, explanations) is split into language runs, and German words inside it go to the German voice. Detection uses:
  - word lists, plus the German and English `pyspellchecker` dictionaries and their word frequencies;
  - capitalisation, and an article before a capitalised word (`die Babysitter`);
  - hyphenated compounds (`S-Bahn`);
  - the neighbouring words.

  It also reads course-book notation: `A:` and `CH:` (Austrian and Swiss variants), `etw.`, `jdn.`, `(e)`, `→` and `…sten`.
- Forms lines (`abschließen = to complete`) are German notes; the side right of `=` is read as an English gloss.
- Each run is synthesized on its own. The clip trims each run's built-in silence and pauses by punctuation, so it sounds like one speaker.

Before synthesizing, read the `plan` output and spot-check `<cache>/plan.json`, where `texts` shows every clip as `[de] …` and `[en] …` runs. Fix a mis-split note in the lesson data, not in the audio.

## Spoken grammar explanations (narration.json)

Without narration, `🔊 Erklärung` reads the grammar card itself: title, meaning, rule, patterns and contrast. That is correct, but it sounds like a list. For natural audio, write `narration.json` next to `course.json`, keyed by unit id and grammar id:

```json
{"L01": {"g01": "Use «als» for one single moment in the past, or for one period of your life. For example: «Als ich ein Kind war, hatten wir einen Hund.» After «als», the verb goes to the very end …"}}
```

Write each point as a short spoken explanation:

- **Length and order:** 50–110 words of plain, conversational English, in this order: what it is for, the rule, one or two examples, the usual trap.
- **Marks:** mark every German word, phrase or sentence with «…». Marked text goes to the German voice and nothing is guessed.
- **No symbols:** leave out `+`, `→` and `/`, and isolated endings. Show German through short phrases (say «am größten», not "-sten").
- **No wrong German aloud:** describe the mistake instead of saying it, because learners copy what they hear.

`plan` refuses narration for unknown unit or grammar ids, and lists unmarked words that look German.

## Audio commands

`course_audio.py plan` works offline. It writes `<cache>/plan.json` with each unit's listening order, the German controls (headwords, examples, phrases, variants), the grammar explanation chain and the episode announcement, and reports how many clips are not yet in `<cache>/clips`. Clip ids depend on the voices, the spoken runs and their pauses. Unchanged clips are never synthesized twice, and runs shared by several clips are fetched once.

`course_audio.py synth --confirm-external-tts` sends the missing texts to the Edge TTS service. Ask first and say what is sent: the example sentences, glosses and explanations of the selected units, nothing else.

`course_audio.py episodes` builds one MP3 per unit in `episodes_dir`, in the sheet's listening order:

- vocabulary: headword, English meaning, forms, German example, English translation;
- grammar: the spoken explanation, then its examples;
- Redemittel: frame, use and examples.

After every German item there is a pause about as long as the clip, so the learner can repeat it aloud (shadowing). Expect roughly 15–30 minutes per unit.

Requirements: `pip install edge-tts pyspellchecker imageio-ffmpeg` (or a system ffmpeg).

## App

`build_course_app.py --course course.json --output <Name>_Studienpaket_vN.html` (or `--no-audio`).

**Lernen**
- All reviewed sheets in course order, a unit picker with ‹ ›, and a search over all cards.
- 🔊 on every German headword, example, phrase and variant.
- `🔊 Erklärung` on each grammar point plays its spoken explanation.
- `▶ Ganze Lektion anhören` plays a guided session. German vocabulary and expressions come with pauses to repeat. Grammar is explained, followed by its German examples. The current card is highlighted and scrolled into view.

**Üben**
- One card per sheet card. Vocabulary goes German → English, with English → German optional. Grammar shows its title and asks for the rule and examples. Redemittel show the situation and meaning in English and ask for the German frame, because that is the choice the learner makes while speaking or writing.
- A card takes one tap, and ✓ Gewusst and ✗ Nochmal are visible from the start:
  - **✓** (or swipe right, →, 2): known, and the next card appears. The answer of the card just passed stays below for a few seconds with "Rückgängig" (or Backspace), in case the learner was wrong.
  - **✗** (or swipe left, ←, 1): the answer opens, and "Weiter ›" (or a swipe, or Enter) moves on.
  - **Tapping the card** (or Space) only peeks at the answer.
- A double tap never grades the next card.
- Rounds of 10 cards with a short break screen. A daily summary offers "+10 neue Karten". The progress bar and streak survive reloads.
- Schedule: new cards in course order up to the daily limit, interleaved with due reviews. "Gewusst" moves a card through the intervals 1 → 3 → 7 → 14 → 30 → 60 days. "Nochmal" brings it back after three cards and restarts its interval.
- Settings live in a closed panel: units, parts, direction, new cards per day, round size, browse mode, sound and a progress backup file.

## Size and performance

German clips are embedded at 32 kbit/s and the English explanations at 24 kbit/s. They sit in per-unit text blocks after the app script, so the app becomes usable before the audio has finished loading, and a unit's sounds are unpacked on first use. A 16-unit course is about 40 MB.

Measured with headless Chrome at 4× CPU slowdown on a 41 MB, 16-unit course: usable after about 3 s, fully loaded after 5–7 s. On a desktop it is about 1 s. For quick sharing or old phones, also build a `--no-audio` copy (about 2 MB) and hand over the MP3 episodes.

## Delivery notes

- **Sending it:** messengers and cloud drives handle the file; most mail servers reject 40 MB.
- **Android:** opens the file in Chrome with everything working.
- **iPhone:** the Files and messenger preview shows the text but runs no JavaScript, so audio and practice need a hosted link.
- **MP3 episodes:** play everywhere.
- **Progress:** stays in one browser on one device. The backup button moves it between devices.

## Verify before delivery

1. Run the unit tests (`python -m unittest` in `scripts/`; the speech tests need `pyspellchecker`).
2. Open the app in a phone-sized browser at 360–430 px wide and check there is no horizontal scroll.
3. Check the practice flow:
   - ✓ moves on and offers undo, ✗ opens the answer, and a tap only peeks;
   - swipes grade in both directions;
   - the round break and the daily summary appear;
   - progress survives a reload.
4. Check that at least one clip, one grammar explanation and the start of a guided unit really play. Listen to one mixed clip: the German words in it must sound German.
5. Fully decode one MP3 episode with ffmpeg, so that `-v error` prints nothing.
