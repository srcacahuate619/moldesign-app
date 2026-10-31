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
import { claimEditorExport, editorInstanceId, registerEditorReader, type EditorSnapshot } from "../lib/editorSnapshot";

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
  caseId?: string;
  requestedSmiles?: string;
  initialSmiles?: string;
  onSmilesChange?: (smiles: string) => void;
  height?: number | string;
  /**
   * Recibe, al iniciarse Ketcher, cómo leer su dibujo (molfile). Se lee sólo
   * cuando se pide —al abrir el visor 3D—, nunca en un temporizador: cada lectura
   * pasa por el worker de Indigo (ver la fuga del sondeo en AGENTS.md).
   */
  onLectorDelDibujo?: (leer: () => Promise<string | null>) => void;
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
  caseId,
  requestedSmiles,
  initialSmiles,
  onSmilesChange,
  height = 750,
  onLectorDelDibujo,
}: Props) {
  const ketcherRef = useRef<Ketcher | null>(null);
  const [ready, setReady] = useState(false);
  const lastReportedSmiles = useRef<string | null>(null);
  // Lo que Ketcher devuelve justo después de cargar un SMILES externo. No es una
  // edición del usuario: es su reescritura del texto, y en un macrociclo cambia
  // la molécula (`|c:…|` marca cis todos los dobles enlaces del anillo; la
  // geldanamicina tecleada E,Z,Z volvía al campo como Z,Z,Z). QA-030.
  const ecoDeKetcher = useRef<string | null>(null);

  // Mientras se carga un SMILES de fuera, el «cambio» que anuncia Ketcher es esa carga, no una edición.
  const cargando = useRef(false);
  const revision = useRef(0);
  const instance = useRef<string | null>(null);
  if (instance.current === null) instance.current = editorInstanceId();
  const currentInput = useRef(initialSmiles);
  currentInput.current = initialSmiles;
  const requestedInput = useRef(requestedSmiles);
  requestedInput.current = requestedSmiles;
  const snapshotCache = useRef<{ revision: string; molfile: string; at: number } | null>(null);
  const snapshotExpiry = useRef<ReturnType<typeof setTimeout> | null>(null);
  const snapshotPending = useRef<Promise<EditorSnapshot> | null>(null);
  const invalidarSnapshot = () => {
    revision.current += 1; snapshotCache.current = null;
    if (snapshotExpiry.current) clearTimeout(snapshotExpiry.current);
    snapshotExpiry.current = null;
  };

  const cargarEnKetcher = async (ketcher: Ketcher, smiles: string) => {
    invalidarSnapshot();
    lastReportedSmiles.current = smiles;
    ecoDeKetcher.current = null;
    cargando.current = true;
    try {
      await ketcher.setMolecule(smiles);
      try {
        ecoDeKetcher.current = await ketcher.getSmiles();
      } catch {
        ecoDeKetcher.current = null;
      }
    } finally {
      cargando.current = false;
    }
  };

  // When Ketcher initializes, store the instance and load initial SMILES
  const handleInit = async (ketcher: Ketcher) => {
    ketcherRef.current = ketcher;
    onLectorDelDibujo?.(async () => {
      try {
        return await ketcher.getMolfile();
      } catch {
        return null;
      }
    });
    
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
        await cargarEnKetcher(ketcher, initialSmiles);
      } catch (e) {
        console.warn("Ketcher: could not load initial SMILES", e);
      }
    }
    setReady(true);
  };

  // Ketcher destruye su instancia al desmontarse (un caso nuevo remonta el editor) y entonces `ketcher.editor`
  // lanza «couldn't find ketcher instance N». Un efecto que llega con la instancia ya muerta no debe tirar la
  // pantalla: se queda sin suscribir, y el cierre tampoco lanza.
  const suscribirCambios = (ketcher: Ketcher, alCambiar: () => void): (() => void) | null => {
    try {
      const suscripcion = ketcher.editor.subscribe("change", alCambiar);
      return () => { try { ketcher.editor.unsubscribe("change", suscripcion); } catch { /* instancia ya destruida */ } };
    } catch {
      return null;
    }
  };

  // Del lienzo al campo: sólo cuando Ketcher anuncia un cambio de la estructura.
  //
  // EL FALLO QUE ARREGLA (VM de 1.0.2, 2026-10-12). Esto era un `setInterval` de 500 ms que llamaba a `getSmiles()`
  // para siempre, también con la aplicación quieta y con la pestaña oculta (no se desmonta). Cada `getSmiles()` de
  // Ketcher 3.18 serializa su biblioteca de monómeros entera y la manda al worker de Indigo: 1,57 MB por mensaje, dos
  // por segundo, y esa memoria se queda en el worker, que vive en el mismo proceso que la página. Medido en Edge con
  // el export de producción: +377 MB en 2 min con la app quieta en Molcy tras una evaluación (≈11 GB por hora); con
  // los mensajes al worker bloqueados, −1,6 MB. En la VM de 10 GiB, a la hora: «This page is having a problem · Out of
  // Memory». Ketcher anuncia cada acción con historial (dibujar, borrar, pegar, abrir, deshacer y rehacer) por
  // `editor.subscribe("change")`; quieto, no se le pregunta nada.
  useEffect(() => {
    const ketcher = ketcherRef.current;
    if (!ready || !ketcher || !onSmilesChange) return;

    let vivo = true;
    let espera: ReturnType<typeof setTimeout> | undefined;
    const leer = async (reintentos: number) => {
      if (!vivo || cargando.current) return;
      try {
        const smiles = await ketcher.getSmiles();
        if (
          vivo &&
          smiles !== undefined &&
          smiles !== lastReportedSmiles.current &&
          smiles !== ecoDeKetcher.current
        ) {
          ecoDeKetcher.current = null;
          lastReportedSmiles.current = smiles;
          onSmilesChange(smiles);
        }
      } catch {
        // Una excepción no demuestra que el usuario vació el lienzo: también
        // ocurre mientras Ketcher recalcula o carga una estructura. El borrado
        // real llega como una respuesta válida `""` de getSmiles(). Como ya no
        // hay un sondeo que vuelva a preguntar, se reintenta un par de veces.
        if (vivo && reintentos > 0) espera = setTimeout(() => void leer(reintentos - 1), 500);
      }
    };
    // Un trazo genera varios cambios seguidos: se lee una vez, cuando paran.
    const alCambiar = () => {
      if (espera) clearTimeout(espera);
      espera = setTimeout(() => void leer(2), 300);
    };
    const desuscribir = suscribirCambios(ketcher, alCambiar);
    if (!desuscribir) return;
    // Lo que cambió entre la carga inicial y la suscripción.
    void leer(2);

    return () => {
      vivo = false;
      if (espera) clearTimeout(espera);
      desuscribir();
    };
  }, [ready, onSmilesChange]);

  useEffect(() => {
    const ketcher = ketcherRef.current;
    if (!ready || !caseId || !ketcher) return;
    let alive = true;
    const desuscribir = suscribirCambios(ketcher, invalidarSnapshot);
    if (!desuscribir) return;
    const currentRevision = () => `${instance.current}:${revision.current}`;
    const stable = () => alive && !cargando.current && !isProcessing.current && pendingSmiles.current === null &&
      (currentInput.current === undefined || currentInput.current === lastReportedSmiles.current) &&
      (requestedInput.current === undefined || requestedInput.current === lastReportedSmiles.current);
    const reader = {
      snapshot: (): Promise<EditorSnapshot> => {
        if (!stable()) return Promise.resolve({ status: "not_ready" });
        const rev = currentRevision();
        const cache = snapshotCache.current;
        if (cache && cache.revision === rev && Date.now() - cache.at < 300000) return Promise.resolve({ status: "ok", molfile: cache.molfile, revision: rev });
        if (snapshotPending.current) return snapshotPending.current;
        if (!claimEditorExport()) return Promise.resolve({ status: "read_limit" });
        const pending = (async (): Promise<EditorSnapshot> => {
          try {
            const molfile = await ketcher.getMolfile();
            if (!stable() || currentRevision() !== rev) return { status: "changed" };
            if (typeof molfile !== "string" || !molfile.trim()) return { status: "failed" };
            if (new TextEncoder().encode(molfile).length > 262144) return { status: "too_large" };
            snapshotCache.current = { revision: rev, molfile, at: Date.now() };
            if (snapshotExpiry.current) clearTimeout(snapshotExpiry.current);
            snapshotExpiry.current = setTimeout(() => { snapshotCache.current = null; snapshotExpiry.current = null; }, 300000);
            return { status: "ok", molfile, revision: rev };
          } catch { return { status: "failed" }; }
        })();
        snapshotPending.current = pending;
        void pending.finally(() => { if (snapshotPending.current === pending) snapshotPending.current = null; });
        return pending;
      },
      check: (expected: string) => stable() && currentRevision() === expected,
    };
    const unregister = registerEditorReader(caseId, reader);
    return () => { alive = false; unregister(); snapshotCache.current = null; if (snapshotExpiry.current) clearTimeout(snapshotExpiry.current); snapshotExpiry.current = null; desuscribir(); };
  }, [ready, caseId]);

  const isProcessing = useRef(false);
  const pendingSmiles = useRef<string | null>(null);

  // Internal function to handle the heavy lifting
  const syncToKetcher = async (smiles: string) => {
    if (!ready || !ketcherRef.current) return;
    
    if (isProcessing.current) {
      pendingSmiles.current = smiles;
      return;
    }

    let current = "";
    try {
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
            await cargarEnKetcher(ketcherRef.current, smiles);
        }
      }
    } catch (e) {
      // SMILES inválido: el lienzo conserva la estructura anterior. Si
      // `lastReportedSmiles` se quedara con el texto tecleado, el sondeo vería
      // un «cambio» y devolvería la molécula anterior al campo, borrando lo que
      // el usuario escribió sin decírselo: se evaluaba otra molécula (QA-020).
      // Se alinea con el lienzo para que el texto se quede y lo marque la
      // validación.
      lastReportedSmiles.current = current;
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
