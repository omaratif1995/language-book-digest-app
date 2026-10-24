# Self-contained lesson audio

Use this mode only when the user requests audio. It extends the compact three-section sheet; it does not change the lesson selection or add a fourth section.

## Required result

- Generate natural Standard German neural speech ahead of time. Do not use `speechSynthesis`: installed browser voices vary and may sound poor.
- Embed every audio payload in the HTML as a `data:audio/mpeg;base64,...` URL. Do not link to local MP3 files, CDNs or hosted audio.
- Put one compact whole-lesson play/pause control in the header.
- Put a small speaker control beside each vocabulary headword, German example, grammar example, Redemittel frame and useful German variant.
- Keep normal speaking speed unless the user asks otherwise.
- Make the whole-lesson mode reuse the same embedded clips. It may narrate concise English glosses and explanations between German learning strings, but should not duplicate audio bytes.
- Keep playback sequential and predictable. Starting an individual clip stops whole-lesson playback; starting the whole lesson stops any individual clip. After completion, pressing the whole-lesson control restarts from the beginning.

The whole-lesson sequence should cover the meaningful visible sheet in reading order: title, the three section names, vocabulary headwords/forms/glosses/examples, grammar meaning/rule/patterns/examples/relevant contrast, and Redemittel groups/frames/glosses/use cues/variants/examples. Normalise visual notation such as `…`, `+` and abbreviations into speakable text where needed; do not make the voice read HTML punctuation mechanically.

## Voice and privacy

Prefer a clear neural voice intended for Standard German. A multilingual neural voice is useful when one continuous listening sequence alternates German and English. Keep the provider and voice configurable; do not imply the skill owns or guarantees a third-party service.

Hosted synthesis sends the selected learner text to the provider. Obtain explicit user approval for that transmission before generating audio. Cache generated clips only under `_work` or `_skill_test`, never beside the learner HTML. The delivered HTML must work without the cache and without a network connection.

## Bundled helper

`scripts/embed_audio.py` synthesizes a reviewed lesson's audio, embeds it in a newly named HTML copy, and adds both control types:

```powershell
py -3 <skill-dir>/scripts/embed_audio.py --lesson L24_Lesson_v2.json --input L24_Studysheet.html --output L24_Studysheet_AudioTest.html --cache-dir _work/audio/L24 --voice de-DE-SeraphinaMultilingualNeural
```

The helper requires the `edge-tts` Python package and network access during generation. The resulting HTML does not. Never overwrite the input. Run the ordinary strict HTML validator and browser inspection on the output, then test real playback with `node scripts/inspect_audio.mjs BROWSER_EXE AUDIO_SHEET.html`.

For several units at once, the shared clip cache, spoken grammar explanations and MP3 listening episodes, use `course_audio.py` and `build_course_app.py` instead; see [course-app.md](course-app.md). Both tools use the same clip ids, so one cache serves sheets, app and episodes.
