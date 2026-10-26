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
});
