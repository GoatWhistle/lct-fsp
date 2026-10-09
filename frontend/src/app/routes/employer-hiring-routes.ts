import type { RouteObject } from "react-router"
import { page } from "./page"

const needEditor = page(
  () => import("@/pages/employer-need-editor/employer-need-editor-page"),
  "EmployerNeedEditorPage",
)

export const EMPLOYER_HIRING_ROUTES: RouteObject[] = [
  {
    path: "needs",
    lazy: page(() => import("@/pages/employer-needs/employer-needs-page"), "EmployerNeedsPage"),
  },
  { path: "needs/new", lazy: needEditor },
  {
    path: "needs/text",
    lazy: page(
      () => import("@/pages/employer-need-text/employer-need-text-page"),
      "EmployerNeedTextPage",
    ),
  },
  { path: "needs/:id", lazy: needEditor },
  {
    path: "selections/:id",
    lazy: page(
      () => import("@/pages/employer-selection/employer-selection-page"),
      "EmployerSelectionPage",
    ),
  },
  {
    path: "candidates",
    lazy: page(
      () => import("@/pages/employer-candidates/employer-candidates-page"),
      "EmployerCandidatesPage",
    ),
  },
  {
    path: "candidates/:id",
    lazy: page(
      () => import("@/pages/employer-candidate/employer-candidate-page"),
      "EmployerCandidatePage",
    ),
  },
]
