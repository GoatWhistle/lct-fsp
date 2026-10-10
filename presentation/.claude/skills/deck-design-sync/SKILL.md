---
name: deck-design-sync
description: Make the deck look exactly like the product — export design tokens from the frontend, bring the product fonts, radii, colors, icons, logo and signature data components into the slides, and verify side by side against product screenshots. Use when starting a deck, after the product design changes, or when slides look unlike the site — «как на сайте», «стиль сайта», «дизайн-система в презентации», «токены в деку», «шрифты в презентацию», "match the product style".
---

# Deck design sync

The deck is the product on a projector. A juror who saw the stand must recognize the deck in one
glance: same type, same corners, same accent, same icons, same data components. The deck never
invents its own style and never edits tokens by hand.

## Steps

1. **Tokens.** `cd frontend && npm run tokens:export` writes `presentation/src/core/css/tokens.css`
   (both themes, the contract names from `presentation/AGENTS.md`). Rerun after every design
   change in the frontend; the file is regenerated, never edited.
2. **Fonts.** `npm run tokens:export -- --fonts` copies the product font files, or place them in
   `src/fonts/` with `@font-face` rules in `src/core/css/fonts.css`. The build inlines them, the
   deck works offline. Numbers use the product mono font with `tabular-nums`.
3. **Logo.** The symbol paths from `docs/brand/symbol.svg` go into `<template id="brand-mark">`
   in `src/shell.html` (skill `deck-cover-final`). Custom lettering comes from
   `docs/brand/wordmark-*.svg`.
4. **Shape and color.** Radii only through `--radius-*`; surfaces, text, lines and accent only
   through the `--deck-*` aliases in `deck.css`. One accent; status colors only for statuses.
   Content slides on the base surface, the cover and final on the dark moment surface or the
   product's hero surface. The QR stays black on white.
5. **Icons.** The same icon set and stroke width as the product (the frontend `Icon` names). Copy
   the path data as inline SVG with `stroke="currentColor"`; one concept, one icon, same as in
   the product.
6. **Data components.** The product's signature components (score, badge, status, chart, card)
   are rebuilt on the slide with the same structure and the same CSS rules, selectors scoped
   under the slide id. A screenshot is used only when the real screen is the proof (slide 04).
7. **Charts.** Product tokens, gray plus one accent; skill `storytelling-with-data`.
8. **Verify side by side.** `cd frontend && npm run shots` and `cd presentation && npm run shots`;
   put a product screenshot next to each slide with a product element and compare font, weight,
   radius, accent, icon style and spacing rhythm. Fix deviations in the deck, never by changing
   the deck's tokens.
9. **No literals.** This must print nothing:
   ```bash
   grep -rnE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|cubic-bezier" src --include=*.css | grep -v "core/css/tokens.css"
   ```

Done when: `tokens.css` is fresh from the current frontend, the fonts and the mark are the
product's, the literal check is empty, and the side-by-side comparison shows no visible difference
in type, shape, color or icons.
