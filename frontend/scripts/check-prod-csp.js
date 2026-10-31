// scripts/check-prod-csp.js
// =============================================================================
// F-11 — Validador READ-ONLY de la CSP de producción (nunca muta configuración).
//
// El build de producción empaqueta la CSP de src-tauri/tauri.conf.prod.json
// (merge vía `tauri build --config src-tauri/tauri.conf.prod.json`; ver
// package.json → "tauri:build"). Este script verifica ese artefacto ANTES de
// empaquetar y bloquea el build (exit 1) si le falta algo que la aplicación
// necesita para funcionar.
//
// -----------------------------------------------------------------------------
// CORRECCIÓN DEL 2026-09-01 — la premisa anterior era falsa
// -----------------------------------------------------------------------------
// Hasta hoy este script BLOQUEABA el build si la CSP contenía 'unsafe-eval',
// razonando: «el bundle compilado de Next.js no usa eval(); Ketcher y MolStar
// sólo lo requieren en dev».
//
// Eso resultó ser falso, y costó un instalador entero. En el primer build de
// producción real, la aplicación instalada mostró:
//
//     Evaluating a string as JavaScript violates the following Content
//     Security Policy directive because 'unsafe-eval' is not an allowed
//     source of script
//
// El bundle SERVIDO contiene `eval(`/`new Function(` en dos archivos:
//   - out/molstar.js     → 4 apariciones
//   - out/3Dmol-min.js   → 1 aparición
//
// Los dos son visores moleculares que se cargan como scripts globales desde
// `public/`. No son código de desarrollo: viajan en el instalador y se ejecutan
// en la máquina del investigador. Nunca se había detectado porque la config de
// DESARROLLO (`tauri.conf.json`) sí trae 'unsafe-eval', así que en `tauri dev`
// todo funcionaba; el overlay de producción lo quitaba, y el overlay de
// producción no se había ejercitado hasta el primer `tauri:build`.
//
// La decisión de producto: se conserva 'unsafe-eval' para que los visores 3D
// funcionen. Un visor molecular que no pinta nada es un fallo que el
// investigador ve en el primer minuto; el riesgo de 'unsafe-eval' en una
// aplicación de escritorio cuyo `default-src` es 'self' y que no carga
// contenido remoto es real pero mucho menor. Queda como DESVIACIÓN DECLARADA:
// se retira el día que molstar y 3Dmol se sustituyan o se parcheen, no antes.
//
// -----------------------------------------------------------------------------
// Excepciones aceptadas, con su motivo
// -----------------------------------------------------------------------------
//   'unsafe-inline' en style-src : Next.js + Tailwind generan estilos inline
//                                  (~50% de los componentes usan style={{...}}).
//                                  Refactor pendiente (Tarea #3 del audit).
//   'unsafe-inline' en script-src: el runtime de Next.js inyecta scripts inline
//                                  durante la hidratación. El nonce del
//                                  middleware sólo aplica en browser.
//   'unsafe-eval'   en script-src: molstar.js y 3Dmol-min.js. Ver arriba.
//   data:           en connect-src: el módulo WebAssembly de Mol* viaja como `data:` URI dentro
//                                  de molstar.js y se carga con fetch (QA1-010; Ketcher al abrir un
//                                  receptor lo vio igual). Decisión del propietario, 2026-10-04.
//                                  Un `data:` no abre ninguna conexión de red. Sólo en connect-src:
//                                  nunca en default/script/style/worker/frame-src.
//
// -----------------------------------------------------------------------------
// Lo que este script SÍ bloquea
// -----------------------------------------------------------------------------
// Un gate que sólo avisa no es un gate. Lo que se comprueba ahora es que la CSP
// contenga lo que la aplicación NECESITA, porque el modo de fallo real de este
// archivo no fue «alguien añadió un permiso de más», sino «alguien quitó uno de
// menos y la aplicación dejó de funcionar sin que ninguna prueba lo notara».
//
// En particular `connect-src` tiene que incluir el ORIGEN PROPIO. En Windows,
// Tauri v2 sirve la aplicación desde `http://tauri.localhost`, y la lista
// anterior sólo traía la variante `https://`. Resultado: todo `fetch()` con
// ruta relativa quedaba bloqueado. El síntoma en la aplicación instalada fue
// «No se pudo cargar el registro científico. Failed to fetch», con el archivo
// correctamente empaquetado a un palmo de distancia.
//
// Detalle completo: docs/30_SECURITY_CSP_AUDIT.md
//
// Exit code: 0 = CSP de producción válida, 1 = inválida (bloquea el build).
// Sin dependencias: solo node + fs.
// =============================================================================

const fs = require("fs");
const path = require("path");

const PROD_CONFIG = path.join(__dirname, "..", "src-tauri", "tauri.conf.prod.json");

