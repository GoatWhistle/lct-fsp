import fs from "node:fs"
import path from "node:path"
import { DeckError, ROOT, assemble } from "./assemble.mjs"

const strict = process.argv.includes("--strict")
const out = path.join(ROOT, "dist", "deck.html")

try {
  const { html, warnings, slides } = assemble({ inline: true, strict })
  fs.mkdirSync(path.dirname(out), { recursive: true })
  fs.writeFileSync(out, html)
  for (const warning of warnings) console.warn(`warn: ${warning}`)
  const size = fs.statSync(out).size
  if (size > 15 * 1024 * 1024) console.warn(`warn: deck is ${(size / 1024 / 1024).toFixed(1)} MB, compress images or video`)
  console.log(`dist/deck.html ${(size / 1024).toFixed(0)} KB, ${slides} slides${strict ? ", strict checks passed" : ""}`)
} catch (error) {
  if (!(error instanceof DeckError)) throw error
  console.error(`build failed\n${error.message}`)
  process.exit(1)
}
