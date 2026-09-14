// =====================================================================
// Modelo de datos de CASO — la unidad central del producto
// =====================================================================
//
// Un caso reune proteina, hipotesis de sitio, ligandos, corridas, evidencia y
// decision en un espacio reproducible. Sustituye a "una evaluacion suelta" como
// unidad de trabajo (docs/53 §5).
//
// TRES ESTADOS SEPARADOS, Y NO SE MEZCLAN. Es la regla que docs/53 §4 exige y
// la que este archivo hace imposible de violar por tipos:
//
//   CaseStatus       estado CIENTIFICO del caso     draft..completed/abstained
//   RunExecutionState estado COMPUTACIONAL de una corrida  idle..failed
//   EvidenceDisposition disposicion de la evidencia  unreviewed..abstained
//
// Un `SUCCESS` del backend mueve RunExecutionState a `completed`. NO mueve el
// CaseStatus a `completed` ni la evidencia a `apt`: eso lo decide una persona.
// Por eso son tres uniones distintas y ninguna funcion las convierte.
//
// Campos cientificos sin responder: `undefined` NO es una respuesta. Se
// modelan como ausencia explicita y la UI muestra "No definido". Nunca se
// inventa un valor por defecto.

/**
 * Version del esquema del manifiesto `case.json`. Subir SOLO con migracion.
 *
 * v2 sustituye `activeSection` —siete secciones, cinco de ellas inertes— por
 * `activeView`, que solo admite los dos modos que existen de verdad.
 *
 * v3 anade los INPUTS del caso —receptor y ligando—, el ultimo preflight y las
 * decisiones humanas. Antes, el receptor y el SMILES vivian solo en el estado
 * de React: cerrar el caso los perdia y no habia forma de afirmar que una
 * corrida guardada correspondiera a la hipotesis que se estaba mirando.
 *
 * v4 fija el SISTEMA ESTRUCTURAL al registrar la primera corrida: receptor,
 * cadena, caja efectiva, protocolo y huella. El caso puede seguir recibiendo
 * infinitos ligandos, pero no puede cambiar silenciosamente de sistema.
 *
 * v7 guarda el LIBRO de corridas (`runs`) en lugar de sólo la última. Hasta v6
 * el manifiesto tenía un `activeRun` singular y cada corrida nueva pisaba el
 * puntero a la anterior: el informe seguía intacto en el backend y dejaba de
 * ser alcanzable desde el caso. `activeRun` pasa a DERIVARSE de la última
 * entrada y ya no se escribe en disco.
 *
 * Las migraciones viven en `schema.ts` y son explicitas; un manifiesto v1 o v2
 * se sigue leyendo y se normaliza al abrirlo.
 */
export const CASE_SCHEMA_VERSION = 7;

/** Versiones que este build sabe leer. Una version mayor se rechaza. */
export const SUPPORTED_SCHEMA_VERSIONS: readonly number[] = [1, 2, 3, 4, 5, 6, 7];

// ── Estado cientifico del caso ───────────────────────────────────────

export const CASE_STATUSES = [
  "draft",
  "qualifying",
  "ready",
  "running",
  "review",
  "completed",
  "abstained",
] as const;

export type CaseStatus = (typeof CASE_STATUSES)[number];

/** Etiquetas en castellano. La UI nunca deriva texto del identificador crudo. */
export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  draft: "Borrador",
  qualifying: "Cualificando",
  ready: "Listo",
  running: "Ejecutando",
  review: "En revisión",
  completed: "Completado",
  abstained: "Abstención",
};

// ── Estado COMPUTACIONAL de una corrida ──────────────────────────────
// Deliberadamente disjunto de CaseStatus. Una corrida puede terminar en
// `completed` y el caso seguir en `review` o `abstained`.

export const RUN_EXECUTION_STATES = [
  "idle",
  "submitted",
  "running",
  /**
   * El seguimiento se perdio, NO el backend fallo.
   *
   * Es la distincion que faltaba: un corte de red o un cierre de la ventana
   * dejaba la corrida marcada como `failed`, y eso es una afirmacion sobre el
   * backend que nadie ha comprobado. `interrupted` dice lo unico cierto —que no
   * sabemos como acabo— y conserva el `taskId` para poder volver a preguntar.
   */
  "interrupted",
  "completed",
  "failed",
  "cancelled",
] as const;

export type RunExecutionState = (typeof RUN_EXECUTION_STATES)[number];

/** Estados en los que la corrida ya no puede cambiar por si sola. */
export const TERMINAL_RUN_STATES: readonly RunExecutionState[] = [
  "completed",
  "failed",
  "cancelled",
];

export function isTerminalRunState(state: RunExecutionState): boolean {
  return TERMINAL_RUN_STATES.includes(state);
}

/** Estados que representan trabajo que sigue ejecutandose ahora mismo. */
export function isRunBlocking(state: RunExecutionState): boolean {
  return state === "submitted" || state === "running";
}

