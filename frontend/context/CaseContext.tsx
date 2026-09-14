"use client";

// =====================================================================
// CaseContext — el caso activo, su guardado y el guard de corridas
// =====================================================================
//
// Un solo proveedor por encima del workspace. Elige el repositorio segun el
// runtime UNA vez y no vuelve a preguntarlo: si la decision se tomara en cada
// componente, el fallback web se degradaria por accidente.
//
// TRES INVARIANTES QUE ESTE CONTEXTO HACE CUMPLIR:
//
// 1. AISLAMIENTO. `activeCase.id` es la clave de React del runner. Al cambiar
//    de caso el subarbol se desmonta y se monta de cero, asi que no puede haber
//    contaminacion de SMILES, receptor o resultado entre casos.
//
// 2. NADA REEMPLAZA EL CASO ACTIVO CON TRABAJO VIVO. El guard esta AQUI, no en
//    cada boton: `create`, `select`, `open`, `initialize` y `close` pasan todas
//    por `guardAgainstLiveWork`. Poner el guard en la UI dejaria abierta
//    cualquier ruta nueva que alguien anada manana.
//
// 3. NINGUN GUARDADO SE PIERDE NI SE APLICA FUERA DE ORDEN. La cola por caso
//    (`CaseSaveQueue`) serializa las escrituras y descarta las respuestas
//    viejas; toda operacion que cambie de caso DRENA antes.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { createBrowserCaseRepository } from "../lib/cases/browserCaseRepository";
import { createTauriCaseRepository } from "../lib/cases/tauriCaseRepository";
import {
  isTauriAvailable,
  type CaseRepository,
  type OpenFolderOutcome,
  type RegistryHealth,
} from "../lib/cases/repository";
import { CaseSaveQueue, type SaveOutcome } from "../lib/cases/saveQueue";
import { caseWithRun, touchCase } from "../lib/cases/schema";
import {
  CaseError,
  hasCompletedRun,
  inputsForStructuralSystem,
  latestRun,
  isRunBlocking,
  runMatchesInputs,
  structuralSystemFromRun,
  structuralSystemIsSealed,
  type ActiveRun,
  type CaseContext as CaseContextData,
  type CaseIndexEntry,
  type CaseInputs,
  type CaseRecord,
  type CaseRun,
  type CaseDispositionKind,
  type CaseStudyKind,
  type CaseView,
  type HumanDecision,
  type PreflightSummary,
} from "../lib/cases/types";
import { inputsAffectRun } from "../lib/preflight";
import { getJobStatus } from "../lib/api";

export type SaveState = "idle" | "saving" | "saved" | "error";

/** Trabajo vivo que impide reemplazar el caso activo. */
export interface LiveWork {
  /** Corrida de evaluacion: desde ANTES de enviar hasta el estado terminal. */
  readonly evaluation: boolean;
  /** MM-GBSA u otro calculo asincrono largo. */
  readonly analysis: boolean;
  /** Identificador de la tarea, si ya se conoce. Se persiste en el caso. */
  readonly taskId: string | null;
}

const NO_WORK: LiveWork = { evaluation: false, analysis: false, taskId: null };

export interface CaseContextValue {
  readonly repository: CaseRepository;
  readonly cases: readonly CaseIndexEntry[];
  readonly activeCase: CaseRecord | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly saveState: SaveState;
  readonly liveWork: LiveWork;
  /** `true` si hay CUALQUIER trabajo vivo. Es el guard de toda la UI. */
  readonly hasLiveWork: boolean;
  /** Cómo se cargó el índice. `null` mientras no se sabe. */
  readonly registryHealth: RegistryHealth | null;

