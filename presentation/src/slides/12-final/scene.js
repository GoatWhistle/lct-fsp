deckScene("final", {
  init(el) {
    const svg = el.querySelector(".fn-net")
    const random = deckKit.rng(20261010)
    const keep = [[90, 130, 1830, 950]]
    const free = (x, y) => !keep.some(([x1, y1, x2, y2]) => x > x1 && x < x2 && y > y1 && y < y2)
    const nodes = []
    let guard = 0
    while (nodes.length < 40 && guard < 4000) {
      guard += 1
      const x = 40 + random() * 1840
      const y = 30 + random() * 1020
      if (!free(x, y)) continue
      if (nodes.some((n) => Math.hypot(n.x - x, n.y - y) < 110)) continue
      nodes.push({ x, y })
    }
    const links = []
    nodes.forEach((a, i) => {
      const near = nodes
        .map((b, j) => ({ j, d: Math.hypot(a.x - b.x, a.y - b.y) }))
        .filter((n) => n.j > i && n.d < 300)
        .sort((p, q) => p.d - q.d)
        .slice(0, 2)
      for (const n of near) links.push([a, nodes[n.j]])
    })
    const mid = { x: 960, y: 540 }
    const far = (p) => Math.hypot(p.x - mid.x, p.y - mid.y) / 1100
    const paths = []
    links.forEach(([a, b], k) => {
      const accent = k % 7 === 0
      const path = deckKit.svg(
        "path",
        {
          class: `fn-link dr${accent ? " is-accent" : ""}`,
          pathLength: 1,
          d: `M${a.x.toFixed(1)} ${a.y.toFixed(1)} L${b.x.toFixed(1)} ${b.y.toFixed(1)}`,
          style: `--d:${(0.3 + far(a) * 1.4).toFixed(2)}s;--t:0.9s`,
        },
        svg,
      )
      if (accent) paths.push(path)
    })
    nodes.forEach((n, k) => {
      const tone = k % 17 === 3 ? " is-red" : k % 5 === 0 ? " is-blue" : ""
      deckKit.svg(
        "circle",
        {
          class: `fn-dot pop${tone}`,
          cx: n.x.toFixed(1),
          cy: n.y.toFixed(1),
          r: tone ? 6 : 4,
          style: `--d:${(0.2 + far(n) * 1.4).toFixed(2)}s`,
        },
        svg,
      )
    })
    paths.slice(0, 4).forEach((path, k) => {
      const pulse = deckKit.svg("circle", { class: "fn-pulse only-motion", r: 6, style: `--d:${2.6 + k * 0.7}s;--t:${2.4 + k * 0.3}s` }, svg)
      pulse.style.offsetPath = `path("${path.getAttribute("d")}")`
    })
  },
})
