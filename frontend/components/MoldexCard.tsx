"use client";

/* eslint-disable @next/next/no-img-element -- La URL Blob autenticada no admite optimización de Next Image. */

/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4
 * Fila de bioteca compacta: los números ausentes y el alcance del sello siguen explícitos. */

import { Translated, useLanguage } from "@/context/LanguageContext";
import { memo, useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { getApiUrl } from "../lib/config";
import { leerSello, type MoldexMolecule } from "../lib/moldex";

interface MoldexCardProps {
  molecule: MoldexMolecule;
  onClick: (id: string) => void;
  isSelected: boolean;
  onCompareToggle: (id: string) => void;
  isComparing: boolean;
}

const MoldexCard = memo(function MoldexCard({ molecule, onClick, isSelected, onCompareToggle, isComparing }: MoldexCardProps) {
  const { t } = useLanguage();
  const [imgSrc, setImgSrc] = useState<string | undefined>();

  // Sólo las filas visibles de Virtuoso solicitan su 2D. La URL temporal se
  // revoca al salir de pantalla para no retener imágenes de toda la bioteca.
  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    const headers: Record<string, string> = { "ngrok-skip-browser-warning": "true" };
    try {
      const stored = localStorage.getItem("moldesign_auth");
      const token = stored ? JSON.parse(stored).token : null;
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch { /* La petición conserva el comportamiento sin sesión. */ }

    getApiUrl()
      .then((base) => fetch(`${base}/chem/render/${molecule.id}`, { headers }))
      .then((response) => {
        if (!response.ok) throw new Error("Image fetch failed");
        return response.blob();
      })
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setImgSrc(objectUrl);
      })
      .catch(() => { if (active) setImgSrc(""); });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [molecule.id]);

  const score = molecule.metrics?.score ?? null;
  const shortName = `MDX-${molecule.target?.pdb_id || "UKN"}-${molecule.smiles_hash.substring(0, 4).toUpperCase()}`;
  const displayName = !molecule.name || molecule.name.startsWith("Ligando ") ? shortName : molecule.name;
  const seal = leerSello(molecule.blockchain);

  return (
    <article className={`group relative mb-2 border bg-[var(--bg-card)] transition-colors ${
      isSelected ? "border-[var(--accent-strong)]" : "border-[var(--border)] hover:border-[var(--border-light)]"
    }`}>
      <button
        type="button"
        onClick={() => onClick(molecule.id)}
        aria-pressed={isSelected}
        className="flex w-full cursor-pointer items-start gap-3 p-3 text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--accent-strong)]"
      >
        <div className="flex size-[76px] shrink-0 items-center justify-center overflow-hidden border border-[var(--border)] bg-white p-1">
          {imgSrc ? (
            <img src={imgSrc} alt={molecule.name || shortName} className="max-h-full max-w-full object-contain" loading="lazy" />
          ) : imgSrc === undefined ? (
            <span className="size-4 animate-spin rounded-full border-2 border-[var(--accent-strong)] border-t-transparent" aria-label={t("mx_cargando_2d")} />
          ) : (
            <span className="px-1 text-center font-mono text-[9px] text-[var(--text-dim)]"><Translated id="z_sin_vista_previa" /></span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-start justify-between gap-2">
            <span className="truncate text-sm font-semibold text-[var(--text)]" title={displayName}>{displayName}</span>
            <span className="shrink-0 border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-dim)]">{molecule.target?.pdb_id || "—"}</span>
          </div>
          <p className="truncate font-mono text-[10px] text-[var(--text-dim)]" title={molecule.smiles}>{molecule.smiles}</p>
          <div className="mt-3 flex items-end justify-between gap-2">
            <div>
              <span className="block font-mono text-[9px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("mx_indice_compuesto")}</span>
              <span className="font-display text-lg font-bold tabular-nums text-[var(--accent-strong)]">{score !== null ? score.toFixed(1) : "—"}</span>
            </div>
            {seal === "vigente" && (
              <span className="flex items-center gap-1 text-[10px] font-bold text-[var(--categoria-hallazgo)]"><ShieldCheck size={12} />{t("mx_sello_vigente")}</span>
            )}
            {(seal === "corrida-anterior" || seal === "indeterminado") && (
              <span className="flex items-center gap-1 text-[10px] font-bold text-[var(--categoria-corrigendum)]" title={seal === "corrida-anterior" ? t("mx_sello_desfasado") : t("pg_mx_sello_sin_corrida")}>
                <ShieldAlert size={12} />{seal === "corrida-anterior" ? t("mx_sello_desfasado") : t("mx_sello_indeterminado")}
              </span>
            )}
          </div>
        </div>
      </button>
      <div className="border-t border-[var(--border)] px-3 py-2">
        <button
          type="button"
          aria-pressed={isComparing}
          onClick={() => onCompareToggle(molecule.id)}
          className={`min-h-7 w-full cursor-pointer border px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.1em] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${
            isComparing
              ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)] text-[var(--accent-strong)]"
              : "border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--border-light)] hover:text-[var(--text)]"
          }`}
        >
          {isComparing ? t("auto_6f82b47554ca") : t("mx_comparar")}
        </button>
      </div>
    </article>
  );
});

export default MoldexCard;
