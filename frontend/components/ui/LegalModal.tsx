/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 */
"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { animateElements, cancelAnimations } from "@/lib/webAnimation";
import { createPortal } from "react-dom";
import { BookOpen, ExternalLink, FileCode2, FileText, Lock, Scale, Shield, X } from "lucide-react";

import { useScrollLock } from "@/hooks/useScrollLock";
import { LICENSE_HIGHLIGHTS, PRODUCT, type LicenseHighlight } from "@/lib/softwareCatalog";
// Alias `EnlaceExterno` para no chocar con el icono `ExternalLink` de lucide.
import { ExternalLink as EnlaceExterno } from "@/components/ui/ExternalLink";
import { LocalDocViewer, type LocalDoc } from "@/components/ui/LocalDocViewer";

/**
 * Documentos que viajan EMPAQUETADOS y deben poder leerse sin red.
 *
 * No se mandan al navegador del sistema: son assets de la propia aplicacion y
 * la licencia obliga a ponerlos a disposicion aunque no haya conexion. Se abren
 * en una vista interna con «Volver», sin abandonar el modal ni perder estado.
 */
const DOCUMENTOS_LOCALES: readonly LocalDoc[] = [
  { path: PRODUCT.noticesUrl, title: "Inventario completo de terceros" },
  { path: PRODUCT.sourceOfferUrl, title: "Fuente y recompilación" },
  { path: PRODUCT.commercialLicenseUrl, title: "Licencia de uso comercial" },
] as const;

type Tab = "terms" | "privacy" | "licenses";

interface LegalModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: Tab;
}

const TABS: Array<{ id: Tab; label: string; icon: ReactNode }> = [
  { id: "terms", label: "Términos", icon: <Shield size={13} aria-hidden="true" /> },
  { id: "privacy", label: "Privacidad", icon: <Lock size={13} aria-hidden="true" /> },
  { id: "licenses", label: "Licencias", icon: <BookOpen size={13} aria-hidden="true" /> },
];

const EFFECTIVE_DATE = "10 de septiembre de 2026";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-[12px] font-semibold text-white/85">{title}</h3>
      <div className="text-[12px] leading-relaxed text-white/60">{children}</div>
    </section>
  );
}

function TermsContent() {
  return (
    <div className="space-y-5">
      <header>
        <h3 className="text-sm font-bold text-white/90">Condiciones de uso científico</h3>
        <p className="mt-1 text-[12px] leading-relaxed text-white/60">MolDesign AI es una herramienta de investigación computacional. Sus resultados son hipótesis in silico y requieren validación experimental.</p>
      </header>
      <Section title="1. Alcance y uso responsable">
        No es un dispositivo médico ni reemplaza el juicio clínico, farmacéutico, toxicológico o regulatorio. El usuario debe cumplir la legislación aplicable y no utilizar la plataforma para actividades ilícitas.
      </Section>
      <Section title="2. Resultados y reproducibilidad">
        Scores, poses, propiedades y explicaciones dependen de los datos, versiones, parámetros y modelos registrados en cada corrida. Ninguna predicción constituye por sí sola evidencia experimental.
      </Section>
      <Section title="3. Datos y trabajos del usuario">
        MolDesign no reclama propiedad sobre las moléculas, casos o resultados aportados por el usuario. Un certificado criptográfico acredita integridad y fecha, pero no concede automáticamente una patente ni otro derecho registral.
      </Section>
      <Section title="4. Código, modelos y componentes de terceros">
        El código y los modelos propios identificados de MolDesign se ofrecen bajo {PRODUCT.license} para fines no comerciales. Cualquier uso comercial requiere un acuerdo escrito separado. Los conjuntos de datos, modelos y componentes de terceros conservan sus propias licencias.
      </Section>
      <Section title="5. Servicios opcionales">
        Algunas funciones sólo operan si el usuario configura o descarga recursos externos, entre ellos Hugging Face, DiffDock, ColabFold, RFdiffusion, Solana o proveedores de IA. Su disponibilidad y condiciones dependen de cada proveedor.
      </Section>
      <Section title="6. Sin garantía">
        El software se proporciona “tal cual”, sin garantías expresas o implícitas, dentro de los límites permitidos por la legislación aplicable y por las licencias incluidas.
      </Section>
      <p className="border-t border-white/[0.07] pt-3 font-mono text-[10px] text-white/40">Versión {PRODUCT.version} · Vigente desde {EFFECTIVE_DATE}</p>
    </div>
  );
}

