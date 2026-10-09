import type { InfiniteData } from "@tanstack/react-query"
import { levelFrom } from "@/entities/measure"
import type { Level, Selection, SelectionBlock, SelectionEntry, TopicFit } from "@/shared/api"

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
