export { useTranslation } from "react-i18next"
export {
  BACKEND_CONTENT_LANG,
  BackendText,
  type BackendTextElement,
  type BackendTextProps,
} from "./backend-text"
export { createFormatters, type Formatters, type MeasureUnit } from "./formatters"
export { createI18n, i18n } from "./instance"
export {
  DEFAULT_LOCALE,
  isLocale,
  LOCALE_STORAGE_KEY,
  LOCALES,
  type Locale,
} from "./locale"
export { LocaleProvider, type LocaleProviderProps } from "./locale-provider"
export { NAMESPACES, type Namespace } from "./resources"
export { isSalaryRange, SALARY_STEP, useMoneyRange } from "./salary"
export { type CatalogNames, useCatalogNames } from "./use-catalog-names"
export { useDocumentTitle } from "./use-document-title"
export { errorCodeOf, useErrorText } from "./use-error-text"
export { useFormatters } from "./use-formatters"
export { type LocaleState, useLocale } from "./use-locale"
