"use client";

// =====================================================================
// global-error — la red que impide la pantalla en blanco
// =====================================================================
//
// EL FALLO QUE CUBRE. `ErrorBoundary` envuelve el contenido de `main` y el
// panel de chat, pero NO a los providers que lo rodean: wallet, auth, tema,
// idioma, descargas e IA quedaban fuera. Una excepción en cualquiera de ellos
// —o en `Navigation`— escapa hacia la raíz, y en el App Router de Next una
// excepción no capturada en el layout raíz deja la ventana EN BLANCO.
//
// En un navegador eso se diagnostica abriendo la consola. En la app instalada
// no hay consola que abrir: el usuario ve una ventana vacía y no tiene forma de
// saber si el producto está roto, si le falta algo o si debe esperar.
//
// `global-error.tsx` es el único punto del App Router que captura eso, y por
// contrato reemplaza al layout raíz entero — por eso lleva sus propios `<html>`
// y `<body>` y no puede apoyarse en providers, temas ni traducciones: cuando
// esto se pinta, puede que ninguno de ellos haya llegado a montarse.
//
// Los estilos van en línea a propósito. Si el fallo fuera la propia hoja de
// estilos, un fallback que dependa de ella sería otra pantalla en blanco.

import { useEffect } from "react";
import { useLanguage } from "../context/LanguageContext";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useLanguage();
  useEffect(() => {
    // Queda en la consola del WebView y en el log del plugin de Tauri, que es
    // lo que un usuario puede adjuntar en un reporte.
    console.error("[global-error]", error?.message, error?.digest, error?.stack);
  }, [error]);

  return (
    <html lang={t("auto_09cd68a2a77b")}>
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#09090b",
          color: "#e4e4e7",
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
          padding: "2rem",
        }}
      >
        <main style={{ maxWidth: "34rem", textAlign: "left" }}>
          <p
            style={{
              margin: 0,
              fontSize: "0.7rem",
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "#f87171",
              fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace",
            }}
          >
            {t("pg_err_titulo")}
          </p>
          <h1 style={{ margin: "0.75rem 0 0", fontSize: "1.4rem", fontWeight: 600 }}>
            {t("pg_err_subtitulo")}
          </h1>
          <p style={{ margin: "0.75rem 0 0", fontSize: "0.9rem", lineHeight: 1.6, color: "#a1a1aa" }}>
            {t("pg_err_datos_intactos")}
          </p>

          <pre
            style={{
              margin: "1.25rem 0 0",
              padding: "0.75rem 0.9rem",
              backgroundColor: "#18181b",
              border: "1px solid #27272a",
              borderRadius: "0.5rem",
              fontSize: "0.75rem",
              lineHeight: 1.5,
              color: "#d4d4d8",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace",
            }}
          >
            {error?.message || t("auto_090a83af1bac")}
            {error?.digest ? `\ndigest: ${error.digest}` : ""}
          </pre>

          <div style={{ marginTop: "1.25rem", display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => reset()}
              style={{
                padding: "0.55rem 1.1rem",
                borderRadius: "0.5rem",
                border: "1px solid #3f3f46",
                backgroundColor: "#27272a",
                color: "#e4e4e7",
                fontSize: "0.85rem",
                cursor: "pointer",
              }}
            >
              {t("c_reintentar")}
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: "0.55rem 1.1rem",
                borderRadius: "0.5rem",
                border: "1px solid #27272a",
                backgroundColor: "transparent",
                color: "#a1a1aa",
                fontSize: "0.85rem",
                cursor: "pointer",
              }}
            >
              {t("pg_err_recargar")}
            </button>
          </div>

          <p style={{ margin: "1.25rem 0 0", fontSize: "0.75rem", lineHeight: 1.6, color: "#71717a" }}>
            {t("pg_err_reiniciar_seguro")}
          </p>
        </main>
      </body>
    </html>
  );
}
