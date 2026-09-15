"use client";


import { useLanguage } from "@/context/LanguageContext";
import React from "react";
import { Wifi, WifiOff, Loader, Cpu, Zap, AlertTriangle, ShieldAlert, HardDrive } from "lucide-react";
import type { AIProviderInfo, DestinoInfo, ResourceStatus } from "@/context/AIContext";

type Props = {
  provider: AIProviderInfo | null;
  isStreaming: boolean;
  resourceStatus: ResourceStatus | null;
  /**
   * A dónde salen los datos con este proveedor (MOLCHAT-NET-005).
   *
   * Lo calcula el backend. `null` significa que todavía no se sabe, y entonces
   * la insignia lo dice: no se afirma «local» por optimismo.
   */
  destino?: DestinoInfo | null;
  onClick?: () => void;
};

const PROVIDER_COLORS: Record<string, string> = {
  local: "#8B5CF6",
  ollama: "#F59E0B",
  claude: "#10B981",
  gemini: "#3B82F6",
  openai: "#06B6D4",
};

export function ProviderBadge({ provider, isStreaming, resourceStatus, destino = null, onClick }: Props) {
  const { t } = useLanguage();
  if (!provider) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.78em", color: "var(--text-secondary)" }}>
        <WifiOff size={12} /> {t("ia_sin_proveedor")}
      </div>
    );
  }

  // El nombre del proveedor no dice a dónde van los datos: `ollama` apuntado a
  // otra máquina sale igual. Mientras el backend no conteste se mantiene el
  // heurístico antiguo, y la línea de destino lo declara sin comprobar.
  const isCloud = destino ? destino.es_remoto : provider.id !== "local";
  const color = PROVIDER_COLORS[provider.id] || "var(--accent)";

  let statusIcon: React.ReactNode = <Wifi size={12} color={color} />;
  let statusText = "";
  let statusColor = "var(--text-secondary)";

  if (isStreaming) {
    statusIcon = <Loader size={12} style={{ animation: "spin 1s linear infinite" }} />;
    statusText = "Generando...";
  } else if (!provider.configured) {
    if (isCloud) {
      statusIcon = <WifiOff size={12} color="#EF4444" />;
      statusText = "No configurado";
      statusColor = "#EF4444";
    } else {
      statusIcon = <AlertTriangle size={12} color="#F59E0B" />;
      statusText = "llama.cpp no detectado";
      statusColor = "#F59E0B";
    }
  } else if (isCloud) {
    statusIcon = <Wifi size={12} color={color} />;
    statusText = "Conectado";
    statusColor = color;
  } else if (resourceStatus) {
    const { llm_state, pipeline_state, using_gpu, gpu_name, gpu_vram_total_gb, vram_free_gb, ram_free_gb, ram_total_gb } = resourceStatus;

    switch (llm_state) {
      case "loaded":
        if (using_gpu && gpu_name) {
          statusIcon = <Zap size={12} color="#22C55E" />;
          const freeDisplay = vram_free_gb >= 0
            ? `${vram_free_gb.toFixed(1)}G/${gpu_vram_total_gb?.toFixed(0) ?? t("auto_5bab61eb5317")}G`
            : `${gpu_vram_total_gb?.toFixed(1) ?? t("auto_5bab61eb5317")}G total`;
          statusText = `GPU · ${gpu_name} libre ${freeDisplay}`;
        } else {
          statusIcon = <Cpu size={12} color="#22C55E" />;
          statusText = `CPU · ${ram_free_gb?.toFixed(1) ?? t("auto_5bab61eb5317")}G libre / ${ram_total_gb?.toFixed(0) ?? t("auto_5bab61eb5317")}G`;
        }
        statusColor = "#22C55E";
        break;
      case "loading":
        statusIcon = <Loader size={12} style={{ animation: "spin 1s linear infinite" }} />;
        statusText = using_gpu ? "Cargando en GPU..." : "Cargando modelo...";
        statusColor = "#F59E0B";
        break;
      case "unloaded":
        if (pipeline_state === "busy") {
          if (gpu_name && !using_gpu) {
            statusIcon = <Loader size={12} style={{ animation: "spin 1s linear infinite" }} />;
            statusText = `Evaluación · GPU libre ${vram_free_gb >= 0 ? vram_free_gb.toFixed(1) + "G" : t("auto_5bab61eb5317")} · RAM ${ram_free_gb?.toFixed(1)}G`;
          } else {
            statusIcon = <Loader size={12} style={{ animation: "spin 1s linear infinite" }} />;
            statusText = `Evaluación en curso · ${ram_free_gb?.toFixed(1)}G RAM libre`;
          }
          statusColor = "#F59E0B";
        } else if (gpu_name && gpu_vram_total_gb > 0 && !using_gpu) {
          statusIcon = <Zap size={12} color="var(--text-dim)" />;
          statusText = `GPU ${gpu_name} · descargada`;
          statusColor = "var(--text-dim)";
        } else {
          statusIcon = <Cpu size={12} color="var(--text-dim)" />;
          statusText = `RAM ${ram_free_gb?.toFixed(1)}G / ${ram_total_gb?.toFixed(0) ?? t("auto_5bab61eb5317")}G · descargado`;
          statusColor = "var(--text-dim)";
        }
        break;
    }
  } else {
    statusIcon = <Cpu size={12} color={color} />;
    statusText = "Disponible";
    statusColor = color;
  }

  return (
    <div
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontSize: "0.78em",
        color: statusColor,
        cursor: onClick ? "pointer" : "default",
        lineHeight: 1.3,
      }}
    >
      {statusIcon}
      <div>
        <div style={{ fontWeight: 500 }}>{provider.name}</div>
        <div style={{ fontSize: "0.92em", opacity: 0.85 }}>{statusText}</div>
        <DestinoLinea destino={destino} />
      </div>
    </div>
  );
}

/**
 * Declaración permanente de a dónde van los datos.
 *
 * Es la mitad de interfaz de MOLCHAT-BE-003: antes se podía cambiar el
 * `base_url` y nadie se enteraba de que el chat había cambiado de destino.
 */
function DestinoLinea({ destino }: { destino: DestinoInfo | null }) {
  const { t } = useLanguage();
  if (!destino) {
    return (
      <div style={{ fontSize: "0.88em", opacity: 0.7 }} data-testid="destino-badge">
        {t("ia_destino_sin_comprobar")}
      </div>
    );
  }

  if (!destino.es_remoto) {
    return (
      <div
        data-testid="destino-badge"
        style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.88em", color: "#22C55E" }}
      >
        <HardDrive size={10} /> {t("ia_en_esta_maquina")}
      </div>
    );
  }

  return (
    <div
      data-testid="destino-badge"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        fontSize: "0.88em",
        color: destino.consentido ? "#F59E0B" : "#EF4444",
      }}
    >
      {destino.consentido ? <Wifi size={10} /> : <ShieldAlert size={10} />}
      Sale a {destino.host}
      {destino.consentido ? "" : t("auto_73e38ad50e54")}
    </div>
  );
}
