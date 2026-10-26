"use client";

import React, { useState, useEffect, useId, useRef } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { motion } from "framer-motion";
import {useResultReading} from "./ResultReadingPresentation";
import resultStyles from "./ResultPanels.module.css";
import shapStyles from "./ProXaiShap.module.css";
import {RESULT_FIELD_PRESENTATION} from "@/lib/resultFieldPresentation";
import { Activity, Info, Sliders } from "lucide-react";
import { getGnnAttentionSvg } from "../../../lib/api";
import {ContactMapPanel} from "./ContactMapPanel";

const SHAP_EXPLANATIONS: Record<string, { label: string; desc: string }> = {
  "ecif_N_don_C": { label: "Contactos N-donador \u2192 C", desc: "Cercan\u00eda entre nitr\u00f3genos donadores del ligando y carbonos del bolsillo. NO es un puente de hidr\u00f3geno: el carbono no tiene pares libres ni la electronegatividad para aceptarlo. Mide empaquetamiento y polarizaci\u00f3n." },
  "ecif_N_don_N": { label: "Pares N-donador \u2192 N", desc: "Par compatible con un puente de hidr\u00f3geno, pero ECIF cuenta contactos dentro de un radio de corte: no comprueba geometr\u00eda ni \u00e1ngulo." },
  "ecif_N_don_O": { label: "Pares N-donador \u2192 O", desc: "Par donador-aceptor compatible con puente de hidr\u00f3geno. ECIF lo cuenta por distancia, sin verificar el \u00e1ngulo D-H\u22efA." },
  "ecif_O_don_C": { label: "Contactos O-donador \u2192 C", desc: "Cercan\u00eda entre ox\u00edgenos donadores del ligando y carbonos del bolsillo. NO es un puente de hidr\u00f3geno, por la misma raz\u00f3n: el carbono no acepta. Mide empaquetamiento." },
  "ecif_O_don_O": { label: "Pares O-donador \u2192 O", desc: "Par donador-aceptor compatible con puente de hidr\u00f3geno, contado por distancia y sin geometr\u00eda." },
  "ecif_O_don_N": { label: "Pares O-donador \u2192 N", desc: "Par donador-aceptor compatible con puente de hidr\u00f3geno, contado por distancia y sin geometr\u00eda." },
  "ecif_C_C": { label: "Contactos C-C (Van der Waals)", desc: "Contactos hidrof\u00f3bicos entre \u00e1tomos de Carbono del ligando y de la prote\u00edna." },
  "ecif_C_N": { label: "Contactos C-N", desc: "Contactos at\u00f3micos entre Carbonos y Nitr\u00f3genos." },
  "ecif_C_O": { label: "Contactos C-O", desc: "Contactos at\u00f3micos entre Carbonos y Ox\u00edgenos." },
  "ecif_P_don_O": { label: "Interacci\u00f3n F\u00f3sforo-Ox\u00edgeno", desc: "Contactos at\u00f3micos con grupos fosfato." },
  "ecif_S_don_O": { label: "Interacci\u00f3n Azufre-Ox\u00edgeno", desc: "Contactos at\u00f3micos involucrando tioles o grupos azufrados." },
  "shell_C_C_4_8": { label: "Empaquetamiento (4-8 \u00c5)", desc: "Densidad de Carbonos alrededor del ligando en la franja de distancia media de 4 a 8 \u00c5ngstr\u00f6ms." },
  "shell_C_O_4_8": { label: "Entorno C-O (4-8 \u00c5)", desc: "Contactos de medio alcance entre Carbonos y Ox\u00edgenos." },
  "shell_N_N_0_4": { label: "Contactos N-N (< 4 \u00c5)", desc: "Densidad de Nitr\u00f3genos interactuando fuertemente a menos de 4 \u00c5ngstr\u00f6ms." },
  "shell_O_C_4_8": { label: "Entorno O-C (4-8 \u00c5)", desc: "Densidad de Ox\u00edgenos en un rango intermedio alrededor del ligando." },
  "shell_C_C_8_12": { label: "Influencia Lejana (8-12 \u00c5)", desc: "Efectos conformacionales y est\u00e9ricos de largo alcance ejercidos por los Carbonos del bolsillo." },
  "shell_N_C_8_12": { label: "Entorno N-C (8-12 \u00c5)", desc: "Contactos de largo alcance en el borde del solvente o la superficie proteica exterior." },
  "close_contacts_4A": { label: "Contactos Directos (< 4 \u00c5)", desc: "N\u00famero total de colisiones e interacciones at\u00f3micas \u00edntimas. Fuerte indicador de encaje espacial." },
  "close_contacts_6A": { label: "Contactos Cercanos (< 6 \u00c5)", desc: "N\u00famero total de contactos en la primera y segunda esfera de solvataci\u00f3n del bolsillo." },
  "close_contacts_8A": { label: "Contactos Extendidos (< 8 \u00c5)", desc: "Densidad at\u00f3mica en la cavidad de uni\u00f3n extendida." },
  // ── Keys reales del backend (model_manager.predict → shap_values) ──────────
  // El backend emite estos keys con nombres tipo feature engineering. Sin
  // label explícito caerían al fallback genérico ("vina best score", "mw")
  // que es incomprensible para un químico. Añadimos labels/descs científicos.
  "vina_best_score": { label: "Afinidad Vina (mejor pose)", desc: "Score de docking del mejor pose de AutoDock Vina. Un SHAP positivo indica que poses m\u00e1s afines empujan el score del modelo hacia arriba." },
  "mw": { label: "Peso molecular (MW)", desc: "Descriptor 1D/2D del ligando. Las mol\u00e9culas m\u00e1s pesadas pueden correlacionar con cambios sistem\u00e1ticos en el score del modelo." },
  "pose_score_variance": { label: "Varianza entre poses", desc: "Dispersi\u00f3n de las afinidades entre las poses generadas. Una varianza alta sugiere un bolsillo ambiguo con m\u00faltiples modos de uni\u00f3n." },
  "pose_score_range": { label: "Rango de scores entre poses", desc: "Diferencia entre la mejor y la peor pose de docking. Indica qu\u00e9 tan discriminante es el score en el espacio conformacional muestreado." },
  "shell_C_N_0_4": { label: "Entorno C-N (< 4 \u00c5)", desc: "Densidad de pares Carbono-Nitr\u00f3geno en contacto \u00edntimo (< 4 \u00c5). Puede reflejar puentes de H impl\u00edcitos o empaquetamiento polar cercano." },
  "shell_O_C_8_10": { label: "Entorno O-C (8-10 \u00c5)", desc: "Densidad de pares Ox\u00edgeno-Carbono en el borde del solvente (8-10 \u00c5). Contribuye al contexto est\u00e9rico de largo alcance." },
  "ecif_C_ali_O": { label: "Contactos C-alif\u00e1tico \u2192 O", desc: "Pares entre \u00e1tomos de carbono alif\u00e1tico del ligando y ox\u00edgenos del bolsillo. Captura interacciones dipolo-dipolo y puentes de H con aceptores." },
};

