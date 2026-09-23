/* eslint-disable no-console */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const ROOT = path.resolve(__dirname, "..");
const WRITE = process.argv.includes("--write");

function walk(dir, accept, out) {
  out = out || [];
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (["node_modules", ".next", "out", "__tests__", "e2e"].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, accept, out);
    else if (accept(full)) out.push(full);
  }
  return out;
}
function nameOf(node) {
  return node && (ts.isIdentifier(node) || ts.isStringLiteral(node)) ? node.text : undefined;
}
function valueOf(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isParenthesizedExpression(node)) return valueOf(node.expression);
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const left = valueOf(node.left);
    const right = valueOf(node.right);
    return left === undefined || right === undefined ? undefined : left + right;
  }
  return undefined;
}
function column(file, language) {
  const source = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found = new Map();
  function visit(node) {
    if (ts.isPropertyAssignment(node) && nameOf(node.name) === language && ts.isObjectLiteralExpression(node.initializer)) {
      for (const item of node.initializer.properties) {
        if (!ts.isPropertyAssignment(item)) continue;
        const key = nameOf(item.name);
        const value = valueOf(item.initializer);
        if (key && value !== undefined) found.set(key, value);
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return found;
}
const pairs = new Map();
const translationDir = path.join(ROOT, "context", "traducciones");
for (const file of walk(translationDir, function (p) { return p.endsWith(".ts") && !p.endsWith("index.ts"); })) {
  const es = column(file, "es");
  const en = column(file, "en");
  for (const entry of es) if (en.has(entry[0])) pairs.set(entry[0], { es: entry[1], en: en.get(entry[0]) });
}
const contextFile = path.join(ROOT, "context", "LanguageContext.tsx");
const historicEs = column(contextFile, "es");
const historicEn = column(contextFile, "en");
for (const entry of historicEs) if (historicEn.has(entry[0])) pairs.set(entry[0], { es: entry[1], en: historicEn.get(entry[0]) });
const bySpanish = new Map();
const byEnglish = new Map();
function normalize(value) {
  return value.replace(/&quot;/g, "\"").replace(/\s+/g, " ").trim();
}
for (const entry of pairs) {
  if (entry[1].es === entry[1].en) continue;
  const normalized = normalize(entry[1].es);
  const keys = bySpanish.get(normalized) || [];
  keys.push(entry[0]);
  bySpanish.set(normalized, keys);
  const englishKeys = byEnglish.get(normalize(entry[1].en)) || [];
  englishKeys.push(entry[0]);
  byEnglish.set(normalize(entry[1].en), englishKeys);
}
function keyFor(value) {
  const keys = bySpanish.get(normalize(value)) || byEnglish.get(normalize(value));
  return keys && keys.length ? keys[0] : undefined;
}
function componentFor(node) {
  let cursor = node;
  while (cursor) {
    if (ts.isFunctionDeclaration(cursor) && cursor.name && /^[A-Z]/.test(cursor.name.text)) return cursor;
    if ((ts.isArrowFunction(cursor) || ts.isFunctionExpression(cursor)) &&
        ts.isVariableDeclaration(cursor.parent) && ts.isIdentifier(cursor.parent.name) &&
        /^[A-Z]/.test(cursor.parent.name.text)) return cursor;
    if ((ts.isFunctionExpression(cursor) || ts.isArrowFunction(cursor)) &&
        cursor.parent && ts.isCallExpression(cursor.parent) && cursor.parent.parent && ts.isVariableDeclaration(cursor.parent.parent) &&
        ts.isIdentifier(cursor.parent.parent.name) &&
        /^[A-Z]/.test(cursor.parent.parent.name.text)) return cursor;
    cursor = cursor.parent;
  }
}
function inTranslator(node) {
  let cursor = node.parent;
  while (cursor) {
    if (ts.isCallExpression(cursor) && ts.isIdentifier(cursor.expression) && cursor.expression.text === "t") return true;
    if (ts.isStatement(cursor)) return false;
    cursor = cursor.parent;
  }
  return false;
}
function indentation(source, position) {
  const start = source.lastIndexOf("\n", position) + 1;
  const match = source.slice(start, position).match(/^\s*/);
  return match ? match[0] : "";
}
// ── Clasificación de un literal visible ─────────────────────────────────
//
// Las letras acentuadas van con escapes \u y no escritas: el 2026-09-22 este
// regex apareció con las tildes convertidas en «?» (0x3F) por alguna
// herramienta que reescribió la codificación del archivo en d69c460, y la
// rama de castellano pasó a casar sólo signos de interrogación. Con escapes,
// el archivo es ASCII y no hay nada que corromper.
const SPANISH = /[\u00c1\u00c9\u00cd\u00d3\u00da\u00d1\u00dc\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc\u00bf\u00a1]|\b(el|la|los|las|un|una|de|del|que|para|con|por|sin|se|es|son|como|pero|este|esta|todo|hay|desde|cuando|puede|tiene|sobre|entre|cada|otro|otra)\b/i;
const ENGLISH = /\b(the|this|that|with|without|not|is|are|was|were|from|for|your|you|click|view|show|hide|loading|failed|available|select|close|open|download|upload|saved|verified|certify|register|built|camera|unlock)\b/i;
const HAS_WORDS = /[A-Za-z\u00c0-\u00ff]{2}/;

// Lo que NO es texto: clases de Tailwind, colores, URLs, rutas, CSS, la
// cabecera de un CSV. Anclado: «Evaluación #123» o «Ver https://…» sí son
// texto y antes se daban por técnicos porque el patrón casaba en cualquier
// posición.
const NO_ES_TEXTO = /^(?:text|bg|border)-|^rgba?\(|^#[0-9a-f]{3,8}$|^https?:\/\/\S+$|^(?:\/|~\/|\.\.?\/)|!important|^smiles,name,|^_/i;
// Entidades HTML, identificadores camelCase, nombres de archivo, ids de
// repositorio («Qwen/Qwen2.5-1.5B-Instruct-GGUF») y prefijos de parámetro
// («imp=»). Sin /i: «Guardar» no es camelCase.
const NO_ES_TEXTO_EXACTO = /^&[A-Za-z]+;$|^[a-z]+[A-Z][A-Za-z0-9]*$|^[\w.-]+\.(?:json|gguf|pdb|pdbqt|sdf|csv|cpp|txt|zip)$|^[\w.-]+\/[\w.-]+$|^\w+=$/;
const EMAIL = /^[A-Za-z0-9_.+-]+@[A-Za-z0-9_.-]+$/;

// Nombres de más de una palabra o con signos: se quitan enteros antes de
// mirar las palabras sueltas, para que «Open Babel» no autorice «Open».
const NOMBRES_PROPIOS = [
  "AutoDock Vina", "Open Babel", "ESMFold Pro", "MolDesign AI", "PolyForm Noncommercial",
  "ADMET-AI", "Mol*", "kcal/mol", "log mol/L", "QED Score", "SA Score", "\u0394Score",
];

// Siglas, unidades y nombres de producto que se escriben igual en los dos
// idiomas. Sensible a mayúsculas A PROPÓSITO: la bandera /i de la versión
// anterior convertía cualquier palabra sin tilde —Cohortes, OPCIONES,
// Guardar— en «técnica», y el guardián anunciaba 0 sobre cientos de cadenas.
// Una sigla nueva se añade aquí, con nombre, no con un patrón.
const SIGLAS = new Set([
  "\u00c5", "Da", "pH", "Ki", "IC50", "min", "SMILES", "PDB", "PDBQT", "SDF", "JSON", "CSV",
  "PDF", "ZIP", "XLSX", "TXT", "GPU", "CPU", "RAM", "GB", "MB", "SAR", "LogP", "BBB", "QED",
  "ID", "AI", "ADMET", "sha256", "Vina", "MolDesign", "MolChat", "Moldex", "RDKit", "Meeko",
  "ESMFold", "ColabFold", "DiffDock", "RFdiffusion", "TabPFN", "Solana", "Web3D", "MolStar",
  "Lovering", "SHA", "pKi", "Qwen", "Tanimoto", "GGUF",
]);

function isTechnicalOnly(value) {
  if (NO_ES_TEXTO.test(value) || NO_ES_TEXTO_EXACTO.test(value) || EMAIL.test(value)) return true;
  let resto = value;
  for (const nombre of NOMBRES_PROPIOS) resto = resto.split(nombre).join(" ");
  const palabras = resto.match(/[A-Za-z\u00c0-\u00ff][A-Za-z\u00c0-\u00ff0-9]*/g) || [];
  return palabras.every(function (palabra) { return palabra.length < 2 || SIGLAS.has(palabra); });
}

/**
 * ¿Un literal visible sin clave cuenta como texto pendiente de traducir?
 *
 * No depende de adivinar el idioma: cualquier palabra que no sea una sigla o
 * un nombre propio de la lista cuenta. Los detectores de castellano e inglés
 * sólo ordenan el informe; usarlos aquí marcaba «Open Babel» por el «open».
 */
function esPendiente(value) {
  return HAS_WORDS.test(value) && !isTechnicalOnly(value);
}

// ── Autotest: el guardián demuestra que ve antes de anunciar nada ────────
//
// Sin esto, el 2026-09-22 el barrido decía «Detectadas 0» sobre una interfaz
// con la barra de navegación entera sin traducir. Las muestras positivas son
// las que el detector anterior se tragaba.
const DEBE_MARCAR = [
  "Cohortes", "OPCIONES", "Guardar", "Receptor (PDB ID)", "Cohortes guardadas",
  "A\u00f1adir ligando", "\u00bfContinuar?", "~3 pasos", "Open", "SDF descargado",
  "Evaluaci\u00f3n #123", "Ver https://ejemplo.org",
];
const NO_DEBE_MARCAR = [
  "SMILES", "PDB ID", "AutoDock Vina", "kcal/mol", "IC50", "Open Babel", "PDBQT",
  "MolDesign AI \u00b7 PolyForm Noncommercial", "ADMET-AI & TabPFN", "(Lovering 2009)",
  "bg-zinc-900", "https://ejemplo.org/ruta", "#a1b2c3", "12.5 \u00c5", "sha256",
  "contacto@amezcua-dev.com", "~5 min", "&Delta;", "enableADMET", "case.json",
  "Qwen/Qwen2.5-1.5B-Instruct-GGUF", "imp=", "SHA-256", "pKi",
];

function autotest() {
  const ciegas = DEBE_MARCAR.filter(function (muestra) { return !esPendiente(muestra); });
  const falsas = NO_DEBE_MARCAR.filter(function (muestra) { return esPendiente(muestra); });
  if (!SPANISH.test("A\u00f1adir ligando") || !SPANISH.test("est\u00e1 listo") || SPANISH.test("SMILES")) {
    ciegas.push("(la rama de castellano no distingue tildes)");
  }
  if (ciegas.length || falsas.length) {
    console.error("GUARDIAN CIEGO: el autotest del barrido fallo.");
    for (const muestra of ciegas) console.error("  no ve: " + JSON.stringify(muestra));
    for (const muestra of falsas) console.error("  marca de mas: " + JSON.stringify(muestra));
    process.exit(1);
  }
  return DEBE_MARCAR.length + NO_DEBE_MARCAR.length;
}

const VISIBLE_PROPERTIES = new Set([
  "label", "desc", "description", "title", "message", "text", "placeholder",
  "aria-label", "aria-description", "ariaLabel", "ariaDescription", "alt",
  "help", "hint", "warning", "error", "emptyState", "q", "a", "reason", "note", "badge",
]);
function visibleLiteral(node, kind) {
  if (kind === "jsx") return true;
  if (ts.isJsxAttribute(node.parent)) {
    return VISIBLE_PROPERTIES.has(nameOf(node.parent.name));
  }
  if (ts.isPropertyAssignment(node.parent) && VISIBLE_PROPERTIES.has(nameOf(node.parent.name))) return true;
  let cursor = node.parent;
  while (cursor && !ts.isStatement(cursor)) {
    if (ts.isJsxExpression(cursor)) {
      if (ts.isJsxAttribute(cursor.parent)) return VISIBLE_PROPERTIES.has(nameOf(cursor.parent.name));
      return true;
    }
    if (ts.isCallExpression(cursor)) {
      const called = cursor.expression.getText();
      if (/^(alert|confirm|setError|setWarning|setMessage|toast(\.\w+)?)$/.test(called)) return true;
    }
    cursor = cursor.parent;
  }
  return false;
}
function lineOf(sf, node) {
  return sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
}
function barrer() {
let fileCount = 0;
let stringCount = 0;
const unresolved = [];
const remaining = new Set();
const remainingEnglish = new Set();
const remainingUnknown = new Set();
// «fichero: texto», sin número de línea: es lo que compara el trinquete de
// interfazSinTextoFijo.test.ts, y una línea que se mueve no es texto nuevo.
const pendientes = new Set();
const roots = ["app", "components", "hooks"].map(function (p) { return path.join(ROOT, p); });
for (const file of roots.flatMap(function (dir) { return walk(dir, function (p) { return p.endsWith(".tsx"); }); })) {
  let source = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const edits = [];
  const components = new Set();
  let needsTranslated = false;
  function candidate(node, rawValue, kind) {
    const value = rawValue && rawValue.trim();
    if (/^(es(?:-[A-Z]{2})?|s)$/i.test(value || "")) return;
    const key = value && keyFor(value);
    if (inTranslator(node)) return;
    if (!key) {
      const isVisible = value && visibleLiteral(node, kind);
      if (isVisible && SPANISH.test(value)) {
        remaining.add(path.relative(ROOT, file) + ":" + lineOf(sf, node) + ": " + value.replace(/\s+/g, " "));
      }
      const technicalToken = kind !== "jsx" && /^[a-z][a-z0-9_-]*$/.test(value);
      if (isVisible && HAS_WORDS.test(value) && !technicalToken && !isTechnicalOnly(value)) {
        remainingUnknown.add(path.relative(ROOT, file) + ":" + lineOf(sf, node) + ": " + value.replace(/\s+/g, " "));
      }
      if (isVisible && !technicalToken && ENGLISH.test(value)) {
        remainingEnglish.add(path.relative(ROOT, file) + ":" + lineOf(sf, node) + ": " + value.replace(/\s+/g, " "));
      }
      if (isVisible && !technicalToken && esPendiente(value)) {
        pendientes.add(path.relative(ROOT, file).replace(/\\/g, "/") + ": " + value.replace(/\s+/g, " "));
      }
      return;
    }
    // Tener clave no es estar traducido: el texto sigue en castellano fijo
    // hasta que pasa por t(). El 2026-09-23 un lote de migración añadió
    // «Email», «Actividad reciente» y «Modelos y motores» a un módulo, y el
    // barrido dejó de contar esos mismos literales en OTROS ficheros que los
    // seguían pintando sin traducir. Cuentan como pendientes mientras --write
    // tendría que reescribirlos; los de nivel superior no, porque las tablas
    // estáticas se resuelven con t(valor) al renderizar (ver traducciones/index.ts).
    function pendienteConClave() {
      const technicalToken = kind !== "jsx" && /^[a-z][a-z0-9_-]*$/.test(value);
      if (visibleLiteral(node, kind) && !technicalToken && esPendiente(value)) {
        pendientes.add(path.relative(ROOT, file).replace(/\\/g, "/") + ": " + value.replace(/\s+/g, " "));
      }
    }
    const component = componentFor(node);
    if (!component || !component.body || !ts.isBlock(component.body)) {
      if (kind === "jsx") {
        pendienteConClave();
        const raw = source.slice(node.pos, node.end);
        const trimmed = raw.trim();
        const start = node.pos + raw.indexOf(trimmed);
        edits.push({
          start: start, end: start + trimmed.length,
          replacement: "<Translated id=" + JSON.stringify(key) + " />",
          content: true,
        });
        needsTranslated = true;
        return;
      }
      unresolved.push(path.relative(ROOT, file) + ": nivel superior: " + key);
      return;
    }
    pendienteConClave();
    let start = node.getStart(sf);
    let end = node.getEnd();
    let replacement = "t(" + JSON.stringify(key) + ")";
    if (kind === "jsx") {
      const raw = source.slice(node.pos, node.end);
      const trimmed = raw.trim();
      start = node.pos + raw.indexOf(trimmed);
      end = start + trimmed.length;
      replacement = "{" + replacement + "}";
    } else if (kind === "string" && ts.isJsxAttribute(node.parent)) {
      replacement = "{" + replacement + "}";
    }
    edits.push({ start: start, end: end, replacement: replacement, content: true });
    components.add(component);
  }
  function visit(node) {
    if (ts.isJsxText(node)) {
      candidate(node, node.text, "jsx");
      return;
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
      const value = valueOf(node);
      if (value !== undefined && keyFor(value.trim())) {
        candidate(node, value, "expression");
        return;
      }
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      if (ts.isImportDeclaration(node.parent) || ts.isExportDeclaration(node.parent) ||
          (ts.isPropertyAssignment(node.parent) && node.parent.name === node)) return;
      candidate(node, node.text, "string");
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  for (const component of components) {
    const body = component.body;
    const bodyText = source.slice(body.getStart(sf), body.getEnd());
    const match = /const\s*\{\s*([^}]*)\}\s*=\s*useLanguage\(\)\s*;/.exec(bodyText);
    if (match) {
      if (!/(^|,)\s*t\s*(,|$)/.test(match[1])) {
        const absolute = body.getStart(sf) + match.index;
        const brace = source.indexOf("{", absolute);
        edits.push({ start: brace + 1, end: brace + 1, replacement: " t," });
      }
    } else {
      const brace = body.getStart(sf);
      edits.push({ start: brace + 1, end: brace + 1,
        replacement: "\n" + indentation(source, brace) + "  const { t } = useLanguage();" });
    }
  if (needsTranslated && !/import\s*\{[^}]*\bTranslated\b[^}]*\}\s*from\s*["'][^"']*LanguageContext["']/.test(source)) {
    const directive = /^\s*["']use client["'];\s*/.exec(source);
    const position = directive ? directive[0].length : 0;
    edits.push({ start: position, end: position,
      replacement: "\nimport { Translated } from \"@/context/LanguageContext\";\n" });
  }
  }
  if (!edits.length) continue;
  if (!/import\s*\{[^}]*\buseLanguage\b[^}]*\}\s*from\s*["'][^"']*LanguageContext["']/.test(source)) {
    const directive = /^\s*["']use client["'];\s*/.exec(source);
    const position = directive ? directive[0].length : 0;
    edits.push({ start: position, end: position,
      replacement: "\nimport { useLanguage } from \"@/context/LanguageContext\";\n" });
  }
  const unique = new Map();
  for (const edit of edits) unique.set(edit.start + ":" + edit.end + ":" + edit.replacement, edit);
  const ordered = Array.from(unique.values()).sort(function (a, b) { return b.start - a.start || b.end - a.end; });
  for (const edit of ordered) source = source.slice(0, edit.start) + edit.replacement + source.slice(edit.end);
  if (WRITE) fs.writeFileSync(file, source, "utf8");
  fileCount += 1;
  stringCount += ordered.filter(function (edit) { return edit.content; }).length;
}
return {
  fileCount: fileCount, stringCount: stringCount, unresolved: unresolved, remaining: remaining,
  remainingEnglish: remainingEnglish, remainingUnknown: remainingUnknown,
  pendientes: Array.from(pendientes).sort(),
};
}

module.exports = { SPANISH: SPANISH, ENGLISH: ENGLISH, isTechnicalOnly: isTechnicalOnly, esPendiente: esPendiente, autotest: autotest };

if (require.main === module) {
const muestras = autotest();
if (process.argv.includes("--autotest")) {
  console.log("Autotest del barrido: " + muestras + " muestras, el guardian ve.");
  process.exit(0);
}
const { fileCount, stringCount, unresolved, remaining, remainingEnglish, remainingUnknown, pendientes } = barrer();
if (process.argv.includes("--json")) {
  process.stdout.write(JSON.stringify(pendientes, null, 2) + "\n");
  process.exit(0);
}
console.log((WRITE ? "Migradas " : "Detectadas ") + stringCount + " cadenas en " + fileCount + " ficheros.");
console.log("Texto visible pendiente de traducir: " + pendientes.length);
if (unresolved.length) {
  console.log("Pendientes de nivel superior:");
  for (const item of unresolved) console.log("  " + item);
}
if (remaining.size) {
  console.log("Castellano visible sin clave:");
  for (const item of remaining) console.log("  " + item);
}
if (remainingEnglish.size) {
  console.log("Ingles visible sin clave:");
  for (const item of remainingEnglish) console.log("  " + item);
}
if (remainingUnknown.size) {
  console.log("Texto visible sin clave:");
  for (const item of remainingUnknown) console.log("  " + item);
}
if (process.argv.includes("--inventory")) {
  const values = Array.from(new Set(Array.from(remaining, function (item) {
    return item.replace(/^[^:]+:\d+:\s*/, "");
  }))).sort(function (a, b) { return a.localeCompare(b, "es"); });
  const output = path.join(ROOT, ".i18n-inventory.json");
  fs.writeFileSync(output, JSON.stringify(values, null, 2) + "\n", "utf8");
  console.log("Inventario escrito:", values.length, path.relative(ROOT, output));
}
}
