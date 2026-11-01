# Writing the Geschichte

The Geschichte is the last section of every sheet: one short, catchy text that puts the whole lesson back into a living context. The learner reads it, listens to it sentence by sentence or straight through, and meets the new words, grammar and phrases again where they belong. It is the reward at the end of the lesson and its listening exercise.

## What makes it stick

- **A small story with a pull.** Someone wants something, something gets in the way, there is a turn and a small payoff: a joke, a surprise, a warm ending. A list of events with lesson words in it is not a story.
- **A recurring cast.** For a course, give the stories two to four recurring characters, for example a flat-share in Leipzig: a nurse, a software tester, their landlady and her dog. Each unit is the next episode. Keep a short `_work/story_bible.md` with names, jobs, relationships, running jokes and what has happened so far. People want to read the next episode, and earlier vocabulary comes back for free.
- **Adult everyday life** that fits the lesson's topic: work, the flat, friends, appointments, offices, travel, health, studies.
- **Some direct speech.** Dialogue, a chat message, an e-mail or a phone call is where the Redemittel live.
- **Specific detail.** A time, a place, a number, a smell, a feeling. Concrete images are what memory keeps.

## Coverage without stuffing

- Use **at least 80 % of the vocabulary cards**; the validator blocks a story below 60 %.
- Use **every grammar point at least twice**; the validator blocks a story that misses one.
- Use **at least half of the Redemittel**, in situations where a person would really say them.
- Spread the lesson's items: one or two per sentence, never a sentence built only to hold three new words. If an item cannot appear naturally, leave it out; its card still teaches it.
- Use the forms the lesson teaches: the Genitiv after *trotz*, the relative pronoun after a preposition, the Konjunktiv II in a polite request.

## Level and length

- Four to seven paragraphs, 250–600 words: one sitting, two to four minutes of audio.
- One step easier than the lesson's hardest text. Most sentences have 6–14 words. Words outside the lesson stay common.
- Present tense and Perfekt carry most stories. Use the Präteritum for narration only when the lesson teaches it, or for *sein*, *haben* and the modal verbs.

## Audio-friendly writing

The story is spoken by the target language's voice (German: a German voice), one clip per sentence.

- Write numbers, times and abbreviations the way they are spoken when a voice could stumble: *zum Beispiel*, not *z. B.*
- Avoid brackets, slashes, arrows and symbols.
- Use German quotation marks „…“. A sentence may end inside them: „Kommst du mit?“ Sie lacht.

## Originality

Never retell the source: no characters, names, places, plots, statistics or sentences from the book, the slides or the teacher's texts. A Redemittel frame may appear as it is, but what follows it is yours: not *Könnten Sie bitte einen Handwerker schicken?* when the model e-mail says exactly that. Run the validator with the source text; it reports any six-word run the story shares with the source. The story is newly written for the learner, so the sheet can stand on its own.

## Data

In the lesson JSON:

```json
"story": {
  "title": "Der Drucker hasst mich",
  "paragraphs": [
    {"de": "Ein Kollege mit einer riesigen Tasse Kaffee kommt auf mich zu. „Darf ich mich kurz vorstellen?“",
     "en": "A colleague with a huge cup of coffee comes up to me. 'May I briefly introduce myself?'",
     "uses": [{"card": "v1", "form": "Kollege"}, {"card": "e1", "form": "Darf ich mich kurz vorstellen"}]}
  ]
}
```

- `title`: catchy, two to six words, never "Lektion 3".
- `en`: a faithful, natural translation of the paragraph. The sheet folds it under *Übersetzung*, so it is there to check understanding, not to read first.
- `uses`: every lesson card the paragraph realizes, with the exact `form` as it appears in the text (inflected as it stands). Vocabulary and Redemittel forms are underlined on the sheet, at their first occurrence in the paragraph; tapping one in the app shows its meaning and speaks the word. Grammar forms are checked for coverage but not underlined.
- Underlined forms must not overlap. If a phrase contains a lesson word, mark the word in another sentence.

## Review

The review records `"story_quality": "pass"` only when the story:

1. reads as a real story, coherent and with a pull;
2. is natural, correct German at the learner's level;
3. meets the coverage above without stuffed sentences;
4. contains nothing taken from the source; and
5. has faithful translations.
