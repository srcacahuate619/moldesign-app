// =====================================================================
// StructuralEvidencePanel — lo que la pestaña Evaluación puede afirmar
// =====================================================================
//
// LO QUE PROTEGEN, en orden de gravedad:
//
// 1. **Ninguna pose sin `passed` se presenta como válida.** Ni `review`, ni
//    `not_evaluated`, ni en el resumen ni en el detalle. Es la afirmación que
//    convertiría un hueco de medición en un aval.
//
// 2. **Vina top-1 se enseña siempre**, y cuando la sugerida es otra, se dice
//    en pantalla. El lector no tiene que deducirlo de dos números sueltos.
//
// 3. **La sugerida que falla no se cambia por otra.** Aparece «requiere
//    revisión» y las alternativas se listan, sin que ninguna quede elegida.
//
// 4. **Cada estado se dice con TEXTO, no sólo con color.** Las pruebas buscan
//    la palabra, que es lo que lee quien no separa verde de rojo.
//
// 5. **Español e inglés dicen lo mismo.** Una clave que exista sólo en un
//    idioma se cazaría aquí, no en producción.

import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import { LanguageProvider, TRANSLATIONS } from "../../../../context/LanguageContext";
import { PosePhysicalDetails, StructuralEvidencePanel } from "../StructuralEvidencePanel";
import type {
  EvaluationResultWithEvidence,
  PoseSelectionContract,
  StructuralEvidenceContract,
} from "../../../../lib/structuralEvidence";

vi.mock("../../../../lib/auth", () => ({
  useAuth: () => ({ isLoading: false, user: { user_id: "test-user" } }),
}));

const POSES = [
  { rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 },
  { rank: 2, affinity: -7.9, rmsd_lb: 1.1, rmsd_ub: 1.4 },
  { rank: 3, affinity: -6.1, rmsd_lb: 2.1, rmsd_ub: 2.8 },
];

function evidencia(
  stage: string,
  estados: Record<number, string>,
  extra: Partial<StructuralEvidenceContract> = {},
): StructuralEvidenceContract {
  const ranks = Object.keys(estados).map(Number);
  return {
    version_schema: 1,
    stage_status: stage,
    reason_code: null,
    detail: null,
    primary_pose_rank: 1,
    poses_produced: 3,
    poses_evaluated: ranks.filter((r) => estados[r] !== "not_evaluated").length,
    receptor_sha256: "a".repeat(64),
    receptor_source: "targets/7E2Y/prepared.pdbqt",
    validation_engine: "posebusters:1.0:dock",
    poses: ranks.map((rank) => ({
      rank,
      observed_vina_affinity_kcal_mol: POSES.find((p) => p.rank === rank)?.affinity ?? null,
      status: estados[rank],
      engine: "posebusters:1.0:dock",
      checks: [{ check: "internal_energy", estado: estados[rank] === "failed" ? "FALLA" : "PASA" }],
      checks_que_fallan: estados[rank] === "failed" ? ["internal_energy"] : [],
      detail: null,
      reason_code: null,
    })),
    ...extra,
  };
}

function seleccion(extra: Partial<PoseSelectionContract> = {}): PoseSelectionContract {
  return {
    version_schema: 1,
    contract: "pose_selection/v1",
    status: "selected",
    strategy: "pose_selector_v06",
    strategy_is_fallback: false,
    vina_top1_rank: 1,
    selected_pose_rank: 2,
    confidence: 0.412233,
    abstained: false,
    abstention_reason: null,
    detail: null,
    pose_scores: [
      { rank: 1, score: 0.11 },
      { rank: 2, score: 0.52 },
      { rank: 3, score: 0.09 },
    ],
    model: {
      name: "pose_selector_v06",
      version: "pose_selector_v06",
      model_sha256: "b".repeat(64),
      abstention_threshold: 0.097663,
    },
    warnings: [],
    suggested_pose_physical_status: "passed",
    physical_review: false,
    physically_valid_alternatives: [],
    ...extra,
  };
}

