# Скилы mattpocock/skills

Скилы `to-spec`, `to-tickets`, `triage`, `implement`, `grilling`, `domain-modeling`,
`wayfinder`, `grill-with-docs`, `diagnosing-bugs`, `resolving-merge-conflicts`, `research`,
`prototype`, `codebase-design`, `improve-codebase-architecture`, `handoff`,
`writing-for-agents`, `grill-me`, `tdd` — вендоренная копия из
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT, © Matt Pocock),
коммит `3cca18b368ae95cdbdebbff572ccafa662551015` (2026-09-04). Копия снята с
lct-hack вместе с `orchestrate-issues` (свой скил, не апстрим); из `triage` убран обязательный
AI-дисклеймер.

Скилы трекер-агностичны; настройку, которую обычно пишет `setup-matt-pocock-skills`,
заменяет раздел «Скилы, хуки, сдача» в `AGENTS.md`:

- трекер — GitHub Issues через MCP `github`, операции и лейблы — `.claude/tracker.md`;
- доменные доки — `AGENTS.md` и `docs/`.

Обновление: скачать нужные файлы с нового коммита тем же списком и поднять SHA здесь.
Каталоги `agents/openai.yaml` не тащим — это конфиги для Codex.

## Скилы для фронтенда

Вендорены в `.claude/skills/` и нужны при работе в `frontend/` (см. `.claude/frontend-rules.md`):

- `impeccable` — [pbakaus/impeccable](https://github.com/pbakaus/impeccable) v4.5.2
  (Apache 2.0), коммит `d631a8827f99414d2b6daba4ef08b7f8701751d7` (2026-10-10);
- `ui-ux-pro-max` — [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
  (MIT), копия из установленного плагина;
- анимации: `emil-design-eng`, `review-animations`, `improve-animations`,
  `find-animation-opportunities`, `animation-vocabulary`.

Правила `.claude/frontend-rules.md` сильнее рекомендаций этих скилов.
