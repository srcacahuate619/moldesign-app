// =====================================================================
// Soltar un visor 3Dmol de verdad, incluida la GPU
// =====================================================================
//
// EL FALLO. Los dos componentes que crean un visor 3Dmol —`MoleculeViewer3D`
// y `MoleculeTechViewer`— llamaban a `$3Dmol.createViewer` y no lo destruían
// nunca. Cada navegación entre Evaluación, Estructura e Informe dejaba un
// contexto WebGL huérfano con sus búferes de vértices vivos.
//
// Dos consecuencias, y la segunda no se ve venir mirando la memoria:
//
//   · en una máquina virtual sin GPU —donde WebView2 cae al renderizador por
//     software— el proceso pasaba de ~180 MB a más de 600 MB tras varias
//     evaluaciones seguidas;
//   · Chromium mantiene un máximo de ~16 contextos WebGL vivos. Al pasarse,
//     PIERDE el más antiguo: un visor que el usuario tenía abierto se queda en
//     negro sin ningún error en consola.
//
// `MoleculeTechViewer` además dejaba `spin("y", 0.015)` girando después de
// desmontarse: un bucle de render indefinido sobre un contexto que ya nadie
// mira, que en software rendering cuesta CPU real.
//
// POR QUÉ HACE FALTA `WEBGL_lose_context`. La build de 3Dmol que se empaqueta
// (`public/3Dmol-min.js`) no expone `destroy()`, `dispose()` ni
// `forceContextLoss()` — comprobado sobre el archivo—. `removeAllModels()` y
// compañía sí liberan la geometría, porque 3Dmol emite `dispose` por cada una y
// su renderizador responde con `deleteBuffer`; pero el CONTEXTO sobrevive hasta
// que el recolector de Chromium decide actuar, y es el contexto lo que está
// racionado. La extensión estándar es la única forma de soltarlo en el acto.

/**
 * El carbono de cada ligando cuando se superponen dos en el visor de 3Dmol (`greenCarbon` y `magentaCarbon`, cuyo
 * carbono es 0x00FF00 y 0xFF00FF en la build empaquetada). Viven aquí para que la leyenda de quien superpone pinte
 * exactamente lo que el visor dibuja, sin copiar los números a mano en cada componente.
 */
export const CARBONO_DE_LIGANDO = {
  primero: "#00ff00",
  superpuesto: "#ff00ff",
} as const;

/** El gris de un contacto que las dos poses tienen: no es de ninguna, así que no lleva el color de ningún ligando. */
export const CONTACTO_COMPARTIDO = "#a1a1aa";

/** Lo mínimo que se le pide a un contexto WebGL para soltarlo. */
type ContextoGL = { getExtension: (nombre: string) => { loseContext?: () => void } | null };

/** Un visor de 3Dmol. La build empaquetada no trae tipos. */
type Visor3Dmol = {
  spin?: (eje: string | boolean, velocidad?: number) => void;
  removeAllModels?: () => void;
  removeAllSurfaces?: () => void;
  removeAllShapes?: () => void;
  removeAllLabels?: () => void;
  /**
   * El renderizador de 3Dmol. Su contexto WebGL vive en un `OffscreenCanvas` que el visor mantiene aparte; el
   * `<canvas>` que se ve en la página sólo tiene un contexto `bitmaprenderer`, así que `lienzo.getContext("webgl")`
   * devuelve `null` aunque el visor esté dibujando.
   */
  renderer?: { getContext?: () => ContextoGL | null; isLost?: () => boolean };
  /** Observadores que 3Dmol conecta al contenedor al crearse y que él mismo no desconecta nunca. */
  divwatcher?: { disconnect?: () => void };
  intwatcher?: { disconnect?: () => void };
  /** El contenedor al que 3Dmol vuelve a mirar cuando cambia el tamaño de la ventana. */
  container?: unknown;
  resize?: () => void;
  render?: () => void;
};

/**
 * Deja el visor y su contenedor sin nada vivo detrás.
 *
 * Es seguro llamarla con `null`, con un visor a medio inicializar o dos veces:
 * cada paso va en su propio `try`, porque abandonar la limpieza a la primera
 * excepción dejaría vivo justamente lo que se quiere soltar.
 */
