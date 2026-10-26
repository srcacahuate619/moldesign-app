// =====================================================================
// LUNA-05 — la tarjeta de aprobación de un docking propuesto por MolChat
// =====================================================================
//
// QUÉ SE VIGILA.
//
// 1. Aprobar es una llamada AUTENTICADA y propia: `aprobarPropuestaDeDocking(id,
//    hash)`. No se manda «sí» por el chat: un mensaje de texto no es una
//    aprobación.
// 2. El cuerpo lleva sólo la huella; la petición se arma en el servidor.
// 3. Dice la verdad cuando la propuesta ya no existe (404/410) y cuando falla: un
//    botón que parece vivo sobre una propuesta muerta es una promesa falsa.
// 4. `ChatMessage` extrae el marcador (el usuario no lo ve) y sólo muestra la
//    tarjeta cuando el mensaje terminó de llegar.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  aprobarPropuestaDeDocking: vi.fn(),
  rechazarPropuestaDeDocking: vi.fn(),
  consultarPropuestaDeDocking: vi.fn(),
}));
const enviarAlChat = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async () => {
  const real = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...real, ...api };
});
vi.mock("@/context/AIContext", () => ({
  useAI: () => ({
    sendMessage: enviarAlChat,
    state: { providers: [], activeProviderId: "local" },
  }),
}));

import { ApiError } from "@/lib/api";
import { PropuestaDeDocking, MARCADOR_DE_PROPUESTA } from "../PropuestaDeDocking";
import { ChatMessage } from "../ChatMessage";
import { TRANSLATIONS } from "../../../context/LanguageContext";

const ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
const HASH = "sha256:" + "ab12".repeat(16);
const MARCADOR = `<!--__DOCKING_PROPOSAL__ id=${ID} hash=${HASH}-->`;

beforeEach(() => {
  vi.clearAllMocks();
  api.consultarPropuestaDeDocking.mockResolvedValue({
    id: ID, estado: "pendiente", expira_en_s: 800, hash: HASH,
    resumen: { receptor: "7E2Y", cadena: "A", motor: "vina", coste: "40 s – 2 min" },
  });
});

describe("aprobar es una llamada propia, no un mensaje del chat", () => {
  it("lanza con el id y la huella, y no escribe «sí» en el chat", async () => {
    api.aprobarPropuestaDeDocking.mockResolvedValue({
      task_id: "task-9", target_pdb_id: "7E2Y", smiles_hash: "h", message: "ok",
    });
    render(<PropuestaDeDocking id={ID} hash={HASH} />);

    fireEvent.click(screen.getByRole("button", { name: /aprobar y lanzar/i }));

    await waitFor(() => expect(api.aprobarPropuestaDeDocking).toHaveBeenCalledWith(ID, HASH));
    expect(await screen.findByText(/task_id=task-9/)).toBeTruthy();
    expect(enviarAlChat).not.toHaveBeenCalled();
    // Ya lanzada: los botones desaparecen, no se puede aprobar dos veces desde la tarjeta.
    expect(screen.queryByRole("button", { name: /aprobar y lanzar/i })).toBeNull();
  });

  it("cancelar retira la propuesta y no lanza nada", async () => {
    api.rechazarPropuestaDeDocking.mockResolvedValue({ status: "rejected", id: ID });
    render(<PropuestaDeDocking id={ID} hash={HASH} />);

    fireEvent.click(screen.getByRole("button", { name: /cancelar propuesta/i }));

    await waitFor(() => expect(api.rechazarPropuestaDeDocking).toHaveBeenCalledWith(ID));
    expect(await screen.findByText(/no se lanzó nada/i)).toBeTruthy();
    expect(api.aprobarPropuestaDeDocking).not.toHaveBeenCalled();
  });

  it("recuerda, en la propia tarjeta, que escribir «sí» no lanza nada", () => {
    render(<PropuestaDeDocking id={ID} hash={HASH} />);
    expect(screen.getByText(/escribir «sí» en el chat no lanza nada/i)).toBeTruthy();
  });
});

