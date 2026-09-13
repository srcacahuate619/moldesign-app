// =====================================================================
// Tests del Case Workspace — evaluation-first, detalles y revelado del informe
// =====================================================================
//
// Estos tests cubren los criterios de aceptación que no se pueden comprobar
// leyendo el código: que crear un caso lleva a la EVALUACIÓN y no a un
// cuestionario, que la botonera de siete secciones ya no existe, que «Informe»
// sólo aparece cuando hay un resultado recuperable, que dos casos NO comparten
// estado visible y que una corrida activa impide cambiar de caso.
//
// `CaseEvaluationRunner` se mockea. No es pereza: montarlo de verdad arrastra
// Ketcher, Molstar y el polling, y este archivo prueba el WORKSPACE, no la
// evaluación. El mock conserva lo único que importa aquí — que recibe un
// `caseId`, que se remonta al cambiar de caso, y que puede declarar trabajo
// vivo, un resultado publicable o una recuperación fallida.

import { useEffect } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { CaseProvider } from "../../../context/CaseContext";
import { CaseWorkspace } from "../CaseWorkspace";
import { createBrowserCaseRepository } from "../../../lib/cases/browserCaseRepository";
import { CASE_KEY_PREFIX, CASES_INDEX_KEY } from "../../../lib/cases/browserCaseRepository";
import type { ReportableResult, ReportRecoveryState } from "../../../lib/cases/types";

// ── Mock del runner ──────────────────────────────────────────────────
// Guarda cada montaje para poder afirmar que hubo remonte (aislamiento).
const mounts: string[] = [];
let declareLiveWork: ((patch: { evaluation?: boolean; analysis?: boolean; taskId?: string | null }) => void) | null = null;
let declareReportable: ((result: ReportableResult | null) => void) | null = null;
let declareRecovery: ((state: ReportRecoveryState) => void) | null = null;

vi.mock("../../evaluation/CaseEvaluationRunner", () => ({
  default: function MockCaseEvaluationRunner({
    caseId,
    onLiveWorkChange,
    onReportableChange,
    onReportRecoveryChange,
  }: {
    caseId: string;
    onLiveWorkChange?: (patch: { evaluation?: boolean; analysis?: boolean; taskId?: string | null }) => void;
    onReportableChange?: (result: ReportableResult | null) => void;
    onReportRecoveryChange?: (state: ReportRecoveryState) => void;
  }) {
    // Se cuenta el MONTAJE, no el render: el criterio es que el runner pesado
    // no se vuelva a montar al ir y volver del informe.
    useEffect(() => {
      mounts.push(caseId);
    }, [caseId]);
    declareLiveWork = onLiveWorkChange ?? null;
    declareReportable = onReportableChange ?? null;
    declareRecovery = onReportRecoveryChange ?? null;
    return <div data-testid="runner">runner:{caseId}</div>;
  },
}));

// El visor del dossier pide el documento al backend con la proyección del
// caso. Aquí sólo interesa que la vista de informe lo MONTE con el caso y el
// `molecule_id` correctos; el visor tiene sus propios fallos declarados y se
// prueban en `CaseDossierViewer.test.tsx`, no por segunda vez desde aquí.
vi.mock("../CaseDossierViewer", () => ({
  CaseDossierViewer: ({
    caseRecord,
    reportable,
  }: {
    caseRecord: { id: string };
    reportable: { moleculeId: string };
  }) => (
    <div data-testid="case-dossier" data-case={caseRecord.id}>
      dossier:{reportable.moleculeId}
    </div>
  ),
}));

function renderWorkspace() {
    const repository = createBrowserCaseRepository("test-owner");
  const result = render(
    <CaseProvider repository={repository}>
      <CaseWorkspace />
    </CaseProvider>,
  );
  return { ...result, repository };
}

/**
 * Crea un caso a traves de la UI, como lo haria una persona.
 *
 * Usa `fireEvent`, que es la convencion del repo (`LauncherScreen.test.tsx`,
 * `LoginForm.test.tsx`). No se anade `@testing-library/user-event` solo para
 * esto: seria una dependencia nueva por comodidad de un archivo.
 */
