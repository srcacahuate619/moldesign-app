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

import { useId, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, CircleSlash, Loader2, ShieldQuestion } from "lucide-react";

import { useLanguage } from "../../context/LanguageContext";
import { Ayuda } from "../ui/Ayuda";
import type { PreflightControl, PreflightControlState, PreflightReport } from "../../lib/preflight";
import type { HumanDecision, PreflightSummary } from "../../lib/cases/types";

const STATE_ORDER: Record<PreflightControlState, number> = {
  bloquea: 0,
  advertencia: 1,
  no_evaluado: 2,
  pasa: 3,
};

const STATE_LABEL: Record<PreflightControlState, string> = {
  bloquea: "Bloquea",
  advertencia: "Advertencia",
  no_evaluado: "No evaluado",
  pasa: "Pasa",
};

const STATE_STYLE: Record<PreflightControlState, string> = {
  bloquea: "border-red-500/40 text-red-300",
  advertencia: "border-amber-500/40 text-amber-300",
  no_evaluado: "border-surface-600 text-zinc-400",
  pasa: "border-emerald-500/30 text-emerald-300",
};

function dockingMethodLabel(engine: string, route: string): string {
  if (engine === "qvina2") return "Acoplamiento molecular con QuickVina 2";
  if (engine === "vina") return "Acoplamiento molecular con AutoDock Vina";
  return route === "docking_vina" ? "Ruta de acoplamiento compatible con Vina" : "Ruta de acoplamiento configurada";
}

