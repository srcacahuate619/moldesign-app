"use client";

import { presentError } from "../../lib/frontendError";

/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4
 * Historial: jerarquía editorial para datos reales, con todas las operaciones existentes. */

import { useLanguage } from "../../context/LanguageContext";
import { useEffect, useRef, useState } from "react";
import { Download } from "lucide-react";

import { useAuth } from "../../lib/auth";
import { useKeepAliveActive } from "../../context/KeepAliveContext";
import { getEvaluationHistory, getUserStats, downloadCertificate, mensajeDelError } from "../../lib/api";
import { downloadRunReceipt } from "../../lib/history";
import type { EvaluationSummary, HistoryResponse, UserStats } from "../../lib/types";
import { EmptyState } from "../../components/ui/EmptyState";

// Con hora: una molécula se evalúa varias veces el mismo día y cada corrida es su
// propia fila. Sin la hora, dos corridas de la misma molécula con cifras iguales
// se veían como una fila repetida (o como una evaluación sobrescrita).
function formatDate(dateStr: string, locale: string) {
  return new Date(dateStr).toLocaleString(locale === "en" ? "en-US" : "es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  const { t, locale } = useLanguage();
  const { user, isLoading: authLoading } = useAuth();
  // FIX (keep-alive): /history no se desmonta (KeepAliveLayout). Recargar al
  // volver a esta ruta para que las evaluaciones recién hechas aparezcan.
  const isActive = useKeepAliveActive();
  const [historyResult, setHistoryResult] = useState<{ userId: string; data: HistoryResponse } | null>(null);
  // Conservar la tabla durante una actualización, sólo si pertenece a esta cuenta.
  const history = historyResult?.userId === user?.user_id ? historyResult?.data ?? null : null;
  const [stats, setStats] = useState<UserStats | null>(null);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("created_at");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Al cambiar de página u orden, conservar las filas hasta recibir la respuesta.
  // El indicador de carga sustituye la tabla sólo en la primera consulta.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getEvaluationHistory(page, 20, sortBy, "desc")
      .then((data) => { if (!cancelled) setHistoryResult({ userId: user.user_id, data }); })
      .catch((e) => { if (!cancelled) setError(presentError(e, t)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user, page, sortBy, t]);

  // Fetch stats
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getUserStats()
      .then((data) => { if (!cancelled) setStats(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [user]);

  // Al VOLVER a la pestaña (keep-alive) se refresca en silencio: la tabla que había se queda hasta que llega la nueva,
  // sin «cargando». Antes `isActive` no cambiaba nunca (el layout no daba el contexto) y una evaluación nueva no
  // aparecía al volver; con el contexto y el «cargando» de siempre, cada vuelta habría parpadeado.
  const vistaAntes = useRef(isActive);
  useEffect(() => {
    const volvio = isActive && !vistaAntes.current;
    vistaAntes.current = isActive;
    if (!volvio || !user) return;
    let cancelled = false;
    getEvaluationHistory(page, 20, sortBy, "desc")
      .then((data) => { if (!cancelled) setHistoryResult({ userId: user.user_id, data }); })
      .catch(() => { /* se queda la tabla que había */ });
    getUserStats()
      .then((data) => { if (!cancelled) setStats(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [isActive, user, page, sortBy]);

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
        ctaLabel={t("c_iniciar_sesion")}
        footerStatus={t("pg_hist_footer_sesiones")}
      />
    );
  }

  return (
    <main className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] text-[var(--text)]">
      <div className="mx-auto max-w-[1500px] px-4 pb-16 pt-8 sm:px-7 lg:px-10">
      {/* ── Header ── */}
      <section className="mb-10 flex flex-wrap items-end justify-between gap-6 border-b border-[var(--border)] pb-8">
        <div className="max-w-3xl">
          <p className="mb-3 font-mono text-[11px] font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">Moldex / {t("pg_hist_titulo")}</p>
          <h1 className="font-display text-3xl font-bold leading-[1.08] tracking-tight sm:text-4xl lg:text-5xl">{t("pg_hist_titulo")}</h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
          {t("pg_hist_descripcion")} <span className="font-medium">Moldex</span>.
          </p>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-[var(--text-secondary)]">{t("pg_hist_vina_condition")}</p>
        </div>
        {history && (
          <div className="border-l-2 border-[var(--accent-strong)] pl-4 text-right">
            <span className="block font-display text-3xl font-bold tabular-nums">{history.total}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{t("pg_hist_stat_total")}</span>
          </div>
        )}
      </section>

      {/* ── Stats ── */}
      {stats && (
        <section aria-label={t("pg_hist_titulo")} className="mb-9 grid grid-cols-2 border border-[var(--border)] bg-[var(--bg-card)] sm:grid-cols-4">
          <StatCard label={t("pg_hist_stat_total")} value={stats.total_evaluations} />
          <StatCard label={t("lo_filtro_completadas")} value={stats.completed_evaluations} color="text-[var(--categoria-hallazgo)]" />
          <StatCard label={t("lo_filtro_fallidas")} value={stats.failed_evaluations} color="text-[var(--categoria-refutacion)]" />
          <StatCard label={t("pg_hist_targets_unicos")} value={stats.unique_targets} />
        </section>
      )}

      {/* ── Controls ── */}
      <section className="mb-4 flex flex-wrap items-center gap-2 border-b border-[var(--border)] pb-4">
        <span className="mr-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-dim)]">{t("pg_hist_ordenar")}</span>
        {[
          { key: "created_at", label: t("pg_hist_orden_fecha") },
          { key: "affinity_kcal", label: t("c_afinidad") },
        ].map((opt) => (
          <button
            key={opt.key}
            type="button"
            aria-pressed={sortBy === opt.key}
            onClick={() => { setSortBy(opt.key); setPage(1); }}
            className={`min-h-9 cursor-pointer border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${
              sortBy === opt.key
                ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)] text-[var(--text)]"
                : "border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:border-[var(--border-light)] active:bg-[var(--bg-secondary)]"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </section>

      {/* ── Error ── */}
      {error && (
        <section role="alert" className="mb-4 border border-[var(--border-light)] bg-[var(--bg-secondary)] p-4">
          <pre className="whitespace-pre-wrap text-xs text-[var(--text)]">{error}</pre>
        </section>
      )}

      {/* ── Loading ── */}
      {loading && !history && (
        <div className="flex items-center gap-3 border border-[var(--border)] bg-[var(--bg-card)] px-5 py-8 text-sm text-[var(--text-secondary)]" role="status">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--accent-strong)] border-t-transparent" />
          {t("pg_hist_cargando")}
        </div>
      )}

      {/* ── Table / ── EmptyState para logueado sin evaluaciones ── */}
      {history && (
        <div aria-busy={loading}>
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
                { n: "2", t: t("mx_paso_acopla"),  d: t("mx_paso_acopla_vina_d") },
                { n: "3", t: t("mx_paso_guarda"), d: t("pg_hist_ritual_conservar") },
              ]}
              ctaHref="/evaluation"
              ctaLabel={t("c_lanzar_pipeline")}
              footerStatus={t("pg_hist_footer_evaluaciones", { user: user?.email ?? user?.username ?? "local" })}
            />
          ) : (
            <div className="overflow-x-auto border border-[var(--border)] bg-[var(--bg-card)]">
              <table className="w-full min-w-[1120px] border-collapse text-xs">
                <thead className="border-b border-[var(--border)] bg-[var(--bg-secondary)]">
                  <tr>
                    <th className="px-4 py-4 text-left font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">SMILES</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("pg_hist_th_target")}</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("c_estado")}</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("pg_hist_th_corrida")}</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("pg_hist_afinidad_vina")}</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("pg_hist_th_mw")}</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">Lipinski</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">QED</th>
                    <th className="px-3 py-4 text-center font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("pg_hist_th_recibo")}</th>
                    <th className="px-3 py-4 text-right font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{t("pg_hist_th_fecha")}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.items.map((item: EvaluationSummary) => (
                    <tr
                      key={item.task_id ?? item.molecule_id}
                      className="border-b border-[var(--border)] transition-colors last:border-b-0 hover:bg-[var(--bg-secondary)]"
                    >
                      <td className="max-w-[240px] px-4 py-4 font-mono text-[11px] text-[var(--text)]">
                        <span className="block truncate" title={item.smiles}>{item.smiles}</span>
                        {item.is_saved && (
                          <span
                            className="mt-1 inline-block border border-[var(--accent)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[var(--accent-strong)]"
                            title={t("pg_hist_promovida_moldex")}
                          >
                            Moldex
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-4 text-center font-mono font-semibold text-[var(--text-secondary)]">{item.target_pdb_id}</td>
                      <td className="px-3 py-4 text-center">
                        <StatusBadge status={item.status} />
                      </td>
                      {/*
                        HIST-INT-004. La corrida es la identidad con la que se recupera el
                        snapshot inmutable (EVAL-P0-02). Sin ella, una fila del historial no
                        se distingue de la última evaluación de la misma molécula. Aún no
                        abre el caso: eso exige materializarlo desde Evaluación, y es una
                        decisión de arquitectura que este paquete no toma.
                      */}
                      <td className="px-3 py-4 text-center">
                        {item.task_id ? (
                          <button
                            type="button"
                            onClick={() => navigator.clipboard?.writeText(item.task_id as string)}
                            className="cursor-pointer border border-transparent px-1.5 py-1 font-mono text-xs text-[var(--text-secondary)] transition-colors hover:border-[var(--border-light)] hover:text-[var(--text)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"
                            title={t("pg_hist_copiar_id", { taskId: item.task_id })}
                            aria-label={t("pg_hist_copiar_id_corto", { taskId: item.task_id })}
                          >
                            {item.task_id.slice(0, 8)}…
                          </button>
                        ) : (
                          <span
                            className="font-mono text-xs text-[var(--text-dim)]"
                            title={t("pg_hist_anterior_task_id")}
                          >
                            —
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-4 text-center font-mono tabular-nums text-[var(--text)]">
                        {item.affinity_kcal != null ? `${item.affinity_kcal.toFixed(1)} kcal/mol` : "—"}
                        {/* La afinidad conserva la condición del protocolo de origen. */}
                        {item.protocolo_vigente === false && (
                          <span className="mt-1 block text-[9px] font-bold uppercase tracking-[0.08em] text-[var(--categoria-corrigendum)]" title={t("pg_hist_protocolo_d")}>
                            {t("pg_protocolo_anterior")}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-4 text-center font-mono tabular-nums text-[var(--text-secondary)]">
                        {item.molecular_weight != null ? item.molecular_weight.toFixed(0) : "—"}
                      </td>
                      <td className="px-3 py-4 text-center">
                        {item.lipinski_pass != null ? (
                          item.lipinski_pass ? (
                            <span className="font-bold text-[var(--categoria-hallazgo)]">✓</span>
                          ) : (
                            <span className="font-bold text-[var(--categoria-refutacion)]">✗</span>
                          )
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-4 text-center font-mono tabular-nums text-[var(--text-secondary)]">
                        {item.qed != null ? item.qed.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-4 text-center">
                        {item.blockchain_tx_id ? (
                          <button
                            type="button"
                            onClick={() => { void (item.task_id ? downloadRunReceipt(item.task_id) : downloadCertificate(item.molecule_id)).catch((cause) => setError(mensajeDelError(cause))); }}
                            className="inline-flex min-h-8 cursor-pointer items-center gap-1.5 border border-[var(--border-light)] px-2 py-1 text-xs font-bold text-[var(--text)] transition-colors hover:border-[var(--accent-strong)] hover:text-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"
                            title={t("pg_hist_descargar_recibo")}
                            aria-label={t("pg_hist_descargar_recibo")}
                          >
                            <Download className="w-3.5 h-3.5" aria-hidden="true" />
                              PDF
                          </button>
                        ) : (
                          <span className="text-xs text-[var(--text-dim)]">{t("pg_hist_sin_recibo")}</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-right font-mono text-[11px] text-[var(--text-dim)]">
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
            <div className="mt-5 flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={loading || page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="min-h-9 cursor-pointer border border-[var(--border-light)] bg-[var(--bg-card)] px-3 py-1.5 text-xs text-[var(--text)] transition-colors hover:border-[var(--accent)] active:bg-[var(--bg-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t("auto_87b0f80933cd")}
              </button>
              <span className="font-mono text-[11px] tabular-nums text-[var(--text-dim)]">
                {t("auto_b3a7f96a26dc")} {history.page} {t("auto_600ccd1b7156")} {Math.ceil(history.total / history.page_size)}
              </span>
              <button
                type="button"
                disabled={loading || !history.has_next}
                onClick={() => setPage((p) => p + 1)}
                className="min-h-9 cursor-pointer border border-[var(--border-light)] bg-[var(--bg-card)] px-3 py-1.5 text-xs text-[var(--text)] transition-colors hover:border-[var(--accent)] active:bg-[var(--bg-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t("auto_c6e084bf5a4a")}
              </button>
            </div>
          )}
        </div>
      )}
      </div>
    </main>
  );
}

// ── Sub-components ──

function StatCard({
  label,
  value,
  color = "text-[var(--text)]",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="flex min-h-[108px] flex-col justify-between border-b border-r border-[var(--border)] p-4 last:border-r-0 lg:border-b-0">
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-dim)]">{label}</div>
      <div className={`font-display text-2xl font-bold tabular-nums ${color}`}>{value}</div>
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
  pending: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-corrigendum)]", clave: "c_pendiente" },
  validated: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--text-secondary)]", clave: "pg_hist_estado_validada" },
  docking: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-medicion)]", clave: "pg_hist_estado_en_curso" },
  evaluated: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-hallazgo)]", clave: "pg_hist_estado_completada" },
  failed: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-refutacion)]", clave: "pg_hist_estado_fallida" },
  // Nombres de tarea heredados
  completed: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-hallazgo)]", clave: "pg_hist_estado_completada" },
  SUCCESS: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-hallazgo)]", clave: "pg_hist_estado_completada" },
  FAILURE: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-refutacion)]", clave: "pg_hist_estado_fallida" },
  running: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-medicion)]", clave: "pg_hist_estado_en_curso" },
  PENDING: { bg: "bg-[var(--bg-secondary)]", text: "text-[var(--categoria-corrigendum)]", clave: "c_pendiente" },
};

function StatusBadge({ status }: { status: string }) {
  const { t } = useLanguage();
  const c = ESTADO_MOLECULA[status];
  return (
    <span
      className={`inline-block whitespace-nowrap border border-[var(--border)] px-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-wide ${
        c ? `${c.bg} ${c.text}` : "bg-[var(--bg-secondary)] text-[var(--text-secondary)]"
      }`}
    >
      {c ? t(c.clave) : status}
    </span>
  );
}
