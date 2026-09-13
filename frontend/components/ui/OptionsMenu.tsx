"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  Brain,
  Check,
  ChevronRight,
  Database,
  Download,
  FileJson,
  FileText,
  Globe,
  Info,
  LifeBuoy,
  Moon,
  Settings,
  Shield,
  Sun,
  Trash2,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { LANGUAGES, useLanguage } from "../../context/LanguageContext";
import { SupportContent } from "../SupportPanel";
import { AboutModal } from "./AboutModal";
import { CloudAISettingsModal } from "./CloudAISettingsModal";
import { LegalModal } from "./LegalModal";
import { LocalAISettingsModal } from "./LocalAISettingsModal";
import { useAuth } from "../../lib/auth";
import { getUserItem, removeUserItem, setUserItem } from "../../lib/userStorage";
import { PRODUCT } from "@/lib/softwareCatalog";

interface OptionsMenuProps {
  isOpen: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLButtonElement | null>;
}

type PanelView = "options" | "support";
type ExportFormat = "json" | "csv";

const sectionLabelClass =
  "px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]";
const optionButtonClass =
  "flex min-h-11 w-full items-center justify-between rounded-[10px] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5 text-left transition-colors hover:border-[var(--accent)] hover:bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] active:bg-[var(--bg-secondary)]";
const optionTextClass = "text-sm font-medium text-[var(--text)]";

function csvCell(value: unknown): string {
  const content = value === null || value === undefined ? "" : String(value);
  return `"${content.replace(/"/g, '""')}"`;
}

