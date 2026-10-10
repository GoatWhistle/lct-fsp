---
name: speaker-script
description: Write or update the spoken defense text in SPEECH.md, about 6 minutes by default, one section per slide in the deck's order, timed at 120–135 words per minute with [→] key presses, one-phrase handoffs, a 3-minute version and a cut-first list, kept in sync with the slides by npm run speech:check / speech:sync. Use for a speech, talk track, speaker notes, timing, or after any slide changed — «спич», «текст выступления», «что говорить», «тайминг», «заметки докладчика», «обнови спич», «сократить до 3 минут», «кто что говорит», "speaker script".
---

# Speaker script

`SPEECH.md` is the text the speakers rehearse word for word. It is part of the deck: one section per
slide, in the slide order, and it changes in the same turn as the slides. The spoken text is in the
deck language; headings and tables stay as in the template.

## 1. Budget

- Regulation: `data-duration` in `src/shell.html`, 360 s (6:00) unless `context/PLATFORM.md` says
  otherwise. The speech fills it minus a 20 s reserve: 5:40 of speech for 6:00.
- Pace 125 words per minute (120–135). A 30-second slide holds about 60 words; 6:00 holds about
  700 words in total.
- Seconds per slide follow the criteria weights (`plan.md` §2); the template's defaults are in
  the `SPEECH.md` table.

## 2. Sections

Each slide has exactly one section, headed `## 05. Механика [mechanic] 0:35 (2:35)`: two-digit
number, title, slide id in brackets, slide seconds, cumulative time. `npm run speech:init`
creates missing sections from the slides and their `notes.js` cues; `speech:sync` recomputes the
numbers, so only the slide seconds are edited by hand.

## 3. Write each section

- First the claim, then the proof. One idea per sentence, sentences under 15 words.
- Say what the slide does not show: the reason, the example, the consequence. The speaker never
  reads the slide: no sentence repeats the slide text word for word; the speaker faces the room
  and turns to the slide only to point at the visual.
- The end-to-end example is named the same way on every slide.
- Numbers are spoken as words, exactly as in `numbers.json`, with the unit and what was measured:
  «шестьдесят процентов на тысяче отложенных закупок», not «60%». A value not measured yet is
  `[N]`; if it never comes, the whole phrase is deleted, never replaced by «примерно».
- Limitations marked `[HONEST]` in the cards are said aloud on their slide.
- `` `[→]` `` on its own line marks every key press: one per step (`data-steps`) and one per
  slide change, exactly where the press happens.
- Greeting and team: one sentence on the cover, then the promise.
- The last words are «Готовы к вашим вопросам» (in the deck language), never «Спасибо за
  внимание».

## 4. Speakers and handoffs

- Each speaker owns a continuous range of slides; the demo operator owns the demo slot. Write the
  speaker into the table and as `**Name.**` at the top of the section.
- A handoff is one phrase naming the next speaker and topic: «Дальше {{ИМЯ}} покажет, как мы это
  проверили». The next speaker starts with content, no greeting. Mark it `**Handoff:**`.

## 5. Sync with the slides

Run after writing and after every change to the deck:

1. `npm run speech:check` lists every mismatch: a slide without a section, a section without a
   slide, a different order, a slide changed since the last sync (its text, steps or numbers),
   seconds that differ from `notes.js`, a total over the regulation, a section whose words do not
   fit its seconds, too few `[→]`, a thanks line.
2. Rewrite every section it names. A slide added: `npm run speech:init` inserts its section;
   rebalance seconds so the total still fits. A slide removed: delete its section.
3. `npm run speech:sync` writes cumulative times, the table, `notes.js` `time` values and the
   slide fingerprints into `speech.lock.json`.
4. `npm run speech:check` again: 0 errors. `npm run build:final` fails while any section still has
   placeholders or errors.

Also keep `notes.js` `say` as 2–4 cue lines per slide and `caveat` with the `[HONEST]` lines; the
presenter window (`S`) shows them against the clock.

## 6. 3-minute version and cut-first list

- A table: which slides stay, seconds each, what is said. Keep cover, solution, product, the
  heaviest mechanic, measured, final; fold the rest into one sentence each.
- An ordered cut-first list with the seconds each cut saves: architecture details, the second
  mechanic, the status slide, demo extras. The speaker cuts from the top without thinking.

## 7. Rehearse

Read aloud with a stopwatch, log each run in §Rehearsal log, fix the text, not the pace.
`npm run words -- SPEECH.md 125` shows words and seconds per section.

Done when: `speech:check` has 0 errors and 0 unwritten sections, two consecutive full rehearsals
land inside the reserve, and the times in `notes.js`, `SPEECH.md` and `demo-runbook.md` agree.
