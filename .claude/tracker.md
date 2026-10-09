# Issue tracker: GitHub Issues

Issues и спеки живут в `https://github.com/GoatWhistle/lct-fsp-hack/issues`. Все операции — через
MCP-сервер **`github`**; во всех вызовах `owner: GoatWhistle`, `repo: lct-fsp-hack`. Кто работает
в сессии — `get_me` (логин нужен для assignee).

Issues рабочие, **перед сдачей удаляются**. Отсюда два правила:

- долговечное (замысел, решение, критерий готовности) — в репо: `docs/`, карточка
  `tasks/lct-<id>.md`, если она есть; issue ссылается на док, док на issue не ссылается;
- `#N` живёт только внутри issues и в описаниях PR — в коммитах, коде и docs задачу называть
  `lct-<id>` (хук `commit-msg` это проверяет).

Текст issues и комментариев — по-русски, без подписей и дисклеймеров об авторстве
(см. «Без следов ИИ-агентов» в `AGENTS.md`).

## Операции

- **Создать**: `issue_write` `method: create` (title, body, labels). Незнакомый лейбл GitHub
  создаёт сам при навешивании.
- **Прочитать**: `issue_read` `method: get` + `method: get_comments`.
- **Список**: `list_issues` (`state`, `labels`); по тексту — `search_issues`.
- **Комментарий**: `add_issue_comment`.
- **Лейблы, title, body, assignee**: `issue_write` `method: update`. `labels` заменяет весь
  набор — передавать полный список.
- **Закрыть**: комментарий с итогом, затем `issue_write` `update` `state: closed` с
  `state_reason` (`completed` / `not_planned` / `duplicate`).

## Лейблы триажа

Канонические роли скилов 1:1: `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`; категории `bug` / `enhancement`. У триажированного issue ровно
один лейбл состояния и один категории. Спека (`to-spec`) дополнительно несёт лейбл `spec`.
**PR как поверхность запросов: нет** — команда своя, триаж читает только issues.

## Когда скил говорит

- **«publish to the issue tracker»** — `issue_write` `create`.
- **«fetch the relevant ticket»** — `issue_read` `get` + `get_comments` по номеру.
- **«parent issue»** — спека; тикеты из неё — нативные sub-issues спеки
  (`sub_issue_write` `add`) и раздел `## Parent` в теле.

## Блокирующие связи

Строка в начале тела: `Blocked by: #12, #14` или `Blocked by: none (can start immediately)`.
Разблокирован, когда все перечисленные закрыты. Источник правды — эта строка.

Следом идут производные строки `Блокирует: #…` и `Порядок: волна N из M[, критический путь]`,
в спеке — раздел «Порядок работ» с волнами. Те же связи продублированы нативно
(`dependencies/blocked_by`, sub-issues спеки в порядке волн). Правка `Blocked by:` — пересчитать
производные строки у затронутых issues, раздел спеки и нативные связи.

## Ветки и PR

**Один issue — одна свежая сессия и свой worktree.** Параллельные сессии не делят рабочую
копию, а в контексте нет чужих issues.

1. Worktree от свежего `main` (`EnterWorktree`, ляжет в `.claude/worktrees/` — он в игноре),
   ветка `feat/<slug>` — без номера issue: имя ветки попадает в merge-коммит и переживает
   чистку истории. Хуки в worktree работают сами — `core.hooksPath` общий на репо.
2. Коммиты в ветку, push ветки.
3. PR в `main` — `create_pull_request`, `Closes #N` в описании: GitHub закроет issue при мерже.
4. Мерж — через PR; worktree после мержа убрать (`ExitWorktree`).

Прогресс и решения по ходу — комментариями в issue, не в чате сессии.

## Wayfinding operations

Для `/wayfinder`. **Карта** — issue с лейблом `wayfinder:map`, тело — Notes /
Decisions-so-far / Fog. Дети — нативные sub-issues: `issue_write` `create` с
`parent_issue_number: <map>`; порядок — `sub_issue_write` `reprioritize`. Лейблы детей:
`wayfinder:research` / `wayfinder:prototype` / `wayfinder:grilling` / `wayfinder:task`.

- **Frontier**: `issue_read` `get_sub_issues` карты → открытые, без открытых блокеров и без
  assignee; первый по порядку.
- **Claim**: `issue_write` `update` `assignees: [<логин из get_me>]`.
- **Resolve**: комментарий с ответом → закрыть → дописать указатель в Decisions-so-far карты
  (`issue_write` `update` body карты).
