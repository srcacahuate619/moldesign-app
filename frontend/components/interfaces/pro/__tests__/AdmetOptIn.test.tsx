// =====================================================================
// ADMET-AI es opt-in, y la corrida tiene que enterarse
// =====================================================================
//
// Había dos afirmaciones distintas sobre lo mismo:
//
//   ProOptionsModal   DEFAULT_ADVANCED.enableADMET = true
//   ProEvaluation     run_admet_ai !== false        → true si la clave falta
//   backend           .get("run_admet_ai", False)   → false si la clave falta
//
// Es decir: la casilla salía marcada, el botón de ejecutar ni siquiera
// mandaba la clave, y el pipeline corría SIN ADMET. La UI decía que había
// perfil farmacocinético en una corrida que no lo calculó. Y cuando el
// usuario lo encendía a propósito, tampoco llegaba.
//
// Estas pruebas fijan las tres cosas que arreglan eso:
//
//   1. defecto — apagado, en el modal y al leer una configuración sin la clave
//   2. configuración explícita — un `true` guardado se respeta al reabrir
//   3. transmisión — la elección viaja SIEMPRE en `stage_params.properties`
//
// Y, en Opciones, que el aviso diga las cuatro cosas que el usuario necesita
// antes de encenderlo: experimental, local, primera carga lenta (VM), y que
// el docking no lo necesita.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

// El modal monta un `Canvas` de react-three-fiber para previsualizar la caja
// de docking. jsdom no tiene WebGL, y aquí no se prueba la caja: se prueban
// los módulos del pipeline y la copia que los acompaña. El doble del `Canvas`
// NO renderiza a sus hijos —la escena three.js entera queda fuera— porque lo
// que se quiere montar es el panel de Opciones, no el visor.
vi.mock("@react-three/fiber", () => ({
  Canvas: () => <div data-testid="canvas" />,
  useThree: () => ({
    camera: { position: { set: () => {} }, lookAt: () => {}, updateProjectionMatrix: () => {} },
    invalidate: () => {},
    gl: {},
    scene: {},
  }),
}));

vi.mock("@react-three/drei", () => ({
  OrbitControls: () => null,
  Edges: () => null,
  Sphere: () => null,
}));
vi.mock("../../../../lib/api", () => ({
  encenderMotor: vi.fn(async () => {}),
  inventarioDeMotores: vi.fn(async () => ({ motores: [] })),
}));

import ProOptionsModal, { type AdvancedConfig } from "../ProOptionsModal";

// La animación de entrada usa la Web Animations API, que jsdom no implementa.
beforeAll(() => {
  if (typeof Element.prototype.animate !== "function") {
    Element.prototype.animate = (() => ({
      cancel: () => {},
      finish: () => {},
      finished: Promise.resolve(),
    })) as unknown as Element["animate"];
  }
});

const noop = () => {};

function abrirOpciones(props: Partial<React.ComponentProps<typeof ProOptionsModal>> = {}) {
  return render(
    <ProOptionsModal isOpen onClose={noop} onApply={noop} {...props} />,
  );
}

const admetSwitch = () => screen.getByRole("switch", { name: "Perfil ADMET" });

// ── 1. Defecto ────────────────────────────────────────────────────────