/**
 * Última corrida PERSISTIDA en el caso.
 *
 * Vive en el manifiesto y NO en memoria porque su proposito es sobrevivir a lo
 * que mata la memoria: cerrar la ventana, recargar, o cambiar de caso y volver.
 * Sin esto, una corrida lanzada seguia en el backend y el usuario no tenia
 * forma de volver a encontrarla — trabajo huerfano. Al terminar se conserva
 * el `taskId`: deja de bloquear, pero sigue siendo el vínculo para recuperar el
 * resultado sin copiar el payload científico dentro de `case.json`.
 *
 * Es estado COMPUTACIONAL. No es el estado cientifico del caso y no se mezcla
 * con el: un `completed` aqui no completa el caso.
 */
export interface ActiveRun {
  readonly taskId: string;
  /**
   * Referencia durable al resultado. Se guarda al primer SUCCESS valido para
   * poder reabrir la evaluacion aunque el cache de tareas expire o el backend
   * se reinicie. No duplica el payload cientifico: solo conserva su identidad.
   */
  readonly moleculeId?: string;
  readonly executionState: RunExecutionState;
  readonly startedAt: string;
  readonly lastKnownProgress?: number;
  readonly lastError?: string;
  /**
   * Fingerprint de los inputs con los que se lanzo ESTA corrida.
   *
   * Es lo que permite decir, mas tarde, si el informe guardado corresponde a
   * la hipotesis que hay ahora en pantalla o a una anterior. Sin el, cambiar
   * el receptor dejaba un informe antiguo presentandose como evidencia de una
   * hipotesis nueva — el error mas caro que puede cometer este producto.
   *
   * Ausente en corridas lanzadas antes de v3: eso NO se convierte en
   * "corresponde"; se declara desconocido (ver `runMatchesInputs`).
   */
  readonly inputFingerprint?: string;
}

// ── El LIBRO de corridas del caso ────────────────────────────────────
//
// `activeRun` responde «¿qué corrida está mirando o siguiendo esta superficie
// ahora?». NO responde «¿qué ha producido este caso?», y durante seis versiones
// del esquema fue lo único que se guardó: cada corrida nueva pisaba el puntero a
// la anterior y su informe dejaba de ser alcanzable desde el caso. El dato nunca
// se perdía —`evaluation_runs` guarda en el backend el snapshot inmutable de
// cada `task_id` precisamente «de modo que casos y cohortes no cambien al
// ejecutar de nuevo la misma molécula»—; lo que faltaba era el puntero.
//
// `runs` es ese libro, y reparte las responsabilidades igual que el backend:
//
//   runs        el LIBRO   una fila por corrida; no se sobrescribe
//   activeRun   el DEDO    proyección de la última fila
//
// `activeRun` NO SE PERSISTE. Se deriva de la última entrada de `runs` al
// parsear (`schema.ts`). Escribir las dos cosas daría dos fuentes de verdad
// para lo mismo y la próxima escritura tendría que decidir cuál gana.
//
// De cada corrida se guarda su IDENTIDAD más lo justo para pintar su fila SIN
// backend —ligando, afinidad, protocolo—. El payload científico sigue siendo
// del backend: copiarlo aquí lo dejaría envejecer sin que nada lo revalidara,
// que es la misma regla que ya cumple `PreflightSummary`.

/**
 * Protocolo con el que se ejecutó UNA corrida.
 *
 * Se sella por corrida y no por caso a propósito. El sistema estructural
 * —receptor, cadena, caja— sí es del caso: cambiarlo hace que las corridas
 * dejen de ser el mismo experimento. El esfuerzo de muestreo no: repetir el
 * mismo ligando con más `exhaustiveness` para comprobar convergencia es
 * trabajo normal, y prohibirlo no protegía nada. Lo que hay que impedir es
 * comparar en silencio dos corridas que no se pueden comparar, y para eso
 * basta con que cada una diga con qué protocolo se ejecutó.
 */
export interface CaseRunProtocol {
  readonly dockingEngine: string;
  readonly exhaustiveness: number;
  readonly numPoses: number;
  readonly conformers: number;
}

/**
 * Una fila del libro. Es `ActiveRun` más lo que hace falta para enseñarla
 * cuando el backend no contesta.
 */
export interface CaseRun extends ActiveRun {
  /** Momento en que alcanzó un estado terminal. Ausente mientras no lo sea. */
  readonly finishedAt?: string;
  /** SMILES tal como se envió. Identifica la fila; no sustituye al canónico. */
  readonly ligandSmiles?: string;
  /** Titular de la corrida, kcal/mol. Ausente si no terminó o no la produjo. */
  readonly affinityKcal?: number;
  /** Protocolo efectivo. Ausente en corridas migradas de v6. */
  readonly protocol?: CaseRunProtocol;
}

/** Última fila del libro: la corrida a la que apunta `activeRun`. */
export function latestRun(runs: readonly CaseRun[] | undefined): CaseRun | undefined {
  if (!runs || runs.length === 0) return undefined;
  return runs[runs.length - 1];
}

/**
 * Inserta o actualiza una corrida CONSERVANDO el orden del libro.
 *
 * Único punto por el que el libro cambia, y por eso el único sitio donde vive
 * el invariante «activeRun es la última entrada». Una corrida ya presente se
 * actualiza EN SU SITIO —el progreso de una corrida viva llega muchas veces— y
 * una desconocida se añade al final. Nada se borra: un libro del que se puede
 * quitar una página no sirve como registro de lo que un caso produjo.
 */
