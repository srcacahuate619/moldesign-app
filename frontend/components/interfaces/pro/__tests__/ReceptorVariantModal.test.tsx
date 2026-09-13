import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTargetVariant, type Target } from "../../../../lib/api";
import { ReceptorVariantModal } from "../ReceptorVariantModal";

vi.mock("../../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../../lib/api")>("../../../../lib/api");
  return { ...actual, createTargetVariant: vi.fn() };
});

const parent: Target = {
  id: "parent-id",
  pdb_id: "1ABC",
  name: "Receptor fuente",
  organism: "Homo sapiens",
  resolution: 2.1,
  chain: "A",
  requires_cns: false,
  is_hot: false,
  spearman_rho: null,
  calibration_date: null,
  grid_center_x: 1,
  grid_center_y: 2,
  grid_center_z: 3,
  grid_size_x: 20,
  grid_size_y: 21,
  grid_size_z: 22,
  cofactors_whitelist: ["ZN"],
};

describe("variante versionada de receptor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("crea una variante privada sin editar el receptor padre", async () => {
    const created = {
      ...parent,
      pdb_id: "USR_123456",
      name: "Receptor fuente · variante",
      preparation_parent_id: "parent-id",
      prepared_receptor_sha256: "a".repeat(64),
    };
    vi.mocked(createTargetVariant).mockResolvedValue(created);
    const onSuccess = vi.fn();

    render(<ReceptorVariantModal parent={parent} onClose={vi.fn()} onSuccess={onSuccess} />);

    expect(screen.getByText(/el original no cambia/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/metales y cofactores/i), {
      target: { value: "ZN, HEM" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^crear variante$/i }));

    await waitFor(() => expect(createTargetVariant).toHaveBeenCalledWith("1ABC", {
      name: "Receptor fuente · variante",
      chain_id: "A",
      grid_center: [1, 2, 3],
      grid_size: [20, 21, 22],
      cofactors_whitelist: ["ZN", "HEM"],
    }));
    expect(onSuccess).toHaveBeenCalledWith(created);
  });

  it("no envía una caja fuera del dominio permitido", () => {
    render(<ReceptorVariantModal parent={parent} onClose={vi.fn()} onSuccess={vi.fn()} />);

    const sizeInputs = screen.getAllByRole("spinbutton").slice(3);
    fireEvent.change(sizeInputs[0], { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /^crear variante$/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/entre 5 y 80/i);
    expect(createTargetVariant).not.toHaveBeenCalled();
  });
});
