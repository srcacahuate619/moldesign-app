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

console.log("[check-prod-csp] CSP de producción válida: trae el origen propio y el backend local.");
console.log(`[check-prod-csp] ${csp}`);
process.exit(0);
