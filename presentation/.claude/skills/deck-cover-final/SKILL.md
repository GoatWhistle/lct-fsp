---
name: deck-cover-final
description: Build the two signature slides of the deck — the cover (the logo assembles, the product name appears letter by letter, team name, promise) and the final slide (logo and name visualization, «Готовы к вашим вопросам», QR codes to the solution and the code that assemble with animation). Use when making or changing the cover, the last slide, the logo animation or the QR — «обложка», «титульный слайд», «финальный слайд», «последний слайд», «QR на слайде», «анимация лого», "title slide", "closing slide".
---

# Cover and final slide

The jury remembers the first and the last frame. Both slides use the same lockup and the same
motion language, so the deck opens and closes on the product's identity. Templates:
`src/slides/01-cover/` and `src/slides/12-final/`.

## 1. The mark

- The logo lives once, in `<template id="brand-mark">` in `src/shell.html`. Every `[data-mark]`
  element (cover, final, the name in the slide corner, QR center) is filled from it.
- Take the paths from `docs/brand/symbol.svg` (skill `brand-identity`). Split the symbol into
  `mark-base` (the body) and `mark-accent` (the part that carries the meaning: a dot, a facet, a
  stroke). More parts are fine; give each its own class and delay.
- The wordmark is live text in the product font (`.wordmark.is-letters`, split by
  `deckKit.letters` in `scene.js`). Custom lettering instead goes in as inline SVG, one path per
  letter, each with `--i` for the stagger.

Done when: the cover, final and QR center show the product mark, not the placeholder.

## 2. Pick the assembly that acts out the name

Write what the name means as a verb (`context/naming.md` keeps its origin), then pick the movement:

| The name means | Assembly |
| --- | --- |
| builds, joins, completes | the base reveals bottom-up, the accent lands with a turn (default: `is-assemble`) |
| calibrates, balances, measures | the accent oscillates with decaying amplitude and settles in place |
| connects, routes, links | base strokes draw with `pathLength`, the accent travels along a path and docks |
| filters, selects, ranks | scattered dots converge into the accent, the rest fade |
| traces, draws, writes | the outline draws, then the fill fades in |
| finds, detects, scans | a scan line sweeps and stops on the mark, the mark lights up |

Implement extra keyframes in `src/core/css/brand.css`; easing only from tokens. The last frame is
exactly the static lockup. Motion vocabulary already there: `is-assemble` (base clip reveal 1.1 s,
accent lands 0.65 s later), `is-idle` (slow hover of the accent after landing, final only),
`wordmark.is-letters` (letters rise with 70 ms stagger from `--word-d`).

## 3. Cover

Content: the mark, the product name, the team name («команда {{TEAM}}»), the promise as a thesis
in two halves, the event in a quiet micro line. Nothing else: no agenda, no «Презентация
проекта», no member list (that is the kickoff variant), no date or version.

| Time | What appears |
| --- | --- |
| 0.1 s | mark base |
| 0.55 s | name, letter by letter |
| 0.75 s | accent lands |
| 1.45 s | promise |
| 1.6 s | the brand line draws across the full width |
| 1.8 s | team |
| 2.1 s | event |

Readable by 3.5 s. Surface: the dark moment surface or the product's hero surface.

## 4. Final slide

Content: the lockup (smaller, at the top, the accent idling), one line «Готовы к вашим вопросам»
in the deck language ("Ready for your questions" in English), and QR cards on the same slide:
«Решение» to the live stand and «Код» to the repository; one card if only one link exists. Each
card: the QR, a one-word label, the short URL in mono with `data-plain`. Never «Спасибо за
внимание» or "Thank you for your attention", no proof list (that is slide 11).

The QR assembles: modules fly in along rays delayed by distance from the center, the three finder
squares turn in, then the product mark pops into the cleared center (`.qr-mark` with `--d` about
2.2 s after the QR's `data-delay`). The build encodes at error-correction level H, so a mark up to
15% of the side keeps it scannable. The brand line draws behind the cards.

| Time | What appears |
| --- | --- |
| 0.1 s | mark |
| 0.45 s | name, letter by letter |
| 0.9 s | brand line |
| 1.1 s | «Готовы к вашим вопросам» |
| 1.3–1.6 s | QR cards, then modules |
| 3.6–3.8 s | marks in the QR centers |

## 5. Check

1. Frames: `npm run shots -- --slide 1 --at 0.5,1.2,3.5` and the final slide with
   `--at 1,2.5,4.5`. Mid-animation frames look intentional; the last frame equals the static
   lockup.
2. Scan both QR codes with a phone 3 m from the projected slide and from the laptop at half
   size. The links open the live stand and a public repository.
3. `?static` and the PDF show complete codes and the full lockup.
4. Text: deck language everywhere, no thanks line, team name spelled as registered.

Done when: both slides pass the four checks and use the same mark as the product.
