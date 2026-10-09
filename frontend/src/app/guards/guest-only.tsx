import { Navigate, Outlet } from "react-router"
import { CABINET_PATH, useSession } from "@/entities/session"
import { RouteFallback } from "../route-fallback/route-fallback"

export function GuestOnly() {
  const session = useSession()
  if (session.isPending) return <RouteFallback />
  const user = session.data ?? null
  if (user !== null) return <Navigate to={CABINET_PATH[user.role]} replace />
  return <Outlet />
}
