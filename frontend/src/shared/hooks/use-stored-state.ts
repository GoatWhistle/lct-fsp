import { useCallback, useState } from "react"

function read<Value>(key: string, fallback: Value, parse: (raw: string) => Value | null): Value {
  try {
    const raw = globalThis.localStorage?.getItem(key)
    if (raw === null || raw === undefined) return fallback
    return parse(raw) ?? fallback
  } catch {
    return fallback
  }
}

export function useStoredFlag(key: string, fallback: boolean): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState(() =>
    read(key, fallback, (raw) => (raw === "true" ? true : raw === "false" ? false : null)),
  )
  const update = useCallback(
    (next: boolean) => {
      setValue(next)
      try {
        globalThis.localStorage?.setItem(key, String(next))
      } catch {
        return
      }
    },
    [key],
  )
  return [value, update]
}
