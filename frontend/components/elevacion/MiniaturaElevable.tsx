"use client";

/* eslint-disable @next/next/no-img-element -- La URL Blob autenticada no admite optimización de Next Image. */

/**
 * La miniatura 2D de una ficha de Moldex que, al pasar el cursor, se levanta y
 * gira la pose top-1 de su corrida.
 *
 * En reposo es la imagen de siempre (`/chem/render/{id}`). El modelo 3D sólo se
 * pide al primer paso del cursor, y el bucle de animación sólo corre mientras
 * el cursor está encima o la miniatura vuelve a plano: una rejilla quieta no
 * gasta nada. Si la corrida no conserva su SDF, la ficha se queda en 2D; no se
 * sustituye por un conformador, que no sería evidencia de esa corrida.
 *
 * Si el dibujo no se corresponde con la pose (`fiel` falso), la pose se enseña
 * igual, en 3D de entrada: lo que se abstiene es la animación del dibujo a la
 * pose, no la pose, que es evidencia de la corrida (decisión del 2026-10-24: en
 * moléculas de 35 a 51 átomos pesados se abstienen 16 de 37).
 */

import { useLanguage } from "@/context/LanguageContext";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  avisosDePose,
  elevacionDeLaCorrida,
  formatoDeNumero,
  multiplicar,
  pintar,
  prefiereMenosMovimiento,
  prepararEscena,
  proyectar,
  rotX,
  rotY,
  suavizar,
  type AvisoDePose,
  type Escena,
  type ModeloElevacion,
} from "../../lib/elevacion";

/** Una vuelta cada 7 s: se lee la forma sin marear. */
const VUELTA_MS = 7000;
const SUBIDA_MS = 450;
const BAJADA_MS = 280;
/** Inclinación del eje de giro: una molécula plana nunca queda de canto. */
const INCLINACION = 0.38;

/** Carga con signo para leerla: +1, 0, −1. */
function signoDeCarga(carga: number): string {
  if (carga > 0) return `+${carga}`;
  if (carga < 0) return `−${-carga}`;
  return "0";
}

type Props = {
  moleculeId: string;
  taskId: string | null | undefined;
  imgSrc: string;
  alt: string;
};