function PrivacyContent() {
  return (
    <div className="space-y-5">
      <header>
        <h3 className="text-sm font-bold text-white/90">Privacidad local-first</h3>
        <p className="mt-1 text-[12px] leading-relaxed text-white/60">Los casos y resultados permanecen en el espacio de trabajo local, salvo cuando el usuario activa una integración externa identificada.</p>
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {["Casos locales", "Sin analítica propia", "Red bajo demanda"].map((label) => <div key={label} className="rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-center text-[10px] font-semibold text-white/65">{label}</div>)}
      </div>
      <Section title="1. Datos almacenados">
        Cuentas locales, configuraciones, receptores, moléculas, corridas, resultados y respaldos se guardan en el dispositivo y se separan por usuario y sesión.
      </Section>
      <Section title="2. Conexiones externas explícitas">
        Descargar modelos desde Hugging Face, consultar fuentes científicas, certificar en Solana o usar un proveedor de IA transmite a ese tercero la información necesaria para la operación. La interfaz debe identificar esa salida antes de ejecutarla.
      </Section>
      <Section title="3. Telemetría">
        MolDesign no incorpora analítica de producto ni crash reporting remoto. Los componentes locales se configuran para desactivar telemetría propia cuando ofrecen esa opción. Los servicios externos mantienen políticas independientes.
      </Section>
      <Section title="4. Credenciales y respaldos">
        Las credenciales configuradas y los archivos exportados quedan bajo control del usuario. No deben compartirse respaldos que contengan información confidencial sin la protección correspondiente.
      </Section>
      <p className="border-t border-white/[0.07] pt-3 font-mono text-[10px] text-white/40">Versión {PRODUCT.version} · Vigente desde {EFFECTIVE_DATE}</p>
    </div>
  );
}

const ATTENTION_LABEL: Record<NonNullable<LicenseHighlight["attention"]>, string> = {
  copyleft: "Copyleft",
  attribution: "Atribución requerida",
  blocked: "Bloqueo de distribución",
};

/**
 * Cómo se combina cada componente con MolDesign.
 *
 * Sin esta línea, «GPL-2.0-only · Copyleft» junto a un producto bajo PolyForm deja
 * al lector con la pregunta abierta y sin el dato que la contesta. Que Open
 * Babel viaje en el mismo instalador no significa que se cargue como
 * biblioteca; ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.
 */
const LINKAGE_LABEL: Record<NonNullable<LicenseHighlight["linkage"]>, string> = {
  subproceso:
    "Programa independiente: se ejecuta como proceso aparte y sólo intercambia archivos. MolDesign no lo enlaza ni importa su código.",
  biblioteca: "Se enlaza o se importa desde el código de MolDesign.",
};

