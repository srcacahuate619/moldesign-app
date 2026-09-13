// =====================================================================
// MOLCHAT-NET-005 y la mitad de interfaz de MOLCHAT-BE-003
// =====================================================================
//
// EL FALLO QUE VIGILA. La insignia decidía «nube» con `provider.id !== "local"`,
// que es exactamente la suposición que la auditoría desmonta: un `ollama`
// apuntado al servidor de otra persona sale de la máquina igual, y con él el
// contexto de caso y molécula. Y cambiar el `base_url` movía el destino de los
// datos sin que nada en la pantalla lo dijera.
//
// El destino lo calcula el backend a partir del host resuelto para la cuenta.
// Aquí se vigila que la interfaz lo **declare** y no lo vuelva a deducir.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ProviderBadge } from "../ProviderBadge";
import type { AIProviderInfo, DestinoInfo } from "../../../context/AIContext";

const OLLAMA: AIProviderInfo = {
  id: "ollama",
  name: "Ollama",
  description: "",
  requires_api_key: false,
  requires_base_url: true,
  default_base_url: "http://localhost:11434",
  default_model: "gemma3:1b",
  available_models: [],
  configured: true,
  active: true,
};

function destino(parcial: Partial<DestinoInfo>): DestinoInfo {
  return {
    provider_id: "ollama",
    name: "Ollama",
    host: "localhost",
    url: "http://localhost:11434",
    es_remoto: false,
    huella: "ollama@localhost",
    activo: true,
    consentido: true,
    otorgado_en: null,
    ...parcial,
  };
}

describe("la insignia declara a dónde van los datos", () => {
  it("sin dato del backend no afirma que sea local", () => {
    render(<ProviderBadge provider={OLLAMA} isStreaming={false} resourceStatus={null} />);

    expect(screen.getByTestId("destino-badge")).toHaveTextContent(/sin comprobar/i);
  });

  it("un destino en esta máquina se declara como tal", () => {
    render(
      <ProviderBadge
        provider={OLLAMA}
        isStreaming={false}
        resourceStatus={null}
        destino={destino({})}
      />,
    );

    expect(screen.getByTestId("destino-badge")).toHaveTextContent(/en esta máquina/i);
  });

  it("el mismo proveedor apuntado a otra máquina se declara remoto, con su host", () => {
    // El caso que el heurístico por nombre no veía.
    render(
      <ProviderBadge
        provider={OLLAMA}
        isStreaming={false}
        resourceStatus={null}
        destino={destino({
          host: "servidor-ajeno.example",
          url: "http://servidor-ajeno.example:11434",
          es_remoto: true,
          consentido: true,
        })}
      />,
    );

    expect(screen.getByTestId("destino-badge")).toHaveTextContent("servidor-ajeno.example");
  });

  it("un destino remoto sin autorizar lo dice antes de que el usuario escriba", () => {
    render(
      <ProviderBadge
        provider={OLLAMA}
        isStreaming={false}
        resourceStatus={null}
        destino={destino({
          host: "servidor-ajeno.example",
          es_remoto: true,
          consentido: false,
        })}
      />,
    );

    expect(screen.getByTestId("destino-badge")).toHaveTextContent(/sin autorizar/i);
  });
});
