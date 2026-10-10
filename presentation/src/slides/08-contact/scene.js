deckScene("contact", {
  init(el) {
    const cells = el.querySelector(".ct-cells")
    for (let i = 0; i < 20; i += 1) {
      const cell = document.createElement("i")
      if (i >= 17) cell.className = "is-spent"
      cells.append(cell)
    }
  },
})
