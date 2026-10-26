"use client";
import { useCallback, useEffect, useState } from "react";
import { fetchBackend } from "./backendFetch";

export interface AntiDiana {
  pdb_id: string | null;
  name: string;
  category: string;
  risk?: string;
  threshold_kcal?: number;
  source?: string;
  por_defecto?: boolean;
  disponible?: boolean;
  seleccionable?: boolean;
  motivo_no_disponible?: string | null;
  motivo?: string | null;
  aviso?: string | null;
  estructura?: { resolucion_A?: number | null; pose_reproducida?: boolean | null; truncadas_en_sitio?: number | null } | null;
}
export function disponible(a: AntiDiana): boolean {
  return Boolean(a.pdb_id) && a.disponible !== false && a.seleccionable !== false;
}
/** La procedencia del API decide el grupo; no modifica selección ni estados. */
export function agruparAntiDianas(targets: readonly AntiDiana[]) {
  return [
    { seccion: "panel" as const, targets: targets.filter((target) => target.source !== "user") },
    { seccion: "propias" as const, targets: targets.filter((target) => target.source === "user") },
  ];
}
/** El API decide qué se marca al abrir (`por_defecto`): el panel por defecto y las anti-dianas propias del usuario, como siempre. */
export function antiDianasPorDefecto(list: readonly AntiDiana[]): string[] {
  return list.filter((a) => disponible(a) && a.por_defecto !== false).map((a) => a.pdb_id!);
}
export function antiDianasParaEnviar(list: readonly AntiDiana[] | null, selected: readonly string[]): string[] {
  const ids = new Set(list?.filter(disponible).map((a) => a.pdb_id));
  return [...new Set(selected)].filter((id) => ids.has(id));
}
export function useAntiDianas(enabled = true) {
  const [targets, setTargets] = useState<AntiDiana[] | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    setError(false);
    (async () => {
      const response = await fetchBackend(`/pro/anti-targets`);
      if (!response.ok) throw new Error("anti-targets");
      const data = await response.json();
      if (!Array.isArray(data.anti_targets)) throw new Error("anti-targets");
      if (alive) setTargets(data.anti_targets);
    })().catch(() => { if (alive) setError(true); });
    return () => { alive = false; };
  }, [enabled, attempt]);
  return { targets, error, retry };
}
