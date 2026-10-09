import { act, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import {
  createI18n,
  LOCALE_STORAGE_KEY,
  LocaleProvider,
  useDocumentTitle,
  useLocale,
  useTranslation,
} from "@/shared/i18n"
import en from "@/shared/i18n/locales/en/common.json"
import ru from "@/shared/i18n/locales/ru/common.json"

function Probe() {
  const { t } = useTranslation()
  useDocumentTitle(null)
  const { locale, setLocale } = useLocale()
  return (
    <button type="button" data-locale={locale} onClick={() => setLocale("en")}>
      {t("action.close")}
    </button>
  )
}

describe("LocaleProvider", () => {
  afterEach(() => localStorage.clear())

  it("renders russian by default and sets the document language", () => {
    Object.defineProperty(navigator, "languages", { value: ["ru-RU"], configurable: true })
    render(
      <LocaleProvider instance={createI18n()}>
        <Probe />
      </LocaleProvider>,
    )
    expect(screen.getByRole("button").textContent).toBe(ru.action.close)
    expect(document.documentElement.lang).toBe("ru")
    expect(document.title).toBe(ru.app.documentTitle)
  })

  it("translates the document title with the interface", async () => {
    Object.defineProperty(navigator, "languages", { value: ["ru-RU"], configurable: true })
    render(
      <LocaleProvider instance={createI18n()}>
        <Probe />
      </LocaleProvider>,
    )
    await act(async () => screen.getByRole("button").click())
    expect(document.title).toBe(en.app.documentTitle)
  })

  it("switches language, stores the choice and updates lang", async () => {
    render(
      <LocaleProvider instance={createI18n()}>
        <Probe />
      </LocaleProvider>,
    )
    await act(async () => screen.getByRole("button").click())
    expect(screen.getByRole("button").textContent).toBe(en.action.close)
    expect(screen.getByRole("button").dataset.locale).toBe("en")
    expect(document.documentElement.lang).toBe("en")
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en")
  })

  it("restores the stored locale", () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, "en")
    render(
      <LocaleProvider instance={createI18n()}>
        <Probe />
      </LocaleProvider>,
    )
    expect(screen.getByRole("button").textContent).toBe(en.action.close)
  })

  it("falls back to the browser language for an unknown stored locale", () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, "de")
    Object.defineProperty(navigator, "languages", { value: ["en-US"], configurable: true })
    render(
      <LocaleProvider instance={createI18n()}>
        <Probe />
      </LocaleProvider>,
    )
    expect(screen.getByRole("button").dataset.locale).toBe("en")
  })

  it("falls back to russian when the browser language is unsupported", () => {
    Object.defineProperty(navigator, "languages", { value: ["de-DE"], configurable: true })
    render(
      <LocaleProvider instance={createI18n()}>
        <Probe />
      </LocaleProvider>,
    )
    expect(screen.getByRole("button").dataset.locale).toBe("ru")
  })
})
