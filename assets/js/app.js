/* freeage — case study «Два магазина вместо одного»
   Прогрессивное улучшение: без этого файла страница читается и выглядит
   нормально, добавляются только тема, прогресс чтения, появление блоков,
   подсветка оглавления и ленивое видео. */

(() => {
  "use strict";

  const root = document.documentElement;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  root.classList.add("js");

  /* ---------------------------------------------------------------------
     Тема оформления
     --------------------------------------------------------------------- */
  const THEME_COLORS = { light: "#f7f4ef", dark: "#14110d" };
  const toggle = document.querySelector(".theme-toggle");
  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  const resolveTheme = () => {
    if (root.dataset.theme === "light" || root.dataset.theme === "dark") {
      return root.dataset.theme;
    }
    return darkQuery.matches ? "dark" : "light";
  };

  const syncThemeColor = (theme) => {
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => meta.remove());
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = THEME_COLORS[theme];
    document.head.appendChild(meta);
  };

  const syncToggle = (theme) => {
    if (!toggle) return;
    const isDark = theme === "dark";
    toggle.setAttribute("aria-pressed", String(isDark));
    toggle.setAttribute(
      "aria-label",
      isDark ? "Включить светлую тему" : "Включить тёмную тему"
    );
  };

  const applyTheme = (theme, persist) => {
    if (theme === "light" || theme === "dark") {
      root.dataset.theme = theme;
      if (persist) {
        try {
          localStorage.setItem("theme", theme);
        } catch (error) {
          /* приватный режим — просто не запоминаем выбор */
        }
      }
    }
    syncThemeColor(theme);
    syncToggle(theme);
  };

  applyTheme(resolveTheme(), false);

  toggle?.addEventListener("click", () => {
    applyTheme(resolveTheme() === "dark" ? "light" : "dark", true);
  });

  darkQuery.addEventListener?.("change", () => {
    if (!root.dataset.theme) applyTheme(resolveTheme(), false);
  });

  /* ---------------------------------------------------------------------
     Прогресс чтения и состояние шапки
     --------------------------------------------------------------------- */
  const topbar = document.querySelector(".topbar");
  let scrollQueued = false;
  let updateToc = () => {};

  const onScroll = () => {
    scrollQueued = false;
    const scrolled = window.scrollY;
    const distance = document.documentElement.scrollHeight - window.innerHeight;
    root.style.setProperty("--progress", String(clamp(scrolled / Math.max(distance, 1), 0, 1)));
    topbar?.classList.toggle("is-scrolled", scrolled > 8);
    updateToc();
  };

  const queueScroll = () => {
    if (scrollQueued) return;
    scrollQueued = true;
    window.requestAnimationFrame(onScroll);
  };

  window.addEventListener("scroll", queueScroll, { passive: true });
  window.addEventListener("resize", queueScroll, { passive: true });
  onScroll();

  /* ---------------------------------------------------------------------
     Появление блоков при прокрутке
     --------------------------------------------------------------------- */
  const revealItems = document.querySelectorAll(".reveal");

  if (!("IntersectionObserver" in window) || reduceMotion.matches) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  } else {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
    );
    revealItems.forEach((item) => revealObserver.observe(item));
  }

  /* ---------------------------------------------------------------------
     Подсветка активного пункта оглавления
     --------------------------------------------------------------------- */
  const tocLinks = [...document.querySelectorAll(".toc__link")];
  const sections = tocLinks
    .map((link) => document.getElementById(link.hash.slice(1)))
    .filter(Boolean);

  updateToc = () => {
    if (!sections.length) return;
    const threshold = 140;
    let active = sections[0];
    for (const section of sections) {
      if (section.getBoundingClientRect().top - threshold <= 0) active = section;
    }
    tocLinks.forEach((link) => {
      const isActive = link.hash === `#${active.id}`;
      link.classList.toggle("is-active", isActive);
      if (isActive) {
        link.setAttribute("aria-current", "location");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  };

  updateToc();

})();
