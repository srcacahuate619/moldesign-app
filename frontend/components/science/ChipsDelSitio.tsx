"use client";

// =====================================================================
// Los chips que declaran qué se sabe del sitio de unión de un receptor
// =====================================================================
//
// Viven en un componente compartido a propósito. El catálogo de receptores y la
// pestaña de Evaluación tienen que decir EXACTAMENTE lo mismo sobre el mismo
// receptor: si una superficie dice «Interfaz B·A» y la otra calla, el
// investigador no sabe cuál creer, y la que calla es la que engaña.
//
// Qué declara cada chip, en orden de importancia para quien va a leer un número:
//
//   1. Qué cadenas forman el sitio, y en ámbar cuando son varias y sólo se
//      prepara una — ahí es donde la afinidad sale de media cavidad.
//   2. Si la anotación está respaldada por un cristal o sólo por volumen.
//   3. De dónde salen los hotspots, cuando no son los que el receptor traía.
//
// Ninguno de los tres se inventa nada: los mide
// `scripts/expediente_de_receptores.py` sobre el PDB del RCSB y viajan con el
// catálogo.
//
import type { Target } from "../../lib/api";
import { describirSitio, avisoDeEvidencia, describirHotspots } from "../../lib/sitioDelReceptor";

type Props = {
  target: Pick<Target,
    "site_chains" | "site_chain_atoms" | "site_evidence" | "site_ligand" | "chain" | "hotspots_source">;
  /** `compacto` para la tarjeta del catálogo; `linea` para la barra de Evaluación. */
  variante?: "compacto" | "linea";
};

export function ChipsDelSitio({ target, variante = "compacto" }: Props) {
  const sitio = describirSitio(target);
  const aviso = avisoDeEvidencia(target);
  const hs = describirHotspots(target);
  const base = "font-mono px-2 py-0.5 rounded border whitespace-nowrap";
  const tam = variante === "linea" ? "text-[10px]" : "text-[10px]";

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span
        title={`${sitio.detalle}\n\n${hs.detalle}`}
        className={`${base} ${tam} ${
          sitio.tono === "aviso"
            ? "text-amber-300 bg-amber-950/25 border-amber-500/30"
            : sitio.tono === "sin_medir"
              ? "text-zinc-500 bg-zinc-950 border-dashed border-zinc-700"
              : "text-zinc-300 bg-zinc-950 border-zinc-800"
        }`}
      >
        {sitio.etiqueta}
      </span>

      {aviso && (
        <span
          title={sitio.detalle}
          className={`${base} ${tam} border-dashed border-zinc-700 bg-zinc-950 text-zinc-500`}
        >
          {aviso}
        </span>
      )}

      {hs.etiqueta && (
        <span
          title={hs.detalle}
          className={`${base} ${tam} border-dashed border-cyan-500/30 bg-cyan-950/15 text-cyan-200/80`}
        >
          {hs.etiqueta}
        </span>
      )}
    </div>
  );
}

export default ChipsDelSitio;