export function upsertRun(
  runs: readonly CaseRun[] | undefined,
  run: CaseRun,
): readonly CaseRun[] {
  const book = runs ?? [];
  const index = book.findIndex((entry) => entry.taskId === run.taskId);
  if (index === -1) return [...book, run];
  // Se fusiona en vez de reemplazar: una actualización de progreso no trae
  // `ligandSmiles` ni `affinityKcal`, y sustituir la fila entera los perdería.
  const merged: CaseRun = { ...book[index], ...run };
  const next = [...book];
  next[index] = merged;
  return next;
}

/** `true` si alguna corrida del caso llegó a producir evidencia. */
export function hasCompletedRun(runs: readonly CaseRun[] | undefined): boolean {
  return (runs ?? []).some((run) => run.executionState === "completed");
}

/**
 * Cómo se relaciona el protocolo de una corrida con el del sistema del caso.
 *
 * `desconocido` NO se resuelve a «el mismo»: una corrida migrada de v6 no
 * declaró protocolo, y afirmar que coincide sería inventarlo.
 */
export type RunProtocolRelation = "mismo_protocolo" | "otro_protocolo" | "desconocido";

export function runProtocolRelation(
  run: CaseRun,
  system: CaseStructuralSystem | undefined,
): RunProtocolRelation {
  if (!run.protocol || !system) return "desconocido";
  return run.protocol.dockingEngine === system.dockingEngine &&
    run.protocol.exhaustiveness === system.exhaustiveness &&
    run.protocol.numPoses === system.numPoses &&
    run.protocol.conformers === system.conformers
    ? "mismo_protocolo"
    : "otro_protocolo";
}

/** Etiqueta corta del protocolo para la fila del libro. */
export function describeRunProtocol(protocol: CaseRunProtocol): string {
  return `${protocol.dockingEngine} · exh ${protocol.exhaustiveness} · ${protocol.numPoses} poses`;
}

// ── Disposicion de la EVIDENCIA ──────────────────────────────────────
// La decide una persona, nunca el backend.

export const EVIDENCE_DISPOSITIONS = [
  "unreviewed",
  "apt",
  "limited",
  "abstained",
] as const;

export type EvidenceDisposition = (typeof EVIDENCE_DISPOSITIONS)[number];

// ── Almacenamiento ───────────────────────────────────────────────────

export type CaseStorageMode = "browser" | "folder";

export type CaseStorage =
  | {
      readonly mode: "browser";
      /** Etiqueta honesta para la UI. No es una ruta y no debe parecerlo. */
      readonly label: "Guardado en este navegador";
    }
  | {
      readonly mode: "folder";
      /** Ruta absoluta de la carpeta del caso. Solo existe en escritorio. */
      readonly path: string;
    };

// ── Tipo de estudio ──────────────────────────────────────────────────

export const CASE_STUDY_KINDS = [
  "explore-hypothesis",
  "compare-series",
  "review-pose",
  "prepare-evidence",
] as const;

export type CaseStudyKind = (typeof CASE_STUDY_KINDS)[number];

export const CASE_STUDY_KIND_LABELS: Record<CaseStudyKind, string> = {
  "explore-hypothesis": "Explorar una hipótesis",
  "compare-series": "Comparar una serie",
  "review-pose": "Revisar una pose",
  "prepare-evidence": "Preparar evidencia para un cálculo posterior",
};

// ── Modos del caso ───────────────────────────────────────────────────
//
// DOS, y los dos existen de verdad. La version anterior declaraba siete
// secciones —contexto, sistema, sitio, ligandos, evaluar, evidencia, informe—
// y cinco eran destinos inertes con una razon de por que no funcionaban. Eso
// expone la arquitectura interna del producto y obliga a entrar por un
// cuestionario antes de dejar trabajar.
//
// Ahora la evaluacion ES la vista principal, y el informe se REVELA cuando hay
// una corrida completada cuyo resultado se puede recuperar. Contexto, sistema,
// sitio, ligandos y evidencia no desaparecen: son partes del flujo. El contexto
// cientifico vive en «Detalles del caso», dentro de Evaluacion.

export const CASE_VIEWS = ["evaluation", "report"] as const;

export type CaseView = (typeof CASE_VIEWS)[number];

export const CASE_VIEW_LABELS: Record<CaseView, string> = {
  evaluation: "Evaluación",
  report: "Informe",
};

/**
 * Valores de `activeSection` que escribio el esquema v1.
 *
 * Se conservan SOLO para poder normalizarlos. Un caso guardado en `context` o
 * en `ligands` tiene que abrirse en Evaluacion, no desaparecer ni aterrizar en
 * una pantalla vacia.
 */
export const LEGACY_CASE_SECTIONS = [
  "context",
  "system",
  "site",
  "ligands",
  "evaluate",
  "evidence",
  "report",
] as const;

export type LegacyCaseSection = (typeof LEGACY_CASE_SECTIONS)[number];

/**
 * Normaliza un valor CUALQUIERA a un modo que existe.
 *
 * Es la puerta de entrada de todo lo que viene de fuera: un manifiesto editado
 * a mano, un valor corrupto, un `undefined`. Nunca lanza y nunca devuelve algo
 * que la interfaz no sepa pintar — un caso no puede desaparecer ni quedarse en
 * una pantalla vacía por culpa de una preferencia de navegación.
 */
