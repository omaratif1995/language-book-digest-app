# Anki CSV format

Create this only when the user asks for Anki or CSV. It is an export of the structured lesson data, not a separately authored deck.

## File shape

One `L<NN>_Flashcards.csv` per lesson, UTF-8:

```text
Front;Back;Tags
```

- Semicolon-delimited: German content commonly contains commas.
- Exactly three fields per row. No literal semicolon may appear inside `Front`, `Back`, or `Tags`; use ` · ` or a line break instead.
- Keep simple HTML such as `<br>` and `<i>` in fields; Anki renders it. Avoid HTML entities because their semicolon can corrupt a naive semicolon split.
- Preserve the same exact marked teaching target and example used in the sheet where practical.

## Recall directions

| Card type | Front | Back |
|---|---|---|
| noun | `das Geschirr` | gloss + one useful example |
| verb | infinitive or required prompt | gloss + marked/useful example |
| grammar | the decision, for example `Word order after denn?` | rule + one worked example |
| Redemittel — live phrase | communicative job, for example `Welcome a guest` | phrase + example |
| Redemittel — context frame | task goal, for example `Give a reason in a message` | reusable frame + example |

Do not create a front that merely asks the learner to reread a fact. The direction must resemble the choice they will make while speaking, writing, reading, or listening.

## Tags

Use `L<NN>` plus a category and tier:

- `vocab-<group>` or `verben`
- `grammar`
- `redemittel`
- optional context: `writing`, `reading`, `listening`, `speaking`, `culture`, or `classroom`
- `core` or `later`

Example: `L13 vocab-essen core`.

## Validate

```python
import collections
rows = open("L13_Flashcards.csv", encoding="utf-8").read().splitlines()
print("malformed rows:", [r for r in rows if r.count(";") != 2][:3] or "none")
print(collections.Counter(r.rsplit(";", 1)[-1] for r in rows[1:]))   # cards per tag
```

Manually inspect the source line count as well: quoted CSV fields are intentionally not used, so every non-header row must contain exactly two semicolons. Confirm every intended sheet card is represented once and no semicolon slipped into German or HTML content.
