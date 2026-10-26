import type { MolcyAjustes } from "./molcy";

/** Compare the requested presentation to the effective immutable job recipe. */
export function sameMolcyAjustes(requested: MolcyAjustes, stored?: MolcyAjustes): boolean {
  if (!stored?.presentacion || !requested.presentacion) return false;
  const canonical = (value: unknown): string => {
    if (value && typeof value === "object" && !Array.isArray(value)) return JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a],[b]) => a.localeCompare(b)).map(([key,item]) => [key, JSON.parse(canonical(item))])));
    return JSON.stringify(value);
  };
  const normalize = (p: NonNullable<MolcyAjustes["presentacion"]>) => ({ ...p, titulo: p.titulo?.trim() || null, color_receptor: p.color_receptor?.toUpperCase() ?? null, color_residuos: p.color_residuos?.toUpperCase() ?? null, colores_lineas: { polar: p.colores_lineas.polar?.toUpperCase() ?? null, apolar: p.colores_lineas.apolar?.toUpperCase() ?? null } });
  if (canonical(normalize(requested.presentacion)) !== canonical(normalize(stored.presentacion))) return false;
  if (!requested.ensamble_fluido || !stored.ensamble_fluido) return requested.ensamble_fluido === stored.ensamble_fluido;
  return requested.ensamble_fluido.variante === stored.ensamble_fluido.variante &&
    (requested.ensamble_fluido.conformero === undefined || requested.ensamble_fluido.conformero === stored.ensamble_fluido.conformero);
}
