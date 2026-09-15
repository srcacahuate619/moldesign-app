"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useState, useEffect } from "react";
import { Globe, Users, Trophy, Download, Lock, RefreshCw, Wifi, WifiOff, Share2, User } from "lucide-react";
import { getApiUrl } from "../lib/config";
import type { Target } from "../lib/api";
import { getUserItem, setUserItem } from "../lib/userStorage";

interface LeaderboardEntry {
  username: string;
  total_score: number;
  affinity_kcal: number;
}

export function CommunityPanel() {
  const { t } = useLanguage();
  const [enabled, setEnabled] = useState(false);
  const [communityTargets, setCommunityTargets] = useState<Target[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [cloudEmail, setCloudEmail] = useState("");
  const [cloudPassword, setCloudPassword] = useState("");
  const [cloudUser, setCloudUser] = useState<string | null>(
    getUserItem("moldesign_cloud_user")
  );
  const [loginError, setLoginError] = useState<string | null>(null);

  const toggleCommunity = () => {
    const next = !enabled;
    setEnabled(next);
    if (next) fetchCommunity();
  };

  const fetchCommunity = async () => {
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
        setLeaderboard(Array.isArray(l) ? l.slice(0, 5) : []);
      }
    } catch {
      setError(t("auto_02aba466e282"));
      setConnected(false);
    } finally {
      setLoading(false);
    }
  };

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

  const handleLogin = async () => {
    setLoginError(null);
    try {
      const r = await fetch(`${await getApiUrl()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cloudEmail, password: cloudPassword }),
      });
      const data = await r.json();
      if (data.access_token) {
        setCloudUser(data.username || cloudEmail);
        setShowLogin(false);
        setUserItem("moldesign_cloud_user", data.username || cloudEmail);
      } else {
        setLoginError(data.detail || "Login failed");
      }
    } catch {
      setLoginError("No se pudo conectar con el servidor cloud");
    }
  };

  return (
    <div className="rounded-xl border border-zinc-700/30 bg-zinc-800/20 overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-zinc-700/20">
        <div className="flex items-center gap-2">
          <Globe className={`w-4 h-4 ${connected ? "text-emerald-400" : "text-zinc-500"}`} />
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Comunidad Global</h3>
            <p className="text-[10px] text-zinc-500">
              {connected ? `${communityTargets.length} targets` : t("auto_0229a5139372")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!cloudUser && connected && (
            <button onClick={() => setShowLogin(!showLogin)} className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-zinc-400 hover:text-zinc-200">
              <User className="w-3 h-3" /> Login
            </button>
          )}
          {cloudUser && <span className="text-[10px] text-cyan-400 font-mono">@{cloudUser}</span>}
          <button onClick={toggleCommunity} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
            enabled ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-zinc-700/50 text-zinc-400 border border-zinc-600/30 hover:border-zinc-500"
          }`}>
            {enabled ? <><Wifi className="w-3 h-3" /> Conectado</> : <><WifiOff className="w-3 h-3" /> Conectar</>}
          </button>
        </div>
      </div>

      {showLogin && (
        <div className="p-4 border-b border-zinc-700/20 bg-zinc-800/30">
          <div className="flex gap-2">
            <input type="email" placeholder="Email" value={cloudEmail} onChange={e => setCloudEmail(e.target.value)} className="flex-1 px-3 py-1.5 rounded-lg bg-zinc-700 border border-zinc-600 text-xs text-zinc-200" />
            <input type="password" placeholder="Pass" value={cloudPassword} onChange={e => setCloudPassword(e.target.value)} className="w-28 px-3 py-1.5 rounded-lg bg-zinc-700 border border-zinc-600 text-xs text-zinc-200" />
            <button onClick={handleLogin} className="px-3 py-1.5 rounded-lg bg-cyan-600 text-xs font-medium text-white hover:bg-cyan-500">{t("login")}</button>
          </div>
          {loginError && <p className="text-[10px] text-red-400 mt-1">{loginError}</p>}
        </div>
      )}

      {enabled && (
        <div className="p-4 space-y-4">
          {error && <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/5 border border-red-500/10 text-xs text-red-400"><Lock className="w-3.5 h-3.5" />{error}<button onClick={fetchCommunity} className="ml-auto"><RefreshCw className="w-3.5 h-3.5" /></button></div>}
          {loading && <div className="flex items-center justify-center gap-2 py-4 text-xs text-zinc-500"><RefreshCw className="w-3.5 h-3.5 animate-spin" />Conectando...</div>}

          {connected && communityTargets.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 flex items-center gap-1.5"><Users className="w-3 h-3" />{t("z_targets_comunidad")}</h4>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {communityTargets.slice(0, 10).map(t => (
                  <div key={t.pdb_id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-700/20 text-xs hover:bg-zinc-700/30">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-cyan-400 shrink-0">{t.pdb_id}</span>
                      <span className="text-zinc-300 truncate">{t.name}</span>
                      {t.creator_username && <span className="text-[10px] text-violet-400 shrink-0">@{t.creator_username}</span>}
                    </div>
                    <button onClick={() => handleDownload(t.pdb_id)} disabled={downloading === t.pdb_id} className="p-1 rounded hover:bg-zinc-600/50 disabled:opacity-50">
                      {downloading === t.pdb_id ? <RefreshCw className="w-3 h-3 text-zinc-400 animate-spin" /> : <Download className="w-3 h-3 text-zinc-500 hover:text-cyan-400" />}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {connected && leaderboard.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 flex items-center gap-1.5"><Trophy className="w-3 h-3 text-amber-400" />Top Descubrimientos</h4>
              {leaderboard.map((entry, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-700/20 text-xs">
                  <div className="flex items-center gap-2">
                    <span className={`font-mono font-bold w-5 ${i===0?"text-amber-400":i===1?"text-zinc-300":"text-zinc-500"}`}>#{i+1}</span>
                    <span className="text-zinc-300">@{entry.username}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-emerald-400">{entry.total_score?.toFixed(0)}</span>
                    <span className="font-mono text-zinc-500">{entry.affinity_kcal?.toFixed(1)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {connected && (
            <div className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-violet-500/5 to-cyan-500/5 border border-violet-500/10">
              <Share2 className="w-4 h-4 text-violet-400 shrink-0" />
              <div className="text-xs">
                <p className="text-zinc-300 font-medium">Comparti tus descubrimientos</p>
                <p className="text-zinc-500 mt-0.5">{cloudUser ? t("auto_f78181f943ab") : t("auto_c1b0533bca64")}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
