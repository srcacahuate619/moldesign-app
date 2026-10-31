"use client";

import { presentError } from "../../lib/frontendError";

/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V4
 * Molcy: workspace de edición; la vista esquemática nunca se presenta como evidencia. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { useAuth } from "@/lib/auth";
import { useKeepAliveActive } from "@/context/KeepAliveContext";
import { registerNativeJobDestinationResolver } from "@/lib/nativeJobNotifications";
import { sameMolcyAjustes } from "@/lib/molcyPresentation";
import { PresentationControls, AUTO_PRESENTATION, type EnsembleVariant } from "@/components/molcy/PresentationControls";
import { RendererSettings } from "@/components/molcy/RendererSettings";
import { CpuControls } from "@/components/molcy/CpuControls";
import { GpuControls } from "@/components/molcy/GpuControls";
import { JobHistory } from "@/components/molcy/JobHistory";
import { PhotoStudio } from "@/components/molcy/PhotoStudio";
import { DownloadButton } from "@/components/molcy/DownloadButton";
import { InsigniaDelCatalogo } from "@/components/science/InsigniaDelCatalogo";
import { InsigniaDeCorridaGuardada } from "@/components/science/InsigniaDeCorridaGuardada";
import { CatalogoReceptoresMolcy } from "@/components/molcy/CatalogoReceptoresMolcy";
import { CustomReceptorModal } from "@/components/interfaces/pro/CustomReceptorModal";
import { OutputFolder, type EleccionDeEsteVideo } from "@/components/molcy/OutputFolder";
import { PildoraBeta } from "@/components/ui/PildoraBeta";
import { PaqueteMolcyCard } from "@/components/PaqueteMolcyCard";
import {
  FALTA_PARA_EL_PAQUETE, cancelarMolcy, crearFotosMolcy, descargarProcedenciaMolcy, crearMolcy, descargarMolcy, estadoMolcy, fotogramaMolcy, fuentesMolcy,
  pieDelFotograma, recursosMolcy, renderizadorMolcy, salidaMolcy, videoMolcy,
  type MolcyEscena, type MolcyFotograma, type MolcyJob, type MolcyOrientacion, type MolcyRenderer, type MolcySalida, type MolcySources,
} from "@/lib/molcy";
import {
  Aperture, ArrowLeft, ArrowRight, Camera, Check, CircleHelp, Film, Layers3, MonitorPlay,
  Monitor, ScanEye, Smartphone, Sparkles, WandSparkles,
} from "lucide-react";

type SceneId = MolcyEscena;
type FormatId = "vertical" | "horizontal" | "previsualizacion";
/** Qué se entrega: un vídeo (sólo con GPU) o fotos de la escena (Cycles en CPU o en GPU). Decisión del propietario, 2026-10-08. */
type ModeId = "video" | "foto";

const scenes = {
  resultado: {
    number: "01",
    icon: ScanEye,
    es: { name: "Resultado", summary: "Receptor preparado, pose Vina top-1 de la corrida y sus interacciones polares y apolares con el sitio.", phase: ["Receptor preparado", "Pose Vina top-1", "Interacciones medidas"] },
    en: { name: "Result", summary: "Prepared receptor, the run's Vina top-1 pose and its polar and apolar interactions with the site.", phase: ["Prepared receptor", "Vina top-1 pose", "Measured interactions"] },
  },
  receptor: {
    number: "02",
    icon: Aperture,
    es: { name: "Receptor", summary: "Recorrido estructural sin afirmar docking.", phase: ["Estructura preparada", "Caja registrada", "Contexto estructural"] },
    en: { name: "Receptor", summary: "Structural tour without claiming docking.", phase: ["Prepared structure", "Recorded box", "Structural context"] },
  },
  busqueda: {
    number: "03",
    icon: Sparkles,
    es: { name: "Búsqueda", summary: "Poses y pasos registrados durante la exploración, con las interacciones polares y apolares de cada pose.", phase: ["Sitio activo", "Exploración registrada", "Pose seleccionada"] },
    en: { name: "Search", summary: "Recorded poses and steps from the exploration, with each pose's polar and apolar interactions.", phase: ["Active site", "Recorded search", "Selected pose"] },
  },
  ensamble: {
    number: "04",
    icon: Layers3,
    es: { name: "Ensamble", summary: "Las conformaciones que aportaron poses, la mejor pose de cada corrida de Vina y las poses entregadas con sus controles e interacciones.", phase: ["Conformaciones de entrada", "Corridas de Vina", "Poses entregadas y controles"] },
    en: { name: "Ensemble", summary: "The conformations that contributed poses, each Vina run's best pose and the delivered poses with their checks and interactions.", phase: ["Input conformations", "Vina runs", "Delivered poses and checks"] },
  },
} as const;