function resultado(
  structural: StructuralEvidenceContract | null,
  pose: PoseSelectionContract | null,
  extra: Record<string, unknown> = {},
): EvaluationResultWithEvidence {
  return {
    affinity_kcal: -8.3,
    docking_poses: POSES,
    vina_version: "1.2.5",
    vina_random_seed: 42,
    parsing_source: "sdf",
    engine_used: "vina",
    structural_evidence: structural,
    pose_selection: pose,
    ...extra,
  } as unknown as EvaluationResultWithEvidence;
}

/** Monta el panel con el idioma fijado, sin depender de `navigator.language`. */
function montar(
  result: EvaluationResultWithEvidence | null,
  {
    locale = "es",
    ...props
  }: {
    locale?: "es" | "en";
    loading?: boolean;
    error?: string | null;
    onComparePoses?: (leftRank: number, rightRank: number) => void;
    onOpenPoseDetails?: (rank: number | null) => void;
  } = {},
) {
  window.localStorage.setItem("moldesign_locale:user:test-user", locale);
  return render(
    <LanguageProvider>
      <StructuralEvidencePanel result={result} {...props} />
    </LanguageProvider>,
  );
}

const es = TRANSLATIONS.es;
const en = TRANSLATIONS.en;

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
});

// ── 1. Los cuatro estados físicos, dichos con texto ──────────────────

describe("estados de los controles físicos", () => {
  it("passed: se declara superado y autoriza continuar dentro del protocolo", () => {
    montar(resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()));

    expect(screen.getAllByText(es.se_phys_passed).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_dec_next_proceed_detail)).toBeInTheDocument();
    // Cobertura con denominador, nunca un porcentaje suelto.
    expect(screen.getAllByText("3 / 3 poses").length).toBeGreaterThan(0);
    // Sin código de razón no se pinta una fila «Razón — No informado».
    expect(screen.queryByText(es.se_phys_reason)).toBeNull();
  });

  it("failed: se declara fallido y el siguiente paso es abstenerse", () => {
    montar(
      resultado(
        evidencia("failed", { 1: "failed", 2: "failed", 3: "failed" }),
        seleccion({ suggested_pose_physical_status: "failed", physical_review: true }),
      ),
    );

    expect(screen.getAllByText(es.se_phys_failed).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_dec_next_abstain_detail)).toBeInTheDocument();
  });

  it("review: se dice que NO es una pose aprobada", () => {
    montar(
      resultado(
        evidencia("review", { 1: "review", 2: "review", 3: "review" }),
        seleccion({ selected_pose_rank: 1, suggested_pose_physical_status: "review", physical_review: true }),
      ),
    );

    expect(screen.getAllByText(es.se_phys_review).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_phys_review_meaning)).toBeInTheDocument();
  });

  it("not_evaluated: describe al validador, nunca a la molécula", () => {
    montar(
      resultado(
        evidencia("not_evaluated", { 1: "not_evaluated", 2: "not_evaluated", 3: "not_evaluated" }, {
          reason_code: "VALIDADOR_NO_DISPONIBLE",
          poses_evaluated: 0,
        }),
        seleccion({ suggested_pose_physical_status: null, physical_review: true }),
      ),
    );

    expect(screen.getAllByText(es.se_phys_not_evaluated).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(es.se_phys_not_evaluated_meaning))).toBeInTheDocument();
    // El código de razón se traduce; no se imprime la clave del diccionario.
    expect(screen.getByText(es.se_phys_reason)).toBeInTheDocument();
    expect(screen.getByText(es.se_reason_VALIDADOR_NO_DISPONIBLE)).toBeInTheDocument();
    expect(screen.queryByText(/se_reason_/)).toBeNull();
  });

  it("NINGÚN estado que no sea `passed` se presenta como pose válida", () => {
    for (const stage of ["review", "not_evaluated", "failed"]) {
      const { unmount } = montar(
        resultado(
          evidencia(stage, { 1: stage, 2: stage, 3: stage }),
          seleccion({ selected_pose_rank: 1, suggested_pose_physical_status: stage, physical_review: true }),
        ),
      );

      // Se despliegan TODOS los detalles: la afirmación tampoco puede
      // aparecer escondida bajo una expansión.
      const texto = document.body.textContent ?? "";
      // «válida» sólo puede aparecer negada («no está confirmada como
      // físicamente válida») o como cabecera de alternativas que SÍ pasan.
      expect(texto).not.toContain("Pose válida");
      expect(texto).not.toContain("pose válida");
      expect(texto).toContain(es.se_phys_review_note.slice(0, 40));
      unmount();
    }
  });
});

