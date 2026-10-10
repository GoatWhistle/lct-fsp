import fs from "node:fs"
import path from "node:path"
import QRCode from "qrcode"

export const ROOT = path.resolve(import.meta.dirname, "..")
export const SRC = path.join(ROOT, "src")
export const REPO = path.resolve(ROOT, "..")

export const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".avif": "image/avif",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
}

const CSS_FIRST = ["tokens.css", "fonts.css", "type.css", "deck.css", "motion.css", "parts.css"]
const JS_FIRST = ["kit.js", "qr.js", "presenter.js"]
const JS_LAST = "engine.js"
const SLIDE_DIR = /^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/
const PLACEHOLDER = /\{\{(?!@)[^{}]+\}\}/g
const MARKER = /\[(?:NEED [A-Z ]+|HONEST|DO NOT SHOW)\]/g
const EXTERNAL = /^(?:[a-z][a-z0-9+.-]*:)?\/\//i
const SKIP_REF = /^(?:data:|#|mailto:|tel:|javascript:)/i

export class DeckError extends Error {}

const fail = (lines) => {
  throw new DeckError(Array.isArray(lines) ? lines.join("\n") : lines)
}

const read = (file) => fs.readFileSync(file, "utf8")
const exists = (file) => fs.existsSync(file)
const rel = (file) => path.relative(ROOT, file).split(path.sep).join("/")
const posix = (file) => path.relative(SRC, file).split(path.sep).join("/")
const escapeHtml = (text) =>
  String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c])

const dataUri = (file) => {
  const type = MIME[path.extname(file).toLowerCase()]
  if (!type) fail(`unsupported asset type: ${rel(file)}`)
  return `data:${type.split(";")[0]};base64,${fs.readFileSync(file).toString("base64")}`
}

const ordered = (dir, ext, first, last) => {
  if (!exists(dir)) return []
  const names = fs.readdirSync(dir).filter((name) => name.endsWith(ext))
  const head = first.filter((name) => names.includes(name))
  const tail = names.filter((name) => !first.includes(name) && name !== last).sort()
  const end = last && names.includes(last) ? [last] : []
  return [...head, ...tail, ...end].map((name) => path.join(dir, name))
}

const slideFolders = () => {
  const dir = path.join(SRC, "slides")
  const names = fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => entry.name)
    .sort()
  const bad = names.filter((name) => !SLIDE_DIR.test(name))
  if (bad.length) fail(`slide folders must be named NN-id (lowercase, digits, dashes): ${bad.join(", ")}`)
  if (!names.length) fail("no slides in src/slides")
  return names.map((name) => ({ name, id: name.slice(3), dir: path.join(dir, name) }))
}

const stepNumbers = (html) => {
  const values = []
  for (const match of html.matchAll(/\bdata-(?:s|until)="(\d+)"/g)) values.push(Number(match[1]))
  for (const match of html.matchAll(/\bdata-at="([\d,\s]+)"/g)) {
    for (const part of match[1].split(",")) values.push(Number(part))
  }
  return values
}

const loadSlides = () => {
  const ids = new Set()
  return slideFolders().map((slide) => {
    const file = path.join(slide.dir, "slide.html")
    if (!exists(file)) fail(`${rel(slide.dir)}: slide.html is missing`)
    const html = read(file).trim()
    const open = html.match(/^<section\b[^>]*>/)
    if (!open || !/\bclass="(?:[^"]*\s)?slide(?:\s[^"]*)?"/.test(open[0])) {
      fail(`${rel(file)}: must start with <section class="slide" id="${slide.id}" ...>`)
    }
    const id = open[0].match(/\bid="([^"]*)"/)?.[1] ?? ""
    if (id !== slide.id) fail(`${rel(file)}: section id must be "${slide.id}" (folder name without NN-), got "${id}"`)
    if (ids.has(id)) fail(`${rel(file)}: duplicate slide id "${id}"`)
    ids.add(id)
    const steps = Number(open[0].match(/\bdata-steps="(\d+)"/)?.[1] ?? 0)
    const unreachable = stepNumbers(html).filter((value) => value > steps)
    if (unreachable.length) {
      fail(`${rel(file)}: step ${Math.max(...unreachable)} is unreachable, the section has data-steps="${steps}"`)
    }
    const extra = (name) => {
      const target = path.join(slide.dir, name)
      return exists(target) ? target : null
    }
    return { ...slide, file, html, style: extra("style.css"), notes: extra("notes.js"), scene: extra("scene.js") }
  })
}

