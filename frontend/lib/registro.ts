/**
 * Registro cientifico — tipos y carga.
 *
 * Los datos los genera `scripts/build_registro_cientifico.py` a partir de los
 * manifests sellados en `scripts/artifacts_science/`. El manifest es la fuente de
 * verdad de los hechos; el paper escrito a mano solo aporta la prosa.
 *
 * Se sirven como JSON estatico desde `public/registro/` para que funcionen igual en
 * la build web (SSR) y en la de escritorio (`output: "export"` dentro de Tauri).
 */

export type Categoria =
  | "hallazgo"
  | "refutacion"
  | "medicion"
  | "prerregistro"
  | "corrigendum"
  | "inconcluso";

export type Decision = "GO" | "NO_GO" | "INCONCLUSIVE" | null;

export interface Experimento {
  id: string;
  categoria: Categoria;
  etiquetas: string[];
  decision: Decision;
  hipotesis: string | null;
  protocolo: string | null;
  gate: string;
  razonamiento: string | null;
  sellado_en: string | null;
  creado_en: string | null;
  duracion_s: number | null;
  semillas: number | string | null;
  git: { rama: string | null; commit: string; sucio: boolean | null };
  entorno: {
    os: string | null;
    cpu: number | null;
    ram_mb: number | null;
    gpu: string | null;
  };
  n_hashes: number;
  n_complejos: number;
  n_fallos: number;
  metricas: Record<string, string | number | boolean | null> | null;
  mantenimiento_sello: number;
  /** ID del experimento que reemplazo las cifras selladas de este registro, si lo hay. */
  reemplazado_por: string | null;
  tiene_paper: boolean;
  titulo: string;
  entradilla: string | null;
}

export interface IndiceRegistro {
  generado_en: string;
  generador: string;
  advertencia: string;
  categorias: Record<string, string>;
  conteo: Record<Categoria, number>;
  total: number;
  con_paper: number;
  destacados: Partial<Record<Categoria, string[]>>;
  experimentos: Experimento[];
}

/** Fragmento de texto con marca inline. */
export interface Frag {
  t: string;
  m: null | "fuerte" | "enfasis" | "codigo" | "enlace";
  href?: string;
}

export type Bloque =
  | { tipo: "encabezado"; nivel: number; frag: Frag[] }
  | { tipo: "parrafo"; frag: Frag[] }
  | { tipo: "cita"; frag: Frag[] }
  | { tipo: "lista"; ordenada: boolean; items: Frag[][] }
  | {
      tipo: "tabla";
      cabecera: Frag[][];
      alineacion: ("izquierda" | "centro" | "derecha")[];
      filas: Frag[][][];
    }
  | { tipo: "codigo"; lang: string | null; texto: string };

export interface Paper {
  id: string;
  meta: Record<string, string>;
  bloques: Bloque[];
  fuente: string;
}

/** Etiqueta legible y color por categoria. */
export const ESTILO_CATEGORIA: Record<
  Categoria,
  { nombre: string; corto: string; color: string; fondo: string }
> = {
  hallazgo: {
    nombre: "Hallazgo",
    corto: "Gate superado",
    color: "var(--categoria-hallazgo)",
    fondo: "rgba(52, 211, 153, 0.10)",
  },
  refutacion: {
    nombre: "Refutación",
    corto: "Hipótesis derribada",
    color: "var(--categoria-refutacion)",
    fondo: "rgba(248, 113, 113, 0.10)",
  },
  medicion: {
    nombre: "Medición",
    corto: "Mide, no decide",
    color: "var(--categoria-medicion)",
    fondo: "rgba(96, 165, 250, 0.10)",
  },
  prerregistro: {
    nombre: "Prerregistro",
    corto: "Declaración previa",
    color: "var(--categoria-prerregistro)",
    fondo: "rgba(167, 139, 250, 0.10)",
  },
  corrigendum: {
    nombre: "Corrigendum",
    corto: "Corrección propia",
    color: "var(--categoria-corrigendum)",
    fondo: "rgba(251, 191, 36, 0.10)",
  },
  inconcluso: {
    nombre: "Inconcluso",
    corto: "Sin conclusión",
    color: "var(--categoria-inconcluso)",
    fondo: "rgba(148, 163, 184, 0.10)",
  },
};

/**
 * Un color de categoría con transparencia. Los colores son variables CSS
 * (cambian con el tema), así que no admiten un alfa hexadecimal pegado detrás
 * como hacía `${color}44`: eso daba una declaración inválida y el borde
 * desaparecía.
 */
export function conAlfa(color: string, porcentaje: number): string {
  return `color-mix(in srgb, ${color} ${porcentaje}%, transparent)`;
}

export const ORDEN_CATEGORIAS: Categoria[] = [
  "hallazgo",
  "refutacion",
  "medicion",
  "prerregistro",
  "corrigendum",
  "inconcluso",
];

export async function cargarIndice(): Promise<IndiceRegistro> {
  const r = await fetch("/registro/index.json", { cache: "no-store" });
  if (!r.ok) throw new Error(`No se pudo cargar el registro (${r.status})`);
  return r.json();
}

export async function cargarPaper(id: string): Promise<Paper | null> {
  const r = await fetch(`/registro/papers/${id}.json`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

/** Duracion legible: 7326 -> "2 h 2 min". */
export function duracionLegible(s: number | null): string | null {
  if (s == null || s <= 0) return null;
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function fechaLegible(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("es", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
