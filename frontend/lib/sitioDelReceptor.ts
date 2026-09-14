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

// ── La explicación larga, para quien acaba de llegar ─────────────────
//
// POR QUÉ HACE FALTA. Todo lo que este archivo sabe de un receptor cabía en el
// atributo `title` de un chip de 10 px. Un tooltip nativo exige acertarle con el
// ratón y esperar, NO existe en táctil, y como el chip es un `<span>` sin foco,
// con teclado no se alcanza nunca. La frase que más importa —«el ligando
// acoplará contra parte de la cavidad»— estaba enterrada ahí, y le aplica a 110
// de los 380 receptores del catálogo.
//
// QUÉ CAMBIA Y QUÉ NO. El chip corto sigue igual: quien ya sabe lo que es una
// interfaz no necesita leer un párrafo cada vez. Lo que se añade es poder
// ABRIRLO. La versión larga no dice nada que la corta calle; dice lo mismo
// despacio, y responde la pregunta anterior —qué es una cadena— que la corta da
// por sabida.
//
// NO SE INVENTA NADA. Cada frase sale de un campo medido del catálogo:
// `site_chains` y `site_chain_atoms` los mide `expediente_de_receptores.py`
// sobre el PDB del RCSB, `site_evidence` declara con qué, y `hotspots_source`
// de dónde salieron los residuos. Cuando un campo falta, la sección lo dice en
// vez de rellenarlo: 109 de los 380 no tienen ligando co-cristalizado y eso es
// justamente lo que hay que contarle al usuario, no taparlo.

export interface SeccionDelSitio {
  /** El encabezado, escrito como la pregunta que responde. */
  readonly pregunta: string;
  readonly respuesta: string;
  /** `aviso` SÓLO para lo que cambia el número que el usuario va a leer. */
  readonly tono?: "aviso";
}

export interface ExplicacionDelSitio {
  /** Una línea en lenguaje llano. Lo primero que se ve al abrir. */
  readonly titular: string;
  readonly secciones: readonly SeccionDelSitio[];
}

/** Lista legible: «A y B», «A, B y C». Nunca «A,B». */
function enumerar(cadenas: readonly string[]): string {
  if (cadenas.length <= 1) return cadenas[0] ?? "";
  return `${cadenas.slice(0, -1).join(", ")} y ${cadenas[cadenas.length - 1]}`;
}

/**
 * Qué significa un número de resolución, para quien no ha leído uno antes.
 *
 * Es contraintuitivo —menos es mejor— y nadie lo adivina. Los cortes son los
 * de uso común en cristalografía; se dan como orientación, no como umbral de
 * decisión, porque este producto no rechaza un receptor por su resolución.
 */
function calidadDeLaEstructura(resolucion: number): string {
  if (resolucion <= 1.5) return "muy detallada";
  if (resolucion <= 2.5) return "de buen detalle";
  if (resolucion <= 3.0) return "de detalle moderado";
  return "de poco detalle";
}

/**
 * La versión larga y amable de lo que ya dicen los chips.
 *
 * El orden de las secciones es deliberado: primero qué se va a usar, luego la
 * consecuencia si la hay —antes que la evidencia, porque es lo que cambia una
 * decisión—, después de dónde sale lo que afirmamos, y al final la identidad de
 * la estructura.
 */
