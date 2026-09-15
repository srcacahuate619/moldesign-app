"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useCallback, useEffect, useRef, useState } from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { useMoleculeCache, WINDOW_SIZE } from "./SlidingWindowCache";
import MoldexCard from "../MoldexCard";
import { motion } from "framer-motion";

/**
 * VirtualMoleculeList — VirtualScroll con sliding-window cache para la bioteca.
 *
 * USO (dentro de un <SlidingWindowCacheProvider routeKey="moldex">):
 *   <VirtualMoleculeList
 *     fetchPage={(start, limit) => getMoldex(undefined, limit, start)}
 *     onSelect={(id) => setSelectedId(id)}
 *     isSelected={(id) => selectedId === id}
 *     onCompareToggle={(id) => handleToggleCompare(id)}
 *     isComparing={(id) => selectionForCompare.includes(id)}
 *     emptyComponent={<NoMolecules />}
 *   />
 *
 * Internamente:
 *   1. Al montar, fetchea la primera pagina de WINDOW_SIZE items (total=totalCount)
 *   2. cachea items en un Map<index, Molecule> (memoized en ref, no re-render)
 *   3. Virtuoso solo renderiza ~11 items visibles del DOM
 *   4. scrollea al selectedIndex restaurado de sessionStorage (via SlidingWindowCache)
 *   5. Cuando el user scrollea a otro rango, translada la ventana y fetchea faltantes
 */

interface VirtualMoleculeListProps {
  fetchPage: (offset: number, limit: number) => Promise<{
    results: any[];
    total: number;
    has_next?: boolean;
  }>;
  onSelect: (id: string, index: number) => void;
  isSelected: (id: string) => boolean;
  onCompareToggle: (id: string) => void;
  isComparing: (id: string) => boolean;
  emptyComponent?: React.ReactNode;
}

export function VirtualMoleculeList({
  fetchPage,
  onSelect,
  isSelected,
  onCompareToggle,
  isComparing,
  emptyComponent,
}: VirtualMoleculeListProps) {
  const { t } = useLanguage();
  const cache = useMoleculeCache();
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const moleculeMapRef = useRef<Map<number, any>>(new Map());
  const [loading, setLoading] = useState(true);
  const [firstLoad, setFirstLoad] = useState(false);

  // ─── Fetch inicial: obtener total + first page ───
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPage(cache.windowStart, WINDOW_SIZE)
      .then(data => {
        if (cancelled) return;
        cache.setTotal(data.total);
        data.results.forEach((mol, i) => {
          moleculeMapRef.current.set(cache.windowStart + i, mol);
        });
        setFirstLoad(true);
      })
      .catch(err => console.error("[VirtualMolList] fetch error:", err))
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []); // solo al montar

  // ─── Cuando la ventana del cache cambia, fetchear lo que falta ───
  useEffect(() => {
    if (!firstLoad) return;
    const newIndices = range(cache.windowStart, Math.min(cache.windowEnd, cache.total));
    const missing = newIndices.filter(i => !moleculeMapRef.current.has(i));
    if (missing.length === 0) return;

    // Fetch desde el primer índice faltante continuo
    const minMissing = Math.min(...missing);
    const maxMissing = Math.max(...missing);
    const fetchStart = minMissing;
    const fetchSize = maxMissing - minMissing + 1;

    let cancelled = false;
    fetchPage(fetchStart, Math.min(fetchSize, WINDOW_SIZE))
      .then(data => {
        if (cancelled) return;
        data.results.forEach((mol, i) => {
          moleculeMapRef.current.set(fetchStart + i, mol);
        });
        cache.setTotal(data.total);
      })
      .catch(err => console.warn("[VirtualMolList] window fetch error:", err));

    return () => { cancelled = true; };
  }, [cache.windowStart, cache.windowEnd, cache.total, firstLoad]);

  // ─── Scroll al selectedIndex restaurado (sessionStorage) ───
  useEffect(() => {
    if (firstLoad && cache.hydrated && virtuosoRef.current && cache.selectedIndex > 0) {
      virtuosoRef.current.scrollToIndex({
        index: cache.selectedIndex,
        align: "center",
        behavior: "smooth",
      });
    }
  }, [firstLoad, cache.hydrated]);

  const handleRangeChanged = useCallback(
    ({ startIndex, endIndex }: { startIndex: number; endIndex: number }) => {
      cache.scrollRangeIntoView(startIndex, endIndex);
      // También actualizar selectedIndex al centro del rango visible
      if (startIndex <= cache.selectedIndex && cache.selectedIndex <= endIndex) return;
      const center = Math.floor((startIndex + endIndex) / 2);
      cache.setSelectedIndex(center);
    },
    [cache],
  );

  const itemContent = useCallback(
    (_: number, molecule: any) => {
      if (!molecule) {
        return (
          <div className="p-6 text-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent mx-auto" />
          </div>
        );
      }
      return (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
        >
          <MoldexCard
            molecule={molecule}
            isSelected={isSelected(molecule.id)}
            onClick={(id) => {
              const idx = Array.from(moleculeMapRef.current.values()).findIndex(m => m.id === id);
              if (idx >= 0) onSelect(id, cache.windowStart + idx);
              else onSelect(id, 0);
            }}
            onCompareToggle={() => onCompareToggle(molecule.id)}
            isComparing={isComparing(molecule.id)}
          />
        </motion.div>
      );
    },
    [isSelected, isComparing, onCompareToggle, onSelect, cache],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (cache.total === 0 && firstLoad) {
    return <>{emptyComponent || <p className="text-center text-xs text-zinc-500 p-8">{t("z_bioteca_vacia")}</p>}</>;
  }

  const moleculesArray = Array.from({ length: cache.total }, (_, i) =>
    moleculeMapRef.current.get(i) ?? undefined,
  );

  return (
    <Virtuoso
      ref={virtuosoRef}
      style={{ height: "100%" }}
      totalCount={cache.total}
      data={moleculesArray}
      itemContent={itemContent}
      rangeChanged={handleRangeChanged}
      increaseViewportBy={{ bottom: 400, top: 200 }}
      initialTopMostItemIndex={cache.selectedIndex >= 0 ? cache.selectedIndex : 0}
    />
  );
}

function range(start: number, end: number): number[] {
  return Array.from({ length: end - start }, (_, i) => start + i);
}

export default VirtualMoleculeList;
