import { type AstNode, parseScript } from "../parse.ts"
import { resolveSpecifier } from "../paths.ts"
import { type Check, isScript, type SourceFile, type Violation } from "../types.ts"

const MODULE_NODES = new Set([
  "ImportDeclaration",
  "ExportNamedDeclaration",
  "ExportAllDeclaration",
])
const SLICE = /^src\/(features|entities)\/([^/]+)\//

export type Layer = "shared" | "entities" | "features" | "pages" | "app" | "root"

export function layerOf(path: string): Layer {
  if (path.startsWith("src/shared/")) return "shared"
  if (path.startsWith("src/entities/")) return "entities"
  if (path.startsWith("src/features/")) return "features"
  if (path.startsWith("src/pages/")) return "pages"
  if (path.startsWith("src/app/")) return "app"
  return "root"
}

const ALLOWED: Readonly<Record<Layer, ReadonlySet<Layer>>> = {
  shared: new Set(["shared"]),
  entities: new Set(["shared", "entities"]),
  features: new Set(["shared", "entities", "features"]),
  pages: new Set(["shared", "entities", "features", "pages"]),
  app: new Set(["shared", "entities", "features", "pages", "app"]),
  root: new Set(["shared", "entities", "features", "pages", "app", "root"]),
}

export function moduleSpecifiers(file: SourceFile): string[] {
  const body = parseScript(file.path, file.text).program.body as readonly AstNode[]
  return body.flatMap((node) => {
    if (!MODULE_NODES.has(node.type)) return []
    const source = node.source as { value?: unknown } | null | undefined
    return typeof source?.value === "string" ? [source.value] : []
  })
}

export function layerProblem(
  from: string,
  specifier: string,
  target: string | null,
): string | null {
  const source = layerOf(from)
  const bare = target === null && !specifier.startsWith(".") && !specifier.startsWith("@/")
  if (bare || target === null) return null
  const destination = layerOf(target)
  if (!ALLOWED[source].has(destination)) return `${source} imports ${destination}: ${target}`
  const own = SLICE.exec(from)
  const other = SLICE.exec(target)
  if (own !== null && other !== null && own[1] === other[1] && own[2] !== other[2])
    return `${own[1]} ${own[2]} imports ${other[1]} ${other[2]}`
  return null
}

export const layers: Check = {
  id: "layers",
  run: (files) => {
    const sources = files.filter((file) => file.path.startsWith("src/"))
    const known = new Set(sources.map((file) => file.path))
    return sources
      .filter((file) => isScript(file.path))
      .flatMap((file) =>
        moduleSpecifiers(file).flatMap((specifier): Violation[] => {
          const target = resolveSpecifier(file.path, specifier, known)
          const problem = layerProblem(file.path, specifier, target)
          return problem === null ? [] : [{ file: file.path, message: problem }]
        }),
      )
  },
}
