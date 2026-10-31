"use client";

/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V4 */
import { useId, useMemo, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { RESULT_FIELD_KEYS } from "@/lib/resultFieldKeys";
import { RESULT_DATA_GROUPS, resultFieldMatches, resultFieldPresentation, type ResultDataGroup } from "@/lib/resultFieldPresentation";
import styles from "./ResultPanels.module.css";

const FILE_FIELDS = new Set(["receptor_path", "poses_file_path"]);
function logicalValue(value: unknown, key = "", path = ""): unknown {
  const isFile = FILE_FIELDS.has(key) || /(?:path|file|directory|carpeta|ruta)/i.test(key);
  if (typeof value === "string" && isFile && /^(?:[A-Za-z]:[\\/]|\\\\|\/)/.test(value)) {
    const name = value.split(/[\\/]/).filter(Boolean).pop() ?? "archivo";
    return { referencia_archivo: name, identificador_logico: `resultado:${path}`, ruta_local_reservada: true, disponibilidad: "no_comprobada" };
  }
  if (Array.isArray(value)) return value.map((item,index) => logicalValue(item, key, `${path}/${index}`));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, logicalValue(v,k,`${path}/${k.replace(/~/g,"~0").replace(/\//g,"~1")}`)]));
  return value;
}

export function runDataFields(result: object) {
  const record = result as Record<string, unknown>;
  return Array.from(new Set<string>([...RESULT_FIELD_KEYS, ...Object.keys(record)])).sort().map(key => ({
    key, state: !(key in record) || record[key] === undefined ? "absent" : record[key] === null ? "null" : "recorded",
    value: logicalValue(record[key], key, `/${key}`),
  }));
}
function DataValue({ value }: { value: unknown }) {
  const { t } = useLanguage();
  if (value === null || value === undefined) return <span className="text-zinc-400">{t(value === null ? "rx_nulo" : "rx_ausente")}</span>;
  if (typeof value === "boolean") return <span className="font-mono text-zinc-200">{value ? "true" : "false"}</span>;
  if (typeof value !== "object") return <span className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-zinc-200 [overflow-wrap:anywhere]">{String(value)}</span>;
  const entries = Object.entries(value);
  if (entries.length === 0) return <span className="text-zinc-400">{t(Array.isArray(value) ? "rx_lista_vacia" : "rx_objeto_vacio")}</span>;
  return <dl className="min-w-0 divide-y divide-white/5 border-l border-white/10 pl-3">{entries.map(([key,item]) => <div key={key} className="min-w-0 py-2"><dt className="mb-1 break-words font-mono text-sm text-zinc-400">{key}</dt><dd className="min-w-0"><DataValue value={item} /></dd></div>)}</dl>;
}
export function RunDataExplorer({ result }: { result: object }) {
  const { t, locale } = useLanguage();
  const uid = useId();
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<ResultDataGroup | "all">("all");
  const [state, setState] = useState("all");
  const [copyState, setCopyState] = useState<"idle"|"ok"|"error">("idle");
  const fields = useMemo(() => runDataFields(result), [result]);
  const visible = fields.filter(field => (group === "all" || resultFieldPresentation(field.key).group === group)
    && (state === "all" || field.state === state) && resultFieldMatches(field.key, field.value, query));
  const exported = JSON.stringify({ schema: "moldesign.resultado-consultable/1", representation: "Consultable view. Absolute local file paths are reserved and replaced with distinct field references; logical relative locators are preserved. This is not the original backend payload.", fields }, null, 2);
  const download = () => {
    const url = URL.createObjectURL(new Blob([exported], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = t("pr_frontend_109"); a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className={styles.section} aria-labelledby={`${uid}-data-title`} data-run-data="true">
    <div className={styles.sectionHeader}><h4 id={`${uid}-data-title`}>{t("rx_datos_titulo")}</h4></div>
    <p className={styles.intro}>{t("ux_data_scope")}</p>
    <div className={styles.filters}>
      <label className={styles.filter}>{t("rx_buscar")}<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={t("ux_data_search_hint")} /></label>
      <label className={styles.filter}>{t("ux_group_filter")}<select aria-label={t("ux_group_filter")} value={group} onChange={e => setGroup(e.target.value as ResultDataGroup | "all")}>
        <option value="all">{t("ux_group_all")} ({fields.length})</option>
        {RESULT_DATA_GROUPS.map(id => <option key={id} value={id}>{t(`ux_group_${id}`)} ({fields.filter(field => resultFieldPresentation(field.key).group === id).length})</option>)}
      </select></label>
      <label className={styles.filter}>{t("ux_state_filter")}<select aria-label={t("ux_state_filter")} value={state} onChange={e => setState(e.target.value)}>
        <option value="all">{t("ux_state_all")}</option>
        {["recorded","null","absent"].map(id => <option key={id} value={id}>{t(`ux_state_${id}`)} ({fields.filter(field => field.state === id).length})</option>)}
      </select></label>
    </div>
    <div className={styles.dataActions}>
      <p role="status" className={styles.dataCount}>{t("rx_campos", { count: visible.length, total: fields.length })}{copyState !== "idle" && <> · <span>{t(copyState === "ok" ? "rx_copiado" : "rx_error_copia")}</span></>}</p>
      {(query || group !== "all" || state !== "all") && <button type="button" className={styles.action} onClick={() => {setQuery("");setGroup("all");setState("all");}}>{t("ux_reset_filters")}</button>}
      <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(exported); setCopyState("ok"); } catch { setCopyState("error"); } }} className={styles.action}>{t("rx_copiar")}</button>
      <button type="button" onClick={download} className={styles.action}>{t("rx_exportar")}</button>
    </div>
    <details className={styles.details}><summary>{t("ux_export_representation")}</summary><p className={styles.note}>{t("rx_datos_detalle")}</p></details>
    <div className={styles.dataList}>{visible.map(field => {
      const meta = resultFieldPresentation(field.key);
      const label = locale === "en" ? meta.en : meta.es;
      return <details key={field.key} className={styles.dataField} data-field-key={field.key}>
        <summary><span className={styles.fieldLabel}>{label}{label !== field.key && <code>{field.key}</code>}</span><span className={styles.fieldState}>{t(field.state === "absent" ? "rx_ausente" : field.state === "null" ? "rx_nulo" : "rx_registrado")}</span></summary>
        <div className={styles.fieldBody}><DataValue value={field.value} /></div>
      </details>;
    })}</div>
    {visible.length === 0 && <p className="text-zinc-400">{t("rx_sin_coincidencias")}</p>}
  </section>;
}
