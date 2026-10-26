import type { Target } from "./api";
import { normalizarAvisos } from "./avisos";

/** Sólo los mensajes de los avisos, en el orden en que llegaron. */
const textosDeAvisos = (valores: unknown): string[] =>
  normalizarAvisos(valores).map((aviso) => aviso.mensaje);
import type { EvaluationResult, ValidationResult } from "./types";

type Translate = (key: string, values?: Record<string, string | number>) => string;

export type EvidenceStatus = "ready" | "review" | "incomplete";
export type CheckStatus = "available" | "review" | "missing" | "not_evaluated";
export type NextActionStatus = "proceed" | "review" | "abstain";

export interface EvidenceDimension {
  id: "system" | "docking" | "sampling" | "reproducibility" | "physical" | "model" | "physicochemical" | "selectivity";
  label: string;
  status: CheckStatus;
  statusLabel: string;
  detail: string;
}

export interface ReadinessCheck {
  id: "ligand" | "receptor" | "grid" | "hotspots";
  label: string;
  detail: string;
  status: CheckStatus;
}

export interface EvaluationReadiness {
  status: EvidenceStatus;
  label: string;
  summary: string;
  canRun: boolean;
  checks: ReadinessCheck[];
}

export interface EvaluationEvidence {
  status: EvidenceStatus;
  label: string;
  summary: string;
  poseCount: number;
  topPoseAffinity: number | null;
  poseGap: number | null;
  nearTieCount: number;
  /** Conformaciones generadas según el protocolo sellado; `null` si no lo registra (SCI-A-023). */
  conformersGenerated: number | null;
  reproducibility: {
    availableCount: number;
    totalCount: 3;
    vinaVersion: string | null;
    randomSeed: number | null;
    parsingSource: string | null;
    /** Elementos que la corrida registró para poder reconstruirse (SOL-06). */
    reconstruction: {
      presentCount: number;
      totalCount: number;
      missing: string[];
      /** Siempre `false` aquí: la demuestra una prueba de transferencia, no la corrida. */
      demonstrated: false;
    };
  };
  modelContext: {
    engine: string | null;
    model: string | null;
    inDomain: boolean | null;
    fallbackReason: string | null;
  };
  targetReadiness: "listo" | "revisar" | "sin_datos";
  physicalValidity: {
    status: "passed" | "review" | "failed" | "not_evaluated";
    label: string;
    detail: string;
  };
  dimensions: EvidenceDimension[];
  assumptions: string[];
  uncertainties: string[];
  nextAction: {
    status: NextActionStatus;
    label: string;
    detail: string;
  };
  warnings: string[];
}

/** Nombre legible del modelo de rescoring; el motor de docking no va aquí. */
const MODELO_LEGIBLE: Record<string, string> = {
  family: "modelo de familia",
  universal: "modelo universal",
};

function hasGrid(target: Target | null): boolean {
  if (!target) return false;
  if (typeof target.grid_calibrated === "boolean") return target.grid_calibrated;
  return [
    target.grid_center_x,
    target.grid_center_y,
    target.grid_center_z,
    target.grid_size_x,
    target.grid_size_y,
    target.grid_size_z,
  ].every((value) => value != null && Number.isFinite(Number(value)));
}

export function resolveTargetReadiness(target: Target | null): "listo" | "revisar" | "sin_datos" {
  if (!target) return "sin_datos";
  if (target.calibration_status) return target.calibration_status;

  const prepared = target.is_prepared === true;
  const gridReady = hasGrid(target);
  const hotspotCount = target.hotspot_count ?? target.hotspots?.length ?? 0;
  const isManual = target.is_private === true || target.pdb_id.toUpperCase().startsWith("USR_");

  if (prepared && gridReady && (hotspotCount >= 5 || isManual)) return "listo";
  if (prepared && gridReady && hotspotCount > 0) return "revisar";
  return "sin_datos";
}

