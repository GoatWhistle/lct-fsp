import { useSyncExternalStore } from "react"

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (listener) => {
      const list = globalThis.matchMedia?.(query)
      list?.addEventListener("change", listener)
      return () => list?.removeEventListener("change", listener)
    },
    () => globalThis.matchMedia?.(query).matches ?? false,
    () => false,
  )
}