export function normalizeCaseView(raw: unknown): CaseView {
  return raw === "report" || raw === "evaluation" ? (raw as CaseView) : "evaluation";
}

/**
 * Traduce una `activeSection` del esquema v1 al modo con el que se abre.
 *
 * SIEMPRE `evaluation`, incluido el caso `report`. No es descuido: en v1
 * «Informe» era una pestaña inerte que no se podía seleccionar, así que un
 * manifiesto con ese valor no acredita que exista evidencia recuperable.
 * Abrir en Evaluación es lo único afirmable sin comprobar nada, y desde ahí el
 * informe se revela solo si de verdad hay un resultado que recuperar.
 *
 * Está separada de `normalizeCaseView` a propósito: aquel normaliza valores
 * ACTUALES —donde `report` sí es legítimo— y ésta traduce valores VIEJOS, donde
 * no lo es. Compartir una sola función haría que un `report` heredado
 * restaurara una vista que nadie puede garantizar.
 */
export function viewFromLegacySection(_section: unknown): CaseView {
  return "evaluation";
}

/**
 * Referencia MINIMA al resultado de una corrida, suficiente para el informe.
 *
 * Vive en memoria y NO se copia dentro de `case.json`: el payload cientifico
 * pertenece al backend y duplicarlo en el manifiesto crearia una segunda
 * verdad que envejece. Lo que se persiste es el `taskId` dentro de `activeRun`;
 * el `molecule_id` se recupera preguntando por esa tarea.
 */
export interface ReportableResult {
  readonly taskId: string;
  readonly moleculeId: string;
  /** La integridad del dossier ya esta registrada en cadena. */
  readonly certified: boolean;
}

/**
 * Como fue el intento de recuperar el resultado de una corrida persistida.
 *
 * `unrecoverable` es un estado de primera clase a proposito: un caso reabierto
 * cuyo backend ya no conoce la tarea tiene que DECIRLO, no fingir que nunca
 * hubo informe.
 */
export type ReportRecoveryState = "idle" | "recovering" | "recovered" | "unrecoverable";

// ── Contexto cientifico ──────────────────────────────────────────────
// TODOS los campos son opcionales A PROPOSITO. Un campo ausente significa
// "No definido" y se muestra como tal. No hay valores por defecto inventados.

export interface CaseContext {
  readonly studyKind?: CaseStudyKind;
  /** ¿Que intenta responder este caso? */
  readonly question?: string;
  /** ¿Que decision se pretende tomar? */
  readonly decision?: string;
  /** ¿Que justifica la eleccion del sistema? */
  readonly systemRationale?: string;
  /** ¿Que controles o referencias existen? */
  readonly controls?: string;
  /** ¿Que supuestos se estan haciendo? */
  readonly assumptions?: string;
  /** ¿Que incertidumbres ya se conocen? */
  readonly uncertainties?: string;
  readonly notes?: string;
}

/** Las claves de texto libre del contexto, en el orden en que se preguntan. */
export const CASE_CONTEXT_FIELDS = [
  "question",
  "decision",
  "systemRationale",
  "controls",
  "assumptions",
  "uncertainties",
  "notes",
] as const satisfies readonly (keyof CaseContext)[];

export type CaseContextField = (typeof CASE_CONTEXT_FIELDS)[number];

/**
 * Severidad de un campo pendiente.
 *
 * En este sprint SOLO existen `warning` e `info`. No hay `blocker` porque no se
 * inventan reglas cientificas nuevas: ningun campo de contexto impide todavia
 * ejecutar. El nivel existe en el tipo para que la clasificacion futura no
 * obligue a migrar el esquema.
 */
export type CaseFieldSeverity = "blocker" | "warning" | "info";

export interface CaseContextFieldSpec {
  readonly field: CaseContextField;
  readonly question: string;
  readonly severity: CaseFieldSeverity;
  readonly hint: string;
}

export const CASE_CONTEXT_SPECS: readonly CaseContextFieldSpec[] = [
  {
    field: "question",
    question: "¿Qué intenta responder este caso?",
    severity: "warning",
    hint: "Sin esto, el dossier no puede declarar qué se estaba preguntando.",
  },
  {
    field: "decision",
    question: "¿Qué decisión se pretende tomar?",
    severity: "warning",
    hint: "Una evidencia sin decisión asociada no se puede calificar de suficiente ni de insuficiente.",
  },
  {
    field: "systemRationale",
    question: "¿Qué justifica la elección del sistema?",
    severity: "warning",
    hint: "Estructura, ensamblaje, cadenas y estado: por qué éste y no otro.",
  },
  {
    field: "controls",
    question: "¿Qué controles o referencias existen?",
    severity: "warning",
    hint: "Ligando de referencia, redock del cristal, series conocidas, negativos.",
  },
  {
    field: "assumptions",
    question: "¿Qué supuestos se están haciendo?",
    severity: "warning",
    hint: "Protonación, tautomería, aguas, cofactores, rigidez del receptor.",
  },
  {
    field: "uncertainties",
    question: "¿Qué incertidumbres ya se conocen?",
    severity: "info",
    hint: "Lo que ya se sabe que este caso NO podrá resolver.",
  },
  {
    field: "notes",
    question: "Notas",
    severity: "info",
    hint: "Contexto libre. No entra en ningún cálculo.",
  },
];

