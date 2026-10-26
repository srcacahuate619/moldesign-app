"use client";
import { useEffect, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { FALTA_PARA_EL_PAQUETE, configurarMolcy, instalacionMolcy, type MolcyInstallation, type MolcyRenderer } from "@/lib/molcy";

/**
 * Qué Blender usa Molcy (el de MolDesign o uno del equipo) y «Comprobar».
 *
 * Descargar e instalar ya no vive aquí: lo hace la tarjeta del estudio, debajo del guion visual (`PaqueteMolcyCard`), que
 * encadena Blender y Molecular Nodes. Había dos botones de descarga y un tercero de Molecular Nodes repartidos por la columna,
 * y no se veía cuál tocar (propietario, 2026-10-12).
 */
export function RendererSettings({ renderer, onChanged, busy }: {
  renderer: MolcyRenderer | null; onChanged: () => Promise<void>; busy: boolean;
}) {
  const { t } = useLanguage();
  const [status, setStatus] = useState<MolcyInstallation | null>(null);
  // Sin opción marcada hasta saber qué hay: antes salía «Blender de MolDesign» por defecto y, al llegar la lista de los
  // Blender del equipo, saltaba sola a «Usar mi Blender» (medido en el export, 2026-10-10).
  const [mode, setMode] = useState<"administrado" | "existente" | null>(null);
  const [blender, setBlender] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const encontrados = renderer?.blenders_encontrados ?? [];
  // Un Blender hallado que el motor puede usar (versión suficiente o aún desconocida): se ofrece de entrada, sin pedir su ruta.
  const sugerido = encontrados.find(e => e.apto !== false)?.ruta ?? "";
  useEffect(() => {
    let alive = true;
    instalacionMolcy().then(value => { if (alive) setStatus(value); })
      .catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [renderer?.blender]);
  // La propuesta se decide UNA vez, con la instalación y los Blender encontrados ya a la vista. Después sólo la cambia el
  // investigador; una consulta nueva no la pisa.
  useEffect(() => {
    if (mode !== null || !status || !renderer) return;
    const propio = sugerido || (encontrados.length ? "" : renderer.blender || "");
    setMode(status.configuracion.modo || (status.instalado || !propio ? "administrado" : "existente"));
    setBlender(status.configuracion.blender || propio);
    // `encontrados` cambia de identidad en cada consulta; lo que decide es `sugerido` (un texto estable).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, status, renderer, sugerido]);
  const perform = async (action: () => Promise<MolcyInstallation>, refresh = false) => {
    setPending(true); setError(null);
    try { setStatus(await action()); if (refresh) await onChanged(); }
    catch (e) { setError((e as Error).message); }
    finally { setPending(false); }
  };
  const installing = status?.estado === "instalando";
  const disabled = pending || busy || installing;
  // Abierta sólo si lo que falla es de configuración; si falta Blender o Molecular Nodes, la acción está en el estudio.
  const abierta = Boolean(renderer && !renderer.disponible && !FALTA_PARA_EL_PAQUETE.has(renderer.motivo_codigo ?? ""));
  return <details className="mt-4 border border-[var(--border)] p-3 text-xs leading-5" open={abierta}>
    <summary className="cursor-pointer font-semibold">{t("cy_setup")}</summary>
    <p className="mt-3">{t("cy_setup_hint")}</p>
    <p className="mt-2 break-all text-[var(--text-muted)]">{status?.ruta}</p>
    <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={t("cy_setup")}>
      {(["administrado", "existente"] as const).map(id => <button type="button" key={id} aria-pressed={mode === id}
        disabled={disabled} onClick={() => setMode(id)} className="border border-[var(--border)] px-3 py-2 disabled:opacity-50">
        {t(id === "administrado" ? "cy_managed" : "cy_existing")}
      </button>)}
    </div>
    {mode === "existente" && (encontrados.length > 0
      ? <label className="mt-3 block">{t("cy_detected")}
        <select data-testid="blender-encontrado" value={encontrados.some(e => e.ruta === blender) ? blender ?? "" : ""} disabled={disabled}
          onChange={e => setBlender(e.target.value)} className="mt-1 w-full border border-[var(--border)] bg-[var(--bg)] p-2">
          <option value="">{t("cy_detected_other")}</option>
          {encontrados.map(e => <option key={e.ruta} value={e.ruta} disabled={e.apto === false}>
            {`${t(`cy_origin_${e.origen}`)} · ${e.version ?? t("cy_version_unknown")}${e.apto === false ? ` (${t("cy_too_old")})` : ""} — ${e.ruta}`}
          </option>)}
        </select>
      </label>
      : <p className="mt-3 text-[var(--text-muted)]" data-testid="sin-blender-encontrado">{t("cy_detected_none")}</p>)}
    {mode === "existente" && <label className="mt-3 block">{t("cy_blender_path")}
      <input value={blender ?? ""} disabled={disabled} onChange={e => setBlender(e.target.value)}
        className="mt-1 w-full border border-[var(--border)] bg-[var(--bg)] p-2" />
    </label>}
    {/* No hay campo para elegir motor: el cierre de MolDesign (la firma al final de todo video) lo pone el motor incluido. */}
    {renderer?.motor_incluido === false && <p className="mt-3 text-red-400" role="alert">{t("cy_engine_missing")}</p>}
    {renderer?.motor_incluido === true && <p className="mt-3" data-testid="motor-incluido">{t("cy_engine_included")}</p>}
    <button type="button" disabled={disabled || mode === null || (mode === "existente" && !blender)}
      onClick={() => mode && perform(() => configurarMolcy({ modo: mode, blender: mode === "existente" ? blender : null, motor: null }), true)}
      className="mt-3 border border-[var(--accent-strong)] px-3 py-2 disabled:opacity-50">{t("cy_save_setup")}</button>
    <button type="button" disabled={pending || installing || busy} onClick={() => perform(instalacionMolcy, true)}
      className="ml-2 mt-3 border border-[var(--border)] px-3 py-2 disabled:opacity-50">{t("cy_recheck")}</button>
    {error && <p role="alert" className="mt-2 text-red-400">{error}</p>}
  </details>;
}
