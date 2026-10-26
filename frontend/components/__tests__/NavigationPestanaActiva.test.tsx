import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ruta = vi.hoisted(() => ({ actual: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => ruta.actual }));
vi.mock("next/image", () => ({
  // eslint-disable-next-line @next/next/no-img-element
  default: ({ alt }: { alt: string }) => <img alt={alt} />,
}));
vi.mock("../../lib/auth", () => ({ useAuth: () => ({ user: null, logout: () => {} }) }));
vi.mock("../ui/OptionsMenu", () => ({ OptionsMenu: () => null }));
vi.mock("../DownloadNotifications", () => ({ DownloadNotifications: () => null }));
vi.mock("../NativeJobNotifications", () => ({ NativeJobNotifications: () => null }));

import { Navigation, pestanaActiva } from "../Navigation";

/**
 * La barra dice en qué pestaña está el usuario (decisión del propietario, 2026-10-10): la activa va sombreada con el
 * acento y lleva `aria-current="page"`; el logo se ilumina en Inicio. Antes sólo cambiaba el grosor de la letra.
 */
function enlacesDeLaBarra() {
  // El menú móvil está cerrado: los enlaces visibles son los de la barra (más «Entrar»).
  return screen.getAllByRole("link");
}

function enlace(href: string) {
  const encontrado = enlacesDeLaBarra().find((a) => a.getAttribute("href") === href);
  if (!encontrado) throw new Error(`sin enlace a ${href}`);
  return encontrado;
}

describe("navegación: pestaña activa", () => {
  beforeEach(() => {
    ruta.actual = "/";
  });

  it("cada ruta ilumina su pestaña; Batch no enciende Evaluación aunque cuelgue de /evaluation", () => {
    expect(pestanaActiva("/")).toBe("inicio");
    expect(pestanaActiva("/evaluation")).toBe("evaluation");
    expect(pestanaActiva("/evaluation/")).toBe("evaluation");
    expect(pestanaActiva("/evaluation/batch")).toBe("batch");
    expect(pestanaActiva("/preparacion")).toBe("preparacion");
    expect(pestanaActiva("/molcy")).toBe("molcy");
    expect(pestanaActiva("/moldex/MOL-1")).toBe("moldex");
    expect(pestanaActiva("/history")).toBe("history");
    // Páginas que no son pestañas de la barra: ninguna se ilumina.
    expect(pestanaActiva("/login")).toBeNull();
    expect(pestanaActiva("/ciencia")).toBeNull();
    expect(pestanaActiva("/molcyx")).toBeNull();
  });

  it.each([
    ["/preparacion", "/preparacion"],
    ["/molcy", "/molcy"],
    ["/evaluation/batch", "/evaluation/batch"],
    ["/evaluation", "/evaluation"],
    ["/moldex", "/moldex"],
    ["/history", "/history"],
  ])("en %s sólo esa pestaña va marcada y sombreada", (actual, href) => {
    ruta.actual = actual;
    render(<Navigation />);
    const marcados = enlacesDeLaBarra().filter((a) => a.getAttribute("aria-current") === "page");
    expect(marcados.map((a) => a.getAttribute("href"))).toEqual([href]);
    expect(enlace(href).className).toContain("bg-accent-strong/15");
    expect(enlace(href).className).toContain("ring-accent-strong/50");
    for (const otro of enlacesDeLaBarra().filter((a) => a !== enlace(href))) {
      expect(otro.className, otro.getAttribute("href") ?? "").not.toContain("bg-accent-strong/15");
    }
  });

  it("en Inicio se ilumina el logo y ninguna pestaña de texto", () => {
    render(<Navigation />);
    const logo = enlace("/");
    expect(logo).toHaveAttribute("aria-current", "page");
    expect(logo.className).toContain("ring-accent-strong/40");
    expect(enlacesDeLaBarra().filter((a) => a.getAttribute("aria-current") === "page")).toEqual([logo]);
  });

  it("fuera de Inicio el logo no va iluminado", () => {
    ruta.actual = "/moldex";
    render(<Navigation />);
    expect(enlace("/")).not.toHaveAttribute("aria-current");
    expect(enlace("/").className).not.toContain("ring-accent-strong/40");
  });

  it("en el menú móvil también se marca dónde está el usuario", () => {
    ruta.actual = "/history";
    render(<Navigation />);
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    const historial = screen.getAllByRole("link").filter((a) => a.getAttribute("href") === "/history");
    expect(historial).toHaveLength(2);
    for (const a of historial) expect(a).toHaveAttribute("aria-current", "page");
    const evaluacion = screen.getAllByRole("link").filter((a) => a.getAttribute("href") === "/evaluation");
    for (const a of evaluacion) expect(a).not.toHaveAttribute("aria-current");
  });
});
