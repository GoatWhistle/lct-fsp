(() => {
  const kit = window.deckKit
  const SIZE = 1200
  const QUIET = 3
  const FLY = 0.9
  const items = new WeakMap()

  const parse = (box) => {
    const [size, bits] = String(box.dataset.qrMatrix || "").split("|")
    const n = Number(size)
    return n && bits && bits.length === n * n ? { n, bits } : null
  }

  const build = (box, seed) => {
    const matrix = parse(box)
    if (!matrix) return null
    const { n, bits } = matrix
    const canvas = document.createElement("canvas")
    canvas.className = "qr-canvas"
    canvas.width = SIZE
    canvas.height = SIZE
    canvas.setAttribute("role", "img")
    canvas.setAttribute("aria-label", box.dataset.label || box.dataset.qr || "")
    box.prepend(canvas)
    const style = getComputedStyle(box)
    const color = (name, fallback) => style.getPropertyValue(name).trim() || fallback
    const colors = { fg: color("--qr-fg", "black"), bg: color("--qr-bg", "white"), accent: color("--qr-accent", "black") }
    const unit = SIZE / (n + QUIET * 2)
    const lo = Math.floor(n / 2) - 3
    const hi = lo + 6
    const holed = Boolean(box.querySelector(".qr-mark")) && n >= 25
    const hole = (x, y) => holed && x >= lo && x <= hi && y >= lo && y <= hi
    const finder = (x, y) => (x < 7 && y < 7) || (x >= n - 7 && y < 7) || (x < 7 && y >= n - 7)
    const random = kit.rng(seed)
    const base = kit.seconds(box.dataset.delay, 0)
    const mid = (n - 1) / 2
    const mods = []
    for (let y = 0; y < n; y += 1) {
      for (let x = 0; x < n; x += 1) {
        if (bits[y * n + x] !== "1" || finder(x, y) || hole(x, y)) continue
        const dist = Math.hypot(x - mid, y - mid) / (mid * Math.SQRT2)
        const angle = Math.atan2(y - mid, x - mid) + (random() - 0.5) * 1.1
        const far = 4 + random() * 8
        mods.push({
          x,
          y,
          ox: Math.cos(angle) * far,
          oy: Math.sin(angle) * far,
          rot: (random() - 0.5) * Math.PI,
          d: base + 0.2 + dist * 0.9 + random() * 0.3,
        })
      }
    }
    const finders = [
      [0, 0],
      [n - 7, 0],
      [0, n - 7],
    ].map(([x, y], i) => ({ x, y, d: base + i * 0.12 }))
    const until = Math.max(base + 1.2, ...mods.map((m) => m.d + FLY)) + 0.1
    return { ctx: canvas.getContext("2d"), n, bits, unit, colors, mods, finders, hole, until, raf: 0 }
  }

  const draw = (item, time) => {
    const { ctx, n, bits, unit, colors, mods, finders, hole, until } = item
    const offset = QUIET * unit
    const place = (x, y, k, rot) => {
      const s = k * unit
      const c = Math.cos(rot) * s
      const si = Math.sin(rot) * s
      ctx.setTransform(c, si, -si, c, offset + x * unit, offset + y * unit)
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.globalAlpha = 1
    ctx.fillStyle = colors.bg
    ctx.fillRect(0, 0, SIZE, SIZE)
    ctx.setTransform(unit, 0, 0, unit, offset, offset)
    ctx.fillStyle = colors.fg
    ctx.beginPath()
    if (time >= until) {
      for (let y = 0; y < n; y += 1) {
        for (let x = 0; x < n; x += 1) {
          if (bits[y * n + x] === "1" && !hole(x, y)) ctx.rect(x, y, 1.02, 1.02)
        }
      }
      ctx.fill()
      return
    }
    for (const m of mods) if (time >= m.d + FLY) ctx.rect(m.x, m.y, 1.02, 1.02)
    ctx.fill()
    ctx.fillStyle = colors.accent
    for (const m of mods) {
      const p = (time - m.d) / FLY
      if (p <= 0 || p >= 1) continue
      const k = kit.ease.out(p)
      ctx.globalAlpha = Math.min(1, p * 2)
      place(m.x + 0.5 + m.ox * (1 - k), m.y + 0.5 + m.oy * (1 - k), 0.3 + 0.7 * k, m.rot * (1 - k))
      ctx.fillRect(-0.5, -0.5, 1, 1)
    }
    for (const f of finders) {
      const p = kit.clamp01((time - f.d) / FLY)
      if (p <= 0) continue
      const k = kit.ease.out(p)
      ctx.globalAlpha = Math.min(1, p * 2.5)
      place(f.x + 3.5, f.y + 3.5, 1.8 - 0.8 * k, (-Math.PI / 2) * (1 - k))
      ctx.fillStyle = colors.fg
      ctx.fillRect(-3.5, -3.5, 7, 1)
      ctx.fillRect(-3.5, 2.5, 7, 1)
      ctx.fillRect(-3.5, -2.5, 1, 5)
      ctx.fillRect(2.5, -2.5, 1, 5)
      const q = kit.clamp01((time - f.d - 0.4) / 0.6)
      if (q <= 0) continue
      const kq = kit.ease.out(q)
      place(f.x + 3.5, f.y + 3.5, 0.3 + 0.7 * kq, (Math.PI / 4) * (1 - kq))
      ctx.fillStyle = colors.accent
      ctx.fillRect(-1.5, -1.5, 3, 3)
    }
    ctx.globalAlpha = 1
  }

  const play = (scope) => {
    scope.querySelectorAll("[data-qr-matrix]").forEach((box, index) => {
      let item = items.get(box)
      if (!item) {
        item = build(box, 41 + index)
        if (!item) return
        items.set(box, item)
      }
      cancelAnimationFrame(item.raf)
      if (kit.reduced) {
        draw(item, Number.POSITIVE_INFINITY)
        return
      }
      const start = performance.now()
      const loop = (now) => {
        const time = (now - start) / 1000
        draw(item, time)
        if (time < item.until) item.raf = requestAnimationFrame(loop)
      }
      item.raf = requestAnimationFrame(loop)
    })
  }

  kit.qr = { play }
})()
