import { FrontendError, frontendMessage } from "./frontendError";
import { getApiUrl } from "./config";
import { fetchBackend } from "./backendFetch";
import { invoke } from "./tauri";
import { getAuthHeaders, mensajeDelError, requestAuthenticatedJson } from "./api";
import { beginFileDownload, handoffFileDownload, failFileDownload } from "./activityNotifications";

/** Las escenas que Molcy sabe contar. Una desconocida invalida el listado entero (`validarMolcy`). */
export const ESCENAS_MOLCY = ["resultado", "receptor", "busqueda", "ensamble"] as const;
export type MolcyEscena = (typeof ESCENAS_MOLCY)[number];

export type MolcySource = {
  id: string;
  nombre: string;
  receptor?: string;
  task_id?: string | null;
  caso?: { id: string; nombre: string } | null;
  propio?: boolean;
  disponible: boolean;
  motivo: string | null;
  escenas_disponibles?: MolcyEscena[];
};
export type MolcySources = { moldex: MolcySource[]; receptores: MolcySource[] };
/** Un Blender que la aplicación halló en esta máquina sin ejecutarlo. `apto` es null cuando no se pudo saber la versión. */
export type BlenderEncontrado = {
  ruta: string;
  origen: "programa" | "steam" | "tienda" | "gestor" | "asociacion" | "ruta" | "portatil";
  version: string | null;
  apto: boolean | null;
  tambien?: string[];
};
export type MolcyRenderer = {
  disponible: boolean;
  motivo: string | null;
  motivo_codigo?: "falta_addon" | "addon_no_carga" | "cpu_no_disponible" | "falta_blender" | "blender_antiguo" | "motor_alterado";
  /** El VÍDEO: sólo con GPU (EEVEE) desde el 2026-10-08. */
  gpu_disponible?: boolean;
  gpu_memoria?: "automatica";
  motivo_gpu?: string | null;
  /** Las FOTOS: Cycles en CPU siempre (si el motor sabe tomarlas) y en GPU si Cycles rindió con una. */
  foto_disponible?: boolean;
  motivo_foto?: string | null;
  foto_gpu_disponible?: boolean;
  foto_gpu_tipo?: string | null;
  foto_gpu_nombres?: string[];
  motivo_foto_gpu?: string | null;
  cpu_hilos?: number;
  cpu_logicos?: number;
  cpu_hilos_disponibles?: number;
  cpu_hilos_configurables?: boolean;
  cpu_hilos_maximos?: number;
  cpu_hilos_reserva?: number;
  cpu_uso_actual_pct?: number | null;
  gpu_vram_monitorizable?: boolean;
  gpu_vram_total_mib?: number;
  gpu_vram_libre_mib?: number;
  gpu_vram_reserva_mib?: number;
  gpu_vram_max_mib?: number;
  gpu_vram_recomendado_mib?: number;
  blender?: string;
  motor?: string;
  version_blender?: number[];
  molecular_nodes?: string;
  motor_sha256?: string;
  /** Este arranque trae el motor Molcy dentro del instalador (la pantalla no pide una carpeta). */
  motor_incluido?: boolean;
  motor_origen?: "incluido" | "configurado" | "ninguno";
  motor_commit?: string | null;
  motor_licencia?: string | null;
  /** Los Blender hallados (instalador oficial, Steam, Tienda, gestores, ZIP…), el mejor primero. */
  blenders_encontrados?: BlenderEncontrado[];
  espacio?: Record<string, { libre_bytes: number; necesario_bytes: number; disponible: boolean; motivo?: string }> | null;
  /** Espacio para una foto de cada resolución (720p…4k) en la carpeta de salida. */
  espacio_fotos?: Record<string, { libre_bytes: number; necesario_bytes: number; disponible: boolean; motivo?: string }> | null;
  espacio_task_id?: string | null;
  /** La carpeta de salida que midió ese espacio (`predeterminada`, un id elegido o nada). */
  espacio_salida_id?: string | null;
  espacio_motivo?: string;
};
/** Resoluciones de una foto: de 720p (el piso) a 4K (el techo, para imprimir), en 16:9 o 9:16. */
export const RESOLUCIONES_FOTO = ["720p", "1080p", "1440p", "4k"] as const;
export type MolcyResolucion = (typeof RESOLUCIONES_FOTO)[number];
export type MolcyOrientacion = "vertical" | "horizontal";
/** Un instante de la escena que vale una foto: lo propone el motor (pausas, título, recorridos). */
export type MolcyMomento = {
  id: string; fotograma: number; beat: string | null;
  tipo: "lectura" | "imagen_fija" | "titulo" | "recorrido";
  etiquetas: number; pose: number | null; orden: number; miniatura?: string;
};
export type MolcyFoto = {
  id: string; archivo: string; sha256: string; bytes: number; fotograma: number; momento: string | null;
  tipo: string; beat: string | null; resolucion: MolcyResolucion; ancho: number; alto: number;
  dispositivo: "cpu" | "gpu"; cpu_hilos?: number | null;
  segundos?: { escena?: number; capa?: number; total?: number } | null;
  marca?: { esquina: string; lado_px: number; opacidad: number };
  render?: { tipo_gpu?: string | null; gpus?: string[]; muestras?: number } | null;
  creado_s?: number;
};
export type MolcyOperacionFoto = {
  tipo: "foto" | "vista"; estado: "en_cola" | "completo" | "fallido" | "cancelado"; fotograma: number;
  dispositivo: "cpu" | "gpu"; ancho: number; alto: number; resolucion: MolcyResolucion | null; motivo?: string;
};

