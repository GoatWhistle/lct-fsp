import { clsx } from "clsx"
import type { CSSProperties } from "react"
import { useTranslation } from "@/shared/i18n"
import { EventPulse } from "./event-pulse"
import { MapEvent } from "./map-event"
import styles from "./map-network.module.css"
import {
  arcPath,
  CITIES,
  type CityId,
  cityTempo,
  EVENT_CITIES,
  HUB,
  LINKS,
  linkTempo,
  MAP_VIEWBOX,
  phase,
} from "./network"
import { useEventCycle } from "./use-event-cycle"

const CITY_IDS = Object.keys(CITIES) as CityId[]

export interface MapNetworkProps {
  readonly className?: string | undefined
}

export function MapNetwork({ className }: MapNetworkProps) {
  const { t } = useTranslation(["home", "common"])
  const active = EVENT_CITIES[useEventCycle(EVENT_CITIES.length)] ?? EVENT_CITIES[0]
  return (
    <figure className={clsx(styles.figure, className)}>
      <div className={styles.stage}>
        <svg className={styles.map} viewBox={MAP_VIEWBOX} role="img" aria-label={t("map.label")}>
          <g className={styles.land}>
            <use className={styles.ground} href="/brand/map-russia.svg#land" />
            <use className={styles.borders} href="/brand/map-russia.svg#borders" />
          </g>
          {LINKS.map((link, index) => {
            const d = arcPath(link)
            const style = { "--i": index, "--phase": phase(index) } as CSSProperties
            return (
              <g key={d} style={style} data-tempo={linkTempo(link)} data-reverse={index % 3 === 1}>
                <path className={styles.arc} data-long={link.long === true} d={d} pathLength={1} />
                <path className={styles.signalGlow} d={d} pathLength={1} />
                <path className={styles.signal} d={d} pathLength={1} />
              </g>
            )
          })}
          <EventPulse key={active} city={active} />
          {CITY_IDS.map((id, index) => {
            const [cx, cy] = CITIES[id]
            const hub = id === HUB
            return (
              <g key={id} style={{ "--i": index } as CSSProperties} data-tempo={cityTempo(index)}>
                <circle className={styles.ping} cx={cx} cy={cy} r={hub ? 4 : 2.6} />
                <circle
                  className={styles.city}
                  data-hub={hub}
                  data-active={id === active}
                  cx={cx}
                  cy={cy}
                  r={hub ? 4 : 2.6}
                />
              </g>
            )
          })}
        </svg>
        <MapEvent key={active} city={active} />
      </div>
      <figcaption className={styles.caption}>
        <span className={styles.captionTitle}>{t("common:brand.fspFull")}</span>
        {t("map.caption")}
      </figcaption>
    </figure>
  )
}
