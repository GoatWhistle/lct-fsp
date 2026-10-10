# Vendored: storytelling-with-data

- Upstream: https://github.com/sammcj/agentic-coding, path `Skills/storytelling-with-data`
- License: Apache-2.0, see [LICENSE](LICENSE) (kept unchanged)
- Upstream commit date: 2026-07-04
- Vendored: 2026-10-10

## Local edits

1. `SKILL.md` format note: dropped the advice to pair with a pptx skill. The slide deck is the HTML engine in `presentation/` (built with the `pitch-deck` skill), and charts follow the product tokens in `src/core/css/tokens.css`.
2. `SKILL.md` Lesson 4: colour values come from the product tokens; the dataviz skill applies to mark rendering only, where available.
3. `SKILL.md` Lesson 6 and `references/review-checklist.md`: "repeat the key message at least 3 times" became "restate the key message in the title, the visual and the close", so it does not conflict with `pitch-craft`.
4. `references/colour-and-emphasis.md` "Palette and colour system": the dataviz palette was replaced by the product tokens (`--text-muted`, `--text-secondary`, `--border-subtle` for grey, `--action-primary` for the accent, `--status-*` for positive and negative).
