import type { ValoresDeTraduccion } from "../../context/LanguageContext";
import { summarizePendingContext, type CaseContext } from "../../lib/cases/types";

type Translator = (key: string, values?: ValoresDeTraduccion) => string;

/** Recuento traducible de las preguntas que a?n no tienen respuesta. */
export function describePendingDetails(context: CaseContext, t?: Translator): string {
  const { total } = summarizePendingContext(context);
  if (total === 0) return t ? t("ca_pending_details_zero") : "Sin detalles pendientes";
  if (t) return t(total === 1 ? "ca_pending_detail_one" : "ca_pending_details_many", { count: total });
  return `${total} ${total === 1 ? "detalle pendiente" : "detalles pendientes"}`;
}
