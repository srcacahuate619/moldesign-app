"use client";

/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V4
 * Preparación estructural: estados vacíos honestos y requisitos legibles.
 *
 * Cableado (2026-09-27): la auditoría la decide el backend
 * (`POST /evaluation/dossier/{id}/preparacion`, `services/dossier/preparacion.py`).
 * Esta página no recalcula estados, no agrega y no convierte una ausencia en
 * «cumple»: pinta lo que llega, por clave. Los casos se leen en sólo lectura
 * con el mismo repositorio que el traspaso del invitado; montar otro
 * `CaseProvider` aquí duplicaría el autoguardado del caso abierto en Evaluación.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";
import { useAuth } from "@/lib/auth";
import { crearRepositorioDeCasos } from "@/lib/cases/factory";
import type { CaseIndexEntry, CaseRecord, RunInputsRelation } from "@/lib/cases/types";
import {
  buildCaseProjection,
  DossierError,
  dossierPackageFilename,
  requestDossierPackage,
  requestPreparacion,
  saveBlobAs,
} from "@/lib/dossier";
import {
  corridaDelCaso,
  valorVisible,
  type AuditoriaPreparacion,
  type BloquePreparacionId,
  type CorridaAuditable,
  type EstadoBloque,
  type EstadoCampo,
  type EstadoPreparacion,
  type RequisitoPreparacion,
} from "@/lib/preparacion";
import {
  ArrowRight, Boxes, Check, ChevronDown, CircleHelp, ClipboardCheck,
  Database, FileArchive, FlaskConical, Layers3, LoaderCircle, LockKeyhole, RefreshCw,
  ScanSearch, ShieldAlert, SquareDashed,
} from "lucide-react";

type GateId = BloquePreparacionId;
type Locale = "es" | "en";

const gates = {
  receptor: {
    number: "01", icon: Boxes,
    es: { name: "Receptor y sitio", summary: "Identidad de la estructura, cadenas, residuos y sitio de unión.", details: ["Estructura y cadena trazables", "Huecos o residuos incompletos declarados", "Sitio y caja de trabajo identificados"] },
    en: { name: "Receptor and site", summary: "Structure identity, chains, residues and binding site.", details: ["Traceable structure and chain", "Gaps or incomplete residues declared", "Site and search box identified"] },
  },
  ligando: {
    number: "02", icon: FlaskConical,
    es: { name: "Estado químico", summary: "Protonación, tautomería y estereoquímica del ligando.", details: ["Estado usado en la evaluación", "Alternativas sin resolver visibles", "Identidad química reproducible"] },
    en: { name: "Chemical state", summary: "Ligand protonation, tautomerism and stereochemistry.", details: ["State used in the evaluation", "Unresolved alternatives visible", "Reproducible chemical identity"] },
  },
  pose: {
    number: "03", icon: ScanSearch,
    es: { name: "Pose y correspondencia", summary: "Coordenadas, selección de pose y mapeo entre ligandos.", details: ["Pose de origen recuperable", "Regla de selección documentada", "Correspondencia atómica de la serie"] },
    en: { name: "Pose and mapping", summary: "Coordinates, pose selection and mapping between ligands.", details: ["Source pose recoverable", "Selection rule documented", "Atomic mapping across the series"] },
  },
  entorno: {
    number: "04", icon: Layers3,
    es: { name: "Entorno del sitio", summary: "Aguas, metales, cofactores y decisiones de preparación.", details: ["Componentes cercanos identificados", "Tratamiento de aguas declarado", "Decisiones sobre metales y cofactores"] },
    en: { name: "Site environment", summary: "Waters, metals, cofactors and preparation decisions.", details: ["Nearby components identified", "Water handling declared", "Metal and cofactor decisions"] },
  },
  procedencia: {
    number: "05", icon: Database,
    es: { name: "Procedencia y entrega", summary: "Archivos, versiones, hashes y límites de la transferencia.", details: ["Archivos de entrada y salida verificables", "Versiones y parámetros de la corrida", "Ambigüedades pendientes conservadas"] },
    en: { name: "Provenance and handoff", summary: "Files, versions, hashes and transfer limits.", details: ["Verifiable input and output files", "Run versions and parameters", "Pending ambiguities preserved"] },
  },
} as const;

