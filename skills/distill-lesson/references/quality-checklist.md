# Review before delivery

Mechanical validation is necessary but not a pedagogical review. Review the complete source and the concise sheet in both directions.

## Seven semantic checks

1. **Source inspection.** Every relevant page/region, picture vocabulary, margin rule, reference box, model text and productive-task language was inspected. Missing media stays internally recorded.
2. **Selection quality.** Essential taught material has a standalone home. Supporting material is embedded only when natural. Incidental facts/instructions do not become cards. Every displayed item materially earns its space.
3. **Vocabulary quality.** Selected nouns have correct article and useful plural information; verbs retain important reflexive/separable/complement patterns. Every example is natural, translated and source-relevant. Coherent small word fields remain coherent.
4. **Grammar accuracy.** Every explicitly taught concept and important small rule is present. Meaning, formation, pattern, examples and relevant contrast are correct and compact; no reference-chapter expansion.
5. **Redemittel value.** Reusable frames were extracted from model texts and tasks as well as labelled boxes, especially for writing. Placeholders, function and relevant register are preserved without copying full texts.
6. **Example integration.** Embedded source value appears in the declared home, sounds natural, is translated and does not compete with the primary target. Examples increase coverage without becoming dense artificial sentences.
7. **Compression.** Source → sheet loses no essential learning; sheet → source contains no filler, duplicated explanation, giant inventory or unnecessary category. The result feels closer to v3 density than v5.1 encyclopedic output.

Record concrete findings in the internal review JSON. A check is not a count. Resolve selection errors in the inventory first and teaching errors in lesson data, then refresh hashes/review.

## Rendered HTML

- Exactly three `h2` headings: Wortschatz, Grammatik, Redemittel, in order.
- No learner-facing audit/status/coverage/media text or meta-learning panels.
- No Start route, practice, quiz, summary, legend, Later or hidden content.
- Every selected vocabulary/phrase card has a marked example; every grammar rule has at least two.
- No vocabulary table used to squeeze example-free items.
- Open desktop/mobile views and check readability/overflow when possible.
- Preserve prior versions and use a new filename.

When audio was requested, also check that:

- the HTML contains no external media URL and plays after the source files/cache are removed;
- every visible speaker button resolves to non-empty embedded audio;
- the whole-lesson control traverses the complete listening sequence and can pause/resume/restart;
- German targets and examples use a clear Standard German neural voice at normal speed; and
- audio controls do not add another `h2`, hide content, overlap text or cause mobile overflow.

Run the bundled tests and HTML validator. Their pass proves structure and record consistency, not German quality or good selection.
