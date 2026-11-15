// =====================================================================
// Comparador 3D de poses entre corridas: fuentes, poses de cada una y distancia
// =====================================================================
//
// Cada lado del comparador es una pose (rango) de una corrida (task_id) de una molécula. Dos lados pueden ser de la
// misma corrida, de dos corridas de la misma molécula o de dos ligandos distintos del mismo caso; la distancia que
// se enseña depende de eso y se mide en el backend:
//
//   misma corrida     → RMSD entre las dos poses del SDF.
//   misma molécula    → RMSD entre la pose de una corrida y la de otra (sólo con el mismo receptor preparado).
//   ligandos distintos → RMSD del núcleo común (se abstiene si es pequeño o si el receptor no es el mismo).
//
// Nada se inventa aquí: si el backend se abstiene, la medida llega con `disponible: false` y su motivo.

import { getInteractions } from "./api";
import type { CaseRun } from "./cases/types";
import {
  getAnalogPoseComparison,
  getPoseMatches,
  getRunPoseComparison,
  getSameRunPoseComparison,
} from "./proApi";
import { deriveStructuralEvidence, type PhysicalStatus } from "./structuralEvidence";
import type { InteractionsReport } from "./types";

export interface FuenteDeCorrida {
  readonly taskId: string;
  readonly moleculeId: string;
  /** Lo que el usuario lee en el selector: fecha, ligando, protocolo. */
  readonly etiqueta: string;
}

export interface LadoDePose {
  readonly fuente: FuenteDeCorrida;
  readonly rank: number;
}

export interface PoseDeLaLista {
  readonly rank: number;
  readonly affinity: number | null;
  readonly physicalStatus: PhysicalStatus | null;
  /** Sólo `passed` explícito: `review` y `not_evaluated` nunca son válidas. */
  readonly physicallyValid: boolean;
}

/**
 * Las otras corridas terminadas del caso, la más reciente primero, sin la actual. Con `soloMoleculaId` quedan sólo las
 * de esa molécula (la comparación de «Poses y controles» no sale de la molécula que se está viendo; entre ligandos
 * distintos se compara en SAR).
 */
export function fuentesDelCaso(
  caseRuns: readonly CaseRun[] | undefined,
  actualTaskId: string | null | undefined,
  etiquetar: (run: CaseRun) => string,
  soloMoleculaId?: string | null,
): FuenteDeCorrida[] {
  if (!caseRuns) return [];
  return caseRuns
    .filter(
      (run) =>
        run.executionState === "completed" &&
        run.moleculeId &&
        run.taskId !== actualTaskId &&
        (!soloMoleculaId || run.moleculeId === soloMoleculaId),
    )
    .slice()
    .reverse()
    .map((run) => ({ taskId: run.taskId, moleculeId: run.moleculeId as string, etiqueta: etiquetar(run) }));
}

/**
 * Las poses de una corrida a partir de su resultado y del SDF. El SDF manda en cuántas hay (cada rango tiene que
 * poder extraerse); el resultado pone la energía y los controles físicos cuando los conserva.
 */
export function posesDeLaCorrida(sdf: string, resultado: unknown | null): PoseDeLaLista[] {
  const enElSdf = sdf.split(/\$\$\$\$\s*/).filter((registro) => registro.includes("M  END")).length;
  const filas = new Map<number, PoseDeLaLista>();
  if (resultado) {
    const evidencia = deriveStructuralEvidence(resultado as Parameters<typeof deriveStructuralEvidence>[0]);
    for (const fila of evidencia.comparison) {
      filas.set(fila.rank, {
        rank: fila.rank,
        affinity: fila.affinity,
        physicalStatus: fila.physicalStatus,
        physicallyValid: fila.physicallyValid,
      });
    }
  }
  return Array.from({ length: enElSdf }, (_, i) => i + 1).map(
    (rank) => filas.get(rank) ?? { rank, affinity: null, physicalStatus: null, physicallyValid: false },
  );
}

export type TipoDeMedida = "misma_corrida" | "misma_molecula" | "nucleo_comun";

