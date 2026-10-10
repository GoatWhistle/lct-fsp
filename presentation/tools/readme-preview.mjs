import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { launch } from "./browser.mjs"

const repo = path.resolve(import.meta.dirname, "..", "..")
const readme = fs.readFileSync(path.join(repo, "README.md"), "utf8")
const head = readme.slice(0, readme.indexOf("> **"))
const out = path.join(repo, "presentation", "shots")
fs.mkdirSync(out, { recursive: true })
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}
main{max-width:1012px;margin:0 auto;padding:32px}
p{margin:0 0 16px}
@media (prefers-color-scheme: dark){body{background:#0d1117;color:#e6edf3}}
@media (prefers-color-scheme: light){body{background:#ffffff;color:#1f2328}}
</style></head><body><main>${head}</main></body></html>`
fs.writeFileSync(path.join(repo, "preview.html"), html)
const browser = await launch()
for (const scheme of ["light", "dark"]) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 }, colorScheme: scheme })
  await page.goto(pathToFileURL(path.join(repo, "preview.html")).href)
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(out, `readme-${scheme}.png`), fullPage: true })
  await page.close()
}
await browser.close()
fs.rmSync(path.join(repo, "preview.html"))
console.log("shots/readme-light.png, shots/readme-dark.png: the README header as GitHub shows it")
