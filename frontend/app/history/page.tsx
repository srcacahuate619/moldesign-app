"use client";

import Link from "next/link";
import { useLanguage } from "../../context/LanguageContext";
import { useEffect, useState } from "react";
import { Download } from "lucide-react";

import { useAuth } from "../../lib/auth";
import { useKeepAliveActive } from "../../context/KeepAliveContext";
import { getEvaluationHistory, getUserStats, downloadCertificate } from "../../lib/api";
import type { EvaluationSummary, HistoryResponse, UserStats } from "../../lib/types";
import { EmptyState } from "../../components/ui/EmptyState";

function formatDate(dateStr: string, locale: string) {
  return new Date(dateStr).toLocaleDateString(locale === "en" ? "en-US" : "es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function HistoryPage() {
  const { t, locale } = useLanguage();
  const { user, isLoading: authLoading } = useAuth();
  // FIX (keep-alive): /history no se desmonta (KeepAliveLayout). Recargar al
  // volver a esta ruta para que las evaluaciones recién hechas aparezcan.
  const isActive = useKeepAliveActive();
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("created_at");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch history — también cuando la página vuelve a estar activa
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getEvaluationHistory(page, 20, sortBy, "desc")
      .then((data) => { if (!cancelled) setHistory(data); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user, page, sortBy, isActive]);

  // Fetch stats — también al reactivar
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getUserStats()
      .then((data) => { if (!cancelled) setStats(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [user, isActive]);

  // ── ESTADO 1/3: Auth cargando (ThinkingOrb processing, cohesivo con /moldex loader) ──
  if (authLoading) {
    return (
      <EmptyState
        orbState="processing"
        title={t("pg_hist_verificando")}
        description={t("auto_c224ef74ad87")}
        subline={t("pg_hist_subline_jwt")}
        footerStatus={t("pg_hist_footer_autenticado")}
      />
    );
  }

  // ── ESTADO 2/3: No autenticado (ThinkingOrb idle, ritual de autenticación) ──
  if (!user) {
    return (
      <EmptyState
        orbState="idle"
        title={t("pg_hist_acceso_bloqueado")}
        description={
          <>
            {t("pg_hist_privado")}
          </>
        }
        ritual={[
          { n: "1", t: t("pg_hist_ritual_inicia"),  d: t("auto_121e3999ff64") },
          { n: "2", t: t("pg_hist_ritual_conecta"), d: t("pg_hist_ritual_solana") },
          { n: "3", t: t("pg_hist_ritual_accede"),  d: t("pg_hist_ritual_firmado") },
        ]}
        ctaHref="/login"
        ctaLabel={t("pg_hist_iniciar_sesion")}
        footerStatus={t("pg_hist_footer_sesiones")}
      />
    );
  }

  return (
    <main className="space-y-6 pb-12">
      {/* ── Header ── */}
      <section>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{t("pg_hist_titulo")}</h1>
        <p className="mt-1 text-sm text-surface-400">
          {t("pg_hist_descripcion")} <span className="font-medium">Moldex</span>.
        </p>
      </section>

      {/* ── Stats ── */}
      {stats && (
        <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard label={t("pg_hist_stat_total")} value={stats.total_evaluations} />
          <StatCard label={t("lo_filtro_completadas")} value={stats.completed_evaluations} color="text-green-400" />
          <StatCard label={t("lo_filtro_fallidas")} value={stats.failed_evaluations} color="text-red-400" />
          <StatCard
            label={t("pg_hist_stat_mejor_score")}
            value={stats.best_score != null ? stats.best_score.toFixed(1) : "—"}
            color="text-brand-400"
          />
          <StatCard
            label={t("pg_hist_stat_promedio")}
            value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
          />
          <StatCard label={t("pg_hist_targets_unicos")} value={stats.unique_targets} />
        </section>
      )}

      {/* ── Controls ── */}
      <section className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-surface-400">{t("pg_hist_ordenar")}</label>
        {[
          { key: "created_at", label: t("pg_hist_orden_fecha") },
          { key: "total_score", label: t("pg_hist_orden_score_total") },
          { key: "affinity_kcal", label: t("pg_hist_orden_afinidad") },
        ].map((opt) => (
          <button
            key={opt.key}
            onClick={() => { setSortBy(opt.key); setPage(1); }}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              sortBy === opt.key
                ? "bg-brand-600/20 text-brand-400"
                : "text-surface-400 hover:bg-surface-800"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </section>

      {/* ── Error ── */}
      {error && (
        <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
          <pre className="text-xs text-red-300">{error}</pre>
        </section>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex items-center gap-2 py-8 text-sm text-surface-400">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          {t("pg_hist_cargando")}
        </div>
      )}

      {/* ── Table / ── EmptyState para logueado sin evaluaciones ── */}
      {history && !loading && (
        <>
          {history.items.length === 0 ? (
            // ── ESTADO 3/3: Logueado, sin historial (ThinkingOrb idle, ritual de workflow) ──
            <EmptyState
              orbState="idle"
              title={t("pg_hist_en_espera")}
              description={
                <>
                  {t("pg_hist_vacio")}
                </>
              }
              ritual={[
                { n: "1", t: t("mx_paso_disena"), d: t("mx_paso_disena_d") },
                { n: "2", t: t("mx_paso_acopla"),  d: "Vina + XGBoost + GNN" },
                { n: "3", t: t("mx_paso_guarda"), d: t("pg_hist_ritual_conservar") },
              ]}
              ctaHref="/evaluation"
              ctaLabel={t("pg_hist_lanzar_pipeline")}
              footerStatus={t("pg_hist_footer_evaluaciones", { user: user?.email ?? user?.username ?? "local" })}
            />
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-surface-800">
              <table className="w-full text-xs">
                <thead className="border-b border-surface-800 bg-surface-900">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-surface-400">SMILES</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_target")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_estado")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_corrida")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_score")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_afinidad")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_mw")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_lipinski")}</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">QED</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">{t("pg_hist_th_recibo")}</th>
                    <th className="px-3 py-3 text-right font-semibold text-surface-400">{t("pg_hist_th_fecha")}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.items.map((item: EvaluationSummary, i: number) => (
                    <tr
                      key={item.molecule_id + i}
                      className="border-b border-surface-800/50 transition-colors hover:bg-surface-900/50"
                    >
                      <td className="max-w-[200px] truncate px-4 py-3 font-mono text-surface-300">
                        <span>{item.smiles}</span>
                        {item.is_saved && (
                          <span
                            className="ml-2 rounded bg-brand-500/10 px-1.5 py-0.5 text-xs font-bold uppercase tracking-wide text-brand-400"
                            title={t("pg_hist_promovida_moldex")}
                          >
                            Moldex
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-400">{item.target_pdb_id}</td>
                      <td className="px-3 py-3 text-center">
                        <StatusBadge status={item.status} />
                      </td>
                      {/*
                        HIST-INT-004. La corrida es la identidad con la que se recupera el
                        snapshot inmutable (EVAL-P0-02). Sin ella, una fila del historial no
                        se distingue de la última evaluación de la misma molécula. Aún no
                        abre el caso: eso exige materializarlo desde Evaluación, y es una
                        decisión de arquitectura que este paquete no toma.
                      */}
                      <td className="px-3 py-3 text-center">
                        {item.task_id ? (
                          <button
                            onClick={() => navigator.clipboard?.writeText(item.task_id as string)}
                            className="rounded px-1.5 py-0.5 font-mono text-xs text-surface-400 transition-colors hover:bg-surface-800 hover:text-surface-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
                            title={t("pg_hist_copiar_id", { taskId: item.task_id })}
                            aria-label={t("pg_hist_copiar_id_corto", { taskId: item.task_id })}
                          >
                            {item.task_id.slice(0, 8)}…
                          </button>
                        ) : (
                          <span
                            className="font-mono text-xs text-surface-600"
                            title={t("pg_hist_anterior_task_id")}
                          >
                            —
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center font-semibold text-brand-400">
                        {item.total_score != null ? item.total_score.toFixed(1) : "—"}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-300">
                        {item.affinity_kcal != null ? `${item.affinity_kcal.toFixed(1)} kcal/mol` : "—"}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-400">
                        {item.molecular_weight != null ? item.molecular_weight.toFixed(0) : "—"}
                      </td>
                      <td className="px-3 py-3 text-center">
                        {item.lipinski_pass != null ? (
                          item.lipinski_pass ? (
                            <span className="text-green-400">✓</span>
                          ) : (
                            <span className="text-red-400">✗</span>
                          )
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-400">
                        {item.qed != null ? item.qed.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-3 text-center">
                        {item.blockchain_tx_id ? (
                          <button
                            onClick={() => downloadCertificate(item.molecule_id)}
                            className="inline-flex items-center gap-1.5 rounded-md bg-brand-500/10 px-2 py-1 text-xs font-bold text-brand-400 transition-colors hover:bg-brand-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
                            title={t("pg_hist_descargar_recibo")}
                            aria-label={t("pg_hist_descargar_recibo")}
                          >
                            <Download className="w-3.5 h-3.5" aria-hidden="true" />
                              PDF
                          </button>
                        ) : (
                          <span className="text-xs text-surface-600">{t("pg_hist_sin_recibo")}</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right text-surface-500">
                        {item.created_at ? formatDate(item.created_at, locale) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Pagination ── */}
          {history.total > history.page_size && (
            <div className="flex items-center justify-center gap-3">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg border border-surface-700 px-3 py-1.5 text-xs text-surface-300 transition-colors hover:bg-surface-800 disabled:opacity-40"
              >
                {t("auto_87b0f80933cd")}
              </button>
              <span className="text-xs text-surface-400">
                {t("auto_b3a7f96a26dc")} {history.page} {t("auto_600ccd1b7156")} {Math.ceil(history.total / history.page_size)}
              </span>
              <button
                disabled={!history.has_next}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-surface-700 px-3 py-1.5 text-xs text-surface-300 transition-colors hover:bg-surface-800 disabled:opacity-40"
              >
                {t("auto_c6e084bf5a4a")}
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}

// ── Sub-components ──

function StatCard({
  label,
  value,
  color = "text-zinc-900 dark:text-zinc-100",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-surface-800 bg-surface-900 p-3 text-center">
      <div className={`text-lg font-bold ${color}`}>{value}</div>
      <div className="text-xs text-surface-500">{label}</div>
    </div>
  );
}

/**
 * HIST-FE-003. Los estados que la DB produce son los de `MoleculeStatus`, en minúscula:
 * `pending`, `validated`, `docking`, `evaluated`, `failed`. El mapa anterior sólo conocía
 * nombres de tarea Celery —`SUCCESS`, `FAILURE`, `PENDING`, `running`, `completed`—, así
 * que el estado MÁS común, una evaluación terminada, caía al `??` y se pintaba crudo y en
 * inglés: «evaluated» en Historial contra «Completada» en Evaluación, para la misma corrida.
 *
 * Las claves antiguas se conservan porque una respuesta heredada aún puede traerlas.
 */
const ESTADO_MOLECULA: Record<string, { bg: string; text: string; clave: string }> = {
  // MoleculeStatus — core/models.py
  pending: { bg: "bg-yellow-900/30", text: "text-yellow-400", clave: "pg_hist_estado_pendiente" },
  validated: { bg: "bg-surface-800", text: "text-surface-300", clave: "pg_hist_estado_validada" },
  docking: { bg: "bg-blue-900/30", text: "text-blue-400", clave: "pg_hist_estado_en_curso" },
  evaluated: { bg: "bg-green-900/30", text: "text-green-400", clave: "pg_hist_estado_completada" },
  failed: { bg: "bg-red-900/30", text: "text-red-400", clave: "pg_hist_estado_fallida" },
  // Nombres de tarea heredados
  completed: { bg: "bg-green-900/30", text: "text-green-400", clave: "pg_hist_estado_completada" },
  SUCCESS: { bg: "bg-green-900/30", text: "text-green-400", clave: "pg_hist_estado_completada" },
  FAILURE: { bg: "bg-red-900/30", text: "text-red-400", clave: "pg_hist_estado_fallida" },
  running: { bg: "bg-blue-900/30", text: "text-blue-400", clave: "pg_hist_estado_en_curso" },
  PENDING: { bg: "bg-yellow-900/30", text: "text-yellow-400", clave: "pg_hist_estado_pendiente" },
};

function StatusBadge({ status }: { status: string }) {
  const { t } = useLanguage();
  const c = ESTADO_MOLECULA[status];
  return (
    <span
      className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold ${
        c ? `${c.bg} ${c.text}` : "bg-surface-800 text-surface-400"
      }`}
    >
      {c ? t(c.clave) : status}
    </span>
  );
}
