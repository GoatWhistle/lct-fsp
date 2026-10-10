deckScene(
  "adaptive",
  (() => {
    const path = [
      [0.5, 0.25, 1],
      [0.58, 0.21, 1],
      [0.66, 0.18, 0],
      [0.6, 0.16, 1],
      [0.67, 0.14, 1],
      [0.74, 0.125, 0],
      [0.69, 0.11, 1],
      [0.73, 0.1, 0],
      [0.7, 0.09, 1],
      [0.72, 0.08, 0],
      [0.705, 0.072, 1],
      [0.715, 0.066, 1],
    ]
    const cuts = [0.2, 0.4, 0.6, 0.8]
    const erf = (x) => {
      const t = 1 / (1 + 0.3275911 * Math.abs(x))
      const poly = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
      const y = 1 - poly * Math.exp(-x * x)
      return x >= 0 ? y : -y
    }
    const above = (mu, sd, cut) => 0.5 * (1 + erf((mu - cut) / (sd * Math.SQRT2)))
    let stop = () => {}

    const paint = (el, pos) => {
      const i = Math.min(path.length - 1, Math.floor(pos))
      const j = Math.min(path.length - 1, i + 1)
      const f = pos - i
      const mu = path[i][0] + (path[j][0] - path[i][0]) * f
      const sd = path[i][1] + (path[j][1] - path[i][1]) * f
      el.style.setProperty("--mu", mu.toFixed(4))
      el.style.setProperty("--sd", sd.toFixed(4))
      for (const li of el.querySelectorAll(".ad-bars li")) {
        const p = above(mu, sd, cuts[Number(li.dataset.g)])
        li.style.setProperty("--p", p.toFixed(4))
        li.classList.toggle("is-pass", p >= 0.8)
      }
      el.querySelectorAll(".ad-cells li").forEach((li, k) => li.classList.toggle("on", k <= pos))
    }

    return {
      init(el) {
        const list = el.querySelector(".ad-cells")
        for (const [, , ok] of path) {
          const li = document.createElement("li")
          li.className = ok ? "is-hit" : "is-miss"
          li.innerHTML = `<svg class="ic"><use href="#i-${ok ? "circle-check" : "circle-x"}"/></svg>`
          list.append(li)
        }
        paint(el, path.length - 1)
      },
      enter(el) {
        stop()
        paint(el, 0)
        stop = deckKit.tween({
          from: 0,
          to: path.length - 1,
          dur: 4800,
          delay: 900,
          curve: "linear",
          update: (v) => paint(el, v),
        })
      },
      leave() {
        stop()
      },
    }
  })(),
)
