"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useDownload } from "@/hooks/useDownload";

type Props = {
  modelId: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
};

export function RequireModel({ modelId, children, fallback }: Props) {
  const { t } = useLanguage();
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
        {t("c_no_disponible")}
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
        {t("auto_bf1431bba866")} {entry?.name || t("auto_c0f7ffa788c9")} {t("auto_842dd575a113")}
        {status === "downloading"
          ? t("auto_4750b49f870b")
          : status === "error"
            ? t("auto_6c6d4fcf3374")
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
