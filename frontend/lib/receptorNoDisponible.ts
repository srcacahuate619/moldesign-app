// =====================================================================
// receptorNoDisponible — qué se le dice a quien elige un receptor que no se prepara
// =====================================================================
//
// QA1-003. De los 380 receptores del catálogo, 15 llegan con `disponible: false`
// y un `motivo_no_disponible` que escribe el preparador. En 11 de esos 15 el
// motivo es el texto CRUDO de una excepción de Meeko, tal cual:
//
//     Meeko no puede construir el receptor (RuntimeError: for residue_key='A:383',
//     3 have passed: ['HIE', 'HID', 'HIP'] and tied for fewest missing and excess
//     H: HIE HID ).
//
// Eso se le enseñaba a la investigadora dentro de la tarjeta. No le dice qué
// pasa ni qué hacer, y compite con el aviso real. El texto sigue disponible —quien
// depure lo necesita—, pero detrás de «Detalle técnico» y con una frase al frente.
//
// Los otros 4 motivos ya son frases redactadas («Meeko elimina 7 residuo(s) a 6 Å
// o menos de la caja… No se acopla contra un sitio incompleto.») y se muestran
// tal cual.

const EXCEPCION_CRUDA = /RuntimeError|Traceback|\b\w*Error:|\bhave passed:|Expected \d+ paddings/;

/** `true` si el motivo es el texto de una excepción de Python y no una frase redactada. */
export function esExcepcionCruda(motivo: string | null | undefined): boolean {
  return EXCEPCION_CRUDA.test(motivo ?? "");
}
