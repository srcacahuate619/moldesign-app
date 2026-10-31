"use client";

import { saveFailureKind } from "../../lib/evaluationErrorPresentation";
import { marcarEtapaDeEvaluacionChat } from "../../lib/evaluacionDesdeChat";

import { FrontendError, frontendMessage } from "../../lib/frontendError";

import { presentError } from "../../lib/frontendError";


import { Translated, useLanguage } from "@/context/LanguageContext";
// =====================================================================
// CaseEvaluationRunner — la evaluacion actual, ahora dentro de un caso
// =====================================================================
//
// QUE ES Y QUE NO ES. Es el cuerpo que hasta ahora vivia en
// `app/evaluation/page.tsx`, movido tal cual. NO reescribe `ProEvaluation`, no
// cambia el contrato de ningun endpoint y no toca el pipeline. Validar,
// ejecutar, cancelar, hacer polling y mostrar resultados se comportan igual.
//
// LO UNICO QUE SE ANADE:
//
//   1. `caseId`. El padre lo usa como `key`, asi que este componente se monta de
//      cero al cambiar de caso. Ese es el mecanismo de AISLAMIENTO: no hay
//      estado compartido de SMILES, receptor ni resultado entre casos porque no
//      hay instancia compartida.
//
//   2. `onLiveWorkChange`. Avisa al workspace de TODO trabajo vivo —corrida y
//      analisis largo tipo MM-GBSA— para que impida cambiar de caso. Sin esto,
//      cambiar de caso desmontaria este componente y con el se perderia el
//      `setInterval` del polling: la corrida seguiria en el backend y el
//      usuario no volveria a verla.
//
// El estado de ejecucion que se reporta es COMPUTACIONAL. No mueve el estado
// cientifico del caso: un `SUCCESS` no completa un caso (docs/53 §4).

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";

import {
  ApiError,
  cancelEvaluation,
  downloadCertificate,
  downloadComplexFile,
  getEvaluationResult,
  getJobStatus,
  mensajeDelError,
  saveMolecule,
  submitEvaluation,
  validateSmiles,
  type Target,
} from "../../lib/api";
import { useAuth } from "../../lib/auth";
import {
  catalogoEnMemoria,
  invalidarCatalogo,
  obtenerCatalogo,
} from "../../lib/catalogoDeReceptores";
import type { JobStatus, MolecularSuggestion, ValidationResult } from "../../lib/types";
import { playSound } from "../../lib/sounds";
import { notifyRunFinished } from "../../lib/activityNotifications";
import type {
  ActiveRun,
  CaseInputs,
  CaseRun,
  CasePipelineConfig,
  CaseStructuralSystem,
  HumanDecision,
  PreflightSummary,
  ReportableResult,
  ReportRecoveryState,
} from "../../lib/cases/types";
import {
  describeRunBlock,
  requestPreflight,
  summarizePreflight,
  type PreflightReport,
} from "../../lib/preflight";
import { PreparationPanel } from "./PreparationPanel";
import type { PeticionRecibida } from "../../lib/peticionDeEvaluacion";
import type { CaseOperationScope } from "../../context/CaseContext";

interface EvaluationIntent {
  readonly id: string;
  readonly scope: CaseOperationScope;
  readonly controller: AbortController;
  phase: "preflight" | "submitting";
  cancelRequested: boolean;
  invalidated: boolean;
}

const ProEvaluation = dynamic(() => import("../interfaces/pro/ProEvaluation"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[24rem] items-center justify-center bg-surface-950 text-zinc-100 font-mono p-6">
      <div className="text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-surface-700 border-t-transparent mx-auto mb-4" />
        <span className="text-[10px] font-bold uppercase tracking-[0.2em] animate-pulse"><Translated id="z_cargando_pro" /></span>
      </div>
    </div>
  ),
});

const POLL_INTERVAL_MS = 2000;
export const RESULT_RECOVERY_TIMEOUT_MS = 15_000;
const RESULT_RECOVERY_RETRY_DELAYS_MS = [300, 900] as const;

/**
 * Una petición HTTP pendiente no puede dejar el caso en «recuperando» para
 * siempre. La operación subyacente puede terminar después, pero su respuesta
 * queda descartada por la época del runner.
 */
export function withRecoveryDeadline<T>(promise: Promise<T>, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new FrontendError(frontendMessage("ev_recovery_deadline", { label, seconds: RESULT_RECOVERY_TIMEOUT_MS / 1000 })));
    }, RESULT_RECOVERY_TIMEOUT_MS);
    promise.then(
      (value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(value);
      },
      (cause) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        reject(cause);
      },
    );
  });
}

function isTransientRecoveryFailure(cause: unknown): boolean {
  if (cause instanceof ApiError) {
    return cause.status === 408 || cause.status === 425 || cause.status === 429 || cause.status >= 500;
  }
  return cause instanceof TypeError || (cause instanceof FrontendError &&
    ["ev_frontend_204", "ev_recovery_deadline", "pr_frontend_241", "pr_frontend_242"].includes(cause.frontendMessage && "key" in cause.frontendMessage ? cause.frontendMessage.key : ""));
}


export interface LiveWorkPatch {
  readonly evaluation?: boolean;
  readonly analysis?: boolean;
  readonly taskId?: string | null;
}

export interface CaseEvaluationRunnerProps {
  /** Identidad del caso. El padre lo pasa tambien como `key`. */
  readonly caseId: string;
  /**
   * Libro de corridas del caso, sólo de lectura. El runner no lo escribe (eso es
   * `onRunRegistered`); lo pasa a Evaluación para ofrecer al SAR la cohorte
   * histórica del mismo protocolo (CAS-02).
   */
  readonly caseRuns?: readonly CaseRun[];
  /**
   * Última corrida persistida del caso, si la hay. Al montarse se consulta el
   * backend una vez para recuperar el resultado; si no es terminal, además se
   * REANUDA el polling. Así se conserva tanto el trabajo vivo como su evidencia.
   */
  readonly activeRun?: ActiveRun;
  /** Notifica trabajo vivo NO persistido (MM-GBSA). */
  readonly onLiveWorkChange?: (patch: LiveWorkPatch) => void;
  /** Registra o cierra la corrida persistida. `null` la cierra. */
  readonly onActiveRunChange?: (run: CaseRun | null) => void;
  /**
   * Persiste la corrida recién nacida y ESPERA a que llegue al repositorio.
   *
   * Se usa sólo en el instante en que aparece el `taskId`. Los cambios de
   * progreso posteriores siguen por `onActiveRunChange`, con su debounce: ahí
   * perder una actualización no pierde la tarea.
   */
  readonly onRunRegistered?: (run: CaseRun, scope?: CaseOperationScope) => Promise<boolean>;
  /**
   * Publica la referencia MÍNIMA al resultado con el que se puede armar un
   * informe, o `null` si no hay ninguno.
   *
   * Es lo que permite al workspace revelar «Informe» sin duplicar el payload
   * científico ni volver a preguntar por su cuenta. Sale de aquí porque aquí
   * es donde vive el `status` real del polling; cualquier otro sitio tendría
   * que adivinarlo.
   */
  readonly onReportableChange?: (result: ReportableResult | null) => void;
  /**
   * Cómo va el intento de recuperar el resultado de una corrida persistida.
   *
   * `unrecoverable` es información, no ruido: un caso reabierto cuya tarea el
   * backend ya no conoce tiene que poder decirlo en vez de comportarse como si
   * nunca hubiera habido evaluación.
   */
  readonly onReportRecoveryChange?: (state: ReportRecoveryState) => void;
  /**
   * Inputs persistidos del caso. Son el ESTADO INICIAL de receptor y ligando:
   * sin ellos, reabrir un caso empezaba en blanco y la corrida guardada
   * quedaba sin hipótesis que la explicara.
   */
  readonly inputs?: CaseInputs;
  /** Sistema fijado por la primera corrida del caso, si ya existe. */
  readonly structuralSystem?: CaseStructuralSystem;
  /** El sistema ya está SELLADO: alguna corrida del caso terminó en él. */
  readonly structuralSystemSealed?: boolean;
  /** Cuántas corridas tiene el caso en su libro. */
  readonly runCount?: number;
  /** Abre el historial de corridas del caso, si el contenedor lo ofrece. */
  readonly onOpenRunHistory?: () => void;
  /** Persiste receptor/ligando/caja. Invalida el preflight si algo cambió. */
  readonly onInputsChange?: (patch: Partial<CaseInputs>, scope?: CaseOperationScope) => void;
  /** Resumen del último preflight guardado en el caso. */
  readonly preflight?: PreflightSummary;
  readonly onPreflightChange?: (summary: PreflightSummary, scope?: CaseOperationScope) => void;
  readonly decisions?: readonly HumanDecision[];
  readonly onDecision?: (controlCode: string, fingerprint: string) => void;
  /**
   * Preparación pidió volver a evaluar ESTE caso con un ligando y un modo de tautómero
   * (`lib/peticionDeEvaluacion`). Se aplica una vez por `nonce`: el ligando entra como si
   * se escribiera y el modo como si se eligiera en Opciones. No se ejecuta nada.
   */
  readonly peticion?: PeticionRecibida;
  readonly smilesDesdeChat?: { requestId: string; smiles: string; deadline: number; onApplied: () => void };
  readonly receptorDesdeChat?: { requestId: string; pdbId: string; deadline: number; onVisible: (already: boolean) => void; onError: (status: string) => void };
  readonly evaluacionDesdeChat?: { requestId: string; deadline: number; onResult: (result: { status: string; task_id?: string; reason?: string }) => void };
}

