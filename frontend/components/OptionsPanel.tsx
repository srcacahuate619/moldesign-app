"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "../context/ThemeContext";
import { useAI } from "../context/AIContext";
import { useLanguage, LANGUAGES } from "../context/LanguageContext";
import { useDownload } from "../hooks/useDownload";
import { useRouter } from "next/navigation";
import {
  Sun, Moon, Monitor, Info, X, Bot,
  Volume2, VolumeX, Download, Trash2, Scale,
  Upload, CheckCircle, AlertTriangle, Wifi, HardDrive, Globe, Folder, FolderOpen, RefreshCw
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { playSound, isSoundMuted, setSoundMuted } from "../lib/sounds";
import { getMoldex, getEvaluationHistory, getUserStats } from "../lib/api";
import { getUserItem, setUserItem } from "../lib/userStorage";
import { useAuth } from "../lib/auth";

interface Props {
  open: boolean;
  onClose: () => void;
  onAboutClick: () => void;
  onTermsClick: () => void;
}

// ─── Section Header ─────────────────────────────────────────────────────────
function SectionLabel({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-widest" style={{ color: "var(--text)" }}>
      <Icon size={14} strokeWidth={1.5} style={{ color: "var(--accent)" }} />
      <span>{label}</span>
    </div>
  );
}

// ─── Action Row Button ────────────────────────────────────────────────────────
function ActionRow({
  icon: Icon,
  label,
  description,
  onClick,
  loading,
  disabled,
  variant = "default",
}: {
  icon: LucideIcon;
  label: string;
  description?: string;
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "default" | "danger";
}) {
  const danger = variant === "danger";
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="flex items-start gap-3 w-full px-4 py-3 transition-colors text-left disabled:opacity-40 disabled:cursor-not-allowed rounded-lg"
      style={{
        backgroundColor: "var(--bg)",
        border: `1px solid ${danger ? "rgba(239,68,68,0.25)" : "var(--border)"}`,
        color: danger ? "#ef4444" : "var(--text)",
        cursor: disabled || loading ? "not-allowed" : "pointer",
      }}
    >
      <span style={{ paddingTop: 2, flexShrink: 0 }}>
        {loading ? (
          <span className="w-4 h-4 border border-current border-t-transparent rounded-full animate-spin inline-block" />
        ) : (
          <Icon size={16} strokeWidth={1.5} />
        )}
      </span>
      <span>
        <span className="block font-mono text-xs font-bold uppercase tracking-wider" style={{ color: "inherit" }}>
          {label}
        </span>
        {description && (
          <span className="block font-mono text-[10px] mt-0.5 text-zinc-400" style={{ color: "var(--text-dim)", textTransform: "none" }}>
            {description}
          </span>
        )}
      </span>
    </button>
  );
}

