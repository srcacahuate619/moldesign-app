import { getApiUrl } from "./config";
import { getAuthHeaders } from "./api";

/**
 * Convierte una respuesta de error en un mensaje legible.
 *
 * FastAPI contesta `{"detail": "..."}`. Esto devolvía el cuerpo CRUDO, así que
 * el usuario leía literalmente `{"detail":"MM-GBSA no puede parametrizar esta
 * molécula: contiene Cl. …"}` — llaves, comillas y nombre de campo incluidos—
 * dentro de un panel que decía «El cálculo falló». La explicación estaba ahí y
 * el formato la escondía.
 */
async function assertOk(res: Response) {
  if (res.ok) return;
  const cuerpo = await res.text().catch(() => "");
  let mensaje = cuerpo;
  try {
    const json = JSON.parse(cuerpo);
    const detalle = json?.detail;
    if (typeof detalle === "string" && detalle.trim()) {
      mensaje = detalle.trim();
    } else if (Array.isArray(detalle)) {
      // 422 de validación: lista de `{loc, msg}`.
      const partes = detalle
        .map((item: { loc?: unknown; msg?: unknown }) =>
          typeof item?.msg === "string" ? item.msg : null,
        )
        .filter((parte: string | null): parte is string => Boolean(parte));
      if (partes.length) mensaje = partes.join(" · ");
    }
  } catch {
    // No era JSON: se queda el texto tal cual, que ya es mejor que nada.
  }
  throw new Error(mensaje || `HTTP ${res.status} ${res.statusText}`);
}

/** Métodos que se pueden repetir sin que el servidor haga el trabajo dos veces. */
const IDEMPOTENTES = new Set(["GET", "HEAD", "OPTIONS"]);

