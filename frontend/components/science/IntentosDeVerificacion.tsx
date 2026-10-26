"use client";

import { useLanguage } from "@/context/LanguageContext";
import type { Target } from "@/lib/api";
import { numeroOGuion } from "@/lib/formatoNumerico";
import { claveDeCondicion, intentosDelReceptor, type IntentoVerificacion } from "@/lib/seccionCatalogo";

type Traductor = (clave: string, variables?: Record<string, string | number>) => string;

function calibracionNoSuperada(intento: IntentoVerificacion): boolean {
  return intento.decision === "NO_GO" && intento.conclusion === "CALIBRACION_NO_SUPERADA";
}

function cifras(intento: IntentoVerificacion) {
  const c = intento.calibracion;
  const ic = Array.isArray(c.ic95) ? c.ic95 : [];
  const peor = Array.isArray(c.ic95_rho_peor) ? c.ic95_rho_peor : [];
  return { rho: numeroOGuion(c.rho, 2), a: numeroOGuion(ic[0], 2), b: numeroOGuion(ic[1], 2), n: c.n, endpoint: c.endpoint, panel: c.panel,
    rp: numeroOGuion(c.rho_peor, 2), pa: numeroOGuion(peor[0], 2), pb: numeroOGuion(peor[1], 2) };
}

function conclusion(intento: IntentoVerificacion, t: Traductor): string {
  if (intento.decision === "GO" && intento.conclusion === "CALIBRACION_SUPERADA") return t("cat_intento_superado", cifras(intento));
  if (intento.conclusion === "FALLO_TECNICO_PERSISTENTE") return t("cat_intento_fallo_tecnico", cifras(intento));
  if (intento.conclusion === "CRITERIO_ENMENDADO_CUMPLIDO_NO_CONFIRMATORIO") return t("cat_intento_post_hoc", cifras(intento));
  if (!calibracionNoSuperada(intento)) return t("cat_intento_generico", { decision: intento.decision, conclusion: intento.conclusion });
  const resumen = t("cat_intento_calibracion", cifras(intento));
  const ic = intento.calibracion.ic95;
  if (!Array.isArray(ic) || ic.length !== 2 || !ic.every(valor => typeof valor === "number" && Number.isFinite(valor)) || ic[0] > ic[1]) return resumen;
  if (ic[1] < 0) return `${resumen} ${t("cat_intento_inverso")}`;
  if (ic[0] <= 0) return `${resumen} ${t("cat_intento_azar")}`;
  return resumen;
}

function frasesDelIntento(intento: IntentoVerificacion, t: Traductor): string[] {
  return [
    conclusion(intento, t),
    ...(!calibracionNoSuperada(intento) ? [t("cat_cifras", cifras(intento))] : []),
    t("cat_pose", { ok: intento.pose.semillas_rmsd_ok, semillas: intento.pose.semillas }),
    t("cat_parametros", { e: intento.protocolo.exhaustiveness, p: intento.protocolo.num_poses, s: intento.protocolo.semilla }),
    ...intento.condiciones.map(codigo => t(claveDeCondicion(codigo), { codigo })),
    ...(intento.pose.rmsd_top1_A?.length ? [t("cat_rmsd_semillas", { valores: intento.pose.rmsd_top1_A.map(rmsd => numeroOGuion(rmsd, 1)).join(", ") })] : []),
    t("cat_intento_experimento", { experimento: intento.experimento, fecha: intento.fecha }),
  ];
}

/** Sólo información: la pertenencia a Verificados sigue dependiendo del registro. */
export function IntentosPublicados({ targets }: { targets: readonly Target[] }) {
  const { t } = useLanguage();
  const entradas = targets.flatMap(target => intentosDelReceptor(target).map(intento => ({ target, intento })));
  if (!entradas.length) return null;
  return <section aria-label={t("cat_intentos_titulo")} className="space-y-3 border border-[var(--border)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
    <h4 className="text-base font-semibold text-[var(--text)]">{t("cat_intentos_titulo")}</h4>
    <p>{t(entradas.every(({ intento }) => intento.decision === "NO_GO") ? "cat_intentos_texto" : "cat_intentos_texto_mixto")}</p>
    {entradas.map(({ target, intento }, index) => <article key={`${target.pdb_id}-${intento.experimento}-${index}`} className="space-y-2 border-t border-[var(--border)] pt-3 [overflow-wrap:anywhere]">
      <h5 className="font-semibold text-[var(--text)]">{target.pdb_id} · {target.name}</h5>
      {frasesDelIntento(intento, t).map((frase, i) => <p key={i}>{frase}</p>)}
    </article>)}
  </section>;
}

export function IntentoEnTarjeta({ target }: { target: Target }) {
  const { t } = useLanguage();
  return <>{intentosDelReceptor(target).map((intento, index) => {
    const textoCompleto = frasesDelIntento(intento, t).join(" ");
    return <span key={`${intento.experimento}-${index}`} role="note" aria-label={textoCompleto} title={textoCompleto} className="block text-xs leading-5 [overflow-wrap:anywhere]">
      {calibracionNoSuperada(intento) ? t("cat_intento_compacto") : conclusion(intento, t)}
    </span>;
  })}</>;
}

/**
 * SCI-A-016: el resumen expandido decía ρ e IC y perdía el panel, n, la magnitud y
 * las condiciones del ensayo. Usa la misma ficha de frases que «Intentos publicados»
 * y dice que esas cifras son del experimento, no de la corrida que se está viendo.
 */
export function ResumenDeIntentos({ target }: { target?: Target }) {
  const { t } = useLanguage();
  return <>{intentosDelReceptor(target).map((intento, index) => <span key={`${intento.experimento}-${index}`} className="mt-1 block [overflow-wrap:anywhere]">
    <span className="block">{t("cat_intento_resumen")}</span>
    {frasesDelIntento(intento, t).map((frase, i) => <span key={i} className="block text-xs leading-5">{frase}</span>)}
  </span>)}</>;
}
