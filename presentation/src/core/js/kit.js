(() => {
  const root = document.documentElement
  const params = new URLSearchParams(location.search)
  const print = params.has("print")
  const still = print || params.has("static")
  const media = window.matchMedia("(prefers-reduced-motion: reduce)")
  const locale = window.DECK_LOCALE || {}
  const scenes = {}
  const notes = {}
  const NS = "http://www.w3.org/2000/svg"

  const t = (key, vars = {}) => String(locale[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""))

  const clamp01 = (value) => Math.min(1, Math.max(0, value))

  const ease = {
    out: (x) => 1 - (1 - clamp01(x)) ** 4,
    inOut: (x) => {
      const v = clamp01(x)
      return v < 0.5 ? 8 * v ** 4 : 1 - (-2 * v + 2) ** 4 / 2
    },
    linear: clamp01,
  }

  const rng = (seed) => {
    let state = seed >>> 0
    return () => {
      state = (state * 1664525 + 1013904223) >>> 0
      return state / 4294967296
    }
  }

  const seconds = (value, fallback = 0) => {
    const match = /(-?[\d.]+)\s*(ms|s)?/.exec(String(value || ""))
    if (!match) return fallback
    return match[2] === "ms" ? Number(match[1]) / 1000 : Number(match[1])
  }

  const kit = {
    get reduced() {
      return still || media.matches
    },
    print,
    still,
    scenes,
    notes,
    t,
    clamp01,
    ease,
    rng,
    seconds,
  }

  const active = new Set()
  let frame = 0
  const tick = (now) => {
    frame = 0
    for (const tw of active) {
      if (tw.start === null) tw.start = now + tw.delay
      if (now < tw.start) continue
      const p = clamp01((now - tw.start) / tw.dur)
      tw.update(tw.from + (tw.to - tw.from) * tw.curve(p), p)
      if (p >= 1) {
        active.delete(tw)
        tw.done?.()
      }
    }
    if (active.size) frame = requestAnimationFrame(tick)
  }

  kit.tween = ({ from = 0, to = 1, dur = 800, delay = 0, curve = "out", update, done }) => {
    if (kit.reduced) {
      update(to, 1)
      done?.()
      return () => {}
    }
    const tw = { from, to, dur, delay, curve: ease[curve] || ease.out, update, done, start: null }
    active.add(tw)
    if (!frame) frame = requestAnimationFrame(tick)
    return () => active.delete(tw)
  }

  kit.fmt = (value, digits = 0) => {
    const text = new Intl.NumberFormat(root.lang || "ru", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(value)
    return text.replace(/^-/, "−")
  }

  kit.count = (scope) => {
    for (const el of scope.querySelectorAll(".count[data-value]")) {
      const value = Number(el.dataset.value)
      const digits = Number(el.dataset.digits || 0)
      const unit = el.dataset.unit || ""
      const delay = seconds(getComputedStyle(el).getPropertyValue("--d")) * 1000
      el._stop?.()
      el._stop = kit.tween({
        from: 0,
        to: value,
        dur: 1200,
        delay,
        update: (v) => {
          el.textContent = `${kit.fmt(v, digits)}${unit}`
        },
      })
    }
  }

  kit.svg = (tag, attrs = {}, parent = null) => {
    const node = document.createElementNS(NS, tag)
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value))
    if (parent) parent.append(node)
    return node
  }

  kit.letters = (el) => {
    if (!el || el.dataset.split) return
    const text = el.textContent.trim()
    el.dataset.split = "1"
    el.setAttribute("aria-label", text)
    el.textContent = ""
    Array.from(text).forEach((char, i) => {
      const span = document.createElement("span")
      span.textContent = char === " " ? " " : char
      span.style.setProperty("--i", String(i))
      span.setAttribute("aria-hidden", "true")
      el.append(span)
    })
  }

  kit.marks = (scope = document) => {
    const source = document.getElementById("brand-mark")?.content.querySelector("svg")
    if (!source) return
    for (const host of scope.querySelectorAll("[data-mark]")) {
      if (host.firstElementChild) continue
      host.append(source.cloneNode(true))
    }
  }

  kit.followPath = (runner, path) => {
    if (runner && path) runner.style.offsetPath = `path("${path.getAttribute("d")}")`
  }

  const syncReduced = () => root.classList.toggle("is-reduced", kit.reduced)
  media.addEventListener("change", syncReduced)
  syncReduced()
  if (still) root.classList.add("is-static")

  window.deckKit = kit
  window.deckScene = (id, scene) => {
    scenes[id] = scene
  }
  window.deckNotes = (id, note) => {
    notes[id] = note
  }
})()
