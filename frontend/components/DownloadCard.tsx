"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useDownload } from "../hooks/useDownload";
import type { ModuleEntry } from "../lib/types";

import { ExternalLink } from "@/components/ui/ExternalLink";
function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(2)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(0)} MB`;
  return `${(bytes / 1_000).toFixed(0)} KB`;
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec >= 1_000_000) return `${(bytesPerSec / 1_000_000).toFixed(1)} MB/s`;
  if (bytesPerSec >= 1_000) return `${(bytesPerSec / 1_000).toFixed(0)} KB/s`;
  return `${bytesPerSec.toFixed(0)} B/s`;
}

export function DownloadCard({ entry }: { entry: ModuleEntry }) {
  const { t } = useLanguage();
  const { models, progress, startDownload, cancelDownload } = useDownload();
  const status = models[entry.id] || "missing";
  const current = progress[entry.id];
  const downloaded = current ? (current.bytes_downloaded ?? current.downloaded_bytes ?? 0) : 0;
  const percentage = current ? Math.min(100, Math.round((downloaded / (current.total_bytes || 1)) * 100)) : 0;

  return (
    <article className="border border-[var(--border)] bg-[var(--bg-secondary)] p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-bold text-[var(--text)]">{entry.name}</h2>
            {entry.required && <span className="border border-[var(--accent)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--accent)]">Requerido</span>}
          </div>
          <p className="mt-2 text-sm font-medium leading-5 text-[var(--text-secondary)]">{entry.description || (entry.features || []).join(", ")}</p>
          <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
            <div><dt className="inline font-semibold text-[var(--text-secondary)]">{t("pn_tamano")} </dt><dd className="inline">{entry.size_bytes ? formatBytes(entry.size_bytes) : t("se_not_reported")}</dd></div>
            <div><dt className="inline font-semibold text-[var(--text-secondary)]">{t("auto_6c04ad58f580")} </dt><dd className="inline">{entry.license || "Consultar avisos"}</dd></div>
          </dl>
          {(entry.source_url || entry.license_url) && (
            <div className="mt-2 flex flex-wrap gap-3 text-xs font-semibold">
              {entry.source_url && <ExternalLink href={entry.source_url} className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">Ver origen</ExternalLink>}
              {entry.license_url && <ExternalLink href={entry.license_url} className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">Ver licencia</ExternalLink>}
            </div>
          )}
        </div>
        <span className="w-fit shrink-0 border border-[var(--border)] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]" aria-live="polite">
          {status === "ready" ? "Instalado" : status === "extracting" ? "Extrayendo" : status === "downloading" ? `${percentage}%` : status === "error" ? "Error" : "No instalado"}
        </span>
      </div>

      {(status === "downloading" || status === "extracting") && current && (
        <div className="mt-4">
          <div className="h-1 w-full overflow-hidden bg-[var(--bg-alt)]" role="progressbar" aria-label={t("z_descarga_de", { name: entry.name })} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}>
            <div className="h-full bg-[var(--accent)] transition-[width] duration-300" style={{ width: `${percentage}%` }} />
          </div>
          <div className="mt-2 flex justify-between font-mono text-[11px] text-[var(--text-dim)]">
            <span>{formatBytes(downloaded)} / {formatBytes(current.total_bytes)}</span>
            <span>{formatSpeed(current.speed_bytes_per_sec ?? 0)}</span>
          </div>
        </div>
      )}

      <div className="mt-4">
        {(status === "missing" || status === "error") && <button type="button" onClick={() => startDownload(entry.id)} className="min-h-11 w-full whitespace-nowrap border border-[var(--accent)] bg-[var(--accent)] px-4 text-xs font-bold uppercase tracking-wider text-white dark:text-zinc-950 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{status === "error" ? "Reintentar descarga" : "Descargar y verificar"}</button>}
        {status === "downloading" && <button type="button" onClick={() => cancelDownload(entry.id)} className="min-h-11 w-full whitespace-nowrap border border-[var(--border)] px-4 text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] hover:bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("c_cancelar")}</button>}
        {status === "extracting" && <p className="text-sm font-medium text-[var(--text-secondary)]">{t("auto_86cc769fdd42")}</p>}
      </div>
    </article>
  );
}