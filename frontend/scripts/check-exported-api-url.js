// scripts/check-exported-api-url.js
// =============================================================================
// Guardia sobre el ARTEFACTO: ningún puerto de backend horneado en `out/`.
//
// POR QUÉ EXISTE, Y POR QUÉ NO BASTABA EL TEST QUE YA HABÍA.
//
// `lib/__tests__/noHardcodedApiPort.test.ts` escanea el árbol de CÓDIGO y
// prohíbe `127.0.0.1:80xx` fuera de `lib/config.ts`. Es un buen test y estaba
// verde. Aun así, el instalador del 2026-09-01 salió con
// `http://127.0.0.1:8000` dentro de cuatro chunks del bundle.
//
// Entró por `.env.local`. `NEXT_PUBLIC_API_URL` es una variable de ENTORNO, no
// una línea de código: Next la sustituye durante el build y aparece en la
// salida sin haber pasado nunca por un archivo fuente. El guardián miraba al
// sitio correcto para el fallo que conocía, y el fallo llegó por otro lado.
//
// De ahí la regla que este script encarna: **lo que se verifica es lo que se
// entrega.** Un test sobre las fuentes comprueba la intención; esto comprueba
// el artefacto que va a viajar en el instalador.
//
// EL DAÑO QUE EVITA. Rust elige el primer puerto libre de 8000-8019. En un
// equipo con el 8000 ocupado —en el del autor, `legaldesk-server.exe`, que
// contesta 200 con HTML— el frontend hablaba con un producto ajeno. No hay
// error: los receptores giran para siempre. Peor que un fallo ruidoso, porque
// nadie sabe dónde mirar.
//
// Exit code: 0 = limpio, 1 = hay puertos horneados (bloquea el build).
// Sin dependencias: solo node + fs.
// =============================================================================

const fs = require("fs");
const path = require("path");

const OUT = path.join(__dirname, "..", "out");

/**
 * El RANGO QUE ELIGE RUST: 8000-8019. Ni más ni menos.
 *
 * Más estrecho que el del test de fuentes a propósito. `8080` aparece en el
 * chunk de `@solana/web3.js` como su validador local por defecto: no es el
 * backend de MolDesign, no lo escribimos nosotros y bloquear el build por eso
 * sería un guardián que cría desconfianza. Un guardián que se ignora no
 * protege nada.
 */
const PROHIBIDO = /(?:https?:\/\/)?(?:127\.0\.0\.1|localhost):80(?:0\d|1\d)(?!\d)/g;

/**
 * AUTOTEST - un guardian tiene que demostrar que todavia ve.
 *
 * Existe porque este guardian ya mintio una vez. Al estrechar el rango de
 * puertos, un escape mal convertido dejo un caracter de retroceso (0x08)
 * dentro de la expresion regular en vez de `\b`. La regex quedo exigiendo un
 * byte que ningun bundle contiene: el script recorrio los 167 archivos y
 * anuncio «ninguna direccion de backend horneada» sobre el MISMO export que un
 * minuto antes tenia cuatro.
 *
 * Un guardian roto es peor que ninguno. El que no existe no promete nada; este
 * firmaba que el artefacto estaba limpio. Asi que antes de dar por bueno un
 * resultado se prueba contra muestras que TIENE que ver y muestras que NO debe
 * marcar. Si el detector no distingue, el build para.
 */
const DEBE_DETECTAR = ["http://127.0.0.1:8000", "localhost:8019", "https://127.0.0.1:8007"];
const NO_DEBE_DETECTAR = ["localhost:8080", "127.0.0.1:9000", "localhost:80200"];

for (const muestra of DEBE_DETECTAR) {
  if (!new RegExp(PROHIBIDO.source).test(muestra)) {
    console.error(
      `[check-exported-api-url] ERROR: el propio detector esta roto - no ve \`${muestra}\`. ` +
        "Sin esto, un resultado «limpio» no significa nada."
    );
    process.exit(1);
  }
}
for (const muestra of NO_DEBE_DETECTAR) {
  if (new RegExp(PROHIBIDO.source).test(muestra)) {
    console.error(
      `[check-exported-api-url] ERROR: el detector es demasiado ancho - marca \`${muestra}\`, ` +
        "que no es el backend. Un guardian con falsos positivos acaba ignorado."
    );
    process.exit(1);
  }
}