export function deriveEvaluationReadiness(
  smiles: string,
  target: Target | null,
  validation?: ValidationResult | null,
): EvaluationReadiness {
  const normalizedSmiles = smiles.trim();
  const targetStatus = resolveTargetReadiness(target);
  const gridReady = hasGrid(target);
  const hotspotCount = target?.hotspot_count ?? target?.hotspots?.length ?? 0;

  const ligandStatus: CheckStatus = !normalizedSmiles
    ? "missing"
    : validation?.is_valid === false
      ? "review"
      : "available";

  const checks: ReadinessCheck[] = [
    {
      id: "ligand",
      label: "Ligando",
      status: ligandStatus,
      detail: !normalizedSmiles
        ? "Falta una estructura SMILES."
        : validation?.is_valid === false
          ? "La validación química reportó errores."
          : validation?.is_valid === true
            ? "SMILES validado y canonicalizado."
            : "SMILES presente; se validará al ejecutar.",
    },
    {
      id: "receptor",
      label: "Receptor",
      status: !target ? "missing" : targetStatus === "listo" ? "available" : "review",
      detail: !target
        ? "Selecciona un receptor."
        : target.is_prepared === false
          ? "El receptor no está marcado como preparado."
          : `${target.pdb_id} · preparación ${targetStatus.replace("_", " ")}.`,
    },
    {
      id: "grid",
      label: "Caja de búsqueda",
      status: gridReady ? "available" : target ? "review" : "missing",
      detail: gridReady ? "Centro y dimensiones disponibles." : "Falta una caja calibrada completa.",
    },
    {
      id: "hotspots",
      label: "Hotspots",
      status: hotspotCount >= 5 ? "available" : hotspotCount > 0 ? "review" : "missing",
      detail: hotspotCount > 0
        ? `${hotspotCount} residuo${hotspotCount === 1 ? "" : "s"} de referencia.`
        : "Sin residuos de referencia registrados.",
    },
  ];

  const canRun = Boolean(normalizedSmiles && target && validation?.is_valid !== false);
  const hasMissing = checks.some((check) => check.status === "missing");
  const hasReview = checks.some((check) => check.status === "review");
  const status: EvidenceStatus = !canRun || hasMissing ? "incomplete" : hasReview ? "review" : "ready";

  return {
    status,
    canRun,
    label: status === "ready" ? "Listo para evaluar" : status === "review" ? "Ejecutable con revisión" : "Configuración incompleta",
    summary:
      status === "ready"
        ? "El sistema tiene ligando, receptor, grid y referencias estructurales para iniciar el pipeline."
        : status === "review"
          ? "La evaluación puede ejecutarse, pero el dossier deberá conservar estas reservas."
          : "Completa el ligando y el receptor antes de iniciar la evaluación.",
    checks,
  };
}

// ── Reproducibilidad (SOL-06) ───────────────────────────────────────
//
// Antes bastaban tres metadatos —versión del motor, semilla y parser— para
// rotular la fila «Completa» y, con ella, para que el resumen dijera que la
// corrida conserva «parámetros suficientes para reproducción técnica». Un
// resultado sin caja, sin hashes ni preparación recibía la misma etiqueta.
//
// Tres escalones, que no se confunden:
//   1. trazas mínimas (motor, semilla, parser);
//   2. elementos de reconstrucción REGISTRADOS por la corrida (caja de búsqueda efectiva,
//      protocolo de búsqueda, hash del receptor, hashes de entrada y de salida
//      del ligando, preparación del ligando, versión de la aplicación);
//   3. reconstrucción DEMOSTRADA: que un tercero reproduzca el paquete. Esta
//      fila nunca puede afirmarla —sólo una prueba de transferencia (FEP-06)—,
//      así que dice «no demostrada» siempre.
//
// Espejo de `services/blockchain/evidence_summary.py::_reproducibilidad`.
const TRAZAS_MINIMAS = 3;

const lleno = (valor: unknown): boolean =>
  valor != null && valor !== "" && !(Array.isArray(valor) && valor.length === 0);

const terna = (valor: unknown): boolean => Array.isArray(valor) && valor.length === 3;

