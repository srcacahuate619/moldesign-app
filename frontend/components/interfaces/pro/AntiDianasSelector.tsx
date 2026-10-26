"use client";
import { useId, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { agruparAntiDianas, antiDianasParaEnviar, antiDianasPorDefecto, disponible, type AntiDiana } from "@/lib/antiDianas";
import { CustomReceptorModal } from "./CustomReceptorModal";

export function AntiDianasAviso({ targets, selected }: { targets: readonly AntiDiana[] | null; selected: readonly string[] }) {
  const { t } = useLanguage();
  if (targets === null) return null;
  const valid = new Set(antiDianasParaEnviar(targets, selected));
  const omitted = selected.filter((id) => !valid.has(id));
  return omitted.length > 0 ? <p role="status" className="text-base text-amber-800 dark:text-amber-300 font-sans leading-6">{t("pn_anti_excluidas", { ids: omitted.join(", ") })}</p> : null;
}
export function AntiDianasSelector({ targets, selected, onChange, error = false, onRetry, catalogo = false, disabled = false }: {
  targets: readonly AntiDiana[] | null; selected: readonly string[]; onChange: (ids: string[]) => void;
  error?: boolean; onRetry?: () => void; catalogo?: boolean; disabled?: boolean;
}) {
  const { t } = useLanguage();
  const id = useId();
  const [busqueda, setBusqueda] = useState("");
  const [familia, setFamilia] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const titulo = catalogo ? <h3 className="text-base font-semibold text-zinc-100">{t("pn_anti_catalogo")}</h3> : null;
  if (targets === null) return <section aria-label={t(catalogo ? "pn_anti_catalogo" : "pn_anti_selector")} className="space-y-3">
    {titulo}
    <p role="status" className="text-base leading-6 text-zinc-300">{t(error ? "pn_anti_error" : "pn_anti_cargando")}</p>
    {error && <button type="button" className="min-h-11 rounded-lg border border-zinc-600 px-3 text-sm text-zinc-100 hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400" onClick={onRetry}>{t("pn_anti_reintentar")}</button>}
  </section>;
  const available = targets.filter(disponible);
  const effective = antiDianasParaEnviar(targets, selected);
  const rows = [...targets];
  for (const pid of selected) {
    if (!rows.some((a) => a.pdb_id === pid)) rows.push({ pdb_id: pid, name: pid, category: t("pn_anti_guardadas"), disponible: false, motivo_no_disponible: t("pn_anti_ausente") });
  }
  const groups = new Map<string, AntiDiana[]>();
  const nombreFamilia = (value: string) => t(({ "Quinasa": "cat_familia_kinasa", "Enzima": "cat_familia_enzima", "Receptor nuclear": "cat_familia_nuclear" } as Record<string, string>)[value] ?? value);
  for (const row of rows) {
    const family = row.category?.replace(/^Bowes 2012\s*·\s*/, "") || t("pn_anti_sin_familia");
    groups.set(family, [...(groups.get(family) ?? []), row]);
  }
  const normalizar = (text: string) => Array.from(text.normalize("NFD"))
    .filter((character) => {
      const codePoint = character.codePointAt(0)!;
      return codePoint < 0x0300 || codePoint > 0x036f;
    })
    .join("")
    .toLocaleLowerCase();
  const query = normalizar(busqueda.trim());
  const familiaActiva = groups.has(familia) ? familia : "";
  const visibles = [...groups].map(([name, members]) => ({ name, members, visibles: members.filter((row) => !catalogo || ((!familiaActiva || name === familiaActiva) && normalizar(`${row.name} ${row.pdb_id ?? ""} ${name} ${nombreFamilia(name)}`).includes(query))) })).filter((group) => group.visibles.length > 0);
  return <section aria-label={t(catalogo ? "pn_anti_catalogo" : "pn_anti_selector")} className="min-w-0 space-y-3 font-sans">
    {titulo}
    {catalogo && <>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm leading-6 text-zinc-300">
        <span>{t("pn_anti_catalogo_total", { n: targets.length })}</span>
        <span className="text-emerald-800 dark:text-emerald-300">{t("pn_anti_catalogo_disponibles", { n: available.length })}</span>
        <span>{t("pn_anti_catalogo_no_disponibles", { n: targets.length - available.length })}</span>
      </div>
      <p className="text-base leading-6 text-zinc-300">{t("pn_anti_catalogo_ayuda")}</p>
      <label htmlFor={`${id}-search`} className="block space-y-1.5 text-sm font-medium text-zinc-200">
        <span>{t("pn_anti_buscar")}</span>
        <input id={`${id}-search`} type="search" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} placeholder={t("pn_anti_buscar_placeholder")} className="min-h-11 w-full min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 text-base text-zinc-100 placeholder:text-zinc-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400" />
      </label>
      <label htmlFor={`${id}-family`} className="block space-y-1.5 text-sm font-medium text-zinc-200">
        <span>{t("pn_anti_filtrar_familia")}</span>
        <select id={`${id}-family`} value={familiaActiva} onChange={(event) => setFamilia(event.target.value)} className="min-h-11 w-full min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 text-base text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">
          <option value="">{t("pn_anti_todas_familias")}</option>
          {[...groups.keys()].map((name) => <option key={name} value={name}>{nombreFamilia(name)}</option>)}
        </select>
      </label>
    </>}
    <div className="flex flex-wrap items-center gap-2">
      {([ ["por_defecto", "pn_panel_por_defecto"], ["todas", "pn_anti_todas"], ["ninguna", "pn_ninguna"] ] as const).map(([action, label]) => <button type="button" key={action} disabled={disabled} className="min-h-11 rounded-lg border border-zinc-600 px-2 py-1 text-sm text-zinc-200 transition-colors hover:bg-zinc-800 active:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400" onClick={() => onChange(action === "ninguna" ? [] : action === "por_defecto" ? antiDianasPorDefecto(targets) : available.map((a) => a.pdb_id!))}>{t(label)}</button>)}
      {!catalogo && <span role="status" className="text-sm text-zinc-400">{t("pn_anti_recuento", { n: effective.length, total: available.length })}</span>}
    </div>
    <AntiDianasAviso targets={targets} selected={selected} />
    {effective.length > 8 && <p className="text-base text-amber-800 dark:text-amber-300 font-sans leading-6">{t("pn_anti_coste")}</p>}
    {catalogo && <p role="status" className="text-base leading-6 text-zinc-300">{visibles.length ? t("pn_anti_resultados_busqueda", { n: visibles.reduce((total, group) => total + group.visibles.length, 0) }) : t("pn_anti_sin_coincidencias")}</p>}
    {disabled && catalogo && <p role="status" className="text-base leading-6 text-purple-200">{t("pn_anti_seleccion_bloqueada")}</p>}
    <div role={catalogo ? "group" : undefined} aria-label={catalogo ? t("pn_anti_catalogo") : undefined} tabIndex={catalogo ? 0 : undefined}
      className={catalogo ? "custom-scrollbar max-h-[36rem] space-y-4 overflow-y-auto overscroll-auto pr-1 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-purple-400" : "max-h-64 space-y-3 overflow-y-auto pr-1"}>
      {agruparAntiDianas(rows).map(({ seccion, targets: miembros }) => {
        const deSeccion = new Set(miembros);
        const gruposDeSeccion = visibles.map((group) => ({ ...group, members: group.members.filter((row) => deSeccion.has(row)), visibles: group.visibles.filter((row) => deSeccion.has(row)) })).filter((group) => group.visibles.length > 0);
        return <section key={seccion} aria-label={t(seccion === "panel" ? "cat_anti_panel" : "cat_anti_propias")} className="space-y-3">
          <h4 className="text-base font-semibold text-zinc-100">{t(seccion === "panel" ? "cat_anti_panel" : "cat_anti_propias")}</h4>
          <p className="text-sm leading-6 text-zinc-300">{t(seccion === "panel" ? "cat_anti_panel_texto" : "cat_anti_propias_texto")}</p>
          {seccion === "propias" && <>
            <button type="button" disabled={disabled} onClick={() => setShowUpload(true)} className="min-h-11 rounded-lg border border-zinc-600 px-3 text-sm text-zinc-100 hover:bg-zinc-800 focus-visible:outline-2 disabled:opacity-50">{t("cat_anti_subir")}</button>
            {miembros.length === 0 && <p className="text-sm leading-6 text-zinc-300">{t("cat_anti_vacio")}</p>}
          </>}
      {gruposDeSeccion.map(({ name: family, members, visibles: filtrados }, groupIndex) => <fieldset key={family} className="min-w-0 space-y-2 border-t border-zinc-700 pt-2">
        <legend className="px-1 text-sm font-semibold text-zinc-300">{nombreFamilia(family)} · {members.filter((a) => a.pdb_id && effective.includes(a.pdb_id)).length}/{members.filter(disponible).length}</legend>
        {filtrados.map((row, index) => {
          const checkboxId = `${id}-${seccion}-${groupIndex}-${index}`;
          const reasonId = `${checkboxId}-reason`;
          const enabled = disponible(row);
          const marcada = Boolean(row.pdb_id && selected.includes(row.pdb_id));
          const reservas = row.estructura?.pose_reproducida === false || (row.estructura?.truncadas_en_sitio ?? 0) > 0 || Boolean(row.aviso);
          const detalle = <div id={reasonId} className="ml-5 space-y-1 text-base leading-6 text-zinc-400">
            {!enabled && <p>{row.motivo_no_disponible || row.motivo || t("pn_no_disponible")}</p>}
            {row.estructura?.resolucion_A != null && <p>{row.pdb_id} · {t("pn_resolucion")}: {row.estructura.resolucion_A} Å</p>}
            {row.estructura?.pose_reproducida === false && <p className="text-amber-800 dark:text-amber-300">{t("pn_anti_pose")}</p>}
            {(row.estructura?.truncadas_en_sitio ?? 0) > 0 && <p className="text-amber-800 dark:text-amber-300">{t("pn_anti_truncadas", { n: row.estructura!.truncadas_en_sitio! })}</p>}
            {row.aviso && <p className="text-amber-800 dark:text-amber-300">{row.aviso}</p>}
          </div>;
          return <div key={`${row.pdb_id}-${row.name}-${index}`} className={catalogo ? `min-w-0 rounded-lg border p-2 text-sm text-zinc-300 ${marcada ? "border-purple-500/40 bg-purple-500/[0.08]" : "border-white/[0.08] bg-white/[0.02]"}` : "text-sm text-zinc-300"}>
            <label htmlFor={checkboxId} className={`flex min-h-11 items-start gap-2 py-2 ${enabled && !disabled ? "cursor-pointer" : "cursor-default"}`}>
              <input id={checkboxId} type="checkbox" disabled={!enabled || disabled} checked={marcada} aria-describedby={reasonId} className="mt-1 shrink-0 accent-purple-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400" onChange={() => row.pdb_id && onChange(selected.includes(row.pdb_id) ? selected.filter((pid) => pid !== row.pdb_id) : [...selected, row.pdb_id])} />
              <span className="min-w-0 break-words text-base leading-6">{row.name}{row.pdb_id && row.pdb_id !== row.name && <span className="ml-2 font-mono text-sm text-zinc-400">{row.pdb_id}</span>}</span>
            </label>
            {catalogo && enabled && (row.estructura || row.aviso) ? <details>
              <summary className={`ml-5 cursor-pointer rounded py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400 ${reservas ? "text-amber-800 dark:text-amber-300" : "text-zinc-400"}`}>{t(reservas ? "pn_anti_estructura_reservas" : "pn_anti_estructura_detalle")}</summary>
              {detalle}
            </details> : detalle}
          </div>;
        })}
      </fieldset>)}
        </section>;
      })}
    </div>
    {showUpload && <CustomReceptorModal antiDiana onClose={() => setShowUpload(false)} onSuccess={() => { setShowUpload(false); onRetry?.(); }} />}
  </section>;
}
