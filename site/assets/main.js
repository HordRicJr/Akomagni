function activatePlatformTab(target) {
  document.querySelectorAll("[data-platform-tab]").forEach((t) => {
    t.classList.toggle("active", t.getAttribute("data-platform-tab") === target);
  });
  document.querySelectorAll("[data-platform-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.getAttribute("data-platform-panel") === target);
  });
}

function activateHeroPlatform(target) {
  document.querySelectorAll("[data-hero-platform]").forEach((t) => {
    t.classList.toggle("active", t.getAttribute("data-hero-platform") === target);
  });
  document.querySelectorAll("[data-hero-platform-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.getAttribute("data-hero-platform-panel") === target);
  });
}

function detectPlatform() {
  const ua = navigator.userAgent || "";
  if (/Win/i.test(ua) || /Windows/i.test(navigator.platform || "")) {
    return "windows";
  }
  return "linux";
}

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
    activatePlatformTab(tab.getAttribute("data-platform-tab"));
  });
});

document.querySelectorAll("[data-hero-platform]").forEach((tab) => {
  tab.addEventListener("click", () => {
    activateHeroPlatform(tab.getAttribute("data-hero-platform"));
  });
});

if (document.querySelector("[data-platform-tabs]")) {
  activatePlatformTab(detectPlatform());
}

if (document.querySelector("[data-hero-install]")) {
  activateHeroPlatform(detectPlatform());
}

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
