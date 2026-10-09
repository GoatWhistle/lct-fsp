import { readdirSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"

const root = resolve(import.meta.dirname, "..")
const localesDir = join(root, "src", "shared", "i18n", "locales")
const target = join(root, "src", "shared", "i18n", "resources.ts")
const FIRST = ["common", "errors", "catalog", "measure"]

const files = readdirSync(join(localesDir, "en"))
  .filter((file) => file.endsWith(".json"))
  .map((file) => file.replace(/\.json$/, ""))
const namespaces = [
  ...FIRST.filter((name) => files.includes(name)),
  ...files.filter((name) => !FIRST.includes(name)).sort(),
]
const pascal = (name: string) =>
  name
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("")

const imports = ["en", "ru"]
  .flatMap((locale) =>
    namespaces.map(
      (name) => `import ${locale}${pascal(name)} from "./locales/${locale}/${name}.json"`,
    ),
  )
  .sort((left, right) => left.localeCompare(right))
const block = (locale: string) =>
  `const ${locale} = {\n${namespaces.map((name) => `  "${name}": ${locale}${pascal(name)},`).join("\n")}\n}`

const text = `${imports.join("\n")}
import type { Locale } from "./locale"

export const NAMESPACES = [${namespaces.map((name) => `"${name}"`).join(", ")}] as const

export type Namespace = (typeof NAMESPACES)[number]

export const DEFAULT_NAMESPACE: Namespace = "common"

${block("en")}

${block("ru")}

export type Dictionary = typeof en

export const resources = { en, ru } satisfies Record<Locale, Record<Namespace, object>>
`
writeFileSync(target, text)
process.stdout.write(`resources: ${namespaces.join(", ")}\n`)