describe("defecto de ADMET-AI", () => {
  it("el modal de Opciones abre con ADMET apagado", () => {
    abrirOpciones();
    expect(admetSwitch()).toHaveAttribute("aria-checked", "false");
  });

  it("los módulos que sí eran opt-out siguen como estaban", () => {
    // El cambio es de ADMET, no una revisión del panel entero: MM-GBSA sigue
    // encendido y Selectividad apagada. Si esto se rompe, alguien movió algo
    // que nadie pidió mover.
    abrirOpciones();
    expect(screen.getByRole("switch", { name: "Refinamiento MM-GBSA" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(
      screen.getByRole("switch", { name: "Selectividad Anti-Target" }),
    ).toHaveAttribute("aria-checked", "false");
  });
});

// ── 2. Configuración explícita ────────────────────────────────────────

describe("configuración explícita de ADMET-AI", () => {
  const base: AdvancedConfig = {
    numWorkers: 4,
    parallelDocks: 2,
    enableSelectivity: false,
    selectedAntiTargets: [],
    enableMMGBSA: false,
    mmgbsaSteps: 1000,
    enableADMET: false,
  };

  it("una corrida guardada con ADMET encendido reabre encendida", () => {
    abrirOpciones({ initialAdvanced: { ...base, enableADMET: true } });
    expect(admetSwitch()).toHaveAttribute("aria-checked", "true");
  });

  it("una corrida guardada con ADMET apagado reabre apagada", () => {
    abrirOpciones({ initialAdvanced: { ...base, enableADMET: false } });
    expect(admetSwitch()).toHaveAttribute("aria-checked", "false");
  });
});

// ── 3. Aviso en Opciones ──────────────────────────────────────────────

describe("lo que Opciones dice antes de encender ADMET", () => {
  it("advierte: experimental, local, primera carga lenta (VM) y no necesaria para docking", () => {
    abrirOpciones();
    const aviso = screen.getByText(/Módulo experimental/i);

    // Cada afirmación se comprueba por separado: un aviso al que se le cae
    // una frase sigue pareciendo un aviso.
    expect(aviso).toHaveTextContent(/experimental/i);
    expect(aviso).toHaveTextContent(/en local|EN LOCAL/);
    expect(aviso).toHaveTextContent(/primera carga/i);
    expect(aviso).toHaveTextContent(/minutos/i);
    expect(aviso).toHaveTextContent(/m[áa]quina virtual/i);
    expect(aviso).toHaveTextContent(/no es necesari/i);
    expect(aviso).toHaveTextContent(/docking/i);

    // Y la etiqueta lo marca como experimental sin tener que leer el párrafo.
    expect(screen.getByText(/Experimental · opt-in/)).toBeInTheDocument();
  });
});

// ── 4. Lectura y transmisión en ProEvaluation ─────────────────────────
//
// ProEvaluation es un componente de ~1800 líneas con visores 3D, SSE y
// polling: montarlo aquí probaría el visor, no la decisión. Lo que hay que
// fijar son dos expresiones concretas del origen, y eso se lee del origen —
// el mismo enfoque que `ProEvaluationLayout.test.ts`.

const proEvaluationSource = readFileSync(
  resolve(process.cwd(), "components/interfaces/pro/ProEvaluation.tsx"),
  "utf8",
);

describe("ProEvaluation: cómo lee y cómo transmite la elección de ADMET", () => {
  it("lee la configuración como la lee el backend: sólo un true explícito enciende", () => {
    expect(proEvaluationSource).toContain(
      "initialRunConfiguration?.pipelineConfig?.stage_params?.properties?.run_admet_ai === true",
    );
    // El `!== false` es justamente el defecto invertido que se corrige.
    expect(proEvaluationSource).not.toContain("run_admet_ai !== false");
  });

  it("el botón de ejecutar manda la elección, encendida o apagada", () => {
    // Dos constructores de pipelineConfig: el del botón «Ejecutar Evaluación»
    // (advancedOpts) y el de «Aplicar Configuración» del modal (adv). Los dos
    // tienen que declarar la clave; si sólo la declara uno, ejecutar sin
    // pasar por Opciones vuelve a dejar la decisión al defecto del backend.
    expect(proEvaluationSource).toContain(
      "properties: { run_admet_ai: advancedOpts.enableADMET }",
    );
    expect(proEvaluationSource).toContain("properties: { run_admet_ai: adv.enableADMET }");
  });
});

// El documento que firma el preflight y que luego se ejecuta. Si la clave no
// está ahí, el dossier de un caso que nunca abrió Opciones no dice qué se
// hizo con ADMET, y nadie puede reconstruirlo después.
const runnerSource = readFileSync(
  resolve(process.cwd(), "components/evaluation/CaseEvaluationRunner.tsx"),
  "utf8",
);

describe("CaseEvaluationRunner: el protocolo por defecto lo declara", () => {
  it("la configuración de respaldo dice explícitamente que ADMET no corre", () => {
    expect(runnerSource).toContain("properties: { run_admet_ai: false }");
  });
});

// ── 5. Geometría del interruptor ────────────────────────────────────

describe("layout de los interruptores", () => {
  it("el control conserva su ancho y contiene el indicador al encenderse", () => {
    abrirOpciones();
    const control = admetSwitch();

    fireEvent.click(control);

    expect(control).toHaveAttribute("aria-checked", "true");
    expect(control.className).toContain("shrink-0");
    expect(control.className).toContain("overflow-hidden");
    expect(control.querySelector("span")?.className).toContain("translate-x-4");
  });

  it("ningún switch del panel puede encogerse dentro de su tarjeta", () => {
    abrirOpciones();
    for (const control of screen.getAllByRole("switch")) {
      expect(control.className).toContain("shrink-0");
    }
  });
});
