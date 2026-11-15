"use client";

import React, { useState, useEffect, useId, useMemo, useRef } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import resultStyles from "./ResultPanels.module.css";
import shapStyles from "./ProXaiShap.module.css";
import { Info } from "lucide-react";
import { explainFeature } from "../../../lib/xaiFeatures";
import { Ayuda } from "../../ui/Ayuda";

/**
 * Qué magnitud explica el SHAP de esta corrida, según `shap_output`.
 * - `delta_pKi`: el modelo predice la corrección sobre el pKi de Vina.
 * - `pKi`: el modelo predice el pKi directamente.
 * - cualquier otra cosa (incluido `null`): un resultado anterior al registro.
 */
export function notaDeSalidaShap(shapOutput: string | null | undefined): "xai_delta_note" | "xai_pki_note" | "xai_unknown_output_note" {
  if (shapOutput === "delta_pKi") return "xai_delta_note";
  if (shapOutput === "pKi") return "xai_pki_note";
  return "xai_unknown_output_note";
}

/**
 * Las contribuciones SHAP del modelo de regresión. Vive dentro de su tarjeta en
 * «Modelos»: explican a ese modelo, no a la interacción proteína-ligando.
 */
export function ShapContributionChart({values, shapOutput, inApplicabilityDomain, mostrarAvisoDeDominio=true}:{values:Record<string,number>;shapOutput?:string|null;inApplicabilityDomain?:boolean|null;
  /** «Modelos» ya avisa del dominio en la ficha entera y no lo repite aquí. */
  mostrarAvisoDeDominio?:boolean}) {
  const {t}=useLanguage();
  const uid=useId();
  const [selected,setSelected]=useState<string|null>(null);
  const dialog=useRef<HTMLDialogElement>(null);
  const max=useMemo(()=>Math.max(...Object.values(values).map(value=>Math.abs(value)))||1,[values]);
  // Una sola derivación por característica y por idioma: la etiqueta de la fila y
  // la descripción del detalle salen del mismo sitio y no pueden contradecirse.
  const explanations=useMemo(()=>Object.fromEntries(Object.keys(values).map(key=>[key,explainFeature(key,t)])),[values,t]);
  const direction=(value:number)=>value>0?"positive":value<0?"negative":"zero";
  useEffect(()=>{
    const node=dialog.current;if(!node)return;
    if(selected!==null&&!node.open)node.showModal();
    else if(selected===null&&node.open)node.close();
  },[selected]);
  const selectedValue=selected===null?null:values[selected];
  const count=Object.keys(values).length;
  return <section className={`${resultStyles.section} ${shapStyles.chart}`} aria-label={t("ux_shap_title")} data-shap-chart="true">
    {/* La lectura correcta del gráfico (qué magnitud explica, qué falta, qué escala usa) vive en el «?»:
        la gráfica queda limpia y el texto sigue a un clic. */}
    <div className={resultStyles.sectionHeader}>
      <span className="inline-flex items-center gap-2">
        <h4>{t("ux_shap_title")}</h4>
        <Ayuda titulo={t("ux_shap_title")} etiqueta={t("mod_shap_help_label")}>
          <div className="space-y-2">
            <p>{t("ux_shap_scope")}</p>
            <p data-shap-output={shapOutput??"unknown"}>{t(notaDeSalidaShap(shapOutput))}</p>
            <p>{t("ux_shap_scale")}</p>
            <p data-shap-truncation="true">{t("xai_truncation_note",{count})}</p>
          </div>
        </Ayuda>
      </span>
    </div>
    {mostrarAvisoDeDominio&&inApplicabilityDomain!==true&&<p className={resultStyles.warning} role="note" data-shap-domain={inApplicabilityDomain===false?"out":"unknown"}>{t(inApplicabilityDomain===false?"xai_domain_out":"xai_domain_unknown")}</p>}
    <div className={shapStyles.legend} aria-hidden="true"><span>{t("ux_shap_negative")}</span><span className={shapStyles.origin}>0</span><span>{t("ux_shap_positive")}</span></div>
    <div className={shapStyles.plot}>
      <div className={shapStyles.axis} aria-hidden="true"/>
      {Object.entries(values).map(([key,value])=>{
        const side=direction(value);
        const label=explanations[key].label;
        return <button type="button" key={key} className={shapStyles.row} data-direction={side} data-shap-feature={key} data-shap-value={value}
          aria-label={`${label}: ${value>0?"+":""}${value}. ${t(`ux_shap_${side}`)}`} aria-haspopup="dialog" onClick={()=>setSelected(key)}>
          <span className={shapStyles.featureLabel}><span>{label}</span><Info size={14} aria-hidden="true"/></span>
          <span className={shapStyles.graphHalf} aria-hidden="true">
            <span className={shapStyles.barSpace}><span className={shapStyles.bar} style={{width:`${Math.abs(value)/max*100}%`}}/></span>
            <span className={shapStyles.value} title={String(value)}>{value>0?"+":""}{value.toFixed(3)}</span>
          </span>
        </button>;
      })}
    </div>
    <dialog ref={dialog} className={shapStyles.dialog} aria-labelledby={`${uid}-title`} aria-describedby={`${uid}-description`}
      onClose={()=>setSelected(null)} onCancel={()=>setSelected(null)}
      onKeyDown={event=>{
        if(event.key!=="Tab")return;
        const stops=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])')];
        const first=stops[0],last=stops[stops.length-1];if(!first)return;
        if((event.shiftKey&&document.activeElement===first)||(!event.shiftKey&&document.activeElement===last)){event.preventDefault();(event.shiftKey?last:first).focus();}
      }}
      onClick={event=>{if(event.target!==event.currentTarget)return;const r=event.currentTarget.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)setSelected(null);}}>
      <div className={shapStyles.dialogHeader}><h4 id={`${uid}-title`}>{selected===null?t("ux_shap_title"):explanations[selected].label}</h4><button type="button" className={resultStyles.action} onClick={()=>setSelected(null)}>{t("ux_shap_close")}</button></div>
      <p id={`${uid}-description`} className={resultStyles.note}>{selected===null?"":explanations[selected].desc}</p>
      {selected!==null&&typeof selectedValue==="number"&&<>
        <dl className={shapStyles.detailRows}>
          <div><dt>{t("pr_xai_value_shap")}</dt><dd data-shap-exact="true">{selectedValue>0?"+":""}{String(selectedValue)}</dd></div>
          <div><dt>{t("pr_xai_effect")}</dt><dd>{t(`ux_shap_${direction(selectedValue)}`)}</dd></div>
        </dl>
        <p className={resultStyles.note}><code>{selected}</code></p>
        <p className={resultStyles.note}>{t("ux_shap_scope")}</p>
      </>}
    </dialog>
  </section>;
}
