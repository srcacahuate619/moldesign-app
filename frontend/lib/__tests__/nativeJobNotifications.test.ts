import { describe, expect, it, vi } from "vitest";
import { createNativeJobDispatcher, openNativeJobDestination, registerNativeJobDestinationResolver, type NativeJobBridge, type NativeJobEvent, type NativeJobOptions } from "../nativeJobNotifications";

const terminal = (patch: Partial<NativeJobEvent> = {}): NativeJobEvent => ({
  id: "run:evaluation:A", ownerId: "owner-A", source: "evaluation", caseId: "case-A", taskId: "task-A", outcome: "completed", ...patch,
});
function setup(path = "/moldex") {
  let owner: string | null = "owner-A";
  let currentPath = path;
  let action: (token: string) => void = () => {};
  const send = vi.fn<NativeJobBridge["send"]>().mockResolvedValue(undefined);
  const restore = vi.fn<NativeJobBridge["restore"]>().mockResolvedValue(undefined);
  const bridge: NativeJobBridge = {
    listenAction: vi.fn(async cb => { action = cb; return vi.fn(); }),
    permissionGranted: vi.fn(async () => true),
    attention: vi.fn(async () => ({ focused: true, visible: true, minimized: false })),
    send, restore,
  };
  const data = new Map<string, string>();
  const options: NativeJobOptions = { getOwnerId: () => owner, translate: key => key,
    openDestination: vi.fn(async () => true), onOpenFailure: vi.fn(), pathname: () => currentPath,
    storage: { getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value); } },
  };
  const dispatcher = createNativeJobDispatcher(options, bridge);
  return { dispatcher, bridge, send, restore, options, data, click: (token: string) => action(token),
    setOwner: (id: string | null) => { owner = id; }, setPath: (value: string) => { currentPath = value; } };
}

describe("política nativa de trabajos", () => {
  it.each(["completed", "failed"] as const)("veta origen activo incluso en terminal %s y no lo encola al salir", async outcome => {
    const s = setup("/evaluation"); await s.dispatcher.start();
    expect(await s.dispatcher.handle(terminal({ outcome }))).toBe("origin-active");
    s.setPath("/moldex");
    expect(await s.dispatcher.handle(terminal({ outcome }))).toBe("duplicate");
    expect(s.send).not.toHaveBeenCalled();
  });

  it.each(["minimized", "unfocused", "other-area"] as const)("solicita fuera de atención: %s", async kind => {
    const s = setup(kind === "other-area" ? "/preparacion" : "/evaluation");
    if (kind === "minimized") vi.mocked(s.bridge.attention).mockResolvedValue({ focused: false, visible: true, minimized: true });
    if (kind === "unfocused") vi.mocked(s.bridge.attention).mockResolvedValue({ focused: false, visible: true, minimized: false });
    await s.dispatcher.start();
    expect(await s.dispatcher.handle(terminal())).toBe("requested");
    expect(s.send).toHaveBeenCalledOnce();
  });

  it("cancelación e históricos sólo conservan Actividad", async () => {
    const s = setup(); await s.dispatcher.start();
    expect(await s.dispatcher.handle(terminal({ outcome: "cancelled" }))).toBe("cancelled");
    expect(await s.dispatcher.handle(terminal({ recovered: true }))).toBe("historical");
    expect(s.send).not.toHaveBeenCalled();
  });

  it("sin permiso o con atención desconocida no solicita ni reintenta", async () => {
    const s = setup(); await s.dispatcher.start();
    vi.mocked(s.bridge.permissionGranted).mockResolvedValue(false);
    expect(await s.dispatcher.handle(terminal())).toBe("permission-denied");
    vi.mocked(s.bridge.permissionGranted).mockResolvedValue(true);
    vi.mocked(s.bridge.attention).mockRejectedValue(new Error("focus unavailable"));
    expect(await s.dispatcher.handle(terminal({ taskId: "task-B" }))).toBe("attention-unknown");
    expect(s.send).not.toHaveBeenCalled();
  });

  it("requiere identidad exacta y propietario actual antes de solicitar", async () => {
    const s = setup(); await s.dispatcher.start();
    expect(await s.dispatcher.handle(terminal({ ownerId: "owner-B" }))).toBe("wrong-owner");
    expect(await s.dispatcher.handle(terminal({ caseId: undefined }))).toBe("missing-identity");
    expect(await s.dispatcher.handle(terminal({ source: "batch", taskId: undefined, caseId: undefined }))).toBe("missing-identity");
    expect(s.send).not.toHaveBeenCalled();
  });

  it("registra el listener antes de emitir y consume sin cola los eventos durante el arranque", async () => {
    const s = setup();
    let ready!: (cleanup: () => void) => void;
    vi.mocked(s.bridge.listenAction).mockReturnValue(new Promise(resolve => { ready = resolve; }));
    const started = s.dispatcher.start();
    expect(await s.dispatcher.handle(terminal())).toBe("unavailable");
    ready(() => {}); await started;
    expect(await s.dispatcher.handle(terminal())).toBe("duplicate");
    expect(s.send).not.toHaveBeenCalled();
  });

  it("el contenido OS es genérico y sólo incluye un token opaco, nunca nombres ni rutas", async () => {
    const s = setup(); await s.dispatcher.start();
    await s.dispatcher.handle({ ...terminal(), title: "Nombre confidencial", message: "CCO receptor7E2Y D:/privado", params: { secret: "SMILES" } });
    const payload = s.send.mock.calls[0][0];
    expect(payload.body).toBe("nt_native_completed");
    expect(Object.keys(payload).sort()).toEqual(["body", "id", "token"]);
    expect(JSON.stringify(payload)).not.toMatch(/owner-A|case-A|task-A|confidencial|CCO|7E2Y|privado|SMILES/);
  });

  it("el clic restaura y abre sólo la identidad en memoria sin ejecutar cálculo", async () => {
    const s = setup(); await s.dispatcher.start(); await s.dispatcher.handle(terminal());
    s.click("token-ajeno"); expect(s.restore).not.toHaveBeenCalled();
    s.click(s.send.mock.calls[0][0].token);
    await vi.waitFor(() => expect(s.options.openDestination).toHaveBeenCalledWith({ ownerId: "owner-A", source: "evaluation", caseId: "case-A", taskId: "task-A" }));
    expect(s.restore.mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(s.options.openDestination).mock.invocationCallOrder[0]);
    s.click(s.send.mock.calls[0][0].token);
    expect(s.options.openDestination).toHaveBeenCalledOnce();
  });

  it("cambiar cuenta entre emisión y clic impide abrir la corrida anterior", async () => {
    const s = setup(); await s.dispatcher.start(); await s.dispatcher.handle(terminal());
    s.setOwner("owner-B"); s.click(s.send.mock.calls[0][0].token);
    expect(s.restore).not.toHaveBeenCalled(); expect(s.options.openDestination).not.toHaveBeenCalled();
  });

  it("si cambia cuenta al restaurar, tampoco navega", async () => {
    const s = setup(); await s.dispatcher.start(); await s.dispatcher.handle(terminal());
    s.restore.mockImplementation(async () => { s.setOwner("owner-B"); });
    s.click(s.send.mock.calls[0][0].token); await Promise.resolve(); await Promise.resolve();
    expect(s.options.openDestination).not.toHaveBeenCalled();
  });

  it("la persistencia sobrevive al remontaje y se separa por propietario", async () => {
    const s = setup(); await s.dispatcher.start(); await s.dispatcher.handle(terminal());
    const next = createNativeJobDispatcher(s.options, s.bridge); await next.start();
    expect(await next.handle(terminal())).toBe("duplicate");
    s.setOwner("owner-B");
    expect(await next.handle(terminal({ ownerId: "owner-B" }))).toBe("requested");
  });

  it("sin almacenamiento o tras fallo de solicitud no produce una tormenta de reintentos", async () => {
    const s = setup(); await s.dispatcher.start();
    s.send.mockRejectedValue(new Error("OS unavailable"));
    expect(await s.dispatcher.handle(terminal())).toBe("request-error");
    expect(await s.dispatcher.handle(terminal())).toBe("duplicate");
    const other = createNativeJobDispatcher({ ...s.options, storage: { getItem: () => { throw new Error("denied"); }, setItem: () => {} } }, s.bridge);
    await other.start(); expect(await other.handle(terminal())).toBe("storage-unavailable");
    expect(s.send).toHaveBeenCalledOnce();
  });

  it("Molcy y Lotes tienen origen propio y requieren job exacto", async () => {
    const s = setup("/evaluation"); await s.dispatcher.start();
    expect(await s.dispatcher.handle(terminal({ source: "batch", jobId: "batch-A" }))).toBe("requested");
    s.setPath("/molcy");
    expect(await s.dispatcher.handle(terminal({ source: "molcy", jobId: "video-A" }))).toBe("origin-active");
  });
});