/**
 * `3Dmol-min.js` y `molstar.js` son librerías de terceros que viajan tal cual
 * desde `public/`. No las escribimos nosotros y no resuelven el backend; una
 * coincidencia ahí sería de su propio código de ejemplo.
 */
const IGNORADOS = new Set(["3Dmol-min.js", "molstar.js"]);

function* archivos(dir) {
  let entradas;
  try {
    entradas = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entradas) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      yield* archivos(full);
    } else if (/\.(js|html|json|txt)$/.test(e.name) && !IGNORADOS.has(e.name)) {
      yield full;
    }
  }
}

if (!fs.existsSync(OUT)) {
  console.error(
    "[check-exported-api-url] ERROR: no existe `out/`. " +
      "Este script corre DESPUÉS de `build:desktop`, sobre el export estático."
  );
  process.exit(1);
}

// `lib/config.ts` declara `DEFAULT_API_URL = "http://127.0.0.1:8000"` como
// respaldo del NAVEGADOR, y su test de fuentes lo permite explicitamente. Esa
// constante viaja al bundle: webpack la copia al chunk compartido y a cada
// pagina que importe el modulo. Prohibirla a secas convertia el guardian en un
// bloqueo permanente sobre codigo correcto, que es como se acaba desactivando
// un guardian.
//
// Lo que SI delata una fuga es la CANTIDAD. Con `NEXT_PUBLIC_API_URL` vacia,
// `envOverride()` compila a cadena vacia y queda UNA aparicion por archivo: la
// constante. Con la variable puesta, el valor se hornea ademas ahi, y aparece
// una segunda vez. Medido en este repo sobre los dos builds del 2026-09-01.
const PERMITIDO_POR_ARCHIVO = 1;
const DEFECTO_DOCUMENTADO = "http://127.0.0.1:8000";

const hallazgos = [];
let revisados = 0;
for (const archivo of archivos(OUT)) {
  revisados += 1;
  const texto = fs.readFileSync(archivo, "utf-8");
  const encontrados = texto.match(PROHIBIDO);
  if (!encontrados) continue;

  const distintos = [...new Set(encontrados)];
  const ajenos = distintos.filter((u) => !u.endsWith(DEFECTO_DOCUMENTADO));

  // Cualquier direccion que NO sea el defecto documentado sobra siempre: un
  // 8001-8019 solo puede venir de haber horneado un puerto ya descubierto.
  if (ajenos.length > 0) {
    hallazgos.push([path.relative(OUT, archivo), ajenos, "direccion que no es el defecto documentado"]);
    continue;
  }
  if (encontrados.length > PERMITIDO_POR_ARCHIVO) {
    hallazgos.push([
      path.relative(OUT, archivo),
      [`${DEFECTO_DOCUMENTADO} x${encontrados.length}`],
      `se esperaba ${PERMITIDO_POR_ARCHIVO} (la constante de lib/config.ts); las de mas son una variable de entorno horneada`,
    ]);
  }
}

if (hallazgos.length > 0) {
  console.error(
    `[check-exported-api-url] ERROR: ${hallazgos.length} archivo(s) del export ` +
      "traen un puerto de backend horneado:"
  );
  for (const [archivo, puertos, motivo] of hallazgos) {
    console.error(`  ${archivo}  →  ${puertos.join(", ")}   (${motivo})`);
  }
  console.error(
    "\nEn escritorio el puerto lo decide Rust y lo entrega `ensure_backend`. " +
      "Una dirección fija manda al usuario contra el proceso que ocupe ese " +
      "puerto. Causa habitual: `NEXT_PUBLIC_API_URL` en un `.env*` llegando al " +
      "build; `next.config.js` la vacía cuando BUILD_TARGET=desktop."
  );
  console.error("[check-exported-api-url] El build de producción se detiene.");
  process.exit(1);
}

console.log(
  `[check-exported-api-url] ${revisados} archivos del export revisados: ` +
    "ninguna dirección de backend horneada."
);
process.exit(0);
