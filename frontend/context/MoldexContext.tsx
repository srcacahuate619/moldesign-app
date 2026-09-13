"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import { getMoldex, getProteinFile, getPoseFile } from "../lib/api";

const MAX_3D_CACHE_SIZE = 50; // Maximum number of 3D structures (PDB/SDF) kept in RAM

export interface MoldexState {
  molecules: any[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  search: string;
  setSearch: (s: string) => void;
  targetFilter: string;
  setTargetFilter: (f: string) => void;
  sortMode: "DATE_DESC" | "SCORE_DESC" | "SCORE_ASC";
  setSortMode: (m: "DATE_DESC" | "SCORE_DESC" | "SCORE_ASC") => void;

  // Visual & Tab states for Pro UI
  activeView: "LIST" | "3D" | "INFO";
  setActiveView: (v: "LIST" | "3D" | "INFO") => void;
  activeTab: "THERMO" | "GRID" | "ALERTS";
  setActiveTab: (t: "THERMO" | "GRID" | "ALERTS") => void;

  // 3D View Data & Preloading
  proteinData: string | null;
  poseData: string | null;
  loading3D: boolean;

  // Actions
  loadMoldex: (force?: boolean) => Promise<void>;
  selectMolecule: (id: string) => Promise<void>;
}

const MoldexContext = createContext<MoldexState | null>(null);

export function MoldexProvider({ children }: { children: React.ReactNode }) {
  const [molecules, setMolecules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [targetFilter, setTargetFilter] = useState("ALL");
  const [sortMode, setSortMode] = useState<"DATE_DESC" | "SCORE_DESC" | "SCORE_ASC">("DATE_DESC");

  const [activeView, setActiveView] = useState<"LIST" | "3D" | "INFO">("3D");
  const [activeTab, setActiveTab] = useState<"THERMO" | "GRID" | "ALERTS">("THERMO");

  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);
  const [loading3D, setLoading3D] = useState(false);

  // Bounded LRU Cache for 3D Protein & Pose files (Map maintains insertion order)
  const cache3DRef = React.useRef<Map<string, { protein: string | null; pose: string | null }>>(new Map());

  const getCached3D = (id: string) => {
    const cache = cache3DRef.current;
    if (cache.has(id)) {
      const data = cache.get(id)!;
      // Refresh key order for LRU (re-insert at the end)
      cache.delete(id);
      cache.set(id, data);
      return data;
    }
    return null;
  };

  const setCached3D = (id: string, data: { protein: string | null; pose: string | null }) => {
    const cache = cache3DRef.current;
    if (cache.has(id)) {
      cache.delete(id);
    } else if (cache.size >= MAX_3D_CACHE_SIZE) {
      // Evict oldest entry (first key in Map)
      const oldestKey = cache.keys().next().value;
      if (oldestKey) {
        cache.delete(oldestKey);
      }
    }
    cache.set(id, data);
  };

  const loadMoldex = useCallback(async (force = false) => {
    if (!force && molecules.length > 0) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getMoldex();
      setMolecules(data.results || []);
      if (data.results && data.results.length > 0 && !selectedId) {
        setSelectedId(data.results[0].id);
      }
    } catch (err: any) {
      console.error("Error loading Moldex library:", err);
      setError(err.message || "Error al cargar la bioteca.");
    } finally {
      setLoading(false);
    }
  }, [molecules.length, selectedId]);

  useEffect(() => {
    loadMoldex();
  }, [loadMoldex]);

  const selectedMolecule = useMemo(
    () => molecules.find((m) => m.id === selectedId),
    [selectedId, molecules]
  );

  const fetch3DForMolecule = useCallback(async (molId: string) => {
    // Check LRU Cache first
    const cached = getCached3D(molId);
    if (cached) {
      setProteinData(cached.protein);
      setPoseData(cached.pose);
      setLoading3D(false);
      return;
    }

    setLoading3D(true);
    setProteinData(null);
    setPoseData(null);

    try {
      const [protein, pose] = await Promise.all([
        getProteinFile(molId).catch(() => null),
        getPoseFile(molId).catch(() => null),
      ]);

      const data = { protein, pose };
      setCached3D(molId, data);

      // Only set active state if this molecule is still selected
      setSelectedId((currentSelected) => {
        if (currentSelected === molId) {
          setProteinData(protein);
          setPoseData(pose);
        }
        return currentSelected;
      });
    } catch (err) {
      console.error("Error loading 3D data for molecule:", molId, err);
    } finally {
      setLoading3D(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) {
      fetch3DForMolecule(selectedId);
    }
  }, [selectedId, fetch3DForMolecule]);

  const selectMolecule = useCallback(async (id: string) => {
    setSelectedId(id);
  }, []);


  const value: MoldexState = {
    molecules,
    loading,
    error,
    selectedId,
    setSelectedId,
    search,
    setSearch,
    targetFilter,
    setTargetFilter,
    sortMode,
    setSortMode,
    activeView,
    setActiveView,
    activeTab,
    setActiveTab,
    proteinData,
    poseData,
    loading3D,
    loadMoldex,
    selectMolecule,
  };

  return <MoldexContext.Provider value={value}>{children}</MoldexContext.Provider>;
}

export function useMoldex(): MoldexState {
  const ctx = useContext(MoldexContext);
  if (!ctx) {
    throw new Error("useMoldex must be used within a <MoldexProvider>");
  }
  return ctx;
}
