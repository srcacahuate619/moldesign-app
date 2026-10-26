"use client";

// =====================================================================
// Los chips que declaran qué se sabe del sitio de unión de un receptor
// =====================================================================
//
// Viven en un componente compartido a propósito. El catálogo de receptores y la
// pestaña de Evaluación tienen que decir EXACTAMENTE lo mismo sobre el mismo
// receptor: si una superficie dice «Interfaz B·A» y la otra calla, el
// investigador no sabe cuál creer, y la que calla es la que engaña.
//
// Qué declara cada chip, en orden de importancia para quien va a leer un número:
//
//   1. Qué cadenas forman el sitio, y en ámbar cuando son varias y sólo se
//      prepara una — ahí es donde la afinidad sale de media cavidad.
//   2. Si la anotación está respaldada por un cristal o sólo por volumen.
//   3. De dónde salen los hotspots, cuando no son los que el receptor traía.
//
// Ninguno de los tres se inventa nada: los mide
// `scripts/expediente_de_receptores.py` sobre el PDB del RCSB y viajan con el
// catálogo.
//
import type { Target } from "../../lib/api";
import { useLanguage } from "../../context/LanguageContext";
import { describirSitio, avisoDeEvidencia, describirHotspots } from "../../lib/sitioDelReceptor";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useScrollLock } from "../../hooks/useScrollLock";
import styles from "./DetalleDelSitio.module.css";

type Props = {
  target: Pick<Target,
    "pdb_id" | "name" | "site_chains" | "site_chain_atoms" | "site_evidence" | "site_ligand" | "chain" | "hotspots_source">;
  /** `compacto` para la tarjeta del catálogo; `linea` para la barra de Evaluación. */
  variante?: "compacto" | "linea";
  /** El resumen expandible de Evaluación ya declara las cadenas del sitio. */
  mostrarEtiquetaDelSitio?: boolean;
};

export function ChipsDelSitio({ target, variante = "compacto", mostrarEtiquetaDelSitio = true }: Props) {
  const { locale } = useLanguage();
  const idioma = locale.toLowerCase().startsWith("en") ? "en" : "es";
  const sitio = describirSitio(target, idioma);
  const aviso = avisoDeEvidencia(target, idioma);
  const hs = describirHotspots(target, idioma);
  const base = "max-w-full font-sans px-2 py-0.5 rounded border";
  const tam = variante === "linea" ? "text-sm" : "text-xs";

  if (!mostrarEtiquetaDelSitio && !aviso && !hs.etiqueta) return null;

  const Contenedor = variante === "linea" ? "span" : "div";

  return (
    <Contenedor className="flex max-w-full flex-wrap items-center gap-1.5">
      {mostrarEtiquetaDelSitio && <span
        title={`${sitio.detalle}\n\n${hs.detalle}`}
        className={`${base} ${tam} ${
          sitio.tono === "aviso"
            ? "text-amber-300 bg-amber-950/25 border-amber-500/30"
            : sitio.tono === "sin_medir"
              ? "text-zinc-400 bg-zinc-950 border-dashed border-zinc-700"
              : "text-zinc-300 bg-zinc-950 border-zinc-800"
        }`}
      >
        {sitio.etiqueta}
      </span>}

      {aviso && (
        <span
          title={sitio.detalle}
          className={`${base} ${tam} border-dashed border-zinc-700 bg-zinc-950 text-zinc-400`}
        >
          {aviso}
        </span>
      )}

      {hs.etiqueta && <AyudaDeHotspots target={target} etiqueta={hs.etiqueta} detalle={hs.detalle} />}
    </Contenedor>
  );
}

/** Todas las vistas del chip comparten la misma ayuda y el mismo diálogo del sitio. */
function AyudaDeHotspots({ target, etiqueta, detalle }: {
  target: Pick<Target, "pdb_id" | "name">;
  etiqueta: string;
  detalle: string;
}) {
  const { t } = useLanguage();
  const [abierto, setAbierto] = useState(false);
  const botonRef = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDialogElement>(null);
  const presionadoFuera = useRef(false);
  const id = useId();
  useScrollLock(abierto);

  useEffect(() => {
    if (!abierto) return;
    const modal = modalRef.current;
    const boton = botonRef.current;
    modal?.showModal();
    return () => {
      if (modal?.open) modal.close();
      if (boton?.isConnected) boton.focus({ preventScroll: true });
    };
  }, [abierto]);

  function fueraDelPanel(event: React.MouseEvent<HTMLDialogElement> | React.PointerEvent<HTMLDialogElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
  }

  return <>
    <button
      ref={botonRef}
      type="button"
      className={`${styles.trigger} ${styles.hotspotTrigger}`}
      data-hotspot-help
      aria-label={`${t("c_que_significa")}: ${etiqueta}`}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      aria-controls={abierto ? `${id}-dialog` : undefined}
      onClick={() => setAbierto(true)}
    >
      <span className={styles.chip}>
        <span>{etiqueta}</span>
        <span className={styles.question} aria-hidden="true">?</span>
      </span>
    </button>
    {abierto && createPortal(
      <dialog
        ref={modalRef}
        id={`${id}-dialog`}
        className={styles.dialog}
        aria-labelledby={`${id}-title`}
        aria-describedby={`${id}-detail`}
        onCancel={() => setAbierto(false)}
        onClose={() => setAbierto(false)}
        onPointerDown={event => { presionadoFuera.current = fueraDelPanel(event); }}
        onClick={event => {
          if (presionadoFuera.current && fueraDelPanel(event)) setAbierto(false);
          presionadoFuera.current = false;
        }}
      >
        <header className={styles.header}>
          <div>
            <h2 id={`${id}-title`}>{t("cat_hotspot_provenance")}</h2>
            <p>{target.pdb_id} · {target.name}</p>
          </div>
          <button type="button" autoFocus onClick={() => setAbierto(false)} aria-label={t("c_cerrar")}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className={styles.body}>
          <p id={`${id}-detail`} className={styles.summary}>{detalle}</p>
        </div>
      </dialog>, document.body,
    )}
  </>;
}

export default ChipsDelSitio;
