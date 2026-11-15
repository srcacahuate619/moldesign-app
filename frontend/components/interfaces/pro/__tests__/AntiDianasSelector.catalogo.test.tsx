import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import { paneles } from "@/context/traducciones/paneles";
import { agruparAntiDianas, type AntiDiana } from "@/lib/antiDianas";
import { AntiDianasSelector } from "../AntiDianasSelector";

const idioma = vi.hoisted(() => ({ value: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string) => paneles[idioma.value][key] ?? catalogo[idioma.value][key] ?? key }) }));
vi.mock("../CustomReceptorModal", () => ({ CustomReceptorModal: ({ antiDiana, onSuccess }: { antiDiana?: boolean; onSuccess: () => void }) => <button onClick={onSuccess}>{antiDiana ? "SUBIDA_ANTI" : "SUBIDA_RECEPTOR"}</button> }));
const rows: AntiDiana[] = [
  { pdb_id: "5VA1", name: "hERG", category: "Canales", source: "builtin", por_defecto: true, disponible: true },
  { pdb_id: "2BBB", name: "Bowes", category: "Bowes 2012 · GPCR", source: "bowes", disponible: false, motivo_no_disponible: "Sin estructura" },
  { pdb_id: "LOCAL", name: "Mi anti-diana", category: "Custom", source: "user", disponible: true },
];
beforeEach(() => { idioma.value = "es"; });

describe("panel de demostración y anti-dianas propias", () => {
  it.each(["es", "en"] as const)("traduce las familias Bowes sin cambiar la selección en %s", locale => {
    idioma.value = locale;
    const onChange = vi.fn();
    const targets: AntiDiana[] = [
      { pdb_id: "ENZ", name: "COX", category: "Bowes 2012 · Enzima", disponible: true },
      { pdb_id: "KIN", name: "Lck", category: "Bowes 2012 · Quinasa", disponible: true },
      { pdb_id: "NUC", name: "AR", category: "Bowes 2012 · Receptor nuclear", disponible: true },
    ];
    render(<AntiDianasSelector targets={targets} selected={[]} onChange={onChange} catalogo />);
    for (const key of ["cat_familia_enzima", "cat_familia_kinasa", "cat_familia_nuclear"]) expect(screen.getByRole("group", {name:`${catalogo[locale][key]} · 0/1`})).toBeVisible();
    fireEvent.change(screen.getByRole("searchbox"), {target:{value:catalogo[locale].cat_familia_enzima}});
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(["ENZ"]);
  });
  it.each(["es", "en"] as const)("mantiene los dos grupos, estados y selección en %s", (locale) => {
    idioma.value = locale;
    const onChange = vi.fn(), retry = vi.fn();
    render(<AntiDianasSelector targets={rows} selected={[]} onChange={onChange} onRetry={retry} catalogo />);
    expect(screen.getAllByRole("heading", { level: 4 }).map((h) => h.textContent)).toEqual([catalogo[locale].cat_anti_panel, catalogo[locale].cat_anti_propias]);
    const demo = within(screen.getByRole("region", { name: catalogo[locale].cat_anti_panel }));
    // Lo que no se puede elegir no se lista ni se cuenta en el catálogo.
    expect(demo.queryByRole("checkbox", { name: /Bowes/ })).toBeNull();
    expect(screen.queryByText("Sin estructura")).toBeNull();
    fireEvent.click(demo.getByRole("checkbox", { name: /hERG/ }));
    expect(onChange).toHaveBeenCalledWith(["5VA1"]);
    const propias = within(screen.getByRole("region", { name: catalogo[locale].cat_anti_propias }));
    expect(propias.getByRole("checkbox", { name: /Mi anti-diana/ })).toBeEnabled();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "LOCAL" } });
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(propias.getByRole("checkbox", { name: /Mi anti-diana/ })).toBeVisible();
    // «Subir anti-diana» vive junto a «Evaluar seleccionadas», no en el catálogo.
    expect(screen.queryByRole("button", { name: catalogo[locale].cat_anti_subir })).toBeNull();
    expect(retry).not.toHaveBeenCalled();
  });
  it("sin anti-dianas propias, el catálogo no enseña esa sección; la búsqueda sigue funcionando", () => {
    render(<AntiDianasSelector targets={rows.slice(0, 2)} selected={[]} onChange={() => {}} catalogo />);
    expect(screen.queryByText(catalogo.es.cat_anti_vacio)).toBeNull();
    expect(screen.queryByRole("region", { name: "Tus anti-dianas" })).toBeNull();
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "hERG" } });
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  });
  it("fuera del catálogo (parámetros de la evaluación) conserva el botón de subir", () => {
    render(<AntiDianasSelector targets={rows.slice(0, 2)} selected={[]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: catalogo.es.cat_anti_subir })).toBeTruthy();
  });
  it.each(["es", "en"] as const)("la acción ninguna vacía la selección aunque cambie su etiqueta en %s", (locale) => {
    idioma.value = locale;
    const onChange = vi.fn();
    render(<AntiDianasSelector targets={rows} selected={["5VA1"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: paneles[locale].pn_ninguna }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("agrupar conserva todas las filas y las referencias originales", () => {
    const grupos = agruparAntiDianas(rows);
    expect(grupos.map((g) => g.targets.length)).toEqual([2, 1]);
    expect(grupos[1].targets[0]).toBe(rows[2]);
  });
});
