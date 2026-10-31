"use client";


import { useLanguage } from "@/context/LanguageContext";
import { createPortal } from "react-dom";
// =====================================================================
// Ayuda — el "?" que desactiva una lectura equivocada
// =====================================================================
//
// PARA QUÉ EXISTE. Este producto se apoya en distinciones que un usuario no
// tiene por qué conocer y que, mal leídas, invierten la conclusión: «revisión»
// no es «aprobado», el margen del selector no es una probabilidad, una afinidad
// de Vina no es energía libre, y un ensemble no compra precisión. Cada una de
// esas frases cabe en dos líneas; sin ellas, la interfaz es correcta y aun así
// se malinterpreta.
//
// POR QUÉ NO `title=`. El tooltip nativo del navegador no se alcanza con
// teclado, no lo anuncia un lector de pantalla, y en el WebView2 que embebe la
// aplicación tarda cientos de milisegundos en aparecer. Una explicación que
// sólo ve quien ya sabe dónde poner el ratón no explica nada.
//
// DECISIONES DE COMPORTAMIENTO:
//   · se abre con click o Enter/Espacio (es un `<button>` nativo);
//   · se cierra con Escape y devolviendo el foco al botón, que es lo que
//     espera quien navega con teclado;
//   · se cierra al hacer click fuera;
//   · el contenido va en un `role="dialog"` etiquetado por su título, para que
//     un lector de pantalla anuncie de qué es la ayuda y no sólo «diálogo».

import { useEffect, useId, useRef, useState } from "react";
import { HelpCircle, X } from "lucide-react";

export interface AyudaProps {
  /** Título corto: nombra QUÉ se explica. */
  readonly titulo: string;
  /** El cuerpo. Dos o tres frases; si necesita más, el sitio es la documentación. */
  readonly children: React.ReactNode;
  /** Etiqueta accesible del botón. Sin ella todos se llamarían "Ayuda". */
  readonly etiqueta?: string;
  readonly className?: string;
}

export function Ayuda({ titulo, children, etiqueta, className = "" }: AyudaProps) {
  const { t } = useLanguage();
  const [abierto, setAbierto] = useState(false);
  const [posicion, setPosicion] = useState<{ top: number; left: number } | null>(null);
  const panelId = useId();
  const botonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) {
      setPosicion(null);
      return;
    }

    const recolocar = () => {
      const boton = botonRef.current;
      const panel = panelRef.current;
      if (!boton || !panel) return;

      const rectBoton = boton.getBoundingClientRect();
      const rectPanel = panel.getBoundingClientRect();
      const anchoViewport = document.documentElement.clientWidth || window.innerWidth;
      const altoViewport = document.documentElement.clientHeight || window.innerHeight;
      const margen = 12;
      const separacion = 8;

      let left = rectBoton.left + rectBoton.width / 2 - rectPanel.width / 2;
      left = Math.max(margen, Math.min(left, anchoViewport - rectPanel.width - margen));

      let top = rectBoton.bottom + separacion;
      const maxTop = Math.max(margen, altoViewport - rectPanel.height - margen);
      if (top > maxTop && rectBoton.top - rectPanel.height - separacion >= margen) {
        top = rectBoton.top - rectPanel.height - separacion;
      } else {
        top = Math.max(margen, Math.min(top, maxTop));
      }

      setPosicion({ top, left });
    };

    recolocar();
    window.addEventListener("resize", recolocar);
    document.addEventListener("scroll", recolocar, true);
    return () => {
      window.removeEventListener("resize", recolocar);
      document.removeEventListener("scroll", recolocar, true);
    };
  }, [abierto]);

  useEffect(() => {
    if (!abierto) return;

    function alPulsarTecla(evento: KeyboardEvent) {
      if (evento.key !== "Escape") return;
      setAbierto(false);
      // Devolver el foco: sin esto, cerrar con Escape deja al usuario de
      // teclado en el principio del documento.
      botonRef.current?.focus();
    }

    function alHacerClickFuera(evento: MouseEvent) {
      const destino = evento.target as Node;
      if (panelRef.current?.contains(destino) || botonRef.current?.contains(destino)) return;
      setAbierto(false);
    }

    document.addEventListener("keydown", alPulsarTecla);
    document.addEventListener("mousedown", alHacerClickFuera);
    return () => {
      document.removeEventListener("keydown", alPulsarTecla);
      document.removeEventListener("mousedown", alHacerClickFuera);
    };
  }, [abierto]);

  return (
    <span className={`relative inline-flex ${className}`}>
      <button
        ref={botonRef}
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        aria-controls={panelId}
        aria-label={etiqueta ?? t("c_help_meaning", { title: titulo })}
        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-zinc-400 transition-colors hover:text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
      >
        <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
      </button>

      {abierto && typeof document !== "undefined" && createPortal(
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label={titulo}
          style={{
            top: posicion?.top ?? 0,
            left: posicion?.left ?? 0,
            visibility: posicion ? "visible" : "hidden",
          }}
          className="fixed z-[120] max-h-[calc(100dvh-24px)] w-[min(22rem,calc(100vw-24px))] overflow-y-auto rounded-lg border border-surface-700 bg-surface-900 p-3 shadow-xl"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="font-sans text-sm font-bold uppercase tracking-wider text-zinc-400">
              {titulo}
            </p>
            <button
              type="button"
              onClick={() => {
                setAbierto(false);
                botonRef.current?.focus();
              }}
              aria-label={t("z_cerrar_ayuda")}
              className="shrink-0 rounded text-zinc-400 transition-colors hover:text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
          <div className="mt-1.5 text-base leading-6 text-zinc-300 font-sans">{children}</div>
        </div>,
        document.body,
      )}
    </span>
  );
}