  createCase(name: string, studyKind: CaseStudyKind, parentDirectory?: string): Promise<CaseRecord | null>;
  selectCase(id: string): Promise<void>;
  closeCase(): Promise<void>;
  updateContext(patch: Partial<CaseContextData>): void;
  /**
   * Cambia el modo abierto y lo persiste.
   *
   * Se guarda para poder RESTAURARLO al reabrir. Restaurar «Informe» sólo es
   * legítimo si el resultado se puede recuperar de verdad; esa comprobación no
   * vive aquí, sino en el workspace, que es quien sabe si hay evidencia.
   */
  setActiveView(view: CaseView): void;
  /**
   * Fija receptor, ligando y configuración de la corrida.
   *
   * **Invalida el preflight anterior** en cuanto algo que pueda cambiar la
   * corrida cambia. Es la única puerta por la que entran los inputs, y por eso
   * es el único sitio donde tiene que vivir esa regla: si la invalidación
   * viviera en la interfaz, cualquier ruta nueva podría dejar un preflight
   * describiendo una hipótesis que ya no existe.
   */
  setInputs(patch: Partial<CaseInputs>): void;
  /** Guarda el resumen del último preflight generado para estos inputs. */
  setPreflight(summary: PreflightSummary): void;
  /**
   * Registra que una persona vio una advertencia y siguió adelante.
   *
   * No desbloquea nada: los bloqueantes son fallos técnicos y no se negocian.
   * Queda atada al fingerprint para que no se herede a otra hipótesis.
   */
  recordDecision(controlCode: string, fingerprint: string, note?: string): void;
  /** Cierra el caso con una disposición científica explícita y justificada. */
  setDisposition(kind: CaseDispositionKind, rationale: string): boolean;
  setArchived(id: string, archived: boolean): Promise<void>;
  forgetCase(id: string): Promise<void>;
  relocateCase(id: string): Promise<void>;
  /** Restaura el manifiesto desde su copia. Sólo donde el repositorio puede. */
  repairCase(id: string): Promise<void>;
  /** Confirma que el caso vive ahora en la carpeta recién elegida. */
  acceptRelocation(token: string, expectedCaseId: string): Promise<void>;
  /** `true` si el repositorio sabe restaurar desde copia de seguridad. */
  readonly canRepair: boolean;
  openExistingFolder(): Promise<OpenFolderOutcome>;
  initializeFolder(path: string, name: string, studyKind: CaseStudyKind): Promise<CaseRecord | null>;
  revealInFileManager(id: string): Promise<void>;
  /** Lo llama el runner para el trabajo que NO se persiste (MM-GBSA). */
  setLiveWork(patch: Partial<LiveWork>): void;
  /**
   * Escribe o actualiza una corrida en el LIBRO del caso activo.
   *
   * `null` significa que esta superficie dejó de seguir una tarea; no retira
   * nada del libro. Los estados terminales se conservan: dejan de bloquear,
   * pero siguen siendo el vínculo para recuperar su informe.
   */
  setActiveRun(run: CaseRun | null): void;
  /**
   * Persiste la corrida y ESPERA a que llegue al repositorio.
   *
   * Es para el instante en que nace el `taskId`. El autosave con debounce no
   * sirve ahí: entre encolar y escribir hay 600 ms, y si la ventana se cierra
   * en esa ventana la tarea queda viva en el backend sin que nada la registre.
   * Devuelve `false` si NO se pudo escribir.
   */
  registerRun(run: CaseRun): Promise<boolean>;
  /** Corrida cuyo registro no llegó a disco. Bloquea y ofrece reintentar. */
  readonly unregisteredRun: CaseRun | null;
  retryRegisterRun(): Promise<boolean>;
  retrySave(): Promise<void>;
  refresh(): Promise<void>;
  dismissError(): void;
}

const CaseWorkspaceContext = createContext<CaseContextValue | null>(null);
/**
 * Un caso puede no tener ligando todavía, pero nunca debe persistir un objeto
 * `ligand` parcial o vacío: ese estado no representa una hipótesis y Rust lo
 * rechaza correctamente. Se conserva el resto de los inputs y se omite sólo el
 * ligando hasta que exista un SMILES no vacío.
 */
function inputsReadyForPersistence(inputs: CaseInputs): CaseInputs {
  const smiles = inputs.ligand?.inputSmiles;
  if (!inputs.ligand || (typeof smiles === "string" && smiles.trim().length > 0)) {
    return inputs;
  }
  const { ligand: _invalidLigand, ...rest } = inputs;
  return rest;
}

export const AUTOSAVE_DELAY_MS = 600;

export const LIVE_WORK_MESSAGE =
  "Hay trabajo en curso en este caso. Espera a que termine o cancélalo antes de cambiar de caso: cambiar ahora dejaría la ejecución sin seguimiento.";

