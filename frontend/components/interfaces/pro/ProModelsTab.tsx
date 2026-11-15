"use client";

import React, { useId, useMemo } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import type { EvaluationResult } from "../../../lib/types";
import { fichasDeModelos, type IdDeModelo } from "../../../lib/fichasDeModelos";
import { Ayuda } from "../../ui/Ayuda";
import resultStyles from "./ResultPanels.module.css";
import styles from "./ProModelsTab.module.css";
import { ShapContributionChart } from "./ShapContributionChart";

/**
 * «Modelos»: una ficha por modelo con lo que guardó esta evaluación.
 *
 * Sólo muestra; no califica. Un modelo sin salida no tiene ficha (ver
 * `lib/fichasDeModelos.ts` para el contrato) y se nombra al final, sin
 * rellenarlo con un valor neutro. La regresión y el clasificador de XGBoost son
 * dos fichas porque son dos modelos con salidas distintas.
 *
 * Disposición: la regresión (con su SHAP) a la izquierda y, a su lado, el
 * clasificador, CL-GNN. El texto que explica cómo leer algo vive
 * en un «?» junto a lo que explica, no en párrafos debajo.
 */
type Traducir = ReturnType<typeof useLanguage>["t"];

/** Los 64 caracteres de un SHA-256 desbordan una columna; el valor íntegro queda en `title` y en el atributo. */
const abreviarHuella = (huella: string) => (huella.length > 24 ? `${huella.slice(0, 12)}…${huella.slice(-8)}` : huella);

function Hecho({ etiqueta, children, titulo, ayuda }: { etiqueta: string; children: React.ReactNode; titulo?: string; ayuda?: React.ReactNode }) {
  return <div className={resultStyles.row}>
    <dt><span className={styles.etiquetaConAyuda}>{etiqueta}{ayuda}</span></dt>
    <dd title={titulo}>{children}</dd>
  </div>;
}

function Ficha({ id, titulo, rol, estado, children }: { id: IdDeModelo; titulo: string; rol: string; estado: string; children: React.ReactNode }) {
  const uid = useId();
  return <article className={resultStyles.section} data-model-card={id} aria-labelledby={`${uid}-titulo`}>
    <div className={resultStyles.sectionHeader}>
      <h4 id={`${uid}-titulo`}>{titulo}</h4>
      <span className={resultStyles.badge}>{estado}</span>
    </div>
    <p className={resultStyles.intro}>{rol}</p>
    {children}
  </article>;
}

const dosDecimales = (valor: number) => valor.toFixed(2);

function FilaDePeso({ peso, t }: { peso: number | null; t: Traducir }) {
  return <Hecho etiqueta={t("mod_row_weight")}>{peso == null ? t("mod_unknown") : dosDecimales(peso)}</Hecho>;
}

