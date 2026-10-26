(() => {
  "use strict";
  // Explorador del catálogo (/catalogo). Los datos van incrustados en la página
  // (#datos-receptores, copia de receptors.json): no hace ninguna petición.
  const { english, translated, normalize } = window.MolDesignSitio;
  const root = document.documentElement;
  const catalog = JSON.parse(document.getElementById("datos-receptores").textContent);
  const receptors = catalog.records.map(record => ({
    pdb: record[0], name: record[1], family: record[2], organism: record[3], resolution: record[4], chain: record[5]
  }));
  const search = document.querySelector("[data-receptor-search]");
  const family = document.querySelector("[data-receptor-family]");
  const list = document.querySelector("[data-receptor-list]");
  const status = document.querySelector("[data-receptor-status]");
  const detail = document.querySelector("[data-receptor-detail]");
  let selected = receptors.find(record => record.pdb === "8HFI") || receptors[0];
  const unavailable = record => Object.hasOwn(catalog.unavailable, record.pdb);
  const verified = record => catalog.verified?.[record.pdb];
  const sectionLabel = record => verified(record) ? translated("Verificado", "Verified") : translated("Demostración", "Demo");
  const decimal = value => new Intl.NumberFormat(english() ? "en-US" : "es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  const resolution = record => Number.isFinite(record.resolution)
    ? `${new Intl.NumberFormat(english() ? "en-US" : "es-MX", { maximumFractionDigits: 2 }).format(record.resolution)} Å`
    : translated("No declarada", "Not declared");
  const renderReceptorDetail = () => {
    detail.querySelector("dl").hidden = false;
    const sello = verified(selected);
    detail.querySelector("[data-detail-pdb]").textContent = `${selected.pdb} / ${sello ? translated("VERIFICADO", "VERIFIED") : translated("DEMOSTRACIÓN", "DEMO")}`;
    detail.querySelector("[data-detail-name]").textContent = selected.name;
    detail.querySelector("[data-detail-intro]").textContent = sello
      ? translated(`Pose del cristal reproducida y calibración medida (${sello.experiment}): ρ = ${decimal(sello.rho)} (IC 95 % ${decimal(sello.ci95[0])}–${decimal(sello.ci95[1])}), n = ${sello.n}, ${sello.panel}. Ordena esa serie; no predice el Ki de una molécula.`,
        `Crystal pose reproduced and calibration measured (${sello.experiment}): ρ = ${decimal(sello.rho)} (95% CI ${decimal(sello.ci95[0])}–${decimal(sello.ci95[1])}), n = ${sello.n}, ${sello.panel}. It ranks that series; it does not predict the Ki of a single molecule.`)
      : translated("Ficha estructural del depósito. No acredita rendimiento de docking.", "Structural entry from the deposit. It does not establish docking performance.");
    detail.querySelector("[data-detail-family]").textContent = selected.family || translated("No declarada", "Not declared");
    detail.querySelector("[data-detail-organism]").textContent = selected.organism || translated("No declarado", "Not declared");
    detail.querySelector("[data-detail-resolution]").textContent = resolution(selected);
    detail.querySelector("[data-detail-chain]").textContent = selected.chain;
    detail.querySelector("[data-detail-availability]").textContent = unavailable(selected)
      ? translated(`No disponible · receta ${catalog.recipe} / Meeko 0.7.1`, `Unavailable · recipe ${catalog.recipe} / Meeko 0.7.1`)
      : translated(`Disponible en receta ${catalog.recipe} · no equivale a validación`, `Available with recipe ${catalog.recipe} · not scientific validation`);
    const warning = [];
    if (unavailable(selected)) warning.push(translated("La preparación se abstiene. Código: ", "Preparation abstains. Code: ") + catalog.unavailable[selected.pdb]);
    if (catalog.warnings[selected.pdb]?.includes("SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA")) {
      warning.push(translated("Las cadenas del sitio no están todas en la unidad biológica 1 del depósito: el sitio podría ser un contacto del cristal.", "Not all site chains are in the deposit’s biological assembly 1: the site may be a crystal contact."));
    }
    detail.querySelector("[data-detail-warning]").textContent = warning.join(" ");
    detail.querySelector("[data-detail-source]").href = `https://www.rcsb.org/structure/${encodeURIComponent(selected.pdb)}`;
  };
  const renderCatalog = () => {
    const query = normalize(search.value.trim());
    const filtered = receptors.filter(record => (!family.value || record.family === family.value)
      && normalize(`${record.pdb} ${record.name} ${record.family} ${record.organism || ""}`).includes(query));
    const fragment = document.createDocumentFragment();
    filtered.forEach(record => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "catalog-row";
      row.dataset.pdb = record.pdb;
      row.setAttribute("aria-current", String(record === selected));
      const code = document.createElement("span");
      code.className = "catalog-row-code";
      code.textContent = record.pdb;
      const main = document.createElement("span");
      main.className = "catalog-row-main";
      const title = document.createElement("strong");
      title.textContent = record.name;
      const meta = document.createElement("small");
      meta.textContent = `${record.family} · ${sectionLabel(record)}${unavailable(record) ? translated(" · No disponible", " · Unavailable") : ""}`;
      main.append(title, meta);
      const res = document.createElement("span");
      res.className = "catalog-row-resolution";
      res.textContent = resolution(record);
      row.append(code, main, res);
      row.addEventListener("click", () => {
        selected = record;
        list.querySelectorAll("button").forEach(item => item.setAttribute("aria-current", String(item === row)));
        renderReceptorDetail();
      });
      fragment.append(row);
    });
    if (!filtered.length) {
      const empty = document.createElement("p");
      empty.className = "catalog-empty";
      empty.textContent = translated("Ningún receptor coincide. Prueba otro PDB o elimina los filtros.", "No matching receptor. Try another PDB ID or clear the filters.");
      fragment.append(empty);
    }
    list.replaceChildren(fragment);
    status.textContent = translated(`Mostrando ${filtered.length} de ${catalog.count} entradas de Demostración`, `Showing ${filtered.length} of ${catalog.count} Demo entries`);
  };
  [...new Set(receptors.map(record => record.family).filter(Boolean))].sort().forEach(name => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    family.append(option);
  });
  search.addEventListener("input", renderCatalog);
  family.addEventListener("change", renderCatalog);
  root.addEventListener("languagechange", () => { renderCatalog(); renderReceptorDetail(); });
  renderCatalog();
  renderReceptorDetail();
})();
