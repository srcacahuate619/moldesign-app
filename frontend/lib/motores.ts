/**
 * Cómo usa la interfaz el inventario de motores (`GET /evaluation/engines`).
 *
 * Decisión del propietario (2026-10-07): el menú sólo lista lo que esta versión ejecuta.
 * Los motores que no existen (QuickVina 2, DiffDock, ColabFold, ESMFold Pro, RFdiffusion)
 * dejan de aparecer; antes se mostraban como «Próximamente» (ENG-004). El backend sigue
 * declarando los siete con su motivo: eso lo guarda `test_motores_declarados_son_los_que_existen.py`
 * (ENG-001), no el menú.
 *
 * Sólo ESMFold necesita una regla propia. Instalado y apagado no es un motor sin hacer: la
 * corrida lo enciende al empezar (`services/docking/peptide_docking.py`), así que se puede elegir.
 */
import type { MotorDeclarado } from "./api";

/**
 * Se puede elegir un motor si ya responde o si la corrida lo encenderá al empezar.
 * Lo que aún necesita una descarga, una librería o una reparación no se puede elegir:
 * la interfaz lo dice y enlaza la acción, pero no lo ofrece como si funcionara.
 */
export function puedeElegirse(motor: Pick<MotorDeclarado, "disponible" | "accion">): boolean {
  return motor.disponible || motor.accion === "encender";
}
