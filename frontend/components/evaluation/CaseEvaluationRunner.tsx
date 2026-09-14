"use client";

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
  inputsAreComplete,
  requestPreflight,
  summarizePreflight,
  type PreflightReport,
} from "../../lib/preflight";
import { PreparationPanel } from "./PreparationPanel";

const ProEvaluation = dynamic(() => import("../interfaces/pro/ProEvaluation"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[24rem] items-center justify-center bg-surface-950 text-zinc-100 font-mono p-6">
      <div className="text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-surface-700 border-t-transparent mx-auto mb-4" />
        <span className="text-[10px] font-bold uppercase tracking-[0.2em] animate-pulse">Cargando evaluación pro...</span>
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
      reject(new Error(`${label} excedió ${RESULT_RECOVERY_TIMEOUT_MS / 1000} segundos.`));
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
  const message = cause instanceof Error ? cause.message : String(cause);
  return /conexi.n|failed to fetch|network|econnrefused|timeout|excedi.|motor local no est. disponible/i.test(message);
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
  readonly onRunRegistered?: (run: CaseRun) => Promise<boolean>;
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
  readonly onInputsChange?: (patch: Partial<CaseInputs>) => void;
  /** Resumen del último preflight guardado en el caso. */
  readonly preflight?: PreflightSummary;
  readonly onPreflightChange?: (summary: PreflightSummary) => void;
  readonly decisions?: readonly HumanDecision[];
  readonly onDecision?: (controlCode: string, fingerprint: string) => void;
}

export default function CaseEvaluationRunner({
  caseId,
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
}: CaseEvaluationRunnerProps) {
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
  const [isSaved, setIsSaved] = useState(false);
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
    });
  }, [taskId, isTerminal, status?.status]);

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
        ? { lastError: "Se perdió la conexión con el servidor. No se sabe cómo terminó la tarea." }
        : {}),
    });
  }, [taskId, status, pollingInterrupted, activeRun?.startedAt, activeRun?.moleculeId]);

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
    return () => {
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
  const runBlockedReason = describeRunBlock(inputs, preflight);
  const canCheckPreparation = inputsAreComplete(inputs) && !runActive;

  const missingInputs = !inputs?.receptor?.pdbId
    ? "Elige un receptor para poder comprobar la preparación."
    : !inputs?.ligand?.inputSmiles?.trim()
      ? "Introduce o dibuja un ligando para poder comprobar la preparación."
      : runActive
        ? "Hay una corrida en curso: la comprobación previa se puede repetir cuando termine."
        : null;

  const handleCheckPreparation = useCallback(async () => {
    const receptorPdbId = inputs?.receptor?.pdbId;
    const ligandSmiles = inputs?.ligand?.inputSmiles;
    if (!receptorPdbId || !ligandSmiles) return;

    setPreflightLoading(true);
    setPreflightError(null);
    try {
      const pipelineConfig = inputs?.pipelineConfig ?? {
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
        pro_anti_targets: ["5VA1", "4NY4", "4NC3", "1SO2", "6MVW"],
        pro_mmgbsa: false,
        pro_mmgbsa_steps: 1000,
        gnn_precision: "fp32",
      } satisfies CasePipelineConfig;
      const report = await requestPreflight({
        smiles: ligandSmiles,
        targetPdbId: receptorPdbId,
        chain: inputs?.receptor?.chain,
        gridCenter: inputs?.grid?.center as [number, number, number] | undefined,
        gridSize: inputs?.grid?.size as [number, number, number] | undefined,
        customHotspots: inputs?.customHotspots,
        dockingEngine: inputs?.dockingEngine ?? "vina",
        exhaustiveness: inputs?.exhaustiveness ?? 8,
        numPoses: inputs?.numPoses ?? 9,
        // El protocolo declarado entra en la comprobación, así que la huella
        // que sale describe la corrida que de verdad se ejecutará.
        conformers: inputs?.conformers ?? 1,
        pipelineConfig,
      });
      setPreflightReport(report);
      notifyPreflight.current?.(summarizePreflight(report));
      // El canónico se guarda junto al texto introducido. No lo sustituye: el
      // dossier tiene que poder enseñar los dos.
      if (report.ligand.canonical_smiles) {
        notifyInputs.current?.({
          ligand: {
            inputSmiles: ligandSmiles,
            canonicalSmiles: report.ligand.canonical_smiles,
            ...(inputs?.ligand?.name ? { name: inputs.ligand.name } : {}),
          },
        });
      }
    } catch (err) {
      setPreflightError(err instanceof Error ? err.message : String(err));
    } finally {
      setPreflightLoading(false);
    }
  }, [inputs]);

  const preparationSlot = (
    <PreparationPanel
      report={preflightReport}
      summary={preflight}
      loading={preflightLoading}
      error={preflightError}
      stale={preflightStale}
      canCheck={canCheckPreparation}
      missingInputs={missingInputs}
      onCheck={() => void handleCheckPreparation()}
      conformers={inputs?.conformers ?? 1}
      // Cambiar el protocolo escribe en los INPUTS del caso, que es lo que
      // invalida el preflight guardado: el informe anterior describía otra
      // corrida. Sin eso, se podría ejecutar con K=30 un preflight comprobado
      // con K=1, y el resultado diría haber inspeccionado algo que no.
      onConformersChange={(k) => onInputsChange?.({
        conformers: k,
        pipelineConfig: {
          ...(inputs?.pipelineConfig ?? {}),
          stage_params: {
            ...(inputs?.pipelineConfig?.stage_params ?? {}),
            conformer: {
              ...(inputs?.pipelineConfig?.stage_params?.conformer ?? {}),
              conformers: k,
            },
          },
        },
      })}
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
      .then((receptores) => setTargets([...receptores]))
      .catch((err) => setError(`No se pudieron cargar los receptores: ${(err as Error).message}`))
      .finally(() => setLoadingTargets(false));
  }, []);

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
            polled.error || "El backend no devolvió el resultado persistido de la corrida.",
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
              message: "El motor local est\u00e1 terminando de arrancar. Reintentando autom\u00e1ticamente\u2026",
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
              ? "El resultado está guardado, pero tu sesión caducó. Inicia sesión de nuevo para recuperarlo."
              : statusCode === 403
                ? "El resultado está guardado, pero pertenece a otra sesión. Inicia sesión con la cuenta que ejecutó esta corrida."
                : cause instanceof Error && cause.message.startsWith("Error de conexión")
                  ? "El resultado sigue guardado, pero el motor local no está disponible. Comprueba el estado del motor y vuelve a intentarlo."
                  : `El resultado sigue referenciado por este caso, pero no se pudo recuperar: ${cause instanceof Error ? cause.message : String(cause)}`;
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
    [activeRun?.startedAt, startPolling, stopPolling],
  );

  resumeRunRef.current = resumeRun;
  // Al montar con cualquier corrida persistida se pregunta de inmediato. Para
  // una terminal, esta lectura recupera el `result` que no se guarda dentro de
  // case.json; para una viva, además reanuda el polling.
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
      // Se limpian los RESULTADOS, que pueden pertenecer a otra cuenta y cuyo
      // `molecule_id` no se puede guardar con la sesión nueva.
      setSuggestions([]);
      setProteinData(null);
      setPoseData(null);
      setIsSaved(false);
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
            ? "Tu sesión cambió. Los resultados anteriores se limpiaron para no mezclarlos con otra " +
              "cuenta, pero la corrida sigue identificada: recupera la sesión y usa «Reintentar seguimiento»."
            : "Tu sesión cambió. El resultado visible se limpió, pero la corrida terminada conserva " +
              "su identificador para poder recuperarla con la sesión correcta.",
        );
      } else {
        setTaskId(null);
        setStatus(null);
        setError("Tu sesión cambió. Los resultados anteriores se limpiaron para evitar guardar moléculas de otra cuenta.");
      }
    };
    window.addEventListener("auth_expired", handleAuthChange);
    return () => window.removeEventListener("auth_expired", handleAuthChange);
  }, [stopPolling]);

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
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async (
    _gridCenter?: [number, number, number],
    _gridSize?: [number, number, number],
    _customHotspots?: string[],
    peptideDockingEngine?: "esmfold" | "esmfold-pro" | "esmfold-experimental" | "colabfold",
    _pipelineConfig?: CasePipelineConfig
  ) => {
    // GATE. No se ejecuta nada que el preflight no haya inspeccionado. Es la
    // garantía de que la corrida corresponde exactamente a lo que se mostró:
    // sin ella, el panel podría estar describiendo unos inputs y el submit
    // enviando otros.
    const blocked = describeRunBlock(inputs, preflight);
    if (blocked) {
      setError(blocked);
      return;
    }
    const execution = preflight?.executionConfig;
    const inspectedFingerprint = preflight?.fingerprint;
    if (!execution || !inspectedFingerprint) {
      setError("Vuelve a comprobar la preparación antes de ejecutar.");
      return;
    }

    setBusy(true);
    setError(null);
    setSuggestions([]);
    stopPolling();
    setPollingInterrupted(false);
    // La corrida terminal anterior sólo se reemplaza cuando el backend entrega
    // un taskId nuevo. Si el submit falla, el caso conserva su última evidencia.
    initialRegistrationDone.current = false;
    // ANTES de la peticion: a partir de aqui hay trabajo que puede quedar
    // huerfano si se cambia de caso.
    setSubmitting(true);
    try {
      const inspectedTarget = structuralSystem?.receptor.pdbId ?? inputs?.receptor?.pdbId ?? target;
      const inspectedChain = structuralSystem?.receptor.chain ?? inputs?.receptor?.chain;
      if (!inspectedTarget || inspectedTarget.length < 4) {
        setError("Por favor, selecciona un objetivo biológico (Target) del catálogo antes de iniciar la simulación.");
        setBusy(false);
        setSubmitting(false);
        return;
      }
      // Se envía lo que el CASO tiene guardado y lo que el preflight
      // inspeccionó, no lo que traigan los argumentos del componente de
      // presentación. Si esas dos cosas pudieran diferir, el fingerprint
      // dejaría de significar nada.
      const inspectedSmiles = inputs?.ligand?.inputSmiles ?? smiles;
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
        ...(preflight?.fingerprint ? { inputFingerprint: preflight.fingerprint } : {}),
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
        registered = onRunRegistered ? await onRunRegistered(newRun) : true;
      } catch {
        // La tarea ya existe en el backend: aun si el adaptador de persistencia
        // falla de una forma inesperada, el identificador debe llegar a la UI.
        registered = false;
      }
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
          "La corrida arrancó pero su identificador no se pudo guardar en el caso. " +
            "No cierres el caso sin copiarlo o reintentar el guardado.",
        );
      }
      startPolling(result.task_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      // Se apaga sólo el flag de "enviando": si hubo `taskId`, `runActive`
      // sigue en true por el estado de la corrida.
      setSubmitting(false);
    }
  };

  const handleReset = () => {
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
    setIsSaved(false);
  };

  const handleCancel = async () => {
    if (!taskId) return;

    // Cancela únicamente esta tarea y sus subprocesses auxiliares registrados.
    try {
      const result = await cancelEvaluation(taskId);
      if (!result.cancelled) {
        // El proceso pudo terminar o desaparecer entre el ultimo poll y este
        // clic. Reconciliar inmediatamente evita dejar la UI en EJECUTANDO con
        // un boton de cancelar que ya no puede actuar sobre nada.
        await resumeRun(
          taskId,
          activeRun?.executionState === "completed",
          activeRun?.moleculeId,
        );
        setError(
          "La tarea ya no estaba activa. Actualizamos su estado con el backend.",
        );
        return;
      }
    } catch (e) {
      console.error("Error cancelando evaluación:", e);
      stopPolling();
      setPollingInterrupted(true);
      setError(
        `No se pudo confirmar la cancelación: ${(e as Error).message}. ` +
          "El caso fue liberado; puedes reintentar el seguimiento más tarde.",
      );
      return;
    }
    stopPolling();
    setPollingInterrupted(false);
    cancelledTaskRef.current = taskId;
    isTerminalRef.current = true;
    setStatus((prev) =>
      prev
        ? { ...prev, status: "FAILURE", error: "Cancelado por el usuario" }
        : prev
    );
    // Cancelar termina el trabajo, pero conserva su identidad como parte del
    // historial mínimo del caso. `cancelled` no bloquea y el caso pasa a review.
    notifyActiveRun.current?.({
      taskId,
      ...(activeRun?.moleculeId ? { moleculeId: activeRun.moleculeId } : {}),
      executionState: "cancelled",
      startedAt: status?.started_at ?? activeRun?.startedAt ?? new Date().toISOString(),
      ...(runFingerprintRef.current
        ? { inputFingerprint: runFingerprintRef.current }
        : {}),
      ...(typeof status?.progress === "number" ? { lastKnownProgress: status.progress } : {}),
      lastError: "Cancelado por el usuario",
    });
    setBusy(false);
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
      setError((e as Error).message);
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

  return (
    <div className="flex h-full min-h-0 flex-col">
      {pollingInterrupted && taskId && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs leading-relaxed text-amber-200"
        >
          <span className="min-w-0 flex-1">
            {isTerminal ? (
              <>El resultado visible se limpió al cambiar de sesión. La corrida terminada conserva su identificador; vuelve a autenticarte para recuperarla.</>
            ) : (
              <>Se perdió la conexión con el servidor de evaluación. <strong>No se sabe cómo terminó la tarea</strong>: puede seguir corriendo. Su identificador se ha conservado.</>
            )}
          </span>
          <button
            type="button"
            onClick={() => void resumeRun(taskId, activeRun?.executionState === "completed", activeRun?.moleculeId)}
            className="shrink-0 whitespace-nowrap rounded border border-amber-500/40 px-2 py-0.5 text-[11px] hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            Reintentar seguimiento
          </button>
        </div>
      )}
      <div className="min-h-0 flex-1">
      <ProEvaluation
      smiles={smiles}
      setSmiles={(next) => {
        setSmiles(next);
        // Se persiste lo que la persona escribe, tal cual. El canónico llega
        // después, con el preflight; escribirlo aquí sería inventarlo.
        notifyInputs.current?.({
          ligand: { inputSmiles: next },
        });
      }}
      target={target}
      setTarget={(next) => {
        if (structuralSystem) {
          setError(
            "El receptor está fijado por la primera corrida de este caso. " +
              "Crea otro caso para evaluar un sistema estructural distinto.",
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
          customHotspots: [],
        });
      }}
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
          setError("Inicia sesión para guardar moléculas en tu MolDex. El guardado requiere una cuenta para asociar la molécula a tu perfil.");
          return;
        }
        try {
          await saveMolecule(status.result.molecule_id, customName);
          setIsSaved(true);
          playSound("bloom");
          // Notificar a /moldex (y a cualquier otra ruta keep-alive) que la
          // biblioteca cambió. Sin esto, navegar a /moldex tras guardar puede
          // mostrar la lista stale si el efecto keep-alive no dispara a tiempo
          // o si el POST todavía no commiteó cuando el efecto ya corrió.
          // El CustomEvent viaja por `window` y cruza el árbol de providers
          // keep-alive sin necesidad de un Context compartido.
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("moldex:invalidated", {
              detail: { moleculeId: status.result.molecule_id },
            }));
          }
        } catch (e) {
          const msg = (e as Error).message;
          if (msg.includes("401") || msg.includes("403") || msg.includes("No autenticado") || msg.includes("token")) {
            setError("Inicia sesión para guardar moléculas en tu MolDex. Tu sesión expiró o no está activa.");
          } else if (msg.includes("404") || msg.toLowerCase().includes("no encontrada") || msg.toLowerCase().includes("no encontrad")) {
            // La molécula existe pero pertenece a otra cuenta (el backend
            // devuelve 404 "Molécula no encontrada" para no revelar existencia),
            // o la sesión cambió (invitado ↔ cuenta personal) entre evaluación
            // y guardado. Mensaje claro y profesional en lugar del crudo.
            setError("Esta molécula pertenece a otra cuenta. Inicia sesión con la cuenta con la que la evaluaste para guardarla en tu MolDex.");
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
          await downloadCertificate(status.result.molecule_id, "evaluation");
        } catch (e) {
          setError(`No se pudo descargar el certificado: ${(e as Error).message}`);
        }
      }}
      handleDownloadComplex={async () => {
        if (!status?.result?.molecule_id) return;
        try {
          await downloadComplexFile(status.result.molecule_id, "evaluation");
        } catch (e) {
          setError(`No se pudo descargar el complejo: ${(e as Error).message}`);
        }
      }}
      handleValidate={handleValidate}
      handleSubmit={handleSubmit}
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
          pipelineConfig: config.pipelineConfig,
        });
      }}
      />
      </div>
    </div>
  );
}
