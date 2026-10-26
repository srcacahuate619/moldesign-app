import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import { molcy } from "@/context/traducciones/molcy";
import { CatalogoReceptoresMolcy } from "../CatalogoReceptoresMolcy";
import type { Target } from "@/lib/api";
import { verificacionDePrueba } from "@/lib/__tests__/fixtures/verificacionReceptor";
import { intentoPublicado } from "@/lib/__tests__/fixtures/intentoPublicado";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en", catalogo: vi.fn<() => readonly Target[] | null>(() => null) }));

vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string, params: Record<string, string | number> = {}) => Object.entries(params).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, String(v)), catalogo[mocks.locale][key] ?? molcy[mocks.locale][key] ?? key) }) }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: mocks.catalogo }));
beforeEach(() => { mocks.locale = "es"; mocks.catalogo.mockReturnValue(null); });

describe("selector de receptores de Molcy", () => {
  it.each(["es", "en"] as const)("muestra el intento publicado y la tarjeta de demostración al buscar en %s", (locale) => {
    mocks.locale = locale;
    mocks.catalogo.mockReturnValue([{ pdb_id: "8HFI", name: "Transportador", intentos_verificacion: [intentoPublicado] } as Target]);
    const onSelect = vi.fn();
    render(<CatalogoReceptoresMolcy sources={[{ id: "8HFI", nombre: "Transportador", disponible: true, motivo: null }]} selected="" onSelect={onSelect} onUpload={() => {}} />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "8HFI" } });
    expect(screen.getAllByRole("tab").map(tab => tab.textContent)).toEqual(locale === "es" ? ["Demostración", "Verificados", "Mis Receptores"] : ["Demo", "Verified", "My receptors"]);
    const demo = within(screen.getByRole("region", { name: locale === "es" ? "Demostración" : "Demo" }));
    expect(demo.getByText(catalogo[locale].cat_intento_compacto)).toBeVisible();
    expect(demo.queryByText(locale === "es" ? "Verificado" : "Verified", { exact: true })).toBeNull();
    fireEvent.click(demo.getByRole("button", { name: "Transportador · 8HFI" }));
    expect(onSelect).toHaveBeenCalledWith("8HFI");
    fireEvent.click(screen.getByRole("tab", { name: locale === "es" ? "Verificados" : "Verified" }));
    const attempts = screen.getByRole("region", { name: locale === "es" ? "Intentos publicados" : "Published attempts" });
    expect(within(attempts).getByText(/ρ = 0.13.*n = 57/)).toBeVisible();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "ausente" } });
    expect(screen.queryByRole("region", { name: locale === "es" ? "Intentos publicados" : "Published attempts" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Transportador · 8HFI" })).toBeNull();
  });
  it("agrupa las fuentes antiguas, conserva su disponibilidad y abre la subida existente", () => {
    const onSelect = vi.fn(), onUpload = vi.fn();
    render(<CatalogoReceptoresMolcy sources={[
      { id: "1AAA", nombre: "Incluido", disponible: true, motivo: null },
      { id: "LOCAL", nombre: "Propio", propio: true, disponible: true, motivo: null },
      { id: "2BBB", nombre: "Ausente", disponible: false, motivo: "Sin estructura local" },
    ]} selected="" onSelect={onSelect} onUpload={onUpload} />);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Demostración"]);
    expect(screen.getByRole("tab", { name: "Demostración" })).toHaveAttribute("aria-selected", "true");
    const demo = within(screen.getByRole("region", { name: "Demostración" }));
    fireEvent.click(demo.getByRole("button", { name: "Incluido · 1AAA" }));
    expect(onSelect).toHaveBeenCalledWith("1AAA");
    expect(demo.getByRole("button", { name: "Ausente · 2BBB" })).toBeDisabled();
    expect(demo.getAllByText("Demostración")).toHaveLength(1);
    expect(demo.getByText("Demostración").tagName).toBe("H3");
    fireEvent.click(screen.getByRole("tab", { name: "Verificados" }));
    expect(screen.getByText(/Todavía no hay receptores verificados/)).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Mis Receptores" }));
    fireEvent.click(screen.getByRole("button", { name: "Subir receptor" }));
    expect(onUpload).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "LOCAL" } });
    expect(screen.getByRole("button", { name: "Propio · LOCAL" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Incluido · 1AAA" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Demostración" }));
    expect(screen.getByRole("status")).toHaveTextContent("Hay coincidencias en: Mis Receptores.");
    expect(screen.getByRole("searchbox")).toHaveValue("LOCAL");
  });
  it("el sello completo del selector de Molcy conserva las cifras y condiciones al buscar", () => {
    mocks.catalogo.mockReturnValue([{ pdb_id: "8HFI", seccion_catalogo: "verificado", verificacion: verificacionDePrueba } as Target]);
    render(<CatalogoReceptoresMolcy sources={[{ id: "8HFI", nombre: "Transportador", disponible: true, motivo: null }]} selected="" onSelect={() => {}} onUpload={() => {}} />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "8HFI" } });
    fireEvent.click(screen.getByRole("tab", { name: "Verificados" }));
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Verificados"]);
    const section = within(screen.getByRole("region", { name: "Verificados" }));
    expect(section.getByText(/ρ = 0.41/)).toBeVisible();
    expect(section.getByText(/Medido con exhaustividad 8, 9 poses y semilla 42/)).toBeVisible();
    expect(section.getByText(catalogo.es.cat_cond_serie)).toBeVisible();
  });
  it("permite cambiar de sección con el teclado y enfoca la pestaña activa", () => {
    render(<CatalogoReceptoresMolcy sources={[]} selected="" onSelect={() => {}} onUpload={() => {}} />);
    const demo = screen.getByRole("tab", { name: "Demostración" });
    const verified = screen.getByRole("tab", { name: "Verificados" });
    const own = screen.getByRole("tab", { name: "Mis Receptores" });
    fireEvent.keyDown(demo, { key: "ArrowRight" });
    expect(verified).toHaveFocus();
    expect(verified).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(verified, { key: "End" });
    expect(own).toHaveFocus();
    fireEvent.keyDown(own, { key: "ArrowRight" });
    expect(demo).toHaveFocus();
    fireEvent.keyDown(demo, { key: "ArrowLeft" });
    expect(own).toHaveFocus();
    fireEvent.keyDown(own, { key: "Home" });
    expect(demo).toHaveFocus();
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
  });
});
