export type StructureIdentity = { readonly cell?: { readonly transform?: { readonly ref?: string } } };
/** Identidad asignada por Mol*, independiente de los nombres visibles y del idioma. */
export function newlyLoadedStructureRef(before: readonly string[], after: readonly StructureIdentity[]): string | null {
  const known = new Set(before);
  const added = after.map(s => s.cell?.transform?.ref).filter((ref): ref is string => typeof ref === "string" && !known.has(ref));
  return added.length === 1 ? added[0] : null;
}
export function structureByRef<T extends StructureIdentity>(structures: readonly T[], ref: string | null): T | undefined {
  return ref ? structures.find(s => s.cell?.transform?.ref === ref) : undefined;
}
