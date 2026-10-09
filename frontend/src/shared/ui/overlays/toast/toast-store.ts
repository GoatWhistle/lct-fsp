export type ToastTone = "success" | "error" | "info"

export interface ToastAction {
  readonly label: string
  readonly onAction: () => void
}

export interface ToastItem {
  readonly id: number
  readonly tone: ToastTone
  readonly message: string
  readonly action?: ToastAction | undefined
}

type Listener = () => void

let items: readonly ToastItem[] = []
let nextId = 1
const listeners = new Set<Listener>()
const MAX_VISIBLE = 3

function emit(): void {
  for (const listener of listeners) listener()
}

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function readToasts(): readonly ToastItem[] {
  return items
}

export function dismissToast(id: number): void {
  items = items.filter((item) => item.id !== id)
  emit()
}

function push(tone: ToastTone, message: string, action?: ToastAction): number {
  const id = nextId
  nextId += 1
  items = [...items, { id, tone, message, action }].slice(-MAX_VISIBLE)
  emit()
  return id
}

export const toast = {
  success: (message: string, action?: ToastAction) => push("success", message, action),
  error: (message: string, action?: ToastAction) => push("error", message, action),
  info: (message: string, action?: ToastAction) => push("info", message, action),
}

export function clearToasts(): void {
  items = []
  emit()
}
