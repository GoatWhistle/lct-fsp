deckScene("solution", {
  init(el) {
    deckKit.followPath(el.querySelector(".runner"), el.querySelector(".sol-run"))
  },
})
