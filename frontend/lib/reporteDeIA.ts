/**
 * El canal para reportar una respuesta de MolChat.
 *
 * Microsoft exige, en cualquier aplicación que entregue texto generado por un
 * modelo, dos cosas: que el usuario sepa que lo es, y que tenga una vía para
 * reportar una respuesta dañina o inapropiada. Lo primero es el aviso
 * permanente del panel; esto es lo segundo.
 *
 * ES UN CORREO Y NO UNA LLAMADA A UN SERVICIO, y es deliberado. Este producto
 * acaba de cerrar tres caminos que salían a la red sin que nadie los
 * autorizara; abrir un cuarto —que además mandaría la conversación— para
 * cumplir una obligación de transparencia sería contradecir lo que el aviso
 * afirma. El correo se abre con todo escrito y **no se envía**: lo manda la
 * persona, cuando lo ha leído, desde su propio programa de correo.
 *
 * La respuesta se recorta. Un `mailto:` largo lo trunca el cliente de correo en
 * silencio, y un reporte cortado por la mitad sin avisar es peor que uno corto
 * que lo declara.
 */

export const CORREO_DE_REPORTE = "soporte-moldesign@amezcua-dev.com";

/**
 * Cuánta respuesta cabe. Los clientes de correo empiezan a truncar alrededor de
 * los 2000 caracteres de URL completa; esto deja margen para el resto.
 */
export const LIMITE_DE_RESPUESTA = 1200;

export interface TextosDelReporte {
  asunto: string;
  cabecera: string;
  etiquetaRespuesta: string;
  etiquetaProveedor: string;
}

export interface DatosDelReporte {
  respuesta: string;
  proveedor: string;
  version?: string;
}

/** Recorta declarando que recortó. Nunca en silencio. */
export function recortar(texto: string, limite = LIMITE_DE_RESPUESTA): string {
  const limpio = (texto ?? "").trim();
  if (limpio.length <= limite) return limpio;
  return `${limpio.slice(0, limite)}\n\n[…recortado: la respuesta tenía ${limpio.length} caracteres]`;
}

/**
 * El `mailto:` con el reporte ya escrito.
 *
 * Se construye con `URLSearchParams` y no concatenando: el asunto y el cuerpo
 * llevan texto de la conversación, y una respuesta con un `&` dentro partiría
 * la URL en dos parámetros.
 */
export function construirMailtoDeReporte(
  datos: DatosDelReporte,
  textos: TextosDelReporte,
): string {
  const lineas = [
    textos.cabecera,
    "",
    "",
    "---",
    `${textos.etiquetaProveedor}: ${datos.proveedor || "—"}`,
    ...(datos.version ? [`MolDesign: ${datos.version}`] : []),
    "",
    `${textos.etiquetaRespuesta}:`,
    recortar(datos.respuesta),
  ];

  const parametros = new URLSearchParams({
    subject: textos.asunto,
    body: lineas.join("\n"),
  });

  // `URLSearchParams` codifica los espacios como `+`, que en el cuerpo de un
  // `mailto:` los clientes muestran literalmente como signos de suma.
  return `mailto:${CORREO_DE_REPORTE}?${parametros.toString().replace(/\+/g, "%20")}`;
}
