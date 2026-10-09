import type { CSSProperties } from "react"
import { useTranslation } from "@/shared/i18n"
import { Icon } from "@/shared/ui"
import styles from "./map-event.module.css"
import { CITIES, type EventCityId, MAP_SIZE } from "./network"

const EAST_EDGE = 0.62

export interface MapEventProps {
  readonly city: EventCityId
}

export function MapEvent({ city }: MapEventProps) {
  const { t } = useTranslation("home")
  const [x, y] = CITIES[city]
  const position = {
    "--event-x": `${(x / MAP_SIZE.width) * 100}%`,
    "--event-y": `${(y / MAP_SIZE.height) * 100}%`,
  } as CSSProperties
  return (
    <div
      className={styles.event}
      style={position}
      data-side={x / MAP_SIZE.width > EAST_EDGE ? "start" : "end"}
      aria-live="polite"
    >
      <span className={styles.city}>{t(`map.cities.${city}`)}</span>
      <span className={styles.role}>{t(`map.events.${city}.role`)}</span>
      <span className={styles.signal}>
        <Icon name="check" size="sm" />
        {t(`map.events.${city}.signal`)}
      </span>
    </div>
  )
}
