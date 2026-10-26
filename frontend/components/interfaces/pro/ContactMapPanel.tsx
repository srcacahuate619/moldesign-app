"use client";
import {useEffect,useId,useMemo,useState} from "react";
import {useLanguage} from "@/context/LanguageContext";
import {useKeepAliveActive} from "@/context/KeepAliveContext";
import {getContactMap} from "@/lib/api";
import type {InteractionsReport} from "@/lib/types";
import panels from "./ResultPanels.module.css";
import styles from "./ContactMapPanel.module.css";

type Load={key:string;state:"loading"|"ready"|"error";report?:InteractionsReport;error?:string};
/** El motor ProLIF se declara como «prolif:<versión>» en `engine`. */
const esProlif=(engine:string)=>/^prolif:/.test(engine);
const hex=(value:unknown)=>typeof value==="string"&&/^[a-f0-9]{64}$/i.test(value);
export function contactMapMatches(report:InteractionsReport,molecule:string,task:string,rank:number):boolean {
  if(!report||!Array.isArray(report.interactions))return false;
  if(report.molecule_id!==molecule||report.task_id!==task||report.pose_rank!==rank||!hex(report.pose_source_sha256)||!hex(report.protein_source_sha256)||report.total_interactions!==report.interactions.length)return false;
  const map=report.contact_map;
  if(map?.status!=="ready")return true;
  if(!hex(map.analysis_ligand_sha256)||map.analysis_ligand_sha256!==report.analysis_ligand_sha256||!map.svg?.includes("<svg")||!map.width||!map.height||!Number.isFinite(map.width)||!Number.isFinite(map.height)||!Array.isArray(map.atoms)||!Array.isArray(map.contacts)||!Array.isArray(map.highlighted_atom_indices))return false;
  const indices=new Set(map.atoms.map(atom=>atom.index));
  if(indices.size!==map.atoms.length||map.atoms.some(atom=>!Number.isInteger(atom.index)||atom.index<0||!Number.isFinite(atom.x)||!Number.isFinite(atom.y)))return false;
  if(map.contacts.length!==report.interactions.length||new Set(map.contacts.map(item=>item.contact_index)).size!==map.contacts.length)return false;
  return map.contacts.every(contact=>Number.isInteger(contact.contact_index)&&contact.contact_index>=0&&contact.contact_index<report.interactions.length&&Array.isArray(contact.atom_indices)&&contact.atom_indices.every(index=>indices.has(index)&&report.interactions[contact.contact_index].ligand_atom_indices?.includes(index)))&&map.highlighted_atom_indices.every(index=>indices.has(index)&&map.contacts!.some(contact=>contact.atom_indices.includes(index)));
}

