import { expect, test } from "@playwright/test"
import { CANDIDATE, EMPLOYER, prepare, signIn } from "./support"

const WIDTHS = [360, 768, 1280] as const
const THEMES = ["light", "dark"] as const
const LOCALES = ["ru", "en"] as const

const ROLE_SCENARIOS = [
  {
    role: "candidate",
    email: CANDIDATE,
    screenshotRoute: "/candidate/profile",
    routes: [
      "/candidate",
      "/candidate/path",
      "/candidate/test",
      "/candidate/reveal",
      "/candidate/profile",
      "/candidate/invitations",
      "/candidate/vacancies",
      "/candidate/tasks",
    ],
  },
  {
    role: "employer",
    email: EMPLOYER,
    screenshotRoute: "/employer/candidates?spec=devops&grade=middle",
    routes: [
      "/employer",
      "/employer/needs",
      "/employer/needs/new",
      "/employer/needs/text",
      "/employer/candidates?spec=devops&grade=middle",
      "/employer/invitations",
      "/employer/vacancies",
      "/employer/tasks",
      "/employer/company",
    ],
  },
] as const

for (const locale of LOCALES) {
  for (const theme of THEMES) {
    for (const scenario of ROLE_SCENARIOS) {
      for (const width of WIDTHS) {
        test(`${scenario.role} screens fit ${width}px in ${theme} theme and ${locale}`, async ({
          page,
          context,
        }, testInfo) => {
          await prepare(context, theme, locale)
          await page.setViewportSize({ width, height: 900 })
          await signIn(page, scenario.email)

          for (const route of scenario.routes) {
            await page.goto(route, { waitUntil: "networkidle" })
            const dimensions = await page.evaluate(() => ({
              documentWidth: document.documentElement.scrollWidth,
              viewportWidth: document.documentElement.clientWidth,
              clippedProbability: [
                ...document.querySelectorAll<HTMLElement>("[data-probability-label]"),
              ].some((label) => {
                const surface =
                  label.closest<HTMLElement>("[data-probability-surface]") ?? label.parentElement
                if (surface === null) return label.scrollWidth > label.clientWidth
                const labelBounds = label.getBoundingClientRect()
                const surfaceBounds = surface.getBoundingClientRect()
                return labelBounds.right > surfaceBounds.right + 1
              }),
            }))
            expect(
              dimensions.documentWidth,
              `${route} overflows at ${width}px in ${locale}`,
            ).toBeLessThanOrEqual(dimensions.viewportWidth)
            expect(dimensions.clippedProbability, `${route} clips a probability label`).toBe(false)

            if (
              route === scenario.screenshotRoute &&
              locale === "ru" &&
              theme === "light" &&
              width !== 768
            ) {
              const name = `issue-20-${scenario.role}-${width}px.png`
              const image = await page.screenshot({
                path: `e2e/screenshots/${name}`,
                fullPage: true,
              })
              await testInfo.attach(name, { body: image, contentType: "image/png" })
            }
          }
        })
      }
    }
  }
}
