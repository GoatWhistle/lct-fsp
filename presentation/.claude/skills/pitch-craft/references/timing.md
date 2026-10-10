# Timing - budgets, formats, re-sync

## Words per second

| Delivery | wps | Why |
|---|---|---|
| Recorded voiceover, calm narrator | 2.4-2.6 | No audience, no clicker; steady read |
| TTS voices | 2.5-2.8 | Varies by voice; test one segment first |
| Live on stage | 2.0-2.2 | Pauses, audience reactions, slide clicks eat time |

Word ceiling per segment = window seconds x wps. A 16-second voiceover window holds ~38-42 words. Compute ceilings BEFORE drafting and write them next to each beat.

## The per-window pacing check

The rates above are drafting targets. After drafting, check every segment's *actual* density against its real window:

```
density = words / window_seconds
```

`window_seconds` is the gap between consecutive beat timestamps taken from the final rendered video (hyperframes composition timeline, or scrubbing the MP4), never from planned holds.

**Keep each window inside 2.2 - 3.1 w/s.** This is an acceptance band, not a target - a script can average correctly and still have one window at 1.4 and another at 3.6.

- **Below 2.2** - dead air. A voice model reads the segment and stops, leaving visible silence over moving footage. Add a sentence or shorten the beat.
- **Above 3.1** - the read runs past its window and lands on the next beat's frames. Cut clauses, never ask for a faster read.

Run this per window, not on the script as a whole. The average hides exactly the segments that break.

The slot budget line goes at the top of every script, explicitly:

```
Budget: 5:00 slot = ~2:30 spoken deck + 2:36 demo video. Runs ~5:10 as
written - trim points below.
```

If the budget line doesn't balance, no amount of good prose fixes it - cut a beat.

## Formats

**Recorded** (chunks keyed to milestone timestamps):

```
N. M:SS -> M:SS  [MILESTONE_NAME]  (23 words / ceiling ~26)
<prose block, spelled-out numbers, present tense>
```

Annotate each header with the segment's word count against its ceiling - it makes every draft self-verifying, for you and for anyone reviewing the script.

**Live** (slide-anchored, cumulative clock, with cues):

```
[M:SS - Slide N - Name]
<what you say>
(cue: stage direction)
```

**Demo-break marker** - always states coverage so a slide-number jump never looks like a missing section:

```
>>> PLAY DEMO VIDEO (~2:36) - this covers slides 8, 9, 10: accurate,
profitable, safe. You stay quiet; pick up at slide 11. <<<
```

**Change-log block** (optional, bottom of file): when a script revision changes claims or timings, note what changed and why. Future editors (including you) will otherwise re-litigate settled wording.

## The estimation loop

1. Draft the segment.
2. Count its words (`wc -w` on the block) against the ceiling.
3. Over budget: cut clauses, not pace. The speaker's tempo is fixed; the text is not.
4. Read one segment aloud once with a stopwatch to calibrate the wps for THIS voice, then trust the math for the rest.

## Trim points

Every live script names 1-2 trims before it's done, with the seconds they save and what to protect:

```
TRIM (to hit 5:00 flat): fold #6 into #7, cut #12 to one sentence (~15s).
Protect #14 - it is the track-winning slide.
```

Naming trims in advance is what lets a speaker hit the clock on stage without improvising cuts mid-sentence.

## Re-sync after a re-record

A re-recorded take shifts every milestone (live backends have real latency variance - seconds, not milliseconds). Procedure:

1. Take the new beat timestamps from the final rendered video: read them off the hyperframes composition timeline, or scrub the delivered MP4 and note the time each beat starts. Never sync against planned holds from the video script or the recording session's wall clock; both drift from the file by capture offset plus backend latency, and the drift is invisible until the voiceover lands on the wrong frame. Sync to the moment a beat starts, not the later moment its claim becomes visible, or every segment lands late.

   **If a beat's start cannot be pinned on the rendered file, do not sync that segment.** Locate it frame by frame or re-record before writing a word - narration voiced against wrong timestamps has to be re-voiced, not re-cut.
2. Map each narration segment's cue point to its new milestone (seg 1 -> CASE_OPEN, ..., last seg -> END).
3. Where a window shrank, cut prose to fit. Never stretch prose to fill a grown window - let the video breathe instead.
4. 1-2 seconds of drift per segment is acceptable; re-voice only if the wording itself changed.

The inverse constraint also holds: once narration is voiced over a take, changing the video's timing means re-aligning the script. Treat take + script as one versioned pair.
