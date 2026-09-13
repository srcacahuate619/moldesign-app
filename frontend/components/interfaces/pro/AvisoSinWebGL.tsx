"use client";

import { AlertTriangle } from "lucide-react";

import { comprobarWebGL } from "../../../lib/webgl";

/**
 * Aviso propio cuando el equipo no tiene aceleración 3D.
 *
 * Sustituye al visor: si no existe contexto, Mol* no debe montarse ni pintar su
 * mensaje interno. Lo que añade este aviso es lo que la
 * librería no puede saber — qué parte de MolDesign sigue siendo válida.
 *
 * Eso es lo que de verdad necesita quien lo ve. El mensaje de Mol* habla de
 * navegadores desactualizados y de «bad weather» a alguien que está usando una
 * aplicación de escritorio, y deja sin responder la única pregunta que importa:
 * ¿acabo de perder la corrida?
 */
export function AvisoSinWebGL() {
  const estado = comprobarWebGL();
  if (estado.disponible) return null;

  return (
    <div
      role="status"
      className="mx-4 flex max-w-2xl items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2"
    >
      <AlertTriangle size={14} className="mt-0.5 flex-shrink-0 text-amber-400" />
      <div className="text-[11px] leading-relaxed text-amber-200/90">
        <span className="font-semibold">El visor 3D no está disponible en este equipo.</span>{" "}
        {estado.motivo}
        <div className="mt-1 text-amber-200/70">
          <span className="font-semibold">Tu evaluación no se ve afectada.</span> El docking,
          el rescoring, la validez física de las poses y el dossier se calculan en el
          procesador y no dependen del visor. Lo único que no podrás hacer aquí es mirar
          la estructura en 3D; las poses se descargan y se abren en cualquier visor externo.
        </div>
        <div className="mt-1 text-amber-200/50">
          En una máquina virtual, habilitar la GPU virtualizada del hipervisor puede resolverlo.
        </div>
      </div>
    </div>
  );
}
