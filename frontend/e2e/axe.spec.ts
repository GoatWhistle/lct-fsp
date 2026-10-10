import AxeBuilder from "@axe-core/playwright"
import { expect, type Page, test } from "@playwright/test"
import { CANDIDATE, EMPLOYER, openExplanation, prepare, signIn } from "./support"

const PUBLIC = ["/", "/login", "/register", "/missing-page"]
const CANDIDATE_ROUTES = [
  "/candidate",
  "/candidate/profile",
  "/candidate/invitations",
  "/candidate/vacancies",
  "/candidate/tasks",
]
const EMPLOYER_ROUTES = [
  "/employer",
  "/employer/needs",
  "/employer/needs/new",
  "/employer/needs/text",
  "/employer/candidates?spec=devops&grade=middle",
  "/employer/invitations",
  "/employer/vacancies",
  "/employer/tasks",
  "/employer/company",
]
const THEMES = ["light", "dark"] as const

async function audit(page: Page, route: string | null) {
  if (route !== null) await page.goto(route, { waitUntil: "networkidle" })
  await page.waitForTimeout(800)
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze()
  const serious = result.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => ({
      id: violation.id,
      help: violation.help,
      targets: violation.nodes.slice(0, 3).map((node) => node.target.join(" ")),
    }))
  expect(serious, `${route ?? page.url()}`).toEqual([])
}

for (const theme of THEMES) {
  test.describe(`axe ${theme}`, () => {
    test("public screens", async ({ page, context }) => {
      await prepare(context, theme)
      for (const route of PUBLIC) await audit(page, route)
    })

    test("candidate screens", async ({ page, context }) => {
      await prepare(context, theme)
      await signIn(page, CANDIDATE)
      for (const route of CANDIDATE_ROUTES) await audit(page, route)
    })

    test("employer screens", async ({ page, context }) => {
      await prepare(context, theme)
      await signIn(page, EMPLOYER)
      for (const route of EMPLOYER_ROUTES) await audit(page, route)
      await openExplanation(page)
      await audit(page, null)
    })
  })
}
