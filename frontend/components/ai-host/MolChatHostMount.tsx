"use client";

// Hueco del sidecar MolChat (Fase 6): la UI propia del asistente, embebida.
//
// El panel NO redibuja el chat: incrusta la UI que sirve el sidecar
// (`tools/molchat/ui/dist/`) en un iframe y le pasa la sesión por
// postMessage (orígenes loopback, apretón listo→sesión sin carreras: el
// iframe sólo existe cuando ya tenemos token que darle). Los deep links
// vuelven por el mismo puente con el esquema cerrado de §11.3 y aquí se
// convierten en navegación del escritorio. Sin sandbox a propósito: el
// contenido es el nuestro, verificado por hash antes de arrancar; el
// sandbox sólo rompería su sessionStorage sin amenazar a nadie.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Minus } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { useTheme } from "@/context/ThemeContext";
import { getAuthHeaders } from "@/lib/api";
import { fetchBackend } from "@/lib/backendFetch";
import { emitActivityNotification } from "@/lib/activityNotifications";
import type { MolcyPresentacion } from "@/lib/molcy";
import { useAuth } from "@/lib/auth";
import PilotoAutomatico, { PROGRESO_ENVELOPE, TarjetaDelPlan, progresoDelChat, type ProgresoDelChat } from "./PilotoAutomatico";

export const LISTO_ENVELOPE = "molchat-ui-ready";
export const SESION_ENVELOPE = "molchat-host-session";
export const HOST_ENVELOPE = "molchat-host-message";
export const ESTADO_ENVELOPE = "molchat-ui-status";

/** Lo que MolChat está haciendo, en una línea, para la burbuja del panel minimizado. */
export type EstadoChat = { state: "attention" | "error" | "working" | "thinking" | "done"; text: string };

/** Valida el estado que manda el chat: un estado de la lista y una línea corta de texto. ``idle`` (o algo mal formado)
 *  apaga la burbuja. El texto se pinta como texto, nunca como HTML. */
export function estadoDelChat(dato: unknown): EstadoChat | null {
  if (typeof dato !== "object" || dato === null) return null;
  const d = dato as Record<string, unknown>;
  if (Object.keys(d).length !== 3 || d.type !== ESTADO_ENVELOPE) return null;
  if (!["attention", "error", "working", "thinking", "done"].includes(d.state as string)) return null;
  if (typeof d.text !== "string" || d.text.length === 0 || d.text.length > 140 || /[\x00-\x1f]/.test(d.text)) return null;
  return { state: d.state as EstadoChat["state"], text: d.text };
}

/** El botón movible no se sale de la ventana: distancia a los bordes derecho e inferior, con un margen de 8 px. */
export function colocar(pos: { right: number; bottom: number }, ancho: number, alto: number, lado = 52): { right: number; bottom: number } {
  const limite = (v: number, max: number) => Math.round(Math.min(Math.max(v, 8), Math.max(8, max - lado - 8)));
  return { right: limite(pos.right, ancho), bottom: limite(pos.bottom, alto) };
}

const POSICION_GUARDADA = "molchat-burbuja-posicion";

type HostMessage =
  | { kind: "create_case"; request_id: string; name: string }
  | { kind: "load_case_smiles"; request_id: string; case_name: string; smiles: string }
  | { kind: "assign_case_receptor"; request_id: string; case_name: string; pdb_id: string }
  | { kind: "evaluate_case"; request_id: string; case_name: string }
  | { kind: "audit_case_preparation"; request_id: string; case_name: string; task_id: string }
  | { kind: "case_status"; request_id: string; case_name: string }
  | { kind: "molcy_render"; request_id: string; task_id: string; scene: string; format: string; presentation: string }
  | { kind: "notify_download"; request_id: string; phase: string; name: string }
  | { kind: "read_editor"; request_id: string; case_name: string; operation: string; revision: string }
  | { kind: "open_evaluation"; molecule_id: string }
  | { kind: "open_report"; molecule_id: string }
  | { kind: "open_case"; case_id: string }
  | { kind: "open_molcy"; job_id: string }
  | { kind: "request_platform_approval"; proposal_id: string };

