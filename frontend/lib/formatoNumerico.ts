// =====================================================================
// Formateo de magnitudes que pueden no existir
// =====================================================================
//
// EL FALLO QUE ARREGLA. La pestaña Propiedades reventaba con
//
//     Cannot read properties of null (reading 'toFixed')
//
// por una guarda que parecía correcta y no lo era:
//
//     result.molecular_weight !== undefined ? result.molecular_weight.toFixed(1) : "—"
//
// **`null !== undefined` es `true`.** El backend devuelve `null` en JSON para
// una magnitud que no pudo calcular —no `undefined`— así que el valor pasaba la
// guarda y `.toFixed()` explotaba. La pestaña entera dejaba de pintarse por una
// propiedad ausente, que es precisamente el caso normal en una evaluación
// parcial.
//
// La forma correcta con encadenamiento opcional (`result.log_p?.toFixed(2)`)
// convivía en el mismo archivo, cuatro líneas más abajo. Dos maneras de hacer lo
// mismo, una rota, y ninguna prueba que las distinguiera.
//
// Este módulo existe para que no haya dos maneras. `typeof === "number"` cubre
// `null`, `undefined` y cualquier cosa que llegue de un JSON sin tipar;
// `Number.isFinite` cubre además `NaN` e `Infinity`, que un cálculo científico
// fallido sí produce y que `toFixed` formatearía como "NaN" en pantalla.

/** El guion largo con el que la interfaz representa «no disponible». */
export const SIN_DATO = "—";

/**
 * Formatea un número con decimales fijos, o devuelve el guion.
 *
 * @param valor      Lo que llegue: número, `null`, `undefined` o basura.
 * @param decimales  Decimales fijos.
 * @param sufijo     Unidad u otro texto que sólo aparece si hay valor.
 */
export function numeroOGuion(valor: unknown, decimales: number, sufijo = ""): string {
  if (typeof valor !== "number" || !Number.isFinite(valor)) return SIN_DATO;
  return `${valor.toFixed(decimales)}${sufijo}`;
}

/**
 * `true` si la magnitud existe y es utilizable.
 *
 * Para decidir si pintar una barra, un color o una comparación — cosas que con
 * `null` no significan nada y con `0` sí. Por eso no vale un `if (valor)`: un
 * cero legítimo se perdería.
 */
export function hayNumero(valor: unknown): valor is number {
  return typeof valor === "number" && Number.isFinite(valor);
}
