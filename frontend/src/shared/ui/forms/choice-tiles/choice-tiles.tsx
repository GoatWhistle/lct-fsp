import { clsx } from "clsx"
import { type CSSProperties, type ReactNode, useId } from "react"
import { useInputModality } from "../../../motion"
import { Icon, type IconName } from "../../primitives/icon/icon"
import styles from "./choice-tiles.module.css"

export interface ChoiceTile<Value extends string> {
  readonly value: Value
  readonly title: ReactNode
  readonly description?: ReactNode
  readonly icon?: IconName | undefined
  readonly badge?: ReactNode
  readonly disabled?: boolean
  readonly disabledNote?: ReactNode
}

export interface ChoiceTilesProps<Value extends string> {
  readonly legend: string
  readonly hideLegend?: boolean
  readonly tiles: readonly ChoiceTile<Value>[]
  readonly value: Value | null
  readonly onChange: (value: Value) => void
  readonly selected?: readonly Value[] | undefined
  readonly columns?: "auto" | "compact"
  readonly layout?: "stacked" | "inline"
  readonly className?: string | undefined
}

export function ChoiceTiles<Value extends string>({
  legend,
  hideLegend = false,
  tiles,
  value,
  onChange,
  selected,
  columns = "auto",
  layout = "stacked",
  className,
}: ChoiceTilesProps<Value>) {
  const name = useId()
  const isOn = (tile: Value) => (selected === undefined ? tile === value : selected.includes(tile))
  const modality = useInputModality()
  return (
    <fieldset
      className={clsx(styles.tiles, className)}
      data-columns={columns}
      data-layout={layout}
      data-instant={modality.instant}
      onKeyDown={modality.onKeyDown}
      onPointerDown={modality.onPointerDown}
    >
      <legend className={hideLegend ? "visually-hidden" : styles.legend}>{legend}</legend>
      {tiles.map((tile, index) => (
        <label
          key={tile.value}
          className={styles.tile}
          data-checked={isOn(tile.value)}
          data-disabled={tile.disabled === true}
          style={{ "--i": index } as CSSProperties}
        >
          <input
            className={styles.input}
            type={selected === undefined ? "radio" : "checkbox"}
            name={name}
            value={tile.value}
            checked={isOn(tile.value)}
            disabled={tile.disabled === true}
            onChange={() => onChange(tile.value)}
          />
          <span className={styles.head}>
            {tile.icon === undefined ? null : (
              <Icon
                name={tile.disabled === true ? "lock" : tile.icon}
                size="lg"
                className={styles.icon}
              />
            )}
            {tile.badge === undefined ? null : <span className={styles.badge}>{tile.badge}</span>}
          </span>
          <span className={styles.title}>{tile.title}</span>
          {tile.description === undefined ? null : (
            <span className={styles.description}>
              {tile.disabled === true && tile.disabledNote !== undefined
                ? tile.disabledNote
                : tile.description}
            </span>
          )}
          <span className={styles.check} data-on={isOn(tile.value)} aria-hidden="true">
            <Icon name="check" size="sm" />
          </span>
        </label>
      ))}
    </fieldset>
  )
}
