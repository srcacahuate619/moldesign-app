import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const editorHarness = vi.hoisted(() => ({
  onInit: null as null | ((ketcher: unknown) => Promise<void>),
}));

vi.mock("ketcher-react", () => ({
  Editor: (props: { onInit: (ketcher: unknown) => Promise<void> }) => {
    editorHarness.onInit = props.onInit;
    return <div data-testid="ketcher-editor" />;
  },
}));

vi.mock("ketcher-standalone", () => ({
  StandaloneStructServiceProvider: class {},
}));

import KetcherEditorInner from "../KetcherEditorInner";
import { createEditorReadBudget, currentEditorReader } from "../../lib/editorSnapshot";

/**
 * El `editor` de Ketcher 3.18: `subscribe("change")` es lo que la sincronización escucha desde el 2026-10-12 (antes era un
 * sondeo de 500 ms que llevaba a Indigo 1,57 MB por llamada, para siempre). `cambiar()` hace lo que Ketcher al terminar
 * una acción con historial.
 */
function conEditor<T extends object>(ketcher: T) {
  const oyentes = new Set<() => void>();
  const editor = {
    subscribe: vi.fn((nombre: string, oyente: () => void) => {
      if (nombre === "change") oyentes.add(oyente);
      return { oyente };
    }),
    unsubscribe: vi.fn((_nombre: string, suscripcion: { oyente: () => void }) => { oyentes.delete(suscripcion.oyente); }),
  };
  return { ketcher: { ...ketcher, editor }, editor, cambiar: () => oyentes.forEach((o) => o()), oyentes };
}