function getFeatureExplanation(feature: string) {
  if (SHAP_EXPLANATIONS[feature]) return SHAP_EXPLANATIONS[feature];
  if (feature.startsWith("ecif_")) {
    const pair = feature.replace("ecif_", "").replace(/_/g, "-");
    return { label: `Interacci\u00f3n ${pair}`, desc: "Interacci\u00f3n espec\u00edfica de pares at\u00f3micos (ECIF)." };
  }
  if (feature.startsWith("shell_")) {
    const parts = feature.split("_");
    const dist = parts.slice(parts.length - 2).join("-");
    const atoms = parts.slice(1, parts.length - 2).join("-");
    return { label: `Capa Distancia ${atoms} (${dist} \u00c5)`, desc: "Densidad at\u00f3mica en un anillo tridimensional espec\u00edfico." };
  }
  return { label: feature.replace(/_/g, " "), desc: "Propiedad f\u00edsico-qu\u00edmica extra\u00edda del complejo molecular." };
}

function ShapContributionChart({values}:{values:Record<string,number>}) {
  const {t,locale}=useLanguage();
  const uid=useId();
  const [selected,setSelected]=useState<string|null>(null);
  const dialog=useRef<HTMLDialogElement>(null);
  const max=Math.max(...Object.values(values).map(value=>Math.abs(value)))||1;
  const label=(key:string)=>{
    if(key==="vina_best_score")return t("ux_vina_best");
    const meta=RESULT_FIELD_PRESENTATION[key==="mw"?"molecular_weight":key];
    return meta?(locale==="en"?meta.en:meta.es):t(getFeatureExplanation(key).label);
  };
  const direction=(value:number)=>value>0?"positive":value<0?"negative":"zero";
  useEffect(()=>{
    const node=dialog.current;if(!node)return;
    if(selected!==null&&!node.open)node.showModal();
    else if(selected===null&&node.open)node.close();
  },[selected]);
  const selectedValue=selected===null?null:values[selected];
  return <section className={`${resultStyles.section} ${shapStyles.chart}`} aria-label={t("ux_shap_title")} data-shap-chart="true">
    <div className={resultStyles.sectionHeader}><h4>{t("ux_shap_title")}</h4></div>
    <p className={resultStyles.intro}>{t("ux_shap_scope")}</p>
    <div className={shapStyles.legend} aria-hidden="true"><span>{t("ux_shap_negative")}</span><span className={shapStyles.origin}>0</span><span>{t("ux_shap_positive")}</span></div>
    <div className={shapStyles.plot}>
      <div className={shapStyles.axis} aria-hidden="true"/>
      {Object.entries(values).map(([key,value])=>{
        const side=direction(value);
        return <button type="button" key={key} className={shapStyles.row} data-direction={side} data-shap-feature={key} data-shap-value={value}
          aria-label={`${label(key)}: ${value>0?"+":""}${value}. ${t(`ux_shap_${side}`)}`} aria-haspopup="dialog" onClick={()=>setSelected(key)}>
          <span className={shapStyles.featureLabel}><span>{label(key)}</span><Info size={14} aria-hidden="true"/></span>
          <span className={shapStyles.graphHalf} aria-hidden="true">
            <span className={shapStyles.barSpace}><span className={shapStyles.bar} style={{width:`${Math.abs(value)/max*100}%`}}/></span>
            <span className={shapStyles.value} title={String(value)}>{value>0?"+":""}{value.toFixed(3)}</span>
          </span>
        </button>;
      })}
    </div>
    <p className={resultStyles.note}>{t("ux_shap_scale")}</p>
    <dialog ref={dialog} className={shapStyles.dialog} aria-labelledby={`${uid}-title`} aria-describedby={`${uid}-description`}
      onClose={()=>setSelected(null)} onCancel={()=>setSelected(null)}
      onKeyDown={event=>{
        if(event.key!=="Tab")return;
        const stops=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])')];
        const first=stops[0],last=stops[stops.length-1];if(!first)return;
        if((event.shiftKey&&document.activeElement===first)||(!event.shiftKey&&document.activeElement===last)){event.preventDefault();(event.shiftKey?last:first).focus();}
      }}
      onClick={event=>{if(event.target!==event.currentTarget)return;const r=event.currentTarget.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)setSelected(null);}}>
      <div className={shapStyles.dialogHeader}><h4 id={`${uid}-title`}>{selected===null?t("ux_shap_title"):label(selected)}</h4><button type="button" className={resultStyles.action} onClick={()=>setSelected(null)}>{t("ux_shap_close")}</button></div>
      <p id={`${uid}-description`} className={resultStyles.note}>{selected==="vina_best_score"?t("ux_vina_feature_scope"):selected===null?"":t(getFeatureExplanation(selected).desc)}</p>
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

