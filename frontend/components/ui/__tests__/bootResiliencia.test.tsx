// =====================================================================
// Resiliencia de arranque: la ventana no puede quedarse en blanco
// =====================================================================
//
// LO QUE PROTEGEN, en orden de gravedad:
//
// 1. **Una excepción en un PROVIDER no deja la ventana vacía.** `ErrorBoundary`
//    envolvía sólo el contenido de `main` y el chat; wallet, auth, tema,
//    idioma, descargas, IA y `Navigation` quedaban fuera. En un navegador una
//    pantalla en blanco se diagnostica abriendo la consola; en la aplicación
//    instalada no hay consola que abrir.
//
// 2. **La billetera del navegador no se ofrece donde no puede funcionar.**
//    Phantom es una extensión y el WebView2 no carga extensiones; además la CSP
//    de producción sólo permite `connect-src` a 127.0.0.1. Ofrecer el botón
//    igual es peor que no ofrecerlo: el usuario pulsa, no pasa nada, y nada le
//    dice por qué.

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { ErrorBoundary } from "../ErrorBoundary";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function Explota(): React.JSX.Element {
  throw new Error("el provider reventó al montar");
}

describe("frontera de error alrededor de los providers", () => {
  beforeEach(() => {
    // React imprime el error capturado; se silencia para no ensuciar la salida
    // sin ocultar fallos reales de la prueba.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("un provider que revienta deja la ventana con contenido, no en blanco", () => {
    render(
      <ErrorBoundary>
        <Explota />
      </ErrorBoundary>,
    );

    // Lo esencial: hay algo pintado.
    expect(document.body.textContent?.trim()).not.toBe("");
    expect(screen.getByText(/Algo sali[oó] mal/i)).toBeInTheDocument();
    // Y el mensaje real llega al usuario, no un texto genérico vacío.
    expect(screen.getByText(/el provider reventó al montar/)).toBeInTheDocument();
    // Con salida: un callejón sin salida obliga a matar el proceso.
    expect(screen.getByRole("button", { name: /Reintentar/i })).toBeInTheDocument();
  });

  it("el layout mete los providers DENTRO de la frontera", async () => {
    // Se lee el layout como texto: montarlo entero arrastraría Solana, Tauri y
    // el runtime de Next. Lo que se fija es la ESTRUCTURA, que es donde estuvo
    // el fallo — no el comportamiento de cada provider.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const layout = await fs.readFile(
      path.resolve(__dirname, "../../../app/layout.tsx"),
      "utf-8",
    );

    const aperturaFrontera = layout.indexOf("<ErrorBoundary>");
    const aperturaWallet = layout.indexOf("<WalletProvider>");
    expect(aperturaFrontera).toBeGreaterThan(-1);
    expect(aperturaWallet).toBeGreaterThan(-1);
    // La frontera abre ANTES que el primer provider.
    expect(aperturaFrontera).toBeLessThan(aperturaWallet);
    // Y cierra DESPUÉS.
    expect(layout.lastIndexOf("</ErrorBoundary>")).toBeGreaterThan(
      layout.indexOf("</WalletProvider>"),
    );
  });

  it("existe la red de último recurso del App Router", async () => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const global = await fs.readFile(
      path.resolve(__dirname, "../../../app/global-error.tsx"),
      "utf-8",
    );

    expect(global).toContain('"use client"');
    // Reemplaza al layout raíz, así que necesita su propio documento.
    expect(global).toContain("<html");
    expect(global).toContain("<body");
    // Sin depender de la hoja de estilos: si el fallo fuera esa, un fallback
    // que la necesitara sería otra pantalla en blanco.
    expect(global).toContain("style={{");
    expect(global).not.toContain('from "./globals.css"');
    // Y ofrece salida.
    expect(global).toContain("reset()");
  });
});

describe("certificación con billetera del navegador", () => {
  it("no se ofrece en el escritorio, y se dice por qué", async () => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const modal = await fs.readFile(
      path.resolve(__dirname, "../../CertificationModal.tsx"),
      "utf-8",
    );

    // La decisión es en RUNTIME (`isDesktopRuntime`), no por variable de build:
    // el mismo bundle se abre en navegador durante el desarrollo.
    expect(modal).toContain("isDesktopRuntime");
    expect(modal).toContain("billeteraNoDisponible");
    // El botón de billetera queda detrás de la condición.
    const condicion = modal.indexOf("billeteraNoDisponible ?");
    const boton = modal.indexOf("<WalletMultiButton");
    expect(condicion).toBeGreaterThan(-1);
    expect(boton).toBeGreaterThan(condicion);
    // Y se nombra el POC efímero que sí funciona en la app instalada.
    //
    // El texto ya no está en el componente: vive en el módulo de traducción,
    // porque el paquete declara `es-ES` y `en-US` y una cadena escrita a mano
    // se vería en castellano con el idioma en English. La comprobación se parte
    // en dos —que el componente use la clave, y que la clave diga lo que tiene
    // que decir— que es lo mismo que antes verificaba una sola cadena.
    expect(modal).toContain("ce_efimera_detalle");
    const { certificacion } = await import("../../../context/traducciones/certificacion");
    expect(certificacion.es.ce_efimera_detalle).toContain("identidad efímera");
    expect(certificacion.en.ce_efimera_detalle).toContain("ephemeral identity");
    // Y la salida de devnet se ofrece en los dos idiomas, no sólo en uno.
    expect(certificacion.es.ce_prueba_tecnica).toContain("devnet");
    expect(certificacion.en.ce_prueba_tecnica).toContain("devnet");
  });
});