const loadNumbers = () => {
  const file = path.join(SRC, "data", "numbers.json")
  if (!exists(file)) return { file, raw: "", data: {} }
  const raw = read(file)
  try {
    return { file, raw, data: JSON.parse(raw) }
  } catch (error) {
    return fail(`${rel(file)}: invalid JSON (${error.message})`)
  }
}

const sourceProblem = (key, entry) => {
  if (!entry || typeof entry !== "object") return `"${key}" must be an object { value, source }`
  if (entry.value === undefined || entry.value === null || entry.value === "") return `"${key}" has no value`
  const source = typeof entry.source === "string" ? entry.source.trim() : ""
  if (!source) return `"${key}" has no source: every number on a slide needs one`
  if (/^\{\{[^{}]+\}\}$/.test(source) || /^https?:\/\//i.test(source)) return null
  if (/\s/.test(source.split("#")[0])) {
    return `"${key}" source must be a repo-relative file path (optionally with #anchor) or an http(s) URL, got "${source}"`
  }
  const target = path.resolve(REPO, source.split("#")[0])
  if (!target.startsWith(REPO)) return `"${key}" source points outside the repo: ${source}`
  return exists(target) ? null : `"${key}" source file not found: ${source.split("#")[0]}`
}

const formatValue = (entry, lang) => {
  if (typeof entry.value !== "number") return String(entry.value)
  const digits = entry.digits ?? 0
  const text = new Intl.NumberFormat(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(
    entry.value,
  )
  return `${text.replace(/^-/, "−")}${entry.unit ?? ""}`
}

const fillNumbers = (slide, numbers, lang, problems, used) => {
  const where = rel(slide.file)
  const total = (slide.html.match(/\bdata-(?:num|source)="/g) ?? []).length
  let filled = 0
  const html = slide.html.replace(
    /<([a-z][a-z0-9-]*)\b([^>]*?)\sdata-(num|source)="([^"]*)"([^>]*)>([^<]*)<\/\1>/g,
    (match, tag, before, kind, key, after) => {
      filled += 1
      const entry = numbers[key]
      if (!entry) {
        problems.push(`${where}: data-${kind}="${key}" is not defined in src/data/numbers.json`)
        return match
      }
      used.add(key)
      if (kind === "source") return `<${tag}${before} data-source="${key}"${after}>${escapeHtml(entry.source ?? "")}</${tag}>`
      const raw =
        typeof entry.value === "number"
          ? ` data-value="${entry.value}" data-digits="${entry.digits ?? 0}" data-unit="${escapeHtml(entry.unit ?? "")}"`
          : ""
      return `<${tag}${before} data-num="${key}"${after}${raw}>${escapeHtml(formatValue(entry, lang))}</${tag}>`
    },
  )
  if (filled !== total) {
    problems.push(`${where}: an element with data-num or data-source must contain plain text only (no nested tags)`)
  }
  return html
}

const qrMatrix = (text) => {
  const code = QRCode.create(text.replace(/&amp;/g, "&"), { errorCorrectionLevel: "H" })
  const size = code.modules.size
  return `${size}|${Array.from(code.modules.data, (bit) => (bit ? "1" : "0")).join("")}`
}

const withQr = (html) => html.replace(/\sdata-qr="([^"]+)"/g, (match, text) => `${match} data-qr-matrix="${qrMatrix(text)}"`)

const bareDigits = (html) => {
  const text = html
    .replace(/<(script|style|template)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<([a-z][a-z0-9-]*)\b[^>]*\sdata-(?:num|source|plain)\b[^>]*>[^<]*<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(PLACEHOLDER, " ")
    .replace(/&[a-z]+;|&#\d+;/gi, " ")
  return [...new Set((text.match(/\d[\d\s.,]*/g) ?? []).map((value) => value.trim()))]
}

const inlineCss = (file, problems, seen = new Set()) => {
  if (seen.has(file)) return ""
  seen.add(file)
  const dir = path.dirname(file)
  const css = read(file).replace(/@import\s+(?:url\()?\s*["']([^"']+)["']\s*\)?\s*;/g, (match, ref) => {
    if (EXTERNAL.test(ref)) {
      problems.push(`${rel(file)}: external @import ${ref} (the deck must work offline)`)
      return ""
    }
    const target = path.resolve(dir, ref)
    if (!exists(target)) {
      problems.push(`${rel(file)}: @import target not found: ${ref}`)
      return ""
    }
    return inlineCss(target, problems, seen)
  })
  return css.replace(/url\(\s*(["']?)([^"')]+)\1\s*\)/g, (match, quote, ref) => {
    if (SKIP_REF.test(ref)) return match
    if (EXTERNAL.test(ref)) {
      problems.push(`${rel(file)}: external url ${ref} (the deck must work offline)`)
      return match
    }
    const target = path.resolve(dir, ref.split(/[?#]/)[0])
    if (!exists(target)) {
      problems.push(`${rel(file)}: file not found: ${ref}`)
      return match
    }
    return `url("${dataUri(target)}")`
  })
}

const inlineHtml = (html, problems) =>
  html.replace(/<([a-z][a-z0-9-]*)\b[^>]*>/gi, (tag, name) =>
    tag.replace(/\s(src|poster|href|xlink:href)="([^"]*)"/g, (attr, key, ref) => {
      if (name.toLowerCase() === "a" && key === "href") return attr
      if (!ref || SKIP_REF.test(ref)) return attr
      if (EXTERNAL.test(ref)) {
        problems.push(`external resource <${name} ${key}="${ref}"> (the deck must work offline)`)
        return attr
      }
      const target = path.resolve(SRC, ref.split(/[?#]/)[0])
      if (!exists(target)) {
        problems.push(`file not found: ${ref} (asset paths in slides are relative to src/)`)
        return attr
      }
      return ` ${key}="${dataUri(target)}"`
    }),
  )

const fill = (html, token, value) => html.split(`{{@${token}}}`).join(value)

const scan = (label, text, pattern) => (text.match(pattern) ?? []).map((hit) => `${label}: ${hit}`)

const GLYPHS = [
  [/[·•∙]/u, "dot separator"],
  [/—/u, "em dash"],
  [/\s\|\s/u, "pipe separator"],
  [/[←-⇿⟰-⟿⤀-⥿➔➜➝➡]/u, "arrow glyph, use an icon"],
  [/[✅✓-✘❌❎]/u, "check or cross glyph, use an icon"],
  [/[▶▸►◀◂◄]/u, "triangle pointer glyph, use an icon"],
  [/[\u{1F000}-\u{1FAFF}\u{2600}-\u{26FF}\u{FE0F}]/u, "emoji, use an icon"],
]

const visibleText = (html) => {
  const attrs = [...html.matchAll(/\s(?:alt|title|aria-label|data-title|placeholder)="([^"]*)"/g)].map((m) => m[1])
  const text = html
    .replace(/<(script|style|template)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, "\n")
  return [...text.split("\n"), ...attrs].map((line) => line.trim()).filter(Boolean)
}

const glyphProblems = (label, lines) =>
  lines.flatMap((line) => GLYPHS.filter(([pattern]) => pattern.test(line)).map(([, what]) => `${label}: ${what}: ${line.slice(0, 60)}`))

export const assemble = ({ inline, strict = false }) => {
  const problems = []
  const warnings = []
  const shellFile = path.join(SRC, "shell.html")
  if (!exists(shellFile)) fail("src/shell.html is missing")
  const shell = read(shellFile)
  const lang = shell.match(/<html\b[^>]*\blang="([^"]+)"/)?.[1] ?? "ru"
  const localeFile = path.join(SRC, "locales", lang, "deck.json")
  if (!exists(localeFile)) fail(`locale file missing for <html lang="${lang}">: ${rel(localeFile)}`)
  const locale = JSON.parse(read(localeFile))

  const slides = loadSlides()
  const numbers = loadNumbers()
  for (const [key, entry] of Object.entries(numbers.data)) {
    const problem = sourceProblem(key, entry)
    if (problem) problems.push(`src/data/numbers.json: ${problem}`)
  }
  const used = new Set()
  const bodies = slides.map((slide) => fillNumbers(slide, numbers.data, lang, problems, used))
  for (const key of Object.keys(numbers.data)) {
    if (!used.has(key)) warnings.push(`src/data/numbers.json: "${key}" is not used on any slide`)
  }

  const review = []
  problems.push(...glyphProblems("src/shell.html", visibleText(shell)))
  problems.push(...glyphProblems(rel(localeFile), Object.values(locale).map(String)))
  for (const slide of slides) {
    problems.push(...glyphProblems(rel(slide.file), visibleText(slide.html)))
    if (slide.style) {
      const contents = [...read(slide.style).matchAll(/content:\s*"([^"]*)"/g)].map((m) => m[1])
      problems.push(...glyphProblems(rel(slide.style), contents))
    }
  }
  review.push(...scan("src/shell.html", shell, PLACEHOLDER))
  review.push(...scan("src/data/numbers.json", numbers.raw, PLACEHOLDER))
  slides.forEach((slide, index) => {
    review.push(...scan(rel(slide.file), slide.html, PLACEHOLDER))
    review.push(...scan(rel(slide.file), slide.html, MARKER))
    if (slide.notes) {
      const notes = read(slide.notes)
      review.push(...scan(rel(slide.notes), notes, PLACEHOLDER))
      review.push(...scan(rel(slide.notes), notes, MARKER))
    }
    const digits = bareDigits(bodies[index])
    if (digits.length) {
      review.push(`${rel(slide.file)}: digits outside data-num: ${digits.map((d) => `"${d}"`).join(", ")}`)
    }
  })
  if (strict) problems.push(...review)
  else if (review.length) warnings.push(`${review.length} placeholders, markers or unsourced digits remain (npm run build:final lists them)`)

  if (problems.length) fail(["checks failed:", ...problems.map((line) => `  ${line}`)])

  const body = withQr(bodies.join("\n\n"))
  const cssFiles = [...ordered(path.join(SRC, "core", "css"), ".css", CSS_FIRST, null), ...slides.flatMap((s) => (s.style ? [s.style] : []))]
  const jsCore = ordered(path.join(SRC, "core", "js"), ".js", JS_FIRST, JS_LAST)
  const jsFiles = [
    ...jsCore.filter((file) => path.basename(file) !== JS_LAST),
    ...slides.flatMap((s) => [s.notes, s.scene].filter(Boolean)),
    ...jsCore.filter((file) => path.basename(file) === JS_LAST),
  ]
  const boot = `<script>window.DECK_LOCALE = ${JSON.stringify(locale)}</script>`

  let html = shell
  if (inline) {
    const assets = []
    const styles = cssFiles.map((file) => `<style>\n${inlineCss(file, assets)}\n</style>`).join("\n")
    const scripts = jsFiles
      .map((file) => {
        const code = read(file)
        if (/<\/script/i.test(code)) assets.push(`${rel(file)}: contains a closing script tag, write it as <\\/script>`)
        return `<script>\n${code}\n</script>`
      })
      .join("\n")
    html = inlineHtml(html, assets)
    html = fill(html, "slides", inlineHtml(body, assets))
    html = fill(html, "styles", styles)
    html = fill(html, "scripts", `${boot}\n${scripts}`)
    if (assets.length) fail(["asset checks failed:", ...assets.map((line) => `  ${line}`)])
  } else {
    html = fill(html, "styles", cssFiles.map((file) => `<link rel="stylesheet" href="${posix(file)}">`).join("\n"))
    html = fill(html, "slides", body)
    html = fill(html, "scripts", [boot, ...jsFiles.map((file) => `<script src="${posix(file)}"></script>`)].join("\n"))
  }
  return { html, warnings, slides: slides.length }
}