export function explicarSitio(target: Pick<Target,
  "pdb_id" | "name" | "organism" | "resolution" | "chain" | "site_chains"
  | "site_chain_atoms" | "site_evidence" | "site_ligand" | "hotspots" | "hotspots_source">
): ExplicacionDelSitio {
  const cadenas = (target.site_chains ?? []).filter(Boolean);
  const preparada = (target.chain ?? "").trim().toUpperCase();
  const secciones: SeccionDelSitio[] = [];

  // ── 1. Qué parte de la proteína entra en juego ───────────────────
  const queEsUnaCadena =
    "Una proteína puede estar hecha de varias piezas, llamadas cadenas, y cada una "
    + "se nombra con una letra. ";

  let titular: string;
  if (cadenas.length === 0) {
    titular = "No hemos medido qué parte de esta proteína forma el sitio de unión.";
    secciones.push({
      pregunta: "¿Qué parte de la proteína se va a usar?",
      respuesta: queEsUnaCadena
        + "En este receptor no lo hemos medido: puede que lo subieras tú, o que sea "
        + "anterior a que empezáramos a anotarlo. "
        + (preparada
          ? `El acoplamiento preparará la cadena '${preparada}', que es la que declara el receptor, `
            + "pero no podemos afirmar que sea la única que forma el hueco."
          : "El acoplamiento preparará la cadena que declare el receptor."),
      tono: "aviso",
    });
  } else if (cadenas.length === 1) {
    titular = `El sitio de unión está dentro de una sola cadena, la ${cadenas[0]}.`;
    secciones.push({
      pregunta: "¿Qué parte de la proteína se va a usar?",
      respuesta: queEsUnaCadena
        + `Aquí el hueco donde encaja el ligando está entero dentro de una sola cadena, la '${cadenas[0]}'. `
        + "Es el caso más sencillo: se prepara esa cadena y el ligando ve el bolsillo completo.",
    });
  } else {
    const atomos = target.site_chain_atoms ?? null;
    const reparto = atomos
      ? " Cada una pone parte de la pared del hueco: "
        + Object.entries(atomos).map(([c, n]) => `la '${c}' aporta ${n} átomos`).join(", ")
        + "."
      : "";
    titular = cadenas.length <= 3
      ? `El sitio de unión está en la juntura entre ${cadenas.length} cadenas: ${enumerar(cadenas)}.`
      : `El sitio de unión lo forman ${cadenas.length} cadenas a la vez.`;
    secciones.push({
      pregunta: "¿Qué parte de la proteína se va a usar?",
      respuesta: queEsUnaCadena
        + `En este receptor el hueco NO está dentro de una sola: se forma en la juntura entre ${cadenas.length}`
        + (cadenas.length <= 3 ? ` (${enumerar(cadenas)})` : "")
        + ". A esa juntura la llamamos interfaz."
        + reparto,
    });
  }

  // ── 2. La consecuencia, si la hay. Va antes que la evidencia ─────
  //
  // Es lo único de esta explicación que puede cambiar una decisión, así que no
  // se entierra detrás de dos párrafos de procedencia.
  if (cadenas.length > 1 && preparada.length > 0) {
    secciones.push({
      pregunta: "¿Qué significa esto para tu resultado?",
      respuesta:
        `La preparación de este receptor conserva sólo la cadena '${preparada}'. `
        + "Como el hueco lo forman varias, el ligando se acoplará contra PARTE de la "
        + "cavidad, no contra el bolsillo entero. La afinidad que obtengas describe esa "
        + "cavidad incompleta: sigue siendo útil para comparar moléculas entre sí en este "
        + "mismo receptor, pero no la compares con la de un receptor donde el sitio sí "
        + "está completo.",
      tono: "aviso",
    });
  }

  // ── 3. Con qué evidencia lo afirmamos ────────────────────────────
  if (target.site_evidence === "cocrystal_ligand") {
    secciones.push({
      pregunta: "¿Cómo lo sabemos?",
      respuesta:
        "Esta estructura se depositó con una molécula ya encajada en el hueco"
        + (target.site_ligand ? ` (el código '${target.site_ligand}')` : "")
        + ". Eso señala el sitio directamente: miramos qué cadenas tienen átomos a 4,5 Å "
        + "o menos de ella. Es la evidencia más fuerte que se puede tener sin hacer un "
        + "experimento nuevo.",
    });
  } else if (target.site_evidence === "box_volume") {
    secciones.push({
      pregunta: "¿Cómo lo sabemos?",
      respuesta:
        "Esta estructura NO trae ninguna molécula encajada en el hueco, así que no hay "
        + "nada que señale el sitio directamente. Dedujimos las cadenas mirando qué queda "
        + "dentro de la caja de acoplamiento — y eso no distingue la pared del bolsillo de "
        + "lo que simplemente pasa cerca. Es una pista razonable, no una medida.",
      tono: "aviso",
    });
  } else {
    secciones.push({
      pregunta: "¿Cómo lo sabemos?",
      respuesta:
        "Este receptor no registra con qué evidencia se anotó su sitio, así que no "
        + "podemos decirte cuánto fiarte de esa anotación.",
      tono: "aviso",
    });
  }

  // ── 4. Los residuos marcados ─────────────────────────────────────
  const cuantos = target.hotspots?.length ?? 0;
  const origen = target.hotspots_source === "box_ligand_contacts"
    ? "Los de este receptor se volvieron a derivar a partir del ligando que ocupa la caja"
      + (target.site_ligand ? ` ('${target.site_ligand}')` : "")
      + ", tomando los residuos a 4,5 Å o menos, porque los que traía describían otro "
      + "bolsillo de la misma proteína."
    : target.hotspots_source === "auto_pocket_top15"
      ? "Los de este receptor son los 15 residuos más cercanos al ligando co-cristalizado "
        + "que encontró la detección automática."
      : "La procedencia de los de este receptor no está registrada.";
  secciones.push({
    pregunta: "¿Y los residuos marcados?",
    respuesta:
      (cuantos > 0 ? `Este receptor trae ${cuantos} residuos marcados. ` : "")
      + "Son los aminoácidos que forman el bolsillo y que guían la búsqueda. "
      + "Ninguno viene del Protein Data Bank: los deriva MolDesign de la estructura, y por "
      + "eso puedes verlos y desmarcarlos. "
      + origen,
  });

  // ── 5. De qué estructura estamos hablando ────────────────────────
  const resolucion = typeof target.resolution === "number" && target.resolution > 0
    ? `Se resolvió a ${target.resolution.toFixed(1)} Å, una estructura `
      + `${calidadDeLaEstructura(target.resolution)}: en cristalografía, cuanto MENOR es ese `
      + "número, más nítidos se ven los átomos."
    : "Su resolución no está registrada.";
  secciones.push({
    pregunta: "¿De qué estructura hablamos?",
    respuesta:
      `Es la entrada '${target.pdb_id}' del Protein Data Bank, el repositorio público de `
      + "estructuras de proteínas"
      + (target.organism ? `, de ${target.organism}` : "")
      + ". " + resolucion,
  });

  return { titular, secciones };
}
