# Ход работ по фронтенду calibr

Снимок на 2026-10-09. План — [frontend-plan.md](frontend-plan.md), правила — [frontend-rules.md](frontend-rules.md).
Ничего не закоммичено: вся работа лежит в рабочей копии `main` (ветки нет, git — за пользователем).

## Как продолжить

1. Поднять стенд: бэкенд в docker (`POSTGRES_PORT=5433 KEYCLOAK_PORT=8081 docker compose up -d`, бэкенд на 8000),
   фронт `cd frontend && npx vite --port 5180` (порты 3000/5173/5432/8080 на машине заняты).
2. Проверки из `frontend/`: `npx tsc --noEmit -p .`, `npx biome check --write src`, `npm run rules --silent`
   (29 проверок), `npm run i18n:sync` после нового namespace в `src/shared/i18n/locales/{ru,en}/*.json`.
3. Скриншоты: `MSYS_NO_PATHCONV=1 node scripts/shots.ts --routes /a,/b --widths 1440,375 --themes light,dark
   --login employer@demo.example:demo-2026 --out <временная папка> --wait 1500`. Временные скрипты с
   кириллицей в `scripts/` ломают проверку `cyrillic` — держать их вне репо.
4. Демо: работодатель `employer@demo.example`, кандидаты `devops-middle@demo.example`,
   `devops-middle-fsp@demo.example`, пароль `demo-2026`. Свежий кандидат: `/api/auth/register` → письмо в
   mailpit `http://localhost:8025/api/v1/search?query=to:<email>` (в тексте `token=`) → `/api/auth/verify-email`.

## Тонкости, на которых уже спотыкались

- Bash heredoc с длинным текстом падает (`unexpected EOF`) — файлы писать через Write.
- `css-modules`: модуль импортирует только компонент из той же папки. Общее — `src/shared/styles/layout.module.css`
  (импорт относительным путём, переменная строго `styles`, иначе проверка не видит использование) или `composes:`
  из `compose.module.css` / `layout.module.css`. `composes` допустим только в селекторе из одного класса.
- `css-duplicates`: 3 одинаковые декларации в двух файлах — уже ошибка. Общие куски: compose-классы `cardFrame`,
  `cardRow`, `pill`, `bareFieldset`, `stale` (+`data-stale`), `displayText`, `traceArt`; layout-классы `formStep`,
  `enter`, `actions`, `split`, `stack`, `points`, `prose`, `preWrap`.
- `consistency`: в features/pages/entities/app нет сырых `<button>`, `<h2>/<h3>`, прокручиваемых контейнеров —
  `Button`/`PlainButton`, `Card`/`Pane`/`Section`, `ScrollArea`.
- `signal-scope`: `--data-*` только в `entities/measure` и `shared/ui/data-display`.
- Брейкпоинты только из списка (`30/48/64/75/90/120rem` и `N.99rem`); `@container` с `40rem` не прошёл.
- i18n: динамический ключ — шаблоном с namespace: ``t(`selection:status.${s}` as never)``.
- `--surface-option-active` пришлось переопределить в `[data-surface="inverse"]`: `var()` в `:root`
  резолвится светлой темой (было белое активное пятно в сайдбаре).
- В playwright плитки `ChoiceTiles` кликаются через `getByRole("radio").check({ force: true })`.
- Агентам и людям: общие файлы (`shared/ui/index.ts`, токены, `compose.module.css`, `common.json`) правятся точечно.

## Сделано

**Этап 0–1 (фундамент, публичные экраны)** — готово: токены двух тем, шрифты, примитивы `shared/ui`, 29 проверок,
главная, вход, регистрация, подтверждение адреса, 404, оболочка кабинета.

**Этап 2 (кандидат: путь и тест)** — готово:
- `/candidate/path` (было раньше), `/candidate/test` (`pages/candidate-test`, фича `features/test-session`:
  условие на графите, ответ выбором с цифрами 1–9, сортировкой с клавиатурой и `aria-live`, вводом моноширинным,
  Enter отвечает, липкая кнопка на телефоне, `SplitPane`), `/candidate/reveal` (`pages/candidate-reveal`,
  анимация только при `state.fresh` из `entities/candidate-path/reveal-state.ts`).