export type MolcyAddon = { estado: "inactivo" | "instalando" | "completo" | "fallido"; fase?: "comprobando" | "descargando" | "verificando"; motivo?: string | null; version?: string };
export type MolcyJob = {
  ajustes?: MolcyAjustes;
  id: string;
  estado: "en_cola" | "renderizando" | "completo" | "fallido" | "cancelado";
  motivo?: string;
  video_sha256?: string;
  fuente?: { origen?: "moldex" | "receptor"; id?: string; molecule_id?: string; task_id?: string | null;
    target_id?: string; target_name?: string; pdb_id?: string; chain?: string;
    case_id?: string; case_name?: string } | null;
  receptor?: { pdb_id?: string; nombre?: string; cadena?: string; target_id?: string | null };
  creado_s?: number;
  terminado_s?: number;
  carpeta_ruta?: string;
  video_ruta?: string;
  dispositivo?: "cpu" | "gpu";
  formato?: "biblioteca" | "social_vertical" | "previsualizacion";
  cpu_hilos?: number;
  cpu_limite_pct?: number;
  gpu_memoria?: "automatica" | "presupuesto";
  gpu_presupuesto?: { gpu_vram_presupuesto_mib: number };
  progreso?: { fotogramas: number; total: number };
  restante_render_principal_s?: number;
  /** Sesión de fotos: la escena se prepara una vez y de ella salen las fotos. */
  tipo?: "fotos";
  fase?: "preparando" | "foto" | "vista" | null;
  orientacion?: MolcyOrientacion;
  escena?: MolcyEscena;
  momentos?: MolcyMomento[];
  fotos?: MolcyFoto[];
  vistas?: Record<string, { archivo: string; sha256: string }>;
  operacion?: MolcyOperacionFoto;
  ultima_operacion?: MolcyOperacionFoto;
  escena_fotos?: { fotogramas_fuente: number; beats: Record<string, [number, number]>; formato?: { ancho: number; alto: number } };
  foto_ruta?: string;
};
export type MolcyPresentacion = {
  schema: "moldesign.presentacion/1";
  titulo: string | null;
  color_receptor: string | null;
  color_residuos: string | null;
  colores_lineas: { polar: string | null; apolar: string | null };
  receptor: "automatico" | "visible" | "oculto";
  muestra_anterior: boolean;
  etiquetas: boolean;
  contactos: boolean;
};
export type MolcyAjustes = { presentacion?: MolcyPresentacion; ensamble_fluido?: { variante: "lenta" | "detallada"; conformero?: number } };
export type MolcyRequest = {
  presentacion?: MolcyPresentacion;
  ensamble_fluido?: MolcyAjustes["ensamble_fluido"];
  origen: "moldex" | "receptor";
  id: string;
  task_id?: string | null;
  escena: MolcyEscena;
  formato: "horizontal" | "vertical" | "previsualizacion";
  dispositivo: "cpu" | "gpu";
  cpu_hilos?: number;
  /** Carpeta elegida SÓLO para este vídeo, o «predeterminada» para saltarse la preferencia global. */
  salida_id?: string;
  /** @deprecated Los clientes nuevos dejan que Blender gestione la VRAM. */
  gpu_vram_mib?: number;
};