export function CaseProvider({
  children,
  repository: injected,
  ownerUserId,
  autosaveDelayMs = AUTOSAVE_DELAY_MS,
}: {
  children: ReactNode;
  /** Inyectable para tests. En produccion se elige por runtime. */
  repository?: CaseRepository;
  /** Identidad de la sesión que posee y puede ver estos casos. */
  ownerUserId?: string;
  /** Inyectable para tests: un debounce de 0 hace el guardado observable. */
  autosaveDelayMs?: number;
}) {
  const [repository] = useState<CaseRepository>(
    () => {
      if (injected) return injected;
      if (!ownerUserId) {
        throw new Error("CaseProvider requiere una sesión autenticada.");
      }
      if (!isTauriAvailable()) return createBrowserCaseRepository(ownerUserId);
      return createTauriCaseRepository({
        ownerUserId,
        // Los manifiestos anteriores a v6 no tenían propietario. Sólo se
        // reclaman cuando el backend reconoce la tarea con la sesión actual;
        // un 401/403/404 mantiene el caso invisible y evita cruces de cuentas.
        canClaimLegacyCase: async (record) => {
          const taskId = record.activeRun?.taskId;
          if (!taskId) return false;
          try {
            await getJobStatus(taskId);
            return true;
          } catch {
            return false;
          }
        },
      });
    },
  );
  const [cases, setCases] = useState<readonly CaseIndexEntry[]>([]);
  const [activeCase, setActiveCase] = useState<CaseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [liveWork, setLiveWorkState] = useState<LiveWork>(NO_WORK);
  const [registryHealth, setRegistryHealth] = useState<RegistryHealth | null>(null);
  /**
   * Corrida cuyo `taskId` existe pero cuyo registro NO llegó a disco.
   *
   * Se conserva EN MEMORIA a propósito: el identificador es lo único que
   * permite volver a encontrar la tarea, así que perderlo por un fallo de
   * escritura sería el peor desenlace posible. Bloquea el cambio de caso y se
   * puede reintentar o copiar.
   */
  const [unregisteredRun, setUnregisteredRun] = useState<CaseRun | null>(null);

  const mounted = useRef(true);
  const activeCaseRef = useRef<CaseRecord | null>(null);
  activeCaseRef.current = activeCase;
  const liveWorkRef = useRef<LiveWork>(NO_WORK);
  liveWorkRef.current = liveWork;
  // The save queue owns its callback lifetime. Keep the current recovery run
  // in a ref so a later successful write can prove that its taskId is durable.
  const unregisteredRunRef = useRef<ActiveRun | null>(null);
  unregisteredRunRef.current = unregisteredRun;

  const describeError = useCallback((err: unknown): string => {
    if (err instanceof CaseError) {
      return err.detail ? `${err.message} (${err.detail})` : err.message;
    }
    return err instanceof Error ? err.message : String(err);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const list = await repository.listCases();
      if (mounted.current) setCases(list);
    } catch (err) {
      if (mounted.current) setError(describeError(err));
    }
  }, [repository, describeError]);

  // ── Cola de guardado ────────────────────────────────────────────────
  const onOutcome = useCallback(
    (caseId: string, outcome: SaveOutcome) => {
      if (!mounted.current) return;
      if (outcome.kind === "saved") {
        // A later write can recover a task whose initial critical write failed.
        // Only clear the guard when the record that reached disk contains that
        // exact taskId; saving an unrelated edit is not evidence of recovery.
        const pendingRun = unregisteredRunRef.current;
        if (pendingRun && outcome.record.activeRun?.taskId === pendingRun.taskId) {
          setUnregisteredRun(null);
          if (activeCaseRef.current?.id === caseId) setError(null);
        }
        // Solo se refleja si sigue siendo el caso en pantalla: una respuesta de
        // otro caso no debe tocar el estado visible.
        setActiveCase((current) =>
          current && current.id === caseId && current.updatedAt <= outcome.record.updatedAt
            ? outcome.record
            : current,
        );
        if (activeCaseRef.current?.id === caseId) setSaveState("saved");
        void refresh();
      } else if (outcome.kind === "failed") {
        if (activeCaseRef.current?.id === caseId) setSaveState("error");
        setError(
          `${describeError(outcome.error)} El cambio no se ha perdido: puedes reintentar.`,
        );
      }
      // `superseded` no toca nada a proposito: llego tarde y ya hay algo mas
      // nuevo aplicado.
    },
    [refresh, describeError],
  );

  const queueRef = useRef<CaseSaveQueue | null>(null);
  if (queueRef.current === null) {
    queueRef.current = new CaseSaveQueue({
      write: (record) => repository.updateCase(record),
      delayMs: autosaveDelayMs,
      onOutcome,
    });
  }
  const queue = queueRef.current;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      // Al desmontar se intenta volcar lo pendiente. No se puede esperar en un
      // cleanup, pero al menos se dispara en vez de descartarse.
      void queue.drainAll();
    };
  }, [queue]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await repository.listCases();
        if (!cancelled && mounted.current) setCases(list);
      } catch (err) {
        if (!cancelled && mounted.current) setError(describeError(err));
      } finally {
        if (!cancelled && mounted.current) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [repository, describeError]);

  // La salud del índice se CONSUME, no sólo se expone. Un registro corrupto
  // produce una lista vacía idéntica a la de un primer arranque, y presentarla
  // como estado sano es exactamente el fallo que hay que evitar.
  useEffect(() => {
    if (!repository.registryHealth) {
      setRegistryHealth({ state: "ok" });
      return;
    }
    let cancelled = false;
    void repository
      .registryHealth()
      .then((health) => {
        if (cancelled || !mounted.current) return;
        setRegistryHealth(health);
        if (health.state === "corrupted") {
          setError(
            "El índice de casos no se pudo leer y tampoco su copia de seguridad. " +
              "La lista puede estar incompleta: usa «Abrir carpeta existente» para recuperar " +
              `tus casos antes de crear otros. (${health.detail})`,
          );
        } else if (health.state === "recovered_from_backup") {
          setError(
            "El índice de casos se recuperó de su copia de seguridad. " +
              "Puede faltar algún caso reciente; ábrelo por carpeta si no aparece.",
          );
        }
      })
      .catch(() => {
        if (!cancelled && mounted.current) setRegistryHealth({ state: "ok" });
      });
    return () => {
      cancelled = true;
    };
  }, [repository]);

  // ── Guard de trabajo vivo ───────────────────────────────────────────
  //
  // Incluye la corrida PERSISTIDA del caso abierto desde el instante en que se
  // abre, sin esperar a que nadie visite Evaluar. Antes sólo contaba lo que el
  // runner declaraba, así que un caso reabierto con una corrida viva se podía
  // abandonar antes de montar el runner: la tarea seguía en el backend y el
  // usuario cambiaba de caso sin que nada se lo impidiera.
  //
  // También cuenta una corrida cuyo registro falló: su `taskId` sólo existe en
  // memoria y cerrar el caso lo perdería.
  const persistedRunLive =
    activeCase?.activeRun !== undefined && isRunBlocking(activeCase.activeRun.executionState);
  const hasLiveWork =
    liveWork.evaluation || liveWork.analysis || persistedRunLive || unregisteredRun !== null;

  /**
   * Puerta unica. Devuelve `true` si la operacion puede continuar.
   *
   * Centralizarlo aqui es lo que impide que una ruta nueva se salte el guard:
   * cualquier operacion que reemplace el caso activo tiene que pasar por esta
   * funcion, y la que no pase se detecta en revision.
   */
  const hasLiveWorkRef = useRef(false);
  hasLiveWorkRef.current = hasLiveWork;

  const guardAgainstLiveWork = useCallback((): boolean => {
    if (hasLiveWorkRef.current) {
      setError(LIVE_WORK_MESSAGE);
      return false;
    }
    return true;
  }, []);

  /**
   * Drena el guardado del caso activo antes de reemplazarlo.
   *
   * Devuelve `false` si NO se pudo guardar. Quien llama debe abortar: seguir
   * adelante dejaria el borrador en una cola que ya nadie mira, con el caso
   * saliente fuera de pantalla y el texto perdido de hecho aunque siga en
   * memoria. El error NO se limpia — el usuario tiene que poder reintentar.
   */
  const drainActive = useCallback(async (): Promise<boolean> => {
    const current = activeCaseRef.current;
    if (!current) return true;
    const result = await queue.drain(current.id);
    if (!result.ok) {
      if (mounted.current) {
        setSaveState("error");
        setError(
          "No se pudo guardar el cambio pendiente, así que la operación se ha cancelado. " +
            "El caso y su texto siguen aquí: usa «Reintentar».",
        );
      }
      return false;
    }
    return true;
  }, [queue]);

  // ── Operaciones ─────────────────────────────────────────────────────

  const createCase = useCallback(
    async (name: string, studyKind: CaseStudyKind, parentDirectory?: string) => {
      if (!guardAgainstLiveWork()) return null;
      if (!(await drainActive())) return null;
      try {
        const record = await repository.createCase({ name, studyKind, parentDirectory });
        if (mounted.current) {
          setActiveCase(record);
          setError(null);
          setSaveState("idle");
        }
        await refresh();
        return record;
      } catch (err) {
        if (mounted.current) setError(describeError(err));
        throw err;
      }
    },
    [repository, refresh, guardAgainstLiveWork, drainActive, describeError],
  );

  const selectCase = useCallback(
    async (id: string) => {
      if (activeCaseRef.current?.id === id) return;
      if (!guardAgainstLiveWork()) return;
      if (!(await drainActive())) return;
      try {
        const record = await repository.openCase(id);
        if (!mounted.current) return;
        setActiveCase(record);
        setError(null);
        setSaveState("idle");
        void refresh();
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, refresh, guardAgainstLiveWork, drainActive, describeError],
  );

  const closeCase = useCallback(async () => {
    if (!guardAgainstLiveWork()) return;
    if (!(await drainActive())) return;
    if (mounted.current) setActiveCase(null);
  }, [guardAgainstLiveWork, drainActive]);

  const updateContext = useCallback(
    (patch: Partial<CaseContextData>) => {
      setActiveCase((current) => {
        if (!current) return current;
        const next = touchCase(current, { context: { ...current.context, ...patch } });
        queue.enqueue(next);
        setSaveState("saving");
        return next;
      });
    },
    [queue],
  );

  const setActiveView = useCallback(
    (view: CaseView) => {
      setActiveCase((current) => {
        if (!current || current.activeView === view) return current;
        const next = touchCase(current, { activeView: view });
        queue.enqueue(next);
        setSaveState("saving");
        return next;
      });
    },
    [queue],
  );

  const setInputs = useCallback(
    (patch: Partial<CaseInputs>) => {
      setActiveCase((current) => {
        if (!current) return current;
        const requestedInputs = inputsReadyForPersistence({ ...current.inputs, ...patch });
        // Una vez que una corrida TERMINÓ en este sistema, receptor, caja y
        // residuos dejan de ser controles editables. La UI los bloquea, pero
        // esta frontera también protege contra rutas futuras o llamadas
        // directas: un caso no puede cambiar de sistema por accidente.
        //
        // El protocolo NO se restituye. Ver `inputsForStructuralSystem`: motor,
        // exhaustiveness, poses y confórmeros son esfuerzo de muestreo, cada
        // corrida sella el suyo y el libro enseña cuál se salió del protocolo
        // del caso. Congelarlos obligaba a crear un caso nuevo para repetir un
        // ligando con más muestreo, y eso no protegía ninguna comparación.
        const sealed = structuralSystemIsSealed(current);
        const nextInputs = sealed && current.structuralSystem
          ? inputsForStructuralSystem(current.structuralSystem, requestedInputs)
          : requestedInputs;
        if (sealed && JSON.stringify(nextInputs) !== JSON.stringify(requestedInputs)) {
          setError(
            "Este caso ya está fijado a su sistema estructural. Puedes cambiar el ligando y el " +
              "protocolo; para cambiar receptor, caja o residuos crea otro caso.",
          );
        }
        const invalidates = inputsAffectRun(current.inputs, nextInputs);
        if (!invalidates && JSON.stringify(nextInputs) === JSON.stringify(current.inputs ?? {})) {
          // Nada cambió: no se encola una escritura inútil ni se toca el
          // preflight vigente.
          return current;
        }
        const next = touchCase(current, {
          inputs: nextInputs,
          ...(invalidates && (current.status === "completed" || current.status === "abstained")
            ? { status: "review" as const }
            : {}),
        });
        // El preflight describe unos inputs concretos. Si cambian, deja de
        // describir nada: se retira. La corrida guardada NO se toca — sigue
        // siendo historia del caso, sólo que de otra hipótesis.
        const withPreflight: CaseRecord = invalidates
          ? (() => {
              const { preflight: _drop, disposition: _oldDisposition, ...rest } = next;
              return rest as CaseRecord;
            })()
          : next;
        queue.enqueue(withPreflight);
        setSaveState("saving");
        return withPreflight;
      });
    },
    [queue],
  );

  const setPreflight = useCallback(
    (summary: PreflightSummary) => {
      setActiveCase((current) => {
        if (!current) return current;
        const next = touchCase(current, { preflight: summary });
        queue.enqueue(next);
        setSaveState("saving");
        return next;
      });
    },
    [queue],
  );

  const recordDecision = useCallback(
    (controlCode: string, fingerprint: string, note?: string) => {
      setActiveCase((current) => {
        if (!current) return current;
        const previous = current.decisions ?? [];
        // Una decisión por control y fingerprint: repetirla la actualiza, no
        // la duplica.
        const others = previous.filter(
          (d) => !(d.controlCode === controlCode && d.fingerprint === fingerprint),
        );
        const decision: HumanDecision = {
          controlCode,
          fingerprint,
          decision: "reconocida",
          at: new Date().toISOString(),
          ...(note ? { note } : {}),
        };
        const next = touchCase(current, { decisions: [...others, decision] });
        queue.enqueue(next);
        setSaveState("saving");
        return next;
      });
    },
    [queue],
  );

  const setDisposition = useCallback(
    (kind: CaseDispositionKind, rationale: string): boolean => {
      const trimmed = rationale.trim();
      const current = activeCaseRef.current;
      const fingerprint = current?.activeRun?.inputFingerprint ?? current?.preflight?.fingerprint;
      if (!current || !fingerprint) {
        setError("No se puede cerrar el caso sin una corrida vinculada a una huella de inputs.");
        return false;
      }
      if (kind !== "abstain" && runMatchesInputs(current.activeRun, current.preflight?.fingerprint ?? null) !== "corresponde") {
        setError("La evidencia no corresponde a los inputs actuales; sólo se puede registrar una abstención.");
        return false;
      }
      if (trimmed.length < 3) {
        setError("Escribe una justificación breve antes de cerrar el caso.");
        return false;
      }
      const next = touchCase(current, {
        status: kind === "abstain" ? "abstained" : "completed",
        disposition: {
          kind,
          rationale: trimmed,
          fingerprint,
          at: new Date().toISOString(),
        },
      });
      setActiveCase(next);
      queue.enqueue(next);
      setSaveState("saving");
      return true;
    },
    [queue],
  );

  const setArchived = useCallback(
    async (id: string, archived: boolean) => {
      // Archivar entra en la MISMA secuencia de escrituras: si hubiera un
      // cambio de contexto pendiente, archivar antes de drenarlo lo perdería.
      const drained = await queue.drain(id);
      if (!drained.ok) {
        setSaveState("error");
        setError(
          "No se pudo guardar el cambio pendiente, así que no se ha archivado. Usa «Reintentar».",
        );
        return;
      }
      try {
        const updated = await repository.setArchived(id, archived);
        if (mounted.current) {
          setActiveCase((current) => (current && current.id === id ? updated : current));
        }
        await refresh();
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, refresh, queue, describeError],
  );

  const forgetCase = useCallback(
    async (id: string) => {
      if (activeCaseRef.current?.id === id && !guardAgainstLiveWork()) return;
      // Un caso NO DISPONIBLE puede tener un drenaje que nunca va a funcionar
      // —su carpeta ya no existe—, así que aquí el fallo del drenaje no aborta:
      // retirar del índice es precisamente la salida para ese caso. Lo que sí
      // se hace es no perder el error de vista.
      const drained = await queue.drain(id);
      if (!drained.ok && mounted.current) {
        setError(
          "Se retira del índice un caso con cambios sin guardar. Su contenido en disco no se toca.",
        );
      }
      try {
        await repository.forgetCase(id);
        if (mounted.current && activeCaseRef.current?.id === id) setActiveCase(null);
        await refresh();
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, refresh, queue, guardAgainstLiveWork, describeError],
  );

  /**
   * Reparar de VERDAD: restaura `case.json` desde su copia de seguridad.
   *
   * Antes esto llamaba a `retrySave()` del caso ACTIVO, que no tiene nada que
   * ver con el caso roto que se estaba intentando reparar: reintentaba escribir
   * otro caso distinto y dejaba el corrupto igual de corrupto.
   */
  const repairCase = useCallback(
    async (id: string) => {
      if (!repository.repairCase) {
        setError("Este almacenamiento no guarda copias de seguridad, así que no hay nada que restaurar.");
        return;
      }
      try {
        const record = await repository.repairCase(id);
        if (mounted.current) {
          setActiveCase((current) => (current && current.id === id ? record : current));
          setError(
            "El caso se ha restaurado desde su copia de seguridad. Revisa si falta algún cambio reciente.",
          );
        }
        await refresh();
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, refresh, describeError],
  );

  const acceptRelocation = useCallback(
    async (token: string, expectedCaseId: string) => {
      if (!repository.acceptRelocation) return;
      try {
        // El id esperado viaja a Rust, que comprueba el manifiesto ANTES de
        // tocar el registro. Confirmar sin decir qué caso se esperaba sería
        // «acepta lo que haya ahí».
        const record = await repository.acceptRelocation(token, expectedCaseId);
        if (mounted.current) {
          setActiveCase(record);
          setError(null);
        }
        await refresh();
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, refresh, describeError],
  );

  const relocateCase = useCallback(
    async (id: string) => {
      if (!repository.relocateCase) {
        setError("Relocalizar una carpeta requiere la aplicación de escritorio.");
        return;
      }
      if (!guardAgainstLiveWork()) return;
      if (!(await drainActive())) return;
      try {
        const outcome = await repository.relocateCase(id);
        if (outcome.kind === "opened" && mounted.current) {
          setActiveCase(outcome.record);
          setError(null);
        } else if (outcome.kind === "empty" && mounted.current) {
          setError("Esa carpeta no contiene un caso. No se ha importado nada.");
        }
        await refresh();
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, refresh, guardAgainstLiveWork, drainActive, describeError],
  );

  const openExistingFolder = useCallback(async (): Promise<OpenFolderOutcome> => {
    if (!repository.openExistingFolder) return { kind: "cancelled" };
    if (!guardAgainstLiveWork()) return { kind: "cancelled" };
    if (!(await drainActive())) return { kind: "cancelled" };
    try {
      const outcome = await repository.openExistingFolder();
      if (outcome.kind === "opened" && mounted.current) {
        setActiveCase(outcome.record);
        setError(null);
        void refresh();
      }
      return outcome;
    } catch (err) {
      // Todos los errores de abrir se presentan; antes se perdían.
      if (mounted.current) setError(describeError(err));
      return { kind: "cancelled" };
    }
  }, [repository, refresh, guardAgainstLiveWork, drainActive, describeError]);

  const initializeFolder = useCallback(
    async (path: string, name: string, studyKind: CaseStudyKind) => {
      if (!repository.initializeFolder) {
        setError("Este entorno no puede inicializar carpetas.");
        return null;
      }
      if (!guardAgainstLiveWork()) return null;
      if (!(await drainActive())) return null;
      try {
        const record = await repository.initializeFolder(path, name, studyKind);
        if (mounted.current) {
          setActiveCase(record);
          setError(null);
        }
        await refresh();
        return record;
      } catch (err) {
        if (mounted.current) setError(describeError(err));
        return null;
      }
    },
    [repository, refresh, guardAgainstLiveWork, drainActive, describeError],
  );

  const revealInFileManager = useCallback(
    async (id: string) => {
      if (!repository.revealInFileManager) return;
      try {
        await repository.revealInFileManager(id);
      } catch (err) {
        if (mounted.current) setError(describeError(err));
      }
    },
    [repository, describeError],
  );

  const setLiveWork = useCallback((patch: Partial<LiveWork>) => {
    setLiveWorkState((current) => ({ ...current, ...patch }));
  }, []);

  /**
   * Escribe `activeRun` en el manifiesto y mantiene coherente el estado
   * científico del caso.
   *
   * DOS REGLAS QUE NO SE PUEDEN SALTAR:
   *
   * · Mientras hay corrida no terminal, `CaseStatus` es `running`.
   * · Al cerrarla, `running` pasa a `review` — NUNCA se queda atrapado. Un
   *   cálculo que termina no completa un caso: lo deja pendiente de que una
   *   persona lo mire (docs/53 §4). Si el caso no estaba en `running`, no se
   *   toca: el usuario pudo haberlo marcado a mano.
   */
  const setActiveRun = useCallback(
    (run: CaseRun | null) => {
      setActiveCase((current) => {
        if (!current) return current;
        const wasRunning = current.status === "running";
        const live = run !== null && isRunBlocking(run.executionState);
        const status = live ? "running" : wasRunning ? "review" : current.status;

        // `null` significa «esta superficie no está siguiendo ninguna tarea»,
        // NO «este caso no ha corrido nada». El libro no pierde filas por eso:
        // una corrida se deja de seguir muchas veces —al recargar, al cambiar
        // de vista— y cada una de ellas borraba antes el único puntero que
        // quedaba a su informe.
        //
        // Pero una fila que se queda en `running` para siempre bloquearía el
        // caso para siempre, así que se mueve a `interrupted`, que es el estado
        // que existe exactamente para esto: dice lo único cierto —que no
        // sabemos cómo acabó— y conserva el `taskId` para volver a preguntar.
        // Marcarla `failed` sería una afirmación sobre el backend que nadie ha
        // comprobado, y dejarla `running` sería fingir que sigue viva.
        const abandoned = run === null ? latestRun(current.runs) : undefined;
        const withRun: CaseRecord = run
          ? caseWithRun(current, run)
          : abandoned && isRunBlocking(abandoned.executionState)
            ? caseWithRun(current, { ...abandoned, executionState: "interrupted" })
            : touchCase(current, { status });
        const next: CaseRecord = { ...withRun, status };
        // Si nada cambió, no se encola una escritura inútil.
        if (
          JSON.stringify(next.runs) === JSON.stringify(current.runs)
          && next.status === current.status
        ) {
          return current;
        }
        queue.enqueue(next);
        return next;
      });
      setLiveWorkState((current) => ({
        ...current,
        taskId: run?.taskId ?? null,
        evaluation: run !== null && isRunBlocking(run.executionState),
      }));
    },
    [queue],
  );

  /**
   * Escribe la corrida y DRENA de inmediato, sin pasar por el debounce.
   *
   * Devuelve `false` si la escritura falla. El llamador —el runner— no debe
   * declarar la corrida registrada ni soltar su estado `submitting` hasta que
   * esto confirme.
   */
  const registerRun = useCallback(
    async (run: CaseRun): Promise<boolean> => {
      const current = activeCaseRef.current;
      if (!current) return false;

      // El taskId es el momento correcto para ESCRIBIR el sistema: es el único
      // instante en que la huella y la configuración efectiva son las de esta
      // corrida. No es el momento de SELLARLO —eso lo hace la primera corrida
      // que termina, ver `structuralSystemIsSealed`—, así que mientras ninguna
      // haya terminado el sistema se reescribe con el de la corrida nueva. Sin
      // esto, una primera corrida fallida casaba el caso para siempre con una
      // configuración que nunca produjo nada.
      const newSystem = hasCompletedRun(current.runs)
        ? null
        : structuralSystemFromRun(current.inputs, current.preflight, run);
      const next = touchCase(caseWithRun(current, run), {
        status: "running",
        ...(newSystem
          ? {
              structuralSystem: newSystem,
            }
          : {}),
      });
      setActiveCase(next);
      setLiveWorkState((w) => ({ ...w, evaluation: true, taskId: run.taskId }));
      queue.enqueue(next);
      const result = await queue.drain(current.id);
      if (!mounted.current) return result.ok;
      if (!result.ok) {
        // El taskId NO se pierde: se guarda en memoria para poder reintentar o
        // copiarlo. Sin él, la tarea seguiría corriendo sin dueño.
        setUnregisteredRun(run);
        setSaveState("error");
        setError(
          "La corrida arrancó pero su identificador no se pudo guardar en el caso. " +
            "Se conserva en memoria: reintenta o cópialo antes de cerrar.",
        );
        return false;
      }
      setUnregisteredRun(null);
      setSaveState("saved");
      void refresh();
      return true;
    },
    [queue, refresh],
  );

  const retryRegisterRun = useCallback(async (): Promise<boolean> => {
    const run = unregisteredRun;
    if (!run) return true;
    return registerRun(run);
  }, [unregisteredRun, registerRun]);

  const retrySave = useCallback(async () => {
    const current = activeCaseRef.current;
    if (!current) return;
    setSaveState("saving");

    // Los builds anteriores podían dejar en memoria `ligand: { inputSmiles: "" }`.
    // Reintentar ese mismo registro nunca podía funcionar. Se sanea el borrador
    // conservando todos los demás datos antes de volver a cruzar la frontera Rust.
    const normalizedInputs = current.inputs
      ? inputsReadyForPersistence(current.inputs)
      : undefined;
    const repaired =
      current.inputs && normalizedInputs !== current.inputs
        ? touchCase(current, { inputs: normalizedInputs })
        : current;
    if (repaired !== current) {
      setActiveCase(repaired);
      queue.enqueue(repaired);
    }

    const result = repaired !== current
      ? await queue.drain(current.id)
      : await queue.retry(current.id);
    if (!mounted.current) return;
    if (result.ok) {
      setSaveState("saved");
      setError(null);
      void refresh();
    } else {
      setSaveState("error");
      setError(
        `${describeError(result.error)} El reintento volvió a fallar; el cambio continúa pendiente.`,
      );
    }
  }, [queue, refresh, describeError]);

  const dismissError = useCallback(() => setError(null), []);

  const value = useMemo<CaseContextValue>(
    () => ({
      repository, cases, activeCase, loading, error, saveState, liveWork, hasLiveWork,
      registryHealth, unregisteredRun,
      registerRun, retryRegisterRun,
      createCase, selectCase, closeCase, updateContext, setActiveView, setArchived,
      setInputs, setPreflight, recordDecision, setDisposition,
      forgetCase, relocateCase, repairCase, acceptRelocation,
      canRepair: typeof repository.repairCase === "function",
      openExistingFolder, initializeFolder, revealInFileManager,
      setLiveWork, setActiveRun, retrySave, refresh, dismissError,
    }),
    [
      repository, cases, activeCase, loading, error, saveState, liveWork, hasLiveWork,
      registryHealth, unregisteredRun,
      registerRun, retryRegisterRun,
      createCase, selectCase, closeCase, updateContext, setActiveView, setArchived,
      setInputs, setPreflight, recordDecision, setDisposition,
      forgetCase, relocateCase, repairCase, acceptRelocation,
      openExistingFolder, initializeFolder, revealInFileManager,
      setLiveWork, setActiveRun, retrySave, refresh, dismissError,
    ],
  );

  return <CaseWorkspaceContext.Provider value={value}>{children}</CaseWorkspaceContext.Provider>;
}

export function useCases(): CaseContextValue {
  const value = useContext(CaseWorkspaceContext);
  if (!value) {
    throw new Error("useCases debe usarse dentro de <CaseProvider>.");
  }
  return value;
}
