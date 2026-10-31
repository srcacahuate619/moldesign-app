"use client";

import { presentError } from "../../lib/frontendError";

import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, FolderOpen, ImageIcon, ScanSearch } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { DownloadButton } from "./DownloadButton";
import {
  RESOLUCIONES_FOTO, descargarFotoMolcy, estimacionFotoMolcy, imagenMolcy, revelarMolcy, tomarFotoMolcy, vistaMolcy,
  type MolcyFotoEstimate, type MolcyJob, type MolcyMomento, type MolcyOrientacion, type MolcyRenderer, type MolcyResolucion,
} from "@/lib/molcy";

/** Lado corto de cada resolución: de 720p (el piso) a 4K (el techo). Se espeja del backend (`services/molcy/fotos.py`). */
const LADO_CORTO: Record<MolcyResolucion, number> = { "720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160 };
/** Las fotos se entregan a 300 ppp. */
const PPP = 300;

export function dimensionesFoto(orientacion: MolcyOrientacion, resolucion: MolcyResolucion): [number, number] {
  const corto = LADO_CORTO[resolucion];
  const largo = Math.floor(corto * 16 / 9);
  return orientacion === "horizontal" ? [largo, corto] : [corto, largo];
}

/** Tamaño impreso a 300 ppp, en centímetros con un decimal: 4K → 32,5 × 18,3 cm. */
export function tamanoImpreso(ancho: number, alto: number, locale: "es" | "en"): string {
  const cm = (px: number) => (px / PPP * 2.54).toLocaleString(locale === "en" ? "en-US" : "es-MX", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  return `${cm(ancho)} × ${cm(alto)} cm`;
}

/** «25 s», «1 min 35 s», «13 min»: lo mismo en español y en inglés (unidades del SI). */
export function duracion(segundos: number): string {
  const s = Math.max(1, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const min = Math.floor(s / 60);
  const resto = s % 60;
  return min >= 10 || resto === 0 ? `${Math.round(s / 60)} min` : `${min} min ${resto} s`;
}

/** Clave de traducción y valores del nombre de un momento: sale de lo que el motor dice que es, no de un número de fotograma. */
export function etiquetaMomento(m: Pick<MolcyMomento, "tipo" | "beat" | "pose">): [string, Record<string, string | number>?] {
  if (m.tipo === "titulo") return ["cy_moment_titulo"];
  if (m.tipo === "imagen_fija") return ["cy_moment_sitio"];
  if (m.tipo === "lectura") {
    if (m.pose != null) return ["cy_moment_pose", { pose: m.pose }];
    if (m.beat === "pausa_hotspots") return ["cy_moment_hotspots"];
    if (m.beat === "sitio") return ["cy_moment_sitio_rotulado"];
    if (m.beat?.startsWith("llegada")) return ["cy_moment_interacciones"];
    return ["cy_moment_lectura"];
  }
  const recorridos: Record<string, string> = {
    exploracion: "cy_moment_vuelta", busqueda: "cy_moment_busqueda", salida: "cy_moment_salida",
    conformeros: "cy_moment_conformeros", corridas: "cy_moment_corridas", general: "cy_moment_general",
    convergencia: "cy_moment_convergencia", validacion: "cy_moment_validacion",
  };
  return [recorridos[m.beat || ""] || "cy_moment_recorrido"];
}

type Props = {
  job: MolcyJob;
  renderer: MolcyRenderer | null;
  /** Dispositivo y, con CPU, los hilos con que se tomarán las fotos: los de la columna de salida. */
  device: "cpu" | "gpu";
  cpuThreads?: number;
  onJob: (next: MolcyJob) => void;
};

export function PhotoStudio({ job, renderer, device, cpuThreads, onJob }: Props) {
  const { t, locale } = useLanguage();
  const momentos = useMemo(() => [...(job.momentos || [])].sort((a, b) => a.fotograma - b.fotograma), [job.momentos]);
  const total = job.escena_fotos?.fotogramas_fuente || 0;
  const orientacion: MolcyOrientacion = job.orientacion || "vertical";
  const preparando = job.estado === "en_cola" || (job.estado === "renderizando" && job.fase === "preparando");
  const ocupado = job.estado === "en_cola" || job.estado === "renderizando";
  const lista = job.estado === "completo" && total > 0;
  const preferido = momentos.find(m => m.tipo === "lectura" && m.etiquetas > 0) || momentos[0];
  const [elegido, setElegido] = useState<{ fotograma: number; libre: boolean } | null>(null);
  const [libre, setLibre] = useState(1);
  const [resolucion, setResolucion] = useState<MolcyResolucion>("1080p");
  const [miniaturas, setMiniaturas] = useState<Record<string, string>>({});
  const [vista, setVista] = useState<{ fotograma: number; url: string } | null>(null);
  const [fotoVista, setFotoVista] = useState<{ id: string; url: string } | null>(null);
  const [estimacion, setEstimacion] = useState<MolcyFotoEstimate | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const urls = useRef<Set<string>>(new Set());

  const seleccion = elegido ?? (preferido ? { fotograma: preferido.fotograma, libre: false } : null);
  const momentoElegido = seleccion && !seleccion.libre ? momentos.find(m => m.fotograma === seleccion.fotograma) : undefined;

  // Las URL de blob son de esta sesión: se liberan al cambiar de sesión o al salir.
  useEffect(() => {
    const vivas = urls.current;
    return () => { vivas.forEach(url => URL.revokeObjectURL(url)); vivas.clear(); };
  }, [job.id]);
  useEffect(() => { setElegido(null); setVista(null); setFotoVista(null); setMiniaturas({}); setError(null); }, [job.id]);
  useEffect(() => { if (total) setLibre(value => Math.min(Math.max(1, value), total)); }, [total]);

  const momentosClave = momentos.map(m => m.fotograma).join(",");
  useEffect(() => {
    if (!lista || !momentosClave) return;
    const controller = new AbortController();
    for (const f of momentosClave.split(",")) {
      imagenMolcy(job.id, "tomas", f, controller.signal).then(({ url }) => {
        if (controller.signal.aborted) { URL.revokeObjectURL(url); return; }
        urls.current.add(url);
        setMiniaturas(previas => ({ ...previas, [f]: url }));
      }).catch(() => { /* una miniatura que no carga deja su hueco con el nombre */ });
    }
    return () => controller.abort();
  }, [job.id, lista, momentosClave]);

  // La vista libre del fotograma elegido, cuando el backend la tiene.
  const vistaLista = seleccion?.libre && job.vistas?.[String(seleccion.fotograma)] ? seleccion.fotograma : null;
  const vistaSha = vistaLista ? job.vistas?.[String(vistaLista)]?.sha256 : undefined;
  useEffect(() => {
    if (!vistaLista) return;
    const controller = new AbortController();
    imagenMolcy(job.id, "vistas", vistaLista, controller.signal).then(({ url }) => {
      if (controller.signal.aborted) { URL.revokeObjectURL(url); return; }
      urls.current.add(url);
      setVista({ fotograma: vistaLista, url });
    }).catch(() => setVista(null));
    return () => controller.abort();
  }, [job.id, vistaLista, vistaSha]);

  const [ancho, alto] = dimensionesFoto(orientacion, resolucion);
  const espacio = renderer?.espacio_fotos?.[resolucion];
  const hilos = device === "cpu" && renderer?.cpu_hilos_configurables ? cpuThreads : undefined;
  useEffect(() => {
    if (!lista) return;
    const controller = new AbortController();
    setEstimacion(null);
    estimacionFotoMolcy({ orientacion, resolucion, dispositivo: device, ...(hilos ? { cpu_hilos: hilos } : {}) }, controller.signal)
      .then(value => { if (!controller.signal.aborted) setEstimacion(value); })
      .catch(() => { if (!controller.signal.aborted) setEstimacion(null); });
    return () => controller.abort();
  }, [lista, orientacion, resolucion, device, hilos, job.fotos?.length]);

  const fotos = job.fotos || [];
  const verFoto = async (id: string) => {
    setError(null);
    try {
      const { url } = await imagenMolcy(job.id, "fotos", id);
      urls.current.add(url);
      setFotoVista({ id, url });
    } catch (e) { setError(presentError((e as Error), t)); }
  };
  const ultimaFoto = fotos.length ? fotos[fotos.length - 1].id : null;
  const yaVista = useRef<string | null>(null);
  useEffect(() => {
    // Una foto recién entregada se enseña sola.
    if (ultimaFoto && yaVista.current !== null && yaVista.current !== ultimaFoto) void verFoto(ultimaFoto);
    yaVista.current = ultimaFoto ?? "";
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ultimaFoto]);

  const gpuNoVale = device === "gpu" && !renderer?.foto_gpu_disponible;
  const puedeTomar = Boolean(lista && seleccion && !ocupado && !enviando && !gpuNoVale && espacio?.disponible !== false);
  const pedir = async (operacion: "foto" | "vista") => {
    if (!seleccion && operacion === "foto") return;
    setError(null);
    setEnviando(true);
    try {
      const base = { dispositivo: device, ...(hilos ? { cpu_hilos: hilos } : {}) };
      const next = operacion === "foto"
        ? await tomarFotoMolcy(job.id, { ...base, fotograma: seleccion!.fotograma, resolucion })
        : await vistaMolcy(job.id, { ...base, fotograma: libre });
      if (operacion === "vista") setElegido({ fotograma: libre, libre: true });
      setFotoVista(null);
      onJob(next);
    } catch (e) { setError(presentError((e as Error), t)); }
    finally { setEnviando(false); }
  };

  const beatDe = (f: number) => Object.entries(job.escena_fotos?.beats || {}).find(([, [a, b]]) => a <= f && f <= b)?.[0];
  const nombre = (m: MolcyMomento) => { const [key, values] = etiquetaMomento(m); return t(key, values); };
  const imagenGrande = fotoVista?.url
    ?? (seleccion?.libre ? (vista?.fotograma === seleccion.fotograma ? vista.url : null) : (seleccion ? miniaturas[String(seleccion.fotograma)] : null));
  const operacion = job.operacion;
  const ultima = job.ultima_operacion;

  return <div className="flex flex-col">
    <div className="flex min-h-[440px] flex-col items-center justify-center gap-3 overflow-hidden bg-[var(--bg-alt)] px-6 py-8">
      {preparando ? <div role="status" aria-live="polite" className="max-w-sm text-center text-sm leading-6 text-[var(--text-secondary)]">
        <Camera size={28} className="mx-auto mb-3 animate-pulse text-[var(--accent-strong)]" aria-hidden="true" />
        <p className="font-semibold">{t("cy_photo_preparing")}</p>
        <p className="mt-2 text-xs text-[var(--text-muted)]">{t("cy_photo_preparing_note")}</p>
      </div> : imagenGrande ? <figure className="flex max-w-full flex-col items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- blob local de la sesión */}
        <img src={imagenGrande} alt={fotoVista ? t("cy_photo_delivered_alt", { id: fotoVista.id }) : t("cy_photo_preview_alt")}
          className="max-h-[480px] max-w-full border border-[var(--border-light)]" />
        <figcaption className="max-w-md text-center text-xs leading-5 text-[var(--text-secondary)]">
          {fotoVista ? t("cy_photo_delivered_caption", { id: fotoVista.id }) : <>
            <span className="block font-semibold">{momentoElegido ? nombre(momentoElegido) : t("cy_moment_libre")}</span>
            {seleccion && <span className="block font-mono">{t("cy_photo_frame", { frame: seleccion.fotograma, total })}</span>}
            <span className="mt-1 block text-[var(--text-muted)]">{t("cy_photo_preview_note")}</span>
          </>}
        </figcaption>
      </figure> : <div className="max-w-sm text-center text-sm leading-6 text-[var(--text-secondary)]">
        <ImageIcon size={28} className="mx-auto mb-3 text-[var(--accent-strong)]" aria-hidden="true" />
        <p>{job.estado === "fallido" ? (job.motivo || t("cy_fallido")) : job.estado === "cancelado" ? t("cy_cancelado")
          : seleccion?.libre ? t("cy_photo_free_pending") : t("cy_photo_pick")}</p>
      </div>}
    </div>

    {lista && <div className="space-y-6 border-t border-[var(--border)] p-5">
      <section aria-labelledby="molcy-tomas-title">
        <p className="mb-1 font-mono text-[10px] tracking-[0.18em] text-[var(--text-dim)]">{t("cy_photo_suggested_eyebrow")}</p>
        <h3 id="molcy-tomas-title" className="text-sm font-bold">{t("cy_photo_suggested")}</h3>
        <ul className={`mt-3 grid gap-2 ${orientacion === "vertical" ? "grid-cols-3 sm:grid-cols-4 lg:grid-cols-6" : "grid-cols-2 sm:grid-cols-3"}`}>
          {momentos.map(m => {
            const activo = Boolean(seleccion && !seleccion.libre && seleccion.fotograma === m.fotograma && !fotoVista);
            return <li key={m.id} className="min-w-0">
              <button type="button" aria-pressed={activo} onClick={() => { setElegido({ fotograma: m.fotograma, libre: false }); setFotoVista(null); }}
                className={`flex w-full cursor-pointer flex-col gap-1 border p-1 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${activo ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)] hover:border-[var(--border-light)]"}`}>
                <span className={`block w-full overflow-hidden bg-[var(--bg-alt)] ${orientacion === "vertical" ? "aspect-[9/16]" : "aspect-video"}`}>
                  {miniaturas[String(m.fotograma)] &&
                    // eslint-disable-next-line @next/next/no-img-element -- miniatura local de la sesión
                    <img src={miniaturas[String(m.fotograma)]} alt="" className="h-full w-full object-cover" />}
                </span>
                <span className="block text-[11px] font-semibold leading-4">{nombre(m)}</span>
                <span className="block font-mono text-[10px] text-[var(--text-dim)]">{t("cy_photo_frame_short", { frame: m.fotograma })}</span>
              </button>
            </li>;
          })}
        </ul>
      </section>

      <details className="border border-[var(--border)] p-3" open={Boolean(seleccion?.libre)}>
        <summary className="cursor-pointer text-sm font-bold"><ScanSearch size={15} className="mr-2 inline" aria-hidden="true" />{t("cy_photo_free")}</summary>
        <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">{t("cy_photo_free_help")}</p>
        <label htmlFor="molcy-foto-libre" className="mt-3 block text-xs font-semibold">
          {t("cy_photo_frame", { frame: libre, total })}{beatDe(libre) ? ` · ${t(`cy_beat_${beatDe(libre)}`)}` : ""}
        </label>
        <input id="molcy-foto-libre" type="range" min={1} max={total} step={1} value={libre}
          onChange={event => setLibre(Number(event.target.value))} disabled={ocupado}
          className="min-h-11 w-full cursor-pointer accent-[var(--accent-strong)]" />
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => pedir("vista")} disabled={ocupado || enviando || gpuNoVale}
            className="min-h-11 border border-[var(--accent-strong)] px-3 text-xs font-semibold text-[var(--accent-strong)] disabled:opacity-50">
            {t("cy_photo_free_preview")}</button>
          {job.vistas?.[String(libre)] && <button type="button" onClick={() => { setElegido({ fotograma: libre, libre: true }); setFotoVista(null); }}
            className="min-h-11 border border-[var(--border)] px-3 text-xs">{t("cy_photo_free_use")}</button>}
        </div>
      </details>

      <section aria-labelledby="molcy-resolucion-title">
        <h3 id="molcy-resolucion-title" className="text-sm font-bold">{t("cy_photo_resolution")}</h3>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label={t("cy_photo_resolution")}>
          {RESOLUCIONES_FOTO.map(r => {
            const [w, h] = dimensionesFoto(orientacion, r);
            return <button key={r} type="button" aria-pressed={resolucion === r} onClick={() => setResolucion(r)}
              className={`border px-3 py-3 text-left text-xs ${resolucion === r ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)]"}`}>
              <span className="block font-bold">{t(`cy_photo_res_${r}`)}</span>
              <span className="mt-1 block font-mono text-[10px] text-[var(--text-dim)]">{w} × {h}</span>
              <span className="block text-[10px] text-[var(--text-muted)]">{t("cy_photo_print", { size: tamanoImpreso(w, h, locale) })}</span>
            </button>;
          })}
        </div>
        <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]" role="status">
          {estimacion?.estimado_s != null
            ? t("cy_photo_estimate", { time: duracion(estimacion.estimado_s), count: estimacion.muestras })
            : t("cy_photo_estimate_first")}
        </p>
        {gpuNoVale && <p className="mt-2 text-xs text-amber-300">{renderer?.motivo_foto_gpu || t("cy_photo_gpu_missing")}</p>}
        {espacio?.disponible === false && <p role="alert" className="mt-2 text-xs text-red-400">
          {t("cy_space_low", { free: (espacio.libre_bytes / 2 ** 30).toFixed(1), required: (espacio.necesario_bytes / 2 ** 30).toFixed(1) })}</p>}
        <button type="button" onClick={() => pedir("foto")} disabled={!puedeTomar}
          className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 bg-[var(--accent-strong)] px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-[var(--border)] disabled:text-[var(--text-muted)]">
          <Camera size={16} aria-hidden="true" />{t("cy_photo_take", { width: ancho, height: alto })}
        </button>
        <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">{t("cy_photo_mark_note")}</p>
      </section>
    </div>}

    {(operacion || ultima) && <div className="border-t border-[var(--border)] px-5 py-4 text-xs leading-5">
      {operacion && job.estado === "renderizando" && <p role="status" aria-live="polite">
        {t(operacion.tipo === "foto" ? "cy_photo_rendering" : "cy_photo_previewing",
          { frame: operacion.fotograma, width: operacion.ancho, height: operacion.alto, device: operacion.dispositivo.toUpperCase() })}
        {operacion.tipo === "foto" && operacion.dispositivo === "cpu" && operacion.resolucion === "4k" &&
          <span className="mt-1 block text-[var(--text-muted)]">{t("cy_photo_slow_cpu_4k")}</span>}
      </p>}
      {!operacion && ultima && ultima.estado !== "completo" &&
        <p role="alert" className="text-amber-300">{ultima.estado === "cancelado" ? t("cy_photo_cancelled") : (ultima.motivo || t("cy_photo_failed"))}</p>}
    </div>}

    {fotos.length > 0 && <section aria-labelledby="molcy-fotos-title" className="border-t border-[var(--border)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="molcy-fotos-title" className="text-sm font-bold">{t("cy_photo_taken", { count: fotos.length })}</h3>
        <button type="button" onClick={() => revelarMolcy(job.id).catch((e: Error) => setError(presentError(e, t)))}
          className="inline-flex min-h-11 items-center gap-2 border border-[var(--border-light)] px-3 text-xs font-semibold">
          <FolderOpen size={14} aria-hidden="true" />{t("cy_photo_reveal")}</button>
      </div>
      <ul className="mt-3 space-y-2">
        {[...fotos].reverse().map(f => <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] px-3 py-2 text-xs">
          <span className="min-w-0">
            <span className="block font-semibold">{t("cy_photo_item", { id: f.id, width: f.ancho, height: f.alto, frame: f.fotograma })}</span>
            <span className="block text-[var(--text-muted)]">
              {t("cy_photo_item_render", { device: f.dispositivo.toUpperCase() })}{f.segundos?.total ? ` · ${duracion(f.segundos.total)}` : ""}
            </span>
          </span>
          <span className="flex gap-2">
            <button type="button" onClick={() => verFoto(f.id)} aria-pressed={fotoVista?.id === f.id}
              className="min-h-11 border border-[var(--border)] px-3">{t("cy_photo_view")}</button>
            <DownloadButton onDownload={() => descargarFotoMolcy(job.id, f.id)} onError={e => setError(presentError(e, t))}
              className="border border-[var(--accent-strong)] px-3 font-semibold text-[var(--accent-strong)]">
              {t("cy_photo_download")}</DownloadButton>
          </span>
        </li>)}
      </ul>
    </section>}
    {error && <p role="alert" className="border-t border-[var(--border)] px-5 py-3 text-xs text-red-400">{error}</p>}
  </div>;
}
