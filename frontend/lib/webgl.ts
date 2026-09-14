// =====================================================================
// Disponibilidad de WebGL, dicha por MolDesign y no por la librería
// =====================================================================
//
// EL FALLO QUE ARREGLA. En una máquina virtual sin aceleración 3D, el visor
// mostraba el mensaje crudo de la librería:
//
//     WebGL does not seem to be available.
//     This can be caused by an outdated browser, graphics card driver issue,
//     or bad weather. Sometimes, just restarting the browser helps.
//
// Ese texto es de Mol*, no nuestro. Habla de navegadores y de «bad weather» a
// alguien que está usando una aplicación de escritorio, no dice qué parte de
// MolDesign sigue funcionando, y deja al investigador sin saber si su análisis
// es válido o si acaba de perder la corrida.
//
// El visor no debe montarse cuando esta comprobación falla: así MolDesign
// sustituye el mensaje interno de la librería por un estado propio que explica
// qué parte del análisis sigue siendo utilizable.
//
// ── POR QUÉ NO BASTA CON «¿HAY CONTEXTO?» ───────────────────────────────────
//
// La versión anterior sólo preguntaba si se podía crear un contexto, y con eso
// respondía sí o no. Entre esos dos extremos hay un tercer estado que es
// justamente el de una VM: **hay contexto, pero lo dibuja la CPU**.
//
// MEDIDO, comparando la misma máquina con y sin aceleración por hardware:
//
//     hardware   ANGLE (NVIDIA … D3D11)          Mol* listo en 1 072 ms
//     software   ANGLE (… SwiftShader driver)    Mol* listo en 1 260 ms
//
// Las dos funcionan, y las dos tienen las extensiones que Mol* necesita
// (`EXT_color_buffer_float`, `OES_texture_float_linear`, draw buffers y
// texturas de profundidad). Así que por software NO hay que bloquear nada: hay
// que decirlo, porque una escena grande sí se va a arrastrar, y dejar que el
// usuario elija el visor ligero si prefiere fluidez.
//
// Lo que sí hace falta para que ese repliegue exista es que el contenedor lo
// autorice: ver `permitir_webgl_por_software` en `src-tauri/src/lib.rs`.

/** Cómo se está dibujando, cuando se puede dibujar. */
export type Aceleracion = "hardware" | "software";

/** Resultado de la comprobación, con el motivo cuando falla. */
export interface EstadoWebGL {
  readonly disponible: boolean;
  /** `null` si está disponible. */
  readonly motivo: string | null;
  /** `null` si no hay contexto o si el equipo no quiere identificarse. */
  readonly aceleracion: Aceleracion | null;
  /** Lo que anuncia el equipo, tal cual. Para diagnóstico, no para decidir. */
  readonly renderer: string | null;
}

/**
 * Nombres con los que se anuncian los rasterizadores por software.
 *
 * Es una lista de reconocimiento, no una regla: si aparece uno nuevo, lo peor
 * que pasa es que se le trate como hardware y el usuario note que va lento sin
 * que se lo hayamos avisado. Nunca al revés — nada se bloquea por estar aquí.
 */
const POR_SOFTWARE = [
  "swiftshader",
  "llvmpipe",
  "softpipe",
  "software adapter",
  "microsoft basic render",
  "basic display adapter",
  "mesa offscreen",
  "gallium, llvmpipe",
];

let cache: EstadoWebGL | null = null;

function clasificar(renderer: string | null): Aceleracion | null {
  if (!renderer) return null;
  const bajo = renderer.toLowerCase();
  return POR_SOFTWARE.some((nombre) => bajo.includes(nombre)) ? "software" : "hardware";
}

/**
 * Comprueba si el equipo puede crear un contexto WebGL, y cómo lo dibuja.
 *
 * Se crea un canvas desechable y se descarta de inmediato: crear el contexto es
 * la ÚNICA forma fiable de saberlo. Preguntar por el navegador o por el driver
 * da falsos positivos —una VM anuncia un navegador moderno y aun así no expone
 * aceleración— y ese es justo el caso que hay que detectar.
 *
 * El resultado se memoriza: la capacidad no cambia dentro de una sesión, y
 * crear contextos WebGL de prueba consume recursos de GPU de verdad.
 */
export function comprobarWebGL(): EstadoWebGL {
  if (cache) return cache;
  if (typeof window === "undefined" || typeof document === "undefined") {
    // En render de servidor no se puede saber. Se responde «disponible» para no
    // pintar una advertencia que quizá no corresponde: el cliente lo corregirá.
    return { disponible: true, motivo: null, aceleracion: null, renderer: null };
  }
  try {
    const canvas = document.createElement("canvas");
    const contexto =
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl");
    if (!contexto) {
      cache = {
        disponible: false,
        aceleracion: null,
        renderer: null,
        motivo:
          "este equipo no expone aceleración 3D por hardware. Es lo habitual en " +
          "una máquina virtual sin GPU virtualizada.",
      };
      return cache;
    }

    const gl = contexto as WebGLRenderingContext;
    let renderer: string | null = null;
    try {
      // `WEBGL_debug_renderer_info` puede no estar: algunos equipos lo ocultan
      // por privacidad. Sin él no se sabe cómo se dibuja, y eso es un estado
      // legítimo —`aceleracion: null`— y no un fallo.
      const info = gl.getExtension("WEBGL_debug_renderer_info");
      if (info) {
        const crudo = gl.getParameter(info.UNMASKED_RENDERER_WEBGL);
        renderer = typeof crudo === "string" ? crudo : null;
      }
    } catch {
      renderer = null;
    }

    // Liberar el contexto de prueba en vez de dejarlo colgando: los navegadores
    // limitan cuántos hay vivos a la vez, y el visor real necesita el suyo.
    const perder = gl.getExtension("WEBGL_lose_context");
    perder?.loseContext();

    cache = {
      disponible: true,
      motivo: null,
      aceleracion: clasificar(renderer),
      renderer,
    };
    return cache;
  } catch (error) {
    cache = {
      disponible: false,
      aceleracion: null,
      renderer: null,
      motivo: `no se pudo crear un contexto WebGL (${String(error).slice(0, 80)}).`,
    };
    return cache;
  }
}

/** Sólo para pruebas: olvida la comprobación memorizada. */
export function reiniciarComprobacionWebGL(): void {
  cache = null;
}