const FORMAS: Record<HostMessage["kind"], string[]> = {
  create_case: ["request_id", "name"],
  load_case_smiles: ["request_id", "case_name", "smiles"],
  assign_case_receptor: ["request_id", "case_name", "pdb_id"],
  evaluate_case: ["request_id", "case_name"],
  audit_case_preparation: ["request_id", "case_name", "task_id"],
  case_status: ["request_id", "case_name"],
  molcy_render: ["request_id", "task_id", "scene", "format", "presentation"],
  notify_download: ["request_id", "phase", "name"],
  read_editor: ["request_id", "case_name", "operation", "revision"],
  open_evaluation: ["molecule_id"],
  open_report: ["molecule_id"],
  open_case: ["case_id"],
  open_molcy: ["job_id"],
  request_platform_approval: ["proposal_id"],
};

const COLOR = /^#[0-9A-F]{6}$/;
/**
 * La presentación de Molcy que pide el chat, validada campo por campo contra el esquema de la pestaña
 * (`moldesign.presentacion/1`). Lo que no sea exactamente eso se rechaza entero: el chat no puede colar otro ajuste.
 */
export function presentacionDelChat(raw: string): { presentacion: MolcyPresentacion; variante: "lenta" | "detallada" | "referencia" } | null {
  let dato: unknown;
  try { dato = JSON.parse(raw); } catch { return null; }
  if (typeof dato !== "object" || dato === null || Array.isArray(dato)) return null;
  const d = dato as Record<string, unknown>;
  const claves = ["schema", "titulo", "color_receptor", "color_residuos", "colores_lineas", "receptor", "muestra_anterior", "etiquetas", "contactos", "ensamble_variante"];
  if (Object.keys(d).length !== claves.length || !claves.every((k) => k in d)) return null;
  const color = (v: unknown) => v === null || (typeof v === "string" && COLOR.test(v));
  const lineas = d.colores_lineas as Record<string, unknown> | null;
  if (d.schema !== "moldesign.presentacion/1" || !(d.titulo === null || (typeof d.titulo === "string" && d.titulo.length <= 80 && !/[\x00-\x1f]/.test(d.titulo))) ||
      !color(d.color_receptor) || !color(d.color_residuos) || typeof lineas !== "object" || lineas === null ||
      Object.keys(lineas).length !== 2 || !color(lineas.polar) || !color(lineas.apolar) ||
      !["automatico", "visible", "oculto"].includes(d.receptor as string) ||
      typeof d.muestra_anterior !== "boolean" || typeof d.etiquetas !== "boolean" || typeof d.contactos !== "boolean" ||
      !["lenta", "detallada", "referencia"].includes(d.ensamble_variante as string)) return null;
  return {
    presentacion: { schema: "moldesign.presentacion/1", titulo: d.titulo as string | null, color_receptor: d.color_receptor as string | null,
      color_residuos: d.color_residuos as string | null, colores_lineas: { polar: lineas.polar as string | null, apolar: lineas.apolar as string | null },
      receptor: d.receptor as MolcyPresentacion["receptor"], muestra_anterior: d.muestra_anterior as boolean, etiquetas: d.etiquetas as boolean,
      contactos: d.contactos as boolean },
    variante: d.ensamble_variante as "lenta" | "detallada" | "referencia",
  };
}

export function esOrigenLoopback(origin: string): boolean {
  try {
    const url = new URL(origin);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      (url.hostname === "127.0.0.1" ||
        url.hostname === "localhost" ||
        url.hostname === "::1" ||
        url.hostname === "[::1]")
    );
  } catch {
    return false;
  }
}

export function esMensajeHost(value: unknown): value is HostMessage {
  if (typeof value !== "object" || value === null) return false;
  const registro = value as Record<string, unknown>;
  if (typeof registro["kind"] !== "string") return false;
  const campos = FORMAS[registro["kind"] as HostMessage["kind"]];
  if (!campos) return false;
  if (Object.keys(registro).length !== campos.length + 1) return false;
  return campos.every(
    (campo) =>
      typeof registro[campo] === "string" &&
      (registro[campo] as string).length > 0,
  );
}

/** A dónde navega cada deep link (superficies reales; el ítem exacto llega
 *  cuando las páginas acepten parámetros — hasta entonces, la lista). */
export function rutaPara(mensaje: HostMessage): string | null {
  switch (mensaje.kind) {
    case "create_case":
    case "load_case_smiles":
    case "assign_case_receptor":
    case "evaluate_case":
    case "audit_case_preparation":
    case "case_status":
    case "molcy_render":
    case "notify_download":
    case "read_editor":
      return null;
    case "open_molcy":
      return "/molcy";
    case "open_evaluation":
    case "open_report":
      return "/history";
    case "open_case":
      return "/moldex";
    case "request_platform_approval":
      return null; // sin superficie de aprobación en el host: aviso
  }
}

