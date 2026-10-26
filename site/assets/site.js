(() => {
  "use strict";
  // Lo común a todas las páginas: menú, pestañas e idioma. Lo propio de cada página
  // (catálogo, registro) vive en su script y escucha "languagechange".
  const root = document.documentElement;
  const english = () => root.dataset.language === "en";
  const translated = (es, en) => english() ? en : es;
  const normalize = value => String(value).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  window.MolDesignSitio = { english, translated, normalize };

  // Abierto con file:///, el navegador no sirve el index.html de una carpeta: un enlace
  // a "ciencia/" mostraría el listado del directorio. Publicado, sobra y no hace nada.
  if (location.protocol === "file:") {
    document.querySelectorAll('a[href$="/"]').forEach(link => {
      const href = link.getAttribute("href");
      if (!/^[a-z][a-z0-9+.-]*:|^\/\//i.test(href)) link.setAttribute("href", `${href}index.html`);
    });
    document.querySelectorAll('a[href*="/#"]').forEach(link => {
      const href = link.getAttribute("href");
      if (!/^[a-z][a-z0-9+.-]*:|^\/\//i.test(href)) link.setAttribute("href", href.replace("/#", "/index.html#"));
    });
  }

  const menu = document.querySelector("[data-menu-toggle]");
  const mobile = document.getElementById("mobile-menu");
  const closeMenu = () => {
    mobile.hidden = true;
    menu.setAttribute("aria-expanded", "false");
  };
  menu.addEventListener("click", () => {
    mobile.hidden = !mobile.hidden;
    menu.setAttribute("aria-expanded", String(!mobile.hidden));
  });
  mobile.querySelectorAll("a").forEach(link => link.addEventListener("click", closeMenu));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !mobile.hidden) {
      closeMenu();
      menu.focus();
    }
  });
  const largeScreen = matchMedia("(min-width: 60rem)");
  largeScreen.addEventListener("change", event => { if (event.matches) closeMenu(); });

  document.querySelectorAll("[data-tab-group]").forEach(group => {
    const name = group.dataset.tabGroup;
    const tabs = Array.from(group.querySelectorAll("[role=tab]"));
    const panels = Array.from(document.querySelectorAll(`[data-panel-group="${name}"]`));
    const activate = tab => {
      tabs.forEach(item => {
        const active = item === tab;
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
      });
      panels.forEach(panel => { panel.hidden = panel.dataset.panel !== tab.dataset.tab; });
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(tab));
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") next = tabs[(index + tabs.length - 1) % tabs.length];
        if (event.key === "Home") next = tabs[0];
        if (event.key === "End") next = tabs[tabs.length - 1];
        if (!next) return;
        event.preventDefault();
        activate(next);
        next.focus();
      });
    });
  });

  // La banda que desfila se puede parar (más de cinco segundos de movimiento: WCAG 2.2.2).
  // Con «reducir movimiento» no desfila y el botón no hace falta.
  document.querySelectorAll("[data-desfile]").forEach(strip => {
    const button = strip.querySelector("[data-desfile-toggle]");
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    button.hidden = false;
    button.addEventListener("click", () => {
      const paused = strip.dataset.pausado !== "true";
      strip.dataset.pausado = String(paused);
      button.dataset.labelEs = paused ? "Reanudar la banda" : "Pausar la banda";
      button.dataset.labelEn = paused ? "Resume the band" : "Pause the band";
      button.setAttribute("aria-label", translated(button.dataset.labelEs, button.dataset.labelEn));
    });
  });

  // Language is optional browser-local state. Storage restrictions must not break the page.
  const languageButton = document.querySelector("[data-language-toggle]");
  const description = document.querySelector('meta[name="description"]');
  const applyLanguage = value => {
    const next = value === "en" ? "en" : "es";
    root.dataset.language = next;
    root.lang = next;
    languageButton.setAttribute("aria-pressed", String(next === "en"));
    languageButton.setAttribute("aria-label", translated("Switch to English", "Cambiar a español"));
    if (root.dataset.titleEs) document.title = translated(root.dataset.titleEs, root.dataset.titleEn);
    if (description?.dataset.contentEs) description.content = translated(description.dataset.contentEs, description.dataset.contentEn);
    document.querySelectorAll("[data-label-es]").forEach(item => {
      item.setAttribute("aria-label", translated(item.dataset.labelEs, item.dataset.labelEn));
    });
    document.querySelectorAll("[data-placeholder-es]").forEach(item => {
      item.placeholder = translated(item.dataset.placeholderEs, item.dataset.placeholderEn);
    });
    document.querySelectorAll("[data-text-es]").forEach(item => {
      item.textContent = translated(item.dataset.textEs, item.dataset.textEn);
    });
    document.querySelectorAll("[data-alt-es]").forEach(item => {
      item.alt = translated(item.dataset.altEs, item.dataset.altEn);
    });
    // Las capturas existen en los dos idiomas: sólo cambia el sufijo de su nombre.
    document.querySelectorAll("[data-capture]").forEach(item => {
      item.src = item.getAttribute("src").replace(/-(es|en)\.(png|webp)$/, `-${next}.$2`);
    });
    root.dispatchEvent(new Event("languagechange"));
    try { localStorage.setItem("moldesign-site-language", next); } catch { /* Optional preference. */ }
  };
  languageButton.addEventListener("click", () => applyLanguage(english() ? "es" : "en"));

  let savedLanguage;
  try { savedLanguage = localStorage.getItem("moldesign-site-language"); } catch { /* Optional preference. */ }
  applyLanguage(savedLanguage || "es");
})();
