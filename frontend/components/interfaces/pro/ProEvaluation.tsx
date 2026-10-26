/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4
 * Hallmark · component: evaluation structural inputs · genre: modern-minimal · theme: existing MolDesign
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass · mobile: pass
 */
"use client";
import { AntiDianasAviso } from "./AntiDianasSelector";
import { antiDianasParaEnviar, antiDianasPorDefecto, useAntiDianas } from "@/lib/antiDianas";


import React, { useState, useEffect, useRef, useCallback, useMemo, useId } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { ChipsDelSitio } from "../../science/ChipsDelSitio";
import { DetalleDelSitio } from "../../science/DetalleDelSitio";
import { EstimacionDeCorrida } from "../../evaluation/EstimacionDeCorrida";
import { ConfigurationPresentation, ConfigurationSystem } from "../../evaluation/ConfigurationPresentation";
import configurationStyles from "../../evaluation/ConfigurationPresentation.module.css";
import { PipelineDeLaCorrida } from "../../science/PipelineDeLaCorrida";
import { animateElements, cancelAnimations } from "../../../lib/webAnimation";
import { seleccionAplicada, seleccionInicial, seleccionParaGuardar } from "../../../lib/seleccionDeResiduos";
import {
  Database, Play, Download, Activity,
  FileText, Eye, ExternalLink as IconoEnlaceExterno, Settings, FlaskConical, AlertTriangle, X,
  History, ChevronDown,
} from "lucide-react";
import { KetcherEditor } from "../../KetcherEditor";
import { OrbeDeEvaluacion } from "./OrbeDeEvaluacion";
import { useKeepAliveActive } from "../../../context/KeepAliveContext";
import dynamic from "next/dynamic";
const AdvancedMolstarViewer = dynamic(() => import("./AdvancedMolstarViewer"), { ssr: false });
import { AvisoSinWebGL } from "./AvisoSinWebGL";
import { comprobarWebGL } from "../../../lib/webgl";
const Web3DViewer = dynamic(() => import("./Web3DViewer"), { ssr: false });
import { InsigniaDelCatalogo } from "@/components/science/InsigniaDelCatalogo";
import TargetSelectorModal from "./TargetSelectorModal";
import ProOptionsModal from "./ProOptionsModal";
import { PDFReportViewer } from "../../PDFReportViewer";
import { CertificationModal } from "../../CertificationModal";
import type { DockingEngineConfig, GridBoxConfig, AdvancedConfig } from "./ProOptionsModal";
import { ProAnalysisTabs } from "./ProAnalysisTabs";
import { EvaluationEvidencePanel } from "./EvaluationEvidencePanel";
import { EvaluationActionBar } from "./EvaluationActionBar";
import resultStyles from "./ResultReadingPresentation.module.css";
import { ResultReadingPresentation } from "./ResultReadingPresentation";
import { PoseComparisonDialog } from "./PoseComparisonDialog";
import { PipelineTimeline, stagesForPipeline } from "./PipelineTimeline";
import { getTargetPdb, getPoseFile, getProteinFile, getJobStatus, getInteractions } from "../../../lib/api";
import { leerSelloDelResultado } from "../../../lib/moldex";
import type { Target } from "../../../lib/api";
import { runAdmet, runMmgbsa } from "../../../lib/proApi";
import { subscribeToPipelineEvents, stageEventToOrbUpdate } from "../../../lib/pipelineStream";
import type { PipelineEvent } from "../../../lib/pipelineStream";
import { PIPELINES_BY_FAMILY, FAMILY_LABELS, localizePipelineText } from "../../../lib/pipelineDefinitions";
import { describirEtapa, etapasAusentes, pesosRegistrados, protocoloRegistrado, tieneSalidaUms } from "../../../lib/procedenciaDeSenales";
import type { JobStatus, MolecularSuggestion, ValidationResult, EvaluationResult, InteractionDatum } from "../../../lib/types";
import type { StageState } from "./PipelineTimeline";
import type { CasePipelineConfig, CaseRun, CaseStructuralSystem } from "../../../lib/cases/types";

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
  /**
   * La corrida la canceló quien la lanzó. El backend la cierra como `FAILURE`
   * con su motivo; la pantalla no debe decir «falló» por eso.
   */
  cancelled?: boolean;
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
  /**
   * K VIGENTE del caso (confórmeros por molécula), no el congelado en el
   * sistema estructural de la primera corrida.
   *
   * CAS-05: el `onApply` del modal Opciones reconstruía este valor desde
   * `initialRunConfiguration` —que prioriza el sistema sellado de la primera
   * corrida (K=1)—, así que aplicar Opciones sin cambios tras pasar a
   * ensemble pisaba el K=30 del caso y el siguiente submit recibía un 409
   * por una configuración que nadie cambió. El modal edita un borrador de
   * este K; al aplicar se persiste como parte del protocolo del caso.
   *
   * CAS-04: la estimación de duración también lo lee: describir el protocolo
   * que firmará el preflight, no el de la primera corrida.
   */
  activeConformers: number;
  /** Libro de corridas del caso. Alimenta la cohorte histórica del SAR (CAS-02). */
  caseRuns?: readonly CaseRun[];
  /**
   * SOL-10: el caso AÚN no tiene ligando guardado y lo que se ve en el
   * editor es la molécula de muestra, no la hipótesis del usuario.
   *
   * Un caso nuevo inicializa el editor con aspirina SIN escribirla en los
   * inputs — deliberado: persistir la muestra sería atribuirle una decisión
   * que no tomó. La muestra entra al caso en el momento en que alguien pulsa
   * «Ejecutar evaluación» con ella a la vista (ahí sí decide), así que no hace
   * falta editarla antes; la seña le dice que se evaluará tal cual.
   */
  ejemploEnEditor: boolean;
  /** Persiste toda la configuración de docking que invalida la comprobación. */
  onRunConfigurationChange?: (config: {
    center: [number, number, number];
    size: [number, number, number];
    /** Ausente = sin decidir (catálogo); `[]` = «ninguno»; lista = sólo esos. */
    customHotspots?: string[];
    dockingEngine: string;
    exhaustiveness: number;
    numPoses: number;
    conformers: number;
    pipelineConfig: CasePipelineConfig;
  }) => void;
  /** Preparación pidió volver a evaluar con este tautómero: se aplica como desde Opciones, una vez por `nonce`. */
  tautomeroPedido?: { modo: "canonico" | "entrada"; nonce: number };
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
  cancelled = false,
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
  tautomeroPedido,
  activeConformers,
  caseRuns,
  ejemploEnEditor,
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
  // La interfaz se sirve en los dos idiomas que declara el paquete. Todo
  // texto visible pasa por `t()`; una cadena escrita a mano aqui se veria en
  // castellano con el idioma en English, que es motivo de rechazo en Store.
  const { t } = useLanguage();
  const [showPdfPreview, setShowPdfPreview] = useState(false);
  const [showCertificationModal, setShowCertificationModal] = useState(false);
  const [receptorPdb, setReceptorPdb] = useState<string | null>(null);
  const [loadingReceptor, setLoadingReceptor] = useState(false);
  const [showResults, setShowResults] = useState(true);
  const [selectivityWorking, setSelectivityWorking] = useState(false);
  const [physicalFocusRequest, setPhysicalFocusRequest] = useState(0);
  const [poseComparison, setPoseComparison] = useState<{ leftRank: number; rightRank: number } | null>(null);
  // El sistema PROVISIONAL se enseña pero todavía se puede corregir; el
  // SELLADO ya no. `structuralSystemLocked` congela sólo lo que define el
  // sistema —receptor, caja, residuos—; el protocolo se sigue pudiendo cambiar
  // y cada corrida guarda el suyo.
  //
  // CAS-04: la estimación de duración lee el K VIGENTE del caso
  // (`activeConformers`), no el congelado en el sistema de la primera
  // corrida. Con Ensemble K=30, la pantalla estimaba 7–14 s (K=1) mientras
  // la corrida real tardó ~209 s: un número que describe otro protocolo es
  // peor que ninguno. El mismo K que firmará el preflight es el que se
  // estima.
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
  const [resourceKey, setResourceKey] = useState<string | null>(null);
  const [resourcePending, setResourcePending] = useState(false);
  const [realPoseData, setRealPoseData] = useState<string | null>(null);
  const [realProteinData, setRealProteinData] = useState<string | null>(null);
  // Interacciones no-covalentes ligando-proteína (PLIF) para el Web3D
  const [interactions, setInteractions] = useState<InteractionDatum[]>([]);

  // Resultado real: solo cuando el polling (autoridad final) dice SUCCESS.
  // Sin resultado real la sección de resultados no se renderiza (estado vacío).
  const realResult: EvaluationResult | null =
    status?.status === "SUCCESS" && status.result ? status.result : null;
  const selectedResultKey = `${realResult?.molecule_id ?? ""}:${realResult?.task_id ?? ""}`;
  const selectedResultRef = useRef(selectedResultKey);
  selectedResultRef.current = selectedResultKey;
  const hasJob = !!status;
  const isRunning = hasJob && status!.status !== "SUCCESS" && status!.status !== "FAILURE";
  const showProcessing = busy === true || isRunning;
  const failed = hasJob && status!.status === "FAILURE";
  const reviewingResult = showResults && !showProcessing && !failed && realResult !== null;
  const [configurationOpen, setConfigurationOpen] = useState(false);
  const configurationRef = useRef<HTMLDetailsElement>(null);
  const configurationLabelId = useId();
  useEffect(() => { setConfigurationOpen(false); }, [selectedResultKey]);
  useEffect(() => {
    const input = realResult?.ligand_state?.smiles_entrada;
    if (input && smiles.trim() !== input.trim()) setConfigurationOpen(true);
  }, [smiles, selectedResultKey]);
  const recordedProtocol = realResult?.docking_protocol;
  const recordedProtocolFacts = [
    recordedProtocol?.engine ?? realResult?.engine_used,
    typeof recordedProtocol?.exhaustiveness === "number" ? t("pr_ev_protocol_exhaustiveness",{value:recordedProtocol.exhaustiveness}) : null,
    typeof recordedProtocol?.seed === "number" ? t("pr_ev_protocol_seed",{value:recordedProtocol.seed}) : null,
  ].filter(Boolean).join(" · ");

  // FIX (v1.7.5): si el backend reportó SUCCESS pero sin resultado (result
  // null por un fallo de validación silencioso), NO mostrar un resultado
  // inventado — tratar como error honesto.
  const silentResultLoss =
    hasJob && status!.status === "SUCCESS" && !status!.result && !resultRecovery;
  const displayResult: any = silentResultLoss ? null : realResult;
  // Link de blockchain: solo con un resultado real certificado.
  const blockchainTxId = realResult?.blockchain_tx_id ?? null;
  // B-1: el sello puede ser de una corrida anterior de la misma molécula.
  const lecturaDelSello = leerSelloDelResultado(realResult);

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
    engine: "vina",
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
  // Tres estados (ver `lib/seleccionDeResiduos`): `null` = sin decidir (catálogo), `[]` =
  // «ninguno», lista = sólo esos. Antes `[]` se convertía en `null` y la decisión de no usar
  // residuos se perdía al reabrir «Opciones» (QA1-007).
  const [customHotspots, setCustomHotspots] = useState<string[] | null>(() =>
    seleccionInicial(initialRunConfiguration?.customHotspots),
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
    // Como el pH: una corrida guardada reabre con SU modo. Antes del 2026-10-10 el canónico
    // era el defecto y se guardaba sin clave; desde entonces el defecto es el tautómero escrito.
    tautomerMode: ((): "canonico" | "entrada" => {
      const guardado: unknown = initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.tautomero;
      if (guardado === "canonico" || guardado === "entrada") return guardado;
      return initialRunConfiguration?.pipelineConfig ? "canonico" : "entrada";
    })(),
    numWorkers: initialRunConfiguration?.pipelineConfig?.pro_workers ?? 4,
    parallelDocks: initialRunConfiguration?.pipelineConfig?.pro_parallel_docks ?? 2,
    enableSelectivity: initialRunConfiguration?.pipelineConfig?.pro_selectivity ?? false,
    selectedAntiTargets: [...(initialRunConfiguration?.pipelineConfig?.pro_anti_targets ?? [])],
    antiTargetsPending: initialRunConfiguration?.pipelineConfig?.pro_anti_targets === undefined,
    enableMMGBSA: false,
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

  const anti = useAntiDianas();
  const antiDefaultsInitialized = useRef(false);
  useEffect(() => {
    if (anti.targets && !antiDefaultsInitialized.current) {
      antiDefaultsInitialized.current = true;
      if (initialRunConfiguration?.pipelineConfig?.pro_anti_targets === undefined) {
        setAdvancedOpts((value) => ({ ...value, selectedAntiTargets: antiDianasPorDefecto(anti.targets!), antiTargetsPending: false }));
      }
    }
  }, [anti.targets, initialRunConfiguration]);

  // Aplicar Opciones. Una elección que llega de fuera del modal (Preparación pide otro
  // tautómero) pasa por aquí también: si no, el preflight no la vería.
  const aplicarOpciones = (
    engineRaw: DockingEngineConfig,
    gridRaw: GridBoxConfig,
    adv: AdvancedConfig,
    hotspotsRaw?: readonly string[] | null,
    conformers: number = activeConformers,
  ) => {
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
    setCustomHotspots(seleccionAplicada(hotspots));
    // Caja, residuos, motor y profundidad forman una sola hipótesis de
    // ejecución. Persistir sólo la caja dejaba cambiar el motor después
    // del preflight sin invalidarlo.
    onRunConfigurationChange?.({
      center: [grid.centerX, grid.centerY, grid.centerZ],
      size: [grid.sizeX, grid.sizeY, grid.sizeZ],
      customHotspots: seleccionParaGuardar(seleccionAplicada(hotspots)),
      dockingEngine: engine.engine,
      exhaustiveness: grid.exhaustiveness,
      numPoses: grid.numModes,
      conformers,
      pipelineConfig: {
        enabled_stages: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
        stage_params: {
          docking: { exhaustiveness: grid.exhaustiveness, num_poses: grid.numModes },
          properties: { run_admet_ai: adv.enableADMET },
          // `conformers` y `ph` viajan juntos: los dos son del mismo
          // paso. Mandar uno y olvidar el otro dejaba el control de pH
          // de adorno según por dónde se lanzara la corrida.
          //
          // El modal abre con el K vigente, nunca el del sistema
          // congelado. Su borrador aplicado se guarda arriba y aquí
          // en una sola actualización para invalidar el preflight.
          conformer: {
            conformers,
            ph: adv.protonationPh,
            // Siempre explícito: el defecto del backend ya no es el canónico.
            tautomero: adv.tautomerMode ?? "entrada",
          },
        },
        docking_engine: engine.engine,
        pro_workers: adv.numWorkers,
        pro_parallel_docks: adv.parallelDocks,
        pro_selectivity: adv.enableSelectivity,
        pro_anti_targets: [...adv.selectedAntiTargets],
        pro_mmgbsa: false,
        pro_mmgbsa_steps: adv.mmgbsaSteps,
        gnn_precision: engine.gnnPrecision,
        peptide_docking_engine: engine.peptideEngine ?? undefined,
      },
    });
  };

  // Preparación pidió volver a evaluar con este modo: se aplica una vez por petición, cuando
  // las anti-dianas ya están resueltas (aplicarlas pendientes guardaría «ninguna»).
  const tautomeroAplicado = useRef<number | null>(null);
  useEffect(() => {
    if (!tautomeroPedido || tautomeroAplicado.current === tautomeroPedido.nonce) return;
    if (advancedOpts.antiTargetsPending) return;
    tautomeroAplicado.current = tautomeroPedido.nonce;
    aplicarOpciones(dockingEngine, gridBox, { ...advancedOpts, tautomerMode: tautomeroPedido.modo }, customHotspots);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tautomeroPedido, advancedOpts.antiTargetsPending]);

  const effectiveAntiTargets = antiDianasParaEnviar(anti.targets, advancedOpts.selectedAntiTargets);
  const antiNeedsReview = advancedOpts.enableSelectivity && (anti.targets === null || anti.error || effectiveAntiTargets.length !== advancedOpts.selectedAntiTargets.length);

  /**
   * Con un sitio entre cadenas el receptor fijado las lleva todas (QA-001):
   * «1HSG · cadena A» contradecía a la tarjeta «Interfaz B·A» de al lado.
   */
  const cadenasDelSistema = useMemo(() => {
    const sitio = selectedTargetObj?.site_chains ?? [];
    if (!structuralSystem || new Set(sitio).size < 2) return null;
    if (selectedTargetObj?.pdb_id?.toUpperCase() !== structuralSystem.receptor.pdbId.toUpperCase()) return null;
    return [...new Set(sitio)].sort().join("+");
  }, [selectedTargetObj, structuralSystem]);

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

  // Reporta los análisis como TRABAJO VIVO al contenedor del caso. Es un cálculo
  // largo que no pasa por `taskId`, así que sin este aviso el workspace lo
  // daría por inexistente y permitiría cambiar de caso a mitad, dejándolo
  // huérfano. No altera el cálculo: sólo lo declara.
  useEffect(() => {
    onLongRunningWorkChange?.(mmgbsaState === "running" || selectivityWorking);
  }, [mmgbsaState, selectivityWorking, onLongRunningWorkChange]);
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
    const runId = realResult?.task_id;
    const requestKey = selectedResultKey;
    if (!moleculeId || !runId) {
      setAdmetError(t("ev_admet_requiere_corrida"));
      setAdmetState("error");
      return;
    }
    setAdmetState("running");
    setAdmetError(null);
    try {
      const perfil = await runAdmet(moleculeId, { taskId: runId });
      if (selectedResultRef.current !== requestKey) return;
      if (perfil.task_id !== runId) throw new Error(t("pr_sel_result_identity_mismatch"));
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
          : t("ev_admet_no_guardado"),
      );
      setAdmetState("done");
    } catch (err) {
      if (selectedResultRef.current !== requestKey) return;
      setAdmetError(err instanceof Error ? err.message : String(err));
      setAdmetState("error");
    }
  }, [admetState, realResult?.molecule_id, realResult?.task_id, selectedResultKey, status, setStatus, t]);

  useEffect(() => {
    setAdmetState("idle"); setAdmetError(null); setPoseComparison(null);
  }, [selectedResultKey]);

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

  // Every resource belongs to the selected run. A missing historical snapshot
  // stays missing; the catalogue is only an input preview before a result exists.
  useEffect(() => {
    const mid = realResult?.molecule_id;
    const runId = realResult?.task_id ?? null;
    let cancelled = false;
    setResourceKey(`${mid ?? ""}:${runId ?? ""}`);
    setResourcePending(Boolean(mid));
    setRealPoseData(null); setRealProteinData(null); setInteractions([]);
    if (!mid || !runId) { setResourcePending(false); return; }
    void getPoseFile(mid, runId).then(sdf => { if (!cancelled) setRealPoseData(sdf || null); }).catch(() => {});
    void getProteinFile(mid, runId).then(pdb => { if (!cancelled) setRealProteinData(pdb || null); }).catch(() => {}).finally(() => { if (!cancelled) setResourcePending(false); });
    void getInteractions(mid, 1, runId).then(report => {
      if (!cancelled && (!runId || report?.task_id === runId)) setInteractions(report?.interactions ?? []);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [realResult?.molecule_id, realResult?.task_id, realResult?.poses_file_path]);

  const resourcesMatch = resourceKey === `${realResult?.molecule_id ?? ""}:${realResult?.task_id ?? ""}`;

  const executedBox = realResult?.docking_protocol?.execution_provenance;
  const numericTriple = (value: unknown): value is [number, number, number] =>
    Array.isArray(value) && value.length === 3 && value.every(item => typeof item === "number" && Number.isFinite(item));
  const viewerGrid = realResult
    ? numericTriple(executedBox?.box_center) && numericTriple(executedBox?.box_size)
      ? { centerX: executedBox.box_center[0], centerY: executedBox.box_center[1], centerZ: executedBox.box_center[2], sizeX: executedBox.box_size[0], sizeY: executedBox.box_size[1], sizeZ: executedBox.box_size[2] }
      : null
    : gridBox.centerX !== 0 || gridBox.centerY !== 0 || gridBox.centerZ !== 0
      ? { centerX: gridBox.centerX, centerY: gridBox.centerY, centerZ: gridBox.centerZ, sizeX: gridBox.sizeX, sizeY: gridBox.sizeY, sizeZ: gridBox.sizeZ }
      : null;

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

  const systemPanel = structuralSystem ? (
    <ConfigurationSystem system={structuralSystem} provisional={structuralSystemProvisional} chains={cadenasDelSistema ?? null} />
  ) : null;

  return (
    <div className={`${resultStyles.workspace} min-h-full bg-surface-950 p-3 sm:p-4 md:p-8 flex flex-col items-center justify-start space-y-4 sm:space-y-6`}>
      
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
              preparacion={{ ph: advancedOpts.protonationPh, tautomero: advancedOpts.tautomerMode ?? "entrada" }}
            />
          </div>

          {/* Campo SMILES y contexto del sistema que admite esta entrada. */}
          <div className={configurationStyles.smilesField}>
          <div className="h-14 border border-zinc-800 rounded-2xl bg-zinc-950 shadow-lg px-4 flex items-center gap-3">
            <label htmlFor={`${configurationLabelId}-smiles`} className="text-sm font-sans font-bold uppercase tracking-wider text-purple-400 shrink-0">
              SMILES:
            </label>
            <input
              id={`${configurationLabelId}-smiles`}
              aria-describedby={structuralSystem ? `${configurationLabelId}-system-help` : undefined}
              type="text"
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              className="flex-1 bg-surface-950 border border-surface-700 rounded-xl px-3 py-1.5 font-mono text-sm text-zinc-100 placeholder:text-zinc-400 focus-visible:outline-none focus-visible:border-brand-500 focus-visible:ring-1 focus-visible:ring-brand-500 transition-colors h-9"
              placeholder={t("ev_estructura_smiles")}
            />
          </div>
          {structuralSystem && <p id={`${configurationLabelId}-system-help`} className={configurationStyles.smilesSystemNote} data-system-input-note>
            {t(structuralSystemProvisional ? "ev_sistema_provisional_detalle" : "ev_sistema_fijado_detalle")}
          </p>}
          </div>
          {/* SOL-10: la aspirina de muestra NO se persiste como hipótesis del
              usuario al abrir el caso (decisión documentada arriba); lo honesto
              es decir que es muestra y qué pasa si se evalúa tal cual. La nota
              se apaga sola en cuanto el ligando entra al caso, que ocurre al
              editarlo o al pulsar «Ejecutar evaluación». */}
          {ejemploEnEditor && (
            <p
              role="status"
              className="flex items-start gap-2 rounded-2xl border border-amber-500/25 bg-amber-500/[0.05] px-4 py-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans"
            >
              <FlaskConical size={13} className="mt-0.5 shrink-0 text-amber-400" aria-hidden="true" />
              {t("ev_editor_ejemplo")}
            </p>
          )}
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
              <div role="status" className="font-sans text-sm uppercase tracking-wider text-zinc-400">
                {t("ev_comprobando_visor")}
              </div>
            ) : viewerMode === "molstar" ? (
              <AdvancedMolstarViewer
                proteinData={realResult ? resourcesMatch ? realProteinData ?? undefined : undefined : proteinData ?? receptorPdb ?? undefined}
                poseData={realResult ? resourcesMatch ? realPoseData ?? undefined : undefined : poseData ?? undefined}
                height={640}
                isActive={isActive}
                onSwitchViewer={() => setViewerMode("web3d")}
                viewerLabel="Web3D"
                gridInfo={viewerGrid}
                externalCamera={web3dCamera}
                onCameraChange={setMolstarCamera}
              />
            ) : (
              <Web3DViewer
                proteinData={realResult ? resourcesMatch ? realProteinData ?? undefined : undefined : proteinData ?? receptorPdb ?? undefined}
                poseData={realResult ? resourcesMatch ? realPoseData ?? undefined : undefined : poseData ?? undefined}
                interactions={resourcesMatch && interactions.length > 0 ? interactions : undefined}
                chain={realResult ? undefined : selectedTargetObj?.chain ?? undefined}
                hotspots={realResult ? realResult.target_hotspots ?? [] : targetHotspotsList}
                gridInfo={viewerGrid}
                onSwitchViewer={() => setViewerMode("molstar")}
                viewerLabel="MolStar"
                externalCamera={molstarCamera}
                onCameraChange={setWeb3dCamera}
                active={viewerMode === "web3d"}
              />
            )}
          </div>

          {realResult && resourcesMatch && !resourcePending && !realProteinData && <p role="status" className="text-sm leading-6 text-amber-300">{t("rx_sin_receptor_exacto")}</p>}

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
              <span className="text-sm font-sans font-bold uppercase tracking-wider text-white truncate">
                {loadingReceptor ? (
                  <span className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse" />
                    {t("ev_cargando_receptor", { pdbId: target })}
                  </span>
                ) : target ? (
                  t("ev_receptor_elegido", { pdbId: target })
                ) : (
                  t("ev_elige_receptor")
                )}
              </span>
            </div>
            <span className="shrink-0 font-mono text-sm font-semibold text-zinc-200 transition-colors group-hover:text-purple-200">
              {structuralSystemLocked ? t("ev_sistema_fijado_corto") : target ? t("auto_88e384ba325d") : t("auto_a857918b94ae")}
            </span>
          </button>

          {/* Lo que se sabe del sitio de ESTE receptor, dicho donde el usuario
              está a punto de lanzar la evaluación. El catálogo ya lo declara en
              la tarjeta; repetirlo aquí no es redundancia: quien abre un caso
              guardado, o vuelve tras cambiar de pestaña, no pasa por el
              catálogo y se llevaría el número sin la condición. */}
          {selectedTargetObj && (
            <div className="mt-2 space-y-2 px-1">
              <InsigniaDelCatalogo
                ayudaFlotante
                target={selectedTargetObj}
                corrida={realResult}
                etiquetaAdicional={<>
                  <DetalleDelSitio key={selectedTargetObj.pdb_id} target={selectedTargetObj} variante="etiqueta" />
                  <ChipsDelSitio target={selectedTargetObj} variante="linea" mostrarEtiquetaDelSitio={false} />
                </>}
              />
              {/* La etiqueta del sitio abre su explicación; los otros chips
                  conservan evidencia y procedencia de los hotspots. */}
            </div>
          )}
        </div>

        {/* El sistema pertenece al par ligando-receptor, no sólo al receptor.
            En escritorio ocupa ambas columnas; en móvil cae debajo de los dos
            selectores sin introducir desplazamiento horizontal. */}
        {!reviewingResult && systemPanel}

      </div>

      <details ref={configurationRef} className={`${resultStyles.configuration} ${configurationStyles.disclosure}`} open={!reviewingResult || configurationOpen}
        onToggle={event => { if (reviewingResult) setConfigurationOpen(event.currentTarget.open); }} data-evaluation-configuration="true">
        <summary className={configurationStyles.toggle} data-configuration-toggle data-has-system={reviewingResult && Boolean(structuralSystem)}
          aria-labelledby={configurationLabelId}
          aria-describedby={reviewingResult ? `${configurationLabelId}-protocol${structuralSystem ? ` ${configurationLabelId}-system` : ""}` : undefined}>
          <span className={configurationStyles.toggleTitle}><span id={configurationLabelId} className={resultStyles.configurationLabel}>{t(reviewingResult ? "ux_configuration" : "ux_prepare_next")}</span>
          {reviewingResult && <span id={`${configurationLabelId}-protocol`} className={resultStyles.configurationFacts}>{recordedProtocolFacts || t("pn_no_registrado_corrida")}</span>}</span>
          {reviewingResult && structuralSystem && <ConfigurationSystem system={structuralSystem} provisional={structuralSystemProvisional} chains={cadenasDelSistema ?? null} compact id={`${configurationLabelId}-system`} />}
          <ChevronDown className={configurationStyles.toggleChevron} size={18} aria-hidden="true"/>
        </summary>
        <ConfigurationPresentation>
          {reviewingResult && <p className={configurationStyles.intro}>{t("ux_prepare_note")}</p>}
      {/* Preparación de la corrida.
          Aquí vivía `EvaluationReadinessPanel`, que respondía a esta misma
          pregunta CONJETURANDO desde el navegador: «SMILES presente; se
          validará al ejecutar». Dos respuestas distintas a la misma pregunta,
          y la que ocupaba el sitio era la que no había mirado los archivos.
          Ahora el hueco lo llena la comprobación previa real. */}
      <div className={configurationStyles.columns} data-has-preflight={Boolean(preparationSlot)} data-has-estimate={Boolean(canRunEvaluation)}>
        <div>{preparationSlot}</div>

      {/* Cuánto va a tardar, JUSTO antes del botón. Aquí es donde se hace la
          pregunta —no al configurar—, y por eso el estimador que ya existía no
          lo leía nadie: vivía en un panel de opciones que ningún componente
          importaba. Se oculta solo si no hay receptor y ligando: estimar sin
          saber qué se va a correr sería inventar. */}
      {Boolean(canRunEvaluation) && <aside className={configurationStyles.durationColumn}><EstimacionDeCorrida
        visible={Boolean(canRunEvaluation)}
        exhaustiveness={gridBox.exhaustiveness}
        // CAS-04: el K VIGENTE del caso —el que el modal de parámetros
        // acaba de aplicar y el preflight va a firmar—, no el congelado en
        // el sistema de la primera corrida.
        conformers={activeConformers}
        targetPdbId={structuralSystem?.receptor.pdbId ?? target}
        gridSize={[gridBox.sizeX, gridBox.sizeY, gridBox.sizeZ]}
        antiTargets={advancedOpts.enableSelectivity ? effectiveAntiTargets.length : 0}
        mmgbsa={false}
      /></aside>}
      </div>

      {advancedOpts.enableSelectivity && <AntiDianasAviso targets={anti.targets} selected={advancedOpts.selectedAntiTargets} />}
      {advancedOpts.enableSelectivity && (anti.targets === null || anti.error) && <p role="status">{t(anti.error ? "pn_anti_error" : "pn_anti_cargando")}</p>}

        </ConfigurationPresentation>
      </details>

      {/* ── Botonera de Control ── */}
      <div className="w-full max-w-[1600px] flex flex-wrap items-center justify-between gap-4 p-4 border border-zinc-800/80 rounded-2xl bg-[var(--bg-card)] backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowResults((v) => !v)}
            className={`flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2 font-sans text-sm font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 cursor-pointer ${
              showResults 
                ? "bg-[var(--bg-secondary)] border border-purple-500/40 text-[var(--accent-strong)] shadow-sm" 
                : "bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white"
            }`}
          >
            <Activity size={15} className="text-purple-400" />
            {showResults ? t("ev_ocultar_resultados") : t("ev_ver_resultados")}
          </button>
        </div>

        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <button 
            onClick={() => setShowOptionsModal(true)}
            title={
              structuralSystemLocked
                ? t("ev_opciones_fijadas")
                : undefined
            }
            className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2.5 font-sans text-sm font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:bg-zinc-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 cursor-pointer"
          >
            <Settings size={14} />
            {t("ev_parametros_corrida")}
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
                  ? t("ev_sin_evaluaciones_aun")
                  : t("ev_ver_evaluaciones_anteriores")
              }
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2.5 font-sans text-sm font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:bg-zinc-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 cursor-pointer disabled:cursor-not-allowed disabled:opacity-45"
            >
              <History size={14} />
              {t("ev_evaluaciones_anteriores")}
              {runCount > 0 && (
                <span className="rounded-md bg-zinc-800 px-1.5 py-0.5 text-sm text-zinc-300">
                  {runCount}
                </span>
              )}
            </button>
          )}

          <button 
            onClick={() => {
              if (reviewingResult && !configurationOpen) {
                setConfigurationOpen(true);
                configurationRef.current?.scrollIntoView({block:"nearest"});
                return;
              }
              if (antiNeedsReview) return;
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
                  pro_anti_targets: effectiveAntiTargets,
                  pro_mmgbsa: false,
                  pro_mmgbsa_steps: advancedOpts.mmgbsaSteps,
                  gnn_precision: dockingEngine.gnnPrecision,
                  peptide_docking_engine: dockingEngine.peptideEngine ?? undefined,
                }
              );
            }}
            disabled={busy || isRunning || !canRunEvaluation || Boolean(runBlockedReason) || antiNeedsReview}
            title={
              runBlockedReason ??
              (!canRunEvaluation ? t("ev_falta_smiles_o_receptor") : undefined)
            }
            aria-describedby={runBlockedReason ? "run-blocked-reason" : undefined}
            className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-purple-400/30 bg-purple-600 px-6 py-2.5 font-sans text-sm font-bold uppercase tracking-wider text-[#fff] shadow-lg shadow-purple-950/50 transition-colors hover:bg-purple-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy || isRunning ? (
              <>
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white inline-block" />
            {t("ev_evaluando")}
              </>
            ) : (
              <>
                <Play size={14} />
                {t(reviewingResult && !configurationOpen ? "ux_prepare_next" : "ev_ejecutar")}
              </>
            )}
          </button>

          {/* Botón Cancelar: mata todos los procesos del pipeline (incl. MM-GBSA) */}
          {(busy || isRunning) && (
            <button
              onClick={() => {
                void handleCancel?.();
              }}
              className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-rose-400/30 bg-rose-600/80 px-5 py-2.5 font-sans text-sm font-bold uppercase tracking-wider text-[#fff] transition-colors hover:bg-rose-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-300 cursor-pointer"
              title={t("ev_cancelar_corrida")}
            >
              <X size={14} />
              {t("c_cancelar")}
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
          className="w-full max-w-[1600px] rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3 text-base leading-6 text-zinc-400 font-sans"
        >
          {runBlockedReason}
        </p>
      )}

      {/* ── Banner de error (submit sin target, backend failure, etc.) ── */}
      {(error || (failed && status?.error)) && (
        <div role="alert" aria-live="assertive" className="w-full max-w-[1600px] rounded-2xl border border-rose-500/30 bg-rose-950/30 px-4 py-3 text-sm font-mono text-rose-300 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0 text-rose-400" />
          <span className="leading-relaxed">{error ?? status?.error}</span>
        </div>
      )}

      {/* ─── Pantalla de Carga: orbe de la evaluación + Pipeline Timeline LIVE (SSE) ─── */}
      {showProcessing && (
        <div className="w-full max-w-[1600px] flex flex-col items-center justify-center gap-4 animate-in fade-in duration-300">
          <OrbeDeEvaluacion label={t("ev_procesando")} />
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
        <div className={`w-full max-w-[1600px] rounded-2xl border p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300 ${
          cancelled ? "border-zinc-700 bg-zinc-900/40" : "border-rose-500/25 bg-rose-950/20"
        }`}>
          <AlertTriangle size={40} className={cancelled ? "text-zinc-400/70" : "text-rose-400"} />
          <p className={`text-sm font-black uppercase tracking-widest font-sans ${cancelled ? "text-zinc-300" : "text-rose-300"}`}>
            {cancelled ? t("ev_cancelada") : t("ev_fallo")}
          </p>
          <p className="text-base font-sans text-zinc-300 max-w-lg leading-6">
            {status?.error ?? error ?? t("ev_error_pipeline")}
          </p>
          <button
            onClick={() => handleReset?.()}
            className="mt-2 min-h-11 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2 font-sans text-sm font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400 cursor-pointer"
          >
            {t("ev_reiniciar")}
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
            <AlertTriangle size={40} className="text-amber-400" aria-hidden="true" />
          )}
          <p className={`text-sm font-black uppercase tracking-widest font-sans ${resultRecovery.state === "blocked" ? "text-amber-800 dark:text-amber-300" : "text-brand-400"}`}>
            {resultRecovery.state === "recovering"
              ? t("ev_recuperando_resultados")
              : t("ev_no_se_abrio_resultado")}
          </p>
          <p className="text-base font-sans text-zinc-300 max-w-xl leading-6">
            {resultRecovery.message ?? t("ev_consultando_evidencia")}
          </p>
          {resultRecovery.state === "blocked" && onRetryResultRecovery && (
            <button
              type="button"
              onClick={onRetryResultRecovery}
              className="mt-2 min-h-11 whitespace-nowrap rounded-xl border border-amber-500/35 bg-amber-500/10 px-5 py-2 font-sans text-sm font-bold uppercase tracking-wider text-amber-800 dark:text-amber-200 transition-colors hover:bg-amber-500/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
            >
              {resultRecovery.requiresLogin ? t("c_iniciar_sesion") : t("ev_reintentar_recuperacion")}
            </button>
          )}
        </div>
      )}

      {/* ─── FIX v1.7.5: SUCCESS sin resultado (pérdida silenciosa) ─── */}
      {showResults && silentResultLoss && !showProcessing && !failed && (
        <div className="w-full max-w-[1600px] rounded-2xl border border-amber-500/25 bg-amber-950/20 p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300">
          <AlertTriangle size={40} className="text-amber-400" />
          <p className="text-sm font-black uppercase tracking-widest text-amber-800 dark:text-amber-300 font-sans">
            {t("ev_sin_resultados_titulo")}
          </p>
          <p className="text-base font-sans text-zinc-300 max-w-lg leading-6">
            {t("ev_sin_resultados_detalle")}
          </p>
          <button
            onClick={() => handleReset?.()}
            className="mt-2 min-h-11 whitespace-nowrap rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-2 font-sans text-sm font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400 cursor-pointer"
          >
            {t("ev_reiniciar")}
          </button>
        </div>
      )}

      {/* ───── SIN RESULTADOS TODAVÍA: estado honesto, sin mock ───── */}
      {showResults && !showProcessing && !failed && realResult === null && !silentResultLoss && !resultRecovery && (
        <div className="w-full max-w-[1600px] rounded-2xl border border-white/5 bg-white/[0.02] p-10 flex flex-col items-center gap-3 text-center animate-in fade-in duration-300">
          <Activity size={32} className="text-zinc-400" />
          <p className="text-sm font-black uppercase tracking-widest text-zinc-400 font-sans">
            {t("ev_sin_resultados_aun")}
          </p>
          <p className="text-base font-sans text-zinc-300 max-w-md leading-6">
            {t("ev_elige_para_empezar")}
          </p>
        </div>
      )}

      {/* ───── RESULTADOS: HERO → DOT → COLUMNS → VERIFY ───── */}
      {showResults && !showProcessing && !failed && realResult !== null && (
        <ResultReadingPresentation><div className="w-full max-w-[1600px] space-y-6 animate-in fade-in duration-300">

          {/* ─── RESUMEN DE EVIDENCIA ─── */}
          <div ref={heroRef}>
            <EvaluationEvidencePanel
              compact
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
              <p className="min-w-0 break-words font-sans text-base text-zinc-300 leading-6">
                {displayResult.target_name ?? "—"} ({selectedTargetObj?.pdb_id ?? "—"}{t("auto_c2afbe19da8c")} {realResult.molecule_id?.slice(0, 8) ?? t("auto_14009a618e8d")} {t("auto_655a8de817b6")}
                {/* B-2: una corrida reabierta de 1.0.1 no se lee en la escala de hoy. */}
                {realResult.protocolo?.vigente === false && (
                  <span className="mt-1 block font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300" title={t("pg_protocolo_anterior_d")}>
                    {t("pg_protocolo_anterior")} · {t("pg_protocolo_anterior_d")}
                  </span>
                )}
              </p>

            </div>
          </div>

            {/* ─── DOT: Pipeline Timeline (family-gated, dinámico) ─── */}

          {/* ─── ANÁLISIS: evidencia estructural · propiedades · post-docking ─── */}
          <section className="mt-6">
            {!realResult.task_id && <p role="status" className="mb-4 text-sm leading-6 text-amber-300">{t("rx_sin_identidad_corrida")}</p>}
            <ProAnalysisTabs

              signalsSlot={(() => {
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
              const famLabel = localizePipelineText(FAMILY_LABELS[famKey] ?? famKey, t);

              // La definición de familia ordena las etapas. Los valores y
              // pesos que se presentan como registrados pertenecen a la corrida.
              const realDot: Record<string, { value?: string; weight?: number; sub?: string }> = {};
              const registroDePesos = pesosRegistrados(realResult);
              const perfilM5Calculado = protocoloRegistrado(realResult) === "M5-Zn";
              if (realResult) {
                const vinaAff = realResult.docking_poses?.[0]?.affinity;
                if (vinaAff != null) realDot.vina = { value: `${vinaAff.toFixed(1)} kcal/mol` };
                if (realResult.xgb_score != null) realDot.xgb = { value: `salida ${realResult.xgb_score.toFixed(2)}` };
                if (realResult.clgnn_score != null) realDot.clgnn = { value: realResult.clgnn_score.toFixed(2) };
                if (realResult.gnn_score != null) realDot.gnn = { value: realResult.gnn_score.toFixed(2) };
                if (realResult.quantum_score != null) realDot.quantum = { value: realResult.quantum_score.toFixed(2) };
                // La señal AUTORIZADA de los tres perfiles M5-Zn es
                // `ums_warhead` (SMARTS puro). `ums_score` es el UMS histórico
                // —warheads + donantes + MolChamb— y sólo se muestra cuando la
                // corrida es anterior a SCHEMA 18, diciendo que es el histórico.
                if (realResult.ums_warhead != null) {
                  realDot.ums = { value: realResult.ums_warhead.toFixed(2), sub: "SMARTS · informativa" };
                } else if (realResult.ums_score != null) {
                  realDot.ums = { value: realResult.ums_score.toFixed(2), sub: t("ev_ums_historico") };
                }

                // MM-GBSA on-demand (modal): el endpoint NO persiste al ORM,
                // así que el valor vive en estado local → override acá.
                if (mmgbsaResult?.delta_g_total_kcal != null) {
                  realDot.mmgbsa = {
                    value: `${mmgbsaResult.delta_g_total_kcal.toFixed(1)} kcal/mol`,
                    sub: mmgbsaResult.platform ?? t("ev_mmgbsa_motor_predeterminado"),
                  };
                }
                if (!perfilM5Calculado) {
                  for (const [id, weight] of Object.entries(registroDePesos.values)) {
                    realDot[id] = { ...realDot[id], weight };
                  }
                }
              }

              // DOC 71, defectos A3 y A7: la regla vive en
              // `lib/procedenciaDeSenales.ts`, con su prueba. Ver allí por qué
              // «sin salida serializada» sólo puede decirse cuando no hay valor.
              const effectiveStages = pipeline.stages.map((s) => ({
                ...s,
                ...describirEtapa(s, realDot[s.id]),
                weight: perfilM5Calculado ? 0 : registroDePesos.values[s.id] ?? s.weight,
              }));
              const activeStages = effectiveStages.filter((s) => {
                // MM-GBSA no forma parte de las corridas actuales. No ocupamos
                // espacio con su estado de ausencia: sólo aparecerá si existe
                // un resultado real generado después de la evaluación.
                if (s.id === "mmgbsa" && realDot.mmgbsa?.value == null) return false;
                // quantum solo se muestra si el backend lo calculó (no en legacy)
                if (realResult && s.id === "quantum" && realResult.quantum_score == null) return false;
                // ums solo se muestra si el backend lo calculó (metaloenzimas; evita
                // mostrar 0.5 neutral de targets no-metal / registros legacy)
                if (realResult && s.id === "ums" && !tieneSalidaUms(realResult)) return false;
                return perfilM5Calculado ? s.aporto || s.post_hoc : s.weight > 0 || s.post_hoc;
              });
              // Sólo los pesos persistidos permiten afirmar que faltó una
              // señal ponderada. El diseño de familia no completa el registro.
              const ausentes = perfilM5Calculado ? [] : etapasAusentes(effectiveStages.filter((stage) =>
                registroDePesos.values[stage.id] != null,
              ));
              return (
                <>
                <div className="mb-5">
                  <PipelineDeLaCorrida resultado={realResult} />
                </div>

                <section ref={dotRef} className="border-b border-white/5 pb-5">
                  <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
                    <h3 className="text-sm font-bold text-zinc-200">{t("pr_signals_recorded_title")}</h3>
                    <span className="text-sm text-zinc-300 border border-white/10 rounded px-2 py-1">
                      {t("auto_e198b2927fa4")} {famLabel}
                    </span>
                  </div>
                  {!perfilM5Calculado && <p className="mb-4 break-words text-base leading-6 text-zinc-300 font-sans">
                    {registroDePesos.source === "missing" ? t("pr_signals_weights_missing")
                      : t(registroDePesos.source === "effective" ? "pr_signals_effective_weights" : "pr_signals_individual_weights", {
                        weights: Object.entries(registroDePesos.values).map(([id, weight]) =>
                          `${localizePipelineText(pipeline.stages.find((stage) => stage.id === id)?.label ?? id, t)} ${weight.toFixed(4)}`,
                        ).join(" · "),
                      })}
                  </p>}

                  {ausentes.length > 0 && (
                    <div
                      role="status"
                      className="mb-4 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] px-3 py-2.5"
                    >
                      <p className="font-sans text-sm font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300">
                        {t("ev_pipeline_degradado")}
                      </p>
                      <p className="mt-1.5 max-w-[78ch] text-base leading-6 text-amber-800 dark:text-amber-100 font-sans">
                        {t("pr_signals_missing_weighted", {
                          signals: ausentes.map((etapa) => `${localizePipelineText(etapa.label, t)} w=${etapa.pesoDeDiseno.toFixed(4)}`).join(" · "),
                        })}
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
                      const mmgbsaClickable = false;

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
                            className="text-sm font-bold uppercase tracking-wider font-sans whitespace-nowrap"
                            style={{
                              color: mmgbsaClickable ? "#c4b5fd" : mmgbsaRunning ? "#6ee7b7" : mmgbsaDone ? "#34d399" : dimmed ? "#ffffff20" : "#ffffffb3",
                            }}
                          >
                            {mmgbsaRunning ? t("auto_bbaf37d0b894") : localizePipelineText(node.label, t)}
                          </span>
                          <span
                            className="text-sm font-bold font-mono"
                            style={{
                              color: mmgbsaRunning ? "#34d399" : mmgbsaDone ? "#34d399" : dimmed ? "#ffffff20" : "#ffffffe6",
                              opacity: mmgbsaRunning ? 0.7 : 1,
                            }}
                          >
                            {mmgbsaRunning ? "···" : localizePipelineText(node.value, t)}
                          </span>
                          <span className="text-sm font-mono text-zinc-400 whitespace-nowrap">
                            {localizePipelineText(node.sub, t)}
                          </span>
                          {mmgbsaDone && (
                            <span className="text-sm font-sans uppercase tracking-wider text-emerald-400 border border-emerald-500/20 rounded px-1 py-0.5">
                              {t("auto_1699d016aa59")}
                            </span>
                          )}
                          {node.post_hoc && (
                            <span className="text-sm font-sans uppercase tracking-wider text-zinc-400 border border-white/10 rounded px-1 py-0.5">
                              {t("ev_post_hoc_badge")}
                            </span>
                          )}
                          {!node.post_hoc && node.weight > 0 && node.reportedWeight != null && (
                            <span className="text-sm font-mono text-purple-400">
                              w={node.reportedWeight.toFixed(2)}
                            </span>
                          )}
                          {!node.post_hoc && node.weight > 0 && node.reportedWeight == null && (
                            <span className="text-sm font-sans uppercase tracking-wider text-zinc-400">
                              {t("ev_peso_no_reportado")}
                            </span>
                          )}
                          {!perfilM5Calculado && node.weight === 0 &&
                            !node.post_hoc &&
                            !node.degraded && (
                              <span className="text-sm font-sans uppercase tracking-wider text-zinc-400 border border-white/5 rounded px-1 py-0.5">
                                {t("ev_fuera_de_uso")}
                              </span>
                            )}
                          {!perfilM5Calculado && node.note && (
                            <span className="text-sm font-mono text-zinc-400 max-w-[120px] text-center leading-tight mt-0.5">
                              {localizePipelineText(node.note, t)}
                            </span>
                          )}
                        </>
                      );

                      return (
                        <React.Fragment key={node.id}>
                          {isMmgbsa && !mmgbsaDone ? (
                            <button
                              onClick={() => {}}
                              disabled
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
                  {!perfilM5Calculado && <p className="text-base text-zinc-400 mt-2 font-sans leading-6">
                    {t("ev_pesos_no_calibrados")}
                  </p>}
                </section>
                </>
              );
            })()}
              provenanceSlot={<EvaluationEvidencePanel result={realResult} target={selectedTargetObj} provenanceOnly onOpenPhysicalControls={() => setPhysicalFocusRequest(value => value + 1)} />}
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
              moleculeId={realResult?.task_id ? realResult.molecule_id : null}
              taskId={realResult?.task_id ?? null}
              caseRuns={caseRuns}
              structuralEvidenceResult={realResult}
              physicalFocusRequest={physicalFocusRequest}
              onComparePoses={realResult?.task_id ? (leftRank, rightRank) => setPoseComparison({ leftRank, rightRank }) : undefined}
              enableSelectivity={advancedOpts.enableSelectivity}
              onSelectivityWorkChange={setSelectivityWorking}
              onRequestMmgbsa={() => {
                // MM-GBSA retirado hasta validar un motor de reemplazo.
              }}
              mmgbsaRunning={mmgbsaState === "running"}
              mmgbsaDone={mmgbsaAlreadyDone}
              onRequestAdmet={handleRunAdmet}
              admetRunning={admetState === "running"}
              admetDone={admetYaEsta}
              admetError={admetError}
            />
          </section>

          <EvaluationActionBar
            onDownloadReport={handleDownloadCertificate}
            onViewReport={() => setShowPdfPreview(true)}
            onDownloadComplex={handleDownloadComplex}
            onSave={handleSave ? () => handleSave() : undefined}
            isSaved={isSaved}
            integrityAction={{
              onClick: () => setShowCertificationModal(true),
              disabled: !realResult || lecturaDelSello !== "sin-sello",
              state: lecturaDelSello,
              label: lecturaDelSello === "vigente" ? t("stats_certified")
                : lecturaDelSello === "corrida-anterior" ? t("mx_sello_desfasado")
                  : lecturaDelSello === "indeterminado" ? t("pg_mx_sello_sin_corrida")
                    : t("ev_registrar_integridad_solana"),
              title: lecturaDelSello === "corrida-anterior" ? t("ev_sello_otra_corrida")
                : lecturaDelSello === "indeterminado" ? t("pg_mx_recibo_sin_procedencia")
                  : t("ev_certificar_aviso"),
            }}
          />

          {/* ─── VERIFY: Acciones ─── */}
          {blockchainTxId && <section ref={verifyRef} className="flex flex-wrap items-center gap-4 pt-5 border-t border-white/5">
              <ExternalLink
                href={`https://explorer.solana.com/tx/${blockchainTxId}?cluster=devnet`}
                className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.02] px-5 py-2.5 font-sans text-sm font-bold uppercase tracking-wider text-zinc-400 transition-colors hover:border-purple-500/30 hover:text-purple-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
              >
                <IconoEnlaceExterno size={14} />
                {t("ev_ver_en_solana_explorer")}
              </ExternalLink>
          </section>}

        </div></ResultReadingPresentation>
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
                <h3 id="evaluation-pdf-title" className="text-sm font-black text-white uppercase tracking-widest">{t("ev_reporte_vista_previa")}</h3>
              </div>
              <button
                onClick={() => setShowPdfPreview(false)}
                aria-label={t("ev_cerrar_vista_previa")}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                title={t("c_cerrar")}
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden p-4">
              <PDFReportViewer
                moleculeId={realResult.molecule_id}
                taskId={realResult.task_id ?? null}
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
          taskId={realResult.task_id ?? null}
          onClose={() => setShowCertificationModal(false)}
          onSuccess={({ signature }) => {
            void handleCertify?.(signature);
          }}
        />
      )}

      <ProOptionsModal
        onClose={() => setShowOptionsModal(false)}
        onApply={aplicarOpciones}
        isOpen={showOptionsModal}
        systemSealed={structuralSystemLocked}
        initialEngine={dockingEngine}
        initialConformers={activeConformers}
        initialGridBox={gridBox}
        initialAdvanced={advancedOpts}
        initialHotspots={customHotspots ?? undefined}
        targetHotspots={targetHotspotsList}
      />

      {poseComparison && realResult?.molecule_id && realResult.task_id && (
        <PoseComparisonDialog
          moleculeId={realResult.molecule_id}
          taskId={realResult.task_id}
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
                  <h3 id="mmgbsa-dialog-title" className="text-sm font-black text-white uppercase tracking-widest">{t("ev_mmgbsa_titulo")}</h3>
                  <p className="text-base text-zinc-300 font-sans mt-0.5 leading-6">{t("ev_mmgbsa_nombre_completo")}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => { if (mmgbsaState !== "running") setShowMmgbsaModal(false); }}
                disabled={mmgbsaState === "running"}
                aria-label={t("ev_mmgbsa_cerrar")}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10 transition-colors text-sm disabled:opacity-40"
              >✕</button>
            </div>

            {/* Explanation */}
            <div className="px-6 py-3 bg-emerald-500/5 border-b border-emerald-500/10 shrink-0">
              <p className="text-base text-emerald-300 font-sans leading-6">
                <span className="font-bold text-emerald-300">{t("ev_mmgbsa_que_calcula")}</span> {t("ev_mmgbsa_explicacion")}
              </p>
            </div>

            {/* Config */}
            <div className="px-6 py-4 border-b border-white/5 shrink-0">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-black uppercase tracking-widest text-zinc-400 mb-2">{t("ev_mmgbsa_pose_a_refinar")}</label>
                  <select
                    value={mmgbsaPoseRank}
                    onChange={(e) => setMmgbsaPoseRank(Number(e.target.value))}
                    disabled={mmgbsaState === "running"}
                    className="w-full h-9 px-3 font-mono text-sm font-bold rounded-lg outline-none cursor-pointer disabled:opacity-40 bg-black border border-white/10 text-white"
                  >
                    {availablePoseRanks.map(r => (
                      <option key={r} value={r}>{t("ev_mmgbsa_pose_numero", { rank: r })} {r === 1 ? t("auto_0489bdaf3ead") : ""}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-black uppercase tracking-widest text-zinc-400 mb-2">{t("ev_mmgbsa_pasos")}</label>
                  <select
                    value={mmgbsaNumSteps}
                    onChange={(e) => setMmgbsaNumSteps(Number(e.target.value))}
                    disabled={mmgbsaState === "running"}
                    className="w-full h-9 px-3 font-mono text-sm font-bold rounded-lg outline-none cursor-pointer disabled:opacity-40 bg-black border border-white/10 text-white"
                  >
                    <option value={500}>{t("ev_mmgbsa_pasos_rapido")}</option>
                    <option value={1000}>{t("ev_mmgbsa_pasos_estandar")}</option>
                    <option value={2500}>{t("auto_d922d95776df")}</option>
                    <option value={5000}>{t("ev_mmgbsa_pasos_maximo")}</option>
                  </select>
                </div>
              </div>
              <button
                onClick={handleRunMmgbsa}
                disabled={mmgbsaState === "running"}
                className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 whitespace-nowrap rounded-lg font-sans text-sm font-black uppercase tracking-widest transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                style={{
                  backgroundColor: mmgbsaState === "running" ? "rgba(16,185,129,0.15)" : "rgba(16,185,129,0.9)",
                  color: mmgbsaState === "running" ? "#6ee7b7" : "#fff",
                  border: "1px solid rgba(16,185,129,0.3)",
                }}
              >
                {mmgbsaState === "running" ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-300 border-t-transparent inline-block" />
                    {t("ev_mmgbsa_calculando_pasos", { steps: mmgbsaNumSteps.toLocaleString() })}
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    {t("ev_mmgbsa_ejecutar")}
                  </>
                )}
              </button>
            </div>

            {/* Content: idle → processing → results */}
            <div className="flex-1 overflow-y-auto">
              {mmgbsaState === "idle" && (
                <div className="flex flex-col items-center justify-center py-16 gap-3 text-zinc-400">
                  <FlaskConical size={48} className="text-emerald-500/20" />
                  <p className="text-base font-bold text-zinc-300 font-sans leading-6">{t("ev_mmgbsa_configura")}</p>
                  <p className="text-base text-zinc-300 text-center max-w-xs font-sans leading-6">{t("ev_mmgbsa_depende_gpu")}</p>
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
                    <p className="text-sm font-black text-emerald-400 uppercase tracking-widest animate-pulse">{t("ev_mmgbsa_en_curso")}</p>
                    <p className="text-base text-zinc-300 font-sans leading-6">{mmgbsaNumSteps.toLocaleString()} {t("auto_db10d518faf4")}</p>
                    <p className="text-base text-zinc-300 font-sans leading-6">{t("ev_mmgbsa_puede_tardar")}</p>
                  </div>
                </div>
              )}

              {mmgbsaState === "error" && (
                <div className="flex flex-col items-center justify-center py-12 gap-3 px-6">
                  <AlertTriangle size={40} className="text-rose-400" />
                  <p className="text-sm font-black text-rose-300 uppercase tracking-widest font-sans">{t("ev_mmgbsa_fallo")}</p>
                  <p className="text-base font-sans text-zinc-300 text-center max-w-md leading-6">
                    {mmgbsaError ?? t("ev_mmgbsa_error_desconocido")}
                  </p>
                  <p className="text-base font-sans text-zinc-300 leading-6">{t("ev_mmgbsa_puedes_reintentar")}</p>
                </div>
              )}

              {mmgbsaState === "done" && (() => {
                if (!mmgbsaResult) return null;
                const r = mmgbsaResult;
                const totalKcal = r.delta_g_total_kcal;

                const components = [
                  { label: t("ev_mmgbsa_van_der_waals"), key: "vdw", value: r.delta_g_vdw, color: "#6366f1", desc: t("auto_898e5bcf715e") },
                  { label: t("ev_mmgbsa_electrostatica"), key: "elec", value: r.delta_g_electrostatic, color: "#f59e0b", desc: t("auto_56307dd72ba4") },
                  { label: t("ev_mmgbsa_solvatacion_gb"), key: "gb", value: r.delta_g_gb_polar, color: "#3b82f6", desc: t("auto_0ef026dc501a") },
                  { label: t("ev_mmgbsa_solvatacion_sasa"), key: "sasa", value: r.delta_g_nonpolar_sasa, color: "#14b8a6", desc: t("auto_f1b31204597b") },
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
                      <p className="mb-1 text-sm font-black uppercase tracking-widest text-emerald-300">{t("ev_mmgbsa_estimacion")}</p>
                      <p className="font-sans text-4xl font-black text-emerald-300">
                        {totalKcal.toFixed(2)} <span className="text-xl font-bold">kcal/mol</span>
                      </p>
                      <p className="mx-auto mt-3 max-w-md text-base leading-6 text-zinc-300 font-sans">
                        {t("ev_mmgbsa_post_hoc")}
                      </p>
                      <p className="text-base text-zinc-300 mt-2 font-sans leading-6">
                        {t("ev_mmgbsa_pose_numero", { rank: r.pose_rank ?? mmgbsaPoseRank })} {t("auto_b27be63607e8")} {r.minimized ? "✓" : "—"} · {r.platform ?? t("ev_mmgbsa_motor_predeterminado")} · {r.execution_time_s != null ? `${r.execution_time_s.toFixed(1)}s` : "—"}
                      </p>
                    </div>

                    {/* La condición de validez la manda el backend junto al
                        número (`services/chemistry/mmgbsa_contrato.py`) y va
                        aquí, debajo de la cifra grande, no al final del panel.
                        Un ΔG de MM-GBSA cuyo ligando está tipado con átomos de
                        proteína no significa lo que el lector supone que
                        significa, y esa frase es la mitad del dato. */}
                    {r.condicion_de_validez && (
                      <p className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3.5 text-base leading-6 text-amber-800 dark:text-amber-100 font-sans">
                        <strong className="font-semibold">{t("ev_mmgbsa_como_usarlo")}</strong>{" "}
                        {r.condicion_de_validez}
                      </p>
                    )}

                    {/* Decomposition */}
                    <div>
                      <p className="text-sm font-black uppercase tracking-widest text-zinc-400 mb-3">{t("ev_mmgbsa_descomposicion")}</p>
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
                                    <span className="text-sm font-bold text-white/80">{comp.label}</span>
                                    <span className="ml-2 text-sm text-zinc-400 font-mono">{comp.desc}</span>
                                  </div>
                                  <span className={`text-sm font-black font-mono ${isFavorable ? "text-emerald-400" : "text-red-400"}`}>
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
                                <p className="text-base mt-1 font-sans leading-6" style={{ color: isFavorable ? "#6ee7b7" : "#fca5a5" }}>
                                  {isFavorable ? t("auto_2d325f1fbc1d") : t("auto_6dbd2d03ab5b")}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="rounded-xl p-4 border border-white/5 bg-white/[0.02] text-base text-slate-400 leading-6 font-sans">
                          {t("ev_mmgbsa_sin_descomposicion")}
                        </div>
                      )}
                    </div>

                    {/* ΔG Bind */}
                    <div className="flex items-center justify-between p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                      <span className="text-sm font-bold font-mono text-white/70">{t("auto_da25b074a86c")}</span>
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