- Новые примитивы: `SortableList`, `Pane`, `PlainButton`, `Chip`, `Combobox`, `Tabs`, `Dialog size="drawer"`,
  `Menu iconOnly`, `RadioGroup appearance="card"` с `shortcut`, `useMoneyRange` в `shared/i18n`,
  `levelFrom`/`gradeAt` в `entities/measure`.

**Этап 3 (работодатель: подбор)** — моя часть, почти готово:
- Сущности: `entities/need` (CRUD, важность тем, разбор текста), `entities/selection` (подборка с дозагрузкой
  `useInfiniteQuery`, фильтры, шортлист, поиск, карточка кандидата, `anonymousId`),
  `entities/invitation/employer-invitation.queries.ts`.
- `/employer/needs` — список (`features/need-list`): строки с категорией, стеком, последней подборкой,
  «Построить/Перестроить», меню «Изменить/Удалить» с подтверждением.
- `/employer/needs/new`, `/employer/needs/:id` — мастер (`features/need-editor`): Trace (вертикальный от 120rem),
  шаги «Кого ищете», «Требования» (Combobox стека, таблица важности с Segmented и «Вернуть»), «Условия»;
  справа живая сводка. Черновик из текста приходит через `location.state.draft`, неуверенные поля помечены.
- `/employer/needs/text` — `features/need-text`: текст, стадии разбора, черновик или «нет в справочнике»
  с ближайшими специализациями.
- `/employer/selections/:id` — `features/selection-board` + `features/invite`: полоса состава, «Как считается»,
  фильтры (боковые от 120rem, иначе выезжающая панель), блоки выдачи с трассой-разделителем, строки с
  MatchScore/вероятностью/стеком/ФСП, звезда шортлиста, клавиатура (стрелки, S), объяснение справа
  (от 64rem, иначе выезжающая панель) с темами на `GradeRuler`, шортлист и сравнение до трёх, диалог приглашения
  с бюджетом. Выбранная строка — `?candidate=` в адресе.
- Маршруты — `src/app/routes/employer-hiring-routes.ts`.

## Осталось сделать (по порядку)

1. **Довести мою часть этапа 3:**
   - снять скриншот строки подборки после правки колонок (`result-row.module.css`, статус переносится);
   - починить `npm run rules` (на момент остановки 4 проверки красные, список ниже);
   - `/employer/candidates` — поиск по банку (`useCandidateSearch` уже есть): фильтры слева, строки без
     MatchScore, строчный GradeRuler, пустое состояние до выбора специализации и грейда (план §4.5);
   - `/employer/candidates/:id` — карточка (`useCandidateCard` есть): шапка, профиль по темам с TrustBadge,
     достижения ФСП, самоописание, стек, скрытое; контакты после принятия; справа `InviteAction` (план §4.6);
   - в nav у работодателя «Кандидаты» ведёт на `/employer/candidates` — слот для чат-поиска коллеги оставить
     на этой странице.
2. **Агенты** — см. их отчёты ниже: доделать недоделанное.
3. **Этап 6–8 плана:** обзор работодателя (если агент не закончил), токены для PDF/писем
   (`scripts/exportTokens.ts` не адаптирован), аудит (`impeccable` critique/audit/polish, review-animations),
   axe, адаптив 375/768/1440/1920, `npm run verify` зелёный, тест `usedKeys`, удалить `frontend/legacy/`,
   обновить `.claude/frontend-rules.md` (кавычки, lineWidth 100, структура GoatWhistle, список проверок),
   e2e сценарий защиты, `frontend/PRODUCT.md` и `DESIGN.md` для impeccable, Dockerfile на node ≥ 22.18.

## Красные проверки на момент остановки

- `css-duplicates`: мои — `need-row .row` / `importance-table .row` / `draft-result .field` / `topic-fit-row .row`
  (общий кусок: `display grid`, `border-block-end hairline`, `animation rise-in` + stagger — вынести в compose-класс
  строки списка), `need-summary .team` ↔ `vacancy-card .description` (вынести clamp в compose),
  `need-editor .actions` ↔ `vacancy-card .footer`; у агентов — `visibility-section .rules`, `skill-panel .fsp`,
  `answer-row .response`, `section-nav .link` ↔ `compose .listItem` и `tabs .tab`, `vacancy-drawer .group` ↔
  `radio-group .group`.
- `scale-tokens`: `importance-table` — `@container (max-width: 40rem)`; заменить на разрешённое значение
  или на `@media`.
- `consistency`: `compare-dialog .scroller` и `explanation-panel .panel` с `overflow` — перевести на `ScrollArea`.

