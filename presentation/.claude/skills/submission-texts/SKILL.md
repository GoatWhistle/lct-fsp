---
name: submission-texts
description: Write submission form texts under character limits — title, short and long description, categories, technologies — counting every field and reporting n of limit, plus a social post series (idea, engineering, numbers) with 1080×1350 cards rendered from HTML in the product tokens. Use for a submission form, project description, LinkedIn or Telegram posts — «текст для сабмита», «описание проекта», «лимит символов», «пост в LinkedIn», «посты про проект», «карточки для постов», "submission text", "project description".
---

# Submission texts

Short texts that a juror reads before anything else. Same claims and numbers as the deck, fewer
words, and every field inside its limit.

## 1. Fields and limits

From `context/PLATFORM.md`: every field of the form with its minimum and maximum length,
language, and whether it can be edited after submission. Create `submission.md` next to
`SPEECH.md` with one section per field, the limit in the heading:

```markdown
## Title (limit 50)
## Short description (limit 255, min 50)
## Long description (limit 2000, min 600)
## Categories
## Technologies
## Links
```

## 2. Write

- **Title:** product name plus what it does, in the words a juror would search for.
- **Short:** what it is, for whom, the one mechanism that makes it different, one measured proof.
- **Long:** the problem with a sourced number → what the product does → how the key mechanism is
  enforced → what was measured, on what, against what → how to try it without logging in →
  limitations and what is synthetic → stack.
- Numbers exactly as in `evidence.md`, each with its sample; nothing the deck does not claim.
- No filler from the list in [AGENTS.md](../../../AGENTS.md); no internal paths or branch names.

## 3. Count

```bash
npm run chars -- submission.md
```

The script counts characters (Unicode code points, the way most forms count) and words per
section, compares with `limit` and `min` from the heading and exits non-zero on a violation.
Rewrite instead of truncating. Report each field as `n of limit` in the reply.

Done when: every field is within its limits, every number traces to `evidence.md`, every link
opens logged out.

## 4. Social post series

Three posts, by three team members, a few days apart:

| Post | Angle | Content |
| --- | --- | --- |
| 1. The idea | The problem and the rule | The failure the product prevents, why the usual defenses miss it, the one mechanism, the live link |
| 2. The engineering | How it is built | The invariant that makes it trustworthy, how it is tested, the bugs the checks caught |
| 3. The numbers | What was measured | The method, the results with their cost or limit, the number that was thrown out and why, what is not shown yet |

Each post: a first line that states a concrete claim, 120–250 words, one link to try it and one
to the code, at most six hashtags, the domain disclaimer if the topic needs one.

## 5. Cards

Five cards per post, 1080×1350, one idea per card, large type, the product tokens.

1. Copy [cards-template.html](cards-template.html) to `social/<n-name>/cards.html`.
2. One `<section class="card" data-name="1-short-name">` per card; a number card carries its
   source line.
3. `npm run cards -- social/1-idea/cards.html` writes `1-short-name.png` next to the HTML.
4. Look at every PNG at phone size; text under 28px at 1080 wide is too small.

Done when: each post has its text in `social/<n-name>/post.md` with the image order listed, and
the rendered cards match it.
