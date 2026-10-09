import { expect, type Page, test } from "@playwright/test"
import {
  EMPLOYER,
  PASSWORD,
  prepare,
  settle,
  signIn,
  uniqueEmail,
  verificationLink,
} from "./support"

const FSP_CANDIDATE = "devops-middle-fsp@demo.example"
const NEED_TEXT =
  "Looking for a middle DevOps engineer for the payments platform. Stack: Kubernetes, Terraform, Linux. Remote, from 250000 to 320000 rubles."

test.describe.configure({ mode: "serial" })

async function answerItem(page: Page) {
  await expect(page.getByRole("heading", { name: "Your answer" })).toBeVisible()
  await settle(page)
  const number = page.getByText(/Task \d+/).first()
  const before = await number.textContent()
  const field = page.getByPlaceholder("One-line answer")
  if (await field.isVisible()) await field.fill("42")
  else if (await page.getByRole("radio").first().isVisible()) await page.keyboard.press("1")
  await page.getByRole("button", { name: /^Answer/ }).click()
  await expect(number).not.toHaveText(before ?? "", { timeout: 20_000 })
}

test("1. home in dark theme switches language both ways", async ({ page, context }) => {
  await prepare(context, "dark")
  await page.goto("/")
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark")
  const languageButton = page.getByRole("button", { name: /:/ }).first()
  await expect(languageButton).toHaveAccessibleName(/Language/)
  await languageButton.click()
  await page.getByRole("menuitemradio").first().click()
  await expect(page.locator("html")).toHaveAttribute("lang", "ru")
  await settle(page)
  await languageButton.click()
  await page.getByRole("menuitemradio", { name: "English" }).click()
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
})

test("2 and 4. a new candidate signs up by email and starts the adaptive test", async ({
  page,
  context,
  request,
}) => {
  await prepare(context)
  const email = uniqueEmail("defense")
  await page.goto("/register?role=candidate")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD)
  const consent = page.getByRole("checkbox").last()
  await consent.evaluate((input: HTMLInputElement) => input.click())
  await expect(consent).toBeChecked()
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(page.getByText("Check your email")).toBeVisible()

  await page.goto(await verificationLink(request, email))
  await expect(page.getByText("Email confirmed")).toBeVisible()
  await page.goto("/login")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD)
  await page.getByRole("button", { name: "Sign in", exact: true }).click()
  await expect(page).toHaveURL(/\/candidate/)

  await page.goto("/candidate/path")
  await page.getByRole("radio", { name: /DevOps/ }).check({ force: true })
  await page.getByRole("button", { name: "Next: choose a grade" }).click()
  await page.getByRole("radio", { name: /Middle/ }).check({ force: true })
  await page.getByRole("button", { name: /Start the .* test/ }).click()
  await expect(page).toHaveURL(/\/candidate\/test/)
  for (let step = 0; step < 3; step += 1) await answerItem(page)
})

test("3. an FSP participant signs in with FSP ID and gets achievements", async ({
  page,
  context,
}) => {
  await prepare(context)
  await page.goto("/login")
  await page.getByRole("button", { name: "Sign in with FSP ID" }).click()
  await page.waitForURL(/realms/, { timeout: 30_000 })
  await page.locator("#username").fill("fsp-winner")
  await page.locator("#password").fill("fsp-demo-2026")
  await page.locator("#kc-login").click()
  await page.waitForURL(/\/candidate/, { timeout: 30_000 })
  await page.goto("/candidate/profile#fsp")
  await expect(page.locator("#fsp")).toContainText(/Winner|Prize|Finalist/)
})

test("5. a categorised candidate sees the skill profile and FSP signal", async ({
  page,
  context,
}) => {
  await prepare(context)
  await signIn(page, FSP_CANDIDATE)
  await page.goto("/candidate")
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  await expect(page.getByText("FSP").first()).toBeVisible()
  await expect(page.getByRole("img").first()).toBeVisible()
})

