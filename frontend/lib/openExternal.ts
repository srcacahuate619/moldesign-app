// =====================================================================
// Frontera UNICA de navegacion externa
// =====================================================================
//
// POR QUE EXISTE. La aplicacion abria enlaces con `<a target="_blank">`. En un
// navegador eso funciona; dentro del webview de Tauri **no hace nada**: no hay
// navegador que abra una pestana nueva, asi que el clic se perdia en silencio.
// En la aplicacion instalada ningun enlace externo funcionaba —repositorio,
// fuentes de licencias, Hugging Face, explorador de Solana, paginas de wallets,
// soporte por correo—.
//
// COMO SE RESUELVE. Tauri v2 expone `tauri-plugin-opener`; este modulo es el
// unico sitio del frontend que decide como se abre algo hacia fuera. Todos los
// consumidores usan `ExternalLink`, y la guarda `scripts/check-external-links.mjs`
// impide que reaparezcan anchors externos directos.
//
// El binding npm oficial `@tauri-apps/plugin-opener` usa el comando del plugin.
// `isDesktopRuntime()` cubre tanto el puente global de `withGlobalTauri` como el
// puente interno de Tauri, mientras que el navegador normal conserva su fallback
// web. La validacion de esquemas ocurre antes de delegar al sistema.
//
// QUE NO HACE. No abre rutas de archivo, no revela ficheros en el explorador y
// no ejecuta comandos. La capability concede unicamente `opener:allow-open-url`
// sobre la ventana `main`; ampliar esto es una decision de seguridad, no un
// detalle de implementacion.

import { isDesktopRuntime } from "./tauri";
import { openUrl as tauriOpenUrl } from "@tauri-apps/plugin-opener";

/**
 * Esquemas que esta frontera acepta. Todo lo demas se rechaza.
 *
 * `javascript:` y `data:` son vectores de ejecucion si el destino viniera de
 * contenido no controlado; `file:` abriria rutas locales arbitrarias, que es
 * justo la capacidad que la capability NO concede. Un esquema desconocido se
 * rechaza por defecto en vez de delegarse al sistema operativo.
 */
const ESQUEMAS_PERMITIDOS = new Set(["https:", "http:", "mailto:"]);

export class ExternalNavigationError extends Error {
  readonly url: string;
  constructor(message: string, url: string) {
    super(message);
    this.name = "ExternalNavigationError";
    this.url = url;
  }
}


/**
 * `true` si `url` es un destino externo que esta frontera acepta abrir.
 *
 * Una ruta relativa (`/legal/...`, `#seccion`, `./algo`) NO es externa: no se
 * valida aqui y no debe pasar por el opener. `esExterno` es lo que usan los
 * componentes para decidir si delegan o dejan que el enlace navegue solo.
 */
export function esExterno(url: string): boolean {
  if (!url) return false;
  // Sin base, una ruta relativa lanza y eso es exactamente la respuesta: no es
  // absoluta, luego no es externa.
  try {
    const parsed = new URL(url);
    return ESQUEMAS_PERMITIDOS.has(parsed.protocol);
  } catch {
    return false;
  }
}

/** Normaliza y valida; lanza `ExternalNavigationError` si no es admisible. */
function validar(url: string): URL {
  if (typeof url !== "string" || url.trim() === "") {
    throw new ExternalNavigationError("URL vacia", String(url));
  }
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new ExternalNavigationError(
      "No es una URL absoluta. Las rutas internas no pasan por esta frontera.",
      url,
    );
  }
  if (!ESQUEMAS_PERMITIDOS.has(parsed.protocol)) {
    throw new ExternalNavigationError(
      `Esquema no permitido: ${parsed.protocol}. Solo https:, http: y mailto:.`,
      url,
    );
  }
  return parsed;
}

/**
 * Abre `url` fuera de la aplicacion.
 *
 * Dentro de Tauri delega en el plugin opener; en un navegador normal conserva
 * `window.open`. Los errores se propagan: un enlace que no abre debe poder
 * decirlo, no desaparecer —que es precisamente el fallo que este modulo repara—.
 */
export async function openExternal(url: string): Promise<void> {
  const parsed = validar(url);
  const destino = parsed.toString();

  if (isDesktopRuntime()) {
    // El binding oficial usa el comando del plugin y funciona tanto con el
    // puente global como con __TAURI_INTERNALS__. La validacion anterior es la
    // unica frontera que decide que entrada puede llegar a este comando.
    try {
      await tauriOpenUrl(destino);
      return;
    } catch (causa) {
      throw new ExternalNavigationError(
        "Tauri esta presente pero el plugin opener no responde. Comprueba que "
        + "`tauri_plugin_opener::init()` esta registrado y que la capability "
        + `concede opener:allow-open-url. Causa: ${String(causa)}`,
        destino,
      );
    }
  }

  if (typeof window === "undefined") {
    throw new ExternalNavigationError("Sin `window`: no hay donde abrir.", destino);
  }
  const abierta = window.open(destino, "_blank", "noopener,noreferrer");
  // `window.open` devuelve null si un bloqueador lo impidio. Decirlo es mejor
  // que fingir que se abrio.
  if (abierta === null && parsed.protocol !== "mailto:") {
    throw new ExternalNavigationError(
      "El navegador bloqueo la apertura de la ventana.",
      destino,
    );
  }
}
