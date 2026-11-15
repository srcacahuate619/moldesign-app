"use client";

// Visor de respaldo: el receptor y la pose dibujados en un lienzo 2D, sin WebGL.
//
// CUÁNDO APARECE. Cuando el equipo no da ningún contexto 3D —ni por hardware ni
// por software— o cuando Mol* y Web3D fallan los dos. Antes, en ese caso, la
// columna del visor era un recuadro negro con un aviso: se podía evaluar, pero no
// mirar dónde había quedado la pose. Ver `lib/visorSinWebGL.ts`.
//
// CUÁNTO CUESTA. Nada mientras no se toca: no hay bucle de dibujo. Se pinta al
// cambiar los datos, el tamaño o la vista, y como mucho una vez por fotograma.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Cpu, RotateCcw, Tag } from "lucide-react";

import { useLanguage } from "@/context/LanguageContext";
import { appLocale } from "../../../lib/formatoNumerico";
import {
  RADIO_DE_CONTACTO, RADIO_SIN_POSE, ZOOM_MAXIMO, ZOOM_MINIMO,
  construirEscena, girar, mirarDesde, niebla, proyectar,
  type CajaDeBusqueda, type Proyeccion, type Vista,
} from "../../../lib/visorSinWebGL";
import {
  VIEWER_LABEL_BUTTON_CLASS,
  VIEWER_LABEL_PANEL_CLASS,
  VIEWER_SWITCH_BUTTON_CLASS,
} from "./viewerOverlayStyles";

type Props = {
  proteinData?: string;
  poseData?: string;
  gridInfo?: CajaDeBusqueda | null;
  /** Por qué se enseña esta vista en lugar de un visor 3D. */
  motivo: "sin-webgl" | "visor-fallo";
  /** Vuelve a comprobar el equipo y a intentar el visor 3D. Sin él, no se ofrece. */
  onReintentar3D?: () => void;
};

const FONDO = "#05080f";
const COLOR_DE_LA_TRAZA = "#55627a";
const COLOR_DE_LA_CAJA = "#22d3ee";
const CARBONO_DEL_SITIO = "#8794ad";
const CARBONO_DEL_LIGANDO = "#f1f5f9";
const HETEROATOMOS: Record<string, string> = {
  N: "#6f9bff", O: "#ff6b6b", S: "#e8c84f", P: "#ff9d5c",
  F: "#2fd99a", CL: "#2fd99a", BR: "#c98a5e", I: "#b58cf0",
  ZN: "#94a3b8", MG: "#94a3b8", FE: "#d08a5b", CA: "#94a3b8", MN: "#94a3b8",
};
const colorDe = (elemento: string | undefined, carbono: string) =>
  !elemento || elemento === "C" ? carbono : HETEROATOMOS[elemento] ?? "#cbd5e1";

