"use client";

import type { ReactNode } from "react";
import { useLanguage } from "@/context/LanguageContext";
import type { SeccionCatalogo } from "@/lib/seccionCatalogo";
import type { Target } from "@/lib/api";
import { AVISO_UNIDAD_BIOLOGICA, seccionDelReceptor } from "@/lib/seccionCatalogo";
import { SelloVerificado } from "./InsigniaDelCatalogo";
import { IntentoEnTarjeta } from "./IntentosDeVerificacion";

/** La clave de traducción del nombre de cada sección: título de la sección y rótulo de su pestaña. */
export const CLAVE_DE_SECCION: Record<SeccionCatalogo, string> = { verificado: "cat_verificados", propios: "cat_propios", demostracion: "cat_demostracion" };

export function SeccionDelCatalogo({ seccion, vacia, children, onUpload, intentos }: { seccion: SeccionCatalogo; vacia: boolean; children: ReactNode; onUpload?: () => void; intentos?: ReactNode }) {
  const { t } = useLanguage();
  const clave = CLAVE_DE_SECCION[seccion];
  return <section aria-label={t(clave)} className="space-y-4">
    <h3 className="text-lg font-semibold text-[var(--text)]">{t(clave)}</h3>
    <p className="max-w-prose text-sm leading-6 text-[var(--text-secondary)]">{t(`${clave}_texto`)}</p>
    {seccion === "propios" && onUpload && <button type="button" onClick={onUpload} className="min-h-11 rounded-lg border border-[var(--border-light)] px-4 text-sm font-semibold text-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2">{t("cat_subir")}</button>}
    {vacia && seccion !== "demostracion" && <p className="text-sm leading-6 text-[var(--text-secondary)]">{t(`${clave}_vacio`)}</p>}
    {seccion === "verificado" && intentos}
    {children}
  </section>;
}

/** Los números acompañan al estado; los avisos no afectan la selección. */
export function EvidenciaDelCatalogo({ target }: { target: Target }) {
  const { t } = useLanguage();
  const seccion = seccionDelReceptor(target);
  const datos = seccion === "verificado" ? target.verificacion : null;
  return <div className="space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
    {datos && <SelloVerificado verificacion={datos} />}
    <IntentoEnTarjeta target={target} />
    {target.avisos_catalogo?.includes(AVISO_UNIDAD_BIOLOGICA) && <p role="note">{t("cat_aviso_unidad")}</p>}
  </div>;
}
