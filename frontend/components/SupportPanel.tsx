"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, LifeBuoy, Mail, ChevronDown, Heart, ExternalLink as ExternalLinkIcon, Copy, Check } from "lucide-react";
import { ExternalLink } from "./ui/ExternalLink";

interface Props {
  open: boolean;
  onClose: () => void;
}

const FAQ_ITEMS = [
  {
    q: "¿Cómo funciona el docking molecular?",
    a: "MolDesign usa AutoDock Vina para explorar poses plausibles de un ligando dentro de una hipótesis de sitio. El resultado es evidencia computacional de una corrida: no demuestra unión, eficacia ni éxito experimental.",
  },
  {
    q: "¿Cómo debo interpretar los resultados?",
    a: "Lee cada dimensión por separado: preparación, hipótesis de sitio, docking, propiedades, controles y limitaciones. Ningún índice 0–100 es una probabilidad de unión ni una calificación de que la molécula sea un buen fármaco.",
  },
  {
    q: "¿Puedo usar mis propios targets (proteínas)?",
    a: "Sí. En Evaluación puedes seleccionar “Target personalizado” y subir un archivo PDB. Antes de ejecutar, revisa el preflight y confirma las decisiones de preparación que el caso deje abiertas.",
  },
  {
    q: "¿Mis datos son privados?",
    a: "En modo escritorio, casos, moléculas y resultados se almacenan localmente. Las integraciones remotas —comunidad, proveedores de IA o certificación pública— son opcionales y sólo transmiten datos cuando las activas de forma explícita.",
  },
  {
    q: "¿Cómo instalo modelos de IA locales?",
    a: "Abre Opciones → Intérprete IA local. Los modelos son complementarios para explicar evidencia; no sustituyen los cálculos ni añaden certeza científica a una corrida.",
  },
  {
    q: "¿Los resultados son científicamente válidos?",
    a: "MolDesign registra qué evidencia produjo la corrida, qué supuestos hizo, qué controles superó y qué incertidumbres permanecen. Es una herramienta de apoyo para investigación; la interpretación y la validación experimental siguen siendo responsabilidad del laboratorio.",
  },
];

const SOLANA_ADDRESS = "7vBDmFjNEDkSHhEYeFcJXKGU6UvqVBvKk0tKnPL8dE1s";

/**
 * Contenido reutilizable del soporte.
 *
 * El panel de Opciones lo muestra como una vista interna para que la app tenga
 * un único drawer lateral. `SupportPanel` conserva el wrapper histórico para
 * cualquier consumidor que todavía necesite abrir Soporte directamente.
 */
export function SupportContent() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCopyAddress = async () => {
    try {
      await navigator.clipboard.writeText(SOLANA_ADDRESS);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="px-5 py-4 font-sans">
      <section className="mb-6">
        <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">
          Contacto
        </h3>
        <ExternalLink
          href="mailto:soporte-moldesign@amezcua-dev.com"
          className="flex min-h-11 items-center gap-2.5 rounded-[10px] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-3 text-sm text-[var(--text)] no-underline transition-colors hover:border-[var(--accent)] hover:bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] active:bg-[var(--bg-secondary)]"
        >
          <Mail size={18} className="shrink-0 text-[var(--accent)]" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate">soporte-moldesign@amezcua-dev.com</span>
          <ExternalLinkIcon size={14} className="shrink-0 text-[var(--text-dim)]" aria-hidden="true" />
        </ExternalLink>
        <p className="mt-2 text-xs leading-5 text-[var(--text-dim)]">
          ¿Encontraste un error o tienes una propuesta? Escríbenos e incluye los pasos para reproducirlo.
        </p>
      </section>

      <section className="mb-6">
        <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">
          Preguntas frecuentes
        </h3>
        <div className="flex flex-col gap-1.5">
          {FAQ_ITEMS.map((item, index) => {
            const expanded = expandedFaq === index;
            const answerId = `support-answer-${index}`;
            return (
              <div key={item.q} className="overflow-hidden rounded-[10px] border border-[var(--border)]">
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={answerId}
                  onClick={() => setExpandedFaq(expanded ? null : index)}
                  className="flex min-h-11 w-full items-center justify-between bg-[var(--bg)] px-3.5 py-2.5 text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent-strong)] active:bg-[var(--bg-secondary)]"
                >
                  <span className="min-w-0 flex-1 pr-2">{item.q}</span>
                  <ChevronDown
                    size={14}
                    className={`shrink-0 text-[var(--text-dim)] transition-transform ${expanded ? "rotate-180" : ""}`}
                    aria-hidden="true"
                  />
                </button>
                <AnimatePresence initial={false}>
                  {expanded && (
                    <motion.div
                      id={answerId}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.16, ease: "easeOut" }}
                      className="border-t border-[var(--border)] bg-[var(--bg-secondary)]"
                    >
                      <p className="px-3.5 py-3 text-xs leading-5 text-[var(--text-secondary)]">
                        {item.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h3 className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">
          <Heart size={13} className="text-red-400" aria-hidden="true" />
          Apoyar el proyecto
        </h3>
        <p className="mb-3 text-xs leading-5 text-[var(--text-secondary)]">
          MolDesign es software libre. Si te resulta útil, puedes apoyar su mantenimiento con una donación en SOL.
        </p>
        <div className="flex items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5">
          <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-[var(--text-dim)]">
            {SOLANA_ADDRESS}
          </span>
          <button
            type="button"
            onClick={handleCopyAddress}
            className={`relative grid h-8 w-8 shrink-0 place-items-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] active:bg-[var(--bg-secondary)] ${copied ? "text-emerald-400" : "text-[var(--text-dim)] hover:bg-[var(--bg-alt)] hover:text-[var(--text)]"}`}
            aria-label={copied ? "Dirección copiada" : "Copiar dirección de Solana"}
          >
            {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
          </button>
        </div>
        <p className="mt-1.5 text-[11px] leading-4 text-[var(--text-dim)]">
          Red Solana. La certificación y las donaciones son funciones opcionales.
        </p>
      </section>
    </div>
  );
}

export function SupportPanel({ open, onClose }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <div style={{ position: "fixed", inset: 0, zIndex: 55 }}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: "absolute", inset: 0,
              background: "rgba(0,0,0,0.3)", backdropFilter: "blur(2px)",
            }}
          />
          <motion.div
            initial={{ x: -400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -400, opacity: 0 }}
            transition={{ type: "spring", damping: 26, stiffness: 300 }}
            style={{
              position: "absolute",
              left: 0, top: 76, bottom: 0,
              width: 380, maxWidth: "90vw",
              background: "var(--bg-secondary)",
              borderRight: "1px solid var(--border)",
              display: "flex", flexDirection: "column",
              overflow: "hidden",
              boxShadow: "8px 0 40px rgba(0,0,0,0.3)",
            }}
          >
            {/* Header */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "16px 20px", borderBottom: "1px solid var(--border)",
              flexShrink: 0,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <LifeBuoy size={20} style={{ color: "var(--accent)" }} />
                <h2 style={{ margin: 0, fontSize: "1em", fontWeight: 600, color: "var(--text)" }}>
                  Soporte
                </h2>
              </div>
              <button onClick={onClose} style={{
                background: "none", border: "none", color: "var(--text-secondary)",
                cursor: "pointer", padding: 4,
              }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ flex: 1, overflow: "auto" }}>
              <SupportContent />
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
