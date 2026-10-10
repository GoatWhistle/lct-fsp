---
name: pitch-deck
description: Plan and build the defense or pitch deck — criteria-weighted outline, a card per slide in plan.md, the default slide order, kickoff, checkpoint and no-speaker variants, then the HTML slides in src/slides. Use when asked to make, plan, restructure or rewrite a presentation, pitch or slides — «сделай презентацию», «питч», «структура презентации», «слайды для защиты», «дека», «стартовый питч», «чекпоинт», "pitch deck", "defense slides".
---

# Pitch deck

The procedure from evidence to slides. The rules every slide obeys (titles, numbers, filler words,
visual system, final slide) live in [AGENTS.md](../../../AGENTS.md); this skill does not repeat them.

## 1. Frame

Read `context/PLATFORM.md`, `context/requirements.md`, `context/TASK.md`,
`docs/for-jury.md` and `evidence.md`. Fill `plan.md` §1 Regulation and §2 Criteria.

The deck language is the one the user asks for; write it into §1 and set `<html lang>` in
`src/shell.html`. Run skill `deck-design-sync` once the product has tokens.

Done when: talk and Q&A minutes, format, who switches slides and the deck language are filled;
every criterion has its weight; every organizer memo item is a row in §6. Unknowns are questions in
`context/open-questions.md`, not guesses.

## 2. Variant

- Defense or final pitch: continue here.
- Kickoff pitch, checkpoint, international or no-speaker deck, 3-minute slot:
  [variants.md](variants.md), then come back to step 3.

## 3. End-to-end example

Pick one real input the product handles today: real data, a result checked by hand, reproducible
on the demo stand. Prefer a typical case over an impressive edge case that fails one run in three.
Fill `plan.md` §3.

Done when: the example has a source, a hand check (who, when, verdict) and a slot on slides 2, 4
and 7 of the default order.

## 4. Slides and time by weight

Regulation 6:00 by default (`data-duration` in `src/shell.html`): 5:40 of speech plus a 20 s
reserve over twelve slides, 15–40 s each. Give each criterion slides and seconds
roughly proportional to its weight; a criterion of 25% or more gets its own slide with direct
proof. Twelve main slides by default; the template ships them in `src/slides/` in this order.
Replace a template slide whose job carries no weight with another proof of a heavy criterion
rather than dropping below twelve:

| # | Template | Job |
| --- | --- | --- |
| 1 | `01-cover` | Animated logo, product name, team name, the promise in one line (skill `deck-cover-final`) |
| 2 | `02-problem` | The example failing today, one sourced number for cost or scale |
| 3 | `03-solution` | Input to output on one trace, the key mechanic highlighted |
| 4 | `04-product` | The example going through the real product: live demo or real screens with callouts |
| 5 | `05-mechanic` | The mechanism behind the heaviest criterion as a living diagram |
| 6 | `06-funnel` | The second mechanism (selection, ranking, matching) or another proof of a heavy criterion |
| 7 | `07-explain` | Why this result for the example: reasons, sources, what is unknown, where a human decides |
| 8 | `08-measured` | Method in one line, baseline versus ours, the boundary where it fails |
| 9 | `09-architecture` | Only what explains quality or constraints: offline, data stays, replaceable parts |
| 10 | `10-impact` | Before and after for the user in one metric; who pays, if business is judged (skill `competitors`) |
| 11 | `11-status` | Done, in progress, next: three columns, no percentages, statuses from `evidence.md` |
| 12 | `12-final` | Logo and name visualization, «Готовы к вашим вопросам», animated QR to the solution and the code |
| A1… | appendices | Details for questions: metric tables, data, limitations, extra screens |

Fill `plan.md` §2 (criterion → slides, seconds) and §4 (slide list with cumulative time).

Done when: every criterion with a weight maps to a slide; the cumulative time fits the budget.

## 5. Cards

Write a card for every slide in `plan.md` §5 using [slide-card.md](slide-card.md). Gaps get a
marker in TODO, never an invented value.

Done when: every field of every card is filled or carries a marker; every number on a card is a
`numbers.json` key backed by an `evidence.md` row; open markers are listed in §7 with an owner.

## 6. Slides

For each card:

1. Start from the template slide in the same position; for a new kind of slide copy the closest
   one to `src/slides/NN-id/` and rename the section `id`.
2. Title and on-slide text from the card, in the deck language; numbers through `data-num`, the
   source line through `data-source` where the jury reads without a speaker. Slide text is for
   the eye and never the speech: the speaker does not read it.
3. The visual: the product's own components and tokens, replacing the template's generic
   diagram with the real mechanism; motion per skill `deck-motion`, every element animated.
4. `notes.js`: `time` from the card, 2–4 cue lines from "Speaker says", caveats from `[HONEST]`.
5. Check it live with `npm run dev`.

Done when: `npm run build` passes, `npm run shots` reports no console errors and no overflow, and
every slide's last step reads correctly with the sound off.

## 7. Hand-off

The speech is written in the same pass, never later: skill `speaker-script`, then
`npm run speech:sync` and `npm run speech:check` with 0 errors. Demo: `demo-runbook`. Questions: `jury-qa`. Before the first full
rehearsal and again before the defense: `deck-audit`, then `npm run build:final` and `npm run pdf`.
