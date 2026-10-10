# Motion recipes

Copy-ready snippets for the deck engine. Selectors in `style.css` are scoped with the slide `id`.
Working examples: `src/slides/01-cover` (mark assembly, letters, brand line), `05-mechanic` (runners along curves), `03-solution` (pipeline,
steps, `data-at`), `08-measured` (count-up, bars from data), `06-funnel` (seeded generative layout), `12-final` (QR).

## Group choreography

```html
<div class="pipeline" style="--d:0.4s">
  <b class="a">Вход</b>
  <span class="caption a" style="--d:0.55s">что приходит</span>
</div>
```

`--d` is inherited, so children of a group share its delay unless they set their own.

## Steps that land on speech

```html
<section class="slide" id="mechanics" data-steps="2">
  <p class="claim" data-s="1">Шаг первый, появляется на первом нажатии</p>
  <p class="claim" data-s="2">Шаг второй</p>
  <span class="node" data-at="1">подсвечен только на шаге 1</span>
  <p class="hint" data-until="0">видно только до первого нажатия</p>
</section>
```

```css
#mechanics .node.at { scale: 1.2; }
```

## Line drawing and a runner

```html
<div class="flow">
  <svg viewBox="0 0 1680 200">
    <path class="trace dr" pathLength="1" style="--d:0.3s;--t:1.2s" d="M0 100 H1680" />
  </svg>
  <span class="runner only-motion" style="--d:1.5s;--t:2.4s;--loop:infinite"></span>
</div>
```

```css
#flow-slide .flow { position: absolute; left: var(--gutter); top: 420px; width: 1680px; height: 200px; }
```

```js
deckScene("flow-slide", {
  init(el) {
    deckKit.followPath(el.querySelector(".runner"), el.querySelector(".flow path"))
  },
})
```

The box holding the runner must have the same pixel size as the SVG viewBox, so path coordinates
map one to one.

## Count-up and bars from data

```html
<span class="num count" data-num="ours_metric"></span>
<i class="bar-fill" data-bar="ours_metric"></i>
```

`08-measured/scene.js` reads `data-value` written by the build and sets `--w` on each bar; the bar
grows with a keyframe from `scaleX(0)` to `scaleX(var(--w))`.

## Seeded generative scene

```js
deckScene("data-cloud", {
  init(el) {
    const random = deckKit.rng(7)
    const svg = el.querySelector(".cloud")
    for (let i = 0; i < 120; i += 1) {
      const dot = deckKit.svg("circle", { cx: random() * 1680, cy: random() * 520, r: 4, class: "dot" }, svg)
      dot.style.setProperty("--d", `${0.2 + random() * 0.8}s`)
      dot.classList.add("pop")
    }
  },
})
```

## Tween an attribute

```js
deckScene("settle", {
  enter(el) {
    const node = el.querySelector(".marker")
    this.stop?.()
    this.stop = deckKit.tween({
      from: 0,
      to: 1,
      dur: 1800,
      curve: "out",
      update: (t) => node.setAttribute("cx", String(800 + Math.sin(t * 18) * 160 * (1 - t))),
    })
  },
  leave() {
    this.stop?.()
  },
})
```

A decaying oscillation that settles on its target: the calibration cover pattern. With reduced
motion the tween calls `update(1)` once and the marker is drawn at rest.

## Letters and the lockup

```html
<div class="lockup">
  <span class="mark is-assemble" data-mark></span>
  <h1 class="wordmark is-letters">{{PRODUCT}}</h1>
</div>
```

```js
deckScene("cover", {
  init(el) {
    deckKit.letters(el.querySelector(".wordmark"))
  },
})
```

`brand.css` animates `.wordmark.is-letters span` from `--word-d` with a 70 ms stagger, the mark
base with a clip reveal and the accent with a turning landing; `is-idle` adds a slow hover on the
final slide. Size with `--mark-size` and `--word-size` on the lockup. Full cover and final
procedure: skill `deck-cover-final`.

## QR with the product mark

```html
<div class="qr" data-qr="https://github.com/{{REPO}}" data-label="QR: github.com/{{REPO}}" data-delay="1.6">
  <span class="qr-mark" data-mark style="--d:3.8s"></span>
</div>
```

`data-mark` fills it from the brand template; `brand.css` gives it a light plate, dark base and
the pop after the modules land (`--d` about 2.2 s after `data-delay`). Keep it at 15% of the QR
side so level H still recovers the hidden modules.

## Slide-specific keyframes

Name them with the slide id to avoid collisions: `@keyframes measured-grow`. Generic ones live in
`src/core/css/motion.css`: `deck-rise`, `deck-fade`, `deck-scale`, `deck-pop`, `deck-wipe`,
`deck-draw`, `deck-run`, `deck-ping`.
