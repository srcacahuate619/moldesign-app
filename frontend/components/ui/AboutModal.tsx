"use client";
import { useLanguage } from "@/context/LanguageContext";
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 */

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { animateElements, cancelAnimations } from "@/lib/webAnimation";
import { createPortal } from "react-dom";
import { BadgeInfo, BookOpen, BrainCircuit, ExternalLink as IconoEnlaceExterno, FlaskConical, Info, Scale, Server, Sparkles, X, Zap } from "lucide-react";

import { useScrollLock } from "@/hooks/useScrollLock";
import { PRODUCT, SOFTWARE_SECTIONS, type SoftwareCard, type SoftwareSection } from "@/lib/softwareCatalog";

import { ExternalLink } from "@/components/ui/ExternalLink";
interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRequestLegal?: () => void;
}

const SECTION_ICONS: Record<SoftwareSection["id"], ReactNode> = {
  chemistry: <FlaskConical size={14} strokeWidth={1.5} aria-hidden="true" />,
  scoring: <Zap size={14} strokeWidth={1.5} aria-hidden="true" />,
  ai: <BrainCircuit size={14} strokeWidth={1.5} aria-hidden="true" />,
  platform: <Server size={14} strokeWidth={1.5} aria-hidden="true" />,
  sources: <BookOpen size={14} strokeWidth={1.5} aria-hidden="true" />,
};

const AVAILABILITY_STYLES: Record<SoftwareCard["availability"], string> = {
  Incluido: "border-emerald-500/25 text-emerald-300/80",
  Opcional: "border-sky-500/25 text-sky-300/80",
  "Servicio externo": "border-amber-500/25 text-amber-300/80",
  "Método adaptado": "border-purple-400/25 text-purple-300/80",
};

const SECTION_TRANSLATION_KEYS: Record<SoftwareSection["id"], string> = {
  chemistry: "pn_about_section_chemistry",
  scoring: "pn_about_section_scoring",
  ai: "pn_about_section_ai",
  platform: "pn_about_section_platform",
  sources: "pn_about_section_sources",
};

const AVAILABILITY_TRANSLATION_KEYS: Record<SoftwareCard["availability"], string> = {
  Incluido: "pn_about_availability_included",
  Opcional: "pn_about_availability_optional",
  "Servicio externo": "pn_about_availability_external",
  "Método adaptado": "pn_about_availability_adapted",
};

const KIND_TRANSLATION_KEYS: Record<SoftwareCard["kind"], string> = {
  Tercero: "pn_about_kind_third_party",
  MolDesign: "pn_about_kind_moldesign",
  "Fuente científica": "pn_about_kind_scientific_source",
};

export const CARD_TRANSLATION_KEYS: Record<
  string,
  { name?: string; version?: string; description: string; credit?: string }
> = {
  "AutoDock Vina": { description: "pn_about_card_vina_description" },
  Meeko: { description: "pn_about_card_meeko_description" },
  RDKit: { description: "pn_about_card_rdkit_description" },
  "Dimorphite-DL": { description: "pn_about_card_dimorphite_description" },
  gemmi: { description: "pn_about_card_gemmi_description" },
  "Open Babel": {
    description: "pn_about_card_open_babel_description",
    credit: "pn_about_card_open_babel_credit",
  },
  PoseBusters: { description: "pn_about_card_posebusters_description" },
  "OpenMM + PDBFixer": { description: "pn_about_card_openmm_description" },
  "ProLIF + MDAnalysis": { description: "pn_about_card_prolif_description" },
  "xTB (GFN2-xTB)": { description: "pn_about_card_xtb_description" },
  "XGBoost + SHAP": { description: "pn_about_card_xgboost_description" },
  "ADMET-AI": { description: "pn_about_card_admet_description" },
  TabPFN: { description: "pn_about_card_tabpfn_description" },
  RTMScore: {
    version: "pn_about_card_rtmscore_version",
    description: "pn_about_card_rtmscore_description",
  },
  "Modelos MolDesign": {
    name: "pn_about_card_moldesign_models_name",
    version: "pn_about_card_moldesign_models_version",
    description: "pn_about_card_moldesign_models_description",
  },
  ESMFold: { version: "pn_about_card_esmfold_version", description: "pn_about_card_esmfold_description" },
  "llama.cpp": { description: "pn_about_card_llama_description" },
  "Qwen2.5-1.5B-Instruct": { description: "pn_about_card_qwen_description" },
  "Anthropic SDK": { description: "pn_about_card_anthropic_description" },
  Tauri: { description: "pn_about_card_tauri_description" },
  "Next.js + React": { description: "pn_about_card_next_react_description" },
  "FastAPI + Uvicorn": { description: "pn_about_card_fastapi_description" },
  "3Dmol.js + Mol*": { description: "pn_about_card_3dmol_description" },
  Ketcher: { description: "pn_about_card_ketcher_description" },
  "Solana Web3.js": { description: "pn_about_card_solana_description" },
  ReportLab: { description: "pn_about_card_reportlab_description" },
  "Motor Molcy": { name: "pn_about_card_molcy_name", description: "pn_about_card_molcy_description" },
  Blender: { description: "pn_about_card_blender_description" },
  "Molecular Nodes": {
    version: "pn_about_card_molecular_nodes_version",
    description: "pn_about_card_molecular_nodes_description",
  },
  "Microsoft Visual C++ Runtime": { description: "pn_about_card_vcruntime_description" },
  "RCSB Protein Data Bank / wwPDB": {
    version: "pn_about_card_rcsb_version",
    description: "pn_about_card_rcsb_description",
    credit: "pn_about_card_rcsb_credit",
  },
  UniProtKB: {
    description: "pn_about_card_uniprot_description",
    credit: "pn_about_card_uniprot_credit",
  },
  "Publicaciones de métodos": {
    name: "pn_about_card_methods_name",
    version: "pn_about_card_methods_version",
    description: "pn_about_card_methods_description",
    credit: "pn_about_card_methods_credit",
  },
  MolTalk: {
    description: "pn_about_card_moltalk_description",
    credit: "pn_about_card_moltalk_credit",
  },
  "Catálogo MolDesign": {
    name: "pn_about_card_catalog_name",
    version: "pn_about_card_catalog_version",
    description: "pn_about_card_catalog_description",
    credit: "pn_about_card_catalog_credit",
  },
};