const GnnAttentionSvg = React.memo(({ svg, className }: { svg: string; className?: string }) => {
  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
});
GnnAttentionSvg.displayName = "GnnAttentionSvg";

interface Props {
  shapValues: Record<string, number> | null | undefined;
  gnnAttention: unknown;
  gnnAttentionSvg: string | null | undefined;
  gnnPharmacophores: unknown;
  /** UI-7 (2026-08-04): id de molécula para fetchear el SVG on-demand. */
  moleculeId?: string | null;
  taskId?: string | null;
  poses?: readonly {rank:number}[] | null;
  /** F-21: dominio de aplicabilidad del modelo (dist. Mahalanobis). */
  inApplicabilityDomain?: boolean | null;
  /** F-21: motivo del fallback a modelo universal (quality gate). */
  fallbackReason?: string | null;
  // Nota: target_spearman_rho NO se incluye aquí — ya se renderiza en el
  // cabeceras de ProEvaluation y ReproducibilityInfo (regla 4).
}

export function ProXaiTab({ shapValues, gnnAttention, gnnAttentionSvg, gnnPharmacophores, moleculeId, taskId, poses, inApplicabilityDomain, fallbackReason }: Props) {
  const { t } = useLanguage();
  const reading=useResultReading();
  const [expandedSHAP, setExpandedSHAP] = useState<string | null>(null);
  const [expandedGNN, setExpandedGNN] = useState<"2d" | "1d" | null>(null);
  // UI-7: el SVG ya no viaja en el polling; lo fetcheamos on-demand cuando el
  // usuario abre este tab y aún no tenemos el valor en memoria.
  const [fetchedSvg, setFetchedSvg] = useState<string | null | undefined>(undefined);
  const [fetchedAtt, setFetchedAtt] = useState<number[] | null | undefined>(undefined);

  const hasShap = shapValues && Object.keys(shapValues).length > 0;

  // On-demand fetch del SVG de atención GNN (solo si este tab está montado).
  useEffect(() => {
    if (!moleculeId || reading.enabled) return;
    if (gnnAttentionSvg) { setFetchedSvg(gnnAttentionSvg); return; }
    let cancelled = false;
    getGnnAttentionSvg(moleculeId).then((data) => {
      if (cancelled || !data) return;
      if (data.gnn_attention_svg) setFetchedSvg(data.gnn_attention_svg);
      if (data.gnn_attention && data.gnn_attention.length > 0) setFetchedAtt(data.gnn_attention);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [moleculeId, gnnAttentionSvg, reading.enabled]);

  // El SVG efectivo: prop (legacy) > fetch on-demand.
  const effectiveSvg = gnnAttentionSvg ?? fetchedSvg ?? null;
  const effectiveAtt = gnnAttention ?? fetchedAtt ?? null;

  return (
    <>
      <div className="space-y-3 animate-in fade-in duration-200">
        {hasShap ? (
          <div className="space-y-4">
            {reading.enabled ? <ShapContributionChart values={shapValues!}/> : <>
            <div className="font-sans text-base leading-6 text-slate-300 mb-2 font-sans bg-gradient-to-r from-indigo-500/10 to-transparent p-3.5 rounded-xl border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.05)]">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></div>
                <span className="text-indigo-300 font-bold tracking-wider">{t("pr_xai_shap_nativo")}</span>
              </div>
              <p className="opacity-90 leading-6">
                {t("pr_xai_abejas_a")} <span className="text-emerald-400 font-bold">{t("pr_xai_right_green")}</span> {t("pr_xai_abejas_b")} <span className="text-rose-400 font-bold">{t("pr_xai_left_red")}</span> {t("pr_xai_abejas_c")}
              </p>
            </div>

            <div className="relative py-2 mt-2">
              <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/10 z-0"></div>
              <div className="space-y-3.5 relative z-10">
                {(() => {
                  const entries = Object.entries(shapValues!);
                  const maxAbs = Math.max(...entries.map(([_, v]) => Math.abs(v)), 0.001);
                  return entries.map(([feature, val], idx) => {
                    const isPositive = val > 0;
                    const widthPercent = (Math.abs(val) / maxAbs) * 100;
                    return (
                      <motion.div
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: idx * 0.05 }}
                        key={feature}
                        onClick={() => setExpandedSHAP(feature)}
                        className="group relative flex items-center w-full cursor-pointer hover:bg-white/5 py-1.5 px-2 rounded-lg transition-all duration-200"
                      >
                        <div className="w-1/2 flex justify-end items-center pr-2 h-3.5">
                          {!isPositive && (
                            <>
                              <span className="font-sans text-base leading-6 font-mono text-rose-300 mr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                {val.toFixed(3)}
                              </span>
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${widthPercent}%` }}
                                transition={{ type: "spring", stiffness: 60, damping: 12, delay: idx * 0.05 }}
                                className="h-full rounded-l-md bg-gradient-to-l from-rose-500/85 to-rose-400 border-y border-l border-rose-400/50 shadow-[0_0_10px_rgba(244,63,94,0.35)] relative"
                              />
                            </>
                          )}
                          {isPositive && (
                            <div className="flex items-center justify-end w-full pl-2">
                              <span className="text-sm uppercase font-sans font-bold text-slate-400 group-hover:text-indigo-300 transition-colors truncate pr-1 text-right">
                                {t(getFeatureExplanation(feature).label)}
                              </span>
                              <Info size={10} className="text-zinc-400 group-hover:text-indigo-400 transition-colors flex-shrink-0" />
                            </div>
                          )}
                        </div>
                        <div className="w-1/2 flex justify-start items-center pl-2 h-3.5">
                          {isPositive && (
                            <>
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${widthPercent}%` }}
                                transition={{ type: "spring", stiffness: 60, damping: 12, delay: idx * 0.05 }}
                                className="h-full rounded-r-md bg-gradient-to-r from-emerald-500/85 to-emerald-400 border-y border-r border-emerald-400/50 shadow-[0_0_10px_rgba(16,185,129,0.35)] relative"
                              />
                              <span className="font-sans text-base leading-6 font-mono text-emerald-300 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                +{val.toFixed(3)}
                              </span>
                            </>
                          )}
                          {!isPositive && (
                            <div className="flex items-center justify-start w-full pr-2">
                              <Info size={10} className="text-zinc-400 group-hover:text-indigo-400 transition-colors flex-shrink-0 mr-1" />
                              <span className="text-sm uppercase font-sans font-bold text-slate-400 group-hover:text-indigo-300 transition-colors truncate text-left">
                                {t(getFeatureExplanation(feature).label)}
                              </span>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    );
                  });
                })()}
              </div>
            </div>

            </>}

            {!reading.enabled && Boolean(effectiveAtt) && (
              <div className="mt-5 p-4 bg-black/40 rounded-xl border border-emerald-500/20 relative overflow-hidden">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-emerald-400 font-bold flex items-center gap-1.5 text-sm uppercase tracking-wider">
                    <Activity size={14} /> {t("pr_xai_atencion_gnn")}
                  </span>
                  <span className="text-sm text-slate-400 font-mono">{t("pr_xai_mapa_hotspots")}</span>
                </div>
                <div className="grid grid-cols-2 gap-4 items-stretch">
                  <div
                    onClick={() => { if (effectiveSvg) setExpandedGNN('2d') }}
                    className={`flex flex-col items-center justify-center p-3 bg-slate-900/60 rounded-xl border border-white/5 shadow-inner transition-colors duration-200 ${effectiveSvg ? 'cursor-pointer hover:bg-slate-800/80' : ''}`}
                  >
                    <span className="font-sans text-base leading-6 text-zinc-400 uppercase font-sans mb-2 tracking-widest">{t("pr_xai_topologia")}</span>
                    {effectiveSvg ? (
                      <GnnAttentionSvg
                        svg={effectiveSvg}
                        className="w-full flex justify-center items-center [&>svg]:w-full [&>svg]:max-w-[160px] [&>svg]:h-auto filter drop-shadow-[0_0_8px_rgba(16,185,129,0.2)]"
                      />
                    ) : (
                      <div className="w-full aspect-square max-h-[160px] flex items-center justify-center text-sm text-zinc-400 italic">
                        {t("pr_xai_generando")}
                      </div>
                    )}
                  </div>
                  <div
                    onClick={() => { if (gnnPharmacophores) setExpandedGNN('1d') }}
                    className={`flex flex-col items-center justify-start p-3 bg-slate-900/60 rounded-xl border border-white/5 shadow-inner relative overflow-hidden group transition-colors duration-200 ${gnnPharmacophores ? 'cursor-pointer hover:bg-slate-800/80' : ''}`}
                  >
                    <span className="font-sans text-base leading-6 text-zinc-400 uppercase font-sans mb-2 tracking-widest z-10">{t("pr_xai_farmacoforos")}</span>
                    <div className="w-full flex-grow relative min-h-[120px] z-10 flex items-center justify-center">
                      {(() => {
                        const pharm = gnnPharmacophores as Record<string, number> | null | undefined;
                        if (!pharm) return <div className="text-sm text-zinc-400 italic mt-8">{t("c_no_disponible")}</div>;
                        // FIX (keys alignment, 2026-08-04): las categorías del
                        // radar DEBEN coincidir con los keys reales que genera
                        // backend/services/ai/gnn_explainability.py. Antes
                        // usaban "Aromáticos"/"Alifáticos" (acentuados, sin
                        // "H-Bond") → NUNCA coincidían con los keys del
                        // payload → el radar dibujaba 0 en todos los ejes.
                        // Ver docs/36 UI-5 + UI-6.
                        const PHARM_KEYS: { key: string; label: string }[] = [
                          { key: "Aromaticos / Pi-Stacking", label: t("auto_33238333294a") },
                          { key: "Donadores H-Bond", label: t("pn_spider_donadores_h") },
                          { key: "Aceptores H-Bond", label: t("pn_spider_aceptores_h") },
                          { key: "Contactos Lipofilicos", label: t("auto_ca556f18c671") },
                        ];
                        const categories = PHARM_KEYS.map(pk => pk.label);
                        const cx = 100;
                        const cy = 60;
                        const rMax = 45;
                        const angles = [-90, -18, 54, 126, 198];
                        const points = PHARM_KEYS.map((pk, i) => {
                          const val = (pharm[pk.key] || 0) / 100;
                          const rad = (angles[i] * Math.PI) / 180;
                          return `${cx + rMax * val * Math.cos(rad)},${cy + rMax * val * Math.sin(rad)}`;
                        }).join(' ');
                        const bgPentagons = [1, 0.75, 0.5, 0.25].map(scale =>
                          angles.map(ang => {
                            const rad = (ang * Math.PI) / 180;
                            return `${cx + rMax * scale * Math.cos(rad)},${cy + rMax * scale * Math.sin(rad)}`;
                          }).join(' ')
                        );
                        return (
                          <svg viewBox="0 -10 200 140" className="w-full h-full overflow-visible">
                            <defs>
                              <filter id="glow-radar">
                                <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                                <feMerge>
                                  <feMergeNode in="coloredBlur" />
                                  <feMergeNode in="SourceGraphic" />
                                </feMerge>
                              </filter>
                            </defs>
                            {angles.map((ang, i) => {
                              const rad = (ang * Math.PI) / 180;
                              return (
                                <line key={i} x1={cx} y1={cy} x2={cx + rMax * Math.cos(rad)} y2={cy + rMax * Math.sin(rad)} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                              )
                            })}
                            {bgPentagons.map((pts, i) => (
                              <polygon key={i} points={pts} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                            ))}
                            <motion.polygon
                              initial={{ opacity: 0, scale: 0 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ duration: 1, type: "spring" }}
                              style={{ transformOrigin: `${cx}px ${cy}px` }}
                              points={points}
                              fill="rgba(16,185,129,0.3)"
                              stroke="#34d399"
                              strokeWidth="2"
                              filter="url(#glow-radar)"
                            />
                            {categories.map((cat, i) => {
                              const rad = (angles[i] * Math.PI) / 180;
                              const x = cx + (rMax + 15) * Math.cos(rad);
                              const y = cy + (rMax + 12) * Math.sin(rad);
                              return (
                                <text key={cat} x={x} y={y} textAnchor="middle" alignmentBaseline="middle" fill="#d4d4d8" fontSize="14" className="font-sans">
                                  {cat.substring(0, 4)}
                                </text>
                              )
                            })}
                          </svg>
                        );
                      })()}
                    </div>
                    <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-emerald-900/20 to-transparent pointer-events-none" />
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center text-zinc-400 py-12 px-4 border border-white/5 bg-black/20 rounded-2xl">
            <div className="w-10 h-10 rounded-full bg-slate-800/50 flex items-center justify-center mb-3">
              <Activity size={18} className="text-zinc-400" />
            </div>
            <span className="text-sm font-medium">{t("pr_xai_sin_datos")}</span>
            <span className="text-sm mt-1 opacity-70">{t("pr_xai_shap_poblara")}</span>
          </div>
        )}
      </div>

      {/* ── {t("pr_xai_dominio")} (F-21) ────────────────────────────── */}
      {reading.enabled&&<ContactMapPanel key={`${moleculeId??""}:${taskId??""}`} moleculeId={moleculeId} taskId={taskId} poses={poses}/>}
      <div className="p-4 bg-black/40 rounded-xl border border-white/10 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-sm uppercase font-sans font-bold tracking-wider text-slate-400">
            {t("pr_xai_dominio")}
          </span>
          {inApplicabilityDomain === true ? (
            <span className="text-sm font-mono font-bold px-2 py-0.5 rounded border bg-emerald-500/15 text-emerald-300 border-emerald-500/25">
              {t("auto_21838be6b371")}
            </span>
          ) : inApplicabilityDomain === false ? (
            <span className="text-sm font-mono font-bold px-2 py-0.5 rounded border bg-rose-500/15 text-rose-300 border-rose-500/25">
              {t("pr_xai_fuera_dominio")}
            </span>
          ) : (
            <span className="text-sm font-mono font-bold px-2 py-0.5 rounded border bg-white/5 text-slate-400 border-white/10">
              {t("c_no_disponible")}
            </span>
          )}
        </div>
        {fallbackReason && (
          <p className="text-base text-slate-300 leading-6 font-sans">
            {fallbackReason}
          </p>
        )}
        {reading.enabled&&<p className={resultStyles.note}>{t("cm_domain_scope")}</p>}
      </div>

      {expandedSHAP && (() => {
        const explanation = getFeatureExplanation(expandedSHAP);
        const value = shapValues?.[expandedSHAP];
        const isPositive = typeof value === 'number' ? value > 0 : false;
        return (
          <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
            onClick={() => setExpandedSHAP(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              onClick={e => e.stopPropagation()}
              className="relative w-full max-w-lg bg-[#0a0d16] border border-indigo-500/10 rounded-2xl shadow-2xl overflow-hidden"
            >
              <div className="p-6">
                <h3 className="text-sm font-black uppercase tracking-wider text-indigo-300 mb-3 flex items-center gap-2">
                  <Sliders size={16} className="text-indigo-400" />
                  {t(explanation.label)}
                </h3>
                <p className="text-base text-slate-300 leading-6 mb-4 font-sans">{t(explanation.desc)}</p>
                <div className="bg-black/30 rounded-xl border border-white/5 p-4 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm uppercase font-sans text-slate-400">{t("pr_xai_value_shap")}</span>
                    <span className={`text-lg font-black font-mono ${isPositive ? "text-emerald-400" : "text-rose-400"}`}>
                      {typeof value === 'number' ? (isPositive ? "+" : "") + value.toFixed(4) : "N/A"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm uppercase font-sans text-slate-400">{t("pr_xai_effect")}</span>
                    <span className={`text-sm font-bold ${isPositive ? "text-emerald-400" : "text-rose-400"}`}>
                      {isPositive ? t("auto_ba93a478fc9b") : t("auto_00cf99ca43b6")}
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        );
      })()}

      {expandedGNN && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setExpandedGNN(null)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            onClick={e => e.stopPropagation()}
            className="relative w-full max-w-2xl bg-[#0a0d16] border border-emerald-500/10 rounded-2xl shadow-2xl overflow-hidden"
          >
            <div className="p-6">
              <h3 className="text-sm font-black uppercase tracking-wider text-emerald-300 mb-3 flex items-center gap-2">
                <Activity size={16} className="text-emerald-400" />
                {expandedGNN === "2d" ? t("auto_2a2ce172626f") : t("auto_a2f32be1b030")}
              </h3>
              {expandedGNN === "2d" && effectiveSvg && (
                <div className="bg-black/30 rounded-xl border border-white/5 p-6 flex justify-center">
                  <GnnAttentionSvg svg={effectiveSvg} className="[&>svg]:max-w-full [&>svg]:h-auto" />
                </div>
              )}
              {expandedGNN === "1d" && Boolean(gnnPharmacophores) && (
                <div className="bg-black/30 rounded-xl border border-white/5 p-4">
                  {(gnnPharmacophores as Record<string, number>) && Object.entries(gnnPharmacophores as Record<string, number>).map(([key, val]) => (
                    <div key={key} className="flex justify-between items-center py-1.5 border-b border-white/5 last:border-0">
                      <span className="text-sm font-mono text-slate-300">{key}</span>
                      <span className="text-sm font-mono font-bold text-emerald-400">{val.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </>
  );
}