/**
 * La configuración que firma la comprobación y que luego se ejecuta: la del
 * caso si pasó por Opciones, o esta completa por defecto. Toda modificación
 * parcial (p. ej. el número de conformaciones) tiene que partir de aquí.
 *
 * Una configuración guardada a medias —la que dejaba QA-036 en los casos que
 * cambiaron a ensemble sin pasar por Opciones— se completa con los valores por
 * defecto; la que viene de Opciones ya trae todas las claves y no cambia.
 *
 * El merge es PROFUNDO, por etapa y clave (CAS-05). El shallow de antes
 * reemplazaba la etapa entera: un guardado con `conformer: {ph}` sin
 * `conformers` borraba el K del caso y lo devolvía a 1 sin que nadie lo
 * decidiera — y el siguiente preflight firmaba una corrida distinta de la
 * que el panel de preparación mostraba.
 */
export function configuracionDelPipeline(inputs: CaseInputs | undefined): CasePipelineConfig {
  const porDefecto = configuracionPorDefecto(inputs);
  const guardada = inputs?.pipelineConfig;
  if (!guardada) return porDefecto;

  const paramsDefecto = porDefecto.stage_params ?? {};
  const paramsGuardada = guardada.stage_params ?? {};
  const etapas = new Set([...Object.keys(paramsDefecto), ...Object.keys(paramsGuardada)]);
  const stage_params: Record<string, Record<string, unknown>> = {};
  for (const etapa of etapas) {
    const guardadaEtapa = paramsGuardada[etapa];
    if (guardadaEtapa === undefined) {
      if (paramsDefecto[etapa] !== undefined) stage_params[etapa] = { ...paramsDefecto[etapa] };
      continue;
    }
    stage_params[etapa] = { ...(paramsDefecto[etapa] ?? {}), ...guardadaEtapa };
  }
  return {
    ...porDefecto,
    ...guardada,
    stage_params,
  };
}

function configuracionPorDefecto(inputs: CaseInputs | undefined): CasePipelineConfig {
  return {
    enabled_stages: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
    stage_params: {
      docking: {
        exhaustiveness: inputs?.exhaustiveness ?? 8,
        num_poses: inputs?.numPoses ?? 9,
      },
      conformer: { conformers: inputs?.conformers ?? 1 },
      // ADMET-AI es opt-in y aquí se DICE, no se deja al defecto del
      // backend. Este objeto es el que firma el preflight y el que se
      // ejecuta luego: si la clave falta, el documento inspeccionado no
      // declara qué se hizo con ADMET, y el usuario que abra el dossier
      // no puede saberlo. Un caso que nunca pasó por Opciones corre sin
      // ADMET, y así queda escrito.
      properties: { run_admet_ai: false },
    },
    docking_engine: inputs?.dockingEngine ?? "vina",
    pro_workers: 4,
    pro_parallel_docks: 2,
    pro_selectivity: false,
    pro_mmgbsa: false,
    pro_mmgbsa_steps: 1000,
    gnn_precision: "fp32",
  };
}

