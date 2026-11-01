# Self-contained lesson audio

Use this mode only when the user requests audio for a single sheet. It extends the sheet; it does not change the lesson selection or add a section. For several units, build the course app instead ([course-app.md](course-app.md)); it has the same listening controls plus practice and games.

## Required result

- Generate natural neural speech in the target language ahead of time (German: Standard German). Do not use `speechSynthesis`: installed browser voices vary and may sound poor.
- Embed every audio payload in the HTML. Do not link to local MP3 files, CDNs or hosted audio.
- Put one compact **🎧 Anhören** control in the header. It opens a small panel: *Ganze Lektion*, *Nur Beispiele* and, with a story, *Geschichte*; how often each German sentence is played (1×, 2×, 3×, 5×); and whether the session stops or starts again at the end. Once a session was stopped, the panel's first button, *▶ Weiter*, goes on where it stopped. Settings changed during a session apply at once.
- Put a small speaker control beside each vocabulary headword, German example, grammar title, Redemittel frame and useful German variant, a **🔊 Ganze Geschichte** button on the story header, and a speaker control beside each story paragraph. A tap on a story sentence plays that sentence.
- **A tap repeats.** A speaker control plays its clip again and again, with a short pause, until the learner taps it again (the panel can set 1× or 3× instead). Learners use this to hear a sentence until it sticks.
- Keep normal speaking speed unless the user asks otherwise.
- **Pauses separate without dragging.** Before the same sentence again: about 0.8 s after a word and 1.35 s after a sentence. Before the next sentence a little more: about 1.5–2 s after an example, less after headwords, section names and story sentences, more at the end of a paragraph. The pauses are measured from the voice: each clip's own lead-in and tail (about a second at every join) are trimmed when the track is built. (The MP3 episodes keep longer pauses, to repeat aloud.)
- Keep playback predictable and uninterrupted when the screen turns off. Each run is joined on the device into one continuous audio track with lock-screen and headphone controls (⏯ ⏮ ⏭). A bar at the bottom shows what is playing. During a session it has ⏮ (this sentence again; right at its start, the one before), ⏸ / ▶ (pause, then go on in the same sentence), ⏭ (the next sentence now) and ✕ (end). A speaker tap during a session pauses the session and plays that clip; when the clip stops, the session waits, paused, in the bar. Starting a session stops any clip.

The whole-lesson sequence covers the meaningful visible sheet in reading order: title, the section names, vocabulary headwords and examples, grammar explanations and examples, Redemittel frames, variants and examples, then the story read straight through. Normalise visual notation such as `…`, `+` and abbreviations into speakable text where needed; do not make the voice read HTML punctuation mechanically.

## Voice and privacy

Use two single-language neural voices: one for the target language and an English voice for English (defaults: the profile's voice, German `de-DE-KatjaNeural`, and `en-US-AvaNeural`). Do not give mixed text to one multilingual voice. It guesses the language of each request and reads short German words inside English with English pronunciation. `scripts/speech.py` splits mixed text into German and English runs, speaks each with its own voice and joins them with natural pauses (see [course-app.md](course-app.md)). Keep the provider and voices configurable; do not imply the skill owns or guarantees a third-party service.

Hosted synthesis sends the selected learner text to the provider. Obtain explicit user approval for that transmission before generating audio. Cache generated clips only under `_work` or `_skill_test`, never beside the learner HTML. The delivered HTML must work without the cache and without a network connection.

## Bundled helper

`scripts/embed_audio.py` synthesizes a reviewed lesson's audio, embeds it in a newly named HTML copy, and adds the controls:

```text
python <skill-dir>/scripts/embed_audio.py --lesson L24_Lesson_v2.json --input L24_Studysheet.html --output L24_Studysheet_AudioTest.html --cache-dir _work/audio/L24 --confirm-external-tts
```

`--voice-de` and `--voice-en` change the voices. The helper requires `edge-tts`, `pyspellchecker`, ffmpeg (`imageio-ffmpeg` provides one) and network access during generation. The resulting HTML does not. Never overwrite the input. Run the ordinary strict HTML validator and browser inspection on the output, then test real playback with `node scripts/inspect_audio.mjs BROWSER_EXE AUDIO_SHEET.html`.

For several units at once, the shared clip cache, spoken grammar explanations and MP3 listening episodes, use `course_audio.py` and `build_course_app.py` instead; see [course-app.md](course-app.md). Both tools use the same clip ids, so one cache serves sheets, app and episodes.
