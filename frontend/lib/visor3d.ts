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

/** Un visor de 3Dmol. La build empaquetada no trae tipos. */
type Visor3Dmol = {
  spin?: (eje: string | boolean, velocidad?: number) => void;
  removeAllModels?: () => void;
  removeAllSurfaces?: () => void;
  removeAllShapes?: () => void;
  removeAllLabels?: () => void;
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

  // 3. Perder el contexto. Ver arriba: es el recurso racionado.
  try {
    const lienzo = contenedor?.querySelector("canvas");
    const gl =
      (lienzo?.getContext("webgl") as WebGLRenderingContext | null) ??
      (lienzo?.getContext("experimental-webgl") as WebGLRenderingContext | null);
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    /* `getContext` lanza si ya se había perdido; era el objetivo */
  }

  // 4. Quitar el lienzo del DOM para que el contenedor no lo retenga.
  try {
    if (contenedor) contenedor.innerHTML = "";
  } catch {
    /* React puede haber desmontado el nodo antes */
  }
}