/** Nombre de cada requisito por su clave estable. Sin entrada, se usa la etiqueta del backend. */
const requisitos: Record<string, Record<Locale, string>> = {
  "receptor.identidad": { es: "Receptor preparado", en: "Prepared receptor" },
  "receptor.cadenas": { es: "Cadenas del receptor", en: "Receptor chains" },
  "receptor.caja": { es: "Caja de trabajo", en: "Search box" },
  "receptor.cadenas_excluidas": { es: "Cadenas excluidas junto al sitio", en: "Excluded chains near the site" },
  "receptor.residuos_retirados": { es: "Residuos retirados por la preparación", en: "Residues removed by preparation" },
  "receptor.cadenas_truncadas": { es: "Cadenas laterales truncadas", en: "Truncated side chains" },
  "receptor.huecos": { es: "Huecos del esqueleto", en: "Backbone gaps" },
  "receptor.protonacion": { es: "Protonación del receptor", en: "Receptor protonation" },
  "ligando.identidad": { es: "Ligando acoplado", en: "Docked ligand" },
  "ligando.ph": { es: "pH de protonación", en: "Protonation pH" },
  "ligando.especie": { es: "Especie acoplada", en: "Docked species" },
  "ligando.tautomero": { es: "Tautómero", en: "Tautomer" },
  "ligando.estereoquimica": { es: "Estereoquímica", en: "Stereochemistry" },
  "pose.origen": { es: "Poses de la corrida", en: "Run poses" },
  "pose.validez_fisica": { es: "Validez física de la pose principal", en: "Physical validity of the main pose" },
  "pose.regla_de_seleccion": { es: "Regla de selección", en: "Selection rule" },
  "pose.correspondencia_serie": { es: "Correspondencia atómica de la serie", en: "Atomic mapping across the series" },
  "entorno.metales_cofactores": { es: "Metales y cofactores junto al sitio", en: "Metals and cofactors near the site" },
  "entorno.aguas": { es: "Aguas junto al sitio", en: "Waters near the site" },
  "entorno.otras_especies": { es: "Otras especies junto al sitio", en: "Other species near the site" },
  "entorno.politica": { es: "Política de heteroátomos", en: "Heteroatom policy" },
  "procedencia.hashes": { es: "Hashes de entrada y salida", en: "Input and output hashes" },
  "procedencia.versiones": { es: "Versiones de la corrida", en: "Run versions" },
  "procedencia.semilla": { es: "Semilla y parámetros", en: "Seed and parameters" },
  "procedencia.commit": { es: "Commit de código", en: "Code commit" },
  "procedencia.relacion": { es: "Relación con los inputs del caso", en: "Relation to the case inputs" },
  "procedencia.previa_bloqueantes": { es: "Bloqueantes de la comprobación previa", en: "Pre-check blockers" },
  "procedencia.previa_advertencias": { es: "Advertencias de la comprobación previa", en: "Pre-check warnings" },
  "procedencia.previa_sin_evaluar": { es: "Controles previos sin evaluar", en: "Pre-checks not evaluated" },
};

const estadosCampo: Record<EstadoCampo, Record<Locale, string>> = {
  NO_DEFINIDO: { es: "NO DEFINIDO", en: "NOT DEFINED" },
  NO_EVALUADO: { es: "NO EVALUADO", en: "NOT EVALUATED" },
  NO_DISPONIBLE: { es: "NO DISPONIBLE", en: "NOT AVAILABLE" },
  NO_APLICA: { es: "NO APLICA", en: "NOT APPLICABLE" },
  REVISAR: { es: "REVISAR", en: "REVIEW" },
  ABSTENCION: { es: "ABSTENCIÓN", en: "ABSTENTION" },
  REGISTRADO: { es: "REGISTRADO", en: "RECORDED" },
  PASA: { es: "PASA", en: "PASSES" },
};

