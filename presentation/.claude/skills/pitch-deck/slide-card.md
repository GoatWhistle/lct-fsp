# Slide card

One card per slide in `plan.md` §5. The card is the source for the slide, the speech and the
audit, so every field is either filled or marked.

## Fields

| Field | What goes in |
| --- | --- |
| Goal | What the jury knows after this slide that it did not know before. One sentence |
| Criterion (weight) | The judging criterion this slide earns points on, with its weight |
| Title | The thesis in two halves, exact text in the defense language; the second half is accented |
| On-slide text | Exact text beyond the title, about 25 words at most; numbers as `numbers.json` keys |
| Visual | The one living visualization: what is drawn, what moves, what the last step shows |
| Speaker says | The spoken text, exact, in the defense language. Goes to `SPEECH.md` |
| Key sentence | The one sentence the jury should repeat in deliberation |
| What to prove | The evidence that must exist: `evidence.md` row, `numbers.json` key, screen or file |
| TODO | Open work, each line starting with a marker |

## Markers

| Marker | Meaning | Rule |
| --- | --- | --- |
| `[NEED SCREENSHOT]` | A real screen is missing | Name the screen, state and data |
| `[NEED TO MEASURE]` | A number is not measured yet | Until measured, the phrase is cut from slide and speech |
| `[NEED TO CHECK]` | A fact is not confirmed on the current version | Check on the stand, then record in `evidence.md` |
| `[HONEST]` | A limitation the speaker says aloud | Goes to the slide or `notes.js` caveats |
| `[DO NOT SHOW]` | True but misleading without context | Kept for Q&A with a prepared answer in `QA.md` |

`npm run build:final` fails while any marker or `{{placeholder}}` remains on a slide or in notes.

## Example card

A generic product that extracts fields from scanned invoices. Values are illustrative; on a real
deck every number is a `numbers.json` key.

### 8. Measured

- **Goal:** extraction quality was measured on invoices the model never saw, and the weak spot is known.
- **Criterion (weight):** Quality of results (30).
- **Title:** «Поля счёта извлекаются точнее шаблонов, *кроме рукописных правок*»
- **On-slide text:** method line «Отложенные счета, разбиение по поставщикам»; bars `baseline_f1`
  and `ours_f1`; boundary «Граница: рукописные исправления» with `handwritten_f1`.
- **Visual:** two bars grow to measured values; step 1 adds the boundary box under them.
- **Speaker says:** «Проверяли на счетах поставщиков, которых модель не видела. Шаблоны дают
  `baseline_f1`, мы `ours_f1`. [→] Слабое место видим сами: рукописные правки, там `handwritten_f1`.»
- **Key sentence:** quality is measured on unseen suppliers, and the boundary is named.
- **What to prove:** `evidence.md` rows for all three keys with sample size, split and date;
  the evaluation command reproduces the numbers.
- **TODO:**
  - `[NEED TO MEASURE]` `handwritten_f1` on at least 50 invoices with handwritten corrections.
  - `[HONEST]` the test set comes from one region.
  - `[DO NOT SHOW]` exact-match accuracy without explanation: it counts a missing comma as an error.
