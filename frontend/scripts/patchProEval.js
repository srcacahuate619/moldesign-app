const fs = require('fs');

const path = 'd:/molecular-design/frontend/components/interfaces/pro/ProEvaluation.tsx';
let code = fs.readFileSync(path, 'utf8');

// 1. Add imports
code = code.replace(
  'import TargetSelectorModal from "./TargetSelectorModal";',
  'import TargetSelectorModal from "./TargetSelectorModal";\nimport { StageCard, StageInfo, StageStatus } from "./StageCard";\nimport { subscribeToPipelineEvents, PipelineEvent } from "../../../lib/pipelineStream";'
);

// 2. Update ProEvaluationProps
const propRegex = /peptideDockingEngine\?:\s*"diffpepdock"\s*\|\s*"colabfold"\s*\)\s*=>\s*Promise<void>;/;
code = code.replace(
  propRegex,
  'peptideDockingEngine?: "diffpepdock" | "colabfold",\n    pipelineConfig?: any\n  ) => Promise<void>;'
);

// 3. Add Pipeline State inside ProEvaluation component
const stateInjection = `
  // --- PIPELINE STAGES STATE ---
  const [pipelineEvents, setPipelineEvents] = useState<PipelineEvent[]>([]);
  const [pipelineActive, setPipelineActive] = useState(false);
  const [stagesConfig, setStagesConfig] = useState<StageInfo[]>([
    {
      id: "validate", label: "Validación 2D", description: "Curación SMILES con RDKit.",
      required: true, enabled: true, cost_estimate: "Bajo", params: {}
    },
    {
      id: "admet", label: "Filtros ADMET", description: "Modelos Predictivos ADMET-AI.",
      required: false, enabled: true, cost_estimate: "Medio", params: {}
    },
    {
      id: "conformer", label: "Conformómeros 3D", description: "ETKDG v3 + Minimización local MMFF94.",
      required: true, enabled: true, cost_estimate: "Medio", params: { num_conformers: 10 }
    },
    {
      id: "docking", label: "Acoplamiento Mol.", description: "AutoDock Vina sobre Grid Box automático.",
      required: true, enabled: true, cost_estimate: "Medio", params: { exhaustiveness: 32 }
    },
    {
      id: "rescoring", label: "Rescoring GNN", description: "XGBoost + RTMScore sobre poses de docking.",
      required: false, enabled: true, cost_estimate: "Alto", params: {}
    },
    {
      id: "openmm_refinement", label: "Dinámica Molecular (MD)", description: "Refinamiento OpenMM (Amber14SB + GAFF2).",
      required: false, enabled: true, cost_estimate: "Muy Alto", params: { max_iterations: 5000 }
    }
  ]);

  // Subscribe to SSE when taskId is present
  useEffect(() => {
    if (!taskId) return;
    setPipelineEvents([]);
    setPipelineActive(true);
    const unsubscribe = subscribeToPipelineEvents(taskId, (ev) => {
      setPipelineEvents(prev => [...prev, ev]);
      if (ev.type === "pipeline_done" || ev.type === "pipeline_error") {
        setPipelineActive(false);
      }
    }, () => {
      setPipelineActive(false);
    });
    return () => unsubscribe();
  }, [taskId]);

  const handleToggleStage = (id: string) => {
    setStagesConfig(prev => prev.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s));
  };

  const handleParamChange = (id: string, param: string, value: any) => {
    setStagesConfig(prev => prev.map(s => {
      if (s.id === id) {
        return { ...s, params: { ...s.params, [param]: value } };
      }
      return s;
    }));
  };

  const getStageStatus = (stageId: string): StageStatus => {
    const eventsForStage = pipelineEvents.filter(e => e.stage_id === stageId);
    if (eventsForStage.some(e => e.type === "stage_error")) return "error";
    if (eventsForStage.some(e => e.type === "stage_done")) return "done";
    if (eventsForStage.some(e => e.type === "stage_start")) return "running";
    return "idle";
  };
`;
// 3. Add Pipeline State inside ProEvaluation component
const stateInjectionRegex = /const \[showPeptideModal, setShowPeptideModal\] = useState\(false\);/;
code = code.replace(
  stateInjectionRegex,
  'const [showPeptideModal, setShowPeptideModal] = useState(false);\n' + stateInjection
);

// 4. Update executeSubmission to pass pipelineConfig
const executeSubmissionRegex = /const customHotspotsList = Object\.keys\(selectedHotspots\)\.filter\(k => selectedHotspots\[k\]\);\s*await handleSubmit\(centerOverride, sizeOverride, customHotspotsList, engine\);/;

