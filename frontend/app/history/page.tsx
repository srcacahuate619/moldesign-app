"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download } from "lucide-react";

import { useAuth } from "../../lib/auth";
import { useKeepAliveActive } from "../../context/KeepAliveContext";
import { getEvaluationHistory, getUserStats, downloadCertificate } from "../../lib/api";
import type { EvaluationSummary, HistoryResponse, UserStats } from "../../lib/types";
import { EmptyState } from "../../components/ui/EmptyState";

export default function HistoryPage() {
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
        title="Verificando sesión"
        description="Tu identidad molecular se está validando en el servidor local."
        subline="autocomplete · validando token jwt · v 2.0"
        footerStatus="historial molecular · acceso autenticado"
      />
    );
  }

  // ── ESTADO 2/3: No autenticado (ThinkingOrb idle, ritual de autenticación) ──
  if (!user) {
    return (
      <EmptyState
        orbState="idle"
        title="Acceso Bloqueado"
        description={
          <>
            El historial guarda huellas que solo tus ojos deben ver:
            evaluaciones, resultados y recibos de integridad.
            Identifícate para continuar.
          </>
        }
        ritual={[
          { n: "1", t: "Inicia",  d: "con tu cuenta local" },
          { n: "2", t: "Conecta", d: "wallet Solana opcional" },
          { n: "3", t: "Accede",  d: "a tu historial firmado" },
        ]}
        ctaHref="/login"
        ctaLabel="Iniciar Sesión"
        footerStatus="0 sesiones activas · acceso autenticado · v 2.0"
      />
    );
  }

  return (
    <main className="space-y-6 pb-12">
      {/* ── Header ── */}
      <section>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Historial de evaluaciones</h1>
        <p className="mt-1 text-sm text-surface-400">
          Todas las evaluaciones de tu cuenta, tal como están en la base de datos. Las que
          además aparecen en Moldex llevan la marca <span className="font-medium">Moldex</span>.
        </p>
      </section>

      {/* ── Stats ── */}
      {stats && (
        <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard label="Total" value={stats.total_evaluations} />
          <StatCard label="Completadas" value={stats.completed_evaluations} color="text-green-400" />
          <StatCard label="Fallidas" value={stats.failed_evaluations} color="text-red-400" />
          <StatCard
            label="Mejor score"
            value={stats.best_score != null ? stats.best_score.toFixed(1) : "—"}
            color="text-brand-400"
          />
          <StatCard
            label="Promedio"
            value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
          />
          <StatCard label="Targets únicos" value={stats.unique_targets} />
        </section>
      )}

      {/* ── Controls ── */}
      <section className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-surface-400">Ordenar por:</label>
        {[
          { key: "created_at", label: "Fecha" },
          { key: "total_score", label: "Score total" },
          { key: "affinity_kcal", label: "Afinidad" },
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
          Cargando evaluaciones...
        </div>
      )}

      {/* ── Table / ── EmptyState para logueado sin evaluaciones ── */}
      {history && !loading && (
        <>
          {history.items.length === 0 ? (
            // ── ESTADO 3/3: Logueado, sin historial (ThinkingOrb idle, ritual de workflow) ──
            <EmptyState
              orbState="idle"
              title="Historial en espera"
              description={
                <>
                  Todavía no has guardado ninguna evaluación molecular.
                  Una evaluación guardada conserva el docking, sus resultados,
                  los hotspots observados y, cuando existe, su recibo de integridad.
                </>
              }
              ritual={[
                { n: "1", t: "Diseña", d: "con el Ketcher Editor" },
                { n: "2", t: "Acopla",  d: "Vina + XGBoost + GNN" },
                { n: "3", t: "Guarda", d: "conservar en tu historial" },
              ]}
              ctaHref="/evaluation"
              ctaLabel="Lanzar Pipeline"
              footerStatus={`0 evaluaciones guardadas · usuario ${user?.email ?? user?.username ?? "local"} · v 2.0`}
            />
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-surface-800">
              <table className="w-full text-xs">
                <thead className="border-b border-surface-800 bg-surface-900">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-surface-400">SMILES</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Target</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Estado</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Corrida</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Score</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Afinidad</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">MW</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Lipinski</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">QED</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Recibo</th>
                    <th className="px-3 py-3 text-right font-semibold text-surface-400">Fecha</th>
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
                            title="Promovida a Moldex"
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
                            title={`Copiar identificador de corrida: ${item.task_id}`}
                            aria-label={`Copiar identificador de corrida ${item.task_id}`}
                          >
                            {item.task_id.slice(0, 8)}…
                          </button>
                        ) : (
                          <span
                            className="font-mono text-xs text-surface-600"
                            title="Corrida anterior al registro por task_id"
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
                            title="Descargar recibo de integridad PDF"
                            aria-label="Descargar recibo de integridad PDF"
                          >
                            <Download className="w-3.5 h-3.5" aria-hidden="true" />
                              PDF
                          </button>
                        ) : (
                          <span className="text-xs text-surface-600">Sin recibo</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right text-surface-500">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString("es-MX", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        }) : "—"}
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
                ← Anterior
              </button>
              <span className="text-xs text-surface-400">
                Página {history.page} de {Math.ceil(history.total / history.page_size)}
              </span>
              <button
                disabled={!history.has_next}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-surface-700 px-3 py-1.5 text-xs text-surface-300 transition-colors hover:bg-surface-800 disabled:opacity-40"
              >
                Siguiente →
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
const ESTADO_MOLECULA: Record<string, { bg: string; text: string; label: string }> = {
  // MoleculeStatus — core/models.py
  pending: { bg: "bg-yellow-900/30", text: "text-yellow-400", label: "Pendiente" },
  validated: { bg: "bg-surface-800", text: "text-surface-300", label: "Validada" },
  docking: { bg: "bg-blue-900/30", text: "text-blue-400", label: "En curso" },
  evaluated: { bg: "bg-green-900/30", text: "text-green-400", label: "Completada" },
  failed: { bg: "bg-red-900/30", text: "text-red-400", label: "Fallida" },
  // Nombres de tarea heredados
  completed: { bg: "bg-green-900/30", text: "text-green-400", label: "Completada" },
  SUCCESS: { bg: "bg-green-900/30", text: "text-green-400", label: "Completada" },
  FAILURE: { bg: "bg-red-900/30", text: "text-red-400", label: "Fallida" },
  running: { bg: "bg-blue-900/30", text: "text-blue-400", label: "En curso" },
  PENDING: { bg: "bg-yellow-900/30", text: "text-yellow-400", label: "Pendiente" },
};

function StatusBadge({ status }: { status: string }) {
  const c = ESTADO_MOLECULA[status] ?? {
    bg: "bg-surface-800",
    text: "text-surface-400",
    label: status,
  };
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}