## Агент А: кабинет кандидата (остановлен, отчёт получен)

tsc по проекту чистый, biome и rules по его файлам чистые. Глазами проверен только обзор (1440 и 375, обе темы).

**Готово:**
- `/candidate` (индекс, `pages/candidate-overview`, фича `features/candidate-overview`): категория с `GradeRuler`,
  попытка вверх, шаг вниз через «⋯» и подтверждение; профиль навыков с сортировкой и блоком по теме
  (`BlockButton` → `/candidate/test`); история таймлайном; обратная связь; последние приглашения; заполненность
  профиля. Без категории или во время блока ведёт на `/candidate/path`. Есть `CategoryGate` («нужна категория»
  с «Продолжить путь») — ещё ни к чему не подключён.
- `features/conversation`: `ConversationThread({ invitationId, side })` для обеих сторон, опрос 10 с только на видимой
  вкладке, Enter отправляет, Shift+Enter перенос, отметки «доставлено/прочитано».
- Сущности: `entities/profile` (профиль, резюме, PDF, ФСП, обратная связь), `entities/invitation/candidate-invitation.queries.ts`
  (+ `InboxStatusBadge`), `entities/vacancy/candidate-vacancy.queries.ts`, `entities/task/candidate-task.queries.ts`.
- Словари `overview`, `conversation`, `profile` полные; в `invitations` пока только `status.*`.

**Частично — `/candidate/profile`:** все секции `features/profile` написаны и компилируются (about, contacts, stack,
expectations, visibility, resume-drop, fsp-section, profile-preview, section-nav, `profile-draft.ts`,
`use-field-hint.ts`). Не хватает: сборщика `profile-editor` (состояние, сохранение, липкая панель «Сохранить/Отменить»,
`useBlocker` + `ConfirmDialog` с `common:leave.*`), плашек `?fsp=linked`/`?fsp_error=` (`errors:fsp.*`), кнопки PDF,
раскладки в три панели (на <90rem превью в `Dialog`), `features/profile/index.ts`, `pages/candidate-profile`, маршрута.
`FspSection` берёт проп `linkAction`: страница передаёт `<FspSignIn intent="link" ... />` (фича не импортирует `features/auth`).

**Не начато:** `/candidate/invitations[/:id]` (детали из списка, при `sent` вызвать `view`), `/candidate/vacancies[/:id]`
(деталь в `Dialog size="drawer"` по id из списка), `/candidate/tasks` (подключить `CategoryGate`), словари
`vacancies`, `tasks`, полный `invitations`. Запросы для всех трёх уже есть.

**Общие файлы:** `TextArea` (+`onKeyDown`, `hideLabel`), токены `--thread-*`, `--dropzone-min-height`,
compose-класс `.ruledRow`. **`compose.module.css` ровно 250 строк** — новые общие классы класть в новый модуль
в `shared/styles/`.

**Тонкости от агента:** ключ чужого namespace (`t("common:...")` из `useTranslation("x")`) не типизируется — брать
отдельный `useTranslation()`; дата повтора — в `ApiError.detail`, читать `availableAt()` из
`features/candidate-overview/available-at.ts`; фон `--surface-*` + `--radius-inner/card` + padding `consistency`
считает самодельной карточкой — для пузырей `--radius-button`; Python на Windows пишет CRLF — после правок скриптом
`biome check --write`; у демо-кандидатов нет приглашений, вакансий и заданий — завести от `employer@demo.example`.

## Агент Б: рабочие разделы работодателя (остановлен, отчёт получен)

tsc 0 ошибок, biome по его папкам чистый, в rules его нарушений нет. **После доработки ни один его экран не
снят на скриншоте** (ни в обеих темах, ни на 375) — первое, что сделать. Демо-данных приглашений, откликов,
вакансий и заданий в базе нет — заполненные состояния вживую не проверены.

**Готово (маршруты в `employer-desk-routes.ts`):**
- `/employer` — `pages/employer-overview`, `features/employer-overview`: без компании одна задача `CompanyTask`,
  иначе `MetricsRow` (бюджет мини-полосой с датой обновления, новые отклики, новые сообщения); сетка `NeedsPanel`
  (категория, стек, последняя подборка, «Открыть подборку», «Перестроить»), `ActivityPanel`, `AttentionPanel`.
