// =====================================================================
// MOLCHAT-AUD-01, eje FE/UX — el turno que falla, y lo que es cada número
// =====================================================================
//
// LOS FALLOS QUE VIGILA.
//
// 1. `sendMessage` hacía `if (!res.ok) { SET_STREAMING false; return; }`. El
//    mensaje del investigador quedaba en la lista, no llegaba respuesta y NADA
//    decía por qué. Con las correcciones de esta pestaña el backend ya contesta
//    con motivos accionables —403 sin consentimiento del destino, 503 si el
//    historial local no acepta escribir— y ninguno de ellos llegaba a la
//    pantalla.
//
// 2. `ChatInput` hacía `setInput("")` al enviar, sin esperar el desenlace. Un
//    turno fallido se llevaba el borrador con él.
//
// 3. No había reintento. El §8 lo pide idempotente: repetir el turno no puede
//    duplicar el mensaje del investigador.
//
// 4. El bloque de resultados de herramientas se renderizaba como una parte más
//    de la prosa del modelo. Desde la auditoría SCI cada resultado llega
//    etiquetado con su clase y su fuente —cálculo, dato persistido, inferencia,
//    recuperación externa—, y la interfaz tiene que conservar esa distinción:
//    es la mitad de pantalla del eje científico.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ChatInput } from "../ChatInput";
import { BloqueDeEvidencia, separarEvidencia } from "../BloqueDeEvidencia";

describe("el borrador sobrevive a un turno que falla", () => {
  it("se limpia cuando el envío sale bien", async () => {
    const onSend = vi.fn().mockResolvedValue({ ok: true });
    render(<ChatInput onSend={onSend} onStop={() => {}} isStreaming={false} />);

    const caja = screen.getByPlaceholderText(/pregunta/i);
    fireEvent.change(caja, { target: { value: "hola" } });
    fireEvent.keyDown(caja, { key: "Enter" });

    await waitFor(() => expect(onSend).toHaveBeenCalledWith("hola"));
    await waitFor(() => expect((caja as HTMLTextAreaElement).value).toBe(""));
  });

  it("se conserva cuando el envío falla", async () => {
    const onSend = vi.fn().mockResolvedValue({ ok: false, motivo: "sin permiso" });
    render(<ChatInput onSend={onSend} onStop={() => {}} isStreaming={false} />);

    const caja = screen.getByPlaceholderText(/pregunta/i);
    fireEvent.change(caja, { target: { value: "una pregunta cara de escribir" } });
    fireEvent.keyDown(caja, { key: "Enter" });

    await waitFor(() => expect(onSend).toHaveBeenCalled());
    await waitFor(() =>
      expect((caja as HTMLTextAreaElement).value).toBe("una pregunta cara de escribir"),
    );
  });
});

describe("la interfaz separa lo calculado de lo redactado", () => {
  const RESPUESTA = [
    "La aspirina cumple Lipinski.",
    "",
    "[Sistema: resultados de herramientas ejecutadas. Cada bloque declara QUÉ es y DE DÓNDE sale; conserva esa distinción al responder y cita la fuente cuando des un número:]",
    "[cálculo · RDKit (descriptores sobre el SMILES dado)] compute_properties: MW: 180.2 Da",
    "[inferencia (predicción de modelo, no medida) · ADMET-AI local (modelo entrenado, no medida)] predict_admet: LogS: -2.1",
  ].join("\n");

  it("saca el bloque de evidencia de la prosa del modelo", () => {
    const { prosa, evidencias } = separarEvidencia(RESPUESTA);

    expect(prosa).toBe("La aspirina cumple Lipinski.");
    expect(evidencias).toHaveLength(2);
    expect(evidencias[0].clase).toMatch(/cálculo/i);
    expect(evidencias[0].fuente).toMatch(/RDKit/);
    expect(evidencias[0].texto).toContain("MW: 180.2 Da");
  });

  it("una inferencia no se presenta como una medida", () => {
    const { evidencias } = separarEvidencia(RESPUESTA);

    expect(evidencias[1].clase).toMatch(/inferencia/i);
    expect(evidencias[1].fuente).toMatch(/ADMET-AI/);
  });

  it("un mensaje sin herramientas no inventa evidencia", () => {
    const { prosa, evidencias } = separarEvidencia("Sólo texto del modelo.");

    expect(prosa).toBe("Sólo texto del modelo.");
    expect(evidencias).toEqual([]);
  });

  it("cada evidencia se pinta con su clase y su fuente visibles", () => {
    const { evidencias } = separarEvidencia(RESPUESTA);
    render(<BloqueDeEvidencia evidencias={evidencias} />);

    const bloques = screen.getAllByTestId("evidencia");
    expect(bloques).toHaveLength(2);
    expect(bloques[0]).toHaveTextContent(/cálculo/i);
    expect(bloques[0]).toHaveTextContent(/RDKit/);
    expect(bloques[1]).toHaveTextContent(/inferencia/i);
  });

  it("un resultado sin clasificar se marca como no verificado", () => {
    const { evidencias } = separarEvidencia(
      "texto\n\n[Sistema: resultados de herramientas ejecutadas:]\n" +
        "[sin clasificar — trátalo como no verificado] rara: 42",
    );

    render(<BloqueDeEvidencia evidencias={evidencias} />);
    expect(screen.getByTestId("evidencia")).toHaveTextContent(/no verificado/i);
  });
});
