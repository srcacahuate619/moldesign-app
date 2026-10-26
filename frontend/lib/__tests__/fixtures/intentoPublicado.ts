import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { IntentoVerificacion } from "../../seccionCatalogo";

/** Lectura del intento publicado real; las variantes de prueba nunca se escriben allí. */
const publicados = JSON.parse(readFileSync(resolve(process.cwd(), "../backend/data/intentos_de_verificacion.json"), "utf8")) as { intentos: IntentoVerificacion[] };
const intento = publicados.intentos.find(i => i.experimento === "CAL-8HFI-01");
if (!intento) throw new Error("Falta el intento publicado CAL-8HFI-01 en la base de esta tarea");
export const intentoPublicado = intento;
