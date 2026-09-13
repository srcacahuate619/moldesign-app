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
import { getTargets, type Target } from "../../../lib/api";
import { saveBlobAs } from "../../../lib/dossier";
import { beginFileDownload, failFileDownload, notifyRunFinished } from "../../../lib/activityNotifications";
import { getUserItem, removeUserItem, setUserItem } from "../../../lib/userStorage";
import TargetSelectorModal from "../../../components/interfaces/pro/TargetSelectorModal";

type Paso = "definir" | "comprobar" | "guardar" | "ejecutar" | "evidencia" | "informe";

const PASOS: readonly { readonly id: Paso; readonly n: number; readonly label: string }[] = [
  { id: "definir", n: 1, label: "Definir" },
  { id: "comprobar", n: 2, label: "Comprobar" },
  { id: "guardar", n: 3, label: "Guardar" },
  { id: "ejecutar", n: 4, label: "Ejecutar" },
  { id: "evidencia", n: 5, label: "Evidencia" },
  { id: "informe", n: 6, label: "Informe" },
];

const FILTROS: readonly { readonly id: RowStatus | "todas"; readonly label: string }[] = [
  { id: "todas", label: "Todas" },
  { id: "completed", label: "Completadas" },
  { id: "duplicate_reused", label: "Duplicados" },
  { id: "failed", label: "Fallidas" },
  { id: "not_evaluated", label: "No evaluadas" },
];

const CAJA = "rounded-lg border border-white/5 bg-white/[0.02]";
const ETIQUETA = "text-[11px] font-semibold uppercase tracking-wider text-white/65";
const INPUT =
  "w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/90 " +
  "outline-none transition-colors focus:border-brand-400/60";
const BOTON =
  "inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors " +
  "disabled:cursor-not-allowed disabled:opacity-40";
const PRIMARIO = `${BOTON} bg-brand-600 text-white hover:bg-brand-500`;
const SECUNDARIO = `${BOTON} border border-white/10 bg-white/[0.03] text-white/70 hover:text-white`;

const MENSAJES_COHORTE: Readonly<Record<string, string>> = {
  ARCHIVO_ILEGIBLE: "No se pudo leer el archivo. Verifica que no esté dañado.",
  FORMATO_NO_SOPORTADO: "El formato del archivo no es compatible.",
  COLUMNA_SMILES_AUSENTE: "El archivo no contiene una columna de estructuras SMILES.",
  COHORTE_VACIA: "El archivo no contiene moléculas.",
  SIN_MOLECULAS_ELEGIBLES: "Ninguna molécula puede entrar en esta corrida.",
  LECTOR_NO_DISPONIBLE: "Esta instalación no incluye el lector necesario para ese formato.",
  VALIDADOR_NO_DISPONIBLE: "El validador químico no está disponible en esta instalación.",
  SIN_CONTROLES_DECLARADOS: "No se declararon controles; no podrá compararse el resultado con una referencia.",
  SIN_ETIQUETAS_ACTIVE: "No hay etiquetas de actividad; no se calcularán métricas supervisadas.",
  DUPLICADOS_CANONICOS: "Hay estructuras repetidas; se ejecutarán una vez y se declarará su reutilización.",
  FILAS_INVALIDAS: "Algunas filas no entrarán en la corrida. Revisa la cobertura antes de continuar.",
  CAJA_NO_DECLARADA: "La caja de búsqueda se tomará de la configuración validada del receptor.",
  SEMILLA_NO_DECLARADA: "No se indicó semilla; se congelará la semilla predeterminada de esta instalación.",
};

function mensajeCohorte(codigo: string): string {
  return MENSAJES_COHORTE[codigo] ?? "La comprobación detectó una condición que requiere revisión.";
}

function mensajeDe(error: unknown): string {
  if (error instanceof CohortError) return error.message;
  return (error as Error)?.message || "La operación no se pudo completar.";
}

