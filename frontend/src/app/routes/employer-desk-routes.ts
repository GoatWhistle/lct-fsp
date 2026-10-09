import type { RouteObject } from "react-router"
import { page } from "./page"

export const EMPLOYER_DESK_ROUTES: RouteObject[] = [
  {
    index: true,
    lazy: page(
      () => import("@/pages/employer-overview/employer-overview-page"),
      "EmployerOverviewPage",
    ),
  },
  {
    path: "invitations/:id?",
    lazy: page(
      () => import("@/pages/employer-invitations/employer-invitations-page"),
      "EmployerInvitationsPage",
    ),
  },
  {
    path: "vacancies",
    lazy: page(
      () => import("@/pages/employer-vacancies/employer-vacancies-page"),
      "EmployerVacanciesPage",
    ),
  },
  {
    path: "tasks",
    lazy: page(() => import("@/pages/employer-tasks/employer-tasks-page"), "EmployerTasksPage"),
  },
  {
    path: "company",
    lazy: page(
      () => import("@/pages/employer-company/employer-company-page"),
      "EmployerCompanyPage",
    ),
  },
]
