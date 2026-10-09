import { Navigate, Outlet, useLocation } from "react-router"
import { CABINET_PATH, useSession } from "@/entities/session"
import type { Role } from "@/shared/api"
import { RouteFallback } from "../route-fallback/route-fallback"
import { AppShell } from "../shell/app-shell/app-shell"

export interface RequireRoleProps {
  readonly allow: Role
  readonly shell?: boolean
}

export function RequireRole({ allow, shell = true }: RequireRoleProps) {
  const session = useSession()
  const location = useLocation()
  if (session.isPending) return <RouteFallback />
  const user = session.data ?? null
  if (user === null) {
    const back = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(back)}`} replace />
  }
  if (user.role !== allow) return <Navigate to={CABINET_PATH[user.role]} replace />
  return shell ? <AppShell user={user} /> : <Outlet />
}
