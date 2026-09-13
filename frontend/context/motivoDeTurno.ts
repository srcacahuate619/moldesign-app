/**
 * Por qué un turno de MolChat no llegó a responder, dicho de forma accionable.
 *
 * MOLCHAT-AUD-01 (FE/UX). `sendMessage` hacía `if (!res.ok) { ...; return; }`:
 * el mensaje del investigador quedaba en la lista, no llegaba respuesta y nada
 * decía por qué. Las correcciones de esta pestaña añadieron motivos que sí
 * sirven para actuar —403 sin consentimiento del destino (MOLCHAT-NET-005),
 * 503 si el historial local no acepta escribir (MOLCHAT-BE-008)— y todos
 * morían en ese `return`.
 *
 * Vive en su propio módulo, sin React, para que se pueda probar sin montar el
 * proveedor entero.
 */
export async function motivoDeRespuesta(res: {
  status: number;
  json: () => Promise<unknown>;
}): Promise<string> {
  let detalle = "";
  try {
    const cuerpo = (await res.json()) as { detail?: unknown };
    const d = cuerpo?.detail;
    if (typeof d === "string") {
      detalle = d;
    } else if (d && typeof d === "object") {
      const obj = d as { mensaje?: string; motivo?: string };
      detalle = obj.mensaje || obj.motivo || "";
    }
  } catch {
    detalle = "";
  }
  if (detalle) return detalle;
  if (res.status === 401) return "La sesion caduco. Volve a entrar y repeti la pregunta.";
  if (res.status === 403) return "Falta autorizar el destino de los datos en Ajustes de IA.";
  if (res.status === 503) return "El motor no esta disponible en este momento.";
  return `El servidor respondio ${res.status}.`;
}