test("6 and 7. employer turns words into a shortlist and reads the explanation", async ({
  page,
  context,
}) => {
  await prepare(context)
  await signIn(page, EMPLOYER)
  await page.goto("/employer/needs/text")
  await page.getByRole("textbox").first().fill(NEED_TEXT)
  await page.getByRole("button", { name: "Parse" }).click()
  const build = page.getByRole("button", { name: "Build shortlist without saving" })
  await expect(build).toBeVisible({ timeout: 60_000 })
  if (await build.isEnabled()) {
    await build.click()
  } else {
    await page.goto("/employer/needs")
    await page
      .getByRole("button", { name: /Build shortlist|Rebuild/ })
      .last()
      .click()
  }
  await expect(page).toHaveURL(/\/employer\/selections\//, { timeout: 30_000 })

  await page.getByRole("button", { name: "How it works" }).click()
  await expect(page.getByText(/expected share of requirements/)).toBeVisible()
  await page.keyboard.press("Escape")

  const firstRow = page.locator("[data-candidate]").first()
  await firstRow.click()
  await expect(page).toHaveURL(/candidate=/)
  await expect(page.getByText("Why this candidate")).toBeVisible()
  await page.keyboard.press("s")
  await page.getByRole("button", { name: /^Favorites/ }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")

  const invite = page.getByRole("button", { name: "Invite" }).first()
  if (await invite.isVisible()) {
    await invite.click()
    await expect(page.getByRole("dialog")).toBeVisible()
    await expect(page.getByLabel(/From/).first()).not.toHaveValue("")
    await page.keyboard.press("Escape")
  }
})

test("8. candidate accepts the invitation and the employer sees contacts", async ({ browser }) => {
  const candidate = await browser.newContext()
  await prepare(candidate)
  const candidatePage = await candidate.newPage()
  await signIn(candidatePage, FSP_CANDIDATE)
  await candidatePage.goto("/candidate/invitations")
  await candidatePage.locator("main a[href*='/candidate/invitations/']").first().click()
  await expect(candidatePage.getByRole("article")).toBeVisible()
  await settle(candidatePage)
  const accept = candidatePage.getByRole("button", { name: "Accept", exact: true })
  if (await accept.isVisible()) {
    await accept.click()
    await candidatePage.getByRole("dialog").getByRole("button", { name: "Accept" }).click()
  }
  const composer = candidatePage.getByRole("textbox", { name: "Message" })
  await expect(composer).toBeVisible()
  await settle(candidatePage)
  await composer.fill("Hello, happy to talk this week")
  await candidatePage.getByRole("button", { name: "Send" }).click()
  await expect(candidatePage.getByText("Hello, happy to talk this week").first()).toBeVisible()
  await candidate.close()

  const employer = await browser.newContext()
  await prepare(employer)
  const employerPage = await employer.newPage()
  await signIn(employerPage, EMPLOYER)
  await employerPage.goto("/employer/invitations")
  await employerPage.locator("main a[href*='/employer/invitations/']").first().click()
  await settle(employerPage)
  await expect(employerPage.getByText(/@/).first()).toBeVisible()
  await employer.close()
})

test("9. candidate applies for a vacancy and the employer sees the application", async ({
  browser,
}) => {
  const candidate = await browser.newContext()
  await prepare(candidate)
  const candidatePage = await candidate.newPage()
  await signIn(candidatePage, FSP_CANDIDATE)
  await candidatePage.goto("/candidate/vacancies")
  await expect(candidatePage.getByRole("heading", { level: 1 })).toBeVisible()
  await settle(candidatePage)
  const apply = candidatePage.getByRole("button", { name: "Apply", exact: true }).first()
  if (await apply.isVisible()) {
    await apply.click()
    const confirm = candidatePage.getByRole("dialog").getByRole("button", { name: "Apply" })
    if (await confirm.isVisible()) await confirm.click()
  }
  await candidatePage.goto("/candidate/vacancies?tab=applications")
  await expect(candidatePage.locator("main")).toContainText(/sent|viewed|accepted|declined/)
  await candidate.close()

  const employer = await browser.newContext()
  await prepare(employer)
  const employerPage = await employer.newPage()
  await signIn(employerPage, EMPLOYER)
  await employerPage.goto("/employer/invitations?tab=applications")
  await expect(employerPage.locator("main")).toContainText(/Candidate|#/)
  await employer.close()
})

test("10. candidate downloads the PDF profile", async ({ page, context }) => {
  await prepare(context)
  await signIn(page, FSP_CANDIDATE)
  await page.goto("/candidate/profile")
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "Download PDF" }).click()
  const file = await download
  expect(file.suggestedFilename()).toMatch(/\.pdf$/)
})
