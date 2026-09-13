"use client";

import { useDownload } from "@/hooks/useDownload";

type Props = {
  modelId: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
};

export function RequireModel({ modelId, children, fallback }: Props) {
  const { models, manifest, startDownload } = useDownload();
  const entry = manifest.find((m) => m.id === modelId);
  const status = models[modelId];

  if (status === "ready") {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "64px 24px",
        textAlign: "center",
        minHeight: "40vh",
      }}
    >
      <span
        style={{
          fontSize: 13,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 8,
        }}
      >
        {entry?.name || "Modelo requerido"}
      </span>
      <p
        style={{
          fontSize: 28,
          fontWeight: 900,
          textTransform: "uppercase",
          letterSpacing: "-0.02em",
          marginBottom: 16,
        }}
      >
        No disponible
      </p>
      <p
        style={{
          fontSize: 13,
          color: "var(--text-muted)",
          lineHeight: 1.6,
          maxWidth: 400,
          marginBottom: 24,
        }}
      >
        Esta función requiere {entry?.name || "un modelo"} que no está instalado localmente.
        {status === "downloading"
          ? " Se está descargando..."
          : status === "error"
            ? " Hubo un error en la descarga."
            : ""}
      </p>
      {!status || status === "missing" || status === "error" ? (
        <button
          onClick={() => startDownload(modelId)}
          style={{
            padding: "12px 32px",
            fontWeight: 700,
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            cursor: "pointer",
            border: "1px solid var(--text)",
            background: "var(--text)",
            color: "var(--bg)",
          }}
>
        {status === "error" ? "Reintentar descarga" : "Descargar ahora"}
        </button>
      ) : null}
    </div>
  );
}
