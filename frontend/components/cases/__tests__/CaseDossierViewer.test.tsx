// =====================================================================
// CaseDossierViewer — el dossier que se ve es el del caso que se mira
// =====================================================================
//
// LO QUE ESTE ARCHIVO PROTEGE, en orden de gravedad:
//
// 1. **Atribución.** Una respuesta tardía de otro caso NO puede reemplazar el
//    dossier en pantalla. Es el fallo más caro que puede cometer este producto:
//    un documento que afirma describir una hipótesis y describe otra.
//
// 2. **Honestidad del fallo.** Un 409 dice lo que dice el backend y ofrece
//    reintentar; no se degrada a un visor vacío ni a un PDF de otra corrida.
//
// 3. **Ninguna afirmación de más.** Descargar el ZIP no lo declara verificado:
//    lo único que se afirma es que se descargó, y que la verificación la hace
//    quien lo reciba con el manifiesto que viaja dentro.
//
// 4. **Higiene.** Los object URL se revocan al actualizar, al cambiar de caso y
//    al desmontar.

import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { CaseDossierViewer } from "../CaseDossierViewer";
import { resetApiUrl, setApiUrlFromPort } from "../../../lib/config";
import { mockFetch } from "../../../vitest.setup";
import type { CaseRecord, ReportableResult } from "../../../lib/cases/types";

// ── Object URL: jsdom no los implementa ──────────────────────────────
const created: string[] = [];
const revoked: string[] = [];
let objectUrlSeq = 0;

function installObjectUrls() {
  const urlApi = window.URL as unknown as Record<string, unknown>;
  urlApi.createObjectURL = () => {
    const url = `blob:mock/${objectUrlSeq++}`;
    created.push(url);
    return url;
  };
  urlApi.revokeObjectURL = (url: string) => {
    revoked.push(url);
  };
}

const REPORTABLE: ReportableResult = {
  taskId: "task-abcdef123456",
  moleculeId: "mol-0001",
  certified: false,
};

const OTHER_REPORTABLE: ReportableResult = {
  taskId: "task-999999999999",
  moleculeId: "mol-0002",
  certified: false,
};

function caseRecord(overrides: Partial<CaseRecord> = {}): CaseRecord {
  return {
    schemaVersion: 3,
    id: "case-0001",
    name: "Serie de anilinas",
    createdAt: "2026-08-01T09:00:00.000Z",
    updatedAt: "2026-08-01T09:30:00.000Z",
    lastOpenedAt: "2026-08-01T09:30:00.000Z",
    status: "review",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    runs: [],
    activeView: "report",
    context: { question: "¿Tolera el andamio el sustituyente?" },
    archived: false,
    inputs: {
      receptor: { pdbId: "7E2Y", chain: "A", origin: "curado" },
      ligand: { inputSmiles: "CCO" },
    },
    activeRun: {
      taskId: REPORTABLE.taskId,
      executionState: "completed",
      startedAt: "2026-08-01T09:12:00.000Z",
      inputFingerprint: "sha256:0123456789abcdef",
    },
    ...overrides,
  };
}

function pdf(disposition?: string): Response {
  const headers = new Headers({ "content-type": "application/pdf" });
  if (disposition) headers.set("content-disposition", disposition);
  return new Response("%PDF-1.4", { status: 200, headers });
}

function zip(disposition?: string): Response {
  const headers = new Headers({ "content-type": "application/zip" });
  if (disposition) headers.set("content-disposition", disposition);
  return new Response("PK", { status: 200, headers });
}