/** Pinta una proyección. Sin estado: lo mismo entra, lo mismo sale. */
function pintar(ctx: CanvasRenderingContext2D, proyeccion: Proyeccion, ancho: number, alto: number, dpr: number): void {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, ancho, alto);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  const e = proyeccion.escala;
  const grosorSitio = Math.min(4, Math.max(1.4, e * 0.13));
  const grosorLigando = Math.min(9, Math.max(2.6, e * 0.26));
  const radioSitio = Math.min(7, Math.max(2, e * 0.2));
  const radioLigando = Math.min(14, Math.max(3.2, e * 0.36));
  ctx.font = "600 11px ui-sans-serif, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (const p of proyeccion.primitivas) {
    const opacidad = niebla(p.z, proyeccion.fondo);
    if (p.tipo === "linea") {
      if (p.capa === "ligando") {
        // Un borde oscuro bajo cada enlace separa la pose de los residuos que tiene detrás.
        ctx.globalAlpha = 1;
        ctx.strokeStyle = FONDO;
        ctx.lineWidth = grosorLigando + 3;
        ctx.beginPath(); ctx.moveTo(p.x1, p.y1); ctx.lineTo(p.x2, p.y2); ctx.stroke();
      }
      ctx.globalAlpha = p.capa === "traza" ? opacidad * 0.85 : p.capa === "caja" ? opacidad * 0.7 : p.capa === "ligando" ? Math.max(opacidad, 0.8) : opacidad;
      ctx.strokeStyle = p.capa === "traza" ? COLOR_DE_LA_TRAZA : p.capa === "caja" ? COLOR_DE_LA_CAJA
        : colorDe(p.elemento, p.capa === "ligando" ? CARBONO_DEL_LIGANDO : CARBONO_DEL_SITIO);
      ctx.lineWidth = p.capa === "traza" ? 1.6 : p.capa === "caja" ? 1 : p.capa === "ligando" ? grosorLigando : grosorSitio;
      ctx.beginPath(); ctx.moveTo(p.x1, p.y1); ctx.lineTo(p.x2, p.y2); ctx.stroke();
    } else if (p.tipo === "disco") {
      const ligando = p.capa === "ligando";
      ctx.globalAlpha = ligando ? Math.max(opacidad, 0.8) : opacidad;
      ctx.fillStyle = colorDe(p.elemento, ligando ? CARBONO_DEL_LIGANDO : CARBONO_DEL_SITIO);
      ctx.beginPath(); ctx.arc(p.x, p.y, ligando ? radioLigando : radioSitio, 0, Math.PI * 2); ctx.fill();
      if (ligando) { ctx.strokeStyle = FONDO; ctx.lineWidth = 1.2; ctx.stroke(); }
    } else {
      ctx.globalAlpha = Math.max(opacidad, 0.55);
      ctx.strokeStyle = FONDO;
      ctx.lineWidth = 3.5;
      ctx.strokeText(p.texto, p.x, p.y);
      ctx.fillStyle = "#e2e8f0";
      ctx.fillText(p.texto, p.x, p.y);
    }
  }
  ctx.globalAlpha = 1;
}

