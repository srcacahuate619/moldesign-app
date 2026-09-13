import { afterEach, describe, expect, it, vi } from "vitest";

import {
  RESULT_RECOVERY_TIMEOUT_MS,
  withRecoveryDeadline,
} from "../CaseEvaluationRunner";

describe("límite de recuperación de resultados", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("convierte una petición que nunca responde en un error accionable", async () => {
    vi.useFakeTimers();
    const never = new Promise<string>(() => undefined);
    const recovery = withRecoveryDeadline(never, "La lectura de prueba");
    const rejected = expect(recovery).rejects.toThrow(/excedió 15 segundos/i);

    await vi.advanceTimersByTimeAsync(RESULT_RECOVERY_TIMEOUT_MS);

    await rejected;
  });
});