// ── Inputs del caso: la hipotesis computacional ──────────────────────
//
// POR QUE SE PERSISTEN. Hasta v2 el receptor y el SMILES vivian en `useState`
// dentro del runner. Cerrar el caso los borraba, y el manifiesto guardaba una
// corrida cuyo contenido nadie podia reconstruir: quedaba un `taskId` sin
// hipotesis. Un caso es una hipotesis reproducible o no es nada.
//
// LO QUE NO SE PERSISTE. Ni poses, ni energias, ni el payload cientifico del
// backend. Eso pertenece al backend y duplicarlo crearia una segunda verdad
// que envejece. Aqui va solo lo que define QUE se va a ejecutar.

/** De donde salio el receptor. `desconocido` es un estado legitimo. */
export const RECEPTOR_ORIGINS = ["curado", "privado", "comunidad", "subido", "desconocido"] as const;

export type ReceptorOrigin = (typeof RECEPTOR_ORIGINS)[number];

export const RECEPTOR_ORIGIN_LABELS: Record<ReceptorOrigin, string> = {
  curado: "Catálogo curado",
  privado: "Privado",
  comunidad: "Comunidad",
  subido: "Subido por ti",
  desconocido: "Origen no declarado",
};

export function normalizeReceptorOrigin(raw: unknown): ReceptorOrigin {
  return RECEPTOR_ORIGINS.includes(raw as ReceptorOrigin)
    ? (raw as ReceptorOrigin)
    : "desconocido";
}

/** Receptor elegido. La referencia estable sobrevive a que cambie el catalogo. */
export interface CaseReceptor {
  /** Identificador estable del target si el catalogo lo da. */
  readonly targetId?: string;
  readonly pdbId: string;
  /** Cadena que se acopla. Ausente = la que declare el receptor. */
  readonly chain?: string;
  readonly origin: ReceptorOrigin;
  /** Nombre legible para la interfaz y el dossier. */
  readonly name?: string;
}

/** Hipotesis de ligando. El canonico solo existe si el backend lo produjo. */
export interface CaseLigand {
  /** Lo que escribio la persona, tal cual. Nunca se sobrescribe. */
  readonly inputSmiles: string;
  /**
   * Canonico devuelto por el validador del backend.
   *
   * Se guarda aparte del introducido a proposito: el dossier tiene que poder
   * ensenar los dos y decir que la corrida uso el canonico.
   */
  readonly canonicalSmiles?: string;
  readonly name?: string;
}

/** Caja de busqueda tal como se enviara. */
export interface CaseGrid {
  readonly center: readonly [number, number, number];
  readonly size: readonly [number, number, number];
}

export interface CaseInputs {
  readonly receptor?: CaseReceptor;
  readonly ligand?: CaseLigand;
  readonly grid?: CaseGrid;
  readonly customHotspots?: readonly string[];
  readonly dockingEngine?: string;
  readonly exhaustiveness?: number;
  readonly numPoses?: number;
  /**
   * Conformaciones de entrada por molécula. 1 = confórmero único, el protocolo
   * por defecto.
   *
   * Vive en los INPUTS del caso, junto a la caja y la exhaustividad, porque es
   * lo mismo: un parámetro que cambia lo que se ejecuta y que entra en la
   * huella. Cambiarlo invalida el preflight, igual que mover la caja.
   */
  readonly conformers?: number;
  /** Configuración PRO completa, incluida en el fingerprint del preflight. */
  readonly pipelineConfig?: CasePipelineConfig;
}

/** Contrato estable para las opciones que cambian el protocolo de ejecución. */
export interface CasePipelineConfig {
  readonly enabled_stages?: readonly string[];
  readonly stage_params?: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  readonly stage_order?: readonly string[];
  readonly docking_engine?: string;
  readonly peptide_docking_engine?: string;
  readonly gnn_precision?: string;
  readonly pro_workers?: number;
  readonly pro_parallel_docks?: number;
  readonly pro_selectivity?: boolean;
  readonly pro_anti_targets?: readonly string[];
  readonly pro_mmgbsa?: boolean;
  readonly pro_mmgbsa_steps?: number;
}

// ── Sistema estructural fijo ─────────────────────────────────────────
//
// El sistema no es sólo un PDB. Es la hipótesis estructural completa sobre la
// que se pueden comparar ligandos: receptor/cadena, caja, residuos, protocolo
// y la preparación exacta que inspeccionó el backend. Se fija sólo cuando el
// backend ya devolvió un `taskId`; bloquearlo al seleccionar un receptor sería
// confundir una intención editable con una corrida registrada.

