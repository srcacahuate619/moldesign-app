"use client";

import { useEffect, useMemo, useState } from "react";
import { FlaskConical, Loader2, X } from "lucide-react";

import { createTargetVariant, type Target } from "../../../lib/api";

interface ReceptorVariantModalProps {
  readonly parent: Target;
  readonly onClose: () => void;
  readonly onSuccess: (target: Target) => void;
}

function numericTriple(values: readonly string[]): [number, number, number] | null {
  const parsed = values.map((value) => Number(value));
  return parsed.every(Number.isFinite)
    ? [parsed[0], parsed[1], parsed[2]]
    : null;
}

export function ReceptorVariantModal({ parent, onClose, onSuccess }: ReceptorVariantModalProps) {
  const defaultCenter = useMemo(() => [
    String(parent.grid_center_x ?? 0),
    String(parent.grid_center_y ?? 0),
    String(parent.grid_center_z ?? 0),
  ], [parent]);
  const defaultSize = useMemo(() => [
    String(parent.grid_size_x ?? 20),
    String(parent.grid_size_y ?? 20),
    String(parent.grid_size_z ?? 20),
  ], [parent]);

  const [name, setName] = useState(`${parent.name} · variante`);
  const [chain, setChain] = useState(parent.chain || "A");
  const [center, setCenter] = useState(defaultCenter);
  const [size, setSize] = useState(defaultSize);
  const [cofactors, setCofactors] = useState((parent.cofactors_whitelist ?? []).join(", "));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [busy, onClose]);

  const setCoordinate = (
    setter: (values: string[]) => void,
    current: readonly string[],
    index: number,
    value: string,
  ) => setter(current.map((item, itemIndex) => itemIndex === index ? value : item));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const gridCenter = numericTriple(center);
    const gridSize = numericTriple(size);
    if (!name.trim() || !chain.trim() || !gridCenter || !gridSize) {
      setError("Completa el nombre, la cadena y las seis coordenadas.");
      return;
    }
    if (gridSize.some((value) => value < 5 || value > 80)) {
      setError("Cada dimensión de la caja debe estar entre 5 y 80 Å.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const target = await createTargetVariant(parent.pdb_id, {
        name: name.trim(),
        chain_id: chain.trim().toUpperCase(),
        grid_center: gridCenter,
        grid_size: gridSize,
        cofactors_whitelist: cofactors
          .split(",")
          .map((value) => value.trim().toUpperCase())
          .filter(Boolean),
      });
      onSuccess(target);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo crear la variante.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
      <form
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="variant-title"
        className="w-full max-w-2xl overflow-hidden rounded-2xl border border-purple-500/25 bg-zinc-950 shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-zinc-800 px-5 py-4">
          <div className="flex gap-3">
            <span className="rounded-lg border border-purple-500/25 bg-purple-500/10 p-2 text-purple-300">
              <FlaskConical className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <h2 id="variant-title" className="text-sm font-semibold text-white">Nueva variante de preparación</h2>
              <p className="mt-1 text-xs text-zinc-400">
                Parte de {parent.name} ({parent.pdb_id}) y crea un receptor privado nuevo. El original no cambia.
              </p>
            </div>
          </div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Cerrar" className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-900 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-5 p-5">
          <div className="grid gap-4 sm:grid-cols-[1fr_7rem]">
            <label className="text-xs text-zinc-400">
              <span className="mb-1.5 block font-medium text-zinc-300">Nombre de la variante</span>
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} className="w-full rounded-lg border border-zinc-800 bg-black px-3 py-2 text-zinc-100 outline-none focus:border-purple-500/50" />
            </label>
            <label className="text-xs text-zinc-400">
              <span className="mb-1.5 block font-medium text-zinc-300">Cadena</span>
              <input value={chain} onChange={(event) => setChain(event.target.value)} maxLength={4} className="w-full rounded-lg border border-zinc-800 bg-black px-3 py-2 text-zinc-100 outline-none focus:border-purple-500/50" />
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {[
              ["Centro de la caja (Å)", center, setCenter],
              ["Tamaño de la caja (Å)", size, setSize],
            ].map(([label, values, setter]) => (
              <fieldset key={label as string} className="rounded-xl border border-zinc-800 p-3">
                <legend className="px-1 text-xs font-medium text-zinc-300">{label as string}</legend>
                <div className="mt-1 grid grid-cols-3 gap-2">
                  {(values as string[]).map((value, index) => (
                    <label key={index} className="text-[10px] uppercase text-zinc-500">
                      {"XYZ"[index]}
                      <input type="number" step="0.1" value={value} onChange={(event) => setCoordinate(setter as (values: string[]) => void, values as string[], index, event.target.value)} className="mt-1 w-full rounded border border-zinc-800 bg-black px-2 py-1.5 text-xs text-zinc-100 outline-none focus:border-purple-500/50" />
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}
          </div>

          <label className="block text-xs text-zinc-400">
            <span className="mb-1.5 block font-medium text-zinc-300">Metales y cofactores que deben conservarse</span>
            <input value={cofactors} onChange={(event) => setCofactors(event.target.value)} placeholder="Ej. ZN, HEM, FAD" className="w-full rounded-lg border border-zinc-800 bg-black px-3 py-2 text-zinc-100 outline-none focus:border-purple-500/50" />
            <span className="mt-1.5 block leading-relaxed text-zinc-500">
              Separados por comas. Las aguas se eliminan en este MVP; la preparación real y sus hashes se registrarán al crear la variante.
            </span>
          </label>

          {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-xs text-red-300">{error}</p>}
        </div>

        <footer className="flex justify-end gap-2 border-t border-zinc-800 px-5 py-4">
          <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-zinc-800 px-4 py-2 text-xs text-zinc-300 hover:bg-zinc-900 disabled:opacity-50">Cancelar</button>
          <button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-lg border border-purple-500/40 bg-purple-600 px-4 py-2 text-xs font-medium text-white hover:bg-purple-500 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
            {busy ? "Preparando…" : "Crear variante"}
          </button>
        </footer>
      </form>
    </div>
  );
}
