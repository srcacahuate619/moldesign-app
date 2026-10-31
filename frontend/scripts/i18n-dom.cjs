"use strict";
// Lista nombrada de exclusiones. Sólo valores completos y códigos, no regiones DOM.
const TECHNICAL_NAMES = new Set(["Español", "Receptor", "receptor", "Experimental", "experimental",
  "SMILES", "PDB", "PDBQT", "SDF", "RMSD", "Vina", "ESMFold", "MolDesign", "Moldex", "Molcy", "MolChat", "Open Babel"]);
const TECHNICAL_SAMPLES = new Set(["smiles,name,active,control_role CC(=O)Nc1ccc(O)cc1,paracetamol,1,reference CC(C)Cc1ccc(cc1)C(C)C(=O)O,ibuprofeno,0,none"]);
const TECHNICAL_PATH = /^(?:[A-Za-z]:[\\/].+|[\w.-]+(?:\/[\w.-]+)*\.(?:py|ts|tsx|js|json|md|csv|sdf|pdb|pdbqt|txt)|https?:\/\/\S+)$/;
const OWNER_PENDING = [
  { id: "I18N-113", channel: "title", pattern: /^Listo para docking: grid box calibrado y \d+ residuos del sitio activo identificados\.$/ },
  { id: "I18N-115", channel: "title", pattern: /^Requiere revisión: grid box presente pero pocos residuos del sitio activo \(\d+\)\. El ligando de referencia puede no ser un fármaco\.$/ },
  { id: "I18N-116", channel: "title", pattern: /^Sin datos de calibración: el receptor no está preparado o no tiene sitio activo identificado\.$/ },
];
const KEYBOARD_SHORTCUTS = /\((?:(?:Ctrl|Shift|Alt|Cmd|Meta)\+)*(?:Del|Backspace|Esc|Enter|[A-Z])\)/g;
const { dictionaryPairs } = require("./finish-i18n-frontend.cjs");
const words = text => text.replace(/\{[^}]+\}/g, " ").toLowerCase().match(/[a-záéíóúñü]{4,}/g) || [];
const englishWords = new Set(dictionaryPairs.flatMap(pair => words(pair.en)));
const spanishWords = new Set(dictionaryPairs.flatMap(pair => words(pair.es)).filter(word => !englishWords.has(word)));
for (const word of ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre", "lunes", "martes", "jueves", "viernes", "domingo"]) spanishWords.add(word);
// Cognado inglés comprobado en el tooltip de Mol*: principal component axes.
const ENGLISH_COGNATES = new Set(["principal"]);
const SPANISH = /[áéíóúñü¿¡ÁÉÍÓÚÑÜ]|\b(?:el|la|los|las|un|una|del|que|para|con|por|sin|se|son|como|pero|este|esta|hay|desde|cuando|puede|tiene|cada|otro|otra|guardar|guardado|cargando|datos|ninguna|ninguno|pendiente|coordenadas|añadir|revisión|preparación)\b/i;
function inspectItems(items, dataTexts = new Set(), contract = { keys: new Set(), strings: new Set() }) {
  const findings = [], exclusions = [];
  for (const item of items) {
    const text = item.text.replace(/\s+/g, " ").trim();
    if (!text) continue;
    let reason = null;
    if (item.dataField && (text === item.dataField || (item.element === "DT" && contract.keys.has(text)) || (item.element === "SPAN" && contract.strings.has(text)))) reason = "campo o valor original del contrato en el consultable";
    else if (TECHNICAL_NAMES.has(text) || TECHNICAL_SAMPLES.has(text) || TECHNICAL_PATH.test(text)) reason = "valor técnico completo o selector de idioma";
    else if (/^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/.test(text)) reason = "código estable de aviso";
    else if (dataTexts.has(text)) reason = "contenido original de experimento publicado";
    const pending = OWNER_PENDING.find(row => row.channel === item.channel && row.pattern.test(text));
    if (pending) reason = pending.id + ": texto excluido por el propietario";
    if (reason) { exclusions.push({ ...item, text, reason }); continue; }
    const languageText = text.replace(KEYBOARD_SHORTCUTS, "");
    if (SPANISH.test(languageText) || words(languageText).some(word => spanishWords.has(word) && !ENGLISH_COGNATES.has(word))) findings.push({ ...item, text });
  }
  return { findings, exclusions };
}
module.exports = { inspectItems, TECHNICAL_NAMES, OWNER_PENDING };