function LicenseRow({ item }: { item: LicenseHighlight }) {
  const blocked = item.attention === "blocked";
  return (
    <article className={`rounded-lg border p-3 ${blocked ? "border-red-500/30 bg-red-500/[0.05]" : "border-white/[0.08] bg-white/[0.02]"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-[12px] font-semibold text-white/85">{item.name} <span className="font-mono text-[10px] font-normal text-white/45">{item.version}</span></h4>
          <p className="mt-0.5 text-[10px] text-white/45">{item.role}</p>
        </div>
        <span className={`rounded border px-1.5 py-0.5 font-mono text-[9px] ${blocked ? "border-red-500/30 text-red-300" : "border-purple-500/25 text-purple-200"}`}>{item.license}</span>
      </div>
      {item.linkage ? (
        <p className="mt-1.5 text-[10px] leading-relaxed text-white/45">{LINKAGE_LABEL[item.linkage]}</p>
      ) : null}
      <div className="mt-2 flex items-center justify-between gap-3">
        <span className={`text-[10px] ${blocked ? "font-semibold text-red-300" : "text-white/45"}`}>{item.attention ? ATTENTION_LABEL[item.attention] : "Aviso incluido"}</span>
        <EnlaceExterno href={item.sourceUrl} className="flex items-center gap-1 whitespace-nowrap text-[10px] text-purple-300 hover:text-purple-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400">Fuente <ExternalLink size={9} aria-hidden="true" /></EnlaceExterno>
      </div>
    </article>
  );
}

function LicensesContent({ onAbrirDoc }: { onAbrirDoc: (doc: LocalDoc) => void }) {
  return (
    <div className="space-y-5">
      <header>
        <h3 className="text-sm font-bold text-white/90">Licencias y código fuente</h3>
        <p className="mt-1 text-[12px] leading-relaxed text-white/60">Esta pantalla resume los componentes que requieren atención especial. El inventario completo del runtime y los textos íntegros se distribuyen con la aplicación.</p>
      </header>
      <div className="rounded-lg border border-purple-500/25 bg-purple-500/[0.06] p-3">
        <p className="text-[12px] font-semibold text-purple-100">MolDesign AI · PolyForm Noncommercial 1.0.0</p>
        <p className="mt-1 text-[11px] leading-relaxed text-white/60">Uso, estudio, modificación y redistribución no comerciales permitidos. El uso comercial requiere una licencia escrita separada. Es source-available, no open source según OSI.</p>
      </div>
      <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3">
        <p className="text-[12px] font-semibold text-amber-200">Built with PriorLabs-TabPFN</p>
        <p className="mt-1 text-[10px] leading-relaxed text-white/55">Atribución exigida por la Prior Labs License 1.2 para productos que incorporan TabPFN.</p>
      </div>
      <section className="space-y-2" aria-labelledby="license-highlights-title">
        <h3 id="license-highlights-title" className="text-[12px] font-semibold text-white/80">Componentes destacados</h3>
        {LICENSE_HIGHLIGHTS.map((item) => <LicenseRow key={item.name} item={item} />)}
      </section>
      <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/[0.05] p-3">
        <div className="flex items-start gap-2"><BookOpen size={14} className="mt-0.5 shrink-0 text-emerald-300" aria-hidden="true" /><div><p className="text-[11px] font-semibold text-emerald-200">RTMScore · licencia MIT conservada</p><p className="mt-1 text-[10px] leading-relaxed text-white/55">La copia integrada incluye el texto upstream y su atribución: Copyright (c) 2023 sc8668. La licencia permite uso y redistribución comercial conservando ese aviso.</p></div></div>
      </div>
      {/* Botones, no enlaces: estos documentos NO salen de la aplicacion. Son
          assets empaquetados que deben leerse sin red, y mandarlos al navegador
          —o navegar a ellos— sustituiria la app por un Markdown crudo. */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <button type="button" onClick={() => onAbrirDoc(DOCUMENTOS_LOCALES[0])} className="flex min-h-11 items-center justify-between rounded-lg border border-white/[0.1] px-3 text-[11px] font-semibold text-white/70 hover:border-purple-500/35 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"><span className="flex items-center gap-2"><Scale size={13} aria-hidden="true" />Inventario completo</span><FileText size={10} aria-hidden="true" /></button>
        <button type="button" onClick={() => onAbrirDoc(DOCUMENTOS_LOCALES[1])} className="flex min-h-11 items-center justify-between rounded-lg border border-white/[0.1] px-3 text-[11px] font-semibold text-white/70 hover:border-purple-500/35 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"><span className="flex items-center gap-2"><FileCode2 size={13} aria-hidden="true" />Fuente y recompilación</span><FileText size={10} aria-hidden="true" /></button>
        <button type="button" onClick={() => onAbrirDoc(DOCUMENTOS_LOCALES[2])} className="flex min-h-11 items-center justify-between rounded-lg border border-amber-500/20 px-3 text-[11px] font-semibold text-amber-200 hover:border-amber-400/40 hover:text-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"><span className="flex items-center gap-2"><Scale size={13} aria-hidden="true" />Uso comercial</span><FileText size={10} aria-hidden="true" /></button>
      </div>
      <p className="text-[10px] leading-relaxed text-white/40">Los modelos descargables muestran su licencia y procedencia por separado antes de instalarse. Este resumen técnico no sustituye asesoría jurídica profesional.</p>
    </div>
  );
}

export function LegalModal({ isOpen, onClose, initialTab = "terms" }: LegalModalProps) {
  useScrollLock(isOpen);
  const backdropRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  // Documento empaquetado en pantalla, o `null` si se ven las pestanas. El
  // modal NO se cierra al abrirlo: el estado de la aplicacion se conserva y
  // «Volver» devuelve exactamente a donde se estaba.
  const [docAbierto, setDocAbierto] = useState<LocalDoc | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  useEffect(() => { if (isOpen) setActiveTab(initialTab); }, [initialTab, isOpen]);
  useEffect(() => {
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!isOpen || !panel || !backdrop) return;
    cancelAnimations(backdrop);
    cancelAnimations(panel);
    backdrop.style.opacity = "0";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(12px) scale(0.98)";
    animateElements(backdrop, [{ opacity: 0 }, { opacity: 1 }], { duration: 180, fill: "forwards", easing: "ease-out" });
    animateElements(panel, [
      { opacity: 0, transform: "translateY(12px) scale(0.98)" },
      { opacity: 1, transform: "translateY(0) scale(1)" },
    ], { duration: 240, fill: "forwards", easing: "cubic-bezier(0.16, 1, 0.3, 1)" });
    closeButtonRef.current?.focus();
  }, [isOpen]);

  const handleClose = () => {
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!panel || !backdrop) { onClose(); return; }
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
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen || !mounted) return null;
  const content: Record<Tab, ReactNode> = { terms: <TermsContent />, privacy: <PrivacyContent />, licenses: <LicensesContent onAbrirDoc={setDocAbierto} /> };

  return createPortal(
    <div className="fixed inset-0 z-[210] flex items-center justify-center p-2 sm:p-4" role="presentation" onMouseDown={(event) => event.stopPropagation()}>
      <div ref={backdropRef} className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={handleClose} />
      <section ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="legal-title" className="relative z-10 flex max-h-[92vh] w-full max-w-[680px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d0e12] shadow-2xl" style={{ opacity: 0 }}>
        <header className="flex shrink-0 items-center justify-between px-4 pb-3 pt-4 sm:px-5 sm:pt-5">
          <div className="flex items-center gap-2.5"><div className="rounded-lg border border-purple-500/25 bg-purple-500/[0.07] p-1.5"><Scale size={15} className="text-purple-300" aria-hidden="true" /></div><div><h2 id="legal-title" className="text-sm font-bold text-white/90">Legal y privacidad</h2><p className="font-mono text-[10px] text-white/45">{PRODUCT.name} · v{PRODUCT.version}</p></div></div>
          <button ref={closeButtonRef} type="button" onClick={handleClose} aria-label="Cerrar información legal" className="rounded-lg border border-white/[0.08] p-2 text-white/55 hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"><X size={15} aria-hidden="true" /></button>
        </header>
        <div className="shrink-0 px-3 pb-3 sm:px-4"><div className="grid grid-cols-3 gap-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1" role="tablist" aria-label="Información legal">{TABS.map((tab) => <button key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => setActiveTab(tab.id)} className={`flex min-h-10 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border px-2 text-[11px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-purple-400 ${activeTab === tab.id ? "border-purple-500/25 bg-purple-500/10 text-purple-200" : "border-transparent text-white/50 hover:text-white/80"}`}>{tab.icon}<span>{tab.label}</span></button>)}</div></div>
        <div className="h-px shrink-0 bg-white/[0.06]" />
        <div className="flex-1 overflow-y-auto px-4 py-5 custom-scrollbar sm:px-5" role="tabpanel">{docAbierto ? <LocalDocViewer doc={docAbierto} onClose={() => setDocAbierto(null)} /> : content[activeTab]}</div>
        <footer className="flex shrink-0 flex-col gap-2 border-t border-white/[0.06] bg-[#0a0b0f] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5"><p className="text-[10px] text-white/45">Local-first · conexiones externas identificadas</p><EnlaceExterno href={PRODUCT.sourceUrl} className="flex items-center gap-1 whitespace-nowrap text-[10px] text-purple-300 hover:text-purple-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400">Repositorio de esta versión <ExternalLink size={9} aria-hidden="true" /></EnlaceExterno></footer>
      </section>
    </div>,
    document.body,
  );
}
