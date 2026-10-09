import { clsx } from "clsx"
import styles from "./flag.module.css"
import gb from "./gb.svg"
import ru from "./ru.svg"

export type FlagCode = "ru" | "gb"

const FLAG_SOURCES: Readonly<Record<FlagCode, string>> = { ru, gb }

const FLAG_WIDTH = 20
const FLAG_HEIGHT = 15

export interface FlagProps {
  readonly code: FlagCode
  readonly className?: string | undefined
}

export function Flag({ code, className }: FlagProps) {
  return (
    <img
      className={clsx(styles.flag, className)}
      src={FLAG_SOURCES[code]}
      alt=""
      width={FLAG_WIDTH}
      height={FLAG_HEIGHT}
      data-flag={code}
    />
  )
}
