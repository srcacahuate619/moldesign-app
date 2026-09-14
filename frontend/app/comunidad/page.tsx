"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Globe, Users, Trophy, Download, RefreshCw, Wifi, WifiOff,
  Share2, User, Search, ArrowUpRight, Zap, Target, Star,
  TrendingUp, Crown, Medal, Award, ChevronRight, ExternalLink
} from "lucide-react";
import { getApiUrl } from "../../lib/config";
import type { Target as TargetType } from "../../lib/api";
import { getUserItem } from "../../lib/userStorage";

interface LeaderboardEntry {
  username: string;
  total_score: number;
  affinity_kcal: number;
  target_pdb_id?: string;
  smiles?: string;
}

export default function ComunidadPage() {
  const [communityTargets, setCommunityTargets] = useState<TargetType[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [cloudUser] = useState<string | null>(
    getUserItem("moldesign_cloud_user")
  );

  const fetchCommunity = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [targetsRes, leaderRes] = await Promise.all([
        fetch(`${await getApiUrl()}/targets/community`),
        fetch(`${await getApiUrl()}/stats/leaderboard`),
      ]);
      if (targetsRes.ok) {
        const t = await targetsRes.json();
        setCommunityTargets(Array.isArray(t) ? t : []);
        setConnected(true);
      }
      if (leaderRes.ok) {
        const l = await leaderRes.json();
        setLeaderboard(Array.isArray(l) ? l : []);
      }
    } catch {
      setError("No se pudo conectar con la comunidad. Verifica tu conexión a internet.");
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCommunity();
  }, [fetchCommunity]);

  const handleDownload = async (pdbId: string) => {
    setDownloading(pdbId);
    try {
      const r = await fetch(`${await getApiUrl()}/targets/community/download/${pdbId}`, { method: "POST" });
      if (r.ok) {
        window.dispatchEvent(new CustomEvent("target_downloaded", { detail: { pdb_id: pdbId } }));
      }
    } catch {}
    finally { setDownloading(null); }
  };

  const filteredTargets = communityTargets.filter(t =>
    !searchQuery ||
    t.pdb_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.structural_family?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getRankIcon = (index: number) => {
    if (index === 0) return <Crown className="w-4 h-4 text-amber-600 dark:text-amber-400" />;
    if (index === 1) return <Medal className="w-4 h-4 text-muted" />;
    if (index === 2) return <Award className="w-4 h-4 text-amber-600" />;
    return <span className="w-4 text-center font-mono text-xs text-dim">#{index + 1}</span>;
  };

  const getRankBg = (index: number) => {
    if (index === 0) return "bg-gradient-to-r from-amber-500/[0.06] to-transparent border-amber-500/20";
    if (index === 1) return "bg-gradient-to-r from-zinc-400/[0.04] to-transparent border-zinc-500/15";
    if (index === 2) return "bg-gradient-to-r from-amber-700/[0.04] to-transparent border-amber-700/15";
    return "bg-[var(--bg-card)] border-[var(--border)]";
  };

  return (
    <main className="min-h-screen bg-[var(--bg)] font-mono text-theme">
      {/* Hero Header */}
      <section className="relative overflow-hidden border-b border-[var(--border)]">
        <div className="absolute inset-0 bg-gradient-to-b from-purple-900/[0.06] via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(168,85,247,0.04),transparent_60%)]" />
        
        <div className="relative max-w-7xl mx-auto px-6 py-16 lg:py-20">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-full border border-purple-500/30 bg-purple-500/[0.08] flex items-center justify-center">
                  <Globe className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div className="flex items-center gap-2">
                  {connected ? (
                    <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-emerald-700 dark:text-emerald-400">
                      <Wifi className="w-3 h-3" /> Conectado
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 rounded-full border border-[var(--border-light)] bg-[var(--bg-secondary)] px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-muted">
                      <WifiOff className="w-3 h-3" /> Sin Conexión
                    </span>
                  )}
                  {cloudUser && (
                    <span className="rounded-full border border-purple-500/20 bg-purple-500/[0.06] px-2.5 py-1 font-mono text-[10px] text-purple-600 dark:text-purple-400">
                      @{cloudUser}
                    </span>
                  )}
                </div>
              </div>
              
              <h1 className="mb-3 text-3xl font-black uppercase tracking-tight text-theme lg:text-4xl">
                Comunidad Global
              </h1>
              <p className="max-w-lg text-sm leading-relaxed text-muted">
                Explora targets compartidos por la comunidad, descarga receptores curados y consulta
                evaluaciones publicadas bajo sus condiciones declaradas.
              </p>
            </div>

            <button
              onClick={fetchCommunity}
              disabled={loading}
              className="hidden cursor-pointer items-center gap-2 rounded-lg border border-[var(--border-light)] bg-[var(--bg-card)] px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-muted transition-all hover:border-purple-500/40 hover:text-theme disabled:opacity-50 lg:flex"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Actualizar
            </button>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-10">
            {[
              { label: "Targets Compartidos", value: communityTargets.length, icon: Target, color: "text-purple-600 dark:text-purple-400" },
              { label: "Investigadores", value: leaderboard.length, icon: Users, color: "text-blue-600 dark:text-blue-400" },
              { label: "Mejor Score", value: leaderboard[0]?.total_score?.toFixed(0) || "—", icon: TrendingUp, color: "text-emerald-700 dark:text-emerald-400" },
              { label: "Mejor Afinidad", value: leaderboard[0]?.affinity_kcal ? `${leaderboard[0].affinity_kcal.toFixed(1)} kcal` : "—", icon: Zap, color: "text-amber-600 dark:text-amber-400" },
            ].map((stat, i) => (
              <div key={i} className="group relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-card)] px-5 py-4">
                <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-purple-500/[0.03] to-transparent rounded-bl-full" />
                <stat.icon className={`w-4 h-4 ${stat.color} mb-2`} />
                <p className="font-mono text-xl font-black text-theme">{stat.value}</p>
                <p className="mt-1 text-[10px] uppercase tracking-widest text-muted">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Content Grid */}
      <div className="max-w-7xl mx-auto px-6 py-10">
        {error && (
          <div className="mb-8 flex items-center gap-3 rounded-xl border border-red-500/15 bg-red-500/[0.06] p-4 text-sm text-red-700 dark:text-red-400">
            <WifiOff className="w-4 h-4 shrink-0" />
            <span>{error}</span>
            <button onClick={fetchCommunity} className="ml-auto text-red-500 transition-colors hover:text-theme dark:text-red-300">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          
          {/* LEFT: Community Targets (3 cols) */}
          <div className="lg:col-span-3 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Users className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-theme">Targets Compartidos</h2>
                <span className="rounded-full border border-[var(--border)] bg-[var(--bg-card)] px-2 py-0.5 font-mono text-[10px] text-dim">
                  {filteredTargets.length}
                </span>
              </div>
            </div>

            {/* Search Bar */}
            <div className="relative">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
              <input
                type="text"
                placeholder="Buscar por PDB ID, nombre o categoría..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full rounded-xl border border-[var(--border)] bg-[var(--bg-card)] py-3 pr-4 pl-11 font-mono text-sm text-theme transition-all placeholder:text-dim focus:border-purple-500/30 focus:ring-1 focus:ring-purple-500/20 focus:outline-none"
              />
            </div>

            {/* Targets Grid */}
            {loading && !connected ? (
              <div className="flex items-center justify-center gap-3 py-16 text-muted">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span className="text-sm font-mono">Conectando con la comunidad...</span>
              </div>
            ) : filteredTargets.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Target className="mb-3 h-8 w-8 text-dim" />
                <p className="text-sm text-muted">
                  {searchQuery ? "Sin resultados para esta búsqueda" : "No hay targets compartidos aún"}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredTargets.map(t => (
                  <div
                    key={t.pdb_id}
                    className="group relative rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 transition-all hover:border-purple-500/20 hover:bg-[var(--bg-secondary)]"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-black tracking-wide text-purple-600 dark:text-purple-400">{t.pdb_id}</span>
                        {t.resolution && (
                          <span className="rounded bg-[var(--bg-secondary)] px-1.5 py-0.5 font-mono text-[9px] text-muted">
                            {t.resolution}Å
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => handleDownload(t.pdb_id)}
                        disabled={downloading === t.pdb_id}
                        className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-light)] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-muted transition-all hover:border-purple-500/30 hover:bg-purple-500/[0.06] hover:text-theme disabled:opacity-40"
                      >
                        {downloading === t.pdb_id ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          <Download className="w-3 h-3" />
                        )}
                        {downloading === t.pdb_id ? "..." : "Descargar"}
                      </button>
                    </div>

                    <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-muted">
                      {t.name || "Target sin nombre"}
                    </p>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {t.structural_family && (
                          <span className="rounded-full border border-[var(--border-light)] bg-[var(--bg-secondary)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted">
                            {t.structural_family}
                          </span>
                        )}
                      </div>
                      {t.creator_username && (
                        <span className="flex items-center gap-1 font-mono text-[10px] text-purple-700/80 dark:text-purple-400/70">
                          <User className="w-3 h-3" />@{t.creator_username}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RIGHT: Leaderboard (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center gap-3">
              <Trophy className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-theme">Leaderboard Global</h2>
            </div>

            <div className="space-y-2">
              {leaderboard.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--bg-card)] py-16 text-center">
                  <Trophy className="mb-3 h-8 w-8 text-dim" />
                  <p className="text-sm text-muted">Sin datos de leaderboard</p>
                  <p className="mt-1 text-[10px] text-dim">Evalúa moléculas para aparecer aquí</p>
                </div>
              ) : (
                leaderboard.map((entry, i) => (
                  <div
                    key={i}
                    className={`flex items-center justify-between px-4 py-3.5 rounded-xl border transition-all ${getRankBg(i)}`}
                  >
                    <div className="flex items-center gap-3">
                      {getRankIcon(i)}
                      <div>
                        <span className="text-sm font-bold text-theme">@{entry.username}</span>
                        {entry.target_pdb_id && (
                          <span className="ml-2 font-mono text-[9px] text-dim">{entry.target_pdb_id}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="font-mono text-sm font-black text-emerald-700 dark:text-emerald-400">{entry.total_score?.toFixed(0)}</p>
                        <p className="font-mono text-[9px] uppercase text-dim">Score</p>
                      </div>
                      <div className="text-right">
                        <p className="font-mono text-sm font-bold text-muted">{entry.affinity_kcal?.toFixed(1)}</p>
                        <p className="font-mono text-[9px] uppercase text-dim">kcal/mol</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Share CTA */}
            <div className="rounded-xl border border-purple-500/15 bg-gradient-to-br from-purple-500/[0.04] to-transparent p-5 space-y-3">
              <div className="flex items-center gap-2">
                <Share2 className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                <h3 className="text-xs font-bold uppercase tracking-widest text-purple-600 dark:text-purple-300">Comparte tu evidencia</h3>
              </div>
              <p className="text-xs leading-relaxed text-muted">
                {cloudUser
                  ? "Sube un target público para colaborar con la comunidad científica global."
                  : "Inicia sesión cloud para compartir targets con atribución."
                }
              </p>
              <button className="flex cursor-pointer items-center gap-2 rounded-lg border border-purple-500/20 px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-purple-700 transition-all hover:border-purple-500/30 hover:bg-purple-500/[0.08] dark:text-purple-300">
                <ArrowUpRight className="w-3.5 h-3.5" />
                {cloudUser ? "Compartir Target" : "Conectar Cloud"}
              </button>
            </div>

            {/* Quick Stats */}
            <div className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-5">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted">Actividad Reciente</h3>
              <div className="space-y-3">
                {[
                  { text: "Nuevo target compartido", time: "Hace 2h", icon: Target },
                  { text: "Record de score superado", time: "Hace 5h", icon: Star },
                  { text: "Investigador se unió", time: "Hace 1d", icon: User },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs">
                    <item.icon className="h-3.5 w-3.5 shrink-0 text-dim" />
                    <span className="flex-1 text-muted">{item.text}</span>
                    <span className="font-mono text-[9px] text-dim">{item.time}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}
