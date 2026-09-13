"use client";

/**
 * SlidingWindowCache — Cache deslizante para listas grandes (moldex / history).
 *
 * PROBLEMA: rails rendering 10k+ cards en el DOM rompe performance.
 * SOLUTION: mantener una "ventana deslizante" de ~11 items cacheados en memoria
 *           alrededor del selectedIndex. Fetch on-demand los items que faltan.
 *           Persistir selectedIndex / windowStart en sessionStorage ✓.
 *
 * ESTADO DEL CACHE (no los items — eso vive en el page via VirtualMoleculeList):
 *   selectedIndex: number              — índice global (ej: 547)
 *   windowStart:   number              — índice inferior de ventana (ej: 542)
 *   windowEnd:     number              — índice superior (windowStart + 11)
 *   total:         number              — total count del backend (paginación)
 *
 * NIVELES DE PERSISTENCIA:
 *   - sessionStorage      → recupera selectedIndex, scrollbar.
 *   - VirtualMoleculeList  → solo renderiza los ~11 items visibles del DOM.
 *
 * NO guarda los items pesados (cada Molecule con PDB strings, hotspot arrays, etc.)
 * en sessionStorage — solo el selectedIndex. Porque sessionStorage tiene ~5MB
 * limit, y 10k objetos JSON fácilmente la podrían exceder. Los items mismos se
 * recuperan del fetch on-demand desde el backend (que YA tiene pagination).
 *
 * Contract:
 *   - El backend responde con `{ results: [...], total: number, has_next: bool }`
 *   - Llamás `useMoleculeCache()` y recibís:
 *       { selectedIndex, setSelectedIndex, total, setTotal,
 *         windowStart, windowEnd, getRange(start, end),
 *         isLoadingPage(pageStart) }
 *   - `setSelectedIndex(i)` translada la ventana automáticamente si i sale del rango.
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";

interface SlidingWindowState {
  selectedIndex: number;
  windowStart: number;
  windowEnd: number;
  total: number;
  selectedIndexIsKnown: boolean;
}

interface SlidingWindowContextValue {
  selectedIndex: number;
  windowStart: number;
  windowEnd: number;
  total: number;
  setSelectedIndex: (i: number) => void;
  setTotal: (n: number) => void;
  /** Llamar cuando el usuario scrollea hacia una nueva región visible */
  scrollRangeIntoView: (startIndex: number, endIndex: number) => void;
  /** Restaurar desde sessionStorage la primera vez */
  hydrated: boolean;
}

const DEFAULT_WINDOW_HALF = 5;  // → ventana = selectedIndex - 5 ... selectedIndex + 5 (11 items total)

const SlidingWindowContext = createContext<SlidingWindowContextValue | null>(null);

const storageKey = (routeKey: string) => `moldex_cache_${routeKey}`;

interface ProviderProps {
  /** Identificador de route ("/moldex", "/history"). persisted sessionStorage. */
  routeKey: string;
  /** Cuando el cache del backend trae un total nuevo, lo sincroniamos acá. */
  initialSelectedIndex?: number;
  children: React.ReactNode;
}

export function SlidingWindowCacheProvider({ routeKey, initialSelectedIndex = 0, children }: ProviderProps) {
  const [hydrated, setHydrated] = useState(false);
  const [state, setState] = useState<SlidingWindowState>({
    selectedIndex: initialSelectedIndex,
    windowStart: Math.max(0, initialSelectedIndex - DEFAULT_WINDOW_HALF),
    windowEnd: initialSelectedIndex + DEFAULT_WINDOW_HALF + 1,
    total: 0,
    selectedIndexIsKnown: false,
  });

  // ─── Restore desde sessionStorage al montar ───
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(storageKey(routeKey));
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<SlidingWindowState>;
        if (typeof parsed.selectedIndex === "number" && parsed.selectedIndex >= 0) {
          const sel = Math.min(parsed.selectedIndex, parsed.total ? parsed.total - 1 : parsed.selectedIndex);
          setState({
            selectedIndex: sel,
            windowStart: Math.max(0, sel - DEFAULT_WINDOW_HALF),
            windowEnd: sel + DEFAULT_WINDOW_HALF + 1,
            total: parsed.total || 0,
            selectedIndexIsKnown: true,
          });
        }
      }
    } catch (err) {
      console.warn("[SlidingWindowCache] sessionStorage restore skip:", err);
    }
    setHydrated(true);
  }, [routeKey]);

  // ─── Persistir a sessionStorage en cambios relevantes ───
  useEffect(() => {
    if (!hydrated) return;
    try {
      sessionStorage.setItem(storageKey(routeKey), JSON.stringify({
        selectedIndex: state.selectedIndex,
        total: state.total,
      }));
    } catch (err) {
      // Silent fail: si sessionStorage se llena, no rompemos UX
      console.warn("[SlidingWindowCache] sessionStorage save skip:", err);
    }
  }, [routeKey, state.selectedIndex, state.total, hydrated]);

  const setSelectedIndex = useCallback((i: number) => {
    setState(prev => {
      // Clamp al total si lo conocemos
      const next = prev.total > 0 ? Math.min(i, prev.total - 1) : i;
      // Transladar ventana si el nuevo index sale afuera
      let newStart = prev.windowStart;
      let newEnd = prev.windowEnd;
      if (next < prev.windowStart || next >= prev.windowEnd) {
        newStart = Math.max(0, next - DEFAULT_WINDOW_HALF);
        newEnd = next + DEFAULT_WINDOW_HALF + 1;
      }
      return {
        ...prev,
        selectedIndex: next,
        windowStart: newStart,
        windowEnd: newEnd,
        selectedIndexIsKnown: true,
      };
    });
  }, []);

  const setTotal = useCallback((n: number) => {
    setState(prev => ({ ...prev, total: n }));
  }, []);

  // Cuando el user scrollea (via Virtuoso rangeChanged), pegamos la ventana
  // visible con nuestro cache. Si la ventana se translada >5 items, fetch on-demand.
  const scrollRangeIntoView = useCallback((startIndex: number, endIndex: number) => {
    setState(prev => {
      // Si el rango visible sigue dentro del cacheo → nada
      if (startIndex >= prev.windowStart && endIndex <= prev.windowEnd) {
        return prev;
      }
      // Transladar: mantener ~overlap de 2 items con la ventana anterior (smooth)
      const center = Math.floor((startIndex + endIndex) / 2);
      const newStart = Math.max(0, center - DEFAULT_WINDOW_HALF);
      return {
        ...prev,
        windowStart: newStart,
        windowEnd: newStart + DEFAULT_WINDOW_HALF * 2 + 1,
      };
    });
  }, []);

  const value: SlidingWindowContextValue = {
    selectedIndex: state.selectedIndex,
    windowStart: state.windowStart,
    windowEnd: state.windowEnd,
    total: state.total,
    setSelectedIndex,
    setTotal,
    scrollRangeIntoView,
    hydrated,
  };

  return <SlidingWindowContext.Provider value={value}>{children}</SlidingWindowContext.Provider>;
}

export function useMoleculeCache(): SlidingWindowContextValue {
  const ctx = useContext(SlidingWindowContext);
  if (!ctx) {
    throw new Error("useMoleculeCache() must be used inside <SlidingWindowCacheProvider routeKey>");
  }
  return ctx;
}

export const WINDOW_SIZE = DEFAULT_WINDOW_HALF * 2 + 1; // 11
export default SlidingWindowCacheProvider;