const ELEMENTOS_DE_RECONSTRUCCION: readonly {
  readonly etiqueta: string;
  readonly presente: (resultado: EvaluationResult, procedencia: Record<string, unknown>) => boolean;
}[] = [
  {
    etiqueta: "caja de búsqueda efectiva",
    presente: (_r, p) => terna(p.box_center) && terna(p.box_size),
  },
  {
    etiqueta: "protocolo de búsqueda",
    presente: (r) =>
      r.docking_protocol?.exhaustiveness != null && r.docking_protocol?.num_poses != null,
  },
  {
    etiqueta: "hash del receptor",
    presente: (r, p) => lleno(p.receptor_sha256) || lleno(r.receptor_sha256),
  },
  {
    etiqueta: "hashes de entrada del ligando",
    presente: (_r, p) => lleno(p.ligand_input_sha256) && lleno(p.ligand_pdbqt_sha256),
  },
  {
    etiqueta: "hashes de salida (poses y registro)",
    presente: (_r, p) => lleno(p.poses_sha256) && lleno(p.log_sha256),
  },
  {
    etiqueta: "preparación del ligando",
    presente: (r) =>
      lleno(r.ligand_state?.smiles_acoplado) && r.ligand_state?.protonacion != null,
  },
  {
    etiqueta: "versión de la aplicación",
    presente: (_r, p) => lleno(p.app_version),
  },
];

/**
 * Qué dice el registro de la corrida del ensemble y de las réplicas (SCI-A-023).
 *
 * Se escribía siempre «No se registraron réplicas ni ensemble», también cuando el
 * protocolo sellado registra un ensemble. Espejo de `frase_de_muestreo` en
 * `services/blockchain/evidence_summary.py`.
 */
export function conformacionesDelMuestreo(result: Pick<EvaluationResult, "docking_protocol">): number | null {
  const generadas = result.docking_protocol?.conformers_generated;
  return typeof generadas === "number" && Number.isInteger(generadas) ? generadas : null;
}

export function fraseDeMuestreo(generadas: number | null): string {
  if (generadas == null) return "El protocolo no informa si hubo ensemble; no se registraron réplicas.";
  if (generadas > 1) return `Las poses salen de un ensemble de ${generadas} conformaciones; no se registraron réplicas.`;
  return "Confórmero único; no se registraron réplicas.";
}

/** La misma frase, con el catálogo de la interfaz. */
export function fraseDeMuestreoTraducida(generadas: number | null, t: Translate): string {
  if (generadas == null) return t("pr_ev_sampling_unknown");
  if (generadas > 1) return t("pr_ev_sampling_ensemble", { count: generadas });
  return t("pr_ev_sampling_single");
}