- `/employer/invitations[/:id]` — вкладки и раскладка «список + деталь», `features/employer-invitations`
  (`InvitationList`, `InvitationDetail`, переписка через слот `conversation` после принятия) и `features/applications`
  («Открыть профиль и контакты» → отмечает просмотренным и ведёт на `/employer/candidates/:id`; «Принять/Отклонить»
  с подтверждением). Адрес: `?tab=applications&application=<id>&vacancy=<id>`.
- `/employer/vacancies` — `features/vacancy-editor`: вкладки «Опубликованные/Снятые» (`?tab=archived`), `VacancyCard`,
  `VacancyDrawer` (Select, формат плитками с мультивыбором, обязательная вилка, баннер при `company_required`).
- `/employer/tasks` — `features/task-editor`: фильтр активные/ждут оценки/снятые (`?filter=review`), `TaskDrawer`
  (темы Combobox, «выбрано N из 3»), `TaskCard` с ответами в Disclosure, рубрика 0–3, оценка с подтверждением.
- Сущности: `entities/company`, `entities/application`, `entities/vacancy/employer-vacancy.queries.ts`,
  `entities/task/employer-task.queries.ts` (`useAwaitingReview`), в `entities/invitation` — `InvitationBudget`,
  `InvitationStatusBadge`, `isOpenStatus`, `candidateTag`. Словари `employer`, `applications`, `vacancyEditor`, `taskEditor`.

**Не начато:** `/employer/company` (форма + превью «Как вас видит кандидат»): `entities/company` готова, нет словаря
`company`, `features/company-profile`, `pages/employer-company`, маршрута. Пункт в меню пользователя уже есть.

**Общие файлы:** новые примитивы `shared/ui/layout/list-row` (`ListRow`) и `shared/ui/data-display/terms` (`Terms`),
`ChoiceTiles` — проп `selected` для мультивыбора, compose-классы `.linkRow`, `.footnote`, `.fieldPair`.

**Тонкости от агента:** чужой namespace — `useTranslation(["x", "common"])` и `t("common:...")`; выезжающие панели
перемонтируются через `key={editing.session}` (сброс формы без потери анимации закрытия); статусы откликов —
`employer:status.application.*`, приглашений — `employer:status.invitation.*`; тела страниц вынесены в
`vacancy-grid`/`task-grid` из-за лимита сложности biome (15).

## Свести при продолжении

- **Два формата анонимного ID:** мой `anonymousId` (`entities/selection`, `#` + 6 символов) и `candidateTag`
  (`entities/invitation`, 8 символов). Оставить один (лучше в `entities/selection` или отдельной сущности
  `candidate`) и заменить везде — работодатель должен видеть одного кандидата одинаково в подборке, приглашениях
  и откликах.
- Статусы приглашений описаны трижды: `selection:status.*` (мой `InviteAction`), `employer:status.invitation.*`
  (`InvitationStatusBadge`), `invitations:status.*` (кандидат). В `InviteAction` перейти на `InvitationStatusBadge`.
- Порядок работы дальше: (1) красные rules, (2) скриншоты экранов агента Б и моей подборки, (3) `/employer/candidates`
  и `/employer/candidates/:id`, (4) `/employer/company`, (5) профиль кандидата, (6) приглашения, вакансии, задания
  кандидата, (7) этапы 6–8 плана.

## Дополнительно

- Ссылки `/candidate/profile#fsp` с обзора уже стоят: у секции ФСП в профиле должен быть `id="fsp"`.
- `ConversationThread` пока подключён только у работодателя; у кандидата — на экране приглашений, когда он появится.
- Про ключи чужого namespace агенты пишут разное: у одного работает `useTranslation(["x", "common"])` + `t("common:...")`,
  у другого — отдельный `useTranslation()`. Оба варианта компилируются, если namespace указан в массиве.
- В `features/test-session` и подборке `review-animations` ещё не проходили.
- Оба агента остановлены 2026-10-09; их транскрипты в этой сессии, продолжать по этому файлу.

## Проверки на момент остановки

`npx tsc --noEmit -p .` — 0 ошибок. `npm run rules` — 3 красные проверки (`css-duplicates` 6, `scale-tokens` 1,
`consistency` 2), все в моих файлах этапа 3 и в `compose.module.css`/`tabs`/`radio-group`, список выше.
`npx biome check src` — единственная ошибка: `src/.impeccable/hook.cache.json` (кэш хука impeccable, его формат).
Добавить `.impeccable` в исключения `frontend/biome.json` и в `.gitignore`.