/** Una sesión de fotos: la misma fuente y escena que un vídeo, con orientación y dispositivo (CPU o GPU, siempre Cycles). */
export type MolcyFotosRequest = Pick<MolcyRequest, "origen" | "id" | "task_id" | "escena" | "salida_id" | "presentacion" | "ensamble_fluido"> & {
  orientacion: MolcyOrientacion; dispositivo: "cpu" | "gpu"; cpu_hilos?: number;
};
export type MolcyFotoRequest = { fotograma: number; resolucion: MolcyResolucion; dispositivo: "cpu" | "gpu"; cpu_hilos?: number };
export type MolcyVistaRequest = Omit<MolcyFotoRequest, "resolucion">;
/** Cuánto tardará una foto, medido con las fotos anteriores de ESTE equipo; sin medidas, `estimado_s` es null. */
export type MolcyFotoEstimate = { estimado_s: number | null; muestras: number };

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const crearFotosMolcy = (req: MolcyFotosRequest) => peticion<MolcyJob>("/molcy/fotos", json(req));
export const tomarFotoMolcy = (id: string, req: MolcyFotoRequest) =>
  peticion<MolcyJob>(`/molcy/trabajos/${encodeURIComponent(id)}/fotos`, json(req));
export const vistaMolcy = (id: string, req: MolcyVistaRequest) =>
  peticion<MolcyJob>(`/molcy/trabajos/${encodeURIComponent(id)}/vista`, json(req));
export const estimacionFotoMolcy = (req: { orientacion: MolcyOrientacion; resolucion: MolcyResolucion; dispositivo: "cpu" | "gpu"; cpu_hilos?: number },
  signal?: AbortSignal) => peticion<MolcyFotoEstimate>("/molcy/fotos/estimacion", { ...json(req), signal });

async function peticion<T>(path: string, init?: RequestInit): Promise<T> {
  const value = await requestAuthenticatedJson<unknown>(path, init).catch(cause => {
    if (cause instanceof FrontendError) throw cause;
    throw new FrontendError(mensajeDelError(cause));
  });
  // La validación se elige por la ruta, sin la consulta (`?recomprobar=true`): con ella una respuesta ilegible pasaría sin validar.
  validarMolcy(path.split("?")[0], value);
  return value as T;
}

export const fuentesMolcy = () => peticion<MolcySources>("/molcy/fuentes");
// `recomprobar` fuerza un sondeo nuevo (botón «Comprobar»); sin él el backend reutiliza el último que salió bien.
export const renderizadorMolcy = (recomprobar = false) =>
  peticion<MolcyRenderer>(`/molcy/renderizador${recomprobar ? "?recomprobar=true" : ""}`);
export const recursosMolcy = (taskId?: string | null, salidaId?: string | null) => {
  const query = [taskId ? `task_id=${encodeURIComponent(taskId)}` : "", salidaId ? `salida_id=${encodeURIComponent(salidaId)}` : ""].filter(Boolean).join("&");
  return peticion<Partial<MolcyRenderer>>(`/molcy/recursos${query ? `?${query}` : ""}`);
};