const copy = {
  es: {
    eyebrow: "PREPARACIÓN ESTRUCTURAL",
    intro: "Reúne las decisiones que convierten una pose en un sistema transferible. Una revisión honesta distingue lo resuelto, lo que requiere juicio y lo que impide continuar.",
    draft: "Auditor en desarrollo",
    source: "EVALUACIÓN DE ORIGEN",
    sourceTitle: "Selecciona una corrida",
    sourceMissing: "Aún no hay una evaluación vinculada.",
    sourceDetail: "Aquí aparecerán el receptor, el ligando y la ejecución exacta elegida. El estado de preparación dependerá de esa evidencia.",
    sourceAction: "Se audita la última corrida terminada de cada caso",
    sourceLogin: "Inicia sesión para elegir uno de tus casos.",
    sourceLoading: "Cargando casos…",
    sourceEmpty: "Todavía no hay casos. Crea uno y evalúa una molécula en Evaluación.",
    sourceGo: "Ir a Evaluación",
    sourcePick: "Caso",
    sourcePlaceholder: "Elige un caso…",
    sourceRun: "Corrida",
    sourceReceptor: "Receptor",
    sourceLigand: "Ligando",
    sourceListError: "No se pudieron leer los casos",
    sinCorrida: "Este caso no tiene ninguna corrida. Evalúa una molécula antes de auditar su preparación.",
    sinTerminar: "La última corrida de este caso no ha terminado. Sólo se audita una corrida terminada.",
    sinMolecula: "La corrida terminó, pero el caso no guardó su molécula. Ábrelo en Evaluación para recuperar el resultado.",
    relation: {
      corresponde: "La corrida corresponde a los inputs actuales del caso.",
      corrida_anterior: "Los inputs del caso cambiaron después de esta corrida: se audita la corrida, no la hipótesis actual.",
      desconocida: "La corrida no guardó la huella de sus inputs.",
    } as Record<RunInputsRelation, string>,
    board: "MAPA DE PREPARACIÓN",
    boardTitle: "Lo que debe quedar explícito",
    boardHint: "Abre cada bloque para ver qué evidencia se revisó y con qué resultado.",
    unevaluated: "SIN EVALUAR",
    blockState: { BLOQUEADO: "BLOQUEADO", REVISION: "REVISIÓN", REGISTRADO: "REGISTRADO" } as Record<EstadoBloque, string>,
    essential: "imprescindible",
    source_: "fuente",
    status: "ESTADO DEL SISTEMA",
    pending: "Pendiente de una corrida",
    pendingText: "Ningún requisito se marca como cumplido hasta comprobar los archivos y decisiones de la evaluación seleccionada.",
    auditing: "Auditando la corrida…",
    globalState: { BLOQUEADO: "Bloqueado", REVISION: "Revisión", TRANSFERIBLE: "Transferible" } as Record<EstadoPreparacion, string>,
    counts: (b: number, r: number) => `${b} imprescindible(s) sin resolver · ${r} para revisar`,
    razon: {
      BLOQUEADO: "Falta evidencia imprescindible o hay una abstención declarada.",
      REVISION: "Hay decisiones científicas abiertas que el cálculo siguiente heredaría.",
      techo: "Todos los requisitos tienen dato registrado, pero la transferencia a un cálculo FEP no está demostrada: FEP-06 sigue sin sellar.",
      TRANSFERIBLE: "Controles superados para el alcance declarado.",
    },
    alcance: "Auditor de readiness para FEP en desarrollo",
    refresh: "Volver a auditar",
    auditError: "No se pudo auditar la corrida",
    legend: "ESTADOS POSIBLES",
    blocked: "Bloqueado",
    blockedDesc: "Falta evidencia imprescindible.",
    review: "Revisión",
    reviewDesc: "Hay una decisión científica abierta.",
    ready: "Transferible",
    readyDesc: "Controles superados para el alcance declarado. No se emite mientras FEP-06 no esté sellado.",
    transfer: "PAQUETE DE TRANSFERENCIA",
    transferTitle: "Una salida reproducible",
    transferText: "La entrega reunirá estructuras, decisiones, parámetros y un manifiesto verificable. Una pose atractiva por sí sola no basta.",
    export: "Descargar paquete de la corrida",
    exporting: "Preparando paquete…",
    exportHint: "Disponible cuando haya una corrida auditada.",
    exportNote: "Es el paquete reproducible del dossier de esta corrida. No es un paquete FEP.",
    exportSaved: "Paquete guardado",
    exportError: "No se pudo preparar el paquete",
    noBackend: "Auditor de readiness para FEP en desarrollo · la transferencia a un cálculo FEP no está demostrada",
  },
  en: {
    eyebrow: "STRUCTURAL PREPARATION",
    intro: "Gather the decisions that turn a pose into a transferable system. An honest review separates what is resolved, what needs judgement and what prevents progress.",
    draft: "Auditor in development",
    source: "SOURCE EVALUATION",
    sourceTitle: "Select a run",
    sourceMissing: "No evaluation is linked yet.",
    sourceDetail: "The exact selected receptor, ligand and run will appear here. Preparation status will depend on that evidence.",
    sourceAction: "Each case's latest finished run is audited",
    sourceLogin: "Sign in to choose one of your cases.",
    sourceLoading: "Loading cases…",
    sourceEmpty: "There are no cases yet. Create one and evaluate a molecule in Evaluation.",
    sourceGo: "Go to Evaluation",
    sourcePick: "Case",
    sourcePlaceholder: "Choose a case…",
    sourceRun: "Run",
    sourceReceptor: "Receptor",
    sourceLigand: "Ligand",
    sourceListError: "Cases could not be read",
    sinCorrida: "This case has no run. Evaluate a molecule before auditing its preparation.",
    sinTerminar: "This case's latest run has not finished. Only a finished run is audited.",
    sinMolecula: "The run finished, but the case did not store its molecule. Open it in Evaluation to recover the result.",
    relation: {
      corresponde: "The run matches the case's current inputs.",
      corrida_anterior: "The case inputs changed after this run: the run is audited, not the current hypothesis.",
      desconocida: "The run did not store its input fingerprint.",
    } as Record<RunInputsRelation, string>,
    board: "PREPARATION MAP",
    boardTitle: "What must be explicit",
    boardHint: "Open each block to see which evidence was reviewed and with what result.",
    unevaluated: "NOT EVALUATED",
    blockState: { BLOQUEADO: "BLOCKED", REVISION: "REVIEW", REGISTRADO: "RECORDED" } as Record<EstadoBloque, string>,
    essential: "essential",
    source_: "source",
    status: "SYSTEM STATUS",
    pending: "Waiting for a run",
    pendingText: "No requirement is marked as passed until the selected evaluation's files and decisions are checked.",
    auditing: "Auditing the run…",
    globalState: { BLOQUEADO: "Blocked", REVISION: "Review", TRANSFERIBLE: "Transferable" } as Record<EstadoPreparacion, string>,
    counts: (b: number, r: number) => `${b} essential item(s) unresolved · ${r} to review`,
    razon: {
      BLOQUEADO: "Essential evidence is missing or an abstention is declared.",
      REVISION: "Scientific decisions remain open that the next calculation would inherit.",
      techo: "Every requirement has recorded data, but transfer to an FEP calculation is not demonstrated: FEP-06 is still unsealed.",
      TRANSFERIBLE: "Checks passed for the declared scope.",
    },
    alcance: "FEP readiness auditor in development",
    refresh: "Audit again",
    auditError: "The run could not be audited",
    legend: "POSSIBLE STATES",
    blocked: "Blocked",
    blockedDesc: "Essential evidence is missing.",
    review: "Review",
    reviewDesc: "A scientific decision remains open.",
    ready: "Transferable",
    readyDesc: "Checks passed for the declared scope. Not issued while FEP-06 is unsealed.",
    transfer: "HANDOFF PACKAGE",
    transferTitle: "A reproducible output",
    transferText: "The handoff will include structures, decisions, parameters and a verifiable manifest. An attractive pose alone is not enough.",
    export: "Download the run package",
    exporting: "Preparing package…",
    exportHint: "Available once a run has been audited.",
    exportNote: "This is the reproducible dossier package of this run. It is not an FEP package.",
    exportSaved: "Package saved",
    exportError: "The package could not be prepared",
    noBackend: "FEP readiness auditor in development · transfer to an FEP calculation is not demonstrated",
  },
};

