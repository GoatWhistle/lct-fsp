# Demo runbook: {{PRODUCT}}

Not shown to the audience. Slot in the talk: {{1:45–3:45}} (`SPEECH.md` §{{N}}). Facts:
[evidence.md](evidence.md). Run commands: `../docs/running.md`.

Mode: {{live on our laptop / remote stand / recording only}}. Version: {{commit}}.
Operator: {{name}}. Timer: {{name, not a speaker}}.

## Prep: 20 minutes before

1. [ ] Version fixed: `git rev-parse --short HEAD` is {{hash}}, `git status --short` is empty.
2. [ ] Stand up: `{{start command}}`.
3. [ ] Health: `{{health check}}` returns {{expected}}.
4. [ ] Warm-up run of the main scenario: {{expected result}} in {{time}}.
5. [ ] Demo data present: {{dataset, account, seed}}.
6. [ ] Screen 1920×1080, browser zoom 100%, clean profile, notifications off.
7. [ ] Nothing private on screen: no terminal, no `.env`, no tokens, no local paths, no extra tabs.
8. [ ] Backup recording open and paused; the deck PDF open in a background tab.
9. [ ] Network fallback ready: {{offline mode / phone hotspot}}.

## Main scenario

| Time | Action | What is visible | What to say |
| --- | --- | --- | --- |
| {{1:45}} | {{Open screen X with the example loaded}} | {{what the jury sees}} | {{spoken line}} |
| {{2:05}} | {{Click "Run"}} | {{progress, then the result in about N s}} | {{spoken line}} |

If running late: {{skip steps N and M; they are in the recording}}.

## Plan B

| Situation | What we do | What we say |
| --- | --- | --- |
| The stand does not start | Play the backup recording «ЗАПИСЬ {{date}}» | {{"This is a rehearsal recording, not a live run."}} |
| No network | {{offline mode / recording}} | {{one sentence}} |
| Known defect {{id}} appears | {{wait for the safe state, retry once}} | {{name the defect in one sentence}} |
| Result differs from rehearsal | {{show it, explain, move on}} | {{one sentence}} |
| Laptop or projector fails | PDF from USB on the organizer laptop | {{one sentence}} |

## Backup recording

- File: `{{path}}`, {{duration}}, recorded {{date}} on version {{hash}}.
- Label «ЗАПИСЬ {{date}}» visible in the frame for the whole video.
- [ ] Plays offline on the defense machine.

## Rehearsals

| # | Date | Kind | Result | Fixes |
| ---: | --- | --- | --- | --- |
| 1 | | Read-through, the operator clicks along | | |
| 2 | | Full run with timer and presenter window | | |
| 3 | | Demo switched off, plan B from the recording | | |

## Ready: 15 minutes before

- [ ] The main path checked once more by a second person.
- [ ] The deck open at slide 1 in fullscreen; presenter window on the second screen.
- [ ] Each speaker has only their own text and their questions open.
- [ ] The timer is started by a teammate who is not speaking.

## After the show

1. Record the version and what the jury saw: live or recording.
2. Save screenshots and exported results into `{{artifacts/defense/YYYY-MM-DD/}}`.
3. Every failure seen on stage becomes an `evidence.md` row with its date, and a `QA.md` answer if
   a juror noticed it.
