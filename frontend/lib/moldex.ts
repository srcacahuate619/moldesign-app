// =====================================================================
// MOLDEX-INT-007 — contrato tipado del catálogo Moldex
// =====================================================================
//
// `GET /moldex` devolvía `dict[str, Any]` en el backend y `Promise<any>` aquí,
// así que ninguna de las dos puntas obligaba a la otra a nada. Una ficha no
// podía decir de qué corrida salió su número, y por eso ni el sello
// (MOLDEX-SCI-001) ni la comparación (MOLDEX-SCI-004) podían comprobar contra
// qué se estaban midiendo.
//
// Nota de contrato: `/moldex` no declara `response_model` en FastAPI, así que
// no aparece en `docs/api/openapi-current.json` y la guarda automática de
// contrato (`evaluationResultContract.test.ts`) no lo cubre. Mientras siga así,
// este archivo y sus pruebas son la única definición del contrato.

/** Identidad y condiciones de la corrida que produjo las métricas de la ficha. */
export type MoldexProvenance = {
  /** Identidad durable de la corrida. `null` en evaluaciones anteriores al registro. */
  task_id: string | null;
  /** SHA-256 del receptor preparado. Decide si dos fichas son comparables. */
  receptor_sha256: string | null;
  engine_version: string | null;
  random_seed: number | null;
  docking_protocol: Record<string, unknown> | null;
};

export type MoldexTarget = {
  pdb_id: string;
  name: string | null;
  family: string | null;
  hotspots: Array<{ name?: string; [k: string]: unknown }>;
  spearman_rho: number | null;
};

/**
 * Métricas de la ficha. Todas son opcionales de verdad: RDKit puede no calcular
 * un descriptor y el pipeline puede no producir un score. Un `null` aquí
 * significa «no se midió», y no debe convertirse en 0 en ninguna vista.
 */
export type MoldexMetrics = {
  /** kcal/mol. Más negativo = mejor. */
  affinity: number | null;
  log_p: number | null;
  /** Daltons. */
  mw: number | null;
  /** Å². */
  tpsa: number | null;
  /** Escala 0-100. */
  score: number | null;
  /** RTMScore. Sólo en bases antiguas: la app de escritorio nunca lo produce. No se pinta. */
  gnn_score: number | null;
  /**
   * Salida sigmoide de la CL-GNN, en (0, 1), sin calibrar para los pesos que
   * viajan y con peso 0 en el ranking. Nulo si no corrió o falló. Opcional
   * porque un backend anterior a `bb788f5` no lo envía.
   */
  clgnn_score?: number | null;
  lipinski_pass: boolean | null;
  veber_pass: boolean | null;
};

export type MoldexMolecule = {
  id: string;
  name: string;
  smiles: string;
  smiles_hash: string;
  /** Fecha de creación de la molécula. */
  created_at: string;
  /** Fecha de la evaluación. Distinta de `created_at`. */
  evaluated_at: string | null;
  target: MoldexTarget;
  metrics: MoldexMetrics;
  provenance: MoldexProvenance;
  scientific_warnings: string[];
  hotspots_hit: string[];
  blockchain: MoldexSeal;
};

/**
 * Estado del sello de certificación.
 *
 * MOLDEX-SCI-001: el sello vive en la misma fila mutable que las métricas, así
 * que una reevaluación posterior lo deja describiendo una corrida que la ficha
 * ya no muestra.
 */
export type MoldexSeal = {
  certified: boolean;
  tx_signature: string | null;
  /** Corrida que se certificó. `null` en sellos anteriores al registro. */
  certified_task_id: string | null;
  /** Score que quedó atestiguado en la cadena. */
  certified_total_score: number | null;
  /**
   * `true` el sello describe la corrida mostrada; `false` la molécula se
   * reevaluó después de certificarla; `null` indeterminado — no hay sello, o es
   * anterior al registro y no se sabe qué cubrió. Nunca se supone que coincide.
   */
  matches_current_run: boolean | null;
};

/** Cómo debe leerse un sello en la interfaz. */
export type LecturaDelSello =
  | "sin-sello"
  | "vigente"
  | "corrida-anterior"
  | "indeterminado";

/**
 * Traduce el sello a la única afirmación que la ficha puede sostener.
 *
 * La insignia sólo puede decir «certificado» a secas cuando el sello describe la
 * corrida que se está mostrando. En los otros dos casos afirmarlo sería
 * respaldar cifras que la cadena no atestiguó.
 */
export function leerSello(sello: MoldexSeal | undefined | null): LecturaDelSello {
  if (!sello?.certified) return "sin-sello";
  if (sello.matches_current_run === true) return "vigente";
  if (sello.matches_current_run === false) return "corrida-anterior";
  return "indeterminado";
}