## Сессия 2 (2026-10-09, вторая половина дня)

Работаю я + два агента: **А** — кабинет кандидата (профиль, приглашения, вакансии, задания, скриншоты),
**Б** — работодатель (демо-данные, `/employer/company`, скриншоты и полировка обзора, приглашений, вакансий,
заданий, `review-animations`).

Сделал я:
- `npm run rules` 29/29: общий модуль `shared/styles/rows.module.css` (`listRow`, `listRowCompact`), таблица
  важности без колонки «Вернуть» (кнопка в строке темы, `@container (max-width: 29.99rem)`), прокрутка в объяснении
  и сравнении через `ScrollArea`.
- `.impeccable` исключён в `biome.json` (`!**/.impeccable`) и в корневом `.gitignore`.
- Обезличенный ID один: `anonymousId` в `@/shared/api` (`#` + 6 символов); `candidateTag` делегирует в него.
  Статус приглашения в `InviteAction` — `InvitationStatusBadge`; ключи `selection:status.*` удалены.
- Мобильная оболочка: `AccountMenu iconOnly` в шапке, нижняя навигация не наезжает (`min-inline-size: 0`).
- Строка подборки двухъярусная (ID и статус + соответствие, ниже факты), колонка действий фиксирована
  `--row-actions`; бейдж статуса заменён на `IconLabel`.
- `/employer/candidates` — `features/candidate-search` (фильтры в адресе `?spec=&grade=&stack=&fsp=1&confident=1`,
  пустое состояние до выбора категории, строки с `GradeRuler`, вероятностью грейда, ФСП, приглашением и карточкой).
- `/employer/candidates/:id` — `features/candidate-card` (навыки `SkillList`, ФСП с подробностями после раскрытия,
  самоописание через `Terms`, скрытые поля, контакты после принятия, сводка уровня и приглашение справа).
- Словари `search`, `card`; лишние ключи убраны из `selection`, `need`, `card`, `test`, `measure`.
- Тесты: `usedKeys` переписан (учитывает namespace файла из `useTranslation`, массивы, шаблоны),
  `motionTokens` разрешает `stroke-dashoffset` как и проверка проекта. Осталось: неиспользуемые ключи в
  `common`, `auth`, `errors` — чистить в конце, когда агенты допишут.
- Этап 7: `npm run tokens:export [папка]` (по умолчанию `frontend/dist-tokens`) собирает `tokens.css`
  (с `@font-face` Onest и JetBrains Mono, файлы шрифтов рядом в `fonts/`) и `tokens.json` (71 цвет светлой
  темы в hex, имена шрифтов). **Задача бэкенду:** PDF-профиль (`backend/app/adapter/profile_pdf.py`, сейчас
  PT Sans и свои цвета) и письма (`mail.py`) перевести на `tokens.json` и эти шрифты; шапка с локапом,
  `GradeRuler` в SVG по тем же порогам, язык по языку пользователя.
- `frontend/PRODUCT.md`, `frontend/DESIGN.md` написаны; `.claude/frontend-rules.md` обновлён под фактическое
  устройство (Biome, структура, общие модули стилей, список проверок).
- Dockerfile фронта на `node:22-alpine`.
- Анимации: лесенка ограничена 8 шагами (`staggerStyle`), `Spinner delayed` (появляется через
  `--delay-spinner`), кнопка «Пригласить» сменяется статусом через `Swap`.

## Агент Б, сессия 2: готово (отчёт получен)

- Демо-данные: скрипт вне репо `C:\Users\MIKHAI~1\AppData\Local\Temp\claude\w--Projects-hacks-new-lct\34bde4ff-bffe-4921-a30f-9a93b1476a3c\scratchpad\seed-employer.mjs`
  (повторный запуск без дублей): профиль «Демо-Технологии», 4 вакансии (3 опубликованы, QA снята), 2 задания
  devops/middle, приглашения (принято с перепиской у `devops-middle`, просмотрено у `devops-middle-fsp`, ещё одно
  отправлено), отклики обоих кандидатов на DevOps, ответы на задания (2 ждут оценки).
- `/employer/company` — `features/company-profile` + `pages/employer-company`: форма, живое превью «Как вас видит
  кандидат», статус сохранения, «Вернуть как было», `useBlocker` + `ConfirmDialog`. Бэкенд отдаёт кандидату пока
  только `company_name` — превью показывает целевой вид (**задача бэкенду**: отдавать кандидату сферу, описание, сайт).
