"use client";

import { useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { requestAuthenticatedJson } from "../lib/api";

type Ubicacion = { carpeta_datos: string; base_de_datos: string };

/**
 * Dice dónde guarda Moldex. Moldex no guarda archivos sueltos de cada ficha: guarda filas en la base SQLite local
 * y los archivos de cada corrida (poses, PDF…) en la carpeta de datos de MolDesign. No va en la carpeta del caso.
 * Se consulta sólo al desplegar, para no añadir una petición al abrir la biblioteca.
 */
export function MoldexUbicacion() {
  const { t } = useLanguage();
  const [ubicacion, setUbicacion] = useState<Ubicacion | null>(null);
  const [error, setError] = useState(false);

  const alAbrir = (abierto: boolean) => {
    if (!abierto || ubicacion) return;
    requestAuthenticatedJson<Ubicacion>("/moldex/ubicacion").then(setUbicacion).catch(() => setError(true));
  };
  const abrir = () => {
    requestAuthenticatedJson<Ubicacion>("/moldex/ubicacion/abrir", { method: "POST" }).catch(() => setError(true));
  };

  return (
    <details
      className="shrink-0 border-t border-[var(--border)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]"
      onToggle={(event) => alAbrir((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer font-semibold text-[var(--text)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]">
        {t("mx_donde_guarda")}
      </summary>
      <p className="mt-2">{t("mx_donde_guarda_detalle")}</p>
      {ubicacion && (
        <>
          <p className="mt-2 break-all font-mono text-[10px] text-[var(--text-dim)]">{ubicacion.base_de_datos}</p>
          <button
            type="button"
            onClick={abrir}
            className="mt-2 cursor-pointer border border-[var(--border)] px-3 py-2 font-semibold hover:border-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]"
          >
            {t("mx_abrir_carpeta_datos")}
          </button>
        </>
      )}
      {error && <p role="alert" className="mt-2 text-red-400">{t("mx_donde_guarda_error")}</p>}
    </details>
  );
}
