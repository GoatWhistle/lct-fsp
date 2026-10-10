import type { ComponentType } from "react"

type PageModule = Record<string, unknown>

const RELOAD_KEY = "calibr-chunk-reload"
const RELOAD_WINDOW_MS = 10_000

function reloadedRecently(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0)
    if (Date.now() - last < RELOAD_WINDOW_MS) return true
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
    return false
  } catch {
    return true
  }
}

async function loadFresh<Module>(load: () => Promise<Module>): Promise<Module> {
  try {
    return await load()
  } catch (error) {
    if (reloadedRecently()) throw error
    window.location.reload()
    return new Promise<Module>(() => undefined)
  }
}

export function page<Module extends PageModule>(
  load: () => Promise<Module>,
  name: keyof Module & string,
) {
  return async () => {
    const module = await loadFresh(load)
    return { Component: module[name] as ComponentType }
  }
}
