import { expect, test } from "@playwright/test"
import { EMPLOYER, prepare, settle, signIn } from "./support"

const FSP_CANDIDATE = "devops-middle-fsp@demo.example"

test.describe.configure({ mode: "serial" })

test("9. candidate applies for a vacancy and the employer sees the application", async ({
  browser,
}) => {
  const owner = await browser.newContext()
  const ownerPage = await owner.newPage()
  await signIn(ownerPage, EMPLOYER)
  const published = await ownerPage.request.post("/api/employer/vacancies", {
    data: {
      title: "DevOps engineer for the payments platform",
      description: "Kubernetes, Terraform, CI",
      specialization: "devops",
      grade: "middle",
      work_formats: ["remote"],
      salary_from: 250000,
      salary_to: 320000,
    },
  })
  expect(published.ok()).toBeTruthy()
  await owner.close()

  const candidate = await browser.newContext()
  await prepare(candidate)
  const candidatePage = await candidate.newPage()
  await signIn(candidatePage, FSP_CANDIDATE)
  await candidatePage.goto("/candidate/vacancies")
  await expect(candidatePage.getByRole("heading", { level: 1 })).toBeVisible()
  await settle(candidatePage)
  const apply = candidatePage.getByRole("button", { name: "Apply", exact: true }).first()
  await candidatePage.locator("main a[href*='/candidate/vacancies/']").first().click()
  await expect(apply).toBeVisible({ timeout: 20_000 })
  await apply.click()
  await candidatePage.getByRole("button", { name: "Apply", exact: true }).last().click()
  await expect(candidatePage.getByText(/Application sent/).first()).toBeVisible()
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
