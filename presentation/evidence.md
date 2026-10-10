# Defense evidence: {{PRODUCT}}

Every claim on a slide, in the speech, in the video or in an answer has a row here. No row, no
claim. Product-level proofs (reports, test runs, measurements) live in `../docs/evidence.md`;
link to them instead of copying.

Statuses:

- **Live, {{date}}**: checked on the running product or stand, with the version. A run on an older
  version does not prove the current code.
- **Code + tests**: implemented and covered by automated tests; no live run for this claim.
- **Not ready**: absent, or present but not accepted live. On slides it appears as "in progress".

Version: {{commit}}. Stand: {{where it runs}}.

## Claims

| # | Claim | Status | Proof | Slide | On the demo |
| ---: | --- | --- | --- | --- | --- |
| 1 | {{The product turns input X into result Y}} | Live, {{date}} | {{link to run log, screenshot or report}} | {{4}} | {{action in the scenario}} |
| 2 | {{Feature Z handles case W}} | Code + tests | {{test file and command}} | {{6}} | {{not shown}} |
| 3 | {{Feature V}} | Not ready | {{issue or plan}} | {{10}} | {{not shown}} |

## Numbers

One row per `src/data/numbers.json` key. The value exactly as in the source; sample size and runs
always stated.

| Key | Value | Population and runs | How measured | Source | Date |
| --- | --- | --- | --- | --- | --- |
| `ours_metric` | {{N}} | {{held-out set, size, split}} | {{command or procedure}} | {{../docs/evidence.md#...}} | {{date}} |

## Done, in progress, next

| Done, live | Done, tests only | In progress or not started |
| --- | --- | --- |
| {{...}} | {{...}} | {{...}} |

## Organizer memo requirements

| Requirement | Status | Where shown |
| --- | --- | --- |
| {{quote from the memo}} | {{Live, date / Code + tests / Not ready}} | {{slide, demo step or PDF section}} |

## Outdated or conflicting material

- {{file}}: {{what differs from the current state; not used on the defense}}.
