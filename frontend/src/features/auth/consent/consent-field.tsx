import { useState } from "react"
import type { Role } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Button, Card, Checkbox, Dialog } from "@/shared/ui"
import styles from "./consent-field.module.css"

const PURPOSES: Readonly<Record<Role, readonly string[]>> = {
  candidate: ["purpose1", "purpose2", "purpose3"],
  employer: ["purpose1", "purpose2"],
}

const DATA: Readonly<Record<Role, readonly string[]>> = {
  candidate: ["data1", "data2", "data3", "data4", "data5"],
  employer: ["data1", "data2", "data3"],
}

export interface ConsentFieldProps {
  readonly role: Role
  readonly checked: boolean
  readonly onChange: (checked: boolean) => void
}

export function ConsentField({ role, checked, onChange }: ConsentFieldProps) {
  const { t } = useTranslation("auth")
  const [open, setOpen] = useState(false)
  const item = (key: string) => t(`auth:consent.${role}.${key}` as never)
  return (
    <>
      <Checkbox
        checked={checked}
        onChange={onChange}
        label={
          <>
            {t("consent.agree")}{" "}
            <Button variant="link" onClick={() => setOpen(true)}>
              {t("consent.link")}
            </Button>
          </>
        }
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={t("consent.title")}
        size="wide"
        actions={<Button onClick={() => setOpen(false)}>{t("consent.ok")}</Button>}
      >
        <div className={styles.text}>
          <p>{t("consent.intro")}</p>
          <Card level="section" title={t("consent.purposes")}>
            <ul className={styles.list}>
              {PURPOSES[role].map((key) => (
                <li key={key}>{item(key)}</li>
              ))}
            </ul>
          </Card>
          <Card level="section" title={t("consent.data")}>
            <ul className={styles.list}>
              {DATA[role].map((key) => (
                <li key={key}>{item(key)}</li>
              ))}
            </ul>
          </Card>
          <p>{t("consent.actions")}</p>
          <p>{t("consent.term")}</p>
        </div>
      </Dialog>
    </>
  )
}
