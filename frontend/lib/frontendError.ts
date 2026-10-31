import { TRADUCCIONES_POR_SUPERFICIE } from "../context/traducciones";

export type TranslationValues = Readonly<Record<string, string | number>>;
export type Translate = (key: string, values?: TranslationValues) => string;

/** Una clave local conserva el idioma base en Error.message para registros antiguos.
 * La interfaz recibe el traductor al presentar el error. El texto externo no se clasifica.
 */
export type MessageValues = Readonly<Record<string, string | number | FrontendMessage | FrontendList>>;
const spanish: Translate = (key, values) => (TRADUCCIONES_POR_SUPERFICIE.es[key] ?? key).replace(/\{(\w+)\}/g,
  (all, name: string) => values && name in values ? String(values[name]) : all);
export class FrontendMessage {
  constructor(readonly key: string, readonly values?: MessageValues) {}
  render(t: Translate): string {
    const values = this.values && Object.fromEntries(Object.entries(this.values).map(([key, value]) =>
      [key, value instanceof FrontendMessage || value instanceof FrontendList ? value.render(t) : value]));
    return t(this.key, values);
  }
  toString(): string { return this.render(spanish); }
}
export class FrontendList {
  constructor(readonly items: readonly FrontendText[], readonly separator: string) {}
  render(t: Translate): string { return this.items.map(item => typeof item === "string" ? item : item.render(t)).join(this.separator); }
  toString(): string { return this.render(spanish); }
}
export const frontendList = (items: readonly FrontendText[], separator: string): FrontendList => new FrontendList(items, separator);
export type FrontendText = string | FrontendMessage | FrontendList;
export const frontendMessage = (key: string, values?: MessageValues): FrontendMessage => new FrontendMessage(key, values);

export class FrontendError extends Error {
  readonly frontendMessage?: FrontendMessage | FrontendList;
  constructor(message: FrontendText, options?: ErrorOptions) {
    super(String(message), options);
    if (message instanceof FrontendMessage || message instanceof FrontendList) this.frontendMessage = message;
  }
}

/** Sólo traduce errores etiquetados por el frontend; conserva los del backend/Rust. */
export function presentError(error: unknown, t: Translate): string {
  if (error instanceof FrontendError && error.frontendMessage) {
    return error.frontendMessage.render(t);
  }
  if (error && typeof error === "object" && "message" in error && typeof error.message === "string") return error.message;
  return error == null ? "" : String(error);
}
