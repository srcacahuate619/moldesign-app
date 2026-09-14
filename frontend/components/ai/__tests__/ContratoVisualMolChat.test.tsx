import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const aqui = dirname(fileURLToPath(import.meta.url));
const panel = readFileSync(resolve(aqui, "..", "ChatPanel.tsx"), "utf8");

describe("contrato visible de MolChat", () => {
  it("no fabrica tokens, ventana de contexto ni costes", () => {
    expect(panel).not.toContain("estimatedTokens");
    expect(panel).not.toContain("maxTokens");
    expect(panel).not.toContain("sessionCost");
    expect(panel).not.toContain("USD");
  });

  it("sólo afirma adjuntar molécula cuando existe moleculeContext", () => {
    expect(panel).toContain("state.moleculeContext");
    expect(panel).toContain("No hay contexto molecular adjunto");
    expect(panel).not.toContain("contexto de caso y molécula");
  });

  it("mantiene tokens internos y traduce los modos visibles", () => {
    expect(panel).toContain('mode: "speed"');
    expect(panel).toContain('mode: "reasoning"');
    expect(panel).toContain("Rápido");
    expect(panel).toContain("Razonamiento");
    expect(panel).not.toContain("Faster");
    expect(panel).not.toContain("Deep");
  });

  it("no cuantifica una latencia web que la interfaz no mide", () => {
    expect(panel).toContain("puede tardar más");
    expect(panel).not.toMatch(/puede tardar \d/);
  });

  it("expone panel y conversaciones mediante semántica de teclado nativa", () => {
    expect(panel).toContain('role="dialog"');
    expect(panel).toContain('aria-labelledby="molchat-title"');
    expect(panel).toMatch(/state\.conversations\.map[\s\S]*?<button[\s\S]*?loadConversation\(conv\.id\)/);
    expect(panel).toContain('event.key === "Escape"');
  });
});
