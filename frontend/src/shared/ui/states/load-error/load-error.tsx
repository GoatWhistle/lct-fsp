import { useErrorText } from "../../../i18n"
import { ErrorState } from "../error-state/error-state"

export interface LoadErrorProps {
  readonly error: unknown
  readonly onRetry: () => void
  readonly pending?: boolean
}

export function LoadError({ error, onRetry, pending = false }: LoadErrorProps) {
  const errorText = useErrorText()
  return <ErrorState title={errorText(error)} onRetry={onRetry} retryPending={pending} />
}
