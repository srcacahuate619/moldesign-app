import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSpeechRecognition } from "../useSpeechRecognition";

describe("useSpeechRecognition", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("no recurre a Web Speech cuando Whisper local no está disponible", async () => {
    const constructorWeb = vi.fn();
    Object.defineProperty(window, "SpeechRecognition", {
      configurable: true,
      value: constructorWeb,
    });
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ available: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useSpeechRecognition());

    await waitFor(() => expect(result.current.state).toBe("unsupported"));
    expect(result.current.mode).toBe("unsupported");
    expect(result.current.isSupported).toBe(false);
    result.current.startListening();
    expect(constructorWeb).not.toHaveBeenCalled();
  });
});
