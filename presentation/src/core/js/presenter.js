(() => {
  const kit = window.deckKit

  const STYLE = `
:root { color-scheme: dark; --bg: #101012; --surface: #1a1a1d; --line: #2c2c31; --ink: #ececef; --ink-2: #b4b4bb; --ink-3: #85858d; --accent: #93a5ff; --warn: #f2c14e; --late: #ff8a80; --mono: ui-monospace, "Cascadia Mono", Consolas, monospace; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
body { display: grid; grid-template-rows: auto 1fr auto; gap: 18px; padding: 22px 28px; }
header { display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: start; }
.now { display: flex; align-items: baseline; gap: 16px; }
.label { font-family: var(--mono); font-size: 44px; font-weight: 600; color: var(--accent); }
.title { font-size: 28px; font-weight: 600; }
.step { font-family: var(--mono); color: var(--ink-3); margin-top: 4px; }
.timer { text-align: right; min-width: 280px; }
.clock { font-family: var(--mono); font-size: 64px; font-weight: 600; line-height: 1; }
.clock.is-close { color: var(--warn); }
.clock.is-late { color: var(--late); }
.budget { font-family: var(--mono); font-size: 15px; color: var(--ink-3); margin-top: 6px; }
.bar { height: 6px; border-radius: 3px; background: var(--line); margin-top: 10px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); transform-origin: left; transform: scaleX(0); }
main { display: grid; grid-template-columns: 1fr 340px; gap: 22px; min-height: 0; }
.notes { overflow: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 24px 28px; }
.notes p { margin: 0 0 16px; font-size: 24px; line-height: 1.5; }
.notes .caveat { font-size: 18px; color: var(--warn); }
.notes .empty { color: var(--ink-3); font-size: 18px; }
aside { display: flex; flex-direction: column; gap: 14px; min-height: 0; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }
.card small { display: block; font-size: 13px; color: var(--ink-3); margin-bottom: 4px; }
.next b { font-family: var(--mono); color: var(--accent); margin-right: 8px; }
.plan { overflow: auto; flex: 1; }
.plan div { display: grid; grid-template-columns: 36px 1fr 52px; gap: 8px; padding: 5px 6px; font-size: 14px; color: var(--ink-2); border-radius: 8px; }
.plan div.is-now { background: var(--line); color: var(--ink); }
.plan div.is-done { color: var(--ink-3); }
.plan span:last-child { font-family: var(--mono); text-align: right; }
footer { display: flex; gap: 12px; align-items: center; }
button { font: inherit; color: var(--ink); background: var(--surface); border: 1px solid var(--line); border-radius: 999px; min-height: 44px; padding: 0 20px; cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 600; }
footer .hint { margin-left: auto; color: var(--ink-3); font-size: 14px; }
`

  const BODY = `
<header>
  <div>
    <div class="now"><span class="label" id="label"></span><span class="title" id="title"></span></div>
    <div class="step" id="step"></div>
  </div>
  <div class="timer">
    <div class="clock" id="clock">0:00</div>
    <div class="budget" id="budget"></div>
    <div class="bar"><i id="bar"></i></div>
  </div>
</header>
<main>
  <section class="notes" id="notes"></section>
  <aside>
    <div class="card next"><small id="upnext"></small><div id="next"></div></div>
    <div class="card plan" id="plan"></div>
  </aside>
</main>
<footer>
  <button id="prev" type="button"></button>
  <button class="primary" id="fwd" type="button"></button>
  <button id="reset" type="button"></button>
  <span class="hint" id="hint"></span>
</footer>
`

  const main = (L) => {
    let state = null
    const $ = (id) => document.getElementById(id)
    const fill = (template, vars) => String(template).replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? ""))
    const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c])
    const clock = (sec) => {
      const v = Math.max(0, Math.floor(sec))
      return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, "0")}`
    }
    const send = (cmd) => window.opener?.postMessage({ type: "deck-nav", cmd }, "*")
    $("prev").textContent = L.prev
    $("fwd").textContent = L.next
    $("reset").textContent = L.reset
    $("hint").textContent = L.hint
    $("upnext").textContent = L.upnext
    const render = () => {
      if (!state) return
      $("label").textContent = state.label
      $("title").textContent = state.title
      $("step").textContent = state.steps ? fill(L.step, { n: state.step + 1, total: state.steps + 1 }) : ""
      $("next").innerHTML = state.next ? `<b>${esc(state.next.label)}</b>${esc(state.next.title)}` : esc(L.end)
      const note = state.note
      const lines = note ? [...(note.say || []).map((t) => `<p>${t}</p>`), ...(note.caveat || []).map((t) => `<p class="caveat">${t}</p>`)] : []
      $("notes").innerHTML = lines.length ? lines.join("") : `<p class="empty">${esc(L.empty)}</p>`
      let total = 0
      state.target = 0
      $("plan").innerHTML = state.plan
        .map((row, i) => {
          total += row.time
          const now = !state.appendix && i === state.index
          if (now) state.target = total
          const done = state.appendix || i < state.index
          return `<div class="${now ? "is-now" : done ? "is-done" : ""}"><span>${esc(row.label)}</span><span>${esc(row.title)}</span><span>${clock(total)}</span></div>`
        })
        .join("")
    }
    const tick = () => {
      const duration = state?.duration || 420
      const elapsed = state?.started ? (Date.now() - state.started) / 1000 : 0
      $("clock").textContent = clock(elapsed)
      $("clock").classList.toggle("is-close", elapsed > duration * 0.85 && elapsed <= duration)
      $("clock").classList.toggle("is-late", elapsed > duration)
      $("bar").style.transform = `scaleX(${Math.min(1, elapsed / duration)})`
      const plan = state?.target ? fill(L.plan, { time: clock(state.target) }) : ""
      $("budget").textContent = [fill(L.of, { total: clock(duration) }), plan].filter(Boolean).join(", ")
      requestAnimationFrame(tick)
    }
    window.addEventListener("message", (event) => {
      if (event.data?.type !== "deck-state") return
      state = event.data
      render()
    })
    window.addEventListener("keydown", (event) => {
      if (["ArrowRight", "PageDown", " ", "Enter"].includes(event.key)) {
        event.preventDefault()
        send("next")
      }
      if (["ArrowLeft", "PageUp", "Backspace"].includes(event.key)) {
        event.preventDefault()
        send("prev")
      }
    })
    $("prev").addEventListener("click", () => send("prev"))
    $("fwd").addEventListener("click", () => send("next"))
    $("reset").addEventListener("click", () => send("reset"))
    send("hello")
    requestAnimationFrame(tick)
  }

  const labels = () => ({
    title: kit.t("presenter.title"),
    of: kit.t("presenter.of", { total: "{total}" }),
    plan: kit.t("presenter.plan", { time: "{time}" }),
    step: kit.t("presenter.step", { n: "{n}", total: "{total}" }),
    next: kit.t("presenter.next"),
    prev: kit.t("presenter.prev"),
    reset: kit.t("presenter.reset"),
    end: kit.t("presenter.end"),
    upnext: kit.t("presenter.upnext"),
    hint: kit.t("presenter.hint"),
    empty: kit.t("notes.empty"),
  })

  const page = (L) =>
    `<!doctype html><html lang="${document.documentElement.lang}"><head><meta charset="utf-8"><title>${L.title}</title><style>${STYLE}</style></head><body>${BODY}<script>(${main.toString()})(${JSON.stringify(L)})<\/script></body></html>`

  kit.presenter = {
    open: () => {
      const win = window.open("", "deck-presenter", "width=1280,height=820")
      if (!win) return null
      try {
        win.document.open()
        win.document.write(page(labels()))
        win.document.close()
      } catch {
        win.close()
        return null
      }
      return win
    },
  }
})()