/**
 * Fuentes que `connect-src` DEBE traer, y qué se rompe sin cada una.
 * El origen propio va primero porque es el que faltaba.
 */
const CONNECT_SRC_REQUERIDO = [
  ["'self'", "las peticiones al propio origen (registro científico, assets)"],
  ["http://tauri.localhost", "el origen real de la app en Windows (Tauri v2)"],
  ["http://127.0.0.1:*", "el backend local, en el puerto que elija Rust"],
  ["ipc:", "el canal IPC de Tauri"],
  ["http://ipc.localhost", "el canal IPC de Tauri en Windows"],
  ["https://api.devnet.solana.com", "la prueba de concepto de Solana devnet (airdrop, firma y confirmación desde la ventana)"],
  ["wss://api.devnet.solana.com", "la confirmación por suscripción de la transacción de devnet"],
];

/** Directivas sin las cuales la aplicación no funciona. */
const DIRECTIVAS_REQUERIDAS = ["default-src", "connect-src", "script-src", "style-src"];

/** Desviaciones declaradas: se avisan siempre, nunca en silencio. */
const DESVIACIONES = [
  ["'unsafe-eval'", "script-src", "molstar.js y 3Dmol-min.js lo necesitan; sin él los visores 3D no pintan"],
  ["'unsafe-inline'", "style-src", "estilos inline de Next.js/Tailwind (Tarea #3 del audit)"],
];

function fail(msg) {
  console.error(`[check-prod-csp] ERROR: ${msg}`);
  console.error("[check-prod-csp] El build de producción se detiene.");
  process.exit(1);
}

if (!fs.existsSync(PROD_CONFIG)) {
  fail(
    `no se encontró ${PROD_CONFIG} — ` +
      "el build de producción requiere este archivo (merge con --config)."
  );
}

let config;
try {
  config = JSON.parse(fs.readFileSync(PROD_CONFIG, "utf-8"));
} catch (e) {
  fail(`tauri.conf.prod.json no es JSON válido: ${e.message}`);
}

const csp = config && config.app && config.app.security && config.app.security.csp;
if (typeof csp !== "string" || !csp.trim()) {
  fail("app.security.csp ausente o vacío en tauri.conf.prod.json");
}

for (const directiva of DIRECTIVAS_REQUERIDAS) {
  if (!csp.includes(`${directiva} `)) {
    fail(`la CSP de producción no declara \`${directiva}\`.`);
  }
}

// `connect-src` termina en el siguiente `;` o al final de la cadena.
const connectSrc = (csp.split("connect-src")[1] || "").split(";")[0];
for (const [fuente, porque] of CONNECT_SRC_REQUERIDO) {
  if (!connectSrc.includes(fuente)) {
    fail(
      `\`connect-src\` no incluye ${fuente}. Sin eso deja de funcionar: ${porque}. ` +
        "Es el fallo que dejó el instalador del 2026-09-01 sin registro científico."
    );
  }
}

// Molcy necesita medios del backend local. Se conserva el resto de la CSP.
function mediosMolcyPermitidos(policy) {
  const directive = policy.split(";").map(item => item.trim()).find(item => item.startsWith("media-src "));
  const sources = directive ? directive.split(/\s+/).slice(1) : [];
  return ["'self'", "http://127.0.0.1:*", "http://localhost:*"].every(source => sources.includes(source));
}
// El guardián demuestra que detecta permisos ausentes y coincidencias parciales.
if (!mediosMolcyPermitidos("media-src 'self' http://127.0.0.1:* http://localhost:*;") ||
    mediosMolcyPermitidos("default-src 'self';") ||
    mediosMolcyPermitidos("media-src 'self' http://127.0.0.1:*;") ||
    mediosMolcyPermitidos("media-src 'self' http://127.0.0.1:8000 http://localhost:*;")) {
  fail("El guardián de medios Molcy no pasó su autotest.");
}
if (!mediosMolcyPermitidos(csp)) fail("media-src no permite los videos del backend local de Molcy.");

for (const [token, directiva, motivo] of DESVIACIONES) {
  if (csp.includes(token)) {
    console.warn(`[check-prod-csp] DESVIACIÓN DECLARADA en ${directiva}: ${token} — ${motivo}`);
  }
}