export interface CaseStructuralSystem {
  /** Momento en que nació la primera corrida que fijó este sistema. */
  readonly lockedAt: string;
  /** Corrida que dejó el ancla reproducible. */
  readonly sourceRunTaskId: string;
  /** Huella canónica inspeccionada y enviada al backend. */
  readonly inputFingerprint: string;
  readonly receptor: CaseReceptor;
  /** Caja efectiva, nunca el sentinel que pudo haber tenido la UI. */
  readonly grid: CaseGrid;
  readonly customHotspots: readonly string[];
  readonly dockingEngine: string;
  readonly exhaustiveness: number;
  readonly numPoses: number;
  readonly conformers: number;
  readonly pipelineConfig?: CasePipelineConfig;
  /** Hashes declarados por el preflight; ausentes no se inventan. */
  readonly receptorSourceSha256?: string;
  readonly preparedReceptorSha256?: string;
}

// ── Preflight persistido ─────────────────────────────────────────────
//
// Se guarda un RESUMEN, no el informe entero. El detalle —controles, diff,
// hashes— pertenece al backend y se vuelve a pedir cuando hace falta; copiarlo
// dentro de `case.json` lo dejaria envejecer sin que nada lo revalidara.
//
// Lo que si se guarda es lo que hace falta para dos cosas que tienen que
// funcionar sin backend: ensenar el resumen al reabrir, y decidir si el boton
// de ejecutar puede ejecutar.

export interface PreflightSummary {
  /** Fingerprint canonico calculado por el backend. */
  readonly fingerprint: string;
  /**
   * Documento canonico de los inputs, tal como lo serializo el backend.
   *
   * Es PROCEDENCIA, no clave de comparacion: deja por escrito que inputs vio
   * el backend. La correspondencia con los inputs actuales no se decide
   * comparando esto —el cliente no reproduce el formato— sino invalidando el
   * preflight en cuanto los inputs cambian (`inputsAffectRun`).
   */
  readonly inputDocument: string;
  readonly generatedAt: string;
  readonly schemaVersion: number;
  readonly executionRoute: string;
  readonly blockers: readonly string[];
  readonly warnings: readonly string[];
  readonly notEvaluated: readonly string[];
  /** Resumen legible: receptor/cadena, ligando canonico y caja efectiva. */
  readonly receptorLabel: string;
  readonly ligandLabel: string;
  readonly gridLabel: string;
  /** Huellas de la estructura que inspeccionó el backend, si las declaró. */
  readonly receptorSourceSha256?: string;
  readonly preparedReceptorSha256?: string;
  /**
   * Configuración efectiva que el backend inspeccionó. Es la que se envía a
   * ejecutar, incluso cuando la interfaz había partido del sentinel (0,0,0)
   * y el backend derivó una caja real.
   *
   * Opcional sólo para poder abrir casos v3 escritos antes de este contrato;
   * esos casos deben repetir la comprobación antes de ejecutar.
   */
  readonly executionConfig?: {
    readonly gridCenter: readonly [number, number, number];
    readonly gridSize: readonly [number, number, number];
    readonly customHotspots: readonly string[];
    readonly dockingEngine: string;
    readonly exhaustiveness: number;
    readonly numPoses: number;
    readonly seed: number;
    /** Conformaciones de entrada. 1 = confórmero único (protocolo por defecto). */
    readonly conformers?: number;
    readonly pipelineConfig?: CasePipelineConfig;
  };
}

/**
 * Construye el sistema fijo solamente desde evidencia que ya existe. No hay
 * valores por defecto: si faltan receptor, configuración efectiva o huella,
 * la corrida se conserva pero el caso no pretende tener un sistema sellado.
 */
export function structuralSystemFromRun(
  inputs: CaseInputs | undefined,
  preflight: PreflightSummary | undefined,
  run: ActiveRun,
): CaseStructuralSystem | null {
  const config = preflight?.executionConfig;
  if (
    !inputs?.receptor ||
    !config ||
    !run.inputFingerprint ||
    run.inputFingerprint !== preflight?.fingerprint
  ) {
    return null;
  }

  return {
    lockedAt: run.startedAt,
    sourceRunTaskId: run.taskId,
    inputFingerprint: run.inputFingerprint,
    receptor: { ...inputs.receptor },
    grid: {
      center: [...config.gridCenter] as [number, number, number],
      size: [...config.gridSize] as [number, number, number],
    },
    customHotspots: [...config.customHotspots],
    dockingEngine: config.dockingEngine,
    exhaustiveness: config.exhaustiveness,
    numPoses: config.numPoses,
    conformers: config.conformers ?? 1,
    ...(config.pipelineConfig ? { pipelineConfig: config.pipelineConfig } : {}),
    ...(preflight.receptorSourceSha256
      ? { receptorSourceSha256: preflight.receptorSourceSha256 }
      : {}),
    ...(preflight.preparedReceptorSha256
      ? { preparedReceptorSha256: preflight.preparedReceptorSha256 }
      : {}),
  };
}

/**
 * Si el sistema del caso está SELLADO o todavía es provisional.
 *
 * El sistema se escribe al nacer el `taskId` —es el único instante en que la
 * huella y la configuración efectiva son las de esa corrida— pero no queda
 * sellado hasta que alguna corrida TERMINA en él. La versión anterior sellaba
 * en el envío, así que una primera corrida que fallaba —caja mal puesta, Vina
 * reventando en la preparación— casaba el caso para siempre con una
 * configuración que nunca produjo nada, y la única salida era crear otro caso
 * y perder el nombre, el contexto y las notas.
 *
 * Provisional NO significa ausente: el sistema se enseña igual, porque es el
 * que se está usando. Significa que todavía se puede corregir.
 */
