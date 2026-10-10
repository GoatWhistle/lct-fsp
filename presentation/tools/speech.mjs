import { createHash } from "node:crypto"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const SRC = path.join(ROOT, "src")
const SPEECH = path.join(ROOT, "SPEECH.md")
const LOCK = path.join(ROOT, "speech.lock.json")
const HEAD = /^## (\d{2})\. (.+?) \[([a-z0-9-]+)\] (\d+):(\d{2}) \((\d+):(\d{2})\)\s*$/
const FORBIDDEN = /спасибо за внимание|благодарим за внимание|thank you for your attention|thanks for your attention/i
const CLOSING = /готовы к вашим вопросам|ready for your questions/i
const TABLE_HEAD = "| # | Slide | Speaker | Time | Cumulative |"

const [, , command = "check", ...flags] = process.argv
const strict = flags.includes("--strict")
const warnOnly = flags.includes("--warn")
const read = (file) => fs.readFileSync(file, "utf8")
const clock = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`

const shell = read(path.join(SRC, "shell.html"))
const duration = Number(/data-duration="(\d+)"/.exec(shell)?.[1] || 360)
const reserve = Number(process.env.SPEECH_RESERVE || 20)
const numbers = JSON.parse(read(path.join(SRC, "data", "numbers.json")))

const slides = fs
  .readdirSync(path.join(SRC, "slides"), { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && /^\d{2}-[a-z0-9-]+$/.test(entry.name))
  .map((entry) => entry.name)
  .sort()
  .map((name) => {
    const dir = path.join(SRC, "slides", name)
    const html = read(path.join(dir, "slide.html"))
    const notesFile = path.join(dir, "notes.js")
    const notes = fs.existsSync(notesFile) ? read(notesFile) : ""
    const keys = [...html.matchAll(/data-(?:num|source)="([^"]+)"/g)].map((m) => m[1]).sort()
    const used = Object.fromEntries(keys.map((key) => [key, numbers[key] ?? null]))
    return {
      name,
      id: /\sid="([^"]+)"/.exec(html)?.[1] || name.slice(3),
      title: /data-title="([^"]*)"/.exec(html)?.[1] || name.slice(3),
      steps: Number(/data-steps="(\d+)"/.exec(html)?.[1] || 0),
      appendix: /data-kind="appendix"/.test(html),
      notesFile,
      notes,
      time: Number(/\btime:\s*(\d+)/.exec(notes)?.[1] || 30),
      say: [...(/say:\s*\[([\s\S]*?)\],\s*caveat:/.exec(notes)?.[1] || "").matchAll(/"([^"]*)"/g)].map((m) => m[1]),
      hash: createHash("sha1").update(html).update(JSON.stringify(used)).digest("hex").slice(0, 12),
    }
  })
const main = slides.filter((s) => !s.appendix)

const parse = (text) => {
  const lines = text.split("\n")
  const sections = []
  let current = null
  lines.forEach((line, index) => {
    const head = HEAD.exec(line)
    if (head) {
      current = { line: index, no: head[1], title: head[2], id: head[3], seconds: Number(head[4]) * 60 + Number(head[5]), body: [] }
      sections.push(current)
    } else if (/^## |^---\s*$/.test(line)) {
      current = null
    } else if (current) {
      current.body.push(line)
    }
  })
  return { lines, sections }
}

const spoken = (body) =>
  body
    .filter((line) => !/^\s*(\||#|>)/.test(line))
    .join(" ")
    .replace(/`?\[→\]`?/g, " ")
    .replace(/\*\*[^*]+\*\*/g, " ")
    .replace(/[«»"“”*_`]/g, " ")

const pace = (text) => Number(/(\d+) words per minute/.exec(text)?.[1] || 125)

const structure = (sections) => {
  const problems = []
  const ids = sections.map((s) => s.id)
  for (const s of main) if (!ids.includes(s.id)) problems.push(`no speech section for slide ${s.name} [${s.id}]`)
  for (const id of ids) {
    if (!slides.some((s) => s.id === id)) problems.push(`speech section [${id}] has no slide`)
    if (ids.indexOf(id) !== ids.lastIndexOf(id)) problems.push(`speech section [${id}] appears twice`)
  }
  const order = main.map((s) => s.id).filter((id) => ids.includes(id))
  const seen = ids.filter((id) => order.includes(id))
  if (order.join() !== seen.join()) problems.push(`speech order differs from slides: ${order.join(" ")}`)
  return [...new Set(problems)]
}

