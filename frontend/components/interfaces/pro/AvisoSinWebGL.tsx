"use client";


import { useLanguage } from "@/context/LanguageContext";
import { AlertTriangle, Cpu } from "lucide-react";

import { comprobarWebGL } from "../../../lib/webgl";

/**
 * Aviso propio cuando el equipo no puede dibujar en 3D.
 *
 * Sustituye al visor: si no existe contexto, Mol* no debe montarse ni pintar su
 * mensaje interno. Lo que añade este aviso es lo que la librería no puede saber
 * — qué parte de MolDesign sigue siendo válida.
 *
 * Eso es lo que de verdad necesita quien lo ve. El mensaje de Mol* habla de
 * navegadores desactualizados y de «bad weather» a alguien que está usando una
 * aplicación de escritorio, y deja sin responder la única pregunta que importa:
 * ¿acabo de perder la corrida?
 */
export function AvisoSinWebGL({ forzar = false }: { readonly forzar?: boolean }) {
  const { t } = useLanguage();
  const estado = comprobarWebGL();
  if (estado.disponible && !forzar) return null;

  // Dos situaciones distintas, y decirlas iguales sería mentir en una de ellas:
  //
  //   · no hay contexto      la máquina no expone 3D en absoluto
  //   · hay contexto y falló Mol* no pudo usarlo aunque exista; puede que el
  //                          visor ligero sí funcione, y conviene decirlo
  const hayContexto = estado.disponible;

  return (
    <div
      role="status"
      className="mx-4 flex max-w-2xl items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2"
    >
      <AlertTriangle size={14} className="mt-0.5 flex-shrink-0 text-amber-400" />
      <div className="text-[11px] leading-relaxed text-amber-200/90">
        <span className="font-semibold">
          {hayContexto
            ? t("auto_4356059ccdf0")
            : t("auto_f772d2e3af48")}
        </span>{" "}
        {hayContexto
          ? t("auto_248db3e9f594")
          : estado.motivo}
        <div className="mt-1 text-amber-200/70">
          <span className="font-semibold">{t("pn_evaluacion_no_afectada")}</span> {t("pn_sin_webgl")}
        </div>
        <div className="mt-1 text-amber-200/50">
          {hayContexto
            ? t("auto_129ae70d08f8")
            : t("auto_f459de5d43b3")}
        </div>
      </div>
    </div>
  );
}

/**
 * Nota discreta cuando el 3D lo dibuja el procesador, no una tarjeta.
 *
 * NO bloquea nada, y por eso es una nota y no un aviso. Medido en la misma
 * máquina con y sin aceleración por hardware, Mol* queda listo en 1 072 ms
 * contra 1 260 ms, y las extensiones que necesita están en los dos casos. Lo
 * que cambia de verdad es girar una escena grande: eso sí se arrastra, y quien
 * lo sufre merece saber por qué antes de pensar que la aplicación está rota.
 */
export function NotaRenderPorSoftware() {
  const { t } = useLanguage();
  const estado = comprobarWebGL();
  if (!estado.disponible || estado.aceleracion !== "software") return null;

  return (
    <div
      role="status"
      className="pointer-events-none absolute bottom-2 left-2 z-10 flex items-center gap-1.5 rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[10px] leading-none text-sky-200/80"
      title={estado.renderer ?? undefined}
    >
      <Cpu size={11} className="flex-shrink-0" aria-hidden="true" />
      <span>{t("pn_3d_software")}</span>
    </div>
  );
}
