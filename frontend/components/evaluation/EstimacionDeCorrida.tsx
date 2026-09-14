"use client";

// =====================================================================
// Cuánto va a tardar — dicho ANTES de pulsar «Evaluar»
// =====================================================================
//
// POR QUÉ AQUÍ Y NO EN AJUSTES. La pregunta «¿cuánto tarda esto?» se hace justo
// antes de pulsar, no al configurar. Un estimador escondido en un panel de
// opciones es un estimador que nadie lee: el que había —`/hardware/estimate`,
// en `ProConfigPanel`— llevaba meses sin que ningún componente lo importara.
//
// TRES REGLAS DE PRESENTACIÓN, y ninguna es estética:
//
//   1. RANGO, NUNCA UN NÚMERO. Un tiempo exacto es una promesa, y esto no
//      puede prometer: depende de la máquina, del ligando y de la suerte del
//      muestreo. Un rango ancho es honesto; un número clavado y equivocado
//      contradice lo único que este producto vende, que es saber cuándo no
//      fiarse.
//
//   2. SE DICE EN QUÉ SE APOYA. «Calibrado con 7 corridas de este equipo» y
//      «medido en otra máquina» no valen lo mismo y no pueden verse igual.
//
//   3. LOS AVISOS MANDAN SOBRE EL NÚMERO. Que un acoplamiento vaya a superar el
//      límite de 600 s no es una estimación lenta: es una corrida que va a
//      fallar, y eso se lee antes que ninguna cifra.
//
// NO BLOQUEA NADA. Si el motor no contesta, este panel desaparece en silencio:
// no saber cuánto tarda no es motivo para impedir evaluar.

import { useEffect, useState } from "react";
import { Clock, TriangleAlert } from "lucide-react";

import { estimarCorrida, type EstimacionDeCorrida as Estimacion } from "../../lib/api";

export interface EstimacionDeCorridaProps {
  readonly exhaustiveness: number;
  readonly conformers?: number;
  readonly targetPdbId?: string;
  readonly gridSize?: readonly [number, number, number];
  readonly antiTargets?: number;
  readonly mmgbsa?: boolean;
  /** Cuántos ligandos. 1 en Evaluación; N en una cohorte de Batch. */
  readonly ligandos?: number;
  /** Se oculta mientras no haya nada que evaluar. */
  readonly visible?: boolean;
}

/** `95 s` → `1 min 35 s`. Un número de cuatro cifras en segundos no se lee. */
export function formatearDuracion(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const minutos = Math.floor(s / 60);
  if (minutos < 60) {
    const resto = s % 60;
    return resto === 0 ? `${minutos} min` : `${minutos} min ${resto} s`;
  }
  const horas = Math.floor(minutos / 60);
  const restoMin = minutos % 60;
  return restoMin === 0 ? `${horas} h` : `${horas} h ${restoMin} min`;
}

export function EstimacionDeCorrida({
  exhaustiveness,
  conformers,
  targetPdbId,
  gridSize,
  antiTargets,
  mmgbsa,
  ligandos,
  visible = true,
}: EstimacionDeCorridaProps) {
  const [estimacion, setEstimacion] = useState<Estimacion | null>(null);

  // La clave de las dependencias se serializa: `gridSize` es un array nuevo en
  // cada render del padre y volvería a pedir la estimación en cada tecla.
  const clave = JSON.stringify([
    exhaustiveness, conformers, targetPdbId, gridSize, antiTargets, mmgbsa, ligandos,
  ]);

  useEffect(() => {
    if (!visible) return;
    let vivo = true;
    estimarCorrida({
      exhaustiveness,
      conformers,
      targetPdbId,
      gridSize,
      antiTargets,
      mmgbsa,
      ligandos,
    })
      .then((e) => vivo && setEstimacion(e))
      // El motor no está o no sabe estimar. No es un error del usuario y no
      // impide evaluar: el panel simplemente no aparece.
      .catch(() => vivo && setEstimacion(null));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, visible]);

  if (!visible || !estimacion) return null;

  const { segundos_min, segundos_max, apoyo, detalle_apoyo, etapas, una_vez, avisos } = estimacion;
  const calibrado = apoyo === "historial";

  return (
    <div className="w-full max-w-[1600px] rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Clock size={14} className="shrink-0 self-center text-purple-400" aria-hidden="true" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-500">
          {(estimacion.ligandos ?? 1) > 1 ? "Duración estimada de la cohorte" : "Duración estimada"}
        </span>
        <span className="font-mono text-sm font-bold text-zinc-100">
          {formatearDuracion(segundos_min)} – {formatearDuracion(segundos_max)}
        </span>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
            calibrado
              ? "border-emerald-500/30 bg-emerald-500/[0.07] text-emerald-200"
              : "border-zinc-700 bg-zinc-900 text-zinc-400"
          }`}
        >
          {calibrado ? "Calibrado con tu equipo" : "Sin historial todavía"}
        </span>
      </div>

      <p className="mt-1 text-sm leading-6 text-zinc-500">{detalle_apoyo}</p>

      {/* El coste de UNA vez va aparte y en su propio tono: no es que la
          aplicación sea lenta, es que este receptor todavía no está preparado.
          Confundir las dos cosas es lo que hace que una primera corrida
          parezca rota al lado de la segunda. */}
      {una_vez && (
        <p className="mt-2 rounded-lg border border-purple-500/20 bg-purple-500/[0.04] px-3 py-2 text-sm leading-6 text-purple-100/90">
          <span className="font-bold">Sólo esta primera vez: </span>
          {una_vez.nota} Añade entre {formatearDuracion(una_vez.segundos_min)} y{" "}
          {formatearDuracion(una_vez.segundos_max)}.
        </p>
      )}

      {avisos.map((aviso) => (
        <p
          key={aviso}
          role="alert"
          className="mt-2 flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] px-3 py-2 text-sm leading-6 text-amber-100"
        >
          <TriangleAlert size={14} className="mt-1 shrink-0 text-amber-300" aria-hidden="true" />
          {aviso}
        </p>
      ))}

      <details className="group mt-2">
        <summary className="cursor-pointer list-none font-mono text-[10px] font-bold uppercase tracking-wider text-zinc-500 hover:text-zinc-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400">
          De qué se compone
        </summary>
        <ul className="mt-1.5 space-y-1">
          {etapas.map((etapa) => (
            <li key={etapa.etapa} className="flex flex-wrap items-baseline gap-x-2 text-sm leading-6">
              <span className="text-zinc-300">{etapa.etapa}</span>
              <span className="font-mono text-xs text-zinc-400">
                {formatearDuracion(etapa.segundos_min)} – {formatearDuracion(etapa.segundos_max)}
              </span>
              <span className="w-full text-xs text-zinc-500 sm:w-auto">{etapa.nota}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

export default EstimacionDeCorrida;
