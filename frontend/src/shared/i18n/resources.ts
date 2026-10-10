import type { Locale } from "./locale"
import enApplications from "./locales/en/applications.json"
import enAuth from "./locales/en/auth.json"
import enCard from "./locales/en/card.json"
import enCatalog from "./locales/en/catalog.json"
import enCommon from "./locales/en/common.json"
import enCompany from "./locales/en/company.json"
import enConversation from "./locales/en/conversation.json"
import enEmployer from "./locales/en/employer.json"
import enErrors from "./locales/en/errors.json"
import enHome from "./locales/en/home.json"
import enInvitations from "./locales/en/invitations.json"
import enMeasure from "./locales/en/measure.json"
import enNeed from "./locales/en/need.json"
import enOverview from "./locales/en/overview.json"
import enPath from "./locales/en/path.json"
import enProfile from "./locales/en/profile.json"
import enSearch from "./locales/en/search.json"
import enSelection from "./locales/en/selection.json"
import enTaskEditor from "./locales/en/taskEditor.json"
import enTasks from "./locales/en/tasks.json"
import enTest from "./locales/en/test.json"
import enVacancies from "./locales/en/vacancies.json"
import enVacancyEditor from "./locales/en/vacancyEditor.json"
import enVacancyTest from "./locales/en/vacancyTest.json"
import ruApplications from "./locales/ru/applications.json"
import ruAuth from "./locales/ru/auth.json"
import ruCard from "./locales/ru/card.json"
import ruCatalog from "./locales/ru/catalog.json"
import ruCommon from "./locales/ru/common.json"
import ruCompany from "./locales/ru/company.json"
import ruConversation from "./locales/ru/conversation.json"
import ruEmployer from "./locales/ru/employer.json"
import ruErrors from "./locales/ru/errors.json"
import ruHome from "./locales/ru/home.json"
import ruInvitations from "./locales/ru/invitations.json"
import ruMeasure from "./locales/ru/measure.json"
import ruNeed from "./locales/ru/need.json"
import ruOverview from "./locales/ru/overview.json"
import ruPath from "./locales/ru/path.json"
import ruProfile from "./locales/ru/profile.json"
import ruSearch from "./locales/ru/search.json"
import ruSelection from "./locales/ru/selection.json"
import ruTaskEditor from "./locales/ru/taskEditor.json"
import ruTasks from "./locales/ru/tasks.json"
import ruTest from "./locales/ru/test.json"
import ruVacancies from "./locales/ru/vacancies.json"
import ruVacancyEditor from "./locales/ru/vacancyEditor.json"
import ruVacancyTest from "./locales/ru/vacancyTest.json"

export const NAMESPACES = [
  "common",
  "errors",
  "catalog",
  "measure",
  "applications",
  "auth",
  "card",
  "company",
  "conversation",
  "employer",
  "home",
  "invitations",
  "need",
  "overview",
  "path",
  "profile",
  "search",
  "selection",
  "taskEditor",
  "tasks",
  "test",
  "vacancies",
  "vacancyEditor",
  "vacancyTest",
] as const

export type Namespace = (typeof NAMESPACES)[number]

export const DEFAULT_NAMESPACE: Namespace = "common"

const en = {
  common: enCommon,
  errors: enErrors,
  catalog: enCatalog,
  measure: enMeasure,
  applications: enApplications,
  auth: enAuth,
  card: enCard,
  company: enCompany,
  conversation: enConversation,
  employer: enEmployer,
  home: enHome,
  invitations: enInvitations,
  need: enNeed,
  overview: enOverview,
  path: enPath,
  profile: enProfile,
  search: enSearch,
  selection: enSelection,
  taskEditor: enTaskEditor,
  tasks: enTasks,
  test: enTest,
  vacancies: enVacancies,
  vacancyEditor: enVacancyEditor,
  vacancyTest: enVacancyTest,
}

const ru = {
  common: ruCommon,
  errors: ruErrors,
  catalog: ruCatalog,
  measure: ruMeasure,
  applications: ruApplications,
  auth: ruAuth,
  card: ruCard,
  company: ruCompany,
  conversation: ruConversation,
  employer: ruEmployer,
  home: ruHome,
  invitations: ruInvitations,
  need: ruNeed,
  overview: ruOverview,
  path: ruPath,
  profile: ruProfile,
  search: ruSearch,
  selection: ruSelection,
  taskEditor: ruTaskEditor,
  tasks: ruTasks,
  test: ruTest,
  vacancies: ruVacancies,
  vacancyEditor: ruVacancyEditor,
  vacancyTest: ruVacancyTest,
}

export type Dictionary = typeof en

export const resources = { en, ru } satisfies Record<Locale, Record<Namespace, object>>
