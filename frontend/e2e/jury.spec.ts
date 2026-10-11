import { expect, type Page, test } from "@playwright/test"
import { prepare, settle } from "./support"

test.describe.configure({ mode: "serial" })
test.skip(!process.env.E2E_JURY, "needs a stand with DEMO_MODE=true")

async function answerItem(page: Page) {
  await expect(page.getByRole("heading", { name: "Your answer" })).toBeVisible()
  await settle(page)
  const field = page.getByPlaceholder("One-line answer")
  if (await field.isVisible()) await field.fill("42")
  else if (await page.getByRole("radio").first().isVisible()) await page.keyboard.press("1")
  await page.getByRole("button", { name: /^Answer/ }).click()
}

test("new test candidate goes through the express test", async ({ page, context }) => {
  await prepare(context, "light")
  await page.goto("/login")
  await page.getByRole("button", { name: "New test candidate" }).click()
  await expect(page).toHaveURL(/\/candidate\/test/)
  await expect(page.getByText(/express/i).first()).toBeVisible()
  for (let step = 0; step < 8; step += 1) {
    await expect(page.getByText(new RegExp(`Task ${step + 1}, at most 8`))).toBeVisible()
    await answerItem(page)
  }
  await expect(page.getByText("Express estimate").first()).toBeVisible({ timeout: 20_000 })
  await page.screenshot({ path: "test-results/express-result.png" })
  const proceed = page.getByRole("button", { name: "Continue the full test" })
  if (await proceed.isVisible()) {
    await proceed.click()
    await expect(page).toHaveURL(/\/candidate\/test/)
    await expect(page.getByText(/Task 9, at most 30/)).toBeVisible()
  }
})

test("demo employer lands in the cabinet with shortlists and a way to describe a need", async ({
  page,
  context,
}) => {
  await prepare(context, "light")
  await page.goto("/login")
  await page.getByRole("button", { name: "Sign in as employer" }).click()
  await expect(page).toHaveURL(/\/employer$/)
  await expect(page.getByRole("link", { name: "New need" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Active shortlists" })).toBeVisible()
  await expect(page.getByText(/Middle/).first()).toBeVisible()
  await page.screenshot({ path: "test-results/jury-employer.png" })
})
