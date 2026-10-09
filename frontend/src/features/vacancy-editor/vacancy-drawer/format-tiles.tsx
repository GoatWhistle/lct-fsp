import type { WorkFormat } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { ChoiceTiles, Icon, type IconName } from "@/shared/ui"
import { WORK_FORMATS } from "../vacancy-form"
import styles from "./vacancy-drawer.module.css"

const FORMAT_ICON: Readonly<Record<WorkFormat, IconName>> = {
  office: "company",
  hybrid: "city",
  remote: "globe",
}

export interface FormatTilesProps {
  readonly selected: readonly WorkFormat[]
  readonly onToggle: (format: WorkFormat) => void
  readonly error?: string | undefined
}

export function FormatTiles({ selected, onToggle, error }: FormatTilesProps) {
  const { t } = useTranslation(["vacancyEditor", "catalog"])
  return (
    <div className={styles.group}>
      <ChoiceTiles
        legend={t("fields.formats")}
        columns="compact"
        layout="inline"
        value={null}
        selected={selected}
        onChange={onToggle}
        tiles={WORK_FORMATS.map((format) => ({
          value: format,
          title: t(`catalog:workFormat.${format}`),
          icon: FORMAT_ICON[format],
        }))}
      />
      {error === undefined ? null : (
        <p className={styles.error} role="alert">
          <Icon name="alert" size="sm" />
          {error}
        </p>
      )}
    </div>
  )
}
