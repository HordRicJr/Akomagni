document.querySelectorAll("[data-nav-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    const nav = document.querySelector("[data-site-nav]");
    if (nav) {
      nav.classList.toggle("open");
    }
  });
});
