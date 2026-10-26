"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useScrollLock } from "@/hooks/useScrollLock";
import styles from "./DetalleDelSitio.module.css";
// =====================================================================
// El detalle abrible del sitio de unión — para quien acaba de llegar
// =====================================================================
//
// EL FALLO QUE ARREGLA. Todo lo que sabíamos del sitio de un receptor vivía en
// el atributo `title` de un chip de 10 px. Eso exige acertarle con el ratón y
// esperar, NO existe en táctil, y como el chip es un `<span>` sin foco, con
// teclado no se alcanza nunca. La frase que más importa —«el ligando acoplará
// contra parte de la cavidad»— estaba enterrada ahí, y le aplica a 110 de los
// 380 receptores del catálogo.
//
// EN EL CATÁLOGO SE CONSERVA `<details>`. Es el elemento que el
// navegador ya sabe abrir y cerrar: recibe foco, responde a Enter y a Espacio,
// funciona con un toque, se anuncia solo a un lector de pantalla y el buscador
// del navegador (Ctrl+F) encuentra su contenido aunque esté cerrado. Cualquier
// versión hecha sólo con `useState` y `div` necesitaría mantener estas
// garantías. Evaluación usa, por decisión del propietario, una etiqueta que
// abre un `<dialog>` nativo: foco modal, fondo inerte y Escape del navegador.
//
// QUÉ NO HACE. No sustituye al chip corto: quien ya sabe lo que es una interfaz
// no necesita leer un párrafo cada vez que abre el catálogo. Esto es lo que
// aparece SI decides abrirlo.

import { ChevronDown, Info, TriangleAlert, X } from "lucide-react";

import type { Target } from "../../lib/api";
import { describirSitio, explicarSitio } from "../../lib/sitioDelReceptor";

type Props = {
  target: Pick<Target,
    "pdb_id" | "name" | "organism" | "resolution" | "chain" | "site_chains"
    | "site_chain_atoms" | "site_evidence" | "site_ligand" | "hotspots" | "hotspots_source">;
  /** Abierto de entrada. Para la ficha ampliada; en una tarjeta, cerrado. */
  abiertoPorDefecto?: boolean;
  /** Evaluación usa una etiqueta con modal; el catálogo conserva su desplegable. */
  variante?: "desplegable" | "etiqueta";
};

export function DetalleDelSitio({ target, abiertoPorDefecto = false, variante = "desplegable" }: Props) {
  const { t, locale } = useLanguage();
  const explicacion = explicarSitio(target, locale.toLowerCase().startsWith("en") ? "en" : "es");
  // Las secciones que advierten se cuentan para poder decirlo en el resumen:
  // quien no abra el detalle merece saber que hay algo dentro que le afecta.
  const avisos = explicacion.secciones.filter((s) => s.tono === "aviso").length;

  if (variante === "etiqueta") {
    return <EtiquetaDelSitio target={target} explicacion={explicacion} avisos={avisos} />;
  }

  return (
    <details
      open={abiertoPorDefecto}
      className="group rounded-xl border border-zinc-800 bg-zinc-950/60 open:border-zinc-700"
    >
      <summary
        className="flex cursor-pointer list-none items-center gap-2 rounded-xl px-3 py-2 text-left
                   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
                   focus-visible:outline-purple-400 hover:bg-zinc-900/60"
      >
        {avisos > 0 ? (
          <TriangleAlert size={14} className="shrink-0 text-amber-300" aria-hidden="true" />
        ) : (
          <Info size={14} className="shrink-0 text-purple-400" aria-hidden="true" />
        )}
        <span className="min-w-0 flex-1 text-sm leading-5 text-zinc-200">
          {explicacion.titular}
        </span>
        <span className="shrink-0 font-sans text-sm font-bold uppercase tracking-wider text-zinc-400">
          {t("c_que_significa")}
        </span>
        <ChevronDown
          size={14}
          aria-hidden="true"
          className="shrink-0 text-zinc-400 transition-transform group-open:rotate-180"
        />
      </summary>

      <div className="space-y-3 border-t border-zinc-800 px-3 pb-3 pt-3">
        {explicacion.secciones.map((seccion) => (
          <section key={seccion.pregunta}>
            <h4
              className={`text-base font-bold leading-5 ${
                seccion.tono === "aviso" ? "text-amber-200" : "text-zinc-200"
              }`}
            >
              {seccion.pregunta}
            </h4>
            <p
              className={`mt-0.5 text-base leading-6 font-sans ${
                seccion.tono === "aviso" ? "text-amber-100" : "text-zinc-400"
              }`}
            >
              {seccion.respuesta}
            </p>
          </section>
        ))}
      </div>
    </details>
  );
}

export default DetalleDelSitio;

function EtiquetaDelSitio({ target, explicacion, avisos }: {
  target: Props["target"];
  explicacion: ReturnType<typeof explicarSitio>;
  avisos: number;
}) {
  const { t, locale } = useLanguage();
  const [abierto, setAbierto] = useState(false);
  const botonRef = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDialogElement>(null);
  const presionadoFuera = useRef(false);
  const id = useId();
  const sitio = describirSitio(target, locale.toLowerCase().startsWith("en") ? "en" : "es");
  const etiqueta = sitio.tono === "sin_medir" ? sitio.etiqueta : t("rr_site_badge", { site: sitio.etiqueta });
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
      className={styles.trigger}
      data-binding-site-badge
      data-site-has-notices={avisos > 0}
      aria-label={`${t("c_que_significa")}: ${explicacion.titular}${avisos > 0 ? ` · ${t("rr_site_review")}` : ""}`}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      aria-controls={abierto ? id : undefined}
      onClick={() => setAbierto(true)}
    >
      <span className={styles.chip}>
        {avisos > 0 && <TriangleAlert size={14} aria-hidden="true" />}
        <span>{etiqueta}</span>
        {avisos > 0 && <span className={styles.review}>{t("rr_site_review")}</span>}
        <span className={styles.question} aria-hidden="true">?</span>
      </span>
    </button>
    {abierto && createPortal(
      <dialog
        ref={modalRef}
        id={id}
        className={styles.dialog}
        aria-labelledby={`${id}-title`}
        aria-describedby={`${id}-summary`}
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
            <h2 id={`${id}-title`}>{t("rr_site_title")}</h2>
            <p>{target.pdb_id} · {target.name}</p>
          </div>
          <button type="button" autoFocus onClick={() => setAbierto(false)} aria-label={t("c_cerrar")}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className={styles.body}>
          <p id={`${id}-summary`} className={styles.summary}>{explicacion.titular}</p>
          {explicacion.secciones.map(seccion => <section key={seccion.pregunta} data-site-section data-tone={seccion.tono ?? "neutro"}>
            <h3>{seccion.pregunta}</h3>
            <p>{seccion.respuesta}</p>
          </section>)}
        </div>
      </dialog>, document.body,
    )}
  </>;
}