export interface MedidaDeDistancia {
  readonly tipo: TipoDeMedida;
  readonly disponible: boolean;
  readonly rmsd: number | null;
  /** Código del backend cuando no hay distancia (CORE_TOO_SMALL, DIFFERENT_RECEPTOR…). */
  readonly motivo: string | null;
  readonly nucleo: { readonly atomos: number | null; readonly fraccion: number | null } | null;
  readonly vinaIzquierda: number | null;
  readonly vinaDerecha: number | null;
  /** Derecha − izquierda. */
  readonly diferenciaVina: number | null;
  /** Restar afinidades sólo es honesto con el mismo protocolo. */
  readonly diferenciaComparable: boolean;
  readonly marco: "same" | "different" | "undeclared" | null;
  readonly diferencias: ReadonlyArray<{ field: string; a: unknown; b: unknown }>;
  /**
   * Qué átomos de cada pose son del núcleo común (índice del registro SDF, desde 0, con hidrógenos). Sólo cuando se
   * midió el núcleo de dos ligandos distintos en el mismo receptor; si no, el visor dibuja las moléculas como siempre.
   */
  readonly atomosDelNucleo: { readonly izquierda: readonly number[]; readonly derecha: readonly number[] } | null;
}

const finito = (valor: unknown): number | null =>
  typeof valor === "number" && Number.isFinite(valor) ? valor : null;

export async function medirDistancia(izquierda: LadoDePose, derecha: LadoDePose): Promise<MedidaDeDistancia> {
  const mismaCorrida = izquierda.fuente.taskId === derecha.fuente.taskId;
  if (mismaCorrida) {
    const r = await getSameRunPoseComparison(izquierda.fuente.taskId, izquierda.rank, derecha.rank);
    const rmsd = r.difference.pose_rmsd_between_poses;
    return {
      tipo: "misma_corrida",
      disponible: Boolean(rmsd?.available),
      rmsd: rmsd?.available ? finito(rmsd.rmsd_angstrom) : null,
      motivo: rmsd?.available ? null : rmsd?.reason_code ?? "RMSD_NOT_COMPUTABLE",
      nucleo: null,
      vinaIzquierda: finito(r.left.vina_affinity_kcal_mol),
      vinaDerecha: finito(r.right.vina_affinity_kcal_mol),
      diferenciaVina: finito(r.difference.right_minus_left_vina_kcal_mol),
      diferenciaComparable: true,
      marco: null,
      diferencias: [],
      atomosDelNucleo: null,
    };
  }
  if (izquierda.fuente.moleculeId === derecha.fuente.moleculeId) {
    const r = await getRunPoseComparison(izquierda.fuente.taskId, derecha.fuente.taskId, izquierda.rank, derecha.rank);
    const rmsd = r.difference.pose_rmsd_between_runs;
    return {
      tipo: "misma_molecula",
      disponible: Boolean(rmsd.available),
      rmsd: rmsd.available ? finito(rmsd.rmsd_angstrom) : null,
      motivo: rmsd.available ? null : rmsd.reason_code,
      nucleo: null,
      vinaIzquierda: finito(r.a.vina_affinity_kcal_mol),
      vinaDerecha: finito(r.b.vina_affinity_kcal_mol),
      diferenciaVina: finito(r.difference.b_minus_a_vina_kcal_mol),
      diferenciaComparable: r.protocol_differences.length === 0,
      marco: r.frame,
      diferencias: r.protocol_differences,
      atomosDelNucleo: null,
    };
  }
  const r = await getAnalogPoseComparison(izquierda.fuente.taskId, derecha.fuente.taskId, izquierda.rank, derecha.rank);
  const nucleo = r.difference.core_rmsd;
  return {
    tipo: "nucleo_comun",
    disponible: Boolean(nucleo.available),
    rmsd: nucleo.available ? finito(nucleo.rmsd_angstrom) : null,
    motivo: nucleo.available ? null : nucleo.reason_code,
    nucleo: { atomos: finito(nucleo.core_heavy_atoms), fraccion: finito(nucleo.core_fraction_of_smaller) },
    vinaIzquierda: finito(r.a.vina_affinity_kcal_mol),
    vinaDerecha: finito(r.b.vina_affinity_kcal_mol),
    diferenciaVina: finito(r.difference.b_minus_a_vina_kcal_mol),
    diferenciaComparable: r.difference.affinity_delta_comparable,
    marco: r.frame,
    diferencias: r.protocol_differences,
    atomosDelNucleo: nucleo.available && nucleo.core_atoms
      ? { izquierda: nucleo.core_atoms.a, derecha: nucleo.core_atoms.b }
      : null,
  };
}

type Traductor = (key: string, params?: Record<string, string | number>) => string;