/** Carpeta de salida opcional de los vídeos («para todos» = `global`). */
export type MolcySalida = {
  /** Sólo la app de escritorio puede autorizar carpetas con el selector nativo. */
  disponible: boolean;
  global: { id: string; ruta: string } | null;
  /** La preferencia existe pero ya no se puede usar (falta el disco…). */
  problema: string | null;
  predeterminada: string;
};
export type MolcyCarpetaElegida = { id: string; display_path: string };
export const salidaMolcy = () => peticion<MolcySalida>("/molcy/salida");
export const fijarSalidaMolcy = (salidaId: string | null) => peticion<MolcySalida>("/molcy/salida", {
  method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ salida_id: salidaId }),
});
/** Abre el selector nativo; `null` si la persona lo cancela. */
export const elegirCarpetaSalidaMolcy = () => invoke<MolcyCarpetaElegida | null>("molcy_pick_output_dir");
export const estadoAddonMolcy = () => peticion<MolcyAddon>("/molcy/addon");
export const instalarAddonMolcy = () => peticion<MolcyAddon>("/molcy/addon", { method: "POST" });
export const estadoMolcy = (id: string) => peticion<MolcyJob>(`/molcy/trabajos/${encodeURIComponent(id)}`);
export const crearMolcy = (req: MolcyRequest) => peticion<MolcyJob>("/molcy/trabajos", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
});

export async function videoMolcy(id: string): Promise<string> {
  const access = await peticion<{ ruta: string }>(`/molcy/trabajos/${encodeURIComponent(id)}/acceso`, { method: "POST" });
  return `${await getApiUrl()}${access.ruta}`;
}

/**
 * Un fotograma del render en curso. `url` es un blob: quien lo recibe lo libera con `URL.revokeObjectURL`. `indice` es
 * su fotograma del GUION (el cursor para pedir el siguiente); `orden`, su posición entre los ya rendidos; `total`, los
 * que se rinden. Con pausas de lectura y fotogramas reutilizados se rinden menos que los del guion, así que `indice` no
 * va sobre `total`: ver `pieDelFotograma`.
 */
export type MolcyFotograma = { url: string; indice: number; orden: number; total: number };

/**
 * Qué dice el pie del fotograma en vivo. Antes ponía `indice` sobre `total` y la pantalla llegó a decir «Fotograma 681
 * de 667»: el número del guion sobre la cuenta de los que se rinden. Sobre el total va `orden`, la misma cuenta que la
 * barra de progreso.
 */
export function pieDelFotograma(f: Pick<MolcyFotograma, "indice" | "orden" | "total">):
  { clave: "cy_live_frame" | "cy_live_frame_sin_total"; valores: Record<string, number> } {
  if (f.total > 0 && f.orden > 0) return { clave: "cy_live_frame", valores: { done: f.orden, total: f.total } };
  return { clave: "cy_live_frame_sin_total", valores: { done: f.orden > 0 ? f.orden : f.indice } };
}

/**
 * El fotograma completo más reciente del render principal (sin los rótulos de pantalla ni el cierre, que se añaden al
 * codificar), o null si todavía no hay uno más nuevo que `despues` o el trabajo ya no está renderizando. Es una vista
 * previa: quien la pide ignora sus fallos.
 */
export async function fotogramaMolcy(id: string, despues?: number, signal?: AbortSignal): Promise<MolcyFotograma | null> {
  const consulta = despues !== undefined && Number.isInteger(despues) && despues >= 0 ? `?despues=${despues}` : "";
  const response = await fetchBackend(`/molcy/trabajos/${encodeURIComponent(id)}/fotograma${consulta}`, {
    headers: { ...getAuthHeaders() }, signal,
  });
  if (response.status === 204 || response.status === 404) return null;
  if (!response.ok) throw new FrontendError(frontendMessage("mo_fotograma_error_http", { status: response.status }));
  const indice = Number(response.headers.get("X-Molcy-Fotograma"));
  const orden = Number(response.headers.get("X-Molcy-Orden"));
  const total = Number(response.headers.get("X-Molcy-Total"));
  const blob = await response.blob();
  if (!Number.isInteger(indice) || indice < 0 || blob.type !== "image/png")
    throw new FrontendError(frontendMessage("mo_fotograma_error_imagen"));
  return { url: URL.createObjectURL(blob), indice, orden: Number.isInteger(orden) && orden > 0 ? orden : 0,
    total: Number.isInteger(total) && total > 0 ? total : 0 };
}

