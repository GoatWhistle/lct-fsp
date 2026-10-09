import type { Role } from "@/shared/api"
import type { IconName } from "@/shared/ui"

export type NavKey =
  | "overview"
  | "profile"
  | "invitations"
  | "vacancies"
  | "tasks"
  | "needs"
  | "candidates"

export interface NavItem {
  readonly key: NavKey
  readonly to: string
  readonly icon: IconName
  readonly end?: boolean
  readonly unread?: boolean
}

export const NAV_ITEMS: Readonly<Record<Role, readonly NavItem[]>> = {
  candidate: [
    { key: "overview", to: "/candidate", icon: "overview", end: true },
    { key: "profile", to: "/candidate/profile", icon: "profile" },
    { key: "invitations", to: "/candidate/invitations", icon: "invitation", unread: true },
    { key: "vacancies", to: "/candidate/vacancies", icon: "vacancy" },
    { key: "tasks", to: "/candidate/tasks", icon: "task" },
  ],
  employer: [
    { key: "overview", to: "/employer", icon: "overview", end: true },
    { key: "needs", to: "/employer/needs", icon: "need" },
    { key: "candidates", to: "/employer/candidates", icon: "candidates" },
    { key: "invitations", to: "/employer/invitations", icon: "invitation", unread: true },
    { key: "vacancies", to: "/employer/vacancies", icon: "vacancy" },
    { key: "tasks", to: "/employer/tasks", icon: "task" },
  ],
}