/** ¿Contesta el backend ahora mismo? Decide si un reintento es seguro. */
async function backendVivo(): Promise<boolean> {
  try {
    const res = await globalThis.fetch(`${await getApiUrl()}/health`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Reintentos, pero sabiendo QUÉ se está reintentando.
 *
 * ─── EL FALLO QUE ARREGLA ────────────────────────────────────────────────
 *
 * Esto reintentaba CUALQUIER petición 60 veces con un segundo de espera. Dos
 * consecuencias, y la segunda es la grave:
 *
 *   1. Todo error de red tardaba un minuto largo en aparecer, y aparecía como
 *      «Failed to fetch» —el texto crudo del navegador—, que no dice nada. El
 *      usuario informó de un MM-GBSA que «calcula tres minutos y falla»: el
 *      cálculo nunca llegó a correr; lo que veía era esta espera.
 *
 *   2. `POST /pro/mmgbsa` y `POST /pro/selectivity` LANZAN TRABAJO CARO en el
 *      servidor. Si la conexión se corta después de que el backend haya
 *      recibido la petición, el navegador da el mismo error que si nunca
 *      hubiera salido, y este bucle mandaba otras 59: hasta sesenta
 *      minimizaciones de OpenMM en paralelo en el equipo del usuario.
 *
 * ─── LA REGLA ────────────────────────────────────────────────────────────
 *
 * El motivo original de reintentar es real y sigue vigente: durante el
 * arranque el backend todavía no escucha. Pero esa situación se distingue de
 * las demás preguntando: se sondea `/health`.
 *
 *   - si `/health` NO contesta → el backend no está levantado, la petición no
 *     llegó a nadie y repetirla es seguro, sea cual sea el método;
 *   - si `/health` SÍ contesta → el backend está vivo y fue esta petición la
 *     que falló. Repetir un GET no cuesta nada; repetir un POST puede duplicar
 *     el trabajo, así que se falla y se dice por qué.
 */
async function customFetch(url: string, init?: RequestInit): Promise<Response> {
  const metodo = (init?.method ?? "GET").toUpperCase();
  const idempotente = IDEMPOTENTES.has(metodo);
  const maxIntentos = 30;
  const esperaMs = 1000;

  for (let intento = 1; ; intento++) {
    try {
      // Producción protege las rutas /pro y /ai por sesión. En desarrollo
      // algunas configuraciones permisivas ocultaban que este cliente era el
      // único de la app que no adjuntaba el token. Se combinan los headers sin
      // pisar Content-Type ni un Authorization explícito del llamador.
      const headers = new Headers(init?.headers);
      for (const [name, value] of Object.entries(getAuthHeaders())) {
        if (!headers.has(name)) headers.set(name, value);
      }
      return await globalThis.fetch(url, { ...init, headers });
    } catch (err) {
      const agotado = intento >= maxIntentos;
      const arrancando = !(await backendVivo());

      if (!agotado && (arrancando || idempotente)) {
        console.warn(
          `proApi: ${metodo} ${url} falló (intento ${intento}/${maxIntentos}); ` +
            `${arrancando ? "el backend no responde todavía" : "reintento seguro"}.`,
        );
        await new Promise((resolve) => setTimeout(resolve, esperaMs));
        continue;
      }

      // Se traduce el error. «Failed to fetch» es lo que dice el navegador
      // cuando la conexión se corta, y es exactamente lo que el usuario no
      // necesita leer: no distingue «no arrancó» de «se cayó a mitad».
      const causa = err instanceof Error ? err.message : String(err);
      throw new Error(
        arrancando
          ? `El motor de cálculo no responde (${metodo} ${new URL(url).pathname}). ` +
            `Comprueba que la aplicación terminó de arrancar y vuelve a intentarlo.`
          : `La conexión con el motor se interrumpió durante ${metodo} ` +
            `${new URL(url).pathname}. El motor sigue en pie, así que es esta ` +
            `operación la que falló; revisa el registro del motor para ver por qué. ` +
            `(${causa})`,
      );
    }
  }
}

// ── PRO: Selectividad ──────────────────────────────────────────

export async function getAntiTargets(): Promise<
  Array<{ pdb_id: string; name: string; category: string; risk: string; threshold_kcal: number }>
> {
  const res = await customFetch(`${await getApiUrl()}/pro/anti-targets`);
  await assertOk(res);
  const data = await res.json();
  return data.anti_targets || [];
}

export async function runSelectivity(
  moleculeId: string,
  antiTargets?: string[],
  numWorkers: number = 2,
): Promise<{
  selectivity_ratio: number | null;
  selectivity_verdict: string | null;
  on_target: { pdb_id: string; affinity_kcal: number } | null;
  off_targets: Array<{ pdb_id: string; affinity: number; threshold: number; risk: string; safe: boolean }> | null;
  safety_flags: string[];
  execution_time_s: number | null;
}> {
  const params = new URLSearchParams();
  params.set("num_workers", String(numWorkers));
  if (antiTargets && antiTargets.length > 0) {
    params.set("anti_targets", antiTargets.join(","));
  }
  const res = await customFetch(`${await getApiUrl()}/pro/selectivity/${moleculeId}?${params}`, { method: "POST" });
  await assertOk(res);
  return res.json();
}

export async function runSelectivityStream(
  moleculeId: string,
  onEvent: (event: { type: string; anti_target?: any; selectivity_ratio?: number; selectivity_verdict?: string; off_targets?: any[]; safety_flags?: string[]; execution_time_s?: number; total?: number; completed?: number }) => void,
  antiTargets?: string[],
  numWorkers: number = 2,
): Promise<void> {
  const params = new URLSearchParams();
  params.set("num_workers", String(numWorkers));
  if (antiTargets && antiTargets.length > 0) {
    params.set("anti_targets", antiTargets.join(","));
  }

  const url = `${await getApiUrl()}/pro/selectivity/stream/${moleculeId}?${params}`;
  const response = await customFetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("data: ")) {
        try {
          const json = JSON.parse(trimmed.replace(/^data:\s*/, ""));
          onEvent(json);
        } catch {
          // ignore json parse error
        }
      }
    }
  }
}

export async function dockSingleAntiTarget(
  moleculeId: string,
  targetPdbId: string,
): Promise<{
  target: {
    pdb_id: string;
    name: string;
    category: string;
    risk: string;
    affinity: number | null;
    poses: number;
    threshold: number;
    status: string;
    error?: string;
  };
}> {
  const res = await customFetch(
    `${await getApiUrl()}/pro/selectivity/dock-target/${moleculeId}?target_pdb_id=${encodeURIComponent(targetPdbId)}`,
    { method: "POST" },
  );
  await assertOk(res);
  return res.json();
}

