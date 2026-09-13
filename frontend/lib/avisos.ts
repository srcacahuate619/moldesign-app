// =====================================================================
// Avisos científicos: la severidad la declara quien los emite
// =====================================================================
//
// EL FALLO QUE ARREGLA. `scientific_warnings` viajaba como una lista de
// cadenas y la pestaña de alertas decidía el color buscando subcadenas:
//
//     const isPositive = lower.includes("buen") || lower.includes("seguro")
//                     || lower.includes("cumple") || …;
//
// Se pasaron los 184 literales de aviso que emite hoy el backend por esa misma
// función. El resultado, medido:
//
//     INFO 159   ·   PRECAUCIÓN 9   ·   CRÍTICA 13   ·   POSITIVO 3
//
// Ningún falso verde — pero **el 86 % cae en el mismo azul de "nota"**, y ahí
// dentro están las tres cosas que más deberían cambiar la lectura de una
// corrida: que el motor que corrió no fue el que se pidió, que la afinidad
// está fuera del rango en que el score discrimina, y que la semilla no
// coincide con la configurada. Se enseñaban con el mismo peso visual que
// «las afinidades se extrajeron del stdout de Vina».
//
// El generador del PDF del certificado tenía la misma estructura con otro
// vocabulario, y ahí sí disparaba: su lista de positivos incluía `"sin"`, así
// que «Vina no encontrado. Devolviendo estructura plegada sin docking» salía
// etiquetado **[POSITIVA]**, en verde, dentro del documento que se firma.
//
// Y aunque hoy no dispare aquí, mientras la severidad se deduzca de la
// redacción, reescribir la frase de un aviso puede cambiarle el color. Eso no
// es un fallo que se arregle una vez.
//
// LA REGLA. Quien emite el aviso declara su severidad (`services/avisos.py`).
// Aquí no se adivina nada. Una corrida anterior a esta etapa llega como cadena
// suelta y se muestra como «heredada»: sin color y diciendo que su severidad
// no se declaró, que es la verdad.

export type Severidad = "positiva" | "info" | "precaucion" | "critica" | "heredada";

export interface AvisoDeclarado {
  readonly codigo: string;
  readonly severidad: Severidad;
  readonly mensaje: string;
}

const SEVERIDADES: ReadonlySet<string> = new Set([
  "positiva",
  "info",
  "precaucion",
  "critica",
  "heredada",
]);

/** Un aviso del backend —nuevo o heredado— en la forma que usa la interfaz. */
export function normalizarAviso(valor: unknown): AvisoDeclarado | null {
  if (typeof valor === "string") {
    const mensaje = valor.trim();
    return mensaje ? { codigo: "HEREDADO", severidad: "heredada", mensaje } : null;
  }
  if (valor && typeof valor === "object") {
    const bruto = valor as { codigo?: unknown; severidad?: unknown; mensaje?: unknown };
    const mensaje = typeof bruto.mensaje === "string" ? bruto.mensaje.trim() : "";
    if (!mensaje) return null;
    const severidad =
      typeof bruto.severidad === "string" && SEVERIDADES.has(bruto.severidad)
        ? (bruto.severidad as Severidad)
        : "heredada";
    const codigo = typeof bruto.codigo === "string" && bruto.codigo ? bruto.codigo : "SIN_CODIGO";
    return { codigo, severidad, mensaje };
  }
  return null;
}

export function normalizarAvisos(valores: unknown): AvisoDeclarado[] {
  if (!Array.isArray(valores)) return [];
  return valores
    .map(normalizarAviso)
    .filter((aviso): aviso is AvisoDeclarado => aviso !== null);
}

/**
 * Orden de lectura: lo que invalida primero.
 *
 * Antes el orden era el de emisión, así que un «MOTOR SUSTITUIDO» podía quedar
 * el sexto de una lista de ocho, debajo de tres notas de procedencia.
 */
const PESO: Record<Severidad, number> = {
  critica: 0,
  precaucion: 1,
  heredada: 2,
  info: 3,
  positiva: 4,
};

export function ordenarPorSeveridad(avisos: readonly AvisoDeclarado[]): AvisoDeclarado[] {
  return [...avisos].sort((a, b) => PESO[a.severidad] - PESO[b.severidad]);
}

/** Cuántos avisos exigen atención. Es el número del badge de la pestaña. */
export function cuentaQueImporta(avisos: readonly AvisoDeclarado[]): number {
  return avisos.filter((a) => a.severidad === "critica" || a.severidad === "precaucion").length;
}
