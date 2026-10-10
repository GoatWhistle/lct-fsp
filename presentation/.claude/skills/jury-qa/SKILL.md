---
name: jury-qa
description: Prepare answers to jury questions in QA.md — each with a one-sentence answer, proof, limitation and owner — plus the uncomfortable questions, the answering protocol and a red-lines table (don't say / say instead). Use for Q&A prep, likely questions, objections or rehearsing answers — «вопросы жюри», «что спросят», «ответы на вопросы», «неудобные вопросы», «красные линии», «как отвечать», "Q&A prep".
---

# Jury Q&A

Q&A is scored as part of the defense, and one confident wrong answer undoes a slide of evidence.
Every answer here is built from `evidence.md`; what is not there is answered as not measured.

## 1. Collect questions

Generate questions from each source and write them into `QA.md`, merging duplicates:

- Each criterion in `context/requirements.md`: «как вы это измерили», «почему это хорошо».
- Each number on a slide: where it comes from, on what sample, compared to what.
- Each `[HONEST]` and `[DO NOT SHOW]` marker in `plan.md`.
- Each design choice on the architecture slide: «почему не {{очевидная альтернатива}}». Skill
  `competitors` for questions about existing solutions.
- The organizer memo and `context/QA.md` (organizer answers): every constraint the jury will check.
- The usual set: data and privacy, external services, reproducibility, scale (measured numbers
  only), cost, who the user is, what is not done, what a week more would bring, how AI tools were
  used in development, each person's contribution.

Done when: every criterion, every slide number and every marker has at least one question.

## 2. Answer format

```markdown
### N. {{Question as the juror would ask it}}
- **Short answer:** one sentence that answers the question.
- **Proof:** the number, screen, file or test that backs it, with its `evidence.md` row.
- **Limitation:** where the answer stops being true.
- **Owner:** who answers.
```

The short answer comes first, the proof second, in under 30 seconds. «Не измеряли» followed by what
is known beats any estimate.

## 3. Uncomfortable questions

List the 5–10 questions that hurt most: a weak metric, a missing feature, a constraint that was
bent, a number that changed between versions. Each gets an honest answer in the same format. The
single most damaging one is pre-empted on a slide or in the speech.

## 4. Red lines

Fill the table `Don't say | Say instead` with the phrasings that overclaim: «заменяет»,
«гарантирует», «всегда», «уже в проде», «масштабируется», an in-sample metric presented as general,
a planned feature as done. Each row gives the exact honest replacement.

## 5. Owners and protocol

- Every question has an owner and a backup; topics map to who built the part.
- The owner answers; others add only when handed the word.
- A question nobody can answer: «Не знаем, проверим и пришлём», then a follow-up in the chat.

## 6. Drill

Someone outside the topic asks ten random questions from `QA.md` and three new ones; time each
answer. Rewrite answers that took over 30 seconds or started with context instead of the answer.

Done when: every question has an owner, every answer has proof or an explicit «не измеряли», and
the drill ran once with all speakers.
