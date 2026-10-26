(() => {
  "use strict";
  // Registro científico (/ciencia). Los expedientes ya están en el HTML como <details>:
  // este script sólo filtra, busca y abre el que nombra la dirección (#CAL-8HFI-01).
  // Sin JavaScript se ven todos y el ancla sigue funcionando.
  const { translated, normalize } = window.MolDesignSitio;
  const root = document.documentElement;
  const controls = document.querySelector("[data-registro-controles]");
  const search = document.querySelector("[data-registro-buscar]");
  const category = document.querySelector("[data-registro-categoria]");
  const withPaper = document.querySelector("[data-registro-con-paper]");
  const status = document.querySelector("[data-registro-estado]");
  const records = Array.from(document.querySelectorAll("[data-registro-lista] > details.record")).map(element => ({
    element,
    category: element.dataset.categoria,
    paper: element.dataset.paper === "1",
    // Todo el texto, artículo incluido, una sola vez: buscar "protonación" encuentra
    // los expedientes que la tratan aunque no la nombren en el título.
    text: normalize(element.textContent),
  }));
  controls.hidden = false;

  let shown = records.length;
  const render = () => {
    const words = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
    shown = 0;
    records.forEach(record => {
      const visible = (!category.value || record.category === category.value)
        && (!withPaper.checked || record.paper)
        && words.every(word => record.text.includes(word));
      record.element.hidden = !visible;
      if (visible) shown += 1;
    });
    status.textContent = shown
      ? translated(`Mostrando ${shown} de ${records.length} expedientes`, `Showing ${shown} of ${records.length} records`)
      : translated("Ningún expediente coincide. Prueba otro término o elimina los filtros.", "No matching record. Try another term or clear the filters.");
  };
  search.addEventListener("input", render);
  category.addEventListener("change", render);
  withPaper.addEventListener("change", render);
  root.addEventListener("languagechange", render);

  const openFromHash = ({ instant = false } = {}) => {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = id && document.getElementById(id);
    if (!target || !target.matches("details.record")) return;
    if (target.hidden) {
      // Un enlace directo manda sobre los filtros: el expediente pedido tiene que verse.
      search.value = "";
      category.value = "";
      withPaper.checked = false;
      render();
    }
    target.open = true;
    // Al llegar con un enlace, sin animar miles de píxeles de desplazamiento.
    const still = instant || matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ block: "start", behavior: still ? "instant" : "smooth" });
  };
  // Abrir un expediente deja su dirección en la barra, lista para compartir.
  records.forEach(({ element }) => element.addEventListener("toggle", () => {
    if (element.open && location.hash.slice(1) !== element.id) history.replaceState(null, "", `#${element.id}`);
  }));
  window.addEventListener("hashchange", () => openFromHash());
  render();
  openFromHash({ instant: true });
})();
