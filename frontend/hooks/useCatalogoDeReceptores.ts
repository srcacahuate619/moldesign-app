"use client";

import { useEffect, useState } from "react";
import type { Target } from "@/lib/api";
import { catalogoEnMemoria, obtenerCatalogo } from "@/lib/catalogoDeReceptores";

/** Las superficies guardadas comparten el catálogo, sin reutilizar otra sesión. */
export function useCatalogoDeReceptores(enabled = true): readonly Target[] | null {
  let identidad = "";
  try { identidad = window.localStorage.getItem("moldesign_auth") ?? ""; } catch { /* Sin almacenamiento. */ }
  const catalogo = enabled ? catalogoEnMemoria() : null;
  // Buscar o cambiar de vista puede volver a renderizar después del TTL. Esa
  // ausencia también debe renovar la caché, sin esperar a otro montaje.
  const necesitaCatalogo = enabled && catalogo === null;
  const [, refrescar] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let activo = true;
    (async () => {
      await obtenerCatalogo();
      if (activo) refrescar((version) => version + 1);
    })().catch(() => { /* Sin dato: el consumidor conserva demostración. */ });
    return () => { activo = false; };
  }, [enabled, identidad, necesitaCatalogo]);
  return catalogo;
}
