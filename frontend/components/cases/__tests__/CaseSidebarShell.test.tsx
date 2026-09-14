/**
 * El panel de casos se pliega, se estira y lo recuerda.
 *
 * POR QUÉ EXISTE. Medido a 1440×900, el panel ocupaba 272 px fijos —el 19% del
 * ancho— y enfrente el editor químico y el visor 3D se reparten lo que sobra.
 *
 * Lo que estas pruebas vigilan es que plegar no sea una trampa: que quede
 * siempre una salida visible, que la preferencia sobreviva, y que estirar
 * tenga límites (un panel de 1 200 px deja la evaluación inservible, y uno de
 * 40 px no se puede volver a agarrar).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ANCHO_MAXIMO,
  ANCHO_MINIMO,
  ANCHO_PLEGADO,
  ANCHO_POR_DEFECTO,
  CaseSidebarShell,
} from "../CaseSidebarShell";

function panel(onCollapse?: () => void) {
  return (
    <nav aria-label="Casos">
      <button type="button" onClick={onCollapse}>
        Ocultar el panel de casos
      </button>
      <span>contenido del panel</span>
    </nav>
  );
}

function montar(props: Partial<React.ComponentProps<typeof CaseSidebarShell>> = {}) {
  return render(
    <CaseSidebarShell totalCasos={3} onCreate={() => {}} {...props}>
      {({ plegar }) => panel(plegar)}
    </CaseSidebarShell>,
  );
}

/** El contenedor externo, que es quien lleva el ancho. */
function contenedor(): HTMLElement {
  const nodo = document.querySelector(".relative.hidden.shrink-0");
  if (!(nodo instanceof HTMLElement)) throw new Error("no encuentro el contenedor del panel");
  return nodo;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("panel de casos plegable", () => {
  it("arranca desplegado y con el ancho por defecto", () => {
    montar();
    expect(screen.getByText("contenido del panel")).toBeInTheDocument();
    expect(contenedor().style.width).toBe(`${ANCHO_POR_DEFECTO}px`);
  });

  it("plegar deja el raíl y una salida visible, no un panel desaparecido", () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: "Ocultar el panel de casos" }));

    expect(screen.queryByText("contenido del panel")).not.toBeInTheDocument();
    expect(contenedor().style.width).toBe(`${ANCHO_PLEGADO}px`);
    // La salida: un panel que se esfuma sin rastro obliga a buscar cómo
    // recuperarlo, y esa búsqueda cuesta más que los 48 px que ahorra.
    expect(screen.getByRole("button", { name: "Mostrar el panel de casos" })).toBeInTheDocument();
  });

  it("plegado sigue informando: el número de casos y crear uno nuevo", () => {
    const onCreate = vi.fn();
    montar({ onCreate, totalCasos: 7 });
    fireEvent.click(screen.getByRole("button", { name: "Ocultar el panel de casos" }));

    expect(screen.getByText("7")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Crear un caso" }));
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it("con trabajo vivo, crear desde el raíl está bloqueado y dice por qué", () => {
    const onCreate = vi.fn();
    montar({
      onCreate,
      createDisabled: true,
      createDisabledReason: "Hay trabajo en curso en este caso.",
    });
    fireEvent.click(screen.getByRole("button", { name: "Ocultar el panel de casos" }));

    const crear = screen.getByRole("button", { name: "Crear un caso" });
    expect(crear).toBeDisabled();
    expect(crear).toHaveAttribute("title", "Hay trabajo en curso en este caso.");
    fireEvent.click(crear);
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("la preferencia de plegado sobrevive a volver a montar", () => {
    const primero = montar();
    fireEvent.click(screen.getByRole("button", { name: "Ocultar el panel de casos" }));
    primero.unmount();

    montar();
    expect(screen.getByRole("button", { name: "Mostrar el panel de casos" })).toBeInTheDocument();
    expect(contenedor().style.width).toBe(`${ANCHO_PLEGADO}px`);
  });

  it("el ancho guardado se recupera, acotado a los límites", () => {
    window.localStorage.setItem("moldesign_casos_ancho", "360");
    montar();
    expect(contenedor().style.width).toBe("360px");
  });

  it("un ancho guardado absurdo NO se aplica tal cual", () => {
    // Un valor fuera de rango puede venir de una versión anterior o de alguien
    // editando el almacenamiento. Se acota, no se obedece.
    window.localStorage.setItem("moldesign_casos_ancho", "5000");
    const grande = montar();
    expect(contenedor().style.width).toBe(`${ANCHO_MAXIMO}px`);
    grande.unmount();

    window.localStorage.setItem("moldesign_casos_ancho", "12");
    montar();
    expect(contenedor().style.width).toBe(`${ANCHO_MINIMO}px`);
  });

  it("el teclado redimensiona, y no sólo el ratón", () => {
    montar();
    const tirador = screen.getByRole("separator", { name: "Ancho del panel de casos" });

    fireEvent.keyDown(tirador, { key: "ArrowRight" });
    expect(contenedor().style.width).toBe(`${ANCHO_POR_DEFECTO + 16}px`);

    fireEvent.keyDown(tirador, { key: "ArrowLeft", shiftKey: true });
    expect(contenedor().style.width).toBe(`${ANCHO_POR_DEFECTO + 16 - 48}px`);

    fireEvent.keyDown(tirador, { key: "End" });
    expect(contenedor().style.width).toBe(`${ANCHO_MAXIMO}px`);

    fireEvent.keyDown(tirador, { key: "Home" });
    expect(contenedor().style.width).toBe(`${ANCHO_MINIMO}px`);
  });

  it("el tirador anuncia su rango a un lector de pantalla", () => {
    montar();
    const tirador = screen.getByRole("separator", { name: "Ancho del panel de casos" });
    expect(tirador).toHaveAttribute("aria-valuemin", String(ANCHO_MINIMO));
    expect(tirador).toHaveAttribute("aria-valuemax", String(ANCHO_MAXIMO));
    expect(tirador).toHaveAttribute("aria-valuenow", String(ANCHO_POR_DEFECTO));
  });

  it("un almacenamiento que lanza no impide usar el panel", () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("almacenamiento bloqueado");
    };
    try {
      montar();
      // No lanza: la preferencia se pierde, el panel sigue funcionando.
      fireEvent.click(screen.getByRole("button", { name: "Ocultar el panel de casos" }));
      expect(screen.getByRole("button", { name: "Mostrar el panel de casos" })).toBeInTheDocument();
    } finally {
      Storage.prototype.setItem = original;
    }
  });
});
