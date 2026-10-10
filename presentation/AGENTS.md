# Presentation rules

Everything for the defense lives here: the deck engine (`src/`, `tools/`), the working files
(`plan.md`, `SPEECH.md`, `QA.md`, `demo-runbook.md`, `evidence.md`) and the pitch skills in
`.claude/skills/`. Repo-wide rules in [../AGENTS.md](../AGENTS.md) apply too.

Language: everything an agent reads (this file, skills, the working files' headings and instructions)
is English. Everything the audience sees or hears (slide text, `notes.js`, spoken lines, on-screen
labels) is in the defense language from `../context/PLATFORM.md`, Russian by default. Code follows
the repo code rules: no comments, English identifiers, Cyrillic only in `src/locales/ru/`.

## Inputs

Read these before planning or changing any slide:

- `../context/TASK.md`: the task statement.
- `../context/PLATFORM.md`: the regulation (talk and Q&A minutes, on site or online, video limits,
  submission fields and character limits) and the organizer memo with mandatory slides.
- `../context/requirements.md`: judging criteria with weights. Slide time follows the weights.
- `../docs/for-jury.md`: what the jury must take away. The deck tells the same story.
- `evidence.md`: what is proven, how and when. A claim without a row there is not made.

Missing or ambiguous regulation goes to `../context/open-questions.md` as a question. Never guess
minutes, limits or criteria.

## Deck defaults

- **Deck and speech are one artifact.** Every deck comes with `SPEECH.md`, about 6 minutes (regulation
  `data-duration` 360 s in `src/shell.html`, speech 5:40 plus a 20 s reserve), one section per slide.
  Any change to a slide changes its section in the same turn; `npm run speech:check` must show 0
  errors before the work is reported. Input can be a structure, a ready text, a vibe or an edit:
  skill `presentation` routes all of them.
- **HTML only.** Every deck is built in this engine as one offline HTML file. If organizers demand
  a file, ship the PDF from `npm run pdf`; a mandated `.pptx` gets the slide images, the source of
  truth stays HTML.
- **Language** is the one the user asks for (default: `../context/PLATFORM.md`). Every slide text,
  `notes.js`, QR caption and `<html lang>` in `src/shell.html` use it; a language switch rewrites
  the texts, it never mixes two languages on a slide.
- **12 main slides** by default, the template ships them in order (skill `pitch-deck`). 10–13 only
  when the regulation forces it. Everything else goes to appendices after the final slide
  (`data-kind="appendix"`).
- **Harmony of text and visual.** One slide is one thesis plus one living visualization: a
  diagram, a flow, a chart or the product's own component, animated so it shows the mechanism.
  Text is captions to the visual, about 25 words beyond the title at most, no paragraphs, nothing
  under 20px. The visual carries the slide; text and picture never repeat each other.
- **The speaker never reads the slide.** Slide text is what the eye needs; the speech
  (`SPEECH.md`, `notes.js`) is what the ear needs, written separately. The speaker faces the room
  and glances at the slide only to point at the visual.
- **Only the slide on screen.** Content slides carry exactly two quiet marks: the product mark
  and name top left, the slide number (just `5`, never `5 / 12`) bottom right. The cover and the
  final slide have neither (`data-bare`). No progress bar, step dots, menu, toolbar, hint or notes
  overlay. Navigation is hotkeys and the clicker; notes and the timer live only in the separate
  presenter window (`S`). Do not add anything else on screen.
- **No fake icons or AI punctuation on slides**: no em dashes at all, no middle dots or pipes as
  separators, no arrow, check, cross or pointer characters (→ ✓ ✗ ▶), no emoji. Use inline lucide
  icons; flags from flag-icons, company logos from theSVG (skill `asset-sources`). The build fails on
  these characters in slide text, alt texts, deck strings and CSS `content`.
- **Everything is animated**: every slide has an entry choreography, the logo too, and nothing on
  a slide just appears. Motion follows the speech order (skill `deck-motion`).
- **The deck looks exactly like the product**: same tokens, fonts, radii, colors, icons, data
  components and logo (section below, skill `deck-design-sync`).
- The title is the thesis as one sentence in two halves, the second half accented:
  `<h2 class="title">{{claim}}, <em>{{what makes it true}}</em></h2>`. A topic label
  ("Архитектура", "Результаты") is not a title.
- Every figure on a slide comes from `src/data/numbers.json` with a source (see Numbers). An
  unmeasured figure is not claimed: the phrase is dropped from the slide and the speech, never
  softened to "about" or «примерно».
- Filler gets replaced by the measured fact or deleted: «уникальный», «высокая точность»,
  «масштабируется», «мощная платформа», «инновационный», «Добро пожаловать», and their English
  twins "unique", "high accuracy", "scalable", "powerful platform".
- One real end-to-end example, checked by hand, runs through the whole deck: the problem slide
  shows it failing today, the product slide processes it, the explainability slide explains it,
  the demo uses it.
- A limitation sits on the slide that makes the claim, in the same visual weight as the claim.
- No "Team" slide, except the kickoff pitch or when the organizer memo requires one.
- **Cover:** the animated logo (the mark assembles, the name appears letter by letter), the
  product name and the team name, then the one-line promise; the event in a quiet micro line.
  The animation acts out what the name means (skill `deck-cover-final`).
- **Final slide:** a striking visualization of the logo and the name, the line «Готовы к вашим
  вопросам» (or its equivalent in the deck language) and, on the same slide, QR codes to the live
  solution and the code that assemble with animation. Never «Спасибо за внимание» or "Thank you
  for your attention", no proof list here: the summary is slide 11.
- Mandatory items from the organizer memo are placed first; each one maps to a slide in `plan.md`.

## Visual system: the product 1:1

The deck is a continuation of the product, not a separate design.

- **Tokens.** `cd ../frontend && npm run tokens:export` writes `src/core/css/tokens.css`. That file
  is the contract: it is regenerated, never edited by hand, and no other deck CSS holds color,
  radius or easing literals. The single exception is the QR code, which stays black on white to scan.
- **Contract.** `tokens.css` declares the semantic layer twice, under `:root, [data-theme="light"]`
  and under `[data-theme="dark"]`. Plain attribute selectors, not `:root[data-theme]`, so one slide
  can switch theme with `data-theme="dark"`. Until the first export the file holds neutral
  placeholders with the same names.

  | Group | Variables the deck reads |
  | --- | --- |
  | Surfaces | `--surface-base`, `--surface-raised`, `--surface-sunken` |
  | Text | `--text-primary`, `--text-secondary`, `--text-muted` |
  | Lines | `--border-subtle`, `--border-strong` |
  | Accent | `--action-primary`, `--action-primary-text`, `--focus-ring` |
  | Status | `--status-success`, `--status-warning`, `--status-danger` |
  | Type | `--font-sans`, `--font-mono` |
  | Shape | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-pill` |
  | Motion | `--ease-out`, `--ease-in-out`, `--ease-drawer`, `--dur-fast`, `--dur-base`, `--dur-panel`, `--dur-slow`, `--dur-draw` |

  Slides read them through the `--deck-*` aliases defined in `src/core/css/deck.css`.
- **Fonts.** The product's own font files go to `src/fonts/`, with `@font-face` rules in
  `src/core/css/fonts.css`. The build inlines them.
- **Surfaces.** Cover and final are "moment" surfaces (`data-theme="dark"` or the product's hero
  surface). Content slides use the base surface. One accent; danger color only for what is
  actually broken or risky.
- **Data components.** Reproduce the product's own data components (score, badge, status, chart) on
  the same tokens. Use a screenshot only when the real screen is itself the proof.
- **Logo.** One source: `<template id="brand-mark">` in `src/shell.html`. Replace its paths with
  the product symbol from `docs/brand/symbol.svg`, split into `mark-base` and `mark-accent` (more
  parts are fine), never a redraw. Every `[data-mark]` element (cover, final, slide corner, QR
  center) is filled from it, so the logo changes in one place.

## Numbers

`src/data/numbers.json` maps a key to `{ "value", "source", "digits", "unit", "note" }`:

- `value`: a number (formatted for the deck language, animatable) or a string.
- `source`: a repo-relative file path, optionally with `#anchor`, or an http(s) URL. The file
  must exist and must ship: point into `docs/` (validation report, evidence), never into
  `context/` or the working files below. The row in that file states sample size, date and how it
  was measured.
- On a slide: `<span class="num" data-num="key"></span>` prints the value, add class `count` to
  count up; `<span data-source="key"></span>` prints the source. Both elements hold plain text only.
- `npm run build` fails on an unknown key, an empty source or a missing source file.
  `npm run build:final` also fails on any `{{placeholder}}`, marker or digit on a slide outside
  `data-num` (mark a deliberate literal such as a year or URL with `data-plain`).

The working files `plan.md`, `SPEECH.md`, `QA.md`, `demo-runbook.md` and `evidence.md` are cut from
history at submission (`.claude/scrub-paths`); the engine, slides and data ship.

## Demo and backups

Three layers, every time:

1. Live demo on the prepared stand, per `demo-runbook.md`.
2. Backup recording of the same scenario, labelled «ЗАПИСЬ {{date}}» in the frame, stored
   locally, playable offline.
3. The deck as PDF (`npm run pdf`) on a USB stick and in the cloud, the second backup.

The speaker always says which of the three is on screen. A recording is never presented as live.

## Engine

```text
src/
  shell.html             stage, slide name and number template, brand mark, {{@styles}} {{@slides}} {{@scripts}}
  core/css/              tokens.css (exported), fonts.css, type.css, deck.css, motion.css, parts.css, brand.css
  core/js/               kit.js, qr.js, presenter.js, engine.js
  locales/<lang>/        deck.json: UI strings and layout-specific key aliases
  slides/NN-id/          slide.html, style.css, scene.js, notes.js
  data/numbers.json      every figure with its source
  fonts/, img/           local assets, inlined by the build
tools/                   build, serve, pdf, shot, cards (Node, playwright-core)
dist/deck.html           one offline file: CSS, JS, fonts, images and QR matrices inlined
```

- A slide folder is `NN-id`; `slide.html` starts with
  `<section class="slide" id="id" data-title="..." data-steps="N">`. Optional attributes:
  `data-theme="dark"`, `data-bare` (no name and number: cover, final), `data-kind="appendix"`.
- `style.css` scopes every rule with `#id`. Asset paths in slides are relative to `src/`.
- `scene.js` calls `deckScene("id", { init, enter, step, leave, key })`; `notes.js` calls
  `deckNotes("id", { time, say: [...], caveat: [...] })`. `time` in seconds feeds the presenter plan.
- `<html lang>` in `shell.html` picks the locale and number formatting; `data-duration` on
  `.stage` is the talk length in seconds for the presenter timer.
- Animation contract (classes, steps, QR, reduced motion): skill `deck-motion`.

Keys: arrows, space, Enter, PageUp/PageDown (clickers) and Home/End move; ArrowUp/ArrowDown skip
steps; `S` presenter window in a separate window (timer, plan, notes, next slide), `F`
fullscreen, `R` replay the slide, `B` or `.` blackout, `Esc` close. Letter keys work on the Russian layout too.
Click on the left third goes back, elsewhere forward. Hash `#5.2` opens slide 5, step 2.
Modes: `?static` (final frames, no motion), `?print` (all slides at their last step, for PDF).
Reduced motion, `?static` and `?print` share one flag: CSS, tweens, counters and QR jump to the
final frame.

## Commands

Run in `presentation/`:

| Command | What it does |
| --- | --- |
| `npm install --silent` | Installs `qrcode` and `playwright-core` |
| `npm run dev` | Serves `src/` on `http://localhost:4173`, reloads on change, shows build errors |
| `npm run build` | Checks and writes `dist/deck.html`, prints the speech status |
| `npm run build:final` | Same plus strict checks and a fully written, synced speech; must pass before the defense |
| `npm run readme` | Renders the README banner, buttons and badges from `readme/assets.html` and `readme/readme.json` into `docs/readme/` in light and dark, rebuilds the README rows, colors mermaid blocks with product tokens |
| `npm run readme:preview` | The README header as GitHub shows it, light and dark, in `shots/` |
| `npm run speech:init` | Adds `SPEECH.md` sections for slides that have none |
| `npm run speech:check` | Speech against slides: order, missing or stale sections, timing, key presses, thanks line |
| `npm run speech:sync` | Writes cumulative times, the table, `notes.js` times and slide fingerprints (`speech.lock.json`) |
| `npm run shots` | PNG of every slide and step into `shots/`, fails on console errors or overflow; `-- --slide 3 --at 0.5,2` captures animation frames, `-- --width 1366 --height 768` checks scaling |
| `npm run pdf` | `dist/deck.pdf`, one page per slide at its last step |
| `npm run cards -- <file.html>` | Renders social cards (`section.card[data-name]`) to PNG |
| `npm run words -- SPEECH.md 125` | Words and seconds per `## N.` section of the speech at the given pace |
| `npm run chars -- submission.md` | Characters per `## Field (limit N, min M)` section, fails on a violation |

Chrome: `CHROME_PATH` points to a binary, otherwise Playwright uses the installed Google Chrome
(`CHROME_CHANNEL` overrides the channel).

## Skills

| Skill | Reach for it when |
| --- | --- |
| `presentation` | Any request for a deck or speech: structure, text, vibe or an edit; deck and speech together |
| `pitch-deck` | Planning or rebuilding the deck: outline by criteria, slide cards, kickoff and no-speaker variants |
| `speaker-script` | Writing, timing and syncing the speech, handoffs, the 3-minute cut |
| `demo-runbook` | Preparing the live demo, plan B, backup recording, rehearsals |
| `jury-qa` | Preparing answers, uncomfortable questions, red lines |
| `deck-audit` | Checking the deck, speech and numbers before a rehearsal or the defense |
| `deck-motion` | Animating any slide: choreography, steps, runners, counters; deciding when to render video instead |
| `deck-cover-final` | The cover and the final slide: logo assembly, name, team, «Готовы к вашим вопросам», QR assembly |
| `deck-design-sync` | Making the deck match the product 1:1: tokens, fonts, radii, icons, data components, logo |
| `pitch-video` | Scripting and producing the demo or promo video |
| `submission-texts` | Submission form texts under character limits, social post series with cards |
| `pitch-craft` | Writing the spoken words themselves: beats, word budget per window, hook, throughline, close |
| `storytelling-with-data` | Any slide with a chart or a table of numbers: chart choice, decluttering, one accent |
| `banner-design` | Banners and social images beyond the cards template |

Root skills that feed the defense: `competitors` (differentiation, Q&A), `naming` and
`brand-identity` (cover and mark), `humanizer` (strip AI tells from slide text and speech), `slides`
(copy formulas).