export type MoldexCatalog = {
  count: number;
  total: number;
  limit: number | null;
  offset: number;
  has_next: boolean;
  results: MoldexMolecule[];
};

/**
 * Marca temporal por la que se ordena «RECIENTES».
 *
 * La fecha que le importa al investigador es la de la evaluación, no la del día
 * en que dibujó la molécula. `evaluated_at` es `null` en corridas heredadas: en
 * ese caso se cae a `created_at` en vez de mandarlas al fondo.
 */
export function marcaDeOrden(molecula: Pick<MoldexMolecule, "evaluated_at" | "created_at">): number {
  const bruto = molecula.evaluated_at ?? molecula.created_at;
  if (!bruto) return 0;
  const t = new Date(bruto).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/** Comparador descendente por fecha de evaluación. */
export function porEvaluacionReciente(
  a: Pick<MoldexMolecule, "evaluated_at" | "created_at">,
  b: Pick<MoldexMolecule, "evaluated_at" | "created_at">,
): number {
  return marcaDeOrden(b) - marcaDeOrden(a);
}

// =====================================================================
// MOLDEX-SCI-004 — compatibilidad antes de comparar
// =====================================================================

export type VeredictoComparacion = {
  comparable: boolean;
  /** Por qué no lo son. Vacío si lo son. Se acumulan todos, no sólo el primero. */
  motivos: string[];
};

/** Compara dos protocolos de docking por valor, campo a campo. */
function mismoProtocolo(
  a: Record<string, unknown> | null,
  b: Record<string, unknown> | null,
): boolean {
  if (a === null || b === null) return false;
  const clavesA = Object.keys(a).sort();
  const clavesB = Object.keys(b).sort();
  if (clavesA.length !== clavesB.length) return false;
  if (clavesA.some((k, i) => k !== clavesB[i])) return false;
  return clavesA.every((k) => Object.is(a[k], b[k]));
}

/**
 * Decide si dos fichas pueden restarse.
 *
 * Un score de docking sólo significa algo relativo al receptor y al protocolo
 * que lo produjeron. Comparar a través de receptores distintos —o de una
 * exhaustividad distinta, o de un docking rígido contra uno flexible— produce
 * una diferencia que parece una mejora y no lo es: la penalización torsional de
 * un ligando flexible basta para invertir el orden de dos candidatos.
 *
 * Cuando la procedencia no consta (corridas anteriores al registro) el
 * veredicto es **no comparable**. No se supone compatibilidad: no saber contra
 * qué se midió es precisamente el motivo para no restar.
 */
export function compararMoleculas(
  a: MoldexMolecule,
  b: MoldexMolecule,
): VeredictoComparacion {
  const motivos: string[] = [];

  if (a.target?.pdb_id !== b.target?.pdb_id) {
    motivos.push(
      `Son targets distintos (${a.target?.pdb_id ?? "sin target"} y ${b.target?.pdb_id ?? "sin target"}): sus afinidades no están en la misma escala.`,
    );
  }

  const hashA = a.provenance?.receptor_sha256 ?? null;
  const hashB = b.provenance?.receptor_sha256 ?? null;

  if (hashA === null || hashB === null) {
    motivos.push(
      "No consta el receptor de al menos una de las dos corridas, así que no puede comprobarse que se midieran contra la misma estructura.",
    );
  } else if (hashA !== hashB) {
    motivos.push(
      "El receptor preparado no es el mismo: cambia la caja, la protonación o la variante, y con ellas la escala del score.",
    );
  }

  const protoA = a.provenance?.docking_protocol ?? null;
  const protoB = b.provenance?.docking_protocol ?? null;

  if (protoA === null || protoB === null) {
    motivos.push(
      "No consta el protocolo de docking de al menos una de las dos corridas.",
    );
  } else if (!mismoProtocolo(protoA, protoB)) {
    motivos.push(
      "El protocolo de docking difiere (motor, exhaustividad, número de poses o conformaciones): los scores no son directamente restables.",
    );
  }

  return { comparable: motivos.length === 0, motivos };
}

// =====================================================================
// MOLDEX-SCI-003 — semántica nula en la tabla comparativa
// =====================================================================

export type FilaComparativa = {
  etiqueta: string;
  valorA: number | null;
  valorB: number | null;
  /** `null` cuando falta cualquiera de los dos lados. Nunca 0 por defecto. */
  delta: number | null;
  textoA: string;
  textoB: string;
  textoDelta: string;
};

const AUSENTE = "—";

function texto(valor: number | null): string {
  return valor === null ? AUSENTE : valor.toFixed(2);
}

/**
 * Construye una fila de la tabla comparativa conservando el faltante.
 *
 * Antes se hacía `valor ?? 0` y se restaba: una molécula sin logP calculable se
 * comparaba como si su logP fuera 0, y la diferencia contra la otra se pintaba
 * en verde o rojo. Un cero medido y un cero inventado se veían idénticos.
 */
export function filaComparativa(
  etiqueta: string,
  valorA: number | null | undefined,
  valorB: number | null | undefined,
): FilaComparativa {
  const a = valorA ?? null;
  const b = valorB ?? null;
  const delta = a === null || b === null ? null : b - a;

  return {
    etiqueta,
    valorA: a,
    valorB: b,
    delta,
    textoA: texto(a),
    textoB: texto(b),
    textoDelta:
      delta === null ? AUSENTE : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`,
  };
}

// =====================================================================
// MOLDEX-UX-008 — qué afirma la ficha, y sobre qué red
// =====================================================================

/**
 * Lo único que un sello acredita.
 *
 * Es el mismo alcance que ya declaraban `CertificationModal` y el PDF del
 * dossier. Vivía sólo ahí: la ficha, que es lo que el investigador tiene
 * delante todo el tiempo, mostraba una insignia y un encabezado «Evidencia
 * Digital» sin decir de qué es evidencia.
 */
export const ALCANCE_DEL_SELLO =
  "El registro acredita integridad y fecha de la revisión publicada. No demuestra " +
  "que la pose sea válida, ni que la conclusión científica sea correcta, ni " +
  "sustituye evidencia experimental.";

/**
 * Si la red del sello es de pruebas.
 *
 * Una red de desarrollo puede reiniciarse y su historial no es un registro
 * duradero. Ante una red desconocida se responde `true`: no saber dónde se
 * selló no puede leerse como «se selló en producción».
 */
export function esRedDePruebas(red: string | null | undefined): boolean {
  if (!red) return true;
  const normalizada = red.trim().toLowerCase();
  return normalizada !== "mainnet" && normalizada !== "mainnet-beta";
}

/** Enlace al explorador, con la red real en vez de un `cluster` fijo. */
export function urlDelExplorador(
  firma: string,
  red: string | null | undefined,
): string {
  const base = `https://explorer.solana.com/tx/${encodeURIComponent(firma)}`;
  if (!red) return base;
  const normalizada = red.trim().toLowerCase();
  if (normalizada === "mainnet" || normalizada === "mainnet-beta") return base;
  return `${base}?cluster=${encodeURIComponent(normalizada)}`;
}

/**
 * Comparador por score, con los faltantes siempre al final.
 *
 * MOLDEX-SCI-014. El orden usaba `(b.score || 0) - (a.score || 0)`, que trata
 * un score ausente como cero: en descendente lo hunde al fondo como si fuera el
 * peor, y en ascendente lo asciende a la cabeza como si fuera el mejor. No
 * tener score no es tener un score malo ni bueno — es no estar en la escala.
 *
 * El cero **medido** sí es un score válido y participa del orden con normalidad.
 */
export function porScore(
  direccion: "asc" | "desc",
): (a: Pick<MoldexMolecule, "metrics">, b: Pick<MoldexMolecule, "metrics">) => number {
  return (a, b) => {
    const sa = a.metrics?.score ?? null;
    const sb = b.metrics?.score ?? null;

    if (sa === null && sb === null) return 0;
    if (sa === null) return 1;
    if (sb === null) return -1;

    return direccion === "desc" ? sb - sa : sa - sb;
  };
}

/**
 * Cómo se enseña la CL-GNN en la ficha de Moldex.
 *
 * Es la salida sigmoide de un modelo **sin calibrar** para los pesos que viajan,
 * y pesa 0 en el ranking (canal entre sesiones, B→F-003). Por eso:
 * - dos decimales y nunca como porcentaje: un «74 %» se leería como una
 *   probabilidad calibrada, y no lo es;
 * - la condición va pegada al número («no pesa en el ranking»);
 * - un nulo es que no corrió o falló: se pinta «—» y se dice, nunca como cero.
 *
 * Devuelve la clave de la condición, no el texto: la traduce quien pinta.
 */
export function presentarClgnn(
  valor: number | null | undefined,
): { valor: string; condicion: "mx_clgnn_no_pesa" | "mx_clgnn_no_disponible" } {
  if (valor == null || !Number.isFinite(valor)) {
    return { valor: "—", condicion: "mx_clgnn_no_disponible" };
  }
  return { valor: valor.toFixed(2), condicion: "mx_clgnn_no_pesa" };
}