/** «fecha · ligando · exhaustividad» de una corrida del libro del caso, para el selector. */
export function etiquetaDeCorrida(run: CaseRun, t: Traductor, locale: string): string {
  const instante = run.finishedAt ?? run.startedAt;
  const fecha = instante ? new Date(instante) : null;
  const ligando = run.ligandSmiles ? (run.ligandSmiles.length > 28 ? `${run.ligandSmiles.slice(0, 27)}…` : run.ligandSmiles) : "—";
  return t("pn_cmp3d_opcion", {
    fecha: fecha && !Number.isNaN(fecha.getTime()) ? fecha.toLocaleString(locale, { dateStyle: "short", timeStyle: "short" }) : "—",
    ligando,
    e: run.protocol?.exhaustiveness ?? "—",
  });
}

// ── Qué poses de la otra evaluación se parecen a la elegida ──────────────────────────────────────────────────────

export interface CoincidenciaDePose {
  readonly rank: number;
  /** Distancia a la pose elegida del otro lado; `null` si no se pudo medir esa pose. */
  readonly rmsd: number | null;
}

export interface CoincidenciasDelLado {
  /** `core`: ligandos distintos, la distancia es la de su núcleo común. */
  readonly tipo: "molecule" | "core";
  readonly poses: readonly CoincidenciaDePose[];
  readonly masCercana: number | null;
}

/**
 * Las distancias de la pose elegida en un lado contra cada pose del otro. Sólo tiene sentido entre dos evaluaciones
 * distintas y con el mismo receptor preparado: si el backend se abstiene (o falla) no hay coincidencias y quien llama
 * no enseña nada, en vez de adivinar.
 */
export async function coincidenciasDePoses(elegida: LadoDePose, otroLado: FuenteDeCorrida): Promise<CoincidenciasDelLado | null> {
  if (elegida.fuente.taskId === otroLado.taskId) return null;
  const r = await getPoseMatches(elegida.fuente.taskId, otroLado.taskId, elegida.rank);
  if (!r.available) return null;
  return {
    tipo: r.kind,
    poses: r.matches.map((m) => ({ rank: m.rank, rmsd: m.available ? finito(m.rmsd_angstrom) : null })),
    masCercana: r.closest_rank,
  };
}

// ── Contactos que una pose gana o pierde frente a la otra ────────────────────────────────────────────────────────

export interface Punto3D { readonly x: number; readonly y: number; readonly z: number }

export interface ContactoDeUnaPose {
  readonly distancia: number;
  readonly angulo: number | null;
  readonly atomoLigando: string | null;
  readonly atomoReceptor: string | null;
  readonly ligando: Punto3D;
  readonly receptor: Punto3D;
}

export type EstadoDeContacto = "solo_izquierda" | "solo_derecha" | "ambas";

export interface ContactoComparado {
  readonly clave: string;
  /** `hbond`, `hydrophobic`, `pi_stacking`, `salt_bridge`, `cation_pi`, `halogen`… tal como los da el análisis. */
  readonly tipo: string;
  /** «SER123A»: nombre, número y cadena del residuo. */
  readonly residuo: string;
  readonly numero: number;
  readonly estado: EstadoDeContacto;
  readonly izquierda: ContactoDeUnaPose | null;
  readonly derecha: ContactoDeUnaPose | null;
}

export type ComparacionDeContactos =
  | {
      readonly disponible: true;
      readonly contactos: readonly ContactoComparado[];
      readonly motor: string;
      /** Qué cuenta el análisis: sólo el primer contacto de cada tipo por residuo. */
      readonly cobertura: string | null;
      /** Con qué hidrógenos se calculó (geométricos de RDKit: no implican un pH). */
      readonly hidrogenos: string | null;
    }
  | { readonly disponible: false; readonly motivo: "LECTURA_FALLIDA" | "MOTORES_DISTINTOS" | "RECEPTORES_DISTINTOS" };

function contactosDeUnLado(informe: InteractionsReport): Map<string, ContactoComparado & { lado: ContactoDeUnaPose }> {
  const filas = new Map<string, ContactoComparado & { lado: ContactoDeUnaPose }>();
  for (const dato of informe.interactions ?? []) {
    const cadena = (dato.residue_chain ?? "").trim();
    const numero = dato.residue_number ?? 0;
    const nombre = dato.residue_name ?? dato.residue;
    const clave = `${dato.type}|${cadena}|${numero}|${nombre}`;
    const lado: ContactoDeUnaPose = {
      distancia: dato.distance,
      angulo: dato.angle ?? null,
      atomoLigando: dato.ligand_atom ?? null,
      atomoReceptor: dato.protein_atom ?? null,
      ligando: dato.ligand_coords,
      receptor: dato.protein_coords,
    };
    const previo = filas.get(clave);
    // El análisis ya declara una cobertura de un contacto por tipo y residuo; si llegara otro, manda el más cercano.
    if (previo && previo.lado.distancia <= lado.distancia) continue;
    filas.set(clave, {
      clave, tipo: dato.type, residuo: dato.residue, numero, estado: "solo_izquierda", izquierda: null, derecha: null, lado,
    });
  }
  return filas;
}

