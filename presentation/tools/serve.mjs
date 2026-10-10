import fs from "node:fs"
import http from "node:http"
import path from "node:path"
import { DeckError, MIME, SRC, assemble } from "./assemble.mjs"

const port = Number(process.env.PORT || 4173)
const clients = new Set()
const reload = '<script>new EventSource("/__reload").onmessage = () => location.reload()</script>'
const escapeHtml = (text) => String(text).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c])

const page = () => {
  try {
    const { html, warnings } = assemble({ inline: false })
    for (const warning of warnings) console.warn(`warn: ${warning}`)
    return { status: 200, body: html.replace("</body>", `${reload}\n</body>`) }
  } catch (error) {
    if (!(error instanceof DeckError)) throw error
    console.error(error.message)
    return {
      status: 500,
      body: `<!doctype html><meta charset="utf-8"><title>deck build error</title><pre style="font:16px/1.5 ui-monospace,monospace;padding:32px;white-space:pre-wrap">${escapeHtml(error.message)}</pre>${reload}`,
    }
  }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost")
  if (url.pathname === "/__reload") {
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" })
    res.write(": connected\n\n")
    clients.add(res)
    req.on("close", () => clients.delete(res))
    return
  }
  if (url.pathname === "/" || url.pathname === "/index.html") {
    const { status, body } = page()
    res.writeHead(status, { "content-type": MIME[".html"], "cache-control": "no-store" })
    res.end(body)
    return
  }
  const file = path.join(SRC, decodeURIComponent(url.pathname))
  if (!file.startsWith(SRC + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404, { "content-type": "text/plain" })
    res.end("not found")
    return
  }
  res.writeHead(200, {
    "content-type": MIME[path.extname(file).toLowerCase()] ?? "application/octet-stream",
    "cache-control": "no-store",
  })
  fs.createReadStream(file).pipe(res)
})

let timer = null
fs.watch(SRC, { recursive: true }, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    for (const client of clients) client.write("data: reload\n\n")
  }, 80)
})

server.listen(port, () => console.log(`deck: http://localhost:${port}/ (reloads on change in src/)`))