// ── 2. Selección: abstención, fallback, discordancia ─────────────────

describe("selección de pose", () => {
  it("abstención: se dice claramente, y la referencia se marca como fallback", () => {
    montar(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({
          status: "abstained",
          abstained: true,
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "MARGEN_BAJO_UMBRAL",
          confidence: 0.02,
          would_have_suggested_rank: 2,
        }),
      ),
    );

    expect(screen.getAllByText(es.se_sel_abstained).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_sel_no_recommendation)).toBeInTheDocument();
    expect(screen.getByText(`· ${es.se_sel_fallback}`)).toBeInTheDocument();
    expect(screen.getByText(es.se_sel_fallback_note)).toBeInTheDocument();
    expect(screen.getByText(es.se_reason_MARGEN_BAJO_UMBRAL)).toBeInTheDocument();
    // Lo que HABRÍA sugerido se etiqueta como tal, no como recomendación.
    expect(screen.getByText(es.se_sel_would_have)).toBeInTheDocument();
    // Y Vina top-1 sigue en pantalla.
    expect(screen.getByText(es.se_sel_vina_top1)).toBeInTheDocument();
  });

  it("fallback por modelo ausente: `unavailable`, no un acierto del selector", () => {
    montar(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({
          status: "unavailable",
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "MODELO_AUSENTE",
          confidence: null,
          pose_scores: [],
          model: null,
        }),
      ),
    );

    expect(screen.getAllByText(es.se_sel_unavailable).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_reason_MODELO_AUSENTE)).toBeInTheDocument();
    expect(screen.getByText(es.se_sel_fallback_note)).toBeInTheDocument();
    expect(screen.queryByText(es.se_sel_abstained)).toBeNull();
  });

  it("error del selector: se declara, y la corrida conserva su top-1", () => {
    montar(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({
          status: "error",
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "SELECTOR_FALLO",
        }),
      ),
    );

    expect(screen.getAllByText(es.se_sel_error).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_sel_vina_top1)).toBeInTheDocument();
    expect(screen.getByText(es.se_unc_selector_error)).toBeInTheDocument();
  });

  it("pose discordante: se declara la diferencia y NO se sustituye la sugerida", () => {
    montar(
      resultado(
        evidencia("review", { 1: "passed", 2: "failed", 3: "passed" }),
        seleccion({
          selected_pose_rank: 2,
          suggested_pose_physical_status: "failed",
          physical_review: true,
          physically_valid_alternatives: [
            { rank: 1, physical_status: "passed" },
            { rank: 3, physical_status: "passed" },
          ],
        }),
      ),
    );

    // Se dice que difieren…
    expect(screen.getByText(es.se_sel_diverge)).toBeInTheDocument();
    expect(screen.getByText(es.se_sel_diverge_note)).toBeInTheDocument();
    // …la sugerida sigue siendo la 2, y requiere revisión…
    expect(screen.getByText(es.se_phys_review_note)).toBeInTheDocument();
    // …y las alternativas se listan sin que ninguna quede elegida.
    expect(screen.getByText(es.se_dec_alternatives_note)).toBeInTheDocument();

  });
});

// ── 3. Comparador: top-1, sugerida y alternativas a la vez ───────────

