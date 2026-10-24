# Course study app and listening episodes

Use this when several units have reviewed sheets and the learner wants to study on the phone, listen on the go or practise with flashcards. Both deliverables are rendered from the same reviewed lesson records and sheets. They never change the three-section sheets.

## course.json

Write one `course.json` (usually in `_work/`). Paths are relative to the file.

```json
{
  "title": "Mein Kursbuch B1.1",
  "subtitle": "Lektion 1–12 · Wortschatz · Grammatik · Redemittel",
  "voice": "de-DE-SeraphinaMultilingualNeural",
  "cache": "audio",
  "episodes_dir": "../Audio",
  "new_per_day": 20,
  "units": [
    {"id": "L01", "label": "Lektion 1", "lesson": "L01/L01_Lesson_v2.json", "sheet": "../L01_Studysheet_v2.html"}
  ]
}
```

List units in course order. Use the newest reviewed sheet of each unit; drafts are refused. `new_per_day` sets the trainer's default for new cards per day (20 suits most learners; 25 suits a near exam date).

## Audio

`course_audio.py plan` works offline. It writes `<cache>/plan.json` with each unit's narration order, the German controls (headwords, examples, phrases, variants) and the grammar explanation parts (title, meaning, rule, contrast), and reports how many clips are not yet in `<cache>/clips`. Clip ids depend only on voice and text, so unchanged sentences are never synthesized twice.

`course_audio.py synth --confirm-external-tts` sends the missing texts to the Edge TTS service. Ask first and say what is sent: the example sentences, glosses and explanations of the selected units, nothing else.

`course_audio.py episodes` builds one MP3 per unit in `episodes_dir`, in the sheet's listening order: headword, English meaning, forms, German example, English translation; grammar meaning, rule, patterns, examples; Redemittel frames, use and examples. After every German item there is a pause about as long as the clip, so the learner can repeat it aloud (shadowing). Expect roughly 15–30 minutes per unit.

## App

`build_course_app.py --course course.json --output <Name>_Studienpaket_vN.html` (or `--no-audio`).

**Lernen**
- All reviewed sheets in course order, a unit picker with ‹ ›, and a search over all cards.
- 🔊 on every German headword, example, phrase and variant.
- `🔊 Erklärung` on each grammar point plays its English explanation (title, meaning, rule, contrast).
- `▶ Ganze Lektion anhören` plays a guided session. German vocabulary and expressions come with pauses to repeat. Grammar is explained in English, followed by its German examples. The current card is highlighted and scrolled into view.

**Üben**
- One card per sheet card. Vocabulary goes German → English, with English → German optional. Grammar shows its title and asks for the rule and examples. Redemittel show the situation and meaning in English and ask for the German frame, because that is the choice the learner makes while speaking or writing.
- Tap the card to flip it. Then swipe right or tap ✓ Gewusst, or swipe left or tap ✗ Nochmal. "Überspringen ›" always moves on.
- Rounds of 10 cards with a short break screen. A daily summary offers "+10 neue Karten". The progress bar and streak survive reloads.
- Schedule: new cards in course order up to the daily limit, interleaved with due reviews. "Gewusst" moves a card through the intervals 1 → 3 → 7 → 14 → 30 → 60 days. "Nochmal" brings it back after three cards and restarts its interval.
- Settings live in a closed panel: units, parts, direction, new cards per day, round size, browse mode, sound and a progress backup file.

## Size and performance

German clips are embedded at 32 kbit/s and the English explanations at 24 kbit/s, as per-unit text blocks placed after the app script. The app becomes usable before the audio has finished loading, and a unit's sounds are unpacked on first use. A 16-unit course is about 40 MB.

Measured with headless Chrome at 4× CPU slowdown: usable after about 5 s, fully loaded after about 8 s. On a desktop it is about 1 s. For quick sharing or old phones, also build a `--no-audio` copy (about 2 MB) and hand over the MP3 episodes.

## Delivery notes

- **Sending it:** messengers and cloud drives handle the file; most mail servers reject 40 MB.
- **Android:** opens the file in Chrome with everything working.
- **iPhone:** the Files and messenger preview shows the text but runs no JavaScript, so audio and practice need a hosted link.
- **MP3 episodes:** play everywhere.
- **Progress:** stays in one browser on one device. The backup button moves it between devices.

## Verify before delivery

1. Run the unit tests (`python -m unittest` in `scripts/`).
2. Open the app in a phone-sized browser at 360–430 px wide and check there is no horizontal scroll.
3. Check the practice flow: flip, grade by button and by swipe, skip, the round break, the daily summary, and that progress survives a reload.
4. Check that at least one clip, one grammar explanation and the start of a guided unit really play.
5. Fully decode one MP3 episode with ffmpeg, so that `-v error` prints nothing.
