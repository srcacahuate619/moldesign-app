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
let fileCount = 0;
let stringCount = 0;
const unresolved = [];
const remaining = new Set();
const SPANISH = /[????????????????]|\b(el|la|los|las|un|una|de|del|que|para|con|por|sin|se|es|son|est?|est?n|m?s|como|pero|este|esta|todo|hay|desde|cuando|puede|tiene|sobre|entre|cada|otro|otra)\b/i;
const remainingEnglish = new Set();
const ENGLISH = /\b(the|this|that|with|without|not|is|are|was|were|from|for|your|you|click|view|show|hide|loading|failed|available|select|close|open|download|upload|saved|verified|certify|register|built|camera|unlock)\b/i;
const remainingUnknown = new Set();
const TECHNICAL_ONLY = /^(?:[A-Z0-9][A-Z0-9 ._+/#()×-]*|[A-Za-z0-9_.+-]+@[A-Za-z0-9_.-]+|(?:kcal\/mol|log mol\/L|Å|Da|pH|Ki|IC50|SMILES|PDB|PDBQT|SDF|JSON|CSV|PDF|ZIP|GPU|CPU|RAM|Vina|AutoDock Vina|MolDesign|MolChat|Moldex|RDKit|Meeko|Open Babel|ESMFold|ESMFold Pro|ColabFold|DiffDock|RFdiffusion|TabPFN|Solana|Web3D|Mol\*|MolStar))$/i;

function isTechnicalOnly(value) {
  return TECHNICAL_ONLY.test(value)
    || /^(?:text|bg|border)-|rgba\(|#[0-9a-f]{3,}|https?:\/\/|^[/~.]|!important|smiles,name,|^[_ ,]/i.test(value)
    || /^(?:SDF|PDBQT?|PDF|CSV|XLSX|TXT|JSON|SMILES|SAR|LogP|GPU|CPU|GB|BBB|QED Score|SA Score|ΔScore|sha256|imp=|poses)(?:\s|:|·|—|$)/i.test(value)
    || /^(?:&Aring;|&times;|&Delta;|~?\d[\d,.–-]*\s*(?:min|pasos)|MolDesign AI · PolyForm.*|ADMET-AI & TabPFN|· PolyForm Noncommercial|· sha256|· ex|GB[,)]?(?:\. CPU:)?|\(Lovering 2009\)|✓ Permeable)$/i.test(value);
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
      const hasWords = /[A-Za-zÁÉÍÓÚÑÜáéíóúñü]{2}/.test(value);
      if (isVisible && hasWords && !technicalToken && !isTechnicalOnly(value)) {
        remainingUnknown.add(path.relative(ROOT, file) + ":" + lineOf(sf, node) + ": " + value.replace(/\s+/g, " "));
      }
      if (isVisible && !technicalToken && ENGLISH.test(value)) {
        remainingEnglish.add(path.relative(ROOT, file) + ":" + lineOf(sf, node) + ": " + value.replace(/\s+/g, " "));
      }
      return;
    }
    const component = componentFor(node);
    if (!component || !component.body || !ts.isBlock(component.body)) {
      if (kind === "jsx") {
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
console.log((WRITE ? "Migradas " : "Detectadas ") + stringCount + " cadenas en " + fileCount + " ficheros.");
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
