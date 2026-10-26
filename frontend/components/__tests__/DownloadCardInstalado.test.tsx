// =====================================================================
// Descargas: un modelo instalado no invita a bajarlo otra vez
// =====================================================================
//
// Visto por el propietario (2026-10-10): «es muy molesto que te deje
// descargar los modelos si ya los tienes disponibles». La tarjeta de un modelo
// instalado dice que ya está y esconde la descarga detrás de «¿Descargar de
// nuevo?», con una confirmación que explica cuándo usarla (un archivo dañado).

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FALLBACK_MANIFEST } from "@/context/DownloadProvider";
import { DownloadCard } from "../DownloadCard";

const estado = vi.hoisted(() => ({
  models: {} as Record<string, string>,
  progress: {} as Record<string, unknown>,
  startDownload: vi.fn(),
  cancelDownload: vi.fn(),
}));
vi.mock("@/hooks/useDownload", () => ({ useDownload: () => estado }));

const ESMFOLD = FALLBACK_MANIFEST.find((entry) => entry.id === "esmfold-weights")!;

describe("tarjeta de un modelo descargable", () => {
  beforeEach(() => {
    estado.models = {};
    estado.progress = {};
    estado.startDownload.mockClear();
  });

  it("instalado: lo dice, sin el botón grande de descarga", () => {
    estado.models = { [ESMFOLD.id]: "ready" };
    render(<DownloadCard entry={ESMFOLD} />);
    expect(screen.getByText("Ya lo tienes instalado")).toBeInTheDocument();
    expect(screen.getByText("Instalado")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descargar y verificar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descargar de nuevo" })).not.toBeInTheDocument();
  });

  it("«¿Descargar de nuevo?» pide confirmación y explica cuándo usarlo", () => {
    estado.models = { [ESMFOLD.id]: "ready" };
    render(<DownloadCard entry={ESMFOLD} />);
    fireEvent.click(screen.getByRole("button", { name: "¿Descargar de nuevo?" }));
    const grupo = screen.getByRole("group", { name: "Descargar de nuevo" });
    expect(grupo).toHaveTextContent("8.44 GB");
    expect(grupo).toHaveTextContent("sólo si el nuevo pasa la verificación SHA-256");

    // Cancelar no descarga nada.
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(estado.startDownload).not.toHaveBeenCalled();
    expect(screen.queryByRole("group", { name: "Descargar de nuevo" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "¿Descargar de nuevo?" }));
    fireEvent.click(screen.getByRole("button", { name: "Descargar de nuevo" }));
    expect(estado.startDownload).toHaveBeenCalledWith(ESMFOLD.id);
  });

  it("sin instalar: el botón de siempre y nada de «ya lo tienes»", () => {
    estado.models = { [ESMFOLD.id]: "missing" };
    render(<DownloadCard entry={ESMFOLD} />);
    expect(screen.getByRole("button", { name: "Descargar y verificar" })).toBeInTheDocument();
    expect(screen.queryByText("Ya lo tienes instalado")).not.toBeInTheDocument();
  });

  it("con todos los bytes en disco dice que verifica, en vez de una velocidad", () => {
    estado.models = { [ESMFOLD.id]: "downloading" };
    estado.progress = { [ESMFOLD.id]: { model_id: ESMFOLD.id, bytes_downloaded: 8_442_062_570, total_bytes: 8_442_062_570, speed_bytes_per_sec: 0 } };
    render(<DownloadCard entry={ESMFOLD} />);
    expect(screen.getByText("Verificando SHA-256…")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });
});
