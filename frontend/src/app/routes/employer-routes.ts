import type { RouteObject } from "react-router"
import { EMPLOYER_DESK_ROUTES } from "./employer-desk-routes"
import { EMPLOYER_HIRING_ROUTES } from "./employer-hiring-routes"

export const EMPLOYER_ROUTES: RouteObject[] = [...EMPLOYER_HIRING_ROUTES, ...EMPLOYER_DESK_ROUTES]
