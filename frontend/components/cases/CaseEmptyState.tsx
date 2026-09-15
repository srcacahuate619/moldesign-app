"use client";

// =====================================================================
// CaseEmptyState — la pantalla de Evaluación sin caso seleccionado
// =====================================================================
//
// Deliberadamente sobrio. No es un dashboard de tarjetas ni una landing: es la
// puerta de un banco de trabajo. Sin metricas inventadas, sin ejemplos de casos
// reales, sin gradientes, sin orbes, sin emojis.
//
// NO reutiliza `components/ui/EmptyState.tsx` a proposito: aquel es el patron
// "orbe cinematografico + ritual 1·2·3" que encaja en /moldex, y aqui
// contradiria el tono. Aquel componente se conserva intacto para sus rutas.

import { FolderOpen, Plus } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";

export interface CaseEmptyStateProps {
  readonly onCreate: () => void;
  readonly onOpenFolder: () => void;
  readonly canOpenFolder: boolean;
  /** Obligatoria si `canOpenFolder` es false: un control inerte debe explicarse. */
  readonly openFolderUnavailableReason?: string;
  readonly storageLabel: string;
  /** Crear también se bloquea con trabajo vivo: reemplazaría el caso activo. */
  readonly createDisabled?: boolean;
  readonly createDisabledReason?: string;
}

export function CaseEmptyState({
  onCreate,
  onOpenFolder,
  canOpenFolder,
  openFolderUnavailableReason,
  storageLabel,
  createDisabled = false,
  createDisabledReason,
}: CaseEmptyStateProps) {
  const { t } = useLanguage();
  return (
    <div className="flex h-full w-full items-center justify-center px-6 py-12">
      <div className="w-full max-w-xl">
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          {t("ca_crear_titulo")}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-zinc-400">
          {t("ca_crear_descripcion")}
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onCreate}
            disabled={createDisabled}
            aria-describedby={createDisabled && createDisabledReason ? "create-disabled-reason" : undefined}
            className="inline-flex items-center gap-2 rounded-md border border-brand-500/40 bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-950 active:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-brand-600"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Crear caso
          </button>

          <button
            type="button"
            onClick={onOpenFolder}
            disabled={!canOpenFolder}
            aria-describedby={!canOpenFolder ? "open-folder-reason" : undefined}
            className="inline-flex items-center gap-2 rounded-md border border-surface-700 bg-transparent px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-950 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-surface-700 disabled:hover:text-zinc-300"
          >
            <FolderOpen className="h-4 w-4" aria-hidden="true" />
            Abrir carpeta existente
          </button>
        </div>

        {createDisabled && createDisabledReason && (
          <p id="create-disabled-reason" className="mt-3 text-xs leading-relaxed text-amber-400/90">
            {createDisabledReason}
          </p>
        )}

        {!canOpenFolder && openFolderUnavailableReason && (
          <p id="open-folder-reason" className="mt-3 text-xs leading-relaxed text-zinc-500">
            {openFolderUnavailableReason}
          </p>
        )}

        <p className="mt-8 border-t border-surface-800 pt-4 font-mono text-[11px] uppercase tracking-wider text-zinc-600">
          {storageLabel}
        </p>
      </div>
    </div>
  );
}

export default CaseEmptyState;
