document.querySelectorAll("[data-nav-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    const nav = document.querySelector("[data-site-nav]");
    if (nav) {
      nav.classList.toggle("open");
    }
  });
});

document.querySelectorAll("[data-platform-tab]").forEach((tab) => {
  tab.addEventListener("click", () => {
    const target = tab.getAttribute("data-platform-tab");
    document.querySelectorAll("[data-platform-tab]").forEach((t) => {
      t.classList.toggle("active", t.getAttribute("data-platform-tab") === target);
    });
    document.querySelectorAll("[data-platform-panel]").forEach((panel) => {
      panel.classList.toggle("active", panel.getAttribute("data-platform-panel") === target);
    });
  });
});

document.querySelectorAll("[data-filter]").forEach((pill) => {
  pill.addEventListener("click", () => {
    const filter = pill.getAttribute("data-filter");
    document.querySelectorAll("[data-filter]").forEach((p) => {
      p.classList.toggle("active", p.getAttribute("data-filter") === filter);
    });
    document.querySelectorAll("[data-tool-category]").forEach((card) => {
      const cat = card.getAttribute("data-tool-category");
      card.classList.toggle("hidden", filter !== "all" && cat !== filter);
    });
    document.querySelectorAll("[data-tools-section]").forEach((section) => {
      const visible = section.querySelectorAll("[data-tool-category]:not(.hidden)");
      section.style.display = visible.length === 0 ? "none" : "";
    });
  });
});

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy");
    const el = document.getElementById(targetId);
    if (!el) {
      return;
    }
    const text = el.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      const label = button.textContent;
      button.textContent = "Copied!";
      setTimeout(() => {
        button.textContent = label;
      }, 1500);
    } catch {
      button.textContent = "Copy failed";
    }
  });
});