function jsonError(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** Una promesa que se resuelve cuando el test quiera. Para carreras. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function lastRequest(): [string, RequestInit] {
  const calls = mockFetch.mock.calls;
  return calls[calls.length - 1] as unknown as [string, RequestInit];
}

describe("CaseDossierViewer", () => {
  beforeEach(() => {
    created.length = 0;
    revoked.length = 0;
    objectUrlSeq = 0;
    installObjectUrls();
    resetApiUrl();
    setApiUrlFromPort(8017);
  });

  afterEach(() => {
    resetApiUrl();
  });

  it("pide el dossier por POST al abrir el informe, y lo muestra", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );

    // Mientras llega, se dice que está generándose.
    expect(screen.getByText(/Generando el dossier del caso/i)).toBeInTheDocument();

    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    const [url, init] = lastRequest();
    expect(init.method).toBe("POST");
    expect(url).toBe("http://127.0.0.1:8017/evaluation/dossier/mol-0001/preview");
    // NO se usa la ruta histórica del certificado.
    expect(url).not.toContain("/blockchain/");

    // El caso viaja completo en el cuerpo, en snake_case.
    const body = JSON.parse(init.body as string);
    expect(body.case_id).toBe("case-0001");
    expect(body.run.task_id).toBe(REPORTABLE.taskId);
    expect(body.inputs.receptor.pdb_id).toBe("7E2Y");
    expect(body.run_inputs_relation).toBe("corresponde");

    expect(screen.getByTitle("Dossier del caso")).toHaveAttribute(
      "src",
      `${created[0]}#toolbar=0`,
    );
  });

  it("la advertencia de una corrida anterior viaja en la proyección", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corrida_anterior"
      />,
    );
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const [, init] = lastRequest();
    expect(JSON.parse(init.body as string).run_inputs_relation).toBe("corrida_anterior");
  });

  it("una corrida sin huella se declara desconocida, no correspondiente", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="desconocida"
      />,
    );
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    expect(JSON.parse(lastRequest()[1].body as string).run_inputs_relation).toBe("desconocida");
  });

  it("un 409 dice lo que dijo el backend y deja reintentar", async () => {
    const detail = "El caso pide la corrida solicitada y el resultado almacenado pertenece a otra.";
    mockFetch.mockResolvedValueOnce(jsonError(409, detail));

    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );

    expect(await screen.findByText("No se pudo generar el dossier")).toBeInTheDocument();
    expect(screen.getByText(detail)).toBeInTheDocument();
    // Nada se muestra como si fuera el dossier.
    expect(screen.queryByTitle("Dossier del caso")).not.toBeInTheDocument();

    mockFetch.mockResolvedValueOnce(pdf());
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it.each([
    [404, "No existe la molécula solicitada."],
    [422, "El contrato rechazó un campo."],
    [500, "Fallo interno del motor."],
  ])("permite reintentar tras un %i", async (status, detail) => {
    mockFetch.mockResolvedValueOnce(jsonError(status as number, detail as string));
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );

    expect(await screen.findByText(detail as string)).toBeInTheDocument();
    mockFetch.mockResolvedValueOnce(pdf());
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());
  });

  it("un fallo de conexión se declara como tal, no como caso inválido", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );

    expect(await screen.findByText(/conexión/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeEnabled();
  });

  it("«Actualizar dossier» pide otro PDF y revoca el anterior", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());
    const first = created[0];

    mockFetch.mockResolvedValueOnce(pdf());
    fireEvent.click(screen.getByRole("button", { name: /actualizar dossier/i }));

    await waitFor(() => expect(created.length).toBe(2));
    expect(revoked).toContain(first);
    await waitFor(() =>
      expect(screen.getByTitle("Dossier del caso")).toHaveAttribute(
        "src",
        `${created[1]}#toolbar=0`,
      ),
    );
  });

  it("mientras el dossier se genera, «Actualizar» está deshabilitado", async () => {
    const pending = deferred<Response>();
    mockFetch.mockReturnValueOnce(pending.promise as unknown as Promise<Response>);

    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );

    const refresh = screen.getByRole("button", { name: /actualizar dossier/i });
    expect(refresh).toBeDisabled();
    // Y no se puede descargar lo que todavía no existe.
    expect(screen.getByRole("button", { name: /descargar pdf/i })).toBeDisabled();

    await act(async () => {
      pending.resolve(pdf());
    });
    await waitFor(() => expect(refresh).toBeEnabled());
  });

  it("descarga el PDF con el nombre que compone el backend", async () => {
    mockFetch.mockResolvedValueOnce(pdf('inline; filename="dossier_Serie-de-anilinas.pdf"'));
    const clicks: string[] = [];
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicks.push(this.download);
      });

    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /descargar pdf/i }));
    clickSpy.mockRestore();

    expect(clicks).toEqual(["dossier_Serie-de-anilinas.pdf"]);
    // Descargar NO vuelve a pedir el dossier: se guarda el que ya se está viendo.
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("si el backend no propone nombre, el del PDF se deriva del caso", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    const clicks: string[] = [];
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicks.push(this.download);
      });

    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /descargar pdf/i }));
    clickSpy.mockRestore();

    expect(clicks).toEqual(["dossier_Serie-de-anilinas.pdf"]);
  });

  it("exporta el ZIP por POST y NO lo declara verificado", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    mockFetch.mockResolvedValueOnce(
      zip('attachment; filename="moldesign_case_case-0001_run_task-abcdef1.zip"'),
    );
    fireEvent.click(screen.getByRole("button", { name: /exportar paquete zip/i }));

    const notice = await screen.findByText(/Paquete descargado como/i);
    clickSpy.mockRestore();

    const [url, init] = lastRequest();
    expect(url).toBe("http://127.0.0.1:8017/evaluation/dossier/mol-0001/package");
    expect(init.method).toBe("POST");

    // Se afirma que se descargó. NADA sobre que esté verificado.
    expect(notice.textContent).toMatch(/la verificación la hace quien lo reciba/i);
    expect(screen.queryByText(/verificad[oa]\b(?!.*quien)/i)).not.toBeInTheDocument();
  });

  it("mientras el paquete se exporta, su botón no acepta otra pulsación", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    const pending = deferred<Response>();
    mockFetch.mockReturnValueOnce(pending.promise as unknown as Promise<Response>);
    const button = screen.getByRole("button", { name: /exportar paquete zip/i });
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByRole("button", { name: /exportando/i })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: /exportando/i }));
    // Sigue habiendo UNA sola petición de paquete: la de la primera pulsación.
    expect(mockFetch).toHaveBeenCalledTimes(2);

    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await act(async () => {
      pending.resolve(zip());
    });
    clickSpy.mockRestore();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /exportar paquete zip/i })).toBeEnabled(),
    );
  });

  it("cancela el paquete al abandonar Informe y no descarga una respuesta tardía", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    const view = render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    const pending = deferred<Response>();
    mockFetch.mockReturnValueOnce(pending.promise as unknown as Promise<Response>);
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    fireEvent.click(screen.getByRole("button", { name: /exportar paquete zip/i }));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));

    const [, init] = lastRequest();
    view.unmount();
    expect((init.signal as AbortSignal).aborted).toBe(true);

    await act(async () => {
      pending.resolve(zip());
    });
    expect(clickSpy).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("el fallo del paquete NO tumba el dossier que ya se está viendo", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    mockFetch.mockResolvedValueOnce(jsonError(409, "El resultado almacenado pertenece a otra."));
    fireEvent.click(screen.getByRole("button", { name: /exportar paquete zip/i }));

    expect(await screen.findByText(/No se pudo exportar el paquete/i)).toBeInTheDocument();
    expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument();
  });

  it("una respuesta tardía de OTRO caso no reemplaza el dossier actual", async () => {
    const slow = deferred<Response>();
    mockFetch.mockReturnValueOnce(slow.promise as unknown as Promise<Response>);

    const view = render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));

    // Se cambia de caso con la primera petición todavía en vuelo.
    mockFetch.mockResolvedValueOnce(pdf());
    view.rerender(
      <CaseDossierViewer
        caseRecord={caseRecord({ id: "case-0002", name: "Otro caso" })}
        reportable={OTHER_REPORTABLE}
        runRelation="desconocida"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());
    const currentSrc = screen.getByTitle("Dossier del caso").getAttribute("src");

    // Ahora contesta la petición del caso ANTERIOR.
    await act(async () => {
      slow.resolve(pdf());
    });

    // El dossier en pantalla sigue siendo el del caso abierto.
    expect(screen.getByTitle("Dossier del caso")).toHaveAttribute("src", currentSrc as string);
    // Y la petición del segundo caso apuntaba a su propia molécula.
    expect((mockFetch.mock.calls[1] as unknown as [string])[0]).toContain("mol-0002");
  });

  it("un fallo tardío del caso anterior no se pinta sobre el caso nuevo", async () => {
    const slow = deferred<Response>();
    mockFetch.mockReturnValueOnce(slow.promise as unknown as Promise<Response>);

    const view = render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));

    mockFetch.mockResolvedValueOnce(pdf());
    view.rerender(
      <CaseDossierViewer
        caseRecord={caseRecord({ id: "case-0002", name: "Otro caso" })}
        reportable={OTHER_REPORTABLE}
        runRelation="desconocida"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    await act(async () => {
      slow.resolve(jsonError(409, "Corrida ajena"));
    });

    expect(screen.queryByText("No se pudo generar el dossier")).not.toBeInTheDocument();
    expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument();
  });

  it("al cambiar de caso se revoca el object URL del anterior", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    const view = render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(created.length).toBe(1));
    const first = created[0];

    mockFetch.mockResolvedValueOnce(pdf());
    view.rerender(
      <CaseDossierViewer
        caseRecord={caseRecord({ id: "case-0002" })}
        reportable={OTHER_REPORTABLE}
        runRelation="desconocida"
      />,
    );

    await waitFor(() => expect(revoked).toContain(first));
  });

  it("al desmontar se revoca el object URL vivo", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(created.length).toBe(1));

    cleanup();

    expect(revoked).toContain(created[0]);
  });

  it("no ofrece registrar integridad ni menciona la cadena", async () => {
    mockFetch.mockResolvedValueOnce(pdf());
    render(
      <CaseDossierViewer
        caseRecord={caseRecord()}
        reportable={REPORTABLE}
        runRelation="corresponde"
      />,
    );
    await waitFor(() => expect(screen.getByTitle("Dossier del caso")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /registrar integridad/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/blockchain|cadena|certificad/i)).not.toBeInTheDocument();
  });
});
