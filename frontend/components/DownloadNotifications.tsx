"use client";
import { useLanguage } from "@/context/LanguageContext";
/* Hallmark · pre-emit critique: P4 H5 E4 S5 R5 V4 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, CheckCircle2, CircleAlert, Download, Inbox, LoaderCircle, PackageOpen, X } from "lucide-react";

import { useDownload } from "@/hooks/useDownload";
import { useAuth } from "@/lib/auth";
import {
  ACTIVITY_DISMISS_EVENT,
  ACTIVITY_NOTIFICATION_EVENT,
  emitActivityNotification,
  activityHref,
  listenForFileDownloads,
  type ActivityNotification,
} from "@/lib/activityNotifications";
import { idDeAvisoDeModulo } from "@/lib/avisosDeModulos";
import { FALTA_PARA_EL_PAQUETE, ID_AVISO_PAQUETE_MOLCY, instalacionMolcy, megasDelPaquete, renderizadorMolcy } from "@/lib/molcy";
import { avanceDeDescarga, formatearBytes, nombreDelModulo } from "@/lib/modulosDescargables";
import { getUserItem, setUserItem } from "@/lib/userStorage";
import { invoke } from "@/lib/tauri";

const STORAGE_KEY = "moldesign_activity_notifications";
const MAX_ACTIVITY = 40;
/** Marca de que este usuario ya recibió las sugerencias de bienvenida. */
const BIENVENIDA_KEY = "moldesign_activity_bienvenida_modelos";
/** La de Blender + Molecular Nodes va aparte: necesita el backend, y quien ya vio la de los modelos también debe verla una vez. */
const BIENVENIDA_MOLCY_KEY = "moldesign_activity_bienvenida_molcy";
/** Para qué sirve cada modelo, en la sugerencia de bienvenida. */
const SUGERENCIA_POR_MODULO: Readonly<Record<string, string>> = {
  "llm-qwen15": "nt_sugerencia_qwen_msg",
  "esmfold-weights": "nt_sugerencia_esmfold_msg",
};