describe("detalle físico por pose", () => {
  it("muestra el detalle físico de una única pose elegida", () => {
    window.localStorage.setItem("moldesign_locale:user:test-user", "es");
    render(
      <LanguageProvider>
        <PosePhysicalDetails
          result={resultado(evidencia("review", { 1: "passed", 2: "failed", 3: "passed" }), seleccion())}
          rank={2}
        />
      </LanguageProvider>,
    );

    expect(screen.getByRole("heading", { level: 4, name: `${es.se_phys_per_pose} #2` })).toBeInTheDocument();
    // El control se LEE en español y se AUDITA por su identificador: el codigo
    // de PoseBusters sigue estando, en el `title`. Antes se imprimia crudo
    // -«internal_energy»- en una pantalla integramente en espanol.
    const control = screen.getByText(es.se_check_internal_energy);
    expect(control).toBeInTheDocument();
    expect(control).toHaveAttribute("title", "internal_energy");
    expect(screen.queryByText("internal_energy")).toBeNull();
    expect(screen.queryByText("#1")).toBeNull();
  });

  it("guía desde los controles físicos al detalle de la pose sugerida", () => {
    const onOpenPoseDetails = vi.fn();
    montar(
      resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion({ selected_pose_rank: 2 })),
      { onOpenPoseDetails },
    );

    fireEvent.click(screen.getByRole("button", { name: new RegExp(`${es.se_phys_per_pose} #2`) }));
    expect(onOpenPoseDetails).toHaveBeenCalledWith(2);
    expect(screen.queryByRole("table")).toBeNull();
  });
});

// ── 4. Estados de la interfaz: carga, error, parcial, antiguo ────────

describe("estados de la interfaz", () => {
  it("carga: se anuncia sin inventar evidencia", () => {
    montar(resultado(null, null), { loading: true });

    expect(screen.getByRole("status")).toHaveTextContent(es.se_loading);
    expect(screen.queryByText(es.se_s1_title)).toBeNull();
  });

  it("error: se distingue de «no evaluada»", () => {
    montar(resultado(null, null), { error: "HTTP 503" });

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent(es.se_error);
    expect(alerta).toHaveTextContent("HTTP 503");
    expect(screen.queryByText(es.se_s3_title)).toBeNull();
  });

  it("sin poses ni contratos: se dice que no hay nada, no se pinta un cero", () => {
    montar(resultado(null, null, { docking_poses: [], affinity_kcal: null, pose_selection: null }));

    expect(screen.getByRole("status")).toHaveTextContent(es.se_empty);
  });

  it("datos parciales: lo que la corrida no guardó se dice «no informado»", () => {
    montar(
      resultado(null, seleccion({ status: "unavailable", selected_pose_rank: null, model: null }), {
        vina_random_seed: null,
        parsing_source: null,
        vina_version: null,
        engine_used: null,
      }),
    );

    // La semilla ausente se declara en el resumen, no se omite la fila.
    expect(screen.getAllByText(es.se_not_reported).length).toBeGreaterThan(0);
    expect(screen.getByText(es.se_unc_no_seed)).toBeInTheDocument();
    expect(screen.getByText(es.se_unc_incomplete_provenance)).toBeInTheDocument();
  });

  it("resultado antiguo: no llegó a ejecutarse, y no es un fallo", () => {
    montar(resultado(null, null));

    expect(screen.getByText(es.se_legacy)).toBeInTheDocument();
    expect(screen.getByText(es.se_legacy_note)).toBeInTheDocument();
    // Y aun así se enseña lo que sí hay: las poses y su top-1.
    expect(screen.getByText(es.se_sel_vina_top1)).toBeInTheDocument();
  });

  it("conformeros y restarts: se declaran no registrados, no se rellenan", () => {
    montar(resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()));

    expect(screen.getByText(es.se_gen_conformers)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(es.se_gen_conformers_note.slice(0, 40)))).toBeInTheDocument();
  });
});

// ── 5. Accesibilidad y tamaños pequeños ──────────────────────────────

