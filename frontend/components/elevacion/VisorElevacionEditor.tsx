"use client";

import { presentError } from "../../lib/frontendError";

/**
 * Visor alternativo a Ketcher: la molécula dibujada, levantada a 3D y girando.
 *
 * No sustituye al editor: se entra y se sale con el mismo botón de esquina que
 * alterna Mol* y Web3D, y Ketcher sigue montado debajo con su dibujo intacto.
 *
 * Lo que enseña es UN conformador calculado (ETKDGv3 + MMFF94, semilla fija),
 * no una pose de docking, y lo dice encima del dibujo. La vista «Se acoplará»
 * enseña en cambio la especie que prepararía la corrida (tautómero, protonación
 * al pH de la corrida, sin contraiones) sobre el mismo dibujo, con lo que cambió
 * marcado y listado.
 *
 * Parte del dibujo de Ketcher (`molfile`) cuando es la molécula del SMILES, y
 * dice lo que los detectores del producto y la geometría implican para Vina. La
 * vista «Escrita» enseña primero una semilla y después las tres: mientras tanto,
 * la abstención es provisional y se dice.
 *
 * El bucle de animación sólo corre con el visor a la vista: las pestañas de
 * esta aplicación no se desmontan, y un `requestAnimationFrame` en una pestaña
 * oculta seguiría pintando (ver la fuga del sondeo a Ketcher en AGENTS.md).
 */

import { useLanguage } from "@/context/LanguageContext";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ErrorDeElevacion,
  IDENTIDAD,
  elevacionDelEditor,
  formatoDeNumero,
  modeloDelEditorEnCache,
  multiplicar,
  pintar,
  prefiereMenosMovimiento,
  prepararEscena,
  proyectar,
  rotX,
  rotY,
  suavizar,
  type Escena,
  type Matriz,
  type ModeloElevacion,
  type OpcionesDelEditor,
  type PreparacionDeLaCorrida,
  type VistaDelEditor,
} from "../../lib/elevacion";
import { VIEWER_LABEL_BUTTON_CLASS, VIEWER_SWITCH_BUTTON_CLASS } from "../interfaces/pro/viewerOverlayStyles";

const VUELTA_MS = 9000;
const SUBIDA_MS = 650;
const BAJADA_MS = 320;
const ESPERA_MS = 400;
/** Por encima de esto, el ΔE del conformador elegido se señala (kcal/mol, campo de fuerza en fase gas). */
const DELTA_E_AVISO = 5;

type Props = {
  smiles: string;
  /** Visible ahora. Oculto no calcula ni gira: el visor sigue montado, con su estado. */
  activo: boolean;
  /** Vuelve a Ketcher. */
  onSwitchViewer: () => void;
  /** pH y tautómero de la corrida que se va a lanzar, para la vista «Se acoplará». */
  preparacion?: PreparacionDeLaCorrida;
  /** El dibujo de Ketcher al abrir el visor: el levantamiento parte de él. */
  molfile?: string | null;
};

type Carga =
  | { tipo: "vacio" }
  | { tipo: "cargando" }
  | { tipo: "error"; detalle: string }
  | { tipo: "listo"; modelo: ModeloElevacion };

