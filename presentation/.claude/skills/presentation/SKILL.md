---
name: presentation
description: Make or update the defense presentation together with its 6-minute speech, from whatever the user gives — a slide structure, a ready text or speech, a rough idea or vibe, or a change to an existing deck — keeping deck and speech in sync. Use whenever the user asks for a presentation, deck, pitch or speech, sends a structure or text for slides, or asks to change slides — «презентация», «преза», «сделай презу», «вот структура», «вот текст», «по вайбу», «поменяй слайд», «добавь слайд», "make the deck".
---

# Presentation

The deck (`src/slides`) and the speech (`SPEECH.md`) are one artifact. Whatever the input, the
output is both, in sync, in the deck language, at the regulation (6:00 by default). Rules for
slides: [AGENTS.md](../../../AGENTS.md).

## 1. Read the input

| The user gave | Treat it as |
| --- | --- |
| A structure: list of slides, theses or sections | The outline. Map each item onto the 12 template slots in `plan.md` §4; extra items become appendices or merge; missing slots are filled from `context/` and `docs/` |
| A ready text: speech, article, notes | The speech. Split it into beats of 25–45 s; each beat becomes a slide with its thesis and visual; the user's wording stays in `SPEECH.md`, trimmed to the budget |
| A rough idea or "по вайбу" | A brief. Draft the thesis, the end-to-end example and a 12-slide outline from `context/`, `docs/` and the product; show the outline in one message, then build without waiting unless a fact is missing |
| A change: edit, add, remove, reorder slides | An update. Change the slides, then the affected speech sections in the same turn (step 5) |
| Nothing new, "проверь презу" | An audit: skill `deck-audit` |

Missing facts (numbers, links, team name) become `[N]` markers or `{{placeholders}}`, listed at the
end; never invented. The deck language is the one the user asks for; ask only if the request and
`context/PLATFORM.md` both leave it open.

## 2. Plan

`plan.md`: regulation, criteria and weights, the end-to-end example, the slide list with seconds,
a card per slide (skill `pitch-deck`, steps 1–5). For a text input, the cards come from the beats.

## 3. Slides

Build or change the slides (skill `pitch-deck` step 6): cover and final per `deck-cover-final`,
motion per `deck-motion`, the product's look per `deck-design-sync`, charts per
`storytelling-with-data`. `npm run build` and `npm run shots`; look at the shots.

## 4. Speech

Write or rewrite the sections (skill `speaker-script`, the words per `pitch-craft`): about 6
minutes, the speaker never reads the slide, numbers as words, «Готовы к вашим вопросам» at the end.
For a text input, keep the user's sentences where they fit the beat and the clock.

## 5. Sync

```bash
npm run speech:init
npm run speech:check
npm run speech:sync
npm run speech:check
```

`init` adds sections for new slides, `check` names every stale or mismatched section, `sync`
records the timings and slide fingerprints. A change to any slide is not done until `speech:check`
shows 0 errors.

## 6. Report

One short message: what was built or changed (slides by number), the speech total against the
regulation, open markers with what is needed to close them, and the commands to view it
(`npm run dev`, `npm run pdf`).

Done when: `npm run build` passes, `speech:check` has 0 errors, the shots were looked at, and the
open markers are listed.
