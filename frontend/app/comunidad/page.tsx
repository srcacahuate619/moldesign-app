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
    if (index === 0) return <Crown className="w-4 h-4 text-amber-400" />;
    if (index === 1) return <Medal className="w-4 h-4 text-zinc-300" />;
    if (index === 2) return <Award className="w-4 h-4 text-amber-600" />;
    return <span className="text-xs font-mono text-zinc-600 w-4 text-center">#{index + 1}</span>;
  };

  const getRankBg = (index: number) => {
    if (index === 0) return "bg-gradient-to-r from-amber-500/[0.06] to-transparent border-amber-500/20";
    if (index === 1) return "bg-gradient-to-r from-zinc-400/[0.04] to-transparent border-zinc-500/15";
    if (index === 2) return "bg-gradient-to-r from-amber-700/[0.04] to-transparent border-amber-700/15";
    return "bg-zinc-900/40 border-zinc-800/50";
  };

  return (
    <main className="min-h-screen bg-black text-white font-mono">
      {/* Hero Header */}
      <section className="relative overflow-hidden border-b border-zinc-800/60">
        <div className="absolute inset-0 bg-gradient-to-b from-purple-900/[0.06] via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(168,85,247,0.04),transparent_60%)]" />
        
        <div className="relative max-w-7xl mx-auto px-6 py-16 lg:py-20">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-full border border-purple-500/30 bg-purple-500/[0.08] flex items-center justify-center">
                  <Globe className="w-5 h-5 text-purple-400" />
                </div>
                <div className="flex items-center gap-2">
                  {connected ? (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <Wifi className="w-3 h-3" /> Conectado
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest bg-zinc-800 text-zinc-500 border border-zinc-700">
                      <WifiOff className="w-3 h-3" /> Sin Conexión
                    </span>
                  )}
                  {cloudUser && (
                    <span className="text-[10px] font-mono text-purple-400 border border-purple-500/20 rounded-full px-2.5 py-1 bg-purple-500/[0.06]">
                      @{cloudUser}
                    </span>
                  )}
                </div>
              </div>
              
              <h1 className="text-3xl lg:text-4xl font-black uppercase tracking-tight text-white mb-3">
                Comunidad Global
              </h1>
              <p className="text-sm text-zinc-400 max-w-lg leading-relaxed">
                Explora targets compartidos por la comunidad, descarga receptores curados y compite
                en el leaderboard global de descubrimientos moleculares.
              </p>
            </div>

            <button
              onClick={fetchCommunity}
              disabled={loading}
              className="hidden lg:flex items-center gap-2 px-4 py-2.5 rounded-lg border border-zinc-700 bg-zinc-900 text-xs font-bold uppercase tracking-wider text-zinc-300 hover:border-purple-500/40 hover:text-white transition-all cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Actualizar
            </button>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-10">
            {[
              { label: "Targets Compartidos", value: communityTargets.length, icon: Target, color: "text-purple-400" },
              { label: "Investigadores", value: leaderboard.length, icon: Users, color: "text-blue-400" },
              { label: "Mejor Score", value: leaderboard[0]?.total_score?.toFixed(0) || "—", icon: TrendingUp, color: "text-emerald-400" },
              { label: "Mejor Afinidad", value: leaderboard[0]?.affinity_kcal ? `${leaderboard[0].affinity_kcal.toFixed(1)} kcal` : "—", icon: Zap, color: "text-amber-400" },
            ].map((stat, i) => (
              <div key={i} className="relative rounded-xl border border-zinc-800/60 bg-zinc-900/50 px-5 py-4 overflow-hidden group">
                <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-purple-500/[0.03] to-transparent rounded-bl-full" />
                <stat.icon className={`w-4 h-4 ${stat.color} mb-2`} />
                <p className="text-xl font-black text-white font-mono">{stat.value}</p>
                <p className="text-[10px] uppercase tracking-widest text-zinc-500 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Content Grid */}
      <div className="max-w-7xl mx-auto px-6 py-10">
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/[0.06] border border-red-500/15 text-sm text-red-400 mb-8">
            <WifiOff className="w-4 h-4 shrink-0" />
            <span>{error}</span>
            <button onClick={fetchCommunity} className="ml-auto text-red-300 hover:text-white transition-colors">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          
          {/* LEFT: Community Targets (3 cols) */}
          <div className="lg:col-span-3 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Users className="w-4 h-4 text-purple-400" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Targets Compartidos</h2>
                <span className="text-[10px] font-mono text-zinc-600 bg-zinc-900 px-2 py-0.5 rounded-full border border-zinc-800">
                  {filteredTargets.length}
                </span>
              </div>
            </div>

            {/* Search Bar */}
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
              <input
                type="text"
                placeholder="Buscar por PDB ID, nombre o categoría..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-11 pr-4 py-3 rounded-xl bg-zinc-900/60 border border-zinc-800/60 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/30 focus:ring-1 focus:ring-purple-500/20 font-mono transition-all"
              />
            </div>

            {/* Targets Grid */}
            {loading && !connected ? (
              <div className="flex items-center justify-center gap-3 py-16 text-zinc-500">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span className="text-sm font-mono">Conectando con la comunidad...</span>
              </div>
            ) : filteredTargets.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Target className="w-8 h-8 text-zinc-700 mb-3" />
                <p className="text-sm text-zinc-500">
                  {searchQuery ? "Sin resultados para esta búsqueda" : "No hay targets compartidos aún"}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredTargets.map(t => (
                  <div
                    key={t.pdb_id}
                    className="group relative rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-4 hover:border-purple-500/20 hover:bg-zinc-900/60 transition-all"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono font-black text-purple-400 tracking-wide">{t.pdb_id}</span>
                        {t.resolution && (
                          <span className="text-[9px] font-mono text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                            {t.resolution}Å
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => handleDownload(t.pdb_id)}
                        disabled={downloading === t.pdb_id}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border border-zinc-700 text-zinc-400 hover:text-white hover:border-purple-500/30 hover:bg-purple-500/[0.06] transition-all disabled:opacity-40 cursor-pointer"
                      >
                        {downloading === t.pdb_id ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          <Download className="w-3 h-3" />
                        )}
                        {downloading === t.pdb_id ? "..." : "Descargar"}
                      </button>
                    </div>

                    <p className="text-xs text-zinc-300 leading-relaxed mb-3 line-clamp-2">
                      {t.name || "Target sin nombre"}
                    </p>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {t.structural_family && (
                          <span className="text-[9px] font-mono uppercase tracking-wider text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded-full border border-zinc-700/50">
                            {t.structural_family}
                          </span>
                        )}
                      </div>
                      {t.creator_username && (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-purple-400/70">
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
              <Trophy className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-white">Leaderboard Global</h2>
            </div>

            <div className="space-y-2">
              {leaderboard.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center rounded-xl border border-zinc-800/40 bg-zinc-900/30">
                  <Trophy className="w-8 h-8 text-zinc-700 mb-3" />
                  <p className="text-sm text-zinc-500">Sin datos de leaderboard</p>
                  <p className="text-[10px] text-zinc-600 mt-1">Evalúa moléculas para aparecer aquí</p>
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
                        <span className="text-sm font-bold text-zinc-200">@{entry.username}</span>
                        {entry.target_pdb_id && (
                          <span className="ml-2 text-[9px] font-mono text-zinc-600">{entry.target_pdb_id}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-sm font-mono font-black text-emerald-400">{entry.total_score?.toFixed(0)}</p>
                        <p className="text-[9px] font-mono text-zinc-600 uppercase">Score</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-mono font-bold text-zinc-400">{entry.affinity_kcal?.toFixed(1)}</p>
                        <p className="text-[9px] font-mono text-zinc-600 uppercase">kcal/mol</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Share CTA */}
            <div className="rounded-xl border border-purple-500/15 bg-gradient-to-br from-purple-500/[0.04] to-transparent p-5 space-y-3">
              <div className="flex items-center gap-2">
                <Share2 className="w-4 h-4 text-purple-400" />
                <h3 className="text-xs font-bold uppercase tracking-widest text-purple-300">Comparte tus descubrimientos</h3>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                {cloudUser
                  ? "Sube un target público para colaborar con la comunidad científica global."
                  : "Inicia sesión cloud para compartir targets con atribución."
                }
              </p>
              <button className="flex items-center gap-2 px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-widest border border-purple-500/20 text-purple-300 hover:bg-purple-500/[0.08] hover:border-purple-500/30 transition-all cursor-pointer">
                <ArrowUpRight className="w-3.5 h-3.5" />
                {cloudUser ? "Compartir Target" : "Conectar Cloud"}
              </button>
            </div>

            {/* Quick Stats */}
            <div className="rounded-xl border border-zinc-800/40 bg-zinc-900/30 p-5 space-y-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Actividad Reciente</h3>
              <div className="space-y-3">
                {[
                  { text: "Nuevo target compartido", time: "Hace 2h", icon: Target },
                  { text: "Record de score superado", time: "Hace 5h", icon: Star },
                  { text: "Investigador se unió", time: "Hace 1d", icon: User },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs">
                    <item.icon className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                    <span className="text-zinc-400 flex-1">{item.text}</span>
                    <span className="text-[9px] font-mono text-zinc-600">{item.time}</span>
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