const SPECIES_CATEGORY_LABEL = {
  water: "agua",
  metal: "metal",
  organic_cofactor: "cofactor orgánico",
  other_heteroatom: "otro componente de la estructura",
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
  readonly canCheck: boolean;
  /**
   * Conformaciones de entrada declaradas para el caso. 1 = confórmero único.
   *
   * Se declara ANTES de comprobar, no al ejecutar: entra en la huella del
   * preflight y se congela con el caso. Un control que lo cambiara después
   * dejaría el resultado describiendo un protocolo distinto del comprobado.
   */
  readonly conformers?: number;
  readonly onConformersChange?: (k: number) => void;
  /** Qué falta para poder comprobar. Se enseña cuando `canCheck` es falso. */
  readonly missingInputs: string | null;
  readonly onCheck: () => void;
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
          {STATE_LABEL[control.state]}
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
  canCheck,
  conformers,
  onConformersChange,
  missingInputs,
  onCheck,
  decisions,
  onAcknowledge,
}: PreparationPanelProps) {
  const { t } = useLanguage();
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
      className="w-full max-w-[1600px] border-y border-surface-800 bg-surface-950/60 px-4 py-4 sm:px-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          <h2
            id="preparation-panel-title"
            className="text-sm font-semibold tracking-tight text-zinc-100"
          >
            {t("pr_preparacion_titulo")}
          </h2>
          <p className="mt-1 max-w-[70ch] text-sm font-medium leading-6 text-zinc-300">
            {t("pr_preparacion_explicacion")}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {/* ── Generación conformacional ─────────────────────────────
              Va aquí, con la comprobación previa, porque es un parámetro de
              PROTOCOLO: entra en la huella y se congela con el caso. Un botón
              que compitiera con «Evaluar» permitiría comparar, dentro de una
              cohorte, una molécula con confórmero único contra otra con
              ensemble — y esa diferencia de protocolo se leería como
              diferencia química. */}
          {onConformersChange && (
            <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1">
              <span className="flex items-center gap-1 font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">
                {t("ayuda_ensemble_titulo")}
                <Ayuda titulo={t("ayuda_ensemble_titulo")}>{t("ayuda_ensemble")}</Ayuda>
              </span>
              <select
                value={conformacionesEfectivas > 1 ? "ensemble" : "unico"}
                onChange={(e) =>
                  onConformersChange(e.target.value === "ensemble" ? 30 : 1)
                }
                aria-label={t("ayuda_ensemble_titulo")}
                className="rounded border border-surface-700 bg-transparent px-1.5 py-0.5 text-xs text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                <option value="unico">{t("pr_conformero_unico")}</option>
                <option value="ensemble">Ensemble</option>
              </select>
              {conformacionesEfectivas > 1 && (
                <label className="flex items-center gap-1 text-xs font-medium text-zinc-300">
                  K =
                  <input
                    type="number"
                    min={2}
                    max={64}
                    value={conformacionesEfectivas}
                    aria-label={t("pr_num_conformaciones")}
                    onChange={(e) => {
                      const bruto = Number.parseInt(e.target.value, 10);
                      if (!Number.isFinite(bruto)) return;
                      onConformersChange(Math.min(Math.max(bruto, 2), 64));
                    }}
                    className="w-14 rounded border border-surface-700 bg-transparent px-1 py-0.5 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                  />
                </label>
              )}
            </div>
          )}
          {conformacionesEfectivas > 1 && (
            <p className="max-w-[34ch] text-right text-xs font-medium leading-5 text-amber-200">
              ≈ {conformacionesEfectivas}× el tiempo de acoplamiento. Amplía la
              cobertura geométrica; no mejora, por sí solo, la elección de la pose top-1.
            </p>
          )}

        <button
          type="button"
          onClick={onCheck}
          disabled={!canCheck || loading}
          className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md border border-brand-500/40 bg-brand-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
          {loading ? "Comprobando…" : visible || persisted ? "Volver a comprobar" : "Comprobar preparación"}
        </button>
        </div>
      </div>

      {/* Qué falta para poder comprobar. Un botón inerte sin explicación deja
          al usuario sin saber qué hacer. */}
      {!canCheck && missingInputs && (
        <p role="status" className="mt-3 text-sm font-medium leading-6 text-zinc-300">
          {missingInputs}
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
        <div className="mt-4 border-t border-surface-800 pt-3">
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Receptor</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">{persisted.receptorLabel}</dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Ligando</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100" title={persisted.ligandLabel}>
                {persisted.ligandLabel}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Caja efectiva</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">{persisted.gridLabel}</dd>
            </div>
            {persisted.executionConfig && (
              <div className="min-w-0">
                <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Protocolo</dt>
                <dd className="truncate text-sm font-semibold text-zinc-100">
                  {persisted.executionConfig.dockingEngine} · ex {persisted.executionConfig.exhaustiveness} ·{" "}
                  {persisted.executionConfig.numPoses} poses · semilla {persisted.executionConfig.seed}
                </dd>
              </div>
            )}
          </dl>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${persisted.blockers.length > 0 ? STATE_STYLE.bloquea : "border-surface-700 text-zinc-300"}`}>
              {persisted.blockers.length} bloqueante{persisted.blockers.length === 1 ? "" : "s"}
            </span>
            <span className={`rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${persisted.warnings.length > 0 ? STATE_STYLE.advertencia : "border-surface-700 text-zinc-300"}`}>
              {persisted.warnings.length} advertencia{persisted.warnings.length === 1 ? "" : "s"}
            </span>
            <span className="rounded border border-surface-700 px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide text-zinc-300">
              {persisted.notEvaluated.length} sin evaluar
            </span>
            <span className="font-mono text-[11px] font-medium text-zinc-400">
              huella {persisted.fingerprint.replace("sha256:", "").slice(0, 12)}…
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {t("pr_resumen_guardado")}
          </p>
        </div>
      )}

      {visible && (
        <>
          {/* ── Resumen compacto ─────────────────────────────────────── */}
          <dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Receptor</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">
                {visible.receptor.pdb_id} · cadena {visible.receptor.chain}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Protocolo</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">
                {visible.effective_config.docking_engine} · ex {visible.effective_config.exhaustiveness} ·{" "}
                {visible.effective_config.num_poses} poses · semilla {visible.effective_config.seed}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">
                {t("pr_ligando_canonico")}
              </dt>
              <dd className="truncate text-sm font-semibold text-zinc-100" title={visible.ligand.canonical_smiles ?? undefined}>
                {visible.ligand.canonical_smiles ?? "No definido"}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="font-mono text-[11px] font-semibold uppercase tracking-wide text-zinc-300">Caja efectiva</dt>
              <dd className="truncate text-sm font-semibold text-zinc-100">
                ({visible.effective_config.grid_center.map((v) => v.toFixed(1)).join(", ")}) ·{" "}
                {visible.effective_config.grid_size[0].toFixed(1)} Å
              </dd>
            </div>
          </dl>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className={`whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${blockers > 0 ? STATE_STYLE.bloquea : "border-surface-700 text-zinc-300"}`}
            >
              {blockers} bloqueante{blockers === 1 ? "" : "s"}
            </span>
            <span
              className={`whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${warnings > 0 ? STATE_STYLE.advertencia : "border-surface-700 text-zinc-300"}`}
            >
              {warnings} advertencia{warnings === 1 ? "" : "s"}
            </span>
            <span className="whitespace-nowrap rounded border border-surface-700 px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide text-zinc-300">
              {notEvaluated} sin evaluar
            </span>
            <span className="whitespace-nowrap font-mono text-[11px] font-medium text-zinc-400">
              huella {visible.input_fingerprint.replace("sha256:", "").slice(0, 12)}…
            </span>
          </div>

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
            {open ? "Ocultar detalle" : "Ver detalle"}
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
                            <th className="py-2 pr-3">Especie</th>
                            <th className="py-2 pr-3">Fuente</th>
                            <th className="py-2 pr-3">Tras filtrar</th>
                            <th className="py-2">Retirado</th>
                          </tr>
                        </thead>
                        <tbody className="font-medium text-zinc-100">
                          {(
                            [
                              ["Átomos de proteína", "atom_records"],
                              ["Aguas", "waters"],
                              ["Metales", "metals"],
                              ["Cofactores orgánicos", "organic_cofactors"],
                              ["Otros heteroátomos", "other_hetatm"],
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
                              <span className="text-zinc-400"> · {SPECIES_CATEGORY_LABEL[species.category]} · </span>
                              <span className="font-semibold text-zinc-100">
                                {species.atom_count} {species.atom_count === 1 ? "átomo" : "átomos"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="mt-1.5 text-sm leading-6 text-zinc-300">
                    No evaluado. {visible.preparation_diff.reason}
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
                      {dockingMethodLabel(
                        visible.effective_config.docking_engine,
                        visible.effective_config.heteroatom_policy.route,
                      )}
                    </dd>
                  </div>
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="font-semibold text-zinc-300">Aguas:</dt>
                    <dd className="font-medium">{t("pr_aguas_eliminadas")}</dd>
                  </div>
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="font-semibold text-zinc-300">Metales:</dt>
                    <dd className="font-medium">
                      {visible.effective_config.heteroatom_policy.cofactors_whitelist_declared.length > 0
                        ? `Se conservan únicamente los declarados: ${visible.effective_config.heteroatom_policy.cofactors_whitelist_declared.join(", ")}`
                        : "No hay metales declarados para conservar"}
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
                  Controles
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
