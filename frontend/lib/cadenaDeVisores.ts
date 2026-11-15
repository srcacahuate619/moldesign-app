// Qué visor abrir cuando el que estaba no puede dibujar.
//
// La columna 3D de Evaluación tiene tres maneras de enseñar el receptor y la
// pose, de la que más pide del equipo a la que menos:
//
//   molstar   Mol*, el visor científico (WebGL, sombreadores propios)
//   web3d     el visor ligero (WebGL, una sola pasada)
//   simple    la vista simplificada en un lienzo 2D (sin WebGL)
//
// Antes cada fallo terminaba en un mensaje. Ahora termina en el siguiente visor
// que sí puede dibujar, y el último no depende de nada que pueda faltar.

export type Motor3D = "molstar" | "web3d";
export type Visor = Motor3D | "simple";

/**
 * El visor que sustituye a `fallido`.
 *
 * Se prueba el otro motor 3D una sola vez: si ya había fallado también, se va
 * a la vista simplificada en lugar de alternar entre dos visores rotos.
 */
export function siguienteVisor(fallido: Motor3D, yaFallaron: ReadonlySet<Motor3D>): Visor {
  const otro: Motor3D = fallido === "molstar" ? "web3d" : "molstar";
  return yaFallaron.has(otro) ? "simple" : otro;
}
