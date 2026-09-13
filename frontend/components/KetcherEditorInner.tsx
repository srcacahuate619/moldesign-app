"use client";

/**
 * Inner Ketcher Editor component.
 *
 * This is loaded dynamically (no SSR) by KetcherEditor.tsx because:
 * - Ketcher uses browser-only APIs (DOM, Web Workers, WASM)
 * - The Indigo WASM module cannot run in Node.js
 *
 * Ketcher is developed by EPAM Systems under Apache 2.0 License.
 * https://github.com/epam/ketcher
 */

import { useEffect, useRef, useState } from "react";

import { Editor } from "ketcher-react";
import { StandaloneStructServiceProvider } from "ketcher-standalone";
import type { Ketcher } from "ketcher-core";

// El CSS de Ketcher NO se importa aqui. Ver `app/layout.tsx`.
//
// EL FALLO QUE ARREGLA. Este archivo se carga con `next/dynamic`, asi que
// importar aqui su hoja la manda a un chunk CSS aparte (174 KB) que el HTML
// exportado NO enlaza: dependia de que Webpack inyectara el <link> en tiempo
// de ejecucion, ya dentro del WebView. En el export estatico de Tauri eso
// dejo a Ketcher pintando sin estilos, con un SVG de la interfaz creciendo
// hasta ocupar todo el lienzo: la figura diagonal de la primera build.
//
// El JavaScript, el worker y el WASM de Indigo SIGUEN siendo carga dinamica,
// que es lo que de verdad hay que diferir. Una hoja de estilos cuesta poco y
// no puede permitirse llegar tarde.

type Props = {
  initialSmiles?: string;
  onSmilesChange?: (smiles: string) => void;
  height?: number | string;
};

// Singleton service provider — reused across remounts
let structServiceProvider: StandaloneStructServiceProvider | null = null;

function getStructServiceProvider() {
  if (!structServiceProvider) {
    structServiceProvider = new StandaloneStructServiceProvider();
  }
  return structServiceProvider;
}

export default function KetcherEditorInner({
  initialSmiles,
  onSmilesChange,
  height = 750,
}: Props) {
  const ketcherRef = useRef<Ketcher | null>(null);
  const [ready, setReady] = useState(false);
  const lastReportedSmiles = useRef<string | null>(null);

  // When Ketcher initializes, store the instance and load initial SMILES
  const handleInit = async (ketcher: Ketcher) => {
    ketcherRef.current = ketcher;
    
    // Enable valency error display and other "free" drawing settings
    ketcher.setSettings({
      "valency-error-display": true,
      "ignore-stereochemistry-errors": true,
      "smart-layout": true,
      "disable-check-on-save": true
    });

    // No se habilita el sondeo hasta que la molécula inicial terminó de
    // cargarse. Ketcher puede responder vacío durante setMolecule(); tratar ese
    // estado transitorio como una edición borraba el ligando persistido.

    // On mobile, Ketcher internally focuses an input after mounting which
    // triggers the virtual keyboard. We explicitly blur it away.
    setTimeout(() => {
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
    }, 100);

    if (initialSmiles) {
      try {
        lastReportedSmiles.current = initialSmiles;
        await ketcher.setMolecule(initialSmiles);
      } catch (e) {
        console.warn("Ketcher: could not load initial SMILES", e);
      }
    }
    setReady(true);
  };

  // Periodically sync SMILES from Ketcher to parent (debounced)
  useEffect(() => {
    if (!ready || !ketcherRef.current || !onSmilesChange) return;

    const interval = setInterval(async () => {
      try {
        if (ketcherRef.current) {
          const smiles = await ketcherRef.current.getSmiles();
          if (smiles !== undefined && smiles !== lastReportedSmiles.current) {
            lastReportedSmiles.current = smiles;
            onSmilesChange(smiles);
          }
        }
      } catch {
        // Una excepción no demuestra que el usuario vació el lienzo: también
        // ocurre mientras Ketcher recalcula o carga una estructura. El borrado
        // real llega como una respuesta válida `""` de getSmiles().
      }
    }, 500); // Slightly slower interval to feel less "jittery"

    return () => clearInterval(interval);
  }, [ready, onSmilesChange]);

  const isProcessing = useRef(false);
  const pendingSmiles = useRef<string | null>(null);

  // Internal function to handle the heavy lifting
  const syncToKetcher = async (smiles: string) => {
    if (!ready || !ketcherRef.current) return;
    
    if (isProcessing.current) {
      pendingSmiles.current = smiles;
      return;
    }

    try {
      let current = "";
      try {
        current = await ketcherRef.current.getSmiles();
      } catch (e) {
        // If it throws, the canvas is empty
        current = "";
      }

      if (current !== smiles) {
        // We only proceed if it's empty or looks like a valid SMILES 
        // (simple heuristic: balanced parentheses and numbers)
        const isPotentiallyValid = smiles === "" || (
            (smiles.match(/\(/g) || []).length === (smiles.match(/\)/g) || []).length
        );

        if (isPotentiallyValid) {
            isProcessing.current = true;
            lastReportedSmiles.current = smiles;
            await ketcherRef.current.setMolecule(smiles);
        }
      }
    } catch (e) {
      // Invalid SMILES during typing - ignore
    } finally {
      isProcessing.current = false;
      // If a new request came in while we were busy, process the LATEST one now
      if (pendingSmiles.current !== null) {
        const next = pendingSmiles.current;
        pendingSmiles.current = null;
        syncToKetcher(next);
      }
    }
  };

  // Sync external SMILES changes to Ketcher (ONLY if they didn't originate from Ketcher)
  useEffect(() => {
    if (ready && ketcherRef.current && initialSmiles !== undefined) {
      if (initialSmiles === lastReportedSmiles.current) return;

      const timeout = setTimeout(() => {
        syncToKetcher(initialSmiles);
      }, 50); // Fast 50ms debounce

      return () => clearTimeout(timeout);
    }
  }, [initialSmiles, ready]);

  return (
    <div
      className="ketcher-wrapper rounded-xl border border-zinc-800"
      style={{ height: height || 750, position: "relative", overflow: "hidden", maxWidth: "100%" }}
    >
      <Editor
        staticResourcesUrl=""
        structServiceProvider={getStructServiceProvider()}
        onInit={handleInit}
        errorHandler={(message: string) => {
          // Log but don't block
          console.debug("Ketcher notice:", message);
        }}
      />
    </div>
  );
}
