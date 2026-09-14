/**
 * ADMET-AI se puede pedir DESPUÉS de acoplar.
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * POR QUÉ EXISTE ESTA PUERTA
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * ADMET-AI es opt-in y la decisión se toma en Opciones avanzadas ANTES de
 * ejecutar. Quien no lo marcó se quedaba sin perfil para siempre: la única
 * forma de obtenerlo era volver a acoplar la molécula entera —minutos de
 * Vina— para recalcular algo que **sólo depende del SMILES**.
 *
 * Es el mismo trato que ya tenía MM-GBSA: un módulo caro que se pide después,
 * sobre una corrida que ya existe.
 *
 * Lo que estas pruebas fijan:
 *
 * 1. La pestaña existe junto a Selectividad y MM-GBSA, que es donde el usuario
 *    va a buscarla.
 * 2. Sin `moleculeId` no se puede pedir, y se explica por qué.
 * 3. Si ya hay perfil, el botón no invita a repetir un cálculo caro.
 * 4. **Un perfil que no se guardó se dice.** El backend puede calcular y fallar
 *    al persistir; entonces el usuario lo ve en pantalla y el dossier no lo
 *    incluiría. Callarlo sería peor que no calcularlo.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("../ProParametersTab", () => ({ ProParametersTab: () => <div>parámetros reales</div> }));
vi.mock("../ProAlertsTab", () => ({ ProAlertsTab: () => <div>alertas reales</div> }));
vi.mock("../ProXaiTab", () => ({ ProXaiTab: () => <div>explicabilidad real</div> }));
vi.mock("../ProSelectivityPanel", () => ({ ProSelectivityPanel: () => <div>selectividad real</div> }));
vi.mock("../ProSarTab", () => ({ ProSarTab: () => <div>SAR existente</div> }));
vi.mock("../ProDockingTab", () => ({ ProDockingTab: () => <div>poses y hotspots</div> }));
vi.mock("../StructuralEvidencePanel", () => ({
  PosePhysicalDetails: () => <div>detalle físico</div>,
  StructuralEvidencePanel: () => <div>expediente estructural</div>,
}));

import { ProAnalysisTabs } from "../ProAnalysisTabs";

const RESULT_SIN_ADMET = {
  docking_poses: [{ rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 }],
  blood_viability_score: null,
};

function abrirPostDocking(props: Record<string, unknown> = {}) {
  render(
    <ProAnalysisTabs
      status={{ result: RESULT_SIN_ADMET } as never}
      selectivityResult={null}
      moleculeId="mol-1"
      {...props}
    />,
  );
  fireEvent.click(screen.getByRole("tab", { name: /Análisis avanzado/ }));
  fireEvent.click(screen.getByRole("tab", { name: /ADMET/ }));
}

describe("ADMET post-docking", () => {
  it("la pestaña vive junto a Selectividad y MM-GBSA", () => {
    render(
      <ProAnalysisTabs
        status={{ result: RESULT_SIN_ADMET } as never}
        selectivityResult={null}
        moleculeId="mol-1"
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /Análisis avanzado/ }));

    // El sitio importa: es donde el usuario ya va a buscar lo post-docking.
    const etiquetas = screen
      .getAllByRole("tab")
      .map((t) => t.textContent ?? "")
      .filter((t) => /Selectividad|MM-GBSA|ADMET|SAR|Explicabilidad/.test(t));
    expect(etiquetas.some((t) => t.includes("ADMET"))).toBe(true);
    expect(etiquetas.some((t) => t.includes("MM-GBSA"))).toBe(true);
    expect(etiquetas.some((t) => t.includes("Selectividad"))).toBe(true);
  });

  it("pide el cálculo y dice que sólo depende del SMILES", () => {
    const onRequestAdmet = vi.fn();
    abrirPostDocking({ onRequestAdmet });

    // La frase que justifica que exista esta puerta: no hace falta re-acoplar.
    expect(screen.getByText(/sólo del SMILES/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Calcular ADMET/i }));
    expect(onRequestAdmet).toHaveBeenCalledTimes(1);
  });

  it("advierte que son predicciones, no mediciones", () => {
    abrirPostDocking({ onRequestAdmet: vi.fn() });
    // La misma advertencia que lleva el interruptor de Opciones: el sitio donde
    // alguien pulsa el botón es donde tiene que leerla.
    expect(screen.getByText(/predicciones de un modelo, no mediciones/i)).toBeInTheDocument();
  });

  it("sin molécula identificable no se puede pedir, y lo explica", () => {
    const onRequestAdmet = vi.fn();
    render(
      <ProAnalysisTabs
        status={{ result: RESULT_SIN_ADMET } as never}
        selectivityResult={null}
        moleculeId={null}
        onRequestAdmet={onRequestAdmet}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /Análisis avanzado/ }));
    fireEvent.click(screen.getByRole("tab", { name: /ADMET/ }));

    expect(screen.getByRole("button", { name: /Calcular ADMET/i })).toBeDisabled();
    expect(screen.getByText(/Requiere una corrida terminada/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Calcular ADMET/i }));
    expect(onRequestAdmet).not.toHaveBeenCalled();
  });

  it("mientras calcula no acepta otra petición", () => {
    const onRequestAdmet = vi.fn();
    abrirPostDocking({ onRequestAdmet, admetRunning: true });

    const boton = screen.getByRole("button", { name: /Calculando/i });
    expect(boton).toBeDisabled();
    fireEvent.click(boton);
    expect(onRequestAdmet).not.toHaveBeenCalled();
  });

  it("con perfil ya calculado no invita a repetir un cálculo caro", () => {
    abrirPostDocking({ onRequestAdmet: vi.fn(), admetDone: true });

    expect(screen.getByRole("button", { name: /ADMET disponible/i })).toBeDisabled();
    expect(screen.getByText(/aparece en/i)).toBeInTheDocument();
  });

  it("un perfil del PIPELINE ya cuenta como calculado", () => {
    // Quien sí marcó ADMET en Opciones no tiene que volver a pedirlo aquí.
    render(
      <ProAnalysisTabs
        status={{ result: { ...RESULT_SIN_ADMET, blood_viability_score: 82.4 } } as never}
        selectivityResult={null}
        moleculeId="mol-1"
        onRequestAdmet={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /Análisis avanzado/ }));
    const pestana = screen.getByRole("tab", { name: /ADMET/ });
    // El punto verde del selector dice «este panel tiene resultado».
    expect(pestana.getAttribute("aria-label")).toMatch(/con resultado/);
  });

  it("SI SE CALCULÓ PERO NO SE GUARDÓ, se dice", () => {
    // El caso que convierte un número en un número no fiable: el usuario lo ve
    // y el dossier no lo incluiría. Callarlo sería peor que no calcularlo.
    abrirPostDocking({
      onRequestAdmet: vi.fn(),
      admetDone: true,
      admetError: "El perfil se calculó pero NO se pudo guardar: el dossier de esta corrida no lo incluirá.",
    });

    const aviso = screen.getByRole("alert");
    expect(aviso).toHaveTextContent(/NO se pudo guardar/i);
    // Y entonces NO se anuncia que viaja en el dossier.
    expect(screen.queryByText(/viaja en el dossier/i)).not.toBeInTheDocument();
  });
});