// ─── Main Options Modal Panel ────────────────────────────────────────────────
export function OptionsPanel({ open, onClose, onAboutClick, onTermsClick }: Props) {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const { state, dispatch } = useAI();
  const { locale, setLocale, t } = useLanguage();
  const { models, manifest } = useDownload();
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);

  // Sound Mute State
  const [soundMuted, setSoundMutedState] = useState(false);
  useEffect(() => {
    if (open) setSoundMutedState(isSoundMuted());
  }, [open]);

  // PDF Download Path State (Item 1)
  const [pdfDownloadPath, setPdfDownloadPath] = useState("~/Downloads/MolDesign_PDFs");
  const [isEditingPdfPath, setIsEditingPdfPath] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedPath = getUserItem("moldesign_pdf_download_path", user?.user_id);
      setPdfDownloadPath("~/Downloads/MolDesign_PDFs");
      if (savedPath) setPdfDownloadPath(savedPath);
    }
  }, [user?.user_id]);

  const handleSavePdfPath = (newPath: string) => {
    setPdfDownloadPath(newPath);
    if (typeof window !== "undefined") {
      if (user) setUserItem("moldesign_pdf_download_path", newPath, user.user_id);
    }
  };

  // Backup & Reset State
  const [exportLoading, setExportLoading] = useState(false);
  const [exportDone, setExportDone] = useState(false);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetDone, setResetDone] = useState(false);

  useEffect(() => {
    if (!open) {
      setExportDone(false);
      setResetConfirm(false);
      setResetDone(false);
    }
  }, [open]);

  // Close on Escape or Outside Click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
    };
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", keyHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", keyHandler);
    };
  }, [open, onClose]);

  const handleToggleSound = useCallback(() => {
    const nextMuted = !soundMuted;
    setSoundMuted(nextMuted);
    setSoundMutedState(nextMuted);
    if (!nextMuted) playSound("chime");
  }, [soundMuted]);

  const handleExport = useCallback(async () => {
    setExportLoading(true);
    setExportDone(false);
    try {
      const [moldex, history, stats] = await Promise.allSettled([
        getMoldex(),
        getEvaluationHistory(1, 500),
        getUserStats(),
      ]);

      const backup = {
        version: "1.0.0",
        exported_at: new Date().toISOString(),
        application: "MolDesign",
        data: {
          moldex: moldex.status === "fulfilled" ? moldex.value : null,
          history: history.status === "fulfilled" ? history.value : null,
          stats: stats.status === "fulfilled" ? stats.value : null,
        },
      };

      const blob = new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const ts = new Date().toISOString().split("T")[0];
      a.href = url;
      a.download = `moldesign_backup_${ts}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setExportDone(true);
      playSound("bloom");
    } catch {
      // ignore
    } finally {
      setExportLoading(false);
    }
  }, []);

  const handleResetRequest = useCallback(() => {
    setResetConfirm(true);
    playSound("whisper");
  }, []);

  const handleResetConfirm = useCallback(async () => {
    setResetLoading(true);
    try {
      await new Promise((r) => setTimeout(r, 800));
      localStorage.removeItem("moldesign_auth");
      setResetDone(true);
      setResetConfirm(false);
    } finally {
      setResetLoading(false);
    }
  }, []);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[500] flex items-start justify-center bg-black/60 backdrop-blur-md" style={{ paddingTop: "calc(57px + 12px)", paddingBottom: "12px", paddingLeft: "16px", paddingRight: "16px" }}>
          <motion.div
            ref={panelRef}
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-[560px] flex flex-col shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8)] border overflow-hidden rounded-2xl"
            style={{ maxHeight: "calc(100vh - 57px - 24px)", backgroundColor: "var(--bg-alt)", borderColor: "var(--border)" }}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b shrink-0" style={{ borderColor: "var(--border)" }}>
              <span className="font-mono text-sm font-bold uppercase tracking-widest" style={{ color: "var(--text)" }}>
                {t("options")}
              </span>
              <button
                onClick={onClose}
                aria-label={t("close")}
                className="p-1 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
                style={{ color: "var(--text-muted)" }}
              >
                <X size={18} strokeWidth={1.5} />
              </button>
            </div>

            {/* Scrollable Modal Content Body */}
            <div className="p-6 space-y-7 overflow-y-auto flex-1">

              {/* ── 1. Apariencia & Modo ──────────────────────────────── */}
              <section>
                <SectionLabel icon={Moon} label={t("opt_appearance")} />
                <div className="ml-6 mt-3 max-w-xs">
                  {/* Theme Switcher */}
                  <div className="flex items-center gap-1 p-1 w-full rounded-lg" style={{ backgroundColor: "var(--bg)", border: "1px solid var(--border)" }}>
                    <button
                      type="button"
                      onClick={() => setTheme("dark")}
                      className={`flex-1 flex items-center justify-center gap-2 h-9 px-4 text-xs font-bold font-mono uppercase tracking-wider rounded transition-all cursor-pointer border-none`}
                      style={{
                        backgroundColor: theme === "dark" ? "var(--text)" : "transparent",
                        color: theme === "dark" ? "var(--bg)" : "var(--text-muted)",
                      }}
                    >
                      <Moon size={14} />
                      {t("opt_theme_dark")}
                    </button>
                    <button
                      type="button"
                      onClick={() => setTheme("light")}
                      className={`flex-1 flex items-center justify-center gap-2 h-9 px-4 text-xs font-bold font-mono uppercase tracking-wider rounded transition-all cursor-pointer border-none`}
                      style={{
                        backgroundColor: theme === "light" ? "var(--text)" : "transparent",
                        color: theme === "light" ? "var(--bg)" : "var(--text-muted)",
                      }}
                    >
                      <Sun size={14} />
                      {t("opt_theme_light")}
                    </button>
                  </div>
                </div>
              </section>

              {/* ── 2. Idioma / Language (Top-Level Rank) ──────────── */}
              <section className="border-t pt-5" style={{ borderColor: "var(--border)" }}>
                <SectionLabel icon={Globe} label="Idioma / Language" />
                <div className="ml-6 mt-3">
                  <div className="relative w-full">
                    <select
                      value={locale}
                      onChange={(e) => {
                        // `e.target.value` es `string`. En vez de afirmar que es
                        // un `Locale`, se busca en la lista que llena el propio
                        // select: si algún día se añade una opción con un código
                        // que no está en `Locale`, esto no la aplica en silencio.
                        const elegido = LANGUAGES.find((l) => l.code === e.target.value);
                        if (!elegido) return;
                        setLocale(elegido.code);
                        playSound("toggle");
                      }}
                      className="w-full h-10 px-4 font-mono text-xs font-bold tracking-wider cursor-pointer outline-none transition-colors rounded-lg"
                      style={{
                        backgroundColor: "var(--bg)",
                        border: "1px solid var(--border)",
                        color: "var(--text)",
                        appearance: "none",
                        paddingRight: "36px",
                      }}
                    >
                      {LANGUAGES.map((lang) => (
                        <option key={lang.code} value={lang.code} style={{ backgroundColor: "var(--bg-alt)", color: "var(--text)" }}>
                          {lang.flag} {lang.name}
                        </option>
                      ))}
                    </select>
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-muted" style={{ fontSize: 10 }}>
                      ▼
                    </div>
                  </div>
                </div>
              </section>

              {/* ── 3. Directorio de Descarga PDF ──────────────────── */}
              <section className="border-t pt-5" style={{ borderColor: "var(--border)" }}>
                <SectionLabel icon={Folder} label={t("z_ruta_reportes")} />
                <div className="ml-6 mt-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={pdfDownloadPath}
                      onChange={(e) => handleSavePdfPath(e.target.value)}
                      className="flex-1 h-10 px-4 font-mono text-xs rounded-lg outline-none transition-colors"
                      style={{
                        backgroundColor: "var(--bg)",
                        border: "1px solid var(--border)",
                        color: "var(--text)",
                      }}
                      placeholder="~/Downloads/MolDesign_PDFs"
                    />
                    <button
                      onClick={() => handleSavePdfPath("~/Downloads/MolDesign_PDFs")}
                      className="px-3 h-10 font-mono text-xs font-bold uppercase tracking-wider rounded-lg transition-colors cursor-pointer flex items-center gap-1.5"
                      style={{
                        backgroundColor: "var(--bg)",
                        border: "1px solid var(--border)",
                        color: "var(--text-muted)",
                      }}
                      title="Restablecer ruta predeterminada"
                    >
                      <RefreshCw size={12} />
                      Default
                    </button>
                  </div>
                  <p className="font-mono text-[10px] text-zinc-400">
                    {t("pn_ruta_pdf_detalle")}
                  </p>
                </div>
              </section>

              {/* ── 4. Sonidos de Efectos ───────────────────────────── */}
              <section className="border-t pt-5" style={{ borderColor: "var(--border)" }}>
                <SectionLabel icon={soundMuted ? VolumeX : Volume2} label={t("opt_sounds")} />
                <div className="ml-6 mt-3">
                  <button
                    onClick={handleToggleSound}
                    className="flex items-center gap-3 px-4 py-2.5 w-full font-mono text-xs font-bold uppercase tracking-wider transition-colors rounded-lg"
                    style={{
                      backgroundColor: soundMuted ? "var(--bg)" : "var(--text)",
                      color: soundMuted ? "var(--text-muted)" : "var(--bg)",
                      border: "1px solid var(--border)",
                      cursor: "pointer",
                    }}
                  >
                    {soundMuted ? <VolumeX size={14} strokeWidth={1.5} /> : <Volume2 size={14} strokeWidth={1.5} />}
                    {soundMuted ? t("opt_sounds_muted") : t("opt_sounds_active")}
                    <span
                      className="ml-auto font-mono text-[9px] uppercase tracking-wider"
                      style={{ color: soundMuted ? "var(--text-dim)" : "var(--bg)", opacity: 0.7 }}
                    >
                      {soundMuted ? t("opt_sounds_activate") : t("opt_sounds_silence")}
                    </span>
                  </button>
                </div>
              </section>

              {/* ── 5. Intérprete IA ───────────────────────────────── */}
              <section className="border-t pt-5" style={{ borderColor: "var(--border)" }}>
                <SectionLabel icon={Bot} label={t("opt_ai")} />
                <div className="ml-6 mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    onClick={() => {
                      dispatch({ type: "SET_SETTINGS_OPEN", open: true });
                      onClose();
                    }}
                    className="flex items-center gap-2 px-4 py-2.5 text-xs font-mono font-bold uppercase tracking-wider transition-colors rounded-lg"
                    style={{
                      backgroundColor: "var(--bg)",
                      border: "1px solid var(--border)",
                      color: "var(--text)",
                      cursor: "pointer",
                    }}
                  >
                    <span style={{ flex: 1, textAlign: "left" }}>{t("opt_ai_config")}</span>
                    <span
                      style={{
                        fontSize: "10px",
                        color: state.activeProviderId ? "#22C55E" : "var(--text-muted)",
                      }}
                    >
                      {state.activeProviderId ? "OK" : "N/A"}
                    </span>
                  </button>

                  <button
                    onClick={() => {
                      dispatch({ type: "SET_PANEL_OPEN", open: !state.isPanelOpen });
                      if (!state.isPanelOpen) dispatch({ type: "SET_ACTIVE_PROVIDER", id: "local" });
                      onClose();
                    }}
                    className="flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-mono font-bold uppercase tracking-wider transition-colors rounded-lg"
                    style={{
                      backgroundColor: state.isPanelOpen ? "var(--text)" : "transparent",
                      border: "1px solid var(--border)",
                      color: state.isPanelOpen ? "var(--bg)" : "var(--text-muted)",
                      cursor: "pointer",
                    }}
                  >
                    <Bot size={13} strokeWidth={1.5} />
                    {state.isPanelOpen ? t("opt_ai_chat_close") : t("opt_ai_chat_open")}
                  </button>
                </div>
              </section>

              {/* ── 6. Módulos & Launcher ──────────────────────────── */}
              <section className="border-t pt-5" style={{ borderColor: "var(--border)" }}>
                <SectionLabel icon={HardDrive} label={t("opt_modules") || t("auto_a4e3d3490896")} />
                <div className="ml-6 mt-3 space-y-2">
                  {manifest.map((entry) => {
                    const status = models[entry.id] || "missing";
                    return (
                      <div
                        key={entry.id}
                        className="flex items-center gap-2 px-3 py-2 font-mono text-xs rounded-lg transition-colors"
                        style={{
                          backgroundColor: "var(--bg)",
                          border: "1px solid var(--border)",
                          color: "var(--text)",
                        }}
                      >
                        <span style={{
                          width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                          backgroundColor: status === "ready" ? "#22c55e" : status === "downloading" || status === "extracting" ? "#f59e0b" : status === "error" ? "#ef4444" : "var(--text-dim)",
                        }} />
                        <span style={{ flex: 1, fontWeight: 700, letterSpacing: "0.03em" }}>
                          {entry.name}
                        </span>
                        <span style={{
                          color: status === "ready" ? "#22c55e" : status === "error" ? "#ef4444" : "var(--text-dim)",
                          textTransform: "uppercase",
                          fontSize: "10px",
                          fontWeight: 700
                        }}>
                          {status === "ready" ? "Listo" : status === "downloading" ? "Descargando" : status === "extracting" ? "Extrayendo" : status === "error" ? "Error" : "Pendiente"}
                        </span>
                      </div>
                    );
                  })}
                  <button
                    onClick={() => { router.push("/launcher"); onClose(); }}
                    className="flex items-center justify-center gap-2 w-full px-4 py-2.5 text-xs font-mono uppercase tracking-wider font-bold transition-colors rounded-lg mt-1"
                    style={{
                      backgroundColor: "var(--text)",
                      color: "var(--bg)",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    <HardDrive size={13} strokeWidth={1.5} />
                    {t("opt_manage_modules") || t("auto_65299f4a07a8")}
                  </button>
                </div>
              </section>

              {/* ── 7. Datos y Respaldo ────────────────────────────── */}
              <section className="border-t pt-5" style={{ borderColor: "var(--border)" }}>
                <SectionLabel icon={Download} label={t("opt_data")} />
                <div className="ml-6 mt-3 space-y-3">
                  <ActionRow
                    icon={exportDone ? CheckCircle : Download}
                    label={exportDone ? t("opt_data_export_success") : t("opt_data_export")}
                    description={t("opt_data_export_desc")}
                    onClick={handleExport}
                    loading={exportLoading}
                  />

                  {!resetConfirm && !resetDone && (
                    <ActionRow
                      icon={Trash2}
                      label={t("opt_data_reset")}
                      description={t("opt_data_reset_desc")}
                      onClick={handleResetRequest}
                      variant="danger"
                    />
                  )}

                  {resetConfirm && !resetDone && (
                    <div
                      className="px-4 py-3 space-y-3 rounded-lg"
                      style={{ border: "1px solid rgba(239,68,68,0.3)", backgroundColor: "rgba(239,68,68,0.04)" }}
                    >
                      <div className="flex items-start gap-2">
                        <AlertTriangle size={15} strokeWidth={1.5} style={{ color: "#ef4444", flexShrink: 0, marginTop: 1 }} />
                        <p className="font-mono text-xs" style={{ color: "var(--text-muted)", lineHeight: 1.6 }}>
                          {t("opt_data_reset_warning")}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={handleResetConfirm}
                          disabled={resetLoading}
                          className="px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider rounded transition-colors"
                          style={{ backgroundColor: "#ef4444", color: "#fff", border: "none", cursor: "pointer" }}
                        >
                          {resetLoading ? "Limpiando..." : t("auto_9340a078aa31")}
                        </button>
                        <button
                          onClick={() => setResetConfirm(false)}
                          className="px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider rounded transition-colors"
                          style={{ backgroundColor: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", cursor: "pointer" }}
                        >
                          {t("c_cancelar")}
                        </button>
                      </div>
                    </div>
                  )}

                  {resetDone && (
                    <div className="px-4 py-3 font-mono text-xs text-emerald-400 border border-emerald-500/30 bg-emerald-500/10 rounded-lg">
                      {t("z_datos_eliminados")}
                    </div>
                  )}
                </div>
              </section>

            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
