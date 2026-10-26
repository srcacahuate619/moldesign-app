"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, FolderOpen, MonitorPlay, Play, X } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { useKeepAliveActive } from "@/context/KeepAliveContext";
import { eliminarMolcy, revelarMolcy, trabajosMolcy, videoMolcy, type MolcyJob } from "@/lib/molcy";

const HISTORY_PAGE_SIZE = 9;

export function JobHistory({ userId, current, onSelect, onRemoved, onActive, onEnCurso }: {
  userId?: string;
  current: MolcyJob | null;
  onSelect: (value: MolcyJob) => void;
  onRemoved: (id: string) => void;
  onActive?: (active: boolean) => void;
  /** El trabajo que se está renderizando o preparando ahora (el más reciente), o null: la página ofrece volver a él. */
  onEnCurso?: (job: MolcyJob | null) => void;
}) {
  const { t, locale } = useLanguage();
  // Con Molcy oculta (keep-alive) no se pregunta cada 5 s; al volver, se refresca enseguida.
  const activa = useKeepAliveActive();
  const [jobs, setJobs] = useState<MolcyJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [revealError, setRevealError] = useState<{ id: string; message: string } | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [revealing, setRevealing] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(HISTORY_PAGE_SIZE);
  const [preview, setPreview] = useState<MolcyJob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!userId || !activa) return;
    let alive = true;
    const refresh = () => trabajosMolcy().then(data => {
      if (alive) {
        setJobs(data.trabajos);
        setError(null);
        const enCurso = data.trabajos.find(value => ["en_cola", "renderizando"].includes(value.estado)) ?? null;
        onActive?.(enCurso !== null);
        onEnCurso?.(enCurso);
      }
    }).catch((e: Error) => { if (alive) setError(e.message); });
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [userId, activa, current?.id, current?.estado, onActive, onEnCurso]);

  useEffect(() => {
    const element = dialog.current;
    if (!preview) {
      if (element?.open) element.close();
      setPreviewUrl(null);
      return;
    }

    if (element && !element.open) element.showModal();
    let alive = true;
    setPreviewLoading(true);
    setPreviewError(false);
    setPreviewUrl(null);
    videoMolcy(preview.id).then(url => {
      if (alive) setPreviewUrl(url);
    }).catch(() => {
      if (alive) setPreviewError(true);
    }).finally(() => {
      if (alive) setPreviewLoading(false);
    });
    return () => { alive = false; };
  }, [preview]);

  const remove = async (id: string) => {
    setDeleting(true);
    setError(null);
    try {
      await eliminarMolcy(id);
      setJobs(list => list.filter(job => job.id !== id));
      onRemoved(id);
      setConfirm(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  const reveal = async (job: MolcyJob) => {
    setRevealing(job.id);
    setRevealError(null);
    try {
      await revelarMolcy(job.id);
    } catch (e) {
      setRevealError({ id: job.id, message: (e as Error).message });
    } finally {
      setRevealing(null);
    }
  };

  const fecha = (seconds?: number) => {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) return null;
    const language = locale === "en" ? "en-US" : "es-MX";
    return new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" })
      .format(new Date(seconds * 1000));
  };
  const visibleJobs = jobs.slice(0, visibleCount);

  return <>
    <section className="mt-8 border-t border-[var(--border)] pt-6" aria-labelledby="molcy-history-title">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">04 / {t("cy_history_eyebrow")}</p>
          <h2 id="molcy-history-title" className="font-display text-xl font-bold">{t("cy_history")}</h2>
          <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">{t("cy_history_intro")}</p>
        </div>
        <span className="border border-[var(--border)] px-3 py-2 font-mono text-xs text-[var(--text-secondary)]">
          {jobs.length.toString().padStart(2, "0")}
        </span>
      </div>

      {!jobs.length && <p className="border border-dashed border-[var(--border-light)] bg-[var(--bg-card)] px-4 py-5 text-sm text-[var(--text-muted)]">{t("cy_history_empty")}</p>}

      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleJobs.map((job, index) => {
          const receptorName = job.receptor?.nombre || job.fuente?.target_name || job.receptor?.pdb_id ||
            job.fuente?.pdb_id || t("cy_history_receptor_unknown");
          const pdbId = job.receptor?.pdb_id || job.fuente?.pdb_id ||
            (job.fuente?.origen === "receptor" ? job.fuente.id : undefined);
          const targetId = job.receptor?.target_id || job.fuente?.target_id;
          const isCurrent = current?.id === job.id;
          const created = fecha(job.creado_s);
          const finished = !["en_cola", "renderizando"].includes(job.estado);
          const fotos = job.tipo === "fotos";
          return <li key={job.id} className={`min-w-0 border bg-[var(--bg-card)] p-4 ${isCurrent ? "border-[var(--accent-strong)]" : "border-[var(--border)]"}`}>
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-semibold">
                  <button type="button" aria-pressed={isCurrent} onClick={() => onSelect(job)}
                    className="min-h-11 max-w-full cursor-pointer text-left leading-5 text-[var(--text)] underline decoration-[var(--border-light)] underline-offset-4 hover:decoration-[var(--accent-strong)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
                    {t(fotos ? "cy_history_photos" : "cy_history_job", { number: jobs.length - index })} · {fotos && job.estado === "completo"
                      ? t("cy_history_photos_count", { count: job.fotos?.length ?? 0 }) : t(`cy_${job.estado}`)}
                  </button>
                </h3>
                <p className="mt-1 text-[10px] uppercase tracking-[0.1em] text-[var(--text-muted)]">{t("cy_history_receptor")}</p>
                <p className="break-words text-sm text-[var(--text-secondary)]">{receptorName}</p>
              </div>
              <span className="shrink-0 border border-[var(--border)] px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                {t(job.fuente?.origen === "moldex" ? "cy_origen_moldex" : "cy_origen_receptor")}
              </span>
            </div>

            <dl className="mt-4 grid min-w-0 grid-cols-2 gap-x-4 gap-y-3 border-t border-[var(--border)] pt-3 text-xs">
              {job.fuente?.case_name && <div className="col-span-2 min-w-0">
                <dt className="text-[var(--text-muted)]">{t("cy_history_case")}</dt>
                <dd className="mt-1 break-words text-[var(--text-secondary)]">{job.fuente.case_name}</dd>
              </div>}
              <div className="min-w-0">
                <dt className="text-[var(--text-muted)]">{t("cy_history_pdb")}</dt>
                <dd className="mt-1 break-words font-mono text-[var(--text-secondary)]">{pdbId || "—"}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-[var(--text-muted)]">{t("cy_history_moldex_id")}</dt>
                <dd className="mt-1 break-words font-mono text-[var(--text-secondary)]">
                  {targetId || (job.fuente?.origen === "moldex" ? t("cy_history_moldex_id_missing") : "—")}
                </dd>
              </div>
              {job.receptor?.cadena && <div className="min-w-0">
                <dt className="text-[var(--text-muted)]">{t("cy_history_chain")}</dt>
                <dd className="mt-1 font-mono text-[var(--text-secondary)]">{job.receptor.cadena}</dd>
              </div>}
              {job.fuente?.task_id && <div className="col-span-2 min-w-0">
                <dt className="text-[var(--text-muted)]">{t("cy_history_run")}</dt>
                <dd className="mt-1 break-words font-mono text-[var(--text-secondary)]">{job.fuente.task_id}</dd>
              </div>}
              {created && <div className="col-span-2 min-w-0">
                <dt className="text-[var(--text-muted)]">{t("cy_history_saved_at")}</dt>
                <dd className="mt-1 text-[var(--text-secondary)]"><time dateTime={new Date((job.creado_s ?? 0) * 1000).toISOString()}>{created}</time></dd>
              </div>}
            </dl>

            <div className="mt-4 flex flex-wrap gap-2">
              {job.estado === "completo" && !fotos && <button type="button" onClick={() => setPreview(job)}
                className="inline-flex min-h-11 cursor-pointer items-center gap-2 border border-[var(--accent-strong)] px-3 text-sm font-semibold text-[var(--accent-strong)] transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
                <Play size={15} aria-hidden="true" />{t("cy_history_play")}
              </button>}
              {/* Un trabajo en curso que el estudio no está enseñando: sin esto, abrir otro trabajo dejaba el render sin
                  manera visible de volver a su progreso (propietario, 2026-10-12). */}
              {!finished && !isCurrent && <button type="button" onClick={() => onSelect(job)}
                className="inline-flex min-h-11 cursor-pointer items-center gap-2 border border-[var(--accent-strong)] px-3 text-sm font-semibold text-[var(--accent-strong)] transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
                <MonitorPlay size={15} aria-hidden="true" />{t("cy_history_view_in_studio")}
              </button>}
              {job.estado === "completo" && fotos && <button type="button" onClick={() => onSelect(job)}
                className="inline-flex min-h-11 cursor-pointer items-center gap-2 border border-[var(--accent-strong)] px-3 text-sm font-semibold text-[var(--accent-strong)] transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
                <Camera size={15} aria-hidden="true" />{t("cy_history_open_studio")}
              </button>}
              <button type="button" onClick={() => reveal(job)} disabled={revealing === job.id}
                className="inline-flex min-h-11 cursor-pointer items-center gap-2 border border-[var(--border-light)] px-3 text-sm font-semibold text-[var(--text)] transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-wait disabled:opacity-60">
                <FolderOpen size={15} aria-hidden="true" />{revealing === job.id ? t("cy_history_reveal_busy")
                  : t(fotos ? (job.fotos?.length ? "cy_history_reveal_photo" : "cy_history_reveal_folder")
                    : job.estado === "completo" ? "cy_history_reveal_video" : "cy_history_reveal_folder")}
              </button>
              {finished && <button type="button" disabled={deleting} onClick={() => setConfirm(job.id)}
                className="min-h-11 cursor-pointer border border-[var(--border)] px-3 text-sm text-[var(--text-secondary)] transition-colors hover:border-red-400/70 hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:opacity-60">
                {t(fotos ? "cy_delete_photos" : "cy_delete_job")}
              </button>}
            </div>

            {revealError?.id === job.id && revealing === null && <p role="alert" className="mt-2 break-words text-xs text-red-400">{revealError.message}</p>}
            {confirm === job.id && <div className="mt-3 border-t border-[var(--border)] pt-3 text-xs">
              <p>{t(fotos ? "cy_delete_photos_confirm" : "cy_delete_confirm")}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" disabled={deleting} onClick={() => remove(job.id)} className="min-h-11 border border-red-400/60 px-3 font-semibold text-red-300 disabled:opacity-60">{t(fotos ? "cy_delete_photos" : "cy_delete_job")}</button>
                <button type="button" disabled={deleting} onClick={() => setConfirm(null)} className="min-h-11 border border-[var(--border)] px-3">{t("cy_keep_job")}</button>
              </div>
            </div>}
          </li>;
        })}
      </ul>
      {(visibleCount < jobs.length || visibleCount > HISTORY_PAGE_SIZE) && <div className="mt-4 flex flex-wrap gap-2">
        {visibleCount < jobs.length && <button type="button" onClick={() => setVisibleCount(count => count + HISTORY_PAGE_SIZE)}
          className="min-h-11 border border-[var(--border-light)] px-4 text-sm font-semibold hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
          {t("cy_history_show_more", { count: Math.min(HISTORY_PAGE_SIZE, jobs.length - visibleCount) })}
        </button>}
        {visibleCount > HISTORY_PAGE_SIZE && <button type="button" onClick={() => setVisibleCount(HISTORY_PAGE_SIZE)}
          className="min-h-11 border border-[var(--border)] px-4 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
          {t("cy_history_show_less")}
        </button>}
      </div>}
      {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
    </section>

    <dialog ref={dialog} aria-labelledby="molcy-history-player-title" onClose={() => setPreview(null)}
      onClick={event => { if (event.target === event.currentTarget) event.currentTarget.close(); }}
      className="m-auto max-h-[92dvh] w-[min(94vw,1040px)] max-w-none overflow-hidden border border-[var(--border-light)] bg-[var(--bg-card)] p-0 text-[var(--text)] shadow-2xl backdrop:bg-black/80">
      {preview && <div className="flex max-h-[calc(92dvh-2px)] flex-col">
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-[var(--accent-strong)]">{t("cy_history")}</p>
            <h2 id="molcy-history-player-title" className="mt-1 break-words text-lg font-bold">
              {t("cy_history_preview_title", { receptor: preview.receptor?.nombre || preview.fuente?.target_name || preview.receptor?.pdb_id || preview.fuente?.pdb_id || t("cy_history_receptor_unknown") })}
            </h2>
          </div>
          <button type="button" onClick={() => dialog.current?.close()} aria-label={t("cy_history_close")}
            className="inline-flex min-h-11 min-w-11 shrink-0 cursor-pointer items-center justify-center border border-[var(--border)] hover:bg-[var(--bg-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]">
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto bg-black p-4 sm:p-6">
          {previewLoading && <p role="status" className="text-sm text-white/75">{t("cy_history_preview_loading")}</p>}
          {previewError && <p role="alert" className="max-w-md text-center text-sm leading-6 text-red-300">{t("cy_history_preview_error")}</p>}
          {previewUrl && !previewError && <video src={previewUrl} controls autoPlay playsInline preload="auto"
            onError={() => setPreviewError(true)} aria-label={t("cy_history_preview_title", { receptor: preview.receptor?.nombre || preview.receptor?.pdb_id || preview.fuente?.target_name || "Molcy" })}
            className="max-h-[calc(92dvh-110px)] max-w-full" />}
        </div>
      </div>}
    </dialog>
  </>;
}
