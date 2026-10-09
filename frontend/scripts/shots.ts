import { mkdirSync } from "node:fs"
import { join, resolve } from "node:path"
import { type Browser, chromium, type Page } from "playwright-core"

interface Options {
  readonly base: string
  readonly routes: readonly string[]
  readonly widths: readonly number[]
  readonly themes: readonly string[]
  readonly locales: readonly string[]
  readonly login: string | null
  readonly out: string
  readonly wait: number
  readonly full: boolean
}

const HEIGHT = 900

function option(name: string, fallback: string): string {
  const index = process.argv.indexOf(`--${name}`)
  return index === -1 ? fallback : (process.argv[index + 1] ?? fallback)
}

function parse(): Options {
  return {
    base: option("base", "http://localhost:5180"),
    routes: option("routes", "/").split(","),
    widths: option("widths", "1440").split(",").map(Number),
    themes: option("themes", "light").split(","),
    locales: option("locales", "ru").split(","),
    login: process.argv.includes("--login") ? option("login", "") : null,
    out: resolve(option("out", "screenshots/latest")),
    wait: Number(option("wait", "900")),
    full: process.argv.includes("--full"),
  }
}

async function signIn(page: Page, base: string, credentials: string): Promise<void> {
  const [email, password] = credentials.split(":")
  const response = await page.request.post(`${base}/api/auth/login`, {
    data: { email, password },
  })
  if (!response.ok()) throw new Error(`login failed: ${response.status()}`)
}

async function shoot(browser: Browser, options: Options): Promise<void> {
  for (const theme of options.themes) {
    for (const locale of options.locales) {
      const context = await browser.newContext({ viewport: { width: 1440, height: HEIGHT } })
      await context.addInitScript(
        ([chosenTheme, chosenLocale]) => {
          localStorage.setItem("calibr-theme", chosenTheme ?? "light")
          localStorage.setItem("calibr-locale", chosenLocale ?? "ru")
        },
        [theme, locale],
      )
      const page = await context.newPage()
      if (options.login !== null) await signIn(page, options.base, options.login)
      for (const route of options.routes) {
        for (const width of options.widths) {
          await page.setViewportSize({ width, height: HEIGHT })
          await page.goto(`${options.base}${route}`, { waitUntil: "networkidle" })
          await page.waitForTimeout(options.wait)
          const name = `${route.replace(/[^\w]+/g, "_") || "root"}-${width}-${theme}-${locale}.png`
          await page.screenshot({ path: join(options.out, name), fullPage: options.full })
          process.stdout.write(`${name}\n`)
        }
      }
      await context.close()
    }
  }
}

const options = parse()
mkdirSync(options.out, { recursive: true })
const browser = await chromium.launch({ channel: "chrome" })
try {
  await shoot(browser, options)
} finally {
  await browser.close()
}
