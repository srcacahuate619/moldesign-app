import { beforeAll, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ProParametersTab } from "../ProParametersTab";

beforeAll(() => {
  if (!("IntersectionObserver" in globalThis)) {
    Object.assign(globalThis, { IntersectionObserver: class {
      observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
    } });
  }
});

const base = {
  molecular_weight: 180.16, log_p: 1.19, qed: 0.55, sa_score: 1.9,
  blood_viability_score: null, blood_solubility_logs: null, blood_ppb_category: null,
  blood_hia_permeable: null, blood_bbb_permeable: null,
};

function row(label: string) { return screen.getByText(label).parentElement!; }

describe("el contrato de propiedades conserva valores y ausencias", () => {
  it.each([2.3, 0])("lee la clave canónica de LLE: %s", (value) => {
    render(<ProParametersTab result={{ ...base, ligand_lipophilicity_efficiency: value }} />);
    expect(row("LLE")).toHaveTextContent(value.toFixed(2));
  });

  it("null en filtros y PAINS no se representa como fallo ni aprobado", () => {
    render(<ProParametersTab result={{ ...base,
      lipinski_pass: null, veber_pass: null, ghose_pass: null, egan_pass: null,
      muegge_pass: null, muegge_score: null, is_pains: null,
    }} />);
    for (const label of ["Lipinski", "Veber", "Ghose", "Egan", "Muegge", "PAINS"]) {
      expect(within(row(label)).getByText("No registrado")).toBeInTheDocument();
      expect(row(label)).not.toHaveTextContent("✓");
      expect(row(label)).not.toHaveTextContent("✗");
    }
  });

  it("conserva los veredictos registrados true y false", () => {
    render(<ProParametersTab result={{ ...base, lipinski_pass: true, veber_pass: false, is_pains: false }} />);
    expect(row("Lipinski")).toHaveTextContent("✓");
    expect(row("Veber")).toHaveTextContent("✗");
    expect(row("PAINS")).toHaveTextContent("✓");
  });
});