/** Una miniatura (`tomas`, por fotograma), una vista libre (`vistas`) o una foto entregada (`fotos`, por id), como blob local. */
export async function imagenMolcy(id: string, clase: "tomas" | "vistas" | "fotos", clave: string | number,
  signal?: AbortSignal): Promise<{ url: string; nombre: string | null }> {
  const response = await fetchBackend(`/molcy/trabajos/${encodeURIComponent(id)}/${clase}/${encodeURIComponent(String(clave))}`, {
    headers: { ...getAuthHeaders() }, signal,
  });
  if (!response.ok) throw new FrontendError(frontendMessage("mo_frontend_228", { v0: response.status }));
  const blob = await response.blob();
  if (blob.type !== "image/png") throw new FrontendError(frontendMessage("mo_frontend_229"));
  const nombre = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") || "")?.[1] ?? null;
  return { url: URL.createObjectURL(blob), nombre };
}

/** Registra la preparación y la entrega al navegador; no afirma que el archivo se haya guardado. */
async function descargarArchivoMolcy(nombre: string,
  preparar: () => Promise<{ url: string; nombre?: string | null }>, liberarUrl = false): Promise<void> {
  const activityId = beginFileDownload(nombre);
  let url: string | undefined;
  try {
    const archivo = await preparar();
    url = archivo.url;
    nombre = archivo.nombre || nombre;
    const a = document.createElement("a");
    a.href = url;
    a.download = nombre;
    document.body.appendChild(a);
    handoffFileDownload(activityId, nombre, url);
    try { a.click(); } finally { a.remove(); }
  } catch (error) {
    failFileDownload(activityId, nombre);
    throw error;
  } finally {
    if (liberarUrl && url) {
      const liberable = url;
      window.setTimeout(() => URL.revokeObjectURL(liberable), 1000);
    }
  }
}

/** Descarga una foto entregada (con su marca y su procedencia dentro del PNG) con el nombre que le dio MolDesign. */
export async function descargarFotoMolcy(id: string, fotoId: string): Promise<void> {
  await descargarArchivoMolcy(`molcy_${id}_${fotoId}.png`, () => imagenMolcy(id, "fotos", fotoId), true);
}

export async function descargarMolcy(id: string): Promise<void> {
  await descargarArchivoMolcy(`molcy_${id}.mp4`, async () => ({ url: await videoMolcy(id) }));
}

export type MolcyInstallation = {
  estado: "inactivo" | "instalando" | "completo" | "fallido" | "cancelado";
  fase?: string;
  motivo?: string | null;
  ruta: string | null;
  version: string;
  descarga_bytes: number;
  reserva_bytes: number;
  recibidos_bytes?: number;
  instalado: boolean;
  configuracion: { modo?: "administrado" | "existente"; blender?: string | null; motor?: string | null };
};
/** Lo que pesa Molecular Nodes, medido una vez con Blender 5.2 y Molecular Nodes 520.2.0 (ver `cy_addon_reason`). */
export const MOLECULAR_NODES_MB_MEDIDOS = 133;
/** El aviso de la campana del paquete Blender + Molecular Nodes: la sugerencia y el resultado son la misma entrada. */
export const ID_AVISO_PAQUETE_MOLCY = "molcy:paquete";
/** Razones que se arreglan descargando (Blender o Molecular Nodes). Las demás no: un motor alterado o una CPU que no renderiza. */
export const FALTA_PARA_EL_PAQUETE: ReadonlySet<string> = new Set(["falta_blender", "blender_antiguo", "falta_addon"]);
/** MB del paquete entero: el ZIP oficial de Blender más Molecular Nodes. */
export const megasDelPaquete = (instalacion: Pick<MolcyInstallation, "descarga_bytes">) =>
  Math.ceil(instalacion.descarga_bytes / 1e6) + MOLECULAR_NODES_MB_MEDIDOS;