async function createCaseViaUi(name: string) {
  fireEvent.click(screen.getAllByRole("button", { name: /nuevo caso|crear caso/i })[0]);
  const dialog = await screen.findByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText(/nombre/i), { target: { value: name } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Crear caso" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
}

/** Abre «Detalles del caso» y devuelve su diálogo. */
async function openDetails() {
  fireEvent.click(screen.getByRole("button", { name: /detalles del caso/i }));
  return screen.findByRole("dialog", { name: /detalles del caso/i });
}

const REPORTABLE: ReportableResult = {
  taskId: "task-abcdef123456",
  moleculeId: "mol-0001",
  certified: false,
};

describe("Case Workspace", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mounts.length = 0;
    declareLiveWork = null;
    declareReportable = null;
    declareRecovery = null;
  });

  describe("estado vacío", () => {
    it("muestra el onboarding sobrio con las dos acciones", async () => {
      renderWorkspace();
      expect(await screen.findByText("Crea un caso de estudio")).toBeInTheDocument();
      expect(
        screen.getByText(/Reúne una proteína, una hipótesis de sitio/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Crear caso" })).toBeEnabled();
      expect(screen.getByRole("button", { name: /abrir carpeta existente/i })).toBeDisabled();
    });

    it("explica por qué «Abrir carpeta» está deshabilitado en web", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      const button = screen.getByRole("button", { name: /abrir carpeta existente/i });
      const describedBy = button.getAttribute("aria-describedby");
      expect(describedBy).toBeTruthy();
      expect(document.getElementById(describedBy as string)?.textContent).toMatch(
        /aplicación de escritorio/i,
      );
    });

    it("no muestra ninguna ruta falsa: dice dónde guarda de verdad", async () => {
      renderWorkspace();
      expect(await screen.findByText("Guardado en este navegador")).toBeInTheDocument();
      // Nada que parezca una ruta de disco.
      expect(screen.queryByText(/^[A-Z]:\\/)).not.toBeInTheDocument();
      expect(screen.queryByText(/^\/home\//)).not.toBeInTheDocument();
    });

    it("la evaluación NO aparece sin un caso activo", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      expect(screen.queryByTestId("runner")).not.toBeInTheDocument();
    });
  });

  describe("crear y abrir", () => {
    it("crear un caso abre la EVALUACIÓN, no un cuestionario", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");

      await createCaseViaUi("Serie de prueba");

      expect(await screen.findByRole("heading", { name: "Serie de prueba" })).toBeInTheDocument();
      // El destino es la evaluación real, montada de inmediato.
      expect(await screen.findByTestId("runner")).toBeInTheDocument();
      // Y NO el panel de contexto: las preguntas dejaron de ser el peaje de
      // entrada. Siguen existiendo, pero detrás de «Detalles del caso».
      expect(screen.queryByRole("heading", { name: "Contexto" })).not.toBeInTheDocument();
      // Estado inicial visible en la cabecera.
      expect(screen.getByText("Borrador")).toBeInTheDocument();
      // Y aparece en la barra lateral.
      const nav = screen.getByRole("navigation", { name: "Casos" });
      expect(within(nav).getByText("Serie de prueba")).toBeInTheDocument();
    });

    it("el destino guardado es `evaluation`", async () => {
      const { repository } = renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Persistente");

      const [entry] = await repository.listCases();
      const record = await repository.readCase(entry.id);
      expect(record.activeView).toBe("evaluation");
    });

    it("persiste tras recargar (repositorio nuevo sobre el mismo almacenamiento)", async () => {
      const first = renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Sobrevive");
      first.unmount();

      renderWorkspace();
      const nav = await screen.findByRole("navigation", { name: "Casos" });
      expect(await within(nav).findByText("Sobrevive")).toBeInTheDocument();
    });

    it("el diálogo no deja crear sin nombre", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      fireEvent.click(screen.getByRole("button", { name: "Crear caso" }));
      const dialog = await screen.findByRole("dialog");
      expect(within(dialog).getByRole("button", { name: "Crear caso" })).toBeDisabled();
    });
  });

  describe("compatibilidad con casos guardados por el build anterior", () => {
    /**
     * Escribe a mano un manifiesto v1 en el almacenamiento del navegador, con
     * una `activeSection` de las que ya no existen.
     */
    function seedLegacyCase(id: string, activeSection: string) {
      const now = "2026-08-01T10:00:00.000Z";
      window.localStorage.setItem(
        `${CASE_KEY_PREFIX}test-owner:${id}`,
        JSON.stringify({
          schemaVersion: 1,
          ownerUserId: "test-owner",
          id,
          name: "Caso heredado",
          createdAt: now,
          updatedAt: now,
          lastOpenedAt: now,
          status: "draft",
          storage: { mode: "browser", label: "Guardado en este navegador" },
          activeSection,
          context: { studyKind: "explore-hypothesis" },
          archived: false,
        }),
      );
      window.localStorage.setItem(
        `${CASES_INDEX_KEY}:test-owner`,
        JSON.stringify([
          {
            id,
            name: "Caso heredado",
            status: "draft",
            updatedAt: now,
            lastOpenedAt: now,
            archived: false,
            storageMode: "browser",
          },
        ]),
      );
    }

    it.each(["context", "system", "site", "ligands", "evidence", "report"])(
      "un caso v1 en «%s» abre en Evaluación en vez de desaparecer",
      async (section) => {
        seedLegacyCase(`legacy-${section}`, section);
        renderWorkspace();

        const nav = await screen.findByRole("navigation", { name: "Casos" });
        // La fila EXISTE: un valor histórico no puede hacer desaparecer el caso.
        const row = await within(nav).findByText("Caso heredado");
        fireEvent.click(row);

        expect(await screen.findByRole("heading", { name: "Caso heredado" })).toBeInTheDocument();
        // Y aterriza en la evaluación, no en una pantalla vacía.
        expect(await screen.findByTestId("runner")).toBeInTheDocument();
      },
    );
  });

  describe("detalles del caso", () => {
    it("abre el contexto en un panel accesible y guarda sin bloquear", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Con contexto");
      await screen.findByTestId("runner");

      const opener = screen.getByRole("button", { name: /detalles del caso/i });
      expect(opener).toHaveAttribute("aria-expanded", "false");
      expect(opener).toHaveAttribute("aria-controls", "case-details-drawer");
      // El recuento acompaña, sin alarma: son 7 preguntas sin responder.
      expect(opener).toHaveAccessibleName(/7 detalles pendientes/);
      expect(screen.getByText(/7 detalles pendientes/)).toBeInTheDocument();

      const drawer = await openDetails();
      expect(opener).toHaveAttribute("aria-expanded", "true");

      const field = within(drawer).getByLabelText("¿Qué intenta responder este caso?");
      fireEvent.change(field, { target: { value: "Si la serie discrimina" } });

      // Autosave discreto: primero "Guardando…", luego "Guardado."
      await waitFor(() =>
        expect(within(drawer).getByRole("status")).toHaveTextContent(/Guardando|Guardado/),
      );
      await waitFor(
        () => expect(within(drawer).getByRole("status")).toHaveTextContent("Guardado."),
        { timeout: 4000 },
      );

      // La evaluación SIGUE montada detrás: responder no interrumpe el trabajo.
      expect(screen.getByTestId("runner")).toBeInTheDocument();
    });

    it("Escape cierra el panel y devuelve el foco a quien lo abrió", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Teclado");
      await screen.findByTestId("runner");

      const opener = screen.getByRole("button", { name: /detalles del caso/i });
      opener.focus();
      const drawer = await openDetails();

      fireEvent.keyDown(drawer, { key: "Escape" });
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: /detalles del caso/i })).not.toBeInTheDocument(),
      );
      await waitFor(() => expect(document.activeElement).toBe(opener));
    });

    it("clasifica las preguntas por severidad y no inventa bloqueantes", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Severidades");
      await screen.findByTestId("runner");
      const drawer = await openDetails();

      expect(within(drawer).getAllByText("Advertencia científica").length).toBeGreaterThan(0);
      expect(within(drawer).getAllByText("Contexto opcional").length).toBeGreaterThan(0);
      // En este sprint NO se declara ningún bloqueante técnico.
      expect(screen.queryByText("Bloqueante técnico")).not.toBeInTheDocument();
    });
  });

  describe("modos", () => {
    it("no existe la botonera de siete secciones", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Sin botonera");
      await screen.findByTestId("runner");

      for (const name of ["Contexto", "Sistema", "Sitio", "Ligandos", "Evaluar", "Evidencia"]) {
        expect(screen.queryByRole("tab", { name })).not.toBeInTheDocument();
      }
      // Y tampoco quedan controles inertes prometiendo lo que no hay.
      expect(screen.queryByText(/aún no implementado/i)).not.toBeInTheDocument();
    });

    it("antes de evaluar sólo existe Evaluación: «Informe» no aparece", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Sin informe");
      await screen.findByTestId("runner");

      expect(screen.queryByRole("tab", { name: "Informe" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /abrir informe/i })).not.toBeInTheDocument();
      // Un único destino no necesita conmutador.
      expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    });

    it("una evaluación completada revela «Informe» y lo ofrece sin navegar sola", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Con evidencia");
      await waitFor(() => expect(declareReportable).not.toBeNull());

      act(() => declareReportable?.(REPORTABLE));

      // Aparece el segundo modo y la llamada explícita…
      expect(await screen.findByRole("tab", { name: "Informe" })).toBeInTheDocument();
      const cta = screen.getByRole("button", { name: /abrir informe/i });
      // …pero NADIE ha movido al usuario de pantalla.
      expect(screen.getByRole("tab", { name: "Evaluación" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      expect(screen.queryByTestId("case-dossier")).not.toBeInTheDocument();

      fireEvent.click(cta);

      expect(await screen.findByTestId("case-dossier")).toHaveTextContent("dossier:mol-0001");
      expect(screen.getByRole("tab", { name: "Informe" })).toHaveAttribute("aria-selected", "true");
    });

    it("restaura una preferencia de Informe sólo después de recuperar evidencia real", async () => {
      const now = "2026-08-01T10:00:00.000Z";
      const id = "case-report-restored";
      window.localStorage.setItem(
        `${CASE_KEY_PREFIX}test-owner:${id}`,
        JSON.stringify({
          schemaVersion: 2,
          ownerUserId: "test-owner",
          id,
          name: "Informe persistido",
          createdAt: now,
          updatedAt: now,
          lastOpenedAt: now,
          status: "review",
          storage: { mode: "browser", label: "Guardado en este navegador" },
          activeView: "report",
          context: { studyKind: "explore-hypothesis" },
          archived: false,
          activeRun: {
            taskId: REPORTABLE.taskId,
            executionState: "completed",
            startedAt: now,
          },
        }),
      );

      const { repository } = renderWorkspace();
      const nav = await screen.findByRole("navigation", { name: "Casos" });
      fireEvent.click(await within(nav).findByText("Informe persistido"));
      await waitFor(() => expect(declareRecovery).not.toBeNull());

      // El primer render todavía no tiene molecule_id. Eso no autoriza a
      // sobrescribir la preferencia guardada mientras el runner la recupera.
      await waitFor(async () => {
        expect((await repository.readCase(id)).activeView).toBe("report");
      });

      act(() => declareRecovery?.("recovering"));
      act(() => declareReportable?.(REPORTABLE));
      act(() => declareRecovery?.("recovered"));

      expect(await screen.findByTestId("case-dossier")).toHaveTextContent(
        `dossier:${REPORTABLE.moleculeId}`,
      );
      expect(screen.getByRole("tab", { name: "Informe" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });

    it("las dos vistas implementan navegación de pestañas con teclado", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Teclado");
      await waitFor(() => expect(declareReportable).not.toBeNull());
      act(() => declareReportable?.(REPORTABLE));

      const evaluationTab = await screen.findByRole("tab", { name: "Evaluación" });
      fireEvent.keyDown(evaluationTab, { key: "ArrowRight" });
      const reportTab = screen.getByRole("tab", { name: "Informe" });
      await waitFor(() => expect(reportTab).toHaveAttribute("aria-selected", "true"));
      expect(reportTab).toHaveFocus();

      fireEvent.keyDown(reportTab, { key: "Home" });
      await waitFor(() => expect(evaluationTab).toHaveAttribute("aria-selected", "true"));
      expect(evaluationTab).toHaveFocus();
    });

    it("el informe entrega el caso ENTERO al visor y no duplica su contexto", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Con propósito");
      await waitFor(() => expect(declareReportable).not.toBeNull());

      const drawer = await openDetails();
      fireEvent.change(within(drawer).getByLabelText("¿Qué intenta responder este caso?"), {
        target: { value: "Si el andamio tolera el sustituyente" },
      });
      fireEvent.click(within(drawer).getByRole("button", { name: /cerrar detalles/i }));

      act(() => declareReportable?.(REPORTABLE));
      fireEvent.click(await screen.findByRole("button", { name: /abrir informe/i }));

      // El visor recibe el caso abierto: es lo que necesita para proyectarlo.
      const viewer = await screen.findByTestId("case-dossier");
      expect(viewer.getAttribute("data-case")).toBeTruthy();
      expect(viewer).toHaveTextContent(`dossier:${REPORTABLE.moleculeId}`);

      // El contexto científico NO se repite encima del visor: ya viaja en la
      // proyección y se imprime dentro del PDF, que es el documento que
      // circula. Mantener dos redacciones dejaría envejecer la de la pantalla.
      expect(screen.queryByText("Propósito y contexto del caso")).not.toBeInTheDocument();
      expect(screen.queryByText("Si el andamio tolera el sustituyente")).not.toBeInTheDocument();
    });

    it("«Volver a Evaluación» devuelve al trabajo sin desmontar el runner", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Ida y vuelta");
      await waitFor(() => expect(declareReportable).not.toBeNull());
      act(() => declareReportable?.(REPORTABLE));
      fireEvent.click(await screen.findByRole("button", { name: /abrir informe/i }));
      await screen.findByTestId("case-dossier");

      const mountsBefore = mounts.length;
      fireEvent.click(screen.getByRole("button", { name: /volver a evaluación/i }));

      await waitFor(() =>
        expect(screen.getByRole("tab", { name: "Evaluación" })).toHaveAttribute(
          "aria-selected",
          "true",
        ),
      );
      // El runner pesado no se ha vuelto a montar: estaba oculto, no desmontado.
      expect(mounts.length).toBe(mountsBefore);
    });

    it("si el resultado guardado desaparece, el informe se retira sin dejar un destino vacío", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Sesión cambiada");
      await waitFor(() => expect(declareReportable).not.toBeNull());
      act(() => declareReportable?.(REPORTABLE));
      fireEvent.click(await screen.findByRole("button", { name: /abrir informe/i }));
      await screen.findByTestId("case-dossier");

      // El runner limpia el resultado (cambio de sesión, corrida nueva…).
      act(() => declareReportable?.(null));

      await waitFor(() => expect(screen.queryByTestId("case-dossier")).not.toBeInTheDocument());
      expect(screen.queryByRole("tab", { name: "Informe" })).not.toBeInTheDocument();
      expect(screen.getByTestId("runner")).toBeInTheDocument();
    });

    it("declara honestamente que no pudo recuperar el resultado de una corrida completada", async () => {
      const { repository } = renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Irrecuperable");
      const [entry] = await repository.listCases();

      // El caso guarda una corrida COMPLETADA: se esperaba evidencia.
      await act(async () => {
        await repository.updateCase({
          ...(await repository.readCase(entry.id)),
          activeRun: {
            taskId: "task-perdida-0001",
            executionState: "completed",
            startedAt: "2026-08-01T10:00:00.000Z",
          },
        });
      });
      // Se reabre, como haría un reinicio.
      const reopened = renderWorkspace();
      const nav = await within(reopened.container.ownerDocument.body).findAllByRole("navigation", {
        name: "Casos",
      });
      fireEvent.click(within(nav[nav.length - 1]).getAllByText("Irrecuperable")[0]);
      await waitFor(() => expect(declareRecovery).not.toBeNull());

      act(() => declareRecovery?.("unrecoverable"));

      // No hay «Informe» vacío: se dice en Evaluación, con el identificador.
      expect(
        await screen.findByText(/su resultado no se ha podido recuperar/i),
      ).toBeInTheDocument();
      expect(screen.getAllByText(/task-perdida-0001/).length).toBeGreaterThan(0);
      expect(screen.queryByRole("tab", { name: "Informe" })).not.toBeInTheDocument();
    });
  });

  describe("aislamiento entre casos", () => {
    it("remonta el runner con el id del caso nuevo", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");

      await createCaseViaUi("Caso uno");
      await waitFor(() => expect(screen.getByTestId("runner")).toBeInTheDocument());
      const firstId = mounts[mounts.length - 1];

      await createCaseViaUi("Caso dos");
      await waitFor(() => {
        expect(mounts[mounts.length - 1]).not.toBe(firstId);
      });

      // Dos identidades distintas ⇒ dos instancias distintas del runner. No hay
      // instancia compartida donde SMILES o resultado pudieran filtrarse.
      const distinct = new Set(mounts);
      expect(distinct.size).toBeGreaterThanOrEqual(2);
      expect(screen.getByTestId("runner")).toHaveTextContent(mounts[mounts.length - 1]);
    });

    it("el informe de un caso no se enseña en otro", async () => {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Con dossier");
      await waitFor(() => expect(declareReportable).not.toBeNull());
      act(() => declareReportable?.(REPORTABLE));
      expect(await screen.findByRole("tab", { name: "Informe" })).toBeInTheDocument();

      await createCaseViaUi("Recién creado");
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: "Recién creado" })).toBeInTheDocument(),
      );
      // El caso nuevo no hereda la evidencia del anterior.
      expect(screen.queryByRole("tab", { name: "Informe" })).not.toBeInTheDocument();
      expect(screen.queryByTestId("case-dossier")).not.toBeInTheDocument();
    });
  });

  describe("trabajo vivo", () => {
    async function dosCasosAbiertos() {
      renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Primero");
      await createCaseViaUi("Segundo");
      await waitFor(() => expect(declareLiveWork).not.toBeNull());
    }

    it("impide cambiar de caso DURANTE el envío, antes de que exista taskId", async () => {
      await dosCasosAbiertos();

      // `submitting` se enciende ANTES de la petición: en esa ventana todavía
      // no hay `taskId`, y era justo cuando el guard no protegía nada.
      act(() => declareLiveWork?.({ evaluation: true, taskId: null }));

      const nav = screen.getByRole("navigation", { name: "Casos" });
      const otro = within(nav).getByText("Primero").closest("button");
      await waitFor(() => expect(otro).toBeDisabled());
      expect(screen.getByRole("heading", { name: "Segundo" })).toBeInTheDocument();

      act(() => declareLiveWork?.({ evaluation: false, taskId: null }));
      await waitFor(() => expect(otro).toBeEnabled());
    });

    it("impide cambiar de caso durante MM/GBSA, que no pasa por taskId", async () => {
      await dosCasosAbiertos();

      // MM-GBSA es un cálculo largo sin `taskId`: sin declararlo, el workspace
      // lo daría por inexistente y dejaría cambiar de caso a mitad.
      act(() => declareLiveWork?.({ analysis: true }));

      const nav = screen.getByRole("navigation", { name: "Casos" });
      const otro = within(nav).getByText("Primero").closest("button");
      await waitFor(() => expect(otro).toBeDisabled());

      act(() => declareLiveWork?.({ analysis: false }));
      await waitFor(() => expect(otro).toBeEnabled());
    });

    it("deshabilita también «Nuevo caso» mientras hay trabajo vivo", async () => {
      await dosCasosAbiertos();
      const nav = screen.getByRole("navigation", { name: "Casos" });
      const nuevo = within(nav).getByRole("button", { name: /nuevo caso/i });
      expect(nuevo).toBeEnabled();

      act(() => declareLiveWork?.({ evaluation: true }));
      // Crear reemplazaría el caso activo igual que seleccionar: el guard tiene
      // que cubrir las dos rutas, no sólo la lista.
      await waitFor(() => expect(nuevo).toBeDisabled());
    });
  });

  describe("archivar", () => {
    it("archiva y restaura sin borrar", async () => {
      const { repository } = renderWorkspace();
      await screen.findByText("Crea un caso de estudio");
      await createCaseViaUi("Archivable");

      const nav = screen.getByRole("navigation", { name: "Casos" });
      fireEvent.click(within(nav).getByRole("button", { name: /archivar archivable/i }));

      await waitFor(async () => {
        const list = await repository.listCases();
        expect(list[0].archived).toBe(true);
      });
      expect(await within(nav).findByText("Archivados")).toBeInTheDocument();

      fireEvent.click(within(nav).getByRole("button", { name: /restaurar archivable/i }));
      await waitFor(async () => {
        const list = await repository.listCases();
        expect(list[0].archived).toBe(false);
      });
    });
  });
});

