"use client";

// =====================================================================
// CaseSidebar — casos persistentes, no una lista de moléculas
// =====================================================================
//
// Modelo mental de espacio de trabajo persistente: la barra guarda CASOS, y un
// caso sobrevive a la sesión. No lista moléculas ni corridas — ésas viven
// dentro del caso.
//
// UN CASO ROTO SIGUE SIENDO UN CASO. Las filas `unavailable` se muestran con su
// razón visible y con las acciones que tienen sentido para ESE fallo. Omitirlas
// —lo que hacía la versión anterior— hacía desaparecer un caso sin explicación
// y sin forma de recuperarlo.
//
// Escritorio: columna fija de 272 px. Móvil: el contenedor la convierte en
// panel; aquí sólo se garantiza que nada fuerce scroll horizontal (`min-w-0` +
// `truncate` en cada fila).

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Archive, ArchiveRestore, FolderOpen, PanelLeftClose, Plus, Search } from "lucide-react";

import { filterCaseEntries } from "../../lib/cases/repository";
import {
  CASE_RECOVERY_LABELS,
  CASE_STATUS_LABELS,
  isTerminalRunState,
  type CaseIndexEntry,
  type CaseRecoveryAction,
} from "../../lib/cases/types";

export interface CaseSidebarProps {
  readonly cases: readonly CaseIndexEntry[];
  readonly activeCaseId: string | null;
  readonly loading: boolean;
  readonly onSelect: (id: string) => void;
  readonly onCreate: () => void;
  readonly onArchive: (id: string, archived: boolean) => void;
  readonly onReveal?: (id: string) => void;
  readonly onRecover: (id: string, action: CaseRecoveryAction) => void;
  readonly canReveal: boolean;
  /** Bloquea toda operación que reemplace el caso activo, y lo explica. */
  readonly workLocked: boolean;
  readonly workLockedReason?: string;
  /**
   * Pliega el panel. Va aquí, en su cabecera, y no flotando encima: un botón
   * superpuesto tapaba «Nuevo caso».
   */
  readonly onCollapse?: () => void;
}

function formatRelative(iso: string, now: number): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed) || parsed === 0) return "—";
  const deltaMs = Math.max(0, now - parsed);
  const minutes = Math.floor(deltaMs / 60000);
  if (minutes < 1) return "hace instantes";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `hace ${days} d`;
  return new Date(parsed).toLocaleDateString();
}

function formatEvaluationActivity(entry: CaseIndexEntry, now: number): string {
  if (!entry.activeRun) return "sin evaluaciones";
  const relative = formatRelative(entry.activeRun.startedAt, now);
  if (relative === "—") return "evaluación sin fecha";
  return `${isTerminalRunState(entry.activeRun.executionState) ? "evaluada" : "iniciada"} ${relative}`;
}

