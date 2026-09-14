/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4
 * Hallmark · component: evaluation structural inputs · genre: modern-minimal · theme: existing MolDesign
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass · mobile: pass
 */
"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { ChipsDelSitio } from "../../science/ChipsDelSitio";
import { ProtocoloM5Zn } from "../../science/ProtocoloM5Zn";
import { animateElements, cancelAnimations } from "../../../lib/webAnimation";
import {
  Database, Play, ShieldCheck, Download, Activity,
  FileText, Eye, ExternalLink as IconoEnlaceExterno, Settings, FlaskConical, AlertTriangle, X,
  History,
} from "lucide-react";
import { KetcherEditor } from "../../KetcherEditor";
import { ThinkingOrb } from "../../ui/ThinkingOrb";
import { useKeepAliveActive } from "../../../context/KeepAliveContext";
import dynamic from "next/dynamic";
const AdvancedMolstarViewer = dynamic(() => import("./AdvancedMolstarViewer"), { ssr: false });
import { AvisoSinWebGL } from "./AvisoSinWebGL";
import { comprobarWebGL } from "../../../lib/webgl";
const Web3DViewer = dynamic(() => import("./Web3DViewer"), { ssr: false });
import TargetSelectorModal from "./TargetSelectorModal";
import ProOptionsModal from "./ProOptionsModal";
import { PDFReportViewer } from "../../PDFReportViewer";
import { CertificationModal } from "../../CertificationModal";
import type { DockingEngineConfig, GridBoxConfig, AdvancedConfig } from "./ProOptionsModal";
import { ProAnalysisTabs } from "./ProAnalysisTabs";
import { EvaluationEvidencePanel } from "./EvaluationEvidencePanel";
import { PoseComparisonDialog } from "./PoseComparisonDialog";
import { PipelineTimeline, stagesForPipeline } from "./PipelineTimeline";
import { getTargetPdb, getPoseFile, getProteinFile, getJobStatus, getInteractions } from "../../../lib/api";
import type { Target } from "../../../lib/api";
import { runAdmet, runMmgbsa } from "../../../lib/proApi";
import { subscribeToPipelineEvents, stageEventToOrbUpdate } from "../../../lib/pipelineStream";
import type { PipelineEvent } from "../../../lib/pipelineStream";
import { PIPELINES_BY_FAMILY, FAMILY_LABELS } from "../../../lib/pipelineDefinitions";
import { describirEtapa, etapasAusentes, tieneSalidaUms } from "../../../lib/procedenciaDeSenales";
import type { JobStatus, MolecularSuggestion, ValidationResult, EvaluationResult, InteractionDatum } from "../../../lib/types";
import type { StageState } from "./PipelineTimeline";
import type { CasePipelineConfig, CaseStructuralSystem } from "../../../lib/cases/types";

import { ExternalLink } from "@/components/ui/ExternalLink";
interface ProEvaluationProps {
  smiles: string;
  setSmiles: (smiles: string) => void;
  target: string;
  setTarget: (target: string) => void;
  targets: Target[];
  loadingTargets?: boolean;
  validation?: ValidationResult | null;
  setValidation?: (validation: ValidationResult | null) => void;
  taskId?: string | null;
  setTaskId?: (taskId: string | null) => void;
  status?: JobStatus | null;
  /** Estado de rehidratación de una corrida persistida al reabrir el caso. */
  resultRecovery?: {
    readonly state: "recovering" | "blocked";
    readonly message?: string;
    readonly requiresLogin?: boolean;
  } | null;
  onRetryResultRecovery?: () => void;
  setStatus?: (status: JobStatus | null) => void;
  busy?: boolean;
  setBusy?: (busy: boolean) => void;
  error?: string | null;
  setError?: (error: string | null) => void;
  isControl?: boolean;
  setIsControl?: (isControl: boolean) => void;
  isSaved?: boolean;
  setIsSaved?: (isSaved: boolean) => void;
  proteinData?: string | null;
  poseData?: string | null;
  suggestions?: MolecularSuggestion[];
  loadingSuggestions?: boolean;
  handleSave?: (customName?: string) => Promise<void>;
  /** Persiste en el resultado la firma que ya produjo el modal de Solana. */
  handleCertify?: (signature: string) => Promise<void> | void;
  handleDownloadCertificate?: () => Promise<void>;
  /**
   * Notifica trabajo asincrono LARGO que no pasa por `taskId` (MM-GBSA).
   * Existe para que el workspace de casos pueda impedir el cambio de caso
   * mientras ese calculo corre; sin esto quedaria huerfano al desmontar.
   */
  onLongRunningWorkChange?: (active: boolean) => void;
  handleDownloadComplex?: () => Promise<void>;
  handleValidate?: () => Promise<void>;
  handleSubmit?: (
    gridCenter?: [number, number, number],
    gridSize?: [number, number, number],
    customHotspots?: string[],
    peptideDockingEngine?: "esmfold" | "esmfold-pro" | "esmfold-experimental" | "colabfold",
    pipelineConfig?: CasePipelineConfig
  ) => Promise<void>;
  handleReset?: () => void;
  handleCancel?: () => Promise<void>;
  handleUseSuggestion?: (sug: MolecularSuggestion) => Promise<void>;
  startPolling?: (tid: string) => void;
  stopPolling?: () => void;
  onTargetUploadSuccess?: () => void;
  /** Ancla reproducible del caso después de su primera corrida registrada. */
  structuralSystem?: CaseStructuralSystem;
  /**
   * El ancla está SELLADA: alguna corrida del caso terminó en ella.
   *
   * Separado de `structuralSystem` a propósito. El sistema se escribe al nacer
   * el `taskId` —es el único instante en que la huella y la configuración
   * efectiva son las de esa corrida— pero no queda sellado hasta que una
   * corrida produce evidencia. Antes esto no existía y se bloqueaba en el
   * envío: una primera corrida que fallaba casaba el caso para siempre con una
   * configuración que nunca produjo nada, y la única salida era crear otro caso
   * y perder el nombre, el contexto y las notas.
   */
  structuralSystemSealed?: boolean;
  /** Abre el historial de corridas del caso. Ausente fuera de un caso. */
  onOpenRunHistory?: () => void;
  /** Cuántas corridas tiene el caso en su libro. */
  runCount?: number;
  /**
   * Panel de «Preparación de la corrida», inyectado por el contenedor.
   *
   * Llega como nodo en vez de construirse aquí porque su estado —el informe
   * del preflight— pertenece al caso, no a esta pantalla de presentación.
   * Duplicarlo aquí daría dos fuentes para la misma comprobación.
   */
  preparationSlot?: React.ReactNode;
  /**
   * Por qué no se puede ejecutar todavía, o `null` si se puede.
   *
   * Un botón deshabilitado sin explicación es un callejón sin salida: este
   * texto es lo que se enseña en su lugar.
   */
  runBlockedReason?: string | null;
  /** Configuración del caso que debe reaparecer al volver a abrirlo. */
  initialRunConfiguration?: {
    readonly center?: readonly [number, number, number];
    readonly size?: readonly [number, number, number];
    readonly customHotspots?: readonly string[];
    readonly dockingEngine?: string;
    readonly exhaustiveness?: number;
    readonly numPoses?: number;
    readonly pipelineConfig?: CasePipelineConfig;
  };
  /** Persiste toda la configuración de docking que invalida la comprobación. */
  onRunConfigurationChange?: (config: {
    center: [number, number, number];
    size: [number, number, number];
    customHotspots: string[];
    dockingEngine: string;
    exhaustiveness: number;
    numPoses: number;
    pipelineConfig: CasePipelineConfig;
  }) => void;
}

// ── Pipelines por familia (Family-Gated Stacking) ──
// Definiciones movidas a lib/pipelineDefinitions.ts (exportadas para tests).
// PIPELINES_BY_FAMILY es la fuente única de verdad del DOT.

