"use client";

import { useLanguage } from "@/context/LanguageContext";
import type { ReactNode } from "react";
import { useCatalogoDeReceptores } from "@/hooks/useCatalogoDeReceptores";
import type { Target } from "@/lib/api";
import { numeroOGuion } from "@/lib/formatoNumerico";
import { claveDeCondicion, comparacionConElSello, intentosDelReceptor, receptorPorPdbId, seccionDelReceptor, type ParametrosDeCorrida, type VerificacionReceptor } from "@/lib/seccionCatalogo";
import { ResumenDeIntentos } from "./IntentosDeVerificacion";
import { AyudaDeDemostracion } from "./AyudaDeDemostracion";

/** El mismo sello acompaña resultados y tarjetas del selector. */
export function SelloVerificado({ verificacion: v, corrida, compacta = false, etiquetaAdicional }: { verificacion: VerificacionReceptor; corrida?: ParametrosDeCorrida | null; compacta?: boolean; etiquetaAdicional?: ReactNode }) {
  const { t } = useLanguage();
  const { difiere, sinDeclarar } = comparacionConElSello(corrida, v);
  const frases = [
    t("cat_cifras", { rho: numeroOGuion(v.calibracion.rho, 2), a: numeroOGuion(v.calibracion.ic95[0], 2), b: numeroOGuion(v.calibracion.ic95[1], 2), n: v.calibracion.n, endpoint: v.calibracion.endpoint, panel: v.calibracion.panel }),
    t("cat_pose", { ok: v.pose.semillas_rmsd_ok, semillas: v.pose.semillas }),
    t("cat_parametros", { e: v.protocolo.exhaustiveness, p: v.protocolo.num_poses, s: v.protocolo.semilla }),
    ...v.condiciones.map((codigo) => t(claveDeCondicion(codigo), { codigo })),
  ];
  if (Array.isArray(v.pose.rmsd_top1_A) && v.pose.rmsd_top1_A.length) frases.push(t("cat_rmsd_semillas", { valores: v.pose.rmsd_top1_A.map((rmsd) => numeroOGuion(rmsd, 1)).join(", ") }));
  if (difiere.some(campo => campo !== "receptor")) frases.push(t("cat_parametros_distintos"));
  if (difiere.includes("receptor")) frases.push(t("cat_receptor_distinto"));
  if (sinDeclarar.includes("receptor")) frases.push(t("cat_receptor_sin_declarar"));
  if (sinDeclarar.some(campo => campo !== "receptor")) frases.push(t("cat_parametros_sin_declarar"));
  if (compacta) {
    const textoCompleto = [t("cat_verificado"), ...frases].join(" ");
    return <span role="note" aria-label={textoCompleto} title={textoCompleto} className="mt-1 inline-flex max-w-full whitespace-nowrap rounded border border-[var(--border-light)] px-2 py-0.5 text-xs font-semibold text-[var(--text)]">{t(difiere.length || sinDeclarar.length ? "cat_verificado_compacta_no_describe" : "cat_verificado_compacta", { rho: numeroOGuion(v.calibracion.rho, 2) })}</span>;
  }
  return <span role="note" className="mt-2 block text-sm leading-6 text-[var(--text-secondary)]">
    <span className={etiquetaAdicional ? "flex flex-wrap items-center gap-x-2" : undefined}>
      <span className="inline-flex rounded border border-[var(--border-light)] px-2 py-0.5 font-semibold text-[var(--text)]">{t("cat_verificado")}</span>
      {etiquetaAdicional}
    </span>
    {frases.map((frase, index) => <span key={index} className="mt-1 block [overflow-wrap:anywhere]">{frase}</span>)}
  </span>;
}

/** Resultado, corrida y caso leen la misma regla y el mismo catálogo en caché. */
export function InsigniaDelCatalogo({ pdbId, target, corrida, compacta = false, comprobando = false, motivo, etiquetaAdicional, ayudaFlotante = false }: { pdbId?: string | null; target?: Target | null; corrida?: ParametrosDeCorrida | null; compacta?: boolean; comprobando?: boolean; motivo?: string; etiquetaAdicional?: ReactNode; ayudaFlotante?: boolean }) {
  const { t } = useLanguage();
  const catalogo = useCatalogoDeReceptores(!target && Boolean(pdbId));
  const receptor = target ?? receptorPorPdbId(pdbId, catalogo);
  const seccion = seccionDelReceptor(receptor);
  if (seccion === "propios") return etiquetaAdicional ? <span className="flex flex-wrap items-center gap-x-2">{etiquetaAdicional}</span> : null;
  if (seccion === "verificado" && compacta && comprobando) {
    const texto = t("cat_verificado_compacta_comprobando");
    const ayuda = motivo ? `${texto}. ${motivo}` : texto;
    return <span role="note" aria-label={ayuda} title={ayuda} className="mt-1 inline-flex max-w-full rounded border border-[var(--border-light)] px-2 py-0.5 text-xs font-semibold text-[var(--text)]">{texto}</span>;
  }
  if (seccion === "verificado" && receptor?.verificacion) return <SelloVerificado verificacion={receptor.verificacion} corrida={corrida} compacta={compacta} etiquetaAdicional={etiquetaAdicional} />;
  const ayuda = t(intentosDelReceptor(receptor).length ? "cat_intento_ayuda" : "cat_insignia_ayuda");
  if (compacta) {
    const textoCompleto = `${t("cat_demostracion")}. ${ayuda}`;
    return <span role="note" aria-label={textoCompleto} title={textoCompleto} className="mt-1 inline-flex max-w-full whitespace-nowrap rounded border border-[var(--border-light)] px-2 py-0.5 text-xs font-semibold text-[var(--text)]">{t("cat_demostracion")}</span>;
  }
  return <span role="note" className="mt-2 block text-sm leading-6 text-[var(--text-secondary)]">
    <span className={etiquetaAdicional || ayudaFlotante ? "flex flex-wrap items-center gap-x-2" : undefined}>
      {ayudaFlotante
        ? <AyudaDeDemostracion etiqueta={t("cat_demostracion")} texto={ayuda} />
        : <span className="inline-flex rounded border border-[var(--border-light)] px-2 py-0.5 font-semibold text-[var(--text)]">{t("cat_demostracion")}</span>}
      {etiquetaAdicional}
    </span>
    {!ayudaFlotante && <span className="mt-1 block">{ayuda}</span>}
    <ResumenDeIntentos target={receptor} />
  </span>;
}
