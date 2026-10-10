import fs from "node:fs"

const [, , file = "submission.md"] = process.argv
const text = fs.readFileSync(file, "utf8")
let failed = 0

for (const section of text.split(/^## /m).slice(1)) {
  const [head, ...rest] = section.split("\n")
  const body = rest.join("\n").trim()
  const chars = Array.from(body).length
  const words = body.split(/\s+/).filter(Boolean).length
  const limit = Number(/limit\s+(\d+)/i.exec(head)?.[1] ?? 0)
  const min = Number(/min\s+(\d+)/i.exec(head)?.[1] ?? 0)
  const name = head.replace(/\(.*\)/, "").trim()
  let status = "ok"
  if (limit && chars > limit) status = `OVER by ${chars - limit}`
  else if (min && chars < min) status = `UNDER min by ${min - chars}`
  if (status !== "ok") failed += 1
  const of = limit ? `${chars} of ${limit}` : `${chars}`
  console.log(`${name.padEnd(28)} ${of.padStart(12)} chars  ${String(words).padStart(4)} words  ${status}`)
}

if (failed) process.exit(1)
