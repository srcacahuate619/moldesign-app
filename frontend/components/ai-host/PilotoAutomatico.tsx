"use client";

// El piloto automático de MolChat, a la vista. Mientras un plan aprobado maneja MolDesign, la ventana lo dice sin
// ambigüedad: un marco del color de MolChat alrededor de la aplicación, un cartel arriba con lo que hace ahora y un
// cursor propio, rotulado «MolChat», que va al control sobre el que actúa la pestaña (`lib/cursorDelChat.ts`). Con el
// panel minimizado, la burbuja enseña el plan entero (`TarjetaDelPlan`). Nada de esto actúa: sólo enseña lo que el chat
// informa y lo que la pestaña hace.

import { useEffect, useRef, useState } from "react";
import { Bot, Check, Circle, LoaderCircle, Minus, X } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { CURSOR_DEL_CHAT, type DestinoDelCursor } from "@/lib/cursorDelChat";

export const PROGRESO_ENVELOPE = "molchat-ui-progress";

type EstadoPaso = "pending" | "running" | "done" | "failed" | "skipped";
export type ProgresoDelChat = {
  title: string;
  phase: "running" | "rendering" | "done" | "stopped";
  now: string;
  steps: { label: string; state: EstadoPaso }[];
  molecules: { name: string; state: EstadoPaso; vina: number | null; meets: boolean }[];
};

const ESTADOS: EstadoPaso[] = ["pending", "running", "done", "failed", "skipped"];
const texto = (v: unknown, max: number) => typeof v === "string" && v.length > 0 && v.length <= max && !/[\x00-\x1f]/.test(v);
const claves = (d: Record<string, unknown>, lista: string[]) => Object.keys(d).length === lista.length && lista.every((k) => k in d);

/** Valida el progreso que manda el chat, campo por campo; lo que no sea exactamente eso se descarta entero. `null`
 *  (o un sobre sin plan) apaga el piloto. Los textos se pintan como texto, nunca como HTML. */
export function progresoDelChat(dato: unknown): ProgresoDelChat | null {
  if (typeof dato !== "object" || dato === null) return null;
  const recibido = dato as Record<string, unknown>;
  if (!claves(recibido, ["type", "progress"]) || recibido.type !== PROGRESO_ENVELOPE) return null;
  const p = recibido.progress as Record<string, unknown> | null;
  if (typeof p !== "object" || p === null || !claves(p, ["title", "phase", "now", "steps", "molecules"])) return null;
  if (!texto(p.title, 140) || !texto(p.now, 140) || !["running", "rendering", "done", "stopped"].includes(p.phase as string)) return null;
  if (!Array.isArray(p.steps) || p.steps.length > 10 || !Array.isArray(p.molecules) || p.molecules.length > 12) return null;
  const pasos = p.steps.every((s) => typeof s === "object" && s !== null && claves(s as Record<string, unknown>, ["label", "state"])
    && texto((s as Record<string, unknown>).label, 60) && ESTADOS.includes((s as Record<string, unknown>).state as EstadoPaso));
  const moleculas = p.molecules.every((m) => {
    if (typeof m !== "object" || m === null) return false;
    const r = m as Record<string, unknown>;
    return claves(r, ["name", "state", "vina", "meets"]) && texto(r.name, 80) && ESTADOS.includes(r.state as EstadoPaso)
      && (r.vina === null || (typeof r.vina === "number" && Number.isFinite(r.vina) && Math.abs(r.vina) < 100)) && typeof r.meets === "boolean";
  });
  if (!pasos || !moleculas) return null;
  return p as unknown as ProgresoDelChat;
}

export const pilotoActivo = (p: ProgresoDelChat | null) => p !== null && (p.phase === "running" || p.phase === "rendering");

const kcal = (v: number) => v.toFixed(1).replace("-", "−");

function Marca({ estado }: { estado: EstadoPaso }) {
  if (estado === "done") return <Check size={13} aria-hidden="true" />;
  if (estado === "running") return <LoaderCircle size={13} aria-hidden="true" className="molchat-piloto-gira" />;
  if (estado === "failed") return <X size={13} aria-hidden="true" />;
  if (estado === "skipped") return <Minus size={13} aria-hidden="true" />;
  return <Circle size={9} aria-hidden="true" />;
}

