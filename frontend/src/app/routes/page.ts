import type { ComponentType } from "react"

type PageModule = Record<string, unknown>

export function page<Module extends PageModule>(
  load: () => Promise<Module>,
  name: keyof Module & string,
) {
  return async () => {
    const module = await load()
    return { Component: module[name] as ComponentType }
  }
}