// -----------------------------------------------------------------------------
// La trampa que costo la segunda build: un nonce anula 'unsafe-inline'
// -----------------------------------------------------------------------------
// Tauri analiza los assets empaquetados y REESCRIBE la CSP anadiendo nonces y
// hashes. Por especificacion CSP, en cuanto una directiva trae un nonce o un
// hash, `'unsafe-inline'` SE IGNORA por compatibilidad.
//
// Consecuencia medida el 2026-09-01 sobre la app instalada: todos los
// `style={{...}}` de React se descartaron. El boton de MolChat perdio su
// `position: fixed` y su fondo, y aparecio en el flujo normal del documento —
// abajo del todo, a la izquierda, transparente y solo visible con scroll. Lo
// mismo dejo a Ketcher pintando su interfaz sin estilos.
//
// En desarrollo no pasa porque Tauri sirve desde `devUrl` y no reescribe nada:
// la inyeccion solo ocurre sobre assets empaquetados. Por eso `tauri dev`
// funcionaba y el instalador no.
//
// `dangerousDisableAssetCspModification: ["style-src"]` le dice a Tauri que no
// toque esa directiva. Se deja SOLO style-src: en `script-src` la inyeccion de
// hashes de Tauri si funciona (cubre los scripts inline de Next) y se conserva.
const BASE_CONFIG = path.join(__dirname, "..", "src-tauri", "tauri.conf.json");
let base = {};
try {
  base = JSON.parse(fs.readFileSync(BASE_CONFIG, "utf-8"));
} catch (e) {
  fail(`no se pudo leer ${BASE_CONFIG}: ${e.message}`);
}
const sinTocar = ((base.app || {}).security || {}).dangerousDisableAssetCspModification;
const styleSrc = (csp.split("style-src")[1] || "").split(";")[0];
if (styleSrc.includes("'unsafe-inline'")) {
  const cubierto =
    sinTocar === true || (Array.isArray(sinTocar) && sinTocar.includes("style-src"));
  if (!cubierto) {
    fail(
      "`style-src` depende de 'unsafe-inline', pero Tauri tiene permiso para " +
        "inyectar nonces en esa directiva. Un nonce ANULA 'unsafe-inline', y con " +
        "el se caen todos los `style={{...}}` de React: es el fallo que dejo el " +
        "boton de MolChat sin posicion ni color y a Ketcher sin estilos. " +
        'Solucion: `dangerousDisableAssetCspModification: ["style-src"]` en ' +
        "tauri.conf.json.",
    );
  }
  console.log(
    "[check-prod-csp] style-src protegido: Tauri no inyectara nonces ahi, " +
      "asi que los estilos en linea de React sobreviven.",
  );
}

// -----------------------------------------------------------------------------
// `data:` en connect-src, y que el MSIX lleve la MISMA política que producción
// -----------------------------------------------------------------------------
// El MSIX (Microsoft Store) se construye con `tauri.conf.msix.json`, no con la config de
// producción, y este script sólo miraba la segunda. Resultado: cuando Molcy añadió
// `media-src` a la de producción, la del MSIX se quedó sin él y los vídeos de Molcy del backend
// local habrían quedado bloqueados en el paquete de la Store. «Lo que se verifica tiene que ser lo que
// se entrega»: las dos políticas se comparan directiva a directiva.
const MSIX_CONFIG = path.join(__dirname, "..", "src-tauri", "tauri.conf.msix.json");

function ipcPermitido(policy) {
  const sources = directivasDe(policy).get("connect-src") || [];
  return ["ipc:", "http://ipc.localhost"].every(source => sources.includes(source));
}

// No confundir el origen de la ventana con el del protocolo IPC. Tampoco
// aceptar una coincidencia parcial como http://ipc.localhost.ejemplo.com.
if (!ipcPermitido("connect-src ipc: http://ipc.localhost;") ||
    ipcPermitido("connect-src 'self' http://tauri.localhost;") ||
    ipcPermitido("connect-src http://ipc.localhost;") ||
    ipcPermitido("connect-src ipc:;") ||
    ipcPermitido("connect-src ipc: http://ipc.localhost.ejemplo.com;")) {
  fail("El guardián de IPC no pasó su autotest.");
}
const proxySource = fs.readFileSync(path.join(__dirname, "..", "proxy.ts"), "utf8");
const nextPolicy = proxySource.match(/`(connect-src [^`]+)`/);
for (const [name, policy] of [["Next dev (proxy.ts)", nextPolicy?.[1] || ""],
  ["Tauri dev", base.app?.security?.csp || ""], ["Tauri producción", csp]]) {
  if (!ipcPermitido(policy)) fail(`${name}: connect-src bloquea el IPC de Tauri.`);
}

function directivasDe(policy) {
  const mapa = new Map();
  for (const trozo of policy.split(";")) {
    const limpio = trozo.trim();
    if (!limpio) continue;
    const [nombre, ...fuentes] = limpio.split(/\s+/);
    mapa.set(nombre, [...new Set(fuentes)].sort());
  }
  return mapa;
}

// El panel usa exclusivamente el puerto efímero IPv4 del sidecar verificado.
function marcoMolchatPermitido(policy) {
  return (directivasDe(policy).get("frame-src") || []).includes("http://127.0.0.1:*");
}
if (!marcoMolchatPermitido("frame-src 'self' http://127.0.0.1:*;") ||
    marcoMolchatPermitido("frame-src 'self' http://127.0.0.1:8000;") ||
    marcoMolchatPermitido("frame-src 'self' http://127.0.0.1.example:*;")) {
  fail("El guardián de iframe MolChat no pasó sus controles.");
}
for (const [nombre, policy] of [["Tauri dev", base.app?.security?.csp || ""], ["Tauri producción", csp]]) {
  if (!marcoMolchatPermitido(policy)) fail(`${nombre}: frame-src bloquea el sidecar MolChat.`);
}

/** `data:` tiene que estar en connect-src y NO en las directivas que ejecutan o incrustan contenido. */
function problemasDeData(policy) {
  const d = directivasDe(policy);
  const problemas = [];
  if (!(d.get("connect-src") || []).includes("data:")) problemas.push("connect-src no trae `data:`");
  for (const nombre of ["default-src", "script-src", "style-src", "worker-src", "frame-src", "object-src"]) {
    if ((d.get(nombre) || []).includes("data:")) {
      problemas.push(`${nombre} trae \`data:\` (sólo se admite en connect-src, img-src y font-src)`);
    }
  }
  return problemas;
}