export function liberarVisor3D(
  contenedor: HTMLElement | null | undefined,
  visor: Visor3Dmol | null | undefined,
): void {
  // 0. Los observadores de tamaño y de visibilidad que 3Dmol deja conectados al contenedor: sin esto siguen llamando
  //    a `resize()` de un visor que ya no existe.
  try {
    visor?.divwatcher?.disconnect?.();
    visor?.intwatcher?.disconnect?.();
  } catch {
    /* no los había */
  }

  // 1. Parar la animación ANTES de tocar la escena: `spin` sigue pidiendo
  //    fotogramas, y un render sobre una escena a medio desmontar puede lanzar.
  try {
    visor?.spin?.(false);
  } catch {
    /* el visor no giraba, o ya no responde */
  }

  // 2. Soltar la geometría, que es lo que ocupa memoria de GPU.
  try {
    visor?.removeAllSurfaces?.();
    visor?.removeAllShapes?.();
    visor?.removeAllLabels?.();
    visor?.removeAllModels?.();
  } catch {
    /* un visor a medio inicializar no debe impedir el resto */
  }

  // 3. Perder el contexto. Ver arriba: es el recurso racionado. El de 3Dmol está en su renderizador (un
  //    `OffscreenCanvas`); preguntarle al `<canvas>` visible no lo encuentra y dejaba el contexto vivo para siempre,
  //    porque además 3Dmol deja un listener de `resize` en `window` que retiene el visor entero. El canvas queda como
  //    respaldo para otras builds de 3Dmol que sí dibujen en él.
  try {
    let gl: ContextoGL | null | undefined = visor?.renderer?.getContext?.();
    if (!gl) {
      const lienzo = contenedor?.querySelector("canvas");
      gl =
        (lienzo?.getContext("webgl") as ContextoGL | null) ??
        (lienzo?.getContext("experimental-webgl") as ContextoGL | null);
    }
    gl?.getExtension("WEBGL_lose_context")?.loseContext?.();
  } catch {
    /* `getContext` lanza si ya se había perdido; era el objetivo */
  }

  // 4. 3Dmol no quita su listener de `resize` de `window`: seguirá llamando a `visor.resize()` mientras la página
  //    viva. Con el contexto perdido y un contenedor con tamaño, `resize()` reconstruye el renderizador (sobre el
  //    lienzo de quien haya tomado ese contenedor después). Apuntar el visor a un contenedor suelto, sin tamaño, lo
  //    deja inerte.
  try {
    if (visor && typeof document !== "undefined") visor.container = document.createElement("div");
  } catch {
    /* sin DOM no hay listener que neutralizar */
  }

  // 5. Quitar el lienzo del DOM para que el contenedor no lo retenga.
  try {
    if (contenedor) contenedor.innerHTML = "";
  } catch {
    /* React puede haber desmontado el nodo antes */
  }
}

/**
 * Las líneas ATOM de una proteína PDB/PDBQT con su residuo («cadena:número», las columnas fijas del formato, igual que
 * lee 3Dmol), de la última proteína consultada: cambiar de pose vuelve a preguntar por la misma.
 */
let ultimaProteina: { fuente: string; filas: ReadonlyArray<{ residuo: string; texto: string }> } | null = null;

/**
 * Un PDB sólo con los residuos pedidos (el bolsillo de una pose), o cadena vacía si ninguno está en la proteína.
 *
 * Los residuos del bolsillo se dibujan como varillas sobre el cartoon. Si esas varillas son un estilo de la propia
 * proteína, cada pose con otro bolsillo obliga a 3Dmol a reconstruir la geometría ENTERA del receptor (12–22 ms con
 * 2 900 átomos, y crece con el receptor). Como modelo aparte, cambiar de pose sólo reconstruye ~130 átomos (2–3 ms). Sólo
 * `ATOM`: el bolsillo se mide contra átomos de proteína, no contra hetero-átomos que comparten número de residuo.
 */
export function pdbDelBolsillo(proteinData: string, residuos: ReadonlySet<string>): string {
  if (!ultimaProteina || ultimaProteina.fuente !== proteinData) {
    const filas: Array<{ residuo: string; texto: string }> = [];
    for (const linea of proteinData.split("\n")) {
      if (!linea.startsWith("ATOM")) continue;
      filas.push({ residuo: `${linea[21] ?? " "}:${parseInt(linea.slice(22, 26), 10)}`, texto: linea });
    }
    ultimaProteina = { fuente: proteinData, filas };
  }
  const elegidas = ultimaProteina.filas.filter((fila) => residuos.has(fila.residuo)).map((fila) => fila.texto);
  return elegidas.length > 0 ? `${elegidas.join("\n")}\nEND\n` : "";
}

/** ¿Perdió el visor su contexto WebGL? Sin renderizador conocido, no se sabe que sí. */
export function visorSinContexto(visor: Visor3Dmol | null | undefined): boolean {
  try {
    return visor?.renderer?.isLost?.() === true;
  } catch {
    return false;
  }
}

/**
 * Dibuja el visor, o dice que no pudo.
 *
 * 3Dmol no lanza cuando el contexto se perdió: en cada `render()` intenta compilar sus shaders y escribe «could not
 * initialize shader» en la consola, una vez por programa y por fotograma. Aquí se intenta lo que 3Dmol sí sabe hacer
 * (`resize()` reconstruye el renderizador cuando el contenedor tiene tamaño) y, si sigue sin contexto, no se dibuja:
 * el que llama enseña que la vista se perdió y ofrece reabrirla.
 */
export function pintarVisor3D(visor: Visor3Dmol | null | undefined): boolean {
  if (!visor) return false;
  try {
    if (visorSinContexto(visor)) {
      visor.resize?.();
      if (visorSinContexto(visor)) return false;
    }
    visor.render?.();
    return true;
  } catch (error) {
    // Una excepción con el contexto perdido es consecuencia de eso; con contexto, es un defecto y no se esconde.
    if (visorSinContexto(visor)) return false;
    throw error;
  }
}
