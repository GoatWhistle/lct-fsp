import { createBrowserRouter, type RouteObject } from "react-router"
import { GuestOnly } from "./guards/guest-only"
import { RequireRole } from "./guards/require-role"
import { RootLayout } from "./root-layout/root-layout"
import { RouteFallback } from "./route-fallback/route-fallback"
import { CANDIDATE_FOCUS_ROUTES, CANDIDATE_ROUTES } from "./routes/candidate-routes"
import { EMPLOYER_ROUTES } from "./routes/employer-routes"
import { page } from "./routes/page"

const PUBLIC_ROUTES: RouteObject[] = [
  { index: true, lazy: page(() => import("@/pages/home/home-page"), "HomePage") },
  { path: "login", lazy: page(() => import("@/pages/login/login-page"), "LoginPage") },
  { path: "register", lazy: page(() => import("@/pages/register/register-page"), "RegisterPage") },
]

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    hydrateFallbackElement: <RouteFallback />,
    children: [
      { element: <GuestOnly />, children: PUBLIC_ROUTES },
      {
        path: "verify-email",
        lazy: page(() => import("@/pages/verify-email/verify-email-page"), "VerifyEmailPage"),
      },
      {
        path: "candidate",
        children: [
          {
            element: <RequireRole allow="candidate" shell={false} />,
            children: CANDIDATE_FOCUS_ROUTES,
          },
          { element: <RequireRole allow="candidate" />, children: CANDIDATE_ROUTES },
        ],
      },
      {
        path: "employer",
        element: <RequireRole allow="employer" />,
        children: EMPLOYER_ROUTES,
      },
      { path: "*", lazy: page(() => import("@/pages/not-found/not-found-page"), "NotFoundPage") },
    ],
  },
])
