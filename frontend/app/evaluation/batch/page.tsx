"use client";

import { presentError } from "../../../lib/frontendError";

/* Hallmark · pre-emit critique: P5 H4 E5 S5 R5 V4
 * Rediseño de cohortes: conserva el flujo y las operaciones existentes. */

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
  CONTROL_ROLE_KEYS, CohortError, ROW_STATUS_KEYS, RUN_STATUS_KEYS,
  SORT_BY_OBSERVED_AFFINITY, cancelRun, createCohort, dossierPackage, dossierPreview,
  getCohort, getEvidence, getLatestRun, getRun, isRunActive, listCohorts, openRun, preflightCohort,
  resumeRun,
  type CohortListItem, type CohortPreflightResult, type CohortRecord, type CohortRun,
  type CohortStudy, type ControlRole, type RunEvidence, type RowStatus,
} from "../../../lib/cohorts";
import { BatchRowResult } from "../../../components/evaluation/BatchRowResult";
import { EstimacionDeCorrida } from "../../../components/evaluation/EstimacionDeCorrida";
import { type Target } from "../../../lib/api";
import { obtenerCatalogo } from "../../../lib/catalogoDeReceptores";
import { saveBlobAs } from "../../../lib/dossier";
import { beginFileDownload, failFileDownload, notifyRunFinished } from "../../../lib/activityNotifications";
import { getUserItem, removeUserItem, setUserItem } from "../../../lib/userStorage";
import { InsigniaDelCatalogo } from "@/components/science/InsigniaDelCatalogo";
import TargetSelectorModal from "../../../components/interfaces/pro/TargetSelectorModal";
import { TRANSLATIONS, useLanguage } from "../../../context/LanguageContext";
import { useAuth } from "../../../lib/auth";
import { registerNativeJobDestinationResolver } from "../../../lib/nativeJobNotifications";

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

const CAJA = "border border-[var(--border)] bg-[var(--bg-card)]";
const ETIQUETA = "font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-dim)]";
const INPUT =
  "w-full min-w-0 border border-[var(--border-light)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--text)] " +
  "outline-none transition-colors placeholder:text-[var(--text-dim)] hover:border-[var(--accent)] " +
  "focus-visible:border-[var(--accent-strong)] focus-visible:ring-1 focus-visible:ring-[var(--accent-strong)]";
const BOTON =
  "inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 px-4 py-2 text-xs font-bold transition-colors " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] " +
  "disabled:cursor-not-allowed disabled:opacity-40";
const PRIMARIO = `${BOTON} bg-[var(--accent-strong)] text-[var(--bg)] hover:opacity-90 active:opacity-80`;
const SECUNDARIO = `${BOTON} border border-[var(--border-light)] bg-[var(--bg-card)] text-[var(--text)] hover:border-[var(--accent)] active:bg-[var(--bg-secondary)]`;

/**
 * El codigo de la comprobacion previa a su clave de traduccion.
 *
 * Se conserva el codigo del backend tal cual —`lo_msg_ARCHIVO_ILEGIBLE`— para
 * poder cruzarlo de un vistazo con `services/cohort/`. Un codigo que el backend
 * anada y aqui falte cae en `lo_msg_desconocido`, que dice que hay una
 * condicion sin describir en vez de callarla.
 */
/**
 * El rol de control en la lengua de la pantalla, o un guion si la fila no es un control.
 *
 * El índice de fila que la pantalla enseña es el ORDINAL de la molécula en el archivo
 * (1, 2, 3…), el mismo en la comprobación y en la evidencia. El paquete exportado
 * conserva `source_row_index` tal cual lo da el motor, base 0 (QA1-017).
 */
function etiquetaDeControl(rol: ControlRole, t: (clave: string) => string): string {
  const clave = CONTROL_ROLE_KEYS[rol];
  return clave ? t(clave) : "—";
}

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
  if (error instanceof CohortError) return presentError(error, t);
  return presentError((error as Error), t) || t("lo_operacion_fallida");
}