export default function ProEvaluation({
  smiles,
  setSmiles,
  target,
  setTarget,
  targets,
  proteinData,
  poseData,
  onTargetUploadSuccess,
  structuralSystem,
  structuralSystemSealed = false,
  onOpenRunHistory,
  runCount = 0,
  status,
  resultRecovery,
  onRetryResultRecovery,
  setStatus,
  validation,
  busy,
  error,
  setError,
  isSaved,
  taskId,
  handleSave,
  handleCertify,
  handleDownloadCertificate,
  onLongRunningWorkChange,
  handleDownloadComplex,
  handleSubmit,
  handleReset,
  handleCancel,
  preparationSlot,
  runBlockedReason,
  initialRunConfiguration,
  onRunConfigurationChange,
}: ProEvaluationProps) {
  // NIVEL 2 KeepAlive recovery: el wrapper del KeepAlive pasa el flag de
  // visibilidad via Context (las Next.js pages no aceptan props custom).
  // El flag viaja a AdvancedMolstarViewer para forzar un handleResize al volver.
  const isActive = useKeepAliveActive();
  // null durante SSR/hidratación: ningún motor 3D se monta hasta comprobar
  // que el WebView puede crear un contexto. Esto evita el error crudo de Mol*.
  const [webglDisponible, setWebglDisponible] = useState<boolean | null>(null);
  useEffect(() => {
    setWebglDisponible(comprobarWebGL().disponible);
  }, []);

  const [showTargetModal, setShowTargetModal] = useState(false);
  const [showPdfPreview, setShowPdfPreview] = useState(false);
  const [showCertificationModal, setShowCertificationModal] = useState(false);
  const [receptorPdb, setReceptorPdb] = useState<string | null>(null);
  const [loadingReceptor, setLoadingReceptor] = useState(false);
  const [showResults, setShowResults] = useState(true);
  const [physicalFocusRequest, setPhysicalFocusRequest] = useState(0);
  const [poseComparison, setPoseComparison] = useState<{ leftRank: number; rightRank: number } | null>(null);
  // El sistema PROVISIONAL se enseña pero todavía se puede corregir; el
  // SELLADO ya no. `structuralSystemLocked` congela sólo lo que define el
  // sistema —receptor, caja, residuos—; el protocolo se sigue pudiendo cambiar
  // y cada corrida guarda el suyo.
  const structuralSystemLocked = Boolean(structuralSystem) && structuralSystemSealed;
  const structuralSystemProvisional = Boolean(structuralSystem) && !structuralSystemSealed;

  useEffect(() => {
    if (!showPdfPreview) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setShowPdfPreview(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [showPdfPreview]);

  // ── Estado LIVE del pipeline (alimentado por SSE) ──
  const [stageStates, setStageStates] = useState<Record<string, StageState>>({});
  const [stageMessages, setStageMessages] = useState<Record<string, string>>({});
  const [pipelineDone, setPipelineDone] = useState(false);
  const timelineStages = useMemo(
    () => stagesForPipeline(initialRunConfiguration?.pipelineConfig),
    [initialRunConfiguration?.pipelineConfig],
  );
  // Poses/PDB reales descargados vía /evaluation/files/* (el page no los fetchea)
  const [realPoseData, setRealPoseData] = useState<string | null>(null);
  const [realProteinData, setRealProteinData] = useState<string | null>(null);
  // Interacciones no-covalentes ligando-proteína (PLIF) para el Web3D
  const [interactions, setInteractions] = useState<InteractionDatum[]>([]);

  // Resultado real: solo cuando el polling (autoridad final) dice SUCCESS.
  // Sin resultado real la sección de resultados no se renderiza (estado vacío).
  const realResult: EvaluationResult | null =
    status?.status === "SUCCESS" && status.result ? status.result : null;
  const hasJob = !!status;
  const isRunning = hasJob && status!.status !== "SUCCESS" && status!.status !== "FAILURE";
  const showProcessing = busy === true || isRunning;
  const failed = hasJob && status!.status === "FAILURE";
  // FIX (v1.7.5): si el backend reportó SUCCESS pero sin resultado (result
  // null por un fallo de validación silencioso), NO mostrar un resultado
  // inventado — tratar como error honesto.
  const silentResultLoss =
    hasJob && status!.status === "SUCCESS" && !status!.result && !resultRecovery;
  const displayResult: any = silentResultLoss ? null : realResult;
  // Link de blockchain: solo con un resultado real certificado.
  const blockchainTxId = realResult?.blockchain_tx_id ?? null;

  // Mapeo stage_id SSE (registry.py) → orb id del DOT/timeline en
  // lib/pipelineStream.ts (SSE_TO_ORB + stageEventToOrbUpdate — exportados
  // para unit tests). validation→Curación, conformer→3D ETKDG, docking→Vina,
  // xgb→XGBoost, clgnn→CL-GNN, openmm→OpenMM, mmgbsa→MM-GBSA (post-hoc).
  // properties/sa_filter no tienen orb (pre-score, alimentan Parámetros).

  // ── Estados para el modal de Opciones ──
  const [showOptionsModal, setShowOptionsModal] = useState(false);
  // Visor activo: "molstar" (full, poses) | "web3d" (ligero, átomos + grid)
  const [viewerMode, setViewerMode] = useState<"molstar" | "web3d">("molstar");
  // Cámara compartida entre visores (vista COMPLETA: position+target) para
  // sincronizar posición Y orientación al cambiar de visor.
  const [molstarCamera, setMolstarCamera] = useState<{ position: [number, number, number]; target: [number, number, number]; distance: number } | null>(null);
  const [web3dCamera, setWeb3dCamera] = useState<{ position: [number, number, number]; target: [number, number, number]; distance: number } | null>(null);
  const [dockingEngine, setDockingEngine] = useState<DockingEngineConfig>(() => ({
    engine:
      initialRunConfiguration?.dockingEngine === "qvina2" ||
      initialRunConfiguration?.dockingEngine === "diffdock"
        ? initialRunConfiguration.dockingEngine
        : "vina",
    peptideEngine: null,
    gnnPrecision: "fp32",
  }));
  const [gridBox, setGridBox] = useState<GridBoxConfig>(() => ({
    centerX: initialRunConfiguration?.center?.[0] ?? 0,
    centerY: initialRunConfiguration?.center?.[1] ?? 0,
    centerZ: initialRunConfiguration?.center?.[2] ?? 0,
    sizeX: initialRunConfiguration?.size?.[0] ?? 22.5,
    sizeY: initialRunConfiguration?.size?.[1] ?? 22.5,
    sizeZ: initialRunConfiguration?.size?.[2] ?? 22.5,
    exhaustiveness: initialRunConfiguration?.exhaustiveness ?? 8,
    numModes: initialRunConfiguration?.numPoses ?? 9,
  }));
  // Hotspots del receptor seleccionado que el usuario puede filtrar.
  const [customHotspots, setCustomHotspots] = useState<string[] | null>(() =>
    initialRunConfiguration?.customHotspots?.length
      ? [...initialRunConfiguration.customHotspots]
      : null,
  );

  // Hotspots del target actual (del catálogo calibrado). La selección
  // personalizada se conserva al reabrir el mismo receptor.
  const selectedTargetObj = useMemo(
    () => targets.find((x) => x.pdb_id === target) ?? null,
    [targets, target]
  );
  const canRunEvaluation = Boolean(smiles.trim() && target && validation?.is_valid !== false);
  const targetHotspotsList = useMemo(
    () =>
      (selectedTargetObj?.hotspots ?? []).map((h) => ({
        name: h.name,
        importance: h.importance ?? 0.5,
        // Coordenadas REALES del CA (backend, misma cadena del receptor).
        ...(h.x != null && h.y != null && h.z != null ? { x: h.x, y: h.y, z: h.z } : {}),
      })),
    [selectedTargetObj]
  );
  const [advancedOpts, setAdvancedOpts] = useState<AdvancedConfig>(() => ({
    // Reabrir una corrida guardada tiene que recuperar SU pH, no el por
    // defecto: si no, el panel enseñaría 7.4 sobre un expediente que se acopló
    // a otro pH, y al reejecutar lo cambiaría en silencio.
    protonationPh: Number(initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.ph ?? 7.4) || 7.4,
    numWorkers: initialRunConfiguration?.pipelineConfig?.pro_workers ?? 4,
    parallelDocks: initialRunConfiguration?.pipelineConfig?.pro_parallel_docks ?? 2,
    enableSelectivity: initialRunConfiguration?.pipelineConfig?.pro_selectivity ?? false,
    selectedAntiTargets: [...(initialRunConfiguration?.pipelineConfig?.pro_anti_targets ?? ["5VA1", "4NY4", "4NC3", "1SO2", "6MVW"])],
    enableMMGBSA: initialRunConfiguration?.pipelineConfig?.pro_mmgbsa ?? false,
    mmgbsaSteps: initialRunConfiguration?.pipelineConfig?.pro_mmgbsa_steps ?? 1000,
    // ADMET-AI es OPT-IN. `!== false` encendía el interruptor siempre que la
    // configuración no lo apagara a mano —es decir, casi siempre—, mientras el
    // backend leía la MISMA clave con `.get("run_admet_ai", False)` y corría
    // sin ADMET. La casilla decía una cosa y la corrida hacía otra. Ahora las
    // dos lecturas son la misma: sólo un `true` explícito lo enciende, y una
    // corrida guardada que lo traía sigue apareciendo encendida al reabrirla.
    enableADMET:
      initialRunConfiguration?.pipelineConfig?.stage_params?.properties?.run_admet_ai === true,
  }));

  // ── Estado MM-GBSA: flujo real (POST /pro/mmgbsa/{id}) ──
  // El modal abre SOLO si el usuario todavía no tiene resultado: pipeline con
  // mmgbsa_score serializado (WS2) o cálculo on-demand completado → sin modal.
  const [showMmgbsaModal, setShowMmgbsaModal] = useState(false);
  const [mmgbsaState, setMmgbsaState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [mmgbsaResult, setMmgbsaResult] = useState<Awaited<ReturnType<typeof runMmgbsa>> | null>(null);
  const [mmgbsaError, setMmgbsaError] = useState<string | null>(null);
  const [mmgbsaPoseRank, setMmgbsaPoseRank] = useState(1);
  const [mmgbsaNumSteps, setMmgbsaNumSteps] = useState(1000);

  useEffect(() => {
    if (!showMmgbsaModal) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && mmgbsaState !== "running") {
        event.preventDefault();
        setShowMmgbsaModal(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [showMmgbsaModal, mmgbsaState]);

  // Reporta MM-GBSA como TRABAJO VIVO al contenedor del caso. Es un cálculo
  // largo que no pasa por `taskId`, así que sin este aviso el workspace lo
  // daría por inexistente y permitiría cambiar de caso a mitad, dejándolo
  // huérfano. No altera el cálculo: sólo lo declara.
  useEffect(() => {
    onLongRunningWorkChange?.(mmgbsaState === "running");
  }, [mmgbsaState, onLongRunningWorkChange]);
  // ── "Ya calculado": el usuario YA tiene resultado MM-GBSA ──
  // 1) El pipeline lo corrió (pro_mmgbsa) → mmgbsa_score serializado (WS2).
  //    ΔG es negativo en kcal/mol → `!= null` (no truthy), por si diera 0.
  // 2) El usuario lo calculó on-demand desde el modal → estado local, porque
  //    el endpoint /pro/mmgbsa/{id} NO persiste al ORM (verificado en
  //    backend/api/routers/pro_features.py).
  // En ambos casos el orb NO es clickeable y muestra el valor directo.
  //
  // ACTUALIZADO: el endpoint on-demand ya NO es «solo compute + return». Antes
  // devolvía el ΔG sin escribirlo, así que recargar la página borraba minutos
  // de minimización y el dossier declaraba «no calculado» algo que el usuario
  // había visto en pantalla. Ahora persiste `mmgbsa_score`, y por eso esta
  // condición basta para reconocerlo tras un remontaje.
  const mmgbsaAlreadyDone =
    (realResult != null && realResult.mmgbsa_score != null) ||
    mmgbsaState === "done";
  const availablePoseRanks = useMemo(() => {
    const ranks = (realResult?.docking_poses ?? []).map((pose: any, index: number) => {
      const rank = Number(pose?.rank);
      return Number.isInteger(rank) && rank > 0 ? rank : index + 1;
    });
    return ranks.length > 0 ? [...new Set(ranks)] : [1];
  }, [realResult?.docking_poses]);

  useEffect(() => {
    if (!availablePoseRanks.includes(mmgbsaPoseRank)) {
      setMmgbsaPoseRank(availablePoseRanks[0] ?? 1);
    }
  }, [availablePoseRanks, mmgbsaPoseRank]);

  // Ejecutar únicamente el cálculo real; nunca fabricar una salida demo.
  const handleRunMmgbsa = useCallback(async () => {
    if (mmgbsaState === "running") return;
    setMmgbsaState("running");
    setMmgbsaError(null);
    setMmgbsaResult(null);
    const moleculeId = realResult?.molecule_id;
    if (!moleculeId) {
      setMmgbsaError("MM-GBSA requiere una evaluación real con molecule_id.");
      setMmgbsaState("error");
      return;
    }
    try {
      const res = await runMmgbsa(moleculeId, mmgbsaPoseRank, mmgbsaNumSteps);
      setMmgbsaResult(res);
      setMmgbsaState("done");
      // Refetch del job: si el backend algún día persiste mmgbsa_score en el
      // ORM, el orb pasa a done vía realResult. Hoy NO persiste → el orb
      // queda done por el estado local (mmgbsaAlreadyDone).
      if (taskId) {
        try {
          const fresh = await getJobStatus(taskId);
          setStatus?.(fresh);
        } catch {
          // El polling del page (2s) sigue siendo la autoridad; no bloquear.
        }
      }
    } catch (err) {
      setMmgbsaError(err instanceof Error ? err.message : String(err));
      setMmgbsaState("error");
    }
  }, [mmgbsaState, realResult?.molecule_id, mmgbsaPoseRank, mmgbsaNumSteps, taskId, setStatus]);

  // ── ADMET-AI post-docking ────────────────────────────────────────────────
  //
  // ADMET-AI es opt-in y la decisión se toma en Opciones ANTES de ejecutar.
  // Quien no lo marcó se quedaba sin perfil para siempre: la única forma de
  // tenerlo era volver a acoplar la molécula entera —minutos de Vina— para
  // recalcular algo que sólo depende del SMILES.
  //
  // Mismo trato que MM-GBSA: se pide después, sobre una corrida que ya existe,
  // y el backend lo PERSISTE, así que el dossier lo verá.
  const [admetState, setAdmetState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [admetError, setAdmetError] = useState<string | null>(null);

  /** Ya hay perfil: del pipeline o de un cálculo post-docking de esta sesión. */
  const admetYaEsta =
    realResult?.blood_viability_score != null || admetState === "done";

  const handleRunAdmet = useCallback(async () => {
    if (admetState === "running") return;
    const moleculeId = realResult?.molecule_id;
    if (!moleculeId) {
      setAdmetError("Requiere una corrida terminada con una molécula identificable.");
      setAdmetState("error");
      return;
    }
    setAdmetState("running");
    setAdmetError(null);
    try {
      const perfil = await runAdmet(moleculeId);
      // El backend lo guarda en la base, pero `status` es la INSTANTÁNEA del
      // trabajo y no se entera sola: sin fusionarlo aquí, el panel de
      // propiedades seguiría diciendo que no hay perfil hasta recargar. Es lo
      // mismo que ya le pasa a MM-GBSA.
      if (status?.result) {
        setStatus?.({
          ...status,
          result: {
            ...status.result,
            blood_viability_score: perfil.blood_viability_score,
            blood_solubility_logs: perfil.blood_solubility_logs,
            blood_ppb_category: perfil.blood_ppb_category,
            blood_bbb_permeable: perfil.blood_bbb_permeable,
            blood_bbb_motivo: perfil.blood_bbb_motivo,
            blood_cns_mpo: perfil.blood_cns_mpo,
            blood_hia_permeable: perfil.blood_hia_permeable,
            blood_systemic_reactivity: perfil.blood_systemic_reactivity,
            blood_tabpfn_estado: perfil.blood_tabpfn_estado,
          },
        } as JobStatus);
      }
      // Se calculó pero no se pudo guardar: el usuario lo ve y el dossier no lo
      // leería. Decirlo es la diferencia entre un número y un número fiable.
      setAdmetError(
        perfil.persistido
          ? null
          : "El perfil se calculó pero NO se pudo guardar: el dossier de esta corrida no lo incluirá.",
      );
      setAdmetState("done");
    } catch (err) {
      setAdmetError(err instanceof Error ? err.message : String(err));
      setAdmetState("error");
    }
  }, [admetState, realResult?.molecule_id, status, setStatus]);

  // ── Reactividad del Grid Box con el receptor seleccionado ──
  // Cuando el usuario elige un target, el centro y tamaño del grid box se
  // sincronizan con las coordenadas reales calibradas de ese receptor.
  // Así el usuario nunca ve centro (0,0,0) ni tamaños por defecto que no
  // correspondan al bolsillo real.
  const gridTargetRef = useRef(initialRunConfiguration?.center ? target : null);
  useEffect(() => {
    if (structuralSystemLocked || !target || target.length < 3) return;
    const t = targets.find((x) => x.pdb_id === target);
    if (!t) return;
    // Una caja persistida pertenece a este target y se respeta. La caja del
    // catálogo sólo se carga al elegir OTRO receptor (o al abrir un caso
    // antiguo que todavía no guardaba caja).
    if (gridTargetRef.current === target) return;
    gridTargetRef.current = target;
    setCustomHotspots(null);
    const hasRealCenter =
      t.grid_center_x != null && t.grid_center_y != null && t.grid_center_z != null;
    if (hasRealCenter) {
      setGridBox((prev) => ({
        ...prev,
        centerX: Number(t.grid_center_x),
        centerY: Number(t.grid_center_y),
        centerZ: Number(t.grid_center_z),
        sizeX: Number(t.grid_size_x ?? prev.sizeX),
        sizeY: Number(t.grid_size_y ?? prev.sizeY),
        sizeZ: Number(t.grid_size_z ?? prev.sizeZ),
      }));
    }
  }, [structuralSystemLocked, target, targets]);

  // Cargar el PDB del receptor inmediatamente al seleccionarlo — sin esperar
  // a que el docking termine. Así el canvas 3D (MolStar) muestra la proteína
  // apenas el usuario elige un target, no solo después de la evaluación.
  useEffect(() => {
    // FIX (Tauri): al cambiar de receptor, descartar los datos de la
    // evaluación ANTERIOR (realPoseData/realProteinData). Sin esto, el PDB de
    // la primera evaluación ganaba la cadena `proteinData ?? realProteinData ??
    // receptorPdb` y el visor MolStar seguía mostrando el receptor viejo.
    setRealPoseData(null);
    setRealProteinData(null);
    setInteractions([]);
    if (!target || target.length < 3) {
      setReceptorPdb(null);
      return;
    }
    let cancelled = false;
    setLoadingReceptor(true);
    getTargetPdb(target)
      .then((pdb) => {
        if (!cancelled) setReceptorPdb(pdb);
      })
      .catch((err) => {
        console.warn(`[ProEvaluation] No se pudo cargar PDB del receptor ${target}:`, err);
      })
      .finally(() => {
        if (!cancelled) setLoadingReceptor(false);
      });
    return () => { cancelled = true; };
  }, [target]);

  // ── SSE: alimenta los orbs del PipelineTimeline en vivo ──
  // El endpoint /evaluation/stream/{task_id} hace REPLAY de eventos cacheados,
  // así que suscribirse una vez por taskId alcanza. El polling del page
  // (getJobStatus 2s) sigue siendo la autoridad para el estado final.
  useEffect(() => {
    if (!taskId) return;
    setStageStates({});
    setStageMessages({});
    setPipelineDone(false);
    // La suscripción es asíncrona: la dirección del backend se resuelve contra
    // el puerto que eligió Rust. Si el efecto se limpia antes de que abra, se
    // cierra igual — sin esa bandera quedaría un EventSource huérfano por cada
    // corrida que se cancele rápido.
    let closed = false;
    let close: (() => void) | null = null;
    void subscribeToPipelineEvents(
      taskId,
      (event: PipelineEvent) => {
        // pipeline_done/error cierran el timeline sin importar el orb.
        if (event.type === "pipeline_done" || event.type === "pipeline_error") {
          setPipelineDone(true);
          return;
        }
        // Traducción stage SSE → orb (null para stages sin orb o desconocidos:
        // properties/sa_filter alimentan Parámetros, no el DOT; degradación
        // suave ante stage_ids nuevos del backend).
        const update = stageEventToOrbUpdate(event);
        if (!update) return;
        // Destructure a consts: TS no preserva el narrowing de propiedades
        // (update.message) dentro de closures de setState.
        const { orb, state, message } = update;
        setStageStates((prev) => ({ ...prev, [orb]: state }));
        if (message !== undefined) {
          setStageMessages((prev) => ({ ...prev, [orb]: message }));
        }
      },
      () => {
        // SSE cerrado (pipeline_done/error o error de red): el polling decide.
      },
    ).then((unsubscribe) => {
      if (closed) unsubscribe();
      else close = unsubscribe;
    });
    return () => {
      closed = true;
      close?.();
    };
  }, [taskId]);

  // ── Poses/PDB reales: si el resultado trae poses_file_path, descargar el SDF
  // vía /evaluation/files/poses/{molecule_id} para el viewer 3D y el tab Docking.
  useEffect(() => {
    const mid = realResult?.molecule_id;
    if (!mid) return;
    if (realResult?.poses_file_path && !poseData && !realPoseData) {
      getPoseFile(mid)
        .then((sdf) => { if (sdf) setRealPoseData(sdf); })
        .catch(() => {});
    }
    if (!proteinData && !realProteinData) {
      getProteinFile(mid)
        .then((pdb) => { if (pdb) setRealProteinData(pdb); })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [realResult?.molecule_id, realResult?.poses_file_path, poseData, proteinData]);

  // ── Interacciones PLIF: líneas discontinuas ligando-proteína (Web3D) ──
  useEffect(() => {
    const mid = realResult?.molecule_id;
    if (!mid) {
      setInteractions([]);
      return;
    }
    let cancelled = false;
    getInteractions(mid)
      .then((report) => {
        if (!cancelled) setInteractions(report?.interactions ?? []);
      })
      .catch(() => {
        if (!cancelled) setInteractions([]);
      });
    return () => { cancelled = true; };
  }, [realResult?.molecule_id]);

  const heroRef = useRef<HTMLDivElement>(null);
  const dotRef = useRef<HTMLDivElement>(null);
  const verifyRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLButtonElement>(null);
  const mmgbsaLabelRef = useRef<HTMLSpanElement>(null);

  const handleOpenTarget = () => {
    if (structuralSystemLocked) return;
    if (targetRef.current) {
      targetRef.current.animate([{ transform: "scale(0.985)" }, { transform: "scale(1)" }], { duration: 220, easing: "ease-out" });
    }
    setShowTargetModal(true);
  };

  const runReveal = useCallback(() => {
    const sections = [heroRef.current, dotRef.current, verifyRef.current].filter(
      (section): section is HTMLDivElement => Boolean(section),
    );
    if (sections.length === 0) return;

    sections.forEach((section) => {
      cancelAnimations(section);
      section.style.opacity = "0";
      section.style.transform = "translateY(20px)";
      section.style.filter = "blur(4px)";
    });

    const sectionTimings = [
      { duration: 600, delay: 0 },
      { duration: 500, delay: 350 },
      { duration: 350, delay: 700 },
    ];
    sections.forEach((section, index) => {
      const timing = sectionTimings[index] ?? sectionTimings[sectionTimings.length - 1];
      animateElements(section, [
        { opacity: 0, transform: "translateY(20px)", filter: "blur(4px)" },
        { opacity: 1, transform: "translateY(0)", filter: "blur(0px)" },
      ], { ...timing, fill: "forwards", easing: "cubic-bezier(0.16, 1, 0.3, 1)" });
    });

    const dots = dotRef.current?.querySelectorAll(".dot-node");
    if (dots) {
      Array.from(dots).forEach((dot, index) => {
        cancelAnimations(dot);
        animateElements(dot, [
          { opacity: 0, transform: "translateY(8px) scale(0.8)" },
          { opacity: 1, transform: "translateY(0) scale(1)" },
        ], { duration: 300, delay: 650 + index * 80, fill: "forwards", easing: "ease-out" });
      });
    }
  }, []);

  // Al terminar el procesamiento (resultado real o idle mock) → native reveal.
  // El score animado sale del resultado real; si es null cae a 0 (null-safe).
  useEffect(() => {
    if (showProcessing || !showResults || !displayResult) {
      return;
    }
    const timeout = setTimeout(() => {
      // Deferir native reveal hasta que React commit el DOM
      requestAnimationFrame(() => runReveal());
    }, 60);
    return () => clearTimeout(timeout);
  }, [showProcessing, showResults, displayResult?.id, runReveal]);

  return (
    <div className="min-h-full bg-surface-950 p-3 sm:p-4 md:p-8 flex flex-col items-center justify-start space-y-4 sm:space-y-6">
      
      {/* Contenedor Principal de Visores: 2D Visor (Izquierda) + 3D Visor (Derecha) */}
      <div className="w-full max-w-[1600px] grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        
        {/* Left Column: 2D Ketcher Visor & Standalone SMILES Element */}
        <div className="space-y-4">
          <div className="h-[min(56vh,480px)] min-h-[320px] sm:h-[min(62vh,560px)] md:h-[640px] border border-zinc-800 rounded-xl overflow-hidden bg-black shadow-2xl flex flex-col justify-center">
            <KetcherEditor
              initialSmiles={smiles}
              onSmilesChange={(newSmiles: string) => setSmiles(newSmiles)}
              height={640}
              showSmilesInput={false}
            />
          </div>

          {/* Standalone SMILES Element (Strict h-14 equal height) */}
          <div className="h-14 border border-zinc-800 rounded-2xl bg-zinc-950 shadow-lg px-4 flex items-center gap-3">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-purple-400 shrink-0">
              SMILES:
            </span>
            <input
              type="text"
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              className="flex-1 bg-black border border-zinc-800 rounded-xl px-3 py-1.5 font-mono text-xs text-white placeholder-zinc-600 outline-none focus:border-purple-500/40 transition-colors h-9"
              placeholder="Estructura SMILES"
            />
          </div>
        </div>

        {/* Right Column: 3D Visor (MolStar ↔ Web3D) & Standalone Receptor Element */}
        <div className="space-y-4">
          <div className="h-[min(56vh,480px)] min-h-[320px] sm:h-[min(62vh,560px)] md:h-[640px] border border-zinc-800 rounded-xl overflow-hidden bg-black shadow-2xl relative flex items-center justify-center">
            {/* Sólo se monta el visor activo: evita dos motores WebGL consumiendo
                memoria y contexto GPU a la vez. La cámara de cada modo se
                conserva en el estado del contenedor al cambiar. */}
            {webglDisponible === false ? (
              <AvisoSinWebGL />
            ) : webglDisponible === null ? (
              <div role="status" className="font-mono text-xs uppercase tracking-wider text-zinc-500">
                Comprobando compatibilidad del visor 3D…
              </div>
            ) : viewerMode === "molstar" ? (
              <AdvancedMolstarViewer
                proteinData={proteinData ?? realProteinData ?? receptorPdb ?? undefined}
                poseData={poseData ?? realPoseData ?? undefined}
                height={640}
                isActive={isActive}
                onSwitchViewer={() => setViewerMode("web3d")}
                viewerLabel="Web3D"
                gridInfo={
                  gridBox.centerX !== 0 || gridBox.centerY !== 0 || gridBox.centerZ !== 0
                    ? { centerX: gridBox.centerX, centerY: gridBox.centerY, centerZ: gridBox.centerZ,
                        sizeX: gridBox.sizeX, sizeY: gridBox.sizeY, sizeZ: gridBox.sizeZ }
                    : null
                }
                externalCamera={web3dCamera}
                onCameraChange={setMolstarCamera}
              />
            ) : (
              <Web3DViewer
                proteinData={proteinData ?? realProteinData ?? receptorPdb ?? undefined}
                poseData={poseData ?? realPoseData ?? undefined}
                interactions={interactions.length > 0 ? interactions : undefined}
                chain={selectedTargetObj?.chain ?? undefined}
                hotspots={targetHotspotsList}
                gridInfo={
                  gridBox.centerX !== 0 || gridBox.centerY !== 0 || gridBox.centerZ !== 0
                    ? { centerX: gridBox.centerX, centerY: gridBox.centerY, centerZ: gridBox.centerZ,
                        sizeX: gridBox.sizeX, sizeY: gridBox.sizeY, sizeZ: gridBox.sizeZ }
                    : null
                }
                onSwitchViewer={() => setViewerMode("molstar")}
                viewerLabel="MolStar"
                externalCamera={molstarCamera}
                onCameraChange={setWeb3dCamera}
                active={viewerMode === "web3d"}
              />
            )}
          </div>

          {/* Standalone Receptor Selector Element (Strict h-14 equal height) */}
          <button
            type="button"
            ref={targetRef}
            onClick={structuralSystemLocked ? undefined : handleOpenTarget}
            aria-disabled={structuralSystemLocked || undefined}
            disabled={structuralSystemLocked}
            className={`h-14 w-full border border-zinc-800 rounded-2xl bg-zinc-950 shadow-lg px-4 flex items-center justify-between gap-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 group ${
              structuralSystemLocked
                ? "cursor-default border-purple-500/30"
                : "cursor-pointer hover:border-purple-500/30"
            }`}
          >
            <div className="flex items-center gap-2.5 truncate">
              <Database size={15} className="shrink-0 text-purple-400 transition-colors group-hover:text-purple-300" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-white truncate">
                {loadingReceptor ? (
                  <span className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse" />
                    Cargando {target}...
                  </span>
                ) : target ? (
                  `Receptor elegido: ${target}`
                ) : (
                  "Elige receptor"
                )}
              </span>
            </div>
            <span className="shrink-0 font-mono text-xs font-semibold text-zinc-200 transition-colors group-hover:text-purple-200">
              {structuralSystemLocked ? "Sistema fijado" : target ? "Cambiar ↵" : "Seleccionar ↵"}
            </span>
          </button>

          {/* Lo que se sabe del sitio de ESTE receptor, dicho donde el usuario
              está a punto de lanzar la evaluación. El catálogo ya lo declara en
              la tarjeta; repetirlo aquí no es redundancia: quien abre un caso
              guardado, o vuelve tras cambiar de pestaña, no pasa por el
              catálogo y se llevaría el número sin la condición. */}
          {selectedTargetObj && (
            <div className="mt-2 px-1">
              <ChipsDelSitio target={selectedTargetObj} variante="linea" />
            </div>
          )}
        </div>

        {/* El sistema pertenece al par ligando-receptor, no sólo al receptor.
            En escritorio ocupa ambas columnas; en móvil cae debajo de los dos
            selectores sin introducir desplazamiento horizontal. */}
        {structuralSystem && (
          <div className="min-w-0 rounded-2xl border border-purple-500/20 bg-purple-500/[0.04] px-4 py-3 lg:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-xs font-bold uppercase tracking-[0.12em] text-purple-200">
                {structuralSystemProvisional
                  ? "Sistema estructural provisional"
                  : "Sistema estructural fijado"}
              </p>
              <span className="font-mono text-xs font-medium text-zinc-300">
                desde la corrida {structuralSystem.sourceRunTaskId.slice(0, 8)}…
              </span>
            </div>
            <p className="mt-1.5 text-sm font-semibold leading-6 text-zinc-100">
              {structuralSystem.receptor.pdbId}
              {structuralSystem.receptor.chain ? ` · cadena ${structuralSystem.receptor.chain}` : ""}
              {" · caja "}
              {structuralSystem.grid.size.map((value) => value.toFixed(1)).join(" × ")} Å
              {" · "}{structuralSystem.dockingEngine}
            </p>
            <p className="mt-1 text-sm font-medium leading-6 text-zinc-300">
              {structuralSystemProvisional
                ? "Todavía no ha terminado ninguna corrida en este sistema, así que aún puedes corregir receptor o caja. Quedará fijado cuando una corrida termine."
                : "Puedes evaluar nuevos SMILES y cambiar el protocolo en este sistema. Para cambiar receptor, caja o residuos, crea otro caso."}
            </p>
          </div>
        )}

      </div>

      {/* Preparación de la corrida.
          Aquí vivía `EvaluationReadinessPanel`, que respondía a esta misma
          pregunta CONJETURANDO desde el navegador: «SMILES presente; se
          validará al ejecutar». Dos respuestas distintas a la misma pregunta,
          y la que ocupaba el sitio era la que no había mirado los archivos.
          Ahora el hueco lo llena la comprobación previa real. */}
      {preparationSlot}

      {/* ── Botonera de Control ── */}
      <div className="w-full max-w-[1600px] flex flex-wrap items-center justify-between gap-4 p-4 border border-zinc-800/80 rounded-2xl bg-zinc-950/80 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowResults((v) => !v)}
            className={`flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 cursor-pointer ${
              showResults 
                ? "bg-purple-950/40 border border-purple-500/40 text-purple-300 shadow-sm" 
                : "bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white"
            }`}
          >
            <Activity size={15} className="text-purple-400" />
            {showResults ? "Ocultar Resultados" : "Ver Resultados"}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowOptionsModal(true)}
            title={
              structuralSystemLocked
                ? "Caja y residuos fijados por la primera corrida que terminó. El protocolo se puede cambiar."
                : undefined
            }
            className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:bg-zinc-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 cursor-pointer"
          >
            <Settings size={14} />
            Opciones
          </button>

          {/* El libro de corridas del caso. Antes no había ninguna puerta: la
              corrida anterior seguía intacta en el backend y el caso había
              perdido el puntero, así que recuperarla exigía buscarla en Moldex
              o en el historial global y repetirla desde cero. */}
          {onOpenRunHistory && (
            <button
              type="button"
              onClick={onOpenRunHistory}
              disabled={runCount === 0}
              title={
                runCount === 0
                  ? "Este caso todavía no ha lanzado ninguna evaluación."
                  : "Ver las evaluaciones anteriores de este caso"
              }
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:bg-zinc-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 cursor-pointer disabled:cursor-not-allowed disabled:opacity-45"
            >
              <History size={14} />
              Evaluaciones anteriores
              {runCount > 0 && (
                <span className="rounded-md bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300">
                  {runCount}
                </span>
              )}
            </button>
          )}

          <button 
            onClick={() => {
              // Configuración real del pipeline desde el modal de Opciones:
              // grid_center/grid_size del GridBox, engine del docking y
              // avanzadas (selectividad, MMGBSA, workers) del panel Pro.
              handleSubmit?.(
                [gridBox.centerX, gridBox.centerY, gridBox.centerZ],
                [gridBox.sizeX, gridBox.sizeY, gridBox.sizeZ],
                customHotspots ?? undefined,
                dockingEngine.peptideEngine ?? undefined,
                {
                  enabled_stages: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
                  stage_params: {
                    docking: { exhaustiveness: gridBox.exhaustiveness, num_poses: gridBox.numModes },
                    // NO se declara aquí `conformer`. Este objeto llega a
                    // `handleSubmit` como `_pipelineConfig` y se DESCARTA: lo
                    // que se ejecuta es la copia que inspeccionó el preflight,
                    // para que la huella firmada describa la corrida real.
                    // El protocolo del confórmero —número y pH— se escribe en
                    // los inputs del caso: `conformers` desde el panel de
                    // preparación y `ph` al aplicar Opciones. Ponerlo también
                    // aquí no haría nada y sugeriría que sí.
                    // La elección de ADMET viaja SIEMPRE, encendida o apagada.
                    // Omitirla dejaba que el defecto del backend decidiera por
                    // el usuario: el interruptor de Opciones no llegaba a la
                    // corrida y quedaba de adorno.
                    properties: { run_admet_ai: advancedOpts.enableADMET },
                  },
                  docking_engine: dockingEngine.engine,
                  pro_workers: advancedOpts.numWorkers,
                  pro_parallel_docks: advancedOpts.parallelDocks,
                  pro_selectivity: advancedOpts.enableSelectivity,
                  pro_anti_targets: advancedOpts.selectedAntiTargets,
                  pro_mmgbsa: advancedOpts.enableMMGBSA,
                  pro_mmgbsa_steps: advancedOpts.mmgbsaSteps,
                  gnn_precision: dockingEngine.gnnPrecision,
                  peptide_docking_engine: dockingEngine.peptideEngine ?? undefined,
                }
              );
            }}
            disabled={busy || isRunning || !canRunEvaluation || Boolean(runBlockedReason)}
            title={
              runBlockedReason ??
              (!canRunEvaluation ? "Añade un SMILES válido y selecciona un receptor" : undefined)
            }
            aria-describedby={runBlockedReason ? "run-blocked-reason" : undefined}
            className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-purple-400/30 bg-purple-600 px-6 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white shadow-lg shadow-purple-950/50 transition-colors hover:bg-purple-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy || isRunning ? (
              <>
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white inline-block" />
                Evaluando...
              </>
            ) : (
              <>
                <Play size={14} />
                Ejecutar Evaluación
              </>
            )}
          </button>

          {/* Botón Cancelar: mata todos los procesos del pipeline (incl. MM-GBSA) */}
          {(busy || isRunning) && (
            <button
              onClick={() => {
                void handleCancel?.();
              }}
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-rose-400/30 bg-rose-600/80 px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white transition-colors hover:bg-rose-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-300 cursor-pointer"
              title="Cancela la evaluación y mata todos los procesos (docking, MM-GBSA, etc.)"
            >
              <X size={14} />
              Cancelar
            </button>
          )}
        </div>
      </div>

      {/* La razón del bloqueo se ENSEÑA, no sólo se anuncia en un `title`:
          un tooltip no existe para quien navega con teclado ni en móvil. */}
      {runBlockedReason && (
        <p
          id="run-blocked-reason"
          role="status"
          className="w-full max-w-[1600px] rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3 text-xs leading-relaxed text-zinc-400"
        >
          {runBlockedReason}
        </p>
      )}

      {/* ── Banner de error (submit sin target, backend failure, etc.) ── */}
      {(error || (failed && status?.error)) && (
        <div role="alert" aria-live="assertive" className="w-full max-w-[1600px] rounded-2xl border border-rose-500/30 bg-rose-950/30 px-4 py-3 text-xs font-mono text-rose-300 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0 text-rose-400" />
          <span className="leading-relaxed">{error ?? status?.error}</span>
        </div>
      )}

      {/* ─── Pantalla de Carga: ThinkingOrb + Pipeline Timeline LIVE (SSE) ─── */}
      {showProcessing && (
        <div className="w-full max-w-[1600px] flex flex-col items-center justify-center gap-4 animate-in fade-in duration-300">
          <ThinkingOrb state="processing" size="lg" label="Procesando resultados del pipeline" />
          <PipelineTimeline
            stages={timelineStages}
            stageStates={stageStates}
            stageMessages={stageMessages}
            isDone={pipelineDone}
            failed={failed}
            statusLabel={taskId ? `Pipeline · task ${taskId.slice(0, 8)}…` : undefined}
          />
        </div>
      )}

      {/* ─── FALLO: pantalla de error en vez de resultados ─── */}
      {showResults && failed && !showProcessing && (
        <div className="w-full max-w-[1600px] rounded-2xl border border-rose-500/25 bg-rose-950/20 p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300">
          <AlertTriangle size={40} className="text-rose-400/70" />
          <p className="text-sm font-black uppercase tracking-widest text-rose-300 font-mono">
            La evaluación falló
          </p>
          <p className="text-xs font-mono text-white/40 max-w-lg leading-relaxed">
            {status?.error ?? error ?? "Error desconocido durante el pipeline."}
          </p>
          <button
            onClick={() => handleReset?.()}
            className="mt-2 min-h-11 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2 font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400 cursor-pointer"
          >
            Reiniciar
          </button>
        </div>
      )}

      {showResults && resultRecovery && realResult === null && !showProcessing && (
        <div
          role={resultRecovery.state === "blocked" ? "alert" : "status"}
          className={`w-full max-w-[1600px] rounded-2xl border p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300 ${
            resultRecovery.state === "blocked"
              ? "border-amber-500/25 bg-amber-950/20"
              : "border-brand-500/25 bg-surface-900"
          }`}
        >
          {resultRecovery.state === "recovering" ? (
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-brand-400/30 border-t-brand-400" aria-hidden="true" />
          ) : (
            <AlertTriangle size={40} className="text-amber-400/70" aria-hidden="true" />
          )}
          <p className={`text-sm font-black uppercase tracking-widest font-mono ${resultRecovery.state === "blocked" ? "text-amber-300" : "text-brand-400"}`}>
            {resultRecovery.state === "recovering"
              ? "Recuperando resultados guardados"
              : "No se pudo abrir el resultado guardado"}
          </p>
          <p className="text-xs font-mono text-white/45 max-w-xl leading-relaxed">
            {resultRecovery.message ?? "Estamos consultando la evidencia persistida de la última corrida."}
          </p>
          {resultRecovery.state === "blocked" && onRetryResultRecovery && (
            <button
              type="button"
              onClick={onRetryResultRecovery}
              className="mt-2 min-h-11 whitespace-nowrap rounded-xl border border-amber-500/35 bg-amber-500/10 px-5 py-2 font-mono text-xs font-bold uppercase tracking-wider text-amber-200 transition-colors hover:bg-amber-500/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
            >
              {resultRecovery.requiresLogin ? "Iniciar sesión" : "Reintentar recuperación"}
            </button>
          )}
        </div>
      )}

      {/* ─── FIX v1.7.5: SUCCESS sin resultado (pérdida silenciosa) ─── */}
      {showResults && silentResultLoss && !showProcessing && !failed && (
        <div className="w-full max-w-[1600px] rounded-2xl border border-amber-500/25 bg-amber-950/20 p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300">
          <AlertTriangle size={40} className="text-amber-400/70" />
          <p className="text-sm font-black uppercase tracking-widest text-amber-300 font-mono">
            La evaluación terminó sin resultados
          </p>
          <p className="text-xs font-mono text-white/40 max-w-lg leading-relaxed">
            El pipeline reportó éxito pero el resultado no llegó a la interfaz. Esto suele ser un
            problema de serialización del resultado en el backend (no un problema del acoplamiento).
            Reintentá la evaluación o revisá los logs del backend.
          </p>
          <button
            onClick={() => handleReset?.()}
            className="mt-2 min-h-11 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2 font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400 cursor-pointer"
          >
            Reiniciar
          </button>
        </div>
      )}

      {/* ───── SIN RESULTADOS TODAVÍA: estado honesto, sin mock ───── */}
      {showResults && !showProcessing && !failed && realResult === null && !silentResultLoss && !resultRecovery && (
        <div className="w-full max-w-[1600px] rounded-2xl border border-white/5 bg-white/[0.02] p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300">
          <Activity size={32} className="text-white/15" />
          <p className="text-sm font-black uppercase tracking-widest text-white/30 font-mono">
            Sin resultados todavía
          </p>
          <p className="text-xs font-mono text-white/25 max-w-md leading-relaxed">
            Elige un receptor y una molécula, y ejecuta la evaluación para ver el reporte completo del acoplamiento molecular.
          </p>
        </div>
      )}

      {/* ───── RESULTADOS: HERO → DOT → COLUMNS → VERIFY ───── */}
      {showResults && !showProcessing && !failed && realResult !== null && (
        <div className="w-full max-w-[1600px] space-y-6 animate-in fade-in duration-300">

          {/* ─── RESUMEN DE EVIDENCIA ─── */}
          <div ref={heroRef}>
            <EvaluationEvidencePanel
              result={realResult}
              target={selectedTargetObj}
              onOpenPhysicalControls={() => setPhysicalFocusRequest((value) => value + 1)}
            />

            {/* ── Evidencia estructural (P0-C) ──────────────────────────
                Generación, selección y controles físicos de las poses, con
                los contratos que el backend persiste. Va DEBAJO del resumen
                de evidencia y DENTRO de la misma pestaña: la instrucción del
                sprint es no añadir pestañas principales, y esta lectura
                pertenece al mismo resultado que se está mirando. */}
            <div className="flex flex-col gap-4 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="min-w-0 break-words font-mono text-xs text-white/30">
                {displayResult.target_name ?? "—"} ({selectedTargetObj?.pdb_id ?? "—"}) · corrida {realResult.molecule_id?.slice(0, 8) ?? "sin ID"} · señales heredadas disponibles solo como traza técnica
              </p>
              <div className="flex flex-wrap gap-3">
              <button onClick={() => setShowResults(false)} className="min-h-11 whitespace-nowrap rounded-lg border border-white/10 bg-white/5 px-5 font-mono text-xs font-bold uppercase tracking-wider text-white/40 transition-colors hover:text-white/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400">
                Ocultar
              </button>
              </div>
            </div>
          </div>

            {/* ─── DOT: Pipeline Timeline (family-gated, dinámico) ─── */}
            {(() => {
              // FIX UI-8 (2026-08-04): familia desconocida/no curada debe caer
              // al pipeline "default" (stacking neutro explícito, marcado como
              // no curado), NO a gpcr. Antes `?? PIPELINES_BY_FAMILY.gpcr`
              // hacía que un target auto-ingestado sin structural_family
              // mostrara "M4 GPCR · Vina + XGB + CL-GNN" con pesos que no
              // aplican → resultados engañosos. Ver docs/36 UI-8.
              const famKey =
                displayResult.target_family && displayResult.target_family in PIPELINES_BY_FAMILY
                  ? displayResult.target_family
                  : "default";
              const pipeline =
                PIPELINES_BY_FAMILY[famKey] ?? PIPELINES_BY_FAMILY.default;
              const famLabel = FAMILY_LABELS[famKey] ?? famKey;

              // Overrides con datos REALES del backend (WS2 serializa los 8 ML
              // fields). Cuando un campo es null (registros legacy) → fallback
              // a las constantes de PIPELINES_BY_FAMILY (story family-gated).
              const realDot: Record<string, { value?: string; weight?: number; sub?: string }> = {};
              const pesosEfectivos = realResult?.stacking_effective_weights;
              if (realResult) {
                const vinaAff = realResult.docking_poses?.[0]?.affinity;
                if (vinaAff != null) realDot.vina = { value: `${vinaAff.toFixed(1)} kcal/mol` };
                if (realResult.xgb_score != null) realDot.xgb = { value: `salida ${realResult.xgb_score.toFixed(2)}` };
                if (realResult.clgnn_score != null) realDot.clgnn = { value: realResult.clgnn_score.toFixed(2) };
                if (realResult.quantum_score != null) realDot.quantum = { value: realResult.quantum_score.toFixed(2) };
                // La señal AUTORIZADA de los tres perfiles M5-Zn es
                // `ums_warhead` (SMARTS puro). `ums_score` es el UMS histórico
                // —warheads + donantes + MolChamb— y sólo se muestra cuando la
                // corrida es anterior a SCHEMA 18, diciendo que es el histórico.
                if (realResult.ums_warhead != null) {
                  realDot.ums = { value: realResult.ums_warhead.toFixed(2), sub: "SMARTS · informativa" };
                } else if (realResult.ums_score != null) {
                  realDot.ums = { value: realResult.ums_score.toFixed(2), sub: "UMS histórico" };
                }
                if (realResult.mmgbsa_score != null) realDot.mmgbsa = { value: `${realResult.mmgbsa_score.toFixed(1)} kcal/mol` };
                // MM-GBSA on-demand (modal): el endpoint NO persiste al ORM,
                // así que el valor vive en estado local → override acá.
                if (mmgbsaResult?.delta_g_total_kcal != null) {
                  realDot.mmgbsa = {
                    value: `${mmgbsaResult.delta_g_total_kcal.toFixed(1)} kcal/mol`,
                    sub: mmgbsaResult.platform ?? "OpenMM",
                  };
                }
                if (realResult.stacking_vina_weight != null) realDot.vina = { ...realDot.vina, weight: pesosEfectivos?.vina ?? realResult.stacking_vina_weight };
                if (realResult.stacking_xgb_weight != null) realDot.xgb = { ...realDot.xgb, weight: pesosEfectivos?.xgb ?? realResult.stacking_xgb_weight };
                // El peso de CL-GNN es `stacking_clgnn_weight`. Aqui se leia
                // `stacking_gnn_weight`, que es el de la GNN LEGACY (RTMScore):
                // para GPCR el artefacto da gnn 0.40 y clgnn 0.00, asi que el
                // DOT pintaba «CL-GNN 0.40» sobre un modelo con peso cero.
                //
                // `null` en corridas anteriores a SCHEMA 17 significa «no se
                // registro por separado», no «cero»: en ese caso NO se pinta
                // peso y el DOT cae a la constante de la familia.
                if (realResult.stacking_clgnn_weight != null) realDot.clgnn = { ...realDot.clgnn, weight: pesosEfectivos?.clgnn ?? realResult.stacking_clgnn_weight };
                if (realResult.stacking_gnn_weight != null) realDot.gnn = { ...realDot.gnn, weight: pesosEfectivos?.gnn ?? realResult.stacking_gnn_weight };
              }

              // FIX (2026-08-04): el DOT NO debe mostrar el valor hardcodeado de
              // MM-GBSA de pipelineDefinitions.ts ("-7.1 kcal/mol") como si fuera
              // el resultado real de esta molécula. Si no hay mmgbsa_score
              // (pipeline) ni resultado del modal on-demand, mostrar "no
              // calculado" — honesto, no un valor inventado.
              if (realResult && !realDot.mmgbsa) {
                realDot.mmgbsa = {
                  value: "no calculado",
                  sub: "click para calcular",
                };
              }

              // DOC 71, defectos A3 y A7: la regla vive en
              // `lib/procedenciaDeSenales.ts`, con su prueba. Ver allí por qué
              // «sin salida serializada» sólo puede decirse cuando no hay valor.
              const effectiveStages = pipeline.stages.map((s) => ({
                ...s,
                ...describirEtapa(s, realDot[s.id]),
              }));
              const activeStages = effectiveStages.filter((s) => {
                // quantum solo se muestra si el backend lo calculó (no en legacy)
                if (realResult && s.id === "quantum" && realResult.quantum_score == null) return false;
                // ums solo se muestra si el backend lo calculó (metaloenzimas; evita
                // mostrar 0.5 neutral de targets no-metal / registros legacy)
                if (realResult && s.id === "ums" && !tieneSalidaUms(realResult)) return false;
                return s.weight > 0 || s.post_hoc;
              });
              // Etapas que la familia pesa por diseño y que esta corrida no
              // produjo. Ver `lib/procedenciaDeSenales.ts`.
              const ausentes = realResult ? etapasAusentes(effectiveStages) : [];
              return (
                <>
                {/* El protocolo M5-Zn, con el estado que la corrida PERSISTIÓ.
                    No se recalcula ni se «mejora»: si llega un REVIEW_*, se
                    pinta ese valor aunque haya un score al lado. Sólo un
                    estado VALIDATED presenta el número como conclusión.
                    Ver services/pipeline/protocols/interpretabilidad.py. */}
                {realResult?.m5_scientific_status && (
                  <div className="mb-5 border-b border-white/5 pb-5">
                    <ProtocoloM5Zn resultado={realResult} />
                  </div>
                )}

                <section ref={dotRef} className="border-b border-white/5 pb-5">
                  <div className="flex items-baseline justify-between mb-4">
                    <p className="text-sm font-bold uppercase tracking-[0.15em] text-white/30 font-sans">
                      Procedencia de las señales ·{" "}
                      <span className="text-purple-300/80">
                        {pipeline.label}
                      </span>
                    </p>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-white/20 border border-white/10 rounded px-2 py-0.5">
                      familia: {famLabel}
                    </span>
                  </div>

                  {/* El título de arriba describe el DISEÑO de la familia y se
                      pinta siempre. Si alguna de las señales que ese diseño
                      pondera no llegó a opinar, la corrida NO es la que el
                      título anuncia, y eso se dice aquí en vez de dejar que el
                      lector lo deduzca cruzando el encabezado con las
                      tarjetas. */}
                  {ausentes.length > 0 && (
                    <div
                      role="status"
                      className="mb-4 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] px-3 py-2.5"
                    >
                      <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-amber-300">
                        Pipeline degradado en esta corrida
                      </p>
                      <p className="mt-1.5 max-w-[78ch] text-[11px] leading-relaxed text-amber-100/80">
                        {ausentes.map((etapa) => etapa.label).join(", ")}{" "}
                        {ausentes.length === 1 ? "no produjo salida" : "no produjeron salida"} en
                        este equipo, aunque «{pipeline.label}» {ausentes.length === 1 ? "le" : "les"}{" "}
                        asigna peso por diseño
                        {" "}({ausentes.map((etapa) => `${etapa.label} w=${etapa.pesoDeDiseno.toFixed(2)}`).join(" · ")}).
                        El resultado lo sostienen las señales que sí opinaron, con los pesos
                        renormalizados que aparecen en cada tarjeta. La descripción de la familia
                        y su nota de abajo siguen describiendo el diseño, no lo que pasó aquí.
                      </p>
                    </div>
                  )}
                  <div className="flex items-center gap-0 overflow-x-auto">
                    {activeStages.map((node, i, arr) => {
                      const dimmed =
                        node.weight === 0 && !node.post_hoc && !node.degraded;
                      const isMmgbsa = node.id === "mmgbsa";
                      // Sin modal si ya hay resultado (pipeline o modal).
                      const mmgbsaDone = isMmgbsa && mmgbsaAlreadyDone;
                      const mmgbsaRunning = isMmgbsa && mmgbsaState === "running";
                      // Clickable cuando NO hay resultado: idle o error (retry).
                      const mmgbsaClickable = isMmgbsa && !mmgbsaAlreadyDone && mmgbsaState !== "running";

                      const dotNodeContent = (
                        <>
                          <div
                            className={`w-2.5 h-2.5 rounded-full ${mmgbsaRunning ? "animate-pulse" : ""}`}
                            style={{
                              backgroundColor: node.color,
                              opacity: dimmed ? 0.25 : 1,
                            }}
                          />
                          <span
                            ref={mmgbsaClickable ? mmgbsaLabelRef : undefined}
                            className="text-xs font-bold uppercase tracking-wider font-sans whitespace-nowrap"
                            style={{
                              color: mmgbsaClickable ? "#c4b5fd" : mmgbsaRunning ? "#6ee7b7" : mmgbsaDone ? "#34d399" : dimmed ? "#ffffff20" : "#ffffffb3",
                            }}
                          >
                            {mmgbsaRunning ? "calculando…" : node.label}
                          </span>
                          <span
                            className="text-sm font-bold font-mono"
                            style={{
                              color: mmgbsaRunning ? "#34d399" : mmgbsaDone ? "#34d399" : dimmed ? "#ffffff20" : "#ffffffe6",
                              opacity: mmgbsaRunning ? 0.7 : 1,
                            }}
                          >
                            {mmgbsaRunning ? "···" : node.value}
                          </span>
                          <span className="text-[11px] font-mono text-white/25 whitespace-nowrap">
                            {node.sub}
                          </span>
                          {mmgbsaDone && (
                            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400/90 border border-emerald-500/20 rounded px-1 py-0.5">
                              ✓ calculado
                            </span>
                          )}
                          {node.post_hoc && (
                            <span className="text-[10px] font-mono uppercase tracking-wider text-white/20 border border-white/10 rounded px-1 py-0.5">
                              post-hoc
                            </span>
                          )}
                          {!node.post_hoc && node.weight > 0 && node.reportedWeight != null && (
                            <span className="text-[10px] font-mono text-purple-400/70">
                              w={node.reportedWeight.toFixed(2)}
                            </span>
                          )}
                          {!node.post_hoc && node.weight > 0 && node.reportedWeight == null && (
                            <span className="text-[10px] font-mono uppercase tracking-wider text-white/20">
                              peso no reportado
                            </span>
                          )}
                          {node.weight === 0 &&
                            !node.post_hoc &&
                            !node.degraded && (
                              <span className="text-[10px] font-mono uppercase tracking-wider text-white/15 border border-white/5 rounded px-1 py-0.5">
                                off
                              </span>
                            )}
                          {node.note && (
                            <span className="text-[10px] font-mono text-white/15 max-w-[120px] text-center leading-tight mt-0.5">
                              {node.note}
                            </span>
                          )}
                        </>
                      );

                      return (
                        <React.Fragment key={node.id}>
                          {isMmgbsa && !mmgbsaDone ? (
                            <button
                              onClick={() => { if (!mmgbsaRunning) setShowMmgbsaModal(true); }}
                              disabled={mmgbsaRunning}
                              className="dot-node flex min-h-11 shrink-0 flex-col items-center gap-1.5 rounded-lg px-3 transition-[background-color,border-color,box-shadow,opacity,transform] duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
                              style={{
                                boxShadow: mmgbsaClickable
                                  ? "0 0 16px rgba(139,92,246,0.10), inset 0 0 8px rgba(139,92,246,0.04)"
                                  : mmgbsaRunning
                                  ? "0 0 10px rgba(16,185,129,0.08)"
                                  : "none",
                                border: mmgbsaClickable
                                  ? "1px solid rgba(139,92,246,0.15)"
                                  : mmgbsaRunning
                                  ? "1px solid rgba(16,185,129,0.12)"
                                  : "1px solid transparent",
                                backgroundColor: mmgbsaClickable
                                  ? "rgba(139,92,246,0.03)"
                                  : "transparent",
                                cursor: mmgbsaRunning ? "wait" : "pointer",
                              }}
                              onMouseEnter={(e) => {
                                if (mmgbsaClickable) {
                                  e.currentTarget.style.boxShadow = "0 0 24px rgba(139,92,246,0.18), inset 0 0 12px rgba(139,92,246,0.06)";
                                  e.currentTarget.style.borderColor = "rgba(139,92,246,0.3)";
                                }
                              }}
                              onMouseLeave={(e) => {
                                if (mmgbsaClickable) {
                                  e.currentTarget.style.boxShadow = "0 0 16px rgba(139,92,246,0.10), inset 0 0 8px rgba(139,92,246,0.04)";
                                  e.currentTarget.style.borderColor = "rgba(139,92,246,0.15)";
                                }
                              }}
                            >
                              {dotNodeContent}
                            </button>
                          ) : (
                            <div
                              className="dot-node flex flex-col items-center gap-1.5 px-3 shrink-0 rounded-lg"
                              style={mmgbsaDone ? { border: "1px solid rgba(16,185,129,0.12)", backgroundColor: "rgba(16,185,129,0.03)" } : undefined}
                            >
                              {dotNodeContent}
                            </div>
                          )}
                          {i < arr.length - 1 && (
                            <div
                              className="flex-1 h-px min-w-[20px]"
                              style={{
                                background:
                                  node.post_hoc || dimmed
                                    ? "#ffffff0a"
                                    : "#ffffff1a",
                              }}
                            />
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                  {/* «Diseño de la familia:» no es un adorno. Sin ese prefijo,
                      una frase como «CL-GNN domina» se lee como la crónica de
                      esta corrida, y en 2BQV CL-GNN no llegó a correr. */}
                  <p className="text-[11px] font-mono text-white/20 mt-3 italic">
                    Diseño de la familia: {pipeline.note}
                  </p>
                  <p className="text-[10px] font-mono text-white/15 mt-1 text-right">
                    Pesos serializados por el pipeline · no representan confianza calibrada
                  </p>
                </section>
                </>
              );
            })()}

          {/* ─── ANÁLISIS: evidencia estructural · propiedades · post-docking ─── */}
          <section className="mt-6">
            <ProAnalysisTabs 
              status={status?.result ? status : null}
              selectivityResult={
                realResult?.selectivity_ran === true
                  ? {
                      off_targets: realResult?.anti_target_results ?? [],
                      selectivity_ratio: realResult?.selectivity_ratio,
                      selectivity_verdict: realResult?.selectivity_verdict,
                    }
                  : null
              }
              moleculeId={realResult?.molecule_id ?? null}
              structuralEvidenceResult={realResult}
              physicalFocusRequest={physicalFocusRequest}
              onComparePoses={(leftRank, rightRank) => setPoseComparison({ leftRank, rightRank })}
              enableSelectivity={advancedOpts.enableSelectivity}
              onRequestMmgbsa={() => {
                if (mmgbsaState !== "running" && !mmgbsaAlreadyDone) setShowMmgbsaModal(true);
              }}
              mmgbsaRunning={mmgbsaState === "running"}
              mmgbsaDone={mmgbsaAlreadyDone}
              onRequestAdmet={handleRunAdmet}
              admetRunning={admetState === "running"}
              admetDone={admetYaEsta}
              admetError={admetError}
            />
          </section>

          {/* ─── VERIFY: Acciones ─── */}
          <section ref={verifyRef} className="flex flex-wrap items-center gap-4 pt-5 border-t border-white/5">
            {blockchainTxId && (
              <ExternalLink
                href={`https://explorer.solana.com/tx/${blockchainTxId}?cluster=devnet`}
                className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.02] px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white/50 transition-colors hover:border-purple-500/30 hover:text-purple-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
              >
                <IconoEnlaceExterno size={14} />
                Ver en Solana Explorer
              </ExternalLink>
            )}
            <button
              onClick={() => handleDownloadCertificate?.()}
              disabled={!realResult}
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.02] px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white/50 transition-colors hover:border-white/20 hover:text-white/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <FileText size={14} />
              Descargar certificado blockchain
            </button>
            <button
              onClick={() => setShowPdfPreview(true)}
              disabled={!realResult}
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.02] px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white/50 transition-colors hover:border-white/20 hover:text-white/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <Eye size={14} />
              Vista previa del certificado
            </button>
            <button
              onClick={() => handleDownloadComplex?.()}
              disabled={!realResult}
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.02] px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white/50 transition-colors hover:border-white/20 hover:text-white/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <Download size={14} />
              Complejo .PDB
            </button>
            <button
              onClick={() => handleSave?.()}
              disabled={!realResult}
              className={`flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-30 ${
                isSaved
                  ? "border-white/20 bg-white/5 text-white/70"
                  : "border-white/10 bg-white/[0.02] text-white/50 hover:border-white/20 hover:text-white/80"
              }`}
            >
              {isSaved ? "✓ Guardado en MolDex" : "Guardar en MolDex"}
            </button>
            <button
              onClick={() => setShowCertificationModal(true)}
              disabled={!realResult || Boolean(realResult?.blockchain_tx_id)}
              className={`flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed ${
                realResult?.blockchain_tx_id
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-purple-500/40 bg-purple-500/15 text-purple-200 hover:border-purple-400 hover:bg-purple-500/25"
              }`}
              title="Registra en Solana el compuesto, target, señal de score y fecha; no certifica validez científica ni sustituye el dossier."
            >
              <ShieldCheck size={14} />
              {realResult?.blockchain_tx_id ? "Integridad registrada" : "Registrar integridad en Solana"}
            </button>
          </section>

        </div>
      )}

      {/* Target Selector Modal */}
      {showTargetModal && !structuralSystemLocked && (
        <TargetSelectorModal
          isOpen={showTargetModal}
          onClose={() => setShowTargetModal(false)}
          targets={targets}
          onSelect={(tId: string) => {
            setTarget(tId);
            setShowTargetModal(false);
          }}
          selectedTargetId={target}
          onTargetUploadSuccess={onTargetUploadSuccess}
        />
      )}

      {/* ── Modal PDF (Vista Previa del reporte sin salir de la página) ── */}
      {showPdfPreview && realResult?.molecule_id && (
        <div
          className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setShowPdfPreview(false)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="evaluation-pdf-title"
            className="bg-surface-950 border border-slate-800 rounded-2xl w-full max-w-5xl h-[85vh] shadow-2xl relative flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-800 bg-surface-950 rounded-t-2xl shrink-0">
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-purple-400" />
                <h3 id="evaluation-pdf-title" className="text-sm font-black text-white uppercase tracking-widest">Reporte Científico — Vista Previa</h3>
              </div>
              <button
                onClick={() => setShowPdfPreview(false)}
                aria-label="Cerrar vista previa del reporte"
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                title="Cerrar"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden p-4">
              <PDFReportViewer
                moleculeId={realResult.molecule_id}
                isCertified={!!realResult.blockchain_tx_id}
                onCertify={({ signature }) => {
                  void handleCertify?.(signature);
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── ProOptions Modal (Motor · Grid Box · Avanzadas) ── */}
      {showCertificationModal && realResult?.molecule_id && (
        <CertificationModal
          moleculeId={realResult.molecule_id}
          onClose={() => setShowCertificationModal(false)}
          onSuccess={({ signature }) => {
            void handleCertify?.(signature);
          }}
        />
      )}

      <ProOptionsModal
        onClose={() => setShowOptionsModal(false)}
        onApply={(engineRaw, gridRaw, adv, hotspotsRaw) => {
          // Con el sistema sellado, la caja y los residuos vuelven al ancla
          // pase lo que pase. El modal ya los deshabilita; esto es la segunda
          // frontera, porque un control deshabilitado protege la pantalla y no
          // la hipótesis. El protocolo —motor, exhaustiveness, poses— sí pasa:
          // es esfuerzo de muestreo y cada corrida sella el suyo.
          const engine = engineRaw;
          const grid = structuralSystemLocked && structuralSystem
            ? {
                ...gridRaw,
                centerX: structuralSystem.grid.center[0],
                centerY: structuralSystem.grid.center[1],
                centerZ: structuralSystem.grid.center[2],
                sizeX: structuralSystem.grid.size[0],
                sizeY: structuralSystem.grid.size[1],
                sizeZ: structuralSystem.grid.size[2],
              }
            : gridRaw;
          const hotspots = structuralSystemLocked && structuralSystem
            ? [...structuralSystem.customHotspots]
            : hotspotsRaw;
          setDockingEngine(engine);
          setGridBox(grid);
          setAdvancedOpts(adv);
          setCustomHotspots(hotspots && hotspots.length > 0 ? hotspots : null);
          // Caja, residuos, motor y profundidad forman una sola hipótesis de
          // ejecución. Persistir sólo la caja dejaba cambiar el motor después
          // del preflight sin invalidarlo.
          onRunConfigurationChange?.({
            center: [grid.centerX, grid.centerY, grid.centerZ],
            size: [grid.sizeX, grid.sizeY, grid.sizeZ],
            customHotspots: hotspots && hotspots.length > 0 ? [...hotspots] : [],
            dockingEngine: engine.engine,
            exhaustiveness: grid.exhaustiveness,
            numPoses: grid.numModes,
            pipelineConfig: {
              enabled_stages: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
              stage_params: {
                docking: { exhaustiveness: grid.exhaustiveness, num_poses: grid.numModes },
                properties: { run_admet_ai: adv.enableADMET },
                // `conformers` y `ph` viajan juntos: los dos son del mismo
                // paso. Mandar uno y olvidar el otro dejaba el control de pH
                // de adorno según por dónde se lanzara la corrida.
                conformer: {
                  conformers: initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.conformers ?? 1,
                  ph: adv.protonationPh,
                },
              },
              docking_engine: engine.engine,
              pro_workers: adv.numWorkers,
              pro_parallel_docks: adv.parallelDocks,
              pro_selectivity: adv.enableSelectivity,
              pro_anti_targets: [...adv.selectedAntiTargets],
              pro_mmgbsa: adv.enableMMGBSA,
              pro_mmgbsa_steps: adv.mmgbsaSteps,
              gnn_precision: engine.gnnPrecision,
              peptide_docking_engine: engine.peptideEngine ?? undefined,
            },
          });
        }}
        isOpen={showOptionsModal}
        systemSealed={structuralSystemLocked}
        initialEngine={dockingEngine}
        initialGridBox={gridBox}
        initialAdvanced={advancedOpts}
        initialHotspots={customHotspots ?? undefined}
        targetHotspots={targetHotspotsList}
      />

      {poseComparison && realResult?.molecule_id && (
        <PoseComparisonDialog
          moleculeId={realResult.molecule_id}
          leftRank={poseComparison.leftRank}
          rightRank={poseComparison.rightRank}
          onClose={() => setPoseComparison(null)}
        />
      )}

      {/* ── MM-GBSA post-docking (cálculo real) ── */}
      {showMmgbsaModal && (
        <div
          className="fixed inset-0 z-[130] flex items-start justify-center bg-black/80 backdrop-blur-xl"
          style={{ paddingTop: "calc(57px + 12px)", paddingBottom: "12px", paddingLeft: "16px", paddingRight: "16px" }}
          onClick={() => { if (mmgbsaState !== "running") setShowMmgbsaModal(false); }}
          role="presentation"
        >
          <div
            className="bg-zinc-950/95 border border-emerald-500/20 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col overflow-hidden"
            style={{ maxHeight: "calc(100vh - 57px - 24px)" }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="mmgbsa-dialog-title"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
                  <FlaskConical size={18} className="text-emerald-400" />
                </div>
                <div>
                  <h3 id="mmgbsa-dialog-title" className="text-sm font-black text-white uppercase tracking-widest">MM-GBSA — estimación de ΔG de unión</h3>
                  <p className="text-[10px] text-white/30 font-mono mt-0.5">Molecular Mechanics / Generalized Born Surface Area</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => { if (mmgbsaState !== "running") setShowMmgbsaModal(false); }}
                disabled={mmgbsaState === "running"}
                aria-label="Cerrar cálculo MM-GBSA"
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-white/5 text-white/40 hover:text-white hover:bg-white/10 transition-colors text-sm disabled:opacity-40"
              >✕</button>
            </div>

            {/* Explanation */}
            <div className="px-6 py-3 bg-emerald-500/5 border-b border-emerald-500/10 shrink-0">
              <p className="text-[11px] text-emerald-300/80 font-mono leading-relaxed">
                <span className="font-bold text-emerald-300">¿Qué calcula?</span> MM-GBSA post-hoc minimiza la pose con OpenMM y combina términos de mecánica molecular, Generalized Born y superficie accesible al solvente para estimar un ΔG dependiente del protocolo. El signo y la magnitud sólo deben compararse dentro de la misma configuración; no sustituyen una afinidad experimental.
              </p>
            </div>

            {/* Config */}
            <div className="px-6 py-4 border-b border-white/5 shrink-0">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-black uppercase tracking-widest text-white/30 mb-2">Pose a refinar</label>
                  <select
                    value={mmgbsaPoseRank}
                    onChange={(e) => setMmgbsaPoseRank(Number(e.target.value))}
                    disabled={mmgbsaState === "running"}
                    className="w-full h-9 px-3 font-mono text-xs font-bold rounded-lg outline-none cursor-pointer disabled:opacity-40 bg-black border border-white/10 text-white"
                  >
                    {availablePoseRanks.map(r => (
                      <option key={r} value={r}>Pose #{r} {r === 1 ? "(Mejor)" : ""}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-black uppercase tracking-widest text-white/30 mb-2">Pasos de minimización</label>
                  <select
                    value={mmgbsaNumSteps}
                    onChange={(e) => setMmgbsaNumSteps(Number(e.target.value))}
                    disabled={mmgbsaState === "running"}
                    className="w-full h-9 px-3 font-mono text-xs font-bold rounded-lg outline-none cursor-pointer disabled:opacity-40 bg-black border border-white/10 text-white"
                  >
                    <option value={500}>500 pasos (Rápido)</option>
                    <option value={1000}>1,000 pasos (Estándar)</option>
                    <option value={2500}>2,500 pasos (Preciso)</option>
                    <option value={5000}>5,000 pasos (Máximo)</option>
                  </select>
                </div>
              </div>
              <button
                onClick={handleRunMmgbsa}
                disabled={mmgbsaState === "running"}
                className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 whitespace-nowrap rounded-lg font-mono text-xs font-black uppercase tracking-widest transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                style={{
                  backgroundColor: mmgbsaState === "running" ? "rgba(16,185,129,0.15)" : "rgba(16,185,129,0.9)",
                  color: mmgbsaState === "running" ? "#6ee7b7" : "#fff",
                  border: "1px solid rgba(16,185,129,0.3)",
                }}
              >
                {mmgbsaState === "running" ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-300 border-t-transparent inline-block" />
                    Calculando con OpenMM... ({mmgbsaNumSteps.toLocaleString()} pasos)
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    Ejecutar cálculo MM-GBSA
                  </>
                )}
              </button>
            </div>

            {/* Content: idle → processing → results */}
            <div className="flex-1 overflow-y-auto">
              {mmgbsaState === "idle" && (
                <div className="flex flex-col items-center justify-center py-16 gap-3 text-white/40">
                  <FlaskConical size={48} className="text-emerald-500/20" />
                  <p className="text-sm font-bold text-white/50">Configura los parámetros y ejecuta el cálculo</p>
                  <p className="text-xs text-white/30 text-center max-w-xs">El tiempo depende del número de pasos y la disponibilidad de GPU.</p>
                </div>
              )}

              {mmgbsaState === "running" && (
                <div className="flex flex-col items-center justify-center py-16 gap-4">
                  <div className="relative">
                    <div className="h-16 w-16 animate-spin rounded-full border-2 border-emerald-500/20 border-t-emerald-500" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-300/30 border-t-emerald-300" style={{ animationDirection: "reverse" } as React.CSSProperties} />
                    </div>
                  </div>
                  <div className="text-center space-y-1">
                    <p className="text-sm font-black text-emerald-400 uppercase tracking-widest animate-pulse">Minimización en curso...</p>
                    <p className="text-xs text-white/40 font-mono">{mmgbsaNumSteps.toLocaleString()} pasos · OpenMM</p>
                    <p className="text-[10px] text-white/30">Este proceso puede tomar entre 30 segundos y varios minutos según el hardware.</p>
                  </div>
                </div>
              )}

              {mmgbsaState === "error" && (
                <div className="flex flex-col items-center justify-center py-12 gap-3 px-6">
                  <AlertTriangle size={40} className="text-rose-400/70" />
                  <p className="text-sm font-black text-rose-300 uppercase tracking-widest font-mono">El cálculo falló</p>
                  <p className="text-xs font-mono text-white/40 text-center max-w-md leading-relaxed">
                    {mmgbsaError ?? "Error desconocido al ejecutar MM-GBSA."}
                  </p>
                  <p className="text-[10px] font-mono text-white/25">Podés reintentar con el botón de abajo.</p>
                </div>
              )}

              {mmgbsaState === "done" && (() => {
                if (!mmgbsaResult) return null;
                const r = mmgbsaResult;
                const totalKcal = r.delta_g_total_kcal;

                const components = [
                  { label: "Van der Waals", key: "vdw", value: r.delta_g_vdw, color: "#6366f1", desc: "Interacciones hidrofóbicas y de contacto estérico" },
                  { label: "Electrostática", key: "elec", value: r.delta_g_electrostatic, color: "#f59e0b", desc: "Cargas iónicas y puentes de hidrógeno cargados" },
                  { label: "Solvatación GB (polar)", key: "gb", value: r.delta_g_gb_polar, color: "#3b82f6", desc: "Costo de desolvatación polar (Generalized Born)" },
                  { label: "Solvatación SASA (no polar)", key: "sasa", value: r.delta_g_nonpolar_sasa, color: "#14b8a6", desc: "Efecto hidrofóbico (Solvent Accessible Surface Area)" },
                ];
                // FIX MM-GBSA (2026-08-04): el endpoint /pro/mmgbsa ahora devuelve
                // ΔG real (g_complex - g_protein - g_ligand) pero SIN descomposición
                // por contribución (None) — no está disponible. Filtrar nulls para
                // no crashear en toFixed() y mostrar solo lo que venga.
                const numericComponents = components.filter(c => typeof c.value === "number" && !Number.isNaN(c.value));
                const hasDecomposition = numericComponents.length > 0;
                const maxAbs = Math.max(...numericComponents.map(c => Math.abs(c.value as number)), 0.1);

                return (
                  <div className="p-6 space-y-6">
                    {/* ΔG Total Hero */}
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.05] p-5 text-center">
                      <p className="mb-1 text-[10px] font-black uppercase tracking-widest text-emerald-300">Estimación MM-GBSA (ΔG)</p>
                      <p className="font-mono text-4xl font-black text-emerald-300">
                        {totalKcal.toFixed(2)} <span className="text-xl font-bold">kcal/mol</span>
                      </p>
                      <p className="mx-auto mt-3 max-w-md text-[10px] leading-4 text-white/35">
                        Señal post-hoc dependiente del protocolo; no clasifica por sí sola al ligando como candidato.
                      </p>
                      <p className="text-[10px] text-white/30 mt-2 font-mono">
                        Pose #{(r.pose_rank ?? mmgbsaPoseRank)} · Minimizado {r.minimized ? "✓" : "—"} · {r.platform ?? "OpenMM"} · {r.execution_time_s != null ? `${r.execution_time_s.toFixed(1)}s` : "—"}
                      </p>
                    </div>

                    {/* La condición de validez la manda el backend junto al
                        número (`services/chemistry/mmgbsa_contrato.py`) y va
                        aquí, debajo de la cifra grande, no al final del panel.
                        Un ΔG de MM-GBSA cuyo ligando está tipado con átomos de
                        proteína no significa lo que el lector supone que
                        significa, y esa frase es la mitad del dato. */}
                    {r.condicion_de_validez && (
                      <p className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3.5 text-[11px] leading-relaxed text-amber-100/80">
                        <strong className="font-semibold">Cómo se puede usar este número.</strong>{" "}
                        {r.condicion_de_validez}
                      </p>
                    )}

                    {/* Decomposition */}
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-3">Descomposición de Energía por Contribución</p>
                      {hasDecomposition ? (
                        <div className="space-y-3">
                          {numericComponents.map((comp) => {
                            const cvalue = comp.value as number;
                            const pct = Math.abs(cvalue) / maxAbs * 100;
                            const isFavorable = cvalue < 0;
                            return (
                              <div key={comp.key} className="rounded-xl p-3 border border-white/5 bg-white/[0.02]">
                                <div className="flex items-center justify-between mb-1.5">
                                  <div>
                                    <span className="text-xs font-bold text-white/80">{comp.label}</span>
                                    <span className="ml-2 text-[10px] text-white/30 font-mono">{comp.desc}</span>
                                  </div>
                                  <span className={`text-xs font-black font-mono ${isFavorable ? "text-emerald-400" : "text-red-400"}`}>
                                    {cvalue > 0 ? "+" : ""}{cvalue.toFixed(3)} kcal/mol
                                  </span>
                                </div>
                                <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                                  <div
                                    className="h-full rounded-full"
                                    style={{
                                      width: `${Math.min(pct, 100)}%`,
                                      backgroundColor: isFavorable ? comp.color : "#ef4444",
                                      opacity: 0.8,
                                    }}
                                  />
                                </div>
                                <p className="text-[10px] mt-1 font-mono" style={{ color: isFavorable ? "#6ee7b7" : "#fca5a5" }}>
                                  {isFavorable ? "▼ Contribución negativa en este modelo" : "▲ Contribución positiva en este modelo"}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="rounded-xl p-4 border border-white/5 bg-white/[0.02] text-[11px] text-slate-400/80 leading-relaxed">
                          La descomposición por contribución (vdW, electrostática, GB, SASA) no está
                          disponible en este endpoint. El valor reportado es la diferencia calculada entre complejo, receptor y ligando sobre la pose de docking minimizada; depende de la parametrización y no es una medición experimental.
                        </div>
                      )}
                    </div>

                    {/* ΔG Bind */}
                    <div className="flex items-center justify-between p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                      <span className="text-xs font-bold font-mono text-white/70">ΔG Bind (calculado)</span>
                      <span className="text-sm font-black font-mono text-emerald-400">{(r.delta_g_bind ?? r.delta_g_total_kcal).toFixed(2)} kcal/mol</span>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
