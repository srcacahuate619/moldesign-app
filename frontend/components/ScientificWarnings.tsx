type Props = {
  warnings: string[] | null;
};

export function ScientificWarnings({ warnings }: Props) {
  if (!warnings || warnings.length === 0) return null;

  const technical = warnings.filter(w => w.includes("OpenBabel") || w.includes("PDBQT") || w.includes("REMARK VINA"));
  const scientific = warnings.filter(w => !technical.includes(w));

  return (
    <section className="space-y-2">
      {scientific.length > 0 && (
        <div className="rounded-xl border border-yellow-600/30 bg-yellow-950/20 p-4">
          <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-yellow-400">⚠ Advertencias Científicas</h3>
          <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-yellow-200/80">
            {scientific.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
      {technical.length > 0 && (
        <div className="rounded-xl border border-surface-800 bg-surface-950/40 p-3">
          <h3 className="mb-1 text-[10px] font-bold uppercase tracking-wider text-surface-500">Notas de Integridad de Datos</h3>
          <ul className="space-y-0.5 text-[10px] leading-tight text-surface-500">
            {technical.map((w, i) => <li key={i}>• {w}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}