export function ProModelsTab({ result }: { result: EvaluationResult | null | undefined }) {
  const { t } = useLanguage();
  const fichas = useMemo(() => fichasDeModelos(result), [result]);
  const { regresor, clasificador, clgnn, sinSalida } = fichas;
  const nombre: Record<IdDeModelo, string> = {
    regresor: t("mod_reg_title"),
    clasificador: t("mod_clf_title"),
    clgnn: t("mod_clgnn_title"),
  };
  const hayColumnaDerecha = Boolean(clasificador || clgnn);

  return <section className={`${styles.tab} animate-in fade-in duration-200`} aria-label={t("mod_title")} data-models-tab="true">
    <header className="max-w-[78ch]">
      <h3 className="font-display text-lg font-bold tracking-tight text-zinc-100">{t("mod_title")}</h3>
      <p className={resultStyles.intro}>{t("mod_lead")}</p>
    </header>

    {!fichas.conAlguna && <div className="py-8 px-4 border border-white/5 bg-black/20 rounded-2xl text-zinc-400" data-models-empty="true">
      <p className="text-sm font-medium">{t("mod_none")}</p>
      <p className="text-sm mt-1 opacity-70">{t("mod_none_why")}</p>
    </div>}

    {fichas.conAlguna && <div className={`${styles.cuadricula} ${regresor && hayColumnaDerecha ? "" : styles.unaColumna}`} data-models-grid="true">
      {regresor && <div className={styles.columna}>
        <Ficha id="regresor" titulo={t("mod_reg_title")} rol={t("mod_reg_role")} estado={t("mod_state_output")}>
          <dl className={styles.hechos}>
            <Hecho etiqueta={t("mod_row_output")} titulo={regresor.pki == null ? undefined : String(regresor.pki)}>
              {regresor.pki == null ? t("mod_unknown") : `pKi ${dosDecimales(regresor.pki)}`}
            </Hecho>
            <Hecho
              etiqueta={t("mod_row_model")}
              ayuda={regresor.motivoDeRespaldo
                ? <Ayuda titulo={t("mod_row_fallback")} etiqueta={t("mod_fallback_help_label")}>
                    <p data-model-fallback="true">{regresor.motivoDeRespaldo}</p>
                  </Ayuda>
                : undefined}
            >
              {regresor.modelo ?? t("mod_unknown")}
            </Hecho>
            <Hecho
              etiqueta={t("mod_row_domain")}
              ayuda={<Ayuda titulo={t("mod_row_domain")} etiqueta={t("mod_domain_help_label")}>
                <div className="space-y-2">
                  <p>{t("mod_domain_help")}</p>
                  {regresor.enDominio == null && <p data-model-domain="unknown">{t("mod_reg_domain_unknown")}</p>}
                </div>
              </Ayuda>}
            >
              {regresor.enDominio === true ? t("mod_domain_in") : regresor.enDominio === false ? t("mod_domain_out") : t("mod_unknown")}
            </Hecho>
            {regresor.huellaDelModelo && <Hecho etiqueta={t("mod_row_sha")} titulo={regresor.huellaDelModelo}>
              <code className={styles.huella} data-model-sha={regresor.huellaDelModelo}>{abreviarHuella(regresor.huellaDelModelo)}</code>
            </Hecho>}
          </dl>
          {regresor.pki == null
            ? <p className={resultStyles.note}>{t("mod_reg_no_pki")}</p>
            : <p className={resultStyles.note}>{t("mod_reg_out_note")}</p>}
          {regresor.enDominio === false && <p className={resultStyles.warning} role="note" data-model-domain="out">{t("mod_reg_domain_out")}</p>}
          {regresor.shap
            ? <ShapContributionChart values={regresor.shap} shapOutput={regresor.salidaDelShap} inApplicabilityDomain={regresor.enDominio} mostrarAvisoDeDominio={false} />
            : <p className={resultStyles.note} data-model-shap="absent">{t("mod_reg_no_shap")}</p>}
        </Ficha>
      </div>}

      {hayColumnaDerecha && <div className={styles.columna}>
        {clasificador && <Ficha id="clasificador" titulo={t("mod_clf_title")} rol={t("mod_clf_role")} estado={t("mod_state_output")}>
          <dl className={styles.hechos}>
            <Hecho etiqueta={t("mod_row_output")} titulo={String(clasificador.probabilidad)}>{dosDecimales(clasificador.probabilidad)}</Hecho>
            <FilaDePeso peso={clasificador.peso} t={t} />
            <Hecho etiqueta={t("mod_row_model")}>{t("mod_no_id")}</Hecho>
          </dl>
          <p className={resultStyles.note}>{t("mod_prob_note")}</p>
          {clasificador.peso === 0 && <p className={resultStyles.note} data-model-weight="zero">{t("mod_weight_zero_note")}</p>}
        </Ficha>}

        {clgnn && <Ficha id="clgnn" titulo={t("mod_clgnn_title")} rol={t("mod_clgnn_role")} estado={t("mod_state_output")}>
          <dl className={styles.hechos}>
            <Hecho etiqueta={t("mod_row_output")} titulo={String(clgnn.valor)}>{dosDecimales(clgnn.valor)}</Hecho>
            <FilaDePeso peso={clgnn.peso} t={t} />
            <Hecho etiqueta={t("mod_row_model")}>{t("mod_no_id")}</Hecho>
          </dl>
          <p className={resultStyles.note}>{t("mod_prob_note")}</p>
          {clgnn.peso === 0 && <p className={resultStyles.note} data-model-weight="zero">{t("mod_weight_zero_note")}</p>}
        </Ficha>}
      </div>}
    </div>}

    {fichas.conAlguna && sinSalida.length > 0 && <section className={resultStyles.section} data-models-absent="true" aria-label={t("mod_absent_title")}>
      <div className={resultStyles.sectionHeader}><h4>{t("mod_absent_title")}</h4></div>
      <ul className="space-y-1.5">
        {sinSalida.map((entrada) => <li key={entrada.id} data-model-absent={entrada.id} className={resultStyles.note}>
          <strong>{nombre[entrada.id]}</strong>{" — "}
          {entrada.declaradoAusente ? t("mod_absent_declared") : t("mod_absent_generic")}
        </li>)}
      </ul>
    </section>}
  </section>;
}
