// scripts/check-no-remote-assets.js
// =============================================================================
// Guardia sobre el ARTEFACTO: el export no puede pedir nada a Internet al cargar.
//
// POR QUE EXISTE. MolDesign se instala y se ejecuta sin red por diseño: los
// pesos se descargan una vez, a peticion del investigador, y a partir de ahi la
// aplicacion es autonoma. Esa promesa se rompio sin que nadie lo notara.
//
// `@solana/wallet-adapter-react-ui/styles.css` empieza con:
//
//     @import url('https://fonts.googleapis.com/css2?family=DM+Sans...');
//
// `WalletProvider` se monta globalmente, asi que la aplicacion de escritorio
// salia a buscar una tipografia a Google en CADA arranque. Nunca funciono —la
// CSP de produccion bloqueaba la peticion— pero tampoco fallo de forma visible:
// el usuario veia la fuente de respaldo y el arranque perdia el tiempo en una
// peticion condenada. Un fallo silencioso de un requisito declarado.
//
// LO QUE SE COMPRUEBA. Que el CSS y el HTML del export no traigan `@import` ni
// `<link>` a un origen remoto. Se mira el artefacto y no el codigo porque el
// origen estaba dentro de `node_modules`: ningun archivo del repositorio
// mencionaba Google, y un escaneo de fuentes habria dado verde.
//
// Lo que NO cubre: una peticion que un script haga en tiempo de ejecucion. Para
// eso hace falta cargar la pagina, y eso es un smoke test, no un grep. Se dice
// aqui para que nadie lea este verde como mas de lo que es.
//
// Exit code: 0 = limpio, 1 = hay recursos remotos (bloquea el build).
// =============================================================================

const fs = require("fs");
const path = require("path");

const OUT = path.join(__dirname, "..", "out");

/** `@import url(http...)` y `<link ... href="http...">`, con cualquier comilla. */
const REMOTO = [
  /@import\s+(?:url\()?\s*["']?https?:\/\/[^"')\s]+/gi,
  /<link\b[^>]*\bhref\s*=\s*["']https?:\/\/[^"']+["'][^>]*>/gi,
];

/**
 * AUTOTEST - un guardian que no demuestra que ve, no sirve.
 * Ver el incidente del detector con un 0x08 dentro, en check-exported-api-url.js.
 */
const DEBE_VER = [
  `@import url('https://fonts.googleapis.com/css2?family=DM+Sans');`,
  `<link rel="stylesheet" href="https://cdn.ejemplo.com/x.css"/>`,
];
const NO_DEBE_VER = [
  `@import url("./local.css");`,
  `<link rel="stylesheet" href="/_next/static/css/abc.css"/>`,
  `// comenta https://fonts.googleapis.com sin importarlo`,
];

function detecta(texto) {
  return REMOTO.some((re) => new RegExp(re.source, re.flags).test(texto));
}

for (const m of DEBE_VER) {
  if (!detecta(m)) {
    console.error(`[check-no-remote-assets] ERROR: el detector no ve \`${m.slice(0, 60)}\`.`);
    process.exit(1);
  }
}
for (const m of NO_DEBE_VER) {
  if (detecta(m)) {
    console.error(`[check-no-remote-assets] ERROR: el detector marca de mas: \`${m.slice(0, 60)}\`.`);
    process.exit(1);
  }
}

function* archivos(dir) {
  let entradas;
  try {
    entradas = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entradas) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) yield* archivos(full);
    else if (/\.(css|html)$/.test(e.name)) yield full;
  }
}

if (!fs.existsSync(OUT)) {
  console.error("[check-no-remote-assets] ERROR: no existe `out/`. Corre despues de `build:desktop`.");
  process.exit(1);
}

const hallazgos = [];
let revisados = 0;
for (const archivo of archivos(OUT)) {
  revisados += 1;
  const texto = fs.readFileSync(archivo, "utf-8");
  for (const re of REMOTO) {
    const encontrados = texto.match(new RegExp(re.source, re.flags));
    if (encontrados) {
      hallazgos.push([path.relative(OUT, archivo), [...new Set(encontrados)].slice(0, 3)]);
      break;
    }
  }
}

if (hallazgos.length > 0) {
  console.error(
    `[check-no-remote-assets] ERROR: ${hallazgos.length} archivo(s) del export piden ` +
      "un recurso remoto al cargar:"
  );
  for (const [archivo, refs] of hallazgos) {
    console.error(`  ${archivo}`);
    for (const r of refs) console.error(`      ${r.slice(0, 110)}`);
  }
  console.error(
    "\nLa aplicacion de escritorio funciona sin red por diseño. Si la fuente o la " +
      "hoja hacen falta, se empaquetan; si no, se retira la referencia. Un recurso " +
      "remoto que la CSP bloquea no es 'inofensivo': es una promesa rota en silencio."
  );
  process.exit(1);
}

console.log(
  `[check-no-remote-assets] ${revisados} archivos CSS/HTML revisados: ningun recurso remoto.`
);
process.exit(0);
