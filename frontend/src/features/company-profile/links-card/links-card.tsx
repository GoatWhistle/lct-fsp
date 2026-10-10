import { useTranslation } from "@/shared/i18n"
import { Button, Card, ServiceIcon, serviceLabel, TextField, Tooltip } from "@/shared/ui"
import type { CompanyCardProps } from "../about-card/about-card"
import { badLink, MAX_LINKS } from "../company-form"
import styles from "./links-card.module.css"

export function LinksCard({ form, error, onChange, className }: CompanyCardProps) {
  const { t } = useTranslation("company")
  const links = form.links.length === 0 ? [""] : form.links
  const set = (index: number, value: string) =>
    onChange({ links: links.map((link, at) => (at === index ? value : link)) })
  const remove = (index: number) => onChange({ links: links.filter((_, at) => at !== index) })
  const invalid = error("links") !== undefined
  return (
    <Card level="section" title={t("sections.links")} motionIndex={2} className={className}>
      <ul className={styles.list}>
        {links.map((link, index) => (
          <li key={`link-${index.toString()}`} className={styles.row}>
            <Tooltip
              content={
                link.trim() === "" ? t("links.label") : (serviceLabel(link) ?? t("links.other"))
              }
            >
              <span className={styles.badge} data-known={serviceLabel(link) !== null}>
                <ServiceIcon href={link} />
              </span>
            </Tooltip>
            <TextField
              label={`${t("links.label")} ${(index + 1).toString()}`}
              hideLabel
              type="text"
              inputMode="url"
              value={link}
              onChange={(value) => set(index, value)}
              maxLength={300}
              placeholder={t("links.placeholder")}
              error={invalid && badLink(link) ? t("errors.links") : undefined}
              className={styles.input}
            />
            <Button
              variant="ghost"
              size="icon"
              icon="trash"
              disabled={links.length === 1 && link === ""}
              onClick={() => remove(index)}
            >
              {t("links.remove")}
            </Button>
          </li>
        ))}
      </ul>
      {links.length < MAX_LINKS ? (
        <Button
          variant="secondary"
          size="compact"
          icon="plus"
          className={styles.add}
          disabled={links.at(-1)?.trim() === ""}
          onClick={() => onChange({ links: [...links, ""] })}
        >
          {t("links.add")}
        </Button>
      ) : null}
    </Card>
  )
}