- Полировка по скриншотам 1440/1920/375 обеих тем: обзор, приглашения и отклики, вакансии, задания (фильтр на `Tabs`),
  горизонтальной прокрутки на 375 нет.
- Общие правки: `ScrollArea` пересчитывает затухания по `onAnimationEnd`; у `Card .heading` `flex: 1 1 var(--tile-min-compact)`
  (действия не уезжают); новый `shared/styles/feedback.module.css` (`.fieldError`), `Field` берёт ошибку оттуда.
- Хвосты: `review-animations` не проходил (скилл вызывается только пользователем); `Select` без иконки в плейсхолдере;
  плитки формата в вакансии высокие (общий `ChoiceTiles`).
- Псевдоним в ответах на задания бэкенд делает свой на каждое задание намеренно (ответы не сводятся в одного человека);
  на фронте показывается как `#XXXXXX` (`answer-row.tsx`), русское «Кандидат» из строки бэкенда отброшено.

## Агент А, сессия 2: готово (отчёт получен)

- Маршруты кандидата: `profile`, `invitations/:id?`, `vacancies/:id?` (вкладка «Мои отклики» `?tab=applications`), `tasks`.
- Профиль: `profile-editor` + `use-profile-editor.ts`, липкая `save-bar`, `leave-guard` (`useBlocker` + `beforeunload`),
  `fsp-return` (`?fsp=linked`, `?fsp_error=`), `pdf-button`; раскладка навигация + форма + превью (на <90rem превью в
  `Dialog`). Опыт работы (lct-92): `experience.ts`, `experience-section`, `entry-drawer`, `month-field`, годы по
  технологиям в превью.
- Приглашения кандидата (список и деталь, `view` при `sent`, принять/отклонить/отозвать с подтверждением, переписка),
  вакансии (фильтры, деталь в панели, отклик с подтверждением), регулярные задания (вкладки, ответ с подтверждением).
- Общие правки: **`Dialog` оборачивает содержимое в `LayerHost`** (выпадающие списки внутри диалогов раньше рисовались
  под ним), типы `ExperienceEntry*`, `TechnologyYears` в `shared/api/types.ts`, новый `shared/styles/blocks.module.css`
  (`.tintBlock`), композер переписки на <48rem — поле на всю ширину.
- Хвосты: на обзоре кандидата в 1440 пустота ~60px между «Что поднимет выше» и «Приглашения» (строки сетки);
  `OwnAnswer` без балла — пишется просто «оценён».

## Подтянуто из main (коллега, lct-92 «карточка опыта»)

Fast-forward до `12cb457`. Старые файлы фронта из этого PR (`src/api`, `src/candidate/*`, `ExperienceEditor`,
`ExperienceCard`, `styles.css`) перенесены в `frontend/legacy/` как образец; схема API перегенерирована, бэкенд
пересобран. Перед своим PR — смотреть, что нового в main по фронту, и переносить так же.

## PDF и письма в фирменном стиле (бэкенд, моё)

- `backend/app/adapter/brand/`: шрифты Onest (400/500/600) и JetBrains Mono (400/500/700) статичными TTF с OFL,
  `tokens.json` и `catalog.{ru,en}.json` из фронта (`npm run tokens:print` во `frontend/`), `fsp-mark.svg`,
  словари `words/{ru,en}.json` (все тексты PDF и писем), `words.py` (`Words`: ключи, справочник по коду, даты,
  склонение лет), `palette.py` (цвета токенов, альфа поверх белого), `pdf_kit.py` (документ с локапом и подвалом,
  секции с трассой, плашки, шкала грейдов по порогам `Level.thresholds`, слова уровня), `mail_templates.py`
  (`BrandMailTemplates`: текст + HTML с фирменной кнопкой).
- `profile_pdf.py` переписан на этот набор; язык — `GET /api/candidate/profile/pdf?lang=ru|en`.
- Письма: порт `MailTemplates` (`usecase/interface.py`), `Accounts` получает шаблоны, `Mail.html`, SMTP шлёт
  `multipart/alternative`; язык — поле `locale` в `RegisterIn` и `ResendVerificationIn`. Тексты ушли из домена
  (`verification_mail` удалён). Фронт передаёт текущий язык при регистрации, повторном письме и скачивании PDF.