const executeSubmissionNew = `    const customHotspotsList = Object.keys(selectedHotspots).filter(k => selectedHotspots[k]);

    const enabled_stages = stagesConfig.filter(s => s.enabled).map(s => s.id);
    const stage_params: Record<string, any> = {};
    stagesConfig.forEach(s => {
      if (s.enabled && Object.keys(s.params).length > 0) {
        stage_params[s.id] = s.params;
      }
    });

    const pipelineConfig = {
      enabled_stages,
      stage_params,
      stage_order: ["validate", "admet", "conformer", "docking", "rescoring", "openmm_refinement"]
    };

    await handleSubmit(centerOverride, sizeOverride, customHotspotsList, engine, pipelineConfig);`;

code = code.replace(executeSubmissionRegex, executeSubmissionNew);


// 5. Add the rack modules after the grid configuration, right before the target selector modal
const rackModules = `
            {/* RACK MODULES (PIPELINE CONFIG) */}
            <div className="space-y-4 pt-4 border-t border-zinc-800">
              <h3 className="text-xs font-black uppercase tracking-widest text-[#8c7a99] flex items-center gap-2">
                <Layers size={12} className="text-[#8c7a99]" />
                SYS.02 // RACK DE ORQUESTACIÓN
              </h3>
              <div className="space-y-2">
                {stagesConfig.map(stage => (
                  <StageCard
                    key={stage.id}
                    stage={stage}
                    status={getStageStatus(stage.id)}
                    durationMs={pipelineEvents.find(e => e.stage_id === stage.id && e.type === "stage_done")?.duration_ms}
                    error={pipelineEvents.find(e => e.stage_id === stage.id && e.type === "stage_error")?.error}
                    onToggle={() => handleToggleStage(stage.id)}
                    onParamChange={(param, val) => handleParamChange(stage.id, param, val)}
                    disabled={pipelineActive || busy}
                  />
                ))}
              </div>
            </div>
`;

code = code.replace(
  '<TargetSelectorModal',
  rackModules + '\n            <TargetSelectorModal'
);

// 6. Replace old header with the new hardware rack layout
code = code.replace(
  '1. Configuración de Caja (Grid Box)',
  'SYS.01 // SELECTOR DE OBJETIVO'
);


const resultsViewStart = '{/* Celery Pipeline monitor */}';

const waterfallUI = `
          {/* WATERFALL FALLBACK UI */}
          {isTerminal && pipelineEvents.length > 0 && (
            <div className="bg-black border border-zinc-800 p-4 mb-4">
              <h3 className="text-xs font-black uppercase tracking-widest text-[#8c7a99] mb-4">PIPELINE TRACE (CASCADA)</h3>
              <div className="flex flex-col gap-2 relative">
                <div className="absolute left-[9px] top-2 bottom-2 w-px bg-zinc-800" />
                {pipelineEvents.map((ev, i) => (
                  <div key={i} className="flex items-center gap-4 z-10 relative">
                    <div className={\`w-5 h-5 rounded-full flex items-center justify-center border \${ev.type === 'stage_done' || ev.type === 'pipeline_done' ? 'bg-emerald-950 border-emerald-500 text-emerald-500' : ev.type === 'stage_error' || ev.type === 'pipeline_error' ? 'bg-rose-950 border-rose-500 text-rose-500' : 'bg-zinc-900 border-zinc-600 text-zinc-400'}\`}>
                      {ev.type.includes('error') ? <AlertCircle size={10} /> : ev.type.includes('done') ? <CheckCircle2 size={10} /> : <Circle size={10} />}
                    </div>
                    <div className="flex-1">
                      <div className="text-[10px] font-mono text-zinc-300 uppercase">{ev.label || ev.type}</div>
                      {ev.error && <div className="text-[9px] font-mono text-rose-400 mt-1">{ev.error}</div>}
                    </div>
                    {ev.duration_ms && <div className="text-[9px] font-mono text-zinc-500">{(ev.duration_ms / 1000).toFixed(2)}s</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
`;

code = code.replace(resultsViewStart, waterfallUI + resultsViewStart);

// One more fix: we need to import AlertCircle, CheckCircle2, Circle
code = code.replace(
  /import\s*\{\s*Activity,/m,
  'import {\n  Activity,\n  AlertCircle,\n  CheckCircle2,\n  Circle,'
);

fs.writeFileSync(path, code);
console.log("Patched ProEvaluation.tsx");