describe("resolución del destino después del clic", () => {
  const destination = { ownerId: "owner-A", source: "evaluation" as const, caseId: "case-A", taskId: "task-A" };
  it("navegar no acredita el destino: requiere confirmación del workspace", async () => {
    const resolver = vi.fn(async () => false);
    const stop = registerNativeJobDestinationResolver("evaluation", resolver);
    const navigate = vi.fn();
    expect(await openNativeJobDestination(destination, { getOwnerId: () => "owner-A", navigate })).toBe(false);
    expect(navigate).toHaveBeenCalledWith("/evaluation");
    expect(resolver).toHaveBeenCalledWith(destination);
    stop();
  });
  it("espera al workspace que aún no estaba montado y selecciona la identidad exacta", async () => {
    const navigate = vi.fn();
    const open = openNativeJobDestination(destination, { getOwnerId: () => "owner-A", navigate });
    const resolver = vi.fn(async () => true);
    const stop = registerNativeJobDestinationResolver("evaluation", resolver);
    expect(await open).toBe(true);
    expect(resolver).toHaveBeenCalledWith(destination);
    stop();
  });
  it("un recurso inaccesible o un destino no resuelto devuelve false sin fallback a otro trabajo", async () => {
    expect(await openNativeJobDestination(destination, { getOwnerId: () => "owner-A", navigate: vi.fn(), timeoutMs: 1 })).toBe(false);
    const resolver = vi.fn(async () => { throw new Error("deleted"); });
    const stop = registerNativeJobDestinationResolver("evaluation", resolver);
    expect(await openNativeJobDestination(destination, { getOwnerId: () => "owner-A", navigate: vi.fn() })).toBe(false);
    stop();
  });
  it("la cuenta incorrecta no navega ni invoca un resolver", async () => {
    const navigate = vi.fn();
    expect(await openNativeJobDestination(destination, { getOwnerId: () => "owner-B", navigate })).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });
});
