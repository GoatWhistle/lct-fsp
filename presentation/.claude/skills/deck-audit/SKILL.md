---
name: deck-audit
description: Audit the deck and speech before a rehearsal or the defense — can the jury answer from the deck alone, criteria coverage, every number against its source, organizer memo coverage, timing, wording, visual tokens and build checks — and write blockers into plan.md. Use to review, check or audit slides, speech or numbers — «проверь презентацию», «аудит деки», «готовы ли к защите», «покрытие критериев», «сверь цифры», "review the deck", "audit".
---

# Deck audit

A read-only pass that ends in a verdict. It changes nothing except `plan.md` §8 Audit; fixes go
back through `pitch-deck`, `speaker-script` or `jury-qa`. Run it before the first full rehearsal
and again on the day.

## 1. Build checks

Run in `presentation/` and record the result lines:

- `npm run build:final`: lists every placeholder, marker, unsourced digit and source problem.
- `npm run shots`: console errors and overflow per slide; open the PNGs and look at every one.
- `npm run shots -- --width 1366 --height 768 --out shots/small`: scaling on a small projector.
- `npm run pdf`: open the PDF, every page readable at its last step.

## 2. Deck-only test

Answer each question using only the slides, as a juror who missed the speech:

| Question | Answer from the deck | Slide |
| --- | --- | --- |
| What is it, in one sentence? | Yes / Partly / No | |
| For whom, and what problem does it remove? | | |
| How does it work, input to output? | | |
| Does it work now, and how do we know? | | |
| How good is it, measured against what? | | |
| Why can the result be trusted or checked? | | |
| Where does it fail? | | |
| What is done and what is not? | | |
| What does the team ask for or propose next? | | |

Every Partly or No becomes a finding.

## 3. Criteria coverage

| Criterion | Max | Slides | Evidence on those slides | What is missing |
| --- | ---: | --- | --- | --- |

Weights from `context/requirements.md`. A criterion whose evidence is only spoken, not shown,
is a finding.

## 4. Numbers

For every `data-num` key and every number in `SPEECH.md` and `QA.md`:

- Open the source and confirm the value as it is today, on the current version.
- Population, sample size, unit and date are stated on the slide or in the source row.
- A comparison names its baseline; a percentage names its denominator.
- Rounding does not move the claim; the speech says the same number as the slide.
- Nothing measured in-distribution is presented as general.

## 5. Organizer memo coverage

| Requirement (quote) | Where: slide, appendix, demo or PDF | Status |
| --- | --- | --- |

Every mandatory item from `context/PLATFORM.md` is covered or has an owner and a date.

## 6. Timing

- `npm run speech:check`: 0 errors, no unwritten section, no slide changed since the last sync.
- `npm run words -- SPEECH.md 125` against the regulation.
- Times in `notes.js`, `SPEECH.md` and `demo-runbook.md` agree.
- The last rehearsal log entry is inside the reserve.

## 7. Wording and visual

- Every title is a thesis in two halves; no topic labels.
- No filler from the list in [AGENTS.md](../../../AGENTS.md); search `src/slides`, `SPEECH.md`,
  `QA.md` with the Grep tool for
  `уникальн|высок\w* точн|масштабир|мощн\w* платформ|инновацион|добро пожаловать|unique|high accuracy|scalab`.
- No paragraph on a slide; limitations sit beside their claims.
- `src/core/css/tokens.css` matches a fresh `npm run tokens:export`; no color literals in
  `src/slides/**/style.css` (Grep `#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(`).
- The cover and final read on the projector: contrast, size, QR scans from 3 meters.

## 8. Verdict

Write `plan.md` §8 Audit: date, version, then findings in three groups.

- **Blockers:** a wrong or unsourced number, a criterion with no evidence, a memo item missing, a
  failing build, a demo path not rehearsed.
- **Should fix:** a Partly answer, a weak title, timing over by more than 10%.
- **Nice to have:** polish.

Done when: every finding has an owner and a deadline, and the blocker list is empty or each blocker
is due before the next rehearsal.
