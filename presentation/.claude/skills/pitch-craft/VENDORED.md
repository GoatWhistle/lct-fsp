# Vendored: pitch-craft

- Upstream: https://github.com/ooiyeefei/ccc, path `skills/pitch-craft`
- License: MIT, see [LICENSE](LICENSE) (kept unchanged)
- Upstream commit date: 2026-07-20
- Vendored: 2026-10-10

## Local edits

1. `SKILL.md` description: sibling skills re-pointed. `demo-video` became `pitch-video` (video rendered with the hyperframes plugin), `pitch-deck` stays `pitch-deck`, `pitch-package` became `demo-runbook` and `jury-qa`.
2. `SKILL.md`: added a line under the intro: word-rate numbers are calibrated for English; for Russian, time a read-aloud with a stopwatch (target 120-135 words/min) and use that rate.
3. `SKILL.md` step 1: beat timestamps come from the final rendered video (hyperframes composition timeline or scrubbing the MP4), never from planned holds; the sidecar `t_video` and demo-video Gate 3 references were removed. The demo-video storyboard became the `pitch-video` video script.
4. `SKILL.md` step 5: the `demo-video/references/storyboard.md` link became a pointer to the "On screen" blocks of the `pitch-video` script.
5. `SKILL.md` "Re-syncing an existing script": timestamps are read from the final rendered video, never from planned holds.
6. `references/timing.md`: the pacing-check formula no longer cites sidecar `t_video` deltas, and re-sync step 1 was rewritten. It now takes beat timestamps from the final rendered video (hyperframes composition timeline or scrubbing the MP4), never from planned holds. The `t_wall`, `t_proof` and `timestamps_suspect` sidecar fields were removed.
7. `references/storytelling.md`, `references/human-voice.md`: real people, team and product names in examples were replaced with `{{Speaker}}`, `{{Speaker2}}`, `{{TEAM}}` and `{{PRODUCT}}`.