export default function CaseEvaluationRunner({
  caseId,
  caseRuns,
  activeRun,
  onLiveWorkChange,
  onActiveRunChange,
  onRunRegistered,
  onReportableChange,
  onReportRecoveryChange,
  inputs,
  structuralSystem,
  structuralSystemSealed = false,
  runCount = 0,
  onOpenRunHistory,
  onInputsChange,
  preflight,
  onPreflightChange,
  decisions,
  onDecision,
  peticion,
  smilesDesdeChat,
  receptorDesdeChat,
  evaluacionDesdeChat,
}: CaseEvaluationRunnerProps) {
  const { t } = useLanguage();
  const {
    isLoading: authLoading,
    logout,
    token: authToken,
    user: authUser,
  } = useAuth();
  // El estado arranca de lo que el caso tenga guardado. El valor por defecto
  // sólo se usa en un caso nuevo, y no se persiste hasta que alguien lo
  // cambia: guardar la aspirina de ejemplo como «hipótesis del usuario» sería
  // atribuirle una decisión que no tomó.
  const [smiles, setSmiles] = useState(inputs?.ligand?.inputSmiles ?? "CC(=O)Oc1ccccc1C(=O)O");
  const [target, setTarget] = useState(
    structuralSystem?.receptor.pdbId ?? inputs?.receptor?.pdbId ?? "",
  );
  // El catálogo es GLOBAL: los mismos 380 receptores para todos los casos. Si
  // ya está en memoria se arranca con él, y entonces no hay ni parpadeo de
  // «cargando» ni 1,2 MB de descarga al cambiar de caso. Ver
  // `lib/catalogoDeReceptores.ts` para la medición que lo motiva.
  const catalogoInicial = catalogoEnMemoria();
  const [targets, setTargets] = useState<Target[]>(() => [...(catalogoInicial ?? [])]);
  const [loadingTargets, setLoadingTargets] = useState(catalogoInicial === null);
  const [catalogFailed, setCatalogFailed] = useState(false);

  const [validation, setValidation] = useState<ValidationResult | null>(null);
  // Arranca DESDE la corrida persistida: si el caso trae una, este componente
  // no empieza en blanco.
  const [taskId, setTaskId] = useState<string | null>(activeRun?.taskId ?? null);
  const [status, setStatus] = useState<JobStatus | null>(
    activeRun
      ? {
          task_id: activeRun.taskId,
          status:
            activeRun.executionState === "completed" ? "SUCCESS"
            : activeRun.executionState === "failed" || activeRun.executionState === "cancelled" ? "FAILURE"
            : activeRun.executionState === "interrupted" ? "PENDING"
            : "STARTED",
          progress: activeRun.lastKnownProgress ?? 0,
          result: null,
          error: activeRun.lastError ?? null,
          started_at: activeRun.startedAt,
          finished_at: null,
        }
      : null,
  );
  const [resultRecovery, setResultRecovery] = useState<{
    state: "recovering" | "blocked";
    message?: string;
    requiresLogin?: boolean;
  } | null>(
    activeRun?.executionState === "completed" ? { state: "recovering" } : null,
  );
  /**
   * El seguimiento se perdio, NO el backend fallo.
   *
   * Antes, cinco fallos de conexion escribian `status: FAILURE`, que es una
   * afirmacion sobre el backend que nadie habia comprobado: la tarea podia
   * estar terminando perfectamente. Ahora se declara INTERRUMPIDO, se conserva
   * el `taskId` y se ofrece volver a preguntar.
   */
  const [pollingInterrupted, setPollingInterrupted] = useState(
    activeRun?.executionState === "interrupted",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isControl, setIsControl] = useState(false);
  // «Guardada en Moldex» es un hecho de la EVALUACIÓN que se está viendo, no del
  // caso ni de la molécula: una molécula se reevalúa varias veces en el mismo
  // caso y cada evaluación se guarda por separado. Un booleano suelto dejaba
  // «Guardado» pegado al resultado siguiente y no permitía guardarlo.
  const [savedTaskIds, setSavedTaskIds] = useState<ReadonlySet<string>>(() => new Set());
  const resultTaskId = status?.result?.task_id ?? null;
  const isSaved = resultTaskId !== null && savedTaskIds.has(resultTaskId);
  const setIsSaved = (saved: boolean) => {
    if (!saved) setSavedTaskIds(new Set());
    else if (resultTaskId) setSavedTaskIds((prev) => new Set(prev).add(resultTaskId));
  };
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /**
   * Invalida respuestas HTTP que salieron antes de detener/cambiar el polling.
   * Limpiar un timer no cancela una promesa ya en vuelo: sin esta generación,
   * una respuesta de la sesión anterior podía volver a introducir resultados.
   */
  const pollingEpochRef = useRef(0);
  /** Distingue cancelación explícita de un FAILURE real del backend. */
  const cancelledTaskRef = useRef<string | null>(
    activeRun?.executionState === "cancelled" ? activeRun.taskId : null,
  );

  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<MolecularSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // ── Trabajo vivo ──────────────────────────────────────────────────
  //
  // `submitting` se enciende ANTES de llamar a `submitEvaluation`, no al
  // recibir el `taskId`. Entre las dos cosas hay una peticion de red: si el
  // usuario cambiaba de caso en esa ventana, este componente se desmontaba, la
  // respuesta llegaba a un componente muerto y la tarea quedaba corriendo en el
  // backend sin nadie que la siguiera. Ese hueco es el que se cierra aqui.
  const [submitting, setSubmitting] = useState(false);
  // MM-GBSA y cualquier otro calculo largo lo reporta `ProEvaluation`.
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const runnerMounted = useRef(true);
  const operationScope = useRef<CaseOperationScope>({ caseId, ownerUserId: authUser?.user_id });
  operationScope.current = { caseId, ownerUserId: authUser?.user_id };
  const pendingIntent = useRef<EvaluationIntent | null>(null);
  const nextIntentId = useRef(0);
  const cancellingTask = useRef<string | null>(null);
  const scopeIsCurrent = useCallback((scope: CaseOperationScope) =>
    runnerMounted.current && operationScope.current.caseId === scope.caseId &&
    operationScope.current.ownerUserId === scope.ownerUserId, []);
  const intentIsCurrent = useCallback((intent: EvaluationIntent) =>
    pendingIntent.current === intent && !intent.invalidated && !intent.cancelRequested &&
    scopeIsCurrent(intent.scope), [scopeIsCurrent]);

  const isTerminal = status?.status === "SUCCESS" || status?.status === "FAILURE";
  // Una interrupcion conserva el taskId para reintentar, pero ya no representa
  // trabajo que esta siendo seguido. Mantenerla como activa bloqueaba toda la
  // barra lateral aun despues de detener el polling.
  const persistedRunIsTerminal =
    activeRun?.executionState === "completed" ||
    activeRun?.executionState === "failed" ||
    activeRun?.executionState === "cancelled";
  const runActive =
    submitting ||
    (Boolean(taskId) && !isTerminal && !persistedRunIsTerminal && !pollingInterrupted);

  // Refs para el manejador de `auth_expired`, que no debe recrearse en cada
  // cambio de estado: si lo hiciera, se re-suscribiría en cada render.
  const taskIdRef = useRef<string | null>(taskId);
  taskIdRef.current = taskId;
  const statusRef = useRef<JobStatus | null>(status);
  statusRef.current = status;
  const recoveryAttemptsRef = useRef<Map<string, number>>(new Map());
  const recoveryRetryTimerRef = useRef<number | null>(null);
  const resumeRunRef = useRef<
    ((tid: string, expectReport?: boolean, persistedMoleculeId?: string) => Promise<void>) | null
  >(null);
  const isTerminalRef = useRef(isTerminal);
  isTerminalRef.current = isTerminal;
  const terminalNotificationRef = useRef<string | null>(
    persistedRunIsTerminal ? activeRun?.taskId ?? null : null,
  );

  useEffect(() => {
    if (!taskId || !isTerminal || terminalNotificationRef.current === taskId) return;
    terminalNotificationRef.current = taskId;
    notifyRunFinished({
      source: "evaluation",
      runId: taskId,
      successful: status?.status === "SUCCESS",
      outcome: cancelledTaskRef.current === taskId ? "cancelled"
        : status?.status === "SUCCESS" ? "completed" : "failed",
      taskId,
      caseId,
      ownerId: authUser?.user_id,
    });
  }, [taskId, isTerminal, status?.status, caseId, authUser?.user_id]);

  const notifyLiveWork = useRef(onLiveWorkChange);
  notifyLiveWork.current = onLiveWorkChange;

  useEffect(() => {
    notifyLiveWork.current?.({ evaluation: runActive, taskId: taskId ?? null });
  }, [runActive, taskId]);

  // Espeja el estado de la corrida al manifiesto del caso. Es lo que sobrevive
  // a cerrar la ventana; sin esto no habría nada que reanudar.
  const notifyActiveRun = useRef(onActiveRunChange);
  notifyActiveRun.current = onActiveRunChange;

  // El registro inicial lo hace `handleSubmit` de forma esperada; este efecto
  // sólo ESPEJA los cambios posteriores. Sin esta guarda, el efecto correría
  // con el `taskId` nuevo antes de que la escritura crítica confirmara, y el
  // debounce volvería a ser el que decide si la tarea se registra.
  const initialRegistrationDone = useRef(activeRun !== undefined);
  // El alta inicial y el primer tick de progreso pueden ocurrir antes de que el
  // caso reinyecte `activeRun` como prop. La huella vive también en esta ref
  // para que ese tick no pueda borrarla. Los casos afectados se reparan desde
  // su sistema estructural, que sólo pudo fijarse desde esa misma corrida.
  const runFingerprintRef = useRef<string | undefined>(
    activeRun?.inputFingerprint ??
      (activeRun && structuralSystem?.sourceRunTaskId === activeRun.taskId
        ? structuralSystem.inputFingerprint
        : undefined),
  );
  useEffect(() => {
    if (activeRun?.inputFingerprint) {
      runFingerprintRef.current = activeRun.inputFingerprint;
    } else if (
      activeRun &&
      structuralSystem?.sourceRunTaskId === activeRun.taskId &&
      structuralSystem.inputFingerprint
    ) {
      runFingerprintRef.current = structuralSystem.inputFingerprint;
    } else if (!taskId) {
      runFingerprintRef.current = undefined;
    }
  }, [activeRun?.inputFingerprint, activeRun?.taskId, structuralSystem, taskId]);

  useEffect(() => {
    if (!taskId) {
      notifyActiveRun.current?.(null);
      return;
    }
    if (!initialRegistrationDone.current) return;
    const executionState: ActiveRun["executionState"] =
      cancelledTaskRef.current === taskId ? "cancelled"
      : status?.status === "SUCCESS" ? "completed"
      : status?.status === "FAILURE" ? "failed"
      : pollingInterrupted ? "interrupted"
      : status?.status === "submitted" ? "submitted"
      : "running";

    // Una corrida terminal deja de BLOQUEAR, pero no desaparece. El taskId es
    // el vínculo que permite recuperar su resultado al volver a este caso.
    notifyActiveRun.current?.({
      taskId,
      ...(status?.status === "SUCCESS" && status.result?.molecule_id
        ? { moleculeId: status.result.molecule_id }
        : activeRun?.moleculeId
          ? { moleculeId: activeRun.moleculeId }
          : {}),
      executionState,
      startedAt: status?.started_at ?? activeRun?.startedAt ?? new Date().toISOString(),
      // El titular de la corrida se copia a su fila para que el libro se pueda
      // leer sin backend. NO es una segunda copia del informe: es la cifra y el
      // ligando que identifican la fila; el payload sigue detrás del
      // `moleculeId`, que es lo único con lo que se reabre.
      ...(status?.finished_at ? { finishedAt: status.finished_at } : {}),
      ...(typeof status?.result?.affinity_kcal === "number"
        ? { affinityKcal: status.result.affinity_kcal }
        : {}),
      // `ligandSmiles` NO se escribe aquí. Lo puso el submit con el SMILES
      // inspeccionado y `upsertRun` lo conserva al fusionar. Rellenarlo desde
      // `inputs.ligand` sería atribuir a esta corrida el ligando que haya AHORA
      // en pantalla, que es precisamente la atribución falsa que el resto del
      // modelo se dedica a impedir. Una fila migrada de v6 no lo tiene, y lo
      // correcto es que diga que no lo sabe.
      // El fingerprint es de la corrida, no del momento: sobrevive a cada
      // actualización de progreso. Perderlo aquí dejaría la corrida sin poder
      // demostrar a qué hipótesis pertenece.
      ...(runFingerprintRef.current
        ? { inputFingerprint: runFingerprintRef.current }
        : {}),
      ...(typeof status?.progress === "number" ? { lastKnownProgress: status.progress } : {}),
      ...(status?.error
        ? { lastError: status.error }
        : pollingInterrupted && !isTerminal
        ? { lastError: t("ev_frontend_071") }
        : {}),
    });
  }, [taskId, status, pollingInterrupted, activeRun?.startedAt, activeRun?.moleculeId, t]);

  // ── Referencia al resultado publicable ────────────────────────────
  //
  // El informe NO se arma con una copia del resultado: se arma con el
  // `molecule_id` que el backend ya conoce. Publicar sólo esa referencia es lo
  // que impide que `case.json` acabe conteniendo una segunda versión del
  // payload científico, que envejecería sin que nada la revalidara.
  const notifyReportable = useRef(onReportableChange);
  notifyReportable.current = onReportableChange;

  useEffect(() => {
    const moleculeId =
      status?.status === "SUCCESS" ? status.result?.molecule_id ?? null : null;
    if (!taskId || !moleculeId) {
      notifyReportable.current?.(null);
      return;
    }
    notifyReportable.current?.({
      taskId,
      moleculeId,
      certified: Boolean(status?.result?.blockchain_tx_id),
    });
  }, [taskId, status]);

  const notifyRecovery = useRef(onReportRecoveryChange);
  notifyRecovery.current = onReportRecoveryChange;

  useEffect(() => {
    notifyLiveWork.current?.({ analysis: analysisBusy });
  }, [analysisBusy]);

  // Al desmontar, libera el bloqueo. Sin esto, un caso cerrado con una corrida
  // a medias dejaria el workspace bloqueado para siempre.
  useEffect(() => {
    runnerMounted.current = true;
    return () => {
      runnerMounted.current = false;
      const intent = pendingIntent.current;
      if (intent) {
        intent.invalidated = true;
        intent.controller.abort();
        pendingIntent.current = null;
      }
      notifyLiveWork.current?.({ evaluation: false, analysis: false, taskId: null });
    };
  }, []);

  // ── Comprobación previa ───────────────────────────────────────────
  //
  // El informe COMPLETO vive en memoria; el caso guarda sólo su resumen. Al
  // reabrir, el resumen basta para enseñar el estado y para decidir si se
  // puede ejecutar; el detalle se vuelve a pedir con un clic.
  const [preflightReport, setPreflightReport] = useState<PreflightReport | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState<string | null>(null);

  const notifyInputs = useRef(onInputsChange);
  notifyInputs.current = onInputsChange;

  // Se persiste lo que la persona escribe, tal cual. El canónico llega
  // después, con el preflight; escribirlo aquí sería inventarlo.
  const escribirSmiles = useCallback((next: string) => {
    setSmiles(next);
    notifyInputs.current?.({
      ligand: { inputSmiles: next },
    });
  }, []);

  const chatAplicado = useRef<string | null>(null);
  useEffect(() => {
    if (!smilesDesdeChat || chatAplicado.current === smilesDesdeChat.requestId || Date.now() >= smilesDesdeChat.deadline) return;
    chatAplicado.current = smilesDesdeChat.requestId;
    escribirSmiles(smilesDesdeChat.smiles);
    setValidation(null);
  }, [smilesDesdeChat, escribirSmiles]);

  // Cerrar el aviso no la vuelve a aplicar: lo aplicado se recuerda aparte.
  const peticionAplicada = useRef<number | null>(null);
  const [avisoDePeticion, setAvisoDePeticion] = useState<PeticionRecibida | null>(null);
  useEffect(() => {
    if (!peticion || peticionAplicada.current === peticion.nonce) return;
    peticionAplicada.current = peticion.nonce;
    setAvisoDePeticion(peticion);
    escribirSmiles(peticion.smiles);
    // La validación era de otro SMILES.
    setValidation(null);
  }, [peticion, escribirSmiles]);
  const notifyPreflight = useRef(onPreflightChange);
  notifyPreflight.current = onPreflightChange;

  /**
   * El informe en memoria deja de valer en cuanto el caso retira su resumen.
   *
   * `CaseContext.setInputs` borra el preflight guardado al cambiar algo que
   * afecte a la corrida. Aquí se deriva de eso —no se recalcula la
   * correspondencia— para que exista UNA sola regla de invalidación.
   */
  const preflightStale = preflightReport !== null && !preflight;

  const grid = inputs?.grid;

  // LA MOLÉCULA DE EJEMPLO CUENTA COMO LIGANDO AL PULSAR «EVALUAR». El editor de
  // un caso nuevo trae una aspirina de muestra que no se guarda como hipótesis
  // hasta que alguien la cambia (decisión de arriba): guardarla al abrir sería
  // atribuirle una decisión que no tomó. Pero quien pulsa «Evaluar» con ella a la
  // vista SÍ está decidiendo, así que en ese momento —y sólo en ese— entra al caso.
  // Antes había que editarla (aunque fuera para dejarla igual) antes de poder
  // siquiera comprobar: la primera experiencia empezaba por un callejón sin salida.
  const ligandoDeEjemplo = !inputs?.ligand?.inputSmiles?.trim() && smiles.trim().length > 0;
  const entradas: CaseInputs | undefined = ligandoDeEjemplo
    ? { ...inputs, ligand: { inputSmiles: smiles.trim() } }
    : inputs;

  const runBlockedReason = describeRunBlock(entradas, preflight, t);

  /**
   * La comprobación previa. Ya no es un botón: la lanza `handleSubmit` dentro de
   * «Evaluar». Devuelve el resumen para que quien la pidió ejecute CON ÉL, sin
   * esperar a que el estado del caso se entere: lo que se ejecuta es lo que se
   * acaba de inspeccionar, no lo que había en pantalla un instante antes.
   */
  const comprobar = useCallback(async (entradasAComprobar: CaseInputs, intent: EvaluationIntent): Promise<PreflightSummary | null> => {
    const receptorPdbId = entradasAComprobar.receptor?.pdbId;
    const ligandSmiles = entradasAComprobar.ligand?.inputSmiles;
    if (!receptorPdbId || !ligandSmiles) throw new Error(t("ev_elige_receptor_ejecutar"));

    setPreflightLoading(true);
    setPreflightError(null);
    try {
      const pipelineConfig = configuracionDelPipeline(entradasAComprobar);
      const report = await requestPreflight({
        smiles: ligandSmiles,
        targetPdbId: receptorPdbId,
        chain: entradasAComprobar.receptor?.chain,
        gridCenter: entradasAComprobar.grid?.center as [number, number, number] | undefined,
        gridSize: entradasAComprobar.grid?.size as [number, number, number] | undefined,
        customHotspots: entradasAComprobar.customHotspots,
        dockingEngine: entradasAComprobar.dockingEngine ?? "vina",
        exhaustiveness: entradasAComprobar.exhaustiveness ?? 8,
        numPoses: entradasAComprobar.numPoses ?? 9,
        // El protocolo declarado entra en la comprobación, así que la huella
        // que sale describe la corrida que de verdad se ejecutará.
        conformers: entradasAComprobar.conformers ?? 1,
        pipelineConfig,
      }, intent.controller.signal);
      if (!intentIsCurrent(intent)) return null;
      const resumen = summarizePreflight(report);
      setPreflightReport(report);
      notifyPreflight.current?.(resumen, intent.scope);
      // El canónico se guarda junto al texto introducido. No lo sustituye: el
      // dossier tiene que poder enseñar los dos.
      if (report.ligand.canonical_smiles) {
        notifyInputs.current?.({
          ligand: {
            inputSmiles: ligandSmiles,
            canonicalSmiles: report.ligand.canonical_smiles,
            ...(entradasAComprobar.ligand?.name ? { name: entradasAComprobar.ligand.name } : {}),
          },
        }, intent.scope);
      }
      return resumen;
    } catch (err) {
      if (!intentIsCurrent(intent)) return null;
      setPreflightError(err instanceof Error ? presentError(err, t) : String(err));
      throw err;
    } finally {
      if (intentIsCurrent(intent)) setPreflightLoading(false);
    }
  }, [t, intentIsCurrent]);

  const preparationSlot = (
    <PreparationPanel
      report={preflightReport}
      summary={preflight}
      loading={preflightLoading}
      error={preflightError}
      stale={preflightStale}
      conformers={inputs?.conformers ?? 1}
      decisions={decisions ?? []}
      onAcknowledge={(code) => {
        const fingerprint = preflight?.fingerprint;
        if (fingerprint) onDecision?.(code, fingerprint);
      }}
    />
  );

  /**
   * `forzar` es para el botón de recargar, que existe para volver a preguntar
   * de verdad; el montaje normal se queda con lo que haya en memoria.
   *
   * La pantalla NO se pone en «cargando» si ya hay receptores: hacerlo
   * vaciaría un selector que está lleno para volver a llenarlo con lo mismo.
   */
  const loadTargets = useCallback((forzar = false) => {
    setLoadingTargets((previo) => previo || forzar);
    obtenerCatalogo({ forzar })
      .then((receptores) => { setTargets([...receptores]); setCatalogFailed(false); })
      .catch((err) => { setCatalogFailed(true); setError(t("ev_frontend_072", { v0: presentError((err as Error), t) })); })
      .finally(() => setLoadingTargets(false));
  }, [t]);

  useEffect(() => {
    loadTargets();
  }, [loadTargets]);

  const stopPolling = useCallback(() => {
    // Invalida también la petición que ya esté en vuelo. `clearTimeout` por sí
    // solo únicamente impide el siguiente tick.
    pollingEpochRef.current += 1;
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (tid: string) => {
      stopPolling();
      const epoch = pollingEpochRef.current;
      let consecutiveErrors = 0;

      const stillCurrent = () => pollingEpochRef.current === epoch;
      const scheduleNext = () => {
        if (!stillCurrent()) return;
        pollingRef.current = setTimeout(() => {
          pollingRef.current = null;
          void pollOnce();
        }, POLL_INTERVAL_MS);
      };
      const pollOnce = async () => {
        try {
          const polled = await getJobStatus(tid);
          if (!stillCurrent()) return;
          consecutiveErrors = 0;
          isTerminalRef.current = polled.status === "SUCCESS" || polled.status === "FAILURE";
          setStatus(polled);
          if (polled.status === "SUCCESS" || polled.status === "FAILURE") {
            stopPolling();
            if (polled.status === "SUCCESS") {
              playSound("success");
            } else if (polled.status === "FAILURE") {
              playSound("whisper");
            }
            return;
          }
          scheduleNext();
        } catch {
          if (!stillCurrent()) return;
          // FIX (Tauri): antes esto reintentaba forever y dejaba el spinner
          // infinito sin ningún error visible. Cinco fallos consecutivos
          // (≈10s) detienen el polling.
          //
          // Y NO se marca FAILURE. Un corte de conexión no es un fallo del
          // backend: la tarea puede estar terminando bien. Se declara
          // INTERRUMPIDO —lo único cierto—, se conserva el `taskId` y se ofrece
          // volver a preguntar.
          consecutiveErrors++;
          if (consecutiveErrors >= 5) {
            stopPolling();
            setPollingInterrupted(true);
            return;
          }
          scheduleNext();
        }
      };

      // Después del submit se conserva el intervalo histórico de 2 s antes de
      // la primera consulta. `resumeRun` hace su propia consulta inmediata.
      scheduleNext();
    },
    [stopPolling],
  );

  useEffect(() => () => {
    stopPolling();
    // `stopPolling` invalida la recuperación que estuviera en vuelo. Si la guarda
    // de identidad se quedara puesta, el remontaje —StrictMode en desarrollo, el
    // keep-alive al volver a la pestaña— no reintentaría, y «Recuperando
    // resultados guardados» se quedaba para siempre sin ninguna petición
    // (QA-023). Se limpia para que el remontaje la vuelva a pedir una vez.
    resumedIdentityRef.current = null;
    if (recoveryRetryTimerRef.current) clearTimeout(recoveryRetryTimerRef.current);
  }, [stopPolling]);

  /**
   * Consulta el backend UNA vez y decide si hay que seguir siguiendo la tarea.
   *
   * Es el mecanismo de reanudación: se usa al montar con una corrida viva y
   * también cuando el usuario pulsa «Reintentar seguimiento».
   */
  const resumeRun = useCallback(
    async (tid: string, expectReport = false, persistedMoleculeId?: string) => {
      stopPolling();
      const epoch = pollingEpochRef.current;
      setPollingInterrupted(false);
      const visible = statusRef.current;
      if (
        expectReport &&
        visible?.task_id === tid &&
        visible.status === "SUCCESS" &&
        visible.result?.molecule_id
      ) {
        recoveryAttemptsRef.current.delete(tid);
        setResultRecovery(null);
        notifyRecovery.current?.("recovered");
        return;
      }

      if (expectReport) {
        setResultRecovery({ state: "recovering" });
        notifyRecovery.current?.("recovering");
      }
      try {
        // Una corrida completada ya tiene un `moleculeId` durable. Se consulta
        // primero SQLite: el cache de tareas es efímero y no debe bloquear la
        // evidencia que sobrevivió al reinicio del backend.
        let polled: JobStatus | null = null;
        let durableError: unknown = null;
        if (expectReport && persistedMoleculeId) {
          try {
            polled = {
              task_id: tid,
              status: "SUCCESS",
              progress: 100,
              result: await withRecoveryDeadline(
                getEvaluationResult(persistedMoleculeId, tid),
                "La lectura del resultado guardado",
              ),
              error: null,
              started_at: activeRun?.startedAt ?? null,
              finished_at: null,
            };
          } catch (cause) {
            durableError = cause;
          }
        }

        // Sin referencia durable —o si ésta falló— el estado de la tarea sigue
        // siendo una segunda vía válida. También tiene deadline: ninguna red
        // puede dejar un spinner infinito.
        if (polled === null) {
          try {
            polled = await withRecoveryDeadline(
              getJobStatus(tid),
              "La consulta de la corrida",
            );
          } catch (statusError) {
            throw durableError ?? statusError;
          }
        }
        if (expectReport && (polled.status !== "SUCCESS" || !polled.result?.molecule_id)) {
          throw new Error(
            polled.error || t("ev_frontend_073"),
          );
        }
        if (pollingEpochRef.current !== epoch) return;
        isTerminalRef.current = polled.status === "SUCCESS" || polled.status === "FAILURE";
        setStatus(polled);
        if (expectReport) {
          recoveryAttemptsRef.current.delete(tid);
          // Se declara recuperado SÓLO con el `molecule_id` en la mano. Un
          // SUCCESS sin resultado no es un informe: es una pérdida silenciosa,
          // y presentarla como informe disponible sería inventarla.
          notifyRecovery.current?.(
            polled.status === "SUCCESS" && polled.result?.molecule_id
              ? "recovered"
              : "unrecoverable",
          );
          setResultRecovery(null);
        }
        if (polled.status === "SUCCESS" || polled.status === "FAILURE") {
          stopPolling();
          return;
        }
        startPolling(tid);
      } catch (cause) {
        if (pollingEpochRef.current !== epoch) return;
        if (expectReport) {
          const attempts = recoveryAttemptsRef.current.get(tid) ?? 0;
          const retryDelay = RESULT_RECOVERY_RETRY_DELAYS_MS[attempts];
          if (retryDelay !== undefined && isTransientRecoveryFailure(cause)) {
            recoveryAttemptsRef.current.set(tid, attempts + 1);
            setResultRecovery({
              state: "recovering",
              message: t("auto_74f10d125232"),
            });
            if (recoveryRetryTimerRef.current) clearTimeout(recoveryRetryTimerRef.current);
            recoveryRetryTimerRef.current = window.setTimeout(() => {
              void resumeRunRef.current?.(tid, true, persistedMoleculeId);
            }, retryDelay);
            return;
          }
          recoveryAttemptsRef.current.delete(tid);
          const statusCode = cause instanceof ApiError ? cause.status : null;
          const requiresLogin = statusCode === 401 || statusCode === 403;
          const message =
            statusCode === 401
              ? t("ev_frontend_074")
              : statusCode === 403
                ? t("ev_frontend_075")
                : cause instanceof Error && presentError(cause, t).startsWith(t("mx_error_conexion"))
                  ? t("ev_frontend_076")
                  : t("ev_frontend_077", { v0: cause instanceof Error ? presentError(cause, t) : String(cause) });
          setResultRecovery({ state: "blocked", message, requiresLogin });
          notifyRecovery.current?.("unrecoverable");
          // No marcar la corrida como fallida ni reemplazar su SUCCESS
          // persistido: falló la lectura actual, no el cálculo de ayer.
          return;
        }
        // Sigue sin poder consultarse: interrumpido, no fallido.
        setPollingInterrupted(true);
      }
    },
    [activeRun?.startedAt, startPolling, stopPolling, t],
  );

  resumeRunRef.current = resumeRun;
  // Al montar con cualquier corrida persistida se pregunta de inmediato. Para
  // una terminal, esta lectura recupera el `result` que no se guarda dentro de
  // case.json; para una viva, además reanuda el polling.
  const previousOperationScope = useRef(operationScope.current);
  useEffect(() => {
    const previous = previousOperationScope.current;
    const current = operationScope.current;
    previousOperationScope.current = current;
    if (previous.caseId === current.caseId && previous.ownerUserId === current.ownerUserId) return;
    const intent = pendingIntent.current;
    if (intent) {
      intent.invalidated = true;
      intent.controller.abort();
      pendingIntent.current = null;
      setSubmitting(false);
      setBusy(false);
      setPreflightLoading(false);
      notifyLiveWork.current?.({ evaluation: false, taskId: null });
    }
    stopPolling();
  }, [caseId, authUser?.user_id, stopPolling]);

  const resumedIdentityRef = useRef<string | null>(null);
  useEffect(() => {
    if (authLoading || !activeRun) return;
    // La identidad forma parte de la llave: si el usuario vuelve a iniciar
    // sesión con la cuenta correcta, la misma instancia reintenta sin exigir
    // cerrar el caso ni recargar la aplicación.
    const identity = `${activeRun.taskId}:${authUser?.user_id ?? "anonymous"}:${authToken ? "token" : "no-token"}`;
    if (resumedIdentityRef.current === identity) return;
    resumedIdentityRef.current = identity;
    if (activeRun) {
      // Sólo una corrida COMPLETADA promete evidencia recuperable. Para las
      // demás la consulta sigue siendo útil —reanuda el seguimiento— pero no
      // se anuncia una recuperación de informe que nadie esperaba.
      void resumeRun(
        activeRun.taskId,
        activeRun.executionState === "completed",
        activeRun.moleculeId,
      );
    }
  }, [activeRun, authLoading, authToken, authUser?.user_id, resumeRun]);

  // FIX (sesión cambia): si la sesión caduca/cambia (refresh fallido, logout, o
  // auto-login Desktop silencioso), resetear TODO el estado visible de la
  // evaluación. Sin esto el usuario vería resultados/molecule_id de la cuenta
  // ANTERIOR y al pulsar Guardar recibiría 404 "no es tuya". La sesión y los
  // resultados visibles deben estar sincronizados siempre.
  useEffect(() => {
    const handleAuthChange = () => {
      stopPolling();
      const intent = pendingIntent.current;
      if (intent) {
        intent.invalidated = true;
        intent.controller.abort();
        pendingIntent.current = null;
        setSubmitting(false);
        setPreflightLoading(false);
        notifyLiveWork.current?.({ evaluation: false, taskId: null });
      }
      // Se limpian los RESULTADOS, que pueden pertenecer a otra cuenta y cuyo
      // `molecule_id` no se puede guardar con la sesión nueva.
      setSuggestions([]);
      setProteinData(null);
      setPoseData(null);
      setSavedTaskIds(new Set());
      setBusy(false);

      // Pero NO la IDENTIDAD DE LA TAREA. Antes esto ponía `taskId` a null y
      // borraba el estado: la corrida seguía viva en el backend y su
      // identificador desaparecía de la interfaz y del manifiesto. Un cambio
      // de sesión no dice nada sobre cómo va la tarea.
      const knownTaskId = taskIdRef.current;
      const live = knownTaskId !== null && !isTerminalRef.current;
      if (knownTaskId !== null) {
        // Aunque la tarea ya fuera terminal, el resultado se limpió por
        // seguridad de sesión y necesita una acción explícita de recuperación.
        setPollingInterrupted(true);
        setStatus((prev) => (prev ? { ...prev, result: null } : prev));
        setError(
          live
            ? t("auto_b0a87dfd9e6e") +
              t("auto_9d0f79ed0388")
            : t("auto_7d5211dfd7ca") +
              t("auto_e66cbf48ffa4"),
        );
      } else {
        setTaskId(null);
        setStatus(null);
        setError(t("auto_d63f7a54d93b"));
      }
    };
    window.addEventListener("auth_expired", handleAuthChange);
    return () => window.removeEventListener("auth_expired", handleAuthChange);
  }, [stopPolling, t]);

  const handleValidate = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await validateSmiles(smiles);
      setValidation(result);
      if (result.is_valid && result.canonical_smiles) {
        setSmiles(result.canonical_smiles);
      }
    } catch (e) {
      setError(mensajeDelError(e));
    } finally {
      setBusy(false);
    }
  };

  const cancelKnownRun = async (tid: string, acceptedRun?: CaseRun) => {
    if (cancellingTask.current === tid) return;
    const scope = { ...operationScope.current };
    cancellingTask.current = tid;
    stopPolling();
    try {
      const result = await cancelEvaluation(tid);
      if (!scopeIsCurrent(scope)) return;
      if (!result.cancelled) {
        const run = acceptedRun ?? (activeRun?.taskId === tid ? activeRun : undefined);
        await resumeRun(tid, run?.executionState === "completed", run?.moleculeId);
        if (scopeIsCurrent(scope)) setError(t("auto_567d82bb53d9"));
        return;
      }
      setPollingInterrupted(false);
      cancelledTaskRef.current = tid;
      isTerminalRef.current = true;
      setStatus((prev) => ({
        ...(prev?.task_id === tid ? prev : {
          task_id: tid, progress: 0, result: null,
          started_at: acceptedRun?.startedAt ?? null, finished_at: null,
        }),
        status: "FAILURE", error: t("auto_aa7e38e37678"),
      }));
      notifyActiveRun.current?.({
        ...(acceptedRun ?? (activeRun?.taskId === tid ? activeRun : {})),
        taskId: tid,
        executionState: "cancelled",
        startedAt: acceptedRun?.startedAt ?? statusRef.current?.started_at ??
          activeRun?.startedAt ?? new Date().toISOString(),
        ...(runFingerprintRef.current ? { inputFingerprint: runFingerprintRef.current } : {}),
        lastError: t("auto_aa7e38e37678"),
      });
      setBusy(false);
    } catch (cause) {
      if (!scopeIsCurrent(scope)) return;
      setPollingInterrupted(true);
      setError(t("ev_frontend_067", { v0: presentError((cause as Error), t) }) +
        t("auto_9efee153557b"));
    } finally {
      if (cancellingTask.current === tid) cancellingTask.current = null;
    }
  };

  const handleCancel = async () => {
    const intent = pendingIntent.current;
    if (intent && scopeIsCurrent(intent.scope)) {
      intent.cancelRequested = true;
      if (intent.phase === "submitting") {
        // La petición puede haber sido aceptada: esperar su ID evita perderla
        // o mandar la cancelación a la corrida terminal anterior.
        setError(t("ev_cancelacion_envio_pendiente"));
        return;
      }
      intent.controller.abort();
      pendingIntent.current = null;
      setSubmitting(false);
      setBusy(false);
      setPreflightLoading(false);
      setError(null);
      notifyLiveWork.current?.({ evaluation: false, taskId: taskIdRef.current });
      notifyRunFinished({ source: "evaluation", runId: `intent:${intent.scope.caseId}:${intent.id}`,
        successful: false, outcome: "cancelled", caseId: intent.scope.caseId, ownerId: intent.scope.ownerUserId });
      return;
    }
    if (taskIdRef.current) await cancelKnownRun(taskIdRef.current);
  };

  const solicitudChatEnCurso = useRef<typeof evaluacionDesdeChat>(undefined);
  const handleSubmit = async (
    _gridCenter?: [number, number, number],
    _gridSize?: [number, number, number],
    _customHotspots?: string[],
    peptideDockingEngine?: "esmfold" | "esmfold-pro" | "esmfold-experimental" | "colabfold",
    _pipelineConfig?: CasePipelineConfig
  ) => {
    const solicitudChat = solicitudChatEnCurso.current;
    solicitudChatEnCurso.current = undefined;
    if (solicitudChat) marcarEtapaDeEvaluacionChat(solicitudChat.requestId, t("ev_chat_etapa_envio"));
    let chatRespondido = false;
    const responderChat = (status: string, task_id?: string, reason?: string) => {
      if (!solicitudChat || chatRespondido) return;
      chatRespondido = true;
      solicitudChat.onResult({ status, ...(task_id ? { task_id } : {}),
        ...(reason ? { reason: reason.replace(/[\x00-\x1f]/g, " ").slice(0, 500) } : {}) });
    };
    // GATE. No se ejecuta nada que el preflight no haya inspeccionado. Es la
    // garantía de que la corrida corresponde exactamente a lo que se mostró:
    // sin ella, el panel podría estar describiendo unos inputs y el submit
    // enviando otros.
    //
    // La comprobación va DENTRO de «Evaluar»: antes era un botón aparte que había
    // que pulsar primero, y quien no lo sabía se quedaba con «Evaluar»
    // deshabilitado sin entender por qué. Se hace cuando no hay una vigente (caso
    // nuevo, o inputs cambiados: `CaseContext.setInputs` retira el resumen en
    // cuanto cambia algo que afecte a la corrida) y se usa el resumen que
    // devuelve, no el estado del caso, que todavía no se enteró. Un resumen
    // vigente se reutiliza tal cual, como siempre: describe exactamente estos
    // inputs, y repetir la comprobación daría la misma huella.
    const bloqueoPrevio = describeRunBlock(entradas, preflight, t);
    if (bloqueoPrevio) {
      setError(bloqueoPrevio);
      responderChat("blocked", undefined, bloqueoPrevio);
      return;
    }
    if (authLoading || pendingIntent.current || runActive) { responderChat("busy"); return; }
    if (solicitudChat && Date.now() >= solicitudChat.deadline) { responderChat("unknown"); return; }
    const intent: EvaluationIntent = {
      id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}:${++nextIntentId.current}:${Math.random()}`,
      scope: { ...operationScope.current },
      controller: new AbortController(), phase: "preflight",
      cancelRequested: false, invalidated: false,
    };
    const registerAcceptedRun = onRunRegistered;
    pendingIntent.current = intent;
    setSubmitting(true);
    setBusy(true);
    setError(null);
    notifyLiveWork.current?.({ evaluation: true, taskId: taskIdRef.current });
    try {
      let inspeccion: PreflightSummary | null | undefined = preflight;
      const hayQueComprobar = !inspeccion?.executionConfig || !inspeccion.fingerprint;
      if (hayQueComprobar && entradas) {
        setBusy(true);
        setError(null);
        if (ligandoDeEjemplo) {
          notifyInputs.current?.({ ligand: { inputSmiles: smiles.trim() } });
        }
        try {
          inspeccion = await comprobar(entradas, intent);
          if (!inspeccion || !intentIsCurrent(intent)) return;
        } catch (err) {
          if (!intentIsCurrent(intent)) return;
          setError(err instanceof Error ? presentError(err, t) : String(err));
          setBusy(false);
          responderChat("failed");
          return;
        }
        const bloqueoTrasComprobar = describeRunBlock(entradas, inspeccion, t);
        if (bloqueoTrasComprobar) {
          // La comprobación encontró algo que haría fallar la corrida: no se ejecuta
          // nada y el panel de preparación enseña qué y por qué.
          setError(bloqueoTrasComprobar);
          setBusy(false);
          responderChat("blocked", undefined, bloqueoTrasComprobar);
          return;
        }
      }
      if (!intentIsCurrent(intent)) return;
      const execution = inspeccion?.executionConfig;
      const inspectedFingerprint = inspeccion?.fingerprint;
      if (!execution || !inspectedFingerprint) {
        setError(t("auto_dc96db7f7404"));
        setBusy(false);
        responderChat("blocked");
        return;
      }
      if (solicitudChat && Date.now() >= solicitudChat.deadline) { responderChat("unknown"); return; }

      setBusy(true);
      setError(null);
      setSuggestions([]);
      stopPolling();
      setPollingInterrupted(false);
      // La corrida terminal anterior sólo se reemplaza cuando el backend entrega
      // un taskId nuevo. Si el submit falla, el caso conserva su última evidencia.
      initialRegistrationDone.current = false;
      intent.phase = "submitting";
      const inspectedTarget = structuralSystem?.receptor.pdbId ?? inputs?.receptor?.pdbId ?? target;
      const inspectedChain = structuralSystem?.receptor.chain ?? inputs?.receptor?.chain;
      if (!inspectedTarget || inspectedTarget.length < 4) {
        setError(t("auto_b612f6dc223e"));
        setBusy(false);
        setSubmitting(false);
        responderChat("blocked");
        return;
      }
      // Se envía lo que el CASO tiene guardado y lo que el preflight
      // inspeccionó, no lo que traigan los argumentos del componente de
      // presentación. Si esas dos cosas pudieran diferir, el fingerprint
      // dejaría de significar nada.
      const inspectedSmiles = entradas?.ligand?.inputSmiles ?? smiles;
      const inspectedCenter = [...execution.gridCenter] as [number, number, number];
      const inspectedSize = [...execution.gridSize] as [number, number, number];
      const inspectedHotspots = [...execution.customHotspots];
      // La configuración PRO es parte del documento canónico firmado por el
      // preflight. No se reconstruye aquí: añadir defaults equivalentes (por
      // ejemplo `seed: 42`) cambia el JSON y produce un 409 aunque la hipótesis
      // científica sea la misma. Se envía exactamente la copia inspeccionada.
      const inspectedPipelineConfig = execution.pipelineConfig;

      const result = await submitEvaluation(
        inspectedSmiles,
        inspectedTarget,
        isControl,
        inspectedCenter,
        inspectedSize,
        inspectedHotspots,
        peptideDockingEngine,
        inspectedPipelineConfig,
        inspectedFingerprint,
        inspectedChain,
      );

      // PERSISTENCIA CRÍTICA. El `taskId` acaba de nacer y es lo único que
      // permite volver a encontrar la tarea. Se escribe y se ESPERA antes de
      // seguir: con el debounce de 600 ms, cerrar la ventana en esa ventana
      // dejaba la tarea viva en el backend sin que nada la registrara.
      const startedAt = new Date().toISOString();
      const newRun: CaseRun = {
        taskId: result.task_id,
        executionState: "submitted",
        startedAt,
        // La huella de los inputs inspeccionados viaja con la corrida. Es lo
        // que permitirá, más tarde, decir si el informe guardado corresponde a
        // la hipótesis que haya entonces en pantalla o a una anterior.
        ...(inspeccion?.fingerprint ? { inputFingerprint: inspeccion.fingerprint } : {}),
        // Lo justo para que la fila del libro se pueda pintar SIN backend. El
        // ligando y el protocolo salen de lo INSPECCIONADO, no de los controles
        // de la pantalla: si esas dos cosas pudieran diferir, la fila afirmaría
        // un protocolo que la corrida no usó.
        ligandSmiles: inspectedSmiles,
        protocol: {
          dockingEngine: execution.dockingEngine,
          exhaustiveness: execution.exhaustiveness,
          numPoses: execution.numPoses,
          conformers: execution.conformers ?? 1,
        },
      };
      let registered = true;
      try {
        registered = registerAcceptedRun ? await registerAcceptedRun(newRun, intent.scope) : true;
      } catch {
        // La tarea ya existe en el backend: aun si el adaptador de persistencia
        // falla de una forma inesperada, el identificador debe llegar a la UI.
        registered = false;
      }
      if (typeof result.task_id === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(result.task_id)) {
        responderChat(registered && registerAcceptedRun ? "started" : "started_unregistered", result.task_id);
      } else responderChat("unknown");
      // La tarea aceptada ya se preservó en su origen. Una instancia antigua
      // no vuelve a mostrarla ni inicia polling bajo otra sesión/caso.
      if (!scopeIsCurrent(intent.scope) || intent.invalidated) return;
      runFingerprintRef.current = newRun.inputFingerprint;
      initialRegistrationDone.current = true;

      cancelledTaskRef.current = null;
      taskIdRef.current = result.task_id;
      isTerminalRef.current = false;
      setTaskId(result.task_id);
      setStatus({
        task_id: result.task_id,
        status: "submitted",
        progress: 0,
        result: null,
        error: null,
        started_at: startedAt,
        finished_at: null,
      });
      if (!registered) {
        // El contenedor ya muestra el aviso con el identificador y el botón de
        // reintentar. Aquí no se oculta ni se sigue como si nada.
        setError(
          t("auto_d03d4fc90d79") +
            t("auto_f3beed6bd3c8"),
        );
      }
      if (intent.cancelRequested) {
        await cancelKnownRun(result.task_id, newRun);
      } else {
        startPolling(result.task_id);
      }
    } catch (e) {
      if (scopeIsCurrent(intent.scope) && !intent.invalidated) setError(mensajeDelError(e));
      responderChat(intent.phase === "submitting" ? "unknown" : "failed");
    } finally {
      responderChat("unknown");
      // Una respuesta retirada no puede apagar la intención que vino después.
      if (pendingIntent.current === intent) {
        pendingIntent.current = null;
        if (scopeIsCurrent(intent.scope)) {
          setBusy(false);
          setSubmitting(false);
        }
      }
    }
  };

  const handleReset = () => {
    // No se puede borrar la identidad de un envío que aún espera aceptación.
    if (pendingIntent.current || runActive) return;
    stopPolling();
    cancelledTaskRef.current = null;
    initialRegistrationDone.current = false;
    runFingerprintRef.current = undefined;
    taskIdRef.current = null;
    isTerminalRef.current = false;
    setValidation(null);
    setTaskId(null);
    setStatus(null);
    setError(null);
    setSuggestions([]);
    setPoseData(null);
    setProteinData(null);
    setSavedTaskIds(new Set());
  };

  const handleUseSuggestion = async (sug: MolecularSuggestion) => {
    if (!sug.smiles) return;
    setSmiles(sug.smiles);
    handleReset();
    setBusy(true);
    try {
      const result = await validateSmiles(sug.smiles);
      setValidation(result);
    } catch (e) {
      setError(presentError((e as Error), t));
    } finally {
      setBusy(false);
    }
  };

  // Si el backend derivó una caja efectiva durante el preflight, ésa es la
  // configuración que debe reaparecer. Los inputs crudos pueden contener el
  // sentinel (0,0,0), que no fue lo que realmente se inspeccionó ni ejecutará.
  const restoredExecution = preflight?.executionConfig;
  const initialRunConfiguration = {
    center: structuralSystem?.grid.center ?? restoredExecution?.gridCenter ?? inputs?.grid?.center,
    size: structuralSystem?.grid.size ?? restoredExecution?.gridSize ?? inputs?.grid?.size,
    customHotspots: structuralSystem?.customHotspots ?? restoredExecution?.customHotspots ?? inputs?.customHotspots,
    dockingEngine: structuralSystem?.dockingEngine ?? restoredExecution?.dockingEngine ?? inputs?.dockingEngine,
    exhaustiveness: structuralSystem?.exhaustiveness ?? restoredExecution?.exhaustiveness ?? inputs?.exhaustiveness,
    numPoses: structuralSystem?.numPoses ?? restoredExecution?.numPoses ?? inputs?.numPoses,
    pipelineConfig: structuralSystem?.pipelineConfig ?? restoredExecution?.pipelineConfig ?? inputs?.pipelineConfig,
  };

  // Both the UI and MolChat use the same case mutation and structural lock.
  const seleccionarReceptor = useCallback((next: string) => {
        if (structuralSystem) {
          setError(
            t("auto_8819735dd62d") +
              t("auto_ce0ad0ebf48a"),
          );
          return;
        }
        setTarget(next);
        const catalogEntry = targets.find((t) => t.pdb_id === next);
        const hasCatalogGrid =
          catalogEntry?.grid_center_x != null &&
          catalogEntry?.grid_center_y != null &&
          catalogEntry?.grid_center_z != null;
        notifyInputs.current?.({
          receptor: {
            pdbId: next,
            origin: catalogEntry?.is_private
              ? "privado"
              : catalogEntry?.is_community
                ? "comunidad"
                : catalogEntry
                  ? "curado"
                  : "desconocido",
            ...(catalogEntry?.chain ? { chain: catalogEntry.chain } : {}),
            ...(catalogEntry?.id ? { targetId: catalogEntry.id } : {}),
            ...(catalogEntry?.name ? { name: catalogEntry.name } : {}),
          },
          // Una caja o selección de residuos pertenece al receptor anterior.
          // Persistir la caja del nuevo catálogo evita que una comprobación
          // rápida use silenciosamente coordenadas de otra proteína.
          grid: hasCatalogGrid
            ? {
                center: [
                  Number(catalogEntry.grid_center_x),
                  Number(catalogEntry.grid_center_y),
                  Number(catalogEntry.grid_center_z),
                ],
                size: [
                  Number(catalogEntry.grid_size_x ?? 22.5),
                  Number(catalogEntry.grid_size_y ?? 22.5),
                  Number(catalogEntry.grid_size_z ?? 22.5),
                ],
              }
            : undefined,
          // `undefined` BORRA la selección del receptor anterior, pero no decide nada por
          // la investigadora: `[]` es «no quiero residuos de referencia» y el backend lo
          // respeta (SOL-08). Fijar `[]` aquí hacía que toda corrida por defecto fuera sin
          // residuos —sin análisis de contactos— con «Opciones» diciendo «15/15 activos»
          // y el preflight atribuyéndolo a una decisión (QA1-007).
          customHotspots: undefined,
        });

  }, [structuralSystem, targets, t]);
  const receptorProcesado = useRef<string | null>(null);
  const receptorNotificado = useRef<string | null>(null);
  useEffect(() => {
    const request = receptorDesdeChat;
    if (!request || receptorProcesado.current === request.requestId || loadingTargets || Date.now() >= request.deadline) return;
    receptorProcesado.current = request.requestId;
    if (catalogFailed) { receptorNotificado.current = request.requestId; request.onError("unavailable"); return; }
    const matches = targets.filter(item => item.pdb_id?.toUpperCase() === request.pdbId.toUpperCase());
    if (!matches.length) { receptorNotificado.current = request.requestId; request.onError("receptor_not_found"); return; }
    if (matches.length > 1) { receptorNotificado.current = request.requestId; request.onError("receptor_ambiguous"); return; }
    if (matches[0].disponible === false) { receptorNotificado.current = request.requestId; request.onError("unavailable"); return; }
    const already = target.toUpperCase() === matches[0].pdb_id.toUpperCase() && inputs?.receptor?.pdbId?.toUpperCase() === matches[0].pdb_id.toUpperCase();
    if (already) { receptorNotificado.current = request.requestId; request.onVisible(true); return; }
    if (structuralSystem) { receptorNotificado.current = request.requestId; request.onError("locked"); return; }
    seleccionarReceptor(matches[0].pdb_id);
  }, [receptorDesdeChat, loadingTargets, catalogFailed, targets, target, inputs?.receptor?.pdbId, structuralSystem, seleccionarReceptor]);
  useEffect(() => {
    const request = receptorDesdeChat;
    if (!request || receptorProcesado.current !== request.requestId || receptorNotificado.current === request.requestId || Date.now() >= request.deadline) return;
    if (target.toUpperCase() === request.pdbId.toUpperCase()) {
      receptorNotificado.current = request.requestId;
      request.onVisible(false);
    }
  }, [receptorDesdeChat, target]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {pollingInterrupted && taskId && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs leading-relaxed text-amber-200"
        >
          <span className="min-w-0 flex-1">
            {isTerminal ? (
              <>{t("pn_resultado_limpiado")}</>
            ) : (
              <>{t("pn_conexion_perdida")} <strong>{t("pn_no_se_sabe_como_termino")}</strong>{t("pn_puede_seguir_corriendo")}</>
            )}
          </span>
          <button
            type="button"
            onClick={() => void resumeRun(taskId, activeRun?.executionState === "completed", activeRun?.moleculeId)}
            className="shrink-0 whitespace-nowrap rounded border border-amber-500/40 px-2 py-0.5 text-[11px] hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            {t("c_reintentar_seguimiento")}
          </button>
        </div>
      )}
      {avisoDePeticion && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 border-b border-purple-400/30 bg-purple-500/10 px-4 py-2 text-xs leading-relaxed text-purple-100"
        >
          <span className="min-w-0 flex-1 break-all">
            {t("ev_peticion_preparacion", {
              smiles: avisoDePeticion.smiles,
              modo: t(avisoDePeticion.tautomero === "entrada" ? "op_tautomero_entrada" : "op_tautomero_defecto"),
            })}
          </span>
          <button
            type="button"
            onClick={() => setAvisoDePeticion(null)}
            aria-label={t("c_cerrar")}
            className="shrink-0 rounded border border-purple-400/40 px-2 py-0.5 text-[11px] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-300"
          >
            {t("c_cerrar")}
          </button>
        </div>
      )}
      <div className="min-h-0 flex-1">
      <ProEvaluation
      caseId={caseId}
      activeConformers={inputs?.conformers ?? 1}
      caseRuns={caseRuns}
      ejemploEnEditor={!inputs?.ligand?.inputSmiles}
      smiles={smiles}
      smilesDesdeChat={smilesDesdeChat}
      setSmiles={escribirSmiles}
      target={target}
      setTarget={seleccionarReceptor}
      targets={targets}
      loadingTargets={loadingTargets}
      // Subir un receptor propio cambia el catálogo para TODA la aplicación:
      // se invalida lo guardado antes de volver a pedirlo, o los demás casos
      // seguirían mostrando un catálogo sin el receptor recién subido. Se
      // envuelve en una lambda a propósito: pasar `loadTargets` directo le
      // entregaría el argumento del llamador como si fuera `forzar`.
      onTargetUploadSuccess={() => {
        invalidarCatalogo();
        loadTargets(true);
      }}
      validation={validation}
      setValidation={setValidation}
      taskId={taskId}
      setTaskId={setTaskId}
      status={status}
      cancelled={
        Boolean(taskId) &&
        (cancelledTaskRef.current === taskId ||
          (activeRun?.taskId === taskId && activeRun?.executionState === "cancelled"))
      }
      resultRecovery={resultRecovery}
      onRetryResultRecovery={() => {
        if (!taskId) return;
        if (resultRecovery?.requiresLogin) {
          logout();
          window.location.href = "/login?returnTo=%2Fevaluation";
          return;
        }
        void resumeRun(
          taskId,
          activeRun?.executionState === "completed",
          activeRun?.moleculeId,
        );
      }}
      setStatus={setStatus}
      busy={busy}
      setBusy={setBusy}
      error={error}
      setError={setError}
      isControl={isControl}
      setIsControl={setIsControl}
      isSaved={isSaved}
      setIsSaved={setIsSaved}
      proteinData={proteinData}
      poseData={poseData}
      suggestions={suggestions}
      loadingSuggestions={loadingSuggestions}
      handleSave={async (customName) => {
        if (!status?.result?.molecule_id) return;
        // FIX (Tauri): el endpoint /history/save/{id} exige sesión
        // (get_current_user). Si no hay token, avisar de forma profesional
        // en lugar de fallar silenciosamente con un HTTP 401 crudo.
        const storedAuth = typeof window !== "undefined" ? localStorage.getItem("moldesign_auth") : null;
        if (!storedAuth) {
          setError(t("auto_3c658efb0bdc"));
          return;
        }
        const guardada = status.result.task_id ?? null;
        try {
          await saveMolecule(status.result.molecule_id, customName, guardada);
          if (guardada) setSavedTaskIds((prev) => new Set(prev).add(guardada));
          playSound("bloom");
          // Notificar a /moldex (y a cualquier otra ruta keep-alive) que la
          // biblioteca cambió. Sin esto, navegar a /moldex tras guardar puede
          // mostrar la lista stale si el efecto keep-alive no dispara a tiempo
          // o si el POST todavía no commiteó cuando el efecto ya corrió.
          // El CustomEvent viaja por `window` y cruza el árbol de providers
          // keep-alive sin necesidad de un Context compartido.
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("moldex:invalidated", {
              detail: { moleculeId: status.result.molecule_id, taskId: guardada },
            }));
          }
        } catch (e) {
          const msg = presentError((e as Error), t);
          if (saveFailureKind(e) === "session") {
            setError(t("auto_f56a50a80039"));
          } else if (saveFailureKind(e) === "missing") {
            // La molécula existe pero pertenece a otra cuenta (el backend
            // devuelve 404 "Molécula no encontrada" para no revelar existencia),
            // o la sesión cambió (invitado ↔ cuenta personal) entre evaluación
            // y guardado. Mensaje claro y profesional en lugar del crudo.
            setError(t("auto_57652532d30f"));
          } else {
            setError(msg);
          }
        }
      }}
      handleCertify={async (signature) => {
        if (!status?.result?.molecule_id) return;
        setStatus(prev => {
          if (!prev || !prev.result) return prev;
          return {
            ...prev,
            result: {
              ...prev.result,
              blockchain_tx_id: signature,
            },
          };
        });
        playSound("sparkle");
      }}
      handleDownloadCertificate={async () => {
        if (!status?.result?.molecule_id) return;
        try {
          await downloadCertificate(status.result.molecule_id, "evaluation", status.result.task_id);
        } catch (e) {
          setError(t("ev_frontend_069", { v0: presentError((e as Error), t) }));
        }
      }}
      handleDownloadComplex={async () => {
        if (!status?.result?.molecule_id) return;
        try {
          await downloadComplexFile(status.result.molecule_id, "evaluation", status.result.task_id);
        } catch (e) {
          setError(t("ev_frontend_070", { v0: presentError((e as Error), t) }));
        }
      }}
      handleValidate={handleValidate}
      handleSubmit={handleSubmit}
      evaluacionDesdeChat={evaluacionDesdeChat ? { ...evaluacionDesdeChat,
        onInvoke: () => { solicitudChatEnCurso.current = evaluacionDesdeChat; } } : undefined}
      handleReset={handleReset}
      handleCancel={handleCancel}
      handleUseSuggestion={handleUseSuggestion}
      startPolling={startPolling}
      stopPolling={stopPolling}
      onLongRunningWorkChange={setAnalysisBusy}
      structuralSystem={structuralSystem}
      structuralSystemSealed={structuralSystemSealed}
      runCount={runCount}
      onOpenRunHistory={onOpenRunHistory}
      preparationSlot={preparationSlot}
      runBlockedReason={runBlockedReason}
      initialRunConfiguration={initialRunConfiguration}
      tautomeroPedido={peticion ? { modo: peticion.tautomero, nonce: peticion.nonce } : undefined}
      onRunConfigurationChange={(config) => {
        // Con el sistema SELLADO viaja sólo el protocolo. La caja y los
        // residuos no se reenvían siquiera: `setInputs` los restituiría desde
        // el ancla y de paso levantaría un aviso de que se intentó cambiarlos,
        // que es ruido cuando la interfaz ya los tiene deshabilitados.
        //
        // Con el sistema PROVISIONAL —escrito por una corrida que aún no ha
        // terminado— viaja todo: todavía se puede corregir.
        if (structuralSystemSealed && structuralSystem) {
          notifyInputs.current?.({
            dockingEngine: config.dockingEngine,
            exhaustiveness: config.exhaustiveness,
            numPoses: config.numPoses,
            conformers: config.conformers,
            pipelineConfig: config.pipelineConfig,
          });
          return;
        }
        notifyInputs.current?.({
          grid: { center: config.center, size: config.size },
          customHotspots: config.customHotspots,
          dockingEngine: config.dockingEngine,
          exhaustiveness: config.exhaustiveness,
          numPoses: config.numPoses,
          conformers: config.conformers,
          pipelineConfig: config.pipelineConfig,
        });
      }}
      />
      </div>
    </div>
  );
}