- PT Sans удалён; тестовые резюме (`tests/resumes.py`) набираются Onest. Новые тесты `tests/test_brand.py`.
- Бэкенд: ruff и mypy чистые, 2557 тестов проходят; 4 падения — только на Windows (разделитель путей и перевод
  строк в `test_synthetic_market.py`, `test_validation_stand.py`), к этой работе не относятся.

## Состояние на конец сессии 2

Фронт: `tsc` 0, `biome check src scripts` 0, `vitest` 392/392, `npm run rules` 29/29, `vite build` собирается.
`i18n:sync` теперь делает `biome check --write` (сортирует импорты в `resources.ts`).

Осталось: удалить `frontend/legacy/` (после переноса нужного); axe и e2e-сценарий защиты; скриншот-проход
всех экранов после правок агентов (особенно обзор кандидата в 1440); `review-animations` (вызывает пользователь
командой `/review-animations`); презентация и отчёт валидации на `npm run tokens:export`.

## Сессия 3 (финал)

- `frontend/legacy/` удалён (старые файлы — в истории git), исключение из `biome.json` убрано.
- e2e: `@playwright/test`, `@axe-core/playwright`; `frontend/playwright.config.ts` (системный Chrome, EN-интерфейс,
  `E2E_BASE_URL`, по умолчанию `http://localhost:5180`), `npm run e2e`.
  - `e2e/axe.spec.ts` — 18 экранов публичных, кандидата и работодателя, обе темы, без serious/critical нарушений WCAG 2.1 AA.
  - `e2e/defense.spec.ts` — сценарий защиты §10.1: язык туда и обратно в тёмной теме; регистрация по почте через
    Mailpit, вход, направление, грейд, три задания теста; вход через ФСП ID (`fsp-winner`, Keycloak) с достижениями;
    обзор кандидата с категорией; потребность словами, черновик, подборка, «Как считается», объяснение, шортлист,
    диалог приглашения; принятие приглашения и переписка, контакты у работодателя; отклик на вакансию;
    скачивание PDF. Сценарий идемпотентный: повторные прогоны не ломаются о состояние демо-данных.
  - `e2e/support.ts`: `settle(page)` ждёт конца конечных анимаций на документной шкале (переходы между
    экранами иначе съедают клики); ссылка из письма берётся относительной (бэкенд пишет `FRONTEND_URL`).
- Кириллица в e2e запрещена правилом проекта — селекторы по английскому интерфейсу и позиции.
- README: устройство фронта, `npm run verify`, `npm run e2e`, `npm run tokens:print`.
- `npm run verify` зелёный целиком (29 правил, типы, Biome, 392 теста, сборка).
- **Перед защитой:** пересобрать контейнер фронта (`docker compose up -d --build frontend`) — на `:3000` сейчас
  старая сборка, а вход через ФСП ID возвращает именно туда.

## Итог (2026-10-09, конец сессии 3)

Финальный проход агентов: работодатель (выравнивание строк через subgrid, плитки мастера `layout="inline"`,
фокус строки подборки, панель объяснения на узкой ширине, термины EN: shortlist и favorites) и кандидат с
публичными экранами (сетка обзора стопками, липкие блоки под реальную шапку через `--sticky-top`, короткие подписи
нижней навигации `common:navShort.*`, разряды в `NumberField`, падежи грейда в RU, 404 с верхней панелью).
Я перевёл липкие блоки работодателя на `--sticky-top`, заголовок ленты обзора работодателя — «Активность».
Тесты словарей читают только `*.json` (кэш `.impeccable` больше не ломает их).

Контейнер фронта пересобран: `:3000` — новая сборка, вход через ФСП ID возвращает туда.

Проверки: фронт `npm run verify` зелёный (29 правил, типы, Biome, 392 теста, сборка); `npm run e2e` на продовой
сборке (`E2E_BASE_URL=http://localhost:3000`) — 14/14 (axe обе темы + сценарий защиты); бэкенд ruff, format, mypy
чистые, 2557 тестов проходят, 4 падения только на Windows (пути и переводы строк в тестах стенда валидации).

Вне фронта и не сделано: презентация и отчёт валидации на `npm run tokens:export`; `review-animations` запускает
пользователь (`/review-animations`); названия компаний и вакансий в EN — данные бэкенда.
Ничего не закоммичено — коммиты и PR делает пользователь.
