// Preparación → Evaluación: «vuelve a evaluar este caso con esto».
//
// Las dos pestañas viven montadas a la vez (PersistentKeepAliveLayout) y no
// comparten proveedor: el `CaseProvider` es de Evaluación y Preparación lee los
// casos en sólo lectura. La petición viaja por este canal de módulo y la recoge
// el espacio de trabajo de casos, que abre el caso y la aplica como si el
// investigador hubiera elegido eso en Opciones. Nada se ejecuta solo: la persona
// revisa y pulsa «Ejecutar».
//
// Si Evaluación todavía no se ha montado, la petición espera aquí y la toma el
// primer oyente. Sólo hay una pendiente: la última gana.

export interface PeticionDeEvaluacion {
  readonly casoId: string;
  /** Preparación sólo propone conservar el tautómero escrito, nunca el canónico de RDKit. */
  readonly tautomero: "entrada" | "canonico";
  /** El ligando con el que volver a evaluar, tal cual. */
  readonly smiles: string;
}

export interface PeticionRecibida extends PeticionDeEvaluacion {
  /** Distingue dos peticiones iguales seguidas: cada clic se aplica. */
  readonly nonce: number;
}

let pendiente: PeticionRecibida | null = null;
let contador = 0;
const oyentes = new Set<(peticion: PeticionRecibida) => void>();

export function pedirEvaluacion(peticion: PeticionDeEvaluacion): void {
  const recibida = { ...peticion, nonce: ++contador };
  if (oyentes.size === 0) {
    pendiente = recibida;
    return;
  }
  pendiente = null;
  oyentes.forEach((oyente) => oyente(recibida));
}

/** Se suscribe y entrega en el acto la petición que esperaba, si había una. */
export function escucharPeticionesDeEvaluacion(oyente: (peticion: PeticionRecibida) => void): () => void {
  oyentes.add(oyente);
  if (pendiente) {
    const esperada = pendiente;
    pendiente = null;
    oyente(esperada);
  }
  return () => {
    oyentes.delete(oyente);
  };
}

/** Sólo para pruebas. */
export function olvidarPeticionesDeEvaluacion(): void {
  pendiente = null;
  oyentes.clear();
}
