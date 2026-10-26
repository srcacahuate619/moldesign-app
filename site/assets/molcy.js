(() => {
  "use strict";
  // Portada: la demostración en vídeo de Molcy y el tutorial «Del caso al vídeo».
  const { translated } = window.MolDesignSitio;
  const root = document.documentElement;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

  // ── El vídeo se comporta como un GIF: en bucle, sin sonido, sin controles. ──
  // Sólo se reproduce mientras se ve. Con «reducir movimiento» no arranca solo: se queda
  // en su fotograma de reposo con los controles del navegador. Más de cinco segundos de
  // movimiento piden una forma de pararlo (WCAG 2.2.2): el botón.
  const video = document.querySelector("[data-demo]");
  const toggle = document.querySelector("[data-demo-toggle]");
  if (video && toggle) {
    let pausedByUser = reducedMotion.matches;
    // La etiqueta dice lo que hará el botón; el icono, lo mismo.
    const label = () => {
      const playing = !video.paused;
      toggle.dataset.pausado = String(!playing);
      toggle.dataset.labelEs = playing ? "Pausar la demostración" : "Reproducir la demostración";
      toggle.dataset.labelEn = playing ? "Pause the demo" : "Play the demo";
      toggle.setAttribute("aria-label", translated(toggle.dataset.labelEs, toggle.dataset.labelEn));
    };
    const play = () => { video.play().catch(() => { /* Autoplay blocked: the poster and button remain. */ }); };
    if (!reducedMotion.matches) {
      video.controls = false;
      toggle.hidden = false;
      new IntersectionObserver(([entry]) => {
        if (entry.isIntersecting && !pausedByUser) play();
        else if (!entry.isIntersecting) video.pause();
      }, { threshold: 0.35 }).observe(video);
    }
    toggle.addEventListener("click", () => {
      pausedByUser = !video.paused;
      if (video.paused) play(); else video.pause();
    });
    video.addEventListener("play", label);
    video.addEventListener("pause", label);
    root.addEventListener("languagechange", label);
    label();
  }

  // ── El tutorial del Inicio de la aplicación: mismas capturas, mismas cajas. ──
  const tutorial = document.querySelector("[data-tutorial]");
  if (!tutorial) return;
  const data = JSON.parse(document.getElementById("datos-tutorial-molcy").textContent);
  const steps = Array.from(tutorial.querySelectorAll("[data-paso]"));
  const image = tutorial.querySelector("[data-tutorial-img]");
  const box = tutorial.querySelector("[data-tutorial-box]");
  const arrow = tutorial.querySelector("[data-tutorial-arrow]");
  const counter = tutorial.querySelector("[data-tutorial-count]");
  const previous = tutorial.querySelector("[data-tutorial-prev]");
  const next = tutorial.querySelector("[data-tutorial-next]");
  const percent = (value, total) => `${(value / total * 100).toFixed(2)}%`;
  let active = 0;
  tutorial.classList.add("is-enhanced");

  const render = () => {
    const language = root.dataset.language === "en" ? "en" : "es";
    const step = data.pasos[active];
    const mark = data.marcas[language][step];
    const [x, y, w, h] = mark.caja;
    image.src = image.getAttribute("src").replace(/\/(es|en)\/[a-z]+\.webp$/, `/${language}/${step}.webp`);
    image.alt = data.alt[language][step];
    image.width = mark.ancho;
    image.height = mark.alto;
    Object.assign(box.style, {
      left: percent(x - 4, mark.ancho), top: percent(y - 4, mark.alto),
      width: percent(w + 8, mark.ancho), height: percent(h + 8, mark.alto),
    });
    // Desde arriba; si el botón está pegado al borde superior, desde abajo (como en la app).
    const fromBelow = y / mark.alto < 0.14;
    arrow.dataset.desde = fromBelow ? "abajo" : "arriba";
    arrow.style.left = percent(x + w / 2, mark.ancho);
    arrow.style.top = percent(fromBelow ? y + h + 10 : y - 10, mark.alto);
    // Reinicia el rebote de la flecha en cada paso.
    arrow.classList.remove("is-pointing");
    void arrow.offsetWidth;
    arrow.classList.add("is-pointing");
    steps.forEach((button, index) => {
      if (index === active) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    counter.textContent = data.paso[language].replace("{n}", active + 1).replace("{total}", data.pasos.length);
    previous.disabled = active === 0;
    next.disabled = active === data.pasos.length - 1;
  };
  const go = index => { active = Math.max(0, Math.min(data.pasos.length - 1, index)); render(); };
  steps.forEach((button, index) => button.addEventListener("click", () => go(index)));
  previous.addEventListener("click", () => go(active - 1));
  next.addEventListener("click", () => go(active + 1));
  root.addEventListener("languagechange", render);
  render();
})();
