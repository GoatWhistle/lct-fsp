export const REVEAL_ROUTE = "/candidate/reveal"

export interface RevealState {
  readonly fresh: true
  readonly attempted: string | null
}

export function isRevealState(state: unknown): state is RevealState {
  return typeof state === "object" && state !== null && "fresh" in state
}