function readStored(userId?: string): ActivityNotification[] {
  if (!userId) return [];
  try {
    const parsed = JSON.parse(getUserItem(STORAGE_KEY, userId) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    // Un archivo que se estaba preparando cuando se cerró la ventana ya no va a
    // llegar: seguía girando para siempre. (Los modelos se reconcilian aparte,
    // con el estado real de Rust.)
    return parsed.slice(0, MAX_ACTIVITY).map((item: ActivityNotification) => (
      item.status === "in_progress" && !item.moduleId
        ? { ...item, status: "error" as const, title: undefined, titleKey: "nt_archivo_interrumpida" }
        : item
    ));
  } catch {
    return [];
  }
}

/** Cuánto se queda el aviso junto a la campana. Un error, más: hay que leerlo. */
function duracionDelAviso(status: ActivityNotification["status"]): number {
  return status === "error" ? 10_000 : 6_000;
}

function iconoDelEstado(status: ActivityNotification["status"]) {
  return status === "success" ? CheckCircle2 : status === "error" ? CircleAlert : status === "info" ? Download : LoaderCircle;
}

function tonoDelEstado(status: ActivityNotification["status"]): string {
  return status === "success" ? "text-emerald-400" : status === "error" ? "text-red-400" : status === "info" ? "text-purple-300"
    : "animate-spin text-purple-300 motion-reduce:animate-none";
}

function bordeDelEstado(status: ActivityNotification["status"]): string {
  return status === "success" ? "border-l-emerald-400" : status === "error" ? "border-l-red-400" : "border-l-purple-400";
}

function barraDelEstado(status: ActivityNotification["status"]): string {
  return status === "success" ? "bg-emerald-400/70" : status === "error" ? "bg-red-400/70" : "bg-purple-400/70";
}

function enVuelo(status: string | undefined): boolean {
  return status === "downloading" || status === "extracting";
}

/**
 * La campana y su panel de actividad.
 *
 * Desde el 2026-10-10 el panel sólo tiene avisos: la sección fija con todos los
 * modelos —instalados o no, que nunca se iba— y el atajo a Evaluación salieron
 * (decisión del propietario). Una descarga de modelo es un aviso más, con su
 * barra en vivo mientras baja (`lib/avisosDeModulos.ts`).
 */
export function DownloadNotifications() {
  const { t } = useLanguage();
  const { manifest, models, progress, initialized, engine } = useDownload();
  const { user } = useAuth();
  const userId = user?.user_id;
  const [open, setOpen] = useState(false);
  const [activity, setActivity] = useState<ActivityNotification[]>([]);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const reconciliadoRef = useRef<string | null>(null);
  // El aviso que sale junto a la campana: qué entrada enseña y cuántas veces
  // ha salido (cada aviso nuevo reinicia su animación y su cuenta atrás).
  const [aviso, setAviso] = useState<{ id: string; vuelta: number } | null>(null);
  const [pausado, setPausado] = useState(false);
  const [campana, setCampana] = useState(0);
  const [fileError, setFileError] = useState<string | null>(null);
  const activityRef = useRef(activity);
  activityRef.current = activity;
  const openRef = useRef(open);
  openRef.current = open;

  const persist = useCallback((next: ActivityNotification[]) => {
    if (userId) setUserItem(STORAGE_KEY, JSON.stringify(next.slice(0, MAX_ACTIVITY)), userId);
  }, [userId]);

  useEffect(() => { setActivity(readStored(userId)); }, [userId]);

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void listenForFileDownloads().then(cleanup => {
      if (disposed) cleanup();
      else unlisten = cleanup;
    });
    return () => { disposed = true; unlisten?.(); };
  }, []);

  // Una descarga de modelo que figuraba en curso cuando se cerró la aplicación
  // ya no avanza: se dice que se interrumpió (el `.part` se reanuda desde
  // Descargas). Una sola vez, con el estado real de los modelos ya conocido.
  useEffect(() => {
    if (!initialized || !userId || reconciliadoRef.current === userId) return;
    reconciliadoRef.current = userId;
    setActivity((current) => {
      let cambiado = false;
      const next = current.map((item) => {
        if (item.status !== "in_progress" || !item.moduleId || enVuelo(models[item.moduleId])) return item;
        cambiado = true;
        return { ...item, status: "error" as const, titleKey: "nt_modelo_interrumpido", messageKey: "nt_modelo_interrumpido_msg" };
      });
      if (!cambiado) return current;
      persist(next);
      return next;
    });
  }, [initialized, userId, models, persist]);

  useEffect(() => {
    const receive = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => {
      const incoming = { ...event.detail, read: openRef.current };
      const anterior = activityRef.current.find((item) => item.id === incoming.id);
      activityRef.current = [incoming, ...activityRef.current.filter((item) => item.id !== incoming.id)];
      setActivity((current) => {
        const next = [incoming, ...current.filter((item) => item.id !== incoming.id)].slice(0, MAX_ACTIVITY);
        persist(next);
        return next;
      });
      // Junto a la campana sale lo NUEVO o lo que cambia de estado (empieza →
      // termina). Con el panel abierto ya se ve, así que no sale.
      if (!incoming.silent && !openRef.current && (!anterior || anterior.status !== incoming.status)) {
        setAviso((prev) => ({ id: incoming.id, vuelta: (prev?.vuelta ?? 0) + 1 }));
        setPausado(false);
        setCampana((n) => n + 1);
      }
    };
    const retire = (event: WindowEventMap[typeof ACTIVITY_DISMISS_EVENT]) => {
      const { id, soloSi } = event.detail;
      setActivity((current) => {
        const next = current.filter((item) => item.id !== id || (soloSi !== undefined && item.status !== soloSi));
        if (next.length === current.length) return current;
        persist(next);
        return next;
      });
    };
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
    window.addEventListener(ACTIVITY_DISMISS_EVENT, retire);
    return () => {
      window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
      window.removeEventListener(ACTIVITY_DISMISS_EVENT, retire);
    };
  }, [persist]);

  // La primera vez que este usuario abre la aplicación, una sugerencia que se
  // puede quitar por cada modelo opcional que falte (decisión del propietario,
  // 2026-10-10). Con el modelo ya en disco no se sugiere nada, y no vuelve a
  // salir: es una bienvenida, no un recordatorio. Va después del oyente de
  // avisos para que éste ya esté escuchando.
  useEffect(() => {
    if (!initialized || !userId || getUserItem(BIENVENIDA_KEY, userId)) return;
    setUserItem(BIENVENIDA_KEY, new Date().toISOString(), userId);
    for (const entry of manifest) {
      if (models[entry.id] !== "missing") continue;
      emitActivityNotification({
        id: idDeAvisoDeModulo(entry.id),
        source: "models",
        status: "info",
        titleKey: "nt_sugerencia_titulo",
        messageKey: SUGERENCIA_POR_MODULO[entry.id] ?? "nt_sugerencia_msg",
        params: { size: entry.size_bytes ? formatearBytes(entry.size_bytes) : "" },
        moduleId: entry.id,
        progress: null,
        href: "/launcher",
      });
    }
  }, [initialized, userId, manifest, models]);

  // Lo mismo para Blender + Molecular Nodes, que Molcy necesita (decisión del propietario, 2026-10-10), si falta algo que
  // se arregla descargando. Se pregunta al backend una sola vez por usuario, con el motor ya listo; si Blender existe, el
  // backend lo sondea (lo mismo que al abrir Molcy). La marca se pone con la respuesta: un backend que aún no contesta no
  // gasta la bienvenida.
  const motorListo = engine?.state === "ready";
  useEffect(() => {
    if (!initialized || !userId || !motorListo || getUserItem(BIENVENIDA_MOLCY_KEY, userId)) return;
    let vivo = true;
    Promise.all([renderizadorMolcy(), instalacionMolcy()]).then(([renderer, instalacion]) => {
      if (!vivo) return;
      setUserItem(BIENVENIDA_MOLCY_KEY, new Date().toISOString(), userId);
      if (renderer.disponible || !FALTA_PARA_EL_PAQUETE.has(renderer.motivo_codigo ?? "")) return;
      emitActivityNotification({
        id: ID_AVISO_PAQUETE_MOLCY,
        source: "general",
        status: "info",
        titleKey: "nt_sugerencia_titulo",
        messageKey: "nt_sugerencia_molcy_msg",
        params: { name: t("cy_pack_name"), size: `${megasDelPaquete(instalacion)} MB` },
        progress: null,
        href: "/launcher",
      });
    }).catch(() => {});
    return () => { vivo = false; };
    // `t` cambia con el idioma; la bienvenida no se repite por eso.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized, userId, motorListo]);

  const unreadCount = activity.filter((item) => !item.read).length;
  const enCurso = activity.some((item) => item.status === "in_progress");
  const itemDelAviso = aviso && !open ? activity.find((item) => item.id === aviso.id) : undefined;

  // El aviso se va solo; pasar el ratón por encima o enfocarlo lo detiene.
  useEffect(() => {
    if (!aviso || pausado || !itemDelAviso) return;
    const temporizador = window.setTimeout(() => setAviso(null), duracionDelAviso(itemDelAviso.status));
    return () => window.clearTimeout(temporizador);
  }, [aviso, pausado, itemDelAviso?.status]);

  const marcarLeido = (id: string) => {
    setActivity((current) => {
      const next = current.map((item) => (item.id === id ? { ...item, read: true } : item));
      persist(next);
      return next;
    });
  };

  const mostrarArchivo = async (item: ActivityNotification) => {
    setFileError(null);
    try {
      await invoke("file_download_reveal", { id: item.fileId });
      marcarLeido(item.id);
      setOpen(false);
      setAviso(null);
    } catch {
      setFileError(item.id);
    }
  };

  const borrarTodo = () => {
    setActivity([]);
    persist([]);
  };

  const togglePanel = () => {
    setAviso(null);
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

  const textos = (item: ActivityNotification) => {
    const valores = { ...item.params, ...(item.moduleId ? { name: nombreDelModulo(item.moduleId, manifest, t) } : {}) };
    return {
      title: item.titleKey ? t(item.titleKey, valores) : item.title ?? "",
      message: item.messageKey ? t(item.messageKey, valores) : item.message ?? "",
    };
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

  const triggerLabel = unreadCount
    ? t(unreadCount === 1 ? "op_activity_count_one" : "op_activity_count_many", { count: unreadCount })
    : enCurso ? t("nt_en_curso") : t("op_activity");

  return (
    <div className="relative">
      <button ref={triggerRef} type="button"
        aria-label={triggerLabel}
        aria-expanded={open} aria-haspopup="dialog" onClick={togglePanel}
        className="relative min-h-11 min-w-11 rounded-lg p-2 text-zinc-400 transition-colors hover:bg-white/[0.05] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 active:bg-white/[0.08]">
        {/* Se mece una vez por aviso nuevo: la `key` vuelve a montar el icono y reinicia la animación. */}
        <Bell key={campana} size={17} aria-hidden="true" className={campana > 0 ? "origin-top motion-safe:animate-campana" : undefined} />
        {unreadCount > 0 && <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-purple-500 px-1 text-[10px] font-bold text-white">{Math.min(99, unreadCount)}</span>}
        {/* Algo sigue bajando aunque ya se haya leído: un punto, no un número. */}
        {unreadCount === 0 && enCurso && <span data-testid="actividad-en-curso" className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-purple-400 ring-2 ring-[var(--bg)]" />}
      </button>

      {/* Lo lee un lector de pantalla; el aviso visible lleva botones y no puede ser la región viva. */}
      <div role="status" aria-live="polite" className="sr-only">
        {itemDelAviso ? `${textos(itemDelAviso).title}. ${textos(itemDelAviso).message}` : ""}
      </div>

      {aviso && itemDelAviso && (() => {
        const { title, message } = textos(itemDelAviso);
        const otros = unreadCount - (itemDelAviso.read ? 0 : 1);
        const Icon = iconoDelEstado(itemDelAviso.status);
        const cuerpo = (
          <span className="flex min-w-0 flex-1 items-start gap-2.5 text-left">
            <Icon size={16} className={`mt-0.5 shrink-0 ${tonoDelEstado(itemDelAviso.status)}`} aria-hidden="true" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-zinc-100">{title}</span>
              {message && <span className="mt-0.5 line-clamp-2 block break-words text-xs leading-relaxed text-zinc-400">{message}</span>}
              {otros > 0 && <span className="mt-1.5 block text-[11px] font-semibold text-purple-300">{t(otros === 1 ? "nt_avisos_mas_uno" : "nt_avisos_mas_varios", { count: otros })}</span>}
            </span>
          </span>
        );
        const alPulsar = () => { marcarLeido(itemDelAviso.id); setAviso(null); };
        return (
          <div key={aviso.vuelta} data-testid="aviso-de-actividad" role="group" aria-label={t("nt_aviso_nuevo")}
            onMouseEnter={() => setPausado(true)} onMouseLeave={() => setPausado(false)}
            onFocus={() => setPausado(true)}
            onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPausado(false); }}
            style={{ "--aviso-duracion": `${duracionDelAviso(itemDelAviso.status)}ms` } as React.CSSProperties}
            className="absolute right-0 top-[calc(100%+10px)] z-[215] w-[min(92vw,340px)] motion-safe:animate-aviso-entra">
            {/* Apunta a la campana: el aviso sale de ella. */}
            <span aria-hidden="true" className="absolute -top-[5px] right-[17px] h-2.5 w-2.5 rotate-45 border-l border-t border-zinc-700 bg-zinc-950" />
            <div className={`relative overflow-hidden rounded-xl border border-zinc-700 border-l-2 bg-zinc-950 shadow-2xl shadow-black/60 ${bordeDelEstado(itemDelAviso.status)}`}>
              <div className="flex items-start gap-1 py-2.5 pl-3 pr-1">
                {itemDelAviso.fileId
                  ? <button type="button" onClick={() => void mostrarArchivo(itemDelAviso)} title={t("nt_archivo_mostrar")} className="flex min-w-0 flex-1 cursor-pointer rounded py-0.5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">{cuerpo}</button>
                  : <Link href={activityHref(itemDelAviso)} onClick={alPulsar} className="flex min-w-0 flex-1 rounded py-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">{cuerpo}</Link>}
                <button type="button" aria-label={t("nt_cerrar_aviso")} onClick={() => setAviso(null)} className="inline-flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-zinc-500 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400"><X size={13} aria-hidden="true" /></button>
              </div>
              {fileError === itemDelAviso.id && <p role="alert" className="px-3 pb-3 text-xs text-amber-300">{t("nt_archivo_no_disponible")} <Link href={activityHref(itemDelAviso)} onClick={alPulsar} className="underline">{t("nt_ver_origen")}</Link></p>}
              {/* Cuenta atrás: se para mientras el ratón o el foco están en el aviso. Sin animaciones, no sale. */}
              <div aria-hidden="true" className={`h-0.5 bg-zinc-800 motion-reduce:hidden ${pausado ? "opacity-0" : ""}`}>
                {!pausado && <div className={`h-full origin-left animate-aviso-tiempo ${barraDelEstado(itemDelAviso.status)}`} />}
              </div>
            </div>
          </div>
        );
      })()}

      {open && (
        <div ref={panelRef} role="dialog" aria-label={t("op_activity_notifications")} className="absolute right-0 top-[calc(100%+10px)] z-[220] w-[min(92vw,390px)] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
          <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
            <div><p className="text-sm font-bold text-white">{t("op_activity")}</p><p className="mt-0.5 text-xs text-zinc-400">{t("auto_30fa396b093a")}</p></div>
            <div className="flex items-center gap-1">
              {activity.length > 0 && <button type="button" onClick={borrarTodo} className="min-h-11 whitespace-nowrap rounded px-2.5 text-xs font-semibold text-zinc-400 hover:bg-white/[0.05] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">{t("nt_borrar_todo")}</button>}
              <button type="button" aria-label={t("op_activity_close")} onClick={() => setOpen(false)} className="inline-flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-zinc-400 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400"><X size={15} aria-hidden="true" /></button>
            </div>
          </div>
          <div className="max-h-[min(65dvh,460px)] overflow-y-auto p-2 custom-scrollbar">
            {activity.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
                <Inbox size={22} className="text-zinc-600" aria-hidden="true" />
                <p className="text-sm font-semibold text-zinc-300">{t("nt_actividad_vacia")}</p>
                <p className="text-xs leading-relaxed text-zinc-500">{t("nt_actividad_vacia_msg")}</p>
              </div>
            ) : (
              <section aria-labelledby="recent-activity">
                <h2 id="recent-activity" className="px-2 py-1.5 text-xs font-bold uppercase tracking-wider text-zinc-400">{t("op_descargas_actividad_reciente")}</h2>
                {activity.map((item) => {
                  const { title, message } = textos(item);
                  const Icon = iconoDelEstado(item.status);
                  const tono = tonoDelEstado(item.status);
                  const avance = item.status === "in_progress" && item.moduleId ? avanceDeDescarga(progress[item.moduleId]) : null;
                  const row = (
                    <div className="flex min-w-0 flex-1 items-start gap-2.5">
                      <Icon size={16} className={`mt-0.5 shrink-0 ${tono}`} aria-hidden="true" />
                      <div className="min-w-0 flex-1 text-left">
                        <p className="text-sm font-semibold text-zinc-100">{title}</p>
                        <p className="mt-1 break-words text-xs leading-relaxed text-zinc-400">{message}</p>
                        {/* La barra de un modelo se lee en vivo del gestor de descargas, no del aviso guardado. */}
                        {avance && avance.total > 0 && <>
                          <div role="progressbar" aria-label={title} aria-valuenow={avance.porcentaje} aria-valuemin={0} aria-valuemax={100} className="mt-2 h-1 overflow-hidden rounded bg-zinc-800"><div className="h-full bg-purple-500 transition-[width] duration-300" style={{ width: `${avance.porcentaje}%` }} /></div>
                          <p className="mt-1 font-mono text-[11px] text-zinc-500">{avance.verificando ? t("nt_modelo_verificando") : `${formatearBytes(avance.descargados)} / ${formatearBytes(avance.total)} · ${avance.porcentaje} %`}</p>
                        </>}
                        {item.status === "in_progress" && !(avance && avance.total > 0) && item.progress == null && <div role="progressbar" aria-label={title} className="mt-2 h-1 overflow-hidden rounded bg-zinc-800"><div className="h-full w-1/2 animate-pulse bg-purple-500 motion-reduce:animate-none" /></div>}
                        {/* Sólo lo que sigue en curso lleva barra: una terminada al 100 % parecía seguir descargando. */}
                        {item.status === "in_progress" && !item.moduleId && item.progress != null && <div role="progressbar" aria-label={title} aria-valuenow={item.progress} aria-valuemin={0} aria-valuemax={100} className="mt-2 h-1 overflow-hidden rounded bg-zinc-800"><div className="h-full bg-purple-500" style={{ width: `${item.progress}%` }} /></div>}
                      </div>
                    </div>
                  );
                  return (
                    <div key={item.id} className="rounded-lg border border-transparent px-3 py-2.5 hover:border-zinc-800 hover:bg-white/[0.025]">
                      <div className="flex items-start gap-2">
                        {item.fileId
                          ? <button type="button" onClick={() => void mostrarArchivo(item)} title={t("nt_archivo_mostrar")} className="min-w-0 flex-1 cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">{row}</button>
                          : <Link href={activityHref(item)} onClick={() => { marcarLeido(item.id); setOpen(false); }} className="min-w-0 flex-1 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">{row}</Link>}
                        <button type="button" onClick={() => dismiss(item.id)} aria-label={t("nt_descartar", { title })} className="inline-flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-zinc-500 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400"><X size={13} aria-hidden="true" /></button>
                      </div>
                      {fileError === item.id && <p role="alert" className="mt-2 text-xs text-amber-300">{t("nt_archivo_no_disponible")} <Link href={activityHref(item)} onClick={() => setOpen(false)} className="underline">{t("nt_ver_origen")}</Link></p>}
                    </div>
                  );
                })}
              </section>
            )}
          </div>
          <div className="border-t border-zinc-800">
            <Link href="/launcher" onClick={() => setOpen(false)} className="flex min-h-11 items-center justify-center gap-2 whitespace-nowrap text-xs font-bold text-purple-300 hover:bg-purple-500/[0.06] hover:text-purple-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-purple-400"><PackageOpen size={14} aria-hidden="true" /> {t("op_menu_downloads")}</Link>
          </div>
        </div>
      )}
    </div>
  );
}
