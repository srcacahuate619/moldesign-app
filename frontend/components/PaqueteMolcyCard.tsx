"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2 } from "lucide-react";

import { useLanguage } from "@/context/LanguageContext";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { useAuth } from "@/lib/auth";
import { emitActivityNotification } from "@/lib/activityNotifications";
import {
  cancelarBlenderMolcy, configurarMolcy, estadoAddonMolcy, FALTA_PARA_EL_PAQUETE, ID_AVISO_PAQUETE_MOLCY, instalacionMolcy,
  instalarAddonMolcy, instalarBlenderMolcy, MOLECULAR_NODES_MB_MEDIDOS, renderizadorMolcy,
  type MolcyAddon, type MolcyInstallation, type MolcyRenderer,
} from "@/lib/molcy";

const SONDEO_MS = 1500;

/**
 * Blender + Molecular Nodes, el paquete que Molcy necesita, en el menú de Descargas.
 *
 * No es un módulo del manifiesto: no lo baja Rust. Lo instala el backend, con los
 * mismos dos caminos que la pestaña Molcy —Blender portable desde
 * download.blender.org con su SHA-256 fijado, y Molecular Nodes con el gestor de
 * extensiones del propio Blender—, así que aquí sólo se orquestan: con «Descargar
 * e instalar», primero Blender y, al terminar, Molecular Nodes. Lo que decide si
 * está listo es la comprobación del renderizador (la misma que usa Molcy), no la
 * presencia de un archivo: un Blender propio que ya sirve cuenta como instalado.
 *
 * No hay «descargar de nuevo»: el backend no reinstala un Blender administrado
 * que ya existe. Si algo falla, «Comprobar de nuevo» repite el sondeo y la
 * pestaña Molcy permite elegir otro Blender.
 *
 * `contexto="estudio"` es la misma tarjeta dentro de Molcy, debajo del guion
 * visual (pedido del propietario, 2026-10-12: la descarga estaba repartida y no
 * se veía): dice por qué Molcy la necesita y el botón nombra el paquete entero.
 * `onListo` recibe la comprobación que dejó el paquete listo, para que la página
 * no vuelva a lanzar Blender; `onInstalando` le dice si hay una instalación en
 * curso.
 */
