"use client";

// =====================================================================
// El detalle abrible del sitio de unión — para quien acaba de llegar
// =====================================================================
//
// EL FALLO QUE ARREGLA. Todo lo que sabíamos del sitio de un receptor vivía en
// el atributo `title` de un chip de 10 px. Eso exige acertarle con el ratón y
// esperar, NO existe en táctil, y como el chip es un `<span>` sin foco, con
// teclado no se alcanza nunca. La frase que más importa —«el ligando acoplará
// contra parte de la cavidad»— estaba enterrada ahí, y le aplica a 110 de los
// 380 receptores del catálogo.
//
// POR QUÉ `<details>` Y NO UN MODAL O UN POPOVER. Es el elemento que el
// navegador ya sabe abrir y cerrar: recibe foco, responde a Enter y a Espacio,
// funciona con un toque, se anuncia solo a un lector de pantalla y el buscador
// del navegador (Ctrl+F) encuentra su contenido aunque esté cerrado. Cualquier
// versión nuestra con `useState` y `div` sería peor en las cinco cosas y
// tendríamos que mantenerla.
//
// QUÉ NO HACE. No sustituye al chip corto: quien ya sabe lo que es una interfaz
// no necesita leer un párrafo cada vez que abre el catálogo. Esto es lo que
// aparece SI decides abrirlo.

import { ChevronDown, Info, TriangleAlert } from "lucide-react";

import type { Target } from "../../lib/api";
import { explicarSitio } from "../../lib/sitioDelReceptor";

type Props = {
  target: Pick<Target,
    "pdb_id" | "name" | "organism" | "resolution" | "chain" | "site_chains"
    | "site_chain_atoms" | "site_evidence" | "site_ligand" | "hotspots" | "hotspots_source">;
  /** Abierto de entrada. Para la ficha ampliada; en una tarjeta, cerrado. */
  abiertoPorDefecto?: boolean;
};

export function DetalleDelSitio({ target, abiertoPorDefecto = false }: Props) {
  const explicacion = explicarSitio(target);
  // Las secciones que advierten se cuentan para poder decirlo en el resumen:
  // quien no abra el detalle merece saber que hay algo dentro que le afecta.
  const avisos = explicacion.secciones.filter((s) => s.tono === "aviso").length;

  return (
    <details
      open={abiertoPorDefecto}
      className="group rounded-xl border border-zinc-800 bg-zinc-950/60 open:border-zinc-700"
    >
      <summary
        className="flex cursor-pointer list-none items-center gap-2 rounded-xl px-3 py-2 text-left
                   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
                   focus-visible:outline-purple-400 hover:bg-zinc-900/60"
      >
        {avisos > 0 ? (
          <TriangleAlert size={14} className="shrink-0 text-amber-300" aria-hidden="true" />
        ) : (
          <Info size={14} className="shrink-0 text-purple-400" aria-hidden="true" />
        )}
        <span className="min-w-0 flex-1 text-sm leading-5 text-zinc-200">
          {explicacion.titular}
        </span>
        <span className="shrink-0 font-mono text-[10px] font-bold uppercase tracking-wider text-zinc-500">
          Qué significa
        </span>
        <ChevronDown
          size={14}
          aria-hidden="true"
          className="shrink-0 text-zinc-500 transition-transform group-open:rotate-180"
        />
      </summary>

      <div className="space-y-3 border-t border-zinc-800 px-3 pb-3 pt-3">
        {explicacion.secciones.map((seccion) => (
          <section key={seccion.pregunta}>
            <h4
              className={`text-xs font-bold leading-5 ${
                seccion.tono === "aviso" ? "text-amber-200" : "text-zinc-200"
              }`}
            >
              {seccion.pregunta}
            </h4>
            <p
              className={`mt-0.5 text-sm leading-6 ${
                seccion.tono === "aviso" ? "text-amber-100/80" : "text-zinc-400"
              }`}
            >
              {seccion.respuesta}
            </p>
          </section>
        ))}
      </div>
    </details>
  );
}

export default DetalleDelSitio;
