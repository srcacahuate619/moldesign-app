"use client";

import { createContext, useContext } from "react";

/**
 * KeepAliveContext — informa a los componentes hijos (anidados bajo una
 * página keep-alive) si el wrapper del parent está actualmente visible
 * (display:block) u oculto (display:none).
 *
 * Uso professional: las páginas de Next.js App Router NO pueden recibir
 * props arbitrarias (contrato PageProps = { params, searchParams }). Por
 * eso no le pasamos `isActive` como prop a EvaluationPage desde el layout.
 * En su lugar, usamos Context: el layout provee el valor del wrapper,
 * los componentes anidados (ProEvaluation → AdvancedMolstarViewer) lo
 * consumen sin romper el contrato del router.
 *
 * Default: `true` — cualquier uso fuera del KeepAliveLayout (ej. tests,
 * preview aislado) asume que el componente está activo.
 */
export const KeepAliveContext = createContext<boolean>(true);

export function useKeepAliveActive(): boolean {
  return useContext(KeepAliveContext);
}
