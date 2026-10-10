---
name: demo-runbook
description: Prepare the live demo in demo-runbook.md — 20-minute setup checklist, main scenario table (time, action, what is visible, what to say), plan B, a backup recording labelled ЗАПИСЬ, rehearsals with the last one demo-off, and after-show artifacts. Use for a live demo, demo script, backup video or rehearsal — «демо», «живой показ», «сценарий показа», «репетиция», «запасное видео», «план Б», «что если демо упадёт», "demo runbook".
---

# Demo runbook

The demo is the strongest proof in the talk and the likeliest failure. This skill makes it
boring: one fixed path, rehearsed, with a fallback that is just as rehearsed. Facts come from
`evidence.md`; run commands from `docs/running.md`.

## 1. Fix the scenario

One path through the end-to-end example, inside the demo slot from `SPEECH.md`. Choose at most
three moments, each proving a criterion: the main result, the explanation of it, a correct refusal
or edge case. Pick inputs that worked on every rehearsal run; record in `evidence.md` which runs.

Done when: every moment names its criterion and its live evidence row.

## 2. Main scenario table

Fill `demo-runbook.md` §Main scenario: `Time | Action | What is visible | What to say`.

- Time is the talk clock, matching `SPEECH.md`.
- Action is one click or one input, exact (which button, which value).
- What is visible is what the jury sees after the action, including waiting states and how long.
- What to say is the spoken line in the defense language; it explains why, the screen shows what.
- Below the table: which steps are skipped when running late.

## 3. Plan B

Fill §Plan B: `Situation | What we do | What we say`. Cover at least: the stand does not start,
the network is down, a known defect appears, the result differs from the rehearsal, the laptop or
projector fails. Rules:

- Switch to the recording and say it in one phrase: «Это запись репетиции, не живой показ».
- A known defect is named, not hidden; the safe behavior around it is shown if there is one.
- Never retry more than once on stage.

## 4. Backup recording

Record after a clean rehearsal, on the same version, of the same scenario:

- 1080p, the deck resolution, no notifications, no terminal, no secrets, a clean browser profile.
- The label «ЗАПИСЬ {{date}}» is burned into a corner of the frame for the whole video
  («RECORDING {{date}}» for an English audience).
- Length fits the demo slot; playable offline from a local file; checked on the defense machine.

## 5. Rehearsals

Log each in §Rehearsals.

1. Read-through: each speaker reads their part, the operator clicks the scenario.
2. Full run with a timer and the presenter window, target inside the reserve.
3. The last one with the demo switched off: the operator runs plan B from the recording, the speakers
   keep the same text. Repeat on the defense machine if it is a different one.

Done when: two clean full runs, one plan B run, and the timings match `SPEECH.md`.

## 6. Prep and readiness

The 20-minute prep and the 15-minute readiness checklists in the template are run by the operator
out loud, item by item, on the day.

## 7. After the show

Record the version, whether the jury saw live or recording, screenshots and exported results into
the artifacts folder named in the template. Every failure seen on stage becomes an `evidence.md`
row with its date, and a `QA.md` answer if a juror noticed it.
