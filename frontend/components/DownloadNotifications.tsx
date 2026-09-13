/* Hallmark · pre-emit critique: P4 H5 E4 S5 R5 V4 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, CheckCircle2, CircleAlert, Download, FlaskConical, LoaderCircle, PackageOpen, X } from "lucide-react";

import { useDownload } from "@/hooks/useDownload";
import { useAuth } from "@/lib/auth";
import { ACTIVITY_NOTIFICATION_EVENT, type ActivityNotification } from "@/lib/activityNotifications";
import { getUserItem, setUserItem } from "@/lib/userStorage";

const STORAGE_KEY = "moldesign_activity_notifications";
const MAX_ACTIVITY = 40;

function statusLabel(status: string): string {
  if (status === "ready") return "Instalado y verificado";
  if (status === "downloading") return "Descargando";
  if (status === "extracting") return "Instalando";
  if (status === "error") return "Requiere atención";
  return "Disponible para descargar";
}

function readStored(userId?: string): ActivityNotification[] {
  if (!userId) return [];
  try {
    const parsed = JSON.parse(getUserItem(STORAGE_KEY, userId) ?? "[]");
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ACTIVITY) : [];
  } catch {
    return [];
  }
}

export function DownloadNotifications() {
  const { manifest, models, progress } = useDownload();
  const { user } = useAuth();
  const userId = user?.user_id;
  const [open, setOpen] = useState(false);
  const [activity, setActivity] = useState<ActivityNotification[]>([]);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const persist = useCallback((next: ActivityNotification[]) => {
    if (userId) setUserItem(STORAGE_KEY, JSON.stringify(next.slice(0, MAX_ACTIVITY)), userId);
  }, [userId]);

  useEffect(() => { setActivity(readStored(userId)); }, [userId]);

  useEffect(() => {
    const receive = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => {
      setActivity((current) => {
        const incoming = { ...event.detail, read: open };
        const next = [incoming, ...current.filter((item) => item.id !== incoming.id)].slice(0, MAX_ACTIVITY);
        persist(next);
        return next;
      });
    };
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
    return () => window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
  }, [open, persist]);

  const activeCount = manifest.filter((entry) => models[entry.id] === "downloading" || models[entry.id] === "extracting").length;
  const errorCount = manifest.filter((entry) => models[entry.id] === "error").length;
  const unreadCount = activity.filter((item) => !item.read).length;
  const badgeCount = activeCount + errorCount + unreadCount;

  const togglePanel = () => {
    setOpen((value) => {
      const nextOpen = !value;
      if (nextOpen) {
        setActivity((current) => {
          const next = current.map((item) => ({ ...item, read: true }));
          persist(next);
          return next;
        });
      }
      return nextOpen;
    });
  };

  const dismiss = (id: string) => {
    setActivity((current) => {
      const next = current.filter((item) => item.id !== id);
      persist(next);
      return next;
    });
  };

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node) && !triggerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); triggerRef.current?.focus(); }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [open]);

  return (
    <div className="relative">
      <button ref={triggerRef} type="button"
        aria-label={badgeCount ? `Actividad: ${badgeCount} pendiente` : "Actividad"}
        aria-expanded={open} aria-haspopup="dialog" onClick={togglePanel}
        className="relative min-h-11 min-w-11 rounded-lg p-2 text-zinc-400 transition-colors hover:bg-white/[0.05] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 active:bg-white/[0.08]">
        <Bell size={17} aria-hidden="true" />
        {badgeCount > 0 && <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-purple-500 px-1 text-[10px] font-bold text-white">{Math.min(99, badgeCount)}</span>}
      </button>

      {open && (
        <div ref={panelRef} role="dialog" aria-label="Actividad y notificaciones" className="absolute right-0 top-[calc(100%+10px)] z-[220] w-[min(92vw,390px)] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
          <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
            <div><p className="text-sm font-bold text-white">Actividad</p><p className="mt-0.5 text-xs text-zinc-400">Corridas, archivos, modelos y motores</p></div>
            <button type="button" aria-label="Cerrar actividad" onClick={() => setOpen(false)} className="min-h-11 min-w-11 rounded p-2 text-zinc-400 hover:bg-white/[0.05] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400 active:bg-white/[0.08]"><X size={15} aria-hidden="true" /></button>
          </div>
          <div className="max-h-[min(65dvh,460px)] overflow-y-auto p-2 custom-scrollbar">
            {activity.length > 0 && (
              <section aria-labelledby="recent-activity">
                <h2 id="recent-activity" className="px-2 py-1.5 text-xs font-bold uppercase tracking-wider text-zinc-400">Actividad reciente</h2>
                {activity.map((item) => {
                  const Icon = item.status === "success" ? CheckCircle2 : item.status === "error" ? CircleAlert : LoaderCircle;
                  const row = (
                    <div className="flex min-w-0 flex-1 items-start gap-2.5">
                      <Icon size={16} className={`mt-0.5 shrink-0 ${item.status === "success" ? "text-emerald-400" : item.status === "error" ? "text-red-400" : "animate-spin text-purple-300 motion-reduce:animate-none"}`} aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-zinc-100">{item.title}</p>
                        <p className="mt-1 break-words text-sm leading-relaxed text-zinc-300">{item.message}</p>
                        {item.status === "in_progress" && item.progress == null && <div role="progressbar" aria-label={item.title} className="mt-2 h-1 overflow-hidden rounded bg-zinc-800"><div className="h-full w-1/2 animate-pulse bg-purple-500 motion-reduce:animate-none" /></div>}
                        {item.progress != null && <div role="progressbar" aria-label={item.title} aria-valuenow={item.progress} aria-valuemin={0} aria-valuemax={100} className="mt-2 h-1 overflow-hidden rounded bg-zinc-800"><div className="h-full bg-purple-500" style={{ width: `${item.progress}%` }} /></div>}
                      </div>
                    </div>
                  );
                  return (
                    <div key={item.id} className="group flex items-start gap-1 rounded-lg border border-transparent px-3 py-2.5 hover:border-zinc-800 hover:bg-white/[0.025]">
                      {item.href ? <Link href={item.href} onClick={() => setOpen(false)} className="min-w-0 flex-1 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">{row}</Link> : row}
                      <button type="button" onClick={() => dismiss(item.id)} aria-label={`Descartar: ${item.title}`} className="min-h-11 min-w-11 shrink-0 rounded p-2 text-zinc-500 hover:bg-white/[0.05] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400"><X size={13} aria-hidden="true" /></button>
                    </div>
                  );
                })}
              </section>
            )}

            <section aria-labelledby="model-activity">
              <h2 id="model-activity" className="px-2 py-1.5 text-xs font-bold uppercase tracking-wider text-zinc-400">Modelos y motores</h2>
              {manifest.map((entry) => {
                const status = models[entry.id] || "missing";
                const event = progress[entry.id];
                const downloaded = event?.bytes_downloaded ?? event?.downloaded_bytes ?? 0;
                const percent = event?.total_bytes ? Math.min(100, Math.round((downloaded / event.total_bytes) * 100)) : 0;
                const Icon = status === "ready" ? CheckCircle2 : status === "error" ? CircleAlert : status === "downloading" || status === "extracting" ? LoaderCircle : Download;
                return (
                  <div key={entry.id} className="rounded-lg border border-transparent px-3 py-2.5 hover:border-zinc-800 hover:bg-white/[0.025]">
                    <div className="flex items-start gap-2.5">
                      <Icon size={16} className={`mt-0.5 shrink-0 ${status === "ready" ? "text-emerald-400" : status === "error" ? "text-red-400" : status === "downloading" || status === "extracting" ? "animate-spin text-purple-300 motion-reduce:animate-none" : "text-zinc-500"}`} aria-hidden="true" />
                      <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-zinc-200">{entry.name}</p><p className="mt-1 text-sm text-zinc-400">{statusLabel(status)}{status === "downloading" ? ` · ${percent}%` : ""}</p>{status === "downloading" && <div role="progressbar" aria-label={`Descarga de ${entry.name}`} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} className="mt-2 h-1 overflow-hidden rounded bg-zinc-800"><div className="h-full bg-purple-500" style={{ width: `${percent}%` }} /></div>}</div>
                    </div>
                  </div>
                );
              })}
            </section>
          </div>
          <div className="grid grid-cols-2 border-t border-zinc-800">
            <Link href="/evaluation" onClick={() => setOpen(false)} className="flex min-h-11 items-center justify-center gap-2 whitespace-nowrap text-xs font-bold text-zinc-300 hover:bg-white/[0.04] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-purple-400"><FlaskConical size={14} aria-hidden="true" /> Evaluación</Link>
            <Link href="/launcher" onClick={() => setOpen(false)} className="flex min-h-11 items-center justify-center gap-2 whitespace-nowrap border-l border-zinc-800 text-xs font-bold text-purple-300 hover:bg-purple-500/[0.06] hover:text-purple-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-purple-400"><PackageOpen size={14} aria-hidden="true" /> Descargas</Link>
          </div>
        </div>
      )}
    </div>
  );
}