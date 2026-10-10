# Deck variants

The default order in [SKILL.md](SKILL.md) is for the defense. These variants change the order and
the rules that differ; everything else stays.

## Kickoff pitch: 4 slides, 2–3 minutes

At the start of the event nothing is measured yet, so the deck sells a plan and a check, not results.

| # | Slide | Job |
| --- | --- | --- |
| 1 | Cover | Product name and the promise in one line, event and track |
| 2 | Hypothesis | What we build and how we will know it works: «Если {{механика}}, то {{измеримый результат}} по сравнению с {{базовым способом}}», plus the metric and the baseline we will compare against |
| 3 | Team and roles | The one deck where a team slide belongs: each person, their role and the part of the plan they own |
| 4 | Plan to the defense | Days or checkpoints, each with a result that can be shown; the main risk and its fallback |

- No numbers about the product: nothing is measured. Numbers about the problem still need a source.
- Promise only what the plan covers. The kickoff deck is replaced, not edited, for the defense.

## Checkpoint: progress review, 3–5 minutes

| # | Slide | Job |
| --- | --- | --- |
| 1 | What changed since last time | One trace: what we believed, what we found, what we changed |
| 2–3 | Evidence | The measurements that drove the change, before and after |
| 4 | Working now | Short demo or screens of the current version, with its commit |
| 5 | Next | The next measurable step and what would change the plan |

Say plainly what moved to a branch, what failed, what was rolled back. A checkpoint rewards an
honest change of course more than a polished story.

## International or no-speaker deck

For an English-speaking jury, judging from a submitted PDF, or a deck that runs without a speaker.

- The deck language follows `context/PLATFORM.md`: set `<html lang="en">` in `src/shell.html`;
  the engine switches to `src/locales/en/` and English number formatting.
- Titles carry the full claim; each slide adds a 1–2 line caption that replaces the speech.
- Sources are visible on the slide (`data-source`), with sample size in the caption.
- Meaning never depends on motion or steps: the PDF shows each slide at its last step, so the last
  step must be complete. Check `npm run pdf` page by page.
- Demo and narration move to the video: skill `pitch-video`. The deck links to it by QR.

## 3-minute slot

Keep: cover, solution pipeline, working product, the heaviest key mechanic, measured, final.
Problem and architecture shrink to one sentence inside the solution slide; done/next becomes one
line on the final slide. Time per slide is in `SPEECH.md` §3-minute version (skill `speaker-script`).