describe("dice la verdad cuando la propuesta no existe o falla", () => {
  it("una propuesta caducada (410) al aprobar no deja botones vivos", async () => {
    api.aprobarPropuestaDeDocking.mockRejectedValue(
      new ApiError(410, JSON.stringify({ detail: "Esta propuesta ya no está pendiente" })),
    );
    render(<PropuestaDeDocking id={ID} hash={HASH} />);

    fireEvent.click(screen.getByRole("button", { name: /aprobar y lanzar/i }));

    expect(await screen.findByText(/ya no está pendiente/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /aprobar y lanzar/i })).toBeNull();
  });

  it("una tarjeta vieja de un historial recargado se marca al montarse", async () => {
    api.consultarPropuestaDeDocking.mockRejectedValue(new ApiError(410, "{}"));
    render(<PropuestaDeDocking id={ID} hash={HASH} />);

    expect(await screen.findByText(/ya no está pendiente/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /aprobar y lanzar/i })).toBeNull();
  });

  it("un rechazo del servidor (409: la preparación cambió) se muestra tal cual y se puede reintentar la lectura", async () => {
    api.aprobarPropuestaDeDocking.mockRejectedValue(
      new ApiError(409, JSON.stringify({ detail: "La hipótesis o la preparación cambió." })),
    );
    render(<PropuestaDeDocking id={ID} hash={HASH} />);

    fireEvent.click(screen.getByRole("button", { name: /aprobar y lanzar/i }));

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/la preparación cambió/i);
  });

  it("una consulta que falla por red no apaga la tarjeta: decide el servidor al aprobar", async () => {
    api.consultarPropuestaDeDocking.mockRejectedValue(new Error("sin red"));
    render(<PropuestaDeDocking id={ID} hash={HASH} />);

    await waitFor(() => expect(api.consultarPropuestaDeDocking).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: /aprobar y lanzar/i })).toBeTruthy();
  });
});

describe("ChatMessage y el marcador", () => {
  const texto = `**Propuesta de evaluación — todavía NO lanzada.**\n\n- **Receptor:** 7E2Y\n\n${MARCADOR}`;

  it("el marcador se extrae del texto y aparece la tarjeta", () => {
    render(
      <ChatMessage message={{ id: "1", role: "assistant", content: texto } as never} isStreaming={false} />,
    );
    expect(screen.getByRole("group", { name: /aprobación de la evaluación propuesta/i })).toBeTruthy();
    expect(screen.queryByText(/__DOCKING_PROPOSAL__/)).toBeNull();
    expect(screen.getAllByText(/todavía NO lanzada/i).length).toBeGreaterThan(0);
  });

  it("mientras el mensaje se escribe no hay tarjeta que aprobar", () => {
    render(
      <ChatMessage message={{ id: "1", role: "assistant", content: texto } as never} isStreaming />,
    );
    expect(screen.queryByRole("group", { name: /aprobación/i })).toBeNull();
  });

  it("un mensaje del usuario con el marcador no genera tarjeta", () => {
    render(
      <ChatMessage message={{ id: "1", role: "user", content: texto } as never} isStreaming={false} />,
    );
    expect(screen.queryByRole("group", { name: /aprobación/i })).toBeNull();
  });

  it("el marcador casa con el que escribe el backend", () => {
    const coincide = texto.match(MARCADOR_DE_PROPUESTA);
    expect(coincide?.[1]).toBe(ID);
    expect(coincide?.[2]).toBe(HASH);
  });
});

describe("los textos existen en los dos idiomas y no coinciden", () => {
  const claves = [
    "ia_propuesta_grupo", "ia_propuesta_aprobar", "ia_propuesta_cancelar",
    "ia_propuesta_aprobando", "ia_propuesta_nota", "ia_propuesta_lanzada",
    "ia_propuesta_cancelada", "ia_propuesta_ya_no_pendiente", "ia_propuesta_error",
  ];
  it.each(claves)("%s", (clave) => {
    expect(TRANSLATIONS.es[clave], `falta en es`).toBeTruthy();
    expect(TRANSLATIONS.en[clave], `falta en en`).toBeTruthy();
    expect(TRANSLATIONS.es[clave]).not.toBe(TRANSLATIONS.en[clave]);
  });
});
