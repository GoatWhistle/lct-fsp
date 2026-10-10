---
name: pitch-video
description: Script and produce the demo or promo video — timecoded script with "On screen" and "Say" blocks, a 5-second teaser cut from real footage, live versus replay labels in the frame, voice-over text, recording requirements and limits from PLATFORM.md, assembly and render through the hyperframes plugin. Use for a demo video, promo, screencast or submission video — «видео для сабмита», «демо-видео», «промо», «скринкаст», «озвучка», «сценарий видео», "demo video", "pitch video".
---

# Pitch video

The video is judged without the team in the room, so it carries the claim, the proof and the
limits on its own. It reuses the deck's story and numbers; nothing new is claimed in it.

## 1. Constraints

From `context/PLATFORM.md`: maximum and minimum duration, resolution, format, language, whether
a live product run or a voice is required, where it is uploaded and with what visibility. Write
them at the top of `video-script.md` (create it next to `SPEECH.md`).

Done when: each constraint has a value and a source line; unknowns are in
`context/open-questions.md`.

## 2. Structure

Typical 2–4 minutes; stay at least 5 s under the limit.

| Part | Time | Content |
| --- | --- | --- |
| Teaser | 0:00–0:05 | The strongest real moment, cut from the live recording, no voice-over |
| Title | ~0:10 | Product name and the promise in one sentence |
| Problem | ~0:20 | The end-to-end example failing today, one sourced number |
| Mechanism | ~0:30 | The key mechanic on the product's own screens or the deck diagram |
| Demo | 0:40–1:20 | The example through the live product, in real time |
| Proof | ~0:20 | Measured numbers with what they were measured on, and the cost or limit beside them |
| Architecture | ~0:15 | Only if judged: what runs where, what stays local |
| Close | ~0:10 | What it is, where to try it, the link |

## 3. Script

`video-script.md`, one section per part:

```markdown
## 3. Mechanism, 0:30–1:00

**On screen:** {{exact URL or screen, what the cursor does, which overlay label is shown}}

**Say:**
> {{exact voice-over text in the video language}}
```

- On screen names exact URLs, screens and cursor paths, so anyone can record it.
- Say is written for the ear: short sentences, numbers as words, about 140 words per minute.
- Copy all Say blocks in order into `voice-over.md` as plain text for recording or TTS.

## 4. Labels in the frame

The label is in the picture, not only in the voice:

- `live` on a real-time recording of the running product;
- `replay` or «ЗАПИСЬ» on a replayed or pre-recorded session;
- `synthetic data` whenever the data is generated;
- the date of recording on the demo part.

## 5. Recording

- Screen at 1920×1080, at least 720p in the export, 30 fps or more, cursor visible and slow.
- Clean browser profile, no notifications, no bookmarks bar, no secrets, no local paths.
- Voice: external microphone, quiet room, one take per section, peaks under clipping.
- One raw clip per script section, named `NN-part.mp4`.

## 6. Assembly and render

Assemble with the `hyperframes` plugin (entry skill `hyperframes`; the product-launch or general
video workflow): clips on the timeline, titles and overlay labels in the product tokens, captions
burned in for silent autoplay, the voice-over track, the teaser cut placed first. Render to MP4.

## 7. Checks

Watch the whole file at 1× with sound: duration within limits, labels visible, every number equal
to `evidence.md`, captions match the voice, the link in the close works. Upload, then open the link
in a private window without logging in.

Done when: the uploaded video plays logged out, fits every constraint from step 1, and
`video-script.md` and `voice-over.md` match the final cut.
