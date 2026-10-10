import type { APIRequestContext, BrowserContext, Page } from "@playwright/test"

export const PASSWORD = "demo-2026"
export const EMPLOYER = "employer@demo.example"
export const CANDIDATE = "devops-middle@demo.example"
export const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025"

export async function prepare(
  context: BrowserContext,
  theme: "light" | "dark" = "light",
  locale: "ru" | "en" = "en",
) {
  await context.addInitScript(
    (chosen) => {
      localStorage.setItem("calibr-theme", chosen.theme)
      localStorage.setItem("calibr-locale", chosen.locale)
      localStorage.setItem("calibr-test-intro", "false")
    },
    { theme, locale },
  )
}

export async function signIn(page: Page, email: string, password = PASSWORD) {
  const response = await page.request.post("/api/auth/login", { data: { email, password } })
  if (!response.ok()) throw new Error(`login failed for ${email}: ${response.status()}`)
}

export function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.round(Math.random() * 1e6)}@demo.example`
}

export async function verificationLink(request: APIRequestContext, email: string): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const search = await request.get(
      `${MAILPIT}/api/v1/search?query=to:${encodeURIComponent(email)}`,
    )
    const found = (await search.json()) as { messages: { ID: string }[] }
    const id = found.messages[0]?.ID
    if (id !== undefined) {
      const message = await request.get(`${MAILPIT}/api/v1/message/${id}`)
      const body = (await message.json()) as { Text: string }
      const match = /(https?:\/\/\S+\/verify-email\?token=[\w-]+)/.exec(body.Text)
      if (match?.[1] !== undefined) {
        const url = new URL(match[1])
        return `${url.pathname}${url.search}`
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`no verification letter for ${email}`)
}

export async function settle(page: Page) {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .filter((animation) => animation.timeline instanceof DocumentTimeline)
      .filter((animation) => animation.effect?.getTiming().iterations !== Number.POSITIVE_INFINITY)
      .every((animation) => animation.playState !== "running"),
  )
}

export async function openExplanation(page: Page) {
  await page.goto("/employer/needs", { waitUntil: "networkidle" })
  await page.locator("main a[href*='/employer/selections/']").first().click()
  await page.waitForURL(/\/employer\/selections\//)
  await page.locator("[data-candidate]").first().click()
  await page.waitForURL(/candidate=/)
  await page.waitForLoadState("networkidle")
}
