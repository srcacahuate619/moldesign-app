"use client";

import { presentError } from "../../lib/frontendError";

import { useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { elegirCarpetaSalidaMolcy, fijarSalidaMolcy, type MolcySalida } from "@/lib/molcy";

/** Elección de este vídeo: una carpeta concreta, la ubicación por defecto, o nada (se aplica «todos» si existe). */
export type EleccionDeEsteVideo = { id: string; ruta: string } | "predeterminada" | null;

type Props = {
  salida: MolcySalida;
  esteVideo: EleccionDeEsteVideo;
  onEsteVideo: (value: EleccionDeEsteVideo) => void;
  onSalida: (value: MolcySalida) => void;
  disabled?: boolean;
};

/**
 * Carpeta de salida OPCIONAL. Lo habitual (guardar en Moldex → Molcy → generar) no pasa por aquí: el vídeo va al
 * caso o a los datos de MolDesign. Esto sólo existe para quien quiere otra carpeta u otro disco, «para todos los
 * vídeos» o «sólo para éste».
 */
export function OutputFolder({ salida, esteVideo, onEsteVideo, onSalida, disabled }: Props) {
  const { t } = useLanguage();
  const [pendiente, setPendiente] = useState<{ id: string; display_path: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!salida.disponible) return null;

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try { await action(); }
    catch (e) { setError(presentError((e as Error), t) || t("cy_out_error")); }
    finally { setBusy(false); }
  };
  const choose = () => run(async () => {
    const picked = await elegirCarpetaSalidaMolcy();
    if (picked) setPendiente(picked);
  });
  const forAll = () => run(async () => {
    if (!pendiente) return;
    onSalida(await fijarSalidaMolcy(pendiente.id));
    onEsteVideo(null);
    setPendiente(null);
  });
  const forThis = () => {
    if (!pendiente) return;
    onEsteVideo({ id: pendiente.id, ruta: pendiente.display_path });
    setPendiente(null);
  };
  const resetGlobal = () => run(async () => { onSalida(await fijarSalidaMolcy(null)); });
  const boton = "border border-[var(--border)] px-3 py-2 text-xs font-semibold hover:border-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]";

  return (
    <section aria-labelledby="molcy-out-title" className="mt-4 border border-[var(--border)] p-3 text-xs leading-5">
      <h3 id="molcy-out-title" className="font-semibold">{t("cy_out_title")}</h3>
      <p className="mt-1 break-all text-[var(--text-secondary)]" data-testid="molcy-out-estado">
        {esteVideo === "predeterminada" ? t("cy_out_this_default")
          : esteVideo ? t("cy_out_this", { path: esteVideo.ruta })
          : salida.global ? t("cy_out_global", { path: salida.global.ruta })
          : t("cy_out_default")}
      </p>
      {salida.problema && !esteVideo && <p role="alert" className="mt-1 text-red-400">{t("cy_out_problem", { reason: salida.problema })}</p>}
      {pendiente ? (
        <div className="mt-2">
          <p className="break-all">{t("cy_out_picked", { path: pendiente.display_path })}</p>
          <p className="mt-1 text-[var(--text-muted)]">{t("cy_out_subfolder")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" className={boton} disabled={busy || disabled} onClick={forAll}>{t("cy_out_for_all")}</button>
            <button type="button" className={boton} disabled={busy || disabled} onClick={forThis}>{t("cy_out_for_this")}</button>
            <button type="button" className={boton} disabled={busy} onClick={() => setPendiente(null)}>{t("cy_out_cancel")}</button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" className={boton} disabled={busy || disabled} onClick={choose}>{t("cy_out_choose")}</button>
          {salida.global && !esteVideo && <button type="button" className={boton} disabled={busy || disabled} onClick={resetGlobal}>{t("cy_out_reset_global")}</button>}
          {salida.global && !esteVideo && <button type="button" className={boton} disabled={busy || disabled} onClick={() => onEsteVideo("predeterminada")}>{t("cy_out_default_once")}</button>}
          {esteVideo && <button type="button" className={boton} disabled={busy || disabled} onClick={() => onEsteVideo(null)}>{t("cy_out_undo_this")}</button>}
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-red-400">{error}</p>}
    </section>
  );
}
