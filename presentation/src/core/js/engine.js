(() => {
  const kit = window.deckKit
  const root = document.documentElement
  const stage = document.querySelector(".stage")
  const chrome = document.getElementById("slide-chrome")
  const blackout = document.querySelector("[data-blackout]")
  const W = 1920
  const H = 1080
  const duration = Number(stage.dataset.duration || 420)

  let mainCount = 0
  let appendixCount = 0
  const slides = [...document.querySelectorAll(".slide")].map((el, index) => {
    const appendix = el.dataset.kind === "appendix"
    const ordinal = appendix ? ++appendixCount : ++mainCount
    const title = el.dataset.title || el.querySelector("h1, h2")?.textContent.trim() || el.id
    return { el, index, id: el.id, appendix, ordinal, title, steps: Number(el.dataset.steps || 0), ready: false }
  })
  const pad = (value) => String(value).padStart(2, "0")
  const label = (s) => (s.appendix ? `${kit.t("deck.appendix")}${s.ordinal}` : pad(s.ordinal))
  const number = (s) => (s.appendix ? `${kit.t("deck.appendix")}${s.ordinal}` : String(s.ordinal))
  const state = { index: -1, step: 0, started: null, presenter: null }

  stage.setAttribute("aria-roledescription", kit.t("deck.role"))

  for (const s of slides) {
    if (s.el.hasAttribute("data-bare") || !chrome) continue
    const node = chrome.content.firstElementChild.cloneNode(true)
    const counter = node.querySelector("[data-counter]")
    if (counter) counter.textContent = number(s)
    s.el.append(node)
  }
  kit.marks(stage)

  const call = (s, method, ...args) => {
    const scene = kit.scenes[s.id]
    if (!scene || typeof scene[method] !== "function") return
    try {
      scene[method](s.el, ...args)
    } catch (error) {
      console.error(`scene ${s.id}.${method}`, error)
    }
  }

  const applySteps = (s, step) => {
    for (const node of s.el.querySelectorAll("[data-s]")) {
      const from = Number(node.dataset.s)
      const until = node.dataset.until === undefined ? Number.POSITIVE_INFINITY : Number(node.dataset.until)
      node.classList.toggle("on", step >= from && step <= until)
    }
    for (const node of s.el.querySelectorAll("[data-at]")) {
      node.classList.toggle("at", node.dataset.at.split(",").map(Number).includes(step))
    }
    s.el.dataset.step = String(step)
  }

  const init = (s) => {
    if (s.ready) return
    s.ready = true
    call(s, "init")
  }

  const play = (s, step, dir) => {
    s.el.classList.remove("play")
    void s.el.offsetWidth
    s.el.classList.add("play")
    kit.count(s.el)
    kit.qr?.play(s.el)
    call(s, "enter", step, dir)
  }

  const syncHash = () => {
    const hash = `#${state.index + 1}${state.step ? `.${state.step}` : ""}`
    if (location.hash !== hash) history.replaceState(null, "", `${location.search}${hash}`)
  }

  const post = () => {
    const win = state.presenter
    if (!win || win.closed) return
    const s = slides[state.index]
    const next = slides[state.index + 1]
    win.postMessage(
      {
        type: "deck-state",
        index: s.appendix ? -1 : s.ordinal - 1,
        appendix: s.appendix,
        step: state.step,
        steps: s.steps,
        label: label(s),
        title: s.title,
        note: kit.notes[s.id] || null,
        next: next ? { label: label(next), title: next.title } : null,
        plan: slides.filter((x) => !x.appendix).map((x) => ({ label: label(x), title: x.title, time: kit.notes[x.id]?.time || 0 })),
        started: state.started,
        duration,
      },
      "*",
    )
  }

  const go = (index, step = 0, dir = 1) => {
    const target = Math.max(0, Math.min(slides.length - 1, index))
    const s = slides[target]
    const nextStep = Math.max(0, Math.min(s.steps, step))
    if (target !== state.index) {
      const prev = slides[state.index]
      if (prev) {
        call(prev, "leave")
        prev.el.classList.remove("is-current", "play")
      }
      s.el.classList.add("is-current")
      state.index = target
      state.step = nextStep
      applySteps(s, nextStep)
      init(s)
      play(s, nextStep, dir)
    } else {
      state.step = nextStep
      applySteps(s, nextStep)
      call(s, "step", nextStep, dir)
    }
    if (state.started === null && (state.index > 0 || state.step > 0)) state.started = Date.now()
    syncHash()
    post()
  }

  const next = () => {
    const s = slides[state.index]
    if (state.step < s.steps) go(state.index, state.step + 1, 1)
    else if (state.index < slides.length - 1) go(state.index + 1, 0, 1)
  }

  const prev = () => {
    if (state.step > 0) go(state.index, state.step - 1, -1)
    else if (state.index > 0) go(state.index - 1, slides[state.index - 1].steps, -1)
  }

  const replay = () => {
    const s = slides[state.index]
    applySteps(s, state.step)
    play(s, state.step, 1)
  }

  const toggle = (node, force) => node.classList.toggle("open", force ?? !node.classList.contains("open"))

  const openPresenter = () => {
    if (state.presenter && !state.presenter.closed) {
      state.presenter.focus()
      post()
      return
    }
    state.presenter = kit.presenter?.open() ?? null
    if (!state.presenter) return
    setTimeout(post, 300)
  }

  const fullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen()
    else root.requestFullscreen?.()
  }

  const ACTIONS = {
    presenter: openPresenter,
    fullscreen,
    replay,
    blackout: () => toggle(blackout),
  }
  const CODES = { KeyS: "presenter", KeyF: "fullscreen", KeyR: "replay", KeyB: "blackout", Period: "blackout" }
  const CHARS = { s: "presenter", f: "fullscreen", r: "replay", b: "blackout", ".": "blackout" }
  for (const action of Object.keys(ACTIONS)) {
    for (const char of kit.t(`keys.${action}`).replace(`keys.${action}`, "")) CHARS[char] = action
  }

  const onKey = (event) => {
    if (event.target instanceof HTMLElement && event.target.closest("input, textarea, [contenteditable]")) return
    if (event.ctrlKey || event.metaKey || event.altKey) return
    const key = event.key
    if (key === "Escape") {
      toggle(blackout, false)
      return
    }
    const s = slides[state.index]
    if (kit.scenes[s.id]?.key?.(s.el, event) === true) {
      event.preventDefault()
      return
    }
    if (["ArrowRight", "PageDown", " ", "Enter"].includes(key)) {
      event.preventDefault()
      next()
    } else if (["ArrowLeft", "PageUp", "Backspace"].includes(key)) {
      event.preventDefault()
      prev()
    } else if (key === "ArrowDown") {
      event.preventDefault()
      go(state.index + 1, 0, 1)
    } else if (key === "ArrowUp") {
      event.preventDefault()
      go(state.index - 1, 0, -1)
    } else if (key === "Home") {
      go(0, 0, -1)
    } else if (key === "End") {
      go(mainCount - 1, slides[mainCount - 1].steps, 1)
    } else {
      const action = CHARS[key.toLowerCase()] || CHARS[key] || CODES[event.code]
      if (action) {
        event.preventDefault()
        ACTIONS[action]()
      }
    }
  }

  const onClick = (event) => {
    if (event.target.closest("a, button, input, [data-interactive]")) return
    if (event.clientX < window.innerWidth / 3) prev()
    else next()
  }

  let touchX = null
  const onPointerDown = (event) => {
    if (event.pointerType === "touch") touchX = event.clientX
  }
  const onPointerUp = (event) => {
    if (touchX === null) return
    const dx = event.clientX - touchX
    touchX = null
    if (Math.abs(dx) > 60) {
      if (dx < 0) next()
      else prev()
    }
  }

  const readHash = () => {
    const match = /^#(\d+)(?:\.(\d+))?$/.exec(location.hash)
    return match ? { index: Number(match[1]) - 1, step: Number(match[2] || 0) } : null
  }

  const fit = () => {
    const scale = Math.min(window.innerWidth / W, window.innerHeight / H)
    stage.style.transform = `translate(-50%, -50%) scale(${scale})`
  }

  const expose = () => {
    window.deck = {
      go,
      next,
      prev,
      replay,
      get index() {
        return state.index
      },
      get step() {
        return state.step
      },
      slides: slides.map((s) => ({ id: s.id, title: s.title, steps: s.steps, appendix: s.appendix })),
    }
  }

  const bootPrint = () => {
    root.classList.add("is-print")
    for (const s of slides) {
      s.el.classList.add("is-current")
      applySteps(s, s.steps)
      init(s)
      play(s, s.steps, 1)
    }
    expose()
    root.classList.add("is-ready")
  }

  const boot = () => {
    if (kit.print) {
      bootPrint()
      return
    }
    fit()
    window.addEventListener("resize", fit)
    window.addEventListener("keydown", onKey)
    stage.addEventListener("click", onClick)
    window.addEventListener("pointerdown", onPointerDown)
    window.addEventListener("pointerup", onPointerUp)
    window.addEventListener("hashchange", () => {
      const target = readHash()
      if (target && (target.index !== state.index || target.step !== state.step)) go(target.index, target.step, 1)
    })
    window.addEventListener("message", (event) => {
      const data = event.data
      if (data?.type !== "deck-nav") return
      if (data.cmd === "next") next()
      else if (data.cmd === "prev") prev()
      else if (data.cmd === "hello") post()
      else if (data.cmd === "reset") {
        state.started = Date.now()
        post()
      }
    })
    const target = readHash() ?? { index: 0, step: 0 }
    go(target.index, target.step, 1)
    expose()
    root.classList.add("is-ready")
  }

  Promise.race([document.fonts?.ready ?? Promise.resolve(), new Promise((resolve) => setTimeout(resolve, 1500))]).then(boot)
})()
