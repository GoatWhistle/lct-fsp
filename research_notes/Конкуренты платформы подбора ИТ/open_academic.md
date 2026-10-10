# Открытые и академические аналоги платформы подбора ИТ-специалистов (адаптивный тест + обратная механика)

Дата среза: октябрь 2026. Источники — результаты веб-поиска, полные тексты в большинстве случаев не открывались; всё, что не подтверждено первоисточником, помечено «не проверено».

## 1. Открытые CAT-движки и открытые системы подбора: что дают и чем отличаются от нашего подхода

### Takeaway
Открытые CAT-инструменты (catR, mirtCAT, Concerto, TAO, adaptivetesting, catsim, py-irt) закрывают психометрическое ядро (оценка тета, выбор заданий, калибровка), но это тестовые движки или симуляторы, а не продукт подбора: профиль по темам с погрешностью, категория «специализация × грейд», двусторонняя выдача и атакующая валидация в них не заложены. Открытой системы подбора ИТ-кадров с адаптивным тестом и обратной механикой в поиске не найдено.

### Cited Findings
- catR — открытый R-пакет для симуляции CAT (Magis и соавторы); книга 2017 г. описывает реализацию на catR и mstR — [Psychometric Society](https://psychometricsociety.org/post/computerized-adaptive-testing-and-multistage-testing-r), [Springer Professional](https://www.springerprofessional.de/computerized-adaptive-and-multistage-testing-with-r/15249636).
- mirtCAT (Chalmers) — R-пакет, GPL (>=3), версия 1.14 (июль 2024): одно- и многомерный CAT на IRT, HTML-интерфейс через shiny, Монте-Карло для банков заданий; оценка через пакет mirt — [CRAN](https://cran.rstudio.com/web/packages/mirtCAT/index.html), [rdrr.io](https://rdrr.io/cran/mirtCAT/).
- Concerto — открытая веб-платформа адаптивного тестирования Psychometrics Centre (Cambridge), запущена в 2011, бесплатна для коммерческого и академического использования, сочетает HTML и R; основное применение — психологические и медицинские опросники (CAT WHOQOL-100) — [Cambridge](https://www.psychometrics.cam.ac.uk/newconcerto), [EHPS](https://ehps.net/ehp/index.php/contents/article/view/1785), [JMIR/PMC 2020](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7661245/).
- TAO — открытая платформа оценивания на стандарте QTI со встроенной поддержкой CAT; создана в Университете Люксембурга, поддерживается Open Assessment Technologies; лицензия GPL v2 (по вторичному источнику — не проверено по репозиторию); платные редакции Pro/Enterprise — [TAO](https://www.taotesting.com/?p=1747), [OE Global](https://oeweek.oeglobal.org/resources/2018/tao/), [TAO accelerate](https://www.accelerate.taotesting.com/revolutionize-standardized-testing-with-open-source-software).
- py-irt — Python-библиотека байесовской IRT (Pyro/PyTorch, GPU), Lalor & Rodriguez, INFORMS Journal on Computing 35(1), 2023; 1PL/2PL/3PL (набор моделей в актуальном релизе не проверен) — [arXiv:2203.01282](https://arxiv.org/pdf/2203.01282), [GitHub](https://github.com/nd-ball/py-irt).
- adaptivetesting — Python-пакет для CAT с настраиваемой байесовской оценкой; статья Engicht, Bee, Koch, Behavior Research Methods 58, 250 (2026) — [Uni Jena](https://www.fsv.uni-jena.de/95876/adaptivetesting-paper). Страница PyPI/GitHub не найдена.
- catsim — Python-симулятор CAT (инициализация, выбор заданий, оценка, остановка); калибровку параметров не реализует — [PyPI](https://pypi.org/project/catsim).
- EduCAT — Python-инструментарий CAT (в поиске только как упоминание) — [PyPI](https://pypi.org/project/EduCAT/), [GitHub](https://github.com/54zy/EduCAT); обзор «Survey of CAT: a machine-learning perspective» (2024) — [arXiv:2404.00712](https://arxiv.org/pdf/2404.00712).
- Открытые наборы резюме для парсинга и матчинга (синтетика и реальные, MIT) существуют, например на Hugging Face — [HF dataset](https://huggingface.co/datasets/PROFESSORSAM25/resumes/blob/main/README.md); оценок навыков кандидатов в них нет (по описанию карточки).

### Inferences
- Различие для позиционирования: движки дают «тета + SE по одной шкале»; наши профиль по темам, категория и ранжирование только внутри категории — надстройка, которой в этих проектах нет. Их можно цитировать как референс для калибровки и симуляции (py-irt, catsim, mirtCAT), а не как конкурентов по подбору.
- Утверждение «открытых аналогов подбора с CAT нет» опирается на ограниченный поиск; формулировать как «мы не нашли».

### Gaps
- Не искали открытые ATS/рекрутинговые системы (OpenCATS и т.п.) — отдельный запрос не делался.
- Страницы PyPI/GitHub adaptivetesting, актуальные версии catR и лицензия TAO по первоисточнику не проверены.
- Поддержка многотемного профиля и контроля экспозиции в mirtCAT/catR/TAO не проверялась (в catR, по моим знаниям, есть Sympson-Hetter — не проверено).

## 2. Академические работы: двусторонний подбор, перегрузка, сигналы и приглашения

### Takeaway
Есть прямые академические опоры для обратной механики: полевой эксперимент Хортона (алгоритмические рекомендации работодателю повысили заполняемость вакансий на 20 %), теория сигналов предпочтений (Coles–Kushnir–Niederle) и работа о перегрузке (congestion) в рекомендациях вакансий. Это поддерживает вероятность принятия и лимит приглашений; одновременно показывает риск: сигналы/скауты теряют силу при росте их числа.

### Cited Findings
- Horton, «The Effects of Algorithmic Labor Market Recommendations: Evidence from a Field Experiment», J. of Labor Economics 35(2), 2017, 345–385, DOI 10.1086/689213: работодатели с техническими вакансиями, получившие алгоритмические рекомендации кандидатов, имели на 20 % выше долю заполненных вакансий; вытеснения нерекомендованных кандидатов не обнаружено; нанятые по рекомендации похожи на тех, кого работодатель находит сам; эффект сильнее у вакансий с малым пулом откликов — [страница автора](https://john-joseph-horton.com/papers/the-effects-of-algorithmic-labor-market-recommendations-evidence-from-a-field-experiment/), [SUFE](https://academicnewsletter.sufe.edu.cn/info/277475). Замечание: это рекомендации работодателю, а не «приглашения кандидатам»; формулировка «algorithmic invitations» в источнике не подтверждена.
- Coles, Kushnir, Niederle, «Preference Signaling in Matching Markets», NBER WP 16185 (2010), AEJ: Microeconomics 5(2), 2013, 99–134: один бесплатный сигнал интереса повышает число пар и благосостояние работников, эффект для фирм неоднозначен; сильнее в сбалансированных рынках — [NBER](https://www.nber.org/papers/w16185).
- Kushnir, «Matching Markets with Signals» (FEEM, 2009): бесплатные сигналы могут вредить при сходных предпочтениях агентов — [AgEcon](https://ageconsearch.umn.edu/record/50730/files/39-09.pdf).
- Su et al. (оптимизация ранжирования для рынков с «scout»-приглашениями): вероятность ответа соискателя на скаут падает с ростом числа скаутов — пересказ в Goda, Hayashi, Saito, «A Best-of-Both Approach to Improve Match Predictions and Reciprocal Recommendations for Job Search», 2024 — [arXiv:2409.10992](https://arxiv.org/pdf/2409.10992). Оригинал Su et al. не получен; не проверено.
- ReCon: Reducing Congestion in Job Recommendation using Optimal Transport, 2023 — [arXiv:2308.09516](https://arxiv.org/pdf/2308.09516); в ней упоминается система перераспределения откликов LinkedIn (ссылка [4], оригинал не найден).
- Исследование рекомендательной системы французской службы занятости: ИИ-рекомендации усиливают перегрузку, оптимальный транспорт по матрице вероятностей матчинга её заметно снижает — [Crépon, HAL](https://hal-universite-paris-saclay.archives-ouvertes.fr/LISN/hal-03540319).
- Chen, Hsieh, Lin, «Prediction and Congestion in Two-Sided Markets» (2019, онлайн-знакомства): ML-рекомендации концентрируются на малом числе пользователей; равновесный рекомендатель даёт кратное превосходство по hit rate (в источнике — «19×») — [UCR PDF](https://webarchive.ucr.edu/economics.ucr.edu/wp-content/uploads/2019/10/Hseih-paper-for-4-3-19-seminar-title-2.pdf).
- RecSys in HR 2025 (workshop, Nathan et al.): ограничение распределения рекомендаций для избегания перегрузки — [CEUR Vol-4046](https://ceur-ws.org/Vol-4046/RecSysHR2025-paper_6.pdf).
- MODE: Mutual Optimality in Direct Effects of Reciprocal Recommendations in Matching Markets — идентификатор arXiv 2608.01731 из поиска (2026); содержание не проверялось — [arXiv](https://arxiv.org/pdf/2608.01731).
- RecSys Challenge 2017 (XING): холодный старт, подбор кандидатов под новую вакансию, офлайн-фаза и онлайн-фаза в живой системе; 262 команды зарегистрированы — [RecSys 2017](https://recsys.acm.org/recsys17/challenge/).

### Inferences
- Лимит приглашений на кандидата и учёт перегрузки в расчёте вероятности принятия можно обосновать работами по congestion и Su et al.; эффект Хортона — аргумент в пользу ценности рекомендаций работодателю.
- Оговорка Kushnir: при однородных предпочтениях (все хотят топ-кандидатов) сигналы/приглашения могут вредить — стоит учесть в плане валидации.

### Gaps
- Роту (Roth) как автора обзорных работ по двустороннему подбору прицельно не искали; конкретные работы Indeed/LinkedIn (кроме косвенных ссылок) не найдены.
- Полные тексты Су и др., Hseih и др. не открывались; цифры — по пересказам поисковой выдачи.

## 3. Защита от накрутки в CAT и смещения LLM-ранжирования

### Takeaway
Контроль экспозиции заданий (Sympson-Hetter, a-stratification, item-eligibility и др.) и обнаружение скомпрометированных заданий и предзнания — зрелая литература с 1985 г.; прямых работ про LLM как атакующего адаптивных тестов найти не удалось. Смещения LLM при отборе резюме задокументированы (имена, порядок), что поддерживает тезис «LLM не ранжирует».

### Cited Findings
- Sympson & Hetter (1985, Military Testing Association): исходный метод контроля экспозиции — выбранное задание проходит вероятностный фильтр; один из двух самых распространённых подходов наряду с a-stratified — [assess.com](https://assess.com/?p=27276).
- Georgiadou, Triantafillou, Economides, обзор методов контроля экспозиции 1983–2005, JTLA 2007 — [BC ejournals](https://ejournals.bc.edu/index.php/jtla/article/view/1647).
- Barrada, Abad, Veldkamp (2009): метод ограничения (restricted) лучше контролирует максимальную экспозицию, далее item-eligibility, Sympson-Hetter хуже; перекрытие и RMSE почти одинаковы — [Psicothema](https://www.psicothema.com/pi?pii=3632) (результат зависит от размера банка и целевой экспозиции).
- Chang & Ansley (2003): ни один из пяти методов не обладает всеми желаемыми свойствами (по пересказу) — см. обзор [BC ejournals](https://ejournals.bc.edu/index.php/jtla/article/view/1647).
- Последовательное обнаружение скомпрометированных заданий по времени ответа в CAT, Psychometrika — [Cambridge](https://www.cambridge.org/core/journals/psychometrika/article/sequential-detection-of-compromised-items-using-response-times-in-computerized-adaptive-testing/94A5F8416D65BD98D21AED113F8036EB); байесовский подход к предзнанию заданий (в одном эксперименте чувствительность 80 % при специфичности 97 %, симуляция) — [Frontiers 2019](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2019.00829/pdf); при сильной утечке оценка способности смещается — [Springer](https://link.springer.com/article/10.1007/s11336-017-9596-3) (по пересказу выдачи).
- Индустрия: HackerEarth (вендор) называет ИИ-инструменты самым частым способом обмана на непроктор-тестах; интервью с ИИ-помощником на LeetCode-стиле подтверждено экспериментом interviewing.io (пересказ вендора) — [HackerEarth](https://cafe.hackerearth.com/blog/different-ways-candidates-cheat-in-online-technical-assessments). Источник коммерческий.
- Смещения LLM:
  - Wilson & Caliskan, 2024, retrieval-ранжирование резюме: эмбеддинги в 85,1 % случаев предпочитали имена, ассоциируемые с белыми, и в 11,1 % — женские — [arXiv:2407.20371](https://arxiv.org/html/2407.20371v1).
  - FAIRE (2025): все протестированные модели показывают расовое/гендерное смещение разной величины и направления — [arXiv:2504.01420](https://arxiv.org/pdf/2504.01420).
  - Rozado (2025): 22 LLM при выборе из пар резюме предпочитали кандидатов с женскими именами по 70 профессиям; также сильное предпочтение первого в списке; контрбалансировка убирает гендерный эффект — [arXiv:2505.17049](https://arxiv.org/abs/2505.17049v2) (рецензирование не проверено).
  - Iso et al. (NAACL 2025 Industry): явные смещения по полу и расе снизились, неявные по образованию остаются — [arXiv:2503.19182](https://arxiv.org/abs/2503.19182v1).
  - Yin, Vardi, Choudhary (2025): эффекты порядка в LLM — [arXiv:2506.14092](https://arxiv.org/html/2506.14092v2).
  - «Human and LLM-Based Resume Matching: An Observational Study», NAACL Findings 2025: модель OpenAI без примеров в запросе слабо коррелирует с оценками людей (736 резюме) — [ACL Anthology](https://preview.aclanthology.org/moar-dois/2025.findings-naacl.270).
  - «Can LLMs Hire Fairly? Racial Bias in Resume Screening» (arXiv 2606.28978) — содержание не подтверждено, не использовать без проверки — [arXiv](https://arxiv.org/pdf/2606.28978).

### Inferences
- Для защиты: наш банк с контролем экспозиции и мониторингом заданий опирается на устоявшуюся литературу; сравнивать стоит с Sympson-Hetter и item-eligibility как базой.
- Позиционный и именной bias LLM — прямой аргумент для правила «LLM не ранжирует»; в стенде валидации LLM-ранжировщик (Claude Sonnet) уместно сравнивать как базовую линию по этим же метрикам, с контрбалансировкой порядка.

### Gaps
- Академических работ про LLM как атакующего именно адаптивных (IRT) тестов с банком заданий не найдено; для утверждения «первые» нужен отдельный обзор.
- Результаты по Claude-моделям как ранжировщикам отдельно не искались (PMC-статья упоминала Claude 3.5 Sonnet, детали не проверены).

## 4. Бенчмарки и датасеты для сравнения валидации

### Takeaway
Публичные данные для подбора есть (XING RecSys Challenge 2016/2017, наборы резюме и вакансий), но все они — про поведение и тексты, без калиброванных оценок навыков и без скрытой истины, поэтому сравнение с ними ограничено задачей ранжирования подбора, а не качеством теста.

### Cited Findings
- RecSys Challenge 2016/2017 (XING): взаимодействия пользователь–вакансия, impressions; 2017 — холодный старт вакансий и онлайн-оценка; данные анонимизированы — [RecSys 2017](https://recsys.acm.org/recsys17/challenge/), [RecSys Challenge 2016 paper](https://ar5iv.labs.arxiv.org/html/1612.00959). Доступность данных сейчас не проверена.
- Hugging Face: набор резюме реальных и синтетических для парсинга и матчинга, MIT, упор на технические роли — [HF](https://huggingface.co/datasets/PROFESSORSAM25/resumes/blob/main/README.md).
- Данные Upwork-вакансий (53 058) и резюме LiveCareer, использованные в работе о коррелированных ошибках LLM — [arXiv:2506.07962](https://arxiv.org/pdf/2506.07962); готовый бенчмарк не подтверждён.
- conSultantBERT: Siamese Sentence-BERT для матчинга вакансий и кандидатов (2021) — [arXiv:2109.06501](https://arxiv.org/pdf/2109.06501); данные закрытые (не проверено).
- Датасет наблюдательного исследования из NAACL Findings 2025 (736 резюме) — публикация данных не подтверждена.

### Inferences
- Корректный ход для защиты: сравнивать на XING/резюме только модуль ранжирования по признакам; для теста — на синтетике по плану валидации, где скрытая истина отделена от признаков.

### Gaps
- Не удалось найти CareerBuilder, JobRec, ResumeAtlas и обзор person-job fit; не проверены лицензии и доступность датасетов. Нет открытого бенчмарка именно «оценка навыков по тесту → подбор».

## 5. Регуляторика и стандарты, на соответствие которым может ссылаться конкурент

### Takeaway
Для рынков ЕС и США «подбор персонала» — высокий риск (EU AI Act, Annex III; NYC LL144). Для России — 152-ФЗ. ISO 10667 и ISO/IEC 42001 — добровольные стандарты; ссылка на них не заменяет юридических обязанностей.

### Cited Findings
- EU AI Act, Annex III: ИИ для найма и отбора (в т.ч. отбор заявок, оценка кандидатов) — высокий риск; обязанности делятся между провайдером и пользователем (ст. 26) — [EPC Group](https://www.epcgroup.net/blog/ai-hr-security-eu-annex-iii-high-risk-2026), [Sonomos](https://sonomos.ai/blog/ai-hiring-eeoc-nyc-ll144-eu-ai-act-2026/) (вторичные, юридические блоги).
- Сроки: цифровой «омнибус» (временное соглашение, май 2026) переносит требования для автономных систем Annex III (в т.ч. найм) на 2 декабря 2027, для встроенных в продукты Annex I — на 2 августа 2028; на момент источников (май–июль 2026) формальное принятие и публикация в Official Journal не подтверждены — [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement), [Sidley](https://datamatters.sidley.com/?p=8999). Статус на октябрь 2026 проверить по Official Journal. Источники до омнибуса называли 2 августа 2026.
- NYC Local Law 144: автоматизированные инструменты принятия решений о найме/продвижении требуют независимого аудита на смещение; ответственность на работодателе; аудит вендора не заменяет аудит работодателя; в декабре 2025 аудит комптроллера штата нашёл не менее 17 возможных нарушений в 32 компаниях — [The Hire Hub](https://www.thehirehub.ai/blog/ai-hiring-compliance-in-2026-the-recruiter-s-guide-to-nyc-local-law-144-and-the-eu-ai-act), [Sonomos](https://sonomos.ai/blog/ai-hiring-eeoc-nyc-ll144-eu-ai-act-2026/) (вторичные).
- ISO/IEC 42001:2023 (18.12.2023) — стандарт системы менеджмента ИИ, возможна сертификация, не является юридическим требованием — [SCC](https://scc-ccn.ca/standardsdb/standards/2053575). Не заменяет аудит LL144 (по вторичному источнику).
- ISO 10667 (серия про процедуры оценки людей в рабочей среде) — в поиске подтверждения не нашлось; описание из общих знаний, не проверено: проверить по каталогу ISO.
- 152-ФЗ: ФЗ от 30.11.2024 № 420-ФЗ ужесточил КоАП, действует с 30.05.2025, штрафы за утечки выросли; для должностных лиц при утечке 1 000–10 000 субъектов — 200–400 тыс. руб., для граждан 100–200 тыс.; ФЗ № 421-ФЗ — уголовная ответственность с 11.12.2024 — [Harant](https://harant.ru/blog/grazhdanskoe-pravo/pro-personalnye-dannye-v-rabote-yuridicheskih-licz-i-ip-v-2025g-obzor-izmenenij/), [Habr](https://habr.com/ru/articles/913128), [docshell](https://docshell.ru/event-docs/Айти%20Новация%20%5BПДн%5D.pdf). Утверждения о «штрафах до 500 млн» маркетинговые и не подтверждены ([Sostav](https://www.sostav.ru/blogs/250279/62331)). Локализация (ч. 5 ст. 18) в выдаче не подтверждена.

### Inferences
- Конкурент может заявлять соответствие EU AI Act/LL144, но без независимого аудита и документации это маркетинг; наш аргумент — предрегистрированный план валидации и отчёт по смещению, локальная модель без вывода ПДн наружу (152-ФЗ).

### Gaps
- Первоисточники (EUR-Lex, nyc.gov, pravo.gov.ru, iso.org) не открывались; юридические выводы — по блогам. Нужна юридическая проверка перед публичными заявлениями.
- Не проверены статус принятия омнибуса к октябрю 2026 и действующие требования ISO 10667.

## Дополнение: готовые открытые реализации (репозитории и живые проекты)

Данные со страниц GitHub (через WebFetch, снимок октября 2026). Дат последних коммитов страницы не показали — активность оценивается только по числу коммитов и звёзд; актуальность релизов не проверена. Звёзды — на момент просмотра.

| Проект | Ссылка | Стек | Лицензия | Звёзды / коммиты | Что реализовано |
|---|---|---|---|---|---|
| HackerRank Hiring Agent | [GitHub](https://github.com/interviewstreet/hiring-agent) | Python 3.11+, PyMuPDF, Pydantic, Jinja2; Ollama/Google AI/OpenAI | MIT | ~7,3k / 126 | Разбор резюме PDF в JSON, обогащение данными GitHub, скоринг по роли (категории, веса, бонусы с потолком 20, итог считает Python), CLI. Только оценка резюме, адаптивного теста и двусторонней механики нет. |
| OpenCATS | [GitHub](https://github.com/opencats/OpenCATS), [сайт](https://www.opencats.org/) | PHP, MySQL/MariaDB (доки: PHP 7.4, MariaDB 10.7) | в выдаче не названа (файл LICENSE.md) | 759 / 1 020 | ATS и CRM для рекрутеров: вакансии, отклики, отбор. Без оценки навыков и ранжирования. Версии в источниках расходятся (0.9.7.4 против 0.10.0). |
| Eval (openeval/eval) | [GitHub](https://github.com/openeval/eval) | Next.js, React, TypeScript, Supabase, Prisma, Tailwind | не названа в выдаче | 2 / 195 | Платформа оценки кандидатов на реальных issue открытых проектов; список функций на странице отсутствует. Маргинальный проект. |
| INGInious | упомянут в [выдаче](https://selfhostyourself.com/alternative-to/hackerrank) | Python, Docker | не проверено | не проверено | Проверка программ в изолированных контейнерах, ориентирован на вузы и LMS, не на найм. |
| TAO (tao-core) | [GitHub](https://github.com/oat-sa/tao-core) | PHP (язык не показан) | GPL-2.0 | 64 / 22 551 | Платформа оценивания на QTI, поддержка CAT (по вендору); платные редакции. Тема assessment. |
| Concerto | [GitHub](https://github.com/campsych/concerto-platform) | R + веб, Docker | Apache-2.0 | 174 / 1 779 (ветка 5.0-dev) | Платформа онлайн-адаптивного тестирования, активная ветка разработки, wiki и changelog; список функций не показан. Уточняет раздел 1: лицензия не просто «бесплатна», а Apache-2.0. |
| py-irt | [GitHub](https://github.com/nd-ball/py-irt) | Python, Pyro/PyTorch | MIT | 173 / 255 | Байесовская IRT: 1PL, 2PL, 4PL с вариационным выводом, vague/hierarchical priors; 3PL «в планах» (уточняет раздел 1). Релизов нет. Это калибровка, не CAT. |
| catsim | [GitHub](https://github.com/douglasrizzo/catsim) | Python 3.11–3.14 | BSD-3-Clause | 153 / 877 | Симулятор CAT (селекторы вроде MaxInfoSelector, оценка, остановка). Методы контроля экспозиции на странице не названы. |
| catIrt, simCAT, cdCAT | [catIrt CRAN](https://cran.r-project.org/web/packages/catIrt/index.html), [simCAT](https://cran.ms.unimelb.edu.au/web/packages/simCAT/refman/simCAT.html) | R | не проверено | не проверено | catIrt: симуляция CAT с селекторами, оценщиками, критериями остановки. simCAT: максимум информации Фишера, балансировка контента, контроль экспозиции. cdCAT: CAT для когнитивной диагностики, shadow-тест через ограничения. |
| catR, mirtCAT | см. раздел 1 | R | mirtCAT: GPL>=3 | — | catR: правила старта/выбора/остановки, оценщики, контроль экспозиции и баланса контента (по описанию с rdocumentation). |
| adaptivetesting | [Uni Jena](https://www.fsv.uni-jena.de/95876/adaptivetesting-paper) | Python | не проверено | не проверено | Байесовский CAT, статья 2026 г. |
| Resume Matcher и аналоги | [Gitee-зеркало](https://gitee.com/bytesfly/Resume-Matcher), JobKit [PyPI](https://pypi.org/project/jobkit/) | Python, Ollama | не проверено | не проверено | Сопоставление резюме и вакансии с оценкой совпадения, инструменты на стороне соискателя. Оригинальный GitHub-адрес (dmbaruch) дал 404. |

### Наблюдения
- Ближайший по духу живой проект с правилами — Hiring Agent (HackerRank): LLM извлекает данные, итог считает код с ограниченными бонусами. Он валидирует нашу позицию «числа считает код», но ранжирует по резюме и GitHub, то есть по самоописанию, которое у нас имеет низкий вес. Адаптивного теста, погрешности и анти-накрутки нет. Это единственный найденный проект с большой аудиторией (~7,3k звёзд); отметить как публичный ориентир.
- Целостной открытой системы «адаптивный тест + двусторонний подбор + приглашения с вилкой» не найдено; ближайшие — разрозненные части: CAT-движки (Concerto, TAO, R/Python-пакеты), ATS (OpenCATS), оценка резюме (Hiring Agent).
- Открытых реализаций обратного маркетплейса талантов (employer-invites) в выдаче нет; вопрос остаётся в Gaps. Коммерческие обратные площадки (например, Hired, Otta) не искали и не проверяли.

### Антиплагиат и защита от утечки заданий: открытые реализации
- Готовых открытых репозиториев по контролю экспозиции и детекции скомпрометированных заданий нашлось только в составе R-пакетов (catR, simCAT, cdCAT с shadow-тестом). Отдельных открытых сервисов детекции предзнания (в виде репозитория) в выдаче нет; литература из раздела 3 описывает методы, но не их код.
- Проктор/антиплагиат-системы с открытым кодом для найма не найдены; найденное — коммерческие HackerRank, CodeSignal, DevSkiller (облачные), у DevSkiller есть DMCA-удаление скопированных тестовых проектов ([GitHub DMCA mirror](https://source-hub.etos-pro.ru/github/dmca/commit/65f17a9fc5ab2cda5a9cf8722bbd9de0d315b572)) — косвенный довод, что банки заданий утекают в открытый доступ.

### Gaps (дополнение)
- Даты последних коммитов и релизов не получены ни для одного репозитория; «жив/мёртв» не установлен.
- Не проверены лицензии OpenCATS, Eval, INGInious, adaptivetesting, catIrt, simCAT.
- Не искали отдельно: Frappe Hiring, Reactive Resume, Kaggle-решения по подбору, коммерческие обратные площадки и конкретные CAT-проекты на JS (jsCAT и порты).
