// Panel de proveedores: lista sin claves, guardar y autorizar en un paso, rechazos con su motivo.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProveedoresIA } from "../ProveedoresIA";

const CLAVE = "sk-prueba-0123456789abcdef7890";

const traeBackend = vi.fn();

vi.mock("@/context/LanguageContext", () => ({
  useLanguage: () => ({
    t: (clave: string, valores?: Record<string, string>) =>
      valores ? `${clave}:${Object.values(valores).join(",")}` : clave,
  }),
}));
vi.mock("@/lib/api", () => ({ getAuthHeaders: () => ({ Authorization: "Bearer test" }) }));
vi.mock("@/lib/backendFetch", () => ({
  fetchBackend: (...args: unknown[]) => traeBackend(...args),
}));

function json(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const ESTADO = {
  disponible: true,
  motivo: "ok",
  activo: null,
  proveedores: [
    {
      id: "openai",
      nombre: "OpenAI",
      host: "api.openai.com",
      remoto: true,
      requiere_clave: true,
      documentacion: "https://platform.openai.com/docs",
      que_sale: "El texto del chat.",
      modelo: "",
      modelos_ejemplo: ["gpt-4o-mini"],
      clave: { configurada: true, pista: "••••7890" },
      autorizado: true,
      activo: false,
    },
    {
      id: "llama-server",
      nombre: "llama-server",
      host: "127.0.0.1",
      remoto: false,
      requiere_clave: false,
      documentacion: "",
      que_sale: "Nada.",
      modelo: "",
      modelos_ejemplo: [],
      clave: null,
      autorizado: null,
      activo: false,
    },
  ],
};

beforeEach(() => {
  traeBackend.mockReset();
});

describe("ProveedoresIA", () => {
  it("lista los proveedores del servidor y nunca una clave completa", async () => {
    traeBackend.mockResolvedValue(json(ESTADO));
    const { container } = render(<ProveedoresIA />);
    expect(await screen.findByText("OpenAI")).toBeTruthy();
    expect(screen.getByText("llama-server")).toBeTruthy();
    expect(container.textContent).toContain("••••7890");
    expect(container.textContent).not.toContain("sk-");
  });

  it("guardar y autorizar envía el host que se mostró y vacía el campo de la clave", async () => {
    const peticiones: { url: string; init: RequestInit }[] = [];
    traeBackend.mockImplementation(async (url: string, init: RequestInit = {}) => {
      peticiones.push({ url, init });
      if (init.method === "PUT") return json({ ...ESTADO.proveedores[0] });
      return json(ESTADO);
    });
    render(<ProveedoresIA />);
    await screen.findByText("OpenAI");
    const campo = document.getElementById("clave-openai") as HTMLInputElement;
    fireEvent.change(campo, { target: { value: CLAVE } });
    fireEvent.click(screen.getByText("ia_prov_guardar:api.openai.com"));
    await waitFor(() => expect(peticiones.some((p) => p.init.method === "PUT")).toBe(true));
    const put = peticiones.find((p) => p.init.method === "PUT");
    expect(put?.url).toBe("/molchat-host/proveedores/openai/clave");
    expect(JSON.parse(String(put?.init.body))).toMatchObject({
      api_key: CLAVE,
      host_visto: "api.openai.com",
    });
    await waitFor(() => expect(campo.value).toBe(""));
  });

  it("si el destino cambió, lo dice y no guarda nada", async () => {
    traeBackend.mockImplementation(async (_url: string, init: RequestInit = {}) => {
      if (init.method === "PUT") {
        return json({ detail: { motivo: "destino_cambiado" } }, 409);
      }
      return json(ESTADO);
    });
    render(<ProveedoresIA />);
    await screen.findByText("OpenAI");
    fireEvent.change(document.getElementById("clave-openai") as HTMLInputElement, {
      target: { value: CLAVE },
    });
    fireEvent.click(screen.getByText("ia_prov_guardar:api.openai.com"));
    expect(await screen.findByText("ia_prov_error_destino")).toBeTruthy();
  });

  it("sin MolChat lo dice con el motivo del servidor", async () => {
    traeBackend.mockResolvedValue(json({
      disponible: false, motivo: "sin sidecar incluido", activo: null, proveedores: [],
    }));
    render(<ProveedoresIA />);
    expect(await screen.findByText("ia_prov_no_disponible")).toBeTruthy();
    expect(screen.getByText("sin sidecar incluido")).toBeTruthy();
  });
});
