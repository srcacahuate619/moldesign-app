"use client";

// =====================================================================
// Enlace externo — el unico que deben usar los componentes
// =====================================================================
//
// Sustituye a `<a href={...} target="_blank">`, que dentro del webview de Tauri
// no hace NADA: no hay navegador que abra una pestana, y el clic se perdia en
// silencio. Este componente delega en `lib/openExternal`, que es la frontera
// que decide como se abre algo hacia fuera.
//
// Sigue renderizando un `<a>` con su `href` real, a proposito: el menu
// contextual del navegador, «copiar direccion del enlace», los lectores de
// pantalla y el estilo de enlace visitado dependen de que el `href` este ahi.
// Lo que se intercepta es el CLIC, no la semantica.
//
// NO usar para rutas internas (`/moldex`, `#seccion`), blobs ni descargas: ahi
// el enlace debe navegar por si mismo. `esExterno()` decide, y si el destino no
// es externo este componente se aparta y deja pasar el clic.

import { useCallback, useState, type AnchorHTMLAttributes, type ReactNode } from "react";

import { esExterno, openExternal } from "@/lib/openExternal";
import { isDesktopRuntime } from "@/lib/tauri";

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "onClick"> & {
  href: string;
  children: ReactNode;
  /** Se invoca si la apertura falla. Sin esto, el error se registra en consola. */
  onError?: (error: unknown) => void;
};

export function ExternalLink({ href, children, onError, ...rest }: Props) {
  const [fallo, setFallo] = useState<string | null>(null);

  const alHacerClic = useCallback(
    (evento: React.MouseEvent<HTMLAnchorElement>) => {
      // Un destino no externo navega solo: rutas de Next.js, anclas, blobs.
      if (!esExterno(href)) return;
      // Respetar los gestos del usuario: ctrl/cmd/medio son «abrir aparte» y en
      // un navegador ya funcionan. Dentro de Tauri tampoco hacen dano porque el
      // webview los ignora igual que al target.
      if (!isDesktopRuntime() && (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.button !== 0)) return;

      evento.preventDefault();
      setFallo(null);
      void openExternal(href).catch((causa) => {
        // No se traga: se muestra al lado del enlace y se propaga a quien quiera.
        setFallo("No se pudo abrir el enlace");
        if (onError) onError(causa);
        else console.error("[ExternalLink] fallo al abrir", href, causa);
      });
    },
    [href, onError],
  );

  return (
    <>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        onClick={alHacerClic}
        {...rest}
      >
        {children}
      </a>
      {fallo ? (
        <span role="alert" className="ml-1 text-[10px] text-amber-300">
          {fallo}
        </span>
      ) : null}
    </>
  );
}

export default ExternalLink;
