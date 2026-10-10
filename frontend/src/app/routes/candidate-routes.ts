import { type RouteObject, redirect } from "react-router"
import { PROFILE_PARAM } from "@/entities/profile"
import { page } from "./page"

export const CANDIDATE_FOCUS_ROUTES: RouteObject[] = [
  {
    path: "test",
    lazy: page(() => import("@/pages/candidate-test/candidate-test-page"), "CandidateTestPage"),
  },
  {
    path: "reveal",
    lazy: page(
      () => import("@/pages/candidate-reveal/candidate-reveal-page"),
      "CandidateRevealPage",
    ),
  },
]

export const CANDIDATE_ROUTES: RouteObject[] = [
  {
    index: true,
    lazy: page(
      () => import("@/pages/candidate-overview/candidate-overview-page"),
      "CandidateOverviewPage",
    ),
  },
  {
    path: "path",
    lazy: page(() => import("@/pages/candidate-path/candidate-path-page"), "CandidatePathPage"),
  },
  {
    path: "profile",
    loader: ({ request }) => {
      const params = new URL(request.url).searchParams
      params.set(PROFILE_PARAM, "edit")
      return redirect(`/candidate?${params.toString()}`)
    },
  },
  {
    path: "invitations/:id?",
    lazy: page(
      () => import("@/pages/candidate-invitations/candidate-invitations-page"),
      "CandidateInvitationsPage",
    ),
  },
  {
    path: "vacancies/:id?",
    lazy: page(
      () => import("@/pages/candidate-vacancies/candidate-vacancies-page"),
      "CandidateVacanciesPage",
    ),
  },
  {
    path: "tasks",
    lazy: page(() => import("@/pages/candidate-tasks/candidate-tasks-page"), "CandidateTasksPage"),
  },
]
