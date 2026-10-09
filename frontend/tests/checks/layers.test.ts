import { describe, expect, it } from "vitest"
import { layerOf, layers } from "../../scripts/checks/rules/layers.ts"
import type { SourceFile } from "../../scripts/checks/types.ts"

const file = (path: string, text = "export const value = 1\n"): SourceFile => ({ path, text })
const importing = (path: string, specifier: string) =>
  file(path, `import { value } from "${specifier}"\nexport const used = value\n`)

const TARGETS = [
  file("src/shared/ui/index.ts"),
  file("src/entities/salary/salary-range/salary-range.tsx"),
  file("src/entities/grade/grade-ruler/grade-ruler.tsx"),
  file("src/features/selection/selection-row/selection-row.tsx"),
  file("src/features/invitation/invite-dialog/invite-dialog.tsx"),
  file("src/pages/selection/selection-page.tsx"),
  file("src/app/shell/app-shell.tsx"),
]

describe("layers", () => {
  it("names the layer of a path", () => {
    expect(
      ["src/shared/a.ts", "src/entities/x/a.ts", "src/features/x/a.ts", "src/main.tsx"].map(
        layerOf,
      ),
    ).toEqual(["shared", "entities", "features", "root"])
  })

  it("passes dependencies that point down", () => {
    const files = [
      ...TARGETS,
      importing("src/entities/salary/a.ts", "@/shared/ui"),
      importing("src/features/selection/a.ts", "@/entities/grade/grade-ruler/grade-ruler"),
      importing("src/features/selection/b.ts", "./selection-row/selection-row"),
      importing("src/pages/selection/a.ts", "@/features/invitation/invite-dialog/invite-dialog"),
      importing("src/app/a.ts", "@/pages/selection/selection-page"),
      importing("src/features/selection/c.tsx", "react"),
      importing("src/main.tsx", "./app/shell/app-shell"),
    ]
    expect(layers.run(files)).toEqual([])
  })

  it.each([
    ["src/shared/ui/probe.tsx", "@/entities/grade/grade-ruler/grade-ruler"],
    ["src/shared/ui/probe.tsx", "@/app/shell/app-shell"],
    ["src/entities/salary/probe.ts", "@/features/selection/selection-row/selection-row"],
    ["src/entities/salary/probe.ts", "@/entities/grade/grade-ruler/grade-ruler"],
    ["src/features/selection/probe.ts", "@/features/invitation/invite-dialog/invite-dialog"],
    ["src/features/selection/probe.ts", "@/pages/selection/selection-page"],
    ["src/pages/selection/probe.ts", "@/app/shell/app-shell"],
  ])("reports %s importing %s", (path, specifier) => {
    expect(layers.run([...TARGETS, importing(path, specifier)])).toHaveLength(1)
  })
})