export function deriveEvaluationEvidence(
  result: EvaluationResult,
  target: Target | null,
  translate?: Translate,
): EvaluationEvidence {
  const poses = (result.docking_poses ?? [])
    .filter((pose) => Number.isFinite(pose.affinity))
    .slice()
    .sort((a, b) => a.affinity - b.affinity);
  const topPoseAffinity = poses[0]?.affinity ?? null;
  const poseGap = poses.length > 1 ? Number((poses[1].affinity - poses[0].affinity).toFixed(3)) : null;
  const nearTieCount = topPoseAffinity == null
    ? 0
    : poses.filter((pose) => pose.affinity - topPoseAffinity <= 1).length;

  const vinaVersion = result.vina_version ?? null;
  const randomSeed = result.vina_random_seed ?? null;
  const parsingSource = result.parsing_source ?? null;
  const availableCount = [vinaVersion, randomSeed, parsingSource].filter((value) => value != null && value !== "").length;
  const procedenciaEjecutada = result.docking_protocol?.execution_provenance ?? {};
  const elementosFaltantes = ELEMENTOS_DE_RECONSTRUCCION
    .filter((elemento) => !elemento.presente(result, procedenciaEjecutada))
    .map((elemento) => elemento.etiqueta);
  const elementosPresentes = ELEMENTOS_DE_RECONSTRUCCION.length - elementosFaltantes.length;
  const reproducibleConRegistro = availableCount === TRAZAS_MINIMAS && elementosFaltantes.length === 0;
  const registrosPresentes = availableCount + elementosPresentes;
  // Aquí los avisos se leen como prosa —van a la lista de incertidumbres—, así
  // que se toma el mensaje. Con la severidad declarada, un aviso ya no es una
  // cadena: `textosDeAvisos` evita que acabe imprimiéndose el objeto entero.
  const warnings = textosDeAvisos(result.scientific_warnings);
  const targetReadiness = resolveTargetReadiness(target);
  const descriptorCount = [
    result.molecular_weight,
    result.log_p,
    result.tpsa,
    result.hbd,
    result.hba,
    result.rotatable_bonds,
    result.qed,
    result.sa_score,
  ].filter((value) => value != null && Number.isFinite(Number(value))).length;
  const selectivityCount = result.selectivity_ran ? (result.anti_target_results ?? []).length : 0;

  // ── Validez física: se LEE el contrato que persiste el backend ──────
  //
  // CORRECCIÓN. Esto miraba `result.pose_validation`, un campo que el backend
  // no ha emitido nunca, y por eso caía SIEMPRE en la rama de abstención con
  // la frase «esta versión no ejecuta un validador geométrico de poses en
  // producción». Desde P0-A esa frase es falsa: el validador corre por pose y
  // deja su veredicto en `structural_evidence`. Una interfaz que declara no
  // evaluado lo que sí se evaluó es peor que una que no lo enseña.
  //
  // `not_evaluated` se conserva para las corridas anteriores a la etapa —donde
  // sigue siendo la respuesta correcta— y describe lo que le pasó al
  // validador, nunca a la molécula.
  const structural = result.structural_evidence ?? null;
  const stage = structural?.stage_status;
  const physicalValidity: EvaluationEvidence["physicalValidity"] =
    stage === "passed" || stage === "failed" || stage === "review"
      ? {
          status: stage,
          label:
            stage === "passed"
              ? "Controles superados"
              : stage === "failed"
                ? "Controles fallidos"
                : "Requiere revisión",
          detail:
            stage === "passed"
              ? `${structural?.poses_evaluated ?? 0} de ${structural?.poses_produced ?? 0} poses recibieron veredicto y ninguna falla los controles de química o geometría.`
              : stage === "failed"
                ? "Al menos la pose principal falla los controles de química o geometría."
                : "La batería no corrió entera sobre todas las poses; «requiere revisión» no es una pose aprobada.",
        }
      : {
          status: "not_evaluated",
          label: "No evaluada",
          detail: structural
            ? `Los controles físicos no llegaron a emitir veredicto (${structural.reason_code ?? "sin código de razón"}). Describe lo que le pasó al validador, no a la molécula.`
            : "Esta corrida es anterior a la etapa de validación física: no se ejecutó, y eso no dice nada sobre las poses.",
        };

  const incomplete = result.affinity_kcal == null || poses.length === 0;
  const needsReview =
    warnings.length > 0 ||
    targetReadiness !== "listo" ||
    result.in_applicability_domain === false ||
    Boolean(result.fallback_reason) ||
    !reproducibleConRegistro ||
    // SOL-05: un control físico fallido o inconcluso es una reserva de la
    // corrida. Antes la cabecera seguía en «Evidencia disponible» con la
    // lista de incertidumbres VACÍA mientras la acción siguiente sí se
    // abstener/pedir revisión: tres respuestas distintas a la misma
    // pregunta. `not_evaluated` no entra: su reserva ya viaja en la lista
    // y una corrida anterior a la etapa de validación no es una reserva
    // nueva.
    physicalValidity.status === "failed" ||
    physicalValidity.status === "review";
  const status: EvidenceStatus = incomplete ? "incomplete" : needsReview ? "review" : "ready";

  const dimensions: EvidenceDimension[] = [
    {
      id: "system",
      label: "Preparación del sistema",
      status: targetReadiness === "listo" ? "available" : targetReadiness === "revisar" ? "review" : "missing",
      statusLabel: targetReadiness === "listo" ? "Documentada" : targetReadiness === "revisar" ? "Revisar" : "Insuficiente",
      detail: targetReadiness === "listo"
        ? "El inventario registra receptor preparado, grid y referencias estructurales."
        : "El inventario no permite confirmar todos los requisitos de preparación.",
    },
    {
      id: "docking",
      label: "Señal de docking",
      status: incomplete ? "missing" : "available",
      statusLabel: incomplete ? "Insuficiente" : "Disponible",
      detail: incomplete
        ? "Faltan poses o afinidad serializada."
        : `${poses.length} poses serializadas; mejor afinidad cruda ${topPoseAffinity?.toFixed(2)} kcal/mol.`,
    },
    {
      id: "sampling",
      label: "Muestreo de poses",
      status: poses.length < 2 ? (poses.length === 0 ? "missing" : "review") : nearTieCount > 1 ? "review" : "available",
      statusLabel: poses.length === 0 ? "Sin evidencia" : poses.length === 1 ? "No comparable" : nearTieCount > 1 ? "Ambiguo" : "Descriptivo",
      detail: poses.length < 2
        ? "No hay suficientes poses para describir separación interna."
        : `${nearTieCount} poses quedan a ≤1 kcal/mol; Δ pose 1–2 ${poseGap?.toFixed(2)} kcal/mol. ${fraseDeMuestreo(conformacionesDelMuestreo(result))}`,
    },
    {
      id: "reproducibility",
      label: "Reproducibilidad técnica",
      status: reproducibleConRegistro ? "available" : registrosPresentes > 0 ? "review" : "missing",
      statusLabel: reproducibleConRegistro ? "Registrada" : registrosPresentes > 0 ? "Parcial" : "Insuficiente",
      detail:
        `Trazas mínimas ${availableCount}/${TRAZAS_MINIMAS} (versión del motor, semilla y parser); ` +
        `elementos de reconstrucción ${elementosPresentes}/${ELEMENTOS_DE_RECONSTRUCCION.length}` +
        `${elementosFaltantes.length > 0 ? ` — faltan: ${elementosFaltantes.join(", ")}` : ""}. ` +
        "Reconstrucción por un tercero: no demostrada.",
    },
    {
      id: "physical",
      label: "Validez física de poses",
      status: physicalValidity.status === "passed" ? "available" : physicalValidity.status === "not_evaluated" ? "not_evaluated" : "review",
      statusLabel: physicalValidity.label,
      detail: physicalValidity.detail,
    },
    {
      id: "model",
      label: "Dominio del modelo",
      status: result.in_applicability_domain === true ? "available" : result.in_applicability_domain === false ? "review" : "not_evaluated",
      statusLabel: result.in_applicability_domain === true ? "Dentro del dominio declarado" : result.in_applicability_domain === false ? "Fuera del dominio" : "No informado",
      // Misma semántica que `evidence_summary.py` (DOC 71, A6): `engine_used` es el
      // motor HARDWARE del router y en el pipeline vale null, así que aquí salía
      // «motor no informado · family.» (QA-005). Esta fila habla del MODELO.
      detail: `${MODELO_LEGIBLE[result.model_used ?? ""] ?? result.model_used ?? "modelo no informado"}${
        result.fallback_reason ? `; fallback: ${result.fallback_reason}` : ""
      }. El motor de acoplamiento y su versión se declaran en la traza de reproducibilidad.`,
    },
    {
      id: "physicochemical",
      label: "Descriptores fisicoquímicos",
      status: descriptorCount >= 3 ? "available" : descriptorCount > 0 ? "review" : "missing",
      statusLabel: descriptorCount > 0 ? `${descriptorCount} señales reportadas` : "Sin datos",
      detail: "Se reportan valores y reglas por separado; no se convierten en una calificación global.",
    },
    {
      id: "selectivity",
      label: "Evidencia de selectividad",
      status: result.selectivity_ran ? (selectivityCount > 0 ? "available" : "review") : "not_evaluated",
      statusLabel: result.selectivity_ran ? (selectivityCount > 0 ? `${selectivityCount} anti-targets evaluados` : "Ejecución sin resultados") : "No evaluada",
      detail: result.selectivity_ran
        ? "Comparación computacional relativa al protocolo; no demuestra selectividad experimental."
        : "La corrida no registró un panel de anti-targets.",
    },
  ];

  const assumptions = [
    "Las afinidades se interpretan como señales de ranking dentro del protocolo, no como mediciones de energía libre experimental.",
    "La mejor pose cruda se identifica por el orden de afinidad serializado; ese orden no demuestra validez geométrica.",
    "No se atribuyen operaciones de preparación, protonación o minimización que la corrida no haya registrado.",
  ];
  const uncertainties = [
    // SOL-05: el detalle físico viaja en la lista para TODO estado no
    // aprobado — con `failed`/`review` quedaba vacía y el fallo era
    // invisible justo en el bloque donde el investigador busca reservas.
    ...(physicalValidity.status !== "passed" ? [physicalValidity.detail] : []),
    ...(nearTieCount > 1 ? [`${nearTieCount} poses quedan dentro de 1 kcal/mol; la selección de una sola pose es ambigua.`] : []),
    ...(availableCount < TRAZAS_MINIMAS ? ["La traza de reproducibilidad está incompleta."] : []),
    ...(elementosFaltantes.length > 0
      ? [`Faltan elementos para reconstruir la corrida: ${elementosFaltantes.join(", ")}.`]
      : []),
    ...(result.in_applicability_domain === false ? ["La salida derivada está fuera del dominio de aplicabilidad declarado."] : []),
    ...(result.in_applicability_domain == null ? ["El dominio de aplicabilidad del modelo no fue informado."] : []),
    ...warnings,
  ];

  const nextAction: EvaluationEvidence["nextAction"] = incomplete || physicalValidity.status === "failed"
    ? {
        status: "abstain",
        label: "Abstención: completar la corrida",
        detail: "No priorizar el ligando ni iniciar cálculos posteriores hasta recuperar poses y resolver los controles fallidos.",
      }
    : physicalValidity.status !== "passed"
      ? {
          status: "review",
          label: "Validar geometría antes de continuar",
          detail: "Comprobar choques, valencias, geometría, strain y consistencia del complejo antes de MM-GBSA, dinámica molecular o priorización experimental.",
        }
      : needsReview
        ? {
            status: "review",
            label: "Resolver reservas antes de comparar",
            detail: "Documentar las reservas de preparación, dominio o reproducibilidad antes de comparar esta corrida con otras.",
          }
        : {
            status: "proceed",
            label: "Apta para análisis posterior",
            detail: "La evidencia disponible permite continuar dentro del mismo protocolo, conservando las limitaciones documentadas.",
          };

  const evidence: EvaluationEvidence = {
    status,
    label: status === "ready" ? "Evidencia disponible" : status === "review" ? "Revisión necesaria" : "Evidencia incompleta",
    summary:
      status === "ready"
        ? "La corrida conserva poses, procedencia y los elementos registrados para intentar reconstruirla; la reconstrucción por un tercero no está demostrada."
        : status === "review"
          ? "La corrida produjo evidencia útil, pero contiene reservas que deben revisarse antes de continuar."
          : "Faltan afinidad o poses; no debe usarse esta corrida para priorizar el ligando.",
    poseCount: poses.length,
    topPoseAffinity,
    poseGap,
    nearTieCount,
    conformersGenerated: conformacionesDelMuestreo(result),
    reproducibility: {
      availableCount,
      totalCount: TRAZAS_MINIMAS,
      vinaVersion,
      randomSeed,
      parsingSource,
      reconstruction: {
        presentCount: elementosPresentes,
        totalCount: ELEMENTOS_DE_RECONSTRUCCION.length,
        missing: elementosFaltantes,
        /** Sólo una prueba de transferencia puede demostrarla; esta fila no. */
        demonstrated: false as const,
      },
    },
    modelContext: {
      engine: result.engine_used ?? null,
      model: result.model_used ?? null,
      inDomain: result.in_applicability_domain ?? null,
      fallbackReason: result.fallback_reason ?? null,
    },
    targetReadiness,
    physicalValidity,
    dimensions,
    assumptions,
    uncertainties,
    nextAction,
    warnings,
  };
  return translate ? localizeEvaluationEvidence(evidence, result, translate) : evidence;
}

