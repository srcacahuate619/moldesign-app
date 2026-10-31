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
import { Bot, X } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { useTheme } from "@/context/ThemeContext";
import { getAuthHeaders } from "@/lib/api";
import { fetchBackend } from "@/lib/backendFetch";
import { useAuth } from "@/lib/auth";

export const LISTO_ENVELOPE = "molchat-ui-ready";
export const SESION_ENVELOPE = "molchat-host-session";
export const HOST_ENVELOPE = "molchat-host-message";

type HostMessage =
  | { kind: "create_case"; request_id: string; name: string }
  | { kind: "load_case_smiles"; request_id: string; case_name: string; smiles: string }
  | { kind: "assign_case_receptor"; request_id: string; case_name: string; pdb_id: string }
  | { kind: "evaluate_case"; request_id: string; case_name: string }
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
  read_editor: ["request_id", "case_name", "operation", "revision"],
  open_evaluation: ["molecule_id"],
  open_report: ["molecule_id"],
  open_case: ["case_id"],
  open_molcy: ["job_id"],
  request_platform_approval: ["proposal_id"],
};

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

  return (
    <>
      <button
        type="button"
        onClick={() => (abierto ? cerrar() : abrir())}
        aria-label={abierto ? t("opt_ai_chat_close") : t("opt_ai_chat_open")}
        aria-expanded={abierto}
        aria-controls="molchat-host-panel"
        className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        style={{
          position: "fixed",
          bottom: "calc(24px + var(--evaluation-actions-height, 0px) + env(safe-area-inset-bottom, 0px))",
          right: 24,
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
        {abierto ? <X size={24} aria-hidden="true" /> : <Bot size={24} aria-hidden="true" />}
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
              aria-label={t("opt_ai_chat_close")}
              title={t("opt_ai_chat_close")}
              className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              style={{ position: "absolute", top: 9, right: 10, zIndex: 1, width: 34, height: 34,
                display: "grid", placeItems: "center", border: 0, borderRadius: 8,
                background: "var(--bg-secondary)", color: "var(--text-secondary)", cursor: "pointer" }}
            ><X size={18} aria-hidden="true" /></button>
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