const skeleton = (s) => {
  const cues = s.say.map((cue) => cue.replace(/\[→\]\s*/g, ""))
  const groups = Array.from({ length: s.steps + 1 }, (_, g) => {
    if (g < s.steps) return cues[g] ? [cues[g]] : []
    return cues.slice(s.steps)
  }).map((group, g) => (group.length ? group : [g ? "{{Text for the next step}}" : "{{Spoken text in the deck language}}"]))
  const body = ["", "**{{Speaker}}.**", ""]
  groups.forEach((group, g) => {
    for (const cue of group) body.push(cue, "")
    if (g < s.steps || s !== main.at(-1)) body.push("`[→]`", "")
  })
  return [`## ${s.name.slice(0, 2)}. ${s.title} [${s.id}] ${clock(s.time)} (0:00)`, ...body]
}

const check = () => {
  if (!fs.existsSync(SPEECH)) return { errors: ["SPEECH.md is missing: npm run speech:init"], warnings: [] }
  const text = read(SPEECH)
  const { lines, sections } = parse(text)
  const errors = structure(sections)
  const warnings = []
  const wpm = pace(text)
  const lock = fs.existsSync(LOCK) ? JSON.parse(read(LOCK)) : null
  if (!lock) warnings.push("speech never synced: npm run speech:sync")
  let cumulative = 0
  for (const section of sections) {
    const slide = slides.find((s) => s.id === section.id)
    cumulative += section.seconds
    const words = spoken(section.body).split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length
    const body = section.body.join("\n")
    if (!slide) continue
    if (FORBIDDEN.test(body)) errors.push(`[${section.id}] says thanks for attention: end with «Готовы к вашим вопросам»`)
    if (/\{\{/.test(body)) (strict ? errors : warnings).push(`[${section.id}] is not written yet (placeholders)`)
    else {
      const seconds = (words / wpm) * 60
      if (seconds > section.seconds * 1.15 || seconds < section.seconds * 0.85)
        warnings.push(`[${section.id}] ${words} words = ${clock(seconds)} at ${wpm} wpm, planned ${clock(section.seconds)}`)
    }
    const presses = (body.match(/\[→\]/g) || []).length
    const needed = slide.steps + (slide === main.at(-1) ? 0 : 1)
    if (presses < needed) warnings.push(`[${section.id}] ${presses} key presses, the slide needs ${needed}`)
    if (slide.time !== section.seconds) errors.push(`[${section.id}] notes.js time ${slide.time}s differs from speech ${section.seconds}s: npm run speech:sync`)
    const head = HEAD.exec(lines[section.line])
    if (Number(head[6]) * 60 + Number(head[7]) !== cumulative) errors.push(`[${section.id}] cumulative time is stale: npm run speech:sync`)
    if (lock && lock.slides?.[section.id] && lock.slides[section.id] !== slide.hash)
      errors.push(`[${section.id}] slide changed since the speech was synced: rewrite its section, then npm run speech:sync`)
    if (lock && !lock.slides?.[section.id]) errors.push(`[${section.id}] new slide not in the synced speech: write its section, then npm run speech:sync`)
  }
  const last = sections.at(-1)
  if (last && !CLOSING.test(last.body.join("\n"))) warnings.push(`[${last.id}] last words are not «Готовы к вашим вопросам»`)
  const limit = duration - reserve
  if (cumulative > limit) errors.push(`speech ${clock(cumulative)} exceeds ${clock(limit)} (regulation ${clock(duration)} minus ${reserve}s reserve)`)
  if (cumulative < duration * 0.8) warnings.push(`speech ${clock(cumulative)} is short for the ${clock(duration)} regulation`)
  return { errors, warnings, total: cumulative, wpm }
}

const sync = () => {
  const text = read(SPEECH)
  const { lines, sections } = parse(text)
  const problems = structure(sections)
  if (problems.length) {
    console.error(`speech:sync refused, fix the structure first:\n  ${problems.join("\n  ")}`)
    process.exit(1)
  }
  const speakers = Object.fromEntries(
    lines.filter((l) => /^\| \d+ \|/.test(l)).map((l) => l.split("|").map((c) => c.trim())).map((c) => [/\[([a-z0-9-]+)\]/.exec(c[2])?.[1], c[3]]),
  )
  let cumulative = 0
  const rows = []
  for (const section of sections) {
    const slide = slides.find((s) => s.id === section.id)
    cumulative += section.seconds
    lines[section.line] = `## ${slide.name.slice(0, 2)}. ${section.title} [${section.id}] ${clock(section.seconds)} (${clock(cumulative)})`
    rows.push(`| ${slide.name.slice(0, 2)} | ${section.title} [${section.id}] | ${speakers[section.id] || "{{name}}"} | ${clock(section.seconds)} | ${clock(cumulative)} |`)
    fs.writeFileSync(slide.notesFile, slide.notes.replace(/\btime:\s*\d+/, `time: ${section.seconds}`))
  }
  const start = lines.indexOf(TABLE_HEAD)
  if (start >= 0) {
    let end = start + 2
    while (end < lines.length && lines[end].startsWith("|")) end += 1
    lines.splice(start + 2, end - start - 2, ...rows)
  }
  const out = lines.join("\n").replace(/^# Speech: \S+ at regulation \S+/m, `# Speech: ${clock(cumulative)} at regulation ${clock(duration)}`)
  fs.writeFileSync(SPEECH, out)
  const hashes = Object.fromEntries(sections.map((s) => [s.id, slides.find((x) => x.id === s.id).hash]))
  fs.writeFileSync(LOCK, `${JSON.stringify({ total: clock(cumulative), regulation: clock(duration), slides: hashes }, null, 2)}\n`)
  console.log(`speech synced: ${sections.length} sections, ${clock(cumulative)} of ${clock(duration)}`)
}

const init = () => {
  if (!fs.existsSync(SPEECH)) {
    const total = main.reduce((sum, s) => sum + s.time, 0)
    const head = [
      `# Speech: ${clock(total)} at regulation ${clock(duration)}`,
      "",
      "{{PRODUCT}}, {{TEAM}}.",
      "",
      "Pace 125 words per minute. `[→]` is a key press: the next step or slide.",
      "",
      TABLE_HEAD,
      "| ---: | --- | --- | ---: | ---: |",
      "",
      "---",
      "",
    ]
    fs.writeFileSync(SPEECH, [...head, ...main.flatMap(skeleton), "---", ""].join("\n"))
    console.log(`SPEECH.md created with ${main.length} sections: write them, then npm run speech:sync`)
    return
  }
  const { lines, sections } = parse(read(SPEECH))
  const have = new Set(sections.map((s) => s.id))
  const missing = main.filter((s) => !have.has(s.id))
  for (const slide of missing.reverse()) {
    const next = main.slice(main.indexOf(slide) + 1).map((s) => sections.find((x) => x.id === s.id)).find(Boolean)
    const at = next ? next.line : (sections.at(-1)?.line ?? lines.length) + 1 + (sections.at(-1)?.body.length ?? 0)
    lines.splice(at, 0, ...skeleton(slide))
  }
  fs.writeFileSync(SPEECH, lines.join("\n"))
  const orphans = sections.filter((s) => !slides.some((x) => x.id === s.id)).map((s) => s.id)
  console.log(`added ${missing.length} sections${orphans.length ? `; sections without a slide, delete them: ${orphans.join(", ")}` : ""}`)
}

if (command === "init") init()
else if (command === "sync") sync()
else {
  const { errors, warnings, total, wpm } = check()
  if (!warnOnly) for (const w of warnings) console.log(`warn: ${w}`)
  for (const e of errors) console.error(`error: ${e}`)
  if (total !== undefined) console.log(`speech ${clock(total)} of ${clock(duration)} at ${wpm} wpm, ${errors.length} errors, ${warnings.length} warnings`)
  if (errors.length && !warnOnly) process.exit(1)
}
