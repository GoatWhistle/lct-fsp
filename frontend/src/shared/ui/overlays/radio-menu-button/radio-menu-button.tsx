import { type ReactNode, useCallback, useEffect, useId, useRef, useState } from "react"
import { settleDelay } from "../../../motion"
import { Button } from "../../primitives/button/button"
import type { IconName } from "../../primitives/icon/icon"
import { MenuItemRadio, MenuList } from "../menu/menu"
import type { Placement } from "../popover/popover"

export interface RadioMenuOption<Value extends string> {
  readonly value: Value
  readonly content: ReactNode
}

export interface RadioMenuButtonProps<Value extends string> {
  readonly icon: IconName
  readonly label: string
  readonly legend: string
  readonly value: Value
  readonly options: readonly RadioMenuOption<Value>[]
  readonly onChange: (value: Value) => void
  readonly placement?: Placement | undefined
}

export function RadioMenuButton<Value extends string>({
  icon,
  label,
  legend,
  value,
  options,
  onChange,
  placement,
}: RadioMenuButtonProps<Value>) {
  const [open, setOpen] = useState(false)
  const [viaKeyboard, setViaKeyboard] = useState(false)
  const menuId = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const settle = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(settle.current), [])

  const close = useCallback((restoreFocus: boolean) => {
    window.clearTimeout(settle.current)
    setOpen(false)
    if (restoreFocus) trigger.current?.focus()
  }, [])

  const choose = (next: Value) => {
    onChange(next)
    window.clearTimeout(settle.current)
    if (viaKeyboard) close(true)
    else settle.current = window.setTimeout(() => close(true), settleDelay())
  }

  return (
    <>
      <Button
        ref={trigger}
        variant="ghost"
        size="icon"
        icon={icon}
        title={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onKeyDown={() => setViaKeyboard(true)}
        onPointerDown={() => setViaKeyboard(false)}
        onClick={() => (open ? close(false) : setOpen(true))}
      >
        {label}
      </Button>
      <MenuList
        id={menuId}
        open={open}
        label={legend}
        anchorRef={trigger}
        instant={viaKeyboard}
        placement={placement}
        onClose={close}
      >
        {options.map((option) => (
          <MenuItemRadio
            key={option.value}
            checked={option.value === value}
            onSelect={() => choose(option.value)}
          >
            {option.content}
          </MenuItemRadio>
        ))}
      </MenuList>
    </>
  )
}
