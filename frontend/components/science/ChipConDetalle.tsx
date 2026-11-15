"use client";

// Una etiqueta que guarda su explicación detrás de un clic. Mismo patrón y mismos
// estilos que la etiqueta «Sitio: …» (DetalleDelSitio): el resultado muestra sólo
// el rótulo y quien quiere el detalle lo abre en un diálogo modal.

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { useScrollLock } from "../../hooks/useScrollLock";
import styles from "./DetalleDelSitio.module.css";

export function ChipConDetalle({ etiqueta, titulo, subtitulo, resumen, children, aviso = false }: {
  etiqueta: ReactNode;
  titulo: string;
  subtitulo?: string;
  /** Primera línea del diálogo, en grande. */
  resumen?: ReactNode;
  children: ReactNode;
  /** Ámbar: el detalle contiene algo que el lector debe ver. */
  aviso?: boolean;
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
      className={styles.trigger}
      data-site-has-notices={aviso}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      aria-controls={abierto ? id : undefined}
      onClick={() => setAbierto(true)}
    >
      <span className={styles.chip}><span>{etiqueta}</span></span>
    </button>
    {abierto && createPortal(
      <dialog
        ref={modalRef}
        id={id}
        className={styles.dialog}
        aria-labelledby={`${id}-title`}
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
            <h2 id={`${id}-title`}>{titulo}</h2>
            {subtitulo && <p>{subtitulo}</p>}
          </div>
          <button type="button" autoFocus onClick={() => setAbierto(false)} aria-label={t("c_cerrar")}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className={styles.body}>
          {resumen && <p className={styles.summary}>{resumen}</p>}
          {children}
        </div>
      </dialog>, document.body,
    )}
  </>;
}
