import { useState } from "react"
import { Button } from "../../primitives/button/button"
import { TextField, type TextFieldProps } from "../text-field/text-field"

export interface PasswordFieldProps extends Omit<TextFieldProps, "type" | "trailing" | "icon"> {
  readonly showText: string
  readonly hideText: string
}

export function PasswordField({ showText, hideText, ...rest }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)
  const toggle = visible ? hideText : showText
  return (
    <TextField
      {...rest}
      type={visible ? "text" : "password"}
      icon="key"
      trailing={
        <Button
          variant="ghost"
          size="icon"
          icon={visible ? "eye-off" : "eye"}
          title={toggle}
          aria-pressed={visible}
          onClick={() => setVisible(!visible)}
        >
          {toggle}
        </Button>
      }
    />
  )
}
