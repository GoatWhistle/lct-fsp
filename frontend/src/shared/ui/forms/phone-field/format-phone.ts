const COUNTRY = "7"
const TRUNK = "8"
const LOCAL_LENGTH = 10

function digitsOf(text: string): string {
  return text.replace(/\D/g, "")
}

function localDigits(text: string): string {
  const digits = digitsOf(text)
  if (digits === "") return ""
  const national = digits.startsWith(COUNTRY) || digits.startsWith(TRUNK) ? digits.slice(1) : digits
  return national.slice(0, LOCAL_LENGTH)
}

export function formatPhone(text: string): string {
  const local = localDigits(text)
  if (local === "" && digitsOf(text) === "") return ""
  const parts = [`+${COUNTRY}`]
  if (local.length > 0) parts.push(` (${local.slice(0, 3)}`)
  if (local.length >= 3) parts.push(")")
  if (local.length > 3) parts.push(` ${local.slice(3, 6)}`)
  if (local.length > 6) parts.push(`-${local.slice(6, 8)}`)
  if (local.length > 8) parts.push(`-${local.slice(8, 10)}`)
  return parts.join("")
}

export function nextPhone(previous: string, typed: string): string {
  const removed = typed.length < previous.length
  if (removed && digitsOf(typed) === digitsOf(formatPhone(previous))) {
    const local = localDigits(previous)
    return local.length <= 1 ? "" : formatPhone(`${COUNTRY}${local.slice(0, -1)}`)
  }
  return formatPhone(typed)
}

export function isPhoneComplete(text: string): boolean {
  return localDigits(text).length === LOCAL_LENGTH
}