export function structuralSystemIsSealed(record: {
  readonly structuralSystem?: CaseStructuralSystem;
  readonly runs?: readonly CaseRun[];
}): boolean {
  return Boolean(record.structuralSystem) && hasCompletedRun(record.runs);
}

/**
 * Restituye los campos ESTRUCTURALES desde el ancla y deja libre el resto.
 *
 * QUÉ SE RESTITUYE Y QUÉ NO. Receptor, cadena, caja y residuos definen el
 * sistema: dos corridas que no los comparten no son el mismo experimento, y
 * dejarlos editables después de sellar es el error más caro que puede cometer
 * este producto. El protocolo —motor, exhaustiveness, poses, confórmeros— no
 * define el sistema: define el esfuerzo. Restituirlo también obligaba a crear
 * un caso nuevo para repetir el mismo ligando con más muestreo, que es trabajo
 * normal de laboratorio, y no protegía nada que `runProtocolRelation` no diga
 * mejor: cada corrida declara su protocolo y una que se salga se ve.
 *
 * Centralizarlo evita que una ruta nueva cambie la caja por accidente después
 * de que el caso ya es comparable.
 */
export function inputsForStructuralSystem(
  system: CaseStructuralSystem,
  requested: CaseInputs,
): CaseInputs {
  return {
    ...requested,
    receptor: { ...system.receptor },
    grid: {
      center: [...system.grid.center] as [number, number, number],
      size: [...system.grid.size] as [number, number, number],
    },
    customHotspots: [...system.customHotspots],
  };
}

/**
 * Decision humana explicita sobre un control, atada a un fingerprint.
 *
 * ATADA AL FINGERPRINT a proposito: reconocer una advertencia sobre unos
 * inputs no dice nada sobre otros. Si cambia el receptor, la decision anterior
 * sigue en el historial pero deja de aplicar.
 *
 * Una decision NO desbloquea nada. Los bloqueantes son fallos tecnicos
 * verificables y no se negocian; lo que se registra aqui es que una persona
 * vio una advertencia y siguio adelante, que es justo lo que el dossier
 * necesita poder declarar.
 */
export interface HumanDecision {
  readonly controlCode: string;
  readonly fingerprint: string;
  readonly decision: "reconocida";
  readonly at: string;
  readonly note?: string;
}

/**
 * Como se relaciona una corrida guardada con los inputs actuales.
 *
 * `desconocida` existe para las corridas anteriores a v3, que no guardaron
 * fingerprint: no se puede afirmar que correspondan y tampoco que no. Tratar
 * ese hueco como "corresponde" seria exactamente la atribucion falsa que este
 * campo previene.
 */
export type RunInputsRelation = "corresponde" | "corrida_anterior" | "desconocida";

export function runMatchesInputs(
  run: ActiveRun | undefined,
  currentFingerprint: string | null,
): RunInputsRelation {
  if (!run) return "desconocida";
  // Corridas anteriores a v3: no guardaron huella. No se puede afirmar que
  // correspondan, y tampoco que no.
  if (!run.inputFingerprint) return "desconocida";
  // Sin preflight vigente pero CON una corrida con huella: la corrida sólo
  // pudo lanzarse con un preflight, y ese preflight se retiró porque los
  // inputs cambiaron. Es una corrida anterior, no una incógnita.
  if (!currentFingerprint) return "corrida_anterior";
  return run.inputFingerprint === currentFingerprint ? "corresponde" : "corrida_anterior";
}

// ── El caso ──────────────────────────────────────────────────────────

export interface CaseRecord {
  readonly schemaVersion: number;
  readonly id: string;
  /**
   * Cuenta propietaria del caso. Ausente únicamente en manifiestos legacy v1-v5
   * pendientes de una migración autorizada contra el backend.
   */
  readonly ownerUserId?: string;
  readonly name: string;
  /** ISO 8601 UTC. */
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly lastOpenedAt: string;
  readonly status: CaseStatus;
  readonly storage: CaseStorage;
  /** Modo abierto. v1 guardaba `activeSection`; ver `normalizeCaseView`. */
  readonly activeView: CaseView;
  readonly context: CaseContext;
  readonly archived: boolean;
  /**
   * Libro de corridas del caso, en orden de arranque. Nunca se sobrescribe una
   * entrada por otra: cada corrida que este caso lanzó conserva su fila.
   */
  readonly runs: readonly CaseRun[];
  /**
   * Última corrida, viva o terminal. DERIVADA de `runs`: no se persiste y no
   * se escribe a mano. Sigue aquí porque es la pregunta que hace casi toda la
   * UI —qué corrida se está siguiendo— y obligarla a mirar el libro entero
   * para responderla sólo repartiría la misma derivación por treinta sitios.
   */
  readonly activeRun?: ActiveRun;
  /** Receptor y ligando elegidos. Ausente mientras no se elija ninguno. */
  readonly inputs?: CaseInputs;
  /** Último preflight generado. Puede haber quedado obsoleto: se comprueba. */
  readonly preflight?: PreflightSummary;
  /** Sistema estructural fijado por la primera corrida registrada. */
  readonly structuralSystem?: CaseStructuralSystem;
  /** Decisiones humanas registradas, con el fingerprint al que aplican. */
  readonly decisions?: readonly HumanDecision[];
  /** Disposición científica final, separada de los acuses de controles. */
  readonly disposition?: CaseDisposition;
}

