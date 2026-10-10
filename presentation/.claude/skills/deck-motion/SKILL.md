---
name: deck-motion
description: Animate deck slides with the engine's choreography — --d/--t classes under .play, data-steps with slide.step hash links, R replay, pathLength line drawing, offset-path runners, count-up, seeded generative scenes, the QR assembling from the center, a cover animation that acts out the product name, one reduced-motion flag — and decide when a rendered hyperframes video fits better. Use for slide animation or motion in the deck — «анимация слайда», «оживи слайд», «анимация обложки», «QR анимация», «шаги на слайде», "animate slide", "slide transition".
---

# Deck motion

Motion on a slide is a diagram that moves: it shows the mechanism in the order the speaker
explains it. Snippets for every technique are in [recipes.md](recipes.md).

## Principles

- Everything is animated: every slide has an entry choreography, every element arrives in the
  order the speaker talks about it, the logo too. A slide where content just appears is unfinished.
- Each movement shows a step of the mechanism: data flows along the trace, a value settles, a bar
  grows to the measured value. If removing a motion loses no meaning, remove it.
- Content slides reach a readable state within 1.5 s; the cover within 3.5 s. Anything the speaker
  talks about later is a step (`data-s`), not a long delay.
- Easing and durations come from the product tokens (`--ease-out`, `--ease-in-out`, `--dur-*`).
  No bounce, no elastic. Quiet loops (runners, an idle accent) only on the main path of the slide,
  marked `only-motion`.
- Deterministic: generative scenes use `deckKit.rng(seed)`, never `Math.random`, so the rehearsal,
  the defense and the PDF show the same picture.
- The last step is the PDF page and the reduced-motion frame: it must contain everything.

## Engine contract

| Need | How |
| --- | --- |
| Enter choreography | Classes `.a` rise, `.f` fade, `.s` scale in, `.pop`, `.w` wipe, `.dr` line draw. `--d` delay and `--t` duration in seconds, inherited, so set them on a group. Runs when the slide gets `.play` |
| Steps | `data-steps="N"` on the section; `data-s="k"` shows from step k, `data-until="k"` hides after k, `data-at="1,3"` adds class `.at` exactly at those steps. A step element is not also an `.a/.f` element: wrap it |
| Address | Hash `#5.2` is slide 5, step 2; the build fails on a step above `data-steps` |
| Replay | `R` re-adds `.play`, restarts counters and QR, calls `scene.enter` again |
| Line drawing | `<path pathLength="1" class="dr">`; works for any SVG shape |
| Runner along a path | `.runner` inside a box the size of the SVG viewBox, `deckKit.followPath(runner, path)` in `init` |
| Count-up | `data-num="key"` plus class `count`; counts to the value from `numbers.json` |
| Scene logic | `scene.js`: `deckScene(id, { init(el), enter(el, step, dir), step(el, step, dir), leave(el), key(el, event) })` |
| Tween | `deckKit.tween({ from, to, dur, delay, curve: "out" \| "inOut" \| "linear", update, done })` returns a cancel function |
| Letters | `deckKit.letters(el)` splits text into spans with `--i` for staggered reveals |
| Reduced motion | `deckKit.reduced` and class `html.is-reduced`: one flag for prefers-reduced-motion, `?static` and `?print`. CSS animations jump to the end, tweens and the QR draw the final frame, `only-motion` elements hide |

## Animate a slide

1. Write the sequence as sentences first: what appears, in which order, and which spoken words
   each part lands on. Map spoken pauses to steps.
2. Build the static last frame; check it with `?static`.
3. Add choreography classes and `--d` per group; steps for what the speaker introduces later.
4. Add `scene.js` only for what CSS cannot do: values from data, generative layouts, tweens.
5. Check frames: `npm run shots -- --slide <n> --at 0.3,0.8,1.5,3`, then press `R` live.

Done when: the slide reads at 1.5 s, every step lands on its spoken sentence, `?static` and the
PDF page show the full content, and there are no console errors.

## Cover, final and QR

The logo assembly on the cover, the final lockup with «Готовы к вашим вопросам» and the QR
assembly have their own procedure: skill `deck-cover-final`. The rules above apply to them too.

## When to render video instead

Use the `hyperframes` plugin when the output is a file, not a live deck: the submission video,
a teaser, a social clip, an animated title for video, anything synced to voice-over or music, or a
continuous sequence longer than about 20 s. The deck stays in this engine because the speaker
controls the pace and the deck runs offline from one file. Embedding a rendered clip into a slide
is a last resort: it inflates `dist/deck.html` and cannot step with the speech.
