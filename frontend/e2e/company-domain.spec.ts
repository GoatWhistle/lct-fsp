import { expect, test } from "@playwright/test"
import { MAILPIT, prepare, settle, signIn } from "./support"

const EMPLOYER = "employer-2@demo.example"
const CANDIDATE = "qa-middle@demo.example"
const ADDRESS = "hr@retail.demo.example"

test.describe.configure({ mode: "serial" })
test.skip(!process.env.E2E_COMPANY_DOMAIN, "needs a seeded stand with Mailpit")

interface MailpitSearch {
  readonly messages: readonly { readonly ID: string }[]
}

test("employer confirms the company domain by mail", async ({ page, context, request }) => {
  await prepare(context)
  await signIn(page, EMPLOYER)
  await page.goto("/employer/company")
  const card = page.getByRole("region", { name: "Trust mark" })
  const field = card.getByLabel("Address on the website domain")
  await field.fill("hr@gmail.com")
  await card.getByRole("button", { name: "Send the email" }).click()
  await expect(card.getByText("The address must be on the company website domain.")).toBeVisible()
  await field.fill(ADDRESS)
  await card.getByRole("button", { name: "Send the email" }).click()
  await expect(card.getByText(`The email went to ${ADDRESS}. Open the link in it`)).toBeVisible()

  const search = await request.get(`${MAILPIT}/api/v1/search?query=to:${ADDRESS}`)
  const found = (await search.json()) as MailpitSearch
  const id = found.messages[0]?.ID
  expect(id).toBeDefined()
  const message = (await (await request.get(`${MAILPIT}/api/v1/message/${id}`)).json()) as {
    readonly Text: string
  }
  const link = /\/verify-domain\?token=(\S+)/.exec(message.Text)
  expect(link).not.toBeNull()
  await page.goto(`/verify-domain?token=${link?.[1] ?? ""}`)
  await expect(page.getByText("Domain retail.demo.example is confirmed")).toBeVisible()
  await page.goto("/employer/company")
  await expect(card.getByText("Domain confirmed", { exact: true })).toBeVisible()
  await settle(page)
  await page.screenshot({ path: "e2e/screenshots/issue-38-company.png", fullPage: true })
})

test("candidate sees the mark in the invitation", async ({ page, context }) => {
  await prepare(context)
  await signIn(page, CANDIDATE)
  await page.goto("/candidate/invitations")
  await page.locator("main a[href*='/candidate/invitations/']").first().click()
  await expect(page.getByRole("article").getByText("Domain confirmed", { exact: true })).toBeVisible()
  await settle(page)
  await page.screenshot({ path: "e2e/screenshots/issue-38-invitation.png", fullPage: true })
})
