/**
 * ENG-004 — cómo se nombra un motor que esta versión no ejecuta.
 *
 * `GET /evaluation/engines` ya dice si un motor está disponible y por qué no.
 * Lo que no dice —ni debe— es cómo llamarlo delante del investigador. «No
 * instalado» y «servicio aparte» son verdad técnica y suenan a avería: parece
 * que algo se rompió en su equipo cuando lo que pasa es que ese motor todavía
 * no existe en el producto.
 *
 * Para el primer MVP público sólo AutoDock Vina (moléculas pequeñas) y ESMFold
 * (péptidos) se pueden ejecutar. QuickVina 2, DiffDock, ColabFold, ESMFold Pro
 * y RFdiffusion se quedan fuera, y la palabra honesta para eso es
 * «Próximamente».
 *
 * La decisión se deriva de `requiere`, que viene del backend, y NO de una lista
 * de identificadores escrita aquí. El día que QuickVina se empaquete o que un
 * sidecar se instale, su `requiere` cambia y esta función deja de anunciarlo
 * sin que nadie tenga que acordarse de venir a editarla. Es la misma regla que
 * ENG-001: el inventario manda, la interfaz no deduce.
 */
import type { MotorDeclarado } from "./api";

/**
 * Lo que esta versión no puede resolver con ninguna acción de la interfaz.
 *
 * `descarga_bajo_demanda` queda deliberadamente fuera: ESMFold no está
 * disponible hasta que se descarga, pero la aplicación sabe instalarlo y
 * encenderlo. Anunciarlo como «próximamente» seria mentir al reves —
 * escondería una capacidad que sí existe.
 */
const FUERA_DEL_MVP = new Set(["servicio_externo", "binario_externo"]);

export type EstadoParaEtiqueta = Pick<MotorDeclarado, "requiere" | "disponible">;

export function esProximamente(motor: EstadoParaEtiqueta): boolean {
  return !motor.disponible && FUERA_DEL_MVP.has(motor.requiere);
}

export const BADGE_PROXIMAMENTE = "PRÓXIMAMENTE";

/** Por qué no está, dicho para quien usa el programa y no para quien lo escribe. */
export function textoProximamente(etiqueta: string): string {
  return (
    `${etiqueta} todavía no forma parte de MolDesign. Esta versión ejecuta ` +
    `AutoDock Vina para moléculas pequeñas y ESMFold para péptidos.`
  );
}
