// =====================================================================
// Descargas: el paquete Blender + Molecular Nodes para Molcy
// =====================================================================
//
// Pedido por el propietario (2026-10-10): el menú de descargas debía ofrecer
// también lo que Molcy necesita. Lo instala el backend con los dos caminos que
// ya usaba la pestaña Molcy (Blender portable con su SHA-256 fijado y Molecular
// Nodes con el gestor de extensiones de Blender); la tarjeta los encadena y
// decide «instalado» con la comprobación del renderizador, no con un archivo.

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ACTIVITY_NOTIFICATION_EVENT, type ActivityNotification } from "@/lib/activityNotifications";
import type { MolcyAddon, MolcyInstallation, MolcyRenderer } from "@/lib/molcy";
import { PaqueteMolcyCard } from "../PaqueteMolcyCard";

const api = vi.hoisted(() => ({
  renderizadorMolcy: vi.fn(),
  instalacionMolcy: vi.fn(),
  estadoAddonMolcy: vi.fn(),
  instalarBlenderMolcy: vi.fn(),
  instalarAddonMolcy: vi.fn(),
  cancelarBlenderMolcy: vi.fn(),
  configurarMolcy: vi.fn(),
}));
vi.mock("@/lib/molcy", async (original) => ({ ...(await original<typeof import("@/lib/molcy")>()), ...api }));
const sesion = vi.hoisted(() => ({ user: { user_id: "researcher-1" } as { user_id: string } | null, isLoading: false }));
vi.mock("@/lib/auth", () => ({ useAuth: () => sesion }));

const LISTO: MolcyRenderer = { disponible: true, motivo: null, version_blender: [5, 2, 2], molecular_nodes: "520.2.0" };
// Lo que responde el backend sin ningún Blender (`renderer._detectar`): desde el 2026-10-10 con su código.
const FALTA_BLENDER: MolcyRenderer = { disponible: false, motivo_codigo: "falta_blender",
  motivo: "No se encontró Blender. Descárgalo desde la configuración de abajo o elige tu blender.exe." };
const FALTA_ADDON: MolcyRenderer = { disponible: false, motivo: "Falta Molecular Nodes.", motivo_codigo: "falta_addon" };

function instalacion(cambios: Partial<MolcyInstallation> = {}): MolcyInstallation {
  return { estado: "inactivo", ruta: "C:\\datos\\molcy\\blender\\blender.exe", version: "5.2.2",
    descarga_bytes: 404_453_484, reserva_bytes: 0, instalado: false, configuracion: {}, ...cambios };
}

function addon(cambios: Partial<MolcyAddon> = {}): MolcyAddon {
  return { estado: "inactivo", ...cambios };
}

const avanzar = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