const colorEstadoGlobal: Record<EstadoPreparacion, string> = {
  BLOQUEADO: "var(--categoria-refutacion)",
  REVISION: "var(--categoria-corrigendum)",
  TRANSFERIBLE: "var(--categoria-hallazgo)",
};

/** Un bloque REGISTRADO tiene todos sus datos; no es «transferible», así que no usa su color. */
const colorEstadoBloque: Record<EstadoBloque, string> = {
  BLOQUEADO: "var(--categoria-refutacion)",
  REVISION: "var(--categoria-corrigendum)",
  REGISTRADO: "var(--text-secondary)",
};

function mensaje(error: unknown): string {
  if (error instanceof DossierError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

export default function PreparacionPage() {
  const { t, locale } = useLanguage();
  const c = copy[locale];
  const { user, isLoading: authLoading } = useAuth();
  const [expanded, setExpanded] = useState<GateId>("receptor");

  const ownerId = user?.user_id ?? null;
  const repository = useMemo(() => (ownerId ? crearRepositorioDeCasos(ownerId) : null), [ownerId]);

  const [casos, setCasos] = useState<readonly CaseIndexEntry[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [casoId, setCasoId] = useState<string>("");
  const [caso, setCaso] = useState<CaseRecord | null>(null);
  const [corrida, setCorrida] = useState<CorridaAuditable | null>(null);
  const [auditoria, setAuditoria] = useState<AuditoriaPreparacion | null>(null);
  const [auditando, setAuditando] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);
  const [exportando, setExportando] = useState(false);
  const [exportMsg, setExportMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  // Sólo manda la última petición: una respuesta tardía de otro caso se descarta.
  const token = useRef(0);

  useEffect(() => {
    if (!repository) return;
    let vivo = true;
    repository
      .listCases()
      .then((lista) => {
        if (!vivo) return;
        setCasos(lista.filter((entrada) => !entrada.archived && !entrada.unavailable));
        setListError(null);
      })
      .catch((error: unknown) => {
        if (vivo) setListError(mensaje(error));
      });
    return () => {
      vivo = false;
    };
  }, [repository]);

  useEffect(() => {
    const mio = ++token.current;
    setAuditoria(null);
    setAuditError(null);
    setExportMsg(null);
    if (!repository || !casoId) {
      setCaso(null);
      setCorrida(null);
      setAuditando(false);
      return;
    }
    const controller = new AbortController();
    setAuditando(true);
    (async () => {
      try {
        const record = await repository.readCase(casoId);
        if (mio !== token.current) return;
        const resuelta = corridaDelCaso(record);
        setCaso(record);
        setCorrida(resuelta);
        if (resuelta.kind !== "auditable") return;
        const projection = buildCaseProjection(record, resuelta.reportable, resuelta.relation);
        const resultado = await requestPreparacion(
          resuelta.reportable.moleculeId, projection, controller.signal,
        );
        if (mio === token.current) setAuditoria(resultado);
      } catch (error) {
        if ((error as { name?: string } | null)?.name === "AbortError") return;
        if (mio === token.current) setAuditError(mensaje(error));
      } finally {
        if (mio === token.current) setAuditando(false);
      }
    })();
    return () => controller.abort();
  }, [repository, casoId, intento]);

  const exportar = useCallback(async () => {
    if (!caso || corrida?.kind !== "auditable" || exportando) return;
    setExportando(true);
    setExportMsg(null);
    try {
      const projection = buildCaseProjection(caso, corrida.reportable, corrida.relation);
      const artefacto = await requestDossierPackage(corrida.reportable.moleculeId, projection);
      const nombre = artefacto.filename ?? dossierPackageFilename(caso.id, corrida.reportable.taskId);
      saveBlobAs(artefacto.blob, nombre);
      setExportMsg({ ok: true, texto: `${c.exportSaved}: ${nombre}` });
    } catch (error) {
      setExportMsg({ ok: false, texto: `${c.exportError}: ${mensaje(error)}` });
    } finally {
      setExportando(false);
    }
  }, [caso, corrida, exportando, c.exportSaved, c.exportError]);

  const bloque = (id: GateId) => auditoria?.bloques.find((b) => b.id === id) ?? null;
  const nombreRequisito = (r: RequisitoPreparacion) => requisitos[r.clave]?.[locale] ?? r.etiqueta;
  const colorRequisito = (r: RequisitoPreparacion) =>
    auditoria?.bloqueantes.includes(r.clave)
      ? "var(--categoria-refutacion)"
      : auditoria?.en_revision.includes(r.clave)
        ? "var(--categoria-corrigendum)"
        : r.estado === "NO_APLICA"
          ? "var(--text-dim)"
          : "var(--text-secondary)";

  /** La frase del backend, por estado; la de techo cuando no queda nada pendiente. */
  const razonGlobal = (a: AuditoriaPreparacion) =>
    a.estado === "REVISION" && a.en_revision.length === 0 && a.bloqueantes.length === 0
      ? c.razon.techo
      : c.razon[a.estado];

  const motivoNoAuditable =
    corrida?.kind === "sin_corrida" ? c.sinCorrida
      : corrida?.kind === "sin_terminar" ? c.sinTerminar
        : corrida?.kind === "sin_molecula" ? c.sinMolecula
          : null;
  const puedeExportar = Boolean(auditoria && corrida?.kind === "auditable" && !exportando);

  return (
    <main className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] px-4 pb-16 pt-8 text-[var(--text)] sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1450px]">
        <header className="mb-8 flex flex-wrap items-start justify-between gap-5 border-b border-[var(--border)] pb-7">
          <div className="max-w-3xl min-w-0">
            <p className="mb-3 font-mono text-[11px] font-bold tracking-[0.22em] text-[var(--accent-strong)]">{c.eyebrow}</p>
            <h1 className="font-display text-3xl font-bold leading-[1.08] tracking-tight [overflow-wrap:anywhere] sm:text-4xl lg:text-5xl">{t("pg_prep_titulo")}</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{c.intro}</p>
          </div>
          <span className="border border-[var(--border-light)] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-dim)]">{c.draft}</span>
        </header>

        <div className="grid items-start gap-7 lg:grid-cols-[minmax(235px,0.8fr)_minmax(360px,1.45fr)_minmax(250px,0.9fr)]">
          <section aria-labelledby="prep-source-title" className="border border-[var(--border)] bg-[var(--bg-card)]">
            <div className="border-b border-[var(--border)] p-5">
              <p className="font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.source}</p>
              <h2 id="prep-source-title" className="mt-2 font-display text-xl font-bold">{c.sourceTitle}</h2>
            </div>
            <div className="p-5">
              {!authLoading && !user ? (
                <p className="text-xs leading-6 text-[var(--text-muted)]">{c.sourceLogin}</p>
              ) : listError ? (
                <p role="alert" className="text-xs leading-6 text-[var(--categoria-refutacion)]">{c.sourceListError}: {listError}</p>
              ) : casos === null ? (
                <p className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><LoaderCircle size={14} className="animate-spin" />{c.sourceLoading}</p>
              ) : casos.length === 0 ? (
                <div className="text-xs leading-6 text-[var(--text-muted)]">
                  <p>{c.sourceEmpty}</p>
                  <Link href="/evaluation" className="mt-3 inline-flex items-center gap-1.5 font-semibold text-[var(--accent-strong)] hover:underline">{c.sourceGo}<ArrowRight size={13} /></Link>
                </div>
              ) : (
                <label className="block">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{c.sourcePick}</span>
                  <select
                    value={casoId}
                    onChange={(event) => setCasoId(event.target.value)}
                    className="mt-2 w-full cursor-pointer border border-[var(--border-light)] bg-[var(--bg-secondary)] px-3 py-2.5 text-sm text-[var(--text)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"
                  >
                    <option value="">{c.sourcePlaceholder}</option>
                    {casos.map((entrada) => <option key={entrada.id} value={entrada.id}>{entrada.name}</option>)}
                  </select>
                </label>
              )}

              {caso && corrida?.kind === "auditable" ? (
                <dl className="mt-5 space-y-3 border-t border-[var(--border)] pt-4 text-xs">
                  <div><dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{c.sourceReceptor}</dt><dd className="mt-1 font-semibold">{caso.inputs?.receptor ? `${caso.inputs.receptor.pdbId}${caso.inputs.receptor.chain ? ` · ${caso.inputs.receptor.chain}` : ""}` : "—"}</dd></div>
                  <div><dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{c.sourceLigand}</dt><dd className="mt-1 break-all font-mono text-[11px] leading-5">{caso.inputs?.ligand?.inputSmiles ?? "—"}</dd></div>
                  <div><dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{c.sourceRun}</dt><dd className="mt-1 break-all font-mono text-[11px]">{corrida.reportable.taskId}</dd></div>
                  <p className="leading-5" style={{ color: corrida.relation === "corresponde" ? "var(--text-muted)" : "var(--categoria-corrigendum)" }}>{c.relation[corrida.relation]}</p>
                </dl>
              ) : (
                <>
                  <div className="mt-5 flex h-40 flex-col items-center justify-center border border-dashed border-[var(--border-light)] bg-[var(--bg-secondary)] p-4 text-center">
                    <SquareDashed size={25} className="text-[var(--accent-strong)]" />
                    <p className="mt-3 text-xs font-semibold">{motivoNoAuditable ?? c.sourceMissing}</p>
                  </div>
                  {!motivoNoAuditable && <p className="mt-5 text-xs leading-6 text-[var(--text-muted)]">{c.sourceDetail}</p>}
                </>
              )}
              <div className="mt-6 flex items-center gap-2 border-t border-[var(--border)] pt-4 font-mono text-[10px] leading-5 text-[var(--text-dim)]"><LockKeyhole size={15} className="shrink-0" />{c.sourceAction}</div>
            </div>
          </section>

          <section aria-labelledby="prep-board-title" className="min-w-0">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div><p className="font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.board}</p><h2 id="prep-board-title" className="mt-2 font-display text-2xl font-bold">{c.boardTitle}</h2></div>
              <p className="max-w-[225px] text-xs leading-5 text-[var(--text-dim)]">{c.boardHint}</p>
            </div>
            <div className="mt-5 border-t border-[var(--border)]">
              {(Object.keys(gates) as GateId[]).map((id) => {
                const item = gates[id];
                const Icon = item.icon;
                const isOpen = expanded === id;
                const datos = bloque(id);
                return (
                  <div key={id} className="border-b border-[var(--border)]">
                    <button type="button" aria-expanded={isOpen} aria-controls={`prep-details-${id}`} onClick={() => setExpanded(id)} className="group flex w-full cursor-pointer items-start gap-4 py-5 text-left transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] active:bg-[var(--bg-card)]">
                      <span className="mt-0.5 font-mono text-[11px] text-[var(--text-dim)]">{item.number}</span>
                      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center border border-[var(--border-light)] text-[var(--accent-strong)]"><Icon size={17} /></span>
                      <span className="min-w-0 flex-1"><span className="block text-sm font-bold">{item[locale].name}</span><span className="mt-1 block text-xs leading-5 text-[var(--text-muted)]">{item[locale].summary}</span></span>
                      <span className="flex shrink-0 items-center gap-2">
                        {datos ? (
                          <span className="font-mono text-[9px] font-bold tracking-[0.08em]" style={{ color: colorEstadoBloque[datos.estado] }}>{c.blockState[datos.estado]}</span>
                        ) : (
                          <span className="hidden font-mono text-[9px] tracking-[0.08em] text-[var(--text-dim)] sm:block">{c.unevaluated}</span>
                        )}
                        <ChevronDown size={16} className={`text-[var(--text-dim)] transition-transform ${isOpen ? "rotate-180" : ""}`} />
                      </span>
                    </button>
                    <div id={`prep-details-${id}`} hidden={!isOpen} className="pb-5 pl-12 sm:pl-16">
                      {datos ? (
                        <ul className="space-y-4">
                          {datos.requisitos.map((r) => {
                            const valor = valorVisible(r);
                            const color = colorRequisito(r);
                            return (
                              <li key={r.clave} className="flex items-start gap-3 text-xs leading-5">
                                <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                                    <span className="font-semibold text-[var(--text-secondary)]">{nombreRequisito(r)}{r.imprescindible && <span className="ml-2 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--text-dim)]">{c.essential}</span>}</span>
                                    <span className="font-mono text-[9px] font-bold tracking-[0.08em]" style={{ color }}>{estadosCampo[r.estado][locale]}</span>
                                  </div>
                                  {valor && <p className="mt-1 break-words text-[var(--text)] [overflow-wrap:anywhere]">{valor}</p>}
                                  {r.razon && <p className="mt-1 text-[var(--text-muted)]">{r.razon}</p>}
                                  <p className="mt-1 break-all font-mono text-[10px] text-[var(--text-dim)]">{c.source_}: {r.fuente}</p>
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <ul className="space-y-2">
                          {item[locale].details.map((detail) => <li key={detail} className="flex items-start gap-3 text-xs leading-5 text-[var(--text-secondary)]"><span className="mt-1.5 size-1.5 shrink-0 rounded-full border border-[var(--accent)]" />{detail}</li>)}
                        </ul>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <aside className="space-y-5">
            <section aria-live="polite" className="border border-[var(--border)] bg-[var(--bg-card)] p-5">
              <p className="font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.status}</p>
              {auditoria ? (
                <>
                  <div className="mt-5 flex items-center gap-3"><ShieldAlert size={22} className="shrink-0" style={{ color: colorEstadoGlobal[auditoria.estado] }} /><h2 className="font-display text-lg font-bold" style={{ color: colorEstadoGlobal[auditoria.estado] }}>{c.globalState[auditoria.estado]}</h2></div>
                  <p className="mt-4 text-xs leading-6 text-[var(--text-secondary)]">{razonGlobal(auditoria)}</p>
                  <p className="mt-3 font-mono text-[10px] leading-5 text-[var(--text-dim)]">{c.counts(auditoria.bloqueantes.length, auditoria.en_revision.length)}</p>
                  <p className="mt-3 border-t border-[var(--border)] pt-3 text-[11px] leading-5 text-[var(--text-muted)]">{c.alcance}</p>
                  <button type="button" onClick={() => setIntento((n) => n + 1)} disabled={auditando} className="mt-4 inline-flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-[var(--accent-strong)] hover:underline disabled:cursor-not-allowed disabled:opacity-60"><RefreshCw size={13} />{c.refresh}</button>
                </>
              ) : auditando ? (
                <p className="mt-5 flex items-center gap-2 text-xs text-[var(--text-muted)]"><LoaderCircle size={15} className="animate-spin" />{c.auditing}</p>
              ) : auditError ? (
                <>
                  <p role="alert" className="mt-5 text-xs leading-6 text-[var(--categoria-refutacion)]">{c.auditError}: {auditError}</p>
                  <button type="button" onClick={() => setIntento((n) => n + 1)} className="mt-3 inline-flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-[var(--accent-strong)] hover:underline"><RefreshCw size={13} />{c.refresh}</button>
                </>
              ) : (
                <>
                  <div className="mt-5 flex items-center gap-3"><ShieldAlert size={22} className="shrink-0 text-[var(--text-dim)]" /><h2 className="font-display text-lg font-bold">{c.pending}</h2></div>
                  <p className="mt-4 text-xs leading-6 text-[var(--text-muted)]">{c.pendingText}</p>
                </>
              )}
            </section>
            <section className="border border-[var(--border)] bg-[var(--bg-card)] p-5">
              <h2 className="font-mono text-[10px] tracking-[0.18em] text-[var(--text-dim)]">{c.legend}</h2>
              <dl className="mt-5 space-y-4">
                {([
                  { name: c.blocked, desc: c.blockedDesc, color: "var(--categoria-refutacion)" },
                  { name: c.review, desc: c.reviewDesc, color: "var(--categoria-corrigendum)" },
                  { name: c.ready, desc: c.readyDesc, color: "var(--categoria-hallazgo)" },
                ]).map((item) => <div key={item.name} className="flex gap-3"><span className="mt-1 size-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} /><div><dt className="text-xs font-bold">{item.name}</dt><dd className="mt-1 text-xs leading-5 text-[var(--text-muted)]">{item.desc}</dd></div></div>)}
              </dl>
            </section>
            <section className="border-t border-[var(--border)] pt-6">
              <div className="flex items-center gap-2 text-[var(--accent-strong)]"><FileArchive size={18} /><p className="font-mono text-[10px] tracking-[0.17em]">{c.transfer}</p></div>
              <h2 className="mt-3 font-display text-xl font-bold">{c.transferTitle}</h2>
              <p className="mt-3 text-xs leading-6 text-[var(--text-muted)]">{c.transferText}</p>
              <button
                type="button"
                onClick={exportar}
                disabled={!puedeExportar}
                aria-describedby="prep-export-hint"
                className={`mt-6 flex w-full items-center justify-between px-4 py-4 text-sm font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${puedeExportar ? "cursor-pointer bg-[var(--accent-strong)] text-[var(--bg)] hover:opacity-90" : "cursor-not-allowed bg-[var(--border)] text-[var(--text-muted)] opacity-70"}`}
              >
                <span className="flex items-center gap-2">{exportando ? <LoaderCircle size={17} className="animate-spin" /> : <ClipboardCheck size={17} />}{exportando ? c.exporting : c.export}</span><ArrowRight size={16} />
              </button>
              <p id="prep-export-hint" className="mt-3 text-xs leading-5 text-[var(--text-dim)]">{auditoria ? c.exportNote : c.exportHint}</p>
              {exportMsg && (
                <p role={exportMsg.ok ? "status" : "alert"} className="mt-2 flex items-start gap-1.5 text-xs leading-5" style={{ color: exportMsg.ok ? "var(--text-secondary)" : "var(--categoria-refutacion)" }}>
                  {exportMsg.ok && <Check size={14} className="mt-0.5 shrink-0" />}{exportMsg.texto}
                </p>
              )}
            </section>
          </aside>
        </div>
        <p className="mt-10 flex items-center gap-2 border-t border-[var(--border)] pt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-dim)]"><CircleHelp size={14} />{c.noBackend}</p>
      </div>
    </main>
  );
}
