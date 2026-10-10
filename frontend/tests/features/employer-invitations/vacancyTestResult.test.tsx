import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"
import { VacancyTestResult } from "@/features/employer-invitations/vacancy-test-result/vacancy-test-result"
import type { VacancyTest } from "@/shared/api"
import { i18n, LocaleProvider } from "@/shared/i18n"
import vacancyTest from "@/shared/i18n/locales/en/vacancyTest.json"

const PLAN: VacancyTest["plan"] = {
  specialization: { code: "qa", name: "QA" },
  grade: { code: "middle", name: "Middle" },
  items: 12,
  topics: [
    {
      topic: { code: "qa.automation", name: "Automation" },
      importance: "key",
      weight: 0.6,
      items: 7,
    },
    {
      topic: { code: "qa.databases", name: "Databases" },
      importance: "important",
      weight: 0.4,
      items: 5,
    },
  ],
}

function test(changes: Partial<VacancyTest>): VacancyTest {
  return {
    need_title: "QA middle",
    plan: PLAN,
    status: "not_started",
    answered: 0,
    result: null,
    ...changes,
  }
}

function show(value: VacancyTest) {
  return render(
    <LocaleProvider>
      <VacancyTestResult test={value} />
    </LocaleProvider>,
  )
}

beforeEach(async () => {
  await i18n.changeLanguage("en")
})

describe("VacancyTestResult", () => {
  it("shows the plan until the candidate finishes", () => {
    show(test({ status: "in_progress", answered: 3 }))
    expect(screen.getByText("Test in progress: 3 of 12")).toBeTruthy()
    expect(screen.getByText("12 items")).toBeTruthy()
    expect(screen.getByText("7 items")).toBeTruthy()
  })

  it("shows topic results as intervals, not bare probabilities", () => {
    show(
      test({
        status: "finished",
        answered: 12,
        result: {
          finished_at: "2026-10-10T12:00:00Z",
          match: 0.55,
          topics: [
            {
              topic: PLAN.topics[0]?.topic ?? { code: "", name: "" },
              answered: 7,
              correct: 5,
              level: 0.8,
              level_sd: 0.4,
              probability: 0.83,
            },
          ],
        },
      }),
    )
    expect(screen.getByText(vacancyTest.status.finished)).toBeTruthy()
    expect(screen.getByText("5 of 7 correct")).toBeTruthy()
    expect(screen.getByText("80–100%")).toBeTruthy()
    expect(document.body.textContent).not.toContain("83")
  })
})
