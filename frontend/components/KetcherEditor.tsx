"use client";


import { useLanguage } from "@/context/LanguageContext";
import dynamic from "next/dynamic";
import { useCallback, useState, useEffect } from "react";

const KetcherEditorInner = dynamic(() => import("./KetcherEditorInner"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50"
      style={{ height: 550 }}
    >
      <div className="flex items-center gap-3 text-sm font-medium text-zinc-500">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 dark:border-zinc-600 border-t-transparent" />
        Cargando editor molecular...
      </div>
    </div>
  ),
});

type Props = {
  onSmilesChange?: (smiles: string) => void;
  initialSmiles?: string;
  height?: number | string;
  showSmilesInput?: boolean;
};

export function KetcherEditor({ onSmilesChange, initialSmiles, height = 750, showSmilesInput = true }: Props) {
  const { t } = useLanguage();
  const [textSmiles, setTextSmiles] = useState(initialSmiles || "");
  const [ketcherError, setKetcherError] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (initialSmiles !== undefined && initialSmiles !== textSmiles) {
      setTextSmiles(initialSmiles);
    }
  }, [initialSmiles, textSmiles]);

  const handleTextChange = useCallback(
    (value: string) => {
      setTextSmiles(value);
      onSmilesChange?.(value);
    },
    [onSmilesChange],
  );

  const handleKetcherSmiles = useCallback(
    (smiles: string) => {
      if (smiles !== textSmiles && !isFocused) {
        setTextSmiles(smiles);
        onSmilesChange?.(smiles);
      }
    },
    [onSmilesChange, textSmiles, isFocused],
  );

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {ketcherError ? (
          <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 p-12">
            <div className="text-center">
              <div className="mb-3 text-4xl grayscale opacity-80">⚠️</div>
              <p className="text-sm font-semibold text-zinc-900 dark:text-white">
                {t("pn_editor_no_cargo")}
              </p>
              <p className="mt-1 text-xs text-zinc-500">{ketcherError}</p>
            </div>
          </div>
        ) : (
          <div className="rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-white">
            <KetcherEditorInner
              initialSmiles={textSmiles}
              onSmilesChange={handleKetcherSmiles}
              height={height}
            />
          </div>
        )}
        {showSmilesInput && (
          <div className="flex items-center gap-3">
            <label className="text-[11px] font-bold uppercase tracking-widest text-zinc-500">SMILES</label>
            <input
              type="text"
              value={textSmiles}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onChange={(e) => handleTextChange(e.target.value)}
              className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 font-mono text-xs text-zinc-700 dark:text-zinc-300 focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 transition-colors"
              placeholder={t("pn_editor_smiles")}
            />
          </div>
        )}
      </div>
    </div>
  );
}