function SoftwareCardView({ card }: { card: SoftwareCard }) {
  const { t } = useLanguage();
  const translations = CARD_TRANSLATION_KEYS[card.name];
  return (
    <article className="flex min-w-0 flex-col gap-2 rounded-xl border border-white/[0.08] bg-white/[0.025] p-4 transition-colors hover:border-white/[0.16]">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words text-[13px] font-semibold leading-tight text-white/90">
            {translations?.name ? t(translations.name) : card.name}
          </h3>
          <p className="mt-1 font-mono text-[10px] text-purple-300/75">
            {translations?.version ? t(translations.version) : card.version}
          </p>
        </div>
        <span className={`shrink-0 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[9px] ${AVAILABILITY_STYLES[card.availability]}`}>
          {t(AVAILABILITY_TRANSLATION_KEYS[card.availability])}
        </span>
      </div>
      <p className="flex-1 text-[12px] leading-relaxed text-white/65">
        {t(translations?.description ?? card.description)}
      </p>
      <div className="mt-auto border-t border-white/[0.06] pt-2">
        <p className="text-[10px] font-medium text-white/50">{t(KIND_TRANSLATION_KEYS[card.kind])}</p>
        <p className="mt-0.5 text-[10px] leading-relaxed text-white/40">
          {t("auto_9546d6dbdeab")} {translations?.credit ? t(translations.credit) : card.credit}
        </p>
      </div>
    </article>
  );
}