/** Diferencias entre dos políticas, directiva a directiva (el orden y los duplicados no cuentan). */
function diferenciasDePoliticas(a, b) {
  const da = directivasDe(a);
  const db = directivasDe(b);
  const salida = [];
  for (const nombre of new Set([...da.keys(), ...db.keys()])) {
    const x = da.get(nombre);
    const y = db.get(nombre);
    if (!x) salida.push(`${nombre}: sólo está en la segunda`);
    else if (!y) salida.push(`${nombre}: falta en la segunda`);
    else if (x.join(" ") !== y.join(" ")) salida.push(`${nombre}: «${x.join(" ")}» frente a «${y.join(" ")}»`);
  }
  return salida;
}

// El guardián demuestra que ve: casos que deben detectarse y casos que no.
if (
  problemasDeData("default-src 'self'; connect-src 'self' data:; img-src 'self' data: blob:").length !== 0 ||
  problemasDeData("connect-src 'self'; img-src data:").length === 0 || // data: sólo en img-src no vale
  problemasDeData("connect-src 'self' data:; script-src 'self' data:").length === 0 ||
  problemasDeData("default-src 'self' data:; connect-src data:").length === 0 ||
  diferenciasDePoliticas("a-src 'self' x; b-src y", "b-src y; a-src x 'self'").length !== 0 ||
  diferenciasDePoliticas("a-src 'self'; media-src x", "a-src 'self'").length !== 1 ||
  diferenciasDePoliticas("a-src 'self'", "a-src 'self' extra").length !== 1
) {
  fail("El guardián de `data:` y de paridad no pasó su autotest.");
}

for (const problema of problemasDeData(csp)) {
  fail(`CSP de producción: ${problema}. Decisión del 2026-10-04: \`data:\` sólo en connect-src.`);
}
console.warn(
  "[check-prod-csp] DESVIACIÓN DECLARADA en connect-src: data: — el módulo WebAssembly de Mol* viaja como " +
    "`data:` URI y se carga con fetch; no abre ninguna conexión de red (decisión del propietario, 2026-10-04)",
);

if (!fs.existsSync(MSIX_CONFIG)) {
  fail(`no se encontró ${MSIX_CONFIG}: el paquete de la Store se construye con esa configuración.`);
}
let cspMsix;
try {
  cspMsix = JSON.parse(fs.readFileSync(MSIX_CONFIG, "utf-8")).app.security.csp;
} catch (e) {
  fail(`tauri.conf.msix.json no tiene app.security.csp legible: ${e.message}`);
}
for (const problema of problemasDeData(cspMsix)) fail(`CSP del MSIX: ${problema}.`);
if (!marcoMolchatPermitido(cspMsix)) fail("MSIX: frame-src bloquea el sidecar MolChat.");
const proxy = fs.readFileSync(path.join(__dirname, "..", "proxy.ts"), "utf8");
if (!proxy.includes("frame-src 'self' blob: http://127.0.0.1:*")) {
  fail("CSP de Next: frame-src bloquea el sidecar MolChat.");
}
const distintas = diferenciasDePoliticas(csp, cspMsix);
if (distintas.length > 0) {
  fail(
    "la CSP del MSIX (Store) difiere de la de producción — " +
      distintas.join("; ") +
      ". Lo que se publica en la Store tiene que ser lo que este script verifica.",
  );
}
console.log("[check-prod-csp] la CSP del MSIX coincide con la de producción, directiva a directiva.");

console.log("[check-prod-csp] CSP de producción válida: trae el origen propio y el backend local.");
console.log(`[check-prod-csp] ${csp}`);
process.exit(0);