export function PaqueteMolcyCard({ contexto = "descargas", onListo, onInstalando }: {
  contexto?: "descargas" | "estudio";
  onListo?: (renderer: MolcyRenderer) => void;
  onInstalando?: (instalando: boolean) => void;
} = {}) {
  const { t } = useLanguage();
  const { user, isLoading: sesionCargando } = useAuth();
  const [renderer, setRenderer] = useState<MolcyRenderer | null>(null);
  const [instalacion, setInstalacion] = useState<MolcyInstallation | null>(null);
  const [addon, setAddon] = useState<MolcyAddon | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // El investigador pidió el paquete entero: al terminar Blender sigue Molecular Nodes.
  const encadenarRef = useRef(false);

  const comprobar = useCallback(async (recomprobar = false): Promise<MolcyRenderer | null> => {
    setError(null);
    try {
      const [r, i, a] = await Promise.all([renderizadorMolcy(recomprobar), instalacionMolcy(), estadoAddonMolcy()]);
      setRenderer(r); setInstalacion(i); setAddon(a);
      return r;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, []);

  // Las rutas de Molcy piden sesión, y un 401 manda a «Iniciar sesión»: sin sesión no se pregunta. En escritorio
  // siempre la hay (entrada automática); en el navegador, esta página de Descargas no debe expulsar a nadie.
  const conSesion = !sesionCargando && Boolean(user);
  useEffect(() => { if (conSesion) void comprobar(); }, [comprobar, conSesion]);

  const avisar = useCallback((exito: boolean) => {
    emitActivityNotification({
      id: ID_AVISO_PAQUETE_MOLCY, source: "general", status: exito ? "success" : "error",
      titleKey: exito ? "nt_molcy_listo" : "nt_molcy_fallo", messageKey: exito ? "nt_molcy_listo_msg" : "nt_molcy_fallo_msg",
      progress: null, href: exito ? "/molcy" : "/launcher",
    });
  }, []);

  const instalarAddon = useCallback(async () => {
    setError(null);
    try { setAddon(await instalarAddonMolcy()); }
    catch (e) { setError((e as Error).message); encadenarRef.current = false; }
  }, []);

  // Blender instalándose: se sigue hasta que acaba; si el paquete se pidió entero, sigue Molecular Nodes.
  useEffect(() => {
    if (instalacion?.estado !== "instalando") return;
    let vivo = true;
    const id = window.setInterval(() => {
      instalacionMolcy().then(async (siguiente) => {
        if (!vivo) return;
        setInstalacion(siguiente);
        if (siguiente.estado === "instalando") return;
        const r = await comprobar(true);
        if (!vivo) return;
        if (siguiente.estado === "completo" && encadenarRef.current && r?.motivo_codigo === "falta_addon") {
          await instalarAddon();
        } else {
          if (siguiente.estado === "fallido") avisar(false);
          else if (siguiente.estado === "completo" && r?.disponible) avisar(true);
          encadenarRef.current = false;
        }
      }).catch((e: Error) => { if (vivo) setError(e.message); });
    }, SONDEO_MS);
    return () => { vivo = false; window.clearInterval(id); };
  }, [instalacion?.estado, comprobar, instalarAddon, avisar]);

  // Molecular Nodes instalándose (lo hace Blender): se sigue hasta que acaba.
  useEffect(() => {
    if (addon?.estado !== "instalando") return;
    let vivo = true;
    const id = window.setInterval(() => {
      estadoAddonMolcy().then(async (siguiente) => {
        if (!vivo) return;
        setAddon(siguiente);
        if (siguiente.estado === "instalando") return;
        const r = await comprobar();
        if (!vivo) return;
        encadenarRef.current = false;
        avisar(siguiente.estado === "completo" && Boolean(r?.disponible));
      }).catch((e: Error) => { if (vivo) setError(e.message); });
    }, SONDEO_MS);
    return () => { vivo = false; window.clearInterval(id); };
  }, [addon?.estado, comprobar, avisar]);

  const hacer = async (accion: () => Promise<void>) => {
    setOcupado(true); setError(null);
    try { await accion(); }
    catch (e) { setError((e as Error).message); encadenarRef.current = false; }
    finally { setOcupado(false); }
  };

  const instalarTodo = () => hacer(async () => {
    encadenarRef.current = true;
    setInstalacion(await instalarBlenderMolcy());
  });

  // Ya hay un Blender de MolDesign, pero Molcy apunta a otro que no sirve: se vuelve a él.
  const usarAdministrado = () => hacer(async () => {
    await configurarMolcy({ modo: "administrado", blender: null, motor: null });
    const r = await comprobar(true);
    if (r?.motivo_codigo === "falta_addon") { encadenarRef.current = true; await instalarAddon(); }
  });

  const blenderMb = Math.ceil((instalacion?.descarga_bytes ?? 404_453_484) / 1e6);
  const version = instalacion?.version ?? "5.2.2";
  const cargando = conSesion && !renderer && !error;
  const instalandoBlender = instalacion?.estado === "instalando";
  const instalandoAddon = addon?.estado === "instalando";
  const listo = Boolean(renderer?.disponible) && !instalandoBlender && !instalandoAddon;
  const faltaBlender = FALTA_PARA_EL_PAQUETE.has(renderer?.motivo_codigo ?? "") && renderer?.motivo_codigo !== "falta_addon";
  const fallo = instalacion?.estado === "fallido" ? instalacion.motivo : addon?.estado === "fallido" ? addon.motivo : null;

  const enEstudio = contexto === "estudio";
  // Si sólo falta Molecular Nodes y el Blender es el del usuario, la extensión va al perfil de ESE Blender, no a la carpeta
  // de datos de MolDesign: el texto no puede decir lo contrario.
  const normalizar = (ruta: string) => ruta.replace(/\//g, "\\").toLowerCase();
  const blenderPropio = renderer?.motivo_codigo === "falta_addon" && Boolean(renderer.blender && instalacion?.ruta)
    && normalizar(renderer.blender ?? "") !== normalizar(instalacion?.ruta ?? "");
  // La página se entera una vez por cada vez que el paquete pasa a estar listo, con la comprobación que lo dijo.
  const avisadoListo = useRef<MolcyRenderer | null>(null);
  useEffect(() => {
    if (!listo || !renderer || avisadoListo.current === renderer) return;
    avisadoListo.current = renderer;
    onListo?.(renderer);
  }, [listo, renderer, onListo]);
  const instalando = instalandoBlender || instalandoAddon;
  useEffect(() => { onInstalando?.(instalando); }, [instalando, onInstalando]);

  const insignia = listo ? t("op_download_installed")
    : instalandoBlender || instalandoAddon ? t("op_download_downloading")
    : t("op_download_not_installed");

  return (
    <article data-testid="paquete-molcy" className="border border-[var(--border)] bg-[var(--bg-secondary)] p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {enEstudio && <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{t("cy_pack_studio_eyebrow")}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-bold text-[var(--text)]">{t(enEstudio ? "cy_pack_studio_title" : "cy_pack_name")}</h2>
            {!enEstudio && <span className="border border-[var(--border)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">{t("cy_pack_for")}</span>}
          </div>
          {enEstudio ? <>
            <p className="mt-2 text-sm font-medium leading-6 text-[var(--text-secondary)]" data-testid="paquete-molcy-porque">{t("cy_pack_studio_why")}</p>
            <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]" data-testid="paquete-molcy-donde">
              {blenderPropio ? t("cy_pack_studio_where_own", { ruta: renderer?.blender ?? "" }) : t("cy_pack_studio_where", { version })}
            </p>
          </> : <p className="mt-2 text-sm font-medium leading-5 text-[var(--text-secondary)]">{t("cy_pack_description", { version })}</p>}
          <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
            <div><dt className="inline font-semibold text-[var(--text-secondary)]">{t("pn_tamano")} </dt><dd className="inline">{t("cy_pack_size", { blender: blenderMb, mn: MOLECULAR_NODES_MB_MEDIDOS })}</dd></div>
            <div><dt className="inline font-semibold text-[var(--text-secondary)]">{t("auto_6c04ad58f580")} </dt><dd className="inline">{t("cy_pack_license")}</dd></div>
          </dl>
          <div className="mt-2 flex flex-wrap gap-3 text-xs font-semibold">
            <ExternalLink href="https://www.blender.org/download/" className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("cy_pack_view_blender")}</ExternalLink>
            <ExternalLink href="https://extensions.blender.org/add-ons/molecularnodes/" className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("cy_pack_view_mn")}</ExternalLink>
            <ExternalLink href="https://www.blender.org/about/license/" className="text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">{t("op_download_view_license")}</ExternalLink>
          </div>
        </div>
        {/* Sin sondeo (sin sesión, cargando o sin backend) no se sabe: no se afirma «no instalado». */}
        {renderer && <span className={`w-fit shrink-0 border px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${listo ? "border-emerald-500/40 text-emerald-400" : "border-[var(--border)] text-[var(--text-secondary)]"}`} aria-live="polite">
          {insignia}
        </span>}
      </div>

      <div className="mt-4">
        {!sesionCargando && !user && <p className="text-xs leading-5 text-[var(--text-dim)]">{t("cy_pack_needs_session")}</p>}
        {cargando && <p role="status" className="text-xs text-[var(--text-dim)]">{t("cy_pack_checking")}</p>}

        {error && !renderer && (
          <div role="alert" className="text-xs leading-5 text-red-400">
            <p>{t("cy_pack_unreachable", { motivo: error })}</p>
            <button type="button" onClick={() => void comprobar()} className="mt-2 min-h-9 border border-[var(--border)] px-3 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-alt)]">{t("cy_pack_retry")}</button>
          </div>
        )}

        {listo && renderer && (
          <div data-testid="paquete-molcy-instalado">
            <p className="flex items-center gap-2 text-sm font-semibold text-emerald-400">
              <CheckCircle2 size={16} aria-hidden="true" /> {t("op_download_already_installed")}
            </p>
            <p className="mt-1 text-xs leading-5 text-[var(--text-dim)]">
              {t("cy_pack_installed_detail", { blender: renderer.version_blender?.join(".") ?? "?", mn: renderer.molecular_nodes ?? "?" })}
            </p>
            <button type="button" disabled={ocupado} onClick={() => hacer(async () => { await comprobar(true); })} className="mt-2 min-h-9 text-xs font-semibold text-[var(--text-secondary)] underline-offset-4 hover:text-[var(--text)] hover:underline disabled:opacity-50">
              {t("cy_pack_recheck_question")}
            </button>
          </div>
        )}

        {instalandoBlender && instalacion && (
          <div role="status" aria-live="polite">
            <p className="text-xs font-semibold text-[var(--text-secondary)]">{t("cy_pack_step_blender")} · {t("cy_install_progress")}</p>
            <div className="mt-2 h-1 w-full overflow-hidden bg-[var(--bg-alt)]" role="progressbar" aria-label={t("cy_pack_step_blender")} aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={Math.floor(((instalacion.recibidos_bytes ?? 0) / instalacion.descarga_bytes) * 100)}>
              <div className="h-full bg-[var(--accent)] transition-[width] duration-300" style={{ width: `${Math.min(100, ((instalacion.recibidos_bytes ?? 0) / instalacion.descarga_bytes) * 100)}%` }} />
            </div>
            {instalacion.fase !== "instalando" && <button type="button" disabled={ocupado} onClick={() => hacer(async () => { encadenarRef.current = false; setInstalacion(await cancelarBlenderMolcy()); })} className="mt-3 min-h-11 w-full whitespace-nowrap border border-[var(--border)] px-4 text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] hover:bg-[var(--bg-alt)]">{t("cy_cancel_download")}</button>}
          </div>
        )}

        {instalandoAddon && addon && (
          <div role="status" aria-live="polite">
            <p className="text-xs font-semibold text-[var(--text-secondary)]">{t("cy_pack_step_addon")} · {t(addon.fase === "descargando" ? "cy_addon_downloading" : addon.fase === "verificando" ? "cy_addon_verifying" : "cy_addon_checking")}</p>
            <div className="mt-2 h-1 w-full overflow-hidden bg-[var(--bg-alt)]"><div className="h-full w-1/3 animate-pulse bg-[var(--accent)] motion-reduce:animate-none" /></div>
          </div>
        )}

        {renderer && !listo && !instalandoBlender && !instalandoAddon && (
          <>
            {faltaBlender && !instalacion?.instalado && (
              <button type="button" disabled={ocupado} onClick={instalarTodo} className={`min-h-11 w-full border border-[var(--accent)] bg-[var(--accent)] px-4 text-xs font-bold uppercase tracking-wider text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] ${enEstudio ? "py-2 leading-5" : "whitespace-nowrap"}`}>{t(enEstudio ? "cy_pack_install_full" : "cy_pack_install")}</button>
            )}
            {faltaBlender && instalacion?.instalado && (
              <div>
                <p className="text-xs leading-5 text-[var(--text-secondary)]">{t("cy_pack_use_managed_detail", { motivo: renderer.motivo ?? "" })}</p>
                <button type="button" disabled={ocupado} onClick={usarAdministrado} className="mt-3 min-h-11 w-full whitespace-nowrap border border-[var(--accent)] bg-[var(--accent)] px-4 text-xs font-bold uppercase tracking-wider text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-60">{t("cy_pack_use_managed")}</button>
              </div>
            )}
            {renderer.motivo_codigo === "falta_addon" && (
              <div>
                <p className="text-xs leading-5 text-[var(--text-secondary)]">{t("cy_pack_missing_addon")}</p>
                <button type="button" disabled={ocupado} onClick={() => hacer(instalarAddon)} className="mt-3 min-h-11 w-full whitespace-nowrap border border-[var(--accent)] bg-[var(--accent)] px-4 text-xs font-bold uppercase tracking-wider text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-60">{t("cy_addon_install")}</button>
              </div>
            )}
            {!faltaBlender && renderer.motivo_codigo !== "falta_addon" && (
              <p className="text-xs leading-5 text-[var(--text-secondary)]">
                {t("cy_pack_other", { motivo: renderer.motivo ?? "" })}{" "}
                {/* En el estudio ya se está en Molcy: el enlace sólo tiene sentido desde Descargas. */}
                {!enEstudio && <Link href="/molcy" className="font-semibold text-[var(--accent)] underline-offset-4 hover:underline">{t("cy_pack_open_molcy")}</Link>}
              </p>
            )}
          </>
        )}

        {fallo && !listo && !instalandoBlender && !instalandoAddon && <p role="alert" className="mt-3 text-xs leading-5 text-red-400">{t("cy_pack_failed", { motivo: fallo })}</p>}
        {error && renderer && <p role="alert" className="mt-3 text-xs leading-5 text-red-400">{error}</p>}
      </div>
    </article>
  );
}