/** El contenido de la burbuja cuando hay un plan: cabecera, lo que hace ahora, las moléculas y los pasos. */
export function TarjetaDelPlan({ progreso }: { progreso: ProgresoDelChat }) {
  const { t } = useLanguage();
  const activo = pilotoActivo(progreso);
  const cabecera = activo ? t("molchat_piloto") : progreso.phase === "stopped" ? t("molchat_piloto_detenido") : t("molchat_piloto_listo");
  const hechas = progreso.molecules.filter((m) => m.state !== "pending" && m.state !== "running").length;
  return (
    <span className="molchat-plan" data-fase={progreso.phase}>
      <span className="molchat-plan-cabecera">
        <span className="molchat-plan-punto" aria-hidden="true" />
        <strong>MolChat · {cabecera}</strong>
        <span className="molchat-plan-cuenta">{hechas}/{progreso.molecules.length}</span>
      </span>
      <span className="molchat-plan-titulo">{progreso.title}</span>
      <span className="molchat-plan-ahora">{progreso.now}</span>
      <span className="molchat-plan-barra" aria-hidden="true">
        <i style={{ width: `${progreso.molecules.length ? Math.round((100 * hechas) / progreso.molecules.length) : 0}%` }} />
      </span>
      <span className="molchat-plan-moleculas" aria-label={t("molchat_piloto_moleculas")}>
        {progreso.molecules.map((m, i) => (
          <span key={i} className="molchat-plan-molecula" data-estado={m.state} data-cumple={m.meets || undefined}>
            <Marca estado={m.state} />
            <span className="molchat-plan-nombre">{m.name}</span>
            <span className="molchat-plan-vina">{m.vina === null ? (m.state === "running" ? "…" : "") : kcal(m.vina)}</span>
          </span>
        ))}
      </span>
      <span className="molchat-plan-pasos">
        {progreso.steps.map((s, i) => (
          <span key={i} className="molchat-plan-paso" data-estado={s.state}><Marca estado={s.state} />{s.label}</span>
        ))}
      </span>
    </span>
  );
}

/** El marco, el cartel y el cursor de MolChat mientras un plan maneja la aplicación. */
export default function PilotoAutomatico({ progreso }: { progreso: ProgresoDelChat | null }) {
  const { t } = useLanguage();
  const activo = pilotoActivo(progreso);
  const [cursor, setCursor] = useState<{ x: number; y: number; clic: number } | null>(null);
  const temporizadores = useRef<number[]>([]);

  useEffect(() => {
    if (!activo) { setCursor(null); return; }
    // Sale de la esquina del botón de MolChat: de ahí viene quien maneja.
    setCursor((c) => c ?? { x: window.innerWidth - 70, y: window.innerHeight - 70, clic: 0 });
    const recibir = (evento: Event) => {
      const destino = (evento as CustomEvent<DestinoDelCursor>).detail;
      if (!destino || !(destino.elemento instanceof Element)) return;
      const apuntar = (marcaClic: boolean) => {
        if (!destino.elemento.isConnected) return;
        const caja = destino.elemento.getBoundingClientRect();
        if (caja.width === 0 && caja.height === 0) return;
        const x = Math.min(window.innerWidth - 24, Math.max(8, caja.left + caja.width / 2));
        const y = Math.min(window.innerHeight - 24, Math.max(8, caja.top + Math.min(caja.height / 2, 140)));
        setCursor((c) => ({ x, y, clic: (c?.clic ?? 0) + (marcaClic ? 1 : 0) }));
      };
      // La pestaña lleva el elemento a la vista con un desplazamiento suave: se apunta enseguida, otra vez cuando suele
      // haberse asentado (ahí se marca el clic, una sola vez) y una última por si la página siguió moviéndose.
      temporizadores.current.push(window.setTimeout(() => apuntar(false), 300),
        window.setTimeout(() => apuntar(destino.pulsa), 850), window.setTimeout(() => apuntar(false), 1700));
    };
    window.addEventListener(CURSOR_DEL_CHAT, recibir);
    return () => {
      window.removeEventListener(CURSOR_DEL_CHAT, recibir);
      temporizadores.current.forEach((id) => window.clearTimeout(id));
      temporizadores.current = [];
    };
  }, [activo]);

  if (!activo || !progreso) return null;
  const pasoActual = progreso.steps.findIndex((s) => s.state === "running");
  return (
    <>
      <div aria-hidden="true" className={`molchat-piloto-marco${progreso.phase === "rendering" ? " molchat-piloto-marco--espera" : ""}`} />
      <div role="status" aria-live="polite" className="molchat-piloto-cartel" data-testid="molchat-piloto">
        <span className="molchat-plan-punto" aria-hidden="true" />
        <Bot size={16} aria-hidden="true" />
        <strong>{t("molchat_piloto")}</strong>
        <span className="molchat-piloto-sep" aria-hidden="true" />
        <span className="molchat-piloto-ahora">{progreso.phase === "rendering" ? t("molchat_piloto_render") : progreso.now}</span>
        {pasoActual >= 0 && <span className="molchat-piloto-paso">{pasoActual + 1}/{progreso.steps.length} · {progreso.steps[pasoActual].label}</span>}
      </div>
      {cursor && (
        <div aria-hidden="true" className="molchat-piloto-cursor" style={{ transform: `translate(${cursor.x}px, ${cursor.y}px)` }}>
          {cursor.clic > 0 && <span key={cursor.clic} className="molchat-piloto-clic" />}
          <svg width="26" height="26" viewBox="0 0 22 22"><path d="M2 2 L2 18 L7 13 L11 21 L14 19.5 L10 12 L17 12 Z" fill="var(--molchat-violeta, #8b5cf6)" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" /></svg>
          <span className="molchat-piloto-etiqueta">MolChat</span>
        </div>
      )}
    </>
  );
}
