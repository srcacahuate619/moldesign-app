// =====================================================================
// Cola de guardado serializada POR CASO, con revisión monótona
// =====================================================================
//
// EL PROBLEMA QUE RESUELVE. Antes había un único `pendingRecord` global y un
// `setTimeout` compartido. Eso rompía de tres formas distintas:
//
//   1. Editar A y cambiar a B antes del debounce guardaba el borrador de A
//      DESPUÉS de haber cambiado de caso, o lo perdía del todo.
//   2. Dos escrituras que terminan fuera de orden dejaban en pantalla el
//      resultado de la MÁS VIEJA: una respuesta lenta pisaba estado reciente.
//   3. Un fallo de escritura descartaba el cambio: el usuario veía «Error» y su
//      texto ya no existía en ninguna parte.
//
// LAS TRES INVARIANTES:
//
//   · UNA COLA POR `caseId`. Las escrituras de un caso se serializan entre sí y
//     no compiten con las de otro.
//   · REVISIÓN MONÓTONA. Cada cambio incrementa `revision`. Una respuesta cuya
//     revisión es menor que la última aplicada se DESCARTA: no puede reemplazar
//     estado más reciente.
//   · EL PENDIENTE SOBREVIVE AL FALLO. Si la escritura falla, el registro sigue
//     en la cola y se puede reintentar sin que el usuario reescriba nada.
//
// `drain(caseId)` fuerza el vuelco inmediato y espera. Se llama ANTES de
// cualquier operación que reemplace el caso activo.

import type { CaseRecord } from "./types";

/**
 * Resultado de drenar. `ok: false` significa que TODAVIA hay algo sin escribir.
 *
 * Es lo que convierte `drain` en una puerta de verdad: antes devolvia `void` y
 * quien lo llamaba seguia adelante creyendo que estaba todo guardado. Si el
 * disco falla y despues se cambia de caso, el borrador se queda en una cola que
 * ya nadie mira.
 */
export interface DrainResult {
  readonly ok: boolean;
  readonly caseId: string;
  readonly error?: unknown;
}

export type SaveOutcome =
  | { readonly kind: "saved"; readonly record: CaseRecord; readonly revision: number }
  | { readonly kind: "superseded"; readonly revision: number }
  | { readonly kind: "failed"; readonly error: unknown; readonly revision: number };

export interface SaveQueueOptions {
  /** Escritura real. La inyecta el contexto para poder probar con una lenta. */
  readonly write: (record: CaseRecord) => Promise<CaseRecord>;
  readonly delayMs: number;
  readonly onOutcome?: (caseId: string, outcome: SaveOutcome) => void;
  /** Reloj inyectable: los tests no deben depender de timers reales. */
  readonly schedule?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>;
  readonly cancel?: (handle: ReturnType<typeof setTimeout>) => void;
}

interface QueueState {
  /** Último borrador aún no escrito. `null` si no hay nada pendiente. */
  pending: CaseRecord | null;
  /** Revisión del borrador pendiente. */
  pendingRevision: number;
  /** Contador monótono de este caso. */
  revision: number;
  /** Revisión más alta ya aplicada con éxito. */
  applied: number;
  timer: ReturnType<typeof setTimeout> | null;
  /** Cadena de escrituras en curso: serializa dentro del caso. */
  chain: Promise<void>;
  /** Último fallo, para poder reintentar. */
  lastError: unknown;
}

export class CaseSaveQueue {
  private readonly queues = new Map<string, QueueState>();
  private readonly options: Required<Pick<SaveQueueOptions, "write" | "delayMs">> &
    SaveQueueOptions;

  constructor(options: SaveQueueOptions) {
    this.options = options;
  }

  private stateFor(caseId: string): QueueState {
    let state = this.queues.get(caseId);
    if (!state) {
      state = {
        pending: null,
        pendingRevision: 0,
        revision: 0,
        applied: 0,
        timer: null,
        chain: Promise.resolve(),
        lastError: null,
      };
      this.queues.set(caseId, state);
    }
    return state;
  }

