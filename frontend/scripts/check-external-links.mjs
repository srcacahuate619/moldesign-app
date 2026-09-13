import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(SCRIPT_DIR, "..");
const SOURCE_DIRS = ["app", "components", "context", "hooks", "lib"];
const BOUNDARY_FILE = "components/ui/ExternalLink.tsx";
const OPEN_EXTERNAL_FILE = "lib/openExternal.ts";

function relativeFile(filePath) {
  return path.relative(FRONTEND_ROOT, filePath).replaceAll(path.sep, "/");
}

function sourceFiles(directory) {
  if (!fs.existsSync(directory)) return [];
  const entries = fs.readdirSync(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name === "node_modules" || entry.name === ".next" || entry.name === "out" || entry.name === ".agents") continue;
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...sourceFiles(fullPath));
    } else if (/\.(?:ts|tsx)$/.test(entry.name) && !/\.d\.ts$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}

export function findExternalLinkViolations(source, fileName) {
  const normalizedName = fileName.replaceAll("\\", "/");
  const isBoundary = normalizedName.endsWith(BOUNDARY_FILE);
  const isOpenExternal = normalizedName.endsWith(OPEN_EXTERNAL_FILE);
  const violations = [];
  // Los comentarios documentan precisamente el patrón que esta guarda evita.
  // Quitarlos antes de analizar evita falsos positivos sin ocultar código real.
  const code = source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");

  if (!isBoundary && !isOpenExternal && /\bwindow\.open\s*\(/.test(code)) {
    violations.push(fileName + ": window.open() debe vivir en lib/openExternal.ts");
  }

  if (isBoundary || isOpenExternal) return violations;

  const anchorPattern = /<a\b[^>]*>/gi;
  for (const match of code.matchAll(anchorPattern)) {
    const tag = match[0];
    const offset = match.index ?? 0;
    const line = source.slice(0, offset).split("\n").length;
    if (/\btarget\s*=\s*["']_blank["']/i.test(tag)) {
      violations.push(fileName + ":" + line + ": anchor con target=_blank fuera de ExternalLink");
      continue;
    }
    if (/\bhref\s*=\s*["']\s*(?:https?:|mailto:)/i.test(tag)) {
      violations.push(fileName + ":" + line + ": href externo literal fuera de ExternalLink");
      continue;
    }
    const expression = tag.match(/\bhref\s*=\s*\{([^}]*)\}/is)?.[1] ?? "";
    if (/(?:https?:\/\/|mailto:|sourceUrl|source_url|license_url|urlDelExplorador|SOLANA_WALLETS_URL)/i.test(expression)) {
      violations.push(fileName + ":" + line + ": href externo dinámico fuera de ExternalLink");
    }
  }

  return violations;
}

export function runSelfTest() {
  const samples = [
    ["<a href=\"https://example.com\">externo</a>", "bad-literal.tsx", true],
    ["<a href={sourceUrl}>externo</a>", "bad-dynamic.tsx", true],
    ["<a href=\"/login\">interno</a>", "allowed-internal.tsx", false],
    ["<a target=\"_blank\" href={url}>externo</a>", "bad-target.tsx", true],
    ["<ExternalLink href=\"https://example.com\">externo</ExternalLink>", "components/ui/ExternalLink.tsx", false],
    ["window.open(url)", "bad-window.ts", true],
    ["<a href=\"blob:local\">descarga</a>", "allowed-blob.tsx", false],
  ];
  for (const [source, fileName, shouldFail] of samples) {
    const failed = findExternalLinkViolations(source, fileName).length > 0;
    if (failed !== shouldFail) {
      throw new Error("Self-test falló para " + fileName);
    }
  }
}

function main() {
  runSelfTest();
  const violations = [];
  for (const directory of SOURCE_DIRS) {
    for (const filePath of sourceFiles(path.join(FRONTEND_ROOT, directory))) {
      const fileName = relativeFile(filePath);
      const source = fs.readFileSync(filePath, "utf8");
      violations.push(...findExternalLinkViolations(source, fileName));
    }
  }
  if (violations.length > 0) {
    console.error("Se encontraron enlaces externos fuera de la frontera central:");
    for (const violation of violations) console.error(" - " + violation);
    process.exitCode = 1;
    return;
  }
  console.log("External-link boundary: clean");
}

const invokedFile = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (invokedFile === path.resolve(fileURLToPath(import.meta.url))) main();