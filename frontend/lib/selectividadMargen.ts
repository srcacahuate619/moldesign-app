// =====================================================================
// El margen de selectividad: ΔΔG, y UNA sola escala
// =====================================================================
//
// Espejo exacto de `backend/services/docking/selectividad_margen.py`. Hay una
// prueba que compara los umbrales de los dos archivos, porque lo que se está
// arreglando es justamente que existían por duplicado y no coincidían:
//
//     backend  (selectivity_verdict)   > 10   > 3    > 1.5  > 1.0
//     frontend (ProSelectivityPanel)   > 1.8  > 1.2  > 0.9
//
// Un cociente de 2.0 se guardaba en la base y en el dossier como «MODERADAMENTE
// SELECTIVO» mientras la pantalla decía «ALTAMENTE SELECTIVO» para la MISMA
// corrida. Quien exportaba el dossier leía un veredicto y quien miraba el panel
// leía otro.
//
// ─── Y el cociente en sí tampoco servía ─────────────────────────────────
//
// `ratio = ΔG_on / ΔG_off` divide dos energías libres. Eso no es una razón de
// selectividad: como ΔG = −RT·ln K_d, el cociente es ln K_on / ln K_off, el
// logaritmo de una constante de disociación en la base de la otra. No describe
// nada.
//
//     ΔG_on = −10.0, ΔG_off = −5.0   ->  cociente 2.00   ->  ΔΔG = 5.0 kcal/mol
//     ΔG_on =  −6.0, ΔG_off = −3.0   ->  cociente 2.00   ->  ΔΔG = 3.0 kcal/mol
//
// Mismo número, mismo veredicto, y márgenes reales que se diferencian por un
// factor de treinta.
//
// La magnitud correcta es la diferencia: ΔΔG = ΔG_off − ΔG_on, en kcal/mol.

/** ln(10)·R·T a 298.15 K, en kcal/mol. Convierte ΔΔG en órdenes de magnitud. */
export const KCAL_POR_DECADA = 1.3633;

/** Dispersión típica del score de Vina frente a afinidad medida (kcal/mol). */
export const INCERTIDUMBRE_VINA_KCAL = 2.0;

/** Cuántas veces más fuerte es la unión a la diana principal. */
export function factorDeSelectividad(deltaDeltaG: number): number {
  return 10 ** (deltaDeltaG / KCAL_POR_DECADA);
}

/** ΔΔG = ΔG_off − ΔG_on. Positivo = la diana principal une más fuerte. */
export function margenDeSelectividad(
  afinidadOn: number | null | undefined,
  afinidadPeorOff: number | null | undefined,
): number | null {
  if (afinidadOn == null || afinidadPeorOff == null) return null;
  return Number((afinidadPeorOff - afinidadOn).toFixed(2));
}

export const VEREDICTO_SIN_DATOS = "Sin datos suficientes";
export const VEREDICTO_INVERTIDO =
  "MARGEN NEGATIVO — la molécula une más fuerte a una anti-diana que a su diana";

/**
 * Los cortes están en órdenes de magnitud redondos, no elegidos a ojo:
 * 2.73 kcal/mol son 100x, 1.36 son 10x, y 0 es «indistinguible».
 *
 * Ninguna etiqueta dice «seguro». Un margen in silico con ±2 kcal/mol de
 * incertidumbre no autoriza esa palabra, y menos en el panel de anti-dianas.
 */
export const ESCALA_DE_MARGEN: ReadonlyArray<readonly [number, string]> = [
  [2.73, "MARGEN AMPLIO — la diana principal une ~100x más fuerte que la peor anti-diana"],
  [1.36, "MARGEN MODERADO — unas 10x a favor de la diana principal"],
  [0.41, "MARGEN ESTRECHO — menos de 10x; el orden puede invertirse dentro del error del método"],
  [0.0, "SIN MARGEN — afinidades indistinguibles entre diana y anti-diana"],
];

export function veredictoDeMargen(deltaDeltaG: number | null | undefined): string {
  if (deltaDeltaG == null) return VEREDICTO_SIN_DATOS;
  if (deltaDeltaG < 0) return VEREDICTO_INVERTIDO;
  for (const [minimo, veredicto] of ESCALA_DE_MARGEN) {
    if (deltaDeltaG >= minimo) return veredicto;
  }
  return VEREDICTO_SIN_DATOS;
}

/** El color sale de la MISMA escala, no de umbrales propios. */
export function colorDeMargen(deltaDeltaG: number | null | undefined): string {
  if (deltaDeltaG == null) return "#64748b";
  if (deltaDeltaG < 0) return "#ef4444";
  if (deltaDeltaG >= 2.73) return "#10b981";
  if (deltaDeltaG >= 1.36) return "#34d399";
  if (deltaDeltaG >= 0.41) return "#f59e0b";
  return "#ef4444";
}

/** El factor implicado, como intervalo. Un punto sería pseudoprecisión. */
export function bandaDeFactor(deltaDeltaG: number): { min: number; max: number } {
  return {
    min: factorDeSelectividad(deltaDeltaG - INCERTIDUMBRE_VINA_KCAL),
    max: factorDeSelectividad(deltaDeltaG + INCERTIDUMBRE_VINA_KCAL),
  };
}

/** «120x», «1.4x», «0.3x» — sin decimales cuando no los sostiene. */
export function formatearFactor(factor: number): string {
  if (factor >= 100) return `${Math.round(factor).toLocaleString("es")}x`;
  if (factor >= 10) return `${factor.toFixed(0)}x`;
  return `${factor.toFixed(1)}x`;
}
