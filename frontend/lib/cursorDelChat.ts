// Dónde actúa MolChat en la pantalla. Cuando el chat maneja una pestaña (carga una molécula en el editor, pulsa
// «Evaluar», prepara un vídeo en Molcy), la pestaña avisa del elemento sobre el que actúa y el anfitrión lleva allí el
// cursor del piloto automático, para que quien mira distinga lo que hace el agente de lo que hace una persona.
// Sólo dibuja: no pulsa nada ni cambia lo que la pestaña ya hace.

export const CURSOR_DEL_CHAT = "molchat-cursor";

export type DestinoDelCursor = { elemento: Element; pulsa: boolean };

/** `pulsa`: la pestaña va a pulsar ese elemento (el cursor marca el clic al llegar). */
export function apuntarCursorDelChat(elemento: Element | null | undefined, pulsa = false): void {
  if (!elemento || typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<DestinoDelCursor>(CURSOR_DEL_CHAT, { detail: { elemento, pulsa } }));
}