export function ContactMapPanel({moleculeId,taskId,poses}:{moleculeId?:string|null;taskId?:string|null;poses?:readonly {rank:number}[]|null}) {
  const {t}=useLanguage(),uid=useId(),active=useKeepAliveActive();
  const ranks=[...new Set((poses??[{rank:1}]).map(pose=>pose.rank).filter(rank=>Number.isInteger(rank)&&rank>=1))];
  const [chosenRank,setChosenRank]=useState(1),[selected,setSelected]=useState<number|null>(null),[attempt,setAttempt]=useState(0);
  const [zoom,setZoom]=useState(1);
  const rank=ranks.includes(chosenRank)?chosenRank:ranks[0]??1,key=`${moleculeId??""}:${taskId??""}:${rank}`;
  const [load,setLoad]=useState<Load|null>(null);
  useEffect(()=>{
    if(!active||!moleculeId||!taskId||!ranks.length||rank>20)return;
    const controller=new AbortController();setSelected(null);setLoad({key,state:"loading"});
    getContactMap(moleculeId,taskId,rank,controller.signal).then(report=>{
      if(controller.signal.aborted)return;
      if(!contactMapMatches(report,moleculeId,taskId,rank))throw new Error(t("cm_mismatch"));
      setLoad({key,state:"ready",report});
    }).catch(error=>{if(!controller.signal.aborted)setLoad({key,state:"error",error:error instanceof Error?error.message:t("cm_error")});});
    return()=>controller.abort();
  },[active,moleculeId,taskId,rank,key,attempt,ranks.length,t]);
  const current=load?.key===key?load:null,report=current?.state==="ready"?current.report:null,map=report?.contact_map;
  const image=useMemo(()=>map?.status==="ready"&&map.svg?`data:image/svg+xml;charset=utf-8,${encodeURIComponent(map.svg)}`:null,[map]);
  const picked=selected===null?null:report?.interactions[selected],mapping=selected===null?null:map?.contacts?.find(item=>item.contact_index===selected);
  const atoms=map?.atoms?.filter(atom=>mapping?.atom_indices.includes(atom.index))??[];
  const angle=picked?.geometry?.DHA_angle??picked?.angle;
  const kind=(type:string)=>{if(type==="hydrophobic"&&report?.engine==="distancias_sin_quimica")return t("cm_cc_distance");const name=t(`cm_type_${type}`);return name===`cm_type_${type}`?type:name;};
  return <section className={`${panels.section} ${styles.root}`} aria-labelledby={`${uid}-title`} data-contact-map="true" data-contact-task={report?.task_id} data-contact-pose={report?.pose_rank}>
    <div className={panels.sectionHeader}><h4 id={`${uid}-title`}>{t("cm_title")}</h4><span className={panels.source}>{t("cm_geometry")}</span></div>
    <p className={panels.intro}>{t("cm_scope")}</p>
    {!moleculeId||!taskId?<p className={panels.note}>{t("cm_missing_run")}</p>:!ranks.length?<p className={panels.note}>{t("cm_missing_pose")}</p>:<>
      <div className={styles.toolbar}><label htmlFor={`${uid}-pose`}>{t("cm_pose")}<select aria-label={t("cm_pose")} id={`${uid}-pose`} value={rank} onChange={event=>{setChosenRank(Number(event.target.value));setSelected(null);}}>{ranks.map(value=><option key={value} value={value} disabled={value>20}>{t("cm_pose_number",{rank:value})}{value>20?` · ${t("cm_pose_limit")}`:""}</option>)}</select></label><span>{t("cm_independent")}</span></div>
      {rank>20?<p className={panels.note}>{t("cm_pose_limit")}</p>:!current||current.state==="loading"?<p role="status" className={panels.note}>{t("cm_loading")}</p>:current.state==="error"?<div role="status" className={panels.warning}><p>{t("cm_error")}</p><p>{current.error}</p><button className={panels.action} type="button" onClick={()=>setAttempt(value=>value+1)}>{t("cm_retry")}</button></div>:report&&<>
        <p className={panels.note}>{t("cm_computed")}{" "}<strong>{report.engine}</strong></p>
        {report.engine==="distancias_sin_quimica"?<p className={panels.warning}>{t("cm_distance_scope")}</p>:!esProlif(report.engine)?<p className={panels.note}>{t("cm_unknown_method")}</p>:null}
        <div className={styles.workspace}>
          <figure className={styles.figure}>
            {image&&map?.status==="ready"?<>
              <div className={styles.zoom}>
                <button type="button" className={panels.action} aria-label={t("cm_zoom_out")} disabled={zoom<=1} onClick={()=>setZoom(value=>Math.max(1,value-.5))}>−</button>
                <output aria-label={t("cm_zoom_scale")}>{Math.round(zoom*100)}%</output>
                <button type="button" className={panels.action} aria-label={t("cm_zoom_in")} disabled={zoom>=3} onClick={()=>setZoom(value=>Math.min(3,value+.5))}>+</button>
                <button type="button" className={panels.action} disabled={zoom===1} onClick={()=>setZoom(1)}>{t("cm_zoom_reset")}</button>
              </div>
              <div className={styles.paperViewport}><div className={styles.paper} style={{width:`${zoom*100}%`}}><img src={image} alt={t("cm_image_alt",{rank})} width={map.width} height={map.height}/><svg className={styles.overlay} viewBox={`0 0 ${map.width} ${map.height}`} aria-hidden="true">{atoms.map(atom=><circle key={atom.index} data-selected-contact-atom={atom.index} cx={atom.x} cy={atom.y} r={18} className={styles.selectedAtom}/>)}</svg></div></div><figcaption><span className={styles.swatch} aria-hidden="true"/>{t("cm_legend")}<p>{t("cm_numbering")}</p></figcaption></>:<div className={styles.noDiagram}><p>{t("cm_no_diagram")}</p>{map?.reason&&<code>{map.reason}</code>}</div>}
          </figure>
          <div className={styles.contacts}><h5>{t("cm_count",{count:report.total_interactions})}</h5>
            {report.interactions.length?<div className={styles.contactList} role="group" aria-label={t("cm_contact_list")}>{report.interactions.map((contact,index)=><button type="button" key={index} data-contact-index={index} aria-pressed={selected===index} onClick={()=>setSelected(value=>value===index?null:index)}><span><strong>{contact.residue_name?`${contact.residue_chain||"—"}:${contact.residue_name}${contact.residue_number}`:contact.residue}</strong><span>{kind(contact.type)}</span></span><span>{contact.distance} Å</span></button>)}</div>:<p className={panels.note}>{t("cm_no_contacts")}</p>}
            {picked?<div className={styles.selection} aria-live="polite" data-contact-selection="true"><h5>{kind(picked.type)} · {picked.residue}</h5><dl>
              <div><dt>{t("cm_reported_distance")}</dt><dd>{picked.distance} Å</dd></div>
              <div><dt>{t("cm_ligand_atoms")}</dt><dd>{picked.ligand_atom_indices?.map(index=>{const atom=map?.atoms?.find(item=>item.index===index);return atom?`${atom.element}${index}`:String(index);}).join(", ")||t("cm_not_recorded")}</dd></div>
              <div><dt>{t("cm_definition")}</dt><dd>{picked.definition??t("cm_not_recorded")}</dd></div>
            </dl>{!mapping?.atom_indices.length&&<p className={panels.warning}>{t("cm_unmapped")}</p>}{!!mapping?.hidden_hydrogen_indices.length&&<p className={panels.note}>{t("cm_hidden_hydrogens",{count:mapping.hidden_hydrogen_indices.length})}</p>}
              <details className={panels.details}><summary>{t("cm_measures")}</summary><dl className={styles.measures}><div><dt>{t("cm_protein_atom")}</dt><dd>{picked.protein_atom??t("cm_not_recorded")}</dd></div><div><dt>{picked.geometry?.DHA_angle!==undefined?t("cm_dha_angle"):t("cm_reported_angle")}</dt><dd>{angle===null||angle===undefined?t("cm_not_recorded"):`${angle.toFixed(1)}°`}</dd></div>{Object.entries(picked.geometry??{}).map(([name,value])=><div key={name}><dt><code>{name}</code></dt><dd>{String(value)}</dd></div>)}</dl></details>
              <details className={panels.details}><summary>{t("cm_raw_contact")}</summary><p className={panels.note}>{t("cm_strength_scope")}</p><pre className={styles.raw}>{JSON.stringify(picked,null,2)}</pre></details>
            </div>:<p className={panels.note}>{t("cm_select_contact")}</p>}
          </div>
        </div>
        <p className={panels.note}>{t("cm_limits")}</p>
        <details className={panels.details}><summary>{t("cm_provenance")}</summary>{esProlif(report.engine)&&<p className={panels.note}>{t("cm_prolif_scope")}</p>}<dl className={styles.provenance}>
          <div><dt>{t("cm_pose_verification")}</dt><dd>{report.pose_identity_verification==="verified_ensemble_geometry"?t("cm_verified_ensemble"):report.pose_identity_verification==="stored_run_path_and_current_file_hash"?t("cm_stored_file"):t("cm_not_recorded")}</dd></div>
          <div><dt>{t("cm_run")}</dt><dd><code>{report.task_id}</code></dd></div><div><dt>{t("cm_time")}</dt><dd>{report.computed_at??t("cm_not_recorded")}</dd></div><div><dt>{t("cm_method")}</dt><dd>{report.engine}</dd></div><div><dt>{t("cm_hydrogens")}</dt><dd><code>{report.hydrogen_model??t("cm_not_recorded")}</code></dd></div><div><dt>{t("cm_coverage")}</dt><dd><code>{report.contact_coverage??t("cm_not_recorded")}</code></dd></div><div><dt>{t("cm_pose_source")}</dt><dd>{report.pose_source_kind??t("cm_not_recorded")}</dd></div><div><dt>{t("cm_pose_hash")}</dt><dd><code>{report.pose_source_sha256}</code></dd></div><div><dt>{t("cm_analysis_hash")}</dt><dd><code>{report.analysis_ligand_sha256??t("cm_not_recorded")}</code></dd></div><div><dt>{t("cm_receptor_hash")}</dt><dd><code>{report.protein_source_sha256}</code></dd></div><div><dt>{t("cm_renderer")}</dt><dd>{map?.renderer??t("cm_not_recorded")}</dd></div>
        </dl></details>
      </>}
    </>}
  </section>;
}
