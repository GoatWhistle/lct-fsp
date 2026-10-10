# Международные платформы оценки технических навыков и подбора разработчиков (по состоянию на октябрь 2026)

Метод и ограничения: поиск через WebSearch (возвращает сводки со ссылками), сами страницы целиком не открывались. Почти все цифры — маркетинговые заявления вендоров; независимых аудитов найдено не было. Фразы "не найдено" означают отсутствие в выдаче, а не доказательство отсутствия у продукта. Утверждения без URL помечены как непроверенные.

## 1. Какие продукты, адаптивность (IRT), погрешность оценки

### Takeaway
Из найденного явная методология "framework + психометрия" есть у CodeSignal и TestGorilla; адаптивность на основе вопросов у Triplebyte досталась Karat. Публикации оценки с погрешностью по темам (как наш профиль "уровень ± погрешность") не найдено ни у одного вендора. Это наше потенциальное отличие.

### Cited Findings
- CodeSignal: Certified Evaluations строятся на Skills Evaluation Frameworks (blueprint содержания), написаны экспертами и валидированы IO-психологами; вопросы варьируются между кандидатами против плагиата — [CodeSignal framework paper](https://discover.codesignal.com/rs/659-AFH-023/images/General-Coding-Framework-Technical-Research-Paper-CodeSignal.pdf), [блог о frameworks](https://codesignal.com/blog/skills-evaluation-frameworks/), [certified assessments](https://codesignal.com/certified-assessments/)
- CodeSignal заявляет: 2 800 часов исследований на каждую Certified Assessment, модели скоринга на 3+ млн data points; Talent Science делает мониторинг и adverse impact analyses (заявления вендора, без независимой проверки) — [CodeSignal press release](https://codesignal.com/newsroom/press-releases/codesignal-expands-library-of-certified-evaluations-to-meet-growing-demand-for-validated-and-reliable-technical-assessments/)
- CodeSignal: ограничение 70 минут названо в техстатье как фактор валидности (меньше времени на поиск ответов) — [General Coding Framework paper](https://discover.codesignal.com/rs/659-AFH-023/images/General-Coding-Framework-Technical-Research-Paper-CodeSignal.pdf)
- Karat купила адаптивную assessment-технологию Triplebyte (16 марта 2023); сорсинговый бизнес Triplebyte (Magnet) и сеть кандидатов закрыты с 31 марта, профили и оценки кандидатов недоступны; Karat заявляет, что она заменяет автотесты с "высоким drop-off и низкой предсказательностью" (оценка вендора) — [Karat](https://karat.com/karat-acquires-leading-adaptive-assessment-technology-from-triplebyte/), [BusinessWire](https://www.businesswire.com/news/home/20230316005225/en), [citybiz](https://www.citybiz.co/article/393235/karat-acquires-leading-adaptive-assessment-technology-from-triplebyte/)
- TestGorilla заявляет мониторинг надёжности (внутренняя согласованность), content/construct/criterion validity и fairness (DIF, adverse impact), результаты — в fact sheet каждого теста — [TestGorilla assessments technology](https://www.testgorilla.com/assessments-technology/), [science](https://testgorilla.com/blog/science)
- Turing: стандартизованные тесты + AI-матчинг; заявлено, что полный отбор проходят <2% (методология не опубликована). Toptal: "top 3%" (заявление компании, многоэтапно, ручные интервью). Andela: AI-матчинг + ручная проверка специалистами; публичной ставки нет — сравнительные обзоры (вторичные): [fast.io Turing review](https://fast.io/resources/turing-ai-review-2026/), [Flexiple Toptal vs Turing](https://flexiple.com/compare/toptal-vs-turing), [futureproofing Andela vs Turing](https://www.futureproofing.dev/resources/ai-staffing-comparison/andela-vs-turing-2026)

### Inferences
- Ни у одного найденного вендора не видно публичного "уровень ± SE по темам" и категории специализация × грейд; наш IRT-профиль с погрешностью — отличие, но требует эксперимента на стенде (см. правило репо о утверждениях о качестве).
- "Top X%" у Toptal/Turing — отбор по воронке, а не измерение с доверительным интервалом.

### Gaps
- HackerRank, Codility, Coderbyte, Qualified, Woven, Devskiller, Gloat, SeekOut: данных об IRT/адаптивности в выдаче нет. Из общих знаний (непроверено, без источника): классические платформы используют фиксированные наборы задач и автопроверку кода, а не IRT.
- Использует ли CodeSignal IRT формально — поиск не подтвердил (непроверено).

## 2. Античит, прокторинг, плагиат, утечка вопросов

### Takeaway
Рынок решает проблему детектированием поведения (прокторинг, similarity, телеметрия, AI-детекторы), а не устойчивостью самой механики к утечке. Независимых оценок точности детекторов нет; рост мошенничества с AI подтверждается только данными самого вендора.

### Cited Findings
- HackerRank: AI Plagiarism Detection (проприетарные модели на данных HackerRank; поведение кандидата, эволюция кода, сходство решений). Заявлена точность 93% в блоге и 85–93% precision в другой статье HackerRank (оба источника вендорские). Proctor Mode (с июля 2025): алерты смены вкладок, мульти-монитор, replay сессии, image analysis; Secure Mode и Desktop App Mode (мониторинг на уровне ОС) — [HackerRank KB: AI Plagiarism Detection](https://hackerrank-knowledge-base.help.usepylon.com/articles/7287334157-ai-plagiarism-detection), [Proctor Mode](https://hackerrank-knowledge-base.help.usepylon.com/articles/5663779659-proctor-mode), [блог о детекции ИИ-помощи](https://www.hackerrank.com/writing/can-proctor-mode-detect-%63hatgpt-hackerrank-2025-ai-plagiarism-engine)
- Codility: проверка сходства с решениями других кандидатов, совпадение поднимает Integrity Risk до High; заявлено 10+ лет и 12+ млн assessments; вывод — "decision support, а не вердикт", флаг не доказательство — [Codility Anti-Cheating Methods](https://support.codility.com/hc/en-us/articles/360043319434-Anti-Cheating-Methods), [Codility Proctoring](https://www.codility.com/1p/codility-proctoring-integrity/), [Codility IP check blog](https://codility.com/blog/enhanced-fraud-prevention-in-codecheck-with-ip-check). Утверждение об AST-парсинге — только сторонний пост, непроверено: [DEV Community](https://dev.to/christofer-001/inside-codilitys-integrity-stack-event-tracking-ast-parsing-and-native-bypasses-3afj)
- CodeSignal: Suspicion Score по сходству решений, телеметрии, copy-paste и паттернам AI-помощи; запись видео/аудио/экрана, комбинация AI-ревью и человека; встроенный AI-ассистент Cosmo в IDE. Данные вендора (февраль 2026): доля попыток мошенничества в проктореных оценках выросла с 16% (2024) до 35% (2025) — [CodeSignal cheating and fraud](https://codesignal.com/cheating-and-fraud/), [prevent and detect cheating](https://codesignal.com/blog/prevent-and-detect-cheating-in-recruiting/), [оценка с ИИ-помощью](https://codesignal.com/blog/can-%63hatgpt-pass-a-codesignal-assessment/)
- iMocha и Mettl: снимки с вебкамеры, трекинг выхода из окна, IP-ограничения, блок copy-paste/print screen; сравнения написаны самой iMocha — [iMocha vs Mettl](https://blog.imocha.io/mettl-alternatives), [Capterra iMocha](https://www.capterra.com/p/132140/iMocha/reviews)
- Академически: детекторы плагиата обходятся автоматической обфускацией (общий результат, не про конкретного вендора) — [KIT](https://publikationen.bibliothek.kit.edu/1000191756/179040705)

### Inferences
- Прямого аналога "модель угроз утечки вопросов + валидация против атакующего-LLM с опубликованными метриками" в выдаче нет; все публикуют лишь вендорские цифры точности детекции или долю мошенничества.
- Тезис "подбор, который нельзя накрутить" можно сопоставлять с заявлениями 93% (HackerRank), но методологии сравнимости нет.

### Gaps
- Нет данных по Woven, Qualified, Devskiller, Coderbyte, TestGorilla по античиту.
- Нет независимых оценок false positive/negative ни у одного вендора.
- Как именно вендоры работают с утечкой банка вопросов (ротация, генерация вариантов): только общее заявление CodeSignal о вариативности вопросов.

## 3. Обратная механика: инвайты от работодателя, зарплата заранее, анонимность, объяснение матча

### Takeaway
Hired-подобная модель (работодатель шлёт запрос, зарплата видна) была у Hired/Vettery, но бренд поглощён и в 2024 входит в LHH Recruitment Solutions; прямых действующих аналогов с анонимными карточками и объяснением матча в найденном нет, кроме скоринга Eightfold.

### Cited Findings
- Hired (основан 2012, привлёк 130+ млн USD по Crunchbase) куплен Vettery (Adecco) в ноябре 2020, продукты объединены под брендом Hired в марте 2021; по состоянию на 14 июня 2024 Hired — часть LHH Recruitment Solutions. Перед сделкой сообщалось о распродаже активов — [Wikipedia: Hired](https://en.wikipedia.org/wiki/Hired_(company)), [TechCrunch](https://techcrunch.com/2020/11/23/vettery-acquires-hired/amp/), [Recruiting News Network](https://www.recruitingnewsnetwork.com/posts/youre-not-hired-vettery-acquires-a-deeply-troubled-hired)
- Vettery: работодатели смотрят профили и шлют interview requests; кандидат задаёт предпочтения (локация, навыки, зарплата). Заявления "60% interview acceptance, 75% offer acceptance" — самоотчёт, 2020, непроверено — [Wizardsourcer review](https://wizardsourcer.com/review-of-vettery-a-marketplace-hiring-platform/), [Changelog sponsored](https://changelog.com/sponsored/get-a-dedicated-talent-executive-to-help-you-find-your-next-job-9NJ)
- Показ зарплаты в вакансии: Welcome to the Jungle/Otta показывает диапазоны в листингах (Otta влилась в WTTJ в январе 2024); для Wellfound обязательность показа зарплаты и опционов — только из сторонней статьи, непроверено — [WTTJ job example](https://app.welcometothejungle.com/jobs/TP-e1ujM), [WhatJobs review](https://www.whatjobs.com/news/?p=90403)
- Eightfold: match score 0–5 звёзд с шагом 0,5 по навыкам и опыту, демографические входы не используются, используется для первичного отбора и внутренней мобильности — [Eightfold Matching Model](https://eightfold.ai/nyc-eightfold-matching-model)

### Inferences
- Закрытие Triplebyte (sourcing) и распродажа Hired показывают рыночный риск маркетплейсов; наше позиционирование строится на доверии к оценке, а не на объёме.
- Контакты скрыты до принятия и анонимная карточка у найденных вендоров не подтверждены — потенциальное различие, но отсутствие в выдаче не доказательство отсутствия.

### Gaps
- SeekOut, Gloat, Wellfound, Otta: механика объяснения матча и анонимизации не найдена.
- Текущий (2026) функционал Hired не проверен.
- Нет подтверждения, что Toptal/Turing/Andela показывают зарплатную вилку кандидату заранее.

## 4. Опубликованные цифры валидности/надёжности (бенчмарки)

### Takeaway
Конкретных коэффициентов (kappa, корреляции с job performance, 4/5-правило) в найденных публичных материалах мало; ближайшие — аудиты adverse impact Eightfold по NYC LL144 и рамочные заявления CodeSignal/TestGorilla.

### Cited Findings
- Eightfold: аудит BABL AI по LL144 за период январь 2024 – декабрь 2025, более 29 млн оценок с самодекларируемыми демографическими данными, пройдены все три раздела — [Eightfold bias audit results](https://eightfold.ai/trust/bias-audit-results/); отдельные сводки у клиентов: [NetApp](https://www.netapp.com/media/88200-eightfold-match-scoring-bias-audit-summary-declared-demographic.pdf), [Morgan Stanley](https://www.morganstanley.com/content/dam/msdotcom/en/disclosures/Bias_Audit_of_Morgan_Stanleys_Use_of_Eightfold_Model_For_Scoring_Applicants.pdf), [OFCCP vendor info](https://pages.eightfold.ai/rs/278-NXO-307/images/%5BPUBLIC%5D%20Eightfold%20-%20OFCCP%20AI%20Vendor%20Information.pdf?version=0)
- Метаанализ интервью (1994, McDaniel et al.: 245 коэффициентов, 86 311 человек): структурированные интервью валиднее неструктурированных; более поздняя коррекция снижает прежние оценки — [McDaniel 1994](https://home.ubalt.edu/tmitch/645/articles/McDanieletal1994CriterionValidityInterviewsMeta.pdf), [F1000Research](https://f1000research.com/articles/14-1381). Это не данные Karat; специфичного исследования Karat не найдено.
- Правило четырёх пятых EEOC как скрининг adverse impact упомянуто во вторичном источнике (первоисточник 29 CFR 1607 не открывался) — [Rework summary](https://resources.rework.com/tools/recruiting-ats/best-pre-employment-assessment-tools-2026)

### Inferences
- Бенчмарк для нашего отчёта: аудит по импакт-рейшио (4/5) на синтетике и публикация методики — на уровне практики Eightfold, но с открытой методикой (у них отчёты у BABL AI).

### Gaps
- Не найдены числовые надёжность (alpha, SEM) и валидность (r с job performance) для TestGorilla, CodeSignal, HackerRank, Codility; fact sheets TestGorilla и технические отчёты CodeSignal нужно открыть напрямую (в выдаче были только упоминания).

## 5. Регулирование и реакция рынка

### Takeaway
Давление растёт: NYC LL144 активнее проверяется, в США идут иски против Workday и Eightfold, срок high-risk по EU AI Act сдвинут на декабрь 2027, но требования сохраняются.

### Cited Findings
- NYC LL144: нужен bias audit за последний год, публикация сводки, уведомление кандидатов за 10 рабочих дней; DCWP не требует конкретных действий по результатам. Аудит Контролёра штата NY (декабрь 2025): DCWP нашёл 1 проблему в 32 опубликованных аудитах, аудиторы Контролёра — не менее 17; ожидается более жёсткое исполнение в 2026 — [DLA Piper](https://www.dlapiper.com/en/insights/publications/2026/01/critical-audit-of-nyc-ai-hiring-law-signals-increased-risk-for-employers), [STMicro-блог (вторичный)](https://www.stmicro.net/blog/nyc-local-law-144-ai-hiring-compliance/). Один агрегатор называет дату вступления 5 октября 2026 — расходится с январём 2023 в других источниках, непроверено
- Mobley v. Workday (N.D. Cal.): иск о дискриминации ИИ-скрининга; суд допустил теорию Workday как "агента" работодателя, ADEA-коллектив предварительно сертифицирован в мае 2025; Workday называл ~1,1 млрд отклонённых заявок; в 2026 — споры о раскрытии данных bias-тестирования и ходатайство об апелляции — [DWT](https://www.dwt.com/blogs/employment-labor-and-benefits/2025/05/ai-hiring-age-discrimination-federal-court-workday), [Mondaq](https://www.mondaq.com/unitedstates/new-technology/1630454/federal-court-allows-collective-action-lawsuit-over-alleged-ai-hiring-bias), [Gunderson Spring 2026](https://www.gunder.com/en/news-insights/insights/client-insight-quarterly-employment-law-update-spring-2026)
- Kistler v. Eightfold AI: заявлено, что платформа — неучтённое consumer reporting agency по FCRA/ICRAA; на ранней стадии (ходатайство о прекращении дела), решения в выдаче нет — [Gunderson Spring 2026](https://www.gunder.com/en/news-insights/insights/client-insight-quarterly-employment-law-update-spring-2026)
- EU AI Act: найм/подбор — high-risk (Annex III). Digital Omnibus переносит обязанности Annex III с 2 августа 2026 на 2 декабря 2027 (Annex I — на 2 августа 2028); по одному источнику Парламент одобрил 16 июня 2026, Совет — 29 июня 2026; юридическая сила — после публикации в Official Journal (публикация в выдаче не подтверждена). Существо требований (техдокументация, надзор человека, мониторинг смещения) сохраняется; источники расходятся по Article 50 — [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/), [Airia](https://airia.com/the-eu-ai-act-just-got-an-extension-heres-how-to-use-it/), [compliancehub](https://compliancehub.wiki/blog/eu-digital-omnibus-ai-act-deadline-deferral-annex-iii-2027)
- Реакция вендоров: Eightfold публикует аудиты BABL AI по LL144 и информацию для OFCCP; CodeSignal заявляет adverse impact analyses и опору на IO-психологов; Codility подаёт флаги как decision support с человеком в контуре — ссылки выше

### Inferences
- Для нас: LLM не ставит оценок, ранжирование на правилах/IRT, публикуем методику и 4/5-аудит — совпадает с трендом "объяснимость + bias audit + human oversight"; заявление о соответствии AI Act без юридической экспертизы делать не стоит.
- Иски против Workday/Eightfold показывают риск вендора-"агента": объяснение матча и человек в решении — защита.

### Gaps
- Реакция конкретных вендоров на EU AI Act (SeekOut, HackerRank, CodeSignal, TestGorilla) не найдена.
- Итоговый статус публикации Omnibus в OJ и исходы дел Workday/Eightfold на октябрь 2026 не проверены.
- Прямая проверка первоисточников (EUR-Lex, суд, DCWP) не выполнялась.

## Сводная таблица (только подтверждённое выдачей; "?" — не найдено)

| Продукт | Адаптив/IRT | Оценка с погрешностью | Античит | Инвайты + зарплата | Анонимизация | Объяснение матча | Опубл. validity/AI |
|---|---|---|---|---|---|---|---|
| CodeSignal | ? (framework, вариативность вопросов) | ? | да: Suspicion Score, прокторинг | ? | ? | ? | вендорские: 2 800 ч, 3 млн точек, adverse impact |
| HackerRank | ? | ? | да: AI plagiarism, Proctor Mode (93% по вендору) | ? | ? | ? | ? |
| Codility | ? | ? | да: similarity, Integrity Risk | ? | ? | ? | ? |
| TestGorilla | ? | ? | ? | ? | ? | ? | заявлено: fact sheets, DIF |
| Karat/Triplebyte | адаптивный квиз (купили в 2023) | ? | ? | ? | ? | ? | ? |
| Hired/Vettery | нет | нет | нет | да (запросы; зарплата-фильтр) | ? | ? | самоотчёт 2020 |
| Eightfold | нет | звёзды 0–5 | нет | нет | ? | частично (match score) | аудит LL144, 29 млн оценок |
| Turing/Toptal/Andela | ? | ? | ? | ? | ? | ? | "top 2–3%" по заявлению |
| WTTJ/Otta, Wellfound | нет | нет | нет | вакансии с вилкой (WTTJ), Wellfound непроверено | ? | ? | ? |
| Woven, Qualified, Coderbyte, Devskiller, iMocha, Mettl, SeekOut, Gloat | не изучено/нет данных | | iMocha/Mettl: прокторинг | | | | |