/**
 * Los contactos de la pose de cada lado (el análisis de interacciones que ya existe, el mismo de Evaluación), puestos
 * uno frente al otro por tipo y residuo: cuáles sólo tiene la izquierda, cuáles sólo la derecha y cuáles las dos.
 *
 * Sólo vale si los dos análisis se hicieron sobre el MISMO receptor preparado (el hash del receptor que cada análisis
 * usó, no una suposición) y con el mismo motor: con otro, un residuo «sin contacto» podría ser sólo otra química.
 * Se compara por residuo y tipo, no por átomo, porque entre ligandos distintos los átomos no se corresponden.
 */
export async function compararContactos(izquierda: LadoDePose, derecha: LadoDePose): Promise<ComparacionDeContactos> {
  const [a, b] = await Promise.all([
    getInteractions(izquierda.fuente.moleculeId, izquierda.rank, izquierda.fuente.taskId),
    getInteractions(derecha.fuente.moleculeId, derecha.rank, derecha.fuente.taskId),
  ]);
  if (!a || !b) return { disponible: false, motivo: "LECTURA_FALLIDA" };
  if (a.protein_source_sha256 !== b.protein_source_sha256) return { disponible: false, motivo: "RECEPTORES_DISTINTOS" };
  if (a.engine !== b.engine) return { disponible: false, motivo: "MOTORES_DISTINTOS" };

  const deA = contactosDeUnLado(a);
  const deB = contactosDeUnLado(b);
  const contactos: ContactoComparado[] = [];
  for (const [clave, fila] of deA) {
    const otra = deB.get(clave);
    contactos.push({
      clave, tipo: fila.tipo, residuo: fila.residuo, numero: fila.numero,
      estado: otra ? "ambas" : "solo_izquierda", izquierda: fila.lado, derecha: otra?.lado ?? null,
    });
  }
  for (const [clave, fila] of deB) {
    if (deA.has(clave)) continue;
    contactos.push({
      clave, tipo: fila.tipo, residuo: fila.residuo, numero: fila.numero, estado: "solo_derecha", izquierda: null, derecha: fila.lado,
    });
  }
  contactos.sort((x, y) => x.numero - y.numero || x.tipo.localeCompare(y.tipo));
  return {
    disponible: true, contactos, motor: a.engine, cobertura: a.contact_coverage ?? null, hidrogenos: a.hydrogen_model ?? null,
  };
}

/** Los segmentos ligando–receptor de una comparación de contactos, coloreados por lo que cada uno significa. */
export function lineasDeContactos(
  contactos: readonly ContactoComparado[],
  lado: "izquierda" | "derecha" | "ambos",
  colores: { readonly izquierda: string; readonly derecha: string; readonly compartido: string },
): Array<{ start: Punto3D; end: Punto3D; color: string }> {
  const lineas: Array<{ start: Punto3D; end: Punto3D; color: string }> = [];
  for (const c of contactos) {
    // Entre las dos poses, uno compartido se dibuja una vez, con la geometría del lado que se está viendo.
    const propio = lado === "derecha" ? c.derecha : c.izquierda ?? c.derecha;
    if (!propio) continue;
    if (lado === "izquierda" && c.estado === "solo_derecha") continue;
    if (lado === "derecha" && c.estado === "solo_izquierda") continue;
    const color = c.estado === "ambas" ? colores.compartido : c.estado === "solo_izquierda" ? colores.izquierda : colores.derecha;
    lineas.push({ start: propio.ligando, end: propio.receptor, color });
  }
  return lineas;
}

// ── Texto de la comparación, para pegarlo en un informe o un mensaje ─────────────────────────────────────────────

