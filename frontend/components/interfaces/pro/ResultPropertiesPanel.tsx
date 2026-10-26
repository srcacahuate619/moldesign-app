"use client";
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 · existing MolDesign tokens */
import {useId} from "react";
import { LiquidOrb } from "./LiquidOrb";
import {useLanguage} from "@/context/LanguageContext";
import {numeroOGuion} from "@/lib/formatoNumerico";
import {etiquetaPPB} from "@/lib/admetEtiquetas";
import type {EvaluationProperties} from "./ProParametersTab";
import styles from "./ResultPanels.module.css";

export function ResultPropertiesPanel({result,physicochemical,drugRules,admetAbsent}:{
  result:EvaluationProperties;
  physicochemical:Array<{key?:string;label:string;value:string}>;
  drugRules:Array<{label:string;passed?:boolean|null;extra?:string;isNeutral?:boolean}>;
  admetAbsent:boolean;
}){
  const {t}=useLanguage();const uid=useId();
  const anyAdmet=!admetAbsent||result.blood_cns_mpo!=null||Boolean(result.blood_bbb_motivo)
    ||Boolean(result.blood_systemic_reactivity?.length)||result.blood_tabpfn_estado==="evaluado";
  const admetPartial=anyAdmet&&[
    result.blood_viability_score,result.blood_solubility_logs,result.blood_ppb_category,
    result.blood_hia_permeable,result.blood_bbb_permeable,
  ].some(value=>value==null);
  const tabpfnState=result.blood_tabpfn_estado;
  const tabpfnLabel=tabpfnState==null?t("c_no_registrado")
    :tabpfnState==="evaluado"?t("ux_tabpfn_evaluated")
    :tabpfnState==="fallo"?t("ux_tabpfn_failed")
    :tabpfnState==="no_evaluado"?t("ux_checks_not_evaluated"):tabpfnState;
  const booleanValue=(value:boolean|null|undefined,yes:string,no:string)=>value==null?t("c_no_registrado"):value?yes:no;
  const admetRows=[
    {label:t("pr_param_ppb"),value:etiquetaPPB(result.blood_ppb_category)??t("c_no_registrado")},
    {label:t("pr_param_hia"),value:booleanValue(result.blood_hia_permeable,t("auto_96ebe42068b8"),t("auto_d22dcefc76d7")),state:result.blood_hia_permeable==null?"not_evaluated":result.blood_hia_permeable?"passed":"failed"},
    {label:"BBB",value:booleanValue(result.blood_bbb_permeable,t("pr_param_permeable"),t("auto_f7139777c977")),state:result.blood_bbb_permeable==null?"not_evaluated":result.blood_bbb_permeable?"passed":"failed"},
    {label:t("pr_param_cns_mpo"),value:numeroOGuion(result.blood_cns_mpo,2," / 6")},
    {label:"SA Score",value:numeroOGuion(result.sa_score,1," / 10")},
  ];
  return <div>
    <details className={styles.section} aria-labelledby={`${uid}-descriptors`}>
      <summary id={`${uid}-descriptors`} className={styles.sectionSummary}>
        <span className={styles.sectionTitle} role="heading" aria-level={4}>{t("ux_descriptors")}</span>
        <span className={`${styles.source} ${styles.descriptorSource}`}>RDKit</span>
      </summary>
      <div className={styles.sectionBody}>
        <p className={styles.intro}>{t("ux_descriptors_scope")}</p>
        <dl className={styles.metrics}>
          <div className={styles.metric}><dt>{t("auto_a9c8b18d6386")}</dt><dd>{numeroOGuion(result.qed,3)}</dd></div>
          <div className={styles.metric}><dt>{t("auto_dec25aafa6fd")}</dt><dd>{numeroOGuion(result.sa_score,2)}</dd></div>
        </dl>
        <dl className={`${styles.rows} ${styles.descriptorRows}`}>
          {[...physicochemical.filter(item=>!item.key),{label:t("auto_d7687bae4a5c"),value:numeroOGuion(result.fsp3,2)}].map(item=><div key={item.label} className={styles.row}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
        </dl>
        {Boolean(result.sa_reasons?.length)&&<details className={styles.details}><summary>{t("ux_synthetic_notes")} ({result.sa_reasons!.length})</summary><ul className={styles.note}>{result.sa_reasons!.map((reason,index)=><li key={index}>{reason}</li>)}</ul></details>}
        <details className={styles.details}>
          <summary>{t("ux_docking_measures")}</summary>
          <p className={styles.note}>{t("ux_docking_measures_scope")}</p>
          <dl className={`${styles.rows} ${styles.protocolRows}`}>{physicochemical.filter(item=>item.key).map(item=><div key={item.key} className={styles.row}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
        </details>
      </div>
    </details>

    <details className={styles.section} aria-labelledby={`${uid}-rules`}>
      <summary id={`${uid}-rules`} className={styles.sectionSummary}>
        <span className={styles.sectionTitle} role="heading" aria-level={4}>{t("ux_rules")}</span>
      </summary>
      <div className={styles.sectionBody}>
        <p className={styles.intro}>{t("ux_rules_scope")}</p>
        <dl className={styles.rows}>
          {drugRules.filter(rule=>!rule.isNeutral).map(rule=><div key={rule.label} className={styles.row}>
            <dt>{rule.label}</dt>
            <dd className={styles.ruleResult}>
              {rule.extra&&<span className={styles.ruleExtra}>{rule.extra}</span>}
              <span className={styles.badge} data-state={rule.passed==null?"not_evaluated":rule.passed?"passed":"failed"}>{rule.passed==null?t("c_no_registrado"):t(rule.passed?"ux_rule_pass":"ux_rule_fail")}</span>
            </dd>
          </div>)}
          <div className={styles.row}><dt>{t("pr_param_pains")}</dt><dd><span className={styles.badge} data-state={result.is_pains==null?"not_evaluated":result.is_pains?"review":"passed"}>
            {result.is_pains==null?t("c_no_registrado"):result.is_pains?`${result.pains_matches?.length??0} ${t("pr_param_coincidencias")}`:t("pr_param_no")}
          </span></dd></div>
        </dl>
        {Boolean(result.pains_matches?.length)&&<ul className={styles.warning}>{result.pains_matches!.map((match,index)=><li key={index}>{match}</li>)}</ul>}
      </div>
    </details>

    <details className={styles.section} aria-labelledby={`${uid}-admet`}>
      <summary id={`${uid}-admet`} className={styles.sectionSummary}>
        <span className={styles.sectionTitle} role="heading" aria-level={4}>{t("ux_admet_title")}</span>
        <span className={`${styles.badge} ${styles.sectionStatus}`}>{t(admetPartial?"ux_admet_partial":anyAdmet?"ux_analysis_available":"ux_analysis_absent")}</span>
      </summary>
      <div className={styles.sectionBody}>
        <p className={styles.intro}>{t("ux_admet_scope")}</p>
        {admetAbsent&&<div role="status" className={styles.admetUnavailable}>
          <p><strong>{t("pr_param_admet_no_disponible")}</strong></p>
          <p>{t("ux_admet_unavailable")}</p>
          <p><strong>{t("pn_puedes_calcularlo")}</strong>{t("pn_solo_smiles_no_repite")}</p>
        </div>}
        <div className={styles.detailBody}>
          <div className={styles.admetOrbs}>
            <div className={styles.admetOrb}>
              <LiquidOrb
                value={result.blood_viability_score??0}
                unavailable={result.blood_viability_score==null}
                unavailableNote={t(admetAbsent?"auto_2ab36069225c":"ux_admet_value_absent")}
                absolute={numeroOGuion(result.blood_viability_score,0," / 100")}
                label={t("z_perfil_sanguineo")}
                source="ADMET-AI · heurístico"
              />
            </div>
            <div className={styles.admetOrb}>
              <LiquidOrb
                value={result.blood_solubility_logs!=null?Math.max(0,Math.min(100,50+result.blood_solubility_logs*10)):0}
                unavailable={result.blood_solubility_logs==null}
                unavailableNote={t(admetAbsent?"auto_2ab36069225c":"ux_admet_value_absent")}
                absolute={result.blood_solubility_logs!=null?`${result.blood_solubility_logs.toFixed(2)} logS`:"—"}
                label={t("pr_param_solubilidad")}
                source={t("pr_param_admet_ai")}
              />
            </div>
          </div>
          <dl className={`${styles.rows} ${styles.admetMetricRows}`}>{admetRows.map(item=><div key={item.label} className={styles.row}><dt>{item.label}</dt><dd data-state={item.state}>{item.value}</dd></div>)}</dl>
          {result.blood_bbb_motivo&&<p className={styles.note}><strong>BBB · </strong>{result.blood_bbb_motivo}</p>}
          <section className={styles.section} aria-labelledby={`${uid}-reactivity`}>
            <div className={styles.sectionHeader}><h4 id={`${uid}-reactivity`}>{t("pn_reactividad_sistemica")}</h4></div>
            {result.blood_systemic_reactivity?.length
              ?<ul className={styles.warning}>{result.blood_systemic_reactivity.map((message,index)=><li key={index}>{message}</li>)}</ul>
              :<p className={styles.note}>{t(result.blood_systemic_reactivity==null?"ux_reactivity_absent":"ux_reactivity_empty")}</p>}
            <p className={styles.note}>{t("pn_reactividad_tabpfn")}</p>
            <dl className={styles.rows}><div className={styles.row}><dt>{t("ux_tabpfn_legacy_state")}</dt><dd>{tabpfnLabel}</dd></div></dl>
          </section>
        </div>
      </div>
    </details>
  </div>;
}
