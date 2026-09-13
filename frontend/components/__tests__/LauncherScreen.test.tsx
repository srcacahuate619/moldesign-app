// =====================================================================
// Tests para LauncherScreen — pantalla inicial de descarga
// =====================================================================
//
// LauncherScreen es la pantalla que ve el usuario al iniciar la app si
// algún módulo no está instalado. Muestra los módulos del manifiesto,
// permite descargarlos, y muestra el botón "JUGAR" cuando están todos
// listos (o los requeridos si los opcionales aún no).
//
// Tests cubren:
// - allReady → botón "JUGAR" habilitado
// - requiredReady && !allReady → botón "JUGAR (opcionales pendientes)"
// - sin módulos requeridos → permite abrir aunque falten opcionales
// - Verificar módulos instalados → llama checkModules

import { describe, it, expect, beforeEach, vi } from "vitest";
const routerPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }) }));
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { type ReactNode } from "react";

import { LauncherScreen } from "../../components/LauncherScreen";
import { DownloadProvider } from "../../context/DownloadProvider";
import { mockFetch, mockTauriInvoke, setTauriEnv } from "../../vitest.setup";

function renderWithProvider(ui: ReactNode) {
  return render(
    <DownloadProvider>
      {ui}
   </DownloadProvider>
  );
}

describe("LauncherScreen — botones de estado", () => {
  beforeEach(() => {
    routerPush.mockReset();
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
    setTauriEnv(false); // no-Tauri → todos ready por defecto
  });

  it("allReady → muestra botón 'JUGAR' habilitado", async () => {
    renderWithProvider(<LauncherScreen />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^Abrir MolDesign$/i })).toBeInTheDocument();
    });

    const jugarBtn = screen.getByRole("button", { name: /^Abrir MolDesign$/i });
    expect(jugarBtn).toBeEnabled();
  });

  it("requiredReady && !allReady → muestra botón 'JUGAR (módulos opcionales pendientes)'", async () => {
    setTauriEnv(true);
    // Backend responde → base (required) se fuerza ready
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ status: "healthy" }), { status: 200 }));
    // Tauri: base requerido listo; los módulos opcionales faltan.
    let verifyIndex = 0;
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "verify_model") return verifyIndex++ === 0;
      if (cmd === "file_exists") return false;
      throw new Error(`Unexpected: ${cmd}`);
    });

    renderWithProvider(<LauncherScreen />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Abrir sin módulos opcionales/i })).toBeInTheDocument();
    }, { timeout: 8000 });

    const jugarBtn = screen.getByRole("button", { name: /Abrir sin módulos opcionales/i });
    expect(jugarBtn).toBeEnabled();
  });

  it("sin módulos requeridos → permite abrir aunque falten opcionales", async () => {
    setTauriEnv(true);
    // El motor puede estar caído y los modelos opcionales ausentes; el
    // instalador ya incluye el runtime requerido para abrir MolDesign.
    mockFetch.mockRejectedValue(new Error("Network error"));
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "verify_model") return false;
      throw new Error(`Unexpected: ${cmd}`);
    });

    renderWithProvider(<LauncherScreen />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Abrir sin módulos opcionales/i })).toBeInTheDocument();
    }, { timeout: 8000 });

    expect(screen.getByRole("button", { name: /Abrir sin módulos opcionales/i })).toBeEnabled();
  });

  it("botón 'Verificar módulos instalados' llama a checkModules", async () => {
    setTauriEnv(true);
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ status: "healthy" }), { status: 200 }));
    let verifyCallCount = 0;
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "verify_model") {
        verifyCallCount++;
        return true;
      }
      if (cmd === "file_exists") return true;
      throw new Error(`Unexpected: ${cmd}`);
    });

    renderWithProvider(<LauncherScreen />);

    // Espera a que bootstrap termine
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^Abrir MolDesign$/i })).toBeInTheDocument();
    }, { timeout: 8000 });

    const initialCalls = verifyCallCount;

    // Click en "Verificar módulos instalados"
    const verifyBtn = screen.getByRole("button", { name: /Verificar/i });
    fireEvent.click(verifyBtn);

    // checkModules se invoca → más llamadas a verify_model
    await waitFor(() => {
      expect(verifyCallCount).toBeGreaterThan(initialCalls);
    });
  });
});