const copy = {
  es: {
    eyebrow: "ESTUDIO VISUAL · MOLCY",
    intro: "Compón un video o toma fotos de una corrida concreta de Moldex o de un receptor disponible. Cada escena usa sólo la evidencia conservada.",
    draft: "RENDER LOCAL",
    source: "01 / ORIGEN",
    sourceTitle: "Elige el origen",
    sourceMissing: "Ninguna corrida vinculada",
    sourceDetail: "Moldex vincula el video a una corrida exacta. Un receptor por sí solo produce un recorrido estructural.",
    scenes: "02 / NARRATIVA",
    scenesTitle: "Elige qué contar",
    searchNote: "Búsqueda requiere una traza real; el número de pasos nunca se infiere de las poses finales.",
    ensembleNote: "Ensamble enseña sólo lo que la corrida conservó: las conformaciones se alinean a la mejor pose para compararlas y los controles se aplicaron después del acoplamiento. Si un control no se evaluó, el video lo dice.",
    preview: "VISTA PREVIA",
    previewHint: "Esquema de composición · sin datos moleculares cargados",
    previewEmpty: "Aquí aparecerá el sitio activo de la corrida seleccionada.",
    playback: "Fotograma conceptual",
    storyboard: "GUION VISUAL",
    output: "03 / SALIDA",
    outputTitle: "Formato de entrega",
    vertical: "Vertical",
    horizontal: "Horizontal",
    formatHint: "La composición se adaptará al formato. Las estructuras y cifras seguirán siendo las mismas.",
    evidence: "Regla de evidencia",
    evidenceText: "Si falta la traza, una pose o un control, Molcy lo indicará y no dibujará datos de sustitución.",
    generate: "Generar video",
    preparePhotos: "Preparar tomas",
    disabled: "Selecciona una fuente, una escena disponible y un renderizador local.",
    noBackend: "El render se ejecuta en Blender con el motor Molcy externo.",
  },
  en: {
    eyebrow: "VISUAL STUDIO · MOLCY",
    intro: "Compose a video or take photos from one exact Moldex run or an available receptor. Each scene uses only saved evidence.",
    draft: "LOCAL RENDER",
    source: "01 / SOURCE",
    sourceTitle: "Choose a source",
    sourceMissing: "No run linked",
    sourceDetail: "Moldex links the video to an exact run. A receptor alone produces a structural tour.",
    scenes: "02 / NARRATIVE",
    scenesTitle: "Choose what to show",
    searchNote: "Search requires a real trace; the number of steps is never inferred from final poses.",
    ensembleNote: "Ensemble shows only what the run kept: conformations are aligned to the best pose for comparison, and the checks were applied after docking. If a check was not evaluated, the video says so.",
    preview: "PREVIEW",
    previewHint: "Composition sketch · no molecular data loaded",
    previewEmpty: "The selected run’s active site will appear here.",
    playback: "Concept frame",
    storyboard: "VISUAL STORYBOARD",
    output: "03 / OUTPUT",
    outputTitle: "Delivery format",
    vertical: "Vertical",
    horizontal: "Horizontal",
    formatHint: "The composition will adapt to the format. Structures and figures will remain the same.",
    evidence: "Evidence rule",
    evidenceText: "If a trace, pose or check is missing, Molcy will say so and will not draw substitute data.",
    generate: "Generate video",
    preparePhotos: "Prepare shots",
    disabled: "Choose a source, an available scene and a local renderer.",
    noBackend: "Rendering runs in Blender through the external Molcy engine.",
  },
};

export default function MolcyPage() {
  const { user } = useAuth();
  return <MolcyWorkspace key={user?.user_id || "sin-sesion"} />;
}

