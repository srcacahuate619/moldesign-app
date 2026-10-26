// Preparación registra una decisión en un caso sin pisar a Evaluación.
//
// Preparación lee los casos en sólo lectura con su propio repositorio; Evaluación
// tiene el caso activo EN MEMORIA y lo autoguarda entero. Si Preparación escribiera
// directamente sobre el caso que Evaluación tiene abierto, el siguiente autoguardado
// de Evaluación lo sobrescribiría con su copia y la decisión se perdería sin aviso.
//
// Por eso hay un escritor: el `CaseProvider` de Evaluación se registra y, si el caso
// es el suyo activo, la decisión entra por su cola y se espera a que esté en disco.
// Si no lo tiene abierto —o Evaluación no se ha montado—, nadie lo tiene en memoria
// y se escribe directamente: leer, añadir y guardar.

import type { CaseRepository } from "./cases/repository";
import { touchCase } from "./cases/schema";
import type { CaseRecord, HumanDecision } from "./cases/types";

export interface DecisionNueva {
  readonly controlCode: string;
  readonly fingerprint: string;
  readonly note: string;
}

/** Devuelve `true` si el caso era suyo y la decisión ya está guardada; `false` si no lo tiene. */
type Escritor = (casoId: string, decision: DecisionNueva) => Promise<boolean>;

let escritor: Escritor | null = null;

export function registrarEscritorDeDecisiones(nuevo: Escritor): () => void {
  escritor = nuevo;
  return () => {
    if (escritor === nuevo) escritor = null;
  };
}

/** Una decisión por control y huella: repetirla la sustituye, no la duplica. */
export function conDecision(record: CaseRecord, decision: DecisionNueva, at = new Date().toISOString()): CaseRecord {
  const otras = (record.decisions ?? []).filter(
    (d) => !(d.controlCode === decision.controlCode && d.fingerprint === decision.fingerprint),
  );
  const nueva: HumanDecision = {
    controlCode: decision.controlCode,
    fingerprint: decision.fingerprint,
    decision: "reconocida",
    at,
    note: decision.note,
  };
  return touchCase(record, { decisions: [...otras, nueva] }, at);
}

/** Guarda la decisión y devuelve el caso tal como quedó en disco. */
export async function anotarDecision(
  repository: Pick<CaseRepository, "readCase" | "updateCase">,
  casoId: string,
  decision: DecisionNueva,
): Promise<CaseRecord> {
  if (escritor && (await escritor(casoId, decision))) return repository.readCase(casoId);
  const actual = await repository.readCase(casoId);
  return repository.updateCase(conDecision(actual, decision));
}

/** Sólo para pruebas. */
export function olvidarEscritorDeDecisiones(): void {
  escritor = null;
}
