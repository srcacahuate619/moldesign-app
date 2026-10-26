// Moldex → Preparación: «audita la preparación de esta corrida guardada».
//
// Moldex guarda CORRIDAS (molécula, receptor, `task_id`); Preparación audita el
// caso que contiene esa corrida, porque la auditoría necesita la proyección del
// caso —contexto, decisiones, relación con los inputs— y Moldex no la tiene.
//
// Por eso lo que viaja es el `task_id`, y Preparación busca cuál de los casos del
// investigador lo tiene en su libro. Si ninguno lo tiene, lo dice: la corrida se
// guardó en Moldex pero su caso ya no está (se olvidó, o la guardó otra persona),
// y no hay nada que auditar sin él.
//
// El canal es el mismo mecanismo de `lib/peticionDeEvaluacion.ts`: las dos pestañas
// viven montadas a la vez y no comparten proveedor. Si Preparación no se ha montado
// todavía, la petición espera aquí y la toma el primer oyente.

export interface PeticionDePreparacion {
  /** Identidad durable de la corrida guardada. Sin ella no se puede buscar el caso. */
  readonly taskId: string;
  /** Para nombrarla mientras se busca; nunca decide nada. */
  readonly etiqueta?: string;
}

export interface PeticionDePreparacionRecibida extends PeticionDePreparacion {
  /** Distingue dos peticiones iguales seguidas: cada clic se atiende. */
  readonly nonce: number;
}

let pendiente: PeticionDePreparacionRecibida | null = null;
let contador = 0;
const oyentes = new Set<(peticion: PeticionDePreparacionRecibida) => void>();

export function pedirPreparacion(peticion: PeticionDePreparacion): void {
  const recibida = { ...peticion, nonce: ++contador };
  if (oyentes.size === 0) {
    pendiente = recibida;
    return;
  }
  pendiente = null;
  oyentes.forEach((oyente) => oyente(recibida));
}

/** Se suscribe y entrega en el acto la petición que esperaba, si había una. */
export function escucharPeticionesDePreparacion(
  oyente: (peticion: PeticionDePreparacionRecibida) => void,
): () => void {
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
export function olvidarPeticionesDePreparacion(): void {
  pendiente = null;
  oyentes.clear();
}