function localizeEvaluationEvidence(
  evidence: EvaluationEvidence,
  result: EvaluationResult,
  t: Translate,
): EvaluationEvidence {
  const physicalValidity = {
    ...evidence.physicalValidity,
    label: t(`pr_ev_label_${
      evidence.physicalValidity.status === "passed"
        ? "controls_passed"
        : evidence.physicalValidity.status === "failed"
          ? "controls_failed"
          : evidence.physicalValidity.status === "review"
            ? "review_required"
            : "not_evaluated"
    }`),
    detail: evidence.physicalValidity.status === "passed"
      ? t("pr_ev_detail_physical_passed", {
          evaluated: result.structural_evidence?.poses_evaluated ?? 0,
          produced: result.structural_evidence?.poses_produced ?? 0,
        })
      : evidence.physicalValidity.status === "failed"
        ? t("pr_ev_detail_physical_failed")
        : evidence.physicalValidity.status === "review"
          ? t("pr_ev_detail_physical_review")
          : result.structural_evidence
            ? t("pr_ev_detail_physical_not_evaluated_reason", {
                reason: result.structural_evidence.reason_code ?? "no reason code",
              })
            : t("pr_ev_detail_physical_not_evaluated"),
  };

  const missingNames: Record<string, string> = {
    "caja de búsqueda efectiva": t("pr_ev_reconstruction_box"),
    "protocolo de búsqueda": t("pr_ev_reconstruction_protocol"),
    "hash del receptor": t("pr_ev_reconstruction_receptor_hash"),
    "hashes de entrada del ligando": t("pr_ev_reconstruction_ligand_inputs"),
    "hashes de salida (poses y registro)": t("pr_ev_reconstruction_outputs"),
    "preparación del ligando": t("pr_ev_reconstruction_ligand_prep"),
    "versión de la aplicación": t("pr_ev_reconstruction_app_version"),
  };
  const missingItems = evidence.reproducibility.reconstruction.missing
    .map((item) => missingNames[item] ?? item)
    .join(", ");
  const model = result.model_used === "family"
    ? t("pr_ev_model_family")
    : result.model_used === "universal"
      ? t("pr_ev_model_universal")
      : result.model_used ?? t("pr_ev_label_not_reported");
  const fallback = result.fallback_reason
    ? t("pr_ev_fallback_suffix", { reason: result.fallback_reason })
    : "";

  const dimensions = evidence.dimensions.map((dimension) => {
    const label = t(`pr_ev_dimension_${dimension.id}`);
    let statusLabel: string;
    let detail: string;
    switch (dimension.id) {
      case "system":
        statusLabel = t(dimension.status === "available"
          ? "pr_ev_label_documented"
          : dimension.status === "review"
            ? "pr_ev_label_review"
            : "pr_ev_label_insufficient");
        detail = t(evidence.targetReadiness === "listo"
          ? "pr_ev_detail_system_ready"
          : "pr_ev_detail_system_unconfirmed");
        break;
      case "docking":
        statusLabel = t(dimension.status === "available" ? "pr_ev_label_available" : "pr_ev_label_insufficient");
        detail = evidence.poseCount === 0 || evidence.topPoseAffinity == null
          ? t("pr_ev_detail_docking_missing")
          : t("pr_ev_detail_docking_present", {
              poses: evidence.poseCount,
              affinity: evidence.topPoseAffinity.toFixed(2),
            });
        break;
      case "sampling":
        statusLabel = t(evidence.poseCount === 0
          ? "pr_ev_label_no_evidence"
          : evidence.poseCount === 1
            ? "pr_ev_label_not_comparable"
            : evidence.nearTieCount > 1
              ? "pr_ev_label_ambiguous"
              : "pr_ev_label_descriptive");
        detail = evidence.poseCount < 2
          ? t("pr_ev_detail_sampling_insufficient")
          : t("pr_ev_detail_sampling_gap", {
              count: evidence.nearTieCount,
              gap: evidence.poseGap?.toFixed(2) ?? "—",
              muestreo: fraseDeMuestreoTraducida(evidence.conformersGenerated, t),
            });
        break;
      case "reproducibility":
        statusLabel = t(dimension.status === "available"
          ? "pr_ev_label_recorded"
          : dimension.status === "review"
            ? "pr_ev_label_partial"
            : "pr_ev_label_insufficient");
        detail = t("pr_ev_detail_reproducibility", {
          available: evidence.reproducibility.availableCount,
          required: evidence.reproducibility.totalCount,
          present: evidence.reproducibility.reconstruction.presentCount,
          total: evidence.reproducibility.reconstruction.totalCount,
          missing: missingItems
            ? t("pr_ev_missing_items_suffix", { items: missingItems })
            : "",
        });
        break;
      case "physical":
        statusLabel = physicalValidity.label;
        detail = physicalValidity.detail;
        break;
      case "model":
        statusLabel = t(result.in_applicability_domain === true
          ? "pr_ev_label_within_domain"
          : result.in_applicability_domain === false
            ? "pr_ev_label_outside_domain"
            : "pr_ev_label_not_reported");
        detail = t(
          result.fallback_reason
            ? "pr_ev_detail_model_with_fallback"
            : "pr_ev_detail_model",
          { model, fallback },
        );
        break;
      case "physicochemical": {
        const descriptorCount = [
          result.molecular_weight, result.log_p, result.tpsa, result.hbd,
          result.hba, result.rotatable_bonds, result.qed, result.sa_score,
        ].filter((value) => value != null && Number.isFinite(Number(value))).length;
        statusLabel = descriptorCount > 0
          ? t("pr_ev_label_signals_reported", { count: descriptorCount })
          : t("pr_ev_label_no_data");
        detail = t("pr_ev_detail_physicochemical");
        break;
      }
      case "selectivity": {
        const selectivityCount = result.selectivity_ran ? (result.anti_target_results ?? []).length : 0;
        statusLabel = !result.selectivity_ran
          ? t("pr_ev_label_not_evaluated")
          : selectivityCount > 0
            ? t("pr_ev_label_antitarget_count", { count: selectivityCount })
            : t("pr_ev_label_execution_no_results");
        detail = result.selectivity_ran
          ? t("pr_ev_detail_selectivity_evaluated")
          : t("pr_ev_detail_selectivity_missing");
        break;
      }
    }
    return { ...dimension, label, statusLabel, detail };
  });

  const assumptions = [
    t("pr_ev_assumption_affinity"),
    t("pr_ev_assumption_top_pose"),
    t("pr_ev_assumption_preparation"),
  ];
  const uncertainties = [
    ...(physicalValidity.status !== "passed" ? [physicalValidity.detail] : []),
    ...(evidence.nearTieCount > 1
      ? [t("pr_ev_uncertainty_near_tie", { count: evidence.nearTieCount })]
      : []),
    ...(evidence.reproducibility.availableCount < evidence.reproducibility.totalCount
      ? [t("pr_ev_uncertainty_trace")]
      : []),
    ...(missingItems
      ? [t("pr_ev_uncertainty_missing_elements", { items: missingItems })]
      : []),
    ...(result.in_applicability_domain === false
      ? [t("pr_ev_uncertainty_outside_domain")]
      : []),
    ...(result.in_applicability_domain == null
      ? [t("pr_ev_uncertainty_domain_unreported")]
      : []),
    ...evidence.warnings,
  ];

  const nextAction = evidence.nextAction.status === "abstain"
    ? {
        ...evidence.nextAction,
        label: t("pr_ev_next_abstain_label"),
        detail: t("pr_ev_next_abstain_detail"),
      }
    : physicalValidity.status !== "passed"
      ? {
          ...evidence.nextAction,
          label: t("pr_ev_next_validate_label"),
          detail: t("pr_ev_next_validate_detail"),
        }
      : evidence.status === "review"
        ? {
            ...evidence.nextAction,
            label: t("pr_ev_next_reservations_label"),
            detail: t("pr_ev_next_reservations_detail"),
          }
        : {
            ...evidence.nextAction,
            label: t("pr_ev_next_proceed_label"),
            detail: t("pr_ev_next_proceed_detail"),
          };

  return {
    ...evidence,
    label: t(`pr_ev_status_${evidence.status === "ready" ? "available" : evidence.status}`),
    summary: t(`pr_ev_summary_${evidence.status === "ready" ? "available" : evidence.status}`),
    physicalValidity,
    dimensions,
    assumptions,
    uncertainties,
    nextAction,
  };
}