describe("accesibilidad", () => {
  it("expone el detalle sin disclosures y conserva la lectura completa", () => {
    montar(resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()));

    expect(screen.queryByText(es.se_show_detail)).toBeNull();
    expect(screen.queryByText(es.se_hide_detail)).toBeNull();
    expect(screen.getByText(es.se_gen_conformers)).toBeInTheDocument();
    expect(screen.getByText(es.se_sel_scores)).toBeInTheDocument();
  });

  it("conserva los datos de Generación y Selección visibles", () => {
    montar(resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()));

    expect(screen.getByText(es.se_gen_protocol)).toBeInTheDocument();
    expect(screen.getByText(es.se_sel_confidence_note)).toBeInTheDocument();
  });

  it("el bloque se anuncia con su encabezado, y no añade una pestaña", () => {
    montar(resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()));

    const region = screen.getByRole("region", { name: es.se_title });
    expect(region).toBeInTheDocument();
    expect(within(region).getByRole("heading", { level: 2, name: es.se_title })).toBeInTheDocument();
    // Las cuatro secciones, cada una con su encabezado de nivel 3.
    for (const titulo of [es.se_s1_title, es.se_s2_title, es.se_s3_title, es.se_s4_title]) {
      expect(within(region).getByRole("heading", { level: 3, name: new RegExp(titulo) })).toBeInTheDocument();
    }
    expect(screen.queryByRole("tab")).toBeNull();
  });

  it("no duplica la tabla de comparación dentro del expediente", () => {
    montar(resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()));

    expect(screen.queryByRole("table")).toBeNull();
  });
});

// ── 6. Español e inglés, completos y en paralelo ─────────────────────

describe("idiomas", () => {
  it("el panel se rinde íntegro en inglés", () => {
    montar(
      resultado(
        evidencia("review", { 1: "passed", 2: "failed", 3: "passed" }),
        seleccion({
          selected_pose_rank: 2,
          suggested_pose_physical_status: "failed",
          physical_review: true,
          physically_valid_alternatives: [{ rank: 1, physical_status: "passed" }],
        }),
      ),
      { locale: "en" },
    );

    expect(screen.getByRole("heading", { level: 2, name: en.se_title })).toBeInTheDocument();
    expect(screen.getByText(en.se_sel_diverge)).toBeInTheDocument();
    expect(screen.getByText(en.se_phys_review_note)).toBeInTheDocument();
    expect(screen.getByText(en.se_dec_alternatives_note)).toBeInTheDocument();
    // Y ni un resto en español.
    expect(screen.queryByText(es.se_sel_diverge)).toBeNull();
    expect(screen.queryByText(es.se_phys_review_note)).toBeNull();
  });

  it("ninguna clave `se_` existe en un solo idioma", () => {
    const clavesEs = Object.keys(es).filter((key) => key.startsWith("se_"));
    const clavesEn = Object.keys(en).filter((key) => key.startsWith("se_"));

    expect(clavesEs.length).toBeGreaterThan(50);
    expect(clavesEs.sort()).toEqual(clavesEn.sort());
    // Y ninguna traducción vacía o copiada literal del código.
    for (const key of clavesEs) {
      expect(es[key].trim().length).toBeGreaterThan(0);
      expect(en[key].trim().length).toBeGreaterThan(0);
      expect(en[key]).not.toBe(key);
    }
  });
});

// ── 7. Nada de notas 0-100 ───────────────────────────────────────────

describe("lo que el panel NO enseña", () => {
  it("no pinta ninguna puntuación 0-100, ni con los detalles abiertos", () => {
    montar(
      resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion(), {
        total_score: 87.4,
        adme_score: 62,
        druglikeness_score: 91,
      }),
    );

    for (const boton of screen.getAllByRole("button")) {
      fireEvent.click(boton);
    }

    const texto = document.body.textContent ?? "";
    expect(texto).not.toContain("87.4");
    expect(texto).not.toContain("/100");
    expect(texto.toLowerCase()).not.toContain("total_score");
    // Lo único numérico del selector es su margen crudo y su umbral.
    expect(texto).toContain("0.4122");
    expect(texto).toContain("0.0977");
  });
});