export async function saveSelectivityResults(
  moleculeId: string,
  data: {
    off_targets: any[];
    selectivity_ratio?: number | null;
    selectivity_verdict?: string | null;
    safety_flags?: string[];
  },
): Promise<{ success: boolean }> {
  const res = await customFetch(`${await getApiUrl()}/pro/selectivity/save/${moleculeId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await assertOk(res);
  return res.json();
}

// ── PRO: MM-GBSA bajo demanda ─────────────────────────────────

export async function runMmgbsa(
  moleculeId: string,
  poseRank: number = 1,
  numSteps: number = 1000,
): Promise<{
  molecule_id?: string;
  pose_rank?: number;
  delta_g_total_kcal: number;
  // FIX MM-GBSA (2026-08-04): el endpoint /pro/mmgbsa ahora devuelve ΔG real
  // (g_complex - g_protein - g_ligand) pero SIN descomposición por contribución
  // (null) — no está disponible. El modal debe render null-safe.
  delta_g_vdw: number | null;
  delta_g_electrostatic: number | null;
  delta_g_gb_polar: number | null;
  delta_g_nonpolar_sasa: number | null;
  delta_g_bind?: number | null;
  components?: Record<string, number | null>;
  minimized?: boolean;
  platform?: string;
  execution_time_s?: number;
  warnings?: string[];
  /**
   * Bajo qué condición significa algo el ΔG de arriba. Lo emite
   * `services/chemistry/mmgbsa_contrato.py` y viaja pegado al número —a la
   * pantalla y al dossier— porque sin él la cifra se lee como una energía
   * libre calculada con un campo de fuerzas de ligando, y no lo es.
   */
  condicion_de_validez?: string;
  note?: string;
}> {
  const res = await customFetch(
    `${await getApiUrl()}/pro/mmgbsa/${moleculeId}?pose_rank=${poseRank}&num_steps=${numSteps}`,
    { method: "POST" },
  );
  await assertOk(res);
  return res.json();
}

/**
 * Perfil ADMET de una molécula YA evaluada.
 *
 * Existe porque ADMET-AI es opt-in en las opciones avanzadas y esa decisión se
 * toma antes de ejecutar: quien no lo marcó se quedaba sin perfil salvo que
 * volviera a acoplar la molécula entera —minutos de Vina— para recalcular algo
 * que sólo depende del SMILES.
 *
 * El backend lo PERSISTE, así que el dossier lo verá. Pero el resultado que la
 * pantalla tiene en memoria viene de una instantánea del trabajo, no de la base:
 * hay que fusionarlo en el estado local, igual que se hace con MM-GBSA.
 */
export async function runAdmet(
  moleculeId: string,
  opciones: { readonly recalcular?: boolean } = {},
): Promise<{
  molecule_id: string;
  /** `calculado` la primera vez; `ya_calculado` si lo devolvió de la base. */
  estado: "calculado" | "ya_calculado";
  /** `false` si se calculó pero no se pudo guardar. El dossier no lo vería. */
  persistido: boolean;
  blood_viability_score: number | null;
  blood_solubility_logs: number | null;
  blood_ppb_category: string | null;
  blood_bbb_permeable: boolean | null;
  blood_bbb_motivo: string | null;
  blood_cns_mpo: number | null;
  blood_hia_permeable: boolean | null;
  blood_systemic_reactivity: string[];
  blood_tabpfn_estado: string | null;
}> {
  const query = opciones.recalcular ? "?recalcular=true" : "";
  const res = await customFetch(
    `${await getApiUrl()}/pro/admet/${moleculeId}${query}`,
    { method: "POST" },
  );
  await assertOk(res);
  return res.json();
}

// ── GPU Status ─────────────────────────────────────────────────

export async function getGpuStatus(): Promise<{
  openmm_gpu: boolean;
  torch_cuda: boolean;
  platforms: string[];
}> {
  const res = await customFetch(`${await getApiUrl()}/pro/gpu`);
  await assertOk(res);
  return res.json();
}

// ── Health Check ───────────────────────────────────────────────

export async function getHealth(): Promise<{
  status: string;
  app_mode: string;
  environment: string;
  components: Record<string, any>;
}> {
  const res = await customFetch(`${await getApiUrl()}/health`);
  await assertOk(res);
  return res.json();
}

// ── Leaderboard ────────────────────────────────────────────────

export async function getLeaderboard(): Promise<
  Array<{
    molecule_id: string;
    smiles: string;
    total_score: number;
    affinity_kcal: number;
    target_name: string;
    user_name: string;
    created_at: string;
  }>
> {
  const res = await customFetch(`${await getApiUrl()}/stats/leaderboard`);
  await assertOk(res);
  return res.json();
}

// ── Community Targets ──────────────────────────────────────────

export async function getCommunityTargets(): Promise<
  Array<{ pdb_id: string; name: string; description: string; organism: string; creator_username: string; resolution: number | null }>
> {
  const res = await customFetch(`${await getApiUrl()}/targets/community`);
  await assertOk(res);
  return res.json();
}

export async function downloadCommunityTarget(pdbId: string): Promise<{ success: boolean; message: string }> {
  const res = await customFetch(`${await getApiUrl()}/targets/community/download/${pdbId}`, { method: "POST" });
  await assertOk(res);
  return res.json();
}

// ── Target Ingest ──────────────────────────────────────────────

export async function ingestTarget(
  pdbId: string,
  chainId: string = "A",
  structuralFamily?: string,
): Promise<{ success: boolean; pdb_id: string; message: string }> {
  const res = await customFetch(`${await getApiUrl()}/targets/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdb_id: pdbId, chain_id: chainId, structural_family: structuralFamily }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── AI Model Management ────────────────────────────────────────

export async function searchAIModels(query: string): Promise<Array<{ id: string; name: string; description: string; size_gb: number }>> {
  const res = await customFetch(`${await getApiUrl()}/ai/models/search?q=${encodeURIComponent(query)}`);
  await assertOk(res);
  return res.json();
}

export async function getLocalAIModels(): Promise<Array<{ filename: string; size_gb: number; path: string }>> {
  const res = await customFetch(`${await getApiUrl()}/ai/models/local`);
  await assertOk(res);
  return res.json();
}

export async function downloadAIModel(modelId: string): Promise<{ dl_id: string; status: string }> {
  const res = await customFetch(`${await getApiUrl()}/ai/models/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_id: modelId }),
  });
  await assertOk(res);
  return res.json();
}

export async function getDownloadStatus(dlId: string): Promise<{ status: string; progress: number }> {
  const res = await customFetch(`${await getApiUrl()}/ai/models/download/${dlId}`);
  await assertOk(res);
  return res.json();
}

export async function recommendQuantization(): Promise<Array<{ name: string; description: string; size_gb: number; min_ram_gb: number }>> {
  const res = await customFetch(`${await getApiUrl()}/ai/models/recommend-quant`);
  await assertOk(res);
  return res.json();
}

// ── Chem: Properties standalone ────────────────────────────────

export async function calculateProperties(smiles: string): Promise<{
  properties: {
    molecular_weight: number;
    log_p: number;
    tpsa: number;
    hbd: number;
    hba: number;
    rotatable_bonds: number;
    heavy_atom_count: number;
    ring_count: number;
    qed: number;
    sa_score: number;
    lipinski_pass: boolean;
    veber_pass: boolean;
    ghose_pass: boolean;
    egan_pass: boolean;
    muegge_pass: boolean;
    muegge_score: number;
    fsp3: number;
    is_pains: boolean;
    pains_matches: Array<{ name: string; description: string }>;
  };
  adme_summary: string;
  smiles_hash: string;
}> {
  const res = await customFetch(`${await getApiUrl()}/chem/properties`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ smiles }),
  });
  await assertOk(res);
  return res.json();
}

// ── Chem: Conformer 3D standalone ──────────────────────────────

export async function generateConformer(smiles: string, forceRegenerate: boolean = false): Promise<{
  canonical_smiles: string;
  smiles_hash: string;
  conformer_path: string;
  num_atoms_3d: number;
  optimization_converged: boolean;
  had_macrocycle: boolean;
  molecular_formula: string;
  sdf_content: string;
}> {
  const res = await customFetch(`${await getApiUrl()}/chem/conformer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ smiles, force_regenerate: forceRegenerate }),
  });
  await assertOk(res);
  return res.json();
}