export function CaseSidebar({
  cases,
  activeCaseId,
  loading,
  onSelect,
  onCreate,
  onArchive,
  onReveal,
  onRecover,
  canReveal,
  workLocked,
  workLockedReason,
  onCollapse,
}: CaseSidebarProps) {
  const [query, setQuery] = useState("");
  const [now, setNow] = useState(() => Date.now());

  // El reloj es puramente visual. Nunca escribe en el caso ni altera su orden.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const { active, archived } = useMemo(() => {
    const filtered = filterCaseEntries(cases, query);
    return {
      active: filtered.filter((entry) => !entry.archived),
      archived: filtered.filter((entry) => entry.archived),
    };
  }, [cases, query]);

  const renderUnavailable = (entry: CaseIndexEntry) => (
    <li key={entry.id} className="min-w-0">
      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-2">
        <div className="flex min-w-0 items-start gap-1.5">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <span className="block truncate text-sm text-zinc-300">{entry.name}</span>
            <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-wider text-amber-400/90">
              No disponible
            </span>
          </div>
        </div>
        <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-400">
          {entry.unavailable?.message}
        </p>
        {entry.unavailable?.detail && (
          <p className="mt-1 break-all font-mono text-[10px] leading-relaxed text-zinc-600">
            {entry.unavailable.detail}
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {entry.unavailable?.actions.map((action) => (
            <button
              key={action}
              type="button"
              onClick={() => onRecover(entry.id, action)}
              className="whitespace-nowrap rounded border border-surface-700 px-2 py-0.5 text-[11px] text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              {CASE_RECOVERY_LABELS[action]}
            </button>
          ))}
        </div>
      </div>
    </li>
  );

  const renderRow = (entry: CaseIndexEntry) => {
    if (entry.unavailable) return renderUnavailable(entry);
    const isActive = entry.id === activeCaseId;
    const lockedForThis = workLocked && !isActive;
    return (
      <li key={entry.id} className="min-w-0">
        <div
          className={`group flex min-w-0 items-start gap-1 rounded-md border px-2 py-2 transition-colors ${
            isActive
              ? "border-brand-500/40 bg-brand-600/10"
              : "border-transparent hover:border-surface-700 hover:bg-surface-800/40"
          }`}
        >
          <button
            type="button"
            onClick={() => onSelect(entry.id)}
            disabled={lockedForThis}
            aria-current={isActive ? "page" : undefined}
            aria-describedby={lockedForThis ? "case-work-lock-reason" : undefined}
            className="min-w-0 flex-1 rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-1 focus-visible:ring-offset-surface-950 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span className="block truncate text-sm text-zinc-200">{entry.name}</span>
            <span className="mt-0.5 block truncate font-mono text-[10px] uppercase tracking-wider text-zinc-500">
              {CASE_STATUS_LABELS[entry.status]} · {formatEvaluationActivity(entry, now)}
              {entry.recoveredFromBackup ? " · recuperado" : ""}
            </span>
          </button>

          <div className="flex shrink-0 items-center gap-0.5 opacity-100 transition-opacity lg:opacity-0 lg:focus-within:opacity-100 lg:group-hover:opacity-100">
            {canReveal && entry.path && onReveal && (
              <button
                type="button"
                onClick={() => onReveal(entry.id)}
                aria-label={`Mostrar la carpeta de ${entry.name}`}
                className="rounded p-1 text-zinc-500 transition-colors hover:text-zinc-200 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                <FolderOpen className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            )}
            <button
              type="button"
              onClick={() => onArchive(entry.id, !entry.archived)}
              aria-label={entry.archived ? `Restaurar ${entry.name}` : `Archivar ${entry.name}`}
              title={entry.archived ? "Restaurar" : "Archivar (reversible)"}
              className="rounded p-1 text-zinc-500 transition-colors hover:text-zinc-200 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              {entry.archived
                ? <ArchiveRestore className="h-3.5 w-3.5" aria-hidden="true" />
                : <Archive className="h-3.5 w-3.5" aria-hidden="true" />}
            </button>
          </div>
        </div>
      </li>
    );
  };

  return (
    <nav aria-label="Casos" className="flex h-full min-w-0 flex-col border-r border-surface-800 bg-surface-950">
      <div className="flex items-center justify-between gap-2 border-b border-surface-800 px-3 py-3">
        <h2 className="truncate text-xs font-semibold uppercase tracking-wider text-zinc-400">Casos</h2>
        <button
          type="button"
          onClick={onCreate}
          disabled={workLocked}
          aria-describedby={workLocked ? "case-work-lock-reason" : undefined}
          className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md border border-surface-700 px-2 py-1 text-xs text-zinc-300 transition-colors hover:border-brand-500/40 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-surface-700"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          Nuevo caso
        </button>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            aria-expanded
            aria-controls="case-sidebar-panel"
            aria-label="Ocultar el panel de casos"
            title="Ocultar los casos"
            className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-zinc-500 transition-colors hover:bg-surface-800 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="border-b border-surface-800 px-3 py-2">
        <label htmlFor="case-search" className="sr-only">Buscar casos</label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-600"
            aria-hidden="true"
          />
          <input
            id="case-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar"
            className="w-full min-w-0 rounded-md border border-surface-800 bg-surface-900 py-1.5 pl-7 pr-2 text-xs text-zinc-200 placeholder:text-zinc-600 focus-visible:border-brand-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {loading ? (
          <p className="px-2 py-3 text-xs text-zinc-600">Cargando casos…</p>
        ) : active.length === 0 && archived.length === 0 ? (
          <p className="px-2 py-3 text-xs leading-relaxed text-zinc-600">
            {query ? "Ningún caso coincide con la búsqueda." : "Todavía no hay casos."}
          </p>
        ) : (
          <>
            {active.length > 0 && (
              <>
                <h3 className="flex items-center justify-between px-2 pb-1 pt-1 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
                  <span>Casos activos</span>
                  <span aria-label={`${active.length} casos`}>{active.length}</span>
                </h3>
                <ul className="space-y-0.5">{active.map(renderRow)}</ul>
              </>
            )}
            {archived.length > 0 && (
              <>
                <h3 className="px-2 pb-1 pt-4 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
                  Archivados
                </h3>
                <ul className="space-y-0.5 opacity-70">{archived.map(renderRow)}</ul>
              </>
            )}
          </>
        )}
      </div>

      {workLocked && workLockedReason && (
        <p
          id="case-work-lock-reason"
          className="border-t border-surface-800 px-3 py-2 text-[11px] leading-relaxed text-amber-400/90"
        >
          {workLockedReason}
        </p>
      )}
    </nav>
  );
}

export default CaseSidebar;
