"use client";

// =====================================================================
// Visor de documentos legales EMPAQUETADOS — sin red, sin salir de la app
// =====================================================================
//
// POR QUE EXISTE. El inventario de terceros, la oferta de codigo fuente y la
// licencia comercial se abrian con `<a target="_blank">`. Eso tenia dos fallos
// distintos y ambos graves:
//
//   - dentro de Tauri no hacia NADA, asi que los documentos que la licencia
//     obliga a poner a disposicion eran inalcanzables en la app instalada;
//   - en navegador, navegaba fuera y SUSTITUIA la aplicacion por un Markdown
//     crudo, perdiendo el estado de la sesion.
//
// Mandarlos al navegador del sistema tampoco sirve: son assets empaquetados y
// deben poder leerse SIN RED. Se muestran aqui, dentro de la aplicacion, con
// cerrar/volver, y el estado de la app se conserva porque nunca se abandona.
//
// POR QUE TEXTO PLANO Y NO MARKDOWN RENDERIZADO. El proyecto no trae ningun
// renderizador de Markdown, y anadir uno para esto significaria meter una
// dependencia nueva —y una superficie de inyeccion— en la pantalla legal, que
// es justo donde menos interesa. El documento se muestra tal cual se
// distribuye, que ademas es lo que un texto legal debe ser: literal.

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, FileText, Loader2 } from "lucide-react";

export interface LocalDoc {
  /** Ruta del asset empaquetado, siempre relativa al propio origen. */
  path: string;
  title: string;
}

interface Props {
  doc: LocalDoc;
  onClose: () => void;
}

function esRutaDeAssetLocal(path: string): boolean {
  return path.startsWith("/") && !path.startsWith("//") && !/^[a-z][a-z\d+.-]*:/i.test(path);
}

export function LocalDocViewer({ doc, onClose }: Props) {
  const [texto, setTexto] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const botonVolver = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let vigente = true;
    setTexto(null);
    setError(null);
    // La ruta debe ser un asset absoluto del frontend. Así el visor nunca
    // convierte un documento legal en una petición a un origen externo.
    if (!esRutaDeAssetLocal(doc.path)) {
      setError("La ruta del documento legal no pertenece a los assets locales.");
      return () => {
        vigente = false;
      };
    }
    fetch(doc.path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then((t) => {
        if (vigente) setTexto(t);
      })
      .catch((causa: unknown) => {
        if (vigente) {
          setError(
            `No se pudo cargar ${doc.path}. El documento viaja con la aplicacion, `
            + `asi que esto indica un empaquetado incompleto. (${String(causa)})`,
          );
        }
      });
    return () => {
      vigente = false;
    };
  }, [doc.path]);

  useEffect(() => {
    botonVolver.current?.focus();
  }, [doc.path]);

  const alPulsarTecla = useCallback(
    (evento: React.KeyboardEvent) => {
      if (evento.key === "Escape") {
        evento.stopPropagation();
        onClose();
      }
    },
    [onClose],
  );

  return (
    <section
      className="flex h-full flex-col"
      aria-label={doc.title}
      onKeyDown={alPulsarTecla}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-white/[0.06] px-4 py-2">
        <button
          ref={botonVolver}
          type="button"
          onClick={onClose}
          className="flex min-h-8 items-center gap-1 rounded-md border border-white/[0.12] px-2 text-[11px] font-semibold text-white/75 hover:border-purple-500/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
        >
          <ArrowLeft size={12} aria-hidden="true" />
          Volver
        </button>
        <h3 className="flex items-center gap-1.5 text-[11px] font-bold text-white/85">
          <FileText size={12} aria-hidden="true" />
          {doc.title}
        </h3>
      </header>

      <div className="min-h-0 flex-1 overflow-auto px-4 py-3">
        {error ? (
          <p role="alert" className="text-[11px] text-amber-300">
            {error}
          </p>
        ) : texto === null ? (
          <p className="flex items-center gap-2 text-[11px] text-white/50">
            <Loader2 size={12} className="animate-spin" aria-hidden="true" />
            Cargando documento…
          </p>
        ) : (
          <pre className="whitespace-pre-wrap break-words font-mono text-[10.5px] leading-relaxed text-white/70">
            {texto}
          </pre>
        )}
      </div>
    </section>
  );
}

export default LocalDocViewer;
