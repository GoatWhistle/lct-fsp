import type { Level, StackFit, TopicFit } from "@/shared/api"

export const SAMPLE_LEVEL: Level = {
  theta: 0.92,
  theta_sd: 0.28,
  band: { low: "middle", high: "middle", confident: true },
}

function topic(
  code: string,
  importance: TopicFit["importance"],
  weight: number,
  probability: number,
  verdict: TopicFit["verdict"],
): TopicFit {
  return {
    topic: { code, name: code },
    importance,
    weight,
    requirement: 0.5,
    theta: 0.9,
    theta_sd: 0.3,
    probability,
    contribution: weight * probability * 0.85,
    verdict,
    low_data: false,
    regular_task: false,
    verification_confirmed: false,
    fsp_confirmed: code === "backend.algorithms",
  }
}

export const SAMPLE_TOPICS: readonly TopicFit[] = [
  topic("backend.databases", "key", 0.3, 0.94, "confidently_above"),
  topic("backend.api", "key", 0.3, 0.86, "likely_above"),
  topic("backend.algorithms", "important", 0.24, 0.97, "confidently_above"),
  topic("backend.testing", "nice", 0.16, 0.41, "likely_below"),
]

export const SAMPLE_STACK: StackFit = {
  matched: [],
  total: 5,
  overlap: 0.6,
  contribution: 0.09,
}

export const SAMPLE_STACK_CAP = 0.15

export const SAMPLE_SCORE = SAMPLE_TOPICS.reduce(
  (sum, item) => sum + item.weight * item.probability * (1 - SAMPLE_STACK_CAP),
  SAMPLE_STACK_CAP * SAMPLE_STACK.overlap,
)
