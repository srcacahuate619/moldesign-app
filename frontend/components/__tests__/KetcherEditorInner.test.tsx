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
    const ketcher = {
      setSettings: vi.fn(),
      setMolecule: vi.fn(() => initialLoad),
      getSmiles,
    };
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
    expect(getSmiles).toHaveBeenCalledTimes(1);
    expect(onSmilesChange).not.toHaveBeenCalled();

    getSmiles.mockResolvedValueOnce("");
    await vi.advanceTimersByTimeAsync(500);
    expect(onSmilesChange).toHaveBeenCalledWith("");
  });

  it("un SMILES inválido tecleado no se sustituye en silencio por la molécula anterior", async () => {
    // QA-020: Ketcher rechazaba «C1CCCC», el lienzo seguía con la molécula
    // anterior y el sondeo la devolvía al campo: se evaluaba otra molécula.
    const ketcher = {
      setSettings: vi.fn(),
      setMolecule: vi.fn(async (smiles: string) => {
        if (smiles === "C1CCCC") throw new Error("anillo sin cerrar");
      }),
      getSmiles: vi.fn(async () => "CCO"),
    };
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
});
