import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, resolve } from "node:path"
import { describe, expect, it } from "vitest"

const ROOT = resolve(process.cwd(), "src")
const LOCALES = join(ROOT, "shared/i18n/locales/en")
const NAMESPACES = readdirSync(LOCALES)
  .filter((file) => file.endsWith(".json"))
  .map((file) => file.replace(/\.json$/, ""))
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/
const STRING_LITERAL = /"([\w.:-]+)"/g
const TEMPLATE_PREFIX = /`(?:(\w+):)?([\w.]*)\$\{/g
const USE_TRANSLATION = /useTranslation\(\s*(?:"(\w+)"|\[([^\]]*)\])?/g

type Tree = { readonly [key: string]: unknown }

interface SourceUsage {
  readonly namespaces: readonly string[]
  readonly literals: ReadonlySet<string>
  readonly prefixes: readonly { readonly namespace: string | null; readonly prefix: string }[]
}

function leafKeys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([key, value]) =>
    typeof value === "object" && value !== null
      ? leafKeys(value as Tree, `${prefix}${key}.`)
      : [`${prefix}${key}`.replace(PLURAL_SUFFIX, "")],
  )
}

function sources(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.tsx?$/.test(entry) ? [readFileSync(path, "utf8")] : []
  })
}

function namespacesOf(text: string): string[] {
  return [...text.matchAll(USE_TRANSLATION)].flatMap((match) => {
    if (match[1] !== undefined) return [match[1]]
    if (match[2] !== undefined)
      return [...match[2].matchAll(/"(\w+)"/g)].map((item) => item[1] ?? "")
    return ["common"]
  })
}

function usageOf(text: string): SourceUsage {
  return {
    namespaces: namespacesOf(text),
    literals: new Set([...text.matchAll(STRING_LITERAL)].map((match) => match[1] ?? "")),
    prefixes: [...text.matchAll(TEMPLATE_PREFIX)].map((match) => ({
      namespace: match[1] ?? null,
      prefix: match[2] ?? "",
    })),
  }
}

const usages = sources(ROOT).map(usageOf)

function usedIn(usage: SourceUsage, namespace: string, key: string): boolean {
  const full = `${namespace}:${key}`
  if (usage.literals.has(full)) return true
  const local = usage.namespaces.includes(namespace)
  if (local && usage.literals.has(key)) return true
  return usage.prefixes.some((item) =>
    item.namespace === null
      ? local && item.prefix !== "" && key.startsWith(item.prefix)
      : item.namespace === namespace && key.startsWith(item.prefix),
  )
}

function isUsed(namespace: string, key: string): boolean {
  return usages.some((usage) => usedIn(usage, namespace, key))
}

describe("dictionaries", () => {
  it.each(NAMESPACES)("has no unused keys in %s", (namespace) => {
    const tree = JSON.parse(readFileSync(join(LOCALES, `${namespace}.json`), "utf8")) as Tree
    const unused = [...new Set(leafKeys(tree))].filter((key) => !isUsed(namespace, key))
    expect(unused).toEqual([])
  })
})
