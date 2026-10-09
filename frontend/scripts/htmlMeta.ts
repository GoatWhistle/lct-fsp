import { readFileSync } from "node:fs"
import { join } from "node:path"
import type { Plugin } from "vite"

interface MetaWords {
  readonly title: string
  readonly lead: string
  readonly byFsp: string
}

function escapeAttribute(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;")
}

export function metaWords(localesDir: string, locale: string): MetaWords {
  const read = (name: string) =>
    JSON.parse(readFileSync(join(localesDir, locale, `${name}.json`), "utf8"))
  const home = read("home") as { hero: { title: string; lead: string } }
  const common = read("common") as { app: { byFsp: string } }
  return { title: home.hero.title, lead: home.hero.lead, byFsp: common.app.byFsp }
}

export function htmlMeta(localesDir: string, locale = "ru"): Plugin {
  return {
    name: "calibr-html-meta",
    transformIndexHtml(html) {
      const words = metaWords(localesDir, locale)
      const values: Readonly<Record<string, string>> = {
        "%meta.title%": `${words.byFsp}: ${words.title.charAt(0).toLowerCase()}${words.title.slice(1)}`,
        "%meta.lead%": words.lead,
      }
      return Object.entries(values).reduce(
        (result, [token, value]) => result.replaceAll(token, escapeAttribute(value)),
        html,
      )
    },
  }
}
