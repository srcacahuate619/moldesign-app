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

/**
 * 10^(ΔΔG / RT·ln10): la razón que implicaría SI el score fuera una ΔG medida. No
 * lo es y no está validada (SCI-A-037): sirve para justificar dónde caen los
 * cortes de la escala y no se muestra al usuario.
 */
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
  "MARGEN DE SCORE NEGATIVO — la molécula puntúa mejor contra una anti-diana que contra su diana";

/**
 * Los cortes están en 2.73 y 1.36 kcal/mol (lo que serían 100x y 10x SI el score
 * fuera una energía libre medida), y 0 es «indistinguible». SCI-A-037: el rótulo
 * ya no dice «une ~100x más fuerte»: una diferencia de scores de Vina entre
 * receptores distintos no es una razón de afinidades validada.
 *
 * Ninguna etiqueta dice «seguro». Un margen in silico con ±2 kcal/mol de
 * incertidumbre no autoriza esa palabra, y menos en el panel de anti-dianas.
 */
export const ESCALA_DE_MARGEN: ReadonlyArray<readonly [number, string]> = [
  [2.73, "MARGEN DE SCORE AMPLIO — la diana principal puntúa al menos 2.73 kcal/mol mejor que la peor anti-diana"],
  [1.36, "MARGEN DE SCORE MODERADO — entre 1.36 y 2.73 kcal/mol a favor de la diana principal"],
  [0.41, "MARGEN DE SCORE ESTRECHO — menos de 1.36 kcal/mol, dentro de la dispersión del score de Vina"],
  [0.0, "SIN MARGEN DE SCORE — scores indistinguibles entre diana y anti-diana"],
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

/**
 * La clave de traducción de un veredicto conocido (los guardados son el texto
 * castellano canónico); `null` si no se conoce y hay que mostrarlo tal cual.
 */
/** Los rótulos anteriores a SCI-A-037, que siguen guardados en corridas viejas. */
const VEREDICTOS_ANTERIORES: ReadonlyArray<readonly [string, string]> = [
  ["MARGEN AMPLIO — la diana principal une ~100x más fuerte que la peor anti-diana", "pr_sel_margen_amplio"],
  ["MARGEN MODERADO — unas 10x a favor de la diana principal", "pr_sel_margen_moderado"],
  ["MARGEN ESTRECHO — menos de 10x; el orden puede invertirse dentro del error del método", "pr_sel_margen_estrecho"],
  ["SIN MARGEN — afinidades indistinguibles entre diana y anti-diana", "pr_sel_margen_sin"],
  ["MARGEN NEGATIVO — la molécula une más fuerte a una anti-diana que a su diana", "pr_sel_margen_invertido"],
];

export function claveDeVeredicto(veredicto: string): string | null {
  const anterior = VEREDICTOS_ANTERIORES.find(([texto]) => texto === veredicto);
  if (anterior) return anterior[1];
  const indice = ESCALA_DE_MARGEN.findIndex(([, texto]) => texto === veredicto);
  if (indice >= 0) return ["pr_sel_margen_amplio", "pr_sel_margen_moderado", "pr_sel_margen_estrecho", "pr_sel_margen_sin"][indice];
  if (veredicto === VEREDICTO_INVERTIDO) return "pr_sel_margen_invertido";
  if (veredicto === VEREDICTO_SIN_DATOS) return "pr_sel_margen_sin_datos";
  return null;
}