describe("KetcherEditorInner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    editorHarness.onInit = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("limita el número de exportaciones reales durante la vida del renderer", () => {
    const budget = createEditorReadBudget(2);
    expect(budget.claim()).toBe(true);
    expect(budget.claim()).toBe(true);
    expect(budget.claim()).toBe(false);
  });

  it("exporta bajo demanda, comparte lecturas y descarta la caché al editar o desmontar", async () => {
    let resolver!: (value: string) => void;
    const getMolfile = vi.fn().mockImplementationOnce(() => new Promise<string>((resolve) => { resolver = resolve; }))
      .mockResolvedValue("nuevo molfile");
    const harness = conEditor({ setSettings: vi.fn(), setMolecule: vi.fn(async () => {}),
      getSmiles: vi.fn(async () => "CCO"), getMolfile });
    const rendered = render(<KetcherEditorInner caseId="caso-1" initialSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => { await editorHarness.onInit!(harness.ketcher); });
    const reader = currentEditorReader("caso-1")!;
    expect(reader).toBeDefined();
    const first = reader.snapshot(), second = reader.snapshot();
    expect(getMolfile).toHaveBeenCalledTimes(1);
    resolver("primer molfile");
    const [a, b] = await Promise.all([first, second]);
    expect(a.status).toBe("ok");
    expect(b).toEqual(a);
    for (let i = 0; i < 100; i++) await reader.snapshot();
    expect(getMolfile).toHaveBeenCalledTimes(1);
    harness.cambiar();
    expect(a.status === "ok" && reader.check(a.revision)).toBe(false);
    expect((await reader.snapshot()).status).toBe("ok");
    expect(getMolfile).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(300001);
    await reader.snapshot();
    expect(getMolfile).toHaveBeenCalledTimes(3);
    rendered.unmount();
    expect(currentEditorReader("caso-1")).toBeUndefined();
  });

  it("rechaza dibujos demasiado grandes sin conservarlos en caché", async () => {
    const getMolfile = vi.fn().mockResolvedValue("x".repeat(262145));
    const harness = conEditor({ setSettings: vi.fn(), setMolecule: vi.fn(async () => {}),
      getSmiles: vi.fn(async () => "CCO"), getMolfile });
    render(<KetcherEditorInner caseId="caso-grande" initialSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => { await editorHarness.onInit!(harness.ketcher); });
    const reader = currentEditorReader("caso-grande")!;
    expect(await reader.snapshot()).toEqual({ status: "too_large" });
    expect(await reader.snapshot()).toEqual({ status: "too_large" });
    expect(getMolfile).toHaveBeenCalledTimes(2);
  });

  it("no confirma una lectura si el dibujo cambia mientras Ketcher la exporta", async () => {
    let resolver!: (value: string) => void;
    const harness = conEditor({ setSettings: vi.fn(), setMolecule: vi.fn(async () => {}),
      getSmiles: vi.fn(async () => "CCO"), getMolfile: vi.fn(() => new Promise<string>((resolve) => { resolver = resolve; })) });
    render(<KetcherEditorInner caseId="caso-2" initialSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => { await editorHarness.onInit!(harness.ketcher); });
    const reading = currentEditorReader("caso-2")!.snapshot();
    harness.cambiar();
    resolver("molfile anterior");
    expect(await reading).toEqual({ status: "changed" });
  });

  it("invalida la revisión cuando el campo ya cambió aunque el lienzo aún no se sincronice", async () => {
    const harness = conEditor({ setSettings: vi.fn(), setMolecule: vi.fn(async () => {}),
      getSmiles: vi.fn(async () => "CCO"), getMolfile: vi.fn(async () => "molfile") });
    const { rerender } = render(<KetcherEditorInner caseId="caso-cambio" initialSmiles="CCO" requestedSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => { await editorHarness.onInit!(harness.ketcher); });
    const reader = currentEditorReader("caso-cambio")!;
    const snapshot = await reader.snapshot();
    expect(snapshot.status).toBe("ok");
    rerender(<KetcherEditorInner caseId="caso-cambio" initialSmiles="CCO" requestedSmiles="CCC" onSmilesChange={vi.fn()} />);
    expect(snapshot.status === "ok" && reader.check(snapshot.revision)).toBe(false);
    expect(await reader.snapshot()).toEqual({ status: "not_ready" });
  });

  it("no confunde la carga o un error transitorio con el borrado del ligando", async () => {
    let finishInitialLoad!: () => void;
    const initialLoad = new Promise<void>((resolve) => {
      finishInitialLoad = resolve;
    });
    const getSmiles = vi.fn().mockRejectedValueOnce(new Error("Ketcher ocupado"));
    const { ketcher, cambiar } = conEditor({
      setSettings: vi.fn(),
      setMolecule: vi.fn(() => initialLoad),
      getSmiles,
    });
    const onSmilesChange = vi.fn();

    render(
      <KetcherEditorInner initialSmiles="CCOc1cC(O)=O" onSmilesChange={onSmilesChange} />,
    );

    let initialization!: Promise<void>;
    act(() => {
      initialization = editorHarness.onInit!(ketcher);
    });
    await vi.advanceTimersByTimeAsync(1_000);
    expect(getSmiles).not.toHaveBeenCalled();
    expect(onSmilesChange).not.toHaveBeenCalled();

    await act(async () => {
      finishInitialLoad();
      await initialization;
    });
    await vi.advanceTimersByTimeAsync(500);
    // Dos lecturas: el eco tras cargar (QA-030) y la de cuando se habilita la sincronización.
    expect(getSmiles).toHaveBeenCalledTimes(2);
    expect(onSmilesChange).not.toHaveBeenCalled();

    getSmiles.mockResolvedValueOnce("");
    cambiar();
    await vi.advanceTimersByTimeAsync(500);
    expect(onSmilesChange).toHaveBeenCalledWith("");
  });

  it("un SMILES inválido tecleado no se sustituye en silencio por la molécula anterior", async () => {
    // QA-020: Ketcher rechazaba «C1CCCC», el lienzo seguía con la molécula
    // anterior y el sondeo la devolvía al campo: se evaluaba otra molécula.
    const { ketcher } = conEditor({
      setSettings: vi.fn(),
      setMolecule: vi.fn(async (smiles: string) => {
        if (smiles === "C1CCCC") throw new Error("anillo sin cerrar");
      }),
      getSmiles: vi.fn(async () => "CCO"),
    });
    const onSmilesChange = vi.fn();
    const { rerender } = render(
      <KetcherEditorInner initialSmiles="CCO" onSmilesChange={onSmilesChange} />,
    );
    await act(async () => {
      await editorHarness.onInit!(ketcher);
    });
    await vi.advanceTimersByTimeAsync(600);

    rerender(<KetcherEditorInner initialSmiles="C1CCCC" onSmilesChange={onSmilesChange} />);
    await vi.advanceTimersByTimeAsync(2_000);

    expect(ketcher.setMolecule).toHaveBeenCalledWith("C1CCCC");
    expect(onSmilesChange).not.toHaveBeenCalledWith("CCO");
  });

  it("la reescritura de Ketcher de un SMILES tecleado no vuelve al campo", async () => {
    // QA-030: la geldanamicina tecleada con sus E/Z volvía al campo como el
    // CXSMILES de Ketcher (`|c:…|`, todos cis): otro estereoisómero.
    let lienzo = "CCO";
    // Como Ketcher: cargar una estructura también anuncia un cambio, y lo anuncia ANTES de que se pueda leer su eco.
    const harness = conEditor({
      setSettings: vi.fn(),
      setMolecule: vi.fn(async (smiles: string) => {
        lienzo = smiles === "C/C=C/C" ? "CC=CC |c:1|" : smiles;
        harness.cambiar();
      }),
      getSmiles: vi.fn(async () => lienzo),
    });
    const { ketcher, cambiar } = harness;
    const onSmilesChange = vi.fn();
    const { rerender } = render(
      <KetcherEditorInner initialSmiles="CCO" onSmilesChange={onSmilesChange} />,
    );
    await act(async () => {
      await editorHarness.onInit!(ketcher);
    });
    rerender(<KetcherEditorInner initialSmiles="C/C=C/C" onSmilesChange={onSmilesChange} />);
    await vi.advanceTimersByTimeAsync(2_000);

    expect(ketcher.setMolecule).toHaveBeenCalledWith("C/C=C/C");
    expect(onSmilesChange).not.toHaveBeenCalled();

    // Una edición real en el lienzo sí se comunica.
    lienzo = "CCN";
    cambiar();
    await vi.advanceTimersByTimeAsync(600);
    expect(onSmilesChange).toHaveBeenCalledWith("CCN");
  });

  it("con el lienzo quieto no le pregunta nada a Ketcher (cada pregunta lleva 1,57 MB a Indigo)", async () => {
    const { ketcher, cambiar } = conEditor({
      setSettings: vi.fn(),
      setMolecule: vi.fn(async () => {}),
      getSmiles: vi.fn(async () => "CCO"),
    });
    const onSmilesChange = vi.fn();
    render(<KetcherEditorInner initialSmiles="CCO" onSmilesChange={onSmilesChange} />);
    await act(async () => {
      await editorHarness.onInit!(ketcher);
    });
    await vi.advanceTimersByTimeAsync(1_000);
    const alHabilitarse = ketcher.getSmiles.mock.calls.length;
    // Una hora quieto: antes eran 7 200 lecturas.
    await vi.advanceTimersByTimeAsync(60 * 60 * 1_000);
    expect(ketcher.getSmiles).toHaveBeenCalledTimes(alHabilitarse);
    // Un trazo son varios cambios seguidos: una sola lectura cuando paran.
    cambiar(); cambiar(); cambiar();
    await vi.advanceTimersByTimeAsync(1_000);
    expect(ketcher.getSmiles).toHaveBeenCalledTimes(alHabilitarse + 1);
  });

  it("al desmontarse deja de escuchar a Ketcher", async () => {
    const { ketcher, editor, oyentes } = conEditor({
      setSettings: vi.fn(),
      setMolecule: vi.fn(async () => {}),
      getSmiles: vi.fn(async () => "CCO"),
    });
    const { unmount } = render(<KetcherEditorInner initialSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => {
      await editorHarness.onInit!(ketcher);
    });
    expect(oyentes.size).toBe(1);
    unmount();
    expect(editor.unsubscribe).toHaveBeenCalledWith("change", expect.anything());
    expect(oyentes.size).toBe(0);
  });

  it("si Ketcher está ocupado al leer un cambio, lo vuelve a intentar", async () => {
    const getSmiles = vi.fn(async () => "CCO");
    const { ketcher, cambiar } = conEditor({ setSettings: vi.fn(), setMolecule: vi.fn(async () => {}), getSmiles });
    const onSmilesChange = vi.fn();
    render(<KetcherEditorInner initialSmiles="CCO" onSmilesChange={onSmilesChange} />);
    await act(async () => {
      await editorHarness.onInit!(ketcher);
    });
    await vi.advanceTimersByTimeAsync(1_000);
    getSmiles.mockRejectedValueOnce(new Error("Ketcher ocupado")).mockResolvedValue("CCN");
    cambiar();
    await vi.advanceTimersByTimeAsync(2_000);
    expect(onSmilesChange).toHaveBeenCalledWith("CCN");
  });

  it("con la instancia de Ketcher ya destruida no tira la pantalla ni al montar ni al desmontar", async () => {
    // Ketcher lanza «couldn't find ketcher instance N» al leer `.editor` tras destruirse la instancia
    // (un caso nuevo remonta el editor): el efecto debe quedarse sin suscribir, no propagar el error.
    const muerto = { setSettings: vi.fn(), setMolecule: vi.fn(async () => {}), getSmiles: vi.fn(async () => "CCO"),
      get editor(): never { throw new Error("couldn't find ketcher instance 3"); } };
    const { unmount } = render(<KetcherEditorInner caseId="caso-muerto" initialSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => { await editorHarness.onInit!(muerto); });
    expect(currentEditorReader("caso-muerto")).toBeUndefined();
    expect(() => unmount()).not.toThrow();
  });

  it("si la instancia muere después de suscribir, el desmontaje tampoco lanza", async () => {
    let vivo = true;
    const editor = { subscribe: vi.fn(() => ({})), unsubscribe: vi.fn(() => { throw new Error("couldn't find ketcher instance 3"); }) };
    const ketcher = { setSettings: vi.fn(), setMolecule: vi.fn(async () => {}), getSmiles: vi.fn(async () => "CCO"),
      getMolfile: vi.fn(async () => "m"), get editor() { return vivo ? editor : (() => { throw new Error("couldn't find ketcher instance 3"); })(); } };
    const { unmount } = render(<KetcherEditorInner caseId="caso-vivo" initialSmiles="CCO" onSmilesChange={vi.fn()} />);
    await act(async () => { await editorHarness.onInit!(ketcher); });
    expect(currentEditorReader("caso-vivo")).toBeDefined();
    vivo = false;
    expect(() => unmount()).not.toThrow();
    expect(currentEditorReader("caso-vivo")).toBeUndefined();
  });
});
