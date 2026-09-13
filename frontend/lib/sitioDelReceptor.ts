// =====================================================================
// Composición del sitio de unión: qué cadenas lo forman y con qué evidencia
// =====================================================================
//
// El catálogo declara `chain`: la cadena que se PREPARA. El doc 71 midió que
// eso no es lo mismo que las cadenas que FORMAN el sitio, y que confundirlas
// producía dockings contra media cavidad —o contra ninguna—. El backend anota
// ahora las dos cosas por separado (`site_chains`, `site_evidence`) y esta
// función traduce ese hecho medido a lo que ve el investigador.
//
// Tres decisiones de presentación, y por qué:
//
//   1. Se nombran las cadenas, no se cuentan. Un biólogo escribe «cadena A» o
//      «interfaz A·B»; no existe una palabra genérica para «varias». Y la R de
//      7E2Y no significa «receptor»: es el identificador que le puso quien
//      depositó la estructura, igual que la A de los otros 325.
//
//   2. La distinción que importa es UNA cadena contra MÁS DE UNA, no 1/2/3.
//      Es la que cambia si el ligando acopla contra el bolsillo entero.
//
//   3. El color se reserva para cuando cambia el número que el usuario va a
//      leer. Que 286 receptores digan «Cadena A» en gris no cuesta nada; que
//      todos griten no informa de nada.
//
import type { Target } from "./api";

export type TonoDelSitio = "neutro" | "aviso" | "sin_medir";

export interface SitioDelReceptor {
  /** Lo que se imprime en el chip. */
  etiqueta: string;
  tono: TonoDelSitio;
  /** El `title` del chip: la evidencia, en la lengua del usuario. */
  detalle: string;
  /** El sitio lo forma más de una cadena y sólo se prepara una. */
  interfazNoPreparada: boolean;
}

/** Cuántas cadenas se nombran antes de pasar a contarlas. */
const MAX_CADENAS_NOMBRADAS = 3;

function frase(cadenas: string[]): string {
  if (cadenas.length === 1) return `Cadena ${cadenas[0]}`;
  if (cadenas.length <= MAX_CADENAS_NOMBRADAS) return `Interfaz ${cadenas.join("·")}`;
  return `Interfaz de ${cadenas.length} cadenas`;
}

/**
 * Traduce la anotación del sitio a chip. Devuelve `null` sólo cuando no hay
 * NADA que decir; ausencia de medida es una respuesta, no un vacío.
 */
export function describirSitio(target: Pick<Target,
  "site_chains" | "site_chain_atoms" | "site_evidence" | "site_ligand" | "chain">
): SitioDelReceptor {
  const cadenas = (target.site_chains ?? []).filter(Boolean);

  if (cadenas.length === 0) {
    // No es lo mismo «no lo hemos medido» que «es una sola cadena». Un
    // receptor subido por el usuario, o anterior al campo, cae aquí y debe
    // decirlo: suponer monómero es justo el error que documenta el doc 71.
    return {
      etiqueta: "Sitio sin medir",
      tono: "sin_medir",
      detalle: "No hemos medido qué cadenas forman el sitio de este receptor. "
        + "El docking preparará sólo la cadena declarada.",
      interfazNoPreparada: false,
    };
  }

  const preparada = (target.chain ?? "").trim().toUpperCase();
  const interfaz = cadenas.length > 1;
  const interfazNoPreparada = interfaz && preparada.length > 0;

  const conLigando = target.site_evidence === "cocrystal_ligand";
  const evidencia = conLigando
    ? `Medido por contacto con el ligando co-cristalizado${target.site_ligand ? ` (${target.site_ligand})` : ""}, a 4,5 Å o menos.`
    : "Sin ligando co-cristalizado: las cadenas del sitio se dedujeron del volumen dentro de la caja de docking, "
      + "que no distingue el bolsillo de la vecindad.";

  const reparto = target.site_chain_atoms
    ? " Aporte de cada cadena: "
      + Object.entries(target.site_chain_atoms)
        .map(([c, n]) => `${c} ${n}`)
        .join(", ") + " átomos."
    : "";

  const consecuencia = interfazNoPreparada
    ? ` El sitio lo forman ${cadenas.length} cadenas y la preparación conserva sólo '${preparada}': `
      + "el ligando acoplará contra parte de la cavidad."
    : "";

  return {
    etiqueta: frase(cadenas),
    // El aviso es por la interfaz sin preparar, que cambia el número. La
    // evidencia débil se dice en el texto, no en el color: es una advertencia
    // sobre cuánto confiar en la anotación, no sobre el resultado.
    tono: interfazNoPreparada ? "aviso" : "neutro",
    detalle: evidencia + reparto + consecuencia,
    interfazNoPreparada,
  };
}

/**
 * Procedencia de los hotspots. NINGUNO viene del RCSB: los generó este
 * repositorio, y el usuario tiene derecho a saberlo antes de leer un dossier
 * que nombra residuos.
 *
 * El chip visible se reserva para los rederivados —los que cambiamos nosotros
 * después de medir que los heredados describían otro bolsillo—, porque es ahí
 * donde la anotación difiere de la que el receptor traía. Que los demás
 * tampoco sean oficiales se dice en el texto, para los 385, en vez de poner
 * una etiqueta idéntica en cada tarjeta que nadie leería después de la tercera.
 */
export function describirHotspots(target: Pick<Target, "hotspots_source" | "site_ligand">): {
  etiqueta: string | null;
  detalle: string;
} {
  const comun = "Ningún hotspot de este catálogo procede del RCSB: los deriva MolDesign de la estructura.";
  if (target.hotspots_source === "box_ligand_contacts") {
    return {
      etiqueta: "Hotspots re-derivados",
      detalle: comun
        + ` Los de este receptor se rederivaron a partir del ligando que ocupa la caja de docking`
        + `${target.site_ligand ? ` (${target.site_ligand})` : ""}, tomando los residuos a 4,5 Å o menos,`
        + " porque los anteriores describían otro bolsillo de la misma proteína.",
    };
  }
  if (target.hotspots_source === "auto_pocket_top15") {
    return {
      etiqueta: null,
      detalle: comun + " Los de este receptor son los 15 residuos más cercanos al ligando"
        + " co-cristalizado que la detección automática encontró en la estructura.",
    };
  }
  return { etiqueta: null, detalle: comun + " La procedencia de los de este receptor no está registrada." };
}

/** El chip corto de evidencia, sólo cuando hay algo que advertir. */
export function avisoDeEvidencia(target: Pick<Target, "site_evidence">): string | null {
  if (target.site_evidence === "box_volume") return "Sin ligando co-cristalizado";
  return null;
}
