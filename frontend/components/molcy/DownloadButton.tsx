"use client";

import { useRef, useState, type ReactNode } from "react";
import { Download, LoaderCircle } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

export function DownloadButton({ children, onDownload, onError, className = "" }: {
  children: ReactNode;
  onDownload: () => Promise<void>;
  onError: (error: Error) => void;
  className?: string;
}) {
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);

  const download = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      await onDownload();
    } catch (error) {
      onError(error instanceof Error ? error : new Error(String(error)));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };

  return <button type="button" onClick={download} disabled={busy} aria-busy={busy}
    className={`relative inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 transition-[background-color,box-shadow,transform] duration-100 hover:bg-[var(--bg-secondary)] active:translate-y-px active:bg-[var(--bg-secondary)] active:shadow-[inset_0_2px_4px_rgb(0_0_0/0.35)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-wait disabled:bg-[var(--bg-secondary)] disabled:shadow-[inset_0_2px_4px_rgb(0_0_0/0.35)] motion-reduce:transform-none motion-reduce:transition-none ${className}`}>
    {busy ? <LoaderCircle size={14} aria-hidden="true" className="shrink-0 animate-spin motion-reduce:animate-none" />
      : <Download size={14} aria-hidden="true" className="shrink-0" />}
    {children}
    {busy && <span role="status" className="sr-only">{t("nt_archivo_preparando")}</span>}
  </button>;
}
