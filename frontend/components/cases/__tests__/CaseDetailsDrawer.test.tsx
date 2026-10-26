// =====================================================================
// «Detalles del caso» (RESULTS.md §5.6, 1.0.3): Escape cierra el panel y la X no queda bajo la barra de navegación.
// =====================================================================
//
// El manejador de Escape estaba en el contenedor: sólo lo recibía con el foco dentro del panel. Con el foco fuera
// (p. ej. tras un clic en el fondo o en otra zona de la página), Escape no hacía nada. Ahora lo escucha el documento
// mientras el panel está abierto. La barra de navegación (z-[100]) tapaba la cabecera del panel: el panel empieza
// debajo de ella, a 57 px.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { CaseDetailsDrawer } from "../CaseDetailsDrawer";
import type { CaseContext } from "../../../lib/cases/types";

afterEach(cleanup);

function abrir(open = true) {
  const onClose = vi.fn();
  render(
    <CaseDetailsDrawer
      id="detalles-caso"
      open={open}
      onClose={onClose}
      context={{} as CaseContext}
      saveState="idle"
      onChange={vi.fn()}
    />,
  );
  return onClose;
}

describe("Detalles del caso: cierre con Escape", () => {
  it("Escape cierra aunque el foco esté fuera del panel", () => {
    const onClose = abrir();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("con el foco dentro, Escape cierra una sola vez", () => {
    const onClose = abrir();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("con el panel cerrado, Escape no hace nada", () => {
    const onClose = abrir(false);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("el panel empieza debajo de la barra de navegación (57 px), no la tapa", () => {
    abrir();
    const contenedor = screen.getByRole("dialog").parentElement;
    expect(contenedor).toHaveClass("top-[57px]");
  });
});