export type CaseDispositionKind = "accept" | "limit" | "abstain";

export interface CaseDisposition {
  readonly kind: CaseDispositionKind;
  readonly rationale: string;
  readonly fingerprint: string;
  readonly at: string;
}

/**
 * Por que un caso conocido no se puede abrir ahora mismo.
 *
 * EXISTE PORQUE OMITIRLO ERA PEOR. La version anterior descartaba del listado
 * los casos ilegibles: el usuario veia desaparecer un caso sin explicacion y sin
 * forma de recuperarlo. Un caso roto sigue siendo un caso, y su fila tiene que
 * decir que le pasa y que se puede hacer.
 */
export interface CaseUnavailable {
  readonly code: CaseErrorCode;
  readonly message: string;
  readonly detail?: string;
  /** Acciones que tienen sentido para ESTE fallo. La UI no las adivina. */
  readonly actions: readonly CaseRecoveryAction[];
}

export type CaseRecoveryAction = "relocate" | "forget" | "repair";

export const CASE_RECOVERY_LABELS: Record<CaseRecoveryAction, string> = {
  relocate: "Relocalizar",
  forget: "Retirar del índice",
  repair: "Reparar",
};

/**
 * Entrada del indice de recientes.
 *
 * NO es la fuente de verdad: el manifiesto en disco lo es. Esto es solo una
 * cache de ubicaciones para poder listar sin abrir cada carpeta.
 */
export interface CaseIndexEntry {
  readonly id: string;
  /** Propietario persistido; ausente sólo durante migración legacy. */
  readonly ownerUserId?: string;
  readonly name: string;
  readonly status: CaseStatus;
  /** Orden estable del panel: abrir o evaluar un caso nunca cambia su nacimiento. */
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly lastOpenedAt: string;
  readonly archived: boolean;
  readonly storageMode: CaseStorageMode;
  /** Solo en modo carpeta. Ausente en navegador: no se fabrican rutas falsas. */
  readonly path?: string;
  /** Presente si el caso NO se puede abrir. Nunca se omite la fila. */
  readonly unavailable?: CaseUnavailable;
  /** El manifiesto se salvo del backup: se dice, no se disimula. */
  readonly recoveredFromBackup?: boolean;
  /** Última corrida del caso; sólo las no terminales bloquean. */
  readonly activeRun?: ActiveRun;
}

/**
 * Acciones base para cada causa.
 *
 * `repair` NO se incluye aqui: sólo tiene sentido si el almacenamiento guarda
 * una copia de seguridad de la que restaurar, y eso lo sabe el repositorio.
 * Ofrecer un boton "Reparar" que no repara nada es peor que no ofrecerlo.
 */
export function recoveryActionsFor(code: CaseErrorCode): readonly CaseRecoveryAction[] {
  switch (code) {
    case "NOT_FOUND":
      // La carpeta se movió o se borró: relocalizar o quitar del índice.
      return ["relocate", "forget"];
    case "UNAUTHORIZED":
      // El registro perdió la autorización: hay que volver a elegir la carpeta.
      return ["relocate", "forget"];
    case "INVALID_MANIFEST":
      // `repair` lo añade el repositorio si de verdad puede restaurar.
      return ["forget"];
    case "UNSUPPORTED_VERSION":
      // Nada que reparar desde aquí: el build es demasiado viejo.
      return ["forget"];
    default:
      return ["forget"];
  }
}

// ── Errores tipados ──────────────────────────────────────────────────
// Un manifiesto invalido NO produce un caso parcial: produce un error
// explicito con su razon. Ver `schema.ts`.

export type CaseErrorCode =
  | "INVALID_MANIFEST"
  | "UNSUPPORTED_VERSION"
  | "UNSAFE_NAME"
  | "NOT_FOUND"
  | "ALREADY_EXISTS"
  | "IO_ERROR"
  | "UNSUPPORTED_OPERATION"
  /** El caso o la carpeta no están autorizados: lo emite la frontera de Rust. */
  | "UNAUTHORIZED";

export class CaseError extends Error {
  readonly code: CaseErrorCode;
  readonly detail?: string;

  constructor(code: CaseErrorCode, message: string, detail?: string) {
    super(message);
    this.name = "CaseError";
    this.code = code;
    this.detail = detail;
  }
}

/** Cuenta las preguntas de contexto sin responder, por severidad. */
export interface PendingContextSummary {
  readonly warnings: number;
  readonly info: number;
  readonly total: number;
}

export function summarizePendingContext(context: CaseContext): PendingContextSummary {
  let warnings = 0;
  let info = 0;
  for (const spec of CASE_CONTEXT_SPECS) {
    const value = context[spec.field];
    const answered = typeof value === "string" && value.trim().length > 0;
    if (answered) continue;
    if (spec.severity === "info") info += 1;
    else warnings += 1;
  }
  return { warnings, info, total: warnings + info };
}
