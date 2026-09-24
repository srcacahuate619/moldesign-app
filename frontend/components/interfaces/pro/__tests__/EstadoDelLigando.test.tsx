import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EstadoDelLigando } from "../EstadoDelLigando";
import type { EvaluationResult } from "../../../../lib/types";

/** Sólo `ligand_state` importa aquí; el resto del contrato no se toca. */
type ResultadoParcial = Pick<EvaluationResult, "ligand_state">;
const comoResultado = (parcial: ResultadoParcial) => parcial as EvaluationResult;

// ─────────────────────────────────────────────────────────────────────────
// El backend ya registraba que tautomero eligio RDKit y que estado de
// protonacion produjo dimorphite-dl a pH 7.4, y emitia un aviso cuando la
// especie cambiaba. Pero en pantalla el usuario seguia viendo UNICAMENTE el
// SMILES que escribio, y los descriptores —MW, LogP, TPSA— se calculan sobre
// esa forma neutra.
//
// Medido sobre el interprete empaquetado:
//
//     escrito                          acoplado                carga
//     CC(=O)Oc1ccccc1C(=O)O            …C(=O)[O-]                −1
//     CN(C)CCOC(c1ccccc1)c1ccccc1      …[NH+](C)C…               +1
//
// La aspirina se acopla como anion y la difenhidramina como cation, y las dos
// aparecian neutras en pantalla.
// ─────────────────────────────────────────────────────────────────────────

const ASPIRINA = {
  ligand_state: {
    smiles_entrada: "CC(=O)Oc1ccccc1C(=O)O",
    smiles_acoplado: "CC(=O)Oc1ccccc1C(=O)[O-]",
    cambio_respecto_a_la_entrada: true,
    carga_formal_neta: -1,
    formula_acoplada: "C9H7O4-",
    tautomeria: { aplicada: true, motor: "RDKit", alternativas: 2, motivo: null },
    protonacion: { aplicada: true, motor: "dimorphite-dl", ph: 7.4, alternativas: 1, motivo: null },
  },
} satisfies ResultadoParcial;

const CAFEINA = {
  ligand_state: {
    smiles_entrada: "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    smiles_acoplado: "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    cambio_respecto_a_la_entrada: false,
    carga_formal_neta: 0,
    formula_acoplada: "C8H10N4O2",
    tautomeria: { aplicada: true, motor: "RDKit", alternativas: 1, motivo: null },
    protonacion: { aplicada: true, motor: "dimorphite-dl", ph: 7.4, alternativas: 1, motivo: null },
  },
} satisfies ResultadoParcial;

describe("EstadoDelLigando", () => {
  it("declara la carga formal de la especie acoplada", () => {
    render(<EstadoDelLigando result={comoResultado(ASPIRINA)} />);
    expect(screen.getByText("anión −1")).toBeInTheDocument();
    expect(screen.getByText("CC(=O)Oc1ccccc1C(=O)[O-]")).toBeInTheDocument();
  });

  it("dice cuando lo acoplado no es lo escrito, y cuantas alternativas se tiraron", () => {
    render(<EstadoDelLigando result={comoResultado(ASPIRINA)} />);
    const aviso = screen.getByRole("status");
    expect(aviso).toHaveTextContent(/no es la que escribiste/i);
    expect(aviso).toHaveTextContent(/2 enumerados/);
    expect(aviso).toHaveTextContent(/pH 7\.4/);
  });

  it("advierte que los descriptores son de la forma neutra", () => {
    // Es el punto entero de poner la tarjeta ANTES de MW/LogP/TPSA.
    render(<EstadoDelLigando result={comoResultado(ASPIRINA)} />);
    expect(screen.getByRole("status")).toHaveTextContent(/forma neutra que escribiste/i);
  });

  it("no alarma cuando la especie no cambia", () => {
    render(<EstadoDelLigando result={comoResultado(CAFEINA)} />);
    expect(screen.getByText("especie neutra")).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByText(/se acopló tal cual/i)).toBeInTheDocument();
  });

  it("un cation se etiqueta como tal", () => {
    render(
      <EstadoDelLigando
        result={comoResultado({ ligand_state: { ...CAFEINA.ligand_state, carga_formal_neta: 1 } })}
      />,
    );
    expect(screen.getByText("catión +1")).toBeInTheDocument();
  });

  it("declara el motivo cuando la protonacion no pudo correr", () => {
    render(
      <EstadoDelLigando
        result={comoResultado({
          ligand_state: {
            ...CAFEINA.ligand_state,
            protonacion: {
              aplicada: false,
              motivo: "dimorphite-dl no está instalado en este equipo",
            },
          },
        })}
      />,
    );
    expect(screen.getByText(/no está instalado en este equipo/)).toBeInTheDocument();
  });

  it("no se renderiza en corridas anteriores a esta etapa", () => {
    const { container } = render(<EstadoDelLigando result={comoResultado({ ligand_state: null })} />);
    expect(container).toBeEmptyDOMElement();
  });
});

// FEP-ready, paso 1 (56e8733): el backend declara el tautómero en tres estados.
// La tarjeta lo traduce desde el código, no desde la frase del backend.
describe("EstadoDelLigando: declaración del tautómero", () => {
  const conDeclaracion = (declaracion: Record<string, unknown> | null) =>
    comoResultado({
      ligand_state: {
        ...CAFEINA.ligand_state,
        tautomeria: { ...CAFEINA.ligand_state.tautomeria, declaracion },
      },
    });

  it("varios candidatos sin descartar: lo dice y pide revisarlo antes de FEP", () => {
    render(<EstadoDelLigando result={conDeclaracion({ estado: "MULTIESTADO_REQUERIDO", n_candidatos: 3, motivo: "x" })} />);
    const aviso = screen.getByText(/3 candidatos y ninguno descartado con evidencia/);
    expect(aviso).toHaveTextContent(/no una predicción de población/);
    expect(aviso).toHaveTextContent(/antes de un cálculo de energía libre/);
  });

  it("uno solo: lo declara sin alarma", () => {
    render(<EstadoDelLigando result={conDeclaracion({ estado: "RESUELTO_UNICO", n_candidatos: 1 })} />);
    expect(screen.getByText(/uno solo enumerable/)).toBeInTheDocument();
    expect(screen.queryByText(/ninguno descartado/)).toBeNull();
  });

  it("no resuelto: enseña el código del motivo, nunca el texto de la excepción", () => {
    render(<EstadoDelLigando result={conDeclaracion({ estado: "NO_RESUELTO", motivo: "ENUMERACION_FALLO: ValueError: bad valence" })} />);
    expect(screen.getByText(/no resuelto: la enumeración falló/)).toBeInTheDocument();
    expect(screen.getByText(/ENUMERACION_FALLO/)).toBeInTheDocument();
    expect(screen.queryByText(/ValueError/)).toBeNull();
  });

  it("una corrida anterior, sin declaración, no inventa ninguna", () => {
    render(<EstadoDelLigando result={conDeclaracion(null)} />);
    expect(screen.queryByText(/Tautómero:/)).toBeNull();
  });
});
