/**
 * Las conversiones de moléculas pequeñas ya no le llevan la biblioteca de monómeros al worker de Indigo, que la perdía
 * (~1,3 MB por conversión, ver `lib/indigoSinFuga.ts`). Las de macromoléculas, sí.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { cuentaDeIndigo, necesitaLaBibliotecaDeMonomeros, protegerWorkerDeIndigo } from "../indigoSinFuga";

const BIBLIOTECA = JSON.stringify({ root: { templates: [{ $ref: "monomerTemplate-A" }] }, relleno: "x".repeat(2000) });
const conversion = (struct: string, format: string, entrada?: string) => ({
  type: 1,
  data: { struct, format, options: { "input-format": entrada, "smart-layout": "true", monomerLibrary: BIBLIOTECA } },
});

function workerFalso() {
  const recibidos: unknown[] = [];
  return { recibidos, postMessage: vi.fn((m: unknown) => { recibidos.push(m); }) };
}

afterEach(() => { delete (globalThis as { isPolymerEditorTurnedOn?: boolean }).isPolymerEditorTurnedOn; });

describe("cuándo hace falta la biblioteca de monómeros", () => {
  it("no para una molécula pequeña en SMILES, molfile o KET", () => {
    expect(necesitaLaBibliotecaDeMonomeros(conversion("CCO", "ket", "smiles").data, false)).toBe(false);
    expect(necesitaLaBibliotecaDeMonomeros(conversion('{"root":{"nodes":[{"$ref":"mol0"}]}}', "smiles").data, false)).toBe(false);
    expect(necesitaLaBibliotecaDeMonomeros(conversion("CCO", "molfile").data, false)).toBe(false);
  });

  it("sí en el modo de macromoléculas, con formatos de secuencia o con monómeros en la estructura", () => {
    expect(necesitaLaBibliotecaDeMonomeros(conversion("CCO", "ket", "smiles").data, true)).toBe(true);
    expect(necesitaLaBibliotecaDeMonomeros(conversion("ACGT", "ket", "sequence").data, false)).toBe(true);
    expect(necesitaLaBibliotecaDeMonomeros(conversion("PEPTIDE1{A}$$$$V2.0", "ket", "helm").data, false)).toBe(true);
    expect(necesitaLaBibliotecaDeMonomeros(conversion('{"root":{}}', "fasta").data, false)).toBe(true);
    expect(necesitaLaBibliotecaDeMonomeros(conversion('{"monomer0":{"type":"monomer"}}', "smiles").data, false)).toBe(true);
  });

  it("ante un formato que no conoce, la deja", () => {
    expect(necesitaLaBibliotecaDeMonomeros(conversion("x", "formato-nuevo").data, false)).toBe(true);
  });
});

describe("la envoltura del worker", () => {
  it("quita la biblioteca de las conversiones que no la necesitan y deja el resto igual", () => {
    const w = workerFalso();
    protegerWorkerDeIndigo(w);
    const original = conversion("CCO", "ket", "smiles");
    w.postMessage(original);
    const enviado = w.recibidos[0] as typeof original;
    expect(enviado.data.options).not.toHaveProperty("monomerLibrary");
    expect(enviado.data.options["smart-layout"]).toBe("true");
    expect(enviado.data.struct).toBe("CCO");
    // El mensaje de Ketcher no se toca: puede volver a usarlo.
    expect(original.data.options.monomerLibrary).toBe(BIBLIOTECA);
  });

  it("la deja en las de macromoléculas", () => {
    const w = workerFalso();
    protegerWorkerDeIndigo(w);
    (globalThis as { isPolymerEditorTurnedOn?: boolean }).isPolymerEditorTurnedOn = true;
    w.postMessage(conversion("CCO", "ket", "smiles"));
    expect((w.recibidos[0] as ReturnType<typeof conversion>).data.options.monomerLibrary).toBe(BIBLIOTECA);
  });

  it("no toca los mensajes que no son conversiones ni envuelve dos veces", () => {
    const w = workerFalso();
    protegerWorkerDeIndigo(w);
    const envuelto = w.postMessage;
    protegerWorkerDeIndigo(w);
    expect(w.postMessage).toBe(envuelto);
    const otro = { type: 2, data: { struct: "CCO", options: { monomerLibrary: BIBLIOTECA } } };
    w.postMessage(otro);
    expect(w.recibidos[0]).toBe(otro);
  });

  it("protegido el prototipo, lo están todos los workers, también los que se crean después", () => {
    class WorkerDePrueba { recibidos: unknown[] = []; postMessage(m: unknown) { this.recibidos.push(m); } }
    protegerWorkerDeIndigo(WorkerDePrueba.prototype);
    const w = new WorkerDePrueba();
    w.postMessage(conversion("CCO", "smiles"));
    expect((w.recibidos[0] as ReturnType<typeof conversion>).data.options).not.toHaveProperty("monomerLibrary");
  });

  it("cuenta lo que deja de enviar", () => {
    const antes = { ...cuentaDeIndigo };
    const w = workerFalso();
    protegerWorkerDeIndigo(w);
    w.postMessage(conversion("CCO", "ket", "smiles"));
    expect(cuentaDeIndigo.sinBiblioteca - antes.sinBiblioteca).toBe(1);
    expect(cuentaDeIndigo.mbNoEnviados).toBeGreaterThan(antes.mbNoEnviados);
  });
});