export default function VisorSinWebGL({ proteinData, poseData, gridInfo, motivo, onReintentar3D }: Props) {
  const { t, locale } = useLanguage();
  const contenedor = useRef<HTMLDivElement>(null);
  const lienzo = useRef<HTMLCanvasElement>(null);
  const [panelAbierto, setPanelAbierto] = useState(true);
  const [etiquetas, setEtiquetas] = useState(true);

  // La caja llega como objeto nuevo en cada render del contenedor: se compara por valor
  // para no reconstruir la escena (y perder el giro) sin que nada haya cambiado.
  const claveDeLaCaja = gridInfo
    ? [gridInfo.centerX, gridInfo.centerY, gridInfo.centerZ, gridInfo.sizeX, gridInfo.sizeY, gridInfo.sizeZ].join(",")
    : "";
  const escena = useMemo(
    () => construirEscena({ pdb: proteinData, sdf: poseData, caja: gridInfo }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [proteinData, poseData, claveDeLaCaja],
  );

  const vista = useRef<Vista>({ rotacion: mirarDesde(null), zoom: 1 });
  const fotograma = useRef(0);
  const opciones = useRef({ etiquetas });
  opciones.current = { etiquetas };
  const escenaActual = useRef(escena);
  escenaActual.current = escena;

  const dibujar = useCallback(() => {
    fotograma.current = 0;
    const lona = lienzo.current, caja = contenedor.current, actual = escenaActual.current;
    if (!lona || !caja || !actual) return;
    const ancho = caja.clientWidth, alto = caja.clientHeight;
    // Con la pestaña oculta (keep-alive, `display:none`) el tamaño es 0: no hay nada que pintar.
    if (ancho < 2 || alto < 2) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (lona.width !== Math.round(ancho * dpr) || lona.height !== Math.round(alto * dpr)) {
      lona.width = Math.round(ancho * dpr);
      lona.height = Math.round(alto * dpr);
    }
    const ctx = lona.getContext("2d");
    if (!ctx) return;
    // Con muchas etiquetas el dibujo se vuelve ilegible: se enseñan cuando caben.
    const conEtiquetas = opciones.current.etiquetas && actual.sitio.etiquetas.length <= 40;
    pintar(ctx, proyectar(actual, vista.current, ancho, alto, { etiquetas: conEtiquetas }), ancho, alto, dpr);
  }, []);

  /** Como mucho un dibujo por fotograma, por muchos eventos de ratón que lleguen. */
  const programar = useCallback(() => {
    if (fotograma.current) return;
    fotograma.current = requestAnimationFrame(dibujar);
  }, [dibujar]);

  const reencuadrar = useCallback(() => {
    vista.current = { rotacion: mirarDesde(escenaActual.current?.haciaElObservador ?? null), zoom: 1 };
    programar();
  }, [programar]);

  // Escena nueva (otro receptor, otra pose): se vuelve al encuadre inicial.
  useEffect(() => { reencuadrar(); }, [escena, reencuadrar]);
  useEffect(() => { programar(); }, [etiquetas, programar]);

  useEffect(() => {
    const caja = contenedor.current;
    if (!caja) return;
    const observador = typeof ResizeObserver !== "undefined" ? new ResizeObserver(programar) : null;
    observador?.observe(caja);
    window.addEventListener("resize", programar);
    programar();
    return () => {
      observador?.disconnect();
      window.removeEventListener("resize", programar);
      if (fotograma.current) cancelAnimationFrame(fotograma.current);
      fotograma.current = 0;
    };
  }, [programar]);

  // La rueda se escucha a mano: React la registra como pasiva y no deja evitar
  // que, además de acercar, se desplace la página.
  useEffect(() => {
    const lona = lienzo.current;
    if (!lona) return;
    const alGirarLaRueda = (evento: WheelEvent) => {
      evento.preventDefault();
      const zoom = Math.min(ZOOM_MAXIMO, Math.max(ZOOM_MINIMO, vista.current.zoom * Math.exp(-evento.deltaY * 0.0015)));
      vista.current = { ...vista.current, zoom };
      programar();
    };
    lona.addEventListener("wheel", alGirarLaRueda, { passive: false });
    return () => lona.removeEventListener("wheel", alGirarLaRueda);
  }, [programar, escena]);

  const arrastre = useRef<{ x: number; y: number } | null>(null);
  const alPulsar = (evento: React.PointerEvent<HTMLCanvasElement>) => {
    arrastre.current = { x: evento.clientX, y: evento.clientY };
    evento.currentTarget.setPointerCapture?.(evento.pointerId);
    // La explicación se lee una vez; al empezar a mirar la estructura, estorba.
    // Se recoge sola y queda a un clic en el rótulo de la esquina.
    setPanelAbierto(false);
  };
  const alMover = (evento: React.PointerEvent<HTMLCanvasElement>) => {
    const origen = arrastre.current;
    if (!origen) return;
    const dx = evento.clientX - origen.x, dy = evento.clientY - origen.y;
    arrastre.current = { x: evento.clientX, y: evento.clientY };
    vista.current = { ...vista.current, rotacion: girar(vista.current.rotacion, dx * 0.008, dy * 0.008) };
    programar();
  };
  const alSoltar = (evento: React.PointerEvent<HTMLCanvasElement>) => {
    arrastre.current = null;
    evento.currentTarget.releasePointerCapture?.(evento.pointerId);
  };
  const alTeclear = (evento: React.KeyboardEvent<HTMLCanvasElement>) => {
    const paso = 0.14;
    const giros: Record<string, [number, number]> = {
      ArrowLeft: [-paso, 0], ArrowRight: [paso, 0], ArrowUp: [0, -paso], ArrowDown: [0, paso],
    };
    if (giros[evento.key]) {
      vista.current = { ...vista.current, rotacion: girar(vista.current.rotacion, ...giros[evento.key]) };
    } else if (evento.key === "+" || evento.key === "=" || evento.key === "-") {
      const factor = evento.key === "-" ? 1 / 1.2 : 1.2;
      vista.current = { ...vista.current, zoom: Math.min(ZOOM_MAXIMO, Math.max(ZOOM_MINIMO, vista.current.zoom * factor)) };
    } else if (evento.key === "Home" || evento.key === "0") {
      reencuadrar();
    } else return;
    evento.preventDefault();
    programar();
  };

  const queSeDibuja = !escena ? null
    : escena.criterioDelSitio === "ligando"
      ? t("pn_v2d_que_ligando", { distancia: RADIO_DE_CONTACTO.toLocaleString(appLocale(locale)) })
      : escena.criterioDelSitio === "caja"
        ? t("pn_v2d_que_caja", { distancia: RADIO_SIN_POSE.toLocaleString(appLocale(locale)) })
        : t("pn_v2d_que_esqueleto");

  return (
    <div ref={contenedor} data-testid="visor-sin-webgl" className="relative isolate h-full w-full overflow-hidden bg-[#05080f]">
      {escena ? (
        <canvas
          ref={lienzo}
          role="img"
          tabIndex={0}
          aria-label={t("pn_v2d_aria")}
          className="absolute inset-0 h-full w-full cursor-move touch-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-400"
          onPointerDown={alPulsar}
          onPointerMove={alMover}
          onPointerUp={alSoltar}
          onPointerCancel={alSoltar}
          onDoubleClick={reencuadrar}
          onKeyDown={alTeclear}
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center font-mono text-xs uppercase tracking-widest text-slate-500">
          {t("pn_sin_estructura")}
        </div>
      )}

      {/* Esquina superior izquierda: volver al 3D (donde está el cambio de visor en los otros dos, lejos de la burbuja
          de MolChat) y qué es esta vista y por qué se está viendo. */}
      <div className="absolute left-3 top-3 z-10 max-w-[min(360px,calc(100%-1.5rem))]">
        <div className="flex items-center gap-2">
          {onReintentar3D && (
            <button type="button" onClick={onReintentar3D} className={VIEWER_SWITCH_BUTTON_CLASS} title={t("pn_v2d_reintentar_titulo")}>
              {t("pn_v2d_reintentar")}
            </button>
          )}
          <button type="button" onClick={() => setPanelAbierto((abierto) => !abierto)} aria-expanded={panelAbierto}
            className={`${VIEWER_LABEL_BUTTON_CLASS} justify-between`}>
            <span className="flex items-center gap-2 text-amber-300"><Cpu size={12} aria-hidden="true" />{t("pn_v2d_titulo")}</span>
            <span className="text-slate-500" aria-hidden="true">{panelAbierto ? "▾" : "▸"}</span>
          </button>
        </div>
        {panelAbierto && (
          <div role="status" className={`${VIEWER_LABEL_PANEL_CLASS} mt-2 flex flex-col gap-1.5 px-3 py-2.5 text-[11px] leading-relaxed text-slate-300`}>
            <p>{t(motivo === "sin-webgl" ? "pn_v2d_motivo_sin_webgl" : "pn_v2d_motivo_fallo")}</p>
            <p className="text-slate-400"><span className="font-semibold text-slate-300">{t("pn_evaluacion_no_afectada")}</span> {t("pn_v2d_no_afecta")}</p>
            {queSeDibuja && <p className="text-slate-400">{queSeDibuja}</p>}
            {escena && <p className="text-slate-500">{t("pn_v2d_gestos")}</p>}
          </div>
        )}
      </div>

      {escena && (
        <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
          {escena.sitio.etiquetas.length > 0 && escena.sitio.etiquetas.length <= 40 && (
            <button type="button" onClick={() => setEtiquetas((ver) => !ver)} aria-pressed={etiquetas} className={VIEWER_LABEL_BUTTON_CLASS}>
              <Tag size={12} className={etiquetas ? "text-brand-400" : "text-slate-500"} aria-hidden="true" />
              {t("pn_v2d_etiquetas")}
            </button>
          )}
          <button type="button" onClick={reencuadrar} className={VIEWER_LABEL_BUTTON_CLASS}>
            <RotateCcw size={12} className="text-slate-400" aria-hidden="true" />
            {t("pn_v2d_reencuadrar")}
          </button>
        </div>
      )}

      {escena && (
        <div className={`${VIEWER_LABEL_PANEL_CLASS} pointer-events-none absolute bottom-3 left-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-[11px] font-semibold text-slate-300`}>
          {escena.ligando.atomos.length > 0 && (
            <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#f1f5f9]" />{t("pr_viewer_ligand_docked")}</span>
          )}
          {escena.sitio.atomos.length > 0 && (
            <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-[#8794ad]" />
              {t("pn_v2d_ley_sitio", { n: escena.cuenta.residuosDelSitio })}</span>
          )}
          {escena.traza.length > 0 && (
            <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-3 bg-[#55627a]" />{t("pn_v2d_ley_esqueleto")}</span>
          )}
          {escena.caja && (
            <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border border-[#22d3ee]" />{t("pn_caja_acoplamiento")}</span>
          )}
        </div>
      )}

    </div>
  );
}