export function AboutModal({ isOpen, onClose, onRequestLegal }: AboutModalProps) {
  const { t } = useLanguage();
  useScrollLock(isOpen);
  const backdropRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [mounted, setMounted] = useState(false);
  const [activeId, setActiveId] = useState<SoftwareSection["id"]>("chemistry");

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!isOpen || !panel || !backdrop) return;
    cancelAnimations(backdrop);
    cancelAnimations(panel);
    backdrop.style.opacity = "0";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(14px) scale(0.98)";
    animateElements(backdrop, [{ opacity: 0 }, { opacity: 1 }], { duration: 180, fill: "forwards", easing: "ease-out" });
    animateElements(panel, [
      { opacity: 0, transform: "translateY(14px) scale(0.98)" },
      { opacity: 1, transform: "translateY(0) scale(1)" },
    ], { duration: 240, fill: "forwards", easing: "cubic-bezier(0.16, 1, 0.3, 1)" });
    closeButtonRef.current?.focus();
  }, [isOpen]);

  const handleClose = () => {
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!panel || !backdrop) {
      onClose();
      return;
    }
    cancelAnimations(backdrop);
    cancelAnimations(panel);
    animateElements(backdrop, [{ opacity: 1 }, { opacity: 0 }], { duration: 150, fill: "forwards", easing: "ease-in" });
    animateElements(panel, [
      { opacity: 1, transform: "translateY(0) scale(1)" },
      { opacity: 0, transform: "translateY(8px) scale(0.98)" },
    ], { duration: 180, fill: "forwards", easing: "ease-in", onComplete: onClose });
  };

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const active = useMemo(
    () => SOFTWARE_SECTIONS.find((section) => section.id === activeId) ?? SOFTWARE_SECTIONS[0],
    [activeId],
  );

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-2 sm:p-4" role="presentation" onMouseDown={(event) => event.stopPropagation()}>
      <div ref={backdropRef} className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={handleClose} />
      <section
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="about-title"
        className="relative z-10 flex h-[92vh] max-h-[700px] w-full max-w-[920px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d0e12] shadow-2xl"
        style={{ opacity: 0 }}
      >
        <header className="flex shrink-0 items-center justify-between border-b border-white/[0.07] px-4 py-4 sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="rounded-lg border border-purple-500/25 bg-purple-500/[0.07] p-1.5">
              <Info size={15} strokeWidth={1.5} className="text-purple-300" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h2 id="about-title" className="truncate text-sm font-bold text-white/90">{t("opt_legal_about")} {PRODUCT.name}</h2>
              <p className="mt-0.5 font-mono text-[10px] text-white/45">{PRODUCT.edition} · v{PRODUCT.version}</p>
            </div>
          </div>
          <button ref={closeButtonRef} type="button" onClick={handleClose} aria-label={t("pn_cerrar_acerca")} className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-2 text-white/55 transition-colors hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400">
            <X size={15} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className="shrink-0 border-b border-white/[0.07] bg-[#0a0b0f] p-2 md:w-[220px] md:border-b-0 md:border-r md:p-3">
            <p className="px-2 pb-2 pt-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-white/50">{t("pn_como_construido")}</p>
            <nav aria-label={t("pn_areas_stack")} className="grid grid-cols-2 gap-1 sm:grid-cols-3 md:grid-cols-1">
              {SOFTWARE_SECTIONS.map((section) => {
                const isActive = section.id === activeId;
                return (
                  <button key={section.id} type="button" onClick={() => setActiveId(section.id)} aria-pressed={isActive} className={`flex min-w-0 items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-[11px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-purple-400 md:text-[12px] ${isActive ? "border-purple-500/25 bg-purple-500/10 text-purple-200" : "border-transparent text-white/60 hover:bg-white/[0.04] hover:text-white/85"}`}>
                    <span className={isActive ? "text-purple-300" : "text-white/40"}>{SECTION_ICONS[section.id]}</span>
                    <span className="min-w-0 truncate">{t(SECTION_TRANSLATION_KEYS[section.id])}</span>
                  </button>
                );
              })}
            </nav>
            <div className="mt-3 hidden rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 md:block">
              <div className="flex items-center gap-2 text-[11px] font-semibold text-white/75"><Sparkles size={13} className="text-purple-300" aria-hidden="true" /> {t("pn_transparency")}</div>
              <p className="mt-1.5 text-[10px] leading-relaxed text-white/50">{t("pn_acerca_intro")}</p>
            </div>
          </aside>

          <main className="flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/[0.06] px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <p className="truncate text-[12px] font-bold text-purple-200">
                  {t(SECTION_TRANSLATION_KEYS[active.id])}
                </p>
                <p className="mt-0.5 text-[10px] text-white/45">{t("pn_capacidades_desktop")}</p>
              </div>
              <span className="shrink-0 font-mono text-[10px] text-white/40">{t("pn_card_count", { count: active.cards.length })}</span>
            </div>
            <div className="flex-1 overflow-y-auto p-3 custom-scrollbar sm:p-4">
              <div className="grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-2">
                {active.cards.map((card) => <SoftwareCardView key={card.name} card={card} />)}
              </div>
            </div>
          </main>
        </div>

        <footer className="flex shrink-0 flex-col gap-2 border-t border-white/[0.06] bg-[#0a0b0f] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex items-center gap-2 text-[10px] text-white/50"><BadgeInfo size={12} aria-hidden="true" /><span>{PRODUCT.license} {t("auto_d524488efd51")}</span></div>
          <div className="flex items-center gap-3">
            {onRequestLegal && <button type="button" onClick={onRequestLegal} className="flex items-center gap-1.5 whitespace-nowrap text-[10px] font-semibold text-purple-300 transition-colors hover:text-purple-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"><Scale size={12} aria-hidden="true" /> {t("pn_licenses_notices")}</button>}
            <ExternalLink href={PRODUCT.sourceUrl} className="flex items-center gap-1 whitespace-nowrap text-[10px] text-white/55 transition-colors hover:text-white/85 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400">{t("pn_codigo_fuente")} <IconoEnlaceExterno size={10} aria-hidden="true" /></ExternalLink>
          </div>
        </footer>
      </section>
    </div>,
    document.body,
  );
}
