"use client";

import { useState } from "react";
import { useDownload } from "@/hooks/useDownload";
import Link from "next/link";

export function LauncherGate({ children }: { children: React.ReactNode }) {
  const { isLauncherMode, initialized } = useDownload();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return <>{children}</>;

  // Never block the app from booting.
  // The launcher is an OPT-IN option accessible from the top bar.
  // Page-level guards (RequireModel) handle missing models per-feature.

  return (
    <>
      {initialized && isLauncherMode && (
        <div
          style={{
            position: "fixed",
            bottom: 80,
            left: 24,
            zIndex: 45,
            maxWidth: 360,
            padding: "16px 20px",
            background: "var(--bg-card, #1a1a1a)",
            border: "1px solid var(--accent, #FF6B35)",
            color: "var(--text)",
            fontSize: 13,
            lineHeight: 1.5,
            fontFamily: "var(--font-mono, monospace)",
            boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            ⚠ Modelos pendientes
          </div>
          <div style={{ color: "var(--text-muted)", marginBottom: 12 }}>
            Algunos modelos de IA aún no se han descargado. Algunas funciones pueden no estar disponibles.
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Link
              href="/launcher"
              style={{
                flex: 1,
                display: "block",
                textAlign: "center",
                padding: "8px 0",
                fontWeight: 700,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                background: "var(--accent, #FF6B35)",
                color: "#fff",
                textDecoration: "none",
              }}
            >
              Descargar modelos
            </Link>
            <button
              onClick={() => setDismissed(true)}
              style={{
                padding: "8px 12px",
                fontWeight: 700,
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                background: "transparent",
                border: "1px solid var(--border-light)",
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}
      {children}
    </>
  );
}

