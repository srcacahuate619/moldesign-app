import type { Target } from "./api";
import { catalogoEnMemoria } from "./catalogoDeReceptores";

export type VerificacionReceptor = {
  receta_receptor: number;
  receptor_sha256: string;
  protocolo: { exhaustiveness: number; num_poses: number; semilla: number };
  condiciones: string[];
  pose: { semillas: number; semillas_rmsd_ok: number; rmsd_top1_A?: number[]; posebusters_valida?: boolean; protocolo_h?: string };
  calibracion: { metrica?: string; rho: number; ic95: [number, number]; n: number; endpoint: string; panel: string; fallos?: number; artefacto?: string };
  fecha?: string;
};

/** Un resultado publicado informa; nunca concede por sí mismo el sello. */
export type IntentoVerificacion = VerificacionReceptor & {
  pdb_id: string;
  experimento: string;
  fecha: string;
  decision: "GO" | "NO_GO" | "INCONCLUSIVE";
  conclusion: string;
  pose: VerificacionReceptor["pose"] & { gate: "GO" | "NO_GO" };
  /** `rho_peor`: ρ en la peor asignación binaria de lote (sólo los intentos con ensayo de lotes mezclados). */
  calibracion: VerificacionReceptor["calibracion"] & { gate: "GO" | "NO_GO" | "INCONCLUSIVE"; rho_peor?: number; ic95_rho_peor?: number[] };
};

export function intentosDelReceptor(target?: Pick<Target, "pdb_id" | "is_private" | "is_community" | "intentos_verificacion"> | null): readonly IntentoVerificacion[] {
  if (!target || target.is_private || target.is_community) return [];
  return (target.intentos_verificacion ?? []).filter((intento) =>
    intento.pdb_id.toUpperCase() === target.pdb_id.toUpperCase() && (intento.decision === "GO" || intento.decision === "NO_GO" || intento.decision === "INCONCLUSIVE"));
}

export type SeccionCatalogo = "verificado" | "propios" | "demostracion";
export const AVISO_UNIDAD_BIOLOGICA = "SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA";
type Receptor = Pick<Target, "is_private" | "is_community" | "seccion_catalogo" | "verificacion">;

/** Espejo de la receta vigente; su prueba lo contrasta con preparer.py. */
export const RECETA_RECEPTOR_DEL_SELLO = 7;

