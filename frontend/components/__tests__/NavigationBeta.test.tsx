import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("next/image", () => ({
  // eslint-disable-next-line @next/next/no-img-element
  default: ({ alt }: { alt: string }) => <img alt={alt} />,
}));
vi.mock("../../lib/auth", () => ({ useAuth: () => ({ user: null, logout: () => {} }) }));
vi.mock("../ui/OptionsMenu", () => ({ OptionsMenu: () => null }));
vi.mock("../DownloadNotifications", () => ({ DownloadNotifications: () => null }));
vi.mock("../NativeJobNotifications", () => ({ NativeJobNotifications: () => null }));

import { Navigation } from "../Navigation";

/**
 * Molcy sale visible pero marcada «Beta» (decisión del propietario, 2026-10-04): depende de Blender, que es un
 * programa externo, y su funcionamiento no está certificado en una máquina limpia.
 */
describe("navegación: Molcy es Beta", () => {
  it("el enlace de Molcy lleva la marca Beta y es un enlace, no una pestaña oculta", () => {
    render(<Navigation />);
    const enlace = screen.getByRole("link", { name: /^Molcy\s*Beta$/i });
    expect(enlace).toHaveAttribute("href", "/molcy");
    expect(within(enlace).getByTestId("pildora-beta")).toBeTruthy();
  });

  it("sólo Molcy: ningún otro enlace de la barra lleva la marca (control)", () => {
    render(<Navigation />);
    expect(screen.getAllByTestId("pildora-beta")).toHaveLength(1);
    const preparacion = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/preparacion");
    expect(preparacion && within(preparacion).queryByTestId("pildora-beta")).toBeNull();
  });

  it("en el menú móvil también va marcada", () => {
    render(<Navigation />);
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    expect(screen.getAllByTestId("pildora-beta")).toHaveLength(2);
  });

  it("los botones del menú móvil tienen nombre accesible (antes eran sólo un icono)", () => {
    render(<Navigation />);
    const abrir = screen.getByRole("button", { name: "Abrir menú" });
    expect(abrir).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(abrir);
    expect(screen.getAllByRole("button", { name: "Cerrar menú" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole("button", { name: "Cerrar menú" })[0]).toHaveAttribute("aria-expanded", "true");
  });

  it("el nombre de usuario no se enseña por debajo de 1440 px, donde él o la campana pisaban a «Historial»", () => {
    // Medido en el export: a 1024 px «HISTORIAL» y el nombre se solapaban 20 px. Con «USUARIO DE ESCRITORIO»
    // (castellano, sin sesión) también a 1100 px, 63 px, y con el nombre visible la campana pisaba «HISTORIAL»
    // hasta 1360 px (2026-10-10). Desde 1380 px, nada; 1440 deja margen.
    render(<Navigation />);
    const nombre = screen.getByText("Usuario de escritorio");
    expect(nombre.className).toContain("min-[1440px]:inline");
    expect(nombre.className).not.toMatch(/min-\[1(100|280)px\]:inline/);
    expect(nombre.className).not.toMatch(/(^|\s)sm:inline/);
    expect(nombre.className).toContain("hidden");
  });
});
