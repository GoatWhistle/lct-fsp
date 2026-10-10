import fs from "node:fs"

const [, , file = "SPEECH.md", paceArg = "125"] = process.argv
const pace = Number(paceArg)
const text = fs.readFileSync(file, "utf8")
const clock = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`

const spoken = (body) =>
  body
    .split("\n")
    .filter((line) => !/^\s*(\||#|---|`\[→\]`$)/.test(line))
    .join(" ")
    .replace(/`\[→\]`|\[→\]/g, " ")
    .replace(/\*\*[^*]+\*\*/g, " ")
    .replace(/[«»"“”*_`]/g, " ")

let total = 0
let words = 0
for (const section of text.split(/^## /m).slice(1)) {
  const [head, ...rest] = section.split("\n")
  if (!/^\d+\./.test(head)) continue
  const count = spoken(rest.join("\n")).split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length
  const planned = /\] (\d+):(\d{2}) \(/.exec(head)
  const target = planned ? Number(planned[1]) * 60 + Number(planned[2]) : null
  const seconds = (count / pace) * 60
  total += seconds
  words += count
  const delta = target === null ? "" : `  plan ${clock(target)}  ${seconds > target * 1.1 ? "OVER" : seconds < target * 0.9 ? "under" : "ok"}`
  console.log(`${head.trim().slice(0, 48).padEnd(48)} ${String(count).padStart(4)} words  ${clock(seconds)}${delta}`)
}
console.log(`${"total".padEnd(48)} ${String(words).padStart(4)} words  ${clock(total)} at ${pace} wpm`)