export default function CohortesPage() {
  // ── Definición ────────────────────────────────────────────────────
  const [nombre, setNombre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [pdbId, setPdbId] = useState("");
  const [cadena, setCadena] = useState("");
  const [motor, setMotor] = useState<"vina" | "qvina2">("vina");
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
        docking_engine: motor,
        exhaustiveness: exhaustividad,
        num_poses: poses,
        ...(semilla.trim() ? { seed: Number(semilla) } : {}),
      },
    };
  }, [nombre, pdbId, cadena, motor, exhaustividad, poses, semilla]);

  const bloqueada = Boolean(preflight && preflight.decision === "blocked");

  // Batch comparte el catálogo canónico con Evaluación. El campo manual sigue
  // disponible porque no poder listar el catálogo no invalida un PDB conocido.
  const cargarTargets = useCallback(async () => {
    setLoadingTargets(true);
    setTargetsError(null);
    try {
      setTargets(await getTargets());
    } catch (fallo) {
      setTargetsError(`No se pudo cargar el catálogo: ${mensajeDe(fallo)}`);
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
    setMotor(estudioGuardado.config.docking_engine);
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
        setCorrida(recuperada);
        setPaso("ejecutar");
        const suya = await getCohort(recuperada.cohort_id);
        if (vivo) restaurarDefinicion(suya);
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
          setPollError("Se interrumpió el seguimiento de la cohorte. La corrida conserva su estado en el backend; puedes reintentar.");
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
      setError(mensajeDe(fallo));
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
      if (!cohorte) return null;
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
      if (!corrida) return null;
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
  const filas = evidencia?.molecules ?? [];
  const filasVisibles = filtro === "todas" ? filas : filas.filter((m) => m.status === filtro);

  return (
    <div className="min-h-screen bg-[#08090c] text-white/90">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {/* ── Cabecera ────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link href="/evaluation" className={SECUNDARIO}>
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Evaluación
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Cohortes</h1>
              <p className="text-xs text-white/40">
                Define una cohorte comparable, comprueba sus entradas, ejecútala bajo una
                configuración común y entrega evidencia con su cobertura.
              </p>
            </div>
          </div>
        </div>

        {/* ── Pasos ───────────────────────────────────────────────── */}
        <nav aria-label="Pasos" className="mt-5 flex flex-wrap gap-1.5">
          {PASOS.map((p) => (
            <span
              key={p.id}
              data-testid={`paso-${p.id}`}
              aria-current={paso === p.id ? "step" : undefined}
              className={`rounded-md border px-2.5 py-1 text-[11px] font-medium ${
                paso === p.id
                  ? "border-brand-500/40 bg-brand-600/15 text-white"
                  : "border-white/5 bg-white/[0.02] text-white/60"
              }`}
            >
              {p.n} · {p.label}
            </span>
          ))}
        </nav>

        {error && (
          <p role="alert" className="mt-4 rounded-md border border-red-500/25 bg-red-500/10 px-4 py-3 text-xs leading-relaxed text-red-300">
            {error}
          </p>
        )}
        {pollError && corrida && (
          <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 rounded-md border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-200">
            <span className="min-w-0 flex-1">{pollError}</span>
            <button type="button" className={SECUNDARIO} onClick={() => setPollNonce((value) => value + 1)}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Reintentar seguimiento
            </button>
          </div>
        )}

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]">
          <div className="min-w-0 space-y-5">
            {/* ── 1 · Definir ───────────────────────────────────── */}
            <section className={`${CAJA} p-4`} aria-labelledby="def">
              <h2 id="def" className="text-sm font-semibold">1 · Nueva cohorte</h2>
              <p className="mt-1 text-xs text-white/40">
                Un receptor y una configuración común para todas las moléculas. Es lo que
                hace comparables las filas entre sí.
              </p>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className={ETIQUETA}>Nombre</span>
                  <input className={`${INPUT} mt-1`} value={nombre} onChange={(e) => setNombre(e.target.value)}
                    placeholder="Serie de anilinas · lote 3" aria-label="Nombre de la cohorte" />
                </label>
                <label className="block">
                  <span className={ETIQUETA}>Archivo de moléculas</span>
                  <input type="file" accept=".csv,.xlsx,.xls,.sdf,.smi,.txt" aria-label="Archivo de moléculas"
                    onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                    className="mt-1 block w-full text-xs text-white/60 file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-xs file:text-white/80" />
                </label>
                <div className="block">
                  <label htmlFor="cohort-receptor-pdb" className={ETIQUETA}>Receptor (PDB ID)</label>
                  <div className="mt-1 flex gap-2">
                    <input id="cohort-receptor-pdb" className={INPUT} value={pdbId}
                      onChange={(e) => setPdbId(e.target.value)} placeholder="7E2Y"
                      aria-label="Receptor PDB ID" />
                    <button
                      type="button"
                      className={`${SECUNDARIO} shrink-0`}
                      disabled={loadingTargets}
                      aria-label={targetsError ? "Reintentar catálogo de receptores" : "Abrir catálogo de receptores"}
                      onClick={() => targetsError ? void cargarTargets() : setShowTargetModal(true)}
                    >
                      {loadingTargets ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Search className="h-3.5 w-3.5" aria-hidden="true" />}
                      {loadingTargets ? "Cargando" : targetsError ? "Reintentar" : `Catálogo (${targets.length})`}
                    </button>
                  </div>
                  {targetsError && (
                    <p role="status" className="mt-1.5 text-[11px] leading-relaxed text-amber-300/80">
                      {targetsError} Puedes introducir el PDB ID manualmente.
                    </p>
                  )}
                </div>
                <label className="block">
                  <span className={ETIQUETA}>Cadena (opcional)</span>
                  <input className={`${INPUT} mt-1`} value={cadena} onChange={(e) => setCadena(e.target.value)}
                    placeholder="A" aria-label="Cadena" />
                </label>
                <label className="block">
                  <span className={ETIQUETA}>Motor</span>
                  <select className={`${INPUT} mt-1`} value={motor} aria-label="Motor de docking"
                    onChange={(e) => setMotor(e.target.value as "vina" | "qvina2")}>
                    <option value="vina">vina</option>
                    <option value="qvina2">qvina2</option>
                  </select>
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <label className="block">
                    <span className={ETIQUETA}>Exhaust.</span>
                    <input type="number" min={1} max={128} className={`${INPUT} mt-1`} value={exhaustividad}
                      aria-label="Exhaustividad" onChange={(e) => setExhaustividad(Number(e.target.value))} />
                  </label>
                  <label className="block">
                    <span className={ETIQUETA}>Poses</span>
                    <input type="number" min={1} max={20} className={`${INPUT} mt-1`} value={poses}
                      aria-label="Poses" onChange={(e) => setPoses(Number(e.target.value))} />
                  </label>
                  <label className="block">
                    <span className={ETIQUETA}>Semilla</span>
                    <input className={`${INPUT} mt-1`} value={semilla} placeholder="—"
                      aria-label="Semilla" onChange={(e) => setSemilla(e.target.value)} />
                  </label>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button type="button" className={PRIMARIO} onClick={comprobar}
                  disabled={!archivo || !estudio || ocupado === "comprobar"}>
                  {ocupado === "comprobar" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                  Comprobar cohorte
                </button>
                <span className="text-[11px] text-white/30">
                  Comprobar no ejecuta nada.
                </span>
              </div>
            </section>

            {/* ── 2 · Comprobar ─────────────────────────────────── */}
            {preflight && (
              <section className={`${CAJA} p-4`} aria-labelledby="pre" data-testid="resumen-preflight">
                <h2 id="pre" className="text-sm font-semibold">2 · Comprobación previa</h2>
                <p className="mt-1 text-xs text-white/40">
                  Superarla no predice unión ni calidad farmacológica: todavía no se ha
                  calculado nada.
                </p>

                <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    ["Filas", resumen!.total_rows],
                    ["Elegibles", resumen!.eligible_rows],
                    ["Inválidas", resumen!.invalid_rows],
                    ["Duplicados", resumen!.duplicate_rows],
                    ["Moléculas únicas", resumen!.unique_canonical_ligands],
                    ["Referencia", resumen!.explicit_reference_controls],
                    ["Positivos", resumen!.explicit_positive_controls],
                    ["Negativos", resumen!.explicit_negative_controls],
                  ].map(([etiqueta, valor]) => (
                    <div key={String(etiqueta)} className="rounded-md border border-white/5 bg-black/20 px-3 py-2">
                      <dt className={ETIQUETA}>{etiqueta}</dt>
                      <dd className="mt-0.5 text-sm font-medium">{valor}</dd>
                    </div>
                  ))}
                </dl>

                <p className="mt-3 text-xs text-white/50" data-testid="cobertura-preflight">
                  Cobertura de entrada:{" "}
                  {resumen!.input_coverage === null
                    ? "no medible (sin filas)"
                    : `${(resumen!.input_coverage * 100).toFixed(1)} % · ${resumen!.eligible_rows} de ${resumen!.input_coverage_denominator}`}
                </p>

                {preflight.blockers.length > 0 && (
                  <div role="alert" data-testid="blockers" className="mt-3 rounded-md border border-red-500/25 bg-red-500/10 px-3 py-2">
                    <p className="text-xs font-semibold text-red-300">
                      <XCircle className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
                      Bloqueada — no se puede guardar ni ejecutar
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {preflight.blockers.map((b) => (
                        <li key={b} className="text-xs leading-relaxed text-red-100/90">{mensajeCohorte(b)}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {preflight.warnings.length > 0 && (
                  <div data-testid="warnings" className="mt-3 rounded-md border border-amber-500/25 bg-amber-500/10 px-3 py-2">
                    <p className="text-xs font-semibold text-amber-300">
                      <AlertTriangle className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
                      Avisos — no bloquean
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {preflight.warnings.map((w) => (
                        <li key={w} className="text-xs leading-relaxed text-amber-100/90">{mensajeCohorte(w)}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <button type="button" className={PRIMARIO} onClick={guardar}
                    disabled={bloqueada || Boolean(cohorte) || ocupado === "guardar"}>
                    {ocupado === "guardar" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                    3 · Guardar cohorte
                  </button>
                  <span className="break-all font-mono text-[11px] font-medium text-white/55">
                    {preflight.cohort_fingerprint}
                  </span>
                </div>
              </section>
            )}

            {/* ── 3/4 · Cohorte guardada y ejecución ─────────────── */}
            {cohorte && (
              <section className={`${CAJA} p-4`} aria-labelledby="run" data-testid="cohorte-guardada">
                <h2 id="run" className="text-sm font-semibold">4 · Ejecución</h2>
                <p className="mt-1 break-all font-mono text-[11px] font-medium text-white/60">
                  cohorte {cohorte.id} · {cohorte.source.filename} · sha256 {cohorte.source.sha256.slice(0, 16)}…
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-2 text-xs font-medium text-white/65">
                    Paralelismo
                    <input type="number" min={1} max={4} value={workers} aria-label="Paralelismo"
                      onChange={(e) => setWorkers(Number(e.target.value))}
                      className="w-14 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80" />
                  </label>
                  <button type="button" className={PRIMARIO} onClick={lanzar}
                    disabled={Boolean(corrida && isRunActive(corrida.status)) || ocupado === "ejecutar"}>
                    {ocupado === "ejecutar" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                    {ocupado === "ejecutar" ? "Preparando y abriendo…" : "Ejecutar cohorte"}
                  </button>
                </div>

                {corrida && (
                  <div className="mt-4" data-testid="progreso">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-medium">
                        {RUN_STATUS_LABELS[corrida.status]}
                        {corrida.cancel_requested && corrida.status !== "cancelled" && " · cancelación pedida"}
                      </span>
                      <span className="break-all font-mono text-[11px] font-medium text-white/55">
                        corrida {corrida.id}
                      </span>
                    </div>

                    <dl className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
                      {[
                        ["Archivo", corrida.progress.total_rows],
                        ["Elegibles", corrida.progress.eligible_rows],
                        ["Completadas", corrida.progress.completed_rows],
                        ["Duplicados", corrida.progress.duplicate_reused_rows],
                        ["Fallidas", corrida.progress.failed_rows],
                        ["No evaluadas", corrida.progress.not_evaluated_rows],
                      ].map(([etiqueta, valor]) => (
                        <div key={String(etiqueta)} className="border-l border-white/15 py-1 pl-3">
                          <dt className="text-[11px] font-medium uppercase tracking-wider text-white/60">{etiqueta}</dt>
                          <dd className="text-sm font-semibold tabular-nums">{valor}</dd>
                        </div>
                      ))}
                    </dl>

                    {corrida.last_error && (
                      <p role="status" className="mt-2 rounded-md border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                        {corrida.last_error}
                      </p>
                    )}

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" className={SECUNDARIO} onClick={cancelar}
                        disabled={!isRunActive(corrida.status) || ocupado === "cancelar"}>
                        <XCircle className="h-3.5 w-3.5" /> Cancelar
                      </button>
                      <button type="button" className={SECUNDARIO} onClick={reanudar}
                        disabled={
                          !(corrida.status === "interrupted" || corrida.status === "completed_with_exceptions") ||
                          ocupado === "reanudar"
                        }>
                        <RefreshCw className="h-3.5 w-3.5" /> Reanudar
                      </button>
                      <button type="button" className={PRIMARIO} onClick={verEvidencia}
                        disabled={isRunActive(corrida.status) || ocupado === "evidencia"}>
                        <FileSpreadsheet className="h-3.5 w-3.5" /> 5 · Ver evidencia
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* ── 5 · Evidencia ─────────────────────────────────── */}
            {evidencia && (
              <section className={`${CAJA} p-4`} aria-labelledby="ev" data-testid="evidencia">
                <h2 id="ev" className="text-sm font-semibold">5 · Evidencia</h2>
                <p className="mt-1 text-xs text-white/40">
                  Ordenada por afinidad Vina observada. Es un orden, no un veredicto:
                  completar un acoplamiento no demuestra actividad.
                </p>

                <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="cobertura-evidencia">
                  {[
                    ["Filas del archivo", evidencia.coverage.source_rows],
                    ["Elegibles", evidencia.coverage.eligible_rows],
                    ["Moléculas únicas", evidencia.coverage.unique_molecules_executed],
                    ["Completadas", evidencia.coverage.completed_rows],
                    ["Duplicados", evidencia.coverage.duplicate_reused_rows],
                    ["Fallidas", evidencia.coverage.failed_rows],
                    ["No evaluadas", evidencia.coverage.not_evaluated_rows],
                    ["No elegibles", evidencia.coverage.not_eligible_rows],
                  ].map(([etiqueta, valor]) => (
                    <div key={String(etiqueta)} className="border-l border-white/15 py-1 pl-3">
                      <dt className={ETIQUETA}>{etiqueta}</dt>
                      <dd className="mt-0.5 text-sm font-semibold tabular-nums">{valor}</dd>
                    </div>
                  ))}
                </dl>

                {/* Métricas: evaluables o abstención declarada */}
                <div className="mt-3 rounded-md border border-white/5 bg-black/20 px-3 py-2" data-testid="metricas">
                  <p className={ETIQUETA}>Métricas etiquetadas</p>
                  {evidencia.labeled_metrics.status === "evaluated" ? (
                    <>
                      <p className="mt-1 text-sm">
                        ROC-AUC {evidencia.labeled_metrics.roc_auc?.toFixed(4)} ·{" "}
                        {evidencia.labeled_metrics.enrichment_factors
                          .map((ef) => `EF@${Math.round(ef.fraction * 100)}% ${ef.value?.toFixed(2)}`)
                          .join(" · ")}
                      </p>
                      <p className="mt-1 text-[11px] text-white/40">
                        n={evidencia.labeled_metrics.n_total} ({evidencia.labeled_metrics.n_positive} activas,{" "}
                        {evidencia.labeled_metrics.n_negative} inactivas) · cobertura{" "}
                        {evidencia.labeled_metrics.coverage}
                      </p>
                      <p className="mt-1 text-[11px] text-white/40">
                        {evidencia.labeled_metrics.interpretation_limit}
                      </p>
                    </>
                  ) : (
                    <p className="mt-1 text-xs font-medium text-white/70">
                      Métricas no calculadas — {evidencia.labeled_metrics.reason}
                    </p>
                  )}
                </div>

                {evidencia.labeled_metrics.controls.length > 0 && (
                  <div className="mt-3 rounded-md border border-white/5 bg-black/20 px-3 py-2" data-testid="controles">
                    <p className={ETIQUETA}>Controles declarados (fuera de la población de la métrica)</p>
                    <ul className="mt-1 space-y-0.5">
                      {evidencia.labeled_metrics.controls.map((c) => (
                        <li key={c.source_row_index} className="text-xs text-white/60">
                          #{c.source_row_index} {c.source_name ?? "—"} · {CONTROL_ROLE_LABELS[c.control_role]} ·{" "}
                          {c.observed_vina_affinity_kcal_mol?.toFixed(2) ?? "sin afinidad"}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mt-3 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2">
                  <p className={ETIQUETA}>Límites de interpretación</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-amber-100/70">
                    {evidencia.limits.map((limit) => <li key={limit}>{limit}</li>)}
                  </ul>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por estado">
                  {FILTROS.map((f) => (
                    <button key={f.id} type="button" onClick={() => setFiltro(f.id)}
                      aria-pressed={filtro === f.id}
                      className={`rounded-md border px-2 py-1 text-[11px] ${
                        filtro === f.id
                          ? "border-brand-500/40 bg-brand-600/15 text-white"
                          : "border-white/5 bg-white/[0.02] text-white/40 hover:text-white/70"
                      }`}>
                      {f.label}
                    </button>
                  ))}
                </div>

                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[46rem] text-left text-xs tabular-nums">
                    <thead className="font-medium text-white/65">
                      <tr>
                        <th className="px-2 py-1.5 font-normal">#</th>
                        <th className="px-2 py-1.5 font-normal">Nombre</th>
                        <th className="px-2 py-1.5 font-normal">Estado</th>
                        <th className="px-2 py-1.5 font-normal">Afinidad Vina observada (kcal/mol)</th>
                        <th className="px-2 py-1.5 font-normal">Etiqueta</th>
                        <th className="px-2 py-1.5 font-normal">Control</th>
                      </tr>
                    </thead>
                    <tbody data-testid="tabla-evidencia">
                      {filasVisibles.map((m) => (
                        <tr key={m.source_row_index} className="border-t border-white/5">
                          <td className="px-2 py-1.5 text-white/40">{m.source_row_index}</td>
                          <td className="px-2 py-1.5">{m.source_name ?? "—"}</td>
                          <td className="px-2 py-1.5">
                            {ROW_STATUS_LABELS[m.status]}
                            {m.error_code && (
                              <span className="mt-0.5 block max-w-xs text-[11px] leading-snug text-white/60">
                                {m.error_detail || "La evaluación no pudo completarse."}
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-1.5 font-mono">
                            {m.observed_vina_affinity_kcal_mol?.toFixed(2) ?? (
                              <span className="text-white/30">NO DISPONIBLE</span>
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
                          <td colSpan={6} className="border-t border-white/5 px-2 py-6 text-center text-white/60">
                            No hay moléculas con este estado.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <button type="button" className={`${PRIMARIO} mt-4`} onClick={verInforme} disabled={ocupado === "informe"}>
                  {ocupado === "informe" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  6 · Ver informe
                </button>
              </section>
            )}

            {/* ── 6 · Informe ───────────────────────────────────── */}
            {paso === "informe" && (
              <section className={`${CAJA} p-4`} aria-labelledby="inf" data-testid="informe">
                <h2 id="inf" className="text-sm font-semibold">6 · Informe</h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className={SECUNDARIO} onClick={descargarPdf} disabled={!pdfBlob}>
                    <Download className="h-3.5 w-3.5" /> Descargar PDF
                  </button>
                  <button type="button" className={SECUNDARIO} onClick={exportarZip} disabled={ocupado === "zip"}>
                    {ocupado === "zip" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileArchive className="h-3.5 w-3.5" />}
                    Exportar paquete ZIP
                  </button>
                </div>
                {zipGuardado && (
                  <p role="status" className="mt-2 text-[11px] text-white/40">
                    Paquete descargado como <span className="font-mono">{zipGuardado}</span>. Incluye su
                    manifiesto con hashes; la verificación la hace quien lo reciba.
                  </p>
                )}
                <div className="mt-3 h-[70vh] min-h-[24rem] overflow-hidden rounded-md border border-white/5 bg-black/40">
                  {pdfUrl ? (
                    <iframe src={`${pdfUrl}#toolbar=0`} title="Dossier de cohorte" className="h-full w-full border-none" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-white/30">
                      El dossier no está cargado.
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>

          {/* ── Lista lateral ─────────────────────────────────────── */}
          <aside className={`${CAJA} h-fit p-3`} aria-label="Cohortes guardadas">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold">Cohortes guardadas</h2>
              <button type="button" onClick={refrescarLista} className="text-white/30 hover:text-white/60" aria-label="Refrescar lista">
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>
            {guardadas.length === 0 ? (
              <p className="mt-2 text-xs font-medium text-white/55">Ninguna todavía.</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {guardadas.map((item) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => abrirGuardada(item)}
                      className="w-full rounded-md border border-white/5 bg-black/20 px-2 py-1.5 text-left transition-colors hover:border-white/15">
                      <span className="block truncate text-xs">{item.name}</span>
                      <span className="block text-[11px] font-medium text-white/60">
                        {item.receptor_pdb_id} · {item.summary.eligible_rows}/{item.summary.total_rows} elegibles
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 border-t border-white/5 pt-2 text-[11px] font-medium leading-relaxed text-white/55">
              Una cohorte guardada es inmutable: cambiar receptor, configuración o archivo
              produce otra cohorte, no una edición.
            </p>
          </aside>
        </div>

        <p className="mt-6 text-xs font-medium leading-relaxed text-white/55">
          <CheckCircle2 className="mr-1 inline h-3 w-3" aria-hidden="true" />
          Esta pantalla no ordena moléculas por mérito farmacológico ni produce ninguna
          puntuación agregada. La afinidad Vina observada es una señal de ranking dentro de
          este protocolo, no una medida de energía libre ni una predicción de actividad.
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