describe("paquete Blender + Molecular Nodes", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    for (const fn of Object.values(api)) fn.mockReset();
    api.instalacionMolcy.mockResolvedValue(instalacion());
    api.estadoAddonMolcy.mockResolvedValue(addon());
    sesion.user = { user_id: "researcher-1" };
  });
  afterEach(() => vi.useRealTimers());

  it("sin sesión no pregunta a Molcy (un 401 mandaría a «Iniciar sesión»)", async () => {
    sesion.user = null;
    render(<PaqueteMolcyCard />);
    await avanzar(0);
    expect(api.renderizadorMolcy).not.toHaveBeenCalled();
    expect(screen.getByText("Inicia sesión para comprobar si ya tienes Blender y Molecular Nodes.")).toBeInTheDocument();
    // Sin comprobarlo no se afirma nada.
    expect(screen.queryByText("No instalado")).not.toBeInTheDocument();
  });

  it("ya instalado: lo dice con sus versiones y no ofrece descargar", async () => {
    api.renderizadorMolcy.mockResolvedValue(LISTO);
    render(<PaqueteMolcyCard />);
    await avanzar(0);
    expect(screen.getByText("Ya lo tienes instalado")).toBeInTheDocument();
    expect(screen.getByText(/Blender 5\.2\.2 · Molecular Nodes 520\.2\.0/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descargar e instalar" })).not.toBeInTheDocument();

    // «Comprobar de nuevo» repite el sondeo de verdad.
    fireEvent.click(screen.getByRole("button", { name: "¿Algo no funciona? Comprobar de nuevo" }));
    await avanzar(0);
    expect(api.renderizadorMolcy).toHaveBeenLastCalledWith(true);
  });

  it("sin nada: «Descargar e instalar» pone Blender y, al terminar, Molecular Nodes", async () => {
    const recibidos: ActivityNotification[] = [];
    const oir = (e: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => recibidos.push(e.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, oir);
    try {
      api.renderizadorMolcy.mockResolvedValue(FALTA_BLENDER);
      render(<PaqueteMolcyCard />);
      await avanzar(0);
      expect(screen.getByText(/405 MB de Blender \+ unos 133 MB de Molecular Nodes/)).toBeInTheDocument();

      api.instalarBlenderMolcy.mockResolvedValue(instalacion({ estado: "instalando", fase: "descargando", recibidos_bytes: 0 }));
      fireEvent.click(screen.getByRole("button", { name: "Descargar e instalar" }));
      await avanzar(0);
      expect(api.instalarBlenderMolcy).toHaveBeenCalledTimes(1);

      // Blender a medias: barra con su avance.
      api.instalacionMolcy.mockResolvedValue(instalacion({ estado: "instalando", fase: "descargando", recibidos_bytes: 202_226_742 }));
      await avanzar(1500);
      expect(screen.getByRole("progressbar", { name: "Paso 1 de 2 · Blender" })).toHaveAttribute("aria-valuenow", "50");

      // Blender listo: falta Molecular Nodes y se instala sin pedir otro clic.
      api.instalacionMolcy.mockResolvedValue(instalacion({ estado: "completo", instalado: true }));
      api.renderizadorMolcy.mockResolvedValue(FALTA_ADDON);
      api.instalarAddonMolcy.mockResolvedValue(addon({ estado: "instalando", fase: "descargando" }));
      await avanzar(1500);
      expect(api.renderizadorMolcy).toHaveBeenLastCalledWith(true);
      expect(api.instalarAddonMolcy).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Paso 2 de 2 · Molecular Nodes/)).toBeInTheDocument();

      // Molecular Nodes listo: instalado, y la campana lo dice.
      api.estadoAddonMolcy.mockResolvedValue(addon({ estado: "completo", version: "520.2.0" }));
      api.renderizadorMolcy.mockResolvedValue(LISTO);
      await avanzar(1500);
      expect(screen.getByText("Ya lo tienes instalado")).toBeInTheDocument();
      expect(recibidos.map((r) => [r.id, r.status, r.titleKey])).toEqual([["molcy:paquete", "success", "nt_molcy_listo"]]);
    } finally {
      window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, oir);
    }
  });

  it("con Blender y sin Molecular Nodes, ofrece sólo Molecular Nodes", async () => {
    api.renderizadorMolcy.mockResolvedValue(FALTA_ADDON);
    render(<PaqueteMolcyCard />);
    await avanzar(0);
    expect(screen.getByText("Blender ya está; falta Molecular Nodes.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descargar e instalar" })).not.toBeInTheDocument();
    api.instalarAddonMolcy.mockResolvedValue(addon({ estado: "instalando", fase: "comprobando" }));
    fireEvent.click(screen.getByRole("button", { name: "Descargar e instalar Molecular Nodes" }));
    await avanzar(0);
    expect(api.instalarAddonMolcy).toHaveBeenCalledTimes(1);
    expect(api.instalarBlenderMolcy).not.toHaveBeenCalled();
  });

  it("un Blender de MolDesign ya descargado se reutiliza en vez de bajarlo otra vez", async () => {
    api.renderizadorMolcy.mockResolvedValue({ ...FALTA_BLENDER, motivo_codigo: "blender_antiguo", motivo: "Blender 4.2 es demasiado antiguo." });
    api.instalacionMolcy.mockResolvedValue(instalacion({ instalado: true, configuracion: { modo: "existente" } }));
    render(<PaqueteMolcyCard />);
    await avanzar(0);
    expect(screen.queryByRole("button", { name: "Descargar e instalar" })).not.toBeInTheDocument();
    api.configurarMolcy.mockResolvedValue(instalacion({ instalado: true, configuracion: { modo: "administrado" } }));
    api.renderizadorMolcy.mockResolvedValue(LISTO);
    fireEvent.click(screen.getByRole("button", { name: "Usar el Blender de MolDesign" }));
    await avanzar(0);
    expect(api.configurarMolcy).toHaveBeenCalledWith({ modo: "administrado", blender: null, motor: null });
    expect(api.instalarBlenderMolcy).not.toHaveBeenCalled();
    expect(screen.getByText("Ya lo tienes instalado")).toBeInTheDocument();
  });

  it("si el backend no contesta, lo dice y deja reintentar", async () => {
    api.renderizadorMolcy.mockRejectedValue(new Error("Failed to fetch"));
    render(<PaqueteMolcyCard />);
    await avanzar(0);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo consultar el estado de Molcy: Failed to fetch");
    api.renderizadorMolcy.mockResolvedValue(LISTO);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await avanzar(0);
    expect(screen.getByText("Ya lo tienes instalado")).toBeInTheDocument();
  });

  it("un fallo de Blender se dice en la tarjeta y en la campana", async () => {
    const recibidos: ActivityNotification[] = [];
    const oir = (e: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => recibidos.push(e.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, oir);
    try {
      api.renderizadorMolcy.mockResolvedValue(FALTA_BLENDER);
      api.instalacionMolcy.mockResolvedValue(instalacion({ estado: "instalando", fase: "descargando", recibidos_bytes: 10 }));
      render(<PaqueteMolcyCard />);
      await avanzar(0);
      api.instalacionMolcy.mockResolvedValue(instalacion({ estado: "fallido", motivo: "Blender no coincide con el SHA-256 oficial; no se instalará." }));
      await avanzar(1500);
      expect(screen.getByRole("alert")).toHaveTextContent("La instalación no terminó: Blender no coincide con el SHA-256 oficial");
      expect(recibidos.map((r) => r.status)).toEqual(["error"]);
    } finally {
      window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, oir);
    }
  });

  it("otra razón (p. ej. el motor alterado) no ofrece descargas: enlaza a Molcy", async () => {
    api.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo: "El motor no coincide con su manifiesto.", motivo_codigo: "motor_alterado" });
    render(<PaqueteMolcyCard />);
    await avanzar(0);
    expect(screen.getByText(/Molcy no puede usar esta instalación: El motor no coincide/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir Molcy" })).toHaveAttribute("href", "/molcy");
    expect(screen.queryByRole("button", { name: "Descargar e instalar" })).not.toBeInTheDocument();
  });

  // En Molcy, debajo del guion visual (propietario, 2026-10-12): la descarga estaba repartida por la columna y no se veía.
  it("en el estudio dice por qué Molcy lo necesita y el botón nombra el paquete entero", async () => {
    api.renderizadorMolcy.mockResolvedValue(FALTA_BLENDER);
    render(<PaqueteMolcyCard contexto="estudio" />);
    await avanzar(0);
    expect(screen.getByRole("heading", { name: "Molcy necesita Blender + Molecular Nodes" })).toBeInTheDocument();
    expect(screen.getByTestId("paquete-molcy-porque")).toHaveTextContent("«Generar video» y «Preparar tomas» no pueden empezar");
    api.instalarBlenderMolcy.mockResolvedValue(instalacion({ estado: "instalando", fase: "descargando", recibidos_bytes: 0 }));
    fireEvent.click(screen.getByRole("button", { name: "Descargar e instalar Blender + Molecular Nodes" }));
    await avanzar(0);
    expect(api.instalarBlenderMolcy).toHaveBeenCalledTimes(1);
  });

  it("en el estudio avisa a la página una sola vez al quedar listo, con la comprobación que lo dijo", async () => {
    const onListo = vi.fn();
    const onInstalando = vi.fn();
    api.renderizadorMolcy.mockResolvedValue(FALTA_ADDON);
    render(<PaqueteMolcyCard contexto="estudio" onListo={onListo} onInstalando={onInstalando} />);
    await avanzar(0);
    api.instalarAddonMolcy.mockResolvedValue(addon({ estado: "instalando", fase: "descargando" }));
    fireEvent.click(screen.getByRole("button", { name: "Descargar e instalar Molecular Nodes" }));
    await avanzar(0);
    expect(onInstalando).toHaveBeenLastCalledWith(true);
    api.estadoAddonMolcy.mockResolvedValue(addon({ estado: "completo", version: "520.2.0" }));
    api.renderizadorMolcy.mockResolvedValue(LISTO);
    await avanzar(1500);
    await avanzar(3000);
    expect(onListo).toHaveBeenCalledTimes(1);
    expect(onListo).toHaveBeenCalledWith(LISTO);
    expect(onInstalando).toHaveBeenLastCalledWith(false);
  });

  it("en el estudio, con el Blender del usuario, dice que Molecular Nodes va a ESE Blender y no a la carpeta de MolDesign", async () => {
    api.renderizadorMolcy.mockResolvedValue({ ...FALTA_ADDON, blender: "E:\\blender.exe" });
    render(<PaqueteMolcyCard contexto="estudio" />);
    await avanzar(0);
    expect(screen.getByTestId("paquete-molcy-donde")).toHaveTextContent("se instala en el perfil de tu Blender (E:\\blender.exe)");
    expect(screen.getByTestId("paquete-molcy-donde")).not.toHaveTextContent("carpeta de datos de MolDesign");
  });

  it("en el estudio, con el Blender de MolDesign, sigue diciendo la carpeta de datos", async () => {
    api.renderizadorMolcy.mockResolvedValue({ ...FALTA_ADDON, blender: "c:/datos/molcy/blender/blender.exe" });
    render(<PaqueteMolcyCard contexto="estudio" />);
    await avanzar(0);
    expect(screen.getByTestId("paquete-molcy-donde")).toHaveTextContent("carpeta de datos de MolDesign");
  });

  it("en el estudio, otra razón no enlaza a Molcy: ya se está en Molcy", async () => {
    api.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo: "El motor no coincide con su manifiesto.", motivo_codigo: "motor_alterado" });
    render(<PaqueteMolcyCard contexto="estudio" />);
    await avanzar(0);
    expect(screen.getByText(/Molcy no puede usar esta instalación: El motor no coincide/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Abrir Molcy" })).not.toBeInTheDocument();
  });
});