export default function CohortesPage() {
  // Toda la pantalla pasa por `t()`: es la superficie con mas texto de la
  // aplicacion y la que peor tolera una traduccion a medias, porque aqui se
  // declara lo que una corrida NO midio.
  const { t, locale } = useLanguage();
  const { user } = useAuth();

  // ── Definición ────────────────────────────────────────────────────
  const [nombre, setNombre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [pdbId, setPdbId] = useState("");
  const [cadena, setCadena] = useState("");
  const [exhaustividad, setExhaustividad] = useState(8);
  // 9 poses, como Evaluación: una molécula evaluada en las dos pantallas con los valores por
  // defecto debe usar el mismo protocolo (decisión del propietario, 2026-10-04; QA1 menor).
  const [poses, setPoses] = useState(9);
  const [semilla, setSemilla] = useState<string>("42");
  // Como Evaluación: por defecto se acopla el tautómero escrito (decisión del propietario, 2026-10-10).
  const [tautomero, setTautomero] = useState<"entrada" | "canonico">("entrada");
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
  const eleccionCohorte = useRef(0);
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
  const [informePedido, setInformePedido] = useState<{ runId: string; revision: number } | null>(null);

  const publicarPdf = useCallback((url: string | null) => {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = url;
    setPdfUrl(url);
  }, []);

  useEffect(() => {
    if (!informePedido || informePedido.runId !== corrida?.id) return;
    const controller = new AbortController();
    let vigente = true;
    publicarPdf(null);
    setPdfBlob(null);
    setZipGuardado(null);
    setError(null);
    setOcupado("informe");
    dossierPreview(informePedido.runId, controller.signal).then(({ blob, filename }) => {
      if (!vigente) return;
      publicarPdf(URL.createObjectURL(blob));
      setPdfBlob(blob);
      setPdfNombre(filename);
    }).catch(fallo => {
      if (vigente) setError(mensajeDe(fallo, t));
    }).finally(() => {
      if (vigente) setOcupado(null);
    });
    return () => { vigente = false; controller.abort(); };
  }, [informePedido, corrida?.id, locale, publicarPdf, t]);

  // Revocación al desmontar. Un blob de varios MB retenido por visita es una
  // fuga que el usuario paga en memoria.
  useEffect(() => {
    return () => {
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
    };
  }, []);

  const estudio: CohortStudy | null = useMemo(() => {
    const seed = semilla.trim() ? Number(semilla) : 42;
    if (!nombre.trim() || !pdbId.trim() || !Number.isInteger(seed) || seed < 1 || seed > 2147483647) return null;
    return {
      schema_version: 1,
      name: nombre.trim(),
      receptor: { pdb_id: pdbId.trim().toUpperCase(), ...(cadena.trim() ? { chain: cadena.trim().toUpperCase() } : {}) },
      config: {
        docking_engine: "vina",
        exhaustiveness: exhaustividad,
        num_poses: poses,
        seed,
        tautomero,
      },
    };
  }, [nombre, pdbId, cadena, exhaustividad, poses, semilla, tautomero]);

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
  }, [t]);

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
    // Una cohorte congelada sin el campo acopló el canónico de RDKit.
    setTautomero(estudioGuardado.config.tautomero === "entrada" ? "entrada" : "canonico");
  }, []);

  const nativeBatchState = useRef({ ownerId: user?.user_id, corrida, ocupado });
  nativeBatchState.current = { ownerId: user?.user_id, corrida, ocupado };
  const [nativeBatchSelection, setNativeBatchSelection] = useState<{ ownerId: string; jobId: string } | null>(null);
  const nativeBatchAck = useRef<((opened: boolean) => void) | null>(null);
  useEffect(() => {
    if (nativeBatchSelection && corrida?.id === nativeBatchSelection.jobId && user?.user_id === nativeBatchSelection.ownerId) {
      nativeBatchAck.current?.(true); nativeBatchAck.current = null;
    }
  }, [nativeBatchSelection, corrida?.id, user?.user_id]);
  useEffect(() => {
    const unregister = registerNativeJobDestinationResolver("batch", async destination => {
      const current = nativeBatchState.current;
      if (!current.ownerId || destination.ownerId !== current.ownerId || !destination.jobId || current.ocupado
        || (current.corrida && isRunActive(current.corrida.status) && current.corrida.id !== destination.jobId)) return false;
      const choice = ++eleccionCohorte.current;
      try {
        const requested = await getRun(destination.jobId);
        if (requested.id !== destination.jobId || choice !== eleccionCohorte.current
          || nativeBatchState.current.ownerId !== destination.ownerId) return false;
        const cohort = await getCohort(requested.cohort_id);
        if (cohort.id !== requested.cohort_id || choice !== eleccionCohorte.current
          || nativeBatchState.current.ownerId !== destination.ownerId || nativeBatchState.current.ocupado
          || (nativeBatchState.current.corrida && isRunActive(nativeBatchState.current.corrida.status)
            && nativeBatchState.current.corrida.id !== destination.jobId)) return false;
        return new Promise<boolean>(resolve => {
          nativeBatchAck.current?.(false);
          const timer = setTimeout(() => { if (nativeBatchAck.current === done) { nativeBatchAck.current = null; resolve(false); } }, 10000);
          const done = (opened: boolean) => { clearTimeout(timer); resolve(opened); };
          nativeBatchAck.current = done;
          restaurarDefinicion(cohort);
          setCorrida(requested); setEvidencia(null); publicarPdf(null); setPdfBlob(null); setZipGuardado(null);
          setUserItem("moldesign_cohort_run", requested.id);
          setPaso("ejecutar");
          setNativeBatchSelection({ ownerId: destination.ownerId, jobId: requested.id });
        });
      } catch { return false; }
    });
    return () => { unregister(); eleccionCohorte.current += 1; nativeBatchAck.current?.(false); nativeBatchAck.current = null; };
  }, [user?.user_id, restaurarDefinicion, publicarPdf]);

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
    if (!user?.user_id) return;
    const ownerAtStart = user.user_id;
    const guardado = getUserItem("moldesign_cohort_run");
    if (!guardado || corrida) return;
    let vivo = true;
    const eleccionAlMontar = eleccionCohorte.current;
    (async () => {
      try {
        const recuperada = await getRun(guardado);
        if (!vivo || eleccionAlMontar !== eleccionCohorte.current || nativeBatchState.current.ownerId !== ownerAtStart) return;
        const suya = await getCohort(recuperada.cohort_id);
        if (!vivo || eleccionAlMontar !== eleccionCohorte.current || nativeBatchState.current.ownerId !== ownerAtStart) return;
        restaurarDefinicion(suya);
        setCorrida(recuperada);
        setPaso("ejecutar");
      } catch {
        if (vivo && eleccionAlMontar === eleccionCohorte.current) removeUserItem("moldesign_cohort_run");
      }
    })();
    return () => {
      vivo = false;
    };
    // Sólo al montar: recuperar es una operación de arranque.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restaurarDefinicion, user?.user_id]);

  // ── Sondeo del progreso ───────────────────────────────────────────
  useEffect(() => {
    pollEpoch.current += 1;
    const epoch = pollEpoch.current;
    if (pollTimer.current !== null) window.clearTimeout(pollTimer.current);
    pollTimer.current = null;
    setPollError(null);
    if (!corrida || !isRunActive(corrida.status)) return;
    const ownerAtPoll = nativeBatchState.current.ownerId;
    let failures = 0;
    const schedule = (delay: number) => {
      if (pollEpoch.current !== epoch) return;
      pollTimer.current = window.setTimeout(() => void poll(), delay);
    };
    const poll = async () => {
      if (pollEpoch.current !== epoch) return;
      try {
        const next = await getRun(corrida.id);
        if (pollEpoch.current !== epoch || nativeBatchState.current.ownerId !== ownerAtPoll) return;
        failures = 0;
        setPollError(null);
        if (!isRunActive(next.status) && next.status !== "cancelled" && next.status !== "interrupted") {
          notifyRunFinished({
            source: "batch",
            runId: next.id,
            jobId: next.id, ownerId: ownerAtPoll,
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
  }, [corrida?.id, corrida?.status, pollNonce, t]);

  // ── Acciones ──────────────────────────────────────────────────────
  async function ejecutar<T>(clave: string, accion: () => Promise<T>): Promise<T | null> {
    if (ocupado) return null;
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
      const ownerId = nativeBatchState.current.ownerId;
      const next = await cancelRun(corrida.id);
      if (nativeBatchState.current.ownerId !== ownerId) return null;
      setCorrida(next);
      if (next.status === "cancelled") notifyRunFinished({ source: "batch", runId: next.id, jobId: next.id,
        ownerId, successful: false, outcome: "cancelled" });
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

  const verInforme = () => {
    if (!corrida || ocupado) return;
    setInformePedido(anterior => ({ runId: corrida.id, revision: (anterior?.revision ?? 0) + 1 }));
    setPaso("informe");
  };

  const descargarPdf = () => {
    if (!pdfBlob) return;
    saveBlobAs(pdfBlob, pdfNombre ?? t("lo_frontend_003"), "batch");
  };

  const exportarZip = () =>
    ejecutar("zip", async () => {
      if (!corrida) return null;
      const proposedName = t("lo_frontend_004", { v0: corrida.id });
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
      eleccionCohorte.current += 1;
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
  // QA1-015: la comprobación devolvía qué filas fallan y por qué, y la pantalla sólo enseñaba el
  // recuento («Inválidas 1»). En una cohorte de hasta 500 moléculas eso no deja corregir nada.
  const filasRechazadas = (preflight?.rows ?? []).filter((fila) => fila.eligibility !== "eligible");
  // Cuántos ligandos se van a acoplar DE VERDAD: los elegibles, no las filas
  // del archivo. Estimar sobre el total prometería tiempo por moléculas que la
  // comprobación previa ya descartó.
  const ligandosDeLaCohorte = resumen?.eligible_rows ?? 0;
  const filas = evidencia?.molecules ?? [];
  const filasVisibles = filtro === "todas" ? filas : filas.filter((m) => m.status === filtro);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] text-[var(--text)]">
      <div className="mx-auto max-w-[1500px] px-4 pb-16 pt-8 sm:px-7 lg:px-10">
        {/* ── Cabecera ────────────────────────────────────────────── */}
        <header className="flex flex-wrap items-start justify-between gap-5 border-b border-[var(--border)] pb-7">
          <div className="max-w-3xl min-w-0">
            <p className="mb-3 font-mono text-[11px] font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">{t("pg_nav_batch")}</p>
            <h1 className="font-display text-3xl font-bold leading-[1.08] tracking-tight sm:text-4xl lg:text-5xl">{t("lo_titulo_cohortes")}</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{t("pg_lote_intro")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="border border-[var(--border-light)] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">AutoDock Vina</span>
            <Link href="/evaluation" className={SECUNDARIO}>
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              {t("evaluation")}
            </Link>
          </div>
        </header>

        {/* ── Pasos ───────────────────────────────────────────────── */}
        <nav aria-label={t("lo_aria_pasos")} className="mt-7 grid grid-cols-3 gap-px border border-[var(--border)] bg-[var(--border)] lg:grid-cols-6">
          {PASOS.map((p) => (
            <span
              key={p.id}
              data-testid={`paso-${p.id}`}
              aria-current={paso === p.id ? "step" : undefined}
              className={`flex min-h-16 flex-col justify-center border-b-2 px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-[0.11em] ${
                paso === p.id
                  ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)] text-[var(--text)]"
                  : "border-transparent bg-[var(--bg-card)] text-[var(--text-dim)]"
              }`}
            >
              <span className="mb-1 text-[var(--accent-strong)]">0{p.n}</span>
              <span>{t(p.clave)}</span>
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

        <div className="mt-7 grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <div className="min-w-0 space-y-7">
            {/* ── 1 · Definir ───────────────────────────────────── */}
            <section className={`${CAJA} p-5 sm:p-7`} aria-labelledby="def">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">{t("lo_paso_definir")}</p>
              <h2 id="def" className="mt-2 font-display text-xl font-bold">{t("auto_568830f9f57b")}</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                {t("pg_lote_receptor_comun")}
              </p>

              <div className="mt-6 grid gap-5 border-t border-[var(--border)] pt-6 sm:grid-cols-2">
                <label className="block">
                  <span className={ETIQUETA}>{t("c_nombre")}</span>
                  <input className={`${INPUT} mt-1`} value={nombre} onChange={(e) => setNombre(e.target.value)}
                    placeholder={t("lo_nombre_ejemplo")} aria-label={t("lo_nombre_cohorte")} />
                </label>

                <section className="border-l-2 border-[var(--accent)] bg-[var(--bg-secondary)] p-5 sm:col-span-2" aria-labelledby="guia-archivo">
                  <h3 id="guia-archivo" className="font-display text-base font-bold">{t("lo_prepara_archivo")}</h3>
                  <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-xs leading-6 text-[var(--text-secondary)]">
                    <li>{t("lo_limite_moleculas")}</li>
                    <li>{t("lo_csv_recomendaciones")} <code className="font-mono font-semibold text-zinc-900 dark:text-white">smiles</code>{t("lo_tambien_se_aceptan")} <code className="font-mono">canonical_smiles</code> {t("ca_and")} <code className="font-mono">structure</code>.</li>
                    <li>{t("lo_mismo_receptor")}</li>
                  </ol>
                  <p className="mt-4 font-mono text-[10px] font-bold uppercase tracking-[0.13em] text-[var(--text-dim)]">{t("lo_ejemplo_csv")}</p>
                  <pre className="mt-2 overflow-x-auto border border-[var(--border)] bg-[var(--bg-card)] p-4 font-mono text-xs leading-6 text-[var(--text)]"><code>{`smiles,name,active,control_role
CC(=O)Nc1ccc(O)cc1,paracetamol,1,reference
CC(C)Cc1ccc(cc1)C(C)C(=O)O,ibuprofeno,0,none`}</code></pre>
                  <details className="mt-4 text-xs leading-6 text-[var(--text-secondary)]">
                    <summary className="cursor-pointer font-semibold text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("lo_ver_formatos")}</summary>
                    <div className="mt-3 space-y-3 border-t border-[var(--border)] pt-3">
                      <p><strong>{t("auto_460799387e92")}</strong> {t("lo_formatos_csv_xlsx")} <code className="font-mono">smiles</code>{t("lo_tambien_se_aceptan")} <code className="font-mono">canonical_smiles</code> {t("lo_o")} <code className="font-mono">structure</code>{t("lo_formatos_opcionales")} <code className="font-mono">name</code>, <code className="font-mono">{t("lo_campo_active")}</code> {t("ca_and")} <code className="font-mono">control_role</code>{t("lo_formatos_xlsx_hoja")}</p>
                      <p><strong>{t("auto_e3d883a02cc8")}</strong> {t("lo_formatos_smi")} <code className="font-mono">{t("lo_ejemplo_smi_columnas")}</code>{t("lo_formatos_smi_separador")} <code className="font-mono">#</code> {t("lo_formatos_smi_comentarios")}</p>
                      <p><strong>SDF:</strong> {t("lo_formatos_sdf")} <code className="font-mono">_Name</code>{t("lo_formatos_sdf_propiedades")} <code className="font-mono">{t("lo_campo_active")}</code> {t("ca_and")} <code className="font-mono">control_role</code> {t("lo_formatos_sdf_opcionales")}</p>
                      <p>{t("lo_formatos_para")} <code className="font-mono">{t("lo_campo_active")}</code>, {t("lo_formatos_usa")} <code className="font-mono">1</code> {t("lo_formatos_activa")} <code className="font-mono">0</code> {t("lo_formatos_inactiva")} <code className="font-mono">control_role</code>, {t("lo_formatos_usa")} <code className="font-mono">reference</code>, <code className="font-mono">positive</code>, <code className="font-mono">negative</code> {t("lo_o")} <code className="font-mono">none</code>.</p>
                    </div>
                  </details>
                </section>

                <label className="group block">
                  <span className={ETIQUETA}>{t("lo_archivo_moleculas")}</span>
                  <span className="relative mt-2 flex min-h-11 items-center gap-3 border border-dashed border-[var(--border-light)] bg-[var(--bg-secondary)] p-2 text-xs text-[var(--text-secondary)] group-focus-within:outline-2 group-focus-within:outline-[var(--accent-strong)]">
                    <input type="file" accept=".csv,.xlsx,.sdf,.smi,.txt" aria-label={t("lo_archivo_moleculas")}
                      aria-describedby="cohort-file-name"
                      onChange={(e) => seleccionarArchivo(e.target.files?.[0] ?? null)}
                      className="absolute inset-0 h-full w-full cursor-pointer opacity-0" />
                    <span aria-hidden="true" className="shrink-0 bg-[var(--border)] px-3 py-2 font-bold text-[var(--text)]">{t("lo_elegir_archivo")}</span>
                    <span id="cohort-file-name" className="min-w-0 break-all">{archivo?.name ?? t("lo_sin_archivo")}</span>
                  </span>
                </label>
                <div className="block">
                  {pdbId && <InsigniaDelCatalogo pdbId={pdbId} />}
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
                      {loadingTargets ? t("c_cargando") : targetsError ? t("c_reintentar") : t("lo_catalogo_con_cuenta", { n: targets.length })}
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
                    <label className={`flex items-start gap-3 border p-4 ${
                      motorHistoricoQuickVina
                        ? "border-[var(--border)] bg-[var(--bg-secondary)]"
                        : "border-[var(--accent-strong)] bg-[var(--bg-secondary)]"
                    }`}>
                      <input type="radio" name="motor" value="vina" checked={!motorHistoricoQuickVina} readOnly className="mt-0.5 accent-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50" />
                      <span><span className="block text-sm font-semibold">AutoDock Vina</span><span className="block text-xs text-zinc-600 dark:text-white/60">{t("lo_motor_disponible")}</span></span>
                    </label>
                    <label className={`flex cursor-not-allowed items-start gap-3 border p-4 ${
                      motorHistoricoQuickVina
                        ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                        : "border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-dim)]"
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
                    <input type="number" min={1} max={2147483647} step={1} className={`${INPUT} mt-1`} value={semilla} placeholder="42"
                      aria-label={t("se_gen_seed")} aria-describedby="batch-seed-help" onChange={(e) => setSemilla(e.target.value)} />
                    <button type="button" className="mt-1 text-xs underline" onClick={() => setSemilla("42")}>{t("lo_seed_default")}</button>
                  </label>
                </div>
                <p id="batch-seed-help" className="mt-2 text-xs text-[var(--text-dim)]">{t("lo_seed_help")}</p>
                <label className="block sm:col-span-2">
                  <span className={ETIQUETA}>{t("op_tautomero")}</span>
                  <select className={`${INPUT} mt-1`} value={tautomero} aria-label={t("op_tautomero")}
                    aria-describedby="batch-tautomer-help"
                    onChange={(e) => setTautomero(e.target.value === "canonico" ? "canonico" : "entrada")}>
                    <option value="entrada">{t("op_tautomero_entrada")}</option>
                    <option value="canonico">{t("op_tautomero_defecto")}</option>
                  </select>
                  <span id="batch-tautomer-help" className="mt-2 block text-xs text-[var(--text-dim)]">{t("lo_tautomero_help")}</span>
                </label>
              </div>

              <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[var(--border)] pt-5">
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
              <section className={`${CAJA} p-5 sm:p-7`} aria-labelledby="pre" data-testid="resumen-preflight">
                <h2 id="pre" className="font-display text-xl font-bold">{t("lo_titulo_comprobacion")}</h2>
                <p className="mt-1 text-sm text-zinc-600 dark:text-white/60">
                  {t("pg_lote_superarla_no_predice")}
                </p>

                <dl className="mt-5 grid grid-cols-2 gap-px border border-[var(--border)] bg-[var(--border)] sm:grid-cols-4">
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
                    <div key={String(etiqueta)} className="bg-[var(--bg-secondary)] px-4 py-3">
                      <dt className={ETIQUETA}>{etiqueta}</dt>
                      <dd className="mt-2 font-mono text-lg font-bold tabular-nums">{valor}</dd>
                    </div>
                  ))}
                </dl>

                <p className="mt-3 text-sm text-zinc-600 dark:text-white/50" data-testid="cobertura-preflight">
                  {t("auto_416ef02a1420")}{" "}
                  {resumen!.input_coverage === null
                    ? t("lo_cobertura_no_medible")
                    : `${(resumen!.input_coverage * 100).toFixed(1)} % · ${t("lo_cobertura_n_de_m", { n: resumen!.eligible_rows, m: resumen!.input_coverage_denominator })}`}
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

                {filasRechazadas.length > 0 && (
                  <details open={filasRechazadas.length <= 12} data-testid="filas-rechazadas"
                    className="mt-3 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2">
                    <summary className="cursor-pointer text-sm font-semibold">
                      {t("lo_filas_rechazadas_titulo", { n: filasRechazadas.length })}
                    </summary>
                    <p className="mt-1 text-xs text-zinc-600 dark:text-white/60">{t("lo_filas_rechazadas_ayuda")}</p>
                    <ul className="mt-2 space-y-1">
                      {filasRechazadas.slice(0, 50).map((fila) => (
                        <li key={fila.row_index} data-testid="fila-rechazada" className="text-xs leading-5">
                          <span className="font-mono font-semibold">{t("lo_fila_numero", { n: fila.row_index + 1 })}</span>
                          {fila.source_name ? ` · ${fila.source_name}` : ""} ·{" "}
                          <span className="break-all font-mono">{fila.input_smiles || "—"}</span>
                          {" — "}
                          {fila.reasons.map((razon) => t(claveDelMensaje(razon))).join(" ")}
                        </li>
                      ))}
                    </ul>
                    {filasRechazadas.length > 50 && (
                      <p className="mt-1 text-xs">{t("lo_y_n_mas", { n: filasRechazadas.length - 50 })}</p>
                    )}
                  </details>
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
              <section className={`${CAJA} p-5 sm:p-7`} aria-labelledby="run" data-testid="cohorte-guardada">
                <h2 id="run" className="font-display text-xl font-bold">{t("lo_titulo_ejecucion")}</h2>
                <p className="mt-1 break-all font-mono text-xs font-medium text-zinc-600 dark:text-white/60">
                  {t("lo_cohorte_prefijo")} {cohorte.id} · {cohorte.source.filename} · sha256 {cohorte.source.sha256.slice(0, 16)}…
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-2 text-xs font-medium text-zinc-600 dark:text-white/65">
                    {t("lo_paralelismo")}
                    <input type="number" min={1} max={4} value={workers} aria-label={t("lo_paralelismo")}
                      onChange={(e) => setWorkers(Number(e.target.value))}
                      className="w-16 border border-[var(--border-light)] bg-[var(--bg)] px-2 py-2 text-xs text-[var(--text)] outline-none focus-visible:border-[var(--accent-strong)] focus-visible:ring-1 focus-visible:ring-[var(--accent-strong)]" />
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
                      exhaustiveness={cohorte?.preflight.normalized_study.config.exhaustiveness ?? exhaustividad}
                      ligandos={ligandosDeLaCohorte}
                    />
                  </div>
                )}

                {corrida && (
                  <div className="mt-4" data-testid="progreso">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-medium">
                        {t(RUN_STATUS_KEYS[corrida.status])}
                        {corrida.cancel_requested && corrida.status !== "cancelled" && t("lo_cancelacion_pedida")}
                      </span>
                      <span className="break-all font-mono text-xs font-medium text-zinc-600 dark:text-white/55">
                        {t("lo_run_id_label", { id: corrida.id })}
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
                        <div key={String(etiqueta)} className="border-l-2 border-[var(--accent)] py-1 pl-3">
                          <dt className={ETIQUETA}>{etiqueta}</dt>
                          <dd className="mt-1 font-mono text-base font-bold tabular-nums">{valor}</dd>
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
                        disabled={isRunActive(corrida.status) || Boolean(ocupado)}>
                        <FileSpreadsheet className="h-3.5 w-3.5" /> {t("auto_8796008ea42e")}
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* ── 5 · Evidencia ─────────────────────────────────── */}
            {evidencia && (
              <section className={`${CAJA} p-5 sm:p-7`} aria-labelledby="ev" data-testid="evidencia">
                <h2 id="ev" className="font-display text-xl font-bold">{t("auto_cc09f4f40c71")}</h2>
                <InsigniaDelCatalogo pdbId={typeof evidencia.receptor.pdb_id === "string" ? evidencia.receptor.pdb_id : cohorte?.preflight.normalized_study.receptor.pdb_id ?? pdbId} corrida={{ receptor_sha256: evidencia.receptor.prepared_sha256, docking_protocol: evidencia.effective_config }} />
                <p className="mt-1 text-sm text-zinc-600 dark:text-white/60">
                  {t("pg_lote_orden_no_veredicto")}
                </p>

                <dl className="mt-5 grid grid-cols-2 gap-3 border-y border-[var(--border)] py-5 sm:grid-cols-4" data-testid="cobertura-evidencia">
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
                    <div key={String(etiqueta)} className="border-l-2 border-[var(--accent)] py-1 pl-3">
                      <dt className={ETIQUETA}>{etiqueta}</dt>
                      <dd className="mt-1 font-mono text-base font-bold tabular-nums">{valor}</dd>
                    </div>
                  ))}
                </dl>

                {/* Métricas: evaluables o abstención declarada */}
                <div className="mt-5 border-l-2 border-[var(--accent)] bg-[var(--bg-secondary)] px-4 py-4" data-testid="metricas">
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
                  <div className="mt-4 border-l-2 border-[var(--accent)] bg-[var(--bg-secondary)] px-4 py-4" data-testid="controles">
                    <p className={ETIQUETA}>{t("lo_controles_declarados")}</p>
                    <ul className="mt-1 space-y-0.5">
                      {evidencia.labeled_metrics.controls.map((c) => (
                        <li key={c.source_row_index} className="text-xs text-zinc-600 dark:text-white/60">
                          #{c.source_row_index + 1} {c.source_name ?? "—"} · {etiquetaDeControl(c.control_role, t)} ·{" "}
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

                <div className="mt-5 flex flex-wrap gap-2 border-t border-[var(--border)] pt-5" role="group" aria-label={t("lo_filtrar_por_estado")}>
                  {FILTROS.map((f) => (
                    <button key={f.id} type="button" onClick={() => setFiltro(f.id)}
                      aria-pressed={filtro === f.id}
                      className={`cursor-pointer border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${
                        filtro === f.id
                          ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)] text-[var(--text)]"
                          : "border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-dim)] hover:border-[var(--border-light)] hover:text-[var(--text)]"
                      }`}>
                      {t(f.clave)}
                    </button>
                  ))}
                </div>

                <div className="mt-4 overflow-x-auto border border-[var(--border)]">
                  <table className="w-full min-w-[46rem] text-left text-xs tabular-nums">
                    <thead className="bg-[var(--bg-secondary)] font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">
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
                        <tr key={m.source_row_index} className="border-t border-[var(--border)] hover:bg-[var(--bg-secondary)]">
                          <td className="px-2 py-1.5 text-zinc-500 dark:text-white/60">{m.source_row_index + 1}</td>
                          <td className="px-2 py-1.5">{m.source_name ?? "—"}{m.molecule_id && <BatchRowResult row={m} pdbId={cohorte?.preflight.normalized_study.receptor.pdb_id ?? pdbId} />}</td>
                          <td className="px-2 py-1.5">
                            {t(ROW_STATUS_KEYS[m.status])}
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
                            {m.active_label === null ? "—" : t(m.active_label ? "lo_etiqueta_activa" : "lo_etiqueta_inactiva")}
                          </td>
                          <td className="px-2 py-1.5">{etiquetaDeControl(m.control_role, t)}</td>
                        </tr>
                      ))}
                      {filasVisibles.length === 0 && (
                        <tr>
                          <td colSpan={6} className="border-t border-[var(--border)] px-2 py-6 text-center text-[var(--text-muted)]">
                            {t("pg_lote_sin_estado")}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <button type="button" className={`${PRIMARIO} mt-4`} onClick={verInforme} disabled={Boolean(ocupado)}>
                  {ocupado === "informe" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  {t("auto_2f1a6f19a8c3")}
                </button>
              </section>
            )}

            {/* ── 6 · Informe ───────────────────────────────────── */}
            {paso === "informe" && (
              <section className={`${CAJA} p-5 sm:p-7`} aria-labelledby="inf" data-testid="informe">
                <h2 id="inf" className="font-display text-xl font-bold">{t("auto_304a0bfa0894")}</h2>
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
                <div className="mt-4 h-[70vh] min-h-[24rem] overflow-hidden border border-[var(--border)] bg-[var(--bg-secondary)]">
                  {pdfUrl ? (
                    <iframe src={`${pdfUrl}#toolbar=0&view=FitH`} title={t("lo_dossier_cohorte")} className="h-full w-full border-none" />
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
          <aside className={`${CAJA} h-fit p-5 xl:sticky xl:top-20`} aria-label={t("lo_cohortes_guardadas")}>
            <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
              <div><p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">{t("lo_paso_guardar")}</p><h2 className="mt-2 font-display text-lg font-bold">{t("lo_cohortes_guardadas")}</h2></div>
              <button type="button" onClick={refrescarLista} className="flex size-9 cursor-pointer items-center justify-center border border-[var(--border-light)] text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--text)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]" aria-label={t("lo_refrescar_lista")}>
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
            {guardadas.length === 0 ? (
              <p className="mt-5 border border-dashed border-[var(--border-light)] p-5 text-xs leading-6 text-[var(--text-muted)]">{t("lo_ninguna_todavia")}</p>
            ) : (
              <ul className="mt-4 max-h-[50vh] space-y-2 overflow-y-auto">
                {guardadas.map((item) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => abrirGuardada(item)} disabled={Boolean(ocupado)}
                      className="w-full cursor-pointer border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-3 text-left transition-colors hover:border-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
                      <span className="block truncate text-xs font-bold">{item.name}</span>
                      <span className="mt-1 block font-mono text-[10px] text-[var(--text-dim)]">
                        <InsigniaDelCatalogo compacta pdbId={item.receptor_pdb_id} />
                        {item.receptor_pdb_id} · {item.summary.eligible_rows}/{item.summary.total_rows} {t("lo_elegibles_sufijo")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-5 border-t border-[var(--border)] pt-4 text-xs leading-6 text-[var(--text-muted)]">
              {t("pg_lote_inmutable")}
            </p>
          </aside>
        </div>

        <p className="mt-7 border-t border-[var(--border)] pt-5 text-xs leading-6 text-[var(--text-muted)]">
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
