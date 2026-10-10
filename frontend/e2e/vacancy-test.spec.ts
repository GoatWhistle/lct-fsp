import { expect, type Page, test } from "@playwright/test"
import { prepare, settle, signIn } from "./support"

const EMPLOYER = "employer-2@demo.example"
const CANDIDATE = "qa-middle@demo.example"

test.describe.configure({ mode: "serial" })
test.skip(!process.env.E2E_VACANCY_TEST, "needs a freshly seeded stand: it sends an invitation")

interface NeedRow {
  readonly id: string
  readonly specialization: { readonly code: string }
  readonly grade: { readonly code: string }
}

async function qaNeed(page: Page): Promise<string> {
  const needs = (await (await page.request.get("/api/employer/needs")).json()) as NeedRow[]
  const need = needs.find((row) => row.specialization.code === "qa")
  if (need === undefined) throw new Error("demo employer has no QA need")
  return need.id
}

async function answerItem(page: Page) {
  await expect(page.getByRole("heading", { name: "Your answer" })).toBeVisible()
  await settle(page)
  const field = page.getByPlaceholder("One-line answer")
  if (await field.isVisible()) await field.fill("42")
  else if (await page.getByRole("radio").first().isVisible()) await page.keyboard.press("1")
  await page.getByRole("button", { name: /^Answer/ }).click()
}

let invitationId = ""

test("employer previews the vacancy test and attaches it", async ({ page, context, browser }) => {
  await prepare(context)
  await signIn(page, EMPLOYER)
  const needId = await qaNeed(page)

  await page.goto(`/employer/needs/${needId}`)
  await page.getByRole("button", { name: "Vacancy test" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog.getByRole("region", { name: "Test topics" })).toBeVisible()
  const examples = dialog.getByRole("article")
  await expect(examples.first()).toBeVisible()
  const before = await examples.allTextContents()
  await dialog.getByRole("button", { name: "Other samples" }).click()
  await expect.poll(async () => examples.allTextContents()).not.toEqual(before)
  await settle(page)
  await page.screenshot({ path: "e2e/screenshots/issue-14-preview.png", fullPage: true })
  await page.keyboard.press("Escape")

  const candidate = await browser.newContext()
  await prepare(candidate)
  const candidatePage = await candidate.newPage()
  await signIn(candidatePage, CANDIDATE)
  const me = (await (await candidatePage.request.get("/api/auth/me")).json()) as { id: string }
  await candidate.close()

  const sent = await page.request.post("/api/employer/invitations", {
    data: {
      candidate_id: me.id,
      description: "QA engineer for the payments team",
      salary_from: 200000,
      salary_to: 260000,
      contact: "Telegram @qa_hr",
      test_need_id: needId,
    },
  })
  expect(sent.status()).toBe(201)
  invitationId = ((await sent.json()) as { id: string }).id
})

test("candidate takes the test from the invitation", async ({ page, context }) => {
  await prepare(context)
  await signIn(page, CANDIDATE)
  await page.goto(`/candidate/invitations/${invitationId}`)
  const panel = page.getByRole("region", { name: "Vacancy test" })
  await expect(panel).toBeVisible()
  await panel.getByRole("button", { name: "Take the test" }).click()
  await expect(page).toHaveURL(/\/candidate\/test/)
  await expect(page.getByText(/Vacancy test:/).first()).toBeVisible()
  const back = page.getByRole("region", { name: "Vacancy test" })
  const number = page.getByText(/Task \d+ of \d+/).first()
  while (!(await back.isVisible())) {
    const before = await number.textContent()
    await answerItem(page)
    await expect(async () => {
      if (await back.isVisible()) return
      expect(await number.textContent()).not.toBe(before)
    }).toPass({ timeout: 20_000 })
  }
  await expect(page).toHaveURL(new RegExp(`/candidate/invitations/${invitationId}`))
  await expect(page.getByText("Test completed. The result went to the company")).toBeVisible()
})

test("employer sees the result only in the invitation", async ({ page, context }) => {
  await prepare(context)
  await signIn(page, EMPLOYER)
  await page.goto(`/employer/invitations/${invitationId}`)
  const panel = page.getByRole("region", { name: "Vacancy test" })
  await expect(panel.getByText("Test completed")).toBeVisible()
  await expect(panel.getByText("Requirements met")).toBeVisible()
  await expect(panel.locator("[data-probability-label]").first()).toBeVisible()
  await settle(page)
  await page.screenshot({ path: "e2e/screenshots/issue-14-result.png", fullPage: true })
})