/** Por qué no hay distancia, en palabras; `null` si la hay. */
export function textoSinDistancia(medida: MedidaDeDistancia, t: Traductor): string | null {
  if (medida.disponible) return null;
  const pct = medida.nucleo?.fraccion != null ? Math.round(medida.nucleo.fraccion * 100) : "—";
  return medida.marco === "different" ? t("pn_cmp_sin_rmsd_distinto")
    : medida.marco === "undeclared" ? t("pn_cmp_sin_rmsd_no_declarado")
    : medida.motivo === "CORE_TOO_SMALL" ? t("pn_ana_sin_nucleo", { core: medida.nucleo?.atomos ?? "—", pct })
    : medida.motivo === "POSES_NOT_AVAILABLE" ? t("pn_ana_sin_poses")
    : t("pn_cmp_sin_rmsd_otro", { codigo: medida.motivo ?? "?" });
}

export interface LadoParaElResumen {
  readonly etiqueta: string;
  readonly taskId: string;
  readonly rank: number;
  readonly vina: number | null;
}

/**
 * El resumen de lo que se está viendo, en texto plano y con sus límites: qué evaluaciones y poses, la distancia (o por
 * qué no hay), lo que difiere entre las corridas y, si se calcularon, los contactos. Se escribe con las mismas frases
 * que la pantalla; no añade ninguna conclusión que la pantalla no tenga.
 */
export function resumenDeLaComparacion(entrada: {
  t: Traductor;
  izquierda: LadoParaElResumen;
  derecha: LadoParaElResumen;
  medida: MedidaDeDistancia | null;
  contactos: ComparacionDeContactos | null;
}): string {
  const { t, izquierda, derecha, medida, contactos } = entrada;
  const kcal = (valor: number | null) => (valor === null ? "—" : valor.toFixed(2));
  const lado = (nombre: string, l: LadoParaElResumen) =>
    `${nombre}: ${l.etiqueta} · ${t("ev_mmgbsa_pose_numero", { rank: l.rank })} · ${kcal(l.vina)} kcal/mol (${l.taskId})`;
  const lineas = [t("pn_cmp3d_res_titulo"), "", lado(t("pn_cmp3d_izquierda"), izquierda), lado(t("pn_cmp3d_derecha"), derecha)];

  if (medida) {
    lineas.push("");
    const etiqueta = t(medida.tipo === "nucleo_comun" ? "pn_ana_nucleo" : "pn_cmp3d_rmsd");
    lineas.push(medida.disponible && medida.rmsd !== null ? `${etiqueta}: ${medida.rmsd.toFixed(2)} Å` : (textoSinDistancia(medida, t) ?? etiqueta));
    if (medida.tipo === "nucleo_comun") lineas.push(t("pn_cmp3d_otro_ligando"));
    lineas.push(t("pn_cmp3d_res_vina", { izquierda: kcal(medida.vinaIzquierda), derecha: kcal(medida.vinaDerecha) }));
    if (!medida.diferenciaComparable) lineas.push(t("pn_ana_delta_no_comparable"));
    if (medida.tipo === "misma_corrida" || medida.marco === "same") lineas.push(t("pn_cmp3d_res_receptor_mismo"));
    if (medida.diferencias.length > 0) {
      lineas.push(t("pn_cmp3d_res_diferencias"));
      for (const d of medida.diferencias) {
        const valor = (v: unknown) => (d.field === "receptor_sha256" ? `${String(v ?? "").slice(0, 8)}…` : String(v ?? t("pn_cmp_no_declarado")));
        lineas.push(`  ${t(`pn_cmp_f_${d.field}`)}: ${valor(d.a)} → ${valor(d.b)}`);
      }
    }
  }

  if (contactos?.disponible) {
    const nombre = (c: ContactoComparado) => `${c.residuo} (${t(`cm_type_${c.tipo}`)})`;
    const grupo = (estado: EstadoDeContacto, clave: string) => {
      const filas = contactos.contactos.filter((c) => c.estado === estado);
      lineas.push(t(clave, { n: filas.length }), `  ${filas.length ? filas.map(nombre).join(", ") : t("pn_cmp3d_contactos_ninguno")}`);
    };
    lineas.push("", t("pn_cmp3d_contactos_titulo"));
    grupo("solo_izquierda", "pn_cmp3d_contactos_solo_izq");
    grupo("solo_derecha", "pn_cmp3d_contactos_solo_der");
    grupo("ambas", "pn_cmp3d_contactos_ambas");
    lineas.push(t("pn_cmp3d_contactos_nota", { motor: contactos.motor }));
  }

  lineas.push("", t("pn_cmp3d_res_aviso"));
  return lineas.join("\n");
}
