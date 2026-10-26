/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4
 * Hallmark · component: scientific preflight panel · genre: modern-minimal · theme: existing MolDesign
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass — secondary copy raised from zinc-500/600 to zinc-300/400
 */
"use client";

// =====================================================================
// PreparationPanel — qué va a entrar en la corrida, antes de ejecutarla
// =====================================================================
//
// SUSTITUYE A UNA CONJETURA. En este mismo hueco vivía un panel que decía
// «SMILES presente; se validará al ejecutar» y contaba hotspots del catálogo:
// afirmaciones construidas en el navegador, sin tocar el receptor ni conocer
// la política de preparación. Ocupaba el sitio de la respuesta sin darla.
//
// Ahora lo que se enseña sale del backend, que inspecciona los archivos reales
// con la misma función que ejecuta la corrida. Cuando algo no se puede saber,
// se dice «No evaluado» con su causa — nunca se rellena.
//
// LO QUE ESTE PANEL NO HACE:
//
//   · no puntúa: no hay nota 0-100 ni veredicto global;
//   · no decide: una advertencia no bloquea, y un bloqueante no se negocia;
//   · no corrige: no toca aguas, metales, cadenas ni formas químicas;
//   · no navega: el detalle se despliega aquí mismo, sin una pestaña nueva.
//
// SEPARACIÓN QUE SÍ IMPORTA. Los controles se agrupan en tres bloques —hechos
// comprobados, lo que no se pudo evaluar, y lo que espera una decisión
// humana— porque mezclarlos es exactamente lo que convierte un informe en un
// veredicto.

import { useEffect, useId, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, CircleSlash, Loader2, ShieldQuestion } from "lucide-react";

import { useLanguage } from "../../context/LanguageContext";
import { localizeReceptorLabel } from "../../lib/preflight";
import { Ayuda } from "../ui/Ayuda";
import { ConfigurationInputs, ConfigurationMetadata, useConfigurationPresentation } from "./ConfigurationPresentation";
import configurationStyles from "./ConfigurationPresentation.module.css";
import type { PreflightControl, PreflightControlState, PreflightReport } from "../../lib/preflight";
import type { HumanDecision, PreflightSummary } from "../../lib/cases/types";

const STATE_ORDER: Record<PreflightControlState, number> = {
  bloquea: 0,
  advertencia: 1,
  no_evaluado: 2,
  pasa: 3,
};

const STATE_LABEL: Record<PreflightControlState, string> = {
  bloquea: "pr_preflight_state_blocking",
  advertencia: "pr_preflight_state_warning",
  no_evaluado: "pr_preflight_state_not_evaluated",
  pasa: "pr_preflight_state_pass",
};

const STATE_STYLE: Record<PreflightControlState, string> = {
  bloquea: "border-red-500/40 text-red-300",
  advertencia: "border-amber-500/40 text-amber-300",
  no_evaluado: "border-surface-600 text-zinc-400",
  pasa: "border-emerald-500/30 text-emerald-300",
};

function dockingMethodKey(engine: string, route: string): string {
  if (engine === "qvina2") return "pr_preflight_method_qvina";
  if (engine === "vina") return "pr_preflight_method_vina";
  return route === "docking_vina"
    ? "pr_preflight_method_vina_compatible"
    : "pr_preflight_method_configured";
}

const SPECIES_CATEGORY_KEY = {
  water: "pr_preflight_species_water",
  metal: "pr_preflight_species_metal",
  organic_cofactor: "pr_preflight_species_organic_cofactor",
  other_heteroatom: "pr_preflight_species_other_component",
} as const;

function StateIcon({ state }: { state: PreflightControlState }) {
  const className = "h-3.5 w-3.5 shrink-0";
  if (state === "bloquea") return <AlertTriangle className={className} aria-hidden="true" />;
  if (state === "advertencia") return <ShieldQuestion className={className} aria-hidden="true" />;
  if (state === "no_evaluado") return <CircleSlash className={className} aria-hidden="true" />;
  return <CheckCircle2 className={className} aria-hidden="true" />;
}

