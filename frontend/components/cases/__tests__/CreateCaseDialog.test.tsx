import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CreateCaseDialog } from "../CreateCaseDialog";

afterEach(() => cleanup());

const POR_DEFECTO = { token: "tok-defecto", displayPath: "C:\\Users\\ana\\Documents\\MolDesign\\Casos" };
const ELEGIDA = { token: "tok-elegida", displayPath: "D:\\Mis casos" };

function montar(extra: Partial<React.ComponentProps<typeof CreateCaseDialog>> = {}) {
  const onCreate = vi.fn().mockResolvedValue(true);
  const onClose = vi.fn();
  render(
    <CreateCaseDialog
      open
      onClose={onClose}
      onCreate={onCreate}
      requiresDirectory
      storageLabel="Navegador"
      onPickDirectory={vi.fn().mockResolvedValue(ELEGIDA)}
      onDefaultDirectory={vi.fn().mockResolvedValue(POR_DEFECTO)}
      {...extra}
    />,
  );
  return { onCreate, onClose };
}

const nombrar = (valor: string) =>
  fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: valor } });
const botonCrear = () => screen.getByRole("button", { name: /^crear/i }) as HTMLButtonElement;

describe("crear un caso con la carpeta por defecto (decisión del 2026-10-04)", () => {
  it("la propuesta aparece sola y basta nombrar el caso: no hay que elegir carpeta", async () => {
    const { onCreate } = montar();
    await screen.findByText(/Documents\\MolDesign\\Casos/);
    expect(screen.getByText("Carpeta por defecto. Puedes cambiarla.")).toBeTruthy();

    nombrar("Inhibición de ACE");
    expect(botonCrear().disabled).toBe(false);
    fireEvent.click(botonCrear());

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    // Crea con el TOKEN de la carpeta por defecto, no con una ruta.
    expect(onCreate).toHaveBeenCalledWith("Inhibición de ACE", expect.any(String), "tok-defecto");
  });

  it("«Cambiar carpeta» deja elegir otra y ésa sustituye a la propuesta", async () => {
    const { onCreate } = montar();
    await screen.findByText(/MolDesign\\Casos/);
    fireEvent.click(screen.getByRole("button", { name: /cambiar carpeta/i }));
    await screen.findByText(/Mis casos/);
    expect(screen.queryByText("Carpeta por defecto. Puedes cambiarla.")).toBeNull();

    nombrar("Serie A");
    fireEvent.click(botonCrear());
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith("Serie A", expect.any(String), "tok-elegida"));
  });

  it("control: sin carpeta por defecto se sigue exigiendo elegir una", async () => {
    montar({ onDefaultDirectory: undefined });
    nombrar("Serie A");
    expect(botonCrear().disabled).toBe(true);
    expect(screen.getByRole("button", { name: /elegir carpeta/i })).toBeTruthy();
  });

  it("si la propuesta falla no se crea «en ningún sitio»: se avisa y se exige elegir", async () => {
    montar({ onDefaultDirectory: vi.fn().mockRejectedValue(new Error("sin Documentos")) });
    await screen.findByText("No se pudo preparar la carpeta por defecto. Elige una carpeta.");
    nombrar("Serie A");
    expect(botonCrear().disabled).toBe(true);
  });

  it("si la carpeta propuesta está dentro de OneDrive, se avisa del riesgo", async () => {
    montar({
      onDefaultDirectory: vi.fn().mockResolvedValue({
        token: "tok-od",
        displayPath: "C:\\Users\\ana\\OneDrive\\Documentos\\MolDesign\\Casos",
      }),
    });
    await screen.findByRole("note");
    expect(screen.getByRole("note").textContent).toMatch(/OneDrive/);
  });

  it("control: una carpeta fuera de OneDrive no lleva ese aviso", async () => {
    montar();
    await screen.findByText(/MolDesign\\Casos/);
    expect(screen.queryByRole("note")).toBeNull();
  });
});