export default function MiniaturaElevable({ moleculeId, taskId, imgSrc, alt }: Props) {
  const { t, locale } = useLanguage();
  const svgRef = useRef<SVGSVGElement>(null);
  const datos = useRef<{ modelo: ModeloElevacion; escena: Escena } | null>(null);
  const estado = useRef({ encima: false, s: 0, inicio: 0, giro: 0, ultimo: 0, frame: 0 });
  const [elevada, setElevada] = useState(false);
  const [sinPose, setSinPose] = useState(false);
  const [noFiel, setNoFiel] = useState(false);

  const detener = useCallback(() => {
    if (estado.current.frame) cancelAnimationFrame(estado.current.frame);
    estado.current.frame = 0;
  }, []);

  const paso = useCallback((ahora: number) => {
    const e = estado.current;
    const d = datos.current;
    const svg = svgRef.current;
    if (!d || !svg) { e.frame = 0; return; }
    const dt = e.ultimo ? ahora - e.ultimo : 16;
    e.ultimo = ahora;
    // Sin levantar: se pasa del dibujo a la pose (y vuelta) sin interpolar.
    const levanta = d.modelo.fiel;
    if (e.encima) {
      e.s = levanta ? Math.min(1, e.s + dt / SUBIDA_MS) : 1;
      e.giro += (dt / VUELTA_MS) * 2 * Math.PI;
    } else {
      e.s = levanta ? Math.max(0, e.s - dt / BAJADA_MS) : 0;
    }
    const s = suavizar(e.s);
    const R = multiplicar(rotX(INCLINACION * s), rotY(e.giro));
    svg.innerHTML = pintar(d.modelo, d.escena, proyectar(d.modelo, d.escena, R, s));
    if (!e.encima && e.s <= 0) {
      // De vuelta en plano: se enseña otra vez la imagen y el bucle se apaga.
      e.frame = 0;
      e.giro = 0;
      e.ultimo = 0;
      setElevada(false);
      return;
    }
    e.frame = requestAnimationFrame(paso);
  }, []);

  const arrancar = useCallback(() => {
    if (!estado.current.frame) {
      estado.current.ultimo = 0;
      estado.current.frame = requestAnimationFrame(paso);
    }
  }, [paso]);

  const entrar = useCallback(() => {
    if (sinPose || prefiereMenosMovimiento()) return;
    estado.current.encima = true;
    void elevacionDeLaCorrida(moleculeId, taskId).then((modelo) => {
      if (!modelo) { setSinPose(true); return; }
      setNoFiel(!modelo.fiel);
      if (!datos.current || datos.current.modelo !== modelo) datos.current = { modelo, escena: prepararEscena(modelo) };
      if (!estado.current.encima) return;
      setElevada(true);
      arrancar();
    });
  }, [arrancar, moleculeId, sinPose, taskId]);

  const salir = useCallback(() => {
    estado.current.encima = false;
    if (datos.current && estado.current.s > 0) arrancar();
  }, [arrancar]);

  useEffect(() => detener, [detener]);

  const modelo = datos.current?.modelo;
  const avisos = modelo ? avisosDePose(modelo) : [];
  const textoDeAviso = (aviso: AvisoDePose): string => {
    if (!modelo) return "";
    const atomos = (indices: number[]) => indices.map((i) => `${modelo.atomos[i].elemento}${i + 1}`).join(", ");
    switch (aviso.tipo) {
      case "estereo_invertido":
        return t("el_aviso_estereo_invertido", { atomos: atomos(aviso.atomos) });
      case "estereo_sin_declarar":
        return t("el_aviso_estereo_sin_declarar", { atomos: atomos(aviso.atomos) });
      case "estereo_no_verificable":
        return t("el_aviso_estereo_no_verificable", { atomos: atomos(aviso.atomos) });
      case "doble_invertido":
        return t("el_aviso_doble_invertido", {
          enlaces: aviso.enlaces.map(([a, b]) => `${modelo.atomos[a].elemento}${a + 1}=${modelo.atomos[b].elemento}${b + 1}`).join(", "),
        });
      case "validez_fisica":
        return t("el_aviso_validez_fisica", {
          veredicto: aviso.label ?? aviso.status,
          comprobaciones: aviso.comprobaciones.join(", ") || "—",
        });
      case "especie_cargada":
        return t("el_aviso_especie", {
          acoplada: signoDeCarga(aviso.carga_acoplada),
          smiles: signoDeCarga(aviso.carga_smiles),
        });
    }
  };
  // Lo que se lee al pasar el cursor: afinidad, ajuste y avisos, una línea cada uno.
  const detalle = modelo?.pose
    ? [
        modelo.pose.afinidad_kcal_mol !== null
          ? t("el_pose_afinidad", { valor: formatoDeNumero(modelo.pose.afinidad_kcal_mol, locale) })
          : null,
        t("el_ajuste", { px: formatoDeNumero(modelo.desajuste_px, locale), lienzo: String(modelo.lienzo) }),
        ...avisos.map(textoDeAviso),
        modelo.pose.contraiones?.length ? t("el_contraiones", { lista: modelo.pose.contraiones.join(", ") }) : null,
        // Un veredicto que pasa (o que no se evaluó) se dice igual: también es evidencia.
        modelo.pose.validez_fisica && !avisos.some((a) => a.tipo === "validez_fisica")
          ? t("el_validez_fisica", { veredicto: modelo.pose.validez_fisica.label ?? modelo.pose.validez_fisica.status ?? "—" })
          : null,
        modelo.pose.validez_fisica === null ? t("el_validez_fisica_sin") : null,
      ].filter((linea): linea is string => linea !== null).join("\n")
    : "";
  const titulo = sinPose
    ? t("el_sin_pose")
    : [noFiel ? t("el_no_fiel") : null, detalle || null].filter(Boolean).join("\n") || t("el_pose_titulo");

  return (
    <div
      className="relative flex size-full items-center justify-center"
      onPointerEnter={entrar}
      onPointerLeave={salir}
      title={titulo}
      data-testid="moldex-miniatura"
      data-elevada={elevada ? "true" : "false"}
    >
      <img
        src={imgSrc}
        alt={alt}
        className="max-h-full max-w-full object-contain"
        loading="lazy"
        style={{ visibility: elevada ? "hidden" : "visible" }}
      />
      <svg
        ref={svgRef}
        viewBox={`0 0 ${modelo?.lienzo ?? 300} ${modelo?.lienzo ?? 300}`}
        className="pointer-events-none absolute inset-0 size-full"
        style={{ display: elevada ? "block" : "none" }}
        role="img"
        aria-label={t("el_pose_chip")}
      />
      {elevada && (
        <span
          className={`pointer-events-none absolute bottom-0 left-0 right-0 px-0.5 text-center font-mono text-[7px] font-bold uppercase leading-[10px] tracking-[0.06em] ${
            avisos.length ? "bg-amber-100/95 text-amber-900" : "bg-white/85 text-zinc-700"
          }`}
        >
          {avisos.length ? t("el_pose_revisar") : t("el_pose_chip")}
        </span>
      )}
    </div>
  );
}
