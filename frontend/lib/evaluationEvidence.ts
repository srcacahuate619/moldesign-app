import type { Target } from "./api";
import { normalizarAvisos } from "./avisos";

/** Sólo los mensajes de los avisos, en el orden en que llegaron. */
const textosDeAvisos = (valores: unknown): string[] =>
  normalizarAvisos(valores).map((aviso) => aviso.mensaje);
import type { EvaluationResult, ValidationResult } from "./types";

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
  reproducibility: {
    availableCount: number;
    totalCount: 3;
    vinaVersion: string | null;
    randomSeed: number | null;
    parsingSource: string | null;
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

export function deriveEvaluationEvidence(
  result: EvaluationResult,
  target: Target | null,
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
    availableCount < 3;
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
        : `${nearTieCount} poses quedan a ≤1 kcal/mol; Δ pose 1–2 ${poseGap?.toFixed(2)} kcal/mol. No se registraron réplicas ni ensemble.`,
    },
    {
      id: "reproducibility",
      label: "Reproducibilidad técnica",
      status: availableCount === 3 ? "available" : availableCount > 0 ? "review" : "missing",
      statusLabel: availableCount === 3 ? "Completa" : availableCount > 0 ? "Parcial" : "Insuficiente",
      detail: `${availableCount}/3 trazas: versión del motor, semilla y parser.`,
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
      detail: `${result.engine_used ?? "motor no informado"} · ${result.model_used ?? "modelo no informado"}${result.fallback_reason ? ` · fallback: ${result.fallback_reason}` : ""}.`,
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
    ...(physicalValidity.status === "not_evaluated" ? [physicalValidity.detail] : []),
    ...(nearTieCount > 1 ? [`${nearTieCount} poses quedan dentro de 1 kcal/mol; la selección de una sola pose es ambigua.`] : []),
    ...(availableCount < 3 ? ["La traza de reproducibilidad está incompleta."] : []),
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

  return {
    status,
    label: status === "ready" ? "Evidencia disponible" : status === "review" ? "Revisión necesaria" : "Evidencia incompleta",
    summary:
      status === "ready"
        ? "La corrida conserva poses, procedencia y parámetros suficientes para revisión y reproducción técnica."
        : status === "review"
          ? "La corrida produjo evidencia útil, pero contiene reservas que deben revisarse antes de continuar."
          : "Faltan afinidad o poses; no debe usarse esta corrida para priorizar el ligando.",
    poseCount: poses.length,
    topPoseAffinity,
    poseGap,
    nearTieCount,
    reproducibility: {
      availableCount,
      totalCount: 3,
      vinaVersion,
      randomSeed,
      parsingSource,
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
}
