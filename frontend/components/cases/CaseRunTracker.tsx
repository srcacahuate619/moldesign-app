"use client";

// =====================================================================
// CaseRunTracker — seguir una corrida sin montar la evaluación entera
// =====================================================================
//
// EL HUECO QUE CIERRA. Una corrida persistida sólo se reanudaba al montar
// `CaseEvaluationRunner`, y ese componente sólo se monta al visitar Evaluar.
// Un caso reabierto con una corrida viva, con el usuario leyendo Contexto,
// no seguía a nadie: la tarea corría en el backend sin que la interfaz lo
// supiera, y `hasLiveWork` no la veía.
//
// Montar el runner automáticamente habría arrastrado Ketcher, Molstar y el
// catálogo de receptores sólo para hacer un `GET` cada dos segundos. Esto es lo
// mínimo: pregunta, actualiza el estado de la corrida y no renderiza nada.
//
// No sustituye al runner. Cuando el usuario entra en Evaluar, el runner toma el
// relevo y este componente se desmonta.
//
// ESTADO ACTUAL (sprint evaluation-first): el workspace ya NO lo monta. Con la
// evaluación como vista de entrada, el runner se monta con el caso y reanuda el
// polling por sí solo desde el primer instante, así que mantener además este
// seguidor pondría dos escritores sobre la misma corrida. Se conserva —con sus
// pruebas— porque es el mecanismo correcto en cuanto exista otra vez un destino
// del caso que no monte el runner; el sprint siguiente mete la cualificación
// dentro de Evaluación y podría volver a necesitarlo.

import { useEffect, useRef } from "react";

import { getJobStatus } from "../../lib/api";
import { isTerminalRunState, type ActiveRun } from "../../lib/cases/types";

const POLL_INTERVAL_MS = 2000;
/** Fallos seguidos antes de declarar el seguimiento interrumpido. */
const MAX_CONSECUTIVE_ERRORS = 5;

export interface CaseRunTrackerProps {
  readonly activeRun: ActiveRun;
  readonly onActiveRunChange: (run: ActiveRun | null) => void;
  /**
   * Intervalo entre consultas. Existe como costura de prueba: el umbral de
   * interrupcion son cinco fallos seguidos, y esperarlos a 2 s reales haria el
   * test lento y dependiente del reloj. En produccion nadie lo pasa.
   */
  readonly pollIntervalMs?: number;
}

export function CaseRunTracker({
  activeRun,
  onActiveRunChange,
  pollIntervalMs = POLL_INTERVAL_MS,
}: CaseRunTrackerProps) {
  const notify = useRef(onActiveRunChange);
  notify.current = onActiveRunChange;
  const runRef = useRef(activeRun);
  runRef.current = activeRun;

  useEffect(() => {
    if (isTerminalRunState(activeRun.executionState)) return;
    const taskId = activeRun.taskId;
    let cancelled = false;
    let consecutiveErrors = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const stop = () => {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const interrupt = (message: string) => {
      stop();
      notify.current({
        ...runRef.current,
        taskId,
        executionState: "interrupted",
        lastError: message,
      });
    };

    const scheduleNext = () => {
      if (cancelled || timer !== null) return;
      timer = setTimeout(() => {
        timer = null;
        void poll();
      }, pollIntervalMs);
    };

    const poll = async () => {
      try {
        const status = await getJobStatus(taskId);
        if (cancelled) return;
        consecutiveErrors = 0;
        // Un error de transporte anterior deja de ser vigente en cuanto el
        // backend vuelve a responder. Se omite explícitamente al construir el
        // siguiente estado para no arrastrarlo hasta una corrida completada.
        const { lastError: _staleError, ...currentRun } = runRef.current;
        if (status.status === "SUCCESS" || status.status === "FAILURE") {
          stop();
          // Terminal deja de bloquear, pero conserva el taskId. Evaluar hará
          // una lectura puntual para recuperar el resultado desde el backend.
          notify.current({
            ...currentRun,
            taskId,
            executionState: status.status === "SUCCESS" ? "completed" : "failed",
            ...(typeof status.progress === "number" ? { lastKnownProgress: status.progress } : {}),
            ...(status.error ? { lastError: status.error } : {}),
          });
          return;
        }
        notify.current({
          ...currentRun,
          taskId,
          executionState: "running",
          ...(typeof status.progress === "number" ? { lastKnownProgress: status.progress } : {}),
        });
        scheduleNext();
      } catch {
        if (cancelled) return;
        consecutiveErrors += 1;
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          // INTERRUMPIDO, no fallido: no se sabe cómo acabó la tarea y el
          // `taskId` se conserva para poder volver a preguntar.
          interrupt("Se perdió la conexión con el servidor. No se sabe cómo terminó la tarea.");
          return;
        }
        scheduleNext();
      }
    };

    // Pregunta de inmediato y después con intervalo: esperar al primer tick
    // dejaría dos segundos en los que el estado mostrado ya es viejo.
    // `.catch` explícito además del try/catch interno: `void` NO adjunta un
    // manejador, así que cualquier rechazo que se escapara del cuerpo se vería
    // como no gestionado y podría tumbar el proceso de pruebas o el webview.
    const safePoll = () => {
      poll().catch(() => {});
    };
    safePoll();

    // Un cambio de sesión invalida cualquier respuesta que ya estuviera en
    // vuelo. El tracker no renderiza resultados, pero tampoco debe cerrar una
    // tarea usando una respuesta perteneciente a la cuenta anterior.
    const handleAuthChange = () => {
      cancelled = true;
      stop();
      interrupt("La sesión cambió. Recupera la sesión antes de reintentar el seguimiento.");
    };
    window.addEventListener("auth_expired", handleAuthChange);
    return () => {
      cancelled = true;
      stop();
      window.removeEventListener("auth_expired", handleAuthChange);
    };
    // Sólo se reinicia si cambia la TAREA. Incluir `executionState` hacía que
    // running → interrupted desmontara y montara el efecto, reanudando el
    // polling que acababa de detenerse.
  }, [activeRun.taskId, pollIntervalMs]);

  return null;
}

export default CaseRunTracker;