// =====================================================================
// Un informe anterior no es evidencia de la hipótesis nueva
// =====================================================================
//
// EL ERROR MÁS CARO QUE PUEDE COMETER ESTE PRODUCTO: enseñar el dossier de una
// corrida como si respondiera a los inputs que hay ahora en pantalla. El
// informe no se retira —eso perdería trazabilidad— pero se etiqueta.

describe("atribución del informe", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mounts.length = 0;
    declareReportable = null;
  });

  async function caseWithRun(fingerprint: string | undefined, preflightFingerprint: string | null) {
    const { repository } = renderWorkspace();
    await screen.findByText("Crea un caso de estudio");
    await createCaseViaUi("Con corrida");
    const [entry] = await repository.listCases();

    await act(async () => {
      const record = await repository.readCase(entry.id);
      await repository.updateCase({
        ...record,
        activeRun: {
          taskId: "task-anterior",
          executionState: "completed",
          startedAt: "2026-08-24T09:00:00.000Z",
          ...(fingerprint ? { inputFingerprint: fingerprint } : {}),
        },
        ...(preflightFingerprint
          ? {
              preflight: {
                fingerprint: preflightFingerprint,
                inputDocument: "{}",
                generatedAt: "2026-08-24T10:00:00.000Z",
                schemaVersion: 1,
                executionRoute: "docking_vina",
                blockers: [],
                warnings: [],
                notEvaluated: [],
                receptorLabel: "7E2Y · cadena A",
                ligandLabel: "CCO",
                gridLabel: "(1.00, 2.00, 3.00)",
              },
            }
          : {}),
      });
    });

    // Se reabre para que el workspace lea el manifiesto actualizado.
    const reopened = renderWorkspace();
    const navs = await within(reopened.container.ownerDocument.body).findAllByRole("navigation", {
      name: "Casos",
    });
    fireEvent.click(within(navs[navs.length - 1]).getAllByText("Con corrida")[0]);
    await waitFor(() => expect(declareReportable).not.toBeNull());
    act(() => declareReportable?.(REPORTABLE));
    return reopened;
  }

  it("mantiene la disposición fuera de Evaluación y dentro del informe desplazable", async () => {
    await caseWithRun("sha256:misma", "sha256:misma");

    expect(screen.queryByRole("heading", { name: "Disposición científica" })).not.toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /abrir informe/i }));

    expect(await screen.findByRole("heading", { name: "Disposición científica" })).toBeInTheDocument();
    expect(screen.getByTestId("case-dossier")).toBeInTheDocument();
  });
  it("con la misma huella, el informe se presenta sin salvedades", async () => {
    await caseWithRun("sha256:misma", "sha256:misma");

    fireEvent.click(await screen.findByRole("button", { name: /abrir informe/i }));
    await screen.findByTestId("case-dossier");

    expect(screen.queryByText(/corrida anterior/i)).not.toBeInTheDocument();
  });

  it("si los inputs cambiaron, el informe se etiqueta como de una corrida anterior", async () => {
    await caseWithRun("sha256:vieja", "sha256:nueva");

    // La llamada ya lo advierte antes de abrir nada.
    expect(await screen.findByText(/corrida ANTERIOR/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /abrir informe/i }));
    expect(await screen.findByText(/Este informe es de una corrida anterior/i)).toBeInTheDocument();
    // Y NO se retira: la trazabilidad se conserva.
    expect(screen.getByTestId("case-dossier")).toBeInTheDocument();
  });

  it("una corrida sin huella no se atribuye a los inputs actuales", async () => {
    await caseWithRun(undefined, "sha256:nueva");

    fireEvent.click(await screen.findByRole("button", { name: /abrir informe/i }));
    expect(
      await screen.findByText(/No se puede afirmar a qué inputs corresponde/i),
    ).toBeInTheDocument();
  });
});
