import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "../ChatInput";

vi.mock("@/hooks/useSpeechRecognition", () => ({
  useSpeechRecognition: () => ({
    state: "unsupported",
    interimText: "",
    startListening: vi.fn(),
    stopListening: vi.fn(),
    isSupported: false,
    mode: "unsupported",
  }),
}));

describe("dictado de MolChat", () => {
  it("mantiene el micrófono deshabilitado y explica la alternativa escrita", () => {
    render(<ChatInput onSend={vi.fn()} onStop={vi.fn()} isStreaming={false} />);

    expect(screen.getByRole("button", { name: "Dictado no disponible" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/falta el reconocimiento de voz local/i);
    expect(screen.getByRole("status")).toHaveTextContent(/puedes seguir escribiendo/i);
  });

  it("mantiene perceptible el icono de enviar cuando el botón está deshabilitado", () => {
    render(<ChatInput onSend={vi.fn()} onStop={vi.fn()} isStreaming={false} />);

    const send = screen.getByRole("button", { name: "Enviar mensaje" });
    expect(send).toBeDisabled();
    expect(send.getAttribute("style")).toEqual(expect.stringContaining("color: var(--text-secondary)"));
    expect(send.getAttribute("style")).toEqual(expect.stringContaining("border: 1px solid var(--border)"));
    expect(send.getAttribute("style")).toEqual(expect.stringContaining("opacity: 0.7"));
  });
});
