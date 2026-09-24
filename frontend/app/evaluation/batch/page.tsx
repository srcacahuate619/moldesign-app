"use client";

// =====================================================================
// Cohortes — define, comprueba, congela, ejecuta, documenta
// =====================================================================
//
// SUSTITUYE al Batch histórico en la interfaz. La ruta se conserva para no
// romper enlaces, pero el flujo es otro y no llama a `/evaluation/batch` en
// ninguna parte.
//
// QUÉ DESAPARECE, Y POR QUÉ:
//
//   ALL / multi-target   dos filas acopladas contra receptores distintos no
//                        son comparables aunque compartan tabla
//   Early Exit           filtraba qué llegaba a docking sin declararlo
//   total_score 0-100    presentaba una puntuación agregada como veredicto
//   «mejor fármaco»      un acoplamiento no demuestra actividad
//   tiempo estimado      el backend no lo mide; inventarlo aquí sería una
//                        cifra sin medida detrás
//
// QUÉ APARECE:
//
//   1 Definir · 2 Comprobar · 3 Guardar · 4 Ejecutar · 5 Evidencia · 6 Informe
//
// EL ESTADO VIVE EN EL BACKEND. Al recargar, la corrida se recupera
// preguntando —no restaurando algo que la pestaña recordaba—, porque la corrida
// es durable y sobrevive al cierre de la aplicación.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle, ArrowLeft, CheckCircle2, Download, FileArchive, FileSpreadsheet,
  FileText, Loader2, Play, RefreshCw, Save, Search, XCircle,
} from "lucide-react";

import {
  CONTROL_ROLE_LABELS, CohortError, ROW_STATUS_LABELS, RUN_STATUS_LABELS,
  SORT_BY_OBSERVED_AFFINITY, cancelRun, createCohort, dossierPackage, dossierPreview,
  getCohort, getEvidence, getLatestRun, getRun, isRunActive, listCohorts, openRun, preflightCohort,
  resumeRun,
  type CohortListItem, type CohortPreflightResult, type CohortRecord, type CohortRun,
  type CohortStudy, type RunEvidence, type RowStatus,
} from "../../../lib/cohorts";
import { EstimacionDeCorrida } from "../../../components/evaluation/EstimacionDeCorrida";
import { type Target } from "../../../lib/api";
import { obtenerCatalogo } from "../../../lib/catalogoDeReceptores";
import { saveBlobAs } from "../../../lib/dossier";
import { beginFileDownload, failFileDownload, notifyRunFinished } from "../../../lib/activityNotifications";
import { getUserItem, removeUserItem, setUserItem } from "../../../lib/userStorage";
import TargetSelectorModal from "../../../components/interfaces/pro/TargetSelectorModal";
import { TRANSLATIONS, useLanguage } from "../../../context/LanguageContext";

type Paso = "definir" | "comprobar" | "guardar" | "ejecutar" | "evidencia" | "informe";

// Las constantes de modulo no pueden llamar a `t()` —viven fuera de React— asi
// que llevan la CLAVE y la traduce quien las pinta. Es lo que permite que el
// idioma cambie sin recargar: el texto se resuelve en cada render.
const PASOS: readonly { readonly id: Paso; readonly n: number; readonly clave: string }[] = [
  { id: "definir", n: 1, clave: "lo_paso_definir" },
  { id: "comprobar", n: 2, clave: "lo_paso_comprobar" },
  { id: "guardar", n: 3, clave: "lo_paso_guardar" },
  { id: "ejecutar", n: 4, clave: "lo_paso_ejecutar" },
  { id: "evidencia", n: 5, clave: "lo_paso_evidencia" },
  { id: "informe", n: 6, clave: "lo_paso_informe" },
];

const FILTROS: readonly { readonly id: RowStatus | "todas"; readonly clave: string }[] = [
  { id: "todas", clave: "lo_filtro_todas" },
  { id: "completed", clave: "lo_filtro_completadas" },
  { id: "duplicate_reused", clave: "lo_filtro_duplicados" },
  { id: "failed", clave: "lo_filtro_fallidas" },
  { id: "not_evaluated", clave: "lo_filtro_no_evaluadas" },
];

const CAJA = "rounded-lg border border-zinc-200 bg-white dark:border-white/10 dark:bg-white/[0.02]";
const ETIQUETA = "text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-white/65";
const INPUT =
  "w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 " +
  "outline-none transition-colors focus-visible:border-brand-500 focus-visible:ring-2 focus-visible:ring-brand-500/30 " +
  "dark:border-white/10 dark:bg-black/30 dark:text-white/90 dark:focus-visible:border-brand-400/60";
const BOTON =
  "inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 focus-visible:ring-offset-2 " +
  "focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:opacity-40 dark:focus-visible:ring-offset-[#08090c]";
const PRIMARIO = `${BOTON} bg-brand-600 text-white hover:bg-brand-500`;
const SECUNDARIO = `${BOTON} border border-zinc-300 bg-zinc-50 text-zinc-700 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70 dark:hover:text-white`;

/**
 * El codigo de la comprobacion previa a su clave de traduccion.
 *
 * Se conserva el codigo del backend tal cual —`lo_msg_ARCHIVO_ILEGIBLE`— para
 * poder cruzarlo de un vistazo con `services/cohort/`. Un codigo que el backend
 * anada y aqui falte cae en `lo_msg_desconocido`, que dice que hay una
 * condicion sin describir en vez de callarla.
 */
function claveDelMensaje(codigo: string): string {
  const clave = `lo_msg_${codigo}`;
  return clave in TRANSLATIONS.es ? clave : "lo_msg_desconocido";
}

/**
 * Texto de un fallo. `t` entra por parametro porque esto vive fuera de React.
 *
 * El mensaje de `CohortError` lo compone el backend y viaja en el idioma en que
 * lo escribio; traducirlo aqui exigiria adivinar su contenido. Lo que si se
 * traduce es el respaldo, que es nuestro.
 */
function mensajeDe(error: unknown, t: (clave: string) => string): string {
  if (error instanceof CohortError) return error.message;
  return (error as Error)?.message || t("lo_operacion_fallida");
}


