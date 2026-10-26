"use client";

import { useId, useRef, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { useCatalogoDeReceptores } from "@/hooks/useCatalogoDeReceptores";
import type { MolcySource } from "@/lib/molcy";
import { seccionPorPdbId, type SeccionCatalogo } from "@/lib/seccionCatalogo";
import { CLAVE_DE_SECCION, SeccionDelCatalogo, EvidenciaDelCatalogo } from "@/components/science/SeccionDelCatalogo";
import { IntentosPublicados } from "@/components/science/IntentosDeVerificacion";

const PESTANAS: readonly SeccionCatalogo[] = ["demostracion", "verificado", "propios"];

/** Usa las fuentes de Molcy para conservar exactamente su disponibilidad. */
export function CatalogoReceptoresMolcy({ sources, selected, onSelect, onUpload }: { sources: readonly MolcySource[]; selected: string; onSelect: (id: string) => void; onUpload: () => void }) {
  const { t } = useLanguage();
  const catalogo = useCatalogoDeReceptores();
  const [busqueda, setBusqueda] = useState("");
  const [seccionActiva, setSeccionActiva] = useState<SeccionCatalogo>("demostracion");
  const botones = useRef<Partial<Record<SeccionCatalogo, HTMLButtonElement | null>>>({});
  const id = useId();
  const seccionDe = (source: MolcySource) => source.propio ? "propios" : seccionPorPdbId(source.id, catalogo);
  const coincide = (source: MolcySource) => `${source.nombre} ${source.id}`.toLocaleLowerCase().includes(busqueda.trim().toLocaleLowerCase());
  const etiqueta = (seccion: SeccionCatalogo) => t(seccion === "propios" ? "cy_catalog_own" : CLAVE_DE_SECCION[seccion]);
  return <div className="mt-4 space-y-5">
    <label htmlFor={id} className="block text-sm font-semibold">{t("z_buscar_receptor")}</label>
    <input id={id} type="search" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} className="min-h-11 w-full border border-[var(--border-light)] bg-[var(--bg-secondary)] px-3 text-sm" />
    <div role="tablist" aria-label={t("cat_secciones_aria")} className="grid grid-cols-3 gap-1 border-b border-[var(--border)] pb-2">
      {PESTANAS.map((seccion, index) => <button
        key={seccion}
        ref={(element) => { botones.current[seccion] = element; }}
        type="button"
        role="tab"
        id={`${id}-tab-${seccion}`}
        aria-controls={`${id}-panel-${seccion}`}
        aria-selected={seccionActiva === seccion}
        tabIndex={seccionActiva === seccion ? 0 : -1}
        onClick={() => setSeccionActiva(seccion)}
        onKeyDown={(event) => {
          let siguiente: number;
          if (event.key === "ArrowRight") siguiente = (index + 1) % PESTANAS.length;
          else if (event.key === "ArrowLeft") siguiente = (index - 1 + PESTANAS.length) % PESTANAS.length;
          else if (event.key === "Home") siguiente = 0;
          else if (event.key === "End") siguiente = PESTANAS.length - 1;
          else return;
          event.preventDefault();
          setSeccionActiva(PESTANAS[siguiente]);
          botones.current[PESTANAS[siguiente]]?.focus();
        }}
        className={`min-h-11 min-w-0 border px-2 py-2 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${seccionActiva === seccion ? "border-[var(--accent)] bg-[var(--bg-secondary)] text-[var(--text)]" : "border-transparent text-[var(--text-secondary)] hover:border-[var(--border-light)] hover:text-[var(--text)]"}`}
      >{etiqueta(seccion)}</button>)}
    </div>
    {PESTANAS.map((seccion) => {
      const miembros = sources.filter((source) => seccionDe(source) === seccion);
      const visibles = miembros.filter(coincide);
      const otras = PESTANAS.filter((otra) => {
        return otra !== seccion && sources.some((source) => seccionDe(source) === otra && coincide(source));
      });
      return <div key={seccion} role="tabpanel" id={`${id}-panel-${seccion}`} aria-labelledby={`${id}-tab-${seccion}`} hidden={seccionActiva !== seccion} tabIndex={0} className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]">
        {seccionActiva === seccion && <SeccionDelCatalogo seccion={seccion} vacia={miembros.length === 0} onUpload={onUpload} intentos={seccion === "verificado" && <IntentosPublicados targets={(catalogo ?? []).filter(row => `${row.name} ${row.pdb_id}`.toLocaleLowerCase().includes(busqueda.trim().toLocaleLowerCase()))} />}>
          {busqueda.trim() && visibles.length === 0 && <p role="status" className="text-sm leading-6 text-[var(--text-secondary)]">
            {t("cat_busqueda_sin_resultados")}
            {otras.length > 0 && <> {t("cat_busqueda_en_otras", { secciones: otras.map(etiqueta).join(", ") })}</>}
          </p>}
          <div className="max-h-64 space-y-3 overflow-y-auto">
            {visibles.map((source) => {
              const target = catalogo?.find((row) => row.pdb_id.toUpperCase() === source.id.toUpperCase());
              return <div key={source.id} className="space-y-2 border border-[var(--border)] p-3">
                <button type="button" disabled={!source.disponible} aria-pressed={selected === source.id} onClick={() => onSelect(source.id)} className="min-h-11 w-full text-left text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60">{source.nombre} · {source.id}</button>
                {target && <EvidenciaDelCatalogo target={target} />}
                {source.motivo && <p className="text-sm leading-6">{source.motivo}</p>}
              </div>;
            })}
          </div>
        </SeccionDelCatalogo>}
      </div>;
    })}
  </div>;
}
