// =====================================================================
// MolChat declara su estado — y no inventa disponibilidad
// =====================================================================
//
// EL FALLO QUE VIGILA. `FALLBACK_PROVIDER` decía `configured: true`, así que
// antes de que `/ai/providers` contestara —o si no contestaba nunca— la
// insignia declaraba un proveedor local listo. El usuario leía «conectado», el
// primer mensaje fallaba, y nada en la pantalla explicaba por qué.
//
// Un proveedor sin comprobar se declara sin comprobar. La insignia es el único
// sitio donde el usuario puede enterarse antes de escribir.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ProviderBadge } from "../ProviderBadge";
import { FALLBACK_PROVIDER } from "../../../context/AIContext";

describe("ProviderBadge", () => {
  it("el proveedor por defecto NO se declara configurado antes de comprobarlo", () => {
    // Es la propiedad, no el render: cualquier consumidor que lea `configured`
    // —la insignia, el modal de ajustes, el guard del envío— tiene que ver un
    // estado sin comprobar.
    expect(FALLBACK_PROVIDER.configured).toBe(false);
    expect(FALLBACK_PROVIDER.active).toBe(false);
  });

  it("sin proveedor, lo dice en vez de fingir uno", () => {
    render(<ProviderBadge provider={null} isStreaming={false} resourceStatus={null} />);

    expect(screen.getByText(/sin proveedor/i)).toBeInTheDocument();
  });

  it("un proveedor local sin comprobar muestra un estado accionable", () => {
    render(
      <ProviderBadge provider={FALLBACK_PROVIDER} isStreaming={false} resourceStatus={null} />,
    );

    // Accionable: nombra el componente que falta, no un «error» genérico.
    expect(screen.getByText(/llama\.cpp no detectado/i)).toBeInTheDocument();
    expect(screen.queryByText(/^conectado$/i)).not.toBeInTheDocument();
  });

  it("un proveedor de nube sin clave se declara no configurado", () => {
    render(
      <ProviderBadge
        provider={{ ...FALLBACK_PROVIDER, id: "openai", name: "OpenAI", requires_api_key: true }}
        isStreaming={false}
        resourceStatus={null}
      />,
    );

    expect(screen.getByText(/no configurado/i)).toBeInTheDocument();
  });
});