export default function VisorElevacionEditor({ smiles, activo, onSwitchViewer, preparacion, molfile }: Props) {
  const { t, locale } = useLanguage();
  const cajaRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const datos = useRef<{ modelo: ModeloElevacion; escena: Escena } | null>(null);
  // Lo ya levantado (vista, preparación y SMILES): volver a mostrar el visor no lo recalcula ni lo vuelve a levantar.
  const cargadoPara = useRef<string | null>(null);
  // SMILES en pantalla: cambiar de vista con la misma molécula conserva el giro.
  const smilesMostrado = useRef<string | null>(null);
  const [vista, setVista] = useState<VistaDelEditor>("escrita");
  const ph = preparacion?.ph, tautomero = preparacion?.tautomero;
  const opciones = useMemo<OpcionesDelEditor>(
    () => ({
      vista,
      preparacion: ph !== undefined && tautomero !== undefined ? { ph, tautomero } : undefined,
      molfile: molfile ?? null,
    }),
    [vista, ph, tautomero, molfile],
  );
  const anim = useRef({ R: IDENTIDAD as Matriz, s: 0, meta: 1, ultimo: 0, frame: 0, visible: true, arrastre: null as null | { x: number; y: number } });
  const [carga, setCarga] = useState<Carga>({ tipo: "vacio" });
  const [girando, setGirando] = useState(() => !prefiereMenosMovimiento());
  const girandoRef = useRef(girando);
  girandoRef.current = girando;

  const dibujar = useCallback(() => {
    const d = datos.current, svg = svgRef.current;
    if (!d || !svg) return;
    const a = anim.current;
    svg.innerHTML = pintar(d.modelo, d.escena, proyectar(d.modelo, d.escena, a.R, suavizar(a.s)));
  }, []);

  const paso = useCallback((ahora: number) => {
    const a = anim.current;
    a.frame = 0;
    if (!datos.current || !a.visible) return;
    const dt = a.ultimo ? Math.min(64, ahora - a.ultimo) : 16;
    a.ultimo = ahora;
    if (a.s < a.meta) a.s = Math.min(a.meta, a.s + dt / SUBIDA_MS);
    else if (a.s > a.meta) a.s = Math.max(a.meta, a.s - dt / BAJADA_MS);
    const gira = girandoRef.current && a.meta > 0 && !a.arrastre;
    if (gira) a.R = multiplicar(rotY((dt / VUELTA_MS) * 2 * Math.PI), a.R);
    dibujar();
    // Quieto y en su sitio: no hay nada que pintar hasta el próximo gesto.
    if (gira || a.s !== a.meta) a.frame = requestAnimationFrame(paso);
    else a.ultimo = 0;
  }, [dibujar]);

  const arrancar = useCallback(() => {
    const a = anim.current;
    if (!a.frame && a.visible) {
      a.ultimo = 0;
      a.frame = requestAnimationFrame(paso);
    }
  }, [paso]);

  // El conformador del SMILES actual, con una espera corta: dibujar en Ketcher
  // y volver no dispara un cálculo por cada trazo. Oculto, no calcula: lo pide
  // al mostrarse. Una molécula ya levantada no vuelve a levantarse al volver.
  useEffect(() => {
    const limpio = smiles.trim();
    if (!limpio) {
      cargadoPara.current = null;
      smilesMostrado.current = null;
      datos.current = null;
      setCarga({ tipo: "vacio" });
      return;
    }
    const clave = `${opciones.vista}|${opciones.preparacion?.ph ?? ""}|${opciones.preparacion?.tautomero ?? ""}|${limpio}|${opciones.molfile ?? ""}`;
    if (cargadoPara.current === clave) return;
    if (!activo) return;
    const mostrar = (modelo: ModeloElevacion) => {
      datos.current = { modelo, escena: prepararEscena(modelo) };
      // Una respuesta provisional no cuenta como cargada: si el efecto se repite, se completa.
      if (!modelo.abstencion_provisional) cargadoPara.current = clave;
      const a = anim.current;
      if (smilesMostrado.current !== limpio) {
        a.R = multiplicar(rotX(0.35), IDENTIDAD);
        // Sin levantar, la vista empieza ya en 3D: no se anima un paso que el dibujo no sostiene.
        a.s = modelo.fiel ? 0 : 1;
        a.meta = 1;
      } else if (!modelo.fiel) {
        a.s = a.meta = 1;
      }
      smilesMostrado.current = limpio;
      setCarga({ tipo: "listo", modelo });
    };
    const enCache = modeloDelEditorEnCache(limpio, opciones);
    if (enCache) {
      mostrar(enCache);
      return;
    }
    const control = new AbortController();
    setCarga({ tipo: "cargando" });
    // «Escrita» por etapas: una semilla enseguida y las tres después. «Se acoplará»
    // es un solo conformador y llega de una vez.
    const pedir = async () => {
      if (opciones.vista !== "acoplada") {
        const rapido = await elevacionDelEditor(limpio, control.signal, { ...opciones, rapida: true });
        if (control.signal.aborted) return;
        mostrar(rapido);
      }
      const completo = await elevacionDelEditor(limpio, control.signal, opciones);
      if (!control.signal.aborted) mostrar(completo);
    };
    const espera = setTimeout(() => {
      pedir().catch((error) => {
        if (control.signal.aborted) return;
        if (datos.current && smilesMostrado.current === limpio) return; // queda lo provisional a la vista
        datos.current = null;
        setCarga({ tipo: "error", detalle: error instanceof ErrorDeElevacion ? presentError(error, t) : String(error) });
      });
    }, ESPERA_MS);
    return () => { clearTimeout(espera); control.abort(); };
  }, [smiles, activo, opciones, t]);

  useEffect(() => {
    if (carga.tipo !== "listo") return;
    dibujar();
    arrancar();
  }, [carga, dibujar, arrancar]);

  useEffect(() => { if (girando) arrancar(); }, [girando, arrancar]);

  // Oculto por la pestaña (display:none) o fuera de pantalla: se para.
  useEffect(() => {
    const caja = cajaRef.current;
    if (!caja || typeof IntersectionObserver === "undefined") return;
    const observador = new IntersectionObserver(([entrada]) => {
      anim.current.visible = entrada.isIntersecting;
      if (entrada.isIntersecting) arrancar();
    });
    observador.observe(caja);
    return () => observador.disconnect();
  }, [arrancar]);

  useEffect(() => () => {
    if (anim.current.frame) cancelAnimationFrame(anim.current.frame);
    anim.current.frame = 0;
  }, []);

  const alPresionar = (e: React.PointerEvent) => {
    if (carga.tipo !== "listo") return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    anim.current.arrastre = { x: e.clientX, y: e.clientY };
    anim.current.meta = 1;
    arrancar();
  };
  const alMover = (e: React.PointerEvent) => {
    const a = anim.current;
    if (!a.arrastre) return;
    const dx = e.clientX - a.arrastre.x, dy = e.clientY - a.arrastre.y;
    a.arrastre = { x: e.clientX, y: e.clientY };
    a.R = multiplicar(multiplicar(rotY(dx * 0.01), rotX(dy * 0.01)), a.R);
    if (a.s >= a.meta) dibujar();
    else arrancar();
  };
  const alSoltar = () => {
    anim.current.arrastre = null;
    if (girandoRef.current) arrancar();
  };

  /** Vuelve al dibujo plano; girar o arrastrar lo levanta otra vez. */
  const aPlano = () => {
    anim.current.meta = 0;
    setGirando(false);
    arrancar();
  };

  const alternarGiro = () => {
    if (!girando) anim.current.meta = 1;
    setGirando(!girando);
  };

  const modelo = carga.tipo === "listo" ? carga.modelo : null;
  const especie = modelo?.especie_acoplada;
  const nombre = (i: number) => (modelo ? `${modelo.atomos[i]?.elemento ?? "?"}${i + 1}` : "");
  const carga_ = (c: number) => (c > 0 ? `+${c}` : c < 0 ? `−${-c}` : "0");
  const orden = (o: number) => (o === 1.5 ? t("el_orden_aromatico") : String(o));
  // Lo que la preparación cambió, una línea por átomo o enlace.
  const lineasDeCambio = especie
    ? [
        ...especie.cambios.atomos.map((c) => t("el_cambio_atomo", {
          atomo: nombre(c.atomo), carga_antes: carga_(c.carga[0]), carga_despues: carga_(c.carga[1]),
          h_antes: String(c.hidrogenos[0]), h_despues: String(c.hidrogenos[1]),
        })),
        ...especie.cambios.enlaces.map((c) => t("el_cambio_enlace", {
          a: nombre(c.a), b: nombre(c.b), antes: orden(c.orden[0]), despues: orden(c.orden[1]),
        })),
        ...(especie.estereo.sin_declarar.length
          ? [t("el_estereo_fijada", { atomos: especie.estereo.sin_declarar.map(nombre).join(", ") })] : []),
        ...(especie.contraiones.length ? [t("el_contraiones", { lista: especie.contraiones.join(", ") })] : []),
        ...(especie.aviso_de_ph ? [especie.aviso_de_ph] : []),
      ]
    : [];
  const sinCambios = especie && !especie.cambios.atomos.length && !especie.cambios.enlaces.length;
  const atomos = (indices: number[]) => indices.map(nombre).join(", ");
  const textoDeDetector = (d: NonNullable<ModeloElevacion["detectores"]>[number]) => {
    if (d.tipo === "ojiva") return t("el_det_ojiva", { nombre: d.nombre, atomos: atomos(d.atomos) });
    if (d.tipo === "pains") return t("el_det_pains", { nombre: d.nombre, atomos: atomos(d.atomos) });
    // Un motivo nuevo del backend sin texto propio se dice con el suyo.
    const clave = `el_det_${d.codigo}`;
    const texto = t(clave, { atomos: atomos(d.atomos) });
    return texto === clave ? `${d.nombre} (${atomos(d.atomos)})` : texto;
  };
  const deltaE = modelo?.conformador?.delta_e_kcal_mol;
  const geometria = modelo?.geometria;
  // Lo que el modelo implica, una línea cada cosa.
  const notas = modelo
    ? [
        ...(modelo.abstencion_provisional ? [t("el_provisional")] : []),
        ...(modelo.dibujo?.motivo ? [t("el_dibujo_rdkit")] : []),
        ...(modelo.detectores ?? []).map(textoDeDetector),
        ...(geometria?.plana ? [t("el_plana", { espesor: formatoDeNumero(geometria.espesor_A ?? 0, locale) })] : []),
        ...(geometria?.macrociclos.length ? [t("el_macrociclo", { tamanos: geometria.macrociclos.join(", ") })] : []),
        ...(geometria?.anillos_rigidos_grandes.length
          ? [t("el_anillo_rigido", { tamanos: geometria.anillos_rigidos_grandes.join(", ") })] : []),
        ...(vista === "escrita" && typeof deltaE === "number"
          ? [t(deltaE > DELTA_E_AVISO ? "el_delta_e_alto" : "el_delta_e", {
              valor: formatoDeNumero(deltaE, locale), campo: modelo.conformador?.campo_de_fuerza ?? "",
            })]
          : []),
      ]
    : [];

  return (
    <div
      ref={cajaRef}
      className={activo ? "absolute inset-0 z-10 flex flex-col bg-white" : "hidden"}
      data-testid="visor-elevacion"
    >
      <div className="flex items-start justify-between gap-2 border-b border-zinc-200 px-3 py-2">
        <p className="text-xs leading-5 text-zinc-600">
          {vista === "acoplada" ? (
            <>
              <strong className="font-semibold text-zinc-900">{t("el_acoplada_titulo")}</strong>{" "}
              {especie && t("el_acoplada_nota", {
                ph: especie.ph === null ? "—" : formatoDeNumero(especie.ph, locale),
                modo: especie.tautomero.modo === "canonico" ? t("el_tautomero_canonico") : t("el_tautomero_entrada"),
                semilla: String(especie.conformador.semilla ?? "—"),
              })}
            </>
          ) : (
            <>
              <strong className="font-semibold text-zinc-900">{t("el_conformador_titulo")}</strong>{" "}
              {modelo?.conformador
                ? t("el_conformador_nota", { campo: modelo.conformador.campo_de_fuerza })
                : t("el_conformador_nota", { campo: "MMFF94" })}
            </>
          )}
          {modelo && !modelo.fiel && <> {t("el_no_fiel_editor")}</>}
        </p>
        <div role="group" aria-label={t("el_vista_grupo")} className="flex shrink-0 overflow-hidden rounded-md border border-zinc-300 text-[11px] font-medium">
          {(["escrita", "acoplada"] as const).map((opcion) => (
            <button
              key={opcion}
              type="button"
              aria-pressed={vista === opcion}
              onClick={() => setVista(opcion)}
              className={vista === opcion ? "bg-zinc-900 px-2 py-1 text-white" : "bg-white px-2 py-1 text-zinc-600 hover:bg-zinc-50"}
            >
              {opcion === "escrita" ? t("el_vista_escrita") : t("el_vista_acoplada")}
            </button>
          ))}
        </div>
      </div>
      {vista === "acoplada" && especie && (
        <ul className="max-h-24 overflow-y-auto border-b border-zinc-200 px-3 py-1.5 text-[11px] leading-5 text-zinc-700" data-testid="cambios-de-la-preparacion">
          {sinCambios && <li>{t("el_sin_cambios")}</li>}
          {lineasDeCambio.map((linea) => <li key={linea}>{linea}</li>)}
        </ul>
      )}
      {notas.length > 0 && (
        <ul className="max-h-24 overflow-y-auto border-b border-zinc-200 px-3 py-1.5 text-[11px] leading-5 text-zinc-600" data-testid="notas-del-modelo">
          {notas.map((linea) => <li key={linea}>{linea}</li>)}
        </ul>
      )}
      <div
        className="relative min-h-0 flex-1 touch-none select-none"
        style={{ cursor: modelo ? "grab" : "default" }}
        onPointerDown={alPresionar}
        onPointerMove={alMover}
        onPointerUp={alSoltar}
        onPointerCancel={alSoltar}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${modelo?.lienzo ?? 300} ${modelo?.lienzo ?? 300}`}
          className="absolute inset-0 size-full"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={t("el_conformador_titulo")}
          style={{ display: modelo ? "block" : "none" }}
        />
        {carga.tipo !== "listo" && (
          <div className="absolute inset-0 flex items-center justify-center p-8 text-center text-sm text-zinc-500">
            {carga.tipo === "cargando" && (
              <span className="flex items-center gap-3">
                <span className="size-4 animate-spin rounded-full border-2 border-zinc-300 border-t-transparent" />
                {vista === "acoplada" ? t("el_cargando_acoplada") : t("el_cargando")}
              </span>
            )}
            {carga.tipo === "vacio" && t("el_vacio")}
            {carga.tipo === "error" && t("el_error", { detalle: carga.detalle })}
          </div>
        )}
        {modelo && (
          <p className="pointer-events-none absolute left-3 top-3 font-mono text-[10px] uppercase tracking-[0.1em] text-zinc-400">
            {t("el_arrastrar")}
          </p>
        )}
        {modelo && (
          <p className="pointer-events-none absolute right-3 top-3 font-mono text-[10px] text-zinc-400">
            {t("el_ajuste", { px: formatoDeNumero(modelo.desajuste_px, locale), lienzo: String(modelo.lienzo) })}
          </p>
        )}
      </div>
      <div className="pointer-events-auto absolute bottom-3 right-3 z-10 flex items-center gap-2">
        {modelo && (
          <>
            <button type="button" className={VIEWER_LABEL_BUTTON_CLASS} onClick={alternarGiro} aria-pressed={girando}>
              {girando ? <Pause size={12} /> : <Play size={12} />}
              {girando ? t("el_pausar") : t("el_girar")}
            </button>
            <button type="button" className={VIEWER_LABEL_BUTTON_CLASS} onClick={aPlano}>
              <RotateCcw size={12} />
              {t("el_plano")}
            </button>
          </>
        )}
        <button
          type="button"
          onClick={onSwitchViewer}
          className={VIEWER_SWITCH_BUTTON_CLASS}
          title={t("pr_viewer_switch_to", { viewer: "Ketcher" })}
        >
          {t("pr_viewer_switch_label", { viewer: "Ketcher" })}
        </button>
      </div>
    </div>
  );
}