export const instalacionMolcy = () => peticion<MolcyInstallation>("/molcy/blender");
export const instalarBlenderMolcy = () => peticion<MolcyInstallation>("/molcy/blender", { method: "POST" });
export const cancelarBlenderMolcy = () => peticion<MolcyInstallation>("/molcy/blender/cancelar", { method: "POST" });
export const configurarMolcy = (config: MolcyInstallation["configuracion"]) => peticion<MolcyInstallation>("/molcy/configuracion", {
  method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config),
});
export const trabajosMolcy = () => peticion<{ trabajos: MolcyJob[] }>("/molcy/trabajos");
export const cancelarMolcy = (id: string) => peticion<MolcyJob>(`/molcy/trabajos/${encodeURIComponent(id)}/cancelar`, { method: "POST" });
export const eliminarMolcy = (id: string) => peticion<{ eliminado: boolean }>(`/molcy/trabajos/${encodeURIComponent(id)}`, { method: "DELETE" });
export const revelarMolcy = (id: string) => peticion<{ ruta: string; tipo: "video" | "foto" | "carpeta" }>(
  `/molcy/trabajos/${encodeURIComponent(id)}/revelar`, { method: "POST" });
export async function descargarProcedenciaMolcy(id: string): Promise<void> {
  await descargarArchivoMolcy(`molcy_${id}_procedencia.json`, async () => {
    const value = await peticion<Record<string, unknown>>(`/molcy/trabajos/${encodeURIComponent(id)}/procedencia`);
    return { url: URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" })) };
  }, true);
}

function objeto(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function trabajo(value: unknown): boolean {
  if (!(objeto(value) && typeof value.id === "string" &&
    ["en_cola", "renderizando", "completo", "fallido", "cancelado"].includes(String(value.estado)))) return false;
  if (value.tipo === undefined) return true;
  // Una sesión de fotos dibuja tomas y fotos: si sus listas no son legibles, no se dibuja nada.
  return value.tipo === "fotos" &&
    (value.momentos === undefined || (Array.isArray(value.momentos) && value.momentos.every(m =>
      objeto(m) && Number.isInteger(m.fotograma) && Number(m.fotograma) >= 1 && typeof m.tipo === "string"))) &&
    (value.fotos === undefined || (Array.isArray(value.fotos) && value.fotos.every(f =>
      objeto(f) && typeof f.id === "string" && /^[0-9]{2,4}$/.test(f.id) && Number.isInteger(f.ancho) && Number.isInteger(f.alto))));
}
/** Rechaza contratos ilegibles antes de habilitar acciones o dibujar evidencia. */
export function validarMolcy(path: string, value: unknown): void {
  let ok = objeto(value);
  if (ok) {
    const data = value as Record<string, unknown>;
    if (path.endsWith("/fuentes")) {
      ok = [data.moldex, data.receptores].every(list => Array.isArray(list) && list.every(item =>
        objeto(item) && typeof item.id === "string" && typeof item.nombre === "string" && typeof item.disponible === "boolean" &&
        (item.caso == null || (objeto(item.caso) && typeof item.caso.id === "string" && typeof item.caso.nombre === "string")) &&
        (item.escenas_disponibles === undefined || (Array.isArray(item.escenas_disponibles) && item.escenas_disponibles.every(scene => (ESCENAS_MOLCY as readonly unknown[]).includes(scene))))));
    } else if (path.endsWith("/renderizador") || path.endsWith("/recursos")) {
      ok = path.endsWith("/recursos") || (typeof data.disponible === "boolean" && (data.motivo === null || typeof data.motivo === "string"));
      for (const name of ["cpu_hilos", "cpu_logicos", "cpu_hilos_disponibles", "cpu_hilos_maximos", "cpu_hilos_reserva"]) {
        if (data[name] !== undefined) ok = ok && Number.isInteger(data[name]) && Number(data[name]) >= 1;
      }
      if (data.cpu_hilos_configurables !== undefined) ok = ok && typeof data.cpu_hilos_configurables === "boolean";
      if (data.cpu_hilos_disponibles !== undefined && data.cpu_hilos !== undefined)
        ok = ok && Number(data.cpu_hilos) <= Number(data.cpu_hilos_disponibles);
      if (path.endsWith("/recursos")) ok = ok && Number.isInteger(data.cpu_hilos_maximos) && typeof data.gpu_vram_monitorizable === "boolean";
      if (data.cpu_hilos_maximos !== undefined) ok = ok && Number(data.cpu_hilos_maximos) <= Math.max(1, Math.floor(Number(data.cpu_hilos_disponibles) * 0.75)) && Number(data.cpu_hilos) <= Number(data.cpu_hilos_maximos);
      if (data.cpu_uso_actual_pct != null) ok = ok && typeof data.cpu_uso_actual_pct === "number" && Number.isFinite(data.cpu_uso_actual_pct) && data.cpu_uso_actual_pct >= 0 && data.cpu_uso_actual_pct <= 100;
      if (data.gpu_vram_monitorizable !== undefined) ok = ok && typeof data.gpu_vram_monitorizable === "boolean";
      if (data.gpu_vram_monitorizable === true) {
        for (const key of ["gpu_vram_total_mib", "gpu_vram_libre_mib", "gpu_vram_reserva_mib", "gpu_vram_max_mib", "gpu_vram_recomendado_mib"])
          ok = ok && Number.isInteger(data[key]) && Number(data[key]) >= 0;
        ok = ok && Number(data.gpu_vram_total_mib) > 0 && Number(data.gpu_vram_libre_mib) <= Number(data.gpu_vram_total_mib) && Number(data.gpu_vram_max_mib) <= Math.max(0, Number(data.gpu_vram_libre_mib) - Number(data.gpu_vram_reserva_mib)) && Number(data.gpu_vram_recomendado_mib) <= Number(data.gpu_vram_max_mib);
      }
      for (const name of ["espacio", "espacio_fotos"]) {
        if (data[name] != null) ok = ok && objeto(data[name]) && Object.values(data[name] as Record<string, unknown>).every(item =>
          objeto(item) && typeof item.disponible === "boolean" && typeof item.libre_bytes === "number" &&
          typeof item.necesario_bytes === "number" && Number.isFinite(item.libre_bytes) && Number.isFinite(item.necesario_bytes));
      }
      if (data.espacio_task_id != null) ok = ok && typeof data.espacio_task_id === "string";
      if (data.espacio_salida_id != null) ok = ok && typeof data.espacio_salida_id === "string";
    } else if (path === "/molcy/fotos/estimacion") {
      const seconds = data.estimado_s;
      ok = Number.isInteger(data.muestras) && Number(data.muestras) >= 0 &&
        (seconds === null ? data.muestras === 0 :
          typeof seconds === "number" && Number.isFinite(seconds) && seconds >= 0 && Number(data.muestras) > 0);
    } else if (path === "/molcy/fotos") {
      ok = trabajo(data);
    } else if (path.endsWith("/salida")) {
      ok = typeof data.disponible === "boolean" && typeof data.predeterminada === "string" &&
        (data.global === null || (objeto(data.global) && typeof data.global.id === "string" && typeof data.global.ruta === "string"));
    } else if (path.endsWith("/acceso")) {
      ok = typeof data.ruta === "string" && /^\/molcy\/medios\/[A-Za-z0-9_-]{32,}$/.test(data.ruta);
    } else if (path.endsWith("/revelar")) {
      ok = typeof data.ruta === "string" && ["video", "foto", "carpeta"].includes(String(data.tipo));
    } else if (path.endsWith("/procedencia")) {
      ok = data.schema === "molcy.procedencia/1" && objeto(data.build) && trabajo(data.trabajo);
    } else if (path === "/molcy/trabajos" && Array.isArray(data.trabajos)) {
      ok = data.trabajos.every(trabajo);
    } else if (path.includes("/trabajos") && data.eliminado === undefined) {
      ok = trabajo(data);
    } else if (path.includes("/blender") || path.endsWith("/configuracion")) {
      ok = typeof data.instalado === "boolean" && typeof data.descarga_bytes === "number" &&
        typeof data.version === "string" && objeto(data.configuracion) &&
        ["inactivo", "instalando", "completo", "fallido", "cancelado"].includes(String(data.estado));
    } else if (path.endsWith("/addon")) {
      ok = ["inactivo", "instalando", "completo", "fallido"].includes(String(data.estado));
    }
  }
  if (!ok) throw new FrontendError(frontendMessage("mo_frontend_230"));
}