export function OptionsMenu({ isOpen, onClose, triggerRef }: OptionsMenuProps) {

  const router = useRouter();
  const { user } = useAuth();
  const panelRef = useRef<HTMLElement>(null);
  const firstControlRef = useRef<HTMLButtonElement>(null);
  const [mounted, setMounted] = useState(false);
  const [activeView, setActiveView] = useState<PanelView>("options");

  const { theme, toggleTheme } = useTheme();
  const { locale, setLocale, currentLanguage } = useLanguage();
  const [soundsMuted, setSoundsMuted] = useState(true);
  const [soundsVolume, setSoundsVolume] = useState(0.5);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [legalOpen, setLegalOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [localAIOpen, setLocalAIOpen] = useState(false);
  const [cloudAIOpen, setCloudAIOpen] = useState(false);
  const childModalOpen = legalOpen || aboutOpen || localAIOpen || cloudAIOpen;

  useEffect(() => {
    setMounted(true);
    const muted = getUserItem("moldesign_sounds_muted", user?.user_id);
    const volume = getUserItem("moldesign_sounds_volume", user?.user_id);
    setSoundsMuted(true);
    setSoundsVolume(0.5);
    if (muted !== null) setSoundsMuted(muted === "true");
    if (volume !== null) setSoundsVolume(Number.parseFloat(volume));
  }, [user?.user_id]);

  useEffect(() => {
    if (isOpen) return;
    setLegalOpen(false);
    setAboutOpen(false);
    setLocalAIOpen(false);
    setCloudAIOpen(false);
    setShowLangPicker(false);
    setActiveView("options");
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    return () => triggerRef?.current?.focus();
  }, [isOpen, triggerRef]);

  useEffect(() => {
    if (!isOpen || childModalOpen) return;
    const frame = window.requestAnimationFrame(() => firstControlRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [activeView, childModalOpen, isOpen]);

  useEffect(() => {
    if (!isOpen || childModalOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [childModalOpen, isOpen, onClose]);

  const toggleSounds = () => {
    const next = !soundsMuted;
    setSoundsMuted(next);
    if (user) setUserItem("moldesign_sounds_muted", String(next), user.user_id);
  };

  const handleVolume = (value: number) => {
    setSoundsVolume(value);
    if (user) setUserItem("moldesign_sounds_volume", String(value), user.user_id);
  };

  const exportData = (format: ExportFormat) => {
    try {
      const parsed: unknown = JSON.parse(getUserItem("moldesign_moldex", user?.user_id) || "[]");
      const data = Array.isArray(parsed) ? (parsed as Record<string, unknown>[]) : [];
      const columns = [
        "id",
        "smiles",
        "name",
        "target_pdb_id",
        "total_score",
        "affinity_kcal",
        "evaluated_at",
      ];
      const content =
        format === "csv"
          ? [columns.join(","), ...data.map((row) => columns.map((key) => csvCell(row[key])).join(","))].join("\n")
          : JSON.stringify(data, null, 2);
      const mimeType = format === "csv" ? "text/csv;charset=utf-8" : "application/json;charset=utf-8";
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `moldesign_bioteca.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      window.alert("No se pudieron exportar los datos locales.");
    }
  };

  const deleteLegacyData = () => {
    if (!window.confirm("¿Limpiar las preferencias y el historial local heredado? Los casos de estudio no se eliminarán.")) {
      return;
    }
    removeUserItem("moldesign_moldex", user?.user_id);
    removeUserItem("moldesign_custom_targets", user?.user_id);
    removeUserItem("moldesign_evaluation_history", user?.user_id);
  };

  if (!mounted) return null;

  const portal = createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-x-0 bottom-0 top-14 z-[150] font-sans">
          <motion.div
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={onClose}
            className="absolute inset-0 cursor-default bg-black/30 backdrop-blur-[2px]"
          />
          <motion.aside
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="options-panel-title"
            initial={{ x: -400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -400, opacity: 0 }}
            transition={{ type: "spring", damping: 26, stiffness: 300 }}
            className="absolute inset-y-0 left-0 flex w-[380px] max-w-[92vw] flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--bg-secondary)] shadow-[8px_0_40px_rgba(0,0,0,0.3)]"
          >
            <header className="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <div className="flex min-w-0 items-center gap-2.5">
                {activeView === "support" ? (
                  <button
                    ref={firstControlRef}
                    type="button"
                    onClick={() => setActiveView("options")}
                    className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-alt)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] active:bg-[var(--bg)]"
                    aria-label="Volver a Opciones"
                  >
                    <ArrowLeft size={17} aria-hidden="true" />
                  </button>
                ) : (
                  <Settings size={20} className="shrink-0 text-[var(--accent)]" aria-hidden="true" />
                )}
                <h2 id="options-panel-title" className="truncate text-base font-semibold text-[var(--text)]">
                  {activeView === "support" ? "Soporte" : "Opciones"}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-alt)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] active:bg-[var(--bg)]"
                aria-label="Cerrar opciones"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain">
              {activeView === "support" ? (
                <SupportContent />
              ) : (
                <div className="space-y-1 p-4">
                  <section>
                    <h3 className={sectionLabelClass}>Apariencia</h3>
                    <button ref={firstControlRef} type="button" onClick={toggleTheme} className={optionButtonClass}>
                      <span className="flex items-center gap-3">
                        {theme === "dark" ? (
                          <Moon size={16} className="text-[var(--accent)]" aria-hidden="true" />
                        ) : (
                          <Sun size={16} className="text-amber-400" aria-hidden="true" />
                        )}
                        <span className={optionTextClass}>Tema {theme === "dark" ? "oscuro" : "claro"}</span>
                      </span>
                      <span
                        aria-hidden="true"
                        className={`flex h-5 w-9 items-center rounded-full border px-0.5 transition-colors ${
                          theme === "dark"
                            ? "justify-end border-purple-500/30 bg-purple-500/20"
                            : "justify-start border-amber-500/30 bg-amber-500/20"
                        }`}
                      >
                        <span className={`h-3.5 w-3.5 rounded-full ${theme === "dark" ? "bg-purple-400" : "bg-amber-400"}`} />
                      </span>
                    </button>
                  </section>

                  <section>
                    <h3 className={sectionLabelClass}>Idioma</h3>
                    <button
                      type="button"
                      aria-expanded={showLangPicker}
                      onClick={() => setShowLangPicker((current) => !current)}
                      className={optionButtonClass}
                    >
                      <span className="flex items-center gap-3">
                        <Globe size={16} className="text-[var(--accent)]" aria-hidden="true" />
                        <span className={optionTextClass}>
                          {currentLanguage?.flag} {currentLanguage?.name}
                        </span>
                      </span>
                      <ChevronRight
                        size={14}
                        className={`text-[var(--text-dim)] transition-transform ${showLangPicker ? "rotate-90" : ""}`}
                        aria-hidden="true"
                      />
                    </button>
                    {showLangPicker && (
                      <div className="custom-scrollbar mt-1 grid max-h-[180px] grid-cols-2 gap-1 overflow-y-auto px-1">
                        {LANGUAGES.map((language) => (
                          <button
                            key={language.code}
                            type="button"
                            onClick={() => {
                              setLocale(language.code);
                              setShowLangPicker(false);
                            }}
                            className={`flex min-h-10 items-center gap-2 rounded-lg border px-2.5 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] ${
                              locale === language.code
                                ? "border-purple-500/30 bg-purple-500/10 text-purple-300"
                                : "border-[var(--border)] bg-[var(--bg)] text-[var(--text-secondary)] hover:bg-[var(--bg-alt)] hover:text-[var(--text)]"
                            }`}
                          >
                            <span aria-hidden="true">{language.flag}</span>
                            <span className="truncate">{language.name}</span>
                            {locale === language.code && <Check size={11} className="ml-auto shrink-0" aria-hidden="true" />}
                          </button>
                        ))}
                      </div>
                    )}
                  </section>

                  <section>
                    <h3 className={sectionLabelClass}>Sonidos</h3>
                    <div className="space-y-2 rounded-[10px] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5">
                      <button type="button" onClick={toggleSounds} className="flex min-h-6 w-full items-center justify-between focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]">
                        <span className="flex items-center gap-3">
                          {soundsMuted ? (
                            <VolumeX size={16} className="text-red-400" aria-hidden="true" />
                          ) : (
                            <Volume2 size={16} className="text-[var(--accent)]" aria-hidden="true" />
                          )}
                          <span className={optionTextClass}>Sonidos de interfaz</span>
                        </span>
                        <span
                          aria-hidden="true"
                          className={`flex h-5 w-9 items-center rounded-full border px-0.5 transition-colors ${
                            soundsMuted
                              ? "justify-start border-[var(--border)] bg-[var(--bg-alt)]"
                              : "justify-end border-purple-500/30 bg-purple-500/20"
                          }`}
                        >
                          <span className={`h-3.5 w-3.5 rounded-full ${soundsMuted ? "bg-[var(--text-dim)]" : "bg-purple-400"}`} />
                        </span>
                      </button>
                      {!soundsMuted && (
                        <label className="flex items-center gap-3">
                          <span className="w-8 text-right font-mono text-[11px] text-[var(--text-dim)]">
                            {Math.round(soundsVolume * 100)}%
                          </span>
                          <span className="sr-only">Volumen de los sonidos de interfaz</span>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={soundsVolume}
                            onChange={(event) => handleVolume(Number.parseFloat(event.target.value))}
                            className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]"
                            style={{ accentColor: "#a78bfa" }}
                          />
                        </label>
                      )}
                    </div>
                  </section>

                  <section>
                    <h3 className={sectionLabelClass}>Intérprete IA</h3>
                    <div className="space-y-1">
                      <button type="button" onClick={() => setLocalAIOpen(true)} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <Brain size={16} className="text-emerald-400" aria-hidden="true" />
                          <span className={optionTextClass}>Intérprete IA local</span>
                        </span>
                        <span className="text-[11px] text-[var(--text-dim)]">Configurar</span>
                      </button>
                      <button type="button" onClick={() => setCloudAIOpen(true)} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <Database size={16} className="text-sky-400" aria-hidden="true" />
                          <span className={optionTextClass}>Intérprete IA online</span>
                        </span>
                        <span className="text-[11px] text-[var(--text-dim)]">Cloud / API</span>
                      </button>
                    </div>
                  </section>

                  <section>
                    <h3 className={sectionLabelClass}>Modelos y motores</h3>
                    <div className="space-y-1">
                      <button
                        type="button"
                        onClick={() => { onClose(); router.push("/launcher"); }}
                        className={optionButtonClass}
                      >
                        <span className="flex items-center gap-3">
                          <Download size={16} className="text-[var(--accent)]" aria-hidden="true" />
                          <span className={optionTextClass}>Gestionar descargas</span>
                        </span>
                        <ChevronRight size={14} className="text-[var(--text-dim)]" aria-hidden="true" />
                      </button>
                    </div>
                  </section>


                  <section>
                    <h3 className={sectionLabelClass}>Datos y respaldo</h3>
                    <div className="space-y-1">
                      <button type="button" onClick={() => exportData("json")} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <FileJson size={16} className="text-[var(--accent)]" aria-hidden="true" />
                          <span className={optionTextClass}>Exportar bioteca como JSON</span>
                        </span>
                        <Download size={13} className="text-[var(--text-dim)]" aria-hidden="true" />
                      </button>
                      <button type="button" onClick={() => exportData("csv")} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <FileText size={16} className="text-[var(--accent)]" aria-hidden="true" />
                          <span className={optionTextClass}>Exportar bioteca como CSV</span>
                        </span>
                        <Download size={13} className="text-[var(--text-dim)]" aria-hidden="true" />
                      </button>
                      <button type="button" onClick={deleteLegacyData} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <Trash2 size={16} className="text-red-400" aria-hidden="true" />
                          <span className="text-sm font-medium text-red-400">Limpiar datos locales heredados</span>
                        </span>
                      </button>
                    </div>
                  </section>

                  <section>
                    <h3 className={sectionLabelClass}>Legal e información</h3>
                    <div className="space-y-1">
                      <button type="button" onClick={() => setLegalOpen(true)} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <Shield size={16} className="text-[var(--accent)]" aria-hidden="true" />
                          <span className={optionTextClass}>Legal, privacidad y licencias</span>
                        </span>
                      </button>
                      <button type="button" onClick={() => setAboutOpen(true)} className={optionButtonClass}>
                        <span className="flex items-center gap-3">
                          <Info size={16} className="text-[var(--accent)]" aria-hidden="true" />
                          <span className={optionTextClass}>Acerca de MolDesign</span>
                        </span>
                        <span className="font-mono text-[11px] text-[var(--text-dim)]">v{PRODUCT.version}</span>
                      </button>
                    </div>
                  </section>

                  <section className="border-t border-[var(--border)] pt-3">
                    <button type="button" onClick={() => setActiveView("support")} className={optionButtonClass}>
                      <span className="flex items-center gap-3">
                        <LifeBuoy size={16} className="text-[var(--accent)]" aria-hidden="true" />
                        <span className={optionTextClass}>Soporte y ayuda</span>
                      </span>
                      <ChevronRight size={14} className="text-[var(--text-dim)]" aria-hidden="true" />
                    </button>
                  </section>
                </div>
              )}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );

  return (
    <>
      {portal}
      <LegalModal isOpen={legalOpen} onClose={() => setLegalOpen(false)} />
      <AboutModal isOpen={aboutOpen} onClose={() => setAboutOpen(false)} onRequestLegal={() => { setAboutOpen(false); setLegalOpen(true); }} />
      <LocalAISettingsModal isOpen={localAIOpen} onClose={() => setLocalAIOpen(false)} />
      <CloudAISettingsModal isOpen={cloudAIOpen} onClose={() => setCloudAIOpen(false)} />
    </>
  );
}
