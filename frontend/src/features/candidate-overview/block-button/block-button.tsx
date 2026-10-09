import { useNavigate } from "react-router"
import { useStartTopicBlock } from "@/entities/candidate-path"
import { useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { Button, type ButtonVariant, IconLabel, toast } from "@/shared/ui"
import { availableAt, TEST_ROUTE } from "../available-at"

export interface BlockButtonProps {
  readonly topic: string
  readonly blockedUntil?: string | null | undefined
  readonly variant?: ButtonVariant
}

export function BlockButton({
  topic,
  blockedUntil = null,
  variant = "secondary",
}: BlockButtonProps) {
  const { t } = useTranslation("overview")
  const format = useFormatters()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const start = useStartTopicBlock()
  const until = blockedUntil ?? availableAt(start.error)

  if (until !== null)
    return (
      <IconLabel icon="calendar" tone="secondary">
        {t("block.availableFrom", { date: format.dateMoscow(until) })}
      </IconLabel>
    )

  const run = () =>
    start.mutate(topic, {
      onSuccess: () => navigate(TEST_ROUTE, { viewTransition: true }),
      onError: (error) => {
        if (availableAt(error) === null) toast.error(errorText(error))
      },
    })

  return (
    <Button
      variant={variant}
      size="compact"
      icon="test"
      pending={start.isPending}
      pendingLabel={t("block.pending")}
      onClick={run}
    >
      {t("block.start")}
    </Button>
  )
}