// ── Chem: Render 2D ────────────────────────────────────────────

export async function getMolRender(moleculeId: string): Promise<string> {
  const res = await customFetch(`${await getApiUrl()}/chem/render/${moleculeId}`);
  await assertOk(res);
  return res.text();
}

// ── SAR: Structure-Activity Relationship ───────────────────────

export async function getSarData(moleculeId: string): Promise<{
  analogs: Array<{
    smiles: string;
    similarity: number;
    total_score: number | null;
    affinity_kcal: number | null;
    ml_prob: number | null;
  }>;
}> {
  const res = await customFetch(`${await getApiUrl()}/sar/${moleculeId}`);
  await assertOk(res);
  return res.json();
}

// ── Blockchain: verify ─────────────────────────────────────────

export async function verifyBlockchainSignature(signature: string): Promise<{
  valid: boolean;
  molecule_id: string | null;
  timestamp: string | null;
  data_hash: string | null;
}> {
  const res = await customFetch(`${await getApiUrl()}/blockchain/verify/${signature}`);
  await assertOk(res);
  return res.json();
}

// ── DiffDock ───────────────────────────────────────────────────

export interface DiffDockPose {
  rank: number;
  confidence: number;
  affinity_predicted: number | null;
  ligand_pdb: string;
  rmsd_from_input: number | null;
}

