# Compact three-section visual system

Use the full style block in `master-template.html` for newly generated sheets in one batch. The page is local, self-contained, dark, readable on mobile and visually close to the earlier v3 density.

## Stable meanings

- coloured article text: noun gender, without a separate legend;
- yellow `mark`: the primary example target;
- purple card: grammar;
- green card: reusable Redemittel;
- blue-grey inset: example plus English translation.

Text and card shape must carry meaning without colour.

## Required restraint

- A small header identifies book/level, lesson and topic.
- Render only Wortschatz, Grammatik and Redemittel.
- Use short semantic group headings; no Core/Later hierarchy.
- No navigation, goal box, Start route, legend, status banner, media warning, summary, culture box, exercise or footer.
- No accordions, tabs, filters, hidden cards or “show more.”
- No gamification, progress, streaks, timers, motivational slogans or decorative character imagery.
- No external CSS, JavaScript, fonts or network assets.
- Keep examples readable, spacing consistent and `prefers-reduced-motion` respected.

For requested embedded audio, use one restrained header play/pause button and small speaker buttons beside playable German text. Audio controls must not cover text, create a new section, or turn every explanatory English line into visible UI. Use inline JavaScript and embedded audio data only; playback must still work when the HTML is opened offline.

Status belongs in machine metadata and the delivery message, not visible HTML. IDs may exist as implementation hooks but must not be printed as content.

## Browser check

When a local Chromium browser is available, run `node scripts/inspect_html.mjs BROWSER_EXE SHEET.html NEW_QA_DIRECTORY`. It checks desktop/mobile overflow, hidden cards, section order and examples, and saves screenshots. Inspect the screenshots. This is layout evidence, not language or source review.