function esObjeto(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** El backend decide la sección; un contrato incompleto nunca conserva el sello. */
export function superaElProtocolo(entrada: unknown): entrada is VerificacionReceptor {
  if (!esObjeto(entrada) || entrada.receta_receptor !== RECETA_RECEPTOR_DEL_SELLO) return false;
  const { protocolo, condiciones, pose, calibracion: cal } = entrada;
  if (!esObjeto(protocolo) || !["exhaustiveness", "num_poses", "semilla"].every((key) => Number.isInteger(protocolo[key]))) return false;
  if (!Array.isArray(condiciones) || !condiciones.every((codigo) => typeof codigo === "string" && codigo.length > 0)) return false;
  if (typeof entrada.receptor_sha256 !== "string" || !entrada.receptor_sha256) return false;
  if (!esObjeto(pose) || !esObjeto(cal)) return false;
  // SCI-D-002: el protocolo fija cinco semillas exactas, no un mínimo de cinco.
  if (pose.semillas !== 5
    || typeof pose.semillas_rmsd_ok !== "number" || !Number.isInteger(pose.semillas_rmsd_ok)
    || pose.semillas_rmsd_ok < 3 || pose.semillas_rmsd_ok > pose.semillas || pose.posebusters_valida !== true) return false;
  const ic = cal.ic95;
  const enDominio = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= -1 && v <= 1;
  // Una ρ y su IC viven en [−1, 1], y una ρ ≤ 0 contradice un IC que la da por positiva.
  return enDominio(cal.rho) && cal.rho > 0
    && Array.isArray(ic) && ic.length === 2 && ic.every(enDominio)
    && ic[0] > 0 && ic[0] <= ic[1]
    && typeof cal.n === "number" && Number.isInteger(cal.n) && cal.n > 0
    && typeof cal.endpoint === "string" && cal.endpoint.length > 0
    && typeof cal.panel === "string" && cal.panel.length > 0;
}

/** Un contrato antiguo o incompleto nunca promociona un receptor. */
export function seccionDelReceptor(target?: Receptor | null): SeccionCatalogo {
  if (target?.is_private || target?.is_community) return "propios";
  if (target?.seccion_catalogo === "verificado" && superaElProtocolo(target.verificacion)) return "verificado";
  return "demostracion";
}

/** Resuelve también identificadores locales. Ausencia de dato = demostración. */
export function receptorPorPdbId(pdbId: string | null | undefined, catalogo: readonly Target[] | null = catalogoEnMemoria()): Target | undefined {
  const id = pdbId?.toUpperCase();
  if (!id) return undefined;
  return catalogo?.find((target) => target.pdb_id.toUpperCase() === id || target.id?.toUpperCase() === id);
}

export function seccionPorPdbId(pdbId: string | null | undefined, catalogo: readonly Target[] | null = catalogoEnMemoria()): SeccionCatalogo {
  return seccionDelReceptor(receptorPorPdbId(pdbId, catalogo));
}

export type ParametrosDeCorrida = {
  receptor_sha256?: unknown;
  docking_protocol?: { exhaustiveness?: unknown; num_poses?: unknown; seed?: unknown; execution_provenance?: Record<string, unknown> | null } | null;
  vina_random_seed?: unknown;
};

export type CampoDelSello = "receptor" | "exhaustiveness" | "num_poses" | "seed";

/** Una tarjeta sin corrida no compara; una corrida vacía no declara nada. */
export function comparacionConElSello(corrida: ParametrosDeCorrida | null | undefined, verificacion: VerificacionReceptor): { difiere: CampoDelSello[]; sinDeclarar: CampoDelSello[] } {
  const difiere: CampoDelSello[] = [];
  const sinDeclarar: CampoDelSello[] = [];
  if (corrida == null) return { difiere, sinDeclarar };
  const protocolo = verificacion.protocolo;
  const campos: Array<[CampoDelSello, unknown[], unknown]> = [
    ["receptor", [corrida.receptor_sha256, corrida.docking_protocol?.execution_provenance?.receptor_sha256], verificacion.receptor_sha256],
    ["exhaustiveness", [corrida.docking_protocol?.exhaustiveness], protocolo.exhaustiveness],
    ["num_poses", [corrida.docking_protocol?.num_poses], protocolo.num_poses],
    ["seed", [corrida.docking_protocol?.seed, corrida.vina_random_seed], protocolo.semilla],
  ];
  for (const [campo, valores, medido] of campos) {
    const declarados = valores.filter(valor => valor != null);
    if (declarados.some(valor => valor !== medido)) difiere.push(campo);
    else if (!declarados.length) sinDeclarar.push(campo);
  }
  return { difiere, sinDeclarar };
}

export function claveDeCondicion(codigo: string): string {
  switch (codigo) {
    case "RECEPTOR_SIN_IONES": return "cat_cond_sin_iones";
    case "SERIE_CONGENERICA": return "cat_cond_serie";
    case "CONDICIONES_DEL_ENSAYO_NO_DOCUMENTADAS": return "cat_cond_ensayo";
    case "ENSAYO_DTBZ_PLAQUETAS": return "cat_cond_ensayo_vmat2";
    case "KD_POR_LOTE_NO_ADJUDICADO": return "cat_cond_lote";
    default: return "cat_condicion_desconocida";
  }
}

export const SECCIONES_CATALOGO = ["verificado", "propios", "demostracion"] as const;

export function agruparSecciones(targets: readonly Target[]): Array<{ seccion: SeccionCatalogo; targets: Target[] }> {
  return SECCIONES_CATALOGO.map((seccion) => ({ seccion, targets: targets.filter((target) => seccionDelReceptor(target) === seccion) }));
}
