import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"

const ROOT = path.resolve(import.meta.dirname, "..")
const ICONS = path.resolve(ROOT, "..", "frontend", "node_modules", "lucide-react", "dist", "esm", "icons")
const SHELL = path.join(ROOT, "src", "shell.html")
const START = "<!-- icons:start -->"
const END = "<!-- icons:end -->"

const names = [
  "arrow-right",
  "badge-check",
  "banknote",
  "building",
  "circle-check",
  "circle-x",
  "clipboard-list",
  "code",
  "database",
  "eye",
  "file-text",
  "flask-conical",
  "gauge",
  "key-round",
  "layers",
  "list-checks",
  "lock",
  "lock-open",
  "mail",
  "message-square",
  "plug",
  "refresh-cw",
  "scale",
  "search",
  "send",
  "server",
  "shield-check",
  "target",
  "timer",
  "triangle-alert",
  "trophy",
  "user",
  "users",
  "wallet",
]

const attrs = (props) =>
  Object.entries(props)
    .filter(([key]) => key !== "key")
    .map(([key, value]) => `${key}="${value}"`)
    .join(" ")

const symbols = []
for (const name of names) {
  const mod = await import(pathToFileURL(path.join(ICONS, `${name}.mjs`)).href)
  const inner = mod.__iconData.node.map(([tag, props]) => `<${tag} ${attrs(props)}/>`).join("")
  symbols.push(`<symbol id="i-${name}" viewBox="0 0 24 24">${inner}</symbol>`)
}
const sprite = `${START}\n<svg class="sprite" aria-hidden="true">${symbols.join("")}</svg>\n${END}`
const shell = fs.readFileSync(SHELL, "utf8")
const next = shell.includes(START)
  ? shell.replace(new RegExp(`${START}[\s\S]*?${END}`), sprite)
  : shell.replace("<div class=\"viewport\">", `${sprite}\n<div class="viewport">`)
fs.writeFileSync(SHELL, next)
console.log(`icons: ${names.length}`)