  private startTimer(state: QueueState, caseId: string): void {
    const schedule = this.options.schedule ?? ((fn, ms) => setTimeout(fn, ms));
    const cancel = this.options.cancel ?? ((handle) => clearTimeout(handle));
    if (state.timer !== null) cancel(state.timer);
    state.timer = schedule(() => {
      state.timer = null;
      void this.flush(caseId);
    }, this.options.delayMs);
  }

  /** Encola un cambio. Devuelve la revisión asignada. */
  enqueue(record: CaseRecord): number {
    const state = this.stateFor(record.id);
    state.revision += 1;
    state.pending = record;
    state.pendingRevision = state.revision;
    state.lastError = null;
    this.startTimer(state, record.id);
    return state.revision;
  }

  /** `true` si el caso tiene un cambio sin escribir o una escritura en vuelo. */
  hasPending(caseId: string): boolean {
    const state = this.queues.get(caseId);
    if (!state) return false;
    return state.pending !== null || state.applied < state.revision;
  }

  lastError(caseId: string): unknown {
    return this.queues.get(caseId)?.lastError ?? null;
  }

  /**
   * Vuelca lo pendiente y espera a que la cadena de este caso quede vacía.
   *
   * Se llama ANTES de crear, seleccionar, abrir, inicializar o cerrar otro
   * caso: sin esto, el borrador del caso saliente se escribiría —o se perdería—
   * después de haber cambiado de caso.
   */
  async drain(caseId: string): Promise<DrainResult> {
    const state = this.queues.get(caseId);
    if (!state) return { ok: true, caseId };
    const cancel = this.options.cancel ?? ((handle) => clearTimeout(handle));
    if (state.timer !== null) {
      cancel(state.timer);
      state.timer = null;
    }
    await this.flush(caseId);
    await state.chain;
    // La comprobacion que importa: si queda pendiente o hubo error, el drenaje
    // NO tuvo exito y quien llame debe abortar su transicion.
    if (state.pending !== null || state.lastError !== null) {
      return { ok: false, caseId, error: state.lastError };
    }
    return { ok: true, caseId };
  }

  /** Vuelca TODOS los casos con algo pendiente. */
  async drainAll(): Promise<DrainResult[]> {
    return Promise.all([...this.queues.keys()].map((id) => this.drain(id)));
  }

  /** Reintenta el último cambio que falló, si sigue pendiente. */
  async retry(caseId: string): Promise<DrainResult> {
    const state = this.queues.get(caseId);
    if (!state || state.pending === null) return { ok: true, caseId };
    await this.flush(caseId);
    await state.chain;
    if (state.pending !== null || state.lastError !== null) {
      return { ok: false, caseId, error: state.lastError };
    }
    return { ok: true, caseId };
  }

  private flush(caseId: string): Promise<void> {
    const state = this.stateFor(caseId);
    const record = state.pending;
    if (record === null) return state.chain;
    const revision = state.pendingRevision;
    // Se retira el pendiente ANTES de escribir para que un cambio nuevo durante
    // la escritura entre como pendiente distinto y no se pise con éste.
    state.pending = null;

    state.chain = state.chain.then(async () => {
      try {
        const saved = await this.options.write(record);
        // SUPERADA si, mientras esta escritura estaba en vuelo, entró una
        // edición más nueva. `state.revision` es la última enqueued, no la
        // última aplicada: comparar contra `applied` no bastaba, porque con las
        // escrituras serializadas nunca hay dos en vuelo y ese contador no se
        // movía. El caso real que hay que atrapar es éste — el usuario siguió
        // escribiendo y la respuesta de lo anterior llega después.
        if (revision < state.revision) {
          this.options.onOutcome?.(caseId, { kind: "superseded", revision });
          return;
        }
        state.applied = revision;
        state.lastError = null;
        this.options.onOutcome?.(caseId, { kind: "saved", record: saved, revision });
      } catch (error) {
        // El cambio NO se pierde: vuelve a la cola para poder reintentar. Sólo
        // se restaura si no hay uno más nuevo esperando.
        if (state.pending === null) {
          state.pending = record;
          state.pendingRevision = revision;
        }
        state.lastError = error;
        this.options.onOutcome?.(caseId, { kind: "failed", error, revision });
      }
    });
    return state.chain;
  }
}