export default function CohortesPage() {
  // Toda la pantalla pasa por `t()`: es la superficie con mas texto de la
  // aplicacion y la que peor tolera una traduccion a medias, porque aqui se
  // declara lo que una corrida NO midio.
  const { t } = useLanguage();

  // ── Definición ────────────────────────────────────────────────────
  const [nombre, setNombre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [pdbId, setPdbId] = useState("");
  const [cadena, setCadena] = useState("");
  const [exhaustividad, setExhaustividad] = useState(8);
  const [poses, setPoses] = useState(5);
  const [semilla, setSemilla] = useState<string>("");
  const [workers, setWorkers] = useState(2);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(true);
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [showTargetModal, setShowTargetModal] = useState(false);

  // ── Flujo ─────────────────────────────────────────────────────────
  const [paso, setPaso] = useState<Paso>("definir");
  const [preflight, setPreflight] = useState<CohortPreflightResult | null>(null);
  const [cohorte, setCohorte] = useState<CohortRecord | null>(null);
  const [corrida, setCorrida] = useState<CohortRun | null>(null);
  const [evidencia, setEvidencia] = useState<RunEvidence | null>(null);
  const [guardadas, setGuardadas] = useState<CohortListItem[]>([]);
  const [filtro, setFiltro] = useState<RowStatus | "todas">("todas");

  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [pollNonce, setPollNonce] = useState(0);
  const pollEpoch = useRef(0);
  const pollTimer = useRef<number | null>(null);

  // ── Informe ───────────────────────────────────────────────────────
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [pdfNombre, setPdfNombre] = useState<string | null>(null);
  const objectUrl = useRef<string | null>(null);
  const [zipGuardado, setZipGuardado] = useState<string | null>(null);

  const publicarPdf = useCallback((url: string | null) => {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = url;
    setPdfUrl(url);
  }, []);

  // Revocación al desmontar. Un blob de varios MB retenido por visita es una
  // fuga que el usuario paga en memoria.
  useEffect(() => {
    return () => {
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
    };
  }, []);

  const estudio: CohortStudy | null = useMemo(() => {
    if (!nombre.trim() || !pdbId.trim()) return null;
    return {
      schema_version: 1,
      name: nombre.trim(),
      receptor: { pdb_id: pdbId.trim().toUpperCase(), ...(cadena.trim() ? { chain: cadena.trim().toUpperCase() } : {}) },
      config: {
        docking_engine: "vina",
        exhaustiveness: exhaustividad,
        num_poses: poses,
        ...(semilla.trim() ? { seed: Number(semilla) } : {}),
      },
    };
  }, [nombre, pdbId, cadena, exhaustividad, poses, semilla]);

  const bloqueada = Boolean(preflight && preflight.decision === "blocked");
  const motorHistoricoQuickVina =
    cohorte?.preflight.normalized_study.config.docking_engine === "qvina2";

  // Batch comparte el catálogo canónico con {t("evaluation")}. El campo manual sigue
  // disponible porque no poder listar el catálogo no invalida un PDB conocido.
  const cargarTargets = useCallback(async () => {
    setLoadingTargets(true);
    setTargetsError(null);
    try {
      setTargets([...(await obtenerCatalogo())]);
    } catch (fallo) {
      setTargetsError(t("lo_catalogo_no_cargado", { detalle: mensajeDe(fallo, t) }));
    } finally {
      setLoadingTargets(false);
    }
  }, []);

  useEffect(() => {
    void cargarTargets();
  }, [cargarTargets]);

  const seleccionarTarget = useCallback((targetId: string) => {
    const normalizado = targetId.trim().toUpperCase();
    const elegido = targets.find((item) =>
      item.pdb_id.toUpperCase() === normalizado || item.id?.toUpperCase() === normalizado
    );
    setPdbId((elegido?.pdb_id ?? normalizado).toUpperCase());
    // La cadena pertenece al receptor: no se debe conservar la del target anterior.
    setCadena(elegido?.chain?.trim().toUpperCase() ?? "");
    setShowTargetModal(false);
  }, [targets]);

  const restaurarDefinicion = useCallback((registro: CohortRecord) => {
    const estudioGuardado = registro.preflight.normalized_study;
    setCohorte(registro);
    setPreflight(registro.preflight);
    setNombre(registro.name);
    setArchivo(null);
    setPdbId(estudioGuardado.receptor.pdb_id);
    setCadena(estudioGuardado.receptor.chain ?? "");
    setExhaustividad(estudioGuardado.config.exhaustiveness);
    setPoses(estudioGuardado.config.num_poses);
    setSemilla(estudioGuardado.config.seed == null ? "" : String(estudioGuardado.config.seed));
  }, []);

  // ── Lista lateral ─────────────────────────────────────────────────
  const refrescarLista = useCallback(async () => {
    try {
      setGuardadas(await listCohorts());
    } catch {
      // El listado es orientación, no el trabajo. Un fallo aquí no puede
      // tapar la pantalla; el error de la operación en curso sí se muestra.
    }
  }, []);

  useEffect(() => {
    void refrescarLista();
  }, [refrescarLista]);

  // ── Recuperación al recargar ──────────────────────────────────────
  // La corrida es durable: si esta pestaña recuerda un `run_id`, se le
  // pregunta al backend por su estado real. No se restaura desde localStorage
  // nada que el backend pueda contradecir.
  useEffect(() => {
    const guardado = getUserItem("moldesign_cohort_run");
    if (!guardado || corrida) return;
    let vivo = true;
    (async () => {
      try {
        const recuperada = await getRun(guardado);
        if (!vivo) return;
        const suya = await getCohort(recuperada.cohort_id);
        if (!vivo) return;
        restaurarDefinicion(suya);
        setCorrida(recuperada);
        setPaso("ejecutar");
      } catch {
        if (vivo) removeUserItem("moldesign_cohort_run");
      }
    })();
    return () => {
      vivo = false;
    };
    // Sólo al montar: recuperar es una operación de arranque.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restaurarDefinicion]);

  // ── Sondeo del progreso ───────────────────────────────────────────
  useEffect(() => {
    pollEpoch.current += 1;
    const epoch = pollEpoch.current;
    if (pollTimer.current !== null) window.clearTimeout(pollTimer.current);
    pollTimer.current = null;
    setPollError(null);
    if (!corrida || !isRunActive(corrida.status)) return;
    let failures = 0;
    const schedule = (delay: number) => {
      if (pollEpoch.current !== epoch) return;
      pollTimer.current = window.setTimeout(() => void poll(), delay);
    };
    const poll = async () => {
      if (pollEpoch.current !== epoch) return;
      try {
        const next = await getRun(corrida.id);
        if (pollEpoch.current !== epoch) return;
        failures = 0;
        setPollError(null);
        if (!isRunActive(next.status) && next.status !== "cancelled" && next.status !== "interrupted") {
          notifyRunFinished({
            source: "batch",
            runId: next.id,
            successful: next.status === "completed" || next.status === "completed_with_exceptions",
            withExceptions: next.status === "completed_with_exceptions",
          });
        }
        setCorrida(next);
        if (isRunActive(next.status)) schedule(2500);
      } catch {
        if (pollEpoch.current !== epoch) return;
        failures += 1;
        if (failures >= 5) {
          setPollError(t("lo_seguimiento_interrumpido"));
          return;
        }
        schedule(Math.min(15000, 2500 * 2 ** (failures - 1)));
      }
    };
    void poll();
    return () => {
      pollEpoch.current += 1;
      if (pollTimer.current !== null) window.clearTimeout(pollTimer.current);
      pollTimer.current = null;
    };
  }, [corrida?.id, corrida?.status, pollNonce]);

  // ── Acciones ──────────────────────────────────────────────────────
  async function ejecutar<T>(clave: string, accion: () => Promise<T>): Promise<T | null> {
    setOcupado(clave);
    setError(null);
    try {
      return await accion();
    } catch (fallo) {
      setError(mensajeDe(fallo, t));
      return null;
    } finally {
      setOcupado(null);
    }
  }

  const comprobar = () =>
    ejecutar("comprobar", async () => {
      if (!archivo || !estudio) return null;
      const resultado = await preflightCohort(archivo, estudio);
      setPreflight(resultado);
      setCohorte(null);
      setCorrida(null);
      setEvidencia(null);
      setPaso("comprobar");
      return resultado;
    });

  const seleccionarArchivo = (siguiente: File | null) => {
    setArchivo(siguiente);
    if (!siguiente) return;

    // Un archivo nuevo inicia otra cohorte. No debe heredar ni siquiera la
    // proyección visual del motor de un registro histórico abierto.
    setPreflight(null);
    setCohorte(null);
    setCorrida(null);
    setEvidencia(null);
    publicarPdf(null);
    setPdfBlob(null);
    setZipGuardado(null);
    removeUserItem("moldesign_cohort_run");
    setPaso("definir");
  };

  const guardar = () =>
    ejecutar("guardar", async () => {
      if (!archivo || !estudio || !preflight) return null;
      // Una cohorte bloqueada no es una entrada ejecutable: no se guarda.
      if (preflight.decision !== "ready") return null;
      const registro = await createCohort(archivo, estudio, preflight.cohort_fingerprint);
      setCohorte(registro);
      setPaso("guardar");
      await refrescarLista();
      return registro;
    });

  const lanzar = () =>
    ejecutar("ejecutar", async () => {
      if (!cohorte || motorHistoricoQuickVina) return null;
      const aceptada = await openRun(cohorte.id, workers);
      setUserItem("moldesign_cohort_run", aceptada.run_id);
      setCorrida(await getRun(aceptada.run_id));
      setPaso("ejecutar");
      return aceptada;
    });

  const cancelar = () =>
    ejecutar("cancelar", async () => {
      if (!corrida) return null;
      setCorrida(await cancelRun(corrida.id));
      return true;
    });

  const reanudar = () =>
    ejecutar("reanudar", async () => {
      if (!corrida || motorHistoricoQuickVina) return null;
      await resumeRun(corrida.id, workers);
      setCorrida(await getRun(corrida.id));
      return true;
    });

  const verEvidencia = () =>
    ejecutar("evidencia", async () => {
      if (!corrida) return null;
      const resumen = await getEvidence(corrida.id, SORT_BY_OBSERVED_AFFINITY);
      setEvidencia(resumen);
      setPaso("evidencia");
      return resumen;
    });

  const verInforme = () =>
    ejecutar("informe", async () => {
      if (!corrida) return null;
      publicarPdf(null);
      setPdfBlob(null);
      setZipGuardado(null);
      const { blob, filename } = await dossierPreview(corrida.id);
      publicarPdf(URL.createObjectURL(blob));
      setPdfBlob(blob);
      setPdfNombre(filename);
      setPaso("informe");
      return true;
    });

  const descargarPdf = () => {
    if (!pdfBlob) return;
    saveBlobAs(pdfBlob, pdfNombre ?? "dossier_cohorte.pdf", "batch");
  };

  const exportarZip = () =>
    ejecutar("zip", async () => {
      if (!corrida) return null;
      const proposedName = `cohorte_${corrida.id}.zip`;
      const activityId = beginFileDownload(proposedName, "batch");
      try {
        const { blob, filename } = await dossierPackage(corrida.id);
        const nombreZip = filename ?? proposedName;
        saveBlobAs(blob, nombreZip, "batch", activityId);
        setZipGuardado(nombreZip);
        return true;
      } catch (failure) {
        failFileDownload(activityId, proposedName, "batch");
        throw failure;
      }
    });

  const abrirGuardada = (item: CohortListItem) =>
    ejecutar("abrir", async () => {
      const registro = await getCohort(item.id);
      restaurarDefinicion(registro);
      setCorrida(null);
      setEvidencia(null);
      setFiltro("todas");
      publicarPdf(null);
      setPdfBlob(null);
      try {
        const ultima = await getLatestRun(registro.id);
        setCorrida(ultima);
        setUserItem("moldesign_cohort_run", ultima.id);
        setPaso("ejecutar");
      } catch (fallo) {
        if (!(fallo instanceof CohortError) || fallo.status !== 404) throw fallo;
        setPaso("guardar");
      }
      return registro;
    });

  // ── Render ────────────────────────────────────────────────────────
  const resumen = preflight?.summary;
  // Cuántos ligandos se van a acoplar DE VERDAD: los elegibles, no las filas
  // del archivo. Estimar sobre el total prometería tiempo por moléculas que la
  // comprobación previa ya descartó.
  const ligandosDeLaCohorte = resumen?.eligible_rows ?? 0;
  const filas = evidencia?.molecules ?? [];
  const filasVisibles = filtro === "todas" ? filas : filas.filter((m) => m.status === filtro);

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-[#08090c] dark:text-white/90">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {/* ── Cabecera ────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link href="/evaluation" className={SECUNDARIO}>
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              {t("evaluation")}
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">{t("lo_titulo_cohortes")}</h1>
              <p className="text-sm text-zinc-600 dark:text-white/60">
                {t("pg_lote_intro")}
              </p>
            </div>
          </div>
        </div>

        {/* ── Pasos ───────────────────────────────────────────────── */}
        <nav aria-label={t("lo_aria_pasos")} className="mt-5 flex flex-wrap gap-1.5">
          {PASOS.map((p) => (
            <span
              key={p.id}
              data-testid={`paso-${p.id}`}
              aria-current={paso === p.id ? "step" : undefined}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium ${
                paso === p.id
                  ? "border-brand-500/40 bg-brand-600/10 text-brand-800 dark:bg-brand-600/15 dark:text-white"
                  : "border-zinc-200 bg-white text-zinc-600 dark:border-white/10 dark:bg-white/[0.02] dark:text-white/60"
              }`}
            >
              {p.n} · {t(p.clave)}
            </span>
          ))}
        </nav>

        {error && (
          <p role="alert" className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm leading-relaxed text-red-800 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-300">
            {error}
          </p>
        )}
        {pollError && corrida && (
          <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-200">
            <span className="min-w-0 flex-1">{pollError}</span>
            <button type="button" className={SECUNDARIO} onClick={() => setPollNonce((value) => value + 1)}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> {t("c_reintentar_seguimiento")}
            </button>
          </div>
        )}

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]">
          <div className="min-w-0 space-y-5">
            {/* ── 1 · Definir ───────────────────────────────────── */}
            <section className={`${CAJA} p-4`} aria-labelledby="def">
              <h2 id="def" className="text-sm font-semibold">{t("auto_568830f9f57b")}</h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-white/60">
                {t("pg_lote_receptor_comun")}
              </p>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className={ETIQUETA}>{t("c_nombre")}</span>
                  <input className={`${INPUT} mt-1`} value={nombre} onChange={(e) => setNombre(e.target.value)}
                    placeholder={t("lo_nombre_ejemplo")} aria-label={t("lo_nombre_cohorte")} />
                </label>

                <section className="sm:col-span-2 rounded-md border border-zinc-200 bg-zinc-50 p-4 dark:border-white/10 dark:bg-black/20" aria-labelledby="guia-archivo">
                  <h3 id="guia-archivo" className="text-sm font-semibold">{t("lo_prepara_archivo")}</h3>
                  <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-zinc-700 dark:text-white/70">
                    <li>{t("lo_limite_moleculas")}</li>
                    <li>{t("lo_csv_recomendaciones")} <code className="font-mono font-semibold text-zinc-900 dark:text-white">smiles</code>{t("lo_tambien_se_aceptan")} <code className="font-mono">canonical_smiles</code> y <code className="font-mono">structure</code>.</li>
                    <li>{t("lo_mismo_receptor")}</li>
                  </ol>
                  <p className="mt-3 text-xs font-semibold text-zinc-700 dark:text-white/65">{t("lo_ejemplo_csv")}</p>
                  <pre className="mt-1 overflow-x-auto rounded-md border border-zinc-300 bg-white p-3 text-sm leading-relaxed text-zinc-900 dark:border-white/10 dark:bg-black/40 dark:text-white/90"><code>{`smiles,name,active,control_role
CCO,etanol,1,reference
CC(=O)O,acido_acetico,0,none`}</code></pre>
                  <details className="mt-3 text-sm text-zinc-700 dark:text-white/70">
                    <summary className="cursor-pointer rounded-sm font-semibold text-zinc-900 outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 dark:text-white">{t("lo_ver_formatos")}</summary>
                    <div className="mt-3 space-y-3 border-t border-zinc-200 pt-3 dark:border-white/10">
                      <p><strong>{t("auto_460799387e92")}</strong> {t("lo_formatos_csv_xlsx")} <code className="font-mono">smiles</code>{t("lo_tambien_se_aceptan")} <code className="font-mono">canonical_smiles</code> {t("lo_o")} <code className="font-mono">structure</code>{t("lo_formatos_opcionales")} <code className="font-mono">name</code>, <code className="font-mono">active</code> y <code className="font-mono">control_role</code>{t("lo_formatos_xlsx_hoja")}</p>
                      <p><strong>{t("auto_e3d883a02cc8")}</strong> {t("lo_formatos_smi")} <code className="font-mono">{t("lo_ejemplo_smi_columnas")}</code>{t("lo_formatos_smi_separador")} <code className="font-mono">#</code> {t("lo_formatos_smi_comentarios")}</p>
                      <p><strong>SDF:</strong> {t("lo_formatos_sdf")} <code className="font-mono">_Name</code>{t("lo_formatos_sdf_propiedades")} <code className="font-mono">active</code> y <code className="font-mono">control_role</code> {t("lo_formatos_sdf_opcionales")}</p>
                      <p>{t("lo_formatos_para")} <code className="font-mono">active</code>, {t("lo_formatos_usa")} <code className="font-mono">1</code> {t("lo_formatos_activa")} <code className="font-mono">0</code> {t("lo_formatos_inactiva")} <code className="font-mono">control_role</code>, {t("lo_formatos_usa")} <code className="font-mono">reference</code>, <code className="font-mono">positive</code>, <code className="font-mono">negative</code> {t("lo_o")} <code className="font-mono">none</code>.</p>
                    </div>
                  </details>
                </section>

                <label className="block">
                  <span className={ETIQUETA}>{t("lo_archivo_moleculas")}</span>
                  <input type="file" accept=".csv,.xlsx,.sdf,.smi,.txt" aria-label={t("lo_archivo_moleculas")}
                    onChange={(e) => seleccionarArchivo(e.target.files?.[0] ?? null)}
                    className="mt-1 block w-full text-sm text-zinc-600 file:mr-3 file:rounded-md file:border file:border-zinc-300 file:bg-zinc-100 file:px-3 file:py-2 file:text-sm file:text-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 dark:text-white/60 dark:file:border-0 dark:file:bg-white/10 dark:file:text-white/80" />
                </label>
                <div className="block">
                  <label htmlFor="cohort-receptor-pdb" className={ETIQUETA}>{t("lo_receptor_pdb_id")}</label>
                  <div className="mt-1 flex gap-2">
                    <input id="cohort-receptor-pdb" className={INPUT} value={pdbId}
                      onChange={(e) => setPdbId(e.target.value)} placeholder="7E2Y"
                      aria-label={t("lo_receptor_pdb_aria")} />
                    <button
                      type="button"
                      className={`${SECUNDARIO} shrink-0`}
                      disabled={loadingTargets}
                      aria-label={targetsError ? t("lo_reintentar_catalogo") : t("lo_abrir_catalogo")}
                      onClick={() => targetsError ? void cargarTargets() : setShowTargetModal(true)}
                    >
                      {loadingTargets ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Search className="h-3.5 w-3.5" aria-hidden="true" />}
                      {loadingTargets ? "Cargando" : targetsError ? t("c_reintentar") : t("lo_catalogo_con_cuenta", { n: targets.length })}
                    </button>
                  </div>
                  {targetsError && (
                    <p role="status" className="mt-1.5 text-xs leading-relaxed text-amber-800 dark:text-amber-300/80">
                      {targetsError} {t("auto_03d50be324c8")}
                    </p>
                  )}
                </div>
                <label className="block">
                  <span className={ETIQUETA}>{t("lo_cadena_opcional")}</span>
                  <input className={`${INPUT} mt-1`} value={cadena} onChange={(e) => setCadena(e.target.value)}
                    placeholder="A" aria-label={t("c_cadena")} />
                </label>
                <fieldset className="sm:col-span-2">
                  <legend className={ETIQUETA}>{t("c_motor")}</legend>
                  <div className="mt-1 grid gap-2 sm:grid-cols-2">
                    <label className={`flex items-start gap-3 rounded-md border p-3 ${
                      motorHistoricoQuickVina
                        ? "border-zinc-200 bg-zinc-50 dark:border-white/10 dark:bg-white/[0.02]"
                        : "border-brand-500/40 bg-brand-50 dark:bg-brand-600/10"
                    }`}>
                      <input type="radio" name="motor" value="vina" checked={!motorHistoricoQuickVina} readOnly className="mt-0.5 accent-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50" />
                      <span><span className="block text-sm font-semibold">AutoDock Vina</span><span className="block text-xs text-zinc-600 dark:text-white/60">{t("lo_motor_disponible")}</span></span>
                    </label>
                    <label className={`flex cursor-not-allowed items-start gap-3 rounded-md border p-3 ${
                      motorHistoricoQuickVina
                        ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                        : "border-zinc-200 bg-zinc-100 text-zinc-600 dark:border-white/10 dark:bg-white/[0.02] dark:text-white/60"
                    }`}>
                      <input type="radio" name="motor" checked={motorHistoricoQuickVina} disabled aria-describedby="quickvina-note" className="mt-0.5" />
                      <span><span className="block text-sm font-semibold">{t("lo_qvina_proximamente")}</span><span id="quickvina-note" className="block text-xs leading-relaxed">{motorHistoricoQuickVina ? t("lo_qvina_no_disponible") : t("lo_qvina_requiere_binario")}</span></span>
                    </label>
                  </div>
                </fieldset>
                <div className="grid grid-cols-3 gap-2">
                  <label className="block">
                    <span className={ETIQUETA}>{t("lo_exhaust_label")}</span>
                    <input type="number" min={1} max={128} className={`${INPUT} mt-1`} value={exhaustividad}
                      aria-label={t("c_exhaustividad")} onChange={(e) => setExhaustividad(Number(e.target.value))} />
                  </label>
                  <label className="block">
                    <span className={ETIQUETA}>{t("lo_poses_label")}</span>
                    <input type="number" min={1} max={20} className={`${INPUT} mt-1`} value={poses}
                      aria-label={t("lo_poses_label")} onChange={(e) => setPoses(Number(e.target.value))} />
                  </label>
                  <label className="block">
                    <span className={ETIQUETA}>{t("se_gen_seed")}</span>
                    <input className={`${INPUT} mt-1`} value={semilla} placeholder="—"
                      aria-label={t("se_gen_seed")} onChange={(e) => setSemilla(e.target.value)} />
                  </label>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button type="button" className={PRIMARIO} onClick={comprobar}
                  disabled={!archivo || !estudio || ocupado === "comprobar"}>
                  {ocupado === "comprobar" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                  {t("lo_comprobar_cohorte")}
                </button>
                <span className="text-xs text-zinc-500 dark:text-white/60">
                  {t("pg_lote_comprobar_no_ejecuta")}
                </span>
              </div>
            </section>

            {/* ── 2 · Comprobar ─────────────────────────────────── */}
            {preflight && (
              <section className={`${CAJA} p-4`} aria-labelledby="pre" data-testid="resumen-preflight">
                <h2 id="pre" className="text-sm font-semibold">{t("lo_titulo_comprobacion")}</h2>
                <p className="mt-1 text-sm text-zinc-600 dark:text-white/60">
                  {t("pg_lote_superarla_no_predice")}
                </p>

                <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    [t("lo_filas"), resumen!.total_rows],
                    [t("lo_elegibles"), resumen!.eligible_rows],
                    [t("lo_invalidas"), resumen!.invalid_rows],
                    [t("lo_filtro_duplicados"), resumen!.duplicate_rows],
                    [t("lo_moleculas_unicas"), resumen!.unique_canonical_ligands],
                    [t("lo_rol_referencia"), resumen!.explicit_reference_controls],
                    [t("lo_rol_positivos"), resumen!.explicit_positive_controls],
                    [t("lo_rol_negativos"), resumen!.explicit_negative_controls],
                  ].map(([etiqueta, valor]) => (
                    <div key={String(etiqueta)} className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 dark:border-white/10 dark:bg-black/20">
                      <dt className={ETIQUETA}>{etiqueta}</dt>
                      <dd className="mt-0.5 text-sm font-medium">{valor}</dd>
                    </div>
                  ))}
                </dl>

                <p className="mt-3 text-sm text-zinc-600 dark:text-white/50" data-testid="cobertura-preflight">
                  {t("auto_416ef02a1420")}{" "}
                  {resumen!.input_coverage === null
                    ? t("lo_cobertura_no_medible")
                    : `${(resumen!.input_coverage * 100).toFixed(1)} % · ${resumen!.eligible_rows} de ${resumen!.input_coverage_denominator}`}
                </p>

                {preflight.blockers.length > 0 && (
                  <div role="alert" data-testid="blockers" className="mt-3 rounded-md border border-red-300 bg-red-50 px-3 py-2 dark:border-red-500/25 dark:bg-red-500/10">
                    <p className="text-sm font-semibold text-red-800 dark:text-red-300">
                      <XCircle className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
                      {t("pg_lote_bloqueada")}
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {preflight.blockers.map((b) => (
                        <li key={b} className="text-sm leading-relaxed text-red-800 dark:text-red-100/90">{t(claveDelMensaje(b))}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {preflight.warnings.length > 0 && (
                  <div data-testid="warnings" className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-500/25 dark:bg-amber-500/10">
                    <p className="text-sm font-semibold text-amber-900 dark:text-amber-300">
                      <AlertTriangle className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
                      {t("pg_lote_avisos")}
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {preflight.warnings.map((w) => (
                        <li key={w} className="text-sm leading-relaxed text-amber-900 dark:text-amber-100/90">{t(claveDelMensaje(w))}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <button type="button" className={PRIMARIO} onClick={guardar}
                    disabled={bloqueada || Boolean(cohorte) || ocupado === "guardar"}>
                    {ocupado === "guardar" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                    {t("auto_bedef67ee5db")}
                  </button>
                  <span className="break-all font-mono text-xs font-medium text-zinc-600 dark:text-white/55">
                    {preflight.cohort_fingerprint}
                  </span>
                </div>
              </section>
            )}

            {/* ── 3/4 · Cohorte guardada y ejecución ─────────────── */}
            {cohorte && (
              <section className={`${CAJA} p-4`} aria-labelledby="run" data-testid="cohorte-guardada">
                <h2 id="run" className="text-sm font-semibold">{t("lo_titulo_ejecucion")}</h2>
                <p className="mt-1 break-all font-mono text-xs font-medium text-zinc-600 dark:text-white/60">
                  {t("lo_cohorte_prefijo")} {cohorte.id} · {cohorte.source.filename} · sha256 {cohorte.source.sha256.slice(0, 16)}…
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-2 text-xs font-medium text-zinc-600 dark:text-white/65">
                    {t("lo_paralelismo")}
                    <input type="number" min={1} max={4} value={workers} aria-label={t("lo_paralelismo")}
                      onChange={(e) => setWorkers(Number(e.target.value))}
                      className="w-14 rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-900 outline-none focus-visible:border-brand-500 focus-visible:ring-2 focus-visible:ring-brand-500/30 dark:border-white/10 dark:bg-black/30 dark:text-white/80" />
                  </label>
                  <button type="button" className={PRIMARIO} onClick={lanzar}
                    aria-describedby={motorHistoricoQuickVina ? "motor-historico-bloqueado" : undefined}
                    disabled={motorHistoricoQuickVina || Boolean(corrida && isRunActive(corrida.status)) || ocupado === "ejecutar"}>
                    {ocupado === "ejecutar" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                    {ocupado === "ejecutar" ? t("lo_preparando") : t("lo_ejecutar_cohorte")}
                  </button>
                </div>
                {motorHistoricoQuickVina && (
                  <p id="motor-historico-bloqueado" role="status" className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
                    {t("lo_qvina_no_disponible")}
                  </p>
                )}

                {/* Cuánto va a tardar la COHORTE, antes de lanzarla. Aquí es
                    donde más importa: una evaluación suelta que se estima mal
                    cuesta minutos, y una cohorte de cientos de ligandos cuesta
                    horas. El paralelismo entra en el cálculo porque es la
                    palanca que el usuario tiene delante. */}
                {!corrida && ligandosDeLaCohorte > 0 && (
                  <div className="mt-3">
                    <EstimacionDeCorrida
                      exhaustiveness={8}
                      ligandos={ligandosDeLaCohorte}
                    />
                  </div>
                )}

                {corrida && (
                  <div className="mt-4" data-testid="progreso">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-medium">
                        {RUN_STATUS_LABELS[corrida.status]}
                        {corrida.cancel_requested && corrida.status !== "cancelled" && t("lo_cancelacion_pedida")}
                      </span>
                      <span className="break-all font-mono text-xs font-medium text-zinc-600 dark:text-white/55">
                        corrida {corrida.id}
                      </span>
                    </div>

                    <dl className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
                      {[
                        [t("lo_progreso_archivo"), corrida.progress.total_rows],
                        [t("lo_elegibles"), corrida.progress.eligible_rows],
                        [t("lo_filtro_completadas"), corrida.progress.completed_rows],
                        [t("lo_filtro_duplicados"), corrida.progress.duplicate_reused_rows],
                        [t("lo_filtro_fallidas"), corrida.progress.failed_rows],
                        [t("lo_filtro_no_evaluadas"), corrida.progress.not_evaluated_rows],
                      ].map(([etiqueta, valor]) => (
                        <div key={String(etiqueta)} className="border-l border-zinc-300 py-1 pl-3 dark:border-white/15">
                          <dt className="text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-white/60">{etiqueta}</dt>
                          <dd className="text-sm font-semibold tabular-nums">{valor}</dd>
                        </div>
                      ))}
                    </dl>

                    {corrida.last_error && (
                      <p role="status" className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-200">
                        {corrida.last_error}
                      </p>
                    )}

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" className={SECUNDARIO} onClick={cancelar}
                        disabled={!isRunActive(corrida.status) || ocupado === "cancelar"}>
                        <XCircle className="h-3.5 w-3.5" /> {t("c_cancelar")}
                      </button>
                      <button type="button" className={SECUNDARIO} onClick={reanudar}
                        aria-describedby={motorHistoricoQuickVina ? "motor-historico-bloqueado" : undefined}
                        disabled={
                          motorHistoricoQuickVina ||
                          !(corrida.status === "interrupted" || corrida.status === "completed_with_exceptions") ||
                          ocupado === "reanudar"
                        }>
                        <RefreshCw className="h-3.5 w-3.5" /> {t("lo_reanudar")}
                      </button>
                      <button type="button" className={PRIMARIO} onClick={verEvidencia}
                        disabled={isRunActive(corrida.status) || ocupado === "evidencia"}>
                        <FileSpreadsheet className="h-3.5 w-3.5" /> {t("auto_8796008ea42e")}
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* ── 5 · Evidencia ─────────────────────────────────── */}
            {evidencia && (
              <section className={`${CAJA} p-4`} aria-labelledby="ev" data-testid="evidencia">
                <h2 id="ev" className="text-sm font-semibold">{t("auto_cc09f4f40c71")}</h2>
                <p className="mt-1 text-sm text-zinc-600 dark:text-white/60">
                  {t("pg_lote_orden_no_veredicto")}
                </p>

                <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="cobertura-evidencia">
                  {[
                    [t("lo_filas_del_archivo"), evidencia.coverage.source_rows],
                    [t("lo_elegibles"), evidencia.coverage.eligible_rows],
                    [t("lo_moleculas_unicas"), evidencia.coverage.unique_molecules_executed],
                    [t("lo_filtro_completadas"), evidencia.coverage.completed_rows],
                    [t("lo_filtro_duplicados"), evidencia.coverage.duplicate_reused_rows],
                    [t("lo_filtro_fallidas"), evidencia.coverage.failed_rows],
                    [t("lo_filtro_no_evaluadas"), evidencia.coverage.not_evaluated_rows],
                    [t("lo_no_elegibles"), evidencia.coverage.not_eligible_rows],
                  ].map(([etiqueta, valor]) => (
                    <div key={String(etiqueta)} className="border-l border-zinc-300 py-1 pl-3 dark:border-white/15">
                      <dt className={ETIQUETA}>{etiqueta}</dt>
                      <dd className="mt-0.5 text-sm font-semibold tabular-nums">{valor}</dd>
                    </div>
                  ))}
                </dl>

                {/* Métricas: evaluables o abstención declarada */}
                <div className="mt-3 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 dark:border-white/10 dark:bg-black/20" data-testid="metricas">
                  <p className={ETIQUETA}>{t("lo_metricas_etiquetadas")}</p>
                  {evidencia.labeled_metrics.status === "evaluated" ? (
                    <>
                      <p className="mt-1 text-sm">
                        ROC-AUC {evidencia.labeled_metrics.roc_auc?.toFixed(4)} ·{" "}
                        {evidencia.labeled_metrics.enrichment_factors
                          .map((ef) => `EF@${Math.round(ef.fraction * 100)}% ${ef.value?.toFixed(2)}`)
                          .join(" · ")}
                      </p>
                      <p className="mt-1 text-xs text-zinc-600 dark:text-white/60">
                        n={evidencia.labeled_metrics.n_total} ({evidencia.labeled_metrics.n_positive} {t("auto_b12b25b7b597")}{" "}
                        {evidencia.labeled_metrics.n_negative} {t("auto_22063fc5d2df")}{" "}
                        {evidencia.labeled_metrics.coverage}
                      </p>
                      <p className="mt-1 text-xs text-zinc-600 dark:text-white/60">
                        {evidencia.labeled_metrics.interpretation_limit}
                      </p>
                    </>
                  ) : (
                    <p className="mt-1 text-sm font-medium text-zinc-700 dark:text-white/70">
                      {t("auto_98a7a2997090")} {evidencia.labeled_metrics.reason}
                    </p>
                  )}
                </div>

                {evidencia.labeled_metrics.controls.length > 0 && (
                  <div className="mt-3 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 dark:border-white/10 dark:bg-black/20" data-testid="controles">
                    <p className={ETIQUETA}>{t("lo_controles_declarados")}</p>
                    <ul className="mt-1 space-y-0.5">
                      {evidencia.labeled_metrics.controls.map((c) => (
                        <li key={c.source_row_index} className="text-xs text-zinc-600 dark:text-white/60">
                          #{c.source_row_index} {c.source_name ?? "—"} · {CONTROL_ROLE_LABELS[c.control_role]} ·{" "}
                          {c.observed_vina_affinity_kcal_mol?.toFixed(2) ?? t("lo_sin_afinidad")}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-500/20 dark:bg-amber-500/5">
                  <p className={ETIQUETA}>{t("lo_limites_interpretacion")}</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-xs leading-relaxed text-amber-900 dark:text-amber-100/70">
                    {evidencia.limits.map((limit) => <li key={limit}>{limit}</li>)}
                  </ul>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label={t("lo_filtrar_por_estado")}>
                  {FILTROS.map((f) => (
                    <button key={f.id} type="button" onClick={() => setFiltro(f.id)}
                      aria-pressed={filtro === f.id}
                      className={`rounded-md border px-2 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 ${
                        filtro === f.id
                          ? "border-brand-500/40 bg-brand-600/10 text-brand-800 dark:bg-brand-600/15 dark:text-white"
                          : "border-zinc-200 bg-white text-zinc-600 hover:text-zinc-900 dark:border-white/10 dark:bg-white/[0.02] dark:text-white/60 dark:hover:text-white/70"
                      }`}>
                      {t(f.clave)}
                    </button>
                  ))}
                </div>

                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[46rem] text-left text-xs tabular-nums">
                    <thead className="font-medium text-zinc-600 dark:text-white/65">
                      <tr>
                        <th className="px-2 py-1.5 font-normal">#</th>
                        <th className="px-2 py-1.5 font-normal">{t("c_nombre")}</th>
                        <th className="px-2 py-1.5 font-normal">{t("c_estado")}</th>
                        <th className="px-2 py-1.5 font-normal">{t("lo_th_afinidad_vina")}</th>
                        <th className="px-2 py-1.5 font-normal">{t("lo_th_etiqueta")}</th>
                        <th className="px-2 py-1.5 font-normal">{t("lo_th_control")}</th>
                      </tr>
                    </thead>
                    <tbody data-testid="tabla-evidencia">
                      {filasVisibles.map((m) => (
                        <tr key={m.source_row_index} className="border-t border-zinc-200 dark:border-white/10">
                          <td className="px-2 py-1.5 text-zinc-500 dark:text-white/60">{m.source_row_index}</td>
                          <td className="px-2 py-1.5">{m.source_name ?? "—"}</td>
                          <td className="px-2 py-1.5">
                            {ROW_STATUS_LABELS[m.status]}
                            {m.error_code && (
                              <span className="mt-0.5 block max-w-xs text-xs leading-snug text-zinc-600 dark:text-white/60">
                                {m.error_detail || t("lo_evaluacion_no_completada")}
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-1.5 font-mono">
                            {m.observed_vina_affinity_kcal_mol?.toFixed(2) ?? (
                              <span className="text-zinc-500 dark:text-white/60">{t("lo_no_disponible")}</span>
                            )}
                          </td>
                          <td className="px-2 py-1.5">
                            {m.active_label === null ? "—" : m.active_label ? "activa" : "inactiva"}
                          </td>
                          <td className="px-2 py-1.5">{CONTROL_ROLE_LABELS[m.control_role]}</td>
                        </tr>
                      ))}
                      {filasVisibles.length === 0 && (
                        <tr>
                          <td colSpan={6} className="border-t border-zinc-200 px-2 py-6 text-center text-zinc-600 dark:border-white/10 dark:text-white/60">
                            {t("pg_lote_sin_estado")}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <button type="button" className={`${PRIMARIO} mt-4`} onClick={verInforme} disabled={ocupado === "informe"}>
                  {ocupado === "informe" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  {t("auto_2f1a6f19a8c3")}
                </button>
              </section>
            )}

            {/* ── 6 · Informe ───────────────────────────────────── */}
            {paso === "informe" && (
              <section className={`${CAJA} p-4`} aria-labelledby="inf" data-testid="informe">
                <h2 id="inf" className="text-sm font-semibold">{t("auto_304a0bfa0894")}</h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className={SECUNDARIO} onClick={descargarPdf} disabled={!pdfBlob}>
                    <Download className="h-3.5 w-3.5" /> {t("z_descargar_pdf")}
                  </button>
                  <button type="button" className={SECUNDARIO} onClick={exportarZip} disabled={ocupado === "zip"}>
                    {ocupado === "zip" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileArchive className="h-3.5 w-3.5" />}
                    {t("c_exportar_zip")}
                  </button>
                </div>
                {zipGuardado && (
                  <p role="status" className="mt-2 text-xs text-zinc-600 dark:text-white/60">
                    {t("pg_lote_paquete_descargado")} <span className="font-mono">{zipGuardado}</span>{t("pg_lote_manifiesto")}
                  </p>
                )}
                <div className="mt-3 h-[70vh] min-h-[24rem] overflow-hidden rounded-md border border-zinc-200 bg-zinc-100 dark:border-white/10 dark:bg-black/40">
                  {pdfUrl ? (
                    <iframe src={`${pdfUrl}#toolbar=0`} title={t("lo_dossier_cohorte")} className="h-full w-full border-none" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-zinc-500 dark:text-white/60">
                      {t("pg_lote_dossier_no_cargado")}
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>

          {/* ── Lista lateral ─────────────────────────────────────── */}
          <aside className={`${CAJA} h-fit p-3`} aria-label={t("lo_cohortes_guardadas")}>
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold">{t("lo_cohortes_guardadas")}</h2>
              <button type="button" onClick={refrescarLista} className="rounded-sm text-zinc-500 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 dark:text-white/60 dark:hover:text-white/80" aria-label={t("lo_refrescar_lista")}>
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>
            {guardadas.length === 0 ? (
              <p className="mt-2 text-xs font-medium text-zinc-600 dark:text-white/55">{t("lo_ninguna_todavia")}</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {guardadas.map((item) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => abrirGuardada(item)}
                      className="w-full rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1.5 text-left transition-colors hover:border-zinc-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 dark:border-white/10 dark:bg-black/20 dark:hover:border-white/20">
                      <span className="block truncate text-xs">{item.name}</span>
                      <span className="block text-xs font-medium text-zinc-600 dark:text-white/60">
                        {item.receptor_pdb_id} · {item.summary.eligible_rows}/{item.summary.total_rows} {t("lo_elegibles_sufijo")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 border-t border-zinc-200 pt-2 text-xs font-medium leading-relaxed text-zinc-600 dark:border-white/10 dark:text-white/60">
              {t("pg_lote_inmutable")}
            </p>
          </aside>
        </div>

        <p className="mt-6 text-sm font-medium leading-relaxed text-zinc-600 dark:text-white/55">
          <CheckCircle2 className="mr-1 inline h-3 w-3" aria-hidden="true" />
          {t("pg_lote_sin_merito")}
        </p>
      </div>
      <TargetSelectorModal
        isOpen={showTargetModal}
        onClose={() => setShowTargetModal(false)}
        targets={targets}
        onSelect={seleccionarTarget}
        selectedTargetId={pdbId || null}
        onTargetUploadSuccess={cargarTargets}
      />
    </div>
  );
}