export interface DiffDockResponse {
  success: boolean;
  poses: DiffDockPose[];
  best_confidence: number | null;
  execution_time_s: number | null;
  warnings: string[];
  error: string | null;
}

export async function runDiffDock(
  proteinPdbId: string,
  ligandSmiles: string,
  numPoses: number = 5,
): Promise<DiffDockResponse> {
  const res = await customFetch(`${await getApiUrl()}/docking/diffdock/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      protein_pdb_id: proteinPdbId,
      ligand_smiles: ligandSmiles,
      num_poses: numPoses,
    }),
  });
  await assertOk(res);
  return res.json();
}

export async function getDiffDockHealth(): Promise<{ status: string; message: string }> {
  const res = await customFetch(`${await getApiUrl()}/docking/diffdock/health`);
  await assertOk(res);
  return res.json();
}

// ── ColabFold ──────────────────────────────────────────────────

export interface ColabFoldPose {
  rank: number;
  iptm: number;
  ptm: number;
  plddt: number;
  complex_pdb: string;
}

export interface ColabFoldResponse {
  success: boolean;
  poses: ColabFoldPose[];
  best_plddt: number | null;
  best_iptm: number | null;
  execution_time_s: number | null;
  warnings: string[];
  error: string | null;
}

export async function runColabFold(
  proteinPdbId: string,
  peptideSmiles: string,
): Promise<ColabFoldResponse> {
  const res = await customFetch(`${await getApiUrl()}/docking/colabfold/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      protein_pdb_id: proteinPdbId,
      peptide_smiles: peptideSmiles,
    }),
  });
  await assertOk(res);
  return res.json();
}

export async function getColabFoldHealth(): Promise<{ status: string; message: string }> {
  const res = await customFetch(`${await getApiUrl()}/docking/colabfold/health`);
  await assertOk(res);
  return res.json();
}

// ── Protein Surgery ────────────────────────────────────────────

export interface MetalFeaturesResponse {
  sulfonamide_count: number;
  carboxylate_count: number;
  thiol_count: number;
  hydroxamic_acid_count: number;
  imidazole_count: number;
  phosphate_count: number;
  zn_binding_groups_total: number;
  has_metal_binding_potential: boolean;
}

export async function getMetalFeatures(smiles: string): Promise<MetalFeaturesResponse> {
  const res = await customFetch(`${await getApiUrl()}/proteins/surgery/metal-features`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ smiles }),
  });
  await assertOk(res);
  return res.json();
}

export interface DetectedMetal {
  element: string;
  position_x: number;
  position_y: number;
  position_z: number;
}

export interface DetectMetalsResponse {
  metals: DetectedMetal[];
  count: number;
}

export async function detectMetals(pdbContent: string): Promise<DetectMetalsResponse> {
  const res = await customFetch(`${await getApiUrl()}/proteins/surgery/detect-metals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdb_content: pdbContent }),
  });
  await assertOk(res);
  return res.json();
}

export interface DynamicBoxResponse {
  center_x: number;
  center_y: number;
  center_z: number;
  size: number;
  ligand_span_x: number;
  ligand_span_y: number;
  ligand_span_z: number;
}

export async function getDynamicBox(ligandPdbContent: string): Promise<DynamicBoxResponse> {
  const res = await customFetch(`${await getApiUrl()}/proteins/surgery/dynamic-box`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ligand_pdb_content: ligandPdbContent }),
  });
  await assertOk(res);
  return res.json();
}

export interface ValidateVinaAtomsResponse {
  all_supported: boolean;
  unsupported_elements: string[];
}

export async function validateVinaAtoms(smiles: string): Promise<ValidateVinaAtomsResponse> {
  const res = await customFetch(`${await getApiUrl()}/proteins/surgery/validate-atoms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ smiles }),
  });
  await assertOk(res);
  return res.json();
}

export interface PrepareTargetResponse {
  success: boolean;
  vina_receptor_pdb: string | null;
  vina_center_x: number;
  vina_center_y: number;
  vina_center_z: number;
  vina_size: number;
  metal_count: number;
  chain_count: Record<string, number>;
  warnings: string[];
}

export async function prepareTarget(
  proteinPdbContent: string,
  ligandSmiles?: string,
): Promise<PrepareTargetResponse> {
  const res = await customFetch(`${await getApiUrl()}/proteins/surgery/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      protein_pdb_content: proteinPdbContent,
      ligand_smiles: ligandSmiles,
    }),
  });
  await assertOk(res);
  return res.json();
}