type Sesion = { url: string; token: string; expiraEnS: number; desde: number; owner: string };

export default function MolChatHostMount() {
  const { t, locale } = useLanguage();
  const { theme } = useTheme();
  const { user } = useAuth();
  const cuenta = useRef(user?.user_id);
  cuenta.current = user?.user_id;
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [fase, setFase] = useState<"cargando" | "ausente" | "error" | "listo">("cargando");
  const [motivo, setMotivo] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  // Minimizado, el panel se oculta pero el chat sigue trabajando; la burbuja dice en qué está.
  const [estadoChat, setEstadoChat] = useState<EstadoChat | null>(null);
  // El plan que maneja la aplicación, si hay uno: lo enseñan el piloto automático y la burbuja.
  const [progreso, setProgreso] = useState<ProgresoDelChat | null>(null);
  const [visto, setVisto] = useState("");
  // La posición guardada se lee después de montar: leerla en el primer render pintaba en el cliente otro botón que el
  // del HTML del servidor (React avisaba de una hidratación que no cuadra y no lo corregía).
  const [posicion, setPosicion] = useState<{ right: number; bottom: number } | null>(null);
  useEffect(() => {
    try {
      const dato = JSON.parse(window.localStorage.getItem(POSICION_GUARDADA) ?? "null") as { right?: unknown; bottom?: unknown } | null;
      if (dato && typeof dato.right === "number" && typeof dato.bottom === "number") setPosicion({ right: dato.right, bottom: dato.bottom });
    } catch { /* sin almacenamiento: la esquina de siempre */ }
  }, []);
  const arrastre = useRef<{ x: number; y: number; right: number; bottom: number; movido: boolean } | null>(null);
  const sesion = useRef<Sesion | null>(null);
  const marco = useRef<HTMLIFrameElement | null>(null);
  const peticiones = useRef(new Set<string>());
  const [, horquilla] = useState(0);
  const forzar = useCallback(() => horquilla((n) => n + 1), []);

  const publicarSesion = useCallback(() => {
    const actual = sesion.current;
    const ventana = marco.current?.contentWindow;
    if (!actual || !ventana) return;
    ventana.postMessage(
      { type: SESION_ENVELOPE, token: actual.token, locale, theme },
      actual.url,
    );
  }, [locale, theme]);

  useEffect(() => {
    publicarSesion();
  }, [publicarSesion]);

  const iniciar = useCallback(async () => {
    setFase("cargando");
    setMotivo("");
    try {
      const owner = cuenta.current;
      if (!owner) throw new Error("sin sesión de usuario");
      const estado = await fetchBackend("/molchat-host/status");
      if (!estado.ok) throw new Error(`status ${estado.status}`);
      const cuerpo = (await estado.json()) as {
        disponible: boolean; motivo: string; version?: string;
      };
      if (!cuerpo.disponible) {
        setMotivo(cuerpo.motivo || "");
        setFase("ausente");
        return;
      }
      const resp = await fetchBackend("/molchat-host/session", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      });
      if (!resp.ok) throw new Error(`session ${resp.status}`);
      const dato = (await resp.json()) as {
        url: string; token: string; expira_en_s: number;
      };
      if (cuenta.current !== owner) throw new Error("la cuenta cambió durante la conexión");
      sesion.current = {
        url: dato.url, token: dato.token,
        expiraEnS: dato.expira_en_s, desde: Date.now(), owner,
      };
      setFase("listo");
      forzar();
    } catch (err) {
      setMotivo(err instanceof Error ? err.message : String(err));
      setFase("error");
    }
  }, [forzar]);

  // El puente, escuchando desde antes de que exista ningún iframe.
  useEffect(() => {
    const alMensaje = (event: MessageEvent) => {
      const actual = sesion.current;
      const ventana = marco.current?.contentWindow;
      if (!actual || !ventana || event.source !== ventana) return;
      let origenEsperado: string;
      try {
        origenEsperado = new URL(actual.url).origin;
      } catch {
        return;
      }
      if (!esOrigenLoopback(event.origin) || event.origin !== origenEsperado) return;
      const dato = event.data as { type?: unknown } | null;
      if (!dato || typeof dato !== "object") return;
      if (dato.type === LISTO_ENVELOPE) {
        publicarSesion();
        return;
      }
      if (dato.type === ESTADO_ENVELOPE) {
        setEstadoChat(estadoDelChat(dato));
        return;
      }
      if (dato.type === PROGRESO_ENVELOPE) {
        setProgreso(progresoDelChat(dato));
        return;
      }
      if (dato.type !== HOST_ENVELOPE) return;
      const { type: _tipo, ...resto } = dato as Record<string, unknown>;
      if (!esMensajeHost(resto)) return;
      if (resto.kind === "read_editor") {
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || resto.case_name.length > 100 ||
            resto.case_name !== resto.case_name.trim() || /[\x00-\x1f]/.test(resto.case_name) ||
            !["snapshot", "check"].includes(resto.operation) || !/^[\w:-]{1,100}$/.test(resto.revision) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const deadline = Date.now() + 25000;
        const responder = (result: { status: string; molfile?: string; revision?: string }) => {
          if (terminado) return;
          terminado = true;
          ventana.postMessage({ type: "molchat-editor-result", request_id: resto.request_id, ...result }, origenEsperado);
        };
        const detalle = { caseName: resto.case_name, operation: resto.operation, revision: resto.revision,
          owner: actual.owner, deadline, handled: false, respond: responder };
        window.dispatchEvent(new CustomEvent("molchat-read-editor", { detail: detalle }));
        if (!detalle.handled && resto.operation === "snapshot") {
          router.push("/evaluation");
          let intentos = 0;
          const espera = window.setInterval(() => {
            if (terminado || ++intentos > 40) { window.clearInterval(espera); if (!terminado) responder({ status: "not_ready" }); return; }
            window.dispatchEvent(new CustomEvent("molchat-read-editor", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        } else if (!detalle.handled) responder({ status: "changed" });
        return;
      }
      if (resto.kind === "evaluate_case") {
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || !resto.case_name || resto.case_name.length > 100 ||
            resto.case_name !== resto.case_name.trim() || /[\x00-\x1f]/.test(resto.case_name) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const responder = (result: { status: string; task_id?: string; reason?: string }) => {
          if (terminado) return;
          terminado = true;
          ventana.postMessage({ type: "molchat-evaluation-result", request_id: resto.request_id, ...result }, origenEsperado);
        };
        const detalle = { caseName: resto.case_name, owner: actual.owner, requestId: resto.request_id,
          deadline: Date.now() + 120000, handled: false, respond: responder };
        window.dispatchEvent(new CustomEvent("molchat-evaluate-case", { detail: detalle }));
        if (!detalle.handled) {
          router.push("/evaluation");
          let intentos = 0;
          const espera = window.setInterval(() => {
            if (terminado || ++intentos > 40) {
              window.clearInterval(espera);
              if (!terminado) responder({ status: "failed" });
              return;
            }
            window.dispatchEvent(new CustomEvent("molchat-evaluate-case", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        }
        return;
      }
      if (resto.kind === "audit_case_preparation") {
        // El asistente pide auditar en Preparación la corrida que acaba de evaluar. La pestaña hace la auditoría
        // a la vista y devuelve la proyección del caso; aquí sólo se valida la forma y se hace de puente.
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || !resto.case_name || resto.case_name.length > 100 ||
            resto.case_name !== resto.case_name.trim() || /[\x00-\x1f]/.test(resto.case_name) ||
            !/^[A-Za-z0-9_.:-]{1,128}$/.test(resto.task_id) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const permitidos = ["audited", "case_not_found", "case_mismatch", "not_auditable", "audit_failed", "busy", "failed", "unknown"];
        const responder = (result: Record<string, unknown>) => {
          if (terminado) return;
          terminado = true;
          const status = typeof result.status === "string" && permitidos.includes(result.status) ? result.status : "unknown";
          const cuerpo: Record<string, unknown> = { status };
          if (status === "audited") {
            // Sólo viaja lo que el paquete necesita: la molécula, el estado que dictó el backend y la proyección.
            cuerpo.molecule_id = result.molecule_id;
            cuerpo.estado = result.estado;
            cuerpo.projection = result.projection;
          } else if (typeof result.reason === "string") cuerpo.reason = result.reason.slice(0, 300);
          ventana.postMessage({ type: "molchat-preparation-result", request_id: resto.request_id, ...cuerpo }, origenEsperado);
        };
        const detalle = { caseName: resto.case_name, taskId: resto.task_id, owner: actual.owner,
          deadline: Date.now() + 120000, handled: false, respond: responder };
        // La pestaña se enseña siempre: es la auditoría a la vista lo que se pide, no un cálculo escondido.
        router.push("/preparacion");
        window.dispatchEvent(new CustomEvent("molchat-audit-preparation", { detail: detalle }));
        if (!detalle.handled) {
          // La primera visita a la pestaña puede tardar (en desarrollo la página se compila): se insiste hasta el
          // plazo de la petición, no 10 s, y si nadie contesta se dice por qué.
          const espera = window.setInterval(() => {
            if (terminado || Date.now() >= detalle.deadline) {
              window.clearInterval(espera);
              if (!terminado) responder({ status: "failed", reason: t("molchat_motivo_preparacion_no_contesta") });
              return;
            }
            window.dispatchEvent(new CustomEvent("molchat-audit-preparation", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        }
        return;
      }
      if (resto.kind === "notify_download") {
        // Sólo un aviso: lo que MolChat descarga (el cuaderno, la entrega) o que el vídeo ya entró en la entrega. El
        // nombre se valida y se pinta como texto; la descarga la hace MolChat. Fases: started, done, failed, video_ready.
        const fases: Record<string, { status: "in_progress" | "success" | "error"; titleKey: string; messageKey: string }> = {
          started: { status: "in_progress", titleKey: "nt_molchat_descargando", messageKey: "nt_molchat_descargando_msg" },
          done: { status: "success", titleKey: "nt_molchat_descargado", messageKey: "nt_molchat_descargado_msg" },
          failed: { status: "error", titleKey: "nt_molchat_descarga_fallo", messageKey: "nt_molchat_descarga_fallo_msg" },
          video_ready: { status: "success", titleKey: "nt_molchat_video_listo", messageKey: "nt_molchat_video_listo_msg" },
        };
        const fase = fases[resto.phase];
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || !fase || !/^[A-Za-z0-9._ -]{1,80}$/.test(resto.name) ||
            cuenta.current !== actual.owner) return;
        emitActivityNotification({ id: `molchat-descarga:${resto.request_id}`, source: "general", status: fase.status,
          ownerId: actual.owner, titleKey: fase.titleKey, messageKey: fase.messageKey, params: { name: resto.name },
          progress: null });
        return;
      }
      if (resto.kind === "molcy_render") {
        // El asistente pide un vídeo de una corrida guardada. La pestaña de Molcy lo prepara a la vista (origen, escena,
        // formato) y pulsa su propio botón; aquí sólo se valida la forma, se enseña la pestaña y se hace de puente.
        const presentacion = presentacionDelChat(resto.presentation);
        if (!presentacion || !/^[a-f0-9]{32}$/.test(resto.request_id) || !/^[A-Za-z0-9_.:-]{1,128}$/.test(resto.task_id) ||
            !["resultado", "receptor", "busqueda", "ensamble"].includes(resto.scene) ||
            !["vertical", "horizontal", "previsualizacion"].includes(resto.format) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const permitidos = ["started", "not_found", "unavailable", "busy", "failed", "unknown"];
        const responder = (result: Record<string, unknown>) => {
          if (terminado) return;
          terminado = true;
          const status = typeof result.status === "string" && permitidos.includes(result.status) ? result.status : "unknown";
          const cuerpo: Record<string, unknown> = { status };
          if (status === "started" && typeof result.job_id === "string" && /^[A-Za-z0-9-]{8,64}$/.test(result.job_id)) cuerpo.job_id = result.job_id;
          if (status !== "started" && typeof result.reason === "string") cuerpo.reason = result.reason.slice(0, 300);
          ventana.postMessage({ type: "molchat-molcy-result", request_id: resto.request_id, ...cuerpo }, origenEsperado);
        };
        const detalle = { taskId: resto.task_id, scene: resto.scene, format: resto.format, presentacion: presentacion.presentacion,
          variante: presentacion.variante, owner: actual.owner, deadline: Date.now() + 90000, handled: false, respond: responder };
        router.push("/molcy");
        window.dispatchEvent(new CustomEvent("molchat-molcy-render", { detail: detalle }));
        if (!detalle.handled) {
          const espera = window.setInterval(() => {
            if (terminado || Date.now() >= detalle.deadline) {
              window.clearInterval(espera);
              if (!terminado) responder({ status: "failed", reason: t("molchat_motivo_molcy_no_contesta") });
              return;
            }
            window.dispatchEvent(new CustomEvent("molchat-molcy-render", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        }
        return;
      }
      if (resto.kind === "case_status") {
        // Sólo lectura: el asistente pregunta si el caso puede recibir otra molécula (la corrida anterior ya cerró)
        // en vez de adivinarlo probando a cargar. No navega ni cambia nada.
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || !resto.case_name || resto.case_name.length > 100 ||
            resto.case_name !== resto.case_name.trim() || /[\x00-\x1f]/.test(resto.case_name) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const permitidos = ["idle", "busy", "not_found", "ambiguous", "failed", "unknown"];
        const responder = (result: Record<string, unknown>) => {
          if (terminado) return;
          terminado = true;
          const status = typeof result.status === "string" && permitidos.includes(result.status) ? result.status : "unknown";
          const cuerpo: Record<string, unknown> = { status };
          if (typeof result.run_state === "string" && /^[a-z_]{1,32}$/.test(result.run_state)) cuerpo.run_state = result.run_state;
          if (typeof result.task_id === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(result.task_id)) cuerpo.task_id = result.task_id;
          ventana.postMessage({ type: "molchat-case-status-result", request_id: resto.request_id, ...cuerpo }, origenEsperado);
        };
        const detalle = { caseName: resto.case_name, owner: actual.owner, handled: false, respond: responder };
        window.dispatchEvent(new CustomEvent("molchat-case-status", { detail: detalle }));
        // Sin espacio de casos montado no hay nada vivo que bloquee: no se navega para contestar una pregunta.
        if (!detalle.handled) responder({ status: "unknown" });
        return;
      }
      if (resto.kind === "assign_case_receptor") {
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || !resto.case_name || resto.case_name.length > 100 ||
            resto.case_name !== resto.case_name.trim() || /[\x00-\x1f]/.test(resto.case_name) ||
            !/^[A-Za-z0-9_-]{1,64}$/.test(resto.pdb_id) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const responder = (status: string) => {
          if (terminado) return;
          terminado = true;
          ventana.postMessage({ type: "molchat-receptor-result", request_id: resto.request_id, status }, origenEsperado);
        };
        const detalle = { caseName: resto.case_name, pdbId: resto.pdb_id, owner: actual.owner,
          requestId: resto.request_id, deadline: Date.now() + 40000, handled: false, respond: responder };
        window.dispatchEvent(new CustomEvent("molchat-assign-receptor", { detail: detalle }));
        if (!detalle.handled) {
          router.push("/evaluation");
          let intentos = 0;
          const espera = window.setInterval(() => {
            if (terminado || ++intentos > 40) {
              window.clearInterval(espera);
              if (!terminado) responder("failed");
              return;
            }
            window.dispatchEvent(new CustomEvent("molchat-assign-receptor", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        }
        return;
      }
      if (resto.kind === "load_case_smiles") {
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || resto.case_name.length > 100 ||
            resto.case_name !== resto.case_name.trim() || /[\x00-\x1f]/.test(resto.case_name) ||
            resto.smiles.length > 2000 || resto.smiles !== resto.smiles.trim() || /[\x00-\x1f]/.test(resto.smiles) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const deadline = Date.now() + 40000;
        const responder = (status: "applied" | "not_found" | "ambiguous" | "busy" | "failed" | "unknown") => {
          if (terminado) return;
          terminado = true;
          ventana.postMessage({ type: "molchat-smiles-result", request_id: resto.request_id, status }, origenEsperado);
        };
        const detalle = { caseName: resto.case_name, smiles: resto.smiles, owner: actual.owner,
          requestId: resto.request_id, deadline, handled: false, respond: responder };
        window.dispatchEvent(new CustomEvent("molchat-load-smiles", { detail: detalle }));
        if (!detalle.handled) {
          router.push("/evaluation");
          let intentos = 0;
          const espera = window.setInterval(() => {
            if (terminado || ++intentos > 40) {
              window.clearInterval(espera);
              if (!terminado) responder("failed");
              return;
            }
            window.dispatchEvent(new CustomEvent("molchat-load-smiles", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        }
        return;
      }
      if (resto.kind === "create_case") {
        if (!/^[a-f0-9]{32}$/.test(resto.request_id) || resto.name.length > 100 ||
            resto.name !== resto.name.trim() || /[\x00-\x1f]/.test(resto.name) ||
            peticiones.current.has(resto.request_id) || cuenta.current !== actual.owner) return;
        peticiones.current.add(resto.request_id);
        let terminado = false;
        const responder = (status: "created" | "exists" | "failed" | "unknown") => {
          if (terminado) return;
          terminado = true;
          ventana.postMessage({ type: "molchat-case-result", request_id: resto.request_id, status }, origenEsperado);
        };
        const detalle = { name: resto.name, owner: actual.owner, handled: false, respond: responder };
        window.dispatchEvent(new CustomEvent("molchat-create-case", { detail: detalle }));
        if (!detalle.handled) {
          router.push("/evaluation");
          let intentos = 0;
          const espera = window.setInterval(() => {
            if (terminado || ++intentos > 40) {
              window.clearInterval(espera);
              if (!terminado) responder("failed");
              return;
            }
            window.dispatchEvent(new CustomEvent("molchat-create-case", { detail: detalle }));
            if (detalle.handled) window.clearInterval(espera);
          }, 250);
        }
        return;
      }
      const ruta = rutaPara(resto);
      if (ruta) {
        router.push(ruta);
      } else {
        setAviso(t("molchat_host_aprobacion"));
      }
    };
    window.addEventListener("message", alMensaje);
    return () => window.removeEventListener("message", alMensaje);
  }, [publicarSesion, router, t]);

  const abrir = () => {
    const actual = sesion.current;
    const caducada = !actual || actual.owner !== cuenta.current || Date.now() - actual.desde > (actual.expiraEnS - 30) * 1000;
    setAbierto(true);
    if (estadoChat) setVisto(`${estadoChat.state}:${estadoChat.text}`);
    if (fase === "listo" && !caducada) {
      // El iframe persiste con su oyente: basta re-publicar la sesión.
      setTimeout(publicarSesion, 0);
    } else {
      void iniciar();
    }
  };

  const cerrar = () => {
    const actual = sesion.current;
    if (actual) marco.current?.contentWindow?.postMessage({ type: "molchat-host-hidden" }, actual.url);
    setAbierto(false);
  };

  // El botón se arrastra a cualquier sitio y recuerda dónde se dejó; un clic sin moverlo abre o minimiza.
  const empezarArrastre = (e: React.PointerEvent<HTMLButtonElement>) => {
    const caja = e.currentTarget.getBoundingClientRect();
    arrastre.current = { x: e.clientX, y: e.clientY, right: window.innerWidth - caja.right, bottom: window.innerHeight - caja.bottom, movido: false };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const moverArrastre = (e: React.PointerEvent<HTMLButtonElement>) => {
    const a = arrastre.current;
    if (!a) return;
    const dx = e.clientX - a.x, dy = e.clientY - a.y;
    if (!a.movido && Math.hypot(dx, dy) < 5) return;
    a.movido = true;
    setPosicion(colocar({ right: a.right - dx, bottom: a.bottom - dy }, window.innerWidth, window.innerHeight));
  };
  const soltarArrastre = () => {
    const a = arrastre.current;
    arrastre.current = null;
    if (!a || !a.movido) return; // un clic sin moverse lo resuelve onClick
    setPosicion((actual) => {
      if (actual) { try { window.localStorage.setItem(POSICION_GUARDADA, JSON.stringify(actual)); } catch { /* sin almacenamiento: sólo esta sesión */ } }
      return actual;
    });
    soloArrastre.current = true;
  };
  const soloArrastre = useRef(false);

  const claveEstado = estadoChat ? `${estadoChat.state}:${estadoChat.text}` : "";
  // Un resultado ya visto con el panel abierto no se repite; lo que está en marcha o espera a la persona, sí.
  const burbuja = !abierto && estadoChat && !(estadoChat.state === "done" && claveEstado === visto) ? estadoChat : null;
  const lugar: { right: number; bottom: number | null } = posicion ?? { right: 24, bottom: null };
  const ancho = typeof window === "undefined" ? 0 : window.innerWidth;
  // La burbuja se abre hacia el lado con más sitio.
  const aLaIzquierda = lugar.right < ancho / 2;

  return (
    <>
      <PilotoAutomatico progreso={progreso} />
      {burbuja && (
        <button
          type="button"
          onClick={abrir}
          className={`molchat-burbuja molchat-burbuja--${burbuja.state}${progreso ? " molchat-burbuja--plan" : ""}`}
          aria-label={`${t("opt_ai_chat_open")}: ${burbuja.text}`}
          style={{
            position: "fixed", zIndex: 50,
            bottom: lugar.bottom === null ? "calc(30px + var(--evaluation-actions-height, 0px) + env(safe-area-inset-bottom, 0px))" : lugar.bottom + 6,
            ...(aLaIzquierda ? { right: lugar.right + 64 } : { left: ancho - lugar.right + 12 }),
          }}
        >
          {progreso ? <TarjetaDelPlan progreso={progreso} /> : <span role="status" aria-live="polite">{burbuja.text}</span>}
          {!progreso && (burbuja.state === "working" || burbuja.state === "thinking") && (
            <span className="molchat-burbuja-puntos" aria-hidden="true"><i /><i /><i /></span>
          )}
        </button>
      )}
      <button
        type="button"
        onClick={() => {
          if (soloArrastre.current) { soloArrastre.current = false; return; }
          if (abierto) cerrar(); else abrir();
        }}
        onPointerDown={empezarArrastre}
        onPointerMove={moverArrastre}
        onPointerUp={soltarArrastre}
        onPointerCancel={() => { arrastre.current = null; }}
        title={t("molchat_host_mover")}
        aria-label={abierto ? t("molchat_host_minimizar") : t("opt_ai_chat_open")}
        aria-expanded={abierto}
        aria-controls="molchat-host-panel"
        className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        style={{
          position: "fixed",
          bottom: lugar.bottom === null ? "calc(24px + var(--evaluation-actions-height, 0px) + env(safe-area-inset-bottom, 0px))" : lugar.bottom,
          right: lugar.right,
          touchAction: "none",
          zIndex: 50,
          width: 52,
          height: 52,
          borderRadius: 16,
          background: "var(--accent)",
          color: "#fff",
          border: "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
        }}
      >
        {abierto ? <Minus size={24} aria-hidden="true" /> : <Bot size={24} aria-hidden="true" />}
        {!abierto && burbuja && (burbuja.state === "attention" || burbuja.state === "error") && (
          <span aria-hidden="true" className={`molchat-burbuja-marca molchat-burbuja-marca--${burbuja.state}`} />
        )}
      </button>

      {(abierto || sesion.current) && (
        <div hidden={!abierto} style={{ display: abierto ? undefined : "none", position: "fixed", inset: 0, zIndex: 55, pointerEvents: "none" }}>
          <div
            onClick={cerrar}
            aria-hidden="true"
            style={{
              position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)",
              pointerEvents: "auto",
            }}
          />
          <div
            id="molchat-host-panel"
            role="dialog"
            aria-modal="true"
            aria-label={t("molchat_host_titulo")}
            style={{
              position: "absolute", right: 0, top: 76, bottom: 0, width: 420,
              maxWidth: "100vw", background: "var(--bg-secondary)",
              borderLeft: "1px solid var(--border)", display: "flex",
              flexDirection: "column", pointerEvents: "auto",
              boxShadow: "-8px 0 40px rgba(0,0,0,0.2)",
            }}
          >
            <button
              type="button"
              onClick={cerrar}
              aria-label={t("molchat_host_minimizar")}
              title={t("molchat_host_minimizar_ayuda")}
              className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              style={{ position: "absolute", top: 9, right: 10, zIndex: 1, width: 34, height: 34,
                display: "grid", placeItems: "center", border: 0, borderRadius: 8,
                background: "var(--bg-secondary)", color: "var(--text-secondary)", cursor: "pointer" }}
            ><Minus size={18} aria-hidden="true" /></button>
            {aviso && (
              <div role="status" style={{ padding: "8px 16px", fontSize: 13 }}>
                {aviso}{" "}
                <button type="button" onClick={() => setAviso(null)}>×</button>
              </div>
            )}
            {fase === "cargando" && (
              <p style={{ padding: 16 }}>{t("molchat_host_cargando")}</p>
            )}
            {fase === "ausente" && (
              <p style={{ padding: 16 }}>
                {t("molchat_host_ausente")}
                {motivo ? ` (${motivo})` : ""}
              </p>
            )}
            {fase === "error" && (
              <div style={{ padding: 16 }}>
                <p>{t("molchat_host_error")}{motivo ? `: ${motivo}` : ""}</p>
                <button type="button" onClick={() => void iniciar()}>
                  {t("molchat_host_reintentar")}
                </button>
              </div>
            )}
            {fase === "listo" && sesion.current && (
              <iframe
                ref={marco}
                title={t("molchat_host_titulo")}
                src={sesion.current.url}
                allow="microphone"
                style={{ flex: 1, width: "100%", border: "none" }}
              />
            )}
          </div>
        </div>
      )}
    </>
  );
}
