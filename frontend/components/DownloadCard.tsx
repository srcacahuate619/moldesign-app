"use client";


import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { useDownload } from "../hooks/useDownload";
import type { ModuleEntry } from "../lib/types";
import { avanceDeDescarga, descripcionDelModulo, formatearBytes as formatBytes, nombreDelModulo } from "@/lib/modulosDescargables";

import { ExternalLink } from "@/components/ui/ExternalLink";

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec >= 1_000_000) return `${(bytesPerSec / 1_000_000).toFixed(1)} MB/s`;
  if (bytesPerSec >= 1_000) return `${(bytesPerSec / 1_000).toFixed(0)} KB/s`;
  return `${bytesPerSec.toFixed(0)} B/s`;
}

export function DownloadCard({ entry }: { entry: ModuleEntry }) {
  const { t } = useLanguage();
  const name = nombreDelModulo(entry.id, [entry], t);
  const description = descripcionDelModulo(entry, t);
  const { models, progress, startDownload, cancelDownload } = useDownload();
  // Volver a descargar un modelo instalado se confirma: son gigas, y el botón
  // grande de antes invitaba a bajarlo otra vez sin motivo.
  const [confirmando, setConfirmando] = useState(false);
  const status = models[entry.id] || "missing";
  const current = progress[entry.id];
  const { porcentaje: percentage, descargados: downloaded, total, verificando } = avanceDeDescarga(current);
  const size = entry.size_bytes ? formatBytes(entry.size_bytes) : t("se_not_reported");

  return (
    <article className="border border-[var(--border)] bg-[var(--bg-secondary)] p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-bold text-[var(--text)]">{name}</h2>
            {entry.required && <span className="border border-[var(--accent)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--accent)]">{t("op_download_required")}</span>}
          </div>
          <p className="mt-2 text-sm font-medium leading-5 text-[var(--text-secondary)]">{description}</p>
          <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
            <div><dt className="inline font-semibold text-[var(--text-secondary)]">{t("pn_tamano")} </dt><dd className="inline">{size}</dd></div>
            <div><dt className="inline font-semibold text-[var(--text-secondary)]">{t("auto_6c04ad58f580")} </dt><dd className="inline">{entry.license || t("op_download_consult_notices")}</dd></div>
          </dl>
          {(entry.source_url || entry.license_url) && (
            <div className="mt-2 flex flex-wrap gap-3 text-xs font-semibold">
              {entry.source_url && <ExternalLink href={entry.source_url} className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("op_download_view_source")}</ExternalLink>}
              {entry.license_url && <ExternalLink href={entry.license_url} className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("op_download_view_license")}</ExternalLink>}
            </div>
          )}
        </div>
        <span className={`w-fit shrink-0 border px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${status === "ready" ? "border-emerald-500/40 text-emerald-400" : "border-[var(--border)] text-[var(--text-secondary)]"}`} aria-live="polite">
          {status === "ready" ? t("op_download_installed") : status === "extracting" ? t("op_download_extracting") : status === "downloading" ? `${percentage}%` : status === "error" ? t("error") : t("op_download_not_installed")}
        </span>
      </div>

      {(status === "downloading" || status === "extracting") && current && (
        <div className="mt-4">
          <div className="h-1 w-full overflow-hidden bg-[var(--bg-alt)]" role="progressbar" aria-label={t("z_descarga_de", { name })} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}>
            <div className="h-full bg-[var(--accent)] transition-[width] duration-300" style={{ width: `${percentage}%` }} />
          </div>
          <div className="mt-2 flex justify-between font-mono text-[11px] text-[var(--text-dim)]">
            <span>{formatBytes(downloaded)} / {formatBytes(total)}</span>
            {/* Con todo en disco, Rust calcula el SHA-256: más de medio minuto con ESMFold y la barra llena. */}
            <span>{verificando ? t("nt_modelo_verificando") : formatSpeed(current.speed_bytes_per_sec ?? 0)}</span>
          </div>
        </div>
      )}

      <div className="mt-4">
        {status === "ready" && (
          <div data-testid="modulo-instalado">
            <p className="flex items-center gap-2 text-sm font-semibold text-emerald-400">
              <CheckCircle2 size={16} aria-hidden="true" /> {t("op_download_already_installed")}
            </p>
            <p className="mt-1 text-xs leading-5 text-[var(--text-dim)]">{t("op_download_already_installed_detail")}</p>
            {!confirmando ? (
              <button type="button" onClick={() => setConfirmando(true)} className="mt-2 min-h-9 text-xs font-semibold text-[var(--text-secondary)] underline-offset-4 hover:text-[var(--text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">
                {t("op_download_again_question")}
              </button>
            ) : (
              <div role="group" aria-label={t("op_download_again")} className="mt-3 border border-[var(--border)] bg-[var(--bg-alt)] p-3">
                <p className="text-xs leading-5 text-[var(--text-secondary)]">{t("op_download_again_detail", { size })}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => { setConfirmando(false); void startDownload(entry.id); }} className="min-h-10 whitespace-nowrap border border-[var(--accent)] px-4 text-xs font-bold uppercase tracking-wider text-[var(--accent)] hover:bg-[var(--accent)] hover:text-white dark:hover:text-zinc-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("op_download_again")}</button>
                  <button type="button" onClick={() => setConfirmando(false)} className="min-h-10 whitespace-nowrap border border-[var(--border)] px-4 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("c_cancelar")}</button>
                </div>
              </div>
            )}
          </div>
        )}
        {(status === "missing" || status === "error") && <button type="button" onClick={() => startDownload(entry.id)} className="min-h-11 w-full whitespace-nowrap border border-[var(--accent)] bg-[var(--accent)] px-4 text-xs font-bold uppercase tracking-wider text-white dark:text-zinc-950 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{status === "error" ? t("op_download_retry") : t("op_download_and_verify")}</button>}
        {status === "downloading" && <button type="button" onClick={() => cancelDownload(entry.id)} className="min-h-11 w-full whitespace-nowrap border border-[var(--border)] px-4 text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] hover:bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("c_cancelar")}</button>}
        {status === "extracting" && <p className="text-sm font-medium text-[var(--text-secondary)]">{t("auto_86cc769fdd42")}</p>}
      </div>
    </article>
  );
}