function MolcyWorkspace() {
  const { t, locale } = useLanguage();
  const { user } = useAuth();
  const c = copy[locale];
  const [scene, setScene] = useState<SceneId>("resultado");
  const [format, setFormat] = useState<FormatId>("vertical");
  const [mode, setModeState] = useState<ModeId>("video");
  // La persona eligió el modo: el sondeo del renderizador ya no lo cambia por ella.
  const modeTouched = useRef(false);
  const setMode = useCallback((value: ModeId) => { modeTouched.current = true; setModeState(value); }, []);
  const [orientacion, setOrientacion] = useState<MolcyOrientacion>("vertical");
  // El dispositivo de las FOTOS (Cycles en CPU o en GPU). El vídeo siempre usa la GPU.
  const [device, setDevice] = useState<"cpu" | "gpu">("gpu");
  const [selectedThreads, setSelectedThreads] = useState<number | null>(null);
  const [resourcesError, setResourcesError] = useState(false);
  const [sourceKind, setSourceKind] = useState<"moldex" | "receptor">("moldex");
  const [sourceId, setSourceId] = useState("");
  const [sources, setSources] = useState<MolcySources | null>(null);
  const [renderer, setRenderer] = useState<MolcyRenderer | null>(null);
  // Blender o Molecular Nodes instalándose desde la tarjeta del estudio: la configuración espera.
  const [paqueteInstalando, setPaqueteInstalando] = useState(false);
  const [salida, setSalida] = useState<MolcySalida | null>(null);
  const [esteVideo, setEsteVideo] = useState<EleccionDeEsteVideo>(null);
  // Lo que se le pide al backend: la carpeta de ESTE vídeo, «predeterminada» o nada (entonces vale la de «todos»).
  const salidaSolicitada = esteVideo === null ? undefined : esteVideo === "predeterminada" ? "predeterminada" : esteVideo.id;
  const [presentacion, setPresentacion] = useState(AUTO_PRESENTATION);
  const [ensembleVariant, setEnsembleVariant] = useState<EnsembleVariant>("lenta");
  const [job, setJob] = useState<MolcyJob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoPlaybackError, setVideoPlaybackError] = useState(false);
  // El último fotograma que Blender terminó de rendir: se enseña en el panel central mientras el vídeo se forma.
  const [liveFrame, setLiveFrame] = useState<MolcyFotograma | null>(null);
  const pieEnVivo = liveFrame ? pieDelFotograma(liveFrame) : null;
  const liveUrl = useRef<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  // El trabajo que el historial ve en curso (render de vídeo o sesión de fotos preparándose), aunque el estudio enseñe otro.
  const [enCurso, setEnCurso] = useState<MolcyJob | null>(null);
  const [videoAttempt, setVideoAttempt] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const userId = user?.user_id;
  const ownerRef = useRef(userId);
  ownerRef.current = userId;
  const selectionRevision = useRef(0);
  const jobId = job?.id;
  const jobEstado = job?.estado;
  const esSesionDeFotos = job?.tipo === "fotos";
  // Enseñar otro trabajo en el estudio (desde el historial o desde el aviso del trabajo en curso). El que se deja no se
  // detiene: sigue en el backend, y el historial lo ofrece para volver.
  const verTrabajo = useCallback((next: MolcyJob) => {
    selectionRevision.current += 1;
    setError(null);
    if (next.id === jobId && next.estado === jobEstado) {
      setJob(next);
      return;
    }
    setVideoUrl(null); setVideoPlaybackError(false); setJob(next);
  }, [jobId, jobEstado]);
  useEffect(() => registerNativeJobDestinationResolver("molcy", async destination => {
    if (!destination.jobId || destination.ownerId !== ownerRef.current) return false;
    const requestedOwner = destination.ownerId;
    const next = await estadoMolcy(destination.jobId);
    if (ownerRef.current !== requestedOwner || next.id !== destination.jobId) return false;
    verTrabajo(next);
    return true;
  }), [verTrabajo]);
  // Molcy no se desmonta al cambiar de pestaña (PersistentKeepAliveLayout): conserva lo elegido y un render en curso
  // sigue en segundo plano. Oculta, sigue preguntando por el trabajo y por las instalaciones; deja de pedir recursos,
  // fotogramas en vivo y el historial, y pausa cualquier vídeo. Al volver, refresca las corridas guardadas en Moldex.
  const activa = useKeepAliveActive();
  const raiz = useRef<HTMLElement>(null);
  const vistaAntes = useRef(activa);
  useEffect(() => {
    const volvio = activa && !vistaAntes.current;
    vistaAntes.current = activa;
    if (!activa) raiz.current?.querySelectorAll("video").forEach((video) => video.pause());
    if (!volvio || !userId) return;
    let alive = true;
    fuentesMolcy().then((next) => { if (alive) setSources(next); }).catch(() => { /* se queda la lista que había */ });
    return () => { alive = false; };
  }, [activa, userId]);
  const mostrarFotograma = useCallback((next: MolcyFotograma | null) => {
    if (liveUrl.current && liveUrl.current !== next?.url) URL.revokeObjectURL(liveUrl.current);
    liveUrl.current = next?.url ?? null;
    setLiveFrame(next);
  }, []);
  useEffect(() => () => { if (liveUrl.current) URL.revokeObjectURL(liveUrl.current); }, []);
  const usarRenderizador = useCallback((next: MolcyRenderer) => {
    setRenderer(next);
    setDevice(current => (current === "gpu" && !next.foto_gpu_disponible) ? "cpu" : current);
    if (!modeTouched.current && !next.gpu_disponible && next.foto_disponible) setModeState("foto");
  }, []);
  const refreshRenderer = useCallback(async () => {
    // Lo llama la configuración tras guardar o pulsar «Comprobar»: ahí sí hay que sondear de nuevo.
    usarRenderizador(await renderizadorMolcy(true));
  }, [usarRenderizador]);
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoading(true);
    const sourceRequest = fuentesMolcy().then(s => { if (!cancelled) setSources(s); });
    const rendererRequest = renderizadorMolcy().then(r => {
      if (!cancelled) {
        setRenderer(r);
        setDevice(current => (current === "gpu" && !r.foto_gpu_disponible) ? "cpu" : current);
        // Sin GPU para vídeo, la página abre en fotos (que sí funcionan con la CPU), salvo que la persona haya elegido.
        if (!modeTouched.current && !r.gpu_disponible && r.foto_disponible) setModeState("foto");
      }
    });
    Promise.allSettled([sourceRequest, rendererRequest]).then(results => {
      if (cancelled) return;
      const failure = results.find(result => result.status === "rejected");
      if (failure?.status === "rejected") setError((failure.reason as Error).message);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [userId, locale]);
  useEffect(() => {
    if (!userId) return;
    const key = `molcy-job:${userId}`;
    let saved: string | null = null;
    try { saved = window.localStorage.getItem(key); } catch {}
    let alive = true;
    const revision = selectionRevision.current;
    setJob(null);
    if (saved) estadoMolcy(saved).then(value => { if (alive && revision === selectionRevision.current && ownerRef.current === userId) setJob(value); }).catch(() => { if (alive) { try { window.localStorage.removeItem(key); } catch {} } });
    return () => { alive = false; };
  }, [userId]);

  useEffect(() => {
    if (!activa || !userId || !renderer?.disponible || submitting || historyBusy || jobEstado === "en_cola" || jobEstado === "renderizando") return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const update = async () => {
      try {
        const latest = await recursosMolcy(sourceKind === "moldex" ? sourceId : null, salidaSolicitada);
        if (!cancelled) { setRenderer(previous => previous ? { ...previous, ...latest } : previous); setResourcesError(false); }
      } catch { if (!cancelled) setResourcesError(true); }
      finally { if (!cancelled) timer = setTimeout(update, 5000); }
    };
    void update();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [activa, userId, renderer?.disponible, submitting, historyBusy, jobEstado, sourceKind, sourceId, salidaSolicitada]);
  useEffect(() => {
    let alive = true;
    salidaMolcy().then(value => { if (alive) setSalida(value); }).catch(() => { if (alive) setSalida(null); });
    return () => { alive = false; };
  }, [userId]);
  useEffect(() => {
    if (userId && jobId) { try { window.localStorage.setItem(`molcy-job:${userId}`, jobId); } catch {} }
  }, [userId, jobId]);
  useEffect(() => {
    if (!jobId || !["en_cola", "renderizando"].includes(jobEstado || "")) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const owner = userId;
    const tick = async () => {
      try {
        const next = await estadoMolcy(jobId);
        if (!cancelled && ownerRef.current === owner && next.id === jobId) setJob(current => current?.id === jobId ? next : current);
      } catch (error) { if (!cancelled && ownerRef.current === owner) setError(presentError((error as Error), t)); }
      if (!cancelled) timer = setTimeout(tick, 3000);
    };
    timer = setTimeout(tick, 3000);
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [jobId, jobEstado, userId, t]);
  useEffect(() => {
    if (jobEstado !== "completo" || !jobId || esSesionDeFotos) return;
    let cancelled = false;
    videoMolcy(jobId).then((url) => {
      if (!cancelled) setVideoUrl(url);
    }).catch((e: Error) => { if (!cancelled) setError(presentError(e, t)); });
    return () => { cancelled = true; };
  }, [jobId, jobEstado, videoAttempt, esSesionDeFotos, t]);
  // Vista previa en vivo: mientras Blender renderiza se pide, cada poco, el último fotograma entero. Es un extra: si falla no
  // se muestra como error ni interrumpe el render.
  useEffect(() => {
    if (!activa || !jobId || jobEstado !== "renderizando" || esSesionDeFotos) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let ultimo: number | undefined;
    const controller = new AbortController();
    const tick = async () => {
      try {
        const frame = await fotogramaMolcy(jobId, ultimo, controller.signal);
        if (cancelled) { if (frame) URL.revokeObjectURL(frame.url); return; }
        if (frame) { ultimo = frame.indice; mostrarFotograma(frame); }
      } catch { /* sin vista previa este turno */ }
      if (!cancelled) timer = setTimeout(tick, 1500);
    };
    void tick();
    return () => { cancelled = true; controller.abort(); if (timer) clearTimeout(timer); };
  }, [activa, jobId, jobEstado, mostrarFotograma, esSesionDeFotos]);
  // El fotograma es de UN trabajo: cambiar de trabajo, fallar o llegar el vídeo lo retira.
  useEffect(() => { mostrarFotograma(null); }, [jobId, mostrarFotograma]);
  useEffect(() => {
    if (videoUrl || jobEstado === "fallido" || jobEstado === "cancelado") mostrarFotograma(null);
  }, [videoUrl, jobEstado, mostrarFotograma]);

  const candidates = sourceKind === "moldex" ? sources?.moldex : sources?.receptores;
  const chosen = candidates?.find((item) => (sourceKind === "moldex" ? item.task_id : item.id) === sourceId);
  const canScene = Boolean(chosen?.disponible &&
    ((sourceKind === "moldex" && (scene === "resultado" || scene === "busqueda" || scene === "ensamble")) || scene === "receptor") &&
    (!chosen.escenas_disponibles || chosen.escenas_disponibles.includes(scene)));
  const destinationRun = sourceKind === "moldex" ? sourceId || null : null;
  // El espacio sólo vale si se midió para ESTA corrida y ESTA carpeta de salida.
  // El espacio sólo vale si se midió para ESTA corrida y ESTA carpeta. Una sesión de fotos reserva lo de una foto 4K.
  const diskBudget = (renderer?.espacio_task_id ?? null) === destinationRun
    && (renderer?.espacio_salida_id ?? null) === (salidaSolicitada ?? null)
    ? (mode === "foto" ? renderer?.espacio_fotos?.["4k"]
      : renderer?.espacio?.[format === "horizontal" ? "biblioteca" : format === "vertical" ? "social_vertical" : "previsualizacion"])
    : undefined;
  const cpuMaximum = renderer?.cpu_hilos_maximos ?? Math.max(1, Math.floor((renderer?.cpu_hilos_disponibles || 1) * 0.75));
  const cpuThreads = Math.min(cpuMaximum, selectedThreads ?? renderer?.cpu_hilos ?? 1);
  // Falta lo que se arregla descargando (Blender o Molecular Nodes): la tarjeta del estudio, bajo el guion, lo instala.
  const faltaPaquete = Boolean(renderer && !renderer.disponible && FALTA_PARA_EL_PAQUETE.has(renderer.motivo_codigo ?? ""));
  const canGpu = Boolean(renderer?.gpu_disponible);
  const canPhotoGpu = Boolean(renderer?.foto_gpu_disponible);
  const busy = Boolean(submitting || historyBusy || jobEstado === "en_cola" || jobEstado === "renderizando");
  // La misma escena ya preparada en el estudio: no hace falta prepararla otra vez.
  const ajustes = { presentacion, ...(scene === "ensamble" && ensembleVariant !== "referencia" ? { ensamble_fluido: { variante: ensembleVariant } } : {}) };
  const samePresentation = sameMolcyAjustes(ajustes, job?.ajustes);
  const sameSession = Boolean(samePresentation && esSesionDeFotos && jobEstado === "completo" && chosen && job?.escena === scene &&
    job?.orientacion === orientacion && (sourceKind === "moldex" ? job?.fuente?.task_id === chosen.task_id : job?.fuente?.id === chosen.id));
  const canGenerate = mode === "video"
    ? Boolean(canScene && renderer?.disponible && diskBudget?.disponible && canGpu && !busy)
    : Boolean(canScene && renderer?.foto_disponible && diskBudget?.disponible && !busy && !sameSession &&
      (device === "gpu" ? canPhotoGpu : !resourcesError));
  const generate = async () => {
    if (!chosen || !canGenerate) return;
    const revision = selectionRevision.current;
    const owner = userId;
    setError(null);
    setSubmitting(true);
    setVideoUrl(null);
    setVideoPlaybackError(false);
    mostrarFotograma(null);
    try {
      const next = mode === "video"
        ? await crearMolcy({ origen: sourceKind, id: chosen.id,
          task_id: chosen.task_id, escena: scene, formato: format, dispositivo: "gpu", ...ajustes,
          ...(salidaSolicitada ? { salida_id: salidaSolicitada } : {}) })
        : await crearFotosMolcy({ origen: sourceKind, id: chosen.id, task_id: chosen.task_id, escena: scene, orientacion, ...ajustes,
          dispositivo: device, ...(device === "cpu" && renderer?.cpu_hilos_configurables ? { cpu_hilos: cpuThreads } : {}),
          ...(salidaSolicitada ? { salida_id: salidaSolicitada } : {}) });
      if (ownerRef.current === owner) window.dispatchEvent(new CustomEvent("moldesign:molcy-job-created", { detail: { ownerId: owner, jobId: next.id } }));
      if (ownerRef.current === owner && revision === selectionRevision.current) verTrabajo(next);
      setEsteVideo(null); // «sólo este vídeo» no se arrastra al siguiente
    } catch (e) { setError(presentError((e as Error), t)); }
    finally { setSubmitting(false); }
  };
  const selected = scenes[scene][locale];

  return (
    <main ref={raiz} className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] px-4 pb-16 pt-8 text-[var(--text)] sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px]">
        <header className="mb-8 flex flex-wrap items-start justify-between gap-5 border-b border-[var(--border)] pb-7">
          <div className="max-w-3xl min-w-0">
            <p className="mb-3 font-mono text-[11px] font-bold tracking-[0.22em] text-[var(--accent-strong)]">{c.eyebrow}<PildoraBeta /></p>
            <h1 className="font-display text-3xl font-bold leading-[1.08] tracking-tight [overflow-wrap:anywhere] sm:text-4xl lg:text-5xl">{t("pg_molcy_titulo")}</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{c.intro}</p>
          </div>
          <span className="border border-[var(--border-light)] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-dim)]">{c.draft}</span>
        </header>

        <div className="grid items-start gap-6 xl:grid-cols-[minmax(245px,0.84fr)_minmax(360px,1.55fr)_minmax(250px,0.82fr)]">
          <aside className="space-y-7">
            <section aria-labelledby="molcy-source-title">
              <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.source}</p>
              <h2 id="molcy-source-title" className="font-display text-xl font-bold">{c.sourceTitle}</h2>
              <div className="mt-4 border border-dashed border-[var(--border-light)] bg-[var(--bg-card)] p-5">
                <div className="grid grid-cols-2 gap-2">
                  {(["moldex", "receptor"] as const).map((kind) =>
                    <button key={kind} type="button" aria-pressed={sourceKind === kind}
                      onClick={() => { setSourceKind(kind); setSourceId(""); setScene(kind === "moldex" ? "resultado" : "receptor"); }}
                      className={`border px-3 py-3 text-xs font-semibold ${sourceKind === kind ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)]"}`}>
                      {t(kind === "moldex" ? "cy_origen_moldex" : "cy_origen_receptor")}
                    </button>)}
                </div>
                {sourceKind === "receptor" ? <CatalogoReceptoresMolcy sources={candidates ?? []} selected={sourceId} onSelect={setSourceId} onUpload={() => setShowUpload(true)} /> : <>
                <label htmlFor="molcy-source" className="mt-4 block text-xs font-semibold">{t("cy_elegir")}</label>
                <select id="molcy-source" value={sourceId} onChange={(event) => {
                  const value = event.target.value;
                  setSourceId(value);
                  const source = candidates?.find(item => (sourceKind === "moldex" ? item.task_id : item.id) === value);
                  if (source?.escenas_disponibles?.length && !source.escenas_disponibles.includes(scene))
                    setScene(source.escenas_disponibles[0]);
                }}
                  className="mt-2 w-full border border-[var(--border-light)] bg-[var(--bg-secondary)] p-3 text-sm text-[var(--text)]">
                  <option value="">{t("cy_elegir")}</option>
                  {candidates?.map((item) => <option key={item.task_id || item.id} value={sourceKind === "moldex" ? item.task_id || "" : item.id} disabled={!item.disponible}>
                    {item.caso ? `${item.caso.nombre} · ` : ""}{item.nombre}{item.receptor ? ` · ${item.receptor}` : ""}{item.task_id ? ` · ${item.task_id.slice(0, 8)}` : ""}
                  </option>)}
                </select>
                </>}
                {chosen && (sourceKind === "receptor" ? <InsigniaDelCatalogo pdbId={chosen.id} /> : <InsigniaDeCorridaGuardada pdbId={chosen.receptor} moleculeId={chosen.id} taskId={chosen.task_id} />)}
                {chosen?.task_id && <p className="mt-2 break-all font-mono text-[10px] text-[var(--text-dim)]">{t("cy_corrida")}: {chosen.task_id}</p>}
                {sourceKind === "moldex" && chosen && <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
                  {chosen.caso ? t("cy_case_output", { name: chosen.caso.nombre }) : t("cy_no_case_output")}
                </p>}
                {chosen?.motivo && <p className="mt-2 text-xs text-[var(--text-muted)]">{chosen.motivo}</p>}
                {loading && <p className="mt-3 text-xs text-[var(--text-muted)]">{t("cy_cargando")}</p>}
                {!loading && candidates?.length === 0 && <p className="mt-3 text-xs text-[var(--text-muted)]">{t(sourceKind === "moldex" ? "cy_sin_moldex" : "cy_sin_receptores")}</p>}
                <p className="mt-4 text-xs leading-6 text-[var(--text-muted)]">{c.sourceDetail}</p>
              </div>
            </section>

            <section aria-labelledby="molcy-scenes-title">
              <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.scenes}</p>
              <h2 id="molcy-scenes-title" className="font-display text-xl font-bold">{c.scenesTitle}</h2>
              <div className="mt-4 space-y-2" role="group" aria-label={c.scenesTitle}>
                {(Object.keys(scenes) as SceneId[]).map((id) => {
                  const item = scenes[id];
                  const Icon = item.icon;
                  const active = scene === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      aria-pressed={active}
                      disabled={((id === "resultado" || id === "busqueda" || id === "ensamble") && sourceKind !== "moldex") || (id === "busqueda" && !chosen?.escenas_disponibles?.includes("busqueda")) || (id === "ensamble" && !chosen?.escenas_disponibles?.includes("ensamble")) || Boolean(chosen?.escenas_disponibles && !chosen.escenas_disponibles.includes(id))}
                      onClick={() => setScene(id)}
                      className={`flex w-full cursor-pointer items-start gap-3 border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-50 ${active ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)] bg-[var(--bg-card)] hover:border-[var(--border-light)] active:bg-[var(--bg-secondary)]"}`}
                    >
                      <Icon size={18} className="mt-0.5 shrink-0 text-[var(--accent-strong)]" />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2"><span className="text-sm font-bold">{item[locale].name}</span><span className="font-mono text-[10px] text-[var(--text-dim)]">{item.number}</span></span>
                        <span className="mt-1 block text-xs leading-5 text-[var(--text-muted)]">{item[locale].summary}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
              {scene === "ensamble" && <p className="mt-3 flex gap-2 text-xs leading-5 text-[var(--text-muted)]"><CircleHelp size={15} className="mt-0.5 shrink-0" />{c.ensembleNote}</p>}
              <p className="mt-3 text-base leading-6 text-[var(--text-muted)]">{scene === "busqueda" ? c.searchNote : t(scene === "resultado" ? "cy_resultado_solo" : sourceKind === "moldex" ? "cy_receptor_corrida" : "cy_receptor_solo")}</p>
              {!chosen?.escenas_disponibles?.includes("busqueda") && <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{t("cy_busqueda_falta")}</p>}
              {sourceKind === "moldex" && chosen && !chosen.escenas_disponibles?.includes("ensamble") && <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{t("cy_ensamble_falta")}</p>}
            </section>
          </aside>

          <section aria-labelledby="molcy-preview-title" className="min-w-0 border border-[var(--border)] bg-[var(--bg-card)]">
            <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
              <div className="flex items-center gap-2">{esSesionDeFotos ? <Camera size={16} className="text-[var(--accent-strong)]" /> : <MonitorPlay size={16} className="text-[var(--accent-strong)]" />}<h2 id="molcy-preview-title" className="font-mono text-xs font-bold tracking-[0.16em]">{esSesionDeFotos ? t("cy_photo_studio") : jobEstado === "completo" ? t("cy_completo") : liveFrame ? t("cy_live_title") : c.preview}</h2></div>
              {!esSesionDeFotos && jobEstado !== "completo" && !liveFrame && <span className="hidden font-mono text-[10px] text-[var(--text-dim)] sm:block">{c.previewHint}</span>}
            </div>
            {/* El estudio enseña otro trabajo mientras uno sigue en curso: el render no se detiene, y aquí se vuelve a él. */}
            {enCurso && enCurso.id !== jobId && <div role="status" data-testid="molcy-en-curso"
              className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--accent-strong)] bg-[var(--bg-secondary)] px-5 py-3 text-xs leading-5">
              <p className="min-w-0">
                {t(enCurso.tipo === "fotos" ? "cy_en_curso_fotos" : "cy_en_curso_video")}
                {enCurso.progreso && enCurso.tipo !== "fotos" && <span className="ml-1 font-mono text-[var(--text-secondary)]">
                  {t("cy_progress", { done: enCurso.progreso.fotogramas, total: enCurso.progreso.total })}</span>}
              </p>
              <button type="button" onClick={() => verTrabajo(enCurso)}
                className="inline-flex min-h-9 shrink-0 items-center gap-2 border border-[var(--accent-strong)] px-3 font-semibold text-[var(--accent-strong)] hover:bg-[var(--bg-card)]">
                <ArrowLeft size={14} aria-hidden="true" />{t(enCurso.tipo === "fotos" ? "cy_en_curso_volver_fotos" : "cy_en_curso_volver_video")}
              </button>
            </div>}
            {esSesionDeFotos && job ? <PhotoStudio job={job} renderer={renderer} device={device}
              cpuThreads={renderer?.cpu_hilos_configurables ? cpuThreads : undefined} onJob={next => setJob(current => current?.id === next.id ? next : current)} /> : <>
            {jobEstado === "completo" && <section aria-label={t("cy_video_origin")} className="border-b border-[var(--border)] px-5 py-4 text-xs leading-5">
              <h3 className="font-semibold">{t("cy_video_origin")}</h3>
              {job?.fuente?.origen === "moldex" && job.fuente.task_id ? <>
                <p className="mt-2">{t("cy_video_run")}<span className="block break-all font-mono">{job.fuente.task_id}</span></p>
                <p className="mt-2">{t("cy_video_molecule")}<span className="block break-all font-mono">{job.fuente.molecule_id || job.fuente.id || t("cy_video_origin_missing")}</span></p>
              </> : job?.fuente?.origen === "receptor" && job.fuente.id ?
                <p className="mt-2">{t("cy_video_receptor")}<span className="block break-all font-mono">{job.fuente.id}</span></p> :
                <p className="mt-2">{t("cy_video_origin_missing")}</p>}
              <p className="mt-2 text-[var(--text-secondary)]">{t("cy_video_draft_separate")}</p>
            </section>}
            <div className="flex min-h-[440px] items-center justify-center overflow-hidden bg-[var(--bg-alt)] px-6 py-8">
              {videoPlaybackError && jobEstado === "completo" ?
                <div className="max-w-sm text-center text-sm leading-6 text-[var(--text-secondary)]">
                  <p role="status">{t("cy_reproduccion_bloqueada")}</p>
                  <button type="button" onClick={() => { setVideoUrl(null); setVideoPlaybackError(false); setVideoAttempt(value => value + 1); }}
                    className="mt-3 border border-[var(--border)] px-3 py-2">{t("cy_retry_video")}</button>
                </div> :
               videoUrl ? <video src={videoUrl} controls playsInline onError={() => setVideoPlaybackError(true)}
                 className="max-h-[560px] max-w-full" aria-label={t("cy_completo")} /> :
              liveFrame ? <figure className="flex max-w-full flex-col items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element -- blob local del render en curso */}
                <img src={liveFrame.url} alt={t("cy_live_alt")} className="max-h-[480px] max-w-full border border-[var(--border-light)]" />
                <figcaption className="max-w-sm text-center text-xs leading-5 text-[var(--text-secondary)]">
                  <span className="block font-mono">{pieEnVivo && t(pieEnVivo.clave, pieEnVivo.valores)}</span>
                  <span className="mt-1 block">{t("cy_live_note")}</span>
                </figcaption>
              </figure> :
              <div className={`relative flex max-h-[480px] w-full flex-col overflow-hidden border border-[var(--border-light)] bg-[var(--bg-secondary)] transition-[aspect-ratio] duration-300 ${format === "vertical" ? "aspect-[9/16] max-w-[270px]" : format === "previsualizacion" ? "aspect-square max-w-[400px]" : "aspect-video max-w-[470px]"}`}>
                <div className="absolute inset-0 opacity-50" style={{ backgroundImage: "radial-gradient(var(--border-light) 0.7px, transparent 0.7px)", backgroundSize: "22px 22px" }} />
                <div className="relative z-10 flex items-start justify-between p-4 font-mono text-[10px] uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  <span>Molcy / {scenes[scene].number}</span><span>{format === "vertical" ? "9:16" : format === "previsualizacion" ? "1:1" : "16:9"}</span>
                </div>
                <div className="relative z-10 flex flex-1 items-center justify-center p-5">
                  <div className="relative flex size-44 max-w-full items-center justify-center rounded-full border border-[var(--border-light)] sm:size-52">
                    <div className="absolute inset-5 rounded-full border border-dashed border-[var(--border-light)]" />
                    <div className="absolute inset-12 rounded-full border border-[var(--accent)] opacity-70" />
                    <Aperture size={32} strokeWidth={1} className="text-[var(--accent-strong)]" aria-hidden="true" />
                  </div>
                </div>
                <div className="relative z-10 border-t border-[var(--border)] bg-[var(--bg-card)] p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--accent-strong)]">{c.playback}</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{c.previewEmpty}</p>
                </div>
              </div>}
            </div>
            {(jobEstado === "en_cola" || jobEstado === "renderizando") && <div className="flex items-center gap-3 border-t border-[var(--border)] px-5 py-4 text-[var(--text-dim)]">
              <progress value={job?.progreso?.fotogramas ?? 0} max={job?.progreso?.total || 100}
                aria-label={t("cy_progress", { done: job?.progreso?.fotogramas ?? 0, total: job?.progreso?.total ?? 0 })}
                className="h-2 flex-1 accent-[var(--accent)]" />
            </div>}
            <div className="border-t border-[var(--border)] p-5">
              <p className="mb-4 font-mono text-[10px] tracking-[0.18em] text-[var(--text-dim)]">{c.storyboard}</p>
              <ol className="grid gap-2 sm:grid-cols-3">
                {selected.phase.map((phase, index) => <li key={phase} className="min-w-0 border-l-2 border-[var(--accent)] bg-[var(--bg-secondary)] px-3 py-3"><span className="font-mono text-[10px] text-[var(--text-dim)]">0{index + 1}</span><p className="mt-1 text-xs font-semibold leading-5">{phase}</p></li>)}
              </ol>
            </div>
            </>}
            {/* Debajo del guion visual, donde se ve: sin Blender y Molecular Nodes no hay vídeo ni fotos (pedido del propietario, 2026-10-12). */}
            {faltaPaquete && <div className="border-t border-[var(--border)] p-5" data-testid="molcy-paquete-estudio">
              <PaqueteMolcyCard contexto="estudio" onListo={usarRenderizador} onInstalando={setPaqueteInstalando} />
            </div>}
          </section>

          <aside className="space-y-7">
            <section aria-labelledby="molcy-output-title">
              <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.output}</p>
              <h2 id="molcy-output-title" className="font-display text-xl font-bold">{c.outputTitle}</h2>
              <div className="mt-4 grid grid-cols-2 gap-2" role="group" aria-label={t("cy_mode_title")}>
                {(["video", "foto"] as ModeId[]).map(id => <button key={id} type="button" aria-pressed={mode === id} onClick={() => setMode(id)}
                  className={`flex items-center gap-2 border px-3 py-3 text-left text-xs font-semibold ${mode === id ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)]"}`}>
                  {id === "video" ? <Film size={16} className="text-[var(--accent-strong)]" /> : <Camera size={16} className="text-[var(--accent-strong)]" />}
                  <span><span className="block">{t(id === "video" ? "cy_mode_video" : "cy_mode_photo")}</span>
                    <span className="mt-0.5 block font-mono text-[10px] font-normal text-[var(--text-dim)]">{t(id === "video" ? "cy_mode_video_hint" : "cy_mode_photo_hint")}</span></span>
                </button>)}
              </div>
              {mode === "video" && <>
              <div className="mt-4 grid grid-cols-3 gap-2" role="group" aria-label={c.outputTitle}>
                {(["vertical", "horizontal", "previsualizacion"] as FormatId[]).map((id) => <button key={id} type="button" aria-pressed={format === id} onClick={() => setFormat(id)} className={`cursor-pointer border px-3 py-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${format === id ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)] hover:border-[var(--border-light)] active:bg-[var(--bg-secondary)]"}`}>{id === "vertical" ? <Smartphone size={16} className="mb-3 text-[var(--accent-strong)]" /> : <Monitor size={16} className="mb-3 text-[var(--accent-strong)]" />}<span className="block text-xs font-bold">{id === "previsualizacion" ? t("cy_preview_short") : c[id]}</span><span className="mt-1 block font-mono text-[10px] text-[var(--text-dim)]">{id === "vertical" ? "9:16" : id === "horizontal" ? "16:9" : "1:1"}</span></button>)}
              </div>
              <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]">{c.formatHint}</p>
              <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]" data-testid="aviso-cierre">{t("cy_outro_note")}</p>
              <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">{t("cy_video_gpu_only")}</p>
              {canGpu && renderer && <GpuControls />}
              {renderer?.disponible && !canGpu && <div className="mt-3 border border-amber-400/50 p-3 text-xs leading-5" data-testid="video-sin-gpu">
                <p>{renderer.motivo_gpu || t("cy_video_needs_gpu")}</p>
                {renderer.foto_disponible && <button type="button" onClick={() => setMode("foto")}
                  className="mt-2 border border-[var(--accent-strong)] px-3 py-2 font-semibold text-[var(--accent-strong)]">{t("cy_switch_to_photos")}</button>}
              </div>}
              </>}
              {mode === "foto" && <>
              <h3 className="mt-6 text-sm font-bold">{t("cy_photo_orientation")}</h3>
              <div className="mt-3 grid grid-cols-2 gap-2" role="group" aria-label={t("cy_photo_orientation")}>
                {(["vertical", "horizontal"] as MolcyOrientacion[]).map(id => <button key={id} type="button" aria-pressed={orientacion === id}
                  onClick={() => setOrientacion(id)}
                  className={`border px-3 py-4 text-left ${orientacion === id ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)]"}`}>
                  {id === "vertical" ? <Smartphone size={16} className="mb-3 text-[var(--accent-strong)]" /> : <Monitor size={16} className="mb-3 text-[var(--accent-strong)]" />}
                  <span className="block text-xs font-bold">{c[id]}</span>
                  <span className="mt-1 block font-mono text-[10px] text-[var(--text-dim)]">{id === "vertical" ? "9:16" : "16:9"}</span>
                </button>)}
              </div>
              <h3 className="mt-6 text-sm font-bold">{t("cy_device_title")}</h3>
              <div className="mt-3 grid grid-cols-2 gap-2" role="group" aria-label={t("cy_device_title")}>
                {(["gpu", "cpu"] as const).map((id) => <button key={id} type="button" aria-pressed={device === id}
                  disabled={id === "gpu" ? !canPhotoGpu : !renderer?.foto_disponible}
                  onClick={() => setDevice(id)}
                  className={`border px-3 py-3 text-left text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${device === id ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)]"}`}>
                  {t(id === "gpu" ? "cy_photo_device_gpu" : "cy_photo_device_cpu")}
                  {id === "gpu" && canPhotoGpu && renderer?.foto_gpu_nombres?.[0] && <span className="mt-1 block font-mono text-[10px] font-normal text-[var(--text-dim)]">{renderer.foto_gpu_nombres[0]}</span>}
                  {id === "gpu" && canPhotoGpu && <span className="mt-1 block font-mono text-[10px] text-[var(--accent-strong)]">{t("cy_device_recommended")}</span>}
                </button>)}
              </div>
              <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">{t("cy_photo_same_result")}</p>
              {device === "cpu" && renderer?.foto_disponible && renderer.cpu_hilos_configurables && <CpuControls
                renderer={renderer} threads={cpuThreads} onThreads={setSelectedThreads} busy={busy} />}
              {device === "cpu" && resourcesError && <p role="alert" className="mt-3 text-base leading-6 text-amber-300">{t("cy_resources_error")}</p>}
              {device === "cpu" && renderer?.foto_disponible && !renderer.cpu_hilos_configurables && <p className="mt-2 text-xs text-[var(--text-muted)]">{t("cy_cpu_threads_update")}</p>}
              {renderer?.disponible && !canPhotoGpu && <p className="mt-2 text-xs text-[var(--text-muted)]">{renderer.motivo_foto_gpu || t("cy_photo_gpu_missing")}</p>}
              {renderer?.disponible && !renderer.foto_disponible && <p className="mt-2 text-xs text-[var(--text-muted)]">{renderer.motivo_foto || t("cy_photo_unavailable")}</p>}
              <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]" data-testid="aviso-marca">{t("cy_photo_mark_note")}</p>
              {sameSession && <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">{t("cy_photo_same_session")}</p>}
              </>}
              <PresentationControls value={presentacion} onChange={setPresentacion} scene={scene} disabled={busy} ensembleVariant={ensembleVariant} onEnsembleVariant={setEnsembleVariant} />
            </section>
            <section className="border-t border-[var(--border)] pt-6">
              <div className="flex items-center gap-2"><Check size={17} className="text-[var(--categoria-hallazgo)]" /><h2 className="text-sm font-bold">{c.evidence}</h2></div>
              <p className="mt-3 text-xs leading-6 text-[var(--text-muted)]">{c.evidenceText}</p>
            </section>
            <section className="border-t border-[var(--border)] pt-6">
              {salida && <OutputFolder salida={salida} esteVideo={esteVideo} onEsteVideo={setEsteVideo} onSalida={setSalida}
                disabled={Boolean(submitting || historyBusy || jobEstado === "en_cola" || jobEstado === "renderizando")} />}
              <button type="button" disabled={!canGenerate} onClick={generate} aria-describedby="molcy-disabled" className="mt-4 flex w-full cursor-pointer items-center justify-between bg-[var(--accent-strong)] px-4 py-4 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-[var(--border)] disabled:text-[var(--text-muted)] disabled:opacity-70"><span className="flex items-center gap-2">{mode === "video" ? <WandSparkles size={17} /> : <Camera size={17} />}{mode === "video" ? c.generate : c.preparePhotos}</span><ArrowRight size={16} /></button>
              <p id="molcy-disabled" className="mt-3 text-xs leading-5 text-[var(--text-dim)]">{renderer?.disponible ? (diskBudget?.disponible ? t("cy_renderer_ok") : t("cy_renderer_space_blocked")) : faltaPaquete ? t("cy_pack_needed_short") : `${t("cy_renderer_falta")}: ${renderer?.motivo || c.disabled}`}</p>
              <RendererSettings renderer={renderer} onChanged={refreshRenderer}
                busy={Boolean(submitting || historyBusy || paqueteInstalando || jobEstado === "en_cola" || jobEstado === "renderizando")} />
              {renderer?.disponible && !diskBudget?.disponible && <p role="alert" className="mt-3 text-xs text-red-400">{diskBudget?.motivo || (!diskBudget && renderer?.espacio_motivo) || (diskBudget ? t("cy_space_low", { free: (diskBudget.libre_bytes / 2**30).toFixed(1), required: (diskBudget.necesario_bytes / 2**30).toFixed(1) }) : t("cy_space_unknown"))}</p>}
              {error && <p role="alert" className="mt-3 text-xs text-red-400">{error}</p>}
              {job && <div className="mt-4 border border-[var(--border)] p-3 text-xs">
                <p className="font-semibold">{esSesionDeFotos ? t(job.estado === "completo" ? "cy_photo_state_ready"
                  : job.fase === "foto" ? "cy_photo_state_taking" : job.fase === "vista" ? "cy_photo_state_previewing"
                  : job.estado === "en_cola" || job.estado === "renderizando" ? "cy_photo_state_preparing" : `cy_${job.estado}`) : t(`cy_${job.estado}`)}</p>
                {job.dispositivo === "cpu" && job.cpu_hilos != null && <p className="mt-1">{t("cy_cpu_job_threads", { count: job.cpu_hilos })}</p>}
                {["en_cola", "renderizando"].includes(job.estado) && <button type="button"
                  onClick={() => cancelarMolcy(job.id).then(next => setJob(current => current?.id === next.id ? next : current)).catch((e: Error) => setError(presentError(e, t)))}
                  className="mt-2 border border-[var(--border)] px-3 py-2">{t("cy_cancel_render")}</button>}
                {job.estado === "completo" && <DownloadButton
                  onDownload={() => descargarProcedenciaMolcy(job.id)} onError={e => setError(presentError(e, t))}
                  className="mt-2 border border-[var(--border)] px-3 py-2">{t("cy_provenance")}</DownloadButton>}
                {job.estado === "renderizando" && !esSesionDeFotos && <p role="status" className="mt-2">
                  {job.progreso ? t("cy_progress", { done: job.progreso.fotogramas, total: job.progreso.total }) : t("cy_eta_calibrating")}
                  {job.progreso && job.restante_render_principal_s != null && <span className="mt-1 block">{t("cy_eta_main", { minutes: Math.max(1, Math.ceil(job.restante_render_principal_s / 60)) })}</span>}
                  {job.progreso && job.restante_render_principal_s == null && <span className="mt-1 block">{t(job.progreso.fotogramas >= job.progreso.total ? "cy_finalizing" : "cy_eta_calibrating")}</span>}
                </p>}
                {job.motivo && <p role="alert" className="mt-2">{job.motivo}</p>}
                {job.estado === "completo" && !esSesionDeFotos && <DownloadButton onDownload={() => descargarMolcy(job.id)} onError={e => setError(presentError(e, t))} className="mt-3 border border-[var(--accent-strong)] px-3 py-2 font-semibold">{t("cy_descargar")}</DownloadButton>}
                {job.video_sha256 && <p className="mt-3 break-all font-mono text-[10px]">{t("cy_hash")}: {job.video_sha256}</p>}
              </div>}
              <p className="mt-5 border-t border-[var(--border)] pt-4 font-mono text-[10px] uppercase tracking-[0.11em] text-[var(--text-dim)]">{c.noBackend}</p>
            </section>
          </aside>
        </div>
        <JobHistory userId={userId} current={job} onActive={setHistoryBusy} onEnCurso={setEnCurso} onSelect={verTrabajo}
          onRemoved={id => { if (id === jobId) { setJob(null); setVideoUrl(null); } }} />
      </div>
      {showUpload && <CustomReceptorModal onClose={() => setShowUpload(false)} onSuccess={() => {
        setShowUpload(false);
        fuentesMolcy().then(setSources).catch((e: Error) => setError(presentError(e, t)));
      }} />}
    </main>
  );
}