export interface PreparationPanelProps {
  readonly report: PreflightReport | null;
  /** Resumen que sobrevive a cerrar la aplicación aunque el detalle no esté en memoria. */
  readonly summary?: PreflightSummary;
  readonly loading: boolean;
  readonly error: string | null;
  /** `true` cuando los inputs cambiaron y el informe dejó de corresponder. */
  readonly stale: boolean;
  /**
   * Conformaciones de entrada declaradas para el caso. 1 = confórmero único.
   *
   * Resumen de lo aplicado en Parámetros de la evaluación. Entra en la
   * huella del preflight y se conserva con el caso.
   */
  readonly conformers?: number;
  readonly decisions: readonly HumanDecision[];
  readonly onAcknowledge: (controlCode: string) => void;
}

function ControlRow({
  control,
  acknowledged,
  onAcknowledge,
}: {
  control: PreflightControl;
  acknowledged: boolean;
  onAcknowledge: (code: string) => void;
}) {
  const { t } = useLanguage();
  return (
    <li className="border-b border-surface-800 py-4 last:border-b-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span
          className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${STATE_STYLE[control.state]}`}
        >
          <StateIcon state={control.state} />
          {t(STATE_LABEL[control.state])}
        </span>
        <span className="min-w-0 text-sm font-semibold text-zinc-100">{control.title}</span>
      </div>
      <p className="mt-2 break-words text-sm font-medium leading-6 text-zinc-100">{control.observation}</p>
      <p className="mt-1 break-words text-sm leading-6 text-zinc-300">{control.reason}</p>

      {/* Sólo las advertencias admiten decisión. Un bloqueante técnico no se
          reconoce: se arregla, o la corrida falla igual. */}
      {control.state === "advertencia" && (
        <div className="mt-2">
          {acknowledged ? (
            <p className="font-mono text-[11px] font-semibold uppercase tracking-wide text-emerald-300">
              {t("pr_revisada_aceptada")}
            </p>
          ) : (
            <button
              type="button"
              onClick={() => onAcknowledge(control.code)}
              className="rounded border border-surface-700 px-2.5 py-1 text-xs font-medium text-zinc-200 transition-colors hover:border-surface-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              {t("pr_marcar_revisada")}
            </button>
          )}
        </div>
      )}
    </li>
  );
}

export function PreparationPanel({
  report,
  summary,
  loading,
  error,
  stale,
  conformers,
  decisions,
  onAcknowledge,
}: PreparationPanelProps) {
  const { t } = useLanguage();
  const configuration = useConfigurationPresentation();
  const [open, setOpen] = useState(false);
  const detailId = useId();
  // Un valor imposible cae al defecto en vez de propagarse a la corrida: el
  // backend aplica el mismo techo, y aquí se evita enseñar un K que no existe.
  const conformacionesEfectivas =
    typeof conformers === "number" && Number.isFinite(conformers)
      ? Math.min(Math.max(Math.trunc(conformers), 1), 64)
      : 1;

  const visible = report && !stale ? report : null;
  const persisted = !stale ? summary : undefined;
  const blockers = visible?.technical_blockers.length ?? 0;
  const warnings = visible?.warnings.length ?? 0;
  const notEvaluated = visible?.not_evaluated.length ?? 0;
  useEffect(() => {
    setOpen(blockers > 0);
  }, [visible?.input_fingerprint, blockers]);

  const acknowledgedCodes = new Set(
    visible ? decisions.filter((d) => d.fingerprint === visible.input_fingerprint).map((d) => d.controlCode) : [],
  );

  const controls = visible
    ? [...visible.controls].sort((a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state])
    : [];
  const removedSpecies = visible?.preparation_diff.removed_species ?? [];

  return (
    <section
      aria-labelledby="preparation-panel-title"
      className={configuration ? configurationStyles.preflight : "w-full max-w-[1600px] border-y border-surface-800 bg-surface-950/60 px-4 py-3 sm:px-6"}
      data-configuration-preflight={configuration || undefined}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h2
            id="preparation-panel-title"
            className="text-sm font-semibold tracking-tight text-zinc-100"
          >
            {t("pr_preparacion_titulo")}
          </h2>
          <Ayuda titulo={t("pr_preparacion_titulo")}>{t("pr_preparacion_explicacion")}</Ayuda>
          {!loading && !visible && !persisted && !error && (
            <span className="text-xs font-mono text-zinc-400">{t("pr_comprobacion_pendiente")}</span>
          )}
        </div>

        <span className="text-xs font-mono text-zinc-300">
          {t(conformacionesEfectivas === 1 ? "pr_conformeros_resumen_uno" : "pr_conformeros_resumen_varios", { cantidad: conformacionesEfectivas })}
        </span>
      </div>

      {/* La comprobación NO es un botón: la hace «Evaluar» antes de ejecutar. Este
          panel sólo cuenta en qué punto está, para que nadie busque un paso que
          ya no existe (antes, quien no lo pulsaba se quedaba con «Evaluar»
          deshabilitado sin saber por qué). */}
      {loading && (
        <p role="status" className="mt-3 flex items-center gap-2 text-sm font-medium leading-6 text-zinc-300">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          {t("auto_338dc7ae83f6")}
        </p>
      )}
      {!loading && !visible && !persisted && !error && (
        <p role="status" className="mt-1 text-sm font-medium leading-6 text-zinc-300">
          {t("pr_comprobacion_automatica")}
        </p>
      )}

      {error && (
        <p role="alert" className="mt-3 text-xs leading-relaxed text-amber-300">
          {error}
        </p>
      )}

      {stale && report && (
        <p role="status" className="mt-3 text-xs leading-relaxed text-amber-300">
          {t("pr_inputs_cambiaron")}
        </p>
      )}

      {!visible && persisted && (
        <div className={configuration ? undefined : "mt-4 border-t border-surface-800 pt-3"}>
          {configuration ? <ConfigurationInputs summary={persisted} /> : (<dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("pr_preflight_receptor")}</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">{localizeReceptorLabel(persisted.receptorLabel, t)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("pr_preflight_ligand")}</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100" title={persisted.ligandLabel}>
                {persisted.ligandLabel}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("pr_preflight_effective_box")}</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">{persisted.gridLabel}</dd>
            </div>
            {persisted.executionConfig && (
              <div className="min-w-0">
                <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("se_gen_protocol")}</dt>
                <dd className="truncate text-sm font-semibold text-zinc-100">
                  {persisted.executionConfig.dockingEngine} · {t("c_exhaustividad")} {persisted.executionConfig.exhaustiveness} ·{" "}
                  {persisted.executionConfig.numPoses} {t("auto_f3d3bbae83b6")} {persisted.executionConfig.seed}
                </dd>
              </div>
            )}
          </dl>)}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${persisted.blockers.length > 0 ? STATE_STYLE.bloquea : "border-surface-700 text-zinc-300"}`}>
              {persisted.blockers.length} {t(persisted.blockers.length === 1 ? "pr_preflight_blocker_one" : "pr_preflight_blocker_many")}
            </span>
            <span className={`rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${persisted.warnings.length > 0 ? STATE_STYLE.advertencia : "border-surface-700 text-zinc-300"}`}>
              {persisted.warnings.length} {t(persisted.warnings.length === 1 ? "pr_preflight_warning_one" : "pr_preflight_warning_many")}
            </span>
            <span className="rounded border border-surface-700 px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide text-zinc-300">
              {persisted.notEvaluated.length} {t("se_phys_count_skip")}
            </span>
            {!configuration && <span className="font-mono text-[11px] font-medium text-zinc-400">
              {t("pr_preflight_fingerprint")} {persisted.fingerprint.replace("sha256:", "").slice(0, 12)}…
            </span>}
          </div>
          {configuration ? <ConfigurationMetadata fingerprint={persisted.fingerprint} note={t("pr_resumen_guardado")} /> : <p className="mt-2 text-sm leading-6 text-zinc-300">
            {t("pr_resumen_guardado")}
          </p>}
        </div>
      )}

      {visible && (
        <>
          {/* ── Resumen compacto ─────────────────────────────────────── */}
          {configuration ? <ConfigurationInputs report={visible} /> : (<dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("pr_preflight_receptor")}</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">
                {visible.receptor.pdb_id} {t("auto_da63fdf7d65b")} {visible.receptor.chain}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("se_gen_protocol")}</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">
              {visible.effective_config.docking_engine} · {t("c_exhaustividad")} {visible.effective_config.exhaustiveness} ·{" "}
                {visible.effective_config.num_poses} {t("auto_f3d3bbae83b6")} {visible.effective_config.seed}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">
                {t("pr_ligando_canonico")}
              </dt>
              <dd className="truncate text-sm font-semibold text-zinc-100" title={visible.ligand.canonical_smiles ?? undefined}>
                {visible.ligand.canonical_smiles ?? t("c_no_definido")}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">{t("pr_preflight_effective_box")}</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">
                ({visible.effective_config.grid_center.map((v) => v.toFixed(1)).join(", ")}) ·{" "}
                {visible.effective_config.grid_size[0].toFixed(1)} Å
              </dd>
            </div>
          </dl>)}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className={`whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${blockers > 0 ? STATE_STYLE.bloquea : "border-surface-700 text-zinc-300"}`}
            >
              {blockers} {t(blockers === 1 ? "pr_preflight_blocker_one" : "pr_preflight_blocker_many")}
            </span>
            <span
              className={`whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${warnings > 0 ? STATE_STYLE.advertencia : "border-surface-700 text-zinc-300"}`}
            >
              {warnings} {t(warnings === 1 ? "pr_preflight_warning_one" : "pr_preflight_warning_many")}
            </span>
            <span className="whitespace-nowrap rounded border border-surface-700 px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide text-zinc-300">
              {notEvaluated} {t("se_phys_count_skip")}
            </span>
            {!configuration && <span className="whitespace-nowrap font-mono text-[11px] font-medium text-zinc-400">
              {t("pr_preflight_fingerprint")} {visible.input_fingerprint.replace("sha256:", "").slice(0, 12)}…
            </span>}
          </div>
          {configuration && <ConfigurationMetadata fingerprint={visible.input_fingerprint} />}

          {/* ── Detalle, sin salir de aquí ───────────────────────────── */}
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls={detailId}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
              aria-hidden="true"
            />
            {open ? t("se_hide_detail") : t("se_show_detail")}
          </button>

          {open && (
            <div id={detailId} className="mt-4 space-y-6">
              {/* Cambios fuente → preparado */}
              <section aria-labelledby={`${detailId}-diff`}>
                <h3
                  id={`${detailId}-diff`}
                  className="text-sm font-semibold uppercase tracking-wide text-zinc-200"
                >
                  {t("pr_de_la_fuente")}
                </h3>
                {visible.preparation_diff.state === "evaluado" && visible.preparation_diff.removed ? (
                  <>
                    <p className="mt-1.5 text-sm leading-6 text-zinc-300">
                      {visible.preparation_diff.reason}
                    </p>
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full min-w-[28rem] border-collapse text-sm">
                        <thead>
                          <tr className="border-b border-surface-700 text-left font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">
                            <th className="py-2 pr-3">{t("pr_preflight_species")}</th>
                            <th className="py-2 pr-3">{t("pr_preflight_source")}</th>
                            <th className="py-2 pr-3">{t("pr_preflight_after_filtering")}</th>
                            <th className="py-2">{t("pr_preflight_removed")}</th>
                          </tr>
                        </thead>
                        <tbody className="font-medium text-zinc-100">
                          {(
                            [
                              [t("auto_808cfa7d641c"), "atom_records"],
                              [t("pr_preflight_waters"), "waters"],
                              [t("pr_preflight_metals"), "metals"],
                              [t("auto_efa071aa71dd"), "organic_cofactors"],
                              [t("auto_f134454d6dec"), "other_hetatm"],
                            ] as const
                          ).map(([label, key]) => {
                            const source = visible.preparation_diff.source?.[key] ?? 0;
                            const routeInput = visible.preparation_diff.route_input?.[key] ?? 0;
                            const removed = source - routeInput;
                            return (
                              <tr key={key} className="border-b border-surface-800/60 last:border-b-0">
                                <td className="py-1.5 pr-3">{label}</td>
                                <td className="py-1.5 pr-3 font-mono">{source}</td>
                                <td className="py-1.5 pr-3 font-mono">{routeInput}</td>
                                <td className={`py-1.5 font-mono font-semibold ${removed > 0 ? "text-amber-300" : "text-zinc-400"}`}>
                                  {removed > 0 ? `−${removed}` : "0"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    {removedSpecies.length > 0 && (
                      <div className="mt-4 rounded-lg border border-surface-700 bg-surface-900/70 p-3">
                        <h4 className="text-sm font-semibold text-zinc-100">{t("pr_especies_retiradas")}</h4>
                        <p className="mt-1 text-xs font-medium leading-5 text-zinc-300">
                          {t("pr_codigos_residuo")}
                        </p>
                        <ul className="mt-2 flex flex-wrap gap-2">
                          {removedSpecies.map((species) => (
                            <li
                              key={`${species.category}-${species.residue_code}`}
                              className="rounded-md border border-surface-700 bg-black/30 px-2.5 py-1.5 text-xs text-zinc-200"
                            >
                              <strong className="font-mono text-zinc-50">{species.residue_code}</strong>
                              <span className="text-zinc-400"> · {t(SPECIES_CATEGORY_KEY[species.category])} · </span>
                              <span className="font-semibold text-zinc-100">
                                {species.atom_count} {species.atom_count === 1 ? t("auto_7613e1aefca5") : t("pn_atomos")}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="mt-1.5 text-sm leading-6 text-zinc-300">
                    {t("pr_preflight_not_evaluated")} {visible.preparation_diff.reason}
                  </p>
                )}
              </section>

              {/* Política declarada de la ruta */}
              <section aria-labelledby={`${detailId}-policy`}>
                <h3
                  id={`${detailId}-policy`}
                  className="text-sm font-semibold uppercase tracking-wide text-zinc-200"
                >
                  {t("pr_politica_preparacion")}
                </h3>
                <dl className="mt-2 space-y-2 text-sm text-zinc-100">
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="font-semibold text-zinc-300">{t("pr_metodo")}</dt>
                    <dd className="font-medium">
                      {t(dockingMethodKey(
                        visible.effective_config.docking_engine,
                        visible.effective_config.heteroatom_policy.route,
                      ))}
                    </dd>
                  </div>
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="font-semibold text-zinc-300">{t("auto_7b6e6012ac40")}</dt>
                    <dd className="font-medium">{t("pr_aguas_eliminadas")}</dd>
                  </div>
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="font-semibold text-zinc-300">{t("auto_2e487d8b1546")}</dt>
                    <dd className="font-medium">
                      {visible.effective_config.heteroatom_policy.cofactors_whitelist_declared.length > 0
                        ? t("pr_preflight_declared_cofactors", {
                            cofactors: visible.effective_config.heteroatom_policy.cofactors_whitelist_declared.join(", "),
                          })
                        : t("auto_c922a83946da")}
                    </dd>
                  </div>
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="font-semibold text-zinc-300">{t("pr_cofactores_reconocidos")}</dt>
                    <dd className="min-w-0 break-words font-mono text-xs font-medium text-zinc-100">
                      {visible.effective_config.heteroatom_policy.organic_cofactors_kept.join(", ")}
                    </dd>
                  </div>
                </dl>
              </section>

              {/* Controles, separados por naturaleza */}
              <section aria-labelledby={`${detailId}-controls`}>
                <h3
                  id={`${detailId}-controls`}
                  className="text-sm font-semibold uppercase tracking-wide text-zinc-200"
                >
                  {t("pr_preflight_controls")}
                </h3>
                <ul className="mt-1">
                  {controls.map((control) => (
                    <ControlRow
                      key={control.code + control.title}
                      control={control}
                      acknowledged={acknowledgedCodes.has(control.code)}
                      onAcknowledge={onAcknowledge}
                    />
                  ))}
                </ul>
              </section>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default PreparationPanel;
