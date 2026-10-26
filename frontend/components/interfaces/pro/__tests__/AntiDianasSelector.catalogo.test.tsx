import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import { agruparAntiDianas, type AntiDiana } from "@/lib/antiDianas";
import { AntiDianasSelector } from "../AntiDianasSelector";

const idioma = vi.hoisted(() => ({ value: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string) => catalogo[idioma.value][key] ?? key }) }));
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
    expect(demo.getByRole("checkbox", { name: /Bowes/ })).toBeDisabled();
    expect(demo.getByText("Sin estructura")).toBeTruthy();
    fireEvent.click(demo.getByRole("checkbox", { name: /hERG/ }));
    expect(onChange).toHaveBeenCalledWith(["5VA1"]);
    const propias = within(screen.getByRole("region", { name: catalogo[locale].cat_anti_propias }));
    expect(propias.getByRole("checkbox", { name: /Mi anti-diana/ })).toBeEnabled();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "LOCAL" } });
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(propias.getByRole("checkbox", { name: /Mi anti-diana/ })).toBeVisible();
    fireEvent.click(propias.getByRole("button", { name: catalogo[locale].cat_anti_subir }));
    fireEvent.click(screen.getByRole("button", { name: "SUBIDA_ANTI" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
  it("la sección propia vacía sigue visible y la búsqueda abarca ambos grupos", () => {
    render(<AntiDianasSelector targets={rows.slice(0, 2)} selected={[]} onChange={() => {}} catalogo />);
    expect(screen.getByText(catalogo.es.cat_anti_vacio)).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "hERG" } });
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(screen.getByRole("region", { name: "Tus anti-dianas" })).toBeTruthy();
  });
  it("agrupar conserva todas las filas y las referencias originales", () => {
    const grupos = agruparAntiDianas(rows);
    expect(grupos.map((g) => g.targets.length)).toEqual([2, 1]);
    expect(grupos[1].targets[0]).toBe(rows[2]);
  });
});
