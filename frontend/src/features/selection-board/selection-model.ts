import type { InfiniteData } from "@tanstack/react-query"
import { levelFrom } from "@/entities/measure"
import type {
  AcceptanceExplanation,
  AcceptanceFactor,
  Level,
  Selection,
  SelectionBlock,
  SelectionEntry,
  TopicFit,
} from "@/shared/api"

export const BLOCKS: readonly SelectionBlock[] = ["exact", "nearby", "unconfirmed"]

export function entriesOf(data: InfiniteData<Selection, unknown> | undefined): SelectionEntry[] {
  return data?.pages.flatMap((page) => page.entries) ?? []
}

export function hasFsp(entry: SelectionEntry): boolean {
  return entry.topics.some((topic) => topic.fsp_confirmed)
}

export function levelOf(topic: TopicFit): Level {
  return levelFrom(topic.theta, topic.theta_sd)
}

export interface FactorBar {
  readonly factor: AcceptanceFactor
  readonly contribution: number
  readonly share: number
}

export function factorBars(why: AcceptanceExplanation): FactorBar[] {
  const peak = Math.max(...why.factors.map((item) => Math.abs(item.contribution)), Number.EPSILON)
  return why.factors
    .map((item) => ({
      factor: item.factor,
      contribution: item.contribution,
      share: Math.abs(item.contribution) / peak,
    }))
    .sort((a, b) => b.share - a.share)
}